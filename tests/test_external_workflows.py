import json
from datetime import date
from decimal import Decimal

import httpx
import pytest
import tiktoken

from backend import ai
from backend.conversation import build_context
from backend.db import db, one, many
from backend.demo import populate_demo
from backend.grounding import unsupported_amounts


BUDGET_QUESTION = 'Consulta mis ingresos, pagos y ahorro de octubre de 2026 y la inflación anual de Guatemala 2025 en Banco Mundial. Explica la diferencia de períodos.'
GOAL_QUESTION = 'Consulta el Fondo de emergencia y su saldo actual. Consulta la referencia USD/GTQ de Banguat. Compara seis meses aportando Q500 mensuales con seis meses aportando Q750.'


def reference(year):
    return {'available': True, 'annual_percent': '3.00', 'year': year,
            'source': 'https://api.worldbank.org/v2/country/GTM/indicator/FP.CPI.TOTL.ZG',
            'retrieved_at': '2026-11-08T12:00:00+00:00'}


def rate():
    return {'reference_gtq_per_usd': '7.65', 'date': '06/11/2026',
            'source': 'https://www.banguat.gob.gt/variables/ws/TipoCambio.asmx',
            'kind': 'Referencia, no tasa de liquidación de un banco'}


def wire_tokens(payload):
    return len(tiktoken.get_encoding('o200k_harmony').encode_ordinary(json.dumps(payload, ensure_ascii=False, separators=(',', ':'))))


def completion_pair(monkeypatch, tool_name, arguments, answer):
    payloads = []
    def completion(payload):
        payloads.append(payload)
        if len(payloads) == 1:
            content = {'role': 'assistant', 'content': None, 'tool_calls': [
                {'id': 'call_compound', 'type': 'function', 'function': {'name': tool_name, 'arguments': json.dumps(arguments)}}]}
        elif len(payloads) == 2:
            content = {'role': 'assistant', 'content': answer}
        else:
            pytest.fail('El flujo completo no necesita una tercera inferencia')
        return {'choices': [{'message': content, 'finish_reason': 'stop'}],
                'usage': {'prompt_tokens': wire_tokens(payload), 'completion_tokens': 120 if len(payloads) == 1 else 180}}
    monkeypatch.setattr(ai, 'completion', completion)
    monkeypatch.setenv('GROQ_API_KEY', 'mock-only-not-a-real-key')
    return payloads


def assert_two_round_budget(payloads):
    assert len(payloads) == 2
    first, final = payloads
    assert first['parallel_tool_calls'] is False
    assert len(first['tools']) == 1
    assert 'tools' not in final
    assert all(p['max_completion_tokens'] == 768 and p['reasoning_effort'] == 'medium' for p in payloads)
    estimates = [ai.estimate_payload(p) for p in payloads]
    # Even conservative two-call reservations fit in an otherwise idle minute.
    assert sum(estimates) <= 7000, estimates
    # Settlement replaces the first reservation with measured input+output.
    assert wire_tokens(first)+120+estimates[1] <= 7000, estimates
    print(json.dumps({'workflow': first['tools'][0]['function']['name'], 'estimated_reservations': estimates,
                      'first_measured_simulation_plus_next_reservation': wire_tokens(first)+120+estimates[1]}))


def test_budget_external_flow_two_inferences_separate_periods_and_sources(client, auth, monkeypatch):
    with db() as conn:
        populate_demo(conn)
    years = []
    monkeypatch.setattr(ai, 'inflation', lambda year: years.append(year) or reference(year))
    payloads = completion_pair(monkeypatch, 'budget_external_review',
        {'start': '2026-10-01', 'end': '2026-10-31', 'inflation_year': 2025},
        'En octubre de 2026 ingresaron Q7,250.00 y pagaste Q7,177.00: quedaron Q73.00 de flujo. El Banco Mundial reporta 3% anual para 2025, consultado el 8 de noviembre de 2026; es otro período, no la inflación de octubre.')
    response = client.post('/api/v1/ai/budget', headers=auth, json={'prompt': BUDGET_QUESTION})
    assert response.status_code == 200, response.text
    assert years == [2025]
    detail = client.get('/api/v1/history/'+response.json()['id'], headers=auth).json()
    assert len(detail['calls']) == 2
    assert [entry['name'] for entry in detail['tools']] == ['budget_external_review']
    result = detail['tools'][0]['result']
    assert result['flow']['from'] == '2026-10-01' and result['inflation']['year'] == 2025
    assert result['flow']['available'] == '73.00'
    assert result['margin_after_savings'] == '73.00'
    assert result['actions'] == ['financial_summary', 'inflation']
    assert any(source.get('source', '').startswith('https://api.worldbank.org/') for source in response.json()['sources'])
    assert not any(tool['name'] == 'response_check' for tool in detail['tools'])
    assert_two_round_budget(payloads)


