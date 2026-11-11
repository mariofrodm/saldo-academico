"""Limited numeric grounding, not validation of financial advice or semantics.

Checks explicit Q/GTQ and USD amounts and percentages against typed financial fields in
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
    'reference_gtq_per_usd', 'total_contributions'))
USD_FIELDS = frozenset(('monthly_usd', 'contributions_usd', 'projected_balance_usd'))
SKIP_FIELDS = frozenset(('arguments', 'title', 'name', 'body', 'text', 'content', 'description',
    'prompt', 'response', 'instructions', 'constraints', 'source', 'error', 'reason', 'basis'))
RAW_NUMBER = re.compile(r'-?\d+(?:\.\d+)?\Z')
NUMBER = (r'[-+−]?(?:\d{1,3}(?:,\d{3})+(?:\.\d+)?|'
          r'\d{1,3}(?:[ \u202f\u00a0]+\d{3})+(?:[.,]\d{1,2})?|\d+(?:[.,]\d+)?)')
PREFIX = re.compile(r'(?<!\w)(?P<sign>[-+−]?)(?:GTQ|Q)\s*(?P<number>'+NUMBER+r')')
SUFFIX = re.compile(r'(?<![\w.,])(?P<number>'+NUMBER+r')\s*GTQ\b')
USD_PREFIX = re.compile(r'(?<!\w)(?P<sign>[-+−]?)(?:US\$|USD|\$)\s*(?P<number>'+NUMBER+r')')
USD_SUFFIX = re.compile(r'(?<![\w.,])(?P<number>'+NUMBER+r')\s*USD\b')
PERCENT = re.compile(r'(?<![\w.,])(?P<number>[-+−]?\d+(?:[.,]\d+)?)\s*%')
PROPOSAL = re.compile(r'\b(?:aporto|aportar|pongo|poner|ahorro|ahorrar)\s*(?P<number>\d+(?:[.,]\d{1,2})?)(?![\d.,])', re.I)


def _exact_number(value):
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        return None
    if isinstance(value, str) and not RAW_NUMBER.fullmatch(value):
        return None
    try:
        number = Decimal(str(value))
        return number if number.is_finite() else None
    except (InvalidOperation, ValueError):
        return None


def _rounded(value):
    number = _exact_number(value)
    try:
        return number.quantize(CENT, rounding=ROUND_HALF_UP) if number is not None else None
    except InvalidOperation:
        return None


def _supported_percentage(value, original, allowed):
    # Display precision belongs to the explicit percentage: 25% is a legitimate
    # rounded presentation of 25.22%, while 24%, 26% and monetary rounding are not.
    match = PERCENT.fullmatch(original)
    if match is None or value is None:
        return False
    raw = match.group('number').replace(',', '.')
    places = len(raw.partition('.')[2])
    if places > 12:
        return False
    quantum = Decimal(1).scaleb(-places)
    try:
        return any(number.quantize(quantum, rounding=ROUND_HALF_UP) == value for number in allowed)
    except InvalidOperation:
        return False


def _displayed(raw):
    raw = raw.replace('−', '-').strip()
    # Canonical presentation uses comma grouping and dot decimals. Support the
    # unambiguous Spanish decimal comma too, without guessing mixed separators.
    if re.fullmatch(r'[-+]?\d{1,3}(?:,\d{3})+(?:\.\d+)?', raw):
        raw = raw.replace(',', '')
    elif re.fullmatch(r'[-+]?\d+,\d+', raw):
        raw = raw.replace(',', '.')
    elif re.fullmatch(r'[-+]?\d{1,3}(?:[ \u202f\u00a0]+\d{3})+(?:[.,]\d{1,2})?', raw):
        raw = re.sub(r'[ \u202f\u00a0]', '', raw).replace(',', '.')
    if raw.startswith('+'):
        raw = raw[1:]
    return _rounded(raw)


def _facts(value, money, percentages, usd):
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
            elif key in USD_FIELDS:
                number = _rounded(child)
                if number is not None:
                    usd.add(number)
            elif key == 'annual_percent' or key.endswith('_percent'):
                number = _exact_number(child)
                if number is not None:
                    percentages.add(number)
            if isinstance(child, (Mapping, list, tuple)):
                _facts(child, money, percentages, usd)
    elif isinstance(value, (list, tuple)):
        # A prefetched tuple is (name, arguments, result). Its arguments are
        # proposals, not independent evidence for a provider-generated amount.
        if len(value) == 3 and isinstance(value[0], str) and isinstance(value[1], Mapping):
            _facts(value[2], money, percentages, usd)
        else:
            for child in value:
                _facts(child, money, percentages, usd)


def _mentions(text):
    matches = [(match.start(), match.end(), kind, match) for kind, pattern in
               (('money', PREFIX), ('money', SUFFIX), ('usd', USD_PREFIX), ('usd', USD_SUFFIX), ('percent', PERCENT)) for match in pattern.finditer(text)]
    spans = []
    for start, end, kind, match in sorted(matches, key=lambda row: (row[0], -row[1])):
        if any(start < previous_end and end > previous_start for previous_start, previous_end in spans):
            continue
        spans.append((start, end))
        raw = match.group('number')
        if 'sign' in match.re.groupindex and match.group('sign'):
            raw = match.group('sign')+raw
        yield kind, (_exact_number(raw.replace(',', '.')) if kind == 'percent' else _displayed(raw)), match.group(0).strip()


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
    money, percentages, usd = set(), set(), set()
    _facts(tool_results, money, percentages, usd)
    if not money and not percentages and not usd:
        return []
    for text in _user_text(user_messages):
        for kind, value, _ in _mentions(text):
            if value is not None:
                {'money':money,'usd':usd,'percent':percentages}[kind].add(value)
        for match in PROPOSAL.finditer(text):
            suffix = text[match.end():].lstrip()
            if suffix.startswith('%') or re.match(r'(?:USD\b|d[oó]lares\b|\$)', suffix, re.I):
                continue
            value = _displayed(match.group('number'))
            if value is not None:
                money.add(value)
    unsupported = []
    for kind, value, original in _mentions(answer):
        allowed = {'money':money,'usd':usd,'percent':percentages}[kind]
        supported = _supported_percentage(value, original, allowed) if kind == 'percent' else value is not None and value in allowed
        if not supported and original not in unsupported:
            unsupported.append(original)
    return unsupported
