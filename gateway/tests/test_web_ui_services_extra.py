from __future__ import annotations

import json
import re
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from gateway.nifi_registry import ConnectionInfo
from gateway.web_ui_helpers import check_api_auth, error_response, json_response, render_dashboard
from gateway.web_ui_services import connect_from_request, edit_from_request, test_from_request as run_test_from_request


class _DummyUpload:
    def __init__(self, filename: str, data: bytes):
        self.filename = filename
        self._data = data

    async def read(self) -> bytes:
        return self._data


class _DummyRequest:
    def __init__(self, *, headers: dict[str, str], body=None):
        self.headers = headers
        self._body = body or {}

    async def json(self):
        return self._body

    async def form(self):
        return self._body


def _body(response) -> dict:
    return json.loads(response.body.decode())


def _fake_built_client(version: str = "2.1.0"):
    client = MagicMock()
    client.get_version_info.return_value = {"about": {"version": version}}
    client.session.close = MagicMock()
    return client


CONN_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,62}$")


def test_web_ui_helper_responses_and_dashboard_render(monkeypatch):
    resp = json_response({"value": "тест"})
    assert '"тест"' in resp.body.decode()

    err = error_response("boom", 418, ok=False)
    assert _body(err) == {"error": "boom", "ok": False}

    monkeypatch.setattr("gateway.web_ui_helpers.settings.api_key", "")
    assert check_api_auth(_DummyRequest(headers={})) is None

    monkeypatch.setattr("gateway.web_ui_helpers.settings.api_key", "secret")
    denied = check_api_auth(_DummyRequest(headers={}))
    assert denied.status_code == 401

    allowed = check_api_auth(_DummyRequest(headers={"Authorization": "Bearer secret"}))
    assert allowed is None

    html = render_dashboard('"><script>alert(1)</script>')
    assert "lang=\"ru\"" in html
    assert "<script>alert(1)</script>" not in html


def test_web_ui_helper_auth_uses_compare_digest(monkeypatch):
    calls = []

    def fake_compare_digest(left, right):
        calls.append((left, right))
        return True

    monkeypatch.setattr("gateway.web_ui_helpers.settings.api_key", "secret")
    monkeypatch.setattr("gateway.web_ui_helpers.hmac.compare_digest", fake_compare_digest)
    assert check_api_auth(_DummyRequest(headers={"Authorization": "Bearer secret"})) is None
    assert calls == [("secret", "secret")]


def test_web_ui_helper_rejects_invalid_content_length(monkeypatch):
    monkeypatch.setattr("gateway.web_ui_helpers.settings.api_key", "")
    denied = check_api_auth(_DummyRequest(headers={}))
    assert denied is None

    from gateway.web_ui_helpers import enforce_content_length

    response = enforce_content_length(_DummyRequest(headers={"content-length": "oops"}), 10)
    assert response.status_code == 400
    assert _body(response)["error"] == "invalid content-length"


@pytest.mark.asyncio
async def test_connect_from_request_json_paths(monkeypatch, tmp_path: Path):
    registry = MagicMock()
    manager = MagicMock()

    missing = await connect_from_request(
        _DummyRequest(headers={"content-type": "application/json"}, body={"url": "https://nifi"}),
        registry=registry,
        client_manager=manager,
        certs_dir=str(tmp_path),
        conn_name_re=CONN_RE,
        connection_info_cls=ConnectionInfo,
    )
    assert missing.status_code == 400

    invalid = await connect_from_request(
        _DummyRequest(headers={"content-type": "application/json"}, body={"name": "bad name", "url": "https://nifi"}),
        registry=registry,
        client_manager=manager,
        certs_dir=str(tmp_path),
        conn_name_re=CONN_RE,
        connection_info_cls=ConnectionInfo,
    )
    assert invalid.status_code == 400

    manager.connect.side_effect = RuntimeError("connect failed")
    failed = await connect_from_request(
        _DummyRequest(
            headers={"content-type": "application/json"},
            body={"name": "prod", "url": "https://nifi.example.com/nifi-api", "auth_method": "none"},
        ),
        registry=registry,
        client_manager=manager,
        certs_dir=str(tmp_path),
        conn_name_re=CONN_RE,
        connection_info_cls=ConnectionInfo,
    )
    assert failed.status_code == 502
    assert _body(failed)["error"] == "connection failed"
    registry.remove.assert_called_with("prod")


