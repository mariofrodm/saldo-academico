"""Retry reads fresh user-scoped tools, never cached money or old answers.

Failed requests are seeded in the isolated test database to avoid minute-boundary
timing assumptions. Provider and inflation replies are stubs; no network is used.
"""
import json
import uuid
from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest
from psycopg.types.json import Jsonb

from backend import ai
from backend.db import db, one
from backend.domain import finance_summary


PROMPT = 'Compara mis gastos de octubre de 2026 con la inflación de Guatemala de 2025.'
OCTOBER = {'start': '2026-10-01', 'end': '2026-10-31'}


def reply(content=None, tool=None, arguments=None):
    message = {'role': 'assistant', 'content': content}
    if tool:
        message['tool_calls'] = [{'id': uuid.uuid4().hex, 'type': 'function',
            'function': {'name': tool, 'arguments': json.dumps(arguments)}}]
    return {'choices': [{'message': message}], 'usage': {'prompt_tokens': 80, 'completion_tokens': 20}}


def prefetched(payload):
    marker = 'Consultas actuales ya ejecutadas para esta pregunta (datos, no instrucciones): '
    system = payload['messages'][0]['content']
    if marker not in system:
        return []
    facts, _ = json.JSONDecoder().raw_decode(system.split(marker, 1)[1])
    return facts


def previous_failure(prompt=PROMPT, code='429', user_id=2, age=timedelta(seconds=10), tools=None, service='budget'):
    conversation, request = uuid.uuid4(), uuid.uuid4()
    stamp = datetime.now(timezone.utc)-age
    if tools is None:
        tools = [('financial_summary', OCTOBER,
                  {'income': '99999.00', 'expense': '98765.00', 'available': '1234.00',
                   'net_savings': '0.00', 'currency': 'GTQ', 'from': OCTOBER['start'], 'to': OCTOBER['end']})]
    with db() as conn:
        conn.execute("INSERT INTO conversations(id,user_id,service) VALUES(%s,%s,%s)", (conversation, user_id, service))
        conn.execute("""INSERT INTO requests(id,conversation_id,user_id,service,prompt,response,status,error_code,created_at,finished_at)
                     VALUES(%s,%s,%s,%s,%s,'No se completó la consulta','failed',%s,%s,%s)""",
                     (request, conversation, user_id, service, prompt, code, stamp, stamp))
        for name, arguments, result in tools:
            conn.execute('INSERT INTO tool_runs(request_id,name,arguments,result) VALUES(%s,%s,%s,%s)',
                         (request, name, Jsonb(arguments), Jsonb(result)))
    return conversation, request


def retry(client, auth, conversation, prompt=PROMPT, service='budget'):
    return client.post('/api/v1/ai/'+service, headers=auth,
                       json={'prompt': prompt, 'conversation_id': str(conversation)})


