"""Tests for save performance and async queue coalescing."""
import tempfile
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from availity_app import async_save
from availity_app.automation import (
    _dataframe_multiline_excel_rows,
    _write_results_file,
)
from availity_app.constants import OUTPUT_COLUMNS, REQUIRED_COLUMNS, STATUS_COLUMNS


def _sample_export_df(rows=3, multiline_row=1):
    data = {
        'AltPatientID': ['M1'] * rows,
        'PatientName': ['Doe, Jane'] * rows,
        'DOB': ['01/01/1990'] * rows,
        'StartDate': ['01/01/2025'] * rows,
        'EndDate': ['01/31/2025'] * rows,
        'InvoiceNumber': [f'INV{i}' for i in range(rows)],
        'VisitDate': ['01/05/2025'] * rows,
    }
    for col in OUTPUT_COLUMNS + STATUS_COLUMNS:
        data[col] = [''] * rows
    data['Claim Status'][multiline_row] = '1. Paid\n2. Denied'
    return pd.DataFrame(data)


def test_dataframe_multiline_excel_rows():
    df = _sample_export_df(rows=3, multiline_row=1)
    assert _dataframe_multiline_excel_rows(df) == [3]


def test_progress_save_skips_openpyxl_finalize():
    df = _sample_export_df()
    with tempfile.TemporaryDirectory() as tmp:
        with patch('availity_app.automation._finalize_output_workbook') as mock_finalize:
            with patch('openpyxl.load_workbook') as mock_load:
                path = _write_results_file(df, tmp, finalize=False)
        assert path is not None
        mock_finalize.assert_not_called()
        mock_load.assert_not_called()


def test_finalize_save_skips_openpyxl_finalize_when_formatting_disabled():
    df = _sample_export_df()
    with tempfile.TemporaryDirectory() as tmp:
        with patch('availity_app.automation._finalize_output_workbook') as mock_finalize:
            with patch('openpyxl.load_workbook') as mock_load:
                path = _write_results_file(df, tmp, finalize=True)
        assert path is not None
        mock_finalize.assert_not_called()
        mock_load.assert_not_called()


def test_enqueue_save_coalesces_progress_snapshots():
    async_save._queued_item = None
    async_save._worker_processing = False
    async_save._worker_thread = None

    with patch.object(async_save, 'start_save_worker'):
        folder = '/tmp/out'
        async_save.enqueue_save(pd.DataFrame({'a': [1]}), folder, finalize=False)
        async_save.enqueue_save(pd.DataFrame({'a': [2]}), folder, finalize=False)
        async_save.enqueue_save(pd.DataFrame({'a': [3]}), folder, finalize=False)

    assert async_save._queued_item is not None
    assert async_save._queued_item[0]['a'].iloc[0] == 3
    assert async_save._queued_item[2] is False


def test_enqueue_save_finalize_replaces_progress():
    async_save._queued_item = None
    async_save._worker_processing = False

    with patch.object(async_save, 'start_save_worker'):
        folder = '/tmp/out'
        async_save.enqueue_save(pd.DataFrame({'a': [1]}), folder, finalize=False)
        async_save.enqueue_save(pd.DataFrame({'a': [9]}), folder, finalize=True)

    assert async_save._queued_item[0]['a'].iloc[0] == 9
    assert async_save._queued_item[2] is True


def test_enqueue_save_does_not_replace_pending_finalize_with_progress():
    async_save._queued_item = None
    async_save._worker_processing = False

    with patch.object(async_save, 'start_save_worker'):
        folder = '/tmp/out'
        async_save.enqueue_save(pd.DataFrame({'a': [9]}), folder, finalize=True)
        async_save.enqueue_save(pd.DataFrame({'a': [1]}), folder, finalize=False)

    assert async_save._queued_item[0]['a'].iloc[0] == 9
    assert async_save._queued_item[2] is True
