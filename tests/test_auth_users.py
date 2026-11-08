import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from backend import main
from backend.db import db, one, many
from backend.security import password_ok


PASSWORD = 'test-registration-password-1234'


def signup(client, email='persona@example.test', **extra):
    return client.post('/api/v1/auth/register', json={'email': email, 'password': PASSWORD, **extra})


def login(client, email, password='test-only-password-1234'):
    result = client.post('/api/v1/auth/login', json={'email': email, 'password': password})
    assert result.status_code == 200, result.text
    return {'Authorization': 'Bearer '+result.json()['access_token']}


def test_register_normalizes_email_creates_empty_user_and_starts_session(client):
    result = signup(client, '  Nueva.Persona@EXAMPLE.test  ')
    assert result.status_code == 201, result.text
    session = result.json()
    assert set(session) == {'access_token', 'token_type', 'csrf'}
    cookie = result.headers['set-cookie']
    assert 'HttpOnly' in cookie and 'SameSite=strict' in cookie and 'Max-Age=28800' in cookie
    me = client.get('/api/v1/me').json()
    assert me['email'] == 'nueva.persona@example.test'
    assert me['name'] == 'nueva.persona'
    assert me['role'] == 'user' and me['token_limit'] == 20000
    assert me['tokens_used'] == me['tokens_reserved'] == 0
    with db() as conn:
        stored = one(conn, 'SELECT * FROM users WHERE id=%s', (me['id'],))
        assert stored['active'] and stored['bi_scope'] is None
        assert stored['password_hash'] != PASSWORD and password_ok(PASSWORD, stored['password_hash'])
        for table in ('categories', 'obligations', 'goals', 'recurring'):
            assert one(conn, f'SELECT count(*) AS n FROM {table} WHERE user_id=%s', (me['id'],))['n'] == 0
        assert one(conn, "SELECT count(*) AS n FROM audit WHERE actor_id=%s AND action='register'", (me['id'],))['n'] == 1
    assert client.post('/api/v1/categories', json={'name': 'Nueva', 'kind': 'expense'}).status_code == 403
    assert client.post('/api/v1/categories', headers={'X-CSRF-Token': session['csrf']}, json={'name': 'Nueva', 'kind': 'expense'}).status_code == 200
    assert client.get('/api/v1/admin/users').status_code == 403


def test_register_optional_name_secure_cookie_and_duplicate_identity(client, monkeypatch):
    monkeypatch.setenv('COOKIE_SECURE', 'true')
    result = signup(client, name='  Nombre propio  ')
    assert result.status_code == 201 and 'Secure' in result.headers['set-cookie']
    assert client.get('/api/v1/me').json()['name'] == 'Nombre propio'
    assert signup(client, ' PERSONA@EXAMPLE.TEST ').status_code == 409
    assert signup(client, 'ADMIN@EXAMPLE.TEST').status_code == 409
    assert signup(client, 'otra@example.test', name='   ').status_code == 201
    assert client.get('/api/v1/me').json()['name'] == 'otra'


@pytest.mark.parametrize('extra', [
    {'role': 'admin'}, {'role': 'bi'}, {'token_limit': 100000}, {'active': False},
    {'bi_scope': 2}, {'tokens_used': 0}, {'password_hash': 'plain'},
])
def test_registration_cannot_choose_privileges_or_quota(client, extra):
    assert signup(client, **extra).status_code == 422
    with db() as conn:
        assert one(conn, 'SELECT count(*) AS n FROM users')['n'] == 3


@pytest.mark.parametrize('payload', [
    {'email': 'sin-correo', 'password': PASSWORD},
    {'email': 'dos@@example.test', 'password': PASSWORD},
    {'email': 'name@example.test', 'password': 'short'},
    {'email': 'name@example.test', 'password': 'x'*129},
])
def test_registration_validates_email_and_password(client, payload):
    assert client.post('/api/v1/auth/register', json=payload).status_code == 422


