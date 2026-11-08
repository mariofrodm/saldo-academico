from copy import deepcopy

import pytest

from backend.semantic_guard import FLOW_REMINDER, guard_recorded_flow


FLOW = {'source_id': 'SBUDGET_EXTERNAL', 'flow': {
    'income': '6000.00', 'expense': '1400.00', 'net_savings': '500.00', 'available': '4100.00'}}


@pytest.mark.parametrize('claim', [
    'Este valor refleja la capacidad real de gasto después de cubrir todas tus obligaciones y reservar ahorro.',
    'Ya pagaste todas tus obligaciones.',
    'Tienes todas tus obligaciones cubiertas.',
    'Todas tus deudas ya están pagadas.',
    'Es dinero libre para gastar.',
])
def test_positive_unsupported_claim_is_replaced_without_losing_numbers_or_source(claim):
    start = ('Registraste Q6,000.00 de ingresos, Q1,400.00 de pagos y Q500.00 de ahorro neto: '
             'el margen fue Q4,100.00. El Banco Mundial informa 1,49 % anual para 2025.\n\n')
    facts = deepcopy(FLOW)
    corrected, removed = guard_recorded_flow(start+claim, [facts])
    assert corrected == start+FLOW_REMINDER
    assert removed == [claim]
    assert facts == FLOW


@pytest.mark.parametrize('sentence', [
    'Ese margen no refleja capacidad real de gasto.',
    'No podemos afirmar que ya pagaste todas tus obligaciones.',
    'Nunca afirmes que tienes todas tus obligaciones cubiertas.',
    'Evita decir que todas tus deudas están pagadas.',
    'Es el flujo registrado, no dinero libre para gastar.',
    'Revisa primero tus pagos pendientes antes de gastar.',
    'Deberías cubrir tus obligaciones y revisar tus gastos.',
])
def test_negations_warnings_and_ordinary_recommendations_are_preserved(sentence):
    assert guard_recorded_flow(sentence, [FLOW]) == (sentence, [])


def test_a_negation_in_another_clause_does_not_hide_the_positive_claim():
    sentence = 'No conocemos tu saldo bancario, pero este margen confirma capacidad real de gasto.'
    corrected, removed = guard_recorded_flow(sentence, [FLOW])
    assert corrected == FLOW_REMINDER and removed == [sentence]


def test_no_verified_flow_or_failed_results_do_not_activate_the_narrow_guard():
    claim = 'Ya pagaste todas tus obligaciones.'
    for results in (None, [], [{'source_id': 'SMETAS'}], [{**FLOW, 'available': False}], [{**FLOW, 'status': 'failed'}]):
        assert guard_recorded_flow(claim, results) == (claim, [])


def test_general_overview_and_diagnosis_flows_are_also_protected():
    for result in ({'source_id': 'SFIN', 'current': FLOW['flow']},
                   {'source_id': 'SDIAG', 'flow': {'current': FLOW['flow']}}):
        assert guard_recorded_flow('Es dinero libre para gastar.', [result])[0] == FLOW_REMINDER
