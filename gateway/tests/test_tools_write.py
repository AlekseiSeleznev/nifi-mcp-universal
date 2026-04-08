"""Tests for gateway.tools.write_tools — write operations (readonly guard + tool dispatch)."""
from __future__ import annotations

import json
import pytest
from unittest.mock import MagicMock

from gateway.tools import write_tools
from gateway.nifi.client import NiFiClient


def _mock_client(**methods) -> MagicMock:
    client = MagicMock(spec=NiFiClient)
    for name, return_value in methods.items():
        getattr(client, name).return_value = return_value
    return client


def _parse(result) -> dict | list:
    return json.loads(result[0].text)


# ──────────────────────────────────────────────
#  Readonly guard
# ──────────────────────────────────────────────

class TestReadonlyGuard:
    @pytest.mark.asyncio
    async def test_readonly_blocks_all_writes(self):
        client = _mock_client(start_processor={})
        result = await write_tools.handle("start_processor", {"processor_id": "p1", "version": 0}, client, readonly=True)
        assert "DENIED" in result[0].text
        assert "read-only" in result[0].text.lower()

    @pytest.mark.asyncio
    async def test_non_readonly_allows_write(self):
        client = _mock_client(start_processor={"status": "RUNNING"})
        result = await write_tools.handle("start_processor", {"processor_id": "p1", "version": 0}, client, readonly=False)
        assert "DENIED" not in result[0].text


# ──────────────────────────────────────────────
#  Processor lifecycle
# ──────────────────────────────────────────────

class TestProcessorWriteOps:
    @pytest.mark.asyncio
    async def test_start_processor(self):
        client = _mock_client(start_processor={"id": "p1"})
        result = await write_tools.handle("start_processor", {"processor_id": "p1", "version": 0}, client, readonly=False)
        client.start_processor.assert_called_once_with("p1", 0)

    @pytest.mark.asyncio
    async def test_stop_processor(self):
        client = _mock_client(stop_processor={"id": "p1"})
        result = await write_tools.handle("stop_processor", {"processor_id": "p1", "version": 0}, client, readonly=False)
        client.stop_processor.assert_called_once_with("p1", 0)

    @pytest.mark.asyncio
    async def test_create_processor(self):
        client = _mock_client(create_processor={"id": "new-p"})
        result = await write_tools.handle(
            "create_processor",
            {"process_group_id": "pg1", "processor_type": "org.apache.nifi.processors.standard.LogAttribute", "name": "LogIt"},
            client,
            readonly=False,
        )
        data = _parse(result)
        assert data["id"] == "new-p"

    @pytest.mark.asyncio
    async def test_create_processor_default_positions(self):
        client = _mock_client(create_processor={"id": "new-p"})
        await write_tools.handle(
            "create_processor",
            {"process_group_id": "pg1", "processor_type": "org.apache.nifi.processors.standard.LogAttribute", "name": "LogIt"},
            client,
            readonly=False,
        )
        client.create_processor.assert_called_once_with("pg1", "org.apache.nifi.processors.standard.LogAttribute", "LogIt", 0, 0)

    @pytest.mark.asyncio
    async def test_update_processor_config(self):
        client = _mock_client(update_processor={"id": "p1"})
        await write_tools.handle(
            "update_processor_config",
            {"processor_id": "p1", "version": 3, "config": {"name": "NewName"}},
            client,
            readonly=False,
        )
        client.update_processor.assert_called_once_with("p1", 3, {"name": "NewName"})

    @pytest.mark.asyncio
    async def test_delete_processor(self):
        client = _mock_client(delete_processor={})
        await write_tools.handle("delete_processor", {"processor_id": "p1", "version": 2}, client, readonly=False)
        client.delete_processor.assert_called_once_with("p1", 2)

    @pytest.mark.asyncio
    async def test_terminate_processor(self):
        client = _mock_client(terminate_processor={"status": "stopped_normally"})
        await write_tools.handle("terminate_processor", {"processor_id": "p1", "version": 0}, client, readonly=False)
        client.terminate_processor.assert_called_once_with("p1", 0)

    @pytest.mark.asyncio
    async def test_start_all_processors_in_group(self):
        client = _mock_client(start_all_processors_in_group={"started": [], "failed": [], "already_running": []})
        await write_tools.handle("start_all_processors_in_group", {"pg_id": "pg1"}, client, readonly=False)
        client.start_all_processors_in_group.assert_called_once_with("pg1")

    @pytest.mark.asyncio
    async def test_stop_all_processors_in_group(self):
        client = _mock_client(stop_all_processors_in_group={"stopped": [], "failed": [], "already_stopped": []})
        await write_tools.handle("stop_all_processors_in_group", {"pg_id": "pg1"}, client, readonly=False)
        client.stop_all_processors_in_group.assert_called_once_with("pg1")


# ──────────────────────────────────────────────
#  Connections
# ──────────────────────────────────────────────

