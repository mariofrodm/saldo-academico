import json
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone,timedelta
from decimal import Decimal
import httpx
import pytest
from backend.db import db,one,many
from backend import ai


def test_authentication_and_csrf(client):
    assert client.get('/api/v1/me').status_code==401
    assert client.post('/api/v1/auth/login',json={'email':'demo@example.test','password':'wrong'}).status_code==401
    r=client.post('/api/v1/auth/login',json={'email':'demo@example.test','password':'test-only-password-1234'})
    assert r.status_code==200 and 'HttpOnly' in r.headers['set-cookie']
    assert client.get('/api/v1/me').json()['role']=='user'
    assert client.post('/api/v1/categories',json={'name':'Test','kind':'expense'}).status_code==403
    assert client.post('/api/v1/categories',headers={'X-CSRF-Token':r.json()['csrf']},json={'name':'Test','kind':'expense'}).status_code==200
    assert client.post('/api/v1/auth/logout',headers={'X-CSRF-Token':r.json()['csrf']}).status_code==200
    assert client.get('/api/v1/me').status_code==401


def test_isolation_and_admin(client,auth):
    assert client.get('/api/v1/admin/users',headers=auth).status_code==403
    assert client.get('/api/v1/history?user_id=1',headers=auth).status_code==403
    assert client.get('/api/v1/reports/summary?user_id=1',headers=auth).status_code==403
    assert client.post('/api/v1/goals/999/movements',headers=auth,json={'amount':'10.00','moved_on':'2026-11-02'}).status_code==404


def test_money_and_partial_payments(client,auth):
    r=client.get('/api/v1/board?month=2026-11-01',headers=auth)
    assert r.status_code==200
    data=r.json(); assert data['summary']['income']=='6000.00'
    assert data['summary']['available']=='4100.00'
    row=next(r for r in data['items'] if r['title']=='Universidad noviembre')
    assert row['remaining']=='500.00'
    assert client.post(f'/api/v1/obligations/{row["id"]}/payments',headers=auth,json={'amount':'300.00','paid_on':'2026-11-07'}).status_code==200
    assert client.post(f'/api/v1/obligations/{row["id"]}/payments',headers=auth,json={'amount':'201.00','paid_on':'2026-11-08'}).status_code==409
    assert client.delete(f'/api/v1/obligations/{row["id"]}',headers=auth).status_code==409
    assert client.get('/api/v1/board?month=2026-11-01',headers=auth).json()['summary']['expense']=='1700.00'


def test_rollover_is_not_duplicated(client,auth):
    first=client.get('/api/v1/board?month=2026-12-01',headers=auth).json()['items']
    second=client.get('/api/v1/board?month=2027-01-01',headers=auth).json()['items']
    assert len(first)==len(second)==1
    assert first[0]['id']==second[0]['id'] and first[0]['rollover']
    assert second[0]['remaining']=='500.00'


def test_recurring_idempotent_snapshot(client,auth):
    r=client.post('/api/v1/recurring',headers=auth,json={'category_id':2,'title':'Suscripción','amount':'20.00','start_month':'2026-11-02'})
    assert r.status_code==200
    for _ in range(2): assert client.get('/api/v1/board?month=2026-11-01',headers=auth).status_code==200
    assert client.put('/api/v1/recurring/'+str(r.json()['id']),headers=auth,json={'category_id':2,'title':'Suscripción','amount':'30.00','start_month':'2026-11-01'}).status_code==200
    with db() as conn:
        rows=many(conn,'SELECT * FROM obligations WHERE recurring_id=%s',(r.json()['id'],))
        assert len(rows)==1 and rows[0]['planned']==Decimal('20.00')
    client.get('/api/v1/board?month=2026-12-01',headers=auth)
    with db() as conn: assert one(conn,"SELECT planned FROM obligations WHERE recurring_id=%s AND due_date='2026-12-01'",(r.json()['id'],))['planned']==Decimal('30.00')


