"""Executed public-source workflows survive a final inference quota pause."""
import json

import httpx
import pytest

from backend import ai
from test_external_workflows import wire_tokens
from test_goal_usd_regression import PROMPT as GOAL_PROMPT, RATE, prepare
from test_inflation_regression import PROMPT as BUDGET_PROMPT, worldbank


@pytest.mark.parametrize('service', ['goals','budget'])
def test_compound_facts_survive_second_inference_rate_limit_without_third_attempt(client,auth,monkeypatch,service):
    if service=='goals':
        args=prepare(client,monkeypatch)
        workflow='goal_external_scenarios'
        prompt=GOAL_PROMPT
    else:
        worldbank(monkeypatch,{'date':'2025','value':'1.48841591086168'})
        args={'start':'2026-11-01','end':'2026-11-30','inflation_year':2025}
        workflow='budget_external_review'
        prompt=BUDGET_PROMPT
    payloads=[]
    def completion(payload):
        payloads.append(payload)
        if len(payloads)==1:
            return {'choices':[{'message':{'role':'assistant','content':None,'tool_calls':[
                {'id':'compound','type':'function','function':{'name':workflow,'arguments':json.dumps(args)}}]},'finish_reason':'stop'}],
                'usage':{'prompt_tokens':wire_tokens(payload),'completion_tokens':120}}
        assert len(payloads)==2, 'No third provider attempt'
        req=httpx.Request('POST','https://api.groq.com/openai/v1/chat/completions')
        response=httpx.Response(429,headers={'retry-after':'60'},request=req)
        raise httpx.HTTPStatusError('pause',request=req,response=response)
    monkeypatch.setattr(ai,'completion',completion)
    monkeypatch.setenv('GROQ_API_KEY','mock-only')
    response=client.post('/api/v1/ai/'+service,headers=auth,json={'prompt':prompt})
    assert response.status_code==200,response.text
    assert len(payloads)==2
    text=response.json()['response']
    if service=='goals':
        assert all(value in text for value in ('Q4,000.00','Q5,500.00','US$523.67','US$720.04','10/11/2026'))
    else:
        assert all(value in text for value in ('Q4,100.00','Q500.00','1.49%','2025','Banco Mundial'))
    detail=client.get('/api/v1/history/'+response.json()['id'],headers=auth).json()
    assert len(detail['calls'])==2
    assert detail['calls'][1]['input_tokens']==0 and detail['calls'][1]['output_tokens']==0
    mode=next(t['result'] for t in detail['tools'] if t['name']=='response_mode')
    assert mode['reason']=='usage_limit' and mode['provider_answer_used'] is False


def test_api_outage_still_explains_current_flow_if_model_only_mentions_outage(client,auth,monkeypatch):
    from test_external_workflows import completion_pair
    worldbank(monkeypatch,{'date':'2025','value':None})
    payloads=completion_pair(monkeypatch,'budget_external_review',
        {'start':'2026-11-01','end':'2026-11-30','inflation_year':2025},'No tengo acceso al Banco Mundial.')
    response=client.post('/api/v1/ai/budget',headers=auth,json={'prompt':BUDGET_PROMPT})
    assert response.status_code==200,response.text
    assert 'Q4,100.00' in response.json()['response'] and '2025' in response.json()['response']
    assert 'No pude confirmar' in response.json()['response'] and len(payloads)==2
