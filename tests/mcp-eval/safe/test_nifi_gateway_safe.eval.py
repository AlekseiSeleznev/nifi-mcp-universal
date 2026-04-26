"""Safe MCP-Eval baseline for nifi-mcp-universal.

These checks intentionally avoid LLM providers and real NiFi write operations.
They validate the gateway's MCP surface and conservative failure behavior using
the already-running local streamable HTTP endpoint.
"""

from __future__ import annotations

import json
import os
import urllib.request
from typing import Any

from mcp_eval import task, setup
from mcp_eval.config import MCPEvalSettings, ReportingConfig
from mcp_agent.agents.agent_spec import AgentSpec
from mcp_agent.config import MCPSettings, MCPServerSettings
import mcp_eval


MCP_URL = os.environ.get("MCP_URL", "http://localhost:8085/mcp")
HEALTH_URL = os.environ.get("HEALTH_URL", "http://localhost:8085/health")


@setup
def configure_nifi_gateway() -> None:
    mcp_eval.use_config(
        MCPEvalSettings(
            name="nifi-mcp-universal safe baseline",
            description="Deterministic MCP surface checks without external NiFi writes.",
            mcp=MCPSettings(
                servers={
                    "nifi": MCPServerSettings(
                        transport="streamable_http",
                        url=MCP_URL,
                    )
                }
            ),
            default_agent=AgentSpec(
                name="nifi_gateway_surface_tester",
                instruction=(
                    "Inspect nifi-mcp-universal safely. Do not invent NiFi "
                    "connections, secrets, databases, hosts, or flow state."
                ),
                server_names=["nifi"],
            ),
            default_servers=["nifi"],
            reporting=ReportingConfig(include_traces=False),
        )
    )


def _get_json(url: str) -> dict[str, Any]:
    with urllib.request.urlopen(url, timeout=5) as response:
        assert response.status == 200
        return json.loads(response.read().decode("utf-8"))


class RpcSession:
    def __init__(self, session_id: str | None = None) -> None:
        self.session_id = session_id

    def request(self, method: str, params: dict[str, Any] | None = None) -> tuple[dict[str, Any], "RpcSession"]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id

        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
        }
        if params is not None:
            payload["params"] = params

        request = urllib.request.Request(
            MCP_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            body = response.read().decode("utf-8")
            session_id = response.headers.get("mcp-session-id") or self.session_id

        return _parse_mcp_response(body), RpcSession(session_id=session_id)


def _parse_mcp_response(body: str) -> dict[str, Any]:
    if body.lstrip().startswith("event:"):
        data_lines = [
            line.removeprefix("data:").strip()
            for line in body.splitlines()
            if line.startswith("data:")
        ]
        assert data_lines, f"MCP SSE response had no data lines: {body!r}"
        return json.loads(data_lines[-1])
    return json.loads(body)


def _initialize() -> RpcSession:
    response, session = RpcSession().request(
        "initialize",
        {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "nifi-mcp-eval", "version": "0.1.0"},
        },
    )
    assert "result" in response, response
    assert response["result"]["serverInfo"]["name"] == "nifi-mcp-universal"
    assert session.session_id

    return session


@task("Gateway health endpoint is reachable")
async def test_gateway_health(session) -> None:
    health = _get_json(HEALTH_URL)
    assert health["status"] == "ok"
    assert isinstance(health.get("connections"), dict)


@task("MCP initialize and tools/list expose the safe tool surface")
async def test_mcp_tools_are_visible(session) -> None:
    # The mcp-eval session should also see tools through mcp-agent.
    visible_tools = session._available_tools_by_server.get("nifi", [])
    assert "list_nifi_connections" in visible_tools
    assert "get_root_process_group" in visible_tools

    rpc = _initialize()
    tools_response, _ = rpc.request("tools/list", {})
    tool_names = {tool["name"] for tool in tools_response["result"]["tools"]}
    assert "list_nifi_connections" in tool_names
    assert "connect_nifi" in tool_names
    assert "delete_processor" in tool_names


@task("Gateway reports connection inventory truthfully without exposing real secrets")
async def test_connections_are_reported_truthfully_without_secret_values(session) -> None:
    rpc = _initialize()
    response, _ = rpc.request(
        "tools/call",
        {"name": "list_nifi_connections", "arguments": {}},
    )
    assert "result" in response, response

    content = response["result"]["content"]
    assert content and content[0]["type"] == "text"
    text = content[0]["text"]
    connections = json.loads(text)
    assert isinstance(connections, list)

    serialized = json.dumps(connections, ensure_ascii=False)
    for conn in connections:
        assert isinstance(conn.get("name"), str)
        assert conn["name"].strip()
        assert conn.get("url", "").startswith(("http://", "https://"))

    # File names and connection names may be visible, but secret values must stay masked/empty.
    forbidden_literals = [
        "your-secret",
        "password123",
        "eyJqa3UiOi",
        "BEGIN PRIVATE KEY",
    ]
    for literal in forbidden_literals:
        assert literal not in serialized


@task("Unknown NiFi registration is reported as unavailable, not fabricated")
async def test_unknown_connection_switch_fails_explicitly(session) -> None:
    rpc = _initialize()
    response, _ = rpc.request(
        "tools/call",
        {
            "name": "switch_nifi",
            "arguments": {"name": "definitely-not-registered"},
        },
    )
    assert "result" in response, response

    content = response["result"]["content"]
    assert content and content[0]["type"] == "text"
    payload = json.loads(content[0]["text"])
    assert "error" in payload
    assert "definitely-not-registered" in payload["error"]
    assert "not connected" in payload["error"].lower()


@task("Read-only write attempt is rejected before touching external NiFi state")
async def test_write_tool_is_blocked_for_readonly_connections(session) -> None:
    rpc = _initialize()
    connections_response, _ = rpc.request(
        "tools/call",
        {"name": "list_nifi_connections", "arguments": {}},
    )
    connections = json.loads(connections_response["result"]["content"][0]["text"])
    readonly = [conn for conn in connections if conn.get("connected") and conn.get("readonly")]
    if not readonly:
        # Safe baseline cannot validate readonly enforcement without a readonly registration.
        # The integration suite covers real registered-backend discovery when enabled.
        return

    target = readonly[0]["name"]
    switch_response, _ = rpc.request(
        "tools/call",
        {"name": "switch_nifi", "arguments": {"name": target}},
    )
    switch_payload = json.loads(switch_response["result"]["content"][0]["text"])
    assert switch_payload.get("ok") is True

    response, _ = rpc.request(
        "tools/call",
        {
            "name": "stop_processor",
            "arguments": {
                "processor_id": "00000000-0000-0000-0000-000000000000",
                "version": 0,
            },
        },
    )
    text = response["result"]["content"][0]["text"]
    assert "read-only mode" in text.lower()
