"""Tests for gateway.nifi_client_manager — URL normalisation, session routing, lifecycle."""
from __future__ import annotations

import time
import pytest
from unittest.mock import MagicMock, patch

from gateway.nifi_client_manager import (
    NiFiClientManager,
    SessionState,
    _normalize_nifi_url,
    _build_client,
)
from gateway.nifi_registry import ConnectionInfo, ConnectionRegistry
from gateway.nifi.client import NiFiClient


# ──────────────────────────────────────────────
#  _normalize_nifi_url
# ──────────────────────────────────────────────

class TestNormalizeNiFiUrl:
    def test_bare_host_port(self):
        assert _normalize_nifi_url("https://host:8080") == "https://host:8080/nifi-api"

    def test_trailing_slash_stripped(self):
        assert _normalize_nifi_url("https://host:8080/") == "https://host:8080/nifi-api"

    def test_nifi_path_converted(self):
        assert _normalize_nifi_url("https://host:8080/nifi") == "https://host:8080/nifi-api"

    def test_nifi_api_path_unchanged(self):
        assert _normalize_nifi_url("https://host:8080/nifi-api") == "https://host:8080/nifi-api"

    def test_nifi_api_trailing_slash(self):
        assert _normalize_nifi_url("https://host:8080/nifi-api/") == "https://host:8080/nifi-api"

    def test_complex_path(self):
        url = "https://host/prefix/nifi"
        result = _normalize_nifi_url(url)
        assert result.endswith("/nifi-api")


# ──────────────────────────────────────────────
#  NiFiClientManager — connect / disconnect
# ──────────────────────────────────────────────

def _make_mock_client():
    client = MagicMock(spec=NiFiClient)
    client.get_version_info.return_value = {"about": {"version": "2.0.0"}}
    client.session = MagicMock()
    return client


def _make_manager_with_registry():
    mgr = NiFiClientManager()
    reg = ConnectionRegistry()
    return mgr, reg


class TestClientManagerConnect:
    def test_connect_sets_connected_flag(self):
        mgr = NiFiClientManager()
        conn = ConnectionInfo(name="a", url="https://nifi/nifi-api")

        mock_client = _make_mock_client()
        with patch("gateway.nifi_client_manager._build_client", return_value=mock_client):
            mgr.connect(conn)

        assert conn.connected is True
        assert "a" in mgr._clients

    def test_connect_captures_version(self):
        mgr = NiFiClientManager()
        conn = ConnectionInfo(name="a", url="https://nifi/nifi-api")

        mock_client = _make_mock_client()
        with patch("gateway.nifi_client_manager._build_client", return_value=mock_client):
            mgr.connect(conn)

        assert conn.nifi_version == "2.0.0"

    def test_connect_idempotent(self):
        mgr = NiFiClientManager()
        conn = ConnectionInfo(name="a", url="https://nifi/nifi-api")

        mock_client = _make_mock_client()
        with patch("gateway.nifi_client_manager._build_client", return_value=mock_client) as build_mock:
            mgr.connect(conn)
            mgr.connect(conn)  # second call — should skip
            assert build_mock.call_count == 1

    def test_connect_version_failure_uses_unknown(self):
        mgr = NiFiClientManager()
        conn = ConnectionInfo(name="a", url="https://nifi/nifi-api")

        mock_client = _make_mock_client()
        mock_client.get_version_info.side_effect = Exception("unreachable")
        with patch("gateway.nifi_client_manager._build_client", return_value=mock_client):
            mgr.connect(conn)

        assert conn.nifi_version == "unknown"
        assert conn.connected is True  # still stored

    def test_disconnect_removes_client(self):
        mgr = NiFiClientManager()
        conn = ConnectionInfo(name="a", url="https://nifi/nifi-api")

        mock_client = _make_mock_client()
        with patch("gateway.nifi_client_manager._build_client", return_value=mock_client):
            mgr.connect(conn)

        with patch("gateway.nifi_client_manager.registry") as mock_registry:
            mock_registry.get.return_value = conn
            mgr.disconnect("a")

        assert "a" not in mgr._clients
        assert conn.connected is False

    def test_disconnect_cleans_sessions(self):
        mgr = NiFiClientManager()
        conn = ConnectionInfo(name="a", url="https://nifi/nifi-api")
        mock_client = _make_mock_client()

        with patch("gateway.nifi_client_manager._build_client", return_value=mock_client):
            mgr.connect(conn)

        mgr._sessions["sess1"] = SessionState(conn_name="a")
        mgr._sessions["sess2"] = SessionState(conn_name="b")  # unrelated

        with patch("gateway.nifi_client_manager.registry") as mock_registry:
            mock_registry.get.return_value = conn
            mgr.disconnect("a")

        assert "sess1" not in mgr._sessions
        assert "sess2" in mgr._sessions

    def test_close_all(self):
        mgr = NiFiClientManager()
        for name in ("a", "b"):
            conn = ConnectionInfo(name=name, url="https://nifi/nifi-api")
            mock_client = _make_mock_client()
            with patch("gateway.nifi_client_manager._build_client", return_value=mock_client):
                mgr.connect(conn)

        with patch("gateway.nifi_client_manager.registry") as mock_registry:
            mock_registry.get.return_value = None
            mgr.close_all()

        assert len(mgr._clients) == 0


