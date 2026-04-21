"""Tests for gateway.tools.read_tools — all 25 read-only tools."""
from __future__ import annotations

import json
import pytest
from unittest.mock import MagicMock, patch

from gateway.tools import read_tools
from gateway.nifi.client import NiFiClient


def _mock_client(**methods) -> MagicMock:
    client = MagicMock(spec=NiFiClient)
    for name, return_value in methods.items():
        getattr(client, name).return_value = return_value
    return client


def _parse(result) -> dict | list | str:
    return json.loads(result[0].text)


# ──────────────────────────────────────────────
#  Redact sensitive helper (unit test)
# ──────────────────────────────────────────────

class TestRedactSensitive:
    def test_redacts_password(self):
        data = {"password": "hunter2", "other": "ok"}
        result = read_tools._redact_sensitive(data)
        assert result["password"] == "***REDACTED***"
        assert result["other"] == "ok"

    def test_redacts_token(self):
        data = {"token": "jwt123"}
        result = read_tools._redact_sensitive(data)
        assert result["token"] == "***REDACTED***"

    def test_nested_redaction(self):
        data = {"config": {"password": "secret"}}
        result = read_tools._redact_sensitive(data)
        assert result["config"]["password"] == "***REDACTED***"

    def test_list_truncation(self):
        data = [{"name": f"item{i}"} for i in range(300)]
        result = read_tools._redact_sensitive(data, max_items=200)
        assert len(result) == 201  # 200 items + truncation marker
        assert result[-1].get("truncated") is True

    def test_non_sensitive_keys_untouched(self):
        data = {"name": "NiFi", "version": "2.0.0"}
        result = read_tools._redact_sensitive(data)
        assert result == data


# ──────────────────────────────────────────────
#  get_nifi_version
# ──────────────────────────────────────────────

class TestGetNifiVersion:
    @pytest.mark.asyncio
    async def test_returns_version_info(self):
        client = _mock_client(
            get_version_info={"about": {"version": "2.0.0"}},
            get_version_tuple=(2, 0, 0),
            is_nifi_2x=True,
        )
        result = await read_tools.handle("get_nifi_version", {}, client)
        data = _parse(result)
        assert "version_info" in data
        assert data["is_nifi_2x"] is True
        assert data["parsed_version"] == "2.0.0"


# ──────────────────────────────────────────────
#  get_root_process_group
# ──────────────────────────────────────────────

class TestGetRootProcessGroup:
    @pytest.mark.asyncio
    async def test_returns_flow(self):
        client = _mock_client(get_root_process_group={"processGroupFlow": {}})
        result = await read_tools.handle("get_root_process_group", {}, client)
        data = _parse(result)
        assert "processGroupFlow" in data


# ──────────────────────────────────────────────
#  list_processors
# ──────────────────────────────────────────────

class TestListProcessors:
    @pytest.mark.asyncio
    async def test_returns_processors(self):
        client = _mock_client(list_processors={"processors": [{"id": "p1"}]})
        result = await read_tools.handle("list_processors", {"process_group_id": "pg1"}, client)
        data = _parse(result)
        assert len(data["processors"]) == 1


# ──────────────────────────────────────────────
#  list_connections
# ──────────────────────────────────────────────

class TestListConnections:
    @pytest.mark.asyncio
    async def test_returns_connections(self):
        client = _mock_client(list_connections={"connections": []})
        result = await read_tools.handle("list_connections", {"process_group_id": "pg1"}, client)
        data = _parse(result)
        assert "connections" in data


# ──────────────────────────────────────────────
#  get_bulletins
# ──────────────────────────────────────────────

class TestGetBulletins:
    @pytest.mark.asyncio
    async def test_returns_bulletins(self):
        client = _mock_client(get_bulletins={"bulletinBoard": {"bulletins": []}})
        result = await read_tools.handle("get_bulletins", {}, client)
        data = _parse(result)
        assert "bulletinBoard" in data

    @pytest.mark.asyncio
    async def test_passes_after_ms(self):
        client = _mock_client(get_bulletins={"bulletinBoard": {"bulletins": []}})
        await read_tools.handle("get_bulletins", {"after_ms": 1234}, client)
        client.get_bulletins.assert_called_once_with(1234)


# ──────────────────────────────────────────────
#  list_parameter_contexts
# ──────────────────────────────────────────────

class TestListParameterContexts:
    @pytest.mark.asyncio
    async def test_returns_contexts(self):
        client = _mock_client(list_parameter_contexts={"parameterContexts": []})
        result = await read_tools.handle("list_parameter_contexts", {}, client)
        data = _parse(result)
        assert "parameterContexts" in data


# ──────────────────────────────────────────────
#  get_controller_services
# ──────────────────────────────────────────────

class TestGetControllerServices:
    @pytest.mark.asyncio
    async def test_without_pg_id(self):
        client = _mock_client(get_controller_services={"controllerServices": []})
        result = await read_tools.handle("get_controller_services", {}, client)
        data = _parse(result)
        assert "controllerServices" in data
        client.get_controller_services.assert_called_once_with(None)

    @pytest.mark.asyncio
    async def test_with_pg_id(self):
        client = _mock_client(get_controller_services={"controllerServices": []})
        await read_tools.handle("get_controller_services", {"process_group_id": "pg1"}, client)
        client.get_controller_services.assert_called_once_with("pg1")