@pytest.mark.asyncio
async def test_connect_from_request_multipart_handles_files_and_size_limits(tmp_path: Path, monkeypatch):
    registry = MagicMock()
    manager = MagicMock()
    chmod_calls = []

    def fake_chmod(path, mode):
        chmod_calls.append((Path(path).name, mode))

    monkeypatch.setattr("gateway.web_ui_services.os.chmod", fake_chmod)
    request = _DummyRequest(
        headers={"content-type": "multipart/form-data"},
        body={
            "name": "prod",
            "url": "https://nifi.example.com/nifi-api",
            "auth_method": "certificate_pem",
            "verify_ssl": "false",
            "readonly": "false",
            "cert_file": _DummyUpload("../cert.pem", b"CERT"),
            "key_file": _DummyUpload("../key.pem", b"KEY"),
            "cert_password": "pw",
            "knox_token": "token",
        },
    )

    response = await connect_from_request(
        request,
        registry=registry,
        client_manager=manager,
        certs_dir=str(tmp_path),
        conn_name_re=CONN_RE,
        connection_info_cls=ConnectionInfo,
    )

    assert response.status_code == 200
    added_conn = registry.add.call_args[0][0]
    assert added_conn.cert_path == "prod/cert.pem"
    assert added_conn.cert_key_path == "prod/key.pem"
    assert (tmp_path / "prod" / "cert.pem").read_bytes() == b"CERT"
    assert (tmp_path / "prod" / "key.pem").read_bytes() == b"KEY"
    assert chmod_calls == [("cert.pem", 0o600), ("key.pem", 0o600)]

    too_large = await connect_from_request(
        _DummyRequest(
            headers={"content-type": "multipart/form-data"},
            body={
                "name": "prod",
                "url": "https://nifi.example.com/nifi-api",
                "cert_file": _DummyUpload("cert.pem", b"x" * (1024 * 1024 + 1)),
            },
        ),
        registry=registry,
        client_manager=manager,
        certs_dir=str(tmp_path),
        conn_name_re=CONN_RE,
        connection_info_cls=ConnectionInfo,
    )
    assert too_large.status_code == 400

    invalid_name = await connect_from_request(
        _DummyRequest(
            headers={"content-type": "multipart/form-data"},
            body={"name": "bad name", "url": "https://nifi.example.com/nifi-api"},
        ),
        registry=registry,
        client_manager=manager,
        certs_dir=str(tmp_path),
        conn_name_re=CONN_RE,
        connection_info_cls=ConnectionInfo,
    )
    assert invalid_name.status_code == 400

    no_key = await connect_from_request(
        _DummyRequest(
            headers={"content-type": "multipart/form-data"},
            body={
                "name": "prod2",
                "url": "https://nifi.example.com/nifi-api",
                "cert_file": _DummyUpload("cert.pem", b"CERT"),
            },
        ),
        registry=registry,
        client_manager=manager,
        certs_dir=str(tmp_path),
        conn_name_re=CONN_RE,
        connection_info_cls=ConnectionInfo,
    )
    assert no_key.status_code == 200

    too_large_body = await connect_from_request(
        _DummyRequest(
            headers={"content-type": "multipart/form-data", "content-length": str(3 * 1024 * 1024 + 1)},
            body={"name": "prod3", "url": "https://nifi.example.com/nifi-api"},
        ),
        registry=registry,
        client_manager=manager,
        certs_dir=str(tmp_path),
        conn_name_re=CONN_RE,
        connection_info_cls=ConnectionInfo,
    )
    assert too_large_body.status_code == 413


@pytest.mark.asyncio
async def test_edit_from_request_json_updates_and_preserves_sensitive_values(tmp_path: Path):
    old_conn = ConnectionInfo(
        name="old",
        url="https://nifi.example.com/nifi-api",
        auth_method="basic",
        knox_token="old-token",
        knox_cookie="old-cookie",
        knox_passcode="old-passcode",
        knox_user="old-user",
        knox_password="old-password",
        knox_gateway_url="https://gateway",
        verify_ssl=False,
        readonly=False,
    )
    registry = MagicMock(active="old")
    registry.get.return_value = old_conn
    manager = MagicMock()
    fake_client = _fake_built_client()

    response = await edit_from_request(
        _DummyRequest(
            headers={"content-type": "application/json"},
            body={
                "old_name": "old",
                "name": "new",
                "url": "https://nifi.example.com/nifi-api",
                "knox_token": "***",
            },
        ),
        registry=registry,
        client_manager=manager,
        certs_dir=str(tmp_path),
        conn_name_re=CONN_RE,
        connection_info_cls=ConnectionInfo,
        build_client=MagicMock(return_value=fake_client),
    )

    assert response.status_code == 200
    edited = registry.add.call_args[0][0]
    assert edited.knox_token == "old-token"
    assert edited.knox_password == "old-password"
    assert edited.verify_ssl is False
    assert edited.readonly is False
    assert registry.active == "new"
    registry.save.assert_called_once()


