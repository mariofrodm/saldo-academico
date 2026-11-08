"""Conservative wording for a narrow, verified savings-priority question.

Only the authenticated caller's fresh planning query may supply facts. This
module does not fetch records, calculate a budget, choose a goal or allocate it.
"""
import re
import unicodedata
from collections.abc import Mapping
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation


MONTHS = ('enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto',
          'septiembre', 'octubre', 'noviembre', 'diciembre')
PRIORITY = re.compile(
    r'(?:y\s+)?(?:por\s+)?cual(?:\s+meta|\s+de\s+(?:mis|las|estas)\s+metas)?\s+'
    r'(?:(?:deberia|debo|puedo)\s+)?(?:comienzo|comenzar|empiezo|empezar|priorizo|priorizar)'
    r'(?:\s+primero)?')
GOALS = r'(?:todas\s+)?mis\s+metas(?:\s+de\s+ahorro)?'
CONTEXT = r'(?:,?\s+(?:dado|segun)\s+mi\s+(?:contexto|situacion)(?:\s+actual)?)?'
PLANNING_QUESTIONS = (
    re.compile(r'como(?:\s+(?:puedo|deberia|debo))?\s+(?:priorizo|priorizar|ordeno|ordenar)\s+'+GOALS+CONTEXT),
    re.compile(r'como(?:\s+(?:puedo|deberia|debo))?\s+(?:cumplir|alcanzar)\s+'+GOALS+CONTEXT),
    re.compile(r'que(?:\s+(?:deberia|debo|puedo))?\s+hacer\s+para\s+(?:cumplir|alcanzar)\s+'+GOALS+CONTEXT),
)


def _amount(value):
    if isinstance(value, bool) or not isinstance(value, (str, int, Decimal)):
        return None
    try:
        result = Decimal(str(value))
        if not result.is_finite() or result != result.quantize(Decimal('.01')):
            return None
        return result
    except InvalidOperation:
        return None


def _count(value):
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def planning_answer(prompt, prefetched, today):
    if not isinstance(prompt, str) or not isinstance(today, date):
        return None
    text = ''.join(char for char in unicodedata.normalize('NFD', prompt.casefold())
                   if not unicodedata.combining(char))
    text = text.strip().strip('¿?¡!. ').strip()
    if not PRIORITY.fullmatch(text) and not any(pattern.fullmatch(text) for pattern in PLANNING_QUESTIONS):
        return None
    if not isinstance(prefetched, (list, tuple)) or len(prefetched) != 1:
        return None
    entry = prefetched[0]
    if not isinstance(entry, (list, tuple)) or len(entry) != 3:
        return None
    name, arguments, facts = entry
    if name != 'planning_snapshot' or arguments != {} or not isinstance(facts, Mapping):
        return None
    if (facts.get('source_id') != 'SPLAN' or facts.get('currency') != 'GTQ'
            or facts.get('as_of') != today.isoformat()):
        return None
    if not _count(facts.get('active_future_goal_count')) or not facts['active_future_goal_count']:
        return None
    if not _count(facts.get('expired_active_goal_count')):
        return None
    closed = facts.get('last_closed_month')
    if not isinstance(closed, Mapping):
        return None
    try:
        end = today.replace(day=1)-timedelta(days=1)
    except OverflowError:
        return None
    start = end.replace(day=1)
    if closed.get('from') != start.isoformat() or closed.get('to') != end.isoformat():
        return None
    available = _amount(closed.get('available'))
    income, expense, savings = (_amount(closed.get(key)) for key in ('income', 'expense', 'net_savings'))
    required = _amount(facts.get('active_future_required'))
    margin, gap = (_amount(facts.get(key)) for key in ('historical_margin', 'affordability_gap'))
    if any(value is None for value in (available, income, expense, savings, required, margin, gap)):
        return None
    # An empty ledger is missing context, not proof of a sustainable zero budget.
    if not any(value != 0 for value in (income, expense, savings)):
        return None
    if (required <= 0 or margin < 0 or gap <= 0 or required <= margin
            or 'verified_affordable_contribution' not in facts
            or facts['verified_affordable_contribution'] is not None):
        return None
    if (available >= 0 and margin != available) or (available < 0 and margin != 0):
        return None

    def money(value):
        return 'Q'+format(value, ',.2f')

    period = f'{MONTHS[start.month-1]} de {start.year}'
    balance = (f'el margen registrado fue negativo: {money(available)}' if available < 0
               else f'registraste un margen de {money(available)}')
    first = (f'Empezaría por ajustar el plan antes de comprometer un aporte. En {period} {balance}; '
             f'es el flujo de ese mes cerrado, no tu saldo actual. Tus metas activas que aún están '
             f'dentro de plazo requieren {money(required)} al mes según sus fechas. Ese margen histórico '
             'no cubre todos esos aportes a la vez.')
    second = ('Revisa primero tus gastos esenciales y próximos pagos, y después los plazos y el orden de tus metas. ')
    if facts['expired_active_goal_count']:
        second += 'La meta vencida necesita revisar su fecha o su prioridad; no es una deuda que debas pagar por haber vencido. '
    second += '¿Cuál de tus objetivos es esencial para ti ahora?'
    return first+'\n\n'+second
