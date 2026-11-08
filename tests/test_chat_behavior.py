"""API regressions for readable answers, recoverable limits and verified memory.

Provider replies are stubs. Tests exercise assembly/provenance, not claims that
a language model understands every phrasing. Existing fixtures isolate PostgreSQL.
"""
import json
import uuid
from datetime import date, datetime, timezone

import pytest
from psycopg.types.json import Jsonb

from backend import ai, advisor, demo
from backend.db import db, one, many


OCTOBER = {'start': '2026-10-01', 'end': '2026-10-31'}


class FrozenDateTime(datetime):
    @classmethod
    def now(cls, tz=None):
        stamp = datetime(2026, 11, 8, 16, 25, 30, tzinfo=timezone.utc)
        return stamp if tz is None else stamp.astimezone(tz)


def provider_reply(text=None, name=None, arguments=None):
    message = {'role': 'assistant', 'content': text}
    if name:
        message['tool_calls'] = [{'id': uuid.uuid4().hex, 'type': 'function',
            'function': {'name': name, 'arguments': json.dumps(arguments)}}]
    return {'choices': [{'message': message}],
            'usage': {'prompt_tokens': 70, 'completion_tokens': 30}}


def seed_prior_turn(prompt, response, user_id=2):
    conversation, request = uuid.uuid4(), uuid.uuid4()
    with db() as conn:
        conn.execute("INSERT INTO conversations(id,user_id,service) VALUES(%s,%s,'rag')", (conversation, user_id))
        conn.execute("""INSERT INTO requests(id,conversation_id,user_id,service,prompt,response,status,finished_at)
                     VALUES(%s,%s,%s,'rag',%s,%s,'success',now())""",
                     (request, conversation, user_id, prompt, response))
        conn.execute('INSERT INTO tool_runs(request_id,name,arguments,result) VALUES(%s,%s,%s,%s)',
                     (request, 'spending_breakdown', Jsonb(OCTOBER), Jsonb({
                         'source_id': 'SGASTOS', 'period': OCTOBER,
                         'items': [{'category_id': 2, 'category': 'Alimentación', 'amount': '1100.00'},
                                   {'category_id': 3, 'category': 'Universidad', 'amount': '900.00'}]})))
    return conversation


def test_shared_limit_returns_recoverable_reference_and_retry_preserves_conversation(client, auth, monkeypatch):
    monkeypatch.setenv('GROQ_API_KEY', 'stub-never-sent')
    monkeypatch.setattr(ai, 'datetime', FrozenDateTime)
    monkeypatch.setattr(advisor, 'today', lambda: date(2026, 11, 8))
    monkeypatch.setattr(ai, 'completion', lambda _: pytest.fail('La reserva bloqueada no debe llamar a Groq'))
    period = 'minute:2026-11-08T16:25'
    with db() as conn:
        conn.execute('INSERT INTO budgets(period,used) VALUES(%s,7000)', (period,))
    prompt = '¿En qué gasté más en octubre de 2026?'
    failed = client.post('/api/v1/ai/rag', headers=auth, json={'prompt': prompt})
    assert failed.status_code == 429, failed.text
    body = failed.json()
    assert isinstance(body['detail'], str) and body['detail']
    uuid.UUID(body['conversation_id']); uuid.UUID(body['request_id'])
    assert 1 <= body['retry_after'] <= 61
    assert int(failed.headers['Retry-After']) == body['retry_after']
    with db() as conn:
        request = one(conn, 'SELECT * FROM requests WHERE id=%s', (uuid.UUID(body['request_id']),))
        assert request['prompt'] == prompt and request['status'] == 'failed'
        assert str(request['conversation_id']) == body['conversation_id']
        assert request['error_code'] == '429'
        assert one(conn, 'SELECT count(*) AS n FROM provider_calls')['n'] == 0
        assert one(conn, 'SELECT tokens_used,tokens_reserved FROM users WHERE id=2') == {'tokens_used': 0, 'tokens_reserved': 0}
        conn.execute('UPDATE budgets SET used=0 WHERE period=%s', (period,))
    monkeypatch.setattr(ai, 'completion', lambda _: provider_reply('Revisé los pagos registrados de octubre.'))
    retried = client.post('/api/v1/ai/rag', headers=auth,
                          json={'prompt': prompt, 'conversation_id': body['conversation_id']})
    assert retried.status_code == 200, retried.text
    assert retried.json()['conversation_id'] == body['conversation_id']
    assert retried.json()['id'] != body['request_id']
    with db() as conn:
        requests = many(conn, 'SELECT status,prompt FROM requests WHERE conversation_id=%s',
                        (uuid.UUID(body['conversation_id']),))
        assert len(requests) == 2
        assert {item['status'] for item in requests} == {'failed', 'success'}
        assert all(item['prompt'] == prompt for item in requests)


