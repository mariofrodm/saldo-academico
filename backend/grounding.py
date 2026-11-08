"""Limited numeric grounding, not validation of financial advice or semantics.

Checks explicit Q/GTQ amounts and percentages against typed financial fields in
current tool results and explicit user proposals. Matching numbers can still be
assigned to the wrong period, category or conclusion; callers must not treat an
empty result as a guarantee of correctness. No text is changed by this module.
"""
import re
from collections.abc import Mapping
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


CENT = Decimal('.01')
MONEY_FIELDS = frozenset(('income', 'expense', 'net_savings', 'available', 'amount', 'planned',
    'executed', 'remaining', 'paid_to_cutoff', 'overdue', 'due_today', 'future_due',
    'carry_from_prior_months', 'total_expense', 'observed_income', 'debt_payments',
    'monthly_planned', 'threshold', 'candidate_total', 'expense_excluding_debt',
    'monthly_reduction', 'monthly_extra_income', 'monthly_extra_debt', 'monthly_extra_savings',
    'scenario_available', 'target', 'balance', 'active_target', 'active_balance',
    'active_required_monthly', 'required_monthly_to_deadline', 'required_monthly',
    'monthly_required', 'proposed_monthly', 'projected_balance', 'gap_at_end',
    'extra_monthly_needed', 'difference_gtq', 'historical_margin', 'affordability_gap',
    'active_future_required', 'verified_affordable_contribution', 'total_pending',
    'reference_gtq_per_usd'))
SKIP_FIELDS = frozenset(('arguments', 'title', 'name', 'body', 'text', 'content', 'description',
    'prompt', 'response', 'instructions', 'constraints', 'source', 'error', 'reason', 'basis'))
RAW_NUMBER = re.compile(r'-?\d+(?:\.\d+)?\Z')
NUMBER = (r'[-+−]?(?:\d{1,3}(?:,\d{3})+(?:\.\d+)?|'
          r'\d{1,3}(?:[ \u202f\u00a0]+\d{3})+(?:[.,]\d{1,2})?|\d+(?:[.,]\d+)?)')
PREFIX = re.compile(r'(?<!\w)(?P<sign>[-+−]?)(?:GTQ|Q)\s*(?P<number>'+NUMBER+r')')
SUFFIX = re.compile(r'(?<![\w.,])(?P<number>'+NUMBER+r')\s*GTQ\b')
PERCENT = re.compile(r'(?<![\w.,])(?P<number>[-+−]?\d+(?:[.,]\d+)?)\s*%')
PROPOSAL = re.compile(r'\b(?:aporto|aportar|pongo|poner|ahorro|ahorrar)\s*(?P<number>\d+(?:[.,]\d{1,2})?)(?![\d.,])', re.I)


def _rounded(value):
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        return None
    if isinstance(value, str) and not RAW_NUMBER.fullmatch(value):
        return None
    try:
        number = Decimal(str(value))
        return number.quantize(CENT, rounding=ROUND_HALF_UP) if number.is_finite() else None
    except (InvalidOperation, ValueError):
        return None


def _displayed(raw):
    raw = raw.replace('−', '-').strip()
    # Canonical presentation uses comma grouping and dot decimals. Support the
    # unambiguous Spanish decimal comma too, without guessing mixed separators.
    if re.fullmatch(r'[-+]?\d{1,3}(?:,\d{3})+(?:\.\d+)?', raw):
        raw = raw.replace(',', '')
    elif re.fullmatch(r'[-+]?\d+,\d{1,2}', raw):
        raw = raw.replace(',', '.')
    elif re.fullmatch(r'[-+]?\d{1,3}(?:[ \u202f\u00a0]+\d{3})+(?:[.,]\d{1,2})?', raw):
        raw = re.sub(r'[ \u202f\u00a0]', '', raw).replace(',', '.')
    if raw.startswith('+'):
        raw = raw[1:]
    return _rounded(raw)


def _facts(value, money, percentages):
    if isinstance(value, Mapping):
        if value.get('available') is False or value.get('error') or value.get('status') in ('failed', 'error'):
            return
        for key, child in value.items():
            if not isinstance(key, str) or key in SKIP_FIELDS:
                continue
            if key in MONEY_FIELDS:
                number = _rounded(child)
                if number is not None:
                    money.add(number)
            elif key == 'annual_percent' or key.endswith('_percent'):
                number = _rounded(child)
                if number is not None:
                    percentages.add(number)
            if isinstance(child, (Mapping, list, tuple)):
                _facts(child, money, percentages)
    elif isinstance(value, (list, tuple)):
        # A prefetched tuple is (name, arguments, result). Its arguments are
        # proposals, not independent evidence for a provider-generated amount.
        if len(value) == 3 and isinstance(value[0], str) and isinstance(value[1], Mapping):
            _facts(value[2], money, percentages)
        else:
            for child in value:
                _facts(child, money, percentages)


def _mentions(text):
    matches = [(match.start(), match.end(), kind, match) for kind, pattern in
               (('money', PREFIX), ('money', SUFFIX), ('percent', PERCENT)) for match in pattern.finditer(text)]
    spans = []
    for start, end, kind, match in sorted(matches, key=lambda row: (row[0], -row[1])):
        if any(start < previous_end and end > previous_start for previous_start, previous_end in spans):
            continue
        spans.append((start, end))
        raw = match.group('number')
        if 'sign' in match.re.groupindex and match.group('sign'):
            raw = match.group('sign')+raw
        yield kind, _displayed(raw), match.group(0).strip()


def _user_text(messages):
    if isinstance(messages, str):
        yield messages
    elif isinstance(messages, Mapping):
        if messages.get('role') == 'user' and isinstance(messages.get('content'), str):
            yield messages['content']
    elif isinstance(messages, (list, tuple)):
        for message in messages:
            yield from _user_text(message)


def unsupported_amounts(answer, tool_results, user_messages=()):
    """Return unsupported explicit amounts, in answer order, without mutation.

    No usable financial facts means no validation (an empty list). Source text,
    IDs, counts, dates and token statistics never become monetary evidence.
    """
    if not isinstance(answer, str):
        return []
    money, percentages = set(), set()
    _facts(tool_results, money, percentages)
    if not money and not percentages:
        return []
    for text in _user_text(user_messages):
        for kind, value, _ in _mentions(text):
            if value is not None:
                (money if kind == 'money' else percentages).add(value)
        for match in PROPOSAL.finditer(text):
            suffix = text[match.end():].lstrip()
            if suffix.startswith('%') or re.match(r'(?:USD\b|d[oó]lares\b|\$)', suffix, re.I):
                continue
            value = _displayed(match.group('number'))
            if value is not None:
                money.add(value)
    unsupported = []
    for kind, value, original in _mentions(answer):
        allowed = money if kind == 'money' else percentages
        if (value is None or value not in allowed) and original not in unsupported:
            unsupported.append(original)
    return unsupported
