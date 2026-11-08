"""Read-only, user-scoped facts and deterministic calculations for the advisors.

Totals are aggregated before limiting detail rows. Monetary results are decimal
strings so model output cannot introduce binary floating-point errors.
"""
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_CEILING
from zoneinfo import ZoneInfo

from .db import db, one, many, money
from .domain import finance_summary

LIMIT = 20


def tool(name, description, properties, required):
    return {'type': 'function', 'function': {'name': name, 'description': description,
            'parameters': {'type': 'object', 'properties': properties, 'required': required,
                           'additionalProperties': False}}}


DATES = {k: {'type': 'string', 'description': 'Fecha ISO YYYY-MM-DD, Guatemala.'} for k in ('start', 'end')}
AS_OF = {'as_of': {'type': 'string', 'description': 'Fecha de corte ISO YYYY-MM-DD, Guatemala.'}}
TOOLS = {
    'financial_overview': tool('financial_overview', 'Ingresos, pagos, ahorro neto y disponible registrados en un período (máximo 366 días), comparados con el período anterior de igual duración.', DATES, ['start', 'end']),
    'spending_breakdown': tool('spending_breakdown', 'Ranking completo de pagos reales por categoría y su porcentaje del gasto e ingreso registrado. No usa importes previstos.', DATES, ['start', 'end']),
    'compare_spending': tool('compare_spending', 'Compara dos categorías propias por sus pagos ejecutados y calcula la diferencia exacta. Usa los nombres de categorías consultados; no hace falta pedir IDs.', {**DATES, 'category_a': {'type':'string'}, 'category_b': {'type':'string'}}, ['start','end','category_a','category_b']),
    'recurring_snapshot': tool('recurring_snapshot', 'Plantillas recurrentes propias activas e inactivas: importes mensuales previstos, nunca pagos ejecutados. No crea movimientos.', {}, []),
    'obligations_snapshot': tool('obligations_snapshot', 'Compromisos de gasto pendientes a una fecha: previstos menos pagos registrados hasta ese corte, vencidos y próximos. No todos son deudas bancarias.', AS_OF, ['as_of']),
    'debt_snapshot': tool('debt_snapshot', 'Saldos pendientes SOLO de la categoría Deudas al corte, ordenados de menor a mayor para estudiar bola de nieve. Tasas, mínimos y contratos no disponibles.', AS_OF, ['as_of']),
    'small_expenses': tool('small_expenses', 'Pagos individuales pequeños (hasta el umbral indicado) por categoría, excluyendo Deudas. Son candidatos a revisar; su monto no demuestra que sean gastos hormiga ni ahorro recuperable.', {**DATES, 'threshold': {'type': 'string', 'description': 'Umbral positivo GTQ decimal, por ejemplo 50.00.'}}, ['start', 'end', 'threshold']),
    'budget_scenario': tool('budget_scenario', 'Escenario mensual sin modificar registros: parte de lo ejecutado en el período indicado y aplica reducciones e ingresos/aportes adicionales. No predice ingresos futuros.', {**DATES, **{k: {'type': 'string', 'description': 'Importe mensual adicional no negativo GTQ decimal.'} for k in ('monthly_reduction', 'monthly_extra_income', 'monthly_extra_debt', 'monthly_extra_savings')}}, ['start', 'end', 'monthly_reduction', 'monthly_extra_income', 'monthly_extra_debt', 'monthly_extra_savings']),
    'savings_plan': tool('savings_plan', 'Simula una meta propia activa elegida por la persona: consulta saldo a hoy Guatemala y calcula proyección y brecha sin intereses. No modifica datos.', {'goal_id': {'type': 'integer'}, 'months': {'type': 'integer', 'minimum': 1, 'maximum': 120}, 'monthly': {'type': 'string', 'description': 'Importe GTQ como texto decimal entre comillas, ejemplo "100.00". No enviar número JSON.'}}, ['goal_id', 'months', 'monthly']),
    'goal_snapshot': tool('goal_snapshot', 'Metas propias activas e inactivas, saldos de aportes menos retiros hasta hoy Guatemala, objetivo y vencimiento.', {}, []),
}


def today():
    return datetime.now(ZoneInfo('America/Guatemala')).date()


def _date(value):
    if not isinstance(value, str):
        raise ValueError('Fecha ISO requerida')
    result = date.fromisoformat(value)
    if result.isoformat() != value:
        raise ValueError('Usa YYYY-MM-DD')
    return result


