"""Annual inflation stays tied to the requested publication and recorded flow."""
from decimal import Decimal

import httpx
import pytest

from backend import ai
from backend.grounding import unsupported_amounts
from test_external_workflows import completion_pair, assert_two_round_budget


PROMPT = 'Consulta mis ingresos, pagos y ahorro de noviembre de 2026 y la inflación anual de Guatemala de 2025.'


def worldbank(monkeypatch, row):
    calls=[]
    def get(url, **kwargs):
        calls.append((url,kwargs))
        return httpx.Response(200, request=httpx.Request('GET',url), json=[{'page':1},[row]])
    monkeypatch.setattr(ai.httpx,'get',get)
    return calls


@pytest.mark.parametrize('row', [
    {'date':'2024','value':'1.49'},
    {'date':'2025','value':None},
    {'date':'2025','value':'NaN'},
    {'date':'2025','value':'Infinity'},
    {'date':'2025','value':True},
    {'date':'2025','value':'1.49','countryiso3code':'USA'},
    {'date':'2025','value':'1.49','indicator':{'id':'WRONG'}},
    {'date':'2025','value':'1.49','indicator':None},
])
def test_unavailable_or_mismatched_publication_never_becomes_requested_inflation(client,monkeypatch,row):
    calls=worldbank(monkeypatch,row)
    result=ai.inflation(2025)
    assert result['available'] is False and result['year']==2025
    assert 'annual_percent' not in result and result['retrieved_at']
    assert calls[0][1]['params']['date']=='2025'


@pytest.mark.parametrize('value', ['1.48841591086168','-1.48841591086168','0'])
def test_published_annual_value_preserves_precision_deflation_and_zero(client,monkeypatch,value):
    worldbank(monkeypatch,{'date':'2025','value':value,'countryiso3code':'GTM',
                          'indicator':{'id':'FP.CPI.TOTL.ZG'}})
    result=ai.inflation(2025)
    assert result['annual_percent']==value and result['year']==2025
    assert unsupported_amounts(f'{Decimal(value):.2f}%', [result])==[]
    if value.startswith('-'):
        assert unsupported_amounts('1.49%', [result])==['1.49%']


def test_wrong_model_margin_is_rebuilt_from_flow_and_published_annual_rate(client,auth,monkeypatch):
    worldbank(monkeypatch,{'date':'2025','value':'1.48841591086168'})
    candidate=('En noviembre de 2026 ingresaron Q6,000.00 y pagaste Q1,400.00: quedan Q4,600.00. '
               'La inflación anual de Guatemala fue 1,49% en 2025.')
    payloads=completion_pair(monkeypatch,'budget_external_review',
        {'start':'2026-11-01','end':'2026-11-30','inflation_year':2025},candidate)
    response=client.post('/api/v1/ai/budget',headers=auth,json={'prompt':PROMPT})
    assert response.status_code==200,response.text
    text=response.json()['response']
    assert 'Q4,100.00' in text and 'Q500.00' in text and 'Q4,600.00' not in text
    assert '2025' in text and '1.49%' in text and 'Banco Mundial' in text
    assert 'no puedo confirmar esa cifra' not in text
    detail=client.get('/api/v1/history/'+response.json()['id'],headers=auth).json()
    result=next(t['result'] for t in detail['tools'] if t['name']=='budget_external_review')
    assert unsupported_amounts(text,[result])==[]
    assert_two_round_budget(payloads)


def test_current_year_absent_does_not_silently_use_previous_year(client,auth,monkeypatch):
    calls=worldbank(monkeypatch,{'date':'2025','value':'1.48841591086168'})
    payloads=completion_pair(monkeypatch,'budget_external_review',
        {'start':'2026-11-01','end':'2026-11-30','inflation_year':2026},
        'Tu margen registrado es Q999,999.00 y la inflación de 2026 fue 1.49%.')
    response=client.post('/api/v1/ai/budget',headers=auth,json={
        'prompt':'Consulta mis ingresos y pagos de noviembre de 2026 y la inflación anual de Guatemala de 2026.'})
    assert response.status_code==200,response.text
    text=response.json()['response']
    assert 'Q4,100.00' in text and '2026' in text and 'No pude confirmar' in text
    assert '1.49%' not in text and '2025' not in text
    assert len(calls)==1 and calls[0][1]['params']['date']=='2026'
    assert_two_round_budget(payloads)


def test_network_failure_preserves_actual_records_without_inventing_annual_change(client,monkeypatch):
    def fail(*args,**kwargs):
        raise httpx.ConnectError('unavailable')
    monkeypatch.setattr(ai.httpx,'get',fail)
    result=ai.execute_tool('budget_external_review',
        {'start':'2026-11-01','end':'2026-11-30','inflation_year':2025},2)
    assert result['inflation']['available'] is False
    text=ai.unverified_response(PROMPT,[result])
    assert 'Q4,100.00' in text and 'No pude confirmar' in text and '%' not in text
    assert unsupported_amounts(text,[result])==[]
