"""Regression for Carla's real six-contribution comparison and Banguat rate."""
from decimal import Decimal

import pytest

from backend import ai
from backend.db import db, one
from backend.grounding import unsupported_amounts
from test_external_workflows import completion_pair, assert_two_round_budget


PROMPT = ('Compara aportar Q500 o Q750 mensuales durante seis meses a mi fondo de emergencia '
          'y muestra su equivalencia en dólares usando Banguat')
RATE = {'reference_gtq_per_usd': '7.63846', 'date': '10/11/2026',
        'source': 'https://www.banguat.gob.gt/variables/ws/TipoCambio.asmx',
        'kind': 'Referencia, no tasa de liquidación de un banco'}


def prepare(client, monkeypatch):
    with db() as conn:
        conn.execute("UPDATE goals SET name='Fondo de emergencia',target=5000 WHERE id=1")
        conn.execute('UPDATE savings SET amount=1000 WHERE goal_id=1')
    monkeypatch.setattr(ai, 'exchange_rate', lambda: RATE.copy())
    return {'goal_id': 1, 'months': 6, 'monthly_a': '500', 'monthly_b': '750', 'include_exchange_rate': True}


def test_conversions_use_full_reference_not_rounded_exchange_rate(client, monkeypatch):
    args = prepare(client, monkeypatch)
    result = ai.execute_tool('goal_external_scenarios', args, 2)
    assert result['goal']['balance'] == '1000.00'
    assert [r['total_contributions'] for r in result['scenarios']] == ['3000.00', '4500.00']
    assert [r['projected_balance'] for r in result['scenarios']] == ['4000.00', '5500.00']
    for row in result['scenarios']:
        assert Decimal(row['contributions_usd']) == (Decimal(row['total_contributions']) / Decimal('7.63846')).quantize(Decimal('.01'))
        assert Decimal(row['projected_balance_usd']) == (Decimal(row['projected_balance']) / Decimal('7.63846')).quantize(Decimal('.01'))
    assert result['exchange_rate'] == RATE
    assert unsupported_amounts('Q3,000.00, Q4,500.00 y 7,63846 GTQ por USD.', [result]) == []
    row = result['scenarios'][0]
    assert unsupported_amounts(f'US${row["projected_balance_usd"]}, ${row["projected_balance_usd"]}', [result]) == []
    assert unsupported_amounts(f'Q{row["projected_balance_usd"]}', [result])
    assert unsupported_amounts('US$4,000.00', [result]) == ['US$4,000.00']
    assert unsupported_amounts(f'-US${row["projected_balance_usd"]}', [result])


def test_real_candidate_is_repaired_from_verified_scenarios_without_more_inference(client, auth, monkeypatch):
    args = prepare(client, monkeypatch)
    # The real model calculated rounded dollar amounts instead of using tool facts.
    candidate = ('Aportar Q500.00 mensuales durante seis meses generaría Q3,000.00, '
                 'equivalentes a US$393 (7,63846 GTQ por USD); el fondo tendría Q4,000.00. '
                 'Aportar Q750.00 produciría Q4,500.00, unos US$589, y un fondo de Q5,500.00.')
    payloads = completion_pair(monkeypatch, 'goal_external_scenarios', args, candidate)
    response = client.post('/api/v1/ai/goals', headers=auth, json={'prompt': PROMPT})
    assert response.status_code == 200, response.text
    text = response.json()['response']
    assert 'Q4,000.00' in text and 'Q5,500.00' in text and 'US$' in text
    assert '10/11/2026' in text and '7.63846' in text
    assert 'no puedo confirmar' not in text
    history = client.get('/api/v1/history/'+response.json()['id'], headers=auth).json()
    checks = [t['result'] for t in history['tools'] if t['name'] == 'response_check']
    assert checks and checks[0]['unsupported_amounts'] == ['US$393', 'US$589']
    result = next(t['result'] for t in history['tools'] if t['name'] == 'goal_external_scenarios')
    assert unsupported_amounts(text, [result]) == []
    assert_two_round_budget(payloads)


def test_unavailable_banguat_preserves_gtq_and_never_invents_usd(client, monkeypatch):
    args = prepare(client, monkeypatch)
    monkeypatch.setattr(ai, 'exchange_rate', lambda: {'available': False, 'source': RATE['source']})
    result = ai.execute_tool('goal_external_scenarios', args, 2)
    assert all('projected_balance_usd' not in row for row in result['scenarios'])
    text = ai.unverified_response(PROMPT, [result])
    assert 'Q4,000.00' in text and 'Q5,500.00' in text and 'US$' not in text
    assert 'Banguat no estuvo disponible' in text
    assert unsupported_amounts('US$500', [result]) == ['US$500']
