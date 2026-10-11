"""One-attempt RUN_ONCE dispatch and its uncertainty/read-only boundaries."""
import json
from unittest.mock import MagicMock

import pytest
import requests

from gateway.nifi.client import NiFiClient, NiFiError
from gateway.tools import write_tools


def test_run_once_exact_revision_and_state(nifi_client, mock_session):
    response = mock_session.put.return_value
    response.ok = True
    response.content = b"{}"
    response.json.return_value = {"component": {"id": "proc1"}}
    assert nifi_client.run_once_processor("proc1", 7)["component"]["id"] == "proc1"
    mock_session.put.assert_called_once_with(
        "https://nifi.example.com/nifi-api/processors/proc1/run-status",
        params=None, timeout=5, json={"revision": {"version": 7}, "state": "RUN_ONCE"})


@pytest.mark.parametrize("failure", [requests.Timeout(), requests.ConnectionError()])
def test_transport_uncertainty_is_one_attempt(nifi_client, mock_session, failure):
    mock_session.put.side_effect = failure
    with pytest.raises(type(failure)):
        nifi_client.run_once_processor("proc1", 7)
    assert mock_session.put.call_count == 1


def test_conflict_is_private_and_has_no_retry(nifi_client, mock_session):
    response = mock_session.put.return_value
    response.ok = False
    response.status_code = 409
    response.reason = "Conflict"
    response.text = "PRIVATE RESPONSE"
    with pytest.raises(NiFiError) as exc:
        nifi_client.run_once_processor("proc1", 7)
    assert "PRIVATE RESPONSE" not in str(exc.value)
    assert exc.value.response_body is None
    assert mock_session.put.call_count == 1


@pytest.mark.parametrize("processor_id,version", [(None, 7), ("../other", 7), ("", 7), ("proc1", True), ("proc1", -1), ("proc1", 1.0), ("proc1", "7")])
def test_invalid_inputs_never_dispatch(nifi_client, mock_session, processor_id, version):
    with pytest.raises(ValueError):
        nifi_client.run_once_processor(processor_id, version)
    mock_session.put.assert_not_called()


@pytest.mark.asyncio
async def test_readonly_guard_and_exact_write_dispatch():
    client = MagicMock(spec=NiFiClient)
    client.run_once_processor.return_value = {"component": {"id": "proc1"}}
    args = {"processor_id": "proc1", "version": 7}
    blocked = await write_tools.handle("run_once_processor", args, client, readonly=True)
    assert "read-only" in blocked[0].text
    client.run_once_processor.assert_not_called()
    result = await write_tools.handle("run_once_processor", args, client, readonly=False)
    assert json.loads(result[0].text)["component"]["id"] == "proc1"
    client.run_once_processor.assert_called_once_with("proc1", 7)
    client.run_once_processor.side_effect = requests.Timeout("PRIVATE RESPONSE")
    failed = await write_tools.handle("run_once_processor", args, client, readonly=False)
    assert failed[0].text == "Error: write operation failed"


def test_schema_requires_revision_and_has_no_state_override():
    tool = next(t for t in write_tools.TOOLS if t.name == "run_once_processor")
    assert set(tool.inputSchema["required"]) == {"processor_id", "version"}
    assert tool.inputSchema["additionalProperties"] is False
    assert "state" not in tool.inputSchema["properties"]