def test_savings_no_overdraft(client,auth):
    goal=client.get('/api/v1/goals',headers=auth).json()[0]
    assert goal['balance']=='500.00'
    assert client.post(f'/api/v1/goals/{goal["id"]}/movements',headers=auth,json={'amount':'-501.00','moved_on':'2026-11-08'}).status_code==409
    assert client.post(f'/api/v1/goals/{goal["id"]}/movements',headers=auth,json={'amount':'-100.00','moved_on':'2026-11-08'}).status_code==200
    assert client.get('/api/v1/board?month=2026-11-01',headers=auth).json()['summary']['available']=='4200.00'


def test_admin_management_and_disable(client,admin_auth):
    r=client.post('/api/v1/admin/users',headers=admin_auth,json={'email':'nuevo@example.test','name':'Nuevo','password':'a-test-password-1234','token_limit':5000})
    assert r.status_code==200
    assert client.put('/api/v1/admin/users/'+str(r.json()['id']),headers=admin_auth,json={'name':'Nuevo','active':False,'token_limit':0}).status_code==200
    assert client.post('/api/v1/auth/login',json={'email':'nuevo@example.test','password':'a-test-password-1234'}).status_code==401
    assert client.put('/api/v1/admin/users/1',headers=admin_auth,json={'name':'Admin','active':False,'token_limit':20000}).status_code==409
    assert client.put('/api/v1/admin/services/rag',headers=admin_auth,json={'enabled':False,'model':'openai/gpt-oss-20b','max_output':512,'max_rounds':4}).status_code==200


def test_no_provider_does_not_fake_response(client,auth):
    assert client.post('/api/v1/ai/rag',headers=auth,json={'prompt':'Presupuesto y ahorro'}).status_code==503
    with db() as conn: assert one(conn,'SELECT count(*) AS n FROM provider_calls')['n']==0


def fake_reply(content='Respuesta [D1]',calls=None):
    return {'choices':[{'message':{'role':'assistant','content':content,'tool_calls':calls or []}}],
            'usage':{'prompt_tokens':70,'completion_tokens':30}}


def tc(name,args):
    return {'id':uuid.uuid4().hex,'type':'function','function':{'name':name,'arguments':json.dumps(args)}}


def test_rag_sources_memory_and_usage(client,auth,monkeypatch):
    monkeypatch.setenv('GROQ_API_KEY','test-stub-never-sent')
    payloads=[]
    def fake(payload): payloads.append(payload); return fake_reply()
    monkeypatch.setattr(ai,'completion',fake)
    first=client.post('/api/v1/ai/rag',headers=auth,json={'prompt':'Presupuesto ahorro'})
    assert first.status_code==200
    assert first.json()['sources'][0]['source_id'].startswith('D')
    second=client.post('/api/v1/ai/rag',headers=auth,json={'prompt':'¿Puedes explicarlo otra vez?','conversation_id':first.json()['conversation_id']})
    assert second.status_code==200
    assert any(m['role']=='assistant' and 'Respuesta' in m['content'] for m in payloads[1]['messages'])
    with db() as conn:
        row=one(conn,'SELECT tokens_used,tokens_reserved FROM users WHERE id=2')
        assert row=={'tokens_used':200,'tokens_reserved':0}
        assert one(conn,'SELECT count(*) AS n FROM provider_calls')['n']==2


def test_rag_insufficient_context_instruction(client,auth,monkeypatch):
    monkeypatch.setenv('GROQ_API_KEY','test')
    seen=[]
    monkeypatch.setattr(ai,'completion',lambda payload: seen.append(payload) or fake_reply('Información insuficiente.'))
    r=client.post('/api/v1/ai/rag',headers=auth,json={'prompt':'astronauta plutonio'})
    assert r.status_code==200 and r.json()['sources']==[]
    assert 'Si falta un dato imprescindible, pregunta solo ese' in seen[0]['messages'][0]['content']


