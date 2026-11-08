"""Exact wording for a simple recorded-margin question, never an allocation."""
import calendar
import re
import unicodedata
from collections.abc import Mapping
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation


MONTHS = ('enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto',
          'septiembre', 'octubre', 'noviembre', 'diciembre')
NAMED = r'(?:'+'|'.join(MONTHS)+r')(?:\s+(?:de\s+)?\d{4})?'
INTERVAL = r'(?:del\s+)?\d{4}-\d{2}-\d{2}\s+al\s+\d{4}-\d{2}-\d{2}'
PERIOD = r'(?:(?:en|de|del)\s+)?'+NAMED+r'|'+INTERVAL+r'|este mes|el mes pasado|ese mes'
PREFIX = (r'(?:(?:cuanto|que)\s+(?:margen|disponible|sobrante)(?:\s+(?:me\s+)?(?:dejo|queda|quedo|tuve|tengo))?'
          r'|cuanto\s+me\s+(?:queda|quedo)(?:\s+de)?\s+(?:margen|disponible|sobrante)'
          r'|cual\s+(?:es|fue)\s+(?:mi|el)\s+(?:margen|disponible|sobrante))')
PURPOSE = r'(?:ahorrar(?:\s+o\s+pagar\s+(?:(?:mi|mis|la|las)\s+)?deudas?)?|pagar\s+(?:(?:mi|mis|la|las)\s+)?deudas?)'
QUESTION = re.compile(PREFIX+r'(?:\s+(?P<period>'+PERIOD+r'))?(?:\s+para\s+'+PURPOSE+r')?')


def _money(value):
    if isinstance(value, bool) or not isinstance(value, (str, int, Decimal)):
        return None
    try:
        number = Decimal(str(value))
        return number if number.is_finite() and number == number.quantize(Decimal('.01')) else None
    except InvalidOperation:
        return None


def _facts(prefetched, today):
    if not isinstance(today, date) or not isinstance(prefetched, (list, tuple)) or len(prefetched) != 1:
        return None
    entry = prefetched[0]
    if not isinstance(entry, (list, tuple)) or len(entry) != 3:
        return None
    name, args, facts = entry
    if name != 'financial_overview' or not isinstance(args, Mapping) or not isinstance(facts, Mapping):
        return None
    if facts.get('source_id') != 'SFIN' or facts.get('currency') != 'GTQ' or facts.get('error') or facts.get('status') in ('error', 'failed'):
        return None
    current, period = facts.get('current'), facts.get('period')
    if not isinstance(current, Mapping) or not isinstance(period, Mapping) or current.get('currency') != 'GTQ':
        return None
    try:
        start, end = (date.fromisoformat(period[key]) for key in ('start', 'end'))
    except (KeyError, TypeError, ValueError):
        return None
    if (start > end or end > today or (end-start).days >= 366
            or current.get('from') != start.isoformat() or current.get('to') != end.isoformat()
            or set(args) != {'start', 'end'} or args['start'] != start.isoformat() or args['end'] != end.isoformat()):
        return None
    values = {key: _money(current.get(key)) for key in ('income', 'expense', 'net_savings', 'available')}
    if any(value is None for value in values.values()) or values['income'] < 0 or values['expense'] < 0:
        return None
    if values['available'] != values['income']-values['expense']-values['net_savings']:
        return None
    return start, end, values


def _matches_period(text, start, end, today):
    if text is None or text == 'ese mes':
        return True  # The caller resolves current/verified conversational scope.
    if text == 'este mes':
        return start == today.replace(day=1) and end == today
    if text == 'el mes pasado':
        try:
            last = today.replace(day=1)-timedelta(days=1)
        except OverflowError:
            return False
        return start == last.replace(day=1) and end == last
    dates = re.findall(r'\d{4}-\d{2}-\d{2}', text)
    if dates:
        return dates == [start.isoformat(), end.isoformat()]
    named = re.fullmatch(r'(?:(?:en|de|del)\s+)?(?P<month>'+'|'.join(MONTHS)+r')(?:\s+(?:de\s+)?(?P<year>\d{4}))?', text)
    if not named:
        return False
    month = MONTHS.index(named['month'])+1
    return (start.month == end.month == month and start.year == end.year
            and (not named['year'] or int(named['year']) == start.year)
            and start.day == 1 and end.day == calendar.monthrange(end.year, month)[1])


def _summary(start, end, values, fallback=False):
    def money(number):
        return 'Q'+format(number, ',.2f')
    if start.day == 1 and start.year == end.year and start.month == end.month and end.day == calendar.monthrange(end.year, end.month)[1]:
        period = f'en {MONTHS[start.month-1]} de {start.year}'
    else:
        period = f'del {start.day:02}/{start.month:02}/{start.year} al {end.day:02}/{end.month:02}/{end.year}'
    opening = 'Como referencia, este es un resumen de lo registrado: ' if fallback else ''
    text = (f'{opening}{period} registraste {money(values["income"])} de ingresos cobrados, '
            f'{money(values["expense"])} de pagos y {money(values["net_savings"])} de ahorro neto. '
            f'El margen registrado fue {money(values["available"])}. '
            'Es flujo de ese período, no tu saldo bancario ni un importe confirmado para ahorrar o pagar deuda; '
            'antes de comprometerlo hay que revisar gastos esenciales y pagos pendientes.')
    return text[0].upper()+text[1:]


def budget_answer(prompt, prefetched, today):
    if not isinstance(prompt, str):
        return None
    text = ''.join(char for char in unicodedata.normalize('NFD', prompt.casefold())
                   if not unicodedata.combining(char)).strip().strip('¿?¡!. ').strip()
    match = QUESTION.fullmatch(text)
    facts = _facts(prefetched, today) if match else None
    if facts is None:
        return None
    start, end, values = facts
    return _summary(start, end, values) if _matches_period(match['period'], start, end, today) else None


def overview_fallback(prefetched, today):
    facts = _facts(prefetched, today)
    return _summary(*facts, fallback=True) if facts is not None else None
