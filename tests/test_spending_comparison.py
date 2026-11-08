"""Exact comparisons and refreshed facts, using the isolated test database only."""
from datetime import date

import pytest

from backend import advisor, ai, demo
from backend.conversation import build_context
from backend.db import db, many, one


OCTOBER = {'start': '2026-10-01', 'end': '2026-10-31'}
COMPARISON = {**OCTOBER, 'category_a': 'Alimentación', 'category_b': 'Universidad'}


@pytest.fixture
def comparison_scenario(client):
    with db() as conn:
        uid = one(conn, "SELECT id FROM users WHERE email='demo@example.test'")['id']
        demo.populate_demo(conn, user_id=uid)
    return uid


def snapshot():
    """Financial rows and quota counters; never read passwords or session tokens."""
    with db() as conn:
        return {
            'categories': many(conn, 'SELECT id,user_id,name,kind,active FROM categories ORDER BY id'),
            'obligations': many(conn, 'SELECT id,user_id,category_id,title,planned,due_date,voided FROM obligations ORDER BY id'),
            'payments': many(conn, 'SELECT id,obligation_id,amount,paid_on FROM payments ORDER BY id'),
            'users': many(conn, 'SELECT id,active,token_limit,tokens_used,tokens_reserved FROM users ORDER BY id'),
            'requests': one(conn, 'SELECT count(*) AS n FROM requests')['n'],
            'audit': one(conn, 'SELECT count(*) AS n FROM audit')['n'],
        }


def add_payment(conn, uid, category_name, amount):
    category = one(conn, 'SELECT id FROM categories WHERE user_id=%s AND name=%s AND kind=%s',
                   (uid, category_name, 'expense'))
    if not category:
        category = one(conn, 'INSERT INTO categories(user_id,name,kind) VALUES(%s,%s,%s) RETURNING id',
                       (uid, category_name, 'expense'))
    obligation = one(conn, '''INSERT INTO obligations(user_id,category_id,title,planned,due_date)
        VALUES(%s,%s,'Pago de comparación',%s,'2026-10-15') RETURNING id''',
        (uid, category['id'], amount))
    conn.execute("INSERT INTO payments(obligation_id,amount,paid_on) VALUES(%s,%s,'2026-10-15')",
                 (obligation['id'], amount))


def test_comparison_october_uses_executed_payments_and_exact_difference(comparison_scenario):
    before = snapshot()
    result = advisor.execute('compare_spending', COMPARISON, comparison_scenario)
    assert result['source_id'] == 'SCOMPARA' and result['currency'] == 'GTQ'
    assert result['period']['start'] == OCTOBER['start']
    assert result['period']['end'] == OCTOBER['end']
    assert result['items'] == [{'category': 'Alimentación', 'amount': '1000.00'},
                               {'category': 'Universidad', 'amount': '900.00'}]
    assert result['difference_gtq'] == '100.00'
    assert result['higher_category'] == 'Alimentación' and result['equal'] is False
    reverse = advisor.execute('compare_spending', {**COMPARISON, 'category_a': 'Universidad',
                                                 'category_b': 'Alimentación'}, comparison_scenario)
    assert reverse['difference_gtq'] == '100.00'
    assert reverse['higher_category'] == 'Alimentación'
    assert snapshot() == before


@pytest.mark.parametrize('first,second', [
    ('  ALIMENTACION  ', 'uNiVeRsIdAd'),
    ('alimentación', ' UNIVERSIDAD '),
    ('Alimentacio\u0301n', 'universidad'),
])
def test_comparison_accepts_case_accents_and_surrounding_spaces(comparison_scenario, first, second):
    result = advisor.execute('compare_spending', {**OCTOBER, 'category_a': first,
                                                 'category_b': second}, comparison_scenario)
    assert [item['amount'] for item in result['items']] == ['1000.00', '900.00']
    assert result['difference_gtq'] == '100.00'
    assert result['higher_category'] == 'Alimentación'