def _period(args):
    start, end = _date(args['start']), _date(args['end'])
    if start > end or (end-start).days >= 366:
        raise ValueError('Período inválido: máximo 366 días')
    return start, end


def _amount(value, positive=False):
    if isinstance(value, bool) or not isinstance(value, (str, int, Decimal)):
        raise ValueError('Importe decimal inválido')
    try:
        result = Decimal(str(value))
        if not result.is_finite() or result < 0 or result > Decimal('9999999999999.99'):
            raise ValueError('Importe fuera de rango')
        if positive and result == 0:
            raise ValueError('Importe positivo requerido')
        if result != money(result):
            raise ValueError('Máximo dos decimales')
        return money(result)
    except InvalidOperation as exc:
        raise ValueError('Importe decimal inválido') from exc


def _clean(value):
    if isinstance(value, Decimal):
        return str(money(value))
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, list):
        return [_clean(item) for item in value]
    if isinstance(value, dict):
        return {k: _clean(v) for k, v in value.items()}
    return value


def _ratio(numerator, denominator):
    return money(numerator * 100 / denominator) if denominator else None


def _base(source, start=None, end=None, as_of=None):
    result = {'source_id': source, 'currency': 'GTQ', 'timezone': 'America/Guatemala'}
    if start is not None:
        result['period'] = {'start': start.isoformat(), 'end': end.isoformat(), 'includes_future_dates': end > today()}
    if as_of is not None:
        result['as_of'] = as_of.isoformat()
    return result


def _details(rows, total_count, limit=LIMIT):
    return {'items': rows[:limit], 'total_count': total_count, 'detail_limit': limit,
            'has_more': total_count > limit, 'totals_include_all_records': True}


def financial_overview(conn, user_id, args):
    start, end = _period(args)
    previous_end = start - timedelta(days=1)
    previous_start = previous_end - (end-start)
    current = finance_summary(conn, user_id, start, end)
    previous = finance_summary(conn, user_id, previous_start, previous_end)
    changes = {k: current[k]-previous[k] for k in ('income', 'expense', 'net_savings', 'available')}
    return {**_base('SFIN', start, end), 'current': current, 'previous': previous, 'changes_gtq': changes,
            'expense_to_income_percent': _ratio(current['expense'], current['income']),
            'net_savings_to_income_percent': _ratio(current['net_savings'], current['income']),
            'basis': 'Pagos y movimientos de ahorro por fecha registrada; disponible es flujo registrado, no saldo bancario. Ahorro neto puede ser negativo por retiros.'}


def spending_breakdown(conn, user_id, args):
    start, end = _period(args)
    summary = finance_summary(conn, user_id, start, end)
    rows = many(conn, '''SELECT c.id AS category_id,left(c.name,90) AS category,
               sum(p.amount) AS amount,count(*) AS payment_count FROM payments p
               JOIN obligations o ON o.id=p.obligation_id JOIN categories c ON c.id=o.category_id
               WHERE o.user_id=%s AND NOT o.voided AND c.kind='expense' AND p.paid_on BETWEEN %s AND %s
               GROUP BY c.id ORDER BY amount DESC,c.id''', (user_id, start, end))
    for row in rows:
        row['expense_percent'] = _ratio(row['amount'], summary['expense'])
        row['income_percent'] = _ratio(row['amount'], summary['income'])
    debt_payments = sum((r['amount'] for r in rows if r['category'].lower() == 'deudas'), Decimal(0))
    return {**_base('SGASTOS', start, end), 'total_expense': summary['expense'], 'observed_income': summary['income'],
            'debt_payments': debt_payments, 'debt_payments_to_observed_income_percent': _ratio(debt_payments, summary['income']),
            'payment_count': sum(r['payment_count'] for r in rows), **_details(rows, len(rows)),
            'basis': 'Solo pagos ejecutados registrados, no montos previstos. Porcentajes nulos si el denominador es cero. Pagos Deudas/ingreso registrado es un proxy observado, no DTI ni cuota contractual de endeudamiento.'}


