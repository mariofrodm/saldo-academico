"""Exact, inexpensive wording for a narrow class of verified comparisons.

Open-ended interpretation and advice stay with the model. This path only uses
the two categories and differences that the read-only backend already computed.
"""
import calendar
import re
import unicodedata
from datetime import date
from decimal import Decimal

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
