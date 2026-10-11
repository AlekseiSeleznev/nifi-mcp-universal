"""Existing connection identity and uncertainty guard for revisioned updates."""
import json
from unittest.mock import MagicMock
import pytest
import requests
from gateway.nifi.client import NiFiError, NiFiClient
from gateway.tools import write_tools

ARGS = {"connection_id": "conn1", "version": 7, "destination_id": "putsql1",
        "destination_type": "PROCESSOR", "destination_group_id": "group1", "relationships": ["Original"]}

def test_update_preserves_identity_and_omits_unowned_fields(nifi_client, mock_session):
    response = mock_session.put.return_value
    response.ok = True
    response.content = b"{}"
    response.json.return_value = {"component": {"id": "conn1"}}
    assert nifi_client.update_connection(**ARGS)["component"]["id"] == "conn1"
    mock_session.put.assert_called_once_with(
        "https://nifi.example.com/nifi-api/connections/conn1", params=None, timeout=5,
        json={"revision": {"version": 7}, "component": {"id": "conn1",
              "destination": {"id": "putsql1", "type": "PROCESSOR", "groupId": "group1"},
              "selectedRelationships": ["Original"]}})

@pytest.mark.parametrize("failure", [requests.Timeout(), requests.ConnectionError()])
def test_ambiguous_transport_has_no_automatic_retry(nifi_client, mock_session, failure):
    mock_session.put.side_effect = failure
    with pytest.raises(type(failure)):
        nifi_client.update_connection(**ARGS)
    assert mock_session.put.call_count == 1

def test_conflict_has_no_retry_or_raw_response(nifi_client, mock_session):
    response = mock_session.put.return_value
    response.ok = False
    response.status_code = 409
    response.reason = "Conflict"
    response.text = "PRIVATE RESPONSE"
    with pytest.raises(NiFiError) as exc:
        nifi_client.update_connection(**ARGS)
    assert "PRIVATE RESPONSE" not in str(exc.value)
    assert mock_session.put.call_count == 1

@pytest.mark.parametrize("patch", [{"version": True}, {"version": -1},
    {"destination_id": "../other"}, {"destination_type": "UNKNOWN"},
    {"relationships": []}, {"relationships": ["Original", "Original"]},
    {"relationships": [" "]}])
def test_invalid_request_never_dispatches(nifi_client, mock_session, patch):
    with pytest.raises(ValueError):
        nifi_client.update_connection(**(ARGS | patch))
    mock_session.put.assert_not_called()

@pytest.mark.asyncio
async def test_readonly_blocks_and_write_dispatch_is_exact():
    client = MagicMock(spec=NiFiClient)
    client.update_connection.return_value = {"component": {"id": "conn1"}}
    blocked = await write_tools.handle("update_connection", ARGS, client, readonly=True)
    assert "read-only" in blocked[0].text
    client.update_connection.assert_not_called()
    result = await write_tools.handle("update_connection", ARGS, client, readonly=False)
    assert json.loads(result[0].text)["component"]["id"] == "conn1"
    client.update_connection.assert_called_once_with("conn1", 7, "putsql1", "PROCESSOR", "group1", ["Original"])

def test_tool_schema_requires_revision_and_rejects_arbitrary_config():
    tool = next(t for t in write_tools.TOOLS if t.name == "update_connection")
    assert "version" in tool.inputSchema["required"]
    assert tool.inputSchema["additionalProperties"] is False
    assert "source" not in tool.inputSchema["properties"]
