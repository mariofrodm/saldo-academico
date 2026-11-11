"""Cookie rotation must fail closed before any assistant work begins."""

from backend import ai
from backend.db import db, one


def login(client, email='demo@example.test'):
    response = client.post('/api/v1/auth/login', json={
        'email': email, 'password': 'test-only-password-1234'})
    assert response.status_code == 200, response.text
    return response.json()


def assert_no_assistant_work():
    with db() as conn:
        for table in ('conversations', 'requests', 'tool_runs', 'provider_calls'):
            assert one(conn, f'SELECT count(*) AS n FROM {table}')['n'] == 0


def test_cookie_relogin_rejects_old_csrf_and_me_supplies_current_token(client, monkeypatch):
    def forbidden_provider(*args, **kwargs):
        raise AssertionError('CSRF recovery must not contact an AI provider')

    monkeypatch.setattr(ai, 'completion', forbidden_provider)
    first = login(client)
    first_user = client.get('/api/v1/me').json()
    second = login(client)
    assert first['access_token'] != second['access_token']
    assert first['csrf'] != second['csrf']
    assert client.cookies.get('saldo_session') == second['access_token']
    payload = {'prompt': '¿Qué metas tengo?', 'local_only': True}
    rejected = client.post('/api/v1/ai/goals', headers={'X-CSRF-Token': first['csrf']}, json=payload)
    assert rejected.status_code == 403
    assert rejected.json() == {'detail': 'Falta protección CSRF'}
    assert_no_assistant_work()

    refreshed = client.get('/api/v1/me')
    assert refreshed.status_code == 200
    assert refreshed.json()['id'] == first_user['id']
    assert refreshed.json()['csrf'] == second['csrf']
    accepted = client.post('/api/v1/ai/goals', headers={'X-CSRF-Token': refreshed.json()['csrf']}, json=payload)
    assert accepted.status_code == 200, accepted.text
    with db() as conn:
        assert one(conn, 'SELECT count(*) AS n FROM requests')['n'] == 1
        assert one(conn, 'SELECT count(*) AS n FROM provider_calls')['n'] == 0


def test_cookie_account_change_identifies_new_account_without_replaying_old_request(client):
    first = login(client)
    first_user = client.get('/api/v1/me').json()
    second = login(client, 'admin@example.test')
    rejected = client.post('/api/v1/ai/goals', headers={'X-CSRF-Token': first['csrf']},
                           json={'prompt': '¿Qué metas tengo?', 'local_only': True})
    assert rejected.status_code == 403
    assert rejected.json() == {'detail': 'Falta protección CSRF'}
    refreshed = client.get('/api/v1/me')
    assert refreshed.status_code == 200
    assert refreshed.json()['id'] != first_user['id']
    assert refreshed.json()['email'] == 'admin@example.test'
    assert refreshed.json()['csrf'] == second['csrf']
    assert refreshed.json()['csrf'] != first['csrf']
    assert_no_assistant_work()
