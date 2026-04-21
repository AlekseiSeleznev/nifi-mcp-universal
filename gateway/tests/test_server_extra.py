from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest
from starlette.requests import Request

import gateway.server as server_mod


def _scope(path: str, *, headers: list[tuple[bytes, bytes]] | None = None) -> dict:
    return {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "headers": headers or [],
        "client": ("127.0.0.1", 12345),
        "server": ("testserver", 80),
        "root_path": "",
    }


async def _receive_once():
    return {"type": "http.request", "body": b"", "more_body": False}


class _FakeTransport:
    def __init__(self, mcp_session_id: str):
        self.mcp_session_id = mcp_session_id
        self.is_terminated = False
        self.handled = 0

    async def handle_request(self, scope, receive, send):
        assert server_mod._current_session_id.get() == self.mcp_session_id
        self.handled += 1

    @asynccontextmanager
    async def connect(self):
        yield ("read-stream", "write-stream")


@pytest.mark.asyncio
async def test_session_cleanup_loop_runs_once_and_logs_cleanup(monkeypatch):
    calls = {"count": 0}

    async def fake_sleep(_seconds: int):
        calls["count"] += 1
        if calls["count"] > 1:
            raise asyncio.CancelledError

    cleanup = MagicMock(return_value=2)
    monkeypatch.setattr(server_mod.asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(server_mod, "client_manager", MagicMock(cleanup_sessions=cleanup))
    monkeypatch.setattr(server_mod, "log", MagicMock())

    with pytest.raises(asyncio.CancelledError):
        await server_mod._session_cleanup_loop()

    cleanup.assert_called_once()
    server_mod.log.info.assert_called_once()


@pytest.mark.asyncio
async def test_session_cleanup_loop_skips_log_when_nothing_removed(monkeypatch):
    calls = {"count": 0}

    async def fake_sleep(_seconds: int):
        calls["count"] += 1
        if calls["count"] > 1:
            raise asyncio.CancelledError

    manager = MagicMock(cleanup_sessions=MagicMock(return_value=0))
    log = MagicMock()
    monkeypatch.setattr(server_mod.asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(server_mod, "client_manager", manager)
    monkeypatch.setattr(server_mod, "log", log)

    with pytest.raises(asyncio.CancelledError):
        await server_mod._session_cleanup_loop()

    log.info.assert_not_called()


@pytest.mark.asyncio
async def test_session_cleanup_loop_handles_cleanup_exception(monkeypatch):
    calls = {"count": 0}

    async def fake_sleep(_seconds: int):
        calls["count"] += 1
        if calls["count"] > 1:
            raise asyncio.CancelledError

    manager = MagicMock()
    manager.cleanup_sessions.side_effect = RuntimeError("boom")
    monkeypatch.setattr(server_mod.asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(server_mod, "client_manager", manager)
    monkeypatch.setattr(server_mod, "log", MagicMock())

    with pytest.raises(asyncio.CancelledError):
        await server_mod._session_cleanup_loop()

    server_mod.log.exception.assert_called_once()


@pytest.mark.asyncio
async def test_lifespan_restores_saved_connections_and_default(monkeypatch):
    saved_conn = MagicMock(name="saved_conn")
    cleanup_loop_started = asyncio.Event()

    async def fake_cleanup_loop():
        cleanup_loop_started.set()
        await asyncio.sleep(3600)

    registry = MagicMock()
    registry.load.return_value = [{"name": "saved"}]
    registry.get.return_value = saved_conn
    registry.list_all.return_value = []
    manager = MagicMock()

    monkeypatch.setattr(server_mod, "registry", registry)
    monkeypatch.setattr(server_mod, "client_manager", manager)
    monkeypatch.setattr(server_mod, "_session_cleanup_loop", fake_cleanup_loop)
    monkeypatch.setattr(server_mod, "settings", MagicMock(
        port=8085,
        nifi_api_base="https://nifi.example.com/nifi-api",
        nifi_readonly=False,
        verify_ssl=True,
        knox_token="",
        knox_cookie="",
        knox_passcode_token="",
        knox_user="",
        knox_password="",
        knox_gateway_url="",
        nifi_client_p12="",
        nifi_client_p12_password="",
    ))

    server_mod._session_tasks.clear()
    server_mod._transports.clear()

    async with server_mod.lifespan(MagicMock()):
        await cleanup_loop_started.wait()
        task = asyncio.create_task(asyncio.sleep(3600))
        server_mod._session_tasks["session-1"] = task
        server_mod._transports["session-1"] = object()

    registry.add.assert_called_once()
    assert manager.connect.call_count == 2
    manager.close_all.assert_called_once()
    assert server_mod._session_tasks == {}
    assert server_mod._transports == {}


@pytest.mark.asyncio
async def test_lifespan_logs_restore_and_default_connection_failures(monkeypatch):
    conn = MagicMock(name="conn")

    async def fake_cleanup_loop():
        await asyncio.sleep(3600)

    registry = MagicMock()
    registry.load.return_value = [{"name": "saved"}]
    registry.get.return_value = conn
    registry.list_all.return_value = []
    manager = MagicMock()
    manager.connect.side_effect = [RuntimeError("restore"), RuntimeError("default")]
    log = MagicMock()

    monkeypatch.setattr(server_mod, "registry", registry)
    monkeypatch.setattr(server_mod, "client_manager", manager)
    monkeypatch.setattr(server_mod, "_session_cleanup_loop", fake_cleanup_loop)
    monkeypatch.setattr(server_mod, "log", log)
    monkeypatch.setattr(server_mod, "settings", MagicMock(
        port=8085,
        nifi_api_base="https://nifi.example.com/nifi-api",
        nifi_readonly=True,
        verify_ssl=True,
        knox_token="",
        knox_cookie="",
        knox_passcode_token="",
        knox_user="",
        knox_password="",
        knox_gateway_url="",
        nifi_client_p12="",
        nifi_client_p12_password="",
    ))

    async with server_mod.lifespan(MagicMock()):
        pass

    assert log.exception.call_count >= 2


@pytest.mark.asyncio
async def test_lifespan_without_saved_connections_or_default(monkeypatch):
    async def fake_cleanup_loop():
        await asyncio.sleep(3600)

    registry = MagicMock()
    registry.load.return_value = []
    registry.list_all.return_value = ["existing"]
    manager = MagicMock()
    monkeypatch.setattr(server_mod, "registry", registry)
    monkeypatch.setattr(server_mod, "client_manager", manager)
    monkeypatch.setattr(server_mod, "_session_cleanup_loop", fake_cleanup_loop)
    monkeypatch.setattr(server_mod, "settings", MagicMock(
        port=8085,
        nifi_api_base="https://nifi.example.com/nifi-api",
        nifi_readonly=True,
        verify_ssl=True,
        knox_token="",
        knox_cookie="",
        knox_passcode_token="",
        knox_user="",
        knox_password="",
        knox_gateway_url="",
        nifi_client_p12="",
        nifi_client_p12_password="",
    ))

    async with server_mod.lifespan(MagicMock()):
        pass

    registry.add.assert_not_called()


@pytest.mark.asyncio
async def test_lifespan_restores_multiple_saved_connections(monkeypatch):
    async def fake_cleanup_loop():
        await asyncio.sleep(3600)

    conn_a = MagicMock(name="a")
    conn_b = MagicMock(name="b")
    registry = MagicMock()
    registry.load.return_value = [{"name": "a"}, {"name": "b"}]
    registry.get.side_effect = [conn_a, conn_b]
    registry.list_all.return_value = ["already"]
    manager = MagicMock()
    monkeypatch.setattr(server_mod, "registry", registry)
    monkeypatch.setattr(server_mod, "client_manager", manager)
    monkeypatch.setattr(server_mod, "_session_cleanup_loop", fake_cleanup_loop)
    monkeypatch.setattr(server_mod, "settings", MagicMock(
        port=8085,
        nifi_api_base="",
        nifi_readonly=True,
        verify_ssl=True,
        knox_token="",
        knox_cookie="",
        knox_passcode_token="",
        knox_user="",
        knox_password="",
        knox_gateway_url="",
        nifi_client_p12="",
        nifi_client_p12_password="",
    ))

    async with server_mod.lifespan(MagicMock()):
        pass

    assert manager.connect.call_count == 2


@pytest.mark.asyncio
async def test_lifespan_skips_missing_saved_connection_entries(monkeypatch):
    async def fake_cleanup_loop():
        await asyncio.sleep(3600)

    conn_b = MagicMock(name="b")
    registry = MagicMock()
    registry.load.return_value = [{"name": "a"}, {"name": "b"}]
    registry.get.side_effect = [None, conn_b]
    registry.list_all.return_value = ["already"]
    manager = MagicMock()
    monkeypatch.setattr(server_mod, "registry", registry)
    monkeypatch.setattr(server_mod, "client_manager", manager)
    monkeypatch.setattr(server_mod, "_session_cleanup_loop", fake_cleanup_loop)
    monkeypatch.setattr(server_mod, "settings", MagicMock(
        port=8085,
        nifi_api_base="",
        nifi_readonly=True,
        verify_ssl=True,
        knox_token="",
        knox_cookie="",
        knox_passcode_token="",
        knox_user="",
        knox_password="",
        knox_gateway_url="",
        nifi_client_p12="",
        nifi_client_p12_password="",
    ))

    async with server_mod.lifespan(MagicMock()):
        pass

    manager.connect.assert_called_once_with(conn_b)


@pytest.mark.asyncio
async def test_oauth_token_supports_json_payload_and_rejects_bad_grant(monkeypatch):
    monkeypatch.setattr(server_mod, "settings", MagicMock(enable_simple_token_endpoint=True, api_key="secret"))

    scope = _scope("/oauth/token", headers=[(b"content-type", b"application/json")])

    async def receive_json():
        return {
            "type": "http.request",
            "body": json.dumps({"grant_type": "password", "client_secret": "secret"}).encode(),
            "more_body": False,
        }

    request = Request(scope, receive_json)
    response = await server_mod.oauth_token(request)
    assert response.status_code == 400
    assert json.loads(response.body.decode())["error"] == "unsupported_grant_type"


@pytest.mark.asyncio
async def test_oauth_token_defaults_to_client_credentials_without_content_type(monkeypatch):
    monkeypatch.setattr(server_mod, "settings", MagicMock(enable_simple_token_endpoint=True, api_key="secret"))
    request = Request(_scope("/oauth/token"), _receive_once)
    response = await server_mod.oauth_token(request)
    assert response.status_code == 401
    assert json.loads(response.body.decode())["error"] == "invalid_client"


@pytest.mark.asyncio
async def test_run_session_sets_ready_and_runs_mcp_server(monkeypatch):
    ready = asyncio.Event()
    transport = _FakeTransport("session-a")
    fake_server = MagicMock()
    fake_server.run = AsyncMock()
    fake_server.create_initialization_options.return_value = {"x": 1}
    monkeypatch.setattr(server_mod, "mcp_server", fake_server)

    await server_mod._run_session(transport, ready)

    assert ready.is_set() is True
    fake_server.run.assert_awaited_once_with("read-stream", "write-stream", {"x": 1})


@pytest.mark.asyncio
async def test_handle_mcp_rejects_unauthorized_requests(monkeypatch):
    sent: list[dict] = []

    async def send(message):
        sent.append(message)

    monkeypatch.setattr(server_mod, "settings", MagicMock(api_key="secret"))

    await server_mod.handle_mcp(_scope("/mcp"), _receive_once, send)

    assert sent[0]["status"] == 401


@pytest.mark.asyncio
async def test_handle_mcp_uses_compare_digest(monkeypatch):
    sent: list[dict] = []
    calls = []

    async def send(message):
        sent.append(message)

    def fake_compare_digest(left, right):
        calls.append((left, right))
        return False

    monkeypatch.setattr(server_mod, "settings", MagicMock(api_key="secret"))
    monkeypatch.setattr(server_mod.hmac, "compare_digest", fake_compare_digest)

    await server_mod.handle_mcp(_scope("/mcp", headers=[(b"authorization", b"Bearer secret")]), _receive_once, send)

    assert sent[0]["status"] == 401
    assert calls == [("secret", "secret")]


@pytest.mark.asyncio
async def test_handle_mcp_creates_transport_and_resets_session_context(monkeypatch):
    sent: list[dict] = []

    async def send(message):
        sent.append(message)

    async def fake_run_session(_transport, ready):
        ready.set()

    monkeypatch.setattr(server_mod, "settings", MagicMock(api_key=""))
    monkeypatch.setattr(server_mod, "StreamableHTTPServerTransport", _FakeTransport)
    monkeypatch.setattr(server_mod, "_run_session", fake_run_session)

    server_mod._session_tasks.clear()
    server_mod._transports.clear()

    await server_mod.handle_mcp(_scope("/mcp"), _receive_once, send)

    assert len(server_mod._transports) == 1
    transport = next(iter(server_mod._transports.values()))
    assert transport.handled == 1
    assert server_mod._current_session_id.get() is None

    for task in server_mod._session_tasks.values():
        await task
    server_mod._session_tasks.clear()
    server_mod._transports.clear()


@pytest.mark.asyncio
async def test_handle_mcp_reuses_existing_transport(monkeypatch):
    transport = _FakeTransport("session-a")
    server_mod._transports.clear()
    server_mod._session_tasks.clear()
    server_mod._transports["session-a"] = transport
    monkeypatch.setattr(server_mod, "settings", MagicMock(api_key="secret"))

    await server_mod.handle_mcp(
        _scope("/mcp", headers=[(b"authorization", b"Bearer secret"), (b"mcp-session-id", b"session-a")]),
        _receive_once,
        AsyncMock(),
    )

    assert transport.handled == 1
    assert server_mod._current_session_id.get() is None
    server_mod._transports.clear()


@pytest.mark.asyncio
async def test_handle_mcp_replaces_terminated_transport(monkeypatch):
    sent: list[dict] = []

    async def send(message):
        sent.append(message)

    async def fake_run_session(_transport, ready):
        ready.set()

    old_transport = _FakeTransport("existing")
    old_transport.is_terminated = True
    server_mod._transports.clear()
    server_mod._session_tasks.clear()
    server_mod._transports["existing"] = old_transport

    monkeypatch.setattr(server_mod, "settings", MagicMock(api_key=""))
    monkeypatch.setattr(server_mod, "StreamableHTTPServerTransport", _FakeTransport)
    monkeypatch.setattr(server_mod, "_run_session", fake_run_session)

    await server_mod.handle_mcp(
        _scope("/mcp", headers=[(b"mcp-session-id", b"existing")]),
        _receive_once,
        send,
    )

    assert server_mod._transports["existing"] is not old_transport
    for task in server_mod._session_tasks.values():
        await task
    server_mod._session_tasks.clear()
    server_mod._transports.clear()


@pytest.mark.asyncio
async def test_dashboard_docs_and_dashboard_routes(monkeypatch):
    request = Request(_scope("/dashboard/docs"), _receive_once)
    request._query_params = {"lang": "en"}

    with pytest.MonkeyPatch.context() as mp:
        render_docs = MagicMock(return_value="<p>docs</p>")
        mp.setattr("gateway.web_ui.render_docs", render_docs)
        response = await server_mod.dashboard_docs(request)

    assert response.status_code == 200
    assert response.body == b"<p>docs</p>"
    assert any(route.path == "/dashboard" for route in server_mod._dashboard_routes())


@pytest.mark.asyncio
async def test_app_routes_mcp_requests_to_handle_mcp(monkeypatch):
    handle = AsyncMock()
    inner = AsyncMock()
    monkeypatch.setattr(server_mod, "handle_mcp", handle)
    monkeypatch.setattr(server_mod, "_inner", inner)

    await server_mod.app(_scope("/mcp"), _receive_once, AsyncMock())
    handle.assert_awaited_once()

    await server_mod.app(_scope("/health"), _receive_once, AsyncMock())
    inner.assert_awaited_once()
