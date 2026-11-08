import unittest
from copy import deepcopy
from datetime import date

from backend.budget_answers import budget_answer, overview_fallback


TODAY = date(2026, 11, 8)


def facts(income='7250.00', expense='7177.00', savings='0.00', available='73.00'):
    period = {'start': '2026-10-01', 'end': '2026-10-31'}
    return [('financial_overview', period, {'source_id': 'SFIN', 'currency': 'GTQ', 'period': dict(period),
        'current': {'currency': 'GTQ', 'from': period['start'], 'to': period['end'], 'income': income,
                    'expense': expense, 'net_savings': savings, 'available': available}})]


class BudgetAnswersTests(unittest.TestCase):
    def test_simple_margin_for_saving_or_debt_is_an_exact_cash_flow_summary(self):
        supplied = facts()
        before = deepcopy(supplied)
        result = budget_answer('¿Cuánto margen me dejó octubre de 2026 para ahorrar o pagar deuda?', supplied, TODAY)
        self.assertIn('En octubre de 2026', result)
        for amount in ('Q7,250.00', 'Q7,177.00', 'Q0.00', 'Q73.00'):
            self.assertIn(amount, result)
        self.assertIn('no tu saldo bancario', result)
        self.assertIn('no tu saldo bancario ni un importe confirmado', result)
        self.assertNotIn('\n', result)
        self.assertNotIn('SFIN', result)
        self.assertEqual(supplied, before)

    def test_simple_wording_and_explicit_intervals(self):
        for prompt in ('¿Cuánto disponible tengo en octubre de 2026?', '¿Qué sobrante me quedó en octubre?',
                       '¿Cuál fue mi margen de octubre para pagar mis deudas?',
                       '¿Cuánto me quedó disponible del 2026-10-01 al 2026-10-31?', '¿Cuánto margen tengo?'):
            with self.subTest(prompt=prompt):
                self.assertIsNotNone(budget_answer(prompt, facts(), TODAY))

    def test_zero_negative_and_net_withdrawals_are_not_reallocated_or_double_counted(self):
        self.assertIn('Q0.00', budget_answer('¿Cuánto margen tengo?', facts(expense='7250.00', available='0.00'), TODAY))
        result = budget_answer('¿Cuánto margen tengo?', facts(expense='7300.00', available='-50.00'), TODAY)
        self.assertIn('margen registrado fue Q-50.00', result)
        withdrawn = budget_answer('¿Cuánto margen tengo?', facts(savings='-50.00', available='123.00'), TODAY)
        self.assertIn('Q-50.00 de ahorro neto', withdrawn)
        self.assertIn('margen registrado fue Q123.00', withdrawn)

    def test_mixed_plans_thresholds_allocations_and_recommendations_defer(self):
        for prompt in ('¿Cuánto margen tengo y cómo lo reparto?', '¿Tengo más de Q100 disponibles?',
                       '¿Qué porcentaje del margen debería ahorrar?', '¿Cuánto margen tengo para invertir?',
                       '¿Cuánto margen me dejó octubre para ahorrar? Recomienda una deuda.',
                       '¿Cómo me libero de mis deudas?', '¿Cuánto margen me dejaron septiembre y octubre?'):
            self.assertIsNone(budget_answer(prompt, facts(), TODAY))

    def test_missing_inconsistent_failed_foreign_or_future_facts_do_not_take_shortcut(self):
        for key, value in [('source_id', 'SDEUDA'), ('currency', 'USD'), ('error', 'no disponible')]:
            supplied = facts()
            supplied[0][2][key] = value
            self.assertIsNone(budget_answer('¿Cuánto margen tengo?', supplied, TODAY))
        for key, value in [('available', '74.00'), ('expense', None), ('income', True), ('net_savings', 'NaN')]:
            supplied = facts()
            supplied[0][2]['current'][key] = value
            self.assertIsNone(overview_fallback(supplied, TODAY))
        future = facts()
        for target in (future[0][1], future[0][2]['period']):
            target.update(start='2026-11-01', end='2026-11-30')
        future[0][2]['current'].update({'from': '2026-11-01', 'to': '2026-11-30'})
        self.assertIsNone(overview_fallback(future, TODAY))
        self.assertIsNone(budget_answer('¿Cuánto margen dejó noviembre de 2026?', facts(), TODAY))
        self.assertIsNone(budget_answer('¿Cuánto margen dejó octubre de 2025?', facts(), TODAY))

    def test_fallback_is_explicitly_a_summary_not_an_answer_to_an_arbitrary_question(self):
        result = overview_fallback(facts(), TODAY)
        self.assertTrue(result.startswith('Como referencia, este es un resumen de lo registrado:'))
        self.assertIn('Q73.00', result)
        self.assertIsNone(overview_fallback([], TODAY))


if __name__ == '__main__':
    unittest.main()
