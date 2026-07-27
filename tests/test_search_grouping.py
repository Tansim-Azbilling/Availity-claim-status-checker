"""Tests for search grouping helpers."""
import pandas as pd

from availity_app.constants import PAYER_CONFIG
from availity_app.search_grouping import (
    build_consecutive_search_groups,
    row_eligible_for_grouping,
    search_group_key,
)


def _sample_df():
    return pd.DataFrame([
        {
            'AltPatientID': 'M1',
            'Last_Name': 'Doe',
            'First_Name': 'Jane',
            'DOB': '01/01/1990',
            'StartDate': '01/01/2025',
            'EndDate': '01/31/2025',
            'InvoiceNumber': 'INV1',
            'VisitDate': '01/05/2025',
        },
        {
            'AltPatientID': 'M1',
            'Last_Name': 'Doe',
            'First_Name': 'Jane',
            'DOB': '01/01/1990',
            'StartDate': '01/01/2025',
            'EndDate': '01/31/2025',
            'InvoiceNumber': 'INV2',
            'VisitDate': '01/10/2025',
        },
        {
            'AltPatientID': 'M2',
            'Last_Name': 'Smith',
            'First_Name': 'John',
            'DOB': '02/02/1985',
            'StartDate': '02/01/2025',
            'EndDate': '02/28/2025',
            'InvoiceNumber': 'INV3',
            'VisitDate': '02/05/2025',
        },
    ])


def test_search_group_key_same_member():
    df = _sample_df()
    assert search_group_key(df, 0) == search_group_key(df, 1)
    assert search_group_key(df, 0) != search_group_key(df, 2)


def test_build_consecutive_groups():
    df = _sample_df()
    payer = PAYER_CONFIG['Healthfirst']
    groups = build_consecutive_search_groups([0, 1, 2], df, payer)
    assert groups == [[0, 1], [2]]


def test_ineligible_row_is_singleton_group():
    df = _sample_df()
    df.at[0, 'InvoiceNumber'] = ''
    payer = PAYER_CONFIG['Healthfirst']
    groups = build_consecutive_search_groups([0, 1], df, payer)
    assert groups == [[0], [1]]


def test_row_eligible_requires_invoice_and_dob():
    df = _sample_df()
    assert row_eligible_for_grouping(df, 0) is True
    df.at[0, 'DOB'] = 'Not Found'
    assert row_eligible_for_grouping(df, 0) is False
