"""Tests for gateway.tools.write_service dispatch helpers."""

from __future__ import annotations

import json
import pytest
from unittest.mock import MagicMock

from gateway.tools.write_service import dispatch_write_tool


@pytest.mark.asyncio
async def test_dispatch_create_connection_splits_relationships():
    client = MagicMock()
    client.create_connection.return_value = {"id": "conn1"}
    result = await dispatch_write_tool(
        "create_connection",
        {
            "process_group_id": "pg1",
            "source_id": "src",
            "source_type": "PROCESSOR",
            "destination_id": "dst",
            "destination_type": "PROCESSOR",
            "relationships": "success, failure",
        },
        client,
    )
    assert result["id"] == "conn1"
    client.create_connection.assert_called_once_with(
        "pg1", "src", "PROCESSOR", "dst", "PROCESSOR", ["success", "failure"]
    )


@pytest.mark.asyncio
async def test_dispatch_create_connection_ignores_empty_relationships():
    client = MagicMock()
    client.create_connection.return_value = {"id": "conn1"}
    await dispatch_write_tool(
        "create_connection",
        {
            "process_group_id": "pg1",
            "source_id": "src",
            "source_type": "PROCESSOR",
            "destination_id": "dst",
            "destination_type": "PROCESSOR",
            "relationships": " , ",
        },
        client,
    )
    client.create_connection.assert_called_once_with(
        "pg1", "src", "PROCESSOR", "dst", "PROCESSOR", []
    )


@pytest.mark.asyncio
async def test_dispatch_create_parameter_context_parses_parameters_json():
    client = MagicMock()
    client.create_parameter_context.return_value = {"id": "ctx1"}
    params = json.dumps([{"name": "host", "value": "localhost", "sensitive": False}])
    result = await dispatch_write_tool(
        "create_parameter_context",
        {"name": "ctx", "parameters": params},
        client,
    )
    assert result["id"] == "ctx1"
    parsed_params = client.create_parameter_context.call_args[0][2]
    assert parsed_params[0]["name"] == "host"


@pytest.mark.asyncio
async def test_dispatch_unknown_write_tool_returns_none():
    client = MagicMock()
    result = await dispatch_write_tool("unknown_write_tool", {}, client)
    assert result is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("tool_name", "arguments", "method_name", "expected_args"),
    [
        ("update_input_port", {"port_id": "p1", "version": 1, "name": "Input"}, "update_input_port", ("p1", 1, "Input")),
        ("update_output_port", {"port_id": "p1", "version": 1, "name": "Output"}, "update_output_port", ("p1", 1, "Output")),
        ("stop_input_port", {"port_id": "p1", "version": 1}, "stop_input_port", ("p1", 1)),
        ("start_output_port", {"port_id": "p1", "version": 1}, "start_output_port", ("p1", 1)),
    ],
)
async def test_dispatch_port_operations(tool_name, arguments, method_name, expected_args):
    client = MagicMock()
    getattr(client, method_name).return_value = {"ok": True}
    result = await dispatch_write_tool(tool_name, arguments, client)
    assert result == {"ok": True}
    getattr(client, method_name).assert_called_once_with(*expected_args)


@pytest.mark.asyncio
async def test_dispatch_start_new_flow_uses_builder():
    client = MagicMock()
    builder = MagicMock()
    builder.start_new_flow.return_value = {"process_group": {"id": "pg1"}}
    builder_cls = MagicMock(return_value=builder)

    result = await dispatch_write_tool(
        "start_new_flow",
        {"flow_name": "My Flow", "parent_pg_id": "root"},
        client,
        builder_cls=builder_cls,
    )

    assert result["process_group"]["id"] == "pg1"
    builder_cls.assert_called_once_with(client)
    builder.start_new_flow.assert_called_once_with("My Flow", "root")


@pytest.mark.asyncio
async def test_dispatch_update_parameter_context_handles_optional_parameters():
    client = MagicMock()
    client.update_parameter_context.return_value = {"id": "ctx1"}

    result = await dispatch_write_tool(
        "update_parameter_context",
        {"context_id": "ctx1", "version": 2, "name": "ctx"},
        client,
    )

    assert result["id"] == "ctx1"
    client.update_parameter_context.assert_called_once_with("ctx1", 2, "ctx", None, None)


@pytest.mark.asyncio
async def test_dispatch_parameter_context_rejects_invalid_json():
    client = MagicMock()
    with pytest.raises(ValueError, match="Invalid parameters JSON"):
        await dispatch_write_tool(
            "create_parameter_context",
            {"name": "ctx", "parameters": "{not-json}"},
            client,
        )


@pytest.mark.asyncio
async def test_dispatch_parameter_context_rejects_non_list_json():
    client = MagicMock()
    with pytest.raises(ValueError, match="Invalid parameters JSON"):
        await dispatch_write_tool(
            "create_parameter_context",
            {"name": "ctx", "parameters": '{"name":"host"}'},
            client,
        )
