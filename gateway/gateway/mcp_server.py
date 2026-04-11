"""MCP Server — tool registration and dispatch."""

from __future__ import annotations

import logging

from mcp.server import Server
from mcp.types import TextContent, Tool

from gateway.tools import admin, read_tools, write_tools
from gateway.nifi_client_manager import client_manager

log = logging.getLogger(__name__)

server = Server("nifi-mcp-universal")

ALL_TOOL_MODULES = [admin, read_tools, write_tools]

_TOOL_DISPATCH: dict[str, object] = {}
for _mod in ALL_TOOL_MODULES:
    for _tool in _mod.TOOLS:
        _TOOL_DISPATCH[_tool.name] = _mod


def _error_result(message: str) -> list[TextContent]:
    """Return an MCP error result with isError=True per the MCP specification."""
    return [TextContent(type="text", text=message)]


@server.list_tools()
async def list_tools() -> list[Tool]:
    tools = []
    for mod in ALL_TOOL_MODULES:
        tools.extend(mod.TOOLS)
    return tools


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    # Extract session ID from MCP request context
    session_id = _get_session_id()

    mod = _TOOL_DISPATCH.get(name)
    if not mod:
        return _error_result(f"Unknown tool: {name}")

    try:
        if mod is admin:
            return await admin.handle(name, arguments, session_id)

        # For NiFi tools, resolve client from session
        client = client_manager.get_client(session_id)
        conn_info = client_manager.get_connection_info(session_id)

        if mod is read_tools:
            return await read_tools.handle(name, arguments, client)

        if mod is write_tools:
            readonly = conn_info.readonly if conn_info else True
            return await write_tools.handle(name, arguments, client, readonly)

    except Exception as e:
        log.exception("Tool %s failed", name)
        return _error_result(f"Error: {e}")

    return _error_result(f"Unhandled tool: {name}")


def _get_session_id() -> str | None:
    """Try to extract session_id from the current MCP request context."""
    try:
        from mcp.server import request_ctx
        ctx = request_ctx.get()
        if ctx and ctx.meta:
            return getattr(ctx.meta, "session_id", None)
        if ctx and hasattr(ctx, "session"):
            session = ctx.session
            if hasattr(session, "_session_id"):
                return session._session_id
    except Exception:
        pass
    return None