@pytest.mark.asyncio
async def test_edit_from_request_covers_invalid_name_bool_fields_and_saved_default(tmp_path: Path):
    registry = MagicMock(active="other-default")
    old_conn = ConnectionInfo(
        name="old",
        url="https://nifi.example.com/nifi-api",
        auth_method="none",
        verify_ssl=True,
        readonly=True,
    )
    registry.get.return_value = old_conn
    manager = MagicMock()
    fake_client = _fake_built_client()

    invalid = await edit_from_request(
        _DummyRequest(
            headers={"content-type": "application/json"},
            body={"old_name": "old", "name": "bad name", "url": "https://nifi.example.com/nifi-api"},
        ),
        registry=registry,
        client_manager=manager,
        certs_dir=str(tmp_path),
        conn_name_re=CONN_RE,
        connection_info_cls=ConnectionInfo,
        build_client=MagicMock(return_value=fake_client),
    )
    assert invalid.status_code == 400

    ok = await edit_from_request(
        _DummyRequest(
            headers={"content-type": "application/json"},
            body={
                "old_name": "old",
                "name": "new-name",
                "url": "https://nifi.example.com/nifi-api",
                "verify_ssl": False,
                "readonly": False,
                "knox_token": "new-token",
            },
        ),
        registry=registry,
        client_manager=manager,
        certs_dir=str(tmp_path),
        conn_name_re=CONN_RE,
        connection_info_cls=ConnectionInfo,
        build_client=MagicMock(return_value=fake_client),
    )
    assert ok.status_code == 200
    edited = registry.add.call_args[0][0]
    assert edited.verify_ssl is False
    assert edited.readonly is False
    assert edited.knox_token == "new-token"
    assert registry.active == "other-default"


@pytest.mark.asyncio
async def test_edit_from_request_multipart_and_restore_on_failure(tmp_path: Path, monkeypatch):
    old_conn = ConnectionInfo(
        name="old",
        url="https://nifi.example.com/nifi-api",
        auth_method="certificate_pem",
        cert_path="old/cert.pem",
        cert_key_path="old/key.pem",
        cert_password="oldpw",
    )
    registry = MagicMock(active="default")
    registry.get.return_value = old_conn
    manager = MagicMock()
    manager.connect.side_effect = [RuntimeError("new failed"), None]
    fake_client = _fake_built_client()
    chmod_calls = []

    def fake_chmod(path, mode):
        chmod_calls.append((Path(path).name, mode))

    monkeypatch.setattr("gateway.web_ui_services.os.chmod", fake_chmod)

    request = _DummyRequest(
        headers={"content-type": "multipart/form-data"},
        body={
            "old_name": "old",
            "name": "new",
            "url": "https://nifi.example.com/nifi-api",
            "cert_file": _DummyUpload("cert.pem", b"CERT"),
            "key_file": _DummyUpload("key.pem", b"KEY"),
            "cert_password": "newpw",
        },
    )
    response = await edit_from_request(
        request,
        registry=registry,
        client_manager=manager,
        certs_dir=str(tmp_path),
        conn_name_re=CONN_RE,
        connection_info_cls=ConnectionInfo,
        build_client=MagicMock(return_value=fake_client),
    )

    assert response.status_code == 502
    restored = registry.add.call_args_list[-1][0][0]
    assert restored.name == "old"
    assert (tmp_path / "new" / "cert.pem").read_bytes() == b"CERT"
    assert (tmp_path / "new" / "key.pem").read_bytes() == b"KEY"
    assert chmod_calls == [("cert.pem", 0o600), ("key.pem", 0o600)]