def test_budget_multistep_tools_and_every_call(client,auth,monkeypatch):
    monkeypatch.setenv('GROQ_API_KEY','test')
    replies=iter([fake_reply(None,[tc('financial_summary',{'start':'2026-11-01','end':'2026-11-30'})]),
                  fake_reply(None,[tc('inflation',{'year':2025})]),fake_reply('Comparación con fuente Banco Mundial.')])
    monkeypatch.setattr(ai,'completion',lambda payload: next(replies))
    monkeypatch.setattr(ai,'inflation',lambda year:{'source':'https://api.worldbank.org','year':year,'annual_percent':'3.00','available':True})
    r=client.post('/api/v1/ai/budget',headers=auth,json={'prompt':'Compara mis gastos con inflación 2025'})
    assert r.status_code==200,r.text
    detail=client.get('/api/v1/history/'+r.json()['id'],headers=auth).json()
    assert [t['name'] for t in detail['tools']]==['financial_summary','inflation']
    assert len(detail['calls'])==3
    summary=client.get('/api/v1/reports/summary',headers=auth).json()['items'][0]
    assert summary['requests']==1 and summary['provider_calls']==3 and summary['total_tokens']==300


def test_goals_agent_simulates_two_scenarios(client,auth,monkeypatch):
    monkeypatch.setenv('GROQ_API_KEY','test')
    replies=iter([fake_reply(None,[tc('goal_snapshot',{}),tc('exchange_rate',{})]),
                  fake_reply(None,[tc('simulate_goal',{'target':'5000','balance':'500','months':6,'monthly':'750'}),
                                   tc('simulate_goal',{'target':'5000','balance':'500','months':9,'monthly':'500'})]),
                  fake_reply('Escenarios educativos, referencia Banguat.')])
    monkeypatch.setattr(ai,'completion',lambda payload:next(replies))
    monkeypatch.setattr(ai,'exchange_rate',lambda:{'source':'https://www.banguat.gob.gt','date':'02/11/2026','reference_gtq_per_usd':'7.65'})
    r=client.post('/api/v1/ai/goals',headers=auth,json={'prompt':'Consulta mis metas, cambio y dos escenarios'})
    assert r.status_code==200,r.text
    detail=client.get('/api/v1/history/'+r.json()['id'],headers=auth).json()
    assert len(detail['tools'])==4 and len(detail['calls'])==3
    assert detail['tools'][-1]['result']['reaches_goal'] is True


def test_token_limit_blocks_inference_without_provider(client,auth,monkeypatch):
    monkeypatch.setenv('GROQ_API_KEY','test')
    with db() as conn: conn.execute('UPDATE users SET token_limit=0 WHERE id=2')
    monkeypatch.setattr(ai,'completion',lambda _:pytest.fail('No se debe llamar al proveedor'))
    # Calculated cash-flow summaries remain usable; explanatory generation
    # must still respect the personal allowance before contacting the provider.
    assert client.post('/api/v1/ai/rag',headers=auth,json={'prompt':'Explícame la bola de nieve.'}).status_code==429


def test_concurrent_reservation_only_one_succeeds(client):
    with db() as conn: conn.execute('UPDATE users SET token_limit=100 WHERE id=2')
    def take():
        try: ai.reserve(2,70); return True
        except Exception as e:
            assert e.status_code==429; return False
    with ThreadPoolExecutor(max_workers=2) as pool: result=list(pool.map(lambda _:take(),range(2)))
    assert sum(result)==1
    with db() as conn: assert one(conn,'SELECT tokens_reserved FROM users WHERE id=2')['tokens_reserved']==70


def test_shared_budget_rolls_back_personal_reservation(client):
    with db() as conn:
        conn.execute('INSERT INTO budgets(period,used) VALUES(%s,100000)',('day:'+datetime.now(timezone.utc).strftime('%Y-%m-%d'),))
    with pytest.raises(Exception) as exc: ai.reserve(2,100)
    assert exc.value.status_code==429
    with db() as conn: assert one(conn,'SELECT tokens_reserved FROM users WHERE id=2')['tokens_reserved']==0


