"""Narrow goal status/clarification answers from fresh authenticated facts."""
import re
import unicodedata
from collections.abc import Mapping
from datetime import date
from decimal import Decimal, InvalidOperation


def _normalized(text):
    return ''.join(char for char in unicodedata.normalize('NFD', text.casefold())
                   if not unicodedata.combining(char)).strip().strip('¿?¡!. ').strip()


def _money(value):
    if isinstance(value, bool) or not isinstance(value, (str, int, Decimal)):
        return None
    try:
        number = Decimal(str(value))
        if not number.is_finite() or number < 0 or number != number.quantize(Decimal('.01')):
            return None
        return 'Q'+format(number, ',.2f')
    except InvalidOperation:
        return None


def _fresh(prefetched, name, source, today):
    if not isinstance(prefetched, (list, tuple)) or len(prefetched) != 1:
        return None
    entry = prefetched[0]
    if not isinstance(entry, (list, tuple)) or len(entry) != 3:
        return None
    tool, arguments, result = entry
    if tool != name or arguments != {} or not isinstance(result, Mapping):
        return None
    if result.get('source_id') != source or result.get('currency') != 'GTQ' or result.get('as_of') != today.isoformat():
        return None
    return result


def _listing(facts):
    items, total, totals = facts.get('items'), facts.get('total_count'), facts.get('totals')
    if (not isinstance(items, list) or not isinstance(total, int) or isinstance(total, bool)
            or total < 0 or not isinstance(totals, Mapping) or not isinstance(facts.get('has_more'), bool)):
        return None
    if total == 0:
        return 'No hay metas registradas todavía.' if not items else None
    keys = ('in_progress_count', 'completed_active_count', 'expired_active_count', 'inactive_count')
    counts = [totals.get(key) for key in keys]
    if any(not isinstance(value, int) or isinstance(value, bool) or value < 0 for value in counts) or not items:
        return None
    registered = 'meta registrada' if total == 1 else 'metas registradas'
    completed = 'cumplida' if counts[1] == 1 else 'cumplidas'
    inactive = 'inactiva' if counts[3] == 1 else 'inactivas'
    paragraphs = [f'Tienes {total} {registered}: {counts[0]} en progreso, {counts[1]} {completed}, '
                  f'{counts[2]} con plazo vencido y {counts[3]} {inactive}.']
    if facts['has_more']:
        paragraphs[0] += ' Te muestro una parte de ellas; esos recuentos incluyen todas tus metas.'
    ongoing, other = [], []
    for item in items:
        if not isinstance(item, Mapping) or not isinstance(item.get('name'), str) or not item['name'].strip():
            return None
        balance, target = _money(item.get('balance')), _money(item.get('target'))
        try:
            deadline = date.fromisoformat(item['deadline'])
        except (KeyError, ValueError, TypeError):
            return None
        if balance is None or target is None:
            return None
        name, state = item['name'].strip(), item.get('state')
        when = f'{deadline.day:02}/{deadline.month:02}/{deadline.year}'
        if state == 'en progreso':
            ongoing.append(f'{name} lleva {balance} de {target}, con fecha objetivo {when}.')
        elif state == 'cumplida':
            other.append(f'La meta {name} ya está cumplida: {balance} de {target}.')
        elif state == 'vencida':
            other.append(f'La meta {name} tiene plazo vencido desde el {when}: registra {balance} de {target}. '
                         'Es la fecha de tu meta, no un pago exigible inmediato.')
        elif state == 'inactiva':
            other.append(f'La meta {name} está inactiva: {balance} de {target}, con fecha objetivo {when}.')
        else:
            return None
    if ongoing:
        paragraphs.append(' '.join(ongoing))
    if other:
        paragraphs.append(' '.join(other))
    return '\n\n'.join(paragraphs)


def _named_goal(text, items):
    """A user-mentioned name/ID blocks the generic clarification shortcut."""
    normalized = _normalized(text)
    stopwords = {'meta', 'metas', 'ahorro', 'ahorros', 'objetivo', 'objetivos', 'para', 'trabajo', 'actual',
                 'de', 'del', 'el', 'la', 'los', 'las', 'mis', 'mi', 'por', 'con', 'y'}
    words = [set(re.findall(r'\b\w{4,}\b', _normalized(item['name'])))-stopwords for item in items]
    for index, item in enumerate(items):
        if _normalized(item['name']) in normalized:
            return True
        distinctive = words[index]-set().union(*(group for position, group in enumerate(words) if position != index))
        if any(re.search(r'\b'+re.escape(word)+r'\b', normalized) for word in distinctive):
            return True
        ident = item.get('id')
        if isinstance(ident, int) and not isinstance(ident, bool):
            if re.search(r'(?:\b(?:meta|objetivo)(?:\s+(?:id|numero))?\s*#?\s*|\bid\s*|#)'+str(ident)+r'\b', normalized):
                return True
    return False


def goal_answer(prompt, prefetched, context, today):
    if not isinstance(prompt, str) or not isinstance(today, date):
        return None
    text = _normalized(prompt)
    if re.fullmatch(r'(?:que\s+metas(?:\s+de\s+ahorro)?\s+tengo(?:\s+y\s+como\s+voy)?|como\s+(?:van\s+mis\s+metas|voy\s+con\s+mis\s+metas)(?:\s+de\s+ahorro)?)', text):
        facts = _fresh(prefetched, 'goal_snapshot', 'SMETAS', today)
        return _listing(facts) if facts is not None else None
    contribution = re.fullmatch(r'(?:y\s+)?si\s+aporto\s+(?:q\s*)?(\d{1,13}(?:[.,]\d{1,2})?)\s+(?:al\s+mes|mensuales)', text)
    if not contribution or not isinstance(context, Mapping) or not isinstance(context.get('state'), Mapping):
        return None
    if context['state'].get('topic') != 'goals':
        return None
    amount = _money(contribution.group(1).replace(',', '.'))
    if amount is None or Decimal(contribution.group(1).replace(',', '.')) <= 0:
        return None
    facts = _fresh(prefetched, 'planning_snapshot', 'SPLAN', today)
    if facts is None or not isinstance(facts.get('goals'), Mapping):
        return None
    items = facts['goals'].get('items')
    if not isinstance(items, list) or any(not isinstance(item, Mapping) or not isinstance(item.get('name'), str) for item in items):
        return None
    eligible = [item for item in items if item.get('active') is True and item.get('state') == 'en progreso']
    if len(eligible) < 2:
        return None
    messages = context.get('messages')
    if not isinstance(messages, list):
        return None
    previous_users = [message.get('content') for message in messages if isinstance(message, Mapping) and message.get('role') == 'user']
    if any(not isinstance(previous, str) or _named_goal(previous, items) for previous in previous_users):
        return None
    return f'¿A cuál de tus metas quieres destinar esos {amount} mensuales?'
