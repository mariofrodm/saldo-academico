"""Pure formatting/routing checks for already computed category comparisons."""
import unittest
from copy import deepcopy
from datetime import date

from backend.direct_answers import comparison_answer


TODAY = date(2026, 11, 8)


def facts(equal=False, higher='Alimentación', future=False):
    period = {'start': '2026-11-01', 'end': '2026-11-30'} if future else {'start': '2026-10-01', 'end': '2026-10-31'}
    result = {'period': period,
              'items': [{'category': 'Alimentación', 'amount': '1100.00'},
                        {'category': 'Universidad', 'amount': '1100.00' if equal else '900.00'}],
              'difference_gtq': '0.00' if equal else '200.00',
              'higher_category': None if equal else higher, 'equal': equal}
    return [('compare_spending', {**period, 'category_a': 'Alimentación', 'category_b': 'Universidad'}, result)]


class DirectAnswersTests(unittest.TestCase):
    def test_more_and_less_use_backend_order_and_preserve_facts(self):
        original = facts()
        saved = deepcopy(original)
        more = comparison_answer('¿En cuál pagué más?', original, TODAY)
        less = comparison_answer('¿En cuál pagué menos?', original, TODAY)
        self.assertIn('más en Alimentación', more)
        self.assertIn('Q1,100.00', more)
        self.assertIn('menos en Universidad', less)
        self.assertIn('Q900.00', less)
        self.assertIn('en octubre de 2026', more)
        self.assertEqual(original, saved)

    def test_difference_formats_given_backend_value_without_recomputing(self):
        supplied = facts()
        supplied[0][2]['items'][0]['amount'] = '900.01'
        supplied[0][2]['difference_gtq'] = '0.01'
        text = comparison_answer('¿Cuánto de diferencia?', supplied, TODAY)
        self.assertIn('Q0.01', text)
        self.assertIn('más en Alimentación', text)

    def test_equal_amounts_have_no_invented_winner(self):
        text = comparison_answer('¿Pagué más en una de las dos?', facts(equal=True), TODAY)
        self.assertIn('lo mismo', text)
        self.assertIn('Q1,100.00', text)
        difference = comparison_answer('¿Cuánto de diferencia?', facts(equal=True), TODAY)
        self.assertIn('No hubo diferencia', difference)

    def test_item_order_does_not_determine_winner(self):
        supplied = facts()
        supplied[0][2]['items'].reverse()
        self.assertIn('más en Alimentación', comparison_answer('¿Dónde pagué más?', supplied, TODAY))
        self.assertIn('menos en Universidad', comparison_answer('¿Dónde pagué menos?', supplied, TODAY))

    def test_explanations_advice_and_plans_are_deferred(self):
        for prompt in ('¿Por qué pagué más en alimentación?', '¿Qué recomiendas para gastar menos?',
                       '¿Puedo gastar menos?', 'Compara y prepara un plan de ahorro.',
                       '¿Me conviene pagar más?', '¿Qué hacer para gastar menos?'):
            with self.subTest(prompt=prompt):
                self.assertIsNone(comparison_answer(prompt, facts(), TODAY))

    def test_threshold_is_not_misreported_as_category_winner(self):
        for prompt in ('¿Pagué más de 1000?', '¿Pagué menos de Q 1000?', '¿Pagué igual a GTQ 1000?',
                       '¿Pagué más de Q1000?', '¿Pagué menos de GTQ1000?'):
            with self.subTest(prompt=prompt):
                self.assertIsNone(comparison_answer(prompt, facts(), TODAY))

    def test_future_period_is_not_reported_as_executed(self):
        self.assertIsNone(comparison_answer('¿Dónde pagué más este mes completo?', facts(future=True), TODAY))

    def test_arbitrary_interval_keeps_exact_dates(self):
        supplied = facts()
        supplied[0][2]['period'] = {'start': '2026-10-05', 'end': '2026-10-15'}
        self.assertIn('del 5/10/2026 al 15/10/2026', comparison_answer('¿Dónde pagué más?', supplied, TODAY))

    def test_unconfirmed_or_unrelated_fact_does_not_take_shortcut(self):
        for supplied in ([], facts()+facts(), [('spending_breakdown', {}, facts()[0][2])],
                         [('compare_spending', {}, {'items': []})]):
            with self.subTest(supplied=supplied):
                self.assertIsNone(comparison_answer('¿Dónde pagué más?', supplied, TODAY))

    def test_compound_requests_do_not_drop_total_count_percentage_or_second_question(self):
        for prompt in (
            'En octubre, ¿pagué más en Alimentación o Universidad y cuánto gasté en total?',
            '¿Pagué más en Alimentación o Universidad? ¿Cuántos pagos hice?',
            'Compara Alimentación y Universidad e indica el porcentaje.',
            '¿Pagué más en Alimentación o Universidad y cuál fue la diferencia?',
            '¿Cuál categoría tuvo más pagos y cuántas veces pagué?',
            '¿Dónde pagué más? También quiero el número de pagos.',
        ):
            with self.subTest(prompt=prompt):
                self.assertIsNone(comparison_answer(prompt, facts(), TODAY))

    def test_single_difference_followup_is_still_a_complete_narrow_request(self):
        result = comparison_answer('¿Y cuánto de diferencia?', facts(), TODAY)
        self.assertIn('Q200.00', result)
        self.assertIn('más en Alimentación', result)


if __name__ == '__main__':
    unittest.main()
