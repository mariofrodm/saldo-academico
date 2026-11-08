import unittest
from copy import deepcopy
from datetime import date

from backend.goal_answers import goal_answer


TODAY = date(2026, 11, 8)


def rows():
    return [
        {'id': 1, 'name': 'Fondo de emergencia', 'balance': '550.00', 'target': '5000.00', 'deadline': '2027-04-30', 'active': True, 'state': 'en progreso'},
        {'id': 2, 'name': 'Computadora para trabajo freelance', 'balance': '400.00', 'target': '4500.00', 'deadline': '2027-02-28', 'active': True, 'state': 'en progreso'},
        {'id': 3, 'name': 'Curso corto completado', 'balance': '25.00', 'target': '25.00', 'deadline': '2026-11-30', 'active': True, 'state': 'cumplida'},
        {'id': 4, 'name': 'Equipo', 'balance': '0.00', 'target': '600.00', 'deadline': '2026-10-31', 'active': True, 'state': 'vencida'},
        {'id': 5, 'name': 'Viaje', 'balance': '0.00', 'target': '1200.00', 'deadline': '2027-08-31', 'active': False, 'state': 'inactiva'},
    ]


def listing():
    return [('goal_snapshot', {}, {'source_id': 'SMETAS', 'currency': 'GTQ', 'as_of': TODAY.isoformat(),
        'items': rows(), 'total_count': 5, 'has_more': False, 'totals': {
            'in_progress_count': 2, 'completed_active_count': 1, 'expired_active_count': 1, 'inactive_count': 1}})]


def planning():
    return [('planning_snapshot', {}, {'source_id': 'SPLAN', 'currency': 'GTQ', 'as_of': TODAY.isoformat(), 'goals': {'items': rows()}})]


def context(previous='¿Por cuál comienzo?', recommendation='Te recomiendo primero el Fondo de emergencia.'):
    return {'state': {'topic': 'goals'}, 'messages': [
        {'role': 'user', 'content': previous}, {'role': 'assistant', 'content': recommendation}]}


class GoalAnswersTests(unittest.TestCase):
    def test_listing_reports_explicit_states_without_immediate_payment_recommendations(self):
        supplied = listing()
        before = deepcopy(supplied)
        result = goal_answer('¿Qué metas de ahorro tengo y cómo voy?', supplied, {}, TODAY)
        self.assertIn('5 metas registradas: 2 en progreso, 1 cumplida, 1 con plazo vencido y 1 inactiva', result)
        self.assertIn('Fondo de emergencia lleva Q550.00 de Q5,000.00', result)
        self.assertIn('30/04/2027', result)
        self.assertIn('ya está cumplida: Q25.00 de Q25.00', result)
        self.assertIn('plazo vencido desde el 31/10/2026', result)
        self.assertIn('no un pago exigible inmediato', result)
        self.assertIn('Viaje está inactiva', result)
        self.assertNotIn('paga', result)
        self.assertNotIn('debes aportar', result)
        self.assertNotIn('SMETAS', result)
        self.assertEqual(supplied, before)

    def test_listing_supported_variants_empty_and_truncated_results(self):
        for prompt in ('¿Qué metas tengo?', '¿Cómo van mis metas?', 'COMO VOY CON MIS METAS DE AHORRO'):
            self.assertIsNotNone(goal_answer(prompt, listing(), {}, TODAY))
        empty = listing()
        empty[0][2].update(items=[], total_count=0)
        self.assertEqual(goal_answer('¿Qué metas tengo?', empty, {}, TODAY), 'No hay metas registradas todavía.')
        partial = listing()
        partial[0][2].update(items=rows()[:1], total_count=20, has_more=True)
        result = goal_answer('¿Cómo van mis metas?', partial, {}, TODAY)
        self.assertIn('20 metas registradas', result)
        self.assertIn('Te muestro una parte', result)

    def test_short_unspecified_contribution_asks_for_selection_ignoring_assistant_advice(self):
        for prompt, expected in [('¿Y si aporto 100 al mes?', 'Q100.00'), ('Si aporto Q150,50 mensuales', 'Q150.50')]:
            result = goal_answer(prompt, planning(), context(), TODAY)
            self.assertEqual(result, f'¿A cuál de tus metas quieres destinar esos {expected} mensuales?')

    def test_user_goal_names_aliases_and_ids_defer_to_the_normal_simulation(self):
        for previous in ('Elijo Fondo de emergencia', 'Quiero destinarlo a la computadora', 'La meta 2', 'ID 1', '#2'):
            with self.subTest(previous=previous):
                self.assertIsNone(goal_answer('Y si aporto 100 al mes', planning(), context(previous), TODAY))
        self.assertIsNone(goal_answer('Y si aporto 100 al mes a la computadora', planning(), context(), TODAY))
        earlier_choice = context('Elijo el Fondo de emergencia')
        earlier_choice['messages'] += [
            {'role': 'user', 'content': '¿Por cuál comienzo?'},
            {'role': 'assistant', 'content': 'Primero revisemos tu margen.'}]
        self.assertIsNone(goal_answer('Y si aporto 100 al mes', planning(), earlier_choice, TODAY))

    def test_compound_scenarios_debt_invalid_amounts_and_unrelated_questions_are_not_intercepted(self):
        for prompt in ('Y si aporto 100+500 al mes', 'Y si aporto 100 al mes y pago deudas', 'Si aporto 0 al mes',
                       'Si aporto -100 al mes', 'Si aporto 100.001 al mes', '¿Qué meta debería elegir?',
                       '¿Qué metas tengo y cuánto debería pagar inmediatamente?'):
            self.assertIsNone(goal_answer(prompt, planning(), context(), TODAY))

    def test_missing_scope_freshness_or_multiple_eligible_goals_does_not_guess(self):
        for name, source in [('debt_snapshot', 'SPLAN'), ('planning_snapshot', 'SMETAS')]:
            supplied = planning()
            supplied[0] = (name, {}, {**supplied[0][2], 'source_id': source})
            self.assertIsNone(goal_answer('Y si aporto 100 al mes', supplied, context(), TODAY))
        supplied = planning()
        supplied[0][2]['as_of'] = '2026-11-07'
        self.assertIsNone(goal_answer('Y si aporto 100 al mes', supplied, context(), TODAY))
        supplied = planning()
        supplied[0][2]['goals']['items'] = rows()[:1]
        self.assertIsNone(goal_answer('Y si aporto 100 al mes', supplied, context(), TODAY))
        self.assertIsNone(goal_answer('Y si aporto 100 al mes', planning(), {'state': {'topic': 'debt'}, 'messages': []}, TODAY))


if __name__ == '__main__':
    unittest.main()
