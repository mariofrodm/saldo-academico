"""Plain Spanish presentation, without interpreting model-generated HTML.

This layer changes notation only. It never calculates financial facts or fills
missing values. The original tools and sources remain in the audit history.
"""
import re
from decimal import Decimal, InvalidOperation

# Restrict this namespace to actual application sources. [SI], [SIN INTERESES]
# and other user annotations are ordinary text, not citations to remove.
SOURCE_CODE = r'(?:D\d+|M\d+|S(?:FIN|GASTOS|COMPARA|REC|PEND|DEUDA|MICRO|ESC|METAS|PLAN|DIAG|G\d+))'
REFERENCES = re.compile(r'\['+SOURCE_CODE+r'\]')
# Bare codes are metadata only inside an explicit source annotation. A literal
# code elsewhere in the prose may describe a record and must not disappear.
BARE_REFERENCES = re.compile(r'\b'+SOURCE_CODE+r'\b')
LABELS = {'spending_breakdown': 'pagos por categoría', 'debt_snapshot': 'deudas registradas',
          'compare_spending': 'comparación de pagos por categoría',
          'goal_snapshot': 'metas de ahorro', 'financial_overview': 'resumen financiero',
          'planning_snapshot': 'planificación de metas',
          'financial_diagnosis': 'panorama financiero', 'obligations_snapshot': 'compromisos pendientes',
          'small_expenses': 'pagos pequeños', 'recurring_snapshot': 'compromisos recurrentes',
          'savings_plan': 'plan de ahorro', 'budget_scenario': 'escenario de presupuesto',
          'financial_summary': 'resumen financiero', 'simulate_goal': 'proyección de ahorro',
          'exchange_rate': 'tipo de cambio', 'source_id': 'referencia'}


def _integer(raw, separator=None):
    """Accept a whole number or consistently grouped triples, never guess."""
    if re.fullmatch(r'-?\d+', raw):
        return raw
    if re.fullmatch(r'-?\d{1,3}(?:[ \u202f\u00a0]+\d{3})+', raw):
        return re.sub(r'[ \u202f\u00a0]', '', raw)
    if separator and re.fullmatch(r'-?\d{1,3}(?:'+re.escape(separator)+r'\d{3})+', raw):
        return raw.replace(separator, '')
    return None


def _money(match):
    raw = match.group('amount').strip()
    # A final two-digit decimal is unambiguous only if its whole part is valid.
    # Invalid/mixed groupings remain exactly as supplied instead of changing value.
    decimal = re.search(r'([.,])(\d{2})$', raw)
    if decimal:
        whole = _integer(raw[:decimal.start()].strip(), ',' if decimal.group(1) == '.' else '.')
        numeric = whole+'.'+decimal.group(2) if whole is not None else None
    else:
        # A bare dot with three digits could be decimal or grouping: preserve it.
        numeric = _integer(raw, ',')
    if numeric is None:
        return match.group(0)
    try:
        return 'Q' + format(Decimal(numeric), ',.2f')
    except InvalidOperation:
        return match.group(0)


def _cells(line):
    line = line.strip()
    if line.startswith('|') and line.endswith('|'):
        return [cell.strip() for cell in line[1:-1].split('|')]
    return None


def _tables(lines):
    output, index = [], 0
    while index < len(lines):
        headers = _cells(lines[index])
        separator = _cells(lines[index+1]) if index+1 < len(lines) else None
        if not (headers and separator and len(headers) == len(separator)
                and all(re.fullmatch(r':?-{2,}:?', cell.replace(' ', '')) for cell in separator)):
            # A pipe-delimited sentence without a Markdown separator is not a
            # table. In particular, never discard its first line as a header.
            output.append(lines[index]); index += 1
            continue
        index += 2
        while index < len(lines) and (cells := _cells(lines[index])) is not None:
            index += 1
            if len(cells) != len(headers):
                output.append('; '.join(cells))
                continue
            fields = [(position, head, value) for position, (head, value) in enumerate(zip(headers, cells))
                      if head.casefold() not in ('id', 'identificador', 'código', 'codigo', 'source_id', 'source id', 'id de fuente')]
            title_field = next(((position, value) for position, head, value in fields if head.casefold() in
                                ('título', 'titulo', 'concepto', 'deuda', 'meta', 'categoría', 'categoria')), None)
            details = []
            for position, head, value in fields:
                if title_field is not None and position == title_field[0]:
                    continue
                if '(GTQ)' in head and re.fullmatch(r'-?[\d.,\u202f\u00a0 ]+', value):
                    value = 'Q' + value
                details.append(head.replace('(GTQ)', '').strip().lower() + ': ' + value)
            if fields:
                output.append(((title_field[1]+': ') if title_field else '')+'; '.join(details)+'.')
                output.append('')
    return output


