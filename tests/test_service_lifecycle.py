"""Service CRUD preserves accounting and restricts strategies to audited tool sets."""
import uuid

import pytest

from backend.db import db, one, many


CONFIG = {'name': 'Consulta personalizada', 'enabled': True,
          'model': 'openai/gpt-oss-120b', 'max_output': 768, 'max_rounds': 6}


def test_service_crud_soft_delete_restore_and_preserve_history(client, admin_auth, auth):
    conversation, request = uuid.uuid4(), uuid.uuid4()
    with db() as conn:
        conn.execute("INSERT INTO conversations(id,user_id,service) VALUES(%s,2,'rag')", (conversation,))
        conn.execute("""INSERT INTO requests(id,conversation_id,user_id,service,prompt,response,status)
                     VALUES(%s,%s,2,'rag','Consulta previa','Respuesta previa','success')""", (request, conversation))
        conn.execute("INSERT INTO provider_calls(request_id,model,input_tokens,output_tokens,usage_kind) VALUES(%s,'previous',20,10,'provider')", (request,))
    original = client.get('/api/v1/admin/services', headers=admin_auth).json()
    assert {item['id'] for item in original} == {'rag', 'budget', 'goals'}
    assert all(item['deleted_at'] is None for item in original)
    assert client.post('/api/v1/admin/services', headers=admin_auth, json={'id': 'rag', **CONFIG}).status_code == 409
    changed = client.put('/api/v1/admin/services/rag', headers=admin_auth, json={**CONFIG, 'name': '  Mis finanzas  '})
    assert changed.status_code == 200 and changed.json()['name'] == 'Mis finanzas'
    assert client.delete('/api/v1/admin/services/rag', headers=admin_auth).json() == {'ok': True}
    deleted = next(row for row in client.get('/api/v1/admin/services', headers=admin_auth).json() if row['id'] == 'rag')
    assert deleted['deleted_at'] is not None and not deleted['enabled']
    assert 'rag' not in {row['id'] for row in client.get('/api/v1/services', headers=auth).json()['items']}
    assert client.post('/api/v1/ai/rag', headers=auth, json={'prompt': '¿Cómo voy?'}).status_code == 409
    assert client.put('/api/v1/admin/services/rag', headers=admin_auth, json=CONFIG).status_code == 409
    assert client.delete('/api/v1/admin/services/rag', headers=admin_auth).status_code == 200
    restored = client.post('/api/v1/admin/services', headers=admin_auth, json={'id': 'rag', **CONFIG})
    assert restored.status_code == 201 and restored.json()['deleted_at'] is None
    assert restored.json()['enabled'] and restored.json()['name'] == CONFIG['name']
    assert {row['id'] for row in client.get('/api/v1/services', headers=auth).json()['items']} == {'rag', 'budget', 'goals'}
    with db() as conn:
        assert one(conn, 'SELECT id FROM conversations WHERE id=%s', (conversation,))
        assert one(conn, 'SELECT response FROM requests WHERE id=%s', (request,))['response'] == 'Respuesta previa'
        assert one(conn, 'SELECT input_tokens,output_tokens FROM provider_calls WHERE request_id=%s', (request,)) == {'input_tokens': 20, 'output_tokens': 10}
        assert many(conn, "SELECT action FROM audit WHERE entity='services' AND entity_id='rag' ORDER BY id") == [
            {'action': 'update'}, {'action': 'delete'}, {'action': 'create'}]


def test_service_create_missing_strategy_and_update_legacy_body(client, admin_auth):
    # A fresh installation can configure any of the three supported strategies.
    with db() as conn:
        conn.execute("DELETE FROM services WHERE id='budget'")
    result = client.post('/api/v1/admin/services', headers=admin_auth, json={'id': 'budget', **CONFIG})
    assert result.status_code == 201 and result.json()['id'] == 'budget'
    legacy = {key: value for key, value in CONFIG.items() if key != 'name'}
    updated = client.put('/api/v1/admin/services/budget', headers=admin_auth, json={**legacy, 'enabled': False})
    assert updated.status_code == 200 and updated.json()['name'] == CONFIG['name']
    assert not updated.json()['enabled']
    # Disabled is a reversible configuration; it is distinct from a deleted slot.
    assert client.post('/api/v1/admin/services', headers=admin_auth, json={'id': 'budget', **CONFIG}).status_code == 409
    assert client.put('/api/v1/admin/services/missing', headers=admin_auth, json=CONFIG).status_code == 404
    assert client.delete('/api/v1/admin/services/missing', headers=admin_auth).status_code == 404


@pytest.mark.parametrize('extra', [
    {'id': 'unrestricted'}, {'id': 'rag; DROP TABLE users'}, {'name': '  '}, {'name': None},
    {'model': '../model with spaces'}, {'max_output': 769}, {'max_output': 127},
    {'max_rounds': 1}, {'max_rounds': 7}, {'deleted_at': None},
])
def test_service_create_rejects_invalid_and_unmanaged_fields(client, admin_auth, extra):
    result = client.post('/api/v1/admin/services', headers=admin_auth, json={'id': 'rag', **CONFIG, **extra})
    assert result.status_code == 422, result.text


def test_service_management_requires_administrator(client, auth):
    assert client.get('/api/v1/admin/services', headers=auth).status_code == 403
    assert client.post('/api/v1/admin/services', headers=auth, json={'id': 'rag', **CONFIG}).status_code == 403
    assert client.put('/api/v1/admin/services/rag', headers=auth, json=CONFIG).status_code == 403
    assert client.delete('/api/v1/admin/services/rag', headers=auth).status_code == 403
    client.cookies.clear()
    assert client.get('/api/v1/admin/services').status_code == 401
    with db() as conn:
        assert one(conn, 'SELECT count(*) AS n FROM services WHERE deleted_at IS NOT NULL')['n'] == 0


def test_deleted_service_remains_deleted_after_idempotent_seed(client, admin_auth):
    from backend.seed import seed
    assert client.delete('/api/v1/admin/services/goals', headers=admin_auth).status_code == 200
    seed()
    with db() as conn:
        assert one(conn, "SELECT deleted_at IS NOT NULL AND NOT enabled AS deleted FROM services WHERE id='goals'")['deleted']