def compare_spending(conn, user_id, args):
    import unicodedata
    def normalized(value):
        if not isinstance(value,str) or not 1<=len(value.strip())<=80:
            raise ValueError('Nombre de categoría requerido')
        return ''.join(c for c in unicodedata.normalize('NFD',value.casefold().strip()) if not unicodedata.combining(c))
    start,end=_period(args)
    categories=many(conn,"SELECT id,name FROM categories WHERE user_id=%s AND kind='expense' ORDER BY id",(user_id,))
    selected=[]
    for key in ('category_a','category_b'):
        matches=[row for row in categories if normalized(row['name'])==normalized(args[key])]
        if len(matches)!=1:
            raise ValueError('Categoría propia no encontrada o ambigua; consulta los nombres antes de comparar')
        category=matches[0]
        amount=one(conn,'''SELECT coalesce(sum(p.amount),0) AS amount FROM payments p JOIN obligations o ON o.id=p.obligation_id
                          WHERE o.user_id=%s AND o.category_id=%s AND NOT o.voided AND p.paid_on BETWEEN %s AND %s''',
                   (user_id,category['id'],start,end))['amount']
        selected.append({'category':category['name'],'amount':amount})
    difference=selected[0]['amount']-selected[1]['amount']
    return {**_base('SCOMPARA',start,end),'items':selected,'difference_gtq':abs(difference),
            'higher_category':selected[0 if difference>0 else 1]['category'] if difference else None,
            'equal':difference==0,'basis':'Pagos ejecutados del período; diferencia calculada en el servidor, no importes previstos.'}


def recurring_snapshot(conn, user_id, args):
    totals = many(conn, '''SELECT r.active,c.kind,count(*) AS count,coalesce(sum(r.amount),0) AS monthly_planned
               FROM recurring r JOIN categories c ON c.id=r.category_id WHERE r.user_id=%s
               GROUP BY r.active,c.kind ORDER BY r.active DESC,c.kind''', (user_id,))
    count = sum(r['count'] for r in totals)
    rows = many(conn, '''SELECT r.id,left(r.title,90) AS title,left(c.name,90) AS category,c.kind,r.active,r.amount,r.start_month
               FROM recurring r JOIN categories c ON c.id=r.category_id WHERE r.user_id=%s
               ORDER BY r.active DESC,c.kind,r.id LIMIT %s''', (user_id, LIMIT))
    return {**_base('SREC', as_of=today()), 'totals': totals, **_details(rows, count),
            'basis': 'Plantillas mensuales previstas; incluye activas con inicio futuro identificado. No equivale a pagos ni crea obligaciones.'}


def _pending(conn, user_id, as_of, debt=False, limit=10):
    # Preaggregate payments so every obligation occurs exactly once even with partial payments.
    cte = '''WITH paid AS (SELECT p.obligation_id,sum(p.amount) AS executed FROM payments p
                 JOIN obligations owner ON owner.id=p.obligation_id
                 WHERE owner.user_id=%s AND p.paid_on<=%s GROUP BY p.obligation_id),
             pending AS (SELECT o.id,left(o.title,90) AS title,left(c.name,90) AS category,o.planned,o.due_date,
                 coalesce(p.executed,0) AS paid_to_cutoff,greatest(o.planned-coalesce(p.executed,0),0) AS remaining
                 FROM obligations o JOIN categories c ON c.id=o.category_id LEFT JOIN paid p ON p.obligation_id=o.id
                 WHERE o.user_id=%s AND NOT o.voided AND c.kind='expense' '''
    if debt:
        cte += " AND lower(c.name)='deudas' "
    cte += ' AND o.planned>coalesce(p.executed,0)) '
    params = (user_id, as_of, user_id)
    totals = one(conn, cte+'''SELECT count(*) AS count,coalesce(sum(remaining),0) AS remaining,
                 coalesce(sum(remaining) FILTER(WHERE due_date<%s),0) AS overdue,
                 count(*) FILTER(WHERE due_date<%s) AS overdue_count,
                 coalesce(sum(remaining) FILTER(WHERE due_date=%s),0) AS due_today,
                 coalesce(sum(remaining) FILTER(WHERE due_date>%s),0) AS future_due,
                 coalesce(sum(remaining) FILTER(WHERE due_date<date_trunc('month',%s::date)),0) AS carry_from_prior_months FROM pending''',
                 params+(as_of, as_of, as_of, as_of, as_of))
    ordering = 'remaining,id' if debt else 'due_date,id'
    rows = many(conn, cte+'SELECT * FROM pending ORDER BY '+ordering+' LIMIT %s', params+(limit,))
    return totals, rows


def obligations_snapshot(conn, user_id, args):
    as_of = _date(args['as_of'])
    totals, rows = _pending(conn, user_id, as_of)
    return {**_base('SPEND', as_of=as_of), 'totals': totals, **_details(rows, totals['count'], 10),
            'basis': 'Compromisos expense no anulados menos pagos con fecha hasta el corte. No todos son deuda financiera. Reconstruye pagos; no existe historial de altas/modificaciones de compromisos.'}


