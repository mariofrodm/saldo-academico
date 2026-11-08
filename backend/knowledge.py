"""Load versioned agent guidance and index educational Markdown in PostgreSQL.

Instructions are trusted application files. Retrieved documents remain data,
including administrator edits; they cannot grant tool or database permissions.
"""
import json
import re
from pathlib import Path
from .db import db, one

DOCS = Path(__file__).resolve().parent / 'agent_docs'
SOURCE_PREFIX = 'Saldo · agentes/'


def instructions():
    paths = sorted(DOCS.glob('00*.md'))
    return '\n'.join(path.read_text(encoding='utf-8') for path in paths)


def documents(directory=DOCS):
    for path in sorted(directory.glob('*.md')):
        if path.name.startswith('00'):
            continue
        content = path.read_text(encoding='utf-8')
        title = next((line[2:].strip() for line in content.splitlines() if line.startswith('# ')), path.stem)
        sections = re.split(r'(?m)^## ', content)
        for section_number, section in enumerate(sections):
            section = section.strip()
            if not section:
                continue
            heading = section.splitlines()[0].removeprefix('# ').strip()
            # Complete paragraphs, bounded independently; never truncate JSON/tool results.
            chunks, current = [], ''
            for paragraph in re.split(r'\n\s*\n', section):
                while len(paragraph) > 1800:
                    split_at = paragraph.rfind(' ', 0, 1800)
                    split_at = split_at if split_at > 0 else 1800
                    if current:
                        chunks.append(current)
                        current = ''
                    chunks.append(paragraph[:split_at])
                    paragraph = paragraph[split_at:].lstrip()
                if len(current) + len(paragraph) + 2 > 1800:
                    chunks.append(current)
                    current = ''
                current += ('\n\n' if current else '') + paragraph
            if current:
                chunks.append(current)
            for part, body in enumerate(chunks):
                yield {'title': (title + ' · ' + heading)[:160], 'body': body,
                       'source': f'{SOURCE_PREFIX}{path.name}#{section_number}.{part}'}


def sync_knowledge(conn):
    """Idempotent explicit import; preserve independently managed knowledge."""
    sources = []
    for document in documents():
        sources.append(document['source'])
        existing = one(conn, 'SELECT id FROM knowledge WHERE source=%s ORDER BY id LIMIT 1', (document['source'],))
        if existing:
            conn.execute('UPDATE knowledge SET title=%s,body=%s,active=true WHERE id=%s',
                         (document['title'], document['body'], existing['id']))
        else:
            conn.execute('INSERT INTO knowledge(title,body,source) VALUES(%s,%s,%s)',
                         (document['title'], document['body'], document['source']))
    if sources:
        conn.execute('UPDATE knowledge SET active=false WHERE starts_with(source,%s) AND NOT (source=ANY(%s))',
                     (SOURCE_PREFIX, sources))
    return {'indexed_fragments': len(sources), 'directory': str(DOCS)}


if __name__ == '__main__':
    with db() as conn:
        print(json.dumps(sync_knowledge(conn), ensure_ascii=False))
