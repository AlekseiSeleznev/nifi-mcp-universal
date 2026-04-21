from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import requests

from gateway.nifi.client import NiFiClient


def _make_response(status_code: int, json_data: dict | None = None, text: str = ""):
    resp = MagicMock(spec=requests.Response)
    resp.status_code = status_code
    resp.ok = status_code < 400
    resp.reason = "OK" if status_code < 400 else "Error"
    resp.json.return_value = json_data or {}
    resp.text = text
    resp.content = b"content"
    return resp


@pytest.fixture()
def session():
    s = MagicMock(spec=requests.Session)
    s.headers = {}
    s.verify = True
    s.cert = None
    return s


@pytest.fixture()
def client(session):
    return NiFiClient("https://nifi.example.com/nifi-api", session, timeout_seconds=5)


def test_create_and_update_parameter_context_include_optional_fields(client, session):
    session.post.return_value = _make_response(201, {"id": "ctx"})
    session.put.return_value = _make_response(200, {"id": "ctx"})

    client.create_parameter_context(
        "ctx",
        "desc",
        [{"name": "db.host", "value": "localhost", "sensitive": False, "description": "host"}],
    )
    post_body = session.post.call_args[1]["json"]
    assert post_body["component"]["parameters"][0]["parameter"]["description"] == "host"

    client.update_parameter_context(
        "ctx",
        3,
        name="ctx-new",
        description="updated",
        parameters=[{"name": "db.user", "value": "nifi", "sensitive": True, "description": "user"}],
    )
    put_body = session.put.call_args[1]["json"]
    assert put_body["component"]["name"] == "ctx-new"
    assert put_body["component"]["description"] == "updated"
    assert put_body["component"]["parameters"][0]["parameter"]["description"] == "user"


def test_client_proxy_context_and_parameter_context_without_optional_fields(session):
    client = NiFiClient(
        "https://nifi.example.com/nifi-api",
        session,
        timeout_seconds=5,
        proxy_context_path="/proxy",
    )
    assert session.headers["X-ProxyContextPath"] == "/proxy"

    session.put.return_value = _make_response(200, {"id": "ctx"})
    client.update_parameter_context("ctx", 1, description="", parameters=[{"name": "x", "value": "y"}])
    put_body = session.put.call_args[1]["json"]
    assert put_body["component"]["description"] == ""
    assert "name" not in put_body["component"]
    assert "description" not in put_body["component"]["parameters"][0]["parameter"]

    session.post.return_value = _make_response(200, {"id": "ctx"})
    client.create_parameter_context("ctx")
    assert session.post.call_args[1]["json"]["component"]["parameters"] == []

    client.update_parameter_context("ctx", 2)
    put_body = session.put.call_args[1]["json"]
    assert put_body["component"] == {"id": "ctx"}


