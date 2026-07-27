"""Tests for service-date fill planning helpers."""
from availity_app.utils import service_date_fill_plans, service_dates_cross_year


def test_service_dates_cross_year_same_year():
    assert service_dates_cross_year('01/03/2025', '01/24/2025') is False
    assert service_dates_cross_year('12/15/2024', '12/31/2024') is False


def test_service_dates_cross_year_boundary():
    assert service_dates_cross_year('12/15/2024', '01/24/2025') is True
    assert service_dates_cross_year('01/02/2025', '12/31/2025') is False


def test_service_date_fill_plans_same_year_order():
    plans = service_date_fill_plans('01/03/2025', '01/24/2025')
    assert plans[0] == {'mode': 'robust', 'order': ('to', 'from')}
    assert plans[1] == {'mode': 'robust', 'order': ('from', 'to')}
    assert all(p['mode'] != 'year_first' for p in plans)


def test_service_date_fill_plans_cross_year_order():
    plans = service_date_fill_plans('12/15/2024', '01/24/2025')
    assert plans[0] == {'mode': 'robust', 'order': ('to', 'from')}
    assert plans[1] == {'mode': 'robust', 'order': ('from', 'to')}
    assert plans[2] == {'mode': 'year_first', 'order': ('to', 'from')}


def test_service_date_fill_plans_include_hidden_input_fallback():
    same_year = service_date_fill_plans('01/03/2025', '01/24/2025')
    cross_year = service_date_fill_plans('12/15/2024', '01/24/2025')
    assert same_year[-2]['mode'] == 'hidden_input'
    assert same_year[-1]['mode'] == 'hidden_input'
    assert cross_year[-2]['mode'] == 'hidden_input'
    assert cross_year[-1]['mode'] == 'hidden_input'


def test_service_date_fill_plans_hidden_input_order_prefers_primary():
    same_year = service_date_fill_plans('01/03/2025', '01/24/2025')
    cross_year = service_date_fill_plans('12/15/2024', '01/24/2025')
    assert same_year[-2]['order'] == ('to', 'from')
    assert cross_year[-2]['order'] == ('to', 'from')