def test_goal_external_flow_two_inferences_current_owned_balance_and_two_scenarios(client, auth, monkeypatch):
    with db() as conn:
        populate_demo(conn)
        goal = one(conn, "SELECT id FROM goals WHERE user_id=2 AND name='Fondo de emergencia'")['id']
    calls = []
    monkeypatch.setattr(ai, 'exchange_rate', lambda: calls.append(True) or rate())
    payloads = completion_pair(monkeypatch, 'goal_external_scenarios',
        {'goal_id': goal, 'months': 6, 'monthly_a': '500.00', 'monthly_b': '750.00', 'include_exchange_rate': True},
        'Partiendo de Q550.00, con Q500.00 mensuales llegarías a Q3,550.00; con Q750.00 llegarías a Q5,050.00 y superarías la meta de Q5,000.00. Son escenarios sin rendimientos y no confirman que puedas financiarlos. Banguat publicó Q7.65 por dólar el 6 de noviembre de 2026: es una referencia, no una tasa bancaria.')
    response = client.post('/api/v1/ai/goals', headers=auth, json={'prompt': GOAL_QUESTION})
    assert response.status_code == 200, response.text
    assert len(calls) == 1
    detail = client.get('/api/v1/history/'+response.json()['id'], headers=auth).json()
    assert [tool['name'] for tool in detail['tools']] == ['goal_snapshot', 'goal_external_scenarios']
    result = detail['tools'][1]['result']
    assert result['goal']['balance'] == '550.00'
    assert [r['projected_balance'] for r in result['scenarios']] == ['3550.00', '5050.00']
    assert result['difference_gtq'] == '1500.00'
    assert result['schedule_checked'] is False and result['affordability_checked'] is False
    assert [r['reaches_goal'] for r in result['scenarios']] == [False, True]
    assert result['actions'] == ['savings_plan', 'savings_plan', 'exchange_rate']
    assert any(source.get('source', '').startswith('https://www.banguat.gob.gt/') for source in response.json()['sources'])
    assert not any(tool['name'] == 'response_check' for tool in detail['tools'])
    assert_two_round_budget(payloads)
    with db() as conn:
        assert one(conn, 'SELECT count(*) AS n FROM savings')['n'] == 12


def test_external_workflows_are_service_scoped_and_skip_unrelated_schemas():
    assert ai.selected_tools('budget', BUDGET_QUESTION) == ['budget_external_review']
    assert ai.selected_tools('goals', GOAL_QUESTION) == ['goal_external_scenarios']
    assert 'budget_external_review' not in ai.ALLOWED['rag']
    assert 'goal_external_scenarios' not in ai.ALLOWED['budget']
    assert 'goal_external_scenarios' not in ai.ALLOWED['rag']
    assert ai.external_workflow('goals', 'Quiero cambiar el nombre de una meta') is None
    context = build_context([], BUDGET_QUESTION, date(2026, 11, 8))
    assert context['period_hint'] == {'kind': 'explicit', 'period': {'start': '2026-10-01', 'end': '2026-10-31'}}


def test_external_context_does_not_accumulate_old_answers_or_unrelated_categories():
    context = build_context([], GOAL_QUESTION, date(2026, 11, 8))
    context['instructions'] += 'OLD_ANSWER '*1000
    context['messages'] = [{'role': 'assistant', 'content': 'OLD_ANSWER '*1000}]
    context['state']['categories'] = [{'name': 'UNRELATED_CATEGORY '*20, 'id': i} for i in range(8)]
    context['state']['goals'] = [{'name': 'Meta '+str(i), 'id': i} for i in range(8)]
    packed = ai.external_system(context, [], 'goal_external_scenarios')
    assert 'OLD_ANSWER' not in packed and 'UNRELATED_CATEGORY' not in packed
    assert 'Meta 0' in packed and 'Meta 3' not in packed


@pytest.mark.parametrize('name,args', [
    ('budget_external_review', {'start': '2026-10-01', 'end': '2026-10-31', 'inflation_year': True}),
    ('budget_external_review', {'start': '2026-10-31', 'end': '2026-10-01', 'inflation_year': 2025}),
    ('budget_external_review', {'start': '2026-10-01', 'end': '2026-10-31', 'inflation_year': 2025, 'user_id': 1}),
    ('goal_external_scenarios', {'goal_id': 1, 'months': True, 'monthly_a': '500.00', 'monthly_b': '750.00', 'include_exchange_rate': True}),
    ('goal_external_scenarios', {'goal_id': 1, 'months': 6, 'monthly_a': 500, 'monthly_b': '750.00', 'include_exchange_rate': True}),
    ('goal_external_scenarios', {'goal_id': 1, 'months': 6, 'monthly_a': '-1.00', 'monthly_b': '750.00', 'include_exchange_rate': True}),
    ('goal_external_scenarios', {'goal_id': 1, 'months': 6, 'monthly_a': '500.001', 'monthly_b': '750.00', 'include_exchange_rate': True}),
    ('goal_external_scenarios', {'goal_id': 1, 'months': 6, 'monthly_a': '500.00', 'monthly_b': '750.00', 'include_exchange_rate': 'true'}),
])
def test_compound_tools_validate_arguments_before_external_calls(client, monkeypatch, name, args):
    monkeypatch.setattr(ai, 'inflation', lambda year: pytest.fail('No consultar externo con argumentos inválidos'))
    monkeypatch.setattr(ai, 'exchange_rate', lambda: pytest.fail('No consultar externo con argumentos inválidos'))
    with pytest.raises((ValueError, KeyError, TypeError)):
        ai.execute_tool(name, args, 2)


