"""Gateway management tools — connect/disconnect/switch/list/status/test."""

from __future__ import annotations

import json
from typing import Any

from mcp.types import TextContent, Tool

from gateway.nifi_registry import ConnectionInfo, registry
from gateway.nifi_client_manager import client_manager, _build_client

TOOLS: list[Tool] = [
    Tool(
        name="connect_nifi",
        description="Register and connect to a NiFi instance. Provide name, url, auth_method and credentials.",
        inputSchema={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Connection name"},
                "url": {"type": "string", "description": "NiFi API base URL (e.g. https://nifi.example.com/nifi-api)"},
                "auth_method": {
                    "type": "string",
                    "enum": ["certificate_p12", "certificate_pem", "knox_token", "knox_cookie", "knox_passcode", "basic", "none"],
                    "description": "Authentication method",
                },
                "readonly": {"type": "boolean", "description": "Read-only mode (default true)", "default": True},
                "verify_ssl": {"type": "boolean", "description": "Verify SSL (default true)", "default": True},
                "knox_token": {"type": "string", "description": "Knox JWT token"},
                "knox_cookie": {"type": "string", "description": "Knox cookie"},
                "knox_passcode": {"type": "string", "description": "Knox passcode"},
                "knox_user": {"type": "string", "description": "Username for basic auth"},
                "knox_password": {"type": "string", "description": "Password for basic auth"},
                "knox_gateway_url": {"type": "string", "description": "Knox gateway URL"},
            },
            "required": ["name", "url"],
        },
    ),
    Tool(
        name="disconnect_nifi",
        description="Disconnect and remove a NiFi connection by name.",
        inputSchema={
            "type": "object",
            "properties": {"name": {"type": "string", "description": "Connection name"}},
            "required": ["name"],
        },
    ),
    Tool(
        name="switch_nifi",
        description="Switch the active NiFi connection for the current session.",
        inputSchema={
            "type": "object",
            "properties": {"name": {"type": "string", "description": "Connection name"}},
            "required": ["name"],
        },
    ),
    Tool(
        name="list_nifi_connections",
        description="List all registered NiFi connections with their status.",
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="get_server_status",
        description="Get MCP gateway status: active connections, sessions, default.",
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="test_nifi_connection",
        description="Test connectivity to a NiFi instance without saving.",
        inputSchema={
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "NiFi API base URL"},
                "auth_method": {"type": "string", "enum": ["certificate_p12", "certificate_pem", "knox_token", "knox_cookie", "knox_passcode", "basic", "none"]},
                "verify_ssl": {"type": "boolean", "default": True},
                "knox_token": {"type": "string"},
                "knox_cookie": {"type": "string"},
                "knox_passcode": {"type": "string"},
                "knox_user": {"type": "string"},
                "knox_password": {"type": "string"},
                "knox_gateway_url": {"type": "string"},
            },
            "required": ["url"],
        },
    ),
]


def _json_text(data: Any) -> list[TextContent]:
    return [TextContent(type="text", text=json.dumps(data, indent=2, ensure_ascii=False, default=str))]


async def handle(name: str, arguments: dict, session_id: str | None) -> list[TextContent]:
    if name == "connect_nifi":
        conn_name = arguments["name"].strip()
        url = arguments["url"].strip()
        if not conn_name or not url:
            return _json_text({"error": "name and url are required"})
        conn = ConnectionInfo(
            name=conn_name,
            url=url,
            auth_method=arguments.get("auth_method", "none"),
            readonly=arguments.get("readonly", True),
            verify_ssl=arguments.get("verify_ssl", True),
            knox_token=arguments.get("knox_token", ""),
            knox_cookie=arguments.get("knox_cookie", ""),
            knox_passcode=arguments.get("knox_passcode", ""),
            knox_user=arguments.get("knox_user", ""),
            knox_password=arguments.get("knox_password", ""),
            knox_gateway_url=arguments.get("knox_gateway_url", ""),
        )
        registry.add(conn)
        try:
            client_manager.connect(conn)
        except Exception as e:
            registry.remove(conn_name)
            return _json_text({"error": str(e)})
        return _json_text({"ok": True, "name": conn_name, "nifi_version": conn.nifi_version})

    if name == "disconnect_nifi":
        conn_name = arguments["name"].strip()
        removed = registry.remove(conn_name)
        if not removed:
            return _json_text({"error": f"'{conn_name}' not found"})
        client_manager.disconnect(conn_name)
        return _json_text({"ok": True})

    if name == "switch_nifi":
        conn_name = arguments["name"].strip()
        try:
            client_manager.switch(conn_name, session_id)
        except ValueError as e:
            return _json_text({"error": str(e)})
        if not session_id:
            registry.active = conn_name
            registry.save()
        return _json_text({"ok": True, "active": conn_name})

    if name == "list_nifi_connections":
        conns = registry.list_all()
        return _json_text([c.to_safe_dict() for c in conns])

    if name == "get_server_status":
        return _json_text(client_manager.get_status())

    if name == "test_nifi_connection":
        url = arguments["url"].strip()
        conn = ConnectionInfo(
            name="__test__",
            url=url,
            auth_method=arguments.get("auth_method", "none"),
            verify_ssl=arguments.get("verify_ssl", True),
            knox_token=arguments.get("knox_token", ""),
            knox_cookie=arguments.get("knox_cookie", ""),
            knox_passcode=arguments.get("knox_passcode", ""),
            knox_user=arguments.get("knox_user", ""),
            knox_password=arguments.get("knox_password", ""),
            knox_gateway_url=arguments.get("knox_gateway_url", ""),
        )
        try:
            client = _build_client(conn)
            info = client.get_version_info()
            version = info.get("about", {}).get("version", "unknown")
            client.session.close()
            return _json_text({"ok": True, "nifi_version": version})
        except Exception as e:
            return _json_text({"ok": False, "error": str(e)})

    return _json_text({"error": f"Unknown admin tool: {name}"})
