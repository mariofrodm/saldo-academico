"""Verified planning facts; a mathematical need is not a spending commitment."""
from datetime import timedelta
from decimal import Decimal, ROUND_CEILING

from . import advisor
from .db import many
from .domain import finance_summary


TOOL = advisor.tool('planning_snapshot',
    'Planificación de metas con contexto: mes actual parcial, último mes calendario cerrado, '
    'todas las necesidades de ahorro, mayor aporte requerido y brecha contra margen histórico. '
    'Incluye deudas registradas. No calcula dinero realmente disponible ni aportes asequibles.', {}, [])
GOAL_LIMIT = 10
DEBT_LIMIT = 5


def execute(args, user_id):
    if not isinstance(args, dict) or args:
        raise ValueError('Argumentos inválidos')
    if isinstance(user_id, bool) or not isinstance(user_id, int) or user_id < 1:
        raise ValueError('Usuario inválido')
    stamp = advisor.today()
    current_start = stamp.replace(day=1)
    closed_end = current_start - timedelta(days=1)
    closed_start = closed_end.replace(day=1)
    with advisor.db() as conn:
        conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
        current = finance_summary(conn, user_id, current_start, stamp)
        closed = finance_summary(conn, user_id, closed_start, closed_end)
        rows = many(conn, '''SELECT g.id,g.name,g.deadline,g.active,g.target,
                   coalesce(sum(s.amount) FILTER(WHERE s.moved_on<=%s),0) AS balance
                   FROM goals g LEFT JOIN savings s ON s.goal_id=g.id WHERE g.user_id=%s
                   GROUP BY g.id ORDER BY g.active DESC,g.deadline,g.id''', (stamp, user_id))
        goals, future = [], []
        expired_count = 0
        for row in rows:
            remaining = max(Decimal(0), row['target']-row['balance'])
            state = ('inactiva' if not row['active'] else 'cumplida' if remaining == 0
                     else 'vencida' if row['deadline'] < stamp else 'en progreso')
            monthly = Decimal(0) if state == 'cumplida' else None
            if state == 'en progreso':
                contributions = (row['deadline'].year-stamp.year)*12+row['deadline'].month-stamp.month+1
                monthly = (remaining/Decimal(contributions)).quantize(Decimal('.01'), rounding=ROUND_CEILING)
            goal = {'id': row['id'], 'name': row['name'], 'balance': row['balance'], 'remaining': remaining,
                    'monthly_required': monthly, 'deadline': row['deadline'], 'active': row['active'], 'state': state}
            goals.append(goal)
            if state == 'en progreso':
                future.append(goal)
            elif state == 'vencida':
                expired_count += 1
        required = sum((row['monthly_required'] for row in future), Decimal(0))
        largest = max(future, key=lambda row: row['monthly_required'], default=None)
        largest = {key: largest[key] for key in ('id', 'name', 'monthly_required')} if largest else None
        debt = advisor.debt_snapshot(conn, user_id, {'as_of': stamp.isoformat()})
        historical_margin = max(Decimal(0), closed['available'])
        return advisor._clean({
            'source_id': 'SPLAN', 'currency': 'GTQ', 'as_of': stamp,
            'current_partial': current, 'last_closed_month': closed,
            'goals': {'items': goals[:GOAL_LIMIT], 'total_count': len(goals), 'detail_limit': GOAL_LIMIT,
                      'has_more': len(goals) > GOAL_LIMIT},
            'active_future_goal_count': len(future), 'expired_active_goal_count': expired_count,
            'active_future_required': required, 'largest_required_goal': largest,
            'historical_margin': historical_margin,
            'affordability_gap': max(Decimal(0), required-historical_margin),
            'verified_affordable_contribution': None,
            'debt': {'total_pending': debt['totals']['remaining'], 'count': debt['total_count'],
                     'items': [{'name': row['title'], 'remaining': row['remaining']}
                               for row in debt['items'][:DEBT_LIMIT]],
                     'has_more': debt['total_count'] > DEBT_LIMIT},
            'constraints': [
                'Margen histórico del último mes cerrado, no proyección, saldo bancario ni dinero libre actual; mes actual parcial.',
                'Necesidad: un aporte por mes incluido el actual antes de la fecha meta, sin intereses. Totales y mayor aporte incluyen todas las metas propias, no solo detalles visibles.',
                'No asignar aportes ni porcentajes sin confirmar capacidad y prioridades. Mayor aporte requerido no significa mayor prioridad. Revisar esenciales y pagos próximos antes de comprometer dinero.',
                'No conocemos tasas, mínimos ni penalidades de deudas. Una meta vencida requiere revisar su fecha o prioridad; no implica restricción contractual ni acuerdo existente.',
            ],
        })
