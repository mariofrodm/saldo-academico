import unittest
from copy import deepcopy

from backend.savings_intent import savings_arguments


def snapshot():
    return {'source_id': 'SMETAS', 'currency': 'GTQ', 'as_of': '2026-11-08', 'items': [
        {'id': 1, 'name': 'Fondo de emergencia', 'active': True, 'state': 'en progreso', 'remaining_contributions': 6},
        {'id': 2, 'name': 'Computadora para trabajo freelance', 'active': True, 'state': 'en progreso', 'remaining_contributions': 4},
        {'id': 3, 'name': 'Diplomado para mejorar ingresos', 'active': True, 'state': 'en progreso', 'remaining_contributions': 3},
        {'id': 4, 'name': 'Viaje', 'active': False, 'state': 'inactiva', 'remaining_contributions': 10},
        {'id': 5, 'name': 'Curso', 'active': True, 'state': 'cumplida', 'remaining_contributions': 1},
        {'id': 6, 'name': 'Equipo', 'active': True, 'state': 'vencida', 'remaining_contributions': 0},
    ]}


def context(user='¿Y si aporto 100 al mes?', assistant='¿A cuál de tus metas quieres destinarlo?'):
    return {'messages': [{'role': 'user', 'content': user}, {'role': 'assistant', 'content': assistant}]}


class SavingsIntentTests(unittest.TestCase):
    def test_current_explicit_proposal_selects_exact_name_alias_and_id(self):
        cases = [('Si aporto 100 al mes al fondo de emergencia', 1, 6, '100.00'),
                 ('¿Y si pongo Q150,50 mensuales a la computadora?', 2, 4, '150.50'),
                 ('Si pongo Q0.01 mensuales para meta 3', 3, 3, '0.01'),
                 ('Si aporto100 al mes a #1', 1, 6, '100.00')]
        for prompt, ident, months, monthly in cases:
            with self.subTest(prompt=prompt):
                self.assertEqual(savings_arguments(prompt, context(), snapshot()),
                                 {'goal_id': ident, 'months': months, 'monthly': monthly})

    def test_selection_after_user_proposal_uses_that_user_amount_not_assistant(self):
        ctx = context(assistant='Te recomiendo aportar Q500.00 al fondo.')
        self.assertEqual(savings_arguments('Al fondo de emergencia', ctx, snapshot()),
                         {'goal_id': 1, 'months': 6, 'monthly': '100.00'})
        self.assertEqual(savings_arguments('La computadora', context('Si pongo Q200.25 mensuales'), snapshot()),
                         {'goal_id': 2, 'months': 4, 'monthly': '200.25'})

    def test_previous_explicit_selection_can_precede_current_monthly_amount(self):
        self.assertEqual(savings_arguments('Y si aporto 100 al mes', context('Elijo la computadora'), snapshot()),
                         {'goal_id': 2, 'months': 4, 'monthly': '100.00'})

    def test_assistant_recommendations_or_older_user_amounts_are_not_current_choices(self):
        self.assertIsNone(savings_arguments('Y si aporto 100 al mes', context('¿Qué metas tengo?', 'Elige Fondo de emergencia'), snapshot()))
        ctx = {'messages': [*context()['messages'], {'role': 'user', 'content': '¿Qué opciones hay?'}]}
        self.assertIsNone(savings_arguments('Al fondo de emergencia', ctx, snapshot()))
        self.assertIsNone(savings_arguments('Al fondo de emergencia', {'messages': [{'role': 'assistant', 'content': 'Si aporto 100 al mes'}]}, snapshot()))

    def test_no_implicit_goal_and_ambiguous_or_multiple_names_defer(self):
        self.assertIsNone(savings_arguments('Y si aporto 100 al mes', context('¿Por cuál comienzo?'), snapshot()))
        self.assertIsNone(savings_arguments('Al fondo y la computadora', context(), snapshot()))
        supplied = snapshot()
        supplied['items'].append({'id': 7, 'name': 'Fondo universitario', 'active': True, 'state': 'en progreso', 'remaining_contributions': 9})
        self.assertIsNone(savings_arguments('Al fondo', context(), supplied))
        self.assertEqual(savings_arguments('Al fondo de emergencia', context(), supplied)['goal_id'], 1)

    def test_compound_scenarios_period_overrides_and_foreign_currency_defer(self):
        for prompt in ('Si aporto 100+500 al mes al fondo', 'Si aporto 100 USD al mes al fondo',
                       'Si aporto 100 al mes al fondo y pago deudas', 'Si aporto 100 al mes al fondo durante 6 meses',
                       'Si aporto 100 al mes al fondo hasta 2027-12-01', 'Si aporto 100 al mes al fondo y reduzco gastos',
                       'Si aporto 100 al mes al fondo o la computadora', 'Si pongo 0 mensuales al fondo',
                       'Si aporto -100 al mes al fondo', 'Si aporto 100.001 al mes al fondo'):
            with self.subTest(prompt=prompt):
                self.assertIsNone(savings_arguments(prompt, context(), snapshot()))
        for previous in ('Si aporto 100 al mes USD', 'Si aporto 100 al mes durante 6 meses',
                         'Si aporto 100 al mes al fondo y pago deudas'):
            self.assertIsNone(savings_arguments('Al fondo de emergencia', context(previous), snapshot()))

    def test_completed_inactive_expired_and_invalid_backend_months_defer(self):
        for selected in ('Viaje', 'Curso', 'Equipo'):
            self.assertIsNone(savings_arguments(selected, context(), snapshot()))
        for months in (0, 121, True, '6', None):
            supplied = snapshot()
            supplied['items'][0]['remaining_contributions'] = months
            self.assertIsNone(savings_arguments('Al fondo de emergencia', context(), supplied))

    def test_uses_backend_schedule_literal_without_money_math_or_mutation(self):
        supplied = snapshot()
        supplied['items'][0]['remaining_contributions'] = 7
        before = deepcopy(supplied)
        self.assertEqual(savings_arguments('Al fondo de emergencia', context(), supplied),
                         {'goal_id': 1, 'months': 7, 'monthly': '100.00'})
        self.assertEqual(supplied, before)

    def test_snapshot_scope_and_shape_are_required(self):
        for key, value in [('source_id', 'SDEUDA'), ('currency', 'USD'), ('as_of', 'invalid'), ('items', [])]:
            supplied = snapshot()
            supplied[key] = value
            self.assertIsNone(savings_arguments('Al fondo de emergencia', context(), supplied))
        self.assertIsNone(savings_arguments('Al fondo de emergencia', {}, snapshot()))


if __name__ == '__main__':
    unittest.main()