@pytest.mark.asyncio
async def test_edit_from_request_multipart_covers_string_flags_and_restore_failure(tmp_path: Path):
    old_conn = ConnectionInfo(
        name="old",
        url="https://nifi.example.com/nifi-api",
        auth_method="none",
        verify_ssl=True,
        readonly=True,
    )
    registry = MagicMock(active="old")
    registry.get.return_value = old_conn
    manager = MagicMock()
    manager.connect.side_effect = [RuntimeError("new failed"), RuntimeError("restore failed")]
    fake_client = _fake_built_client()

    cert_too_large = await edit_from_request(
        _DummyRequest(
            headers={"content-type": "multipart/form-data"},
            body={
                "old_name": "old",
                "name": "new",
                "url": "https://nifi.example.com/nifi-api",
                "cert_file": _DummyUpload("cert.pem", b"x" * (1024 * 1024 + 1)),
            },
        ),
        registry=registry,
        client_manager=manager,
        certs_dir=str(tmp_path),
        conn_name_re=CONN_RE,
        connection_info_cls=ConnectionInfo,
        build_client=MagicMock(return_value=fake_client),
    )
    assert cert_too_large.status_code == 400

    key_too_large = await edit_from_request(
        _DummyRequest(
            headers={"content-type": "multipart/form-data"},
            body={
                "old_name": "old",
                "name": "new",
                "url": "https://nifi.example.com/nifi-api",
                "key_file": _DummyUpload("key.pem", b"x" * (1024 * 1024 + 1)),
            },
        ),
        registry=registry,
        client_manager=manager,
        certs_dir=str(tmp_path),
        conn_name_re=CONN_RE,
        connection_info_cls=ConnectionInfo,
    )
    assert key_too_large.status_code == 400

    response = await edit_from_request(
        _DummyRequest(
            headers={"content-type": "multipart/form-data"},
            body={
                "old_name": "old",
                "name": "new",
                "url": "https://nifi.example.com/nifi-api",
                "verify_ssl": "false",
                "readonly": "false",
                "cert_file": _DummyUpload("cert.pem", b"CERT"),
                "key_file": _DummyUpload("key.pem", b"KEY"),
            },
        ),
        registry=registry,
        client_manager=manager,
        certs_dir=str(tmp_path),
        conn_name_re=CONN_RE,
        connection_info_cls=ConnectionInfo,
        build_client=MagicMock(return_value=fake_client),
    )
    assert response.status_code == 502


@pytest.mark.asyncio
async def test_edit_from_request_multipart_without_key_file_and_without_restore_data(tmp_path: Path):
    registry = MagicMock(active="")
    registry.get.return_value = None
    manager = MagicMock()
    manager.connect.side_effect = RuntimeError("new failed")
    fake_client = _fake_built_client()

    response = await edit_from_request(
        _DummyRequest(
            headers={"content-type": "multipart/form-data"},
            body={
                "old_name": "old",
                "name": "new",
                "url": "https://nifi.example.com/nifi-api",
                "cert_file": _DummyUpload("cert.pem", b"CERT"),
            },
        ),
        registry=registry,
        client_manager=manager,
        certs_dir=str(tmp_path),
        conn_name_re=CONN_RE,
        connection_info_cls=ConnectionInfo,
        build_client=MagicMock(return_value=fake_client),
    )
    assert response.status_code == 502


@pytest.mark.asyncio
async def test_edit_from_request_without_default_switch_keeps_active_empty(tmp_path: Path):
    old_conn = ConnectionInfo(name="old", url="https://nifi.example.com/nifi-api")
    registry = MagicMock(active="")
    registry.get.return_value = old_conn
    manager = MagicMock()
    fake_client = _fake_built_client()

    response = await edit_from_request(
        _DummyRequest(
            headers={"content-type": "application/json"},
            body={
                "old_name": "old",
                "name": "new",
                "url": "https://nifi.example.com/nifi-api",
            },
        ),
        registry=registry,
        client_manager=manager,
        certs_dir=str(tmp_path),
        conn_name_re=CONN_RE,
        connection_info_cls=ConnectionInfo,
        build_client=MagicMock(return_value=fake_client),
    )
    assert response.status_code == 200
    assert registry.active == ""


