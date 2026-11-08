import json
from datetime import date
from decimal import Decimal

import psycopg
import pytest

from backend import advisor, demo, planning
from backend.db import db, one


def load_demo(monkeypatch):
    monkeypatch.setattr(advisor, 'today', lambda: date(2026, 11, 8))
    with db() as conn:
        demo.populate_demo(conn)


def test_planning_uses_closed_month_margin_and_exact_goal_ranking(client, monkeypatch):
    load_demo(monkeypatch)
    result = planning.execute({}, 2)
    assert result['as_of'] == '2026-11-08'
    assert result['current_partial']['from'] == '2026-11-01'
    assert result['current_partial']['to'] == '2026-11-08'
    assert result['current_partial']['available'] == '3698.00'
    assert result['last_closed_month']['from'] == '2026-10-01'
    assert result['last_closed_month']['to'] == '2026-10-31'
    assert result['last_closed_month']['income'] == '7250.00'
    assert result['last_closed_month']['available'] == '73.00'
    assert result['historical_margin'] == '73.00'
    assert result['active_future_goal_count'] == 3
    assert result['active_future_required'] == '2316.67'
    assert result['largest_required_goal']['name'] == 'Computadora para trabajo freelance'
    assert result['largest_required_goal']['monthly_required'] == '1025.00'
    assert result['affordability_gap'] == '2243.67'
    assert result['verified_affordable_contribution'] is None
    assert result['goals']['total_count'] == len(result['goals']['items']) == 6
    assert not result['goals']['has_more']
    goals = {row['name']: row for row in result['goals']['items']}
    assert goals['Fondo de emergencia']['monthly_required'] == '741.67'
    assert goals['Curso corto completado']['state'] == 'cumplida'
    assert goals['Curso corto completado']['monthly_required'] == '0.00'
    expired = next(row for row in result['goals']['items'] if row['state'] == 'vencida')
    assert expired['remaining'] == '600.00' and expired['monthly_required'] is None
    assert result['expired_active_goal_count'] == 1
    inactive = next(row for row in result['goals']['items'] if not row['active'])
    assert inactive['monthly_required'] is None
    assert result['debt']['total_pending'] == '7900.00' and result['debt']['count'] == 3
    assert len(json.dumps(result, ensure_ascii=False)) <= 3500


def test_planning_is_user_scoped_and_does_not_invent_capacity_for_empty_account(client, monkeypatch):
    load_demo(monkeypatch)
    result = planning.execute({}, 1)
    assert result['goals']['items'] == []
    assert result['active_future_goal_count'] == 0
    assert result['active_future_required'] == result['historical_margin'] == result['affordability_gap'] == '0.00'
    assert result['largest_required_goal'] is None
    assert result['debt']['count'] == 0 and result['debt']['total_pending'] == '0.00'
    assert result['verified_affordable_contribution'] is None
    assert result['current_partial']['income'] == result['last_closed_month']['income'] == '0.00'


def test_planning_excludes_future_income_debt_payments_and_savings(client, monkeypatch):
    load_demo(monkeypatch)
    before = planning.execute({}, 2)
    with db() as conn:
        debt = one(conn, '''SELECT o.id FROM obligations o JOIN categories c ON c.id=o.category_id
                     WHERE o.user_id=2 AND c.name='Deudas' ORDER BY o.id LIMIT 1''')['id']
        goal = one(conn, "SELECT id FROM goals WHERE user_id=2 AND name='Fondo de emergencia'")['id']
        income = one(conn, 'SELECT id FROM obligations WHERE user_id=2 AND title LIKE %s LIMIT 1', ('Diseño gráfico noviembre%',))['id']
        conn.execute("INSERT INTO payments(obligation_id,amount,paid_on) VALUES(%s,50,'2026-11-09'),(%s,700,'2026-11-09')", (debt, income))
        conn.execute("INSERT INTO savings(goal_id,amount,moved_on) VALUES(%s,300,'2026-11-09')", (goal,))
    assert planning.execute({}, 2) == before


def test_planning_uses_full_calendar_month_across_year_boundary(client, monkeypatch):
    load_demo(monkeypatch)
    monkeypatch.setattr(advisor, 'today', lambda: date(2027, 1, 10))
    result = planning.execute({}, 2)
    assert result['last_closed_month']['from'] == '2026-12-01'
    assert result['last_closed_month']['to'] == '2026-12-31'
    assert result['current_partial']['from'] == '2027-01-01'
    assert result['current_partial']['to'] == '2027-01-10'
    assert result['last_closed_month']['income'] == '0.00'


def test_planning_sums_all_goals_before_limiting_details_and_handles_negative_margin(client, monkeypatch):
    load_demo(monkeypatch)
    with db() as conn:
        for index in range(15):
            conn.execute("INSERT INTO goals(user_id,name,target,deadline) VALUES(2,%s,1,'2027-12-31')", (f'Meta extra {index}',))
        huge = one(conn, "INSERT INTO goals(user_id,name,target,deadline) VALUES(2,'Necesidad mayor',100000,'2027-12-31') RETURNING id")['id']
        university = one(conn, "SELECT id FROM obligations WHERE user_id=2 AND title='Universidad noviembre'")['id']
        # A real October payment of an obligation due in November still belongs
        # to the October cash flow. This makes its historical available negative.
        conn.execute("INSERT INTO payments(obligation_id,amount,paid_on) VALUES(%s,100,'2026-10-31')", (university,))
    result = planning.execute({}, 2)
    assert result['last_closed_month']['available'] == '-27.00'
    assert result['historical_margin'] == '0.00'
    assert result['affordability_gap'] == result['active_future_required']
    assert result['goals']['total_count'] == 22
    assert len(result['goals']['items']) == planning.GOAL_LIMIT and result['goals']['has_more']
    assert result['largest_required_goal']['id'] == huge
    assert Decimal(result['active_future_required']) > Decimal('2316.67')


@pytest.mark.parametrize('args,user', [({'user_id': 1}, 2), ([], 2), ({}, True), ({}, -1), ({}, '2')])
def test_planning_rejects_scope_overrides_and_invalid_arguments(client, args, user):
    with pytest.raises(ValueError):
        planning.execute(args, user)


def test_planning_database_enforces_read_only(client, monkeypatch):
    def accidental_write(conn, user_id, start, end):
        conn.execute('UPDATE users SET tokens_used=0 WHERE id=%s', (user_id,))
    monkeypatch.setattr(planning, 'finance_summary', accidental_write)
    with pytest.raises(psycopg.errors.ReadOnlySqlTransaction):
        planning.execute({}, 2)