# ──────────────────────────────────────────────
#  get_processor_types
# ──────────────────────────────────────────────

class TestGetProcessorTypes:
    @pytest.mark.asyncio
    async def test_returns_types(self):
        client = _mock_client(get_processor_types={"processorTypes": []})
        result = await read_tools.handle("get_processor_types", {}, client)
        data = _parse(result)
        assert "processorTypes" in data


# ──────────────────────────────────────────────
#  search_flow
# ──────────────────────────────────────────────

class TestSearchFlow:
    @pytest.mark.asyncio
    async def test_passes_query(self):
        client = _mock_client(search_flow={"searchResultsDTO": {}})
        await read_tools.handle("search_flow", {"query": "GenerateFlowFile"}, client)
        client.search_flow.assert_called_once_with("GenerateFlowFile")


# ──────────────────────────────────────────────
#  get_processor_details / state
# ──────────────────────────────────────────────

class TestGetProcessorDetails:
    @pytest.mark.asyncio
    async def test_returns_processor(self):
        client = _mock_client(get_processor={"component": {"id": "p1", "name": "LogIt"}})
        result = await read_tools.handle("get_processor_details", {"processor_id": "p1"}, client)
        data = _parse(result)
        assert data["component"]["name"] == "LogIt"

    @pytest.mark.asyncio
    async def test_get_processor_state(self):
        client = _mock_client(get_processor_state="RUNNING")
        result = await read_tools.handle("get_processor_state", {"processor_id": "p1"}, client)
        data = _parse(result)
        assert data["state"] == "RUNNING"


# ──────────────────────────────────────────────
#  list_input_ports / list_output_ports
# ──────────────────────────────────────────────

class TestPorts:
    @pytest.mark.asyncio
    async def test_list_input_ports(self):
        client = _mock_client(get_input_ports={"inputPorts": []})
        result = await read_tools.handle("list_input_ports", {"process_group_id": "pg1"}, client)
        data = _parse(result)
        assert "inputPorts" in data

    @pytest.mark.asyncio
    async def test_list_output_ports(self):
        client = _mock_client(get_output_ports={"outputPorts": []})
        result = await read_tools.handle("list_output_ports", {"process_group_id": "pg1"}, client)
        data = _parse(result)
        assert "outputPorts" in data


# ──────────────────────────────────────────────
#  check_connection_queue / get_connection_details
# ──────────────────────────────────────────────

class TestConnectionDetails:
    @pytest.mark.asyncio
    async def test_get_connection_details(self):
        client = _mock_client(get_connection={"id": "conn1"})
        result = await read_tools.handle("get_connection_details", {"connection_id": "conn1"}, client)
        data = _parse(result)
        assert data["id"] == "conn1"

    @pytest.mark.asyncio
    async def test_check_connection_queue(self):
        client = _mock_client(get_connection_queue_size={"flowFilesQueued": 5, "bytesQueued": 1024})
        result = await read_tools.handle("check_connection_queue", {"connection_id": "conn1"}, client)
        data = _parse(result)
        assert data["flowFilesQueued"] == 5


# ──────────────────────────────────────────────
#  get_flow_summary
# ──────────────────────────────────────────────

class TestGetFlowSummary:
    @pytest.mark.asyncio
    async def test_returns_summary(self):
        client = _mock_client(get_process_group_summary={
            "processorCount": 3, "processorStates": {}, "connectionCount": 2,
            "totalFlowFilesQueued": 0, "totalBytesQueued": 0
        })
        result = await read_tools.handle("get_flow_summary", {"process_group_id": "pg1"}, client)
        data = _parse(result)
        assert data["processorCount"] == 3


# ──────────────────────────────────────────────
#  get_flow_health_status
# ──────────────────────────────────────────────

class TestGetFlowHealthStatus:
    @pytest.mark.asyncio
    async def test_returns_health(self):
        health = {
            "processGroupId": "pg1",
            "processors": {"total": 1, "running": 1, "stopped": 0, "invalid": 0, "disabled": 0},
            "controllerServices": {"total": 0, "enabled": 0, "disabled": 0, "invalid": 0},
            "connections": {"total": 0, "with_queued_data": 0, "backpressure": 0},
            "bulletins": [],
            "errors": [],
            "overallHealth": "HEALTHY",
        }
        client = _mock_client(get_flow_health_status=health)
        result = await read_tools.handle("get_flow_health_status", {"pg_id": "pg1"}, client)
        data = _parse(result)
        assert data["overallHealth"] == "HEALTHY"


# ──────────────────────────────────────────────
#  get_controller_service_details
# ──────────────────────────────────────────────

class TestGetControllerServiceDetails:
    @pytest.mark.asyncio
    async def test_returns_service(self):
        client = _mock_client(get_controller_service={"component": {"id": "svc1"}})
        result = await read_tools.handle("get_controller_service_details", {"service_id": "svc1"}, client)
        data = _parse(result)
        assert data["component"]["id"] == "svc1"


