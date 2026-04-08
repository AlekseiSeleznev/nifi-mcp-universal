"""Tests for gateway.tools.admin — connect/disconnect/switch/list/status/test tools."""
from __future__ import annotations

import json
import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from gateway.tools import admin
from gateway.nifi_registry import ConnectionInfo


# ──────────────────────────────────────────────
#  Helpers
# ──────────────────────────────────────────────

def _parse(result) -> dict | list:
    return json.loads(result[0].text)


# ──────────────────────────────────────────────
#  connect_nifi
# ──────────────────────────────────────────────

class TestConnectNiFi:
    @pytest.mark.asyncio
    async def test_connect_success(self):
        mock_conn = ConnectionInfo(name="a", url="https://nifi/nifi-api", nifi_version="2.0.0")

        with patch("gateway.tools.admin.registry") as mock_registry, \
             patch("gateway.tools.admin.client_manager") as mock_mgr:
            mock_registry.get.return_value = mock_conn
            mock_mgr.connect.return_value = None

            result = await admin.handle("connect_nifi", {"name": "a", "url": "https://nifi/nifi-api"}, None)

        data = _parse(result)
        assert data["ok"] is True
        assert data["name"] == "a"

    @pytest.mark.asyncio
    async def test_connect_empty_name_returns_error(self):
        result = await admin.handle("connect_nifi", {"name": "", "url": "https://nifi"}, None)
        data = _parse(result)
        assert "error" in data

    @pytest.mark.asyncio
    async def test_connect_empty_url_returns_error(self):
        result = await admin.handle("connect_nifi", {"name": "a", "url": ""}, None)
        data = _parse(result)
        assert "error" in data

    @pytest.mark.asyncio
    async def test_connect_client_error_removes_registry_entry(self):
        with patch("gateway.tools.admin.registry") as mock_registry, \
             patch("gateway.tools.admin.client_manager") as mock_mgr:
            mock_mgr.connect.side_effect = Exception("Connection refused")

            result = await admin.handle("connect_nifi", {"name": "a", "url": "https://nifi"}, None)

        data = _parse(result)
        assert "error" in data
        mock_registry.remove.assert_called_once_with("a")


# ──────────────────────────────────────────────
#  disconnect_nifi
# ──────────────────────────────────────────────

class TestDisconnectNiFi:
    @pytest.mark.asyncio
    async def test_disconnect_success(self):
        conn = ConnectionInfo(name="a", url="https://nifi")
        with patch("gateway.tools.admin.registry") as mock_registry, \
             patch("gateway.tools.admin.client_manager") as mock_mgr:
            mock_registry.remove.return_value = conn
            result = await admin.handle("disconnect_nifi", {"name": "a"}, None)

        data = _parse(result)
        assert data["ok"] is True

    @pytest.mark.asyncio
    async def test_disconnect_not_found(self):
        with patch("gateway.tools.admin.registry") as mock_registry:
            mock_registry.remove.return_value = None
            result = await admin.handle("disconnect_nifi", {"name": "ghost"}, None)

        data = _parse(result)
        assert "error" in data


# ──────────────────────────────────────────────
#  switch_nifi
# ──────────────────────────────────────────────

class TestSwitchNiFi:
    @pytest.mark.asyncio
    async def test_switch_success_global(self):
        with patch("gateway.tools.admin.client_manager") as mock_mgr, \
             patch("gateway.tools.admin.registry") as mock_registry:
            result = await admin.handle("switch_nifi", {"name": "b"}, None)

        data = _parse(result)
        assert data["ok"] is True
        assert data["active"] == "b"

    @pytest.mark.asyncio
    async def test_switch_success_session(self):
        with patch("gateway.tools.admin.client_manager") as mock_mgr:
            result = await admin.handle("switch_nifi", {"name": "b"}, "sess1")

        data = _parse(result)
        assert data["ok"] is True

    @pytest.mark.asyncio
    async def test_switch_nonexistent_returns_error(self):
        with patch("gateway.tools.admin.client_manager") as mock_mgr:
            mock_mgr.switch.side_effect = ValueError("NiFi 'ghost' is not connected")
            result = await admin.handle("switch_nifi", {"name": "ghost"}, None)

        data = _parse(result)
        assert "error" in data


# ──────────────────────────────────────────────
#  list_nifi_connections
# ──────────────────────────────────────────────

class TestListNiFiConnections:
    @pytest.mark.asyncio
    async def test_list_empty(self):
        with patch("gateway.tools.admin.registry") as mock_registry:
            mock_registry.list_all.return_value = []
            result = await admin.handle("list_nifi_connections", {}, None)

        data = _parse(result)
        assert isinstance(data, list)
        assert len(data) == 0

    @pytest.mark.asyncio
    async def test_list_returns_safe_dicts(self):
        conn = ConnectionInfo(name="a", url="https://nifi", knox_token="secret")
        with patch("gateway.tools.admin.registry") as mock_registry:
            mock_registry.list_all.return_value = [conn]
            result = await admin.handle("list_nifi_connections", {}, None)

        data = _parse(result)
        assert len(data) == 1
        assert data[0]["knox_token"] == "***"


# ──────────────────────────────────────────────
#  get_server_status
# ──────────────────────────────────────────────

class TestGetServerStatus:
    @pytest.mark.asyncio
    async def test_returns_status_dict(self):
        status = {"connections": {}, "sessions": 0, "active_default": ""}
        with patch("gateway.tools.admin.client_manager") as mock_mgr:
            mock_mgr.get_status.return_value = status
            result = await admin.handle("get_server_status", {}, None)

        data = _parse(result)
        assert "connections" in data
        assert "sessions" in data


# ──────────────────────────────────────────────
#  test_nifi_connection
# ──────────────────────────────────────────────

class TestTestNiFiConnection:
    @pytest.mark.asyncio
    async def test_connection_success(self):
        mock_client = MagicMock()
        mock_client.get_version_info.return_value = {"about": {"version": "2.0.0"}}
        mock_client.session = MagicMock()

        with patch("gateway.tools.admin._build_client", return_value=mock_client):
            result = await admin.handle(
                "test_nifi_connection",
                {"url": "https://nifi/nifi-api"},
                None,
            )

        data = _parse(result)
        assert data["ok"] is True
        assert data["nifi_version"] == "2.0.0"

    @pytest.mark.asyncio
    async def test_connection_failure(self):
        with patch("gateway.tools.admin._build_client") as build_mock:
            build_mock.side_effect = Exception("Connection refused")
            result = await admin.handle(
                "test_nifi_connection",
                {"url": "https://unreachable/nifi-api"},
                None,
            )

        data = _parse(result)
        assert data["ok"] is False
        assert "error" in data


# ──────────────────────────────────────────────
#  Unknown tool
# ──────────────────────────────────────────────

class TestUnknownTool:
    @pytest.mark.asyncio
    async def test_unknown_returns_error(self):
        result = await admin.handle("nonexistent_tool", {}, None)
        data = _parse(result)
        assert "error" in data


# ──────────────────────────────────────────────
#  TOOLS list
# ──────────────────────────────────────────────

class TestAdminToolList:
    def test_tools_have_names(self):
        names = [t.name for t in admin.TOOLS]
        assert "connect_nifi" in names
        assert "disconnect_nifi" in names
        assert "switch_nifi" in names
        assert "list_nifi_connections" in names
        assert "get_server_status" in names
        assert "test_nifi_connection" in names

    def test_connect_nifi_requires_name_and_url(self):
        tool = next(t for t in admin.TOOLS if t.name == "connect_nifi")
        required = tool.inputSchema.get("required", [])
        assert "name" in required
        assert "url" in required