def test_readable_chat_keeps_human_sources_and_full_tool_history(client, auth, monkeypatch):
    monkeypatch.setenv('GROQ_API_KEY', 'stub-never-sent')
    monkeypatch.setattr(advisor, 'today', lambda: date(2026, 11, 8))
    def complete(payload):
        assert 'tools' not in payload
        return provider_reply('**Revisé tus pagos registrados de octubre.** [SGASTOS]\n\nFuente: SGASTOS (spending_breakdown)')
    monkeypatch.setattr(ai, 'completion', complete)
    result = client.post('/api/v1/ai/rag', headers=auth, json={'prompt': '¿En qué gasté más en octubre de 2026?'})
    assert result.status_code == 200, result.text
    body = result.json()
    assert 'Revisé tus pagos registrados de octubre.' in body['response']
    for technical in ('**', '[SGASTOS]', 'spending_breakdown', 'Fuente:'):
        assert technical not in body['response']
    source = next(item for item in body['sources'] if item.get('source_id') == 'SGASTOS')
    assert source['title'] == 'Pagos por categoría'
    history = client.get('/api/v1/history/'+body['id'], headers=auth).json()
    assert history['request']['response'] == body['response']
    assert any(item.get('source_id') == 'SGASTOS' for item in history['request']['sources'])
    calls = [item for item in history['tools'] if item['name'] == 'spending_breakdown']
    assert calls
    assert calls[-1]['arguments'] == OCTOBER
    assert {key: calls[-1]['result']['period'][key] for key in ('start', 'end')} == OCTOBER


def test_long_prior_turn_and_verified_october_context_survive_without_cross_user_access(client, auth, admin_auth, monkeypatch):
    monkeypatch.setenv('GROQ_API_KEY', 'stub-never-sent')
    monkeypatch.setattr(advisor, 'today', lambda: date(2026, 11, 8))
    prompt = ('Quiero revisar mis pagos registrados con cuidado. '*9)+'El período que elegí es octubre de 2026.'
    answer = ('Te explico el alcance de los registros disponibles. '*10)+'El intervalo consultado es octubre de 2026.'
    assert len(prompt) > 350 and len(answer) > 350
    conversation = seed_prior_turn(prompt, answer)
    seen = []
    def complete(payload):
        seen.append(json.loads(json.dumps(payload)))
        return provider_reply('Puedo explicarte los pagos registrados de Alimentación en octubre.')
    monkeypatch.setattr(ai, 'completion', complete)
    result = client.post('/api/v1/ai/rag', headers=auth,
                         json={'prompt': 'En ese mismo mes, ¿puedes explicarme mis gastos de alimentación?',
                               'conversation_id': str(conversation)})
    assert result.status_code == 200, result.text
    messages = seen[0]['messages']
    assert any(item['role'] == 'user' and item['content'] == prompt for item in messages)
    assert any(item['role'] == 'assistant' and item['content'] == answer for item in messages)
    system = messages[0]['content']
    assert '2026-10-01' in system and '2026-10-31' in system
    assert 'context_same' in system
    before = len(seen)
    denied = client.post('/api/v1/ai/rag', headers=admin_auth,
                         json={'prompt': 'Revisa ese mismo mes.', 'conversation_id': str(conversation)})
    assert denied.status_code == 404
    assert len(seen) == before


