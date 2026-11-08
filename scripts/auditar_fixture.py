"""Four real AI questions on a disposable PostgreSQL fixture, opt-in only.

Without --run: prints the plan, with no environment access, network or files.
With --run: creates/migrates/seeds a NEW random local database and uses the same
FastAPI app through synchronous TestClient, without opening a listening port.
The fixture has synthetic demo data and its NEW user's normal 20,000-token
default, never Ana's account/quota. No existing user/quota is changed/reset.

The provider key and passwords are inherited privately. This still consumes the
SAME real Groq Free organization quota: a fixture does not create provider quota.
Current day/minute/call counters are copied conservatively from the ORIGINAL
database using READ ONLY transactions, and refreshed before each AI POST.
The original DB is never modified. The operator also accounts for earlier
fixture/provider consumption not present in that DB; do not repeat fixtures to
bypass application/provider limits. Backend limits 100k/day, 7k/min and 24
rounds/min are unchanged. Hard cap: FOUR AI POST attempts INCLUDING one retry.
Before a POST, a nearly full minute is allowed to expire once (up to60s),
rather than spending one of those attempts on a predictable local rate block.
--prior-fixture-tokens carries earlier isolated consumption into this UTC day's
shared counter; it adds usage, never credits, limits or user quota. Supply the
operator-verified cumulative total not already charged to the original DB.

Run inside the rebuilt local app container, with current backend code:
docker compose -p saldo_academico exec -T app python - --run < scripts/auditar_fixture.py
Results/ledger are private under /tmp/evidencias-locales/auditoria-fixture;
copy them to the host before rebuilding the container. All money is synthetic.
The script restores environment variables and drops ONLY its new DB in finally.
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit


MAX_POSTS = 4
HEADROOM = 6500
MODELS = ('openai/gpt-oss-20b', 'openai/gpt-oss-120b', 'qwen/qwen3.8-27b')
METAS = [
    ('metas', '¿Qué metas de ahorro tengo y cómo voy?'),
    ('metas', '¿Por cuál comienzo?'),
    ('metas', '¿Y si aporto 100 al mes?'),
]
FOURTH = {
    'quincena': 'Cobro por quincena y siento que no me alcanza. ¿Qué revisamos primero?',
    'apr': '¿Cuál es la tasa de interés de mi tarjeta y el pago mínimo?',
    'savings': 'Al fondo de emergencia',
    'budget': '¿Qué tan sano ves mi presupuesto de octubre?',
}


def question_list(fourth):
    return [*METAS, ('metas' if fourth=='savings' else fourth, FOURTH[fourth])]


def now():
    return datetime.now(timezone.utc).isoformat()


def redact(value, private):
    if isinstance(value, dict):
        return {key: redact(item, private) for key, item in value.items()
                if key.lower() not in ('password', 'access_token', 'csrf', 'authorization', 'cookie', 'set-cookie')}
    if isinstance(value, list):
        return [redact(item, private) for item in value]
    if isinstance(value, str):
        for secret in private:
            if secret:
                value = value.replace(secret, '[OCULTO]')
        value = re.sub(r'gsk_[A-Za-z0-9_-]+', '[CLAVE_OCULTA]', value)
        return re.sub(r'postgres(?:ql)?://[^\s"<>]+', '[CONEXION_OCULTA]', value)
    return value


def write_result(path, result, private):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')

    def json_value(value):
        if isinstance(value, Decimal):
            return str(value)  # Preserve exact decimal amounts, including scale.
        if isinstance(value, (date, datetime)):
            return value.isoformat()
        if isinstance(value, uuid.UUID):
            return str(value)
        raise TypeError('Unsupported audit value')

    try:
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(redact(result, private), stream, indent=2, ensure_ascii=False, default=json_value)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, 0o600)
        temporary.replace(path)  # Replace only a complete JSON; preserve previous evidence on failure.
    finally:
        temporary.unlink(missing_ok=True)


def serialization_self_test():
    """Pure regression for the pre-POST checkpoint; no API, DB or environment."""
    with tempfile.TemporaryDirectory(prefix='saldo-audit-json-') as directory:
        path = Path(directory) / 'checkpoint.json'
        payload = {'created': True, 'ai_post_attempts': 1,
                   'synthetic_data': {'financial_periods': [{'args': {'amount': Decimal('100.00'),
                       'on': date(2026, 11, 8)}, 'balance': Decimal('550.00')}],
                       'at': datetime(2026, 11, 8, 12, 30, tzinfo=timezone.utc)},
                   'turns': [{'prompt': '¿Qué metas tengo?', 'started_at': now()}],
                   'password': 'private-test-value', 'note': 'private-test-value'}
        write_result(path, payload, ['private-test-value'])
        loaded = json.loads(path.read_text())
        assert loaded['synthetic_data']['financial_periods'][0]['args'] == {'amount': '100.00', 'on': '2026-11-08'}
        assert loaded['synthetic_data']['financial_periods'][0]['balance'] == '550.00'
        assert loaded['synthetic_data']['at'] == '2026-11-08T12:30:00+00:00'
        assert 'password' not in loaded and loaded['note'] == '[OCULTO]'
        assert path.stat().st_mode & 0o777 == 0o600
        previous = path.read_bytes()
        try:
            write_result(path, {'unsupported': object()}, [])
        except TypeError:
            pass
        else:
            raise AssertionError('An unsupported value must not replace the checkpoint')
        assert path.read_bytes() == previous and not list(Path(directory).glob('*.tmp'))
    class ErrorResponse:
        status_code = 400

        def json(self):
            return {'error': {'code': 'tool_use_failed', 'type': 'invalid_request_error',
                              'message': 'private-test-value gsk_example',
                              'failed_generation': 'private-test-value ' + 'x' * 1700},
                    'headers': {'Authorization': 'must-not-appear'}}

    metadata = provider_error_metadata(ErrorResponse(), ['private-test-value'])
    assert metadata['http_status'] == 400 and metadata['code'] == 'tool_use_failed'
    assert metadata['message'] == '[OCULTO] [CLAVE_OCULTA]'
    assert len(metadata['failed_generation']) == 1500 and metadata['failed_generation_truncated'] is True
    assert 'headers' not in metadata and 'private-test-value' not in json.dumps(metadata)
    return {'serialization_self_test': 'passed', 'network_calls': 0, 'database_calls': 0}


def retry_after(response):
    if response.status_code != 429:
        return None
    detail = str(response.json().get('detail', '')).casefold()
    if 'personal' in detail or 'cuota de tokens agotada' in detail:
        return None
    value = response.headers.get('retry-after')
    if value:
        try:
            seconds = float(value)
        except ValueError:
            try:
                seconds = (parsedate_to_datetime(value) - datetime.now(timezone.utc)).total_seconds()
            except (ValueError, TypeError):
                return None
        return max(1, seconds) if seconds <= 60 else None
    return 60 if any(word in detail for word in ('pausa breve', 'temporal', 'minuto', 'proveedor')) else None


def provider_error_metadata(response, private):
    """Selected error fields only: no payload, request URL, headers or key."""
    result = {'http_status': response.status_code}
    try:
        body = response.json()
    except (ValueError, TypeError):
        result['message'] = 'Proveedor devolvió un error sin JSON reconocido.'
        return result
    error = body.get('error', body) if isinstance(body, dict) else {}
    if not isinstance(error, dict):
        result['message'] = 'Proveedor devolvió un formato de error no reconocido.'
        return result
    for key, limit in (('code', 128), ('type', 128), ('message', 1500), ('failed_generation', 1500)):
        value = error.get(key)
        if value is None:
            continue
        sanitized = redact(str(value), private)
        result[key] = sanitized[:limit]
        if len(sanitized) > limit:
            result[key + '_truncated'] = True
    return result


def run(args):
    import psycopg
    import httpx
    from psycopg import sql

    if os.getenv('APP_ENV') != 'local':
        raise ValueError('Se exige APP_ENV=local explícito.')
    source_url = os.environ['DATABASE_URL']
    parsed = urlsplit(source_url)
    if parsed.hostname not in ('db', 'localhost', '127.0.0.1', '::1'):
        raise ValueError('Se exige PostgreSQL local; no se usa Neon ni otro destino cloud.')
    for key in ('ADMIN_PASSWORD', 'DEMO_PASSWORD', 'BI_PASSWORD', 'GROQ_API_KEY'):
        if not os.environ.get(key):
            raise ValueError('Falta configuración privada requerida.')
    private = [source_url] + [os.environ[key] for key in ('ADMIN_PASSWORD', 'DEMO_PASSWORD', 'BI_PASSWORD', 'GROQ_API_KEY')]
    source_db = parsed.path.lstrip('/')
    fixture = 'saldo_ai_fixture_' + uuid.uuid4().hex[:12]
    admin_url = urlunsplit(parsed._replace(path='/postgres'))
    fixture_url = urlunsplit(parsed._replace(path='/' + fixture))
    private.append(fixture_url)
    directory = Path(args.output_dir).resolve()
    if 'evidencias-locales' not in directory.parts:
        raise ValueError('Salida permitida únicamente bajo evidencias-locales.')
    path = directory / (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '-' + fixture + '.json')
    result = {'started_at': now(), 'scope': 'fixture aislada con datos sintéticos; no cuenta Ana',
              'fixture_database': fixture, 'expected_model': args.model, 'ai_post_attempts': 0,
              'fixture_user_default_token_limit': 20000, 'turns': [], 'stop_reason': None,
              'created': False, 'dropped': False,
              'prior_fixture_tokens_carried': args.prior_fixture_tokens,
              'provider_scope': 'Misma organización Free; consume cuota real. No genera créditos nuevos.'}
    saved_env = {key: os.environ.get(key) for key in ('DATABASE_URL', 'DATABASE_URL_DIRECT', 'APP_ENV', 'COOKIE_SECURE')}
    seen_source = {}
    prior_day = 'day:' + datetime.now(timezone.utc).strftime('%Y-%m-%d')
    prior_applied = False
    completion_module = None
    original_completion = None
    result['prior_fixture_day_utc'] = prior_day

    def original_snapshot():
        current = datetime.now(timezone.utc)
        minute = 'minute:' + current.strftime('%Y-%m-%dT%H:%M')
        keys = ['day:' + current.strftime('%Y-%m-%d'), minute, 'calls:' + minute]
        with psycopg.connect(source_url) as conn:
            conn.execute('SET TRANSACTION READ ONLY')
            counters = conn.execute('SELECT period,used,reserved FROM budgets WHERE period=ANY(%s) ORDER BY period', (keys,)).fetchall()
            users = conn.execute('SELECT id,token_limit,tokens_used,tokens_reserved FROM users ORDER BY id').fetchall()
        return {'budget_rows': [{'period': key, 'used': used, 'reserved': reserved} for key, used, reserved in counters],
                'user_counters': [{'id': ident, 'token_limit': limit, 'tokens_used': used, 'tokens_reserved': reserved}
                                  for ident, limit, used, reserved in users]}

    def refresh_global_budget():
        nonlocal prior_applied
        snapshot = original_snapshot()
        if any(row['reserved'] for row in snapshot['budget_rows']):
            result['stop_reason'] = 'Hay reservas en el origen; detener para no solapar consumo.'
            return False
        with psycopg.connect(fixture_url) as conn:
            if not prior_applied:
                if args.prior_fixture_tokens:
                    conn.execute('''INSERT INTO budgets(period,used,reserved) VALUES(%s,%s,0)
                        ON CONFLICT(period) DO UPDATE SET used=budgets.used+EXCLUDED.used''',
                                 (prior_day, args.prior_fixture_tokens))
                prior_applied = True
            for row in snapshot['budget_rows']:
                prior = seen_source.get(row['period'], 0)
                added = max(0, row['used'] - prior)
                conn.execute('''INSERT INTO budgets(period,used,reserved) VALUES(%s,%s,0)
                    ON CONFLICT(period) DO UPDATE SET used=budgets.used+EXCLUDED.used''', (row['period'], added))
                seen_source[row['period']] = max(prior, row['used'])
        result['last_original_budget_snapshot'] = snapshot['budget_rows']
        return True

    def capacity():
        current = datetime.now(timezone.utc)
        day = 'day:' + current.strftime('%Y-%m-%d')
        minute = 'minute:' + current.strftime('%Y-%m-%dT%H:%M')
        with psycopg.connect(fixture_url) as conn:
            conn.execute('SET TRANSACTION READ ONLY')
            rows = conn.execute('SELECT period,used,reserved FROM budgets WHERE period=ANY(%s)',
                                ([day, minute, 'calls:' + minute],)).fetchall()
        values = {period: used + reserved for period, used, reserved in rows}
        return {'day_available': 100000 - values.get(day, 0),
                'minute_available': 7000 - values.get(minute, 0),
                'minute_calls': values.get('calls:' + minute, 0)}

    try:
        result['original_before'] = original_snapshot()
        with psycopg.connect(admin_url, autocommit=True) as conn:
            conn.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(fixture)))
        result['created'] = True
        os.environ.update(DATABASE_URL=fixture_url, APP_ENV='local', COOKIE_SECURE='false')
        os.environ.pop('DATABASE_URL_DIRECT', None)  # Never migrate the original/direct URL.
        migrated = subprocess.run([sys.executable, '-m', 'alembic', 'upgrade', 'head'],
                                  capture_output=True, text=True, check=False)
        if migrated.returncode:
            result['migration_exit_code'] = migrated.returncode
            raise ValueError('Falló la migración; su salida privada no se imprime.')

        # Import after switching DATABASE_URL; backend SQL resolves the env per connection.
        from backend.seed import seed
        from backend.demo import populate_demo
        from backend.db import db
        from backend.main import app
        from backend import ai
        from fastapi.testclient import TestClient

        completion_module = ai
        original_completion = ai.completion

        def audited_completion(payload):
            try:
                return original_completion(payload)
            except httpx.HTTPStatusError as exc:
                error = provider_error_metadata(exc.response, private)
                error['ai_post_attempt'] = result['ai_post_attempts']
                result.setdefault('provider_http_errors', []).append(error)
                raise  # Preserve the app's original accounting/error behavior.

        ai.completion = audited_completion

        with contextlib.redirect_stdout(io.StringIO()):
            seed()
        with db() as conn:
            demo_id = conn.execute("SELECT id FROM users WHERE email='demo@example.test'").fetchone()['id']
            result['synthetic_data'] = populate_demo(conn, user_id=demo_id)
            configured = conn.execute('''UPDATE services SET model=%s,max_rounds=3,max_output=768
                WHERE id='rag' RETURNING id,model,max_rounds,max_output''', (args.model,)).fetchone()
            result['service_config_effective'] = dict(configured)
            user = conn.execute('SELECT token_limit,tokens_used,tokens_reserved FROM users WHERE id=%s', (demo_id,)).fetchone()
            if dict(user) != {'token_limit': 20000, 'tokens_used': 0, 'tokens_reserved': 0}:
                raise ValueError('La cuenta nueva no tiene los valores predeterminados esperados.')
            result['migration_revision'] = conn.execute('SELECT version_num FROM alembic_version').fetchone()['version_num']
        if not refresh_global_budget():
            return

        with TestClient(app, base_url='http://testserver') as client:
            login = client.post('/api/v1/auth/login', json={'email': 'demo@example.test', 'password': os.environ['DEMO_PASSWORD']})
            if login.status_code != 200:
                raise ValueError('Falló el login de la cuenta aislada.')
            session = login.json()
            private.extend([session['access_token'], session['csrf']])
            headers = {'Authorization': 'Bearer ' + session['access_token']}
            conversation = None
            used_retry = False
            questions = question_list(args.fourth)
            try:
                for group, prompt in questions:
                    while True:
                        me = client.get('/api/v1/me', headers=headers).json()
                        result['fixture_quota_last'] = {key: me[key] for key in ('token_limit', 'tokens_used', 'tokens_reserved')}
                        if result['ai_post_attempts'] >= MAX_POSTS:
                            result['stop_reason'] = 'Máximo de cuatro POST de IA, incluidos reintentos.'
                            return
                        if me['token_limit'] != 20000 or me['tokens_reserved'] or me['token_limit'] - me['tokens_used'] < HEADROOM:
                            result['stop_reason'] = 'Margen inferior a6500 o reserva en curso; no elevar cuota.'
                            return
                        if not refresh_global_budget():
                            return
                        remaining = capacity()
                        if remaining['day_available'] < HEADROOM:
                            result['stop_reason'] = 'Sin margen en el límite diario compartido; no se reinician contadores.'
                            return
                        if remaining['minute_available'] < HEADROOM or remaining['minute_calls'] >= 24:
                            delay = max(1, 60 - datetime.now(timezone.utc).second)
                            result.setdefault('preflight_waits_seconds', []).append(delay)
                            write_result(path, result, private)
                            time.sleep(delay)
                            if not refresh_global_budget():
                                return
                            remaining = capacity()
                            if remaining['day_available'] < HEADROOM or remaining['minute_available'] < HEADROOM or remaining['minute_calls'] >= 24:
                                result['stop_reason'] = 'Sin margen compartido tras una pausa; revisión manual.'
                                return
                        before = client.get('/api/v1/history', headers=headers).json()
                        previous = {row['id'] for row in before}
                        payload = {'prompt': prompt}
                        if group == 'metas' and conversation:
                            payload['conversation_id'] = conversation
                        record = {'group': group, 'prompt': prompt, 'started_at': now()}
                        result['ai_post_attempts'] += 1
                        result['turns'].append(record)
                        write_result(path, result, private)
                        started = time.monotonic()
                        response = client.post('/api/v1/ai/rag', headers=headers, json=payload)
                        record['latency_seconds'] = round(time.monotonic() - started, 3)
                        record['http_status'] = response.status_code
                        body = response.json()
                        after = client.get('/api/v1/history', headers=headers).json()
                        found = [row for row in after if row['id'] not in previous and row['prompt'] == prompt]
                        ident = body.get('id') or (found[0]['id'] if found else None)
                        if ident:
                            detail = client.get('/api/v1/history/' + ident, headers=headers).json()
                            record['history'] = detail
                            record['provider_tokens'] = sum(call['input_tokens'] + call['output_tokens'] for call in detail['calls'])
                            if group == 'metas':
                                conversation = detail['request']['conversation_id']
                        me = client.get('/api/v1/me', headers=headers).json()
                        result['fixture_quota_last'] = {key: me[key] for key in ('token_limit', 'tokens_used', 'tokens_reserved')}
                        if response.status_code == 200:
                            record['response'] = body['response']
                            record['sources'] = body.get('sources', [])
                            record['semantic_verdict'] = 'pendiente de revisión humana'
                            break
                        record['error'] = body.get('detail', 'API sin detalle')
                        delay = retry_after(response)
                        if delay is not None and not used_retry and result['ai_post_attempts'] < MAX_POSTS:
                            used_retry = True
                            record['wait_before_retry_seconds'] = delay
                            write_result(path, result, private)
                            time.sleep(delay)
                            continue
                        result['stop_reason'] = 'Error conservado; no se continúa con más preguntas.'
                        return
                result['stop_reason'] = 'Cuatro preguntas completadas.'
            finally:
                result['logout_http_status'] = client.post('/api/v1/auth/logout', headers=headers).status_code
    except Exception as exc:
        # Exception messages may include DB URLs: retain only the class, never a traceback.
        result['failure_class'] = type(exc).__name__
        result['stop_reason'] = 'Fallo controlado; revisar fase/configuración, sin imprimir secretos.'
    finally:
        if completion_module is not None and original_completion is not None:
            completion_module.completion = original_completion
            result['provider_function_restored'] = True
        for key, value in saved_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        result['environment_restored'] = all(os.environ.get(key) == value for key, value in saved_env.items())
        if result['created'] and fixture != source_db and fixture.startswith('saldo_ai_fixture_'):
            try:
                with psycopg.connect(admin_url, autocommit=True) as conn:
                    conn.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(fixture)))
                result['dropped'] = True
            except Exception as exc:
                result['cleanup_failure_class'] = type(exc).__name__
        try:
            result['original_after'] = original_snapshot()
            result['original_user_counters_unchanged'] = result['original_before']['user_counters'] == result['original_after']['user_counters']
        except Exception as exc:
            result['original_verification_failure_class'] = type(exc).__name__
        result['finished_at'] = now()
        write_result(path, result, private)
        print(str(path), flush=True)  # Only the private artifact path; never responses/credentials.


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', action='store_true')
    parser.add_argument('--self-test', action='store_true', help='Prueba JSON atómico con Decimal/fechas en archivos temporales; sin API ni BD.')
    parser.add_argument('--model', choices=MODELS, default=MODELS[1])
    parser.add_argument('--fourth', choices=FOURTH, default='quincena')
    parser.add_argument('--prior-fixture-tokens', type=int, default=0,
                        help='Uso previo de fixtures del día UTC actual no incluido en la BD origen; se suma al límite diario compartido.')
    parser.add_argument('--output-dir', default='/tmp/evidencias-locales/auditoria-fixture')
    args = parser.parse_args()
    if not 0 <= args.prior_fixture_tokens <= 100000:
        parser.error('El consumo previo debe estar entre 0 y 100000 tokens; nunca aumenta límites.')
    if args.self_test:
        print(json.dumps(serialization_self_test(), ensure_ascii=False))
        return
    if not args.run:
        print(json.dumps({'dry_run': True, 'fixture_default_token_limit': 20000,
                          'model': args.model, 'max_rounds': 3, 'max_output': 768,
                          'max_ai_posts_including_retry': MAX_POSTS,
                          'prior_fixture_tokens_carried': args.prior_fixture_tokens,
                          'questions': question_list(args.fourth),
                          'original_database': 'Solo lecturas; no se alteran Ana, su cuota ni sus datos.',
                          'provider': 'Misma organización y límites Free reales; no nuevos créditos.'},
                         indent=2, ensure_ascii=False))
        return
    try:
        run(args)
    except (ValueError, KeyError, OSError, TypeError):
        raise SystemExit('No se inició la fixture; revisar entorno local/configuración privada. No se imprimen secretos.') from None


if __name__ == '__main__':
    main()
