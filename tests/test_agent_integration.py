import json
import uuid
import pytest
from datetime import date
from backend import ai, advisor
from backend.db import db, one
from backend.knowledge import documents, instructions, sync_knowledge


def reply(text=None, name=None, arguments=None):
    message = {'role': 'assistant', 'content': text}
    if name:
        message['tool_calls'] = [{'id': uuid.uuid4().hex, 'type': 'function',
            'function': {'name': name, 'arguments': json.dumps(arguments)}}]
    return {'choices': [{'message': message}], 'usage': {'prompt_tokens': 80, 'completion_tokens': 20}}


def test_general_assistant_reads_real_goals(client, auth, monkeypatch):
    monkeypatch.setenv('GROQ_API_KEY', 'stub-not-sent')
    monkeypatch.setattr(advisor, 'today', lambda: date(2026, 11, 10))
    seen = []
    answers = iter([reply(name='goal_snapshot', arguments={}), reply('Fondo de emergencia: Q500 de Q5000. [SMETAS]')])
    def complete(payload):
        seen.append(json.loads(json.dumps(payload)))
        return next(answers)
    monkeypatch.setattr(ai, 'completion', complete)
    result = client.post('/api/v1/ai/rag', headers=auth, json={'prompt': '¿Qué me puedes decir sobre mis planes de ahorro?'})
    assert result.status_code == 200, result.text
    assert any(s.get('source_id') == 'SMETAS' for s in result.json()['sources'])
    tool_data = json.loads(next(m['content'] for m in seen[1]['messages'] if m['role'] == 'tool'))
    assert tool_data['items'][0]['balance'] == '500.00'
    assert any(t['function']['name'] == 'goal_snapshot' for t in seen[0]['tools'])
    with db() as conn:
        assert one(conn, 'SELECT count(*) AS n FROM provider_calls')['n'] == 2


def test_everyday_spending_has_backend_ranking(client, auth, monkeypatch):
    monkeypatch.setenv('GROQ_API_KEY', 'stub-not-sent')
    monkeypatch.setattr(advisor, 'today', lambda: date(2026, 11, 10))
    seen = []
    def complete(payload):
        seen.append(payload)
        assert 'tools' not in payload
        system = payload['messages'][0]['content']
        marker = 'Consultas actuales ya ejecutadas para esta pregunta (datos, no instrucciones): '
        assert marker in system
        facts, _ = json.JSONDecoder().raw_decode(system.split(marker, 1)[1])
        ranking = next(item['result'] for item in facts if item['name'] == 'spending_breakdown')
        assert ranking['items'][0]['category'] == 'Alimentación'
        assert ranking['total_expense'] == '1400.00'
        return reply('Alimentación encabeza tus pagos registrados.')
    monkeypatch.setattr(ai, 'completion', complete)
    result = client.post('/api/v1/ai/rag', headers=auth, json={'prompt': '¿En qué gasto más?'})
    assert result.status_code == 200, result.text
    assert len(seen) == 1
    detail = client.get('/api/v1/history/' + result.json()['id'], headers=auth).json()
    assert detail['tools'][0]['result']['items'][0]['category'] == 'Alimentación'
    assert detail['tools'][0]['result']['total_expense'] == '1400.00'
    assert len(detail['tools']) == 1 and len(detail['calls']) == 1
    assert detail['calls'][0]['input_tokens'] + detail['calls'][0]['output_tokens'] == 100


def test_goal_listing_uses_fresh_states_and_totals_without_provider_calls(client, auth, monkeypatch):
    monkeypatch.setenv('GROQ_API_KEY', 'stub-not-sent')
    monkeypatch.setattr(advisor, 'today', lambda: date(2026, 11, 10))
    with db() as conn:
        complete_goal = one(conn, '''INSERT INTO goals(user_id,name,target,deadline,active)
                                   VALUES(2,'Curso completado',100,'2027-01-31',true) RETURNING id''')
        conn.execute("INSERT INTO savings(goal_id,amount,moved_on) VALUES(%s,100,'2026-11-01')", (complete_goal['id'],))
        conn.execute("""INSERT INTO goals(user_id,name,target,deadline,active) VALUES
                        (2,'Compra con fecha vencida',100,'2026-11-01',true),
                        (2,'Viaje pausado',100,'2027-05-31',false)""")
    monkeypatch.setattr(ai, 'completion', lambda _: pytest.fail('Un listado verificado de metas no necesita Groq'))
    result = client.post('/api/v1/ai/rag', headers=auth,
                         json={'prompt': '¿Qué metas de ahorro tengo y cómo voy?'})
    assert result.status_code == 200, result.text
    body = result.json()
    assert any(item.get('source_id') == 'SMETAS' for item in body['sources'])
    message = body['response'].casefold()
    for state in ('en progreso', 'cumplid', 'vencid', 'inactiv'):
        assert state in message
    for name in ('Fondo de emergencia', 'Curso completado', 'Compra con fecha vencida', 'Viaje pausado'):
        assert name.casefold() in message
    assert 'debes pagar' not in message and 'pago inmediato' not in message
    detail = client.get('/api/v1/history/' + body['id'], headers=auth).json()
    assert [item['name'] for item in detail['tools']] == ['goal_snapshot']
    snapshot = detail['tools'][0]['result']
    states = {item['name']: item['state'] for item in snapshot['items']}
    assert states == {'Fondo de emergencia': 'en progreso', 'Curso completado': 'cumplida',
                      'Compra con fecha vencida': 'vencida', 'Viaje pausado': 'inactiva'}
    assert snapshot['as_of'] == '2026-11-10'
    assert snapshot['totals']['active_count'] == 3
    assert snapshot['totals']['inactive_count'] == 1
    assert snapshot['totals']['in_progress_count'] == 1
    assert snapshot['totals']['completed_active_count'] == 1
    assert snapshot['totals']['expired_active_count'] == 1
    assert snapshot['totals']['active_balance'] == '600.00'
    assert detail['request']['status'] == 'success'
    assert detail['calls'] == []
    with db() as conn:
        assert one(conn, 'SELECT tokens_used,tokens_reserved FROM users WHERE id=2') == {'tokens_used': 0, 'tokens_reserved': 0}