@pytest.mark.parametrize('kind',['timeout','429','missing_usage'])
def test_failure_usage_reconciled_and_recorded(client,auth,monkeypatch,kind):
    monkeypatch.setenv('GROQ_API_KEY','test')
    def fake(payload):
        if kind=='timeout': raise httpx.ReadTimeout('test')
        if kind=='429':
            response=httpx.Response(429,request=httpx.Request('POST','https://api.groq.com'))
            raise httpx.HTTPStatusError('test',request=response.request,response=response)
        return {'choices':[{'message':{'role':'assistant','content':'Respuesta'}}]}
    monkeypatch.setattr(ai,'completion',fake)
    r=client.post('/api/v1/ai/rag',headers=auth,json={'prompt':'Presupuesto ahorro'})
    assert r.status_code==(502 if kind=='timeout' else 200)
    if kind=='429':
        # The provider still rejects the call; the app can nevertheless give a
        # clearly labelled summary of facts it already read without inference.
        detail=client.get('/api/v1/history/'+r.json()['id'],headers=auth).json()
        assert 'resumen' in r.json()['response']
        assert detail['calls'][0]['usage_kind']=='rejected'
        assert next(t for t in detail['tools'] if t['name']=='response_mode')['result']['reason']=='usage_limit'
    with db() as conn:
        u=one(conn,'SELECT tokens_used,tokens_reserved FROM users WHERE id=2')
        assert u['tokens_reserved']==0
        assert (u['tokens_used']==0) if kind=='429' else (u['tokens_used']>0)
        assert one(conn,'SELECT count(*) AS n FROM provider_calls')['n']==1


def test_tool_allowlist_and_cross_user_conversation(client,auth,admin_auth,monkeypatch):
    monkeypatch.setenv('GROQ_API_KEY','test')
    monkeypatch.setattr(ai,'completion',lambda _:fake_reply(None,[tc('execute_sql',{'sql':'DELETE FROM users'})]))
    r=client.post('/api/v1/ai/goals',headers=auth,json={'prompt':'Prueba de herramientas'})
    assert r.status_code==502
    with db() as conn: cid=one(conn,'SELECT id FROM conversations WHERE user_id=2')['id']
    assert client.post('/api/v1/ai/goals',headers=admin_auth,json={'prompt':'Otra consulta','conversation_id':str(cid)}).status_code==404


def seed_report():
    with db() as conn:
        cid=uuid.uuid4(); conn.execute("INSERT INTO conversations(id,user_id,service) VALUES(%s,2,'rag')",(cid,))
        for stamp,tokens in [('2026-11-01T05:59:59+00:00',10),('2026-11-01T06:00:00+00:00',20),('2026-11-01T10:00:00+00:00',30)]:
            rid=uuid.uuid4()
            conn.execute("INSERT INTO requests(id,conversation_id,user_id,service,prompt,status,created_at,finished_at) VALUES(%s,%s,2,'rag','Ficticio','success',%s,%s)",(rid,cid,stamp,stamp))
            conn.execute("INSERT INTO provider_calls(request_id,model,input_tokens,output_tokens,usage_kind) VALUES(%s,'test',%s,0,'provider')",(rid,tokens))


def test_report_pagination_dates_and_frozen_cutoff(client,auth):
    seed_report()
    r=client.get('/api/v1/reports/usage?page_size=1&date_from=2026-11-01&date_to=2026-11-01',headers=auth).json()
    assert len(r['items'])==1 and r['items'][0]['total_tokens']==20
    second=client.get('/api/v1/reports/usage',headers=auth,params={'page_size':1,'date_from':'2026-11-01','date_to':'2026-11-01','as_of':r['as_of'],'after':r['next_cursor']}).json()
    assert second['items'][0]['total_tokens']==30 and second['next_cursor'] is None
    totals=client.get('/api/v1/reports/summary?date_from=2026-11-01&date_to=2026-11-01',headers=auth).json()['items'][0]
    assert totals['requests']==2 and totals['total_tokens']==50
    assert client.get('/api/v1/reports/usage?as_of=2026-11-01T08:00:00',headers=auth).status_code==422
    assert client.get('/api/v1/reports/usage?after=invalid',headers=auth).status_code==422


