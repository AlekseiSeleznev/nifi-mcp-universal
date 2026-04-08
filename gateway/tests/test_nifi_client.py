"""Tests for gateway.nifi.client — NiFiClient REST call wrappers."""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch
import requests

from gateway.nifi.client import NiFiClient, NiFiError


def _make_response(status_code: int, json_data: dict = None, text: str = ""):
    resp = MagicMock(spec=requests.Response)
    resp.status_code = status_code
    resp.ok = status_code < 400
    resp.reason = "OK" if status_code < 400 else "Error"
    resp.json.return_value = json_data or {}
    resp.text = text or ""
    resp.content = b"content"
    return resp


# ──────────────────────────────────────────────
#  NiFiError
# ──────────────────────────────────────────────

class TestNiFiError:
    def test_str_includes_status_code(self):
        err = NiFiError("test msg", status_code=409)
        assert "409" in str(err)
        assert "test msg" in str(err)

    def test_str_includes_response_body(self):
        err = NiFiError("fail", status_code=400, response_body="Conflict details")
        assert "Conflict details" in str(err)

    def test_str_without_status(self):
        err = NiFiError("plain error")
        assert "plain error" in str(err)


# ──────────────────────────────────────────────
#  URL construction
# ──────────────────────────────────────────────

class TestNiFiClientUrl:
    def test_url_strips_trailing_slash_from_base(self, mock_session):
        client = NiFiClient("https://nifi.example.com/nifi-api/", mock_session)
        assert client.base_url == "https://nifi.example.com/nifi-api"

    def test_url_builds_correctly(self, mock_session):
        client = NiFiClient("https://nifi.example.com/nifi-api", mock_session)
        assert client._url("flow/about") == "https://nifi.example.com/nifi-api/flow/about"

    def test_url_handles_leading_slash_in_path(self, mock_session):
        client = NiFiClient("https://nifi.example.com/nifi-api", mock_session)
        assert client._url("/flow/about") == "https://nifi.example.com/nifi-api/flow/about"


# ──────────────────────────────────────────────
#  GET / PUT / POST / DELETE wrappers
# ──────────────────────────────────────────────

class TestNiFiClientGet:
    def test_get_success(self, nifi_client, mock_session):
        mock_session.get.return_value = _make_response(200, {"key": "value"})
        result = nifi_client._get("flow/about")
        assert result == {"key": "value"}

    def test_get_raises_nifi_error_on_4xx(self, nifi_client, mock_session):
        mock_session.get.return_value = _make_response(403, text="Forbidden")
        with pytest.raises(NiFiError) as exc_info:
            nifi_client._get("processors/x")
        assert exc_info.value.status_code == 403

    def test_get_passes_params(self, nifi_client, mock_session):
        mock_session.get.return_value = _make_response(200, {})
        nifi_client._get("flow/search", params={"q": "test"})
        call_kwargs = mock_session.get.call_args[1]
        assert call_kwargs["params"] == {"q": "test"}


class TestNiFiClientPut:
    def test_put_success(self, nifi_client, mock_session):
        mock_session.put.return_value = _make_response(200, {"updated": True})
        result = nifi_client._put("processors/abc", {"revision": {"version": 0}})
        assert result == {"updated": True}

    def test_put_raises_on_conflict(self, nifi_client, mock_session):
        mock_session.put.return_value = _make_response(409, text="Conflict")
        with pytest.raises(NiFiError) as exc_info:
            nifi_client._put("processors/abc", {})
        assert exc_info.value.status_code == 409


class TestNiFiClientPost:
    def test_post_success(self, nifi_client, mock_session):
        mock_session.post.return_value = _make_response(201, {"id": "new-id"})
        result = nifi_client._post("process-groups/root/processors", {"component": {}})
        assert result == {"id": "new-id"}

    def test_post_raises_on_error(self, nifi_client, mock_session):
        mock_session.post.return_value = _make_response(400, text="Bad Request")
        with pytest.raises(NiFiError):
            nifi_client._post("process-groups/root/processors", {})


class TestNiFiClientDelete:
    def test_delete_success_with_body(self, nifi_client, mock_session):
        mock_session.delete.return_value = _make_response(200, {"ok": True})
        result = nifi_client._delete("processors/abc", params={"version": 1})
        assert result == {"ok": True}

    def test_delete_empty_body_returns_empty_dict(self, nifi_client, mock_session):
        resp = _make_response(200)
        resp.content = b""
        resp.json.side_effect = Exception("no body")
        mock_session.delete.return_value = resp
        result = nifi_client._delete("processors/abc")
        assert result == {}

    def test_delete_raises_on_error(self, nifi_client, mock_session):
        mock_session.delete.return_value = _make_response(404, text="Not Found")
        with pytest.raises(NiFiError):
            nifi_client._delete("processors/missing")