def _metadata_only(value):
    value = REFERENCES.sub('', value)
    value = BARE_REFERENCES.sub('', value)
    for name in LABELS:
        value = re.sub(r'\b'+re.escape(name)+r'\b', '', value)
    value = re.sub(r'\b\d{4}-\d{2}-\d{2}\b', '', value)
    value = re.sub(r'https?://\S+', '', value)
    value = re.sub(r'\b(?:y|e|and)\b', '', value, flags=re.I)
    return not re.search(r'\w', value)


def _source_notation(line):
    marker = re.search(r'\b(?:fuentes?|sources?|referencias?|herramientas?\s+consultadas)\s*:', line, re.I)
    if not marker:
        return line
    prefix, payload = line[:marker.start()].rstrip(), line[marker.end():].strip()
    if _metadata_only(payload):
        return prefix
    if REFERENCES.search(payload) or BARE_REFERENCES.search(payload):
        # Remove the citation only. A qualifier following it ("no conocemos la
        # tasa", for example) must survive, including its negation and amounts.
        payload = REFERENCES.sub('', payload)
        payload = BARE_REFERENCES.sub('', payload)
        payload = re.sub(r'\(([^()]*)\)', lambda m: '' if _metadata_only(m.group(1)) else m.group(0), payload)
        return (prefix+' '+payload.strip()).strip()
    return line


def _list_marker(line):
    # A marker before a sentence is formatting. A sign before an amount,
    # mathematical operator or explicit identifier must keep its meaning.
    marker = re.match(r'^\s*(?:[-+*]\s+|[1-9]\d?[.)]\s+)(?=[^\W\d_])', line)
    if not marker:
        return line
    remaining = line[marker.end():]
    if re.match(r'(?:Q(?=\s*[+-]?\d)|GTQ(?=\s*[+-]?\d)|ID\b|identificador\b|c[oó]digo\b)', remaining, re.I):
        return line
    return remaining


def natural_text(text):
    text = str(text).replace('\r\n', '\n')
    lines = []
    for line in text.splitlines():
        if re.fullmatch(r'\s*(?:[-*_]\s*){3,}', line):
            continue
        if re.match(r'^\s*```', line):
            continue
        line = re.sub(r'^\s*#{1,6}\s+', '', line)
        # Keep mathematical comparisons such as "> Q500" intact.
        if not re.match(r'^\s*>\s*(?:Q\s*-?\d|GTQ\b|\$|[+\-]?\d)', line):
            line = re.sub(r'^\s*>\s*', '', line)
        line = re.sub(r'\*\*(?=\S)([^*\n]*?\S)\*\*|(?<!\w)__(?=\S)([^_\n]*?\S)__(?!\w)', lambda m: m.group(1) or m.group(2), line)
        # Spaces distinguish multiplication ("2 * 3") from emphasis ("*algo*").
        line = re.sub(r'(?<![\w*])\*(?=\S)([^*\n]*?\S)\*(?![\w*])', r'\1', line)
        line = re.sub(r'`([^`]+)`', r'\1', line)
        line = _list_marker(line)
        line = _source_notation(line)
        line = REFERENCES.sub('', line)
        lines.append(line.rstrip())
    text = '\n'.join(_tables(lines))
    for name, label in LABELS.items():
        text = re.sub(r'\b' + re.escape(name) + r'\b', label, text)
    # Accept the common model notations Q1 000 .00 and 550,00 GTQ.
    number = r'-?\d(?:[\d,.\u202f\u00a0 ]*\d)?'
    text = re.sub(r'(?<!\w)Q\s*(?P<amount>' + number + ')', _money, text)
    text = re.sub(r'(?<![\w.,])(?P<amount>' + number + r')\s*(?:GTQ|Q)\b', _money, text)
    text = re.sub(r'[ \t]+\n', '\n', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()