@pytest.mark.asyncio
async def test_edit_from_request_rejects_too_large_body_and_build_client_failure(tmp_path: Path):
    registry = MagicMock(active="")
    registry.get.return_value = ConnectionInfo(name="old", url="https://nifi.example.com/nifi-api")
    manager = MagicMock()

    too_large = await edit_from_request(
        _DummyRequest(
            headers={"content-type": "application/json", "content-length": str(256 * 1024 + 1)},
            body={"old_name": "old", "name": "new", "url": "https://nifi.example.com/nifi-api"},
        ),
        registry=registry,
        client_manager=manager,
        certs_dir=str(tmp_path),
        conn_name_re=CONN_RE,
        connection_info_cls=ConnectionInfo,
        build_client=MagicMock(),
    )
    assert too_large.status_code == 413

    failed = await edit_from_request(
        _DummyRequest(
            headers={"content-type": "application/json"},
            body={"old_name": "old", "name": "new", "url": "https://nifi.example.com/nifi-api"},
        ),
        registry=registry,
        client_manager=manager,
        certs_dir=str(tmp_path),
        conn_name_re=CONN_RE,
        connection_info_cls=ConnectionInfo,
        build_client=MagicMock(side_effect=RuntimeError("build failed")),
    )
    assert failed.status_code == 502
    assert _body(failed)["error"] == "connection failed"


@pytest.mark.asyncio
async def test_edit_from_request_handles_imported_build_client_failure(tmp_path: Path, monkeypatch):
    registry = MagicMock(active="")
    registry.get.return_value = ConnectionInfo(name="old", url="https://nifi.example.com/nifi-api")
    manager = MagicMock()

    def fail_build(_conn):
        raise RuntimeError("build failed")

    monkeypatch.setattr("gateway.nifi_client_manager._build_client", fail_build)
    failed = await edit_from_request(
        _DummyRequest(
            headers={"content-type": "application/json"},
            body={"old_name": "old", "name": "new", "url": "https://nifi.example.com/nifi-api"},
        ),
        registry=registry,
        client_manager=manager,
        certs_dir=str(tmp_path),
        conn_name_re=CONN_RE,
        connection_info_cls=ConnectionInfo,
    )
    assert failed.status_code == 502
    assert _body(failed)["error"] == "connection failed"


@pytest.mark.asyncio
async def test_edit_from_request_handles_none_trial_client_without_close(tmp_path: Path):
    registry = MagicMock(active="")
    registry.get.return_value = ConnectionInfo(name="old", url="https://nifi.example.com/nifi-api")
    manager = MagicMock()

    failed = await edit_from_request(
        _DummyRequest(
            headers={"content-type": "application/json"},
            body={"old_name": "old", "name": "new", "url": "https://nifi.example.com/nifi-api"},
        ),
        registry=registry,
        client_manager=manager,
        certs_dir=str(tmp_path),
        conn_name_re=CONN_RE,
        connection_info_cls=ConnectionInfo,
        build_client=MagicMock(return_value=None),
    )
    assert failed.status_code == 502
    assert _body(failed)["error"] == "connection failed"