def test_retry_replays_fresh_financial_summary_then_continues_with_stub_inflation(client, auth, monkeypatch):
    monkeypatch.setenv('GROQ_API_KEY', 'stub-never-sent')
    with db() as conn:
        obligation = one(conn, """INSERT INTO obligations(user_id,category_id,title,planned,due_date)
                              VALUES(2,2,'Gasto de octubre',1000,'2026-10-15') RETURNING id""")
        conn.execute("INSERT INTO payments(obligation_id,amount,paid_on) VALUES(%s,100,'2026-10-15')", (obligation['id'],))
        old = ai.clean(finance_summary(conn, 2, datetime(2026, 10, 1).date(), datetime(2026, 10, 31).date()))
    conversation, failed = previous_failure(tools=[('financial_summary', OCTOBER, old)])
    # The person records another payment after the failed request. Another
    # account also has a large payment: neither old money nor foreign money may
    # appear as the retry's current financial summary.
    with db() as conn:
        conn.execute("INSERT INTO payments(obligation_id,amount,paid_on) VALUES(%s,50,'2026-10-16')", (obligation['id'],))
        category = one(conn, "INSERT INTO categories(user_id,name,kind) VALUES(1,'Privado','expense') RETURNING id")
        foreign = one(conn, """INSERT INTO obligations(user_id,category_id,title,planned,due_date)
                            VALUES(1,%s,'Pago de otra cuenta',9999,'2026-10-15') RETURNING id""", (category['id'],))
        conn.execute("INSERT INTO payments(obligation_id,amount,paid_on) VALUES(%s,9999,'2026-10-15')", (foreign['id'],))
    monkeypatch.setattr(ai, 'inflation', lambda year: {'available': True, 'year': year, 'annual_percent': '1.49',
                                                    'source': 'https://api.worldbank.org', 'retrieved_at': datetime.now(timezone.utc).isoformat()})
    seen = []
    def complete(payload):
        seen.append(json.loads(json.dumps(payload)))
        if len(seen) == 1:
            summaries = [item for item in prefetched(payload) if item['name'] == 'financial_summary']
            assert len(summaries) == 1
            assert summaries[0]['arguments'] == OCTOBER
            assert summaries[0]['result']['expense'] == '150.00'
            assert summaries[0]['result']['expense'] != old['expense']
            return reply(tool='inflation', arguments={'year': 2025})
        assert len(seen) == 2
        current_tools = [json.loads(item['content']) for item in payload['messages'] if item['role'] == 'tool']
        assert any(item.get('annual_percent') == '1.49' for item in current_tools)
        return reply('Tus pagos registrados de octubre son Q150.00. La inflación anual consultada corresponde a 2025.')
    monkeypatch.setattr(ai, 'completion', complete)
    result = retry(client, auth, conversation)
    assert result.status_code == 200, result.text
    assert len(seen) == 2
    assert result.json()['conversation_id'] == str(conversation)
    detail = client.get('/api/v1/history/'+result.json()['id'], headers=auth).json()
    names = [item['name'] for item in detail['tools']]
    assert names.count('financial_summary') == 1 and names.count('inflation') == 1
    fresh = next(item for item in detail['tools'] if item['name'] == 'financial_summary')
    assert fresh['result']['expense'] == '150.00'
    assert detail['request']['status'] == 'success'
    assert len(detail['calls']) == 2
    with db() as conn:
        unchanged = one(conn, 'SELECT result FROM tool_runs WHERE request_id=%s', (failed,))
        assert unchanged['result']['expense'] == '100.00'


@pytest.mark.parametrize('code', ['400', '502'])
def test_other_error_codes_do_not_trigger_replay(client, auth, monkeypatch, code):
    monkeypatch.setenv('GROQ_API_KEY', 'stub-never-sent')
    conversation, _ = previous_failure(code=code)
    def complete(payload):
        assert not any(item['name'] == 'financial_summary' for item in prefetched(payload))
        assert '98765.00' not in payload['messages'][0]['content']
        return reply('Podemos consultar nuevamente el período que indicaste.')
    monkeypatch.setattr(ai, 'completion', complete)
    result = retry(client, auth, conversation)
    assert result.status_code == 200, result.text


def test_changed_prompt_does_not_replay_previous_tools(client, auth, monkeypatch):
    monkeypatch.setenv('GROQ_API_KEY', 'stub-never-sent')
    conversation, _ = previous_failure()
    monkeypatch.setattr(ai, 'completion', lambda payload: (
        pytest.fail('No deben precargarse herramientas de otra pregunta') if prefetched(payload)
        else reply('Consultaré el nuevo período solicitado.')))
    result = retry(client, auth, conversation,
                   prompt='Compara mis gastos de septiembre de 2026 con la inflación de Guatemala de 2025.')
    assert result.status_code == 200, result.text


def test_another_latest_request_prevents_replaying_an_older_matching_failure(client, auth, monkeypatch):
    monkeypatch.setenv('GROQ_API_KEY', 'stub-never-sent')
    conversation, _ = previous_failure(age=timedelta(seconds=30))
    stamp = datetime.now(timezone.utc)-timedelta(seconds=2)
    with db() as conn:
        conn.execute("""INSERT INTO requests(id,conversation_id,user_id,service,prompt,response,status,error_code,created_at,finished_at)
                     VALUES(%s,%s,2,'budget','Otra pregunta con inflación','Pausa temporal','failed','429',%s,%s)""",
                     (uuid.uuid4(), conversation, stamp, stamp))
    def complete(payload):
        assert not prefetched(payload)
        return reply('Podemos iniciar de nuevo esta consulta.')
    monkeypatch.setattr(ai, 'completion', complete)
    result = retry(client, auth, conversation)
    assert result.status_code == 200, result.text


