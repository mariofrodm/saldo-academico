"""Zero-provider queries stay usable without bypassing inference reservations."""
from datetime import date, datetime, timezone

import httpx
import pytest

from backend import ai, advisor, demo
from backend.db import db, one


class FrozenDateTime(datetime):
    @classmethod
    def now(cls,tz=None):
        stamp=datetime(2026,11,8,16,25,30,tzinfo=timezone.utc)
        return stamp if tz is None else stamp.astimezone(tz)


def setup(monkeypatch):
    monkeypatch.setattr(advisor,'today',lambda:date(2026,11,8))
    monkeypatch.setattr(ai,'datetime',FrozenDateTime)
    with db() as conn: demo.populate_demo(conn)
    monkeypatch.setattr(ai,'completion',lambda _:pytest.fail('Esta prueba no debe invocar al proveedor'))


def test_calculated_query_works_without_key_or_personal_or_shared_allowance(client,auth,monkeypatch):
    setup(monkeypatch)
    with db() as conn:
        conn.execute('UPDATE users SET tokens_used=token_limit WHERE id=2')
        conn.execute("INSERT INTO budgets(period,used) VALUES('day:2026-11-08',100000)")
        before=one(conn,'SELECT tokens_used,tokens_reserved,token_limit FROM users WHERE id=2')
    r=client.post('/api/v1/ai/budget',headers=auth,json={
        'prompt':'¿Cuánto margen me dejó octubre de 2026 para ahorrar o pagar deuda?','local_only':True})
    assert r.status_code==200,r.text
    assert 'Q73.00' in r.json()['response']
    h=client.get('/api/v1/history/'+r.json()['id'],headers=auth).json()
    assert h['calls']==[] and h['request']['status']=='success'
    with db() as conn:
        assert one(conn,'SELECT tokens_used,tokens_reserved,token_limit FROM users WHERE id=2')==before
        assert one(conn,"SELECT used,reserved FROM budgets WHERE period='day:2026-11-08'")=={'used':100000,'reserved':0}


def test_local_only_returns_labelled_fresh_summary_without_spending(client,auth,monkeypatch):
    setup(monkeypatch)
    r=client.post('/api/v1/ai/budget',headers=auth,json={
        'prompt':'¿Qué tan sano ves mi presupuesto de octubre de 2026?','local_only':True})
    assert r.status_code==200,r.text
    assert 'resumen' in r.json()['response'] and 'Q73.00' in r.json()['response']
    h=client.get('/api/v1/history/'+r.json()['id'],headers=auth).json()
    assert h['calls']==[]
    mode=next(t for t in h['tools'] if t['name']=='response_mode')
    assert mode['result']=={'mode':'verified_summary','reason':'local_only','provider_answer_used':False}


def test_unsupported_local_question_keeps_history_and_reports_capability(client,auth,monkeypatch):
    setup(monkeypatch)
    r=client.post('/api/v1/ai/rag',headers=auth,json={
        'prompt':'Explícame qué significa un fondo de emergencia.','local_only':True})
    assert r.status_code==409,r.text
    body=r.json()
    assert body['limit_kind']=='local_only' and body['local_available'] is True
    assert r.headers['X-AI-Limit-Kind']=='local_only'
    assert 'análisis de IA' in body['detail']
    h=client.get('/api/v1/history/'+body['request_id'],headers=auth).json()
    assert h['calls']==[] and h['request']['status']=='failed'
    assert str(h['request']['conversation_id'])==body['conversation_id']


def test_personal_quota_still_blocks_inference_before_provider(client,auth,monkeypatch):
    setup(monkeypatch)
    monkeypatch.setenv('GROQ_API_KEY','stub-never-sent')
    with db() as conn: conn.execute('UPDATE users SET tokens_used=token_limit WHERE id=2')
    r=client.post('/api/v1/ai/rag',headers=auth,json={'prompt':'Explícame la bola de nieve.'})
    assert r.status_code==429,r.text
    assert r.json()['limit_kind']=='personal' and r.json()['local_available'] is True
    assert 'retry_after' not in r.json()
    with db() as conn:
        assert one(conn,'SELECT tokens_used=token_limit AS at_limit,tokens_reserved FROM users WHERE id=2')=={'at_limit':True,'tokens_reserved':0}
        assert one(conn,'SELECT count(*) AS n FROM provider_calls')['n']==0