@pytest.mark.parametrize(
    ("method_name", "call_args", "expected_path", "expected_json_fragment"),
    [
        ("get_processor_types", (), "flow/processor-types", None),
        ("get_input_ports", ("pg1",), "process-groups/pg1/input-ports", None),
        ("get_output_ports", ("pg1",), "process-groups/pg1/output-ports", None),
        ("create_input_port", ("pg1", "Input", 1.0, 2.0), "process-groups/pg1/input-ports", {"name": "Input"}),
        ("create_output_port", ("pg1", "Output", 1.0, 2.0), "process-groups/pg1/output-ports", {"name": "Output"}),
        ("update_input_port", ("port1", 1, "Input", "RUNNING"), "input-ports/port1", {"state": "RUNNING"}),
        ("update_output_port", ("port1", 1, "Output", "STOPPED"), "output-ports/port1", {"state": "STOPPED"}),
        ("delete_input_port", ("port1", 1), "input-ports/port1", None),
        ("delete_output_port", ("port1", 1), "output-ports/port1", None),
        ("start_input_port", ("port1", 1), "input-ports/port1/run-status", {"state": "RUNNING"}),
        ("stop_input_port", ("port1", 1), "input-ports/port1/run-status", {"state": "STOPPED"}),
        ("start_output_port", ("port1", 1), "output-ports/port1/run-status", {"state": "RUNNING"}),
        ("stop_output_port", ("port1", 1), "output-ports/port1/run-status", {"state": "STOPPED"}),
        ("apply_parameter_context_to_process_group", ("pg1", 2, "ctx1"), "process-groups/pg1", {"id": "pg1"}),
        ("empty_connection_queue", ("conn1",), "flowfile-queues/conn1/drop-requests", {}),
        ("update_controller_service", ("svc1", 3, {"p": "v"}), "controller-services/svc1", {"id": "svc1"}),
        ("get_controller_service", ("svc1",), "controller-services/svc1", None),
        ("delete_controller_service", ("svc1", 4), "controller-services/svc1", None),
    ],
)
def test_client_wrapper_methods_cover_remaining_paths(client, session, method_name, call_args, expected_path, expected_json_fragment):
    session.get.return_value = _make_response(200, {})
    session.post.return_value = _make_response(200, {})
    session.put.return_value = _make_response(200, {})
    session.delete.return_value = _make_response(200, {})

    result = getattr(client, method_name)(*call_args)
    assert result == {}

    if method_name.startswith("get_"):
        url = session.get.call_args[0][0]
        assert url.endswith(expected_path)
    elif method_name.startswith(("create_", "empty_")):
        url = session.post.call_args[0][0]
        assert url.endswith(expected_path)
        if expected_json_fragment is not None:
            payload = session.post.call_args[1]["json"]
            target = payload.get("component", payload)
            assert expected_json_fragment.items() <= target.items()
    elif method_name.startswith(("update_", "start_", "stop_", "apply_")):
        url = session.put.call_args[0][0]
        assert url.endswith(expected_path)
        if expected_json_fragment is not None:
            payload = session.put.call_args[1]["json"]
            target = payload.get("component", payload)
            assert expected_json_fragment.items() <= target.items()
    else:
        url = session.delete.call_args[0][0]
        assert url.endswith(expected_path)


def test_find_controller_services_by_type_and_delete_flags(client, session):
    session.get.return_value = _make_response(
        200,
        {
            "controllerServices": [
                {"component": {"type": "type.a", "id": "1"}},
                {"component": {"type": "type.b", "id": "2"}},
            ]
        },
    )
    matches = client.find_controller_services_by_type("pg1", "type.a")
    assert matches == [{"component": {"type": "type.a", "id": "1"}}]

    session.delete.return_value = _make_response(200, {})
    client.delete_controller_service("svc1", 9, disconnected_ack=True)
    assert session.delete.call_args[1]["params"]["disconnectedNodeAcknowledged"] == "true"


def test_update_ports_without_state_and_healthy_flow(client, session):
    session.put.return_value = _make_response(200, {})
    client.update_input_port("in1", 1, "Input")
    assert "state" not in session.put.call_args[1]["json"]["component"]
    client.update_output_port("out1", 1, "Output")
    assert "state" not in session.put.call_args[1]["json"]["component"]

    with patch.object(client, "list_processors", return_value={"processors": [
            {"component": {"name": "A"}, "status": {"runStatus": "Running"}},
            {"component": {"name": "B"}, "status": {"runStatus": "Disabled"}},
            {"component": {"name": "C"}, "status": {"runStatus": "Running"}},
        ]}), \
         patch.object(client, "get_controller_services", return_value={"controllerServices": [
             {"component": {"name": "svc1", "state": "INVALID"}},
             {"component": {"name": "svc2", "state": "ENABLED"}},
         ]}), \
         patch.object(client, "list_connections", return_value={"connections": [{"status": {"aggregateSnapshot": {"flowFilesQueued": 0, "percentUseCount": 0}}}]}), \
         patch.object(client, "get_bulletins", return_value={"bulletinBoard": {"bulletins": []}}):
        health = client.get_flow_health_status("pg1")
    assert health["processors"]["disabled"] == 1
    assert health["controllerServices"]["invalid"] == 1


