"""Resolve one explicit monthly proposal and goal, without database/model calls.

The caller must provide a fresh, authenticated goal_snapshot. This only resolves
unambiguous user wording; it never promotes an assistant recommendation to a
choice, estimates capacity, or computes a deadline/contribution schedule.
"""
import re
import unicodedata
from collections.abc import Mapping
from datetime import date
from decimal import Decimal, InvalidOperation


PROPOSAL = re.compile(r'(?:y\s+)?(?:si\s+)?(?:aporto|pongo)\s*(?:q\s*)?'
                      r'(?P<amount>\d{1,13}(?:[.,]\d{1,2})?)\s+(?:al\s+mes|mensuales)'
                      r'(?:\s+(?P<goal>.+))?')
PREFIX = re.compile(r'^(?:al?|para|el|la|elijo|escojo|elegir|escoger|quiero(?:\s+(?:elegir|escoger))?)\s+')
STOP = frozenset(('de', 'del', 'el', 'la', 'los', 'las', 'mi', 'mis', 'para', 'por', 'y', 'con',
                  'meta', 'metas', 'objetivo', 'objetivos', 'ahorro', 'ahorros', 'trabajo'))


def _normal(text):
    return ''.join(char for char in unicodedata.normalize('NFD', text.casefold())
                   if not unicodedata.combining(char)).strip().strip('¿?¡!. ').strip()


def _proposal(text):
    match = PROPOSAL.fullmatch(text)
    if not match:
        return None
    try:
        amount = Decimal(match.group('amount').replace(',', '.'))
        if amount <= 0:
            return None
        return format(amount.quantize(Decimal('.01')), '.2f'), match.group('goal') or ''
    except InvalidOperation:
        return None


def _goal(text, items):
    selected = text.strip()
    while (cleaned := PREFIX.sub('', selected)) != selected:
        selected = cleaned
    if not selected:
        return None
    explicit_id = re.fullmatch(r'(?:(?:meta|objetivo)(?:\s+(?:id|numero))?\s*#?\s*|id\s*|#)(\d+)', selected)
    if explicit_id:
        matches = [item for item in items if item['id'] == int(explicit_id.group(1))]
    else:
        matches = [item for item in items if _normal(item['name']) == selected]
        if not matches:
            tokens = set(re.findall(r'\b\w+\b', selected))-STOP
            words = [set(re.findall(r'\b\w+\b', _normal(item['name'])))-STOP for item in items]
            matches = []
            for index, item in enumerate(items):
                others = set().union(*(group for position, group in enumerate(words) if position != index))
                if tokens and tokens <= words[index] and tokens & (words[index]-others):
                    matches.append(item)
    return matches[0] if len(matches) == 1 else None


def savings_arguments(prompt, context, goal_snapshot_result):
    if not isinstance(prompt, str) or not isinstance(context, Mapping) or not isinstance(goal_snapshot_result, Mapping):
        return None
    snapshot = goal_snapshot_result
    if snapshot.get('source_id') != 'SMETAS' or snapshot.get('currency') != 'GTQ':
        return None
    if snapshot.get('has_more') is True:
        return None  # An alias cannot be unique across unseen goals.
    try:
        if date.fromisoformat(snapshot['as_of']).isoformat() != snapshot['as_of']:
            return None
    except (KeyError, TypeError, ValueError):
        return None
    items = snapshot.get('items')
    if not isinstance(items, list) or not items:
        return None
    if any(not isinstance(item, Mapping) or not isinstance(item.get('id'), int) or isinstance(item.get('id'), bool)
           or item['id'] < 1 or not isinstance(item.get('name'), str) or not item['name'].strip() for item in items):
        return None
    messages = context.get('messages')
    if not isinstance(messages, list):
        return None
    users = [message.get('content') for message in messages
             if isinstance(message, Mapping) and message.get('role') == 'user']
    previous = _normal(users[-1]) if users and isinstance(users[-1], str) else ''
    text = _normal(prompt)
    current_proposal = _proposal(text)
    if current_proposal:
        monthly, selection = current_proposal
        # A previous explicit user selection is usable; a prior question or an
        # assistant recommendation cannot pass the narrow goal-name resolver.
        chosen = _goal(selection, items) if selection else _goal(previous, items)
    else:
        previous_proposal = _proposal(previous)
        if not previous_proposal:
            return None
        monthly, previous_selection = previous_proposal
        # Do not silently discard a prior USD unit, custom deadline or compound
        # scenario that happened to follow an otherwise valid monthly amount.
        if previous_selection and _goal(previous_selection, items) is None:
            return None
        chosen = _goal(text, items)
    if chosen is None or chosen.get('active') is not True or chosen.get('state') != 'en progreso':
        return None
    months = chosen.get('remaining_contributions')
    if not isinstance(months, int) or isinstance(months, bool) or not 1 <= months <= 120:
        return None
    return {'goal_id': chosen['id'], 'months': months, 'monthly': monthly}