def test_goal_compound_rejects_foreign_goal_and_does_not_consult_external(client, monkeypatch):
    with db() as conn:
        foreign = one(conn, "INSERT INTO goals(user_id,name,target,deadline) VALUES(1,'Ajena',100,'2027-01-01') RETURNING id")['id']
    monkeypatch.setattr(ai, 'exchange_rate', lambda: pytest.fail('No consultar externo para una meta ajena'))
    args = {'goal_id': foreign, 'months': 6, 'monthly_a': '500.00', 'monthly_b': '750.00', 'include_exchange_rate': True}
    with pytest.raises(ValueError, match='propia'):
        ai.execute_tool('goal_external_scenarios', args, 2)
    args['goal_id'] = 1
    for invalid_user in (0, True, '2'):
        with pytest.raises(ValueError):
            ai.execute_tool('goal_external_scenarios', args, invalid_user)


def test_goal_reference_is_optional_and_external_failure_preserves_verified_calculations(client, monkeypatch):
    args = {'goal_id': 1, 'months': 6, 'monthly_a': '500.00', 'monthly_b': '750.00', 'include_exchange_rate': False}
    monkeypatch.setattr(ai, 'exchange_rate', lambda: pytest.fail('La referencia no fue solicitada'))
    result = ai.execute_tool('goal_external_scenarios', args, 2)
    assert result['exchange_rate'] is None and 'exchange_rate' not in result['actions']
    def fail():
        raise httpx.ConnectError('Fallo externo simulado')
    monkeypatch.setattr(ai, 'exchange_rate', fail)
    result = ai.execute_tool('goal_external_scenarios', {**args, 'include_exchange_rate': True}, 2)
    assert result['exchange_rate']['available'] is False
    assert result['scenarios'][0]['projected_balance'] == '3500.00'
    assert ai.external_results('goal_external_scenarios', result)[0]['available'] is False


def test_nested_budget_and_goal_values_are_grounded(client, monkeypatch):
    monkeypatch.setattr(ai, 'inflation', reference)
    budget = ai.execute_tool('budget_external_review', {'start': '2026-11-01', 'end': '2026-11-30', 'inflation_year': 2025}, 2)
    goal = ai.execute_tool('goal_external_scenarios', {'goal_id': 1, 'months': 6, 'monthly_a': '500.00', 'monthly_b': '750.00', 'include_exchange_rate': False}, 2)
    assert unsupported_amounts('Ingresos Q6,000.00 e inflación 3%. Con Q500.00 quedarían Q3,500.00.', [budget, goal]) == []
    assert unsupported_amounts('Quedarían Q9,999.00.', [budget, goal])


def test_real_budget_regression_margin_includes_savings_and_annual_rounding_is_valid(client, monkeypatch):
    actual_reference = reference(2025)
    actual_reference['annual_percent'] = '1.48841591086168'
    monkeypatch.setattr(ai, 'inflation', lambda year: actual_reference)
    result = ai.execute_tool('budget_external_review',
        {'start': '2026-11-01', 'end': '2026-11-30', 'inflation_year': 2025}, 2)
    assert result['flow']['income'] == '6000.00' and result['flow']['expense'] == '1400.00'
    assert result['flow']['net_savings'] == '500.00'
    assert result['margin_after_savings'] == result['flow']['available'] == '4100.00'
    candidate = ('En noviembre ingresaron Q6,000.00 y pagaste Q1,400.00: el margen es Q4,600.00. '
                 'La inflación anual del Banco Mundial fue 1,49 % para 2025.')
    # Exact real failure: arithmetic that omits saving remains unsupported.
    # The published annual percentage already rounded correctly; no guard bypass.
    assert unsupported_amounts(candidate, [result]) == ['Q4,600.00']
    corrected = ('Ingresaron Q6,000.00, pagaste Q1,400.00 y apartaste Q500.00 de ahorro neto: '
                 'el margen registrado fue Q4,100.00. Inflación anual de 2025: 1,49 %.')
    assert unsupported_amounts(corrected, [result]) == []