class TestConnectionWriteOps:
    @pytest.mark.asyncio
    async def test_create_connection(self):
        client = _mock_client(create_connection={"id": "conn-new"})
        result = await write_tools.handle(
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
            readonly=False,
        )
        data = _parse(result)
        assert data["id"] == "conn-new"
        client.create_connection.assert_called_once_with(
            "pg1", "src", "PROCESSOR", "dst", "PROCESSOR", ["success", "failure"]
        )

    @pytest.mark.asyncio
    async def test_delete_connection(self):
        client = _mock_client(delete_connection={})
        await write_tools.handle("delete_connection", {"connection_id": "conn1", "version": 0}, client, readonly=False)
        client.delete_connection.assert_called_once_with("conn1", 0)

    @pytest.mark.asyncio
    async def test_empty_connection_queue(self):
        client = _mock_client(empty_connection_queue={})
        await write_tools.handle("empty_connection_queue", {"connection_id": "conn1"}, client, readonly=False)
        client.empty_connection_queue.assert_called_once_with("conn1")


# ──────────────────────────────────────────────
#  Controller services
# ──────────────────────────────────────────────

class TestControllerServiceWriteOps:
    @pytest.mark.asyncio
    async def test_create_controller_service(self):
        client = _mock_client(create_controller_service={"id": "svc-new"})
        await write_tools.handle(
            "create_controller_service",
            {"process_group_id": "pg1", "service_type": "org.apache.nifi.dbcp.DBCPConnectionPool", "name": "MyPool"},
            client,
            readonly=False,
        )
        client.create_controller_service.assert_called_once_with(
            "pg1", "org.apache.nifi.dbcp.DBCPConnectionPool", "MyPool"
        )

    @pytest.mark.asyncio
    async def test_enable_controller_service(self):
        client = _mock_client(enable_controller_service={})
        await write_tools.handle("enable_controller_service", {"service_id": "svc1", "version": 0}, client, readonly=False)
        client.enable_controller_service.assert_called_once_with("svc1", 0)

    @pytest.mark.asyncio
    async def test_disable_controller_service(self):
        client = _mock_client(disable_controller_service={})
        await write_tools.handle("disable_controller_service", {"service_id": "svc1", "version": 0}, client, readonly=False)
        client.disable_controller_service.assert_called_once_with("svc1", 0)

    @pytest.mark.asyncio
    async def test_update_controller_service_properties(self):
        client = _mock_client(update_controller_service={})
        await write_tools.handle(
            "update_controller_service_properties",
            {"service_id": "svc1", "version": 2, "properties": {"host": "localhost"}},
            client,
            readonly=False,
        )
        client.update_controller_service.assert_called_once_with("svc1", 2, {"host": "localhost"})

    @pytest.mark.asyncio
    async def test_delete_controller_service(self):
        client = _mock_client(delete_controller_service={})
        await write_tools.handle("delete_controller_service", {"service_id": "svc1", "version": 1}, client, readonly=False)
        client.delete_controller_service.assert_called_once_with("svc1", 1)

    @pytest.mark.asyncio
    async def test_enable_all_controller_services_in_group(self):
        client = _mock_client(enable_all_controller_services_in_group={"enabled": [], "failed": [], "already_enabled": []})
        await write_tools.handle("enable_all_controller_services_in_group", {"pg_id": "pg1"}, client, readonly=False)
        client.enable_all_controller_services_in_group.assert_called_once_with("pg1")


# ──────────────────────────────────────────────
#  Process groups
# ──────────────────────────────────────────────

class TestProcessGroupWriteOps:
    @pytest.mark.asyncio
    async def test_create_process_group(self):
        client = _mock_client(create_process_group={"id": "pg-new"})
        result = await write_tools.handle(
            "create_process_group",
            {"parent_id": "root", "name": "My Flow"},
            client,
            readonly=False,
        )
        data = _parse(result)
        assert data["id"] == "pg-new"

    @pytest.mark.asyncio
    async def test_create_process_group_default_positions(self):
        client = _mock_client(create_process_group={"id": "pg-new"})
        await write_tools.handle(
            "create_process_group",
            {"parent_id": "root", "name": "My Flow"},
            client,
            readonly=False,
        )
        client.create_process_group.assert_called_once_with("root", "My Flow", 0, 0)

    @pytest.mark.asyncio
    async def test_update_process_group_name(self):
        client = _mock_client(update_process_group={"id": "pg1"})
        await write_tools.handle(
            "update_process_group_name",
            {"pg_id": "pg1", "version": 2, "name": "New Name"},
            client,
            readonly=False,
        )
        client.update_process_group.assert_called_once_with("pg1", 2, "New Name")

    @pytest.mark.asyncio
    async def test_delete_process_group(self):
        client = _mock_client(delete_process_group={})
        await write_tools.handle("delete_process_group", {"pg_id": "pg1", "version": 0}, client, readonly=False)
        client.delete_process_group.assert_called_once_with("pg1", 0)


# ──────────────────────────────────────────────
#  Ports
# ──────────────────────────────────────────────

