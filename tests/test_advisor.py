from datetime import date
from decimal import Decimal

import psycopg
import pytest

from backend import advisor
from backend.db import db, one


PERIOD = {'start': '2026-10-01', 'end': '2026-10-31'}


def category(conn, name='Prueba', kind='expense', owner=2):
    return one(conn, 'INSERT INTO categories(user_id,name,kind) VALUES(%s,%s,%s) RETURNING id',
               (owner, name, kind))['id']


def obligation(conn, cat, planned='1000.00', due='2026-10-20', owner=2, title='Compromiso', voided=False):
    return one(conn, '''INSERT INTO obligations(user_id,category_id,title,planned,due_date,voided)
               VALUES(%s,%s,%s,%s,%s,%s) RETURNING id''', (owner, cat, title, planned, due, voided))['id']


def pay(conn, oid, amount, stamp='2026-10-15'):
    conn.execute('INSERT INTO payments(obligation_id,amount,paid_on) VALUES(%s,%s,%s)', (oid, amount, stamp))


def test_advisor_complete_aggregates_before_detail_limit_and_isolation(client):
    with db() as conn:
        income = obligation(conn, category(conn, 'Ingreso prueba', 'income'), '10000')
        pay(conn, income, '10000')
        for index in range(25):
            oid = obligation(conn, category(conn, f'Prueba {index:02d}'))
            pay(conn, oid, '10.11'); pay(conn, oid, '20.22')
        outsider = obligation(conn, category(conn, 'Privado', owner=1), owner=1)
        pay(conn, outsider, '999.99')
        voided = obligation(conn, category(conn, 'Anulado'), voided=True)
        pay(conn, voided, '100')
    result = advisor.execute('spending_breakdown', PERIOD, 2)
    assert result['total_expense'] == '758.25'
    assert result['observed_income'] == '10000.00'
    assert result['payment_count'] == 50
    assert result['total_count'] == 25 and result['has_more']
    assert len(result['items']) == result['detail_limit'] == 20
    assert result['totals_include_all_records']
    assert all(row['amount'] == '30.33' for row in result['items'])
    assert not any(row['category'] == 'Privado' for row in result['items'])


def test_advisor_overview_comparison_and_no_payment_savings_join_product(client):
    with db() as conn:
        inc = obligation(conn, category(conn, 'Ingreso octubre', 'income'), '1000')
        exp = obligation(conn, category(conn, 'Compra octubre'))
        pay(conn, inc, '1000'); pay(conn, exp, '20'); pay(conn, exp, '30')
        pay(conn, exp, '40', '2026-09-30')
        goal = one(conn, "SELECT id FROM goals WHERE user_id=2 LIMIT 1")['id']
        conn.execute('INSERT INTO savings(goal_id,amount,moved_on) VALUES(%s,100,%s),(%s,-25,%s)',
                     (goal, '2026-10-15', goal, '2026-10-16'))
    result = advisor.execute('financial_overview', PERIOD, 2)
    assert result['current']['income'] == '1000.00'
    assert result['current']['expense'] == '50.00'
    assert result['current']['net_savings'] == '75.00'
    assert result['current']['available'] == '875.00'
    assert result['previous']['from'] == '2026-08-31'
    assert result['previous']['to'] == '2026-09-30'
    assert result['changes_gtq']['expense'] == '10.00'
    assert result['expense_to_income_percent'] == '5.00'


def test_advisor_empty_data_is_zero_not_invented(client):
    result = advisor.execute('financial_overview', {'start': '2000-01-01', 'end': '2000-01-31'}, 2)
    assert result['current']['income'] == result['current']['available'] == '0.00'
    assert result['expense_to_income_percent'] is None
    result = advisor.execute('small_expenses', {'start': '2000-01-01', 'end': '2000-01-31', 'threshold': '50'}, 2)
    assert result['candidate_total'] == '0.00' and result['candidate_share_percent'] is None
    assert result['items'] == []


def test_advisor_recurrences_separate_planned_active_and_income(client):
    with db() as conn:
        exp = category(conn, 'Suscripción prueba')
        inc = category(conn, 'Sueldo prueba', 'income')
        outsider = category(conn, 'Suscripción privada', owner=1)
        for owner, cat, amount, active in [(2, exp, '10', True), (2, exp, '20', False), (2, inc, '100', True), (1, outsider, '999', True)]:
            conn.execute('''INSERT INTO recurring(user_id,category_id,title,amount,start_month,active)
                     VALUES(%s,%s,'Plantilla',%s,'2026-10-01',%s)''', (owner, cat, amount, active))
        count_before = one(conn, 'SELECT count(*) AS n FROM obligations')['n']
    result = advisor.execute('recurring_snapshot', {}, 2)
    assert result['total_count'] == 3
    assert {(r['active'], r['kind'], r['monthly_planned']) for r in result['totals']} == {
        (True, 'expense', '10.00'), (False, 'expense', '20.00'), (True, 'income', '100.00')}
    with db() as conn:
        assert one(conn, 'SELECT count(*) AS n FROM obligations')['n'] == count_before