def test_existing_category_without_payments_is_zero_but_unknown_is_not(comparison_scenario):
    with db() as conn:
        conn.execute("INSERT INTO categories(user_id,name,kind) VALUES(%s,'Sin ejecución','expense')",
                     (comparison_scenario,))
    before = snapshot()
    known = advisor.execute('compare_spending', {**COMPARISON, 'category_b': 'Sin ejecución'}, comparison_scenario)
    assert known['items'][1] == {'category': 'Sin ejecución', 'amount': '0.00'}
    assert known['difference_gtq'] == '1000.00' and known['equal'] is False
    empty_period = advisor.execute('compare_spending', {**COMPARISON, 'start': '2000-01-01',
                                                       'end': '2000-01-31'}, comparison_scenario)
    assert [row['amount'] for row in empty_period['items']] == ['0.00', '0.00']
    assert empty_period['equal'] is True and empty_period['higher_category'] is None
    assert empty_period['difference_gtq'] == '0.00'
    for unknown in ('Categoría inexistente', 'Sueldo'):
        with pytest.raises(ValueError):
            advisor.execute('compare_spending', {**COMPARISON, 'category_b': unknown}, comparison_scenario)
    assert snapshot() == before


def test_normalized_ambiguous_category_requires_clarification(comparison_scenario):
    with db() as conn:
        conn.execute("INSERT INTO categories(user_id,name,kind) VALUES(%s,'Alimentacion','expense')",
                     (comparison_scenario,))
    before = snapshot()
    with pytest.raises(ValueError):
        advisor.execute('compare_spending', COMPARISON, comparison_scenario)
    assert snapshot() == before


def test_comparison_excludes_unpaid_plans_voided_and_other_month_payments(comparison_scenario):
    with db() as conn:
        category = one(conn, "SELECT id FROM categories WHERE user_id=%s AND name='Alimentación'", (comparison_scenario,))
        conn.execute('''INSERT INTO obligations(user_id,category_id,title,planned,due_date)
            VALUES(%s,%s,'Solo previsto',9000,'2026-10-20')''', (comparison_scenario, category['id']))
        voided = one(conn, '''INSERT INTO obligations(user_id,category_id,title,planned,due_date,voided)
            VALUES(%s,%s,'Anulado',777,'2026-10-20',true) RETURNING id''', (comparison_scenario, category['id']))
        conn.execute("INSERT INTO payments(obligation_id,amount,paid_on) VALUES(%s,777,'2026-10-20')", (voided['id'],))
        later = one(conn, '''INSERT INTO obligations(user_id,category_id,title,planned,due_date)
            VALUES(%s,%s,'Pago de noviembre',999,'2026-10-25') RETURNING id''', (comparison_scenario, category['id']))
        conn.execute("INSERT INTO payments(obligation_id,amount,paid_on) VALUES(%s,999,'2026-11-02')", (later['id'],))
    before = snapshot()
    result = advisor.execute('compare_spending', COMPARISON, comparison_scenario)
    assert [row['amount'] for row in result['items']] == ['1000.00', '900.00']
    assert result['difference_gtq'] == '100.00'
    assert snapshot() == before


def test_comparison_cannot_read_other_users_payments(comparison_scenario, auth, admin_auth, client):
    with db() as conn:
        other = one(conn, "SELECT id FROM users WHERE email='admin@example.test'")['id']
        add_payment(conn, other, 'Alimentación', '9999.00')
        add_payment(conn, other, 'Universidad', '1234.00')
        conn.execute("INSERT INTO categories(user_id,name,kind) VALUES(%s,'Solo del administrador','expense')", (other,))
    before = snapshot()
    own = client.post('/api/v1/advisor/compare_spending', headers=auth, json={'arguments': COMPARISON})
    assert own.status_code == 200 and own.json()['difference_gtq'] == '100.00'
    other_result = client.post('/api/v1/advisor/compare_spending', headers=admin_auth,
                               json={'arguments': COMPARISON})
    assert other_result.status_code == 200
    assert [row['amount'] for row in other_result.json()['items']] == ['9999.00', '1234.00']
    hidden = client.post('/api/v1/advisor/compare_spending', headers=auth,
                         json={'arguments': {**COMPARISON, 'category_b': 'Solo del administrador'}})
    assert hidden.status_code == 422
    injected = client.post('/api/v1/advisor/compare_spending', headers=auth,
                           json={'arguments': {**COMPARISON, 'user_id': other}})
    assert injected.status_code == 422
    assert snapshot() == before