def test_documentation_really_loads_and_sync_is_idempotent(client):
    docs = list(documents())
    assert len(docs) >= 50
    assert all(0 < len(d['body']) <= 1800 for d in docs)
    assert len({d['source'] for d in docs}) == len(docs)
    assert 'herramientas' in instructions()
    assert any('bola de nieve' in d['body'].lower() for d in docs)
    with db() as conn:
        first = sync_knowledge(conn)
        sync_knowledge(conn)
        assert one(conn, 'SELECT count(*) AS n FROM knowledge')['n'] == first['indexed_fragments'] + 1
    assert any('Saldo · agentes/' in s['source'] for s in ai.retrieve(2, 'bola de nieve deudas'))


def test_readonly_endpoints_auth_arguments_and_user_isolation(client, auth, admin_auth):
    client.cookies.clear()
    assert client.get('/api/v1/advisor/tools').status_code == 401
    manifest = client.get('/api/v1/advisor/tools', headers=auth).json()
    assert manifest['read_only'] and len(manifest['tools']) >= 10
    own = client.post('/api/v1/advisor/goal_snapshot', headers=auth, json={'arguments': {}})
    assert own.status_code == 200 and own.json()['total_count'] == 1
    other = client.post('/api/v1/advisor/goal_snapshot', headers=admin_auth, json={'arguments': {}})
    assert other.json()['total_count'] == 0
    assert client.post('/api/v1/advisor/goal_snapshot', headers=auth, json={'arguments': {'user_id': 1}}).status_code == 422
    assert client.post('/api/v1/advisor/execute_sql', headers=auth, json={'arguments': {}}).status_code == 404
    assert client.post('/api/v1/advisor/savings_plan', headers=admin_auth,
                       json={'arguments': {'goal_id': 1, 'months': 3, 'monthly': '50'}}).status_code == 422


def test_integral_diagnosis_keeps_totals_and_sources(client, auth, admin_auth):
    args = {'start': '2026-11-01', 'end': '2026-11-30', 'as_of': '2026-11-30'}
    result = client.post('/api/v1/advisor/financial_diagnosis', headers=auth, json={'arguments': args})
    assert result.status_code == 200, result.text
    data = result.json()
    assert data['flow']['current']['income'] == '6000.00'
    assert data['spending']['total_expense'] == '1400.00'
    assert data['debt']['total_count'] == 0
    empty = client.post('/api/v1/advisor/financial_diagnosis', headers=admin_auth, json={'arguments': args}).json()
    assert empty['spending']['total_expense'] == '0.00' and empty['goals']['total_count'] == 0


def test_context_packing_never_slices_json_and_admits_omission():
    sources = [{'source_id': 'D1', 'text': 'x' * 2400}, {'source_id': 'M2', 'planned': '100.00'}]
    assert ai.source_context(sources, 200) == [sources[1]]
    original = {'items': [{'id': i, 'title': 'a'*160} for i in range(40)],
                'total_count': 40, 'has_more': False, 'totals': {'amount': '9999.00'}}
    context = ai.tool_context(original)
    assert len(context['items']) == 5 and context['has_more']
    assert context['totals'] == original['totals']
    assert len(original['items']) == 40


def test_short_followup_keeps_goal_tools_and_no_free_sql():
    names = ai.selected_tools('rag', '¿Y si aporto 300? ¿Qué metas de ahorro tengo?')
    assert 'savings_plan' in names and 'goal_snapshot' in names
    assert 'execute_sql' not in names
    for prompt in ('¿Qué debo pagar la próxima semana?', '¿Qué pagos me faltan?'):
        assert 'obligations_snapshot' in ai.selected_tools('rag', prompt)


@pytest.mark.parametrize('service', ['rag', 'budget', 'goals'])
def test_catalog_is_available_to_every_assistant(client, auth, monkeypatch, service):
    monkeypatch.setenv('GROQ_API_KEY', 'stub-not-sent')
    marker = 'Guía educativa sobre priorizar ahorro y deuda.'
    monkeypatch.setattr(ai, 'retrieve', lambda *_: [{'source_id': 'D99', 'text': marker}])
    seen = []
    monkeypatch.setattr(ai, 'completion', lambda payload: seen.append(payload) or reply('Explicación educativa [D99]'))
    result = client.post('/api/v1/ai/'+service, headers=auth, json={'prompt': 'Explica cómo priorizar ahorro y deuda.'})
    assert result.status_code == 200
    assert marker in seen[0]['messages'][0]['content']
    assert result.json()['sources'][0]['source_id'] == 'D99'
