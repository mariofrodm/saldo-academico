"""Live acceptance checks for localhost; never invokes Groq or changes finances.

Run inside the existing local container (credentials remain in its environment):
docker compose -p saldo_academico exec -T app python - < scripts/verificar_aceptacion.py
Only authentication sessions are created, then closed in finally blocks.
"""
import json
import os
from datetime import datetime, timezone
from contextlib import contextmanager

import httpx

BASE = os.getenv('ACCEPTANCE_BASE_URL', 'http://127.0.0.1:8000').rstrip('/')
result = {'base_url': BASE, 'checked_at_utc': datetime.now(timezone.utc).isoformat(),
          'groq_calls': 0, 'checks': [], 'facts': {}}


def check(name, condition):
    result['checks'].append({'name': name, 'passed': bool(condition)})
    if not condition:
        raise AssertionError(name)


@contextmanager
def signed_in(email, password_key):
    with httpx.Client(base_url=BASE, timeout=20, follow_redirects=False) as client:
        login = client.post('/api/v1/auth/login', json={'email': email, 'password': os.environ[password_key]})
        check('Login ' + email, login.status_code == 200)
        headers = {'Authorization': 'Bearer ' + login.json()['access_token']}
        try:
            yield client, headers
        finally:
            client.post('/api/v1/auth/logout', headers=headers)


def tool(client, headers, name, arguments):
    response = client.post('/api/v1/advisor/' + name, headers=headers, json={'arguments': arguments})
    check('Consulta ' + name, response.status_code == 200)
    return response.json()


