"""Exact, inexpensive wording for a narrow class of verified comparisons.

Open-ended interpretation and advice stay with the model. This path only uses
the two categories and differences that the read-only backend already computed.
"""
import calendar
import re
import unicodedata
from datetime import date
from decimal import Decimal, InvalidOperation

MONTHS = ('enero','febrero','marzo','abril','mayo','junio','julio','agosto',
          'septiembre','octubre','noviembre','diciembre')


def comparison_answer(prompt, facts, today):
    if len(facts) != 1 or facts[0][0] != 'compare_spending':
        return None
    text = ''.join(c for c in unicodedata.normalize('NFD',prompt.casefold()) if not unicodedata.combining(c))
    if not re.search(r'\b(mas|menos|diferencia|igual|compara\w*)\b',text):
        return None
    # Only a single, narrow comparison is fully covered by this wording. A
    # second question, total/count/percentage or joined request must continue
    # through the model/tool path rather than silently losing part of the ask.
    if text.count('?') > 1 or re.search(r'\b(total|totales|porcentaje|porcentajes|proporcion|proporciones|cuantos pagos|cuantas veces|cantidad de pagos|numero de pagos)\b', text):
        return None
    joined = re.search(r'\b(?:y|ademas|tambien)\s+(?:cuanto\w*|cual\w*|que|por que|como|donde|cuando)\b', text)
    if joined and re.search(r'\w', text[:joined.start()]):
        return None
    if re.search(r'\b(?:mas|menos|igual)\s+(?:de|a|que)\s*(?:q(?=\s*\d)|gtq(?=\s*\d)|\d)',text):
        return None  # A threshold is not a comparison between the categories.
    if any(word in text for word in ('por que','aconsej','recom','ahorr','reduc','puedo','conviene','hacer','interes','plan')):
        return None
    result = facts[0][2]
    items = result.get('items',[])
    if len(items) != 2 or 'difference_gtq' not in result:
        return None
    start,end = (date.fromisoformat(result['period'][key]) for key in ('start','end'))
    if end > today:
        return None
    if start.day == 1 and start.year == end.year and start.month == end.month and end.day == calendar.monthrange(end.year,end.month)[1]:
        period = f'en {MONTHS[start.month-1]} de {start.year}'
    else:
        period = f'del {start.day}/{start.month}/{start.year} al {end.day}/{end.month}/{end.year}'
    def amount(value):
        return 'Q'+format(Decimal(value),',.2f')
    a,b=items
    if 'diferencia' in text:
        difference=amount(result['difference_gtq'])
        if result['equal']:
            return f'No hubo diferencia {period}: pagaste {amount(a["amount"])} en cada categoría.'
        return f'La diferencia fue de {difference} {period}; pagaste más en {result["higher_category"]}.'
    if result['equal']:
        return f'Pagaste lo mismo {period}: {amount(a["amount"])} en {a["category"]} y en {b["category"]}.'
    wanted = (b if a['category'] == result['higher_category'] else a) if re.search(r'\bmenos\b',text) else next(item for item in items if item['category']==result['higher_category'])
    other = b if wanted is a else a
    word = 'menos' if re.search(r'\bmenos\b',text) else 'más'
    return f'Pagaste {word} en {wanted["category"]} {period}: {amount(wanted["amount"])}, frente a {amount(other["amount"])} en {other["category"]}.'


def spending_answer(prompt, facts, today):
    """Format only a single authenticated ranking; interpretation stays with AI."""
    text = ''.join(c for c in unicodedata.normalize('NFD', prompt.casefold()) if not unicodedata.combining(c))
    months = '|'.join(MONTHS)
    period_words = rf'(?:{months})(?:\s+(?:de\s+)?\d{{4}})?|este mes|ese mes|el mes pasado'
    if not re.fullmatch(rf'[¿?¡!\s]*en que gaste mas(?:\s+(?:en\s+)?(?:{period_words}))?[?.!\s]*', text):
        return None
    if len(facts) != 1 or facts[0][0] != 'spending_breakdown':
        return None
    _, args, result = facts[0]
    if (not isinstance(result, dict) or result.get('source_id') != 'SGASTOS'
            or result.get('currency') != 'GTQ' or result.get('error') or result.get('available') is False):
        return None
    try:
        start, end = (date.fromisoformat(result['period'][key]) for key in ('start', 'end'))
        if start > end or start > today or args != {'start': start.isoformat(), 'end': end.isoformat()}:
            return None
        named = re.search(rf'\b({months})\b(?:\s+(?:de\s+)?(\d{{4}}))?', text)
        if named and (start.month != end.month or start.year != end.year
                      or start.month != MONTHS.index(named.group(1))+1
                      or named.group(2) and start.year != int(named.group(2))):
            return None
        if 'este mes' in text and (start.year, start.month) != (today.year, today.month):
            return None
        previous_month = (today.year-1, 12) if today.month == 1 else (today.year, today.month-1)
        if 'el mes pasado' in text and (start.year, start.month) != previous_month:
            return None
        items = result['items']
        total = Decimal(result['total_expense'])
        if not total.is_finite() or total < 0:
            return None
        if not items:
            return 'No hay pagos de gastos registrados para ese período.' if total == 0 else None
        top = items[0]
        amount = Decimal(top['amount'])
        if not amount.is_finite() or amount < 0 or amount > total or not isinstance(top['category'], str):
            return None
        if any(Decimal(item['amount']) > amount for item in items[1:]):
            return None
        period = (f'en {MONTHS[start.month-1]} de {start.year}' if start.day == 1 and start.year == end.year
                  and start.month == end.month and end.day == calendar.monthrange(end.year, end.month)[1]
                  else f'del {start.day}/{start.month}/{start.year} al {end.day}/{end.month}/{end.year}')
        tied = any(Decimal(item['amount']) == amount for item in items[1:])
        opening = f'{top["category"]} aparece entre las categorías con mayor gasto' if tied else f'La categoría con mayor gasto fue {top["category"]}'
        answer = f'{opening} {period}: Q{amount:,.2f}.'
        percentage = top.get('expense_percent')
        if percentage is not None:
            percentage = Decimal(percentage)
            if not percentage.is_finite() or percentage < 0 or percentage > 100:
                return None
            answer += f' Representa el {percentage:.2f}% de los pagos registrados.'
        if end > today:
            answer += ' El período aún no termina; este resumen corresponde a lo registrado para esas fechas.'
        return answer
    except (KeyError, TypeError, ValueError, InvalidOperation):
        return None
