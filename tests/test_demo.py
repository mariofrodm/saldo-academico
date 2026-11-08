from datetime import date
from decimal import Decimal

import pytest

from backend import demo
from backend.db import db, many, one
from backend.domain import board, finance_summary


def test_demo_is_additive_idempotent_and_preserves_accounts(client):
    with db() as conn:
        original_users = many(conn, 'SELECT * FROM users ORDER BY id')
        original_services = many(conn, 'SELECT * FROM services ORDER BY id')
        original_payments = many(conn, 'SELECT id,obligation_id,amount FROM payments ORDER BY id')
        other_category = one(conn, "INSERT INTO categories(user_id,name,kind) VALUES(1,'Otro usuario','expense') RETURNING id")
        other_obligation = one(conn, '''INSERT INTO obligations(user_id,category_id,title,planned,due_date)
            VALUES(1,%s,'No modificar',75,'2026-11-05') RETURNING *''', (other_category['id'],))
        first = demo.populate_demo(conn, user_id=2)
        assert first['already_present'] is False
        assert first['normalized_legacy_dates'] == 4
        assert first['counts'] == {'categories': 15, 'obligations': 184, 'recurring': 8, 'goals': 6,
                                   'payments': 177, 'savings': 12}
        assert first['created'] == {'categories': 12, 'obligations': 181, 'payments': 174,
                                    'recurring': 8, 'goals': 5, 'savings': 11}
        before_second = {table: many(conn, f'SELECT * FROM {table} ORDER BY id')
                         for table in ('users', 'categories', 'obligations', 'payments', 'goals', 'savings', 'recurring', 'audit')}
        second = demo.populate_demo(conn)
        assert second['already_present'] is True and second['created'] == {}
        assert second['counts'] == first['counts']
        for table, rows in before_second.items():
            assert many(conn, f'SELECT * FROM {table} ORDER BY id') == rows
        assert many(conn, 'SELECT * FROM users ORDER BY id') == original_users
        assert many(conn, 'SELECT * FROM services ORDER BY id') == original_services
        assert many(conn, 'SELECT id,obligation_id,amount FROM payments WHERE id<=3 ORDER BY id') == original_payments
        assert one(conn, 'SELECT * FROM obligations WHERE id=%s', (other_obligation['id'],)) == other_obligation
        assert one(conn, 'SELECT count(*) AS n FROM requests')['n'] == 0
        assert one(conn, 'SELECT count(*) AS n FROM budgets')['n'] == 0
        assert one(conn, "SELECT count(*) AS n FROM audit WHERE action='demo_seed_v1'")['n'] == 1


def test_demo_cash_flows_debts_and_savings_are_reconcilable(client):
    with db() as conn:
        result = demo.populate_demo(conn)
        for month, end, income, expense, savings, available in [
            (9, 30, '6900.00', '6297.00', '500.00', '103.00'),
            (10, 31, '7250.00', '7177.00', '0.00', '73.00'),
            (11, 2, '6000.00', '1677.00', '625.00', '3698.00')]:
            summary = finance_summary(conn, 2, date(2026, month, 1), date(2026, month, end))
            assert [summary[key] for key in ('income', 'expense', 'net_savings', 'available')] == list(map(Decimal, (income, expense, savings, available)))
        debts = result['debts']
        assert [row['remaining'] for row in debts] == list(map(Decimal, ('550', '2050', '5300')))
        assert sum(row['planned'] for row in debts) == Decimal('9400')
        assert sum(row['paid'] for row in debts) == Decimal('1500')
        assert sum(row['remaining'] for row in debts) == Decimal('7900')
        assert one(conn, '''SELECT count(*) AS n FROM obligations o JOIN categories c ON c.id=o.category_id
            WHERE o.user_id=2 AND c.name='Deudas' ''')['n'] == 3
        # Los 9400 de principal previsto no se suman al gasto: solo los abonos.
        assert one(conn, '''SELECT sum(p.amount) AS total FROM payments p JOIN obligations o ON o.id=p.obligation_id
            JOIN categories c ON c.id=o.category_id WHERE o.user_id=2 AND c.name='Deudas'
            AND p.paid_on BETWEEN '2026-10-01' AND '2026-10-31' ''')['total'] == Decimal('750')
        goals = many(conn, '''SELECT g.name,g.target,g.deadline,g.active,coalesce(sum(s.amount),0) AS balance FROM goals g LEFT JOIN savings s ON s.goal_id=g.id
            WHERE g.user_id=2 GROUP BY g.id ORDER BY g.id''')
        assert [row['balance'] for row in goals] == list(map(Decimal, ('550', '400', '150', '0', '25', '0')))
        completed = next(row for row in goals if row['name'] == 'Curso corto completado')
        assert completed['active'] and completed['balance'] == completed['target']
        overdue = next(row for row in goals if row['name'] == 'Renovación de equipo · plazo vencido')
        assert overdue['active'] and overdue['deadline'] < demo.CUTOFF and overdue['balance'] == 0
        # Revisión cronológica del libro de ahorro, no solo del saldo final.
        balances = {}
        for row in many(conn, '''SELECT s.* FROM savings s JOIN goals g ON g.id=s.goal_id
                WHERE g.user_id=2 ORDER BY s.moved_on,s.id'''):
            balances[row['goal_id']] = balances.get(row['goal_id'], Decimal(0)) + row['amount']
            assert balances[row['goal_id']] >= 0