# ──────────────────────────────────────────────
#  Version detection
# ──────────────────────────────────────────────

class TestVersionDetection:
    def test_get_version_info(self, nifi_client, mock_session):
        mock_session.get.return_value = _make_response(200, {"about": {"version": "2.0.0"}})
        info = nifi_client.get_version_info()
        assert info["about"]["version"] == "2.0.0"

    def test_get_version_tuple_2x(self, nifi_client, mock_session):
        mock_session.get.return_value = _make_response(200, {"about": {"version": "2.0.0"}})
        assert nifi_client.get_version_tuple() == (2, 0, 0)

    def test_get_version_tuple_1x(self, nifi_client, mock_session):
        mock_session.get.return_value = _make_response(200, {"about": {"version": "1.23.2"}})
        assert nifi_client.get_version_tuple() == (1, 23, 2)

    def test_is_nifi_2x_true(self, nifi_client, mock_session):
        mock_session.get.return_value = _make_response(200, {"about": {"version": "2.0.0"}})
        assert nifi_client.is_nifi_2x() is True

    def test_is_nifi_2x_false_for_1x(self, nifi_client, mock_session):
        mock_session.get.return_value = _make_response(200, {"about": {"version": "1.23.2"}})
        assert nifi_client.is_nifi_2x() is False

    def test_version_tuple_cached(self, nifi_client, mock_session):
        mock_session.get.return_value = _make_response(200, {"about": {"version": "2.0.0"}})
        nifi_client.get_version_tuple()
        nifi_client.get_version_tuple()  # second call
        assert mock_session.get.call_count == 1  # only fetched once

    def test_version_detection_failure_defaults_to_1x(self, nifi_client, mock_session):
        mock_session.get.side_effect = Exception("network error")
        version = nifi_client.get_version_tuple()
        assert version == (1, 0, 0)


# ──────────────────────────────────────────────
#  Process group operations
# ──────────────────────────────────────────────

class TestProcessGroupOps:
    def test_get_root_process_group(self, nifi_client, mock_session):
        mock_session.get.return_value = _make_response(200, {"processGroupFlow": {}})
        result = nifi_client.get_root_process_group()
        assert "processGroupFlow" in result

    def test_get_process_group(self, nifi_client, mock_session):
        mock_session.get.return_value = _make_response(200, {"id": "pg1"})
        result = nifi_client.get_process_group("pg1")
        assert result["id"] == "pg1"

    def test_create_process_group(self, nifi_client, mock_session):
        mock_session.post.return_value = _make_response(201, {"id": "new-pg"})
        result = nifi_client.create_process_group("root", "My PG", 10.0, 20.0)
        assert result["id"] == "new-pg"
        call_body = mock_session.post.call_args[1]["json"]
        assert call_body["component"]["name"] == "My PG"

    def test_update_process_group(self, nifi_client, mock_session):
        mock_session.put.return_value = _make_response(200, {"updated": True})
        nifi_client.update_process_group("pg1", 5, "New Name")
        call_body = mock_session.put.call_args[1]["json"]
        assert call_body["component"]["name"] == "New Name"
        assert call_body["revision"]["version"] == 5

    def test_delete_process_group(self, nifi_client, mock_session):
        mock_session.delete.return_value = _make_response(200, {})
        nifi_client.delete_process_group("pg1", 3)
        params = mock_session.delete.call_args[1]["params"]
        assert params["version"] == 3


# ──────────────────────────────────────────────
#  Processor operations
# ──────────────────────────────────────────────