def run():
    if os.getenv('APP_ENV', 'local') != 'local' and BASE != 'https://saldo-academico.onrender.com':
        raise ValueError('En producción se exige la URL HTTPS publicada de Saldo.')
    if BASE not in ('http://127.0.0.1:8000', 'https://saldo-academico.onrender.com'):
        raise ValueError('Destino de aceptación no permitido.')
    with httpx.Client(base_url=BASE, timeout=20, follow_redirects=False) as anonymous:
        health = anonymous.get('/api/health')
        check('Salud y PostgreSQL', health.status_code == 200 and health.json().get('database') == 'ok')
        check('Interfaz disponible', anonymous.get('/').status_code == 200)
        schema = anonymous.get('/openapi.json')
        check('OpenAPI de la ampliación', schema.status_code == 200 and '/api/v1/advisor/tools' in schema.json().get('paths', {}))
        check('Identidad protegida', anonymous.get('/api/v1/me').status_code == 401)
        check('Reporte protegido', anonymous.get('/api/v1/reports/summary').status_code == 401)
        check('Herramientas protegidas', anonymous.get('/api/v1/advisor/tools').status_code == 401)

    with signed_in('demo@example.test', 'DEMO_PASSWORD') as (client, headers):
        me = client.get('/api/v1/me', headers=headers).json()
        check('Rol de Ana', me['role'] == 'user')
        check('Sin reservas en curso', me['tokens_reserved'] == 0)
        check('Administración restringida', client.get('/api/v1/admin/users', headers=headers).status_code == 403)
        check('Historial ajeno restringido', client.get('/api/v1/history', headers=headers, params={'user_id': 1}).status_code == 403)
        services = client.get('/api/v1/services', headers=headers).json()
        check('Tres servicios activos', {s['id'] for s in services['items'] if s['enabled']} == {'rag', 'budget', 'goals'})
        result['facts']['provider_configured'] = services['provider_ready']
        result['facts']['quota'] = {k: me[k] for k in ('token_limit', 'tokens_used', 'tokens_reserved')}

        manifest = client.get('/api/v1/advisor/tools', headers=headers).json()
        check('Manifiesto de lectura', manifest['read_only'] and len(manifest['tools']) >= 10)
        october = {'start': '2026-10-01', 'end': '2026-10-31'}
        flow = tool(client, headers, 'financial_overview', october)
        check('Conciliación octubre', [flow['current'][k] for k in ('income', 'expense', 'net_savings', 'available')]
              == ['7250.00', '7177.00', '0.00', '73.00'])
        ranking = tool(client, headers, 'spending_breakdown', october)
        check('Ranking octubre', ranking['items'][0]['category'] == 'Vivienda' and ranking['items'][0]['amount'] == '1500.00')
        check('Ratio observable, no DTI', ranking['debt_payments_to_observed_income_percent'] == '10.34')
        debt = tool(client, headers, 'debt_snapshot', {'as_of': '2026-11-07'})
        check('Saldos de deuda', [r['remaining'] for r in debt['items']] == ['550.00', '2050.00', '5300.00'])
        micro = tool(client, headers, 'small_expenses', {**october, 'threshold': '50'})
        check('Pagos pequeños octubre', micro['candidate_payment_count'] == 60 and micro['candidate_total'] == '1234.00')
        goals = tool(client, headers, 'goal_snapshot', {})
        own_goal = next(g for g in goals['items'] if g['name'] == 'Fondo de emergencia')
        check('Fondo de emergencia', own_goal['balance'] == '550.00' and own_goal['target'] == '5000.00')
        plan = tool(client, headers, 'savings_plan', {'goal_id': own_goal['id'], 'months': 6, 'monthly': '750'})
        check('Simulación de meta', plan['projected_balance'] == '5050.00' and plan['reaches_goal'])
        scenario = tool(client, headers, 'budget_scenario', {**october, 'monthly_reduction': '412.50',
                        'monthly_extra_income': '0', 'monthly_extra_debt': '200', 'monthly_extra_savings': '200'})
        check('Escenario sin doble asignación', scenario['scenario_available'] == '85.50')
        tool(client, headers, 'recurring_snapshot', {})
        tool(client, headers, 'obligations_snapshot', {'as_of': '2026-11-07'})
        tool(client, headers, 'financial_diagnosis', {**october, 'as_of': '2026-11-07'})
        rejected = client.post('/api/v1/advisor/goal_snapshot', headers=headers, json={'arguments': {'user_id': 1}})
        check('Argumentos no amplían alcance', rejected.status_code == 422)
        check('SQL libre no expuesto', client.post('/api/v1/advisor/execute_sql', headers=headers,
              json={'arguments': {}}).status_code == 404)

        # One frozen cutoff across the summary, every page, admin and BI.
        report = client.get('/api/v1/reports/summary', headers=headers).json()
        cutoff = report['as_of']
        rows, cursor = [], None
        while True:
            params = {'as_of': cutoff, 'page_size': 2}
            if cursor:
                params['after'] = cursor
            response = client.get('/api/v1/reports/usage', headers=headers, params=params)
            check('Página de reporte', response.status_code == 200)
            page = response.json()
            rows.extend(page['items'])
            cursor = page['next_cursor']
            if not cursor:
                break
        check('Paginación sin duplicados', len(rows) == len({r['id'] for r in rows}))
        expected = {}
        for row in rows:
            item = expected.setdefault(row['service'], {'service': row['service'], 'requests': 0,
                'provider_calls': 0, 'input_tokens': 0, 'output_tokens': 0, 'total_tokens': 0})
            item['requests'] += 1
            for key in ('provider_calls', 'input_tokens', 'output_tokens', 'total_tokens'):
                item[key] += row[key]
        check('Detalle coincide con resumen', sorted(expected.values(), key=lambda r: r['service']) == report['items'])
        check('Entrada más salida', all(r['input_tokens'] + r['output_tokens'] == r['total_tokens'] for r in report['items']))
        check('Consumo coincide con cuenta', sum(r['total_tokens'] for r in report['items']) == me['tokens_used'])
        result['facts']['report'] = report
        result['facts']['report_rows'] = len(rows)
        with signed_in('admin@example.test', 'ADMIN_PASSWORD') as (administrator, admin_headers):
            admin_report = administrator.get('/api/v1/reports/summary', headers=admin_headers,
                          params={'as_of': cutoff, 'user_id': me['id']})
            check('Administrador coincide al filtrar Ana', admin_report.status_code == 200 and admin_report.json()['items'] == report['items'])
        with httpx.Client(base_url=BASE, timeout=20) as bi:
            basic = ('bi@example.test', os.environ['BI_PASSWORD'])
            bi_report = bi.get('/api/v1/reports/summary', auth=basic, params={'as_of': cutoff, 'user_id': me['id']})
            check('BI coincide al filtrar Ana', bi_report.status_code == 200 and bi_report.json()['items'] == report['items'])
            check('BI no accede al dominio', bi.get('/api/v1/categories', auth=basic).status_code == 401)
        me_after = client.get('/api/v1/me', headers=headers).json()
        check('Ensayo sin consumo de IA', me_after['tokens_used'] == me['tokens_used'] and me_after['tokens_reserved'] == 0)


if __name__ == '__main__':
    try:
        run()
        result['passed'] = True
    except Exception as exc:
        result['passed'] = False
        # Never serialize request bodies, environment values, tokens or headers.
        result['error_type'] = type(exc).__name__
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result['passed'] else 1)