def test_failed_prior_turn_cannot_supply_temporal_facts(client, auth, monkeypatch):
    monkeypatch.setenv('GROQ_API_KEY', 'stub-never-sent')
    monkeypatch.setattr(advisor, 'today', lambda: date(2026, 11, 8))
    conversation = seed_prior_turn('Revisa octubre de 2026.', 'No se completó la consulta.')
    with db() as conn:
        conn.execute("UPDATE requests SET status='failed',error_code='429' WHERE conversation_id=%s", (conversation,))
    seen = []
    monkeypatch.setattr(ai, 'completion', lambda payload: seen.append(payload) or provider_reply('Necesito confirmar a qué mes te refieres.'))
    result = client.post('/api/v1/ai/rag', headers=auth,
                         json={'prompt': '¿Y en ese mismo mes?', 'conversation_id': str(conversation)})
    assert result.status_code == 200, result.text
    assert 'missing_previous_period' in seen[0]['messages'][0]['content']
    assert not any(item['role'] == 'assistant' and item['content'] == 'No se completó la consulta.'
                   for item in seen[0]['messages'])


def test_duplicate_prefetched_tool_reuses_facts_without_doubling_context(client, auth, monkeypatch):
    monkeypatch.setenv('GROQ_API_KEY', 'stub-never-sent')
    monkeypatch.setattr(advisor, 'today', lambda: date(2026, 11, 8))
    execute = ai.execute_tool
    executed, seen = [], []
    def counted(name, args, user_id):
        executed.append((name, args, user_id))
        return execute(name, args, user_id)
    monkeypatch.setattr(ai, 'execute_tool', counted)
    def complete(payload):
        seen.append(json.loads(json.dumps(payload)))
        if len(seen) == 1:
            return provider_reply(name='spending_breakdown', arguments=OCTOBER)
        return provider_reply('Revisé tus pagos de octubre.')
    monkeypatch.setattr(ai, 'completion', complete)
    result = client.post('/api/v1/ai/rag', headers=auth,
                         json={'prompt': 'Muéstrame los gastos de octubre de 2026 y sus categorías.'})
    assert result.status_code == 200, result.text
    assert executed == [('spending_breakdown', OCTOBER, 2)]
    assert len(seen) == 2
    assert '"source_id": "SGASTOS"' in seen[0]['messages'][0]['content']
    assert '"source_id": "SGASTOS"' not in seen[1]['messages'][0]['content']
    facts = json.loads(next(m['content'] for m in seen[1]['messages'] if m['role'] == 'tool'))
    assert facts['source_id'] == 'SGASTOS' and facts['period']['start'] == OCTOBER['start']


