"""Tests for session cleanup in NiFiClientManager."""
from __future__ import annotations

import time
import pytest
from unittest.mock import MagicMock, patch

from gateway.nifi_client_manager import NiFiClientManager, SessionState
from gateway.nifi_registry import ConnectionInfo, ConnectionRegistry


def _make_manager_with_connections(*names: str) -> NiFiClientManager:
    """Create a NiFiClientManager with pre-connected mock clients."""
    mgr = NiFiClientManager()
    for name in names:
        mock_client = MagicMock()
        mock_client.session = MagicMock()
        mgr._clients[name] = mock_client
    return mgr


class TestSessionCleanupAdvanced:
    def test_cleanup_returns_count_of_removed(self):
        mgr = _make_manager_with_connections("a")
        now = time.time()
        # 3 expired sessions
        mgr._sessions = {
            "old1": SessionState(conn_name="a", last_access=now - 100000),
            "old2": SessionState(conn_name="a", last_access=now - 100000),
            "old3": SessionState(conn_name="a", last_access=now - 100000),
        }
        removed = mgr.cleanup_sessions()
        assert removed == 3

    def test_cleanup_leaves_active_sessions_untouched(self):
        mgr = _make_manager_with_connections("a")
        now = time.time()
        mgr._sessions = {
            "active": SessionState(conn_name="a", last_access=now - 60),
        }
        removed = mgr.cleanup_sessions()
        assert removed == 0
        assert "active" in mgr._sessions

    def test_cleanup_mixed_sessions(self):
        mgr = _make_manager_with_connections("a")
        now = time.time()
        mgr._sessions = {
            "fresh": SessionState(conn_name="a", last_access=now - 100),
            "stale": SessionState(conn_name="a", last_access=now - 100000),
        }
        removed = mgr.cleanup_sessions()
        assert removed == 1
        assert "fresh" in mgr._sessions
        assert "stale" not in mgr._sessions

    def test_cleanup_empty_sessions_returns_zero(self):
        mgr = _make_manager_with_connections()
        assert mgr.cleanup_sessions() == 0

    def test_last_access_updated_on_get_active(self):
        mgr = _make_manager_with_connections("a")
        old_time = time.time() - 1000
        mgr._sessions["sess1"] = SessionState(conn_name="a", last_access=old_time)

        mgr.get_active_name("sess1")
        new_time = mgr._sessions["sess1"].last_access
        assert new_time > old_time


class TestClientManagerStatus:
    def test_status_shows_all_connections(self):
        mgr = _make_manager_with_connections("prod", "dev")
        with patch("gateway.nifi_client_manager.registry") as mock_reg:
            mock_reg.active = "prod"
            prod_conn = ConnectionInfo(name="prod", url="https://prod.nifi/nifi-api", auth_method="basic", readonly=False, nifi_version="2.0.0")
            dev_conn = ConnectionInfo(name="dev", url="https://dev.nifi/nifi-api", auth_method="none", readonly=True, nifi_version="1.23.2")
            mock_reg.get.side_effect = lambda n: {"prod": prod_conn, "dev": dev_conn}.get(n)
            status = mgr.get_status()

        assert "prod" in status["connections"]
        assert "dev" in status["connections"]
        assert status["connections"]["prod"]["readonly"] is False
        assert status["connections"]["dev"]["readonly"] is True

    def test_status_sessions_count(self):
        mgr = _make_manager_with_connections("a")
        mgr._sessions["s1"] = SessionState(conn_name="a")
        mgr._sessions["s2"] = SessionState(conn_name="a")
        with patch("gateway.nifi_client_manager.registry") as mock_reg:
            mock_reg.active = "a"
            mock_reg.get.return_value = ConnectionInfo(name="a", url="https://nifi", auth_method="none", readonly=True)
            status = mgr.get_status()
        assert status["sessions"] == 2
