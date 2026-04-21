from __future__ import annotations

import runpy
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from gateway.nifi.best_practices import NiFiBestPractices
from gateway.nifi_registry import ConnectionRegistry
from gateway.tools import admin
from gateway.tools.read_service import dispatch_read_tool


def test___main___runs_uvicorn_with_current_settings():
    fake_settings = MagicMock(port=8085, log_level="DEBUG")
    with patch("gateway.config.settings", fake_settings), patch("uvicorn.run") as run:
        runpy.run_module("gateway.__main__", run_name="__main__")

    run.assert_called_once_with(
        "gateway.server:app",
        host="0.0.0.0",
        port=8085,
        log_level="debug",
    )


@pytest.mark.parametrize(
    ("description", "expected"),
    [
        ("copy to s3 storage", "Storage Integration"),
        ("call a rest api", "API Integration"),
        ("process file batches", "File Processing"),
        ("write into iceberg tables", "Iceberg Integration"),
    ],
)
def test_best_practices_name_suggestions_cover_remaining_keywords(description, expected):
    _, name = NiFiBestPractices.should_create_process_group_for_flow(description)
    assert name == expected


def test_registry_save_failure_is_logged(tmp_path: Path):
    registry = ConnectionRegistry()
    registry._connections = {}
    with patch("gateway.nifi_registry.STATE_FILE", str(tmp_path / "state" / "registry.json")), \
         patch("gateway.nifi_registry.tempfile.mkstemp", side_effect=OSError("disk full")), \
         patch("gateway.nifi_registry.log") as log:
        registry.save()
    log.exception.assert_called_once()


@pytest.mark.asyncio
async def test_admin_test_connection_invalid_auth_returns_json_error():
    result = await admin.handle(
        "test_nifi_connection",
        {"url": "https://nifi.example.com", "auth_method": "invalid"},
        None,
    )
    assert '"ok": false' in result[0].text.lower()


@pytest.mark.asyncio
async def test_read_service_recommended_workflow_branch():
    client = MagicMock()
    result = await dispatch_read_tool(
        "get_recommended_workflow",
        {"user_request": "stream kafka to s3"},
        client,
    )
    assert result.kind == "text"
    assert "process group" in result.payload.lower()