def debt_snapshot(conn, user_id, args):
    as_of = _date(args['as_of'])
    totals, rows = _pending(conn, user_id, as_of, debt=True, limit=LIMIT)
    return {**_base('SDEUDA', as_of=as_of), 'totals': totals, **_details(rows, totals['count']),
            'classification': "Solo categoría expense cuyo nombre exacto, sin distinguir mayúsculas, sea Deudas; el saldo es planned menos pagos, no saldo certificado por un banco.",
            'ordering': 'Saldo menor a mayor: candidato a bola de nieve, no optimización de intereses.',
            'unknown': ['APR/tasa', 'cuota mínima contractual', 'plazo contractual', 'penalidades', 'cuotas de deuda a ingreso'],
            'basis': 'Los pagos futuros no reducen el saldo al corte; no se infieren intereses ni planes bancarios.'}


def small_expenses(conn, user_id, args):
    start, end = _period(args)
    threshold = _amount(args['threshold'], positive=True)
    rows = many(conn, '''SELECT c.id AS category_id,left(c.name,90) AS category,count(*) AS payment_count,sum(p.amount) AS amount
              FROM payments p JOIN obligations o ON o.id=p.obligation_id JOIN categories c ON c.id=o.category_id
              WHERE o.user_id=%s AND NOT o.voided AND c.kind='expense' AND lower(c.name)<>'deudas'
              AND p.paid_on BETWEEN %s AND %s AND p.amount<=%s GROUP BY c.id ORDER BY amount DESC,c.id''', (user_id, start, end, threshold))
    denominator = one(conn, '''SELECT coalesce(sum(p.amount),0) AS amount FROM payments p
              JOIN obligations o ON o.id=p.obligation_id JOIN categories c ON c.id=o.category_id
              WHERE o.user_id=%s AND NOT o.voided AND c.kind='expense' AND lower(c.name)<>'deudas' AND p.paid_on BETWEEN %s AND %s''',
              (user_id, start, end))['amount']
    total = sum((r['amount'] for r in rows), Decimal(0))
    return {**_base('SMICRO', start, end), 'threshold': threshold, 'candidate_total': total,
            'candidate_payment_count': sum(r['payment_count'] for r in rows), 'expense_excluding_debt': denominator,
            'candidate_share_percent': _ratio(total, denominator), **_details(rows, len(rows)),
            'basis': 'Candidatos por importe individual; excluye ingresos y categoría Deudas. No demuestra gasto hormiga: confirmar frecuencia, necesidad y alternativas. El total no es ahorro recuperable.'}


def budget_scenario(conn, user_id, args):
    start, end = _period(args)
    keys = ('monthly_reduction', 'monthly_extra_income', 'monthly_extra_debt', 'monthly_extra_savings')
    reduction, extra_income, extra_debt, extra_savings = (_amount(args[k]) for k in keys)
    base = finance_summary(conn, user_id, start, end)
    if reduction > base['expense']:
        raise ValueError('La reducción supera el gasto observado')
    projected = base['available']+reduction+extra_income-extra_debt-extra_savings
    return {**_base('SESC', start, end), 'base': base,
            'assumptions': dict(zip(keys, (reduction, extra_income, extra_debt, extra_savings))),
            'scenario_available': projected, 'feasible_against_observed_flow': projected >= 0,
            'basis': 'Escenario sin intereses ni cambios en la base. Compara importes mensuales adicionales contra el flujo observado del período elegido; si ese período no es un mes representativo no lo mensualiza ni predice ingresos. No asume que toda reducción sea viable.'}