def test_demo_dates_variety_and_monthly_snapshots(client):
    with db() as conn:
        result = demo.populate_demo(conn)
        assert result['existing_future_movements'] == 0
        assert one(conn, 'SELECT max(paid_on) AS last FROM payments')['last'] == date(2026, 11, 2)
        assert one(conn, 'SELECT max(moved_on) AS last FROM savings')['last'] == date(2026, 11, 2)
        assert one(conn, 'SELECT count(*) AS n FROM recurring WHERE active')['n'] == 7
        assert one(conn, 'SELECT count(*) AS n FROM recurring WHERE NOT active')['n'] == 1
        assert one(conn, 'SELECT count(*) AS n FROM goals WHERE NOT active')['n'] == 1
        assert one(conn, '''SELECT count(*) AS n FROM obligations o LEFT JOIN payments p ON p.obligation_id=o.id
            WHERE o.voided AND p.id IS NOT NULL''')['n'] == 0
        assert one(conn, 'SELECT count(*) AS n FROM obligations WHERE voided')['n'] == 1
        partial = many(conn, '''SELECT o.title,o.planned,sum(p.amount) AS paid FROM obligations o
            JOIN payments p ON p.obligation_id=o.id GROUP BY o.id HAVING sum(p.amount)<o.planned''')
        assert any('Universidad' in row['title'] for row in partial)
        assert any('frenos' in row['title'] for row in partial)
        assert one(conn, '''SELECT count(*) AS n FROM obligations o LEFT JOIN payments p ON p.obligation_id=o.id
            WHERE o.user_id=2 AND NOT o.voided AND p.id IS NULL''')['n'] >= 11
        september = one(conn, "SELECT count(*) AS n FROM payments WHERE paid_on BETWEEN '2026-09-01' AND '2026-09-30'")['n']
        october = one(conn, "SELECT count(*) AS n FROM payments WHERE paid_on BETWEEN '2026-10-01' AND '2026-10-31'")['n']
        assert october > september >= 70
        # Ver el mes actual no crea duplicados de partidas existentes; diciembre
        # materializa solo las siete plantillas activas y conserva su idempotencia.
        before = one(conn, 'SELECT count(*) AS n FROM obligations')['n']
        board(conn, 2, date(2026, 11, 1))
        assert one(conn, 'SELECT count(*) AS n FROM obligations')['n'] == before
        board(conn, 2, date(2026, 12, 1))
        board(conn, 2, date(2026, 12, 1))
        assert one(conn, 'SELECT count(*) AS n FROM obligations')['n'] == before + 7


def test_demo_guards_and_transactional_rollback(client, monkeypatch):
    with db() as conn:
        baseline = one(conn, 'SELECT count(*) AS n FROM obligations')['n']
        audit_before = many(conn, 'SELECT * FROM audit ORDER BY id')
        monkeypatch.setenv('APP_ENV', 'production')
        with pytest.raises(ValueError, match='APP_ENV=local'):
            demo.populate_demo(conn)
        monkeypatch.setenv('APP_ENV', 'local')
        with pytest.raises(ValueError, match='demo@example.test'):
            demo.populate_demo(conn, user_id=1)
        assert one(conn, 'SELECT count(*) AS n FROM obligations')['n'] == baseline
        def fail_after_writes(*args):
            raise RuntimeError('Fallo simulado después de insertar el escenario')
        monkeypatch.setattr(demo, '_summary', fail_after_writes)
        with pytest.raises(RuntimeError, match='Fallo simulado'):
            demo.populate_demo(conn)
        assert one(conn, 'SELECT count(*) AS n FROM obligations')['n'] == baseline
        assert many(conn, 'SELECT * FROM audit ORDER BY id') == audit_before
        assert one(conn, 'SELECT min(paid_on) AS first FROM payments')['first'] == date(2026, 11, 5)


def test_demo_does_not_normalize_later_user_payments(client):
    with db() as conn:
        # Coincide en importe, título y fecha, pero es un abono posterior del
        # usuario: la corrección legacy se restringe al primer registro original.
        obligation_id = one(conn, "SELECT id FROM obligations WHERE title='Universidad noviembre'")['id']
        payment = one(conn, '''INSERT INTO payments(obligation_id,amount,paid_on)
            VALUES(%s,400,'2026-11-05') RETURNING id''', (obligation_id,))
        result = demo.populate_demo(conn)
        assert one(conn, 'SELECT paid_on FROM payments WHERE id=%s', (payment['id'],))['paid_on'] == date(2026, 11, 5)
        assert result['existing_future_movements'] == 1
