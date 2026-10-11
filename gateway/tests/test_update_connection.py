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

@pytest.mark.parametrize("source_type", ["OUTPUT_PORT", "INPUT_PORT"])
def test_port_source_retarget_omits_relationships_and_preserves_source(nifi_client, mock_session, source_type):
    response = mock_session.put.return_value
    response.ok = True
    response.content = b"{}"
    response.json.return_value = {"component": {"id": "conn1", "source": {"type": source_type}}}
    args = {k: v for k, v in ARGS.items() if k != "relationships"}
    assert nifi_client.update_connection(**args)["component"]["source"]["type"] == source_type
    assert mock_session.put.call_count == 1
    component = mock_session.put.call_args.kwargs["json"]["component"]
    assert component == {"id": "conn1", "destination": {"id": "putsql1", "type": "PROCESSOR", "groupId": "group1"}}
    assert "selectedRelationships" not in component
    assert "source" not in component


def test_relationship_only_update_omits_destination(nifi_client, mock_session):
    response = mock_session.put.return_value
    response.ok = True
    response.content = b"{}"
    response.json.return_value = {}
    nifi_client.update_connection("conn1", 7, relationships=["success"])
    assert mock_session.put.call_args.kwargs["json"] == {
        "revision": {"version": 7}, "component": {"id": "conn1", "selectedRelationships": ["success"]}}
    assert mock_session.put.call_count == 1


@pytest.mark.parametrize("args", [
    {"connection_id": "conn1", "version": 7},
    {"connection_id": None, "version": 7, "relationships": ["success"]},
    {"connection_id": "../bad", "version": 7, "relationships": ["success"]},
    {"connection_id": "conn1", "version": 7, "destination_id": "dest"},
    {"connection_id": "conn1", "version": 7, "destination_type": "PROCESSOR"},
    {"connection_id": "conn1", "version": 7, "destination_group_id": "group"},
    ARGS | {"destination_group_id": "../bad"},
    ARGS | {"destination_type": None},
    ARGS | {"relationships": "success"},
    ARGS | {"relationships": [None]},
])
def test_optional_update_invalid_branches_do_not_dispatch(nifi_client, mock_session, args):
    with pytest.raises(ValueError):
        nifi_client.update_connection(**args)
    mock_session.put.assert_not_called()


@pytest.mark.asyncio
async def test_port_destination_only_tool_dispatch_and_readonly():
    args = {k: v for k, v in ARGS.items() if k != "relationships"}
    client = MagicMock(spec=NiFiClient)
    client.update_connection.return_value = {"component": {"id": "conn1"}}
    blocked = await write_tools.handle("update_connection", args, client, readonly=True)
    assert "read-only" in blocked[0].text
    client.update_connection.assert_not_called()
    result = await write_tools.handle("update_connection", args, client, readonly=False)
    assert json.loads(result[0].text)["component"]["id"] == "conn1"
    client.update_connection.assert_called_once_with("conn1", 7, "putsql1", "PROCESSOR", "group1", None)


def test_optional_schema_requires_one_complete_change():
    from jsonschema import Draft202012Validator, ValidationError
    tool = next(t for t in write_tools.TOOLS if t.name == "update_connection")
    validator = Draft202012Validator(tool.inputSchema)
    validator.validate({k: v for k, v in ARGS.items() if k != "relationships"})
    validator.validate({"connection_id": "conn1", "version": 7, "relationships": ["success"]})
    for args in [
        {"connection_id": "conn1", "version": 7},
        {"connection_id": "conn1", "version": 7, "destination_id": "dest", "relationships": ["success"]},
        ARGS | {"relationships": []},
    ]:
        with pytest.raises(ValidationError):
            validator.validate(args)