@pytest.mark.asyncio
async def test_edit_from_request_ignores_trial_client_close_failure(tmp_path: Path):
    old_conn = ConnectionInfo(name="old", url="https://nifi.example.com/nifi-api")
    registry = MagicMock(active="old")
    registry.get.return_value = old_conn
    manager = MagicMock()
    fake_client = _fake_built_client()
    fake_client.session.close.side_effect = RuntimeError("close failed")

    response = await edit_from_request(
        _DummyRequest(
            headers={"content-type": "application/json"},
            body={"old_name": "old", "name": "new", "url": "https://nifi.example.com/nifi-api"},
        ),
        registry=registry,
        client_manager=manager,
        certs_dir=str(tmp_path),
        conn_name_re=CONN_RE,
        connection_info_cls=ConnectionInfo,
        build_client=MagicMock(return_value=fake_client),
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_test_from_request_covers_success_failure_and_validation():
    bad = await run_test_from_request(
        _DummyRequest(headers={"content-type": "application/json"}, body={}),
        build_client=MagicMock(),
        connection_info_cls=ConnectionInfo,
        certs_dir="unused",
    )
    assert bad.status_code == 400

    fake_client = MagicMock()
    fake_client.get_version_info.return_value = {"about": {"version": "2.1.0"}}
    fake_client.session.close = MagicMock()
    ok = await run_test_from_request(
        _DummyRequest(headers={"content-type": "application/json"}, body={"url": "https://nifi"}),
        build_client=MagicMock(return_value=fake_client),
        connection_info_cls=ConnectionInfo,
        certs_dir="unused",
    )
    assert _body(ok) == {"ok": True, "nifi_version": "2.1.0"}
    fake_client.session.close.assert_called_once()

    failed = await run_test_from_request(
        _DummyRequest(headers={"content-type": "application/json"}, body={"url": "https://nifi"}),
        build_client=MagicMock(side_effect=RuntimeError("boom")),
        connection_info_cls=ConnectionInfo,
        certs_dir="unused",
    )
    assert failed.status_code == 502
    assert _body(failed)["ok"] is False
    assert _body(failed)["error"] == "connection test failed"

    too_large = await run_test_from_request(
        _DummyRequest(
            headers={"content-type": "application/json", "content-length": str(256 * 1024 + 1)},
            body={"url": "https://nifi"},
        ),
        build_client=MagicMock(),
        connection_info_cls=ConnectionInfo,
        certs_dir="unused",
    )
    assert too_large.status_code == 413


@pytest.mark.asyncio
async def test_test_from_request_multipart_supports_certificate_p12(tmp_path: Path, monkeypatch):
    chmod_calls = []

    def fake_chmod(path, mode):
        chmod_calls.append((Path(path).name, mode))

    fake_client = MagicMock()
    fake_client.get_version_info.return_value = {"about": {"version": "2.8.0"}}
    fake_client.session.close = MagicMock()

    monkeypatch.setattr("gateway.web_ui_services.os.chmod", fake_chmod)
    response = await run_test_from_request(
        _DummyRequest(
            headers={"content-type": "multipart/form-data"},
            body={
                "url": "https://nifi",
                "auth_method": "certificate_p12",
                "verify_ssl": "false",
                "cert_password": "secret",
                "cert_file": _DummyUpload("client.p12", b"P12DATA"),
            },
        ),
        build_client=MagicMock(return_value=fake_client),
        connection_info_cls=ConnectionInfo,
        certs_dir=str(tmp_path),
    )

    assert _body(response) == {"ok": True, "nifi_version": "2.8.0"}
    fake_client.session.close.assert_called_once()
    assert chmod_calls == [("client.p12", 0o600)]


@pytest.mark.asyncio
async def test_test_from_request_multipart_supports_certificate_pem_and_size_limits(tmp_path: Path, monkeypatch):
    chmod_calls = []

    def fake_chmod(path, mode):
        chmod_calls.append((Path(path).name, mode))

    fake_client = MagicMock()
    fake_client.get_version_info.return_value = {"about": {"version": "2.8.1"}}
    fake_client.session.close = MagicMock()

    monkeypatch.setattr("gateway.web_ui_services.os.chmod", fake_chmod)
    ok = await run_test_from_request(
        _DummyRequest(
            headers={"content-type": "multipart/form-data"},
            body={
                "url": "https://nifi",
                "auth_method": "certificate_pem",
                "cert_file": _DummyUpload("client.pem", b"CERTDATA"),
                "key_file": _DummyUpload("client.key", b"KEYDATA"),
            },
        ),
        build_client=MagicMock(return_value=fake_client),
        connection_info_cls=ConnectionInfo,
        certs_dir=str(tmp_path),
    )

    assert _body(ok) == {"ok": True, "nifi_version": "2.8.1"}
    assert chmod_calls == [("client.pem", 0o600), ("client.key", 0o600)]

    too_large_cert = await run_test_from_request(
        _DummyRequest(
            headers={"content-type": "multipart/form-data"},
            body={
                "url": "https://nifi",
                "auth_method": "certificate_pem",
                "cert_file": _DummyUpload("client.pem", b"x" * (1024 * 1024 + 1)),
            },
        ),
        build_client=MagicMock(),
        connection_info_cls=ConnectionInfo,
        certs_dir=str(tmp_path),
    )
    assert too_large_cert.status_code == 400
    assert _body(too_large_cert)["error"] == "Certificate file too large (max 1 MB)"

    too_large_key = await run_test_from_request(
        _DummyRequest(
            headers={"content-type": "multipart/form-data"},
            body={
                "url": "https://nifi",
                "auth_method": "certificate_pem",
                "key_file": _DummyUpload("client.key", b"x" * (1024 * 1024 + 1)),
            },
        ),
        build_client=MagicMock(),
        connection_info_cls=ConnectionInfo,
        certs_dir=str(tmp_path),
    )
    assert too_large_key.status_code == 400
    assert _body(too_large_key)["error"] == "Key file too large (max 1 MB)"
