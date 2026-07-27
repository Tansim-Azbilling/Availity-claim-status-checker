"""Tests for CDP port availability helpers."""
from unittest.mock import patch

from availity_app import state
from availity_app.driver import (
    ensure_edge_with_cdp,
    is_cdp_available,
    is_cdp_port_free,
)


def test_is_cdp_available_when_version_endpoint_responds():
    with patch(
        "availity_app.driver._cdp_version_info",
        return_value={"webSocketDebuggerUrl": "ws://x"},
    ):
        assert is_cdp_available() is True


def test_is_cdp_available_when_version_endpoint_missing():
    with patch("availity_app.driver._cdp_version_info", return_value=None):
        assert is_cdp_available() is False


def test_is_cdp_port_free_when_tcp_port_closed():
    with patch("availity_app.driver._is_cdp_port_open", return_value=False):
        assert is_cdp_port_free() is True


def test_is_cdp_port_free_when_tcp_port_open():
    with patch("availity_app.driver._is_cdp_port_open", return_value=True):
        assert is_cdp_port_free() is False


def test_ensure_edge_with_cdp_fails_when_port_blocked():
    with patch("availity_app.driver.is_cdp_available", return_value=False):
        with patch("availity_app.driver._is_cdp_port_blocked", return_value=True):
            with patch("availity_app.driver._prepare_clean_edge_launch") as prep_mock:
                assert ensure_edge_with_cdp() is False
                prep_mock.assert_not_called()


def test_ensure_edge_with_cdp_fails_when_port_still_occupied_after_edge_close():
    with patch("availity_app.driver.is_cdp_available", return_value=False):
        with patch("availity_app.driver._is_cdp_port_blocked", return_value=False):
            with patch("availity_app.driver._prepare_clean_edge_launch", return_value=True):
                with patch("availity_app.driver.is_cdp_port_free", return_value=False):
                    with patch(
                        "availity_app.driver._launch_managed_edge_with_cdp"
                    ) as launch_mock:
                        state.managed_edge_process = None
                        assert ensure_edge_with_cdp() is False
                        launch_mock.assert_not_called()
