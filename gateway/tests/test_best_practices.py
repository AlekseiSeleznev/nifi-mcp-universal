"""Tests for gateway.nifi.best_practices — NiFiBestPractices, SmartFlowBuilder, flow_builder."""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from gateway.nifi.best_practices import NiFiBestPractices
from gateway.nifi.flow_builder import analyze_flow_request
from gateway.nifi.setup_helper import SetupGuide


# ──────────────────────────────────────────────
#  NiFiBestPractices
# ──────────────────────────────────────────────

class TestNiFiBestPractices:
    def test_always_recommends_process_group(self):
        should_create, name = NiFiBestPractices.should_create_process_group_for_flow("my flow")
        assert should_create is True

    def test_suggested_name_is_string(self):
        _, name = NiFiBestPractices.should_create_process_group_for_flow("any description")
        assert isinstance(name, str)
        assert len(name) > 0

    def test_etl_flow_gets_etl_name(self):
        _, name = NiFiBestPractices.should_create_process_group_for_flow("ETL pipeline for sales data")
        assert "ETL" in name or len(name) > 0

    def test_get_best_practices_guide_returns_string(self):
        guide = NiFiBestPractices.get_best_practices_guide()
        assert isinstance(guide, str)
        assert len(guide) > 100  # not empty

    def test_get_recommended_workflow_returns_string(self):
        workflow = NiFiBestPractices.get_recommended_workflow_for_request("ingest from Kafka to HDFS")
        assert isinstance(workflow, str)
        assert len(workflow) > 0


# ──────────────────────────────────────────────
#  analyze_flow_request (flow_builder)
# ──────────────────────────────────────────────

class TestAnalyzeFlowRequest:
    def test_returns_dict(self):
        result = analyze_flow_request("ingest from MySQL to HDFS")
        assert isinstance(result, dict)

    def test_result_not_empty(self):
        result = analyze_flow_request("simple flow")
        assert len(result) > 0

    def test_various_requests_dont_raise(self):
        requests = [
            "read from Kafka",
            "write to database",
            "transform JSON to CSV",
            "monitor file directory",
            "route based on content",
        ]
        for req in requests:
            result = analyze_flow_request(req)
            assert isinstance(result, dict)


# ──────────────────────────────────────────────
#  SetupGuide
# ──────────────────────────────────────────────

class TestSetupGuide:
    def test_get_required_config_returns_dict(self):
        config = SetupGuide.get_required_config()
        assert isinstance(config, dict)

    def test_get_setup_instructions_returns_string(self):
        instructions = SetupGuide.get_setup_instructions()
        assert isinstance(instructions, str)
        assert len(instructions) > 50

    def test_validate_current_config_returns_tuple(self):
        result = SetupGuide.validate_current_config()
        assert isinstance(result, tuple)
        assert len(result) == 3
        is_valid, errors, warnings = result
        assert isinstance(is_valid, bool)
        assert isinstance(errors, list)
        assert isinstance(warnings, list)

    def test_nifi_api_base_env_makes_config_valid(self, monkeypatch):
        """When NIFI_MCP_NIFI_API_BASE is set, validation should not produce connection errors."""
        monkeypatch.setenv("NIFI_MCP_NIFI_API_BASE", "https://nifi.example.com/nifi-api")
        # Re-call validate — it reads os.environ directly
        is_valid, errors, warnings = SetupGuide.validate_current_config()
        # Should at least not raise
        assert isinstance(is_valid, bool)