def test_simple_verified_comparison_uses_no_provider_and_keeps_scope_and_history(client, auth, admin_auth, monkeypatch):
    monkeypatch.setenv('GROQ_API_KEY', 'stub-never-sent')
    monkeypatch.setattr(advisor, 'today', lambda: date(2026, 11, 8))
    monkeypatch.setattr(ai, 'completion', lambda _: pytest.fail('Una comparación simple confirmada no necesita Groq'))
    with db() as conn:
        for category, amount in ((2, '1000.00'), (3, '250.00')):
            obligation = one(conn, '''INSERT INTO obligations(user_id,category_id,title,planned,due_date)
                                    VALUES(2,%s,'Pago de octubre',%s,'2026-10-15') RETURNING id''', (category, amount))
            conn.execute("INSERT INTO payments(obligation_id,amount,paid_on) VALUES(%s,%s,'2026-10-15')",
                         (obligation['id'], amount))
        category = one(conn, "INSERT INTO categories(user_id,name,kind) VALUES(1,'Alimentación','expense') RETURNING id")
        other = one(conn, '''INSERT INTO obligations(user_id,category_id,title,planned,due_date)
                            VALUES(1,%s,'Pago privado',9999,'2026-10-15') RETURNING id''', (category['id'],))
        conn.execute("INSERT INTO payments(obligation_id,amount,paid_on) VALUES(%s,9999,'2026-10-15')", (other['id'],))
    result = client.post('/api/v1/ai/rag', headers=auth,
                         json={'prompt': 'En octubre de 2026, ¿pagué más en Alimentación o Universidad?'})
    assert result.status_code == 200, result.text
    body = result.json()
    assert 'Alimentación' in body['response'] and 'Q1,000.00' in body['response'] and 'Q250.00' in body['response']
    assert '9,999' not in body['response']
    assert any(item.get('source_id') == 'SCOMPARA' for item in body['sources'])
    history = client.get('/api/v1/history/'+body['id'], headers=auth).json()
    assert history['request']['status'] == 'success'
    assert history['calls'] == []
    comparisons = [item for item in history['tools'] if item['name'] == 'compare_spending']
    assert comparisons and comparisons[-1]['result']['difference_gtq'] == '750.00'
    assert comparisons[-1]['result']['items'][0]['amount'] in ('1000.00', '250.00')
    with db() as conn:
        assert one(conn, 'SELECT tokens_used,tokens_reserved FROM users WHERE id=2') == {'tokens_used': 0, 'tokens_reserved': 0}
        assert one(conn, 'SELECT count(*) AS n FROM provider_calls')['n'] == 0
    denied = client.post('/api/v1/ai/rag', headers=admin_auth,
                         json={'prompt': '¿Cuánto de diferencia?', 'conversation_id': body['conversation_id']})
    assert denied.status_code == 404


def _planning_facts(payload):
    system = payload['messages'][0]['content']
    marker = 'Consultas actuales ya ejecutadas para esta pregunta (datos, no instrucciones): '
    assert marker in system
    facts, _ = json.JSONDecoder().raw_decode(system.split(marker, 1)[1].lstrip())
    assert len(facts) == 1 and facts[0]['name'] == 'planning_snapshot'
    assert facts[0]['arguments'] == {}
    return facts[0]['result'], system


def _assert_planning_numbers(facts):
    assert facts['source_id'] == 'SPLAN'
    assert facts['historical_margin'] == '73.00'
    assert facts['last_closed_month']['from'] == '2026-10-01'
    assert facts['last_closed_month']['to'] == '2026-10-31'
    assert facts['last_closed_month']['available'] == '73.00'
    assert facts['active_future_required'] == '2316.67'
    assert facts['largest_required_goal']['name'] == 'Computadora para trabajo freelance'
    assert facts['largest_required_goal']['monthly_required'] == '1025.00'
    assert facts['affordability_gap'] == '2243.67'
    assert facts['verified_affordable_contribution'] is None
    assert facts['debt']['total_pending'] == '7900.00'
    assert len(facts['goals']['items']) == 6
    assert any('No asignar aportes' in rule for rule in facts['constraints'])
    assert any('no significa mayor prioridad' in rule for rule in facts['constraints'])