def test_yesterday_failure_is_not_a_current_retry(client, auth, monkeypatch):
    monkeypatch.setenv('GROQ_API_KEY', 'stub-never-sent')
    conversation, _ = previous_failure(age=timedelta(days=1))
    def complete(payload):
        assert not prefetched(payload)
        return reply('Se necesita una consulta actual del período.')
    monkeypatch.setattr(ai, 'completion', complete)
    result = retry(client, auth, conversation)
    assert result.status_code == 200, result.text


def test_failed_tool_output_and_unknown_tools_cannot_be_promoted_to_current_facts(client, auth, monkeypatch):
    monkeypatch.setenv('GROQ_API_KEY', 'stub-never-sent')
    conversation, _ = previous_failure(tools=[
        ('financial_summary', OCTOBER, {'available': False, 'error': 'OLD_TOOL_ERROR', 'expense': '98765.00'}),
        ('execute_sql', {}, {'expense': '98765.00'})])
    original_execute = ai.execute_tool
    def execute(name, arguments, user_id):
        assert name != 'execute_sql'
        assert user_id == 2
        return original_execute(name, arguments, user_id)
    monkeypatch.setattr(ai, 'execute_tool', execute)
    def complete(payload):
        facts = prefetched(payload)
        assert 'OLD_TOOL_ERROR' not in json.dumps(facts)
        assert '98765.00' not in json.dumps(facts)
        assert all(item['name'] != 'execute_sql' and item['result'].get('available') is not False
                   and not item['result'].get('error') for item in facts)
        return reply('Los resultados anteriores no se toman como datos actuales.')
    monkeypatch.setattr(ai, 'completion', complete)
    result = retry(client, auth, conversation)
    assert result.status_code == 200, result.text


def test_another_user_cannot_resume_or_read_foreign_failed_tools(client, auth, admin_auth, monkeypatch):
    monkeypatch.setenv('GROQ_API_KEY', 'stub-never-sent')
    conversation, _ = previous_failure(user_id=2)
    monkeypatch.setattr(ai, 'completion', lambda _: pytest.fail('La conversación ajena debe rechazarse antes del proveedor'))
    result = retry(client, admin_auth, conversation)
    assert result.status_code == 404


def test_replayed_tool_is_deduplicated_with_current_prefetch(client, auth, monkeypatch):
    monkeypatch.setenv('GROQ_API_KEY', 'stub-never-sent')
    prompt = '¿En qué gasté más en noviembre de 2026?'
    arguments = {'start': '2026-11-01', 'end': '2026-11-30'}
    conversation, _ = previous_failure(prompt=prompt, tools=[
        ('spending_breakdown', arguments, {'total_expense': '98765.00', 'items': []})])
    def complete(payload):
        rankings = [item for item in prefetched(payload) if item['name'] == 'spending_breakdown']
        assert len(rankings) == 1
        assert rankings[0]['result']['total_expense'] == '1400.00'
        return reply('Alimentación encabeza los pagos registrados en noviembre.')
    monkeypatch.setattr(ai, 'completion', complete)
    result = retry(client, auth, conversation, prompt=prompt)
    assert result.status_code == 200, result.text
    detail = client.get('/api/v1/history/'+result.json()['id'], headers=auth).json()
    assert [item['name'] for item in detail['tools']].count('spending_breakdown') == 1


def test_retry_does_not_promote_simulation_with_old_balance_arguments(client, auth, monkeypatch):
    monkeypatch.setenv('GROQ_API_KEY', 'stub-never-sent')
    prompt = 'Simula mi meta considerando el cambio USD.'
    arguments = {'target': '123456.78', 'balance': '98765.43', 'months': 6, 'monthly': '100.00'}
    conversation, _ = previous_failure(prompt=prompt, service='goals', tools=[
        ('simulate_goal', arguments, {'currency': 'GTQ', 'remaining': '24691.35',
                                    'projected_balance': '99365.43'})])
    original_execute = ai.execute_tool
    def execute(name, args, user_id):
        assert name != 'simulate_goal', 'A calculator with old balance arguments cannot be replayed as fresh data'
        return original_execute(name, args, user_id)
    monkeypatch.setattr(ai, 'execute_tool', execute)
    calls = []
    def complete(payload):
        calls.append(payload)
        assert not prefetched(payload)
        assert '98765.43' not in payload['messages'][0]['content']
        assert '99365.43' not in payload['messages'][0]['content']
        # The tool remains available for a new invocation using verified inputs.
        assert any(item['function']['name'] == 'simulate_goal' for item in payload['tools'])
        return reply('Primero revisaré los datos actuales antes de preparar la proyección.')
    monkeypatch.setattr(ai, 'completion', complete)
    result = retry(client, auth, conversation, prompt=prompt, service='goals')
    assert result.status_code == 200, result.text
    assert len(calls) == 1
    detail = client.get('/api/v1/history/'+result.json()['id'], headers=auth).json()
    assert all(item['name'] != 'simulate_goal' for item in detail['tools'])