def test_get_flow_health_status_healthy_branch(client):
    with patch.object(client, "list_processors", return_value={"processors": [
            {"component": {"name": "A"}, "status": {"runStatus": "Running"}},
            {"component": {"name": "B"}, "status": {"runStatus": "Stopped"}},
        ]}), \
         patch.object(client, "get_controller_services", return_value={"controllerServices": [
             {"component": {"name": "svc", "state": "ENABLED"}},
         ]}), \
         patch.object(client, "list_connections", return_value={"connections": [{"status": {"aggregateSnapshot": {"flowFilesQueued": 0, "percentUseCount": 0}}}]}), \
         patch.object(client, "get_bulletins", return_value={"bulletinBoard": {"bulletins": []}}):
        health = client.get_flow_health_status("pg1")
    assert health["overallHealth"] == "HEALTHY"


def test_get_flow_health_status_loop_branches_for_disabled_and_invalid_continue(client):
    with patch.object(client, "list_processors", return_value={"processors": [
            {"component": {"name": "Disabled 1"}, "status": {"runStatus": "Disabled"}},
            {"component": {"name": "Disabled 2"}, "status": {"runStatus": "Disabled"}},
            {"component": {"name": "Run"}, "status": {"runStatus": "Running"}},
        ]}), \
         patch.object(client, "get_controller_services", return_value={"controllerServices": [
             {"component": {"name": "Bad 1", "state": "INVALID"}},
             {"component": {"name": "Bad 2", "state": "ERROR"}},
             {"component": {"name": "Good", "state": "ENABLED"}},
         ]}), \
         patch.object(client, "list_connections", return_value={"connections": []}), \
         patch.object(client, "get_bulletins", return_value={"bulletinBoard": {"bulletins": []}}):
        health = client.get_flow_health_status("pg1")
    assert health["processors"]["disabled"] == 2
    assert health["controllerServices"]["invalid"] == 2


def test_bulk_start_stop_and_enable_operations_cover_success_failure_and_already_states(client):
    start_processors = {
        "processors": [
            {"id": "p1", "status": {"runStatus": "Running"}, "revision": {"version": 1}, "component": {"name": "A"}},
            {"id": "p2", "status": {"runStatus": "Stopped"}, "revision": {"version": 2}, "component": {"name": "B"}},
            {"id": "p3", "status": {"runStatus": "Stopped"}, "revision": {"version": 3}, "component": {"name": "C"}},
        ]
    }
    stop_processors = {
        "processors": [
            {"id": "p1", "status": {"runStatus": "Running"}, "revision": {"version": 1}, "component": {"name": "A"}},
            {"id": "p2", "status": {"runStatus": "Stopped"}, "revision": {"version": 2}, "component": {"name": "B"}},
            {"id": "p3", "status": {"runStatus": "Running"}, "revision": {"version": 3}, "component": {"name": "C"}},
        ]
    }
    with patch.object(client, "list_processors", side_effect=[start_processors, stop_processors]), \
         patch.object(client, "start_processor", side_effect=[None, RuntimeError("cannot start")]), \
         patch.object(client, "stop_processor", side_effect=[None, RuntimeError("cannot stop")]), \
         patch.object(client, "get_controller_services", return_value={
            "controllerServices": [
                {"id": "s1", "component": {"state": "ENABLED", "name": "S1"}, "revision": {"version": 1}},
                {"id": "s2", "component": {"state": "DISABLED", "name": "S2"}, "revision": {"version": 2}},
                {"id": "s3", "component": {"state": "DISABLED", "name": "S3"}, "revision": {"version": 3}},
            ]
         }), patch.object(client, "enable_controller_service", side_effect=[None, RuntimeError("cannot enable")]):
        started = client.start_all_processors_in_group("pg1")
        stopped = client.stop_all_processors_in_group("pg1")
        enabled = client.enable_all_controller_services_in_group("pg1")

    assert started["already_running"][0]["id"] == "p1"
    assert started["started"][0]["id"] == "p2"
    assert started["failed"][0]["id"] == "p3"
    assert stopped["already_stopped"][0]["id"] == "p2"
    assert stopped["stopped"][0]["id"] == "p1"
    assert stopped["failed"][0]["id"] == "p3"
    assert enabled["already_enabled"][0]["id"] == "s1"
    assert enabled["enabled"][0]["id"] == "s2"
    assert enabled["failed"][0]["id"] == "s3"