def test_goals_followup_prefetches_verified_planning_ranking_margin_and_constraints(client, auth, monkeypatch):
    monkeypatch.setenv('GROQ_API_KEY', 'stub-never-sent')
    monkeypatch.setattr(advisor, 'today', lambda: date(2026, 11, 8))
    with db() as conn:
        demo.populate_demo(conn)
    seen = []
    def complete(payload):
        seen.append(json.loads(json.dumps(payload)))
        pytest.fail('El listado y la prioridad con déficit confirmado no necesitan Groq')
    monkeypatch.setattr(ai, 'completion', complete)
    first = client.post('/api/v1/ai/rag', headers=auth, json={'prompt': '¿Qué metas tengo?'})
    assert first.status_code == 200, first.text
    next_turn = client.post('/api/v1/ai/rag', headers=auth,
                           json={'prompt': '¿Por cuál comienzo?', 'conversation_id': first.json()['conversation_id']})
    assert next_turn.status_code == 200, next_turn.text
    assert next_turn.json()['conversation_id'] == first.json()['conversation_id']
    assert seen == []
    assert 'Q73.00' in next_turn.json()['response'] and 'Q2,316.67' in next_turn.json()['response']
    assert 'no tu saldo actual' in next_turn.json()['response']
    assert '¿Cuál de tus objetivos es esencial' in next_turn.json()['response']
    history = client.get('/api/v1/history/'+next_turn.json()['id'], headers=auth).json()
    planning_runs = [run for run in history['tools'] if run['name'] == 'planning_snapshot']
    assert len(planning_runs) == 1 and planning_runs[0]['arguments'] == {}
    _assert_planning_numbers(planning_runs[0]['result'])
    assert history['calls'] == []
    assert any(source.get('source_id') == 'SPLAN' for source in next_turn.json()['sources'])


def test_unspecified_monthly_contribution_keeps_facts_and_does_not_turn_advice_into_goal_selection(client, auth, monkeypatch):
    monkeypatch.setenv('GROQ_API_KEY', 'stub-never-sent')
    monkeypatch.setattr(advisor, 'today', lambda: date(2026, 11, 8))
    with db() as conn:
        demo.populate_demo(conn)
    seen = []
    def complete(payload):
        seen.append(json.loads(json.dumps(payload)))
        pytest.fail('Listados, déficit y aclaración del aporte no requieren modelo')
    monkeypatch.setattr(ai, 'completion', complete)
    conversation = None
    for prompt in ('¿Qué metas tengo?', '¿Por cuál comienzo?', '¿Y si aporto 100 al mes?'):
        body = {'prompt': prompt}
        if conversation:
            body['conversation_id'] = conversation
        result = client.post('/api/v1/ai/rag', headers=auth, json=body)
        assert result.status_code == 200, result.text
        conversation = result.json()['conversation_id']
    assert seen == []
    assert '¿A cuál' in result.json()['response']
    history = client.get('/api/v1/history/'+result.json()['id'], headers=auth).json()
    assert any(run['name'] == 'planning_snapshot' for run in history['tools'])
    _assert_planning_numbers(next(run['result'] for run in history['tools'] if run['name'] == 'planning_snapshot'))
    assert not any(run['name'] in ('savings_plan', 'simulate_goal', 'budget_scenario') for run in history['tools'])
    assert history['calls'] == []


def test_planning_api_manifest_and_queries_preserve_authenticated_scope_without_provider(client, auth, admin_auth, monkeypatch):
    monkeypatch.setattr(advisor, 'today', lambda: date(2026, 11, 8))
    monkeypatch.setattr(ai, 'completion', lambda _: pytest.fail('Una lectura directa no debe llamar a Groq'))
    with db() as conn:
        demo.populate_demo(conn)
    client.cookies.clear()
    assert client.get('/api/v1/advisor/tools').status_code == 401
    assert client.post('/api/v1/advisor/planning_snapshot', json={'arguments': {}}).status_code == 401
    manifest = client.get('/api/v1/advisor/tools', headers=auth).json()
    tool = next(item for item in manifest['tools'] if item['function']['name'] == 'planning_snapshot')
    assert tool['function']['parameters']['required'] == []
    assert not tool['function']['parameters']['additionalProperties']
    own = client.post('/api/v1/advisor/planning_snapshot', headers=auth, json={'arguments': {}})
    assert own.status_code == 200, own.text
    _assert_planning_numbers(own.json())
    other = client.post('/api/v1/advisor/planning_snapshot', headers=admin_auth, json={'arguments': {}})
    assert other.status_code == 200
    assert other.json()['goals']['items'] == [] and other.json()['debt']['count'] == 0
    assert other.json()['historical_margin'] == '0.00' and other.json()['largest_required_goal'] is None
    assert client.post('/api/v1/advisor/planning_snapshot', headers=auth,
                       json={'arguments': {'user_id': 1}}).status_code == 422
    with db() as conn:
        assert one(conn, 'SELECT count(*) AS n FROM provider_calls')['n'] == 0
        assert one(conn, 'SELECT count(*) AS n FROM requests')['n'] == 0
        assert one(conn, 'SELECT tokens_used,tokens_reserved FROM users WHERE id=2') == {'tokens_used': 0, 'tokens_reserved': 0}


