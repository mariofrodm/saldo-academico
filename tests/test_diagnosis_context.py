"""Pure context-selection tests; no database/provider activity or new arithmetic."""
import json
import unittest
from copy import deepcopy

from backend.diagnosis import model_context


def fixture():
    period = {'start': '2026-11-01', 'end': '2026-11-08'}
    flow = {'income': '6000.00', 'expense': '1450.00', 'net_savings': '500.00',
            'available': '4050.00', 'currency': 'GTQ', 'from': '2026-11-01', 'to': '2026-11-08'}
    pending = {'count': 12, 'remaining': '10000.00', 'overdue': '1000.00', 'overdue_count': 2,
               'due_today': '0.00', 'future_due': '9000.00', 'carry_from_prior_months': '1000.00'}
    return {'source_id': 'SDIAG', 'currency': 'GTQ', 'period': period, 'as_of': '2026-11-08',
        'limits': 'Flujo por fechas; metas y recurrentes a hoy. Los detalles son muestras; los totales incluyen todos los registros. No conocemos tasas ni cuotas mínimas. Un mes parcial no es margen mensual recurrente.',
        'last_closed_month': {**flow, 'income': '7250.00', 'expense': '7177.00', 'net_savings': '0.00',
                              'available': '73.00', 'from': '2026-10-01', 'to': '2026-10-31'},
        'flow': {'source_id': 'SFIN', 'currency': 'GTQ', 'period': period,
                 'current': flow, 'previous': {'available': '99999.00'},
                 'changes_gtq': {'expense': '-99999.00'}, 'expense_to_income_percent': '24.17',
                 'net_savings_to_income_percent': '8.33'},
        'spending': {'source_id': 'SGASTOS', 'period': period, 'total_expense': '1450.00',
            'observed_income': '6000.00', 'debt_payments': '750.00',
            'debt_payments_to_observed_income_percent': '12.50', 'payment_count': 178,
            'total_count': 13, 'detail_limit': 3, 'has_more': True, 'totals_include_all_records': True,
            'items': [{'category_id': index+1, 'category': name, 'amount': '100.00',
                       'payment_count': 40, 'expense_percent': '6.90', 'income_percent': '1.67'}
                      for index, name in enumerate(('Vivienda', 'Alimentación', 'Universidad'))]},
        'recurring': {'source_id': 'SREC', 'as_of': '2026-11-08', 'total_count': 8, 'has_more': True,
            'totals_include_all_records': True, 'detail_limit': 3,
            'totals': [{'active': True, 'kind': 'expense', 'count': 7, 'monthly_planned': '2500.00'},
                       {'active': False, 'kind': 'expense', 'count': 1, 'monthly_planned': '100.00'}],
            'items': [{'title': 'Servicio '+str(index), 'amount': '100.00'} for index in range(3)]},
        'pending': {'source_id': 'SPEND', 'as_of': '2026-11-08', 'totals': pending, 'total_count': 12,
            'detail_limit': 3, 'has_more': True, 'totals_include_all_records': True,
            'items': [{'title': 'Compromiso '+str(index), 'remaining': '100.00'} for index in range(3)]},
        'debt': {'source_id': 'SDEUDA', 'as_of': '2026-11-08', 'total_count': 3,
            'detail_limit': 3, 'has_more': False, 'totals_include_all_records': True,
            'totals': {'count': 3, 'remaining': '7900.00', 'overdue': '0.00', 'overdue_count': 0,
                       'due_today': '0.00', 'future_due': '7900.00', 'carry_from_prior_months': '0.00'},
            'items': [{'id': index+161, 'title': title, 'remaining': amount, 'due_date': '2026-11-30'}
                      for index, (title, amount) in enumerate((('Préstamo familiar', '550.00'),
                                                            ('Computadora', '2050.00'), ('Préstamo personal', '5300.00')))]},
        'goals': {'source_id': 'SMETAS', 'as_of': '2026-11-08', 'total_count': 6,
            'detail_limit': 3, 'has_more': True, 'totals_include_all_records': True,
            'totals': {'active_count': 5, 'inactive_count': 1, 'active_target': '15000.00',
                       'active_balance': '3500.00', 'active_required_monthly': '2316.67',
                       'expired_active_count': 1, 'in_progress_count': 3, 'completed_active_count': 1},
            'items': [{'id': index+1, 'name': 'Meta financiera '+str(index), 'state': state,
                       'active': True, 'balance': '500.00', 'target': '5000.00', 'remaining': '4500.00',
                       'deadline': '2027-04-30', 'days_to_deadline': 173,
                       'remaining_contributions': 6, 'required_monthly_to_deadline': '750.00'}
                      for index, state in enumerate(('en progreso', 'vencida', 'cumplida'))]}}


