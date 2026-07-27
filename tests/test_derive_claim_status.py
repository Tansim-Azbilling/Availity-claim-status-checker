"""Tests for amount-based claim status derivation."""
from unittest.mock import patch

from availity_app.automation import derive_claim_status
from availity_app.constants import PAID_OVERPAYMENT_STATUS, PAYER_CONFIG


def _claim_data(status='PAID'):
    return {'Claim Status': status}


@patch('availity_app.automation.log_to_gui')
def test_line_level_zero_paid_marks_denied(mock_log):
    """Aetna / line-level: paid $0 with billed > $0 → Denied."""
    claim_data = _claim_data()
    payer_config = PAYER_CONFIG['Aetna Better Health']

    derive_claim_status(claim_data, '$100.00', '$0.00', payer_config)

    assert claim_data['Claim Status'] == 'Denied'


@patch('availity_app.automation.log_to_gui')
def test_line_level_partial_payment(mock_log):
    """Line-level: 0 < paid < billed → Partially Paid."""
    claim_data = _claim_data()
    payer_config = PAYER_CONFIG['Healthfirst']

    derive_claim_status(claim_data, '$100.00', '$40.00', payer_config)

    assert claim_data['Claim Status'] == 'Partially Paid'


@patch('availity_app.automation.log_to_gui')
def test_line_level_overpayment(mock_log):
    """Line-level: paid > billed → Paid (Overpayment)."""
    claim_data = _claim_data()
    payer_config = PAYER_CONFIG['Aetna Better Health']

    derive_claim_status(claim_data, '$100.00', '$120.00', payer_config)

    assert claim_data['Claim Status'] == PAID_OVERPAYMENT_STATUS


@patch('availity_app.automation.log_to_gui')
def test_remittance_zero_paid_marks_denied(mock_log):
    """Remittance payer: paid $0 → Denied (regression)."""
    claim_data = _claim_data()
    payer_config = PAYER_CONFIG['Villagecaremax']

    derive_claim_status(claim_data, '--', '$0.00', payer_config)

    assert claim_data['Claim Status'] == 'Denied'


@patch('availity_app.automation.log_to_gui')
def test_line_level_zero_billed_does_not_mark_denied(mock_log):
    """Line-level: paid $0 with zero billed does not override status."""
    claim_data = _claim_data('PENDING')
    payer_config = PAYER_CONFIG['Healthfirst']

    derive_claim_status(claim_data, '$0.00', '$0.00', payer_config)

    assert claim_data['Claim Status'] == 'PENDING'


@patch('availity_app.automation.log_to_gui')
def test_fully_paid_keeps_portal_status(mock_log):
    """Line-level: paid == billed keeps portal status."""
    claim_data = _claim_data('PAID')
    payer_config = PAYER_CONFIG['Anthem BCBS']

    derive_claim_status(claim_data, '$100.00', '$100.00', payer_config)

    assert claim_data['Claim Status'] == 'PAID'