def test_advisor_pending_and_debt_cutoff_classification_and_snowball(client):
    with db() as conn:
        debt = category(conn, 'dEuDaS')
        other = category(conn, 'No son Deudas')
        income = category(conn, 'Ingreso prueba', 'income')
        a = obligation(conn, debt, '100', '2026-09-01', title='Pequeña')
        b = obligation(conn, debt, '300', '2026-10-20', title='Mayor')
        c = obligation(conn, other, '1000', '2026-10-31')
        obligation(conn, income, '9000')
        pay(conn, a, '20'); pay(conn, a, '80', '2026-11-05')
        pay(conn, b, '25'); pay(conn, b, '25')
        pay(conn, c, '100')
        voided = obligation(conn, debt, '8000', voided=True)
        pay(conn, voided, '1')
    result = advisor.execute('debt_snapshot', {'as_of': '2026-10-25'}, 2)
    assert result['total_count'] == 2
    assert result['totals']['remaining'] == '330.00'
    assert result['totals']['overdue'] == '330.00'
    assert result['totals']['carry_from_prior_months'] == '80.00'
    assert [r['remaining'] for r in result['items']] == ['80.00', '250.00']
    assert result['items'][0]['paid_to_cutoff'] == '20.00'
    assert 'APR/tasa' in result['unknown']
    all_pending = advisor.execute('obligations_snapshot', {'as_of': '2026-10-25'}, 2)
    # Seed has two future November expense commitments; without created_at the
    # cutoff reconstructs payments, not the historic inventory of commitments.
    assert all_pending['totals']['remaining'] == '3130.00'
    assert all_pending['totals']['future_due'] == '2800.00'
    assert all_pending['total_count'] == 5


def test_advisor_small_expenses_individual_threshold_not_obligation_or_every_cost(client):
    with db() as conn:
        grocery = obligation(conn, category(conn, 'Compra'))
        debt = obligation(conn, category(conn, 'Deudas'))
        income = obligation(conn, category(conn, 'Ingreso chico', 'income'))
        pay(conn, grocery, '50'); pay(conn, grocery, '50'); pay(conn, grocery, '100')
        pay(conn, debt, '30'); pay(conn, income, '30')
    result = advisor.execute('small_expenses', {**PERIOD, 'threshold': '50'}, 2)
    assert result['candidate_total'] == '100.00'
    assert result['candidate_payment_count'] == 2
    assert result['expense_excluding_debt'] == '200.00'
    assert result['candidate_share_percent'] == '50.00'
    assert len(result['items']) == 1


def test_advisor_budget_scenario_has_all_deltas_without_mutating_data(client):
    args = {'start': '2026-11-01', 'end': '2026-11-30', 'monthly_reduction': '200',
            'monthly_extra_income': '100', 'monthly_extra_debt': '400', 'monthly_extra_savings': '50'}
    result = advisor.execute('budget_scenario', args, 2)
    assert result['base']['available'] == '4100.00'
    assert result['scenario_available'] == '3950.00'
    assert result['feasible_against_observed_flow']
    with pytest.raises(ValueError):
        advisor.execute('budget_scenario', {**args, 'monthly_reduction': '1400.01'}, 2)
    assert advisor.execute('financial_overview', {'start': '2026-11-01', 'end': '2026-11-30'}, 2)['current']['available'] == '4100.00'


def test_advisor_goals_current_balance_isolation_round_up_and_withdrawals(client, monkeypatch):
    monkeypatch.setattr(advisor, 'today', lambda: date(2026, 11, 2))
    with db() as conn:
        goal = one(conn, "INSERT INTO goals(user_id,name,target,deadline) VALUES(2,'Meta exacta',100,'2027-05-01') RETURNING id")['id']
        outsider = one(conn, "INSERT INTO goals(user_id,name,target,deadline) VALUES(1,'Meta privada',100,'2027-05-01') RETURNING id")['id']
        conn.execute('''INSERT INTO savings(goal_id,amount,moved_on) VALUES(%s,20,'2026-11-01'),
                     (%s,-10,'2026-11-02'),(%s,80,'2026-12-01')''', (goal, goal, goal))
    result = advisor.execute('savings_plan', {'goal_id': goal, 'months': 7, 'monthly': '12.85'}, 2)
    assert result['goal']['balance'] == '10.00'
    assert result['required_monthly'] == '12.86'
    assert result['projected_balance'] == '99.95'
    assert result['gap_at_end'] == '0.05'
    assert result['extra_monthly_needed'] == '0.01'
    assert not result['reaches_goal']
    snapshot = advisor.execute('goal_snapshot', {}, 2)
    assert not any(g['name'] == 'Meta privada' for g in snapshot['items'])
    assert next(g for g in snapshot['items'] if g['id'] == goal)['balance'] == '10.00'
    with pytest.raises(ValueError):
        advisor.execute('savings_plan', {'goal_id': outsider, 'months': 1, 'monthly': '100'}, 2)