def test_basic_readonly_and_scope(client):
    seed_report()
    credentials=('bi@example.test','test-only-password-1234')
    assert client.get('/api/v1/reports/summary',auth=credentials).status_code==200
    assert client.get('/api/v1/categories',auth=credentials).status_code==401
    with db() as conn: conn.execute("UPDATE users SET bi_scope=2 WHERE role='bi'")
    assert client.get('/api/v1/reports/summary?user_id=1',auth=credentials).status_code==403
    assert client.get('/api/v1/reports/summary',auth=('bi@example.test','wrong')).status_code==401


def test_health_and_openapi(client):
    assert client.get('/api/health').json()['database']=='ok'
    schema=client.get('/openapi.json').json()
    assert '/api/v1/ai/{service}' in schema['paths']
    assert '/api/v1/reports/usage' in schema['paths']


def test_decimal_goal_rounding():
    result=ai.simulate_goal('100','0',3,'33.33')
    assert result['required_monthly']=='33.34' and not result['reaches_goal']


def test_retrieval_natural_question_finds_partial_payment(client):
    sources=ai.retrieve(2,'Explica cómo se registra un pago parcial de Universidad. Usa las fuentes recuperadas.')
    assert any(s['source_id'].startswith('D') for s in sources)
    assert any(s.get('title')=='Universidad noviembre' for s in sources)


def test_report_cutoff_excludes_requests_that_finish_later(client,auth):
    seed_report()
    with db() as conn:
        conn.execute("UPDATE requests SET finished_at='2026-11-02T00:00:00Z' WHERE created_at='2026-11-01T10:00:00Z'")
    result=client.get('/api/v1/reports/summary?as_of=2026-11-01T12:00:00%2B00:00',headers=auth).json()
    assert result['items'][0]['total_tokens']==30


def test_interrupted_reservation_recovered_exactly_once(client):
    from backend.recover import recover_stale
    cid,rid=uuid.uuid4(),uuid.uuid4()
    with db() as conn:
        conn.execute("INSERT INTO conversations(id,user_id,service) VALUES(%s,2,'rag')",(cid,))
        conn.execute("INSERT INTO requests(id,conversation_id,user_id,service,prompt) VALUES(%s,%s,2,'rag','Ficticio')",(rid,cid))
    ai.reserve(2,70,rid,'test')
    with db() as conn: conn.execute("UPDATE requests SET pending_started=now()-interval '16 minutes' WHERE id=%s",(rid,))
    assert recover_stale()==1
    assert recover_stale()==0
    with db() as conn:
        row=one(conn,'SELECT tokens_used,tokens_reserved FROM users WHERE id=2')
        assert row=={'tokens_used':70,'tokens_reserved':0}
        assert one(conn,'SELECT usage_kind FROM provider_calls WHERE request_id=%s',(rid,))['usage_kind']=='reserved_unknown'


def test_agent_step_limit_is_failure_with_all_usage(client,auth,monkeypatch):
    monkeypatch.setenv('GROQ_API_KEY','test')
    with db() as conn: conn.execute("UPDATE services SET max_rounds=2 WHERE id='goals'")
    monkeypatch.setattr(ai,'completion',lambda _:fake_reply(None,[tc('goal_snapshot',{})]))
    r=client.post('/api/v1/ai/goals',headers=auth,json={'prompt':'Consulta mis metas'})
    assert r.status_code==422
    with db() as conn:
        assert one(conn,'SELECT status FROM requests')['status']=='failed'
        assert one(conn,'SELECT tokens_used FROM users WHERE id=2')['tokens_used']==200