def test_informal_diagnosis_with_full_records_fits_context_and_keeps_closed_month(client, auth, monkeypatch):
    monkeypatch.setenv('GROQ_API_KEY', 'stub-never-sent')
    monkeypatch.setattr(advisor, 'today', lambda: date(2026, 11, 8))
    with db() as conn:
        demo.populate_demo(conn)
    seen = []
    def complete(payload):
        seen.append(payload)
        assert payload['reasoning_effort'] == 'medium'
        assert payload['include_reasoning'] is False
        assert 'last_closed_month' in payload['messages'][0]['content']
        assert '2026-10-31' in payload['messages'][0]['content']
        assert '73.00' in payload['messages'][0]['content']
        assert '2026-11-08' in payload['messages'][0]['content']
        return provider_reply('Revisemos los gastos y las fechas de tus próximos cobros.')
    monkeypatch.setattr(ai, 'completion', complete)
    result = client.post('/api/v1/ai/rag', headers=auth, json={
        'prompt': 'Cobro por quincena y siento que no me alcanza. ¿Qué revisamos primero?'})
    assert result.status_code == 200, result.text
    assert len(seen) == 1
    detail = client.get('/api/v1/history/'+result.json()['id'], headers=auth).json()
    assert detail['tools'][0]['name'] == 'financial_diagnosis'
    assert len(detail['tools'][0]['result']['goals']['items']) == 3


def test_unverified_generated_money_is_replaced_and_preserved_in_authenticated_history(client, auth, monkeypatch):
    monkeypatch.setenv('GROQ_API_KEY', 'stub-never-sent')
    monkeypatch.setattr(advisor, 'today', lambda: date(2026, 11, 8))
    with db() as conn: demo.populate_demo(conn)
    bad='Esta quincena tienes Q3,000.00 de ingreso y Q838.50 de gasto: te quedan Q2,161.50.'
    monkeypatch.setattr(ai, 'completion', lambda _: provider_reply(bad))
    result=client.post('/api/v1/ai/rag',headers=auth,json={
        'prompt':'Cobro por quincena y siento que no me alcanza. ¿Qué revisamos primero?'})
    assert result.status_code == 200, result.text
    answer=result.json()['response']
    assert all(amount in answer for amount in ('Q7,250.00','Q7,177.00','Q73.00'))
    assert '¿Cuándo recibes tus próximos cobros' in answer
    assert all(amount not in answer for amount in ('Q3,000.00','Q838.50','Q2,161.50'))
    history=client.get('/api/v1/history/'+result.json()['id'],headers=auth).json()
    check=next(step['result'] for step in history['tools'] if step['name']=='response_check')
    assert check['candidate_response']==bad
    assert check['unsupported_amounts']==['Q3,000.00','Q838.50','Q2,161.50']
    assert check['replaced'] is True and check['available'] is False
    assert len(history['calls'])==1
    assert history['calls'][0]['input_tokens']+history['calls'][0]['output_tokens']==100