@pytest.mark.parametrize('bad', ['NaN', 'Infinity', '-1', '0', '1.001', True, 1.2, '100000000000000.00'])
def test_advisor_rejects_invalid_amounts(client, bad):
    with pytest.raises(ValueError):
        advisor.execute('small_expenses', {**PERIOD, 'threshold': bad}, 2)


@pytest.mark.parametrize('args', [
    {'start': '2026-11-01', 'end': '2026-10-01'},
    {'start': '2026-01-01', 'end': '2027-01-02'},
    {'start': '20261101', 'end': '2026-11-30'},
    {'start': '2026-10-01', 'end': '2026-10-31', 'user_id': 1},
])
def test_advisor_validates_dates_and_rejects_extra_scope(client, args):
    with pytest.raises(ValueError):
        advisor.execute('financial_overview', args, 2)


def test_advisor_database_enforces_read_only(client, monkeypatch):
    def accidental_write(conn, user_id, args):
        conn.execute("UPDATE users SET tokens_used=0 WHERE id=%s", (user_id,))
    monkeypatch.setitem(advisor._FUNCTIONS, 'recurring_snapshot', accidental_write)
    with pytest.raises(psycopg.errors.ReadOnlySqlTransaction):
        advisor.execute('recurring_snapshot', {}, 2)


def test_advisor_debt_payment_proxy_uses_registered_income_not_contractual_minimums(client):
    with db() as conn:
        inc = obligation(conn, category(conn, 'Ingreso para proxy', 'income'), '7250')
        debt = obligation(conn, category(conn, 'DEUDAS'))
        pay(conn, inc, '7250'); pay(conn, debt, '750')
    result = advisor.execute('spending_breakdown', PERIOD, 2)
    assert result['debt_payments'] == '750.00'
    assert result['debt_payments_to_observed_income_percent'] == '10.34'
    empty = advisor.execute('spending_breakdown', {'start': '2000-01-01', 'end': '2000-01-31'}, 2)
    assert empty['debt_payments'] == '0.00'
    assert empty['debt_payments_to_observed_income_percent'] is None


def test_advisor_goal_deadline_contributions_cross_year_expired_and_complete(client, monkeypatch):
    monkeypatch.setattr(advisor, 'today', lambda: date(2026, 11, 2))
    with db() as conn:
        cross = one(conn, "INSERT INTO goals(user_id,name,target,deadline) VALUES(2,'Entre años',100,'2027-01-01') RETURNING id")['id']
        expired = one(conn, "INSERT INTO goals(user_id,name,target,deadline) VALUES(2,'Vencida',100,'2026-11-01') RETURNING id")['id']
        complete = one(conn, "INSERT INTO goals(user_id,name,target,deadline) VALUES(2,'Lograda vencida',100,'2026-11-01') RETURNING id")['id']
        conn.execute("INSERT INTO savings(goal_id,amount,moved_on) VALUES(%s,100,'2026-11-01')", (complete,))
    result = advisor.execute('goal_snapshot', {}, 2)
    rows = {r['id']: r for r in result['items']}
    assert rows[cross]['remaining_contributions'] == 3
    assert rows[cross]['required_monthly_to_deadline'] == '33.34'
    assert rows[cross]['days_to_deadline'] == 60
    assert rows[expired]['remaining_contributions'] == 0
    assert rows[expired]['required_monthly_to_deadline'] is None
    assert rows[complete]['required_monthly_to_deadline'] == '0.00'
    assert result['totals']['expired_active_count'] == 1
    assert result['totals']['in_progress_count'] == 2
    assert result['totals']['completed_active_count'] == 1
    assert rows[cross]['state'] == 'en progreso'
    assert rows[expired]['state'] == 'vencida'
    assert rows[complete]['state'] == 'cumplida'
    # Seed contribution is future-dated: 5000/6 rounded up = 833.34,
    # plus 33.34 for the cross-year goal; the expired goal is not allocated.
    assert result['totals']['active_required_monthly'] == '866.68'
