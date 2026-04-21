"""Tests for gateway.tools.read_service dispatch helpers."""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from gateway.tools.read_service import dispatch_read_tool


@pytest.mark.asyncio
async def test_dispatch_get_processor_state_returns_json_payload():
    client = MagicMock()
    client.get_processor_state.return_value = "RUNNING"
    result = await dispatch_read_tool("get_processor_state", {"processor_id": "p1"}, client)
    assert result.kind == "json"
    assert result.payload == {"state": "RUNNING"}
    assert result.redact is False


@pytest.mark.asyncio
async def test_dispatch_find_controller_services_with_root_alias():
    client = MagicMock()
    client.find_controller_services_by_type.return_value = [
        {"component": {"id": "svc1", "name": "DBCP", "type": "t", "state": "ENABLED"}, "revision": {"version": 3}}
    ]
    result = await dispatch_read_tool(
        "find_controller_services_by_type",
        {"process_group_id": "root", "service_type": "org.example.Service"},
        client,
    )
    assert result.kind == "json"
    assert result.payload["count"] == 1
    assert result.payload["services"][0]["id"] == "svc1"
    client.find_controller_services_by_type.assert_called_once_with(None, "org.example.Service")


@pytest.mark.asyncio
async def test_dispatch_unknown_read_tool_returns_error_payload():
    client = MagicMock()
    result = await dispatch_read_tool("unknown_read_tool", {}, client)
    assert result.kind == "json"
    assert "Unknown read tool" in result.payload["error"]
