"""Fit a complete provider payload without cutting questions or financial JSON.

This is a local packing operation: it neither queries data nor calls a model.
The caller owns the trusted, complete alternative system instructions supplied
as ``_brief_content``. Private packing metadata never leaves this module.
"""
import json
from copy import deepcopy

import tiktoken

from .diagnosis import compact


def _without_metadata(value):
    if isinstance(value, dict):
        return {key: _without_metadata(child) for key, child in value.items()
                if not isinstance(key, str) or not key.startswith('_')}
    if isinstance(value, list):
        return [_without_metadata(child) for child in value]
    return deepcopy(value)


def estimate_payload(payload):
    """Use the application's conservative estimate, including reserved output."""
    cleaned = _without_metadata(payload)
    serialized = json.dumps(cleaned, ensure_ascii=False, separators=(',', ':'))
    if cleaned.get('model', '').startswith('openai/gpt-oss'):
        tokens = len(tiktoken.get_encoding('o200k_harmony').encode_ordinary(serialized))
        estimated_input = int(tokens * 1.25) + 512
    else:
        estimated_input = len(serialized.encode()) + 1024
    return estimated_input + cleaned['max_completion_tokens']


def _compact_results(value):
    """Keep complete aggregate fields; mark every shortened detail list honestly."""
    if isinstance(value, list):
        return [_compact_results(child) for child in value]
    if not isinstance(value, dict):
        return value
    result = {key: _compact_results(child) for key, child in value.items()}
    if isinstance(result.get('items'), list):
        upstream_omission = result.get('has_more') is True
        result = compact(result, 1)
        result['has_more'] = upstream_omission or result['has_more']
    return result


def fit_payload(payload, ceiling=6500):
    """Return a fitting copy, or None; preserve this turn's protocol and output.

    Stages remove complete old chat pairs, choose a caller-provided complete
    brief system prompt, compact tool detail arrays, then omit descriptions
    from tool schemas. Current questions, calls/IDs, arguments, names, parameter
    schemas and financial aggregates are never truncated.
    """
    if isinstance(ceiling, bool) or not isinstance(ceiling, int) or ceiling <= 0:
        raise ValueError('El presupuesto de contexto debe ser un entero positivo')
    brief = [message.get('_brief_content')
             if isinstance(message.get('_brief_content'), str) and message['_brief_content'].strip() else None
             for message in payload.get('messages', []) if message.get('role') == 'system']
    packed = _without_metadata(payload)
    if estimate_payload(packed) <= ceiling:
        return packed

    messages = packed.get('messages', [])
    while estimate_payload(packed) > ceiling:
        last_user = max((index for index, message in enumerate(messages)
                         if message.get('role') == 'user'), default=0)
        old = next((index for index, message in enumerate(messages[:last_user])
                    if message.get('role') == 'user' and index + 1 < last_user
                    and messages[index + 1].get('role') == 'assistant'
                    and not messages[index + 1].get('tool_calls')), None)
        if old is None:
            break
        del messages[old:old + 2]
    if estimate_payload(packed) <= ceiling:
        return packed

    # System messages precede historical pairs in the supported chat protocol.
    # Match their original order instead of retaining shifted message indexes.
    alternatives = iter(brief)
    for message in messages:
        if message.get('role') == 'system':
            alternative = next(alternatives, None)
            if alternative is not None:
                message['content'] = alternative
    if estimate_payload(packed) <= ceiling:
        return packed

    for message in messages:
        if message.get('role') != 'tool' or not isinstance(message.get('content'), str):
            continue
        try:
            result = json.loads(message['content'])
        except (ValueError, TypeError):
            continue
        if isinstance(result, (dict, list)):
            message['content'] = json.dumps(_compact_results(result), ensure_ascii=False, separators=(',', ':'))
    if estimate_payload(packed) <= ceiling:
        return packed

    # Descriptions are optional; preserve function names and every parameter
    # constraint, including property descriptions, types, required and bounds.
    for schema in packed.get('tools', []):
        function = schema.get('function') if isinstance(schema, dict) else None
        if isinstance(function, dict):
            function.pop('description', None)
    return packed if estimate_payload(packed) <= ceiling else None
