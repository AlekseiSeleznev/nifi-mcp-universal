"""Additional tests for best_practices — SmartFlowBuilder and root PG id extraction."""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from gateway.nifi.best_practices import NiFiBestPractices, SmartFlowBuilder


class TestSmartFlowBuilder:
    def _make_client(self, root_response: dict, pg_response: dict) -> MagicMock:
        client = MagicMock()
        client.get_root_process_group.return_value = root_response
        client.create_process_group.return_value = pg_response
        return client

    def test_start_new_flow_uses_processGroupFlow_id(self):
        """Root PG response wraps id in processGroupFlow — must be unwrapped."""
        client = self._make_client(
            root_response={"processGroupFlow": {"id": "root-id-123", "flow": {}}},
            pg_response={"id": "new-pg-id", "component": {"name": "My Flow"}},
        )
        builder = SmartFlowBuilder(client)
        result = builder.start_new_flow("My Flow")

        client.create_process_group.assert_called_once()
        call_args = client.create_process_group.call_args[0]
        assert call_args[0] == "root-id-123"  # parent_id must be the extracted id

    def test_start_new_flow_with_explicit_parent(self):
        """When parent_pg_id is provided, should not fetch root PG."""
        client = self._make_client(
            root_response={"processGroupFlow": {"id": "root-id"}},
            pg_response={"id": "child-pg"},
        )
        builder = SmartFlowBuilder(client)
        result = builder.start_new_flow("Sub Flow", parent_pg_id="explicit-parent")

        client.get_root_process_group.assert_not_called()
        call_args = client.create_process_group.call_args[0]
        assert call_args[0] == "explicit-parent"

    def test_start_new_flow_returns_structured_result(self):
        client = self._make_client(
            root_response={"processGroupFlow": {"id": "root"}},
            pg_response={"id": "pg1", "component": {"name": "Test Flow"}},
        )
        builder = SmartFlowBuilder(client)
        result = builder.start_new_flow("Test Flow")

        assert "process_group" in result
        assert "next_steps" in result
        assert isinstance(result["next_steps"], list)

    def test_start_new_flow_fallback_id_from_top_level(self):
        """If processGroupFlow.id is missing, fall back to top-level id."""
        client = self._make_client(
            root_response={"id": "top-level-id"},
            pg_response={"id": "new-pg"},
        )
        builder = SmartFlowBuilder(client)
        builder.start_new_flow("My Flow")

        call_args = client.create_process_group.call_args[0]
        assert call_args[0] == "top-level-id"

    def test_get_current_process_group_initially_none(self):
        client = MagicMock()
        builder = SmartFlowBuilder(client)
        assert builder.get_current_process_group() is None

    def test_get_current_process_group_set_after_start_flow(self):
        client = self._make_client(
            root_response={"processGroupFlow": {"id": "root"}},
            pg_response={"id": "pg-new"},
        )
        builder = SmartFlowBuilder(client)
        builder.start_new_flow("My Flow")
        # current_process_group should be set to the new PG id
        # (SmartFlowBuilder sets self.current_process_group = pg["id"])
        assert builder.get_current_process_group() == "pg-new"


class TestNiFiBestPracticesExtra:
    def test_validate_flow_structure_root_canvas_is_error(self):
        is_valid, errors, suggestions = NiFiBestPractices.validate_flow_structure({
            "process_group_id": "root-123",
            "root_id": "root-123",
        })
        assert not is_valid
        assert any("root" in e.lower() for e in errors)

    def test_validate_flow_structure_with_proper_pg_is_ok(self):
        is_valid, errors, suggestions = NiFiBestPractices.validate_flow_structure({
            "process_group_id": "custom-pg-456",
            "root_id": "root-123",
            "processors": [{"id": "p1"}],
            "connections": [{"id": "c1"}],
        })
        assert is_valid

    def test_validate_flow_multiple_processors_no_connections_error(self):
        is_valid, errors, suggestions = NiFiBestPractices.validate_flow_structure({
            "process_group_id": "pg-1",
            "root_id": "root-1",
            "processors": [{"id": "p1"}, {"id": "p2"}],
            "connections": [],
        })
        assert not is_valid
        assert any("connect" in e.lower() for e in errors)

    def test_suggest_name_for_kafka(self):
        _, name = NiFiBestPractices.should_create_process_group_for_flow(
            "read from kafka and write to HDFS"
        )
        assert "kafka" in name.lower()

    def test_suggest_name_for_sql(self):
        _, name = NiFiBestPractices.should_create_process_group_for_flow(
            "extract from sql server database"
        )
        assert "database" in name.lower() or "sql" in name.lower() or "integration" in name.lower()

    def test_recommend_workflow_for_etl(self):
        workflow = NiFiBestPractices.get_recommended_workflow_for_request("ETL pipeline from S3 to Iceberg")
        assert "process group" in workflow.lower()
        assert "step" in workflow.lower()
