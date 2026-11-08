"""Narrow assertions unsupported by recorded cash flow, not semantic certification.

Matching financial numbers do not prove spending capacity or that every bill
has been paid. Only explicit positive claims recognized below are replaced;
negations, warnings, ordinary recommendations and other prose remain intact.
The caller keeps the original candidate and replacements in the audit trail.
"""
import re
import unicodedata
from collections.abc import Mapping


FLOW_REMINDER = ('Es el flujo registrado del período; aún debes considerar pagos pendientes '
                 'y gastos no anotados.')
OBLIGATIONS = r'(?:obligaciones|deudas|cuentas|compromisos)'
ALL_OWN = r'todas?\s+(?:(?:tus|las|sus|mis)\s+)?'+OBLIGATIONS
CLAIMS = (
    re.compile(r'\bcapacidad\s+(?:real|confirmada|garantizada)\s+(?:de|para)\s+(?:gasto|gastar|pago|pagar)\b'),
    re.compile(r'\bdinero\s+(?:totalmente\s+)?libre\s+para\s+gastar\b'),
    re.compile(r'\b(?:ya\s+)?(?:pagaste|cubriste|saldaste|liquidaste|has\s+(?:pagado|cubierto|saldado|liquidado))\s+'+ALL_OWN+r'\b'),
    re.compile(r'\b(?:tienes|quedan|estan)\s+(?:ya\s+)?'+ALL_OWN+r'\s+(?:ya\s+)?(?:pagadas?|cubiertas?|saldadas?|liquidadas?)\b'),
    re.compile(r'\b'+ALL_OWN+r'\s+(?:ya\s+)?(?:estan|quedan)\s+(?:pagadas?|cubiertas?|saldadas?|liquidadas?)\b'),
)
SENTENCE_BREAK = re.compile(r'((?<=[.!?])\s+(?=[^\W\d_¿¡]|[¿¡])|\n{2,})')
CLAUSE_BREAK = re.compile(r'[,;:]|\b(?:pero|aunque|sin embargo|mientras que)\b')
NEGATED = re.compile(r'\b(?:no|nunca|jamas|tampoco|sin|evita|evitar)\b[^.!?]{0,120}$')


def _normalized(text):
    return ''.join(char for char in unicodedata.normalize('NFD', text.casefold())
                   if not unicodedata.combining(char))


def _has_flow(results):
    if not isinstance(results, (list, tuple)):
        return False
    for result in results:
        if (not isinstance(result, Mapping) or result.get('available') is False or result.get('error')
                or result.get('status') in ('failed','error')):
            continue
        source = result.get('source_id')
        if source == 'SBUDGET_EXTERNAL':
            flow = result.get('flow')
        elif source == 'SFIN':
            flow = result.get('current')
        elif source == 'SDIAG' and isinstance(result.get('flow'), Mapping):
            flow = result['flow'].get('current')
        else:
            continue
        if isinstance(flow, Mapping) and {'income', 'expense', 'net_savings', 'available'} <= set(flow):
            return True
    return False


def guard_recorded_flow(answer, results):
    """Return corrected prose plus exact removed sentences, without inference.

    Sentence boundaries preserve decimal amounts and the original separators.
    Recognition is intentionally limited; an unchanged answer is not proof that
    every interpretation is correct. This guard never validates or changes money.
    """
    if not isinstance(answer, str) or not _has_flow(results):
        return answer, []
    parts = SENTENCE_BREAK.split(answer)
    removed = []
    reminder_used = FLOW_REMINDER in answer
    for index in range(0, len(parts), 2):
        sentence = parts[index]
        normalized = _normalized(sentence)
        unsupported = False
        for pattern in CLAIMS:
            for match in pattern.finditer(normalized):
                prefix = CLAUSE_BREAK.split(normalized[:match.start()])[-1]
                if not NEGATED.search(prefix):
                    unsupported = True
                    break
            if unsupported:
                break
        if unsupported:
            removed.append(sentence)
            parts[index] = '' if reminder_used else FLOW_REMINDER
            reminder_used = True
    return ''.join(parts).strip(), removed