def goal_snapshot(conn, user_id, args):
    stamp = today()
    rows = many(conn, '''SELECT g.id,left(g.name,90) AS name,g.target,g.deadline,g.active,
                 coalesce(sum(s.amount) FILTER(WHERE s.moved_on<=%s),0) AS balance FROM goals g
                 LEFT JOIN savings s ON s.goal_id=g.id WHERE g.user_id=%s
                 GROUP BY g.id ORDER BY g.active DESC,g.deadline,g.id''', (stamp, user_id))
    totals = {'active_count': sum(r['active'] for r in rows), 'inactive_count': sum(not r['active'] for r in rows),
              'active_target': sum((r['target'] for r in rows if r['active']), Decimal(0)),
              'active_balance': sum((r['balance'] for r in rows if r['active']), Decimal(0)),
              'active_required_monthly': Decimal(0), 'expired_active_count': 0,
              'in_progress_count': 0, 'completed_active_count': 0}
    for row in rows:
        row['remaining'] = max(Decimal(0), row['target']-row['balance'])
        row['state'] = ('inactiva' if not row['active'] else 'cumplida' if row['remaining'] == 0
                        else 'vencida' if row['deadline'] < stamp else 'en progreso')
        if row['state'] == 'en progreso': totals['in_progress_count'] += 1
        if row['state'] == 'cumplida': totals['completed_active_count'] += 1
        row['days_to_deadline'] = (row['deadline']-stamp).days
        row['remaining_contributions'] = ((row['deadline'].year-stamp.year)*12+row['deadline'].month-stamp.month+1
                                          if row['deadline'] >= stamp else 0)
        row['required_monthly_to_deadline'] = (
            (row['remaining']/Decimal(row['remaining_contributions'])).quantize(Decimal('.01'), rounding=ROUND_CEILING)
            if row['remaining_contributions'] else Decimal(0) if row['remaining'] == 0 else None)
        if row['active']:
            if row['remaining_contributions']:
                totals['active_required_monthly'] += row['required_monthly_to_deadline']
            elif row['remaining'] > 0:
                totals['expired_active_count'] += 1
    return {**_base('SMETAS', as_of=stamp), 'totals': totals, **_details(rows, len(rows)),
            'basis': 'Aportes menos retiros con fecha hasta hoy Guatemala; excluye movimientos futuros. Aporte necesario: uno en cada mes incluido el actual antes del vencimiento, sin intereses y sin capacidad de pago garantizada. Metas vencidas con faltante no tienen cuota calculable. Cada meta se financia por separado; no sumar su saldo a disponible otra vez.'}


def savings_plan(conn, user_id, args):
    goal_id, months = args['goal_id'], args['months']
    if isinstance(goal_id, bool) or not isinstance(goal_id, int) or goal_id < 1:
        raise ValueError('Meta inválida')
    if isinstance(months, bool) or not isinstance(months, int) or not 1 <= months <= 120:
        raise ValueError('Meses fuera de rango')
    monthly = _amount(args['monthly'])
    stamp = today()
    goal = one(conn, '''SELECT g.id,left(g.name,90) AS name,g.target,g.deadline,
               coalesce(sum(s.amount) FILTER(WHERE s.moved_on<=%s),0) AS balance FROM goals g
               LEFT JOIN savings s ON s.goal_id=g.id WHERE g.id=%s AND g.user_id=%s AND g.active GROUP BY g.id''',
               (stamp, goal_id, user_id))
    if not goal:
        raise ValueError('Meta activa propia no encontrada')
    if goal['balance'] < 0:
        raise ValueError('Saldo histórico inconsistente')
    remaining = max(Decimal(0), goal['target']-goal['balance'])
    needed = (remaining/Decimal(months)).quantize(Decimal('.01'), rounding=ROUND_CEILING)
    projected = goal['balance']+monthly*months
    return {**_base('SG'+str(goal_id), as_of=stamp), 'goal': goal, 'remaining': remaining,
            'months': months, 'required_monthly': needed, 'proposed_monthly': monthly,
            'projected_balance': projected, 'gap_at_end': max(Decimal(0), goal['target']-projected),
            'extra_monthly_needed': max(Decimal(0), needed-monthly), 'reaches_goal': projected >= goal['target'],
            'basis': 'Sin intereses, inflación futura ni rendimientos. Número fijo de aportes futuros; no garantiza que entren antes del vencimiento ni que exista dinero disponible. Contrastar con financial_overview/budget_scenario.'}


_FUNCTIONS = {name: globals()[name] for name in TOOLS}


def execute(name, args, user_id):
    if name not in TOOLS or not isinstance(args, dict):
        raise ValueError('Herramienta o argumentos inválidos')
    expected = set(TOOLS[name]['function']['parameters']['required'])
    if set(args) != expected:
        raise ValueError('Argumentos inválidos')
    if isinstance(user_id, bool) or not isinstance(user_id, int) or user_id < 1:
        raise ValueError('Usuario inválido')
    with db() as conn:
        # Enforced in PostgreSQL too: an accidental mutation in a tool fails.
        conn.execute('SET TRANSACTION READ ONLY')
        return _clean(_FUNCTIONS[name](conn, user_id, args))
