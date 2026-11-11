"""Regression: a rounded financial percentage must not erase a valid answer."""
from decimal import Decimal
from backend.grounding import unsupported_amounts


def test_real_demo_rounding_is_supported_without_rounding_money():
    facts = {'source_id': 'SGASTOS', 'amount': '1500.00', 'expense_percent': '25.22'}
    assert unsupported_amounts('Vivienda: Q1,500.00, el 25\u202f% de tus gastos.', facts) == []
    assert unsupported_amounts('24%, 26%, 25.0%, Q1,499.99.', facts) == ['24%', '26%', '25.0%', 'Q1,499.99']
    assert unsupported_amounts('25.2%, 25,22% y 25.220%.', facts) == []


def test_percent_rounding_uses_original_fact_precision_and_decimal_half_up():
    assert unsupported_amounts('1.4%', {'annual_percent': '1.449'}) == []
    assert unsupported_amounts('1.5%', {'annual_percent': '1.449'}) == ['1.5%']
    assert unsupported_amounts('1.5%', {'annual_percent': '1.45'}) == []
    assert unsupported_amounts('-25%', {'change_percent': Decimal('-25.22')}) == []
    assert unsupported_amounts('25%', {'change_percent': Decimal('-25.22')}) == ['25%']


def test_explicit_finer_user_proposal_is_preserved():
    assert unsupported_amounts('1.234%', {'expense': '10'}, ['Propongo 1.234%']) == []
