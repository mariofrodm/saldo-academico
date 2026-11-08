"""A compact, deterministic overview avoids five separate model round trips."""
from copy import deepcopy
from datetime import timedelta
from . import advisor
from .domain import finance_summary

TOOL = advisor.tool('financial_diagnosis',
    'Diagnóstico global: flujo, ranking de gastos, recurrentes, pendientes, deudas identificadas y metas. '
    'Totales completos y hasta tres detalles por sección. Úsalo para ordenar finanzas o un plan integral.',
    {**advisor.DATES, **advisor.AS_OF}, ['start', 'end', 'as_of'])


def compact(value, detail_limit=3):
    if not isinstance(value, dict):
        return value
    result = dict(value)
    if isinstance(result.get('items'), list):
        result['items'] = result['items'][:detail_limit]
        result['detail_limit'] = min(result.get('detail_limit', detail_limit), detail_limit)
        result['has_more'] = result.get('total_count', len(value['items'])) > len(result['items'])
    return result


def model_context(result):
    """Select complete verified facts for the model, never recompute amounts.

    The original tool result/API/history stays complete. Section aggregates
    always describe all records; detail rows below are explicitly samples. A
    missing field is omitted, not replaced with zero or an inferred fact.
    """
    if not isinstance(result, dict):
        return result
    context = {key: deepcopy(result[key]) for key in (
        'source_id', 'currency', 'period', 'as_of', 'limits', 'last_closed_month'
    ) if key in result}
    flow = result.get('flow')
    if isinstance(flow, dict):
        context['flow'] = {key: deepcopy(flow[key]) for key in (
            'current', 'expense_to_income_percent', 'net_savings_to_income_percent'
        ) if key in flow}

    # Omit repeated identifiers/descriptions, not global financial aggregates.
    omitted = {'source_id', 'currency', 'timezone', 'basis', 'classification',
               'ordering', 'unknown', 'items', 'detail_limit', 'has_more'}

    def section(name, fields, limit):
        original = result.get(name)
        if not isinstance(original, dict):
            return
        value = {key: deepcopy(item) for key, item in original.items() if key not in omitted}
        rows = original.get('items')
        rows = rows if isinstance(rows, list) else []
        sample = [{key: deepcopy(row[key]) for key in fields if key in row}
                  for row in rows[:limit] if isinstance(row, dict)]
        count = original.get('total_count')
        more = (bool(original.get('has_more')) or len(rows) > len(sample)
                or isinstance(count, int) and not isinstance(count, bool) and count > len(sample))
        value['has_more'] = more
        if limit:
            value['items'] = sample
            value['detail_limit'] = limit
        else:
            value['details_omitted'] = more
        context[name] = value

    section('spending', ('category', 'amount', 'expense_percent', 'income_percent'), 2)
    section('recurring', (), 0)
    section('pending', (), 0)
    section('debt', ('title', 'remaining'), 3)
    section('goals', ('id', 'name', 'state', 'balance', 'target', 'deadline'), 2)
    if 'spending' in context:
        context['spending']['meaning']='Pagos reales del período, no importes de plantillas recurrentes.'
    if 'recurring' in context:
        context['recurring']['meaning']='Plantillas previstas, no pagos realizados.'
    return context


def execute(args, user_id):
    if not isinstance(args, dict) or set(args) != {'start', 'end', 'as_of'}:
        raise ValueError('Argumentos inválidos')
    advisor._period(args)
    advisor._date(args['as_of'])
    if isinstance(user_id, bool) or not isinstance(user_id, int) or user_id < 1:
        raise ValueError('Usuario inválido')
    with advisor.db() as conn:
        conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
        period = {k: args[k] for k in ('start', 'end')}
        sections = {
            'flow': advisor.financial_overview(conn, user_id, period),
            'spending': advisor.spending_breakdown(conn, user_id, period),
            'recurring': advisor.recurring_snapshot(conn, user_id, {}),
            'pending': advisor.obligations_snapshot(conn, user_id, {'as_of': args['as_of']}),
            'debt': advisor.debt_snapshot(conn, user_id, {'as_of': args['as_of']}),
            'goals': advisor.goal_snapshot(conn, user_id, {}),
        }
        # The same descriptions live in the tool schemas/catalog. Keep the result small.
        for name, section in sections.items():
            sections[name] = compact({k: v for k, v in section.items()
                                      if k not in ('basis', 'classification', 'ordering', 'timezone', 'unknown')})
        if args['as_of'] == advisor.today().isoformat():
            closed_end = advisor.today().replace(day=1)-timedelta(days=1)
            sections['last_closed_month'] = finance_summary(conn, user_id, closed_end.replace(day=1), closed_end)
        return advisor._clean({'source_id': 'SDIAG', 'currency': 'GTQ',
            'period': period, 'as_of': args['as_of'], **sections,
            'limits': 'Flujo según fechas del período; deudas al corte; metas/recurrentes a hoy. '
                      'No conocemos tasas, cuotas mínimas, patrimonio ni saldo bancario. '
                      'Un mes parcial no es dinero libre recurrente; último mes cerrado es solo referencia histórica. '
                      'Detalles limitados: consulta herramienta específica si has_more=true.'})
