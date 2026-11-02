from datetime import date
from decimal import Decimal
from fastapi import HTTPException
from .db import one, many, money


def owned(conn, table, entity_id, user):
    # table comes exclusively from internal constants, never request input.
    assert table in ('categories', 'obligations', 'goals', 'recurring')
    row = one(conn, f'SELECT * FROM {table} WHERE id=%s AND user_id=%s FOR UPDATE', (entity_id, user['id']))
    if not row:
        raise HTTPException(404, 'Registro no encontrado')
    return row


def instantiate(conn, user_id, month):
    start = month.replace(day=1)
    conn.execute('''INSERT INTO obligations(user_id,category_id,title,planned,due_date,recurring_id)
                    SELECT user_id,category_id,title,amount,%s,id FROM recurring
                    WHERE user_id=%s AND active AND start_month<=%s
                    ON CONFLICT(recurring_id,due_date) DO NOTHING''', (start, user_id, start))


def board(conn, user_id, month):
    instantiate(conn, user_id, month)
    return many(conn, '''SELECT o.*, c.name AS category, c.kind,
                    coalesce(sum(p.amount),0) AS executed,
                    greatest(o.planned-coalesce(sum(p.amount),0),0) AS remaining,
                    o.due_date<date_trunc('month',%s::date) AS rollover
                    FROM obligations o JOIN categories c ON c.id=o.category_id
                    LEFT JOIN payments p ON p.obligation_id=o.id
                    WHERE o.user_id=%s AND NOT o.voided
                    AND o.due_date<date_trunc('month',%s::date)+interval '1 month'
                    GROUP BY o.id,c.name,c.kind
                    HAVING date_trunc('month',o.due_date)=date_trunc('month',%s::date)
                       OR o.planned>coalesce(sum(p.amount),0)
                    ORDER BY o.due_date,o.id''', (month, user_id, month, month))


def finance_summary(conn, user_id, start, end):
    if start > end:
        raise HTTPException(422, 'Período inválido')
    rows = many(conn, '''SELECT c.kind, coalesce(sum(p.amount),0) AS total FROM payments p
                JOIN obligations o ON o.id=p.obligation_id JOIN categories c ON c.id=o.category_id
                WHERE o.user_id=%s AND NOT o.voided AND p.paid_on BETWEEN %s AND %s
                GROUP BY c.kind''', (user_id, start, end))
    totals = {r['kind']: r['total'] for r in rows}
    savings = one(conn, '''SELECT coalesce(sum(s.amount),0) AS total FROM savings s
                           JOIN goals g ON g.id=s.goal_id
                           WHERE g.user_id=%s AND s.moved_on BETWEEN %s AND %s''', (user_id, start, end))['total']
    income, expense = totals.get('income', Decimal(0)), totals.get('expense', Decimal(0))
    return {'income': money(income), 'expense': money(expense), 'net_savings': money(savings),
            'available': money(income-expense-savings), 'currency': 'GTQ', 'from': start, 'to': end}


def goal_rows(conn, user_id):
    return many(conn, '''SELECT g.*,coalesce(sum(s.amount),0) AS balance FROM goals g
                         LEFT JOIN savings s ON s.goal_id=g.id WHERE g.user_id=%s
                         GROUP BY g.id ORDER BY g.id''', (user_id,))
