"""Numeric support helps reject inventions; it does not prove semantic accuracy."""
import unittest
from copy import deepcopy
from decimal import Decimal

from backend.grounding import unsupported_amounts


def facts():
    return [('financial_diagnosis', {}, {'source_id': 'SDIAG',
        'flow': {'current': {'income': '6000.00', 'expense': '1677.00', 'net_savings': '625.00', 'available': '3698.00'},
                 'previous': {'income': '7250.00', 'available': '73.00'}},
        'debt': {'totals': {'remaining': '7900.00'}, 'items': [{'remaining': '550.00'}, {'remaining': '2050.00'}, {'remaining': '5300.00'}]}})]


class GroundingTests(unittest.TestCase):
    def test_rejects_invented_half_month_and_uncomputed_deductions(self):
        answer = 'Para la quincena tienes Q3,000.00, gastos Q838.50 y disponible Q2,161.50.'
        self.assertEqual(unsupported_amounts(answer, facts()), ['Q3,000.00', 'Q838.50', 'Q2,161.50'])

    def test_accepts_current_actuals_and_does_not_change_data(self):
        supplied = facts()
        before = deepcopy(supplied)
        self.assertEqual(unsupported_amounts('Registraste Q6,000.00, Q1,677.00, Q625.00 y Q3,698.00; deuda Q7,900.00.', supplied), [])
        self.assertEqual(supplied, before)

    def test_percentages_negative_changes_and_zero_use_their_financial_fields(self):
        supplied = {'current': {'available': '-27.00', 'expense': '0.00'},
                    'changes_gtq': {'income': '350.00', 'expense': '880.00', 'net_savings': '-500.00'},
                    'debt_payments_to_observed_income_percent': '10.34', 'annual_percent': '1.49'}
        self.assertEqual(unsupported_amounts('Q-27.00, Q0.00, Q350.00, Q880.00, -Q500.00; 10.34% y 1,49%.', supplied), [])
        self.assertEqual(unsupported_amounts('Q10.34 y 350%', supplied), ['Q10.34', '350%'])

    def test_goal_values_and_backend_calculated_scenarios_are_supported(self):
        supplied = {'goals': {'items': [{'target': '5000.00', 'balance': '550.00', 'remaining': '4450.00', 'monthly_required': '741.67'}]},
                    'active_future_required': '2316.67', 'affordability_gap': '2243.67', 'scenario_available': '85.50'}
        self.assertEqual(unsupported_amounts('Tu meta Q5,000.00 tiene Q550.00; faltan Q4,450.00. Necesidad Q741.67, total Q2,316.67, brecha Q2,243.67 y escenario Q85.50.', supplied), [])

    def test_user_proposals_allow_currency_and_specific_bare_amount_phrases(self):
        for question in ('¿Y si aporto 100 al mes?', 'Pongo 100', 'Quiero ahorrar 100', 'Propongo Q100.00', '100 GTQ'):
            with self.subTest(question=question):
                self.assertEqual(unsupported_amounts('Si destinas Q100.00…', facts(), [question]), [])
        self.assertEqual(unsupported_amounts('Q150.50 y 25%', facts(), ['Aporto150,50 al mes y reduzco 25%']), [])

    def test_user_ids_counts_dates_and_assistant_messages_are_not_proposals(self):
        messages = [{'role': 'user', 'content': 'user_id=100, tengo 3 metas y fecha 2026-11-08'},
                    {'role': 'assistant', 'content': 'Podrías destinar Q100.00 y 100%.'}]
        self.assertEqual(unsupported_amounts('Q100.00 y 3%', facts(), messages), ['Q100.00', '3%'])
        self.assertEqual(unsupported_amounts('Q12.00 y Q100.00', facts(), ['Ahorro 12% y aporto 100 USD']), ['Q12.00', 'Q100.00'])

    def test_model_arguments_and_free_text_are_not_grounding(self):
        supplied = {'result': facts()[0][2], 'arguments': {'amount': '3000.00'},
                    'title': 'Presupuesto Q3000', 'name': 'Q3000', 'body': 'Puedes ahorrar Q3000',
                    'text': {'amount': '3000.00'}, 'id': 3000, 'count': 3000, 'input_tokens': 3000,
                    'year': 3000, 'deadline': '3000-01-01'}
        self.assertEqual(unsupported_amounts('Q3,000.00', supplied), ['Q3,000.00'])
        supplied = [('budget_scenario', {'monthly_reduction': '3000.00'}, facts()[0][2])]
        self.assertEqual(unsupported_amounts('Q3,000.00', supplied), ['Q3,000.00'])

    def test_no_financial_facts_means_no_validation(self):
        for supplied in (None, [], {}, {'id': 100, 'count': 100, 'body': 'Q100.00'}, {'expense': 'NaN'}):
            self.assertEqual(unsupported_amounts('Q100.00', supplied), [])

    def test_numeric_types_formatting_rounding_and_currency_suffix_are_supported(self):
        supplied = {'amount': Decimal('2050.50'), 'income': 6000, 'reference_gtq_per_usd': '7.64187'}
        self.assertEqual(unsupported_amounts('Q2,050.50, 6000 GTQ, GTQ7.64 y Q7.64187.', supplied), [])
        self.assertEqual(unsupported_amounts('Q2050.51', supplied), ['Q2050.51'])

    def test_matching_amount_is_not_a_semantic_guarantee(self):
        # 6000 is an income fact. A claim that it is a bank balance is still
        # semantically false; this limited guard deliberately cannot detect that.
        self.assertEqual(unsupported_amounts('Tu saldo bancario garantizado es Q6,000.00.', facts()), [])

    def test_duplicate_inventions_are_reported_once_in_answer_order(self):
        self.assertEqual(unsupported_amounts('Q100.00, Q200.00 y Q100.00.', facts()), ['Q100.00', 'Q200.00'])

    def test_failed_results_cannot_ground_numbers_even_if_they_contain_financial_fields(self):
        for failure in ({'available': False}, {'error': 'Fuente no disponible'}, {'status': 'failed'}, {'status': 'error'}):
            supplied = [*facts(), {**failure, 'amount': '3000.00', 'income': '2161.50'}]
            self.assertEqual(unsupported_amounts('Q3,000.00 y Q2,161.50', supplied), ['Q3,000.00', 'Q2,161.50'])
        self.assertEqual(unsupported_amounts('Q0.00', {'available': '0.00'}), [])


if __name__ == '__main__':
    unittest.main()