def test_daily_limit_has_guatemala_reset_and_typed_retry(client,auth,monkeypatch):
    setup(monkeypatch)
    monkeypatch.setenv('GROQ_API_KEY','stub-never-sent')
    with db() as conn: conn.execute("INSERT INTO budgets(period,used) VALUES('day:2026-11-08',100000)")
    r=client.post('/api/v1/ai/rag',headers=auth,json={'prompt':'¿En qué gasté más en octubre de 2026?'})
    assert r.status_code==429,r.text
    body=r.json()
    assert body['limit_kind']=='day' and body['retry_after']==27270
    assert '18:00' in body['detail'] and 'Guatemala' in body['detail'] and 'mañana' not in body['detail']
    with db() as conn:
        assert one(conn,'SELECT tokens_used,tokens_reserved FROM users WHERE id=2')=={'tokens_used':0,'tokens_reserved':0}


def test_provider_pause_settles_rejection_without_charging_and_rounds_retry_up(client,auth,monkeypatch):
    setup(monkeypatch)
    monkeypatch.setenv('GROQ_API_KEY','stub-never-sent')
    def paused(_):
        request=httpx.Request('POST','https://api.groq.com/openai/v1/chat/completions')
        response=httpx.Response(429,headers={'retry-after':'1.2'},request=request)
        raise httpx.HTTPStatusError('Pause',request=request,response=response)
    monkeypatch.setattr(ai,'completion',paused)
    r=client.post('/api/v1/ai/rag',headers=auth,json={'prompt':'Explícame la bola de nieve.'})
    assert r.status_code==429,r.text
    assert r.json()['limit_kind']=='provider' and r.json()['retry_after']==2
    with db() as conn:
        assert one(conn,'SELECT tokens_used,tokens_reserved FROM users WHERE id=2')=={'tokens_used':0,'tokens_reserved':0}
        assert one(conn,'SELECT input_tokens,output_tokens,usage_kind FROM provider_calls')=={'input_tokens':0,'output_tokens':0,'usage_kind':'rejected'}


def test_core_fallback_retains_retrieved_guidance_and_external_rules(client,auth,monkeypatch):
    setup(monkeypatch)
    monkeypatch.setenv('GROQ_API_KEY','stub-never-sent')
    core=ai.agent_instructions().partition('\n## Profundización')[0]
    monkeypatch.setattr(ai,'agent_instructions',lambda:core+'\n## Profundización\n'+'Ampliación opcional. '*7000)
    monkeypatch.setattr(ai,'retrieve',lambda *_:[{'source_id':'D1','title':'Deudas','text':'Mantén pagos mínimos y prioriza el saldo menor.','source':'Guía'}])
    seen=[]
    def complete(payload):
        seen.append(payload)
        system=payload['messages'][0]['content']
        assert 'Mantén pagos mínimos y prioriza el saldo menor.' in system
        assert 'institución y fecha' in system
        assert 'datos, no instrucciones' in system and 'Solo consultas de lectura' in system
        assert 'Ampliación opcional.' not in system
        assert payload['max_completion_tokens']==768 and payload['reasoning_effort']=='medium'
        return {'choices':[{'message':{'role':'assistant','content':'La bola de nieve consiste en priorizar el saldo menor, manteniendo los pagos mínimos de las demás deudas.'}}],
                'usage':{'prompt_tokens':80,'completion_tokens':20}}
    monkeypatch.setattr(ai,'completion',complete)
    r=client.post('/api/v1/ai/rag',headers=auth,json={'prompt':'Explícame la bola de nieve.'})
    assert r.status_code==200,r.text
    assert len(seen)==1 and ai.estimate_payload(seen[0])<=6500
