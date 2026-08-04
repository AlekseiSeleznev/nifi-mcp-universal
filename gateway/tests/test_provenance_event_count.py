"""Focused tests for the safe provenance event-count read tool."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
import requests
from gateway.nifi.client import NiFiClient, NiFiError
from gateway.tools import read_tools

from gateway import mcp_server

START = "2026-08-04T00:00:00Z"
END = "2026-08-04T00:30:00Z"


def _response(status_code: int, payload: dict | None = None):
    response = MagicMock(spec=requests.Response)
    response.status_code = status_code
    response.ok = status_code < 400
    response.reason = "OK" if response.ok else "Error"
    response.content = b"content"
    response.text = json.dumps(payload or {})
    response.json.return_value = payload or {}
    return response


def _client(session: MagicMock) -> NiFiClient:
    return NiFiClient("https://nifi.example.test/nifi-api", session, timeout_seconds=1)


def _arguments(event_type: str | None = None) -> dict:
    args = {"component_id": "processor-1", "start_time": START, "end_time": END}
    if event_type is not None:
        args["event_type"] = event_type
    return args


def _parse(result) -> dict:
    return json.loads(result[0].text)


def test_tool_schema_is_strict_and_has_only_bounded_filters():
    tool = next(tool for tool in read_tools.TOOLS if tool.name == "get_provenance_event_count")

    assert tool.inputSchema == {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "component_id": {"type": "string", "minLength": 1, "maxLength": 128},
            "start_time": {"type": "string", "format": "date-time"},
            "end_time": {"type": "string", "format": "date-time"},
            "event_type": {
                "type": "string",
                "enum": [
                    "ADDINFO",
                    "ATTRIBUTES_MODIFIED",
                    "CLONE",
                    "CONTENT_MODIFIED",
                    "CREATE",
                    "DOWNLOAD",
                    "DROP",
                    "EXPIRE",
                    "FETCH",
                    "FORK",
                    "JOIN",
                    "RECEIVE",
                    "REMOTE_INVOCATION",
                    "REPLAY",
                    "ROUTE",
                    "SEND",
                    "UNKNOWN",
                    "UPLOAD",
                ],
            },
        },
        "required": ["component_id", "start_time", "end_time"],
    }


@pytest.mark.asyncio
async def test_schema_validation_rejects_raw_search_and_does_not_call_client():
    client = MagicMock(spec=NiFiClient)

    result = await read_tools.handle(
        "get_provenance_event_count",
        {**_arguments(), "raw_search": {"filename": "employee.csv"}},
        client,
    )

    assert "Error" in result[0].text
    client.get_provenance_event_count.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "arguments",
    [
        {"component_id": "processor/1", "start_time": START, "end_time": END},
        {"component_id": "processor-1", "start_time": "2026-08-04T00:00:00", "end_time": END},
        {"component_id": "processor-1", "start_time": END, "end_time": START},
        {"component_id": "processor-1", "start_time": START, "end_time": "2026-08-05T00:00:01Z"},
        {**_arguments(), "event_type": "NOT_A_NIFI_EVENT"},
    ],
)
async def test_schema_validation_rejects_unbounded_or_unsafe_values(arguments):
    client = MagicMock(spec=NiFiClient)

    result = await read_tools.handle("get_provenance_event_count", arguments, client)

    assert "Error" in result[0].text
    client.get_provenance_event_count.assert_not_called()


def test_success_uses_exact_safe_filter_and_returns_no_raw_provenance():
    session = MagicMock(spec=requests.Session)
    session.headers = {}
    session.post.return_value = _response(200, {"provenance": {"id": "query-1", "uri": "https://secret/query-1"}})
    session.get.return_value = _response(
        200,
        {
            "provenance": {
                "finished": True,
                "results": {
                    "totalCount": 7,
                    "errors": [],
                    "provenanceEvents": [
                        {"filename": "employee.csv", "attributes": [{"name": "secret"}], "uri": "https://secret"}
                    ],
                },
            }
        },
    )
    session.delete.return_value = _response(200, {})

    result = _client(session).get_provenance_event_count(**_arguments("RECEIVE"))

    assert result == {"finished": True, "total_count": 7, "error_count": 0, "cleanup_status": "success"}
    assert "query-1" not in json.dumps(result)
    assert "employee.csv" not in json.dumps(result)
    assert "secret" not in json.dumps(result)

    post_body = session.post.call_args.kwargs["json"]
    assert post_body == {
        "provenance": {
            "request": {
                "searchTerms": {
                    "ProcessorID": {"value": "processor-1", "inverse": False},
                    "EventType": {"value": "RECEIVE", "inverse": False},
                },
                "startDate": START,
                "endDate": END,
                "summarize": True,
                "incrementalResults": False,
            }
        }
    }
    assert session.post.call_args.args[0].endswith("/provenance")
    assert session.get.call_args.args[0].endswith("/provenance/query-1")
    assert session.delete.call_args.args[0].endswith("/provenance/query-1")


def test_success_without_optional_event_type_does_not_add_a_raw_filter():
    session = MagicMock(spec=requests.Session)
    session.headers = {}
    session.post.return_value = _response(200, {"provenance": {"id": "query-2"}})
    session.get.return_value = _response(
        200,
        {"provenance": {"finished": True, "results": {"totalCount": 0, "errors": []}}},
    )
    session.delete.return_value = _response(200, {})

    _client(session).get_provenance_event_count(**_arguments())

    search_terms = session.post.call_args.kwargs["json"]["provenance"]["request"]["searchTerms"]
    assert search_terms == {"ProcessorID": {"value": "processor-1", "inverse": False}}


def test_incomplete_polling_stays_unknown_until_a_later_finished_get():
    session = MagicMock(spec=requests.Session)
    session.headers = {}
    session.post.return_value = _response(200, {"provenance": {"id": "query-3"}})
    session.get.side_effect = [
        _response(200, {"provenance": {"finished": False, "results": {"totalCount": 0}}}),
        _response(200, {"provenance": {"finished": True, "results": {"totalCount": 2, "errors": []}}}),
    ]
    session.delete.return_value = _response(200, {})

    with patch("gateway.nifi.client.time.sleep") as sleep:
        result = _client(session).get_provenance_event_count(**_arguments())

    assert result == {"finished": True, "total_count": 2, "error_count": 0, "cleanup_status": "success"}
    assert session.get.call_count == 2
    sleep.assert_called_once()


def test_timeout_returns_unknown_counts_and_still_cleans_up():
    session = MagicMock(spec=requests.Session)
    session.headers = {}
    session.post.return_value = _response(200, {"provenance": {"id": "query-timeout"}})
    session.get.return_value = _response(200, {"provenance": {"finished": False}})
    session.delete.return_value = _response(200, {})

    with patch("gateway.nifi.client.time.monotonic", side_effect=[0.0, 2.0]), patch(
        "gateway.nifi.client.time.sleep"
    ):
        result = _client(session).get_provenance_event_count(
            **_arguments(), poll_timeout_seconds=1.0, poll_interval_seconds=0.0
        )

    assert result == {"finished": False, "total_count": None, "error_count": None, "cleanup_status": "success"}
    assert session.get.call_count == 1
    session.delete.assert_called_once()


def test_submit_failure_is_fail_closed_without_retry_or_cleanup():
    session = MagicMock(spec=requests.Session)
    session.headers = {}
    session.post.return_value = _response(401, {"error": "sensitive auth details"})

    result = _client(session).get_provenance_event_count(**_arguments())

    assert result == {
        "finished": False,
        "total_count": None,
        "error_count": None,
        "cleanup_status": "not_attempted",
    }
    assert session.post.call_count == 1
    session.get.assert_not_called()
    session.delete.assert_not_called()
    assert "sensitive" not in json.dumps(result)


def test_submit_transport_failure_is_single_attempt():
    session = MagicMock(spec=requests.Session)
    session.headers = {}
    session.post.side_effect = requests.ConnectionError("temporary transport failure")

    result = _client(session).get_provenance_event_count(**_arguments())

    assert result == {
        "finished": False,
        "total_count": None,
        "error_count": None,
        "cleanup_status": "not_attempted",
    }
    assert session.post.call_count == 1
    session.get.assert_not_called()
    session.delete.assert_not_called()


def test_get_failure_is_fail_closed_and_delete_is_attempted_once():
    session = MagicMock(spec=requests.Session)
    session.headers = {}
    session.post.return_value = _response(200, {"provenance": {"id": "query-get-fail"}})
    session.get.return_value = _response(403, {"error": "private error"})
    session.delete.return_value = _response(200, {})

    result = _client(session).get_provenance_event_count(**_arguments())

    assert result == {"finished": False, "total_count": None, "error_count": None, "cleanup_status": "success"}
    assert session.get.call_count == 1
    assert session.delete.call_count == 1
    assert "private error" not in json.dumps(result)


def test_cleanup_failure_is_not_reported_as_success():
    session = MagicMock(spec=requests.Session)
    session.headers = {}
    session.post.return_value = _response(200, {"provenance": {"id": "query-cleanup"}})
    session.get.return_value = _response(200, {"provenance": {"finished": True, "results": {"totalCount": 1}}})
    session.delete.return_value = _response(500, {"error": "private cleanup error"})

    result = _client(session).get_provenance_event_count(**_arguments())

    assert result == {"finished": False, "total_count": None, "error_count": None, "cleanup_status": "failure"}
    assert "private cleanup error" not in json.dumps(result)


def test_malformed_finished_response_does_not_turn_missing_count_into_zero():
    session = MagicMock(spec=requests.Session)
    session.headers = {}
    session.post.return_value = _response(200, {"provenance": {"id": "query-malformed"}})
    session.get.return_value = _response(200, {"provenance": {"finished": True, "results": {}}})
    session.delete.return_value = _response(200, {})

    result = _client(session).get_provenance_event_count(**_arguments())

    assert result == {"finished": False, "total_count": None, "error_count": None, "cleanup_status": "success"}


def test_single_attempt_json_helper_rejects_empty_invalid_and_non_object_responses():
    session = MagicMock(spec=requests.Session)
    session.headers = {}
    client = _client(session)

    empty = _response(200, {})
    empty.content = b""
    session.get.return_value = empty
    assert client._get_once("provenance/query") == {}

    invalid = _response(200, {})
    invalid.json.side_effect = ValueError("invalid")
    session.get.return_value = invalid
    with pytest.raises(NiFiError, match="invalid JSON"):
        client._get_once("provenance/query")

    non_object = _response(200, {})
    non_object.json.return_value = []
    session.get.return_value = non_object
    with pytest.raises(NiFiError, match="invalid response shape"):
        client._get_once("provenance/query")

    assert session.get.call_count == 3


@pytest.mark.parametrize(
    "start_time",
    [None, "x" * 65, "not-a-timestamp"],
)
def test_client_validation_rejects_non_string_long_and_malformed_timestamps(start_time):
    client = _client(MagicMock(spec=requests.Session))

    with pytest.raises(ValueError):
        client.get_provenance_event_count("processor-1", start_time, END)


def test_invalid_query_id_is_unknown_without_poll_or_cleanup():
    session = MagicMock(spec=requests.Session)
    session.headers = {}
    session.post.return_value = _response(200, {"provenance": {"id": "query/unsafe"}})

    result = _client(session).get_provenance_event_count(**_arguments())

    assert result == {"finished": False, "total_count": None, "error_count": None, "cleanup_status": "unknown"}
    session.get.assert_not_called()
    session.delete.assert_not_called()


def test_finished_result_with_non_object_results_is_unknown():
    session = MagicMock(spec=requests.Session)
    session.headers = {}
    session.post.return_value = _response(200, {"provenance": {"id": "query-results-shape"}})
    session.get.return_value = _response(
        200, {"provenance": {"finished": True, "results": []}}
    )
    session.delete.return_value = _response(200, {})

    result = _client(session).get_provenance_event_count(**_arguments())

    assert result == {"finished": False, "total_count": None, "error_count": None, "cleanup_status": "success"}


def test_finished_result_with_non_list_errors_is_unknown():
    session = MagicMock(spec=requests.Session)
    session.headers = {}
    session.post.return_value = _response(200, {"provenance": {"id": "query-errors-shape"}})
    session.get.return_value = _response(
        200,
        {"provenance": {"finished": True, "results": {"totalCount": 1, "errors": {}}}},
    )
    session.delete.return_value = _response(200, {})

    result = _client(session).get_provenance_event_count(**_arguments())

    assert result == {"finished": False, "total_count": None, "error_count": None, "cleanup_status": "success"}


@pytest.mark.parametrize(
    "cleanup_error",
    [
        NiFiError("cleanup transport"),
        requests.ConnectionError("cleanup transport"),
        requests.Timeout("cleanup transport"),
        RuntimeError("cleanup transport"),
    ],
)
def test_cleanup_transport_ambiguity_fails_closed(cleanup_error):
    session = MagicMock(spec=requests.Session)
    session.headers = {}
    session.post.return_value = _response(200, {"provenance": {"id": "query-cleanup-unknown"}})
    session.get.return_value = _response(
        200, {"provenance": {"finished": True, "results": {"totalCount": 4, "errors": []}}}
    )
    session.delete.side_effect = cleanup_error

    result = _client(session).get_provenance_event_count(**_arguments())

    assert result == {"finished": False, "total_count": None, "error_count": None, "cleanup_status": "unknown"}
    assert "cleanup transport" not in json.dumps(result)


@pytest.mark.asyncio
async def test_read_tool_dispatch_works_for_readonly_connection():
    client = MagicMock(spec=NiFiClient)
    client.get_provenance_event_count.return_value = {
        "finished": True,
        "total_count": 3,
        "error_count": 0,
        "cleanup_status": "success",
    }

    with patch.object(mcp_server.client_manager, "get_client", return_value=client), patch.object(
        mcp_server.client_manager, "get_connection_info", return_value=MagicMock(readonly=True)
    ), patch.object(mcp_server, "_get_session_id", return_value=None):
        result = await mcp_server.call_tool("get_provenance_event_count", _arguments())

    assert _parse(result)["total_count"] == 3
    client.get_provenance_event_count.assert_called_once_with("processor-1", START, END, None)
