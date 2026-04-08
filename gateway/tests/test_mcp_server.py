"""Tests for gateway.mcp_server — list_tools, call_tool dispatch, error handling."""
from __future__ import annotations

import json
import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from mcp.types import TextContent

from gateway.tools import admin, read_tools, write_tools
import gateway.mcp_server as mcp_mod


# ──────────────────────────────────────────────
#  Tool dispatch table
# ──────────────────────────────────────────────

class TestToolDispatch:
    def test_all_admin_tools_dispatched_to_admin(self):
        for tool in admin.TOOLS:
            assert mcp_mod._TOOL_DISPATCH.get(tool.name) is admin

    def test_all_read_tools_dispatched_to_read_tools(self):
        for tool in read_tools.TOOLS:
            assert mcp_mod._TOOL_DISPATCH.get(tool.name) is read_tools

    def test_all_write_tools_dispatched_to_write_tools(self):
        for tool in write_tools.TOOLS:
            assert mcp_mod._TOOL_DISPATCH.get(tool.name) is write_tools

    def test_total_tools_in_dispatch(self):
        total = len(admin.TOOLS) + len(read_tools.TOOLS) + len(write_tools.TOOLS)
        assert len(mcp_mod._TOOL_DISPATCH) == total


# ──────────────────────────────────────────────
#  _get_session_id — graceful fallback
# ──────────────────────────────────────────────

class TestGetSessionId:
    def test_returns_none_when_no_context(self):
        # When there's no request context, must return None gracefully
        result = mcp_mod._get_session_id()
        assert result is None


# ──────────────────────────────────────────────
#  list_tools (via the registered handler)
# ──────────────────────────────────────────────

class TestListTools:
    @pytest.mark.asyncio
    async def test_list_tools_returns_all_tools(self):
        # Access the handler registered on the server
        # The server wraps handlers; call via the module's function directly
        from gateway.mcp_server import list_tools
        tools = await list_tools()
        tool_names = [t.name for t in tools]

        # Spot-check key tools from each module
        assert "connect_nifi" in tool_names
        assert "get_nifi_version" in tool_names
        assert "start_processor" in tool_names

    @pytest.mark.asyncio
    async def test_list_tools_no_duplicates(self):
        from gateway.mcp_server import list_tools
        tools = await list_tools()
        names = [t.name for t in tools]
        assert len(names) == len(set(names)), "Duplicate tool names detected"


# ──────────────────────────────────────────────
#  call_tool dispatch
# ──────────────────────────────────────────────

class TestCallTool:
    @pytest.mark.asyncio
    async def test_unknown_tool_returns_error(self):
        from gateway.mcp_server import call_tool
        result = await call_tool("totally_unknown_tool", {})
        assert len(result) == 1
        assert "Unknown tool" in result[0].text

    @pytest.mark.asyncio
    async def test_admin_tool_dispatched(self):
        from gateway.mcp_server import call_tool
        with patch("gateway.mcp_server.admin") as mock_admin, \
             patch("gateway.mcp_server._get_session_id", return_value=None), \
             patch.dict(mcp_mod._TOOL_DISPATCH, {"connect_nifi": mock_admin}):
            mock_admin.handle = AsyncMock(return_value=[TextContent(type="text", text='{"ok": true}')])
            result = await call_tool("connect_nifi", {"name": "x", "url": "https://nifi"})
        mock_admin.handle.assert_called_once()

    @pytest.mark.asyncio
    async def test_read_tool_dispatched_with_client(self):
        from gateway.mcp_server import call_tool
        mock_client = MagicMock()
        mock_conn = MagicMock()
        mock_conn.readonly = True

        with patch("gateway.mcp_server._get_session_id", return_value=None), \
             patch("gateway.mcp_server.client_manager") as mock_mgr, \
             patch("gateway.mcp_server.read_tools") as mock_read, \
             patch.dict(mcp_mod._TOOL_DISPATCH, {"get_nifi_version": mock_read}):
            mock_mgr.get_client.return_value = mock_client
            mock_mgr.get_connection_info.return_value = mock_conn
            mock_read.handle = AsyncMock(return_value=[TextContent(type="text", text='{"version": "2.0.0"}')])
            result = await call_tool("get_nifi_version", {})

        mock_read.handle.assert_called_once()

    @pytest.mark.asyncio
    async def test_write_tool_dispatched_with_readonly_flag(self):
        from gateway.mcp_server import call_tool
        mock_client = MagicMock()
        mock_conn = MagicMock()
        mock_conn.readonly = False

        with patch("gateway.mcp_server._get_session_id", return_value=None), \
             patch("gateway.mcp_server.client_manager") as mock_mgr, \
             patch("gateway.mcp_server.write_tools") as mock_write, \
             patch.dict(mcp_mod._TOOL_DISPATCH, {"start_processor": mock_write}):
            mock_mgr.get_client.return_value = mock_client
            mock_mgr.get_connection_info.return_value = mock_conn
            mock_write.handle = AsyncMock(return_value=[TextContent(type="text", text='{}')])
            await call_tool("start_processor", {"processor_id": "p1", "version": 0})

        call_args = mock_write.handle.call_args
        assert call_args[0][3] is False  # readonly=False passed

    @pytest.mark.asyncio
    async def test_exception_in_tool_returns_error_text(self):
        from gateway.mcp_server import call_tool
        with patch("gateway.mcp_server._get_session_id", return_value=None), \
             patch("gateway.mcp_server.client_manager") as mock_mgr, \
             patch("gateway.mcp_server.read_tools") as mock_read, \
             patch.dict(mcp_mod._TOOL_DISPATCH, {"get_nifi_version": mock_read}):
            mock_mgr.get_client.side_effect = RuntimeError("No active NiFi connection")
            result = await call_tool("get_nifi_version", {})

        assert "Error" in result[0].text

    @pytest.mark.asyncio
    async def test_readonly_none_conn_info_defaults_true(self):
        """When get_connection_info returns None, readonly should default to True."""
        from gateway.mcp_server import call_tool
        mock_client = MagicMock()

        with patch("gateway.mcp_server._get_session_id", return_value=None), \
             patch("gateway.mcp_server.client_manager") as mock_mgr, \
             patch("gateway.mcp_server.write_tools") as mock_write, \
             patch.dict(mcp_mod._TOOL_DISPATCH, {"start_processor": mock_write}):
            mock_mgr.get_client.return_value = mock_client
            mock_mgr.get_connection_info.return_value = None
            mock_write.handle = AsyncMock(return_value=[TextContent(type="text", text='{}')])
            await call_tool("start_processor", {"processor_id": "p1", "version": 0})

        call_args = mock_write.handle.call_args
        assert call_args[0][3] is True  # readonly=True (default)
