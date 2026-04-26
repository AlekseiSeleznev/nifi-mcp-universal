"""Gated read-only MCP-Eval integration checks.

Run only via:
  NIFI_MCP_EVAL_INTEGRATION=1 NIFI_MCP_EVAL_CONNECTION=<name> just mcp-eval-integration
"""

from __future__ import annotations

import json
import os
import urllib.request
from typing import Any

from mcp_eval import task, setup
from mcp_eval.config import MCPEvalSettings
from mcp_agent.agents.agent_spec import AgentSpec
from mcp_agent.config import MCPSettings, MCPServerSettings
import mcp_eval


MCP_URL = os.environ.get("MCP_URL", "http://localhost:8085/mcp")
CONNECTION_NAME = os.environ["NIFI_MCP_EVAL_CONNECTION"]


@setup
def configure_nifi_gateway_integration() -> None:
    mcp_eval.use_config(
        MCPEvalSettings(
            name="nifi-mcp-universal integration baseline",
            description="Read-only checks against one registered NiFi connection.",
            mcp=MCPSettings(
                servers={
                    "nifi": MCPServerSettings(
                        transport="streamable_http",
                        url=MCP_URL,
                    )
                }
            ),
            default_agent=AgentSpec(
                name="nifi_gateway_integration_tester",
                instruction=(
                    "Use only read-only NiFi discovery tools. Do not perform "
                    "start, stop, create, update, delete, or queue-emptying operations."
                ),
                server_names=["nifi"],
            ),
            default_servers=["nifi"],
        )
    )


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

        payload = {"jsonrpc": "2.0", "id": 1, "method": method}
        if params is not None:
            payload["params"] = params

        request = urllib.request.Request(
            MCP_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=15) as response:
            body = response.read().decode("utf-8")
            session_id = response.headers.get("mcp-session-id") or self.session_id
        return _parse_mcp_response(body), RpcSession(session_id)


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
            "clientInfo": {"name": "nifi-mcp-eval-integration", "version": "0.1.0"},
        },
    )
    assert "result" in response, response
    return session


def _call_tool(rpc: RpcSession, name: str, arguments: dict[str, Any] | None = None) -> Any:
    response, _ = rpc.request(
        "tools/call",
        {"name": name, "arguments": arguments or {}},
    )
    assert "result" in response, response
    content = response["result"]["content"]
    assert content and content[0]["type"] == "text"
    text = content[0]["text"]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


@task("Configured integration connection is registered and switchable")
async def test_integration_connection_is_registered(session) -> None:
    rpc = _initialize()
    connections = _call_tool(rpc, "list_nifi_connections")
    names = {conn["name"] for conn in connections}
    assert CONNECTION_NAME in names

    switched = _call_tool(rpc, "switch_nifi", {"name": CONNECTION_NAME})
    assert switched.get("ok") is True
    assert switched.get("active") == CONNECTION_NAME


@task("Registered integration connection supports read-only metadata discovery")
async def test_readonly_metadata_discovery(session) -> None:
    rpc = _initialize()
    _call_tool(rpc, "switch_nifi", {"name": CONNECTION_NAME})

    version = _call_tool(rpc, "get_nifi_version")
    assert version["parsed_version"]
    assert isinstance(version["is_nifi_2x"], bool)

    root = _call_tool(rpc, "get_root_process_group")
    root_id = root["processGroupFlow"]["id"]
    assert root_id

    # Read-only list calls should work without mutating flow state.
    processors = _call_tool(rpc, "list_processors", {"process_group_id": root_id})
    connections = _call_tool(rpc, "list_connections", {"process_group_id": root_id})
    assert "processors" in processors
    assert "connections" in connections