def test_registration_rate_limits_address_not_just_email_and_expires(client, monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr(main, 'time', SimpleNamespace(monotonic=lambda: clock[0]))
    for index in range(5):
        assert signup(client, f'persona{index}@example.test').status_code == 201
    denied = signup(client, 'persona5@example.test')
    assert denied.status_code == 429 and denied.headers['retry-after'] == '900'
    with db() as conn:
        assert one(conn, "SELECT id FROM users WHERE email='persona5@example.test'") is None
    clock[0] += 901
    assert signup(client, 'persona5@example.test').status_code == 201


def test_admin_edit_email_preserves_backward_compatibility_and_checks_duplicates(client, admin_auth):
    old = {'name': 'Ana editada', 'active': True, 'token_limit': 18000}
    assert client.put('/api/v1/admin/users/2', headers=admin_auth, json=old).status_code == 200
    assert client.put('/api/v1/admin/users/2', headers=admin_auth, json={**old, 'email': '  ANA.NUEVA@EXAMPLE.TEST '}).status_code == 200
    users = client.get('/api/v1/admin/users', headers=admin_auth).json()
    changed = next(u for u in users if u['id'] == 2)
    assert changed['email'] == 'ana.nueva@example.test' and changed['name'] == 'Ana editada'
    assert client.post('/api/v1/auth/login', json={'email': 'demo@example.test', 'password': 'test-only-password-1234'}).status_code == 401
    login(client, 'ANA.NUEVA@EXAMPLE.TEST')
    conflict = client.put('/api/v1/admin/users/2', headers=admin_auth, json={**old, 'name': 'No debe persistir', 'email': 'ADMIN@EXAMPLE.TEST'})
    assert conflict.status_code == 409
    with db() as conn:
        assert one(conn, 'SELECT name,email,token_limit FROM users WHERE id=2') == {
            'name': 'Ana editada', 'email': 'ana.nueva@example.test', 'token_limit': 18000}


def test_admin_inactivation_revokes_all_sessions_and_reactivation_does_not_restore_them(client, admin_auth):
    first = login(client, 'demo@example.test')
    second = login(client, 'demo@example.test')
    with db() as conn:
        assert one(conn, 'SELECT count(*) AS n FROM sessions WHERE user_id=2')['n'] == 2
    payload = {'name': 'Ana', 'active': False, 'token_limit': 20000}
    assert client.put('/api/v1/admin/users/2', headers=admin_auth, json=payload).status_code == 200
    assert client.get('/api/v1/me', headers=first).status_code == 401
    assert client.get('/api/v1/me', headers=second).status_code == 401
    with db() as conn:
        assert one(conn, 'SELECT count(*) AS n FROM sessions WHERE user_id=2')['n'] == 0
    assert client.put('/api/v1/admin/users/2', headers=admin_auth, json={**payload, 'active': True}).status_code == 200
    assert client.get('/api/v1/me', headers=first).status_code == 401
    assert client.get('/api/v1/me', headers=login(client, 'demo@example.test')).status_code == 200


def test_admin_delete_is_logical_revokes_sessions_and_preserves_history(client, admin_auth):
    user_auth = login(client, 'demo@example.test')
    conversation, request = uuid.uuid4(), uuid.uuid4()
    with db() as conn:
        conn.execute("INSERT INTO conversations(id,user_id,service) VALUES(%s,2,'rag')", (conversation,))
        conn.execute("""INSERT INTO requests(id,conversation_id,user_id,service,prompt,response,status,finished_at)
                     VALUES(%s,%s,2,'rag','Consulta','Respuesta','success',now())""", (request, conversation))
        conn.execute("INSERT INTO provider_calls(request_id,model,input_tokens,output_tokens,usage_kind) VALUES(%s,'test',10,5,'provider')", (request,))
        previous = one(conn, 'SELECT count(*) AS n FROM obligations WHERE user_id=2')['n']
    assert client.delete('/api/v1/admin/users/2', headers=admin_auth).status_code == 200
    assert client.get('/api/v1/me', headers=user_auth).status_code == 401
    assert client.post('/api/v1/auth/login', json={'email': 'demo@example.test', 'password': 'test-only-password-1234'}).status_code == 401
    with db() as conn:
        assert not one(conn, 'SELECT active FROM users WHERE id=2')['active']
        assert one(conn, 'SELECT count(*) AS n FROM obligations WHERE user_id=2')['n'] == previous
        assert one(conn, 'SELECT id FROM requests WHERE id=%s', (request,))
        assert one(conn, 'SELECT input_tokens,output_tokens FROM provider_calls WHERE request_id=%s', (request,)) == {'input_tokens': 10, 'output_tokens': 5}
        assert one(conn, "SELECT id FROM audit WHERE entity='users' AND entity_id='2' AND action='deactivate'")
    # Idempotent logical deletion retains the same identity, including its email.
    assert client.delete('/api/v1/admin/users/2', headers=admin_auth).status_code == 200
    assert signup(client, 'DEMO@EXAMPLE.TEST').status_code == 409
    listed = client.get('/api/v1/admin/users', headers=admin_auth).json()
    assert next(u for u in listed if u['id'] == 2)['active'] is False


def test_user_management_restricts_scope_and_keeps_an_active_admin(client, admin_auth):
    payload = {'name': 'Admin', 'active': False, 'token_limit': 20000}
    assert client.put('/api/v1/admin/users/1', headers=admin_auth, json=payload).status_code == 409
    assert client.delete('/api/v1/admin/users/1', headers=admin_auth).status_code == 409
    assert client.delete('/api/v1/admin/users/999999', headers=admin_auth).status_code == 404
    user_auth = login(client, 'demo@example.test')
    assert client.delete('/api/v1/admin/users/1', headers=user_auth).status_code == 403
    assert client.put('/api/v1/admin/users/1', headers=user_auth, json=payload).status_code == 403
    created = client.post('/api/v1/admin/users', headers=admin_auth, json={
        'email': ' SEGUNDO@EXAMPLE.TEST ', 'name': 'Segundo', 'password': PASSWORD, 'role': 'admin'})
    assert created.status_code == 200
    other_id = created.json()['id']
    # Self-deactivation stays blocked even when there is another active admin.
    assert client.delete('/api/v1/admin/users/1', headers=admin_auth).status_code == 409
    assert client.delete(f'/api/v1/admin/users/{other_id}', headers=admin_auth).status_code == 200
    with db() as conn:
        assert one(conn, "SELECT count(*) AS n FROM users WHERE role='admin' AND active")['n'] == 1


def test_concurrent_admin_deactivations_cannot_remove_last_active_admin(client, admin_auth):
    other = client.post('/api/v1/admin/users', headers=admin_auth, json={
        'email': 'segundo@example.test', 'name': 'Segundo', 'password': PASSWORD, 'role': 'admin'}).json()['id']
    with db() as conn:
        actors = many(conn, 'SELECT id,role FROM users WHERE id IN (1,%s) ORDER BY id', (other,))
    barrier = Barrier(2)
    def deactivate(pair):
        actor, target = pair
        barrier.wait()
        try:
            assert main.user_deactivate(target['id'], actor) == {'ok': True}
            return 200
        except HTTPException as exc:
            return exc.status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(pool.map(deactivate, [(actors[0], actors[1]), (actors[1], actors[0])]))
    assert statuses.count(200) == 1 and all(status in (200, 401, 409) for status in statuses)
    with db() as conn:
        assert one(conn, "SELECT count(*) AS n FROM users WHERE role='admin' AND active")['n'] == 1
