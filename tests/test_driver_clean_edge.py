"""Tests for clean Edge restart before CDP launch."""
from unittest.mock import MagicMock, patch

from availity_app import state
from availity_app.driver import (
    _prepare_clean_edge_launch,
    ensure_edge_with_cdp,
)


def test_prepare_clean_edge_launch_closes_running_edge():
    with patch("availity_app.driver._edge_processes_running", side_effect=[True, False]):
        with patch("availity_app.driver._close_all_edge_processes") as close_mock:
            with patch("availity_app.driver._wait_for_edge_exit", return_value=True):
                assert _prepare_clean_edge_launch() is True
                close_mock.assert_called_once()


def test_prepare_clean_edge_launch_fails_when_edge_wont_exit():
    with patch("availity_app.driver._edge_processes_running", return_value=True):
        with patch("availity_app.driver._close_all_edge_processes"):
            with patch("availity_app.driver._wait_for_edge_exit", return_value=False):
                assert _prepare_clean_edge_launch() is False


def test_prepare_clean_edge_launch_noop_when_edge_not_running():
    state.managed_edge_process = MagicMock()
    state.browser_owned_by_app = True
    with patch("availity_app.driver._edge_processes_running", return_value=False):
        assert _prepare_clean_edge_launch() is True
        assert state.managed_edge_process is None
        assert state.browser_owned_by_app is False


def test_ensure_edge_with_cdp_reuses_existing_cdp():
    with patch("availity_app.driver._cdp_version_info", return_value={"webSocketDebuggerUrl": "ws://x"}):
        with patch("availity_app.driver._prepare_clean_edge_launch") as prep_mock:
            assert ensure_edge_with_cdp() is True
            prep_mock.assert_not_called()


def test_ensure_edge_with_cdp_closes_edge_before_launch():
    with patch("availity_app.driver._cdp_version_info", return_value=None):
        with patch("availity_app.driver._prepare_clean_edge_launch", return_value=True):
            with patch("availity_app.driver._launch_managed_edge_with_cdp", return_value=True) as launch_mock:
                state.managed_edge_process = None
                assert ensure_edge_with_cdp() is True
                launch_mock.assert_called_once()