def test_verified_generated_amounts_are_not_replaced(client, auth, monkeypatch):
    monkeypatch.setenv('GROQ_API_KEY', 'stub-never-sent')
    monkeypatch.setattr(advisor, 'today', lambda: date(2026, 11, 8))
    with db() as conn: demo.populate_demo(conn)
    valid='En octubre ingresaste Q7,250.00 y pagaste Q7,177.00; el margen registrado fue Q73.00.'
    monkeypatch.setattr(ai, 'completion', lambda _: provider_reply(valid))
    result=client.post('/api/v1/ai/rag',headers=auth,json={
        'prompt':'Cobro por quincena y siento que no me alcanza. ¿Qué revisamos primero?'})
    assert result.status_code==200, result.text
    assert result.json()['response']==valid
    history=client.get('/api/v1/history/'+result.json()['id'],headers=auth).json()
    assert not any(step['name']=='response_check' for step in history['tools'])


def test_planning_reply_remembers_the_verified_closed_month_it_presented(client, auth, monkeypatch):
    monkeypatch.setenv('GROQ_API_KEY','stub-never-sent')
    monkeypatch.setattr(advisor,'today',lambda:date(2026,11,8))
    monkeypatch.setattr(ai,'completion',lambda _:pytest.fail('Ambas respuestas tienen hechos completos sin Groq'))
    with db() as conn: demo.populate_demo(conn)
    first=client.post('/api/v1/ai/rag',headers=auth,json={'prompt':'¿Cómo puedo cumplir mis metas dado mi contexto actual?'})
    assert first.status_code==200,first.text
    assert 'octubre de 2026' in first.json()['response']
    follow=client.post('/api/v1/ai/rag',headers=auth,json={'prompt':'En ese mismo mes, ¿pagué más en alimentación o universidad?',
        'conversation_id':first.json()['conversation_id']})
    assert follow.status_code==200,follow.text
    assert 'octubre de 2026' in follow.json()['response']
    assert 'Q1,000.00' in follow.json()['response'] and 'Q900.00' in follow.json()['response']


@pytest.mark.parametrize('followup',[False,True])
def test_explicit_savings_proposal_is_calculated_before_one_provider_call(client, auth, monkeypatch, followup):
    monkeypatch.setenv('GROQ_API_KEY','stub-never-sent')
    monkeypatch.setattr(advisor,'today',lambda:date(2026,11,8))
    with db() as conn: demo.populate_demo(conn)
    seen=[]
    def complete(payload):
        seen.append(payload)
        assert 'tools' not in payload
        marker='Consultas actuales ya ejecutadas para esta pregunta (datos, no instrucciones): '
        facts,_=json.JSONDecoder().raw_decode(payload['messages'][0]['content'].split(marker,1)[1])
        assert len(facts)==1 and facts[0]['name']=='savings_plan'
        assert facts[0]['arguments']=={'goal_id':1,'months':6,'monthly':'100.00'}
        assert facts[0]['result']['projected_balance']=='1150.00'
        assert facts[0]['result']['gap_at_end']=='3850.00'
        return provider_reply('Con Q100.00 al mes durante 6 meses, el fondo llegaría a Q1,150.00; faltarían Q3,850.00 para la meta.')
    monkeypatch.setattr(ai,'completion',complete)
    conversation=None
    prompts=(['¿Qué metas tengo?','¿Por cuál comienzo?','¿Y si aporto 100 al mes?','Al fondo de emergencia']
             if followup else ['Si aporto Q100 al mes al fondo de emergencia'])
    for prompt in prompts:
        body={'prompt':prompt}
        if conversation: body['conversation_id']=conversation
        result=client.post('/api/v1/ai/rag',headers=auth,json=body)
        assert result.status_code==200,result.text
        conversation=result.json()['conversation_id']
    assert len(seen)==1
    history=client.get('/api/v1/history/'+result.json()['id'],headers=auth).json()
    assert [step['name'] for step in history['tools']]==['savings_plan']
    assert len(history['calls'])==1
    assert 'Q1,150.00' in result.json()['response']