class TestSessionRouting:
    def test_get_active_name_no_session(self):
        mgr = NiFiClientManager()
        with patch("gateway.nifi_client_manager.registry") as mock_registry:
            mock_registry.active = "default"
            name = mgr.get_active_name(None)
        assert name == "default"

    def test_get_active_name_with_session(self):
        mgr = NiFiClientManager()
        mgr._sessions["sess1"] = SessionState(conn_name="myconn")
        name = mgr.get_active_name("sess1")
        assert name == "myconn"

    def test_get_active_name_unknown_session_falls_back(self):
        mgr = NiFiClientManager()
        with patch("gateway.nifi_client_manager.registry") as mock_registry:
            mock_registry.active = "global"
            name = mgr.get_active_name("unknown-session")
        assert name == "global"

    def test_switch_creates_session(self):
        mgr = NiFiClientManager()
        conn = ConnectionInfo(name="a", url="https://nifi/nifi-api")
        mock_client = _make_mock_client()
        with patch("gateway.nifi_client_manager._build_client", return_value=mock_client):
            mgr.connect(conn)
        mgr.switch("a", session_id="sess1")
        assert mgr._sessions["sess1"].conn_name == "a"

    def test_switch_nonexistent_raises(self):
        mgr = NiFiClientManager()
        with pytest.raises(ValueError, match="not connected"):
            mgr.switch("ghost", session_id="sess1")

    def test_get_client_no_connection_raises(self):
        mgr = NiFiClientManager()
        with patch("gateway.nifi_client_manager.registry") as mock_registry:
            mock_registry.active = ""
            with pytest.raises(RuntimeError, match="No active NiFi connection"):
                mgr.get_client(None)

    def test_get_client_connected(self):
        mgr = NiFiClientManager()
        conn = ConnectionInfo(name="a", url="https://nifi/nifi-api")
        mock_client = _make_mock_client()

        with patch("gateway.nifi_client_manager._build_client", return_value=mock_client):
            mgr.connect(conn)

        with patch("gateway.nifi_client_manager.registry") as mock_registry:
            mock_registry.active = "a"
            client = mgr.get_client(None)

        assert client is mock_client


class TestSessionCleanup:
    def test_cleanup_removes_expired_sessions(self):
        mgr = NiFiClientManager()
        mgr._sessions["old"] = SessionState(conn_name="a")
        mgr._sessions["old"].last_access = time.time() - 999999

        from gateway.config import settings
        old_timeout = settings.session_timeout
        settings.session_timeout = 1  # 1 second

        removed = mgr.cleanup_sessions()
        settings.session_timeout = old_timeout

        assert removed == 1
        assert "old" not in mgr._sessions

    def test_cleanup_keeps_fresh_sessions(self):
        mgr = NiFiClientManager()
        mgr._sessions["fresh"] = SessionState(conn_name="a")  # last_access = now
        removed = mgr.cleanup_sessions()
        assert removed == 0
        assert "fresh" in mgr._sessions


class TestGetStatus:
    def test_get_status_empty(self):
        mgr = NiFiClientManager()
        with patch("gateway.nifi_client_manager.registry") as mock_registry:
            mock_registry.active = ""
            status = mgr.get_status()
        assert "connections" in status
        assert "sessions" in status
        assert "active_default" in status

    def test_get_status_with_connection(self):
        mgr = NiFiClientManager()
        conn = ConnectionInfo(name="a", url="https://nifi/nifi-api", auth_method="basic", readonly=False)
        mock_client = _make_mock_client()

        with patch("gateway.nifi_client_manager._build_client", return_value=mock_client):
            mgr.connect(conn)

        with patch("gateway.nifi_client_manager.registry") as mock_registry:
            mock_registry.active = "a"
            mock_registry.get.return_value = conn
            status = mgr.get_status()

        assert "a" in status["connections"]
        assert status["connections"]["a"]["auth_method"] == "basic"
        assert status["connections"]["a"]["readonly"] is False