class DiagnosisContextTests(unittest.TestCase):
    def test_six_goal_fixture_stays_within_budget_and_preserves_all_global_facts(self):
        original = fixture()
        context = model_context(original)
        self.assertLessEqual(len(json.dumps(context, ensure_ascii=False)), 3500)
        for key in ('source_id', 'currency', 'period', 'as_of', 'limits', 'last_closed_month'):
            self.assertEqual(context[key], original[key])
        self.assertEqual(context['flow']['current'], original['flow']['current'])
        self.assertEqual(context['flow']['expense_to_income_percent'], original['flow']['expense_to_income_percent'])
        self.assertEqual(context['flow']['net_savings_to_income_percent'], original['flow']['net_savings_to_income_percent'])
        self.assertNotIn('previous', context['flow'])
        self.assertNotIn('changes_gtq', context['flow'])
        for name in ('recurring', 'pending', 'debt', 'goals'):
            self.assertEqual(context[name]['totals'], original[name]['totals'])
            self.assertEqual(context[name]['total_count'], original[name]['total_count'])
        for key in ('total_expense', 'observed_income', 'debt_payments', 'debt_payments_to_observed_income_percent', 'payment_count', 'total_count'):
            self.assertEqual(context['spending'][key], original['spending'][key])

    def test_details_are_samples_with_honest_omission_flags(self):
        context = model_context(fixture())
        for name in ('spending', 'goals'):
            self.assertEqual(len(context[name]['items']), 2)
            self.assertTrue(context[name]['has_more'])
            self.assertTrue(context[name]['totals_include_all_records'])
        self.assertEqual(len(context['debt']['items']),3)
        self.assertFalse(context['debt']['has_more'])
        self.assertEqual(context['debt']['items'][2]['remaining'],'5300.00')
        self.assertIn('Pagos reales',context['spending']['meaning'])
        self.assertIn('Plantillas previstas',context['recurring']['meaning'])
        for name in ('recurring', 'pending'):
            self.assertNotIn('items', context[name])
            self.assertTrue(context[name]['details_omitted'])
            self.assertTrue(context[name]['has_more'])
        self.assertEqual(set(context['debt']['items'][0]), {'title', 'remaining'})
        self.assertEqual(set(context['goals']['items'][0]), {'id', 'name', 'state', 'balance', 'target', 'deadline'})

    def test_original_is_not_mutated_and_nested_results_are_independent(self):
        original = fixture()
        saved = deepcopy(original)
        context = model_context(original)
        self.assertEqual(original, saved)
        context['flow']['current']['available'] = 'changed'
        context['pending']['totals']['remaining'] = 'changed'
        context['spending']['items'][0]['amount'] = 'changed'
        self.assertEqual(original, saved)

    def test_empty_sections_and_unknown_information_do_not_become_invented_zeroes(self):
        context = model_context({'source_id': 'SDIAG', 'pending': {'total_count': 0, 'totals': {'remaining': '0.00'}, 'items': [], 'has_more': False}})
        self.assertEqual(context['pending']['totals'], {'remaining': '0.00'})
        self.assertFalse(context['pending']['has_more'])
        self.assertFalse(context['pending']['details_omitted'])
        self.assertNotIn('goals', context)
        self.assertNotIn('last_closed_month', context)
        self.assertIsNone(model_context(None))

    def test_upstream_omission_is_preserved_even_when_visible_items_fit(self):
        original = {'goals': {'items': [{'id': 7, 'name': 'Fondo'}], 'has_more': True}}
        self.assertTrue(model_context(original)['goals']['has_more'])


if __name__ == '__main__':
    unittest.main()
