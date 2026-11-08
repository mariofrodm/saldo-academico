"""Explicit local cleanup of presentation labels; financial records stay intact.

``python -m backend.labels`` previews counts without writing. Use ``--apply``
after taking a private backup. This is deliberately not a startup migration.
"""
import argparse
import json
import os
import re

from .db import db, many, one
from .demo import scenario_user

VERSION = 'labels_cleanup_v1'
LEGACY_SOURCE = 'Guía educativa interna del prototipo académico'
KNOWN_USERS = {'demo@example.test': 'Ana', 'admin@example.test': 'Administración',
               'bi@example.test': 'Lectura de reportes'}
REFERENCE = re.compile(
    r'\b(?:datos\s+(?:fictici[oa]s?|sint[eé]tic[oa]s?|de\s+pruebas?)|'
    r'de\s+pruebas?|de\s+demostraci[oó]n|acad[eé]mic[oa]s?|fictici[oa]s?|'
    r'demostraci[oó]n|demostrativ[oa]s?|demo|prototipos?|pruebas?|testing|test)\b',
    re.IGNORECASE)


def clean_label(value, fallback='Registro'):
    if not REFERENCE.search(value):
        return value
    value = re.sub(r'\bcliente\s+fictici[oa]\b', 'cliente independiente', value, flags=re.IGNORECASE)
    value = REFERENCE.sub('', value)
    value = re.sub(r'\(\s*\)|\[\s*\]', '', value)
    value = re.sub(r'\s+', ' ', value).strip()
    value = re.sub(r'\s*([·|:;,])\s*(?:[·|:;,]\s*)+', r' \1 ', value)
    value = value.strip(' ·|:;,—–-')
    value = re.sub(r'(?:\s+(?:de|del|para|por|el|la|los|las))+$', '', value, flags=re.IGNORECASE)
    return value.strip(' ·|:;,—–-') or fallback


def cleanup_labels(conn, user_id=None, dry_run=False):
    """Change only names/titles in the established local account and old guide.

    Audit markers and authentication identifiers are never renamed. Repeated
    runs are harmless, and a later newly added label can be cleaned on demand.
    """
    if os.getenv('APP_ENV') != 'local':
        raise ValueError('La limpieza exige APP_ENV=local explícito.')
    with conn.transaction():
        user = scenario_user(conn, user_id)
        uid = user['id']
        existing_marker = one(conn, 'SELECT id FROM audit WHERE actor_id=%s AND action=%s AND entity_id=%s',
                              (uid, VERSION, str(uid)))
        changes = []
        counts = {table: 0 for table in ('users', 'categories', 'obligations', 'goals', 'recurring', 'knowledge')}

        def plan(table, ident, columns):
            changes.append((table, ident, columns))
            counts[table] += 1

        for row in many(conn, 'SELECT id,email,name FROM users WHERE email=ANY(%s) ORDER BY id FOR UPDATE',
                        (list(KNOWN_USERS),)):
            name = clean_label(row['name'], KNOWN_USERS[row['email']])
            if row['name'] != name:
                plan('users', row['id'], {'name': name})

        # Keep every category and its references. Resolve uniqueness without
        # merging, deleting or reclassifying any financial record.
        rows = many(conn, 'SELECT id,name,kind FROM categories WHERE user_id=%s ORDER BY id FOR UPDATE', (uid,))
        reserved = {(row['name'], row['kind']): row['id'] for row in rows}
        for row in rows:
            name = clean_label(row['name'], 'Categoría')
            if name == row['name']:
                continue
            base, suffix = name, 2
            while (name, row['kind']) in reserved and reserved[(name, row['kind'])] != row['id']:
                name = f'{base} ({suffix})'
                suffix += 1
            del reserved[(row['name'], row['kind'])]
            reserved[(name, row['kind'])] = row['id']
            plan('categories', row['id'], {'name': name})

        for table, column in (('obligations', 'title'), ('goals', 'name'), ('recurring', 'title')):
            for row in many(conn, f'SELECT id,{column} FROM {table} WHERE user_id=%s ORDER BY id FOR UPDATE', (uid,)):
                name = clean_label(row[column])
                if name != row[column]:
                    plan(table, row['id'], {column: name})

        # Only the original built-in guide: independently managed/global corpus
        # and historical agent responses are outside this migration's scope.
        for row in many(conn, 'SELECT id,title,body,source FROM knowledge WHERE source=%s FOR UPDATE', (LEGACY_SOURCE,)):
            columns = {'source': 'Guía de finanzas personales'}
            for column in ('title', 'body'):
                value = clean_label(row[column])
                if value != row[column]:
                    columns[column] = value
            plan('knowledge', row['id'], columns)

        if not dry_run:
            for table, ident, columns in changes:
                # Table/column identifiers originate exclusively in the fixed
                # plan above; user-provided text is always a bound parameter.
                assignments = ','.join(f'{column}=%s' for column in columns)
                conn.execute(f'UPDATE {table} SET {assignments} WHERE id=%s', (*columns.values(), ident))
            if not existing_marker:
                conn.execute('INSERT INTO audit(actor_id,action,entity,entity_id) VALUES(%s,%s,%s,%s)',
                             (uid, VERSION, 'presentation_labels', str(uid)))
        return {'action': VERSION, 'user_id': uid, 'dry_run': dry_run,
                'already_applied': bool(existing_marker), 'changed_rows': counts,
                'total_changed_rows': sum(counts.values()),
                'preserved': ['IDs', 'correos', 'credenciales', 'importes', 'fechas', 'estados',
                              'relaciones', 'cantidades de registros financieros', 'historial', 'cuotas de IA']}


def main():
    parser = argparse.ArgumentParser(description='Normaliza nombres visibles de la cuenta local inicializada.')
    parser.add_argument('--apply', action='store_true', help='Aplica los cambios; sin esta opción solo muestra cantidades.')
    args = parser.parse_args()
    with db() as conn:
        result = cleanup_labels(conn, dry_run=not args.apply)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