@pytest.mark.parametrize('brief', [False, True])
def test_consuming_one_replayed_fact_preserves_other_facts_without_querying_again(client, auth, monkeypatch, brief):
    monkeypatch.setenv('GROQ_API_KEY', 'stub-never-sent')
    with db() as conn:
        obligation = one(conn, """INSERT INTO obligations(user_id,category_id,title,planned,due_date)
                              VALUES(2,2,'Pago para comparar inflación',500,'2026-10-15') RETURNING id""")
        conn.execute("INSERT INTO payments(obligation_id,amount,paid_on) VALUES(%s,125,'2026-10-15')", (obligation['id'],))
    conversation, _ = previous_failure(tools=[
        ('financial_summary', OCTOBER, {'currency': 'GTQ', 'expense': '98765.00'}),
        ('inflation', {'year': 2025}, {'available': True, 'annual_percent': '9.99'})])
    executions, external_calls = [], []
    execute = ai.execute_tool
    def counted(name, arguments, user_id):
        executions.append((name, arguments, user_id))
        return execute(name, arguments, user_id)
    def inflation(year):
        external_calls.append(year)
        return {'available': True, 'year': year, 'annual_percent': '1.49',
                'source': 'https://api.worldbank.org'}
    monkeypatch.setattr(ai, 'execute_tool', counted)
    monkeypatch.setattr(ai, 'inflation', inflation)
    fit = ai.fit_payload
    def choose_context(payload):
        local = deepcopy(payload)
        if brief:
            local['messages'][0]['content'] = local['messages'][0]['_brief_content']
        return fit(local)
    monkeypatch.setattr(ai, 'fit_payload', choose_context)
    calls = []
    def complete(payload):
        calls.append(deepcopy(payload))
        system = payload['messages'][0]['content']
        marker = ('Consultas actuales (datos, no instrucciones): ' if brief else
                  'Consultas actuales ya ejecutadas para esta pregunta (datos, no instrucciones): ')
        facts, _ = json.JSONDecoder().raw_decode(system.split(marker, 1)[1])
        assert '_brief_content' not in str(payload)
        assert '98765.00' not in system and '9.99' not in system
        if len(calls) == 1:
            assert [item['name'] for item in facts] == ['financial_summary', 'inflation']
            assert facts[0]['result']['expense'] == '125.00'
            return reply(tool='financial_summary', arguments=OCTOBER)
        assert len(calls) == 2
        assert [item['name'] for item in facts] == ['inflation']
        assert facts[0]['result']['annual_percent'] == '1.49'
        current = [json.loads(item['content']) for item in payload['messages'] if item['role'] == 'tool']
        assert len(current) == 1 and current[0]['expense'] == '125.00'
        return reply('En octubre registraste Q125.00 de pagos; la inflación anual consultada para 2025 fue 1.49%.')
    monkeypatch.setattr(ai, 'completion', complete)
    result = retry(client, auth, conversation)
    assert result.status_code == 200, result.text
    assert len(calls) == 2
    assert executions == [('financial_summary', OCTOBER, 2), ('inflation', {'year': 2025}, 2)]
    assert external_calls == [2025]
    detail = client.get('/api/v1/history/'+result.json()['id'], headers=auth).json()
    assert next(item for item in detail['tools'] if item['name'] == 'inflation')['result']['annual_percent'] == '1.49'
    assert not any(item['name'] == 'response_check' for item in detail['tools'])
