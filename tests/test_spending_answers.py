from copy import deepcopy
from datetime import date
from backend.direct_answers import spending_answer


def facts():
    period = {'start': '2026-11-01', 'end': '2026-11-30'}
    return [('spending_breakdown', period, {'source_id': 'SGASTOS', 'currency': 'GTQ', 'period': period,
            'total_expense': '5948.00', 'items': [{'category': 'Vivienda', 'amount': '1500.00', 'expense_percent': '25.22'},
                                                {'category': 'Alimentación', 'amount': '1000.00', 'expense_percent': '16.81'}]})]


def test_real_current_month_question_has_exact_facts_and_no_model():
    supplied = facts()
    before = deepcopy(supplied)
    answer = spending_answer('¿En qué gasté más en noviembre de 2026?', supplied, date(2026, 11, 10))
    assert 'Vivienda' in answer and 'Q1,500.00' in answer and '25.22%' in answer
    assert 'aún no termina' in answer
    assert supplied == before


def test_closed_month_and_arbitrary_period_are_labelled():
    answer = spending_answer('¿En qué gasté más?', facts(), date(2026, 12, 1))
    assert 'en noviembre de 2026' in answer and 'aún no termina' not in answer
    supplied = facts()
    supplied[0][1].update(start='2026-11-02', end='2026-11-08')
    assert 'del 2/11/2026 al 8/11/2026' in spending_answer('¿En qué gasté más?', supplied, date(2026, 11, 10))


def test_compound_advice_requests_stay_with_model():
    for prompt in ['¿En qué gasté más y qué puedo hacer?', '¿En qué gasté más? ¿Qué recomiendo?',
                   '¿En qué gasté más en noviembre de 2026 y por qué?', '¿Cuánto gasté en total?']:
        assert spending_answer(prompt, facts(), date(2026, 11, 10)) is None


def test_empty_results_and_ties_do_not_invent_winners():
    supplied = facts()
    supplied[0][2]['items'][1]['amount'] = '1500.00'
    assert 'entre las categorías' in spending_answer('¿En qué gasté más?', supplied, date(2026, 11, 10))
    supplied[0][2].update(items=[], total_expense='0.00')
    assert 'No hay pagos' in spending_answer('¿En qué gasté más?', supplied, date(2026, 11, 10))


def test_bad_source_unsorted_and_future_only_are_deferred():
    for mutate in [lambda r: r.update(source_id='OTHER'), lambda r: r.update(currency='USD'),
                   lambda r: r['items'].reverse(), lambda r: r.update(total_expense='100.00')]:
        supplied = facts(); mutate(supplied[0][2])
        assert spending_answer('¿En qué gasté más?', supplied, date(2026, 11, 10)) is None
    assert spending_answer('¿En qué gasté más?', facts(), date(2026, 10, 10)) is None


def test_explicit_and_relative_period_must_agree_with_fresh_facts():
    for prompt in ['¿En qué gasté más en octubre de 2026?', '¿En qué gasté más en noviembre de 2025?',
                   '¿En qué gasté más el mes pasado?']:
        assert spending_answer(prompt, facts(), date(2026, 11, 10)) is None
    assert spending_answer('¿En qué gasté más el mes pasado?', facts(), date(2026, 12, 10)) is not None
    assert spending_answer('¿En qué gasté más este mes?', facts(), date(2026, 12, 10)) is None
    assert spending_answer('¿En qué gasté más ese mes?', facts(), date(2026, 12, 10)) is not None
