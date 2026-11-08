"""Pure routing/wording tests: no database, provider or investment assumptions."""
import unittest
from copy import deepcopy
from datetime import date

from backend.planning_answers import planning_answer


TODAY = date(2026, 11, 8)


def facts(available='73.00', margin='73.00', required='2316.67', gap='2243.67'):
    return [('planning_snapshot', {}, {
        'source_id': 'SPLAN', 'currency': 'GTQ', 'as_of': TODAY.isoformat(),
        'last_closed_month': {'from': '2026-10-01', 'to': '2026-10-31', 'income': '7250.00',
                              'expense': '7177.00', 'net_savings': '0.00', 'available': available},
        'active_future_goal_count': 3, 'expired_active_goal_count': 1,
        'active_future_required': required, 'historical_margin': margin, 'affordability_gap': gap,
        'verified_affordable_contribution': None,
    })]


class PlanningAnswersTests(unittest.TestCase):
    def test_deficit_answer_uses_verified_values_and_does_not_assign_any_payment(self):
        supplied = facts()
        before = deepcopy(supplied)
        result = planning_answer('¿Por cuál comienzo?', supplied, TODAY)
        self.assertEqual(len(result.split('\n\n')), 2)
        self.assertIn('Q73.00', result)
        self.assertIn('Q2,316.67', result)
        self.assertIn('octubre de 2026', result)
        self.assertIn('no tu saldo actual', result)
        self.assertIn('no cubre todos esos aportes', result)
        self.assertIn('no es una deuda', result)
        self.assertIn('¿Cuál de tus objetivos es esencial para ti ahora?', result)
        for invented in ('50%', 'Q600', 'Q1,025', 'Q741', 'contrato', 'acuerdo', 'SPLAN'):
            self.assertNotIn(invented, result)
        self.assertEqual(supplied, before)

    def test_narrow_priority_variants_include_accents_and_case(self):
        for prompt in ('¿Cuál priorizo?', 'POR CUÁL EMPEZAR', '¿Por cuál debo comenzar?',
                       '¿Cuál de mis metas priorizo primero?', '¿Y por cuál comienzo?', 'Por cual empiezo.'):
            with self.subTest(prompt=prompt):
                self.assertIsNotNone(planning_answer(prompt, facts(), TODAY))

    def test_explicit_goal_planning_questions_have_the_same_affordability_guard(self):
        for prompt in ('¿Cómo priorizo mis metas?', '¿Cómo puedo priorizar mis metas de ahorro?',
                       '¿Cómo puedo cumplir mis metas dado mi contexto actual?',
                       '¿Qué debería hacer para cumplir mis metas de ahorro dado mi contexto actual?',
                       '¿Qué puedo hacer para alcanzar todas mis metas, según mi situación actual?'):
            with self.subTest(prompt=prompt):
                result = planning_answer(prompt, facts(), TODAY)
                self.assertIsNotNone(result)
                self.assertIn('Q73.00', result)
                self.assertIn('Q2,316.67', result)
                self.assertNotIn('%', result)

    def test_zero_or_negative_recorded_margin_is_not_replaced_by_positive_capacity(self):
        zero = planning_answer('¿Por cuál comienzo?', facts(available='0.00', margin='0.00', gap='2316.67'), TODAY)
        self.assertIn('margen de Q0.00', zero)
        negative = planning_answer('¿Cuál priorizo?', facts(available='-27.00', margin='0.00', gap='2316.67'), TODAY)
        self.assertIn('margen registrado fue negativo: Q-27.00', negative)
        self.assertNotIn('margen de Q0.00', negative)

    def test_formats_backend_values_without_deriving_ratios_or_rounding_to_new_amounts(self):
        result = planning_answer('¿Por cuál comienzo?', facts(available='49.99', margin='49.99', required='50.00', gap='0.01'), TODAY)
        self.assertIn('Q49.99', result)
        self.assertIn('Q50.00', result)
        self.assertNotIn('%', result)
        self.assertNotIn('Q25', result)

    def test_covered_needs_no_future_goals_or_verified_capacity_use_normal_advice_path(self):
        enough = facts(available='3000.00', margin='3000.00', gap='0.00')
        self.assertIsNone(planning_answer('¿Por cuál comienzo?', enough, TODAY))
        equal = facts(available='2316.67', margin='2316.67', gap='0.00')
        self.assertIsNone(planning_answer('¿Cuál priorizo?', equal, TODAY))
        for key, value in [('active_future_goal_count', 0), ('active_future_required', '0.00'),
                           ('verified_affordable_contribution', '50.00')]:
            supplied = facts()
            supplied[0][2][key] = value
            self.assertIsNone(planning_answer('¿Cuál priorizo?', supplied, TODAY))

    def test_unrelated_questions_and_additional_financial_requests_are_not_intercepted(self):
        for prompt in ('¿Qué metas tengo?', '¿Y si aporto 100 al mes?', '¿Cómo salgo de mis deudas?',
                       '¿Por cuál comienzo y cuánto debería pagar?', '¿Por cuál comienzo con Q9999?',
                       '¿Por cuál comienzo? Recomiéndame inversiones.', '¿Cómo ordeno mis finanzas?',
                       '¿Cómo priorizo mis metas y pago mis deudas?',
                       '¿Qué debería hacer para cumplir mis metas si aporto 100 al mes?'):
            with self.subTest(prompt=prompt):
                self.assertIsNone(planning_answer(prompt, facts(), TODAY))

    def test_source_date_month_and_arguments_are_required_not_supplied_by_the_prompt(self):
        for supplied in ([], facts()+facts(), [('goal_snapshot', {}, facts()[0][2])],
                         [('planning_snapshot', {'user_id': 999}, facts()[0][2])]):
            self.assertIsNone(planning_answer('¿Por cuál comienzo?', supplied, TODAY))
        for key, value in [('source_id', 'SDEUDA'), ('currency', 'USD'), ('as_of', '2026-11-07')]:
            supplied = facts()
            supplied[0][2][key] = value
            self.assertIsNone(planning_answer('¿Por cuál comienzo?', supplied, TODAY))
        for key, value in [('from', '2026-09-01'), ('to', '2026-11-30')]:
            supplied = facts()
            supplied[0][2]['last_closed_month'][key] = value
            self.assertIsNone(planning_answer('¿Por cuál comienzo?', supplied, TODAY))

    def test_missing_or_invalid_facts_and_empty_ledger_do_not_generate_advice(self):
        for key in ('last_closed_month', 'active_future_required', 'historical_margin',
                    'active_future_goal_count', 'verified_affordable_contribution'):
            supplied = facts()
            supplied[0][2].pop(key)
            self.assertIsNone(planning_answer('¿Por cuál comienzo?', supplied, TODAY))
        for key, value in [('active_future_required', 'NaN'), ('historical_margin', True),
                           ('affordability_gap', '0.001'), ('active_future_goal_count', True)]:
            supplied = facts()
            supplied[0][2][key] = value
            self.assertIsNone(planning_answer('¿Por cuál comienzo?', supplied, TODAY))
        supplied = facts(available='0.00', margin='0.00')
        supplied[0][2]['last_closed_month'].update(income='0.00', expense='0.00', net_savings='0.00')
        self.assertIsNone(planning_answer('¿Por cuál comienzo?', supplied, TODAY))

    def test_no_expired_goal_has_no_invented_deadline_problem(self):
        supplied = facts()
        supplied[0][2]['expired_active_goal_count'] = 0
        result = planning_answer('¿Cuál priorizo?', supplied, TODAY)
        self.assertNotIn('vencida', result)


if __name__ == '__main__':
    unittest.main()
