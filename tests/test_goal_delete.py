import pytest
from fastapi import HTTPException

from backend import main
from backend.db import db, one, many
from backend.security import fingerprint


def test_owner_delete_removes_all_movements_updates_cash_flow_and_preserves_other_records(client, auth):
    goal = client.get('/api/v1/goals', headers=auth).json()[0]
    ident = goal['id']
    for amount, stamp in [('100.00', '2026-11-06'), ('-40.00', '2026-11-07')]:
        assert client.post(f'/api/v1/goals/{ident}/movements', headers=auth,
                           json={'amount': amount, 'moved_on': stamp}).status_code == 200
    with db() as conn:
        other_goal = one(conn, "INSERT INTO goals(user_id,name,target,deadline) VALUES(2,'Otra meta',100,'2027-02-01') RETURNING id")['id']
        other_owner = one(conn, "INSERT INTO goals(user_id,name,target,deadline) VALUES(1,'Meta privada',100,'2027-02-01') RETURNING id")['id']
        conn.execute("INSERT INTO savings(goal_id,amount,moved_on) VALUES(%s,20,'2026-08-01'),(%s,30,'2026-11-01')", (other_goal, other_owner))
        unrelated = {table: many(conn, f'SELECT * FROM {table} ORDER BY id') for table in
                     ('obligations', 'payments', 'categories', 'recurring', 'users', 'requests', 'provider_calls', 'services')}
        other_goals = many(conn, 'SELECT * FROM goals WHERE id<>%s ORDER BY id', (ident,))
        other_movements = many(conn, 'SELECT * FROM savings WHERE goal_id<>%s ORDER BY id', (ident,))
    before = client.get('/api/v1/board?month=2026-11-01', headers=auth).json()['summary']
    assert before['net_savings'] == '560.00' and before['available'] == '4040.00'
    removed = client.delete(f'/api/v1/goals/{ident}', headers=auth)
    assert removed.status_code == 200 and removed.json() == {'ok': True, 'deleted_movements': 3}
    assert all(row['id'] != ident for row in client.get('/api/v1/goals', headers=auth).json())
    assert client.get(f'/api/v1/goals/{ident}/movements', headers=auth).status_code == 404
    after = client.get('/api/v1/board?month=2026-11-01', headers=auth).json()['summary']
    assert after['net_savings'] == '0.00' and after['available'] == '4600.00'
    assert after['income'] == before['income'] and after['expense'] == before['expense']
    with db() as conn:
        assert one(conn, 'SELECT id FROM goals WHERE id=%s', (ident,)) is None
        assert one(conn, 'SELECT count(*) AS n FROM savings WHERE goal_id=%s', (ident,))['n'] == 0
        assert many(conn, 'SELECT * FROM goals ORDER BY id') == other_goals
        assert many(conn, 'SELECT * FROM savings ORDER BY id') == other_movements
        for table, rows in unrelated.items():
            assert many(conn, f'SELECT * FROM {table} ORDER BY id') == rows
        assert one(conn, "SELECT actor_id FROM audit WHERE action='delete' AND entity='goals' AND entity_id=%s", (str(ident),))['actor_id'] == 2
        assert one(conn, "SELECT actor_id FROM audit WHERE action='delete_dependents' AND entity='savings' AND entity_id=%s", (f'goal={ident};count=3',))['actor_id'] == 2
    assert client.delete(f'/api/v1/goals/{ident}', headers=auth).status_code == 404


def test_foreign_admin_or_unknown_goal_has_same_404_and_preserves_every_movement(client, auth, admin_auth):
    with db() as conn:
        owned_id = one(conn, 'SELECT id FROM goals WHERE user_id=2')['id']
        other = one(conn, "INSERT INTO goals(user_id,name,target,deadline) VALUES(1,'Privada',100,'2027-01-01') RETURNING id")['id']
        conn.execute("INSERT INTO savings(goal_id,amount,moved_on) VALUES(%s,50,'2026-11-01')", (other,))
        goals = many(conn, 'SELECT * FROM goals ORDER BY id')
        savings = many(conn, 'SELECT * FROM savings ORDER BY id')
    foreign = client.delete(f'/api/v1/goals/{other}', headers=auth)
    unknown = client.delete('/api/v1/goals/9999999', headers=auth)
    assert foreign.status_code == unknown.status_code == 404
    assert foreign.json() == unknown.json()
    assert client.delete(f'/api/v1/goals/{owned_id}', headers=admin_auth).status_code == 404
    with db() as conn:
        assert many(conn, 'SELECT * FROM goals ORDER BY id') == goals
        assert many(conn, 'SELECT * FROM savings ORDER BY id') == savings


def test_goal_deletion_requires_auth_and_cookie_csrf_and_rejects_bi(client):
    with db() as conn:
        ident = one(conn, 'SELECT id FROM goals WHERE user_id=2')['id']
        conn.execute("INSERT INTO sessions(token_hash,user_id,csrf,expires_at) VALUES(%s,3,'test-only-bi-csrf',now()+interval '1 hour')", (fingerprint('test-only-bi-token'),))
    assert client.delete(f'/api/v1/goals/{ident}').status_code == 401
    assert client.delete(f'/api/v1/goals/{ident}', auth=('bi@example.test', 'test-only-password-1234')).status_code == 401
    assert client.delete(f'/api/v1/goals/{ident}', headers={'Authorization': 'Bearer test-only-bi-token'}).status_code == 401
    login = client.post('/api/v1/auth/login', json={'email': 'demo@example.test', 'password': 'test-only-password-1234'})
    assert login.status_code == 200
    assert client.delete(f'/api/v1/goals/{ident}').status_code == 403
    assert client.delete(f'/api/v1/goals/{ident}', headers={'X-CSRF-Token': login.json()['csrf']}).status_code == 200


def test_delete_empty_inactive_goal_does_not_require_moving_money_first(client, auth):
    created = client.post('/api/v1/goals', headers=auth, json={'name': 'Pospuesta', 'target': '100.00', 'deadline': '2027-01-01', 'active': False})
    assert created.status_code == 200
    result = client.delete(f'/api/v1/goals/{created.json()["id"]}', headers=auth)
    assert result.status_code == 200 and result.json() == {'ok': True, 'deleted_movements': 0}


def test_audit_failure_rolls_back_parent_and_dependents_together(client, auth, monkeypatch):
    with db() as conn:
        goal = one(conn, 'SELECT * FROM goals WHERE user_id=2')
        savings = many(conn, 'SELECT * FROM savings WHERE goal_id=%s ORDER BY id', (goal['id'],))
        count = one(conn, 'SELECT count(*) AS n FROM audit')['n']
    def unavailable_audit(*args):
        raise HTTPException(503, 'Auditoría no disponible')
    monkeypatch.setattr(main, 'audit', unavailable_audit)
    result = client.delete(f'/api/v1/goals/{goal["id"]}', headers=auth)
    assert result.status_code == 503
    with db() as conn:
        assert one(conn, 'SELECT * FROM goals WHERE id=%s', (goal['id'],)) == goal
        assert many(conn, 'SELECT * FROM savings WHERE goal_id=%s ORDER BY id', (goal['id'],)) == savings
        assert one(conn, 'SELECT count(*) AS n FROM audit')['n'] == count