class TestPortWriteOps:
    @pytest.mark.asyncio
    async def test_create_input_port(self):
        client = _mock_client(create_input_port={"id": "ip1"})
        await write_tools.handle("create_input_port", {"pg_id": "pg1", "name": "In"}, client, readonly=False)
        client.create_input_port.assert_called_once_with("pg1", "In", 0, 0)

    @pytest.mark.asyncio
    async def test_create_output_port(self):
        client = _mock_client(create_output_port={"id": "op1"})
        await write_tools.handle("create_output_port", {"pg_id": "pg1", "name": "Out"}, client, readonly=False)
        client.create_output_port.assert_called_once_with("pg1", "Out", 0, 0)

    @pytest.mark.asyncio
    async def test_delete_input_port(self):
        client = _mock_client(delete_input_port={})
        await write_tools.handle("delete_input_port", {"port_id": "ip1", "version": 0}, client, readonly=False)
        client.delete_input_port.assert_called_once_with("ip1", 0)

    @pytest.mark.asyncio
    async def test_delete_output_port(self):
        client = _mock_client(delete_output_port={})
        await write_tools.handle("delete_output_port", {"port_id": "op1", "version": 0}, client, readonly=False)
        client.delete_output_port.assert_called_once_with("op1", 0)

    @pytest.mark.asyncio
    async def test_start_input_port(self):
        client = _mock_client(start_input_port={})
        await write_tools.handle("start_input_port", {"port_id": "ip1", "version": 0}, client, readonly=False)
        client.start_input_port.assert_called_once_with("ip1", 0)

    @pytest.mark.asyncio
    async def test_stop_output_port(self):
        client = _mock_client(stop_output_port={})
        await write_tools.handle("stop_output_port", {"port_id": "op1", "version": 0}, client, readonly=False)
        client.stop_output_port.assert_called_once_with("op1", 0)


# ──────────────────────────────────────────────
#  Parameter contexts
# ──────────────────────────────────────────────

class TestParameterContextWriteOps:
    @pytest.mark.asyncio
    async def test_create_parameter_context_empty_params(self):
        client = _mock_client(create_parameter_context={"id": "ctx-new"})
        result = await write_tools.handle(
            "create_parameter_context",
            {"name": "MyCtx"},
            client,
            readonly=False,
        )
        data = _parse(result)
        assert data["id"] == "ctx-new"

    @pytest.mark.asyncio
    async def test_create_parameter_context_with_params(self):
        client = _mock_client(create_parameter_context={"id": "ctx-new"})
        params_json = json.dumps([{"name": "host", "value": "localhost", "sensitive": False}])
        await write_tools.handle(
            "create_parameter_context",
            {"name": "MyCtx", "parameters": params_json},
            client,
            readonly=False,
        )
        call_params = client.create_parameter_context.call_args[0][2]
        assert call_params[0]["name"] == "host"

    @pytest.mark.asyncio
    async def test_delete_parameter_context(self):
        client = _mock_client(delete_parameter_context={})
        await write_tools.handle("delete_parameter_context", {"context_id": "ctx1", "version": 0}, client, readonly=False)
        client.delete_parameter_context.assert_called_once_with("ctx1", 0)

    @pytest.mark.asyncio
    async def test_apply_parameter_context_to_process_group(self):
        client = _mock_client(apply_parameter_context_to_process_group={})
        await write_tools.handle(
            "apply_parameter_context_to_process_group",
            {"pg_id": "pg1", "pg_version": 3, "context_id": "ctx1"},
            client,
            readonly=False,
        )
        client.apply_parameter_context_to_process_group.assert_called_once_with("pg1", 3, "ctx1")


# ──────────────────────────────────────────────
#  Error handling
# ──────────────────────────────────────────────

class TestWriteToolsErrorHandling:
    @pytest.mark.asyncio
    async def test_exception_returns_error_text(self):
        client = MagicMock(spec=NiFiClient)
        client.delete_processor.side_effect = Exception("Processor not found")
        result = await write_tools.handle("delete_processor", {"processor_id": "ghost", "version": 0}, client, readonly=False)
        assert "Error" in result[0].text

    @pytest.mark.asyncio
    async def test_unknown_tool_returns_error(self):
        client = _mock_client()
        result = await write_tools.handle("nonexistent_write_tool", {}, client, readonly=False)
        data = _parse(result)
        assert "error" in data


# ──────────────────────────────────────────────
#  TOOLS list sanity
# ──────────────────────────────────────────────

class TestWriteToolsList:
    def test_tools_count(self):
        assert len(write_tools.TOOLS) >= 20

    def test_all_tools_have_write_operation_tag(self):
        for tool in write_tools.TOOLS:
            assert "WRITE OPERATION" in tool.description, f"Tool {tool.name} missing WRITE OPERATION tag"

    def test_all_tools_have_schema(self):
        for tool in write_tools.TOOLS:
            assert tool.inputSchema is not None
