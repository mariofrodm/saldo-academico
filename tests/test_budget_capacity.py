from datetime import date,datetime,timezone

import pytest

from backend import ai,advisor,demo
from backend.db import db,one

HEALTH='¿Qué tan sano ves mi presupuesto de octubre?'
MARGIN='¿Cuánto margen me dejó octubre de 2026 para ahorrar o pagar deuda?'


def setup_demo(monkeypatch):
    monkeypatch.setenv('GROQ_API_KEY','stub-never-sent')
    monkeypatch.setattr(advisor,'today',lambda:date(2026,11,8))
    with db() as conn: demo.populate_demo(conn)


def answer(text='En octubre registraste Q7,250.00 de ingresos y Q7,177.00 de pagos. El margen fue Q73.00.',finish=None):
    return {'choices':[{'message':{'role':'assistant','content':text},'finish_reason':finish}],
            'usage':{'prompt_tokens':80,'completion_tokens':20}}


@pytest.mark.parametrize('service',['budget','rag','goals'])
def test_budget_health_uses_one_response_with_current_period_and_no_redundant_schemas(client,auth,monkeypatch,service):
    setup_demo(monkeypatch)
    calls=[]
    def completion(payload):
        calls.append(payload)
        assert 'tools' not in payload
        assert '_brief_content' not in str(payload)
        assert ai.estimate_payload(payload)<=6500
        assert '2026-10-01' in payload['messages'][0]['content']
        assert '2026-10-31' in payload['messages'][0]['content']
        assert '73.00' in payload['messages'][0]['content']
        return answer()
    monkeypatch.setattr(ai,'completion',completion)
    r=client.post('/api/v1/ai/'+service,headers=auth,json={'prompt':HEALTH})
    assert r.status_code==200,r.text
    assert len(calls)==1 and 'Q73.00' in r.json()['response']
    history=client.get('/api/v1/history/'+r.json()['id'],headers=auth).json()
    assert [t['name'] for t in history['tools']]==['financial_overview']
    assert len(history['calls'])==1


@pytest.mark.parametrize('service',['budget','rag','goals'])
def test_simple_margin_answers_even_during_shared_minute_pause_without_provider(client,auth,monkeypatch,service):
    setup_demo(monkeypatch)
    now=datetime.now(timezone.utc)
    with db() as conn:
        conn.execute('INSERT INTO budgets(period,used) VALUES(%s,7000)',('minute:'+now.strftime('%Y-%m-%dT%H:%M'),))
    monkeypatch.setattr(ai,'completion',lambda _:pytest.fail('El margen ya está calculado; no necesita proveedor'))
    r=client.post('/api/v1/ai/'+service,headers=auth,json={'prompt':MARGIN})
    assert r.status_code==200,r.text
    assert 'Q73.00' in r.json()['response'] and 'octubre de 2026' in r.json()['response']
    h=client.get('/api/v1/history/'+r.json()['id'],headers=auth).json()
    assert h['calls']==[]
    assert [t['name'] for t in h['tools']]==['financial_overview']


def test_oversized_optional_guidance_is_compacted_before_one_provider_call(client,auth,monkeypatch):
    setup_demo(monkeypatch)
    # Optional elaboration may grow; the versioned core remains complete.
    core=ai.agent_instructions().partition('\n## Profundización')[0]
    monkeypatch.setattr(ai,'agent_instructions',lambda:core+'\n## Profundización\n'+'Guía opcional muy extensa. '*6000)
    calls=[]
    def completion(payload):
        calls.append(payload)
        assert ai.estimate_payload(payload)<=6500
        system=payload['messages'][0]['content']
        assert 'Solo consultas de lectura' in system and '2026-10-31' in system
        assert 'Guía opcional muy extensa.' not in system
        assert payload['messages'][-1]['content']=='Ayúdame a ordenar mis finanzas en octubre de 2026.'
        return answer()
    monkeypatch.setattr(ai,'completion',completion)
    r=client.post('/api/v1/ai/rag',headers=auth,json={'prompt':'Ayúdame a ordenar mis finanzas en octubre de 2026.'})
    assert r.status_code==200,r.text
    assert len(calls)==1


def test_residual_context_capacity_returns_verified_summary_without_spending(client,auth,monkeypatch):
    setup_demo(monkeypatch)
    monkeypatch.setattr(ai,'fit_payload',lambda _:None)
    monkeypatch.setattr(ai,'completion',lambda _:pytest.fail('No debe enviar un payload que no cabe'))
    r=client.post('/api/v1/ai/budget',headers=auth,json={'prompt':HEALTH})
    assert r.status_code==200,r.text
    assert 'Q73.00' in r.json()['response'] and 'resumen' in r.json()['response']
    assert 'contexto' not in r.json()['response'].lower()
    h=client.get('/api/v1/history/'+r.json()['id'],headers=auth).json()
    assert h['calls']==[]
    mode=next(t for t in h['tools'] if t['name']=='response_mode')
    assert mode['result']['reason']=='context_capacity'


def test_output_limit_uses_verified_summary_and_preserves_real_usage(client,auth,monkeypatch):
    setup_demo(monkeypatch)
    monkeypatch.setattr(ai,'completion',lambda _:answer('Texto incompleto que no debe presentarse',finish='length'))
    r=client.post('/api/v1/ai/budget',headers=auth,json={'prompt':HEALTH})
    assert r.status_code==200,r.text
    assert 'Q73.00' in r.json()['response'] and 'Texto incompleto' not in r.json()['response']
    h=client.get('/api/v1/history/'+r.json()['id'],headers=auth).json()
    assert len(h['calls'])==1 and h['calls'][0]['input_tokens']+h['calls'][0]['output_tokens']==100
    assert next(t for t in h['tools'] if t['name']=='response_mode')['result']['reason']=='response_limit'
    with db() as conn: assert one(conn,'SELECT tokens_used,tokens_reserved FROM users WHERE id=2')=={'tokens_used':100,'tokens_reserved':0}