# ──────────────────────────────────────────────
#  find_controller_services_by_type
# ──────────────────────────────────────────────

class TestFindControllerServicesByType:
    @pytest.mark.asyncio
    async def test_finds_services(self):
        services = [
            {
                "component": {"id": "s1", "name": "MyPool", "type": "org.apache.nifi.dbcp.DBCPConnectionPool", "state": "ENABLED"},
                "revision": {"version": 1},
            }
        ]
        client = _mock_client(find_controller_services_by_type=services)
        result = await read_tools.handle(
            "find_controller_services_by_type",
            {"process_group_id": "pg1", "service_type": "org.apache.nifi.dbcp.DBCPConnectionPool"},
            client,
        )
        data = _parse(result)
        assert data["count"] == 1
        assert data["services"][0]["name"] == "MyPool"

    @pytest.mark.asyncio
    async def test_root_pg_converts_to_none(self):
        client = _mock_client(find_controller_services_by_type=[])
        await read_tools.handle(
            "find_controller_services_by_type",
            {"process_group_id": "root", "service_type": "org.apache.nifi.dbcp.DBCPConnectionPool"},
            client,
        )
        client.find_controller_services_by_type.assert_called_once_with(
            None, "org.apache.nifi.dbcp.DBCPConnectionPool"
        )


# ──────────────────────────────────────────────
#  get_parameter_context_details
# ──────────────────────────────────────────────

class TestGetParameterContextDetails:
    @pytest.mark.asyncio
    async def test_returns_context(self):
        client = _mock_client(get_parameter_context={"id": "ctx1", "component": {}})
        result = await read_tools.handle("get_parameter_context_details", {"context_id": "ctx1"}, client)
        data = _parse(result)
        assert data["id"] == "ctx1"


# ──────────────────────────────────────────────
#  analyze_flow_build_request
# ──────────────────────────────────────────────

class TestAnalyzeFlowBuildRequest:
    @pytest.mark.asyncio
    async def test_returns_analysis(self):
        client = MagicMock(spec=NiFiClient)
        with patch("gateway.tools.read_tools.analyze_flow_request", return_value={"guidance": "..."}):
            result = await read_tools.handle(
                "analyze_flow_build_request",
                {"user_request": "ingest from Kafka to HDFS"},
                client,
            )
        data = _parse(result)
        assert "guidance" in data


# ──────────────────────────────────────────────
#  get_setup_instructions / check_configuration
# ──────────────────────────────────────────────

class TestSetupTools:
    @pytest.mark.asyncio
    async def test_get_setup_instructions_returns_text(self):
        client = MagicMock(spec=NiFiClient)
        with patch("gateway.tools.read_tools.SetupGuide") as mock_guide:
            mock_guide.get_setup_instructions.return_value = "Setup guide text"
            result = await read_tools.handle("get_setup_instructions", {}, client)
        assert result[0].text == "Setup guide text"

    @pytest.mark.asyncio
    async def test_check_configuration_returns_validity(self):
        client = MagicMock(spec=NiFiClient)
        with patch("gateway.tools.read_tools.SetupGuide") as mock_guide:
            mock_guide.validate_current_config.return_value = (True, [], [])
            result = await read_tools.handle("check_configuration", {}, client)
        data = _parse(result)
        assert data["is_valid"] is True

    @pytest.mark.asyncio
    async def test_get_best_practices_guide_returns_text(self):
        client = MagicMock(spec=NiFiClient)
        with patch("gateway.tools.read_tools.NiFiBestPractices") as mock_bp:
            mock_bp.get_best_practices_guide.return_value = "Best practices text"
            result = await read_tools.handle("get_best_practices_guide", {}, client)
        assert result[0].text == "Best practices text"


# ──────────────────────────────────────────────
#  Error handling
# ──────────────────────────────────────────────

class TestReadToolsErrorHandling:
    @pytest.mark.asyncio
    async def test_client_exception_returns_error_text(self):
        client = MagicMock(spec=NiFiClient)
        client.get_version_info.side_effect = Exception("Network error")
        client.get_version_tuple.side_effect = Exception("Network error")
        result = await read_tools.handle("get_nifi_version", {}, client)
        assert "Error" in result[0].text

    @pytest.mark.asyncio
    async def test_unknown_tool_returns_error(self):
        client = MagicMock(spec=NiFiClient)
        result = await read_tools.handle("nonexistent_tool", {}, client)
        data = _parse(result)
        assert "error" in data


# ──────────────────────────────────────────────
#  TOOLS list sanity check
# ──────────────────────────────────────────────

class TestReadToolsList:
    def test_tools_count(self):
        assert len(read_tools.TOOLS) >= 20

    def test_all_tools_have_names_and_descriptions(self):
        for tool in read_tools.TOOLS:
            assert tool.name
            assert tool.description

    def test_all_tools_have_schema(self):
        for tool in read_tools.TOOLS:
            assert tool.inputSchema is not None
            assert "type" in tool.inputSchema