def test_get_flow_health_status_covers_health_states(client):
    processors = {
        "processors": [
            {"component": {"name": "Run"}, "status": {"runStatus": "Running"}},
            {"component": {"name": "Stop"}, "status": {"runStatus": "Stopped"}},
            {"component": {"name": "Invalid Proc"}, "status": {"runStatus": "Invalid"}},
            {"component": {"name": "Disabled Proc"}, "status": {"runStatus": "Disabled"}},
        ]
    }
    services = {
        "controllerServices": [
            {"component": {"name": "Good", "state": "ENABLED"}},
            {"component": {"name": "Off", "state": "DISABLED"}},
            {"component": {"name": "Bad", "state": "INVALID"}},
            {"component": {"name": "Err", "state": "ERROR"}},
        ]
    }
    connections = {
        "connections": [
            {"status": {"aggregateSnapshot": {"flowFilesQueued": 0, "percentUseCount": 0}}},
            {"status": {"aggregateSnapshot": {"flowFilesQueued": 2, "percentUseCount": 90}}},
        ]
    }
    bulletins = {
        "bulletinBoard": {
            "bulletins": [
                {"bulletin": {"level": "INFO", "message": "ok", "timestamp": "t1"}},
                {"bulletin": {"level": "WARN", "message": "warn", "timestamp": "t2"}},
                {"bulletin": {"level": "ERROR", "message": "error", "timestamp": "t3"}},
            ]
        }
    }

    with patch.object(client, "list_processors", return_value=processors), \
         patch.object(client, "get_controller_services", return_value=services), \
         patch.object(client, "list_connections", return_value=connections), \
         patch.object(client, "get_bulletins", return_value=bulletins):
        health = client.get_flow_health_status("pg1")

    assert health["processors"]["invalid"] == 1
    assert health["controllerServices"]["invalid"] == 2
    assert health["connections"]["backpressure"] == 1
    assert health["overallHealth"] == "UNHEALTHY"


def test_get_flow_health_status_handles_optional_failures_and_degraded_state(client):
    with patch.object(client, "list_processors", return_value={"processors": []}), \
         patch.object(client, "get_controller_services", side_effect=RuntimeError("no services")), \
         patch.object(client, "list_connections", return_value={
             "connections": [{"status": {"aggregateSnapshot": {"flowFilesQueued": 1, "percentUseCount": 81}}}]
         }), \
         patch.object(client, "get_bulletins", side_effect=RuntimeError("no bulletins")):
        health = client.get_flow_health_status("pg1")

    assert health["overallHealth"] == "DEGRADED"


def test_terminate_processor_stops_normally_or_falls_back_to_thread_delete(client):
    with patch.object(client, "stop_processor", return_value={}) as stop:
        result = client.terminate_processor("p1", 3)
    assert result["status"] == "stopped_normally"
    stop.assert_called_once_with("p1", 3)

    with patch.object(client, "stop_processor", side_effect=RuntimeError("stuck")), \
         patch.object(client, "_delete", return_value={"terminated": True}) as delete:
        result = client.terminate_processor("p2", 4)
    assert result == {"terminated": True}
    assert delete.call_args[0][0] == "processors/p2/threads"