class TestProcessorOps:
    def test_list_processors(self, nifi_client, mock_session):
        mock_session.get.return_value = _make_response(200, {"processors": []})
        result = nifi_client.list_processors("pg1")
        assert "processors" in result

    def test_get_processor(self, nifi_client, mock_session):
        mock_session.get.return_value = _make_response(200, {"component": {"id": "p1"}})
        result = nifi_client.get_processor("p1")
        assert result["component"]["id"] == "p1"

    def test_create_processor(self, nifi_client, mock_session):
        mock_session.post.return_value = _make_response(201, {"id": "new-p"})
        result = nifi_client.create_processor("pg1", "org.apache.nifi.processors.standard.LogAttribute", "LogIt")
        assert result["id"] == "new-p"

    def test_update_processor(self, nifi_client, mock_session):
        mock_session.put.return_value = _make_response(200, {"updated": True})
        nifi_client.update_processor("p1", 2, {"id": "p1", "name": "Updated"})
        call_body = mock_session.put.call_args[1]["json"]
        assert call_body["revision"]["version"] == 2

    def test_delete_processor(self, nifi_client, mock_session):
        mock_session.delete.return_value = _make_response(200, {})
        nifi_client.delete_processor("p1", 1)
        params = mock_session.delete.call_args[1]["params"]
        assert params["version"] == 1

    def test_start_processor(self, nifi_client, mock_session):
        mock_session.put.return_value = _make_response(200, {})
        nifi_client.start_processor("p1", 0)
        call_body = mock_session.put.call_args[1]["json"]
        assert call_body["state"] == "RUNNING"

    def test_stop_processor(self, nifi_client, mock_session):
        mock_session.put.return_value = _make_response(200, {})
        nifi_client.stop_processor("p1", 0)
        call_body = mock_session.put.call_args[1]["json"]
        assert call_body["state"] == "STOPPED"

    def test_get_processor_state(self, nifi_client, mock_session):
        mock_session.get.return_value = _make_response(200, {
            "component": {"state": "RUNNING"}
        })
        state = nifi_client.get_processor_state("p1")
        assert state == "RUNNING"


# ──────────────────────────────────────────────
#  Connection operations
# ──────────────────────────────────────────────

class TestConnectionOps:
    def test_list_connections(self, nifi_client, mock_session):
        mock_session.get.return_value = _make_response(200, {"connections": []})
        result = nifi_client.list_connections("pg1")
        assert "connections" in result

    def test_get_connection(self, nifi_client, mock_session):
        mock_session.get.return_value = _make_response(200, {"id": "conn1"})
        result = nifi_client.get_connection("conn1")
        assert result["id"] == "conn1"

    def test_create_connection(self, nifi_client, mock_session):
        mock_session.post.return_value = _make_response(201, {"id": "new-conn"})
        result = nifi_client.create_connection("pg1", "src", "PROCESSOR", "dst", "PROCESSOR", ["success"])
        assert result["id"] == "new-conn"

    def test_delete_connection(self, nifi_client, mock_session):
        mock_session.delete.return_value = _make_response(200, {})
        nifi_client.delete_connection("conn1", 0)
        params = mock_session.delete.call_args[1]["params"]
        assert params["version"] == 0

    def test_get_connection_queue_size(self, nifi_client, mock_session):
        mock_session.get.return_value = _make_response(200, {
            "status": {
                "aggregateSnapshot": {
                    "flowFilesQueued": 5,
                    "bytesQueued": 1024
                }
            }
        })
        result = nifi_client.get_connection_queue_size("conn1")
        assert result["flowFilesQueued"] == 5
        assert result["bytesQueued"] == 1024

    def test_is_connection_empty_true(self, nifi_client, mock_session):
        mock_session.get.return_value = _make_response(200, {
            "status": {"aggregateSnapshot": {"flowFilesQueued": 0, "bytesQueued": 0}}
        })
        assert nifi_client.is_connection_empty("conn1") is True

    def test_is_connection_empty_false(self, nifi_client, mock_session):
        mock_session.get.return_value = _make_response(200, {
            "status": {"aggregateSnapshot": {"flowFilesQueued": 3, "bytesQueued": 512}}
        })
        assert nifi_client.is_connection_empty("conn1") is False


# ──────────────────────────────────────────────
#  Controller service operations
# ──────────────────────────────────────────────