@pytest.mark.parametrize('changes', [
    {'category_a': ''}, {'category_a': '   '}, {'category_a': None},
    {'category_a': True}, {'category_a': 7}, {'category_a': []},
    {'category_b': {'name': 'Universidad'}}, {'category_b': 'x' * 81},
    {'start': '2026-02-30'}, {'start': 20261001}, {'end': None},
    {'start': '2026-11-01', 'end': '2026-10-31'},
    {'start': '2025-01-01', 'end': '2026-01-02'},
    {'user_id': 1}, {'category_a': "Alimentación'; DROP TABLE payments; --"},
])
def test_invalid_comparison_arguments_do_not_mutate_records(comparison_scenario, changes):
    before = snapshot()
    with pytest.raises(ValueError):
        advisor.execute('compare_spending', {**COMPARISON, **changes}, comparison_scenario)
    assert snapshot() == before


def test_comparison_manifest_and_missing_argument_rejection(client, auth, comparison_scenario):
    client.cookies.clear()
    assert client.get('/api/v1/advisor/tools').status_code == 401
    response = client.get('/api/v1/advisor/tools', headers=auth)
    assert response.status_code == 200
    tool = next(item['function'] for item in response.json()['tools'] if item['function']['name'] == 'compare_spending')
    assert set(tool['parameters']['required']) == {'start', 'end', 'category_a', 'category_b'}
    assert tool['parameters']['additionalProperties'] is False
    missing = {key: value for key, value in COMPARISON.items() if key != 'category_b'}
    before = snapshot()
    result = client.post('/api/v1/advisor/compare_spending', headers=auth, json={'arguments': missing})
    assert result.status_code == 422
    assert snapshot() == before


def october_context(prompt):
    previous = [{'status': 'success', 'prompt': '¿En qué gasté más en octubre de 2026?',
                 'response': 'Una respuesta anterior no es una cifra actual.',
                 'tools': [{'name': 'spending_breakdown', 'arguments': dict(OCTOBER),
                            'result': {'source_id': 'SGASTOS', 'period': dict(OCTOBER), 'items': []}}]}]
    return build_context(previous, prompt, date(2026, 11, 8))


def test_prefetch_resolves_same_october_and_rereads_backend_facts(comparison_scenario, monkeypatch):
    monkeypatch.setattr(ai, 'completion', lambda *_: pytest.fail('Esta consulta no debe llamar al proveedor'))
    prompt = 'En ese mes, ¿gasté más en alimentación o en universidad?'
    context = october_context(prompt)
    assert context['period_hint'] == {'kind': 'context_same', 'period': OCTOBER}
    fetched = ai.prefetch_facts(prompt, context, comparison_scenario)
    assert len(fetched) == 1
    name, arguments, result = fetched[0]
    assert name == 'compare_spending'
    assert {arguments['category_a'], arguments['category_b']} == {'Alimentación', 'Universidad'}
    assert {key: arguments[key] for key in OCTOBER} == OCTOBER
    assert result['difference_gtq'] == '100.00'
    with db() as conn:
        add_payment(conn, comparison_scenario, 'Alimentación', '9.99')
    refreshed = ai.prefetch_facts(prompt, context, comparison_scenario)[0][2]
    assert refreshed['difference_gtq'] == '109.99'
    assert next(row['amount'] for row in refreshed['items'] if row['category'] == 'Alimentación') == '1009.99'


def test_difference_followup_uses_remembered_categories_but_fresh_amounts(comparison_scenario):
    context = october_context('¿Cuánto de diferencia?')
    context['state']['comparison'] = {'category_a': 'Alimentación', 'category_b': 'Universidad'}
    context['period_hint'] = {'kind': 'context_same', 'period': dict(OCTOBER)}
    fetched = ai.prefetch_facts('¿Cuánto de diferencia?', context, comparison_scenario)
    assert len(fetched) == 1 and fetched[0][0] == 'compare_spending'
    assert fetched[0][1] == COMPARISON
    assert fetched[0][2]['difference_gtq'] == '100.00'


@pytest.mark.parametrize('prompt', ['En ese mes, compara alimentación y universidad.',
                                  'Compara alimentación y universidad en octubre y noviembre de 2026.'])
def test_prefetch_does_not_invent_period_for_missing_or_multiple_references(comparison_scenario, prompt):
    context = build_context([], prompt, date(2026, 11, 8))
    assert context['period_hint']['kind'] in ('clarify', 'explicit_multiple')
    before = snapshot()
    assert ai.prefetch_facts(prompt, context, comparison_scenario) == []
    assert snapshot() == before