class TestControllerServiceOps:
    def test_get_controller_services_with_pg(self, nifi_client, mock_session):
        mock_session.get.return_value = _make_response(200, {"controllerServices": []})
        result = nifi_client.get_controller_services("pg1")
        assert "controllerServices" in result
        url = mock_session.get.call_args[0][0]
        assert "pg1" in url

    def test_get_controller_services_without_pg(self, nifi_client, mock_session):
        mock_session.get.return_value = _make_response(200, {"controllerServices": []})
        nifi_client.get_controller_services(None)
        url = mock_session.get.call_args[0][0]
        assert "controller/controller-services" in url

    def test_enable_controller_service(self, nifi_client, mock_session):
        mock_session.put.return_value = _make_response(200, {})
        nifi_client.enable_controller_service("svc1", 0)
        call_body = mock_session.put.call_args[1]["json"]
        assert call_body["state"] == "ENABLED"

    def test_disable_controller_service(self, nifi_client, mock_session):
        mock_session.put.return_value = _make_response(200, {})
        nifi_client.disable_controller_service("svc1", 0)
        call_body = mock_session.put.call_args[1]["json"]
        assert call_body["state"] == "DISABLED"

    def test_create_controller_service(self, nifi_client, mock_session):
        mock_session.post.return_value = _make_response(201, {"id": "svc-new"})
        result = nifi_client.create_controller_service("pg1", "org.apache.nifi.dbcp.DBCPConnectionPool", "MyPool")
        assert result["id"] == "svc-new"

    def test_find_controller_services_by_type(self, nifi_client, mock_session):
        mock_session.get.return_value = _make_response(200, {
            "controllerServices": [
                {"component": {"type": "org.apache.nifi.dbcp.DBCPConnectionPool", "id": "svc1"}},
                {"component": {"type": "org.apache.nifi.ssl.StandardSSLContextService", "id": "svc2"}},
            ]
        })
        result = nifi_client.find_controller_services_by_type("pg1", "org.apache.nifi.dbcp.DBCPConnectionPool")
        assert len(result) == 1
        assert result[0]["component"]["id"] == "svc1"


# ──────────────────────────────────────────────
#  Parameter context operations
# ──────────────────────────────────────────────

class TestParameterContextOps:
    def test_list_parameter_contexts(self, nifi_client, mock_session):
        mock_session.get.return_value = _make_response(200, {"parameterContexts": []})
        result = nifi_client.list_parameter_contexts()
        assert "parameterContexts" in result

    def test_get_parameter_context(self, nifi_client, mock_session):
        mock_session.get.return_value = _make_response(200, {"id": "ctx1"})
        result = nifi_client.get_parameter_context("ctx1")
        assert result["id"] == "ctx1"

    def test_create_parameter_context(self, nifi_client, mock_session):
        mock_session.post.return_value = _make_response(201, {"id": "ctx-new"})
        result = nifi_client.create_parameter_context("MyCtx", "desc",
                                                       [{"name": "host", "value": "localhost", "sensitive": False}])
        assert result["id"] == "ctx-new"
        call_body = mock_session.post.call_args[1]["json"]
        assert call_body["component"]["name"] == "MyCtx"

    def test_delete_parameter_context(self, nifi_client, mock_session):
        mock_session.delete.return_value = _make_response(200, {})
        nifi_client.delete_parameter_context("ctx1", 2)
        params = mock_session.delete.call_args[1]["params"]
        assert params["version"] == 2


# ──────────────────────────────────────────────
#  Bulletins and search
# ──────────────────────────────────────────────

class TestBulletinsAndSearch:
    def test_get_bulletins(self, nifi_client, mock_session):
        mock_session.get.return_value = _make_response(200, {"bulletinBoard": {"bulletins": []}})
        result = nifi_client.get_bulletins()
        assert "bulletinBoard" in result

    def test_get_bulletins_with_since(self, nifi_client, mock_session):
        mock_session.get.return_value = _make_response(200, {"bulletinBoard": {"bulletins": []}})
        nifi_client.get_bulletins(since_ms=12345)
        params = mock_session.get.call_args[1]["params"]
        assert params["after"] == 12345

    def test_search_flow(self, nifi_client, mock_session):
        mock_session.get.return_value = _make_response(200, {"searchResultsDTO": {}})
        nifi_client.search_flow("GenerateFlowFile")
        params = mock_session.get.call_args[1]["params"]
        assert params["q"] == "GenerateFlowFile"


# ──────────────────────────────────────────────
#  Process group summary / health
# ──────────────────────────────────────────────

class TestProcessGroupSummary:
    def _pg_response(self):
        return {
            "processGroupFlow": {
                "flow": {
                    "processors": [
                        {"component": {"state": "RUNNING"}},
                        {"component": {"state": "STOPPED"}},
                    ],
                    "connections": [
                        {"status": {"aggregateSnapshot": {"flowFilesQueued": 0, "bytesQueued": 0}}}
                    ]
                }
            }
        }

    def test_get_process_group_summary(self, nifi_client, mock_session):
        mock_session.get.return_value = _make_response(200, self._pg_response())
        result = nifi_client.get_process_group_summary("pg1")
        assert result["processorCount"] == 2
        assert result["connectionCount"] == 1

    def test_processor_states_counted(self, nifi_client, mock_session):
        mock_session.get.return_value = _make_response(200, self._pg_response())
        result = nifi_client.get_process_group_summary("pg1")
        assert result["processorStates"]["RUNNING"] == 1
        assert result["processorStates"]["STOPPED"] == 1
