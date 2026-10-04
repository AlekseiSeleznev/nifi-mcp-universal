from __future__ import annotations

from pathlib import Path
import time
from unittest.mock import MagicMock, patch

import pytest
import requests

from gateway.nifi.client import NiFiClient
from gateway.nifi_client_manager import CERTS_DIR, NiFiClientManager, SessionState, _build_client
from gateway.nifi_registry import ConnectionInfo


@pytest.mark.parametrize(
    "auth_method,cert_path,cert_key_path",
    [
        ("certificate_p12", "", ""),
        ("certificate_pem", "", ""),
        ("certificate_pem", "nested/client.pem", ""),
        ("certificate_pem", "", "nested/client.key"),
    ],
)
def test_connect_requires_complete_certificate_configuration(auth_method, cert_path, cert_key_path):
    manager = NiFiClientManager()
    conn = ConnectionInfo(
        name="synthetic", url="https://synthetic.example.test", auth_method=auth_method,
        cert_path=cert_path, cert_key_path=cert_key_path, connected=True, nifi_version="2.0.0",
    )
    response = requests.Response()
    response.status_code = 200
    response._content = b'{"about": {"version": "2.11.0"}}'
    with patch.object(requests.Session, "request", return_value=response) as request:
        with pytest.raises(ValueError, match="required"):
            manager.connect(conn)

    request.assert_not_called()
    assert conn.connected is False
    assert conn.nifi_version == ""
    assert manager.get_status()["connections"] == {}


@pytest.mark.parametrize("field", ["cert_path", "cert_key_path"])
@pytest.mark.parametrize("path_kind", ["absolute", "traversal", "symlink"])
def test_connect_rejects_certificate_paths_outside_relative_certificate_storage(
    tmp_path, monkeypatch, field, path_kind,
):
    certs = tmp_path / "certs"
    certs.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    if path_kind == "symlink":
        try:
            (certs / "linked").symlink_to(outside, target_is_directory=True)
        except (OSError, NotImplementedError):
            pytest.skip("Creating directory symlinks is not supported in this environment")
    monkeypatch.setattr("gateway.nifi_client_manager.CERTS_DIR", str(certs))
    unsafe = {
        "absolute": str(certs / "nested" / "client.pem"),
        "traversal": "../outside/client.pem",
        "symlink": "linked/client.pem",
    }[path_kind]
    paths = {"cert_path": "nested/client.pem", "cert_key_path": "nested/client.key", field: unsafe}
    conn = ConnectionInfo(
        name="synthetic", url="https://synthetic.example.test", auth_method="certificate_pem", **paths,
    )
    manager = NiFiClientManager()
    response = requests.Response()
    response.status_code = 200
    response._content = b'{"about": {"version": "2.11.0"}}'
    with patch.object(requests.Session, "request", return_value=response) as request:
        with pytest.raises(ValueError, match="relative|inside"):
            manager.connect(conn)

    request.assert_not_called()
    assert conn.connected is False
    assert manager.get_status()["connections"] == {}


def test_connect_preserves_nested_relative_certificate_paths(tmp_path, monkeypatch):
    certs = tmp_path / "certs"
    certs.mkdir()
    monkeypatch.setattr("gateway.nifi_client_manager.CERTS_DIR", str(certs))
    conn = ConnectionInfo(
        name="synthetic", url="https://synthetic.example.test", auth_method="certificate_pem",
        cert_path="nested/deeper/client.pem", cert_key_path="nested/deeper/client.key",
    )
    manager = NiFiClientManager()
    sent_certificates = []

    def request(session, *args, **kwargs):
        sent_certificates.append(session.cert)
        response = requests.Response()
        response.status_code = 200
        response._content = b'{"about": {"version": "2.11.0"}}'
        return response

    with patch.object(requests.Session, "request", request):
        try:
            manager.connect(conn)
            assert conn.connected is True
            assert conn.nifi_version == "2.11.0"
            assert sent_certificates == [(
                str(certs / "nested" / "deeper" / "client.pem"),
                str(certs / "nested" / "deeper" / "client.key"),
            )]
            manager.switch("synthetic", "synthetic-session")
        finally:
            manager.close_all()


def test_build_client_maps_auth_configuration(monkeypatch):
    created = {}

    def fake_factory(**kwargs):
        created.update(kwargs)
        return MagicMock(build_session=MagicMock(return_value="session"))

    fake_client = MagicMock(spec=NiFiClient)
    with patch("gateway.nifi_client_manager.KnoxAuthFactory", side_effect=fake_factory), \
         patch("gateway.nifi_client_manager.NiFiClient", return_value=fake_client) as nifi_cls:
        conn = ConnectionInfo(
            name="prod",
            url="https://nifi.example.com",
            auth_method="certificate_pem",
            cert_path="prod/cert.pem",
            cert_key_path="prod/key.pem",
            knox_gateway_url="https://gateway.example.com",
            verify_ssl=False,
        )
        _build_client(conn)

    assert created["client_cert"] == str((Path(CERTS_DIR) / "prod/cert.pem").resolve())
    assert created["client_key"] == str((Path(CERTS_DIR) / "prod/key.pem").resolve())
    assert created["verify"] is False
    nifi_cls.assert_called_once()


def test_build_client_maps_p12_and_basic_auth():
    created = {}

    def fake_factory(**kwargs):
        created.update(kwargs)
        return MagicMock(build_session=MagicMock(return_value="session"))

    with patch("gateway.nifi_client_manager.KnoxAuthFactory", side_effect=fake_factory), \
         patch("gateway.nifi_client_manager.NiFiClient", return_value=MagicMock(spec=NiFiClient)):
        conn = ConnectionInfo(
            name="prod",
            url="https://nifi.example.com",
            auth_method="certificate_p12",
            cert_path="prod/client.p12",
            cert_password="secret",
        )
        _build_client(conn)
    assert created["p12_path"] == str((Path(CERTS_DIR) / "prod/client.p12").resolve())
    assert created["p12_password"] == "secret"

    created.clear()
    with patch("gateway.nifi_client_manager.KnoxAuthFactory", side_effect=fake_factory), \
         patch("gateway.nifi_client_manager.NiFiClient", return_value=MagicMock(spec=NiFiClient)):
        conn = ConnectionInfo(
            name="prod",
            url="https://nifi.example.com",
            auth_method="basic",
            knox_user="admin",
            knox_password="secret",
        )
        _build_client(conn)
    assert created["user"] == "admin"
    assert created["password"] == "secret"


def test_connect_handles_concurrent_existing_client():
    mgr = NiFiClientManager()
    conn = ConnectionInfo(name="a", url="https://nifi.example.com")
    existing = MagicMock(spec=NiFiClient)
    new_client = MagicMock(spec=NiFiClient)
    new_client.get_version_info.return_value = {"about": {"version": "2.0.0"}}
    new_client.session = MagicMock()

    def build_client(_conn):
        mgr._clients["a"] = existing
        return new_client

    with patch("gateway.nifi_client_manager._build_client", side_effect=build_client):
        mgr.connect(conn)

    new_client.session.close.assert_called_once()
    assert mgr._clients["a"] is existing


def test_connect_concurrent_existing_ignores_close_exception():
    mgr = NiFiClientManager()
    conn = ConnectionInfo(name="a", url="https://nifi.example.com")
    existing = MagicMock(spec=NiFiClient)
    new_client = MagicMock(spec=NiFiClient)
    new_client.get_version_info.return_value = {"about": {"version": "2.0.0"}}
    new_client.session = MagicMock()
    new_client.session.close.side_effect = RuntimeError("close failed")

    def build_client(_conn):
        mgr._clients["a"] = existing
        return new_client

    with patch("gateway.nifi_client_manager._build_client", side_effect=build_client):
        mgr.connect(conn)

    assert mgr._clients["a"] is existing


def test_disconnect_ignores_close_errors_and_updates_registry():
    mgr = NiFiClientManager()
    client = MagicMock(spec=NiFiClient)
    client.session = MagicMock()
    client.session.close.side_effect = RuntimeError("close failed")
    mgr._clients["a"] = client
    mgr._sessions["sess"] = SessionState(conn_name="a")
    conn = ConnectionInfo(name="a", url="https://nifi.example.com")

    with patch("gateway.nifi_client_manager.registry") as registry:
        registry.get.return_value = conn
        mgr.disconnect("a")

    assert conn.connected is False
    assert "sess" not in mgr._sessions


def test_switch_get_client_and_get_connection_info_cover_remaining_branches():
    mgr = NiFiClientManager()
    client = MagicMock(spec=NiFiClient)
    mgr._clients["a"] = client

    with patch("gateway.nifi_client_manager.registry") as registry:
        registry.active = ""
        mgr.switch("a")
        assert registry.active == "a"

        mgr._sessions["sess"] = SessionState(conn_name="a", last_access=1)
        before = mgr._sessions["sess"].last_access
        assert mgr.get_client("sess") is client
        assert mgr._sessions["sess"].last_access >= before

        registry.get.return_value = ConnectionInfo(name="a", url="https://nifi.example.com")
        assert mgr.get_connection_info("sess").name == "a"

        registry.active = "missing"
        with pytest.raises(RuntimeError, match="not connected"):
            mgr.get_client()


def test_get_status_handles_missing_registry_connection():
    mgr = NiFiClientManager()
    mgr._clients["ghost"] = MagicMock(spec=NiFiClient)

    with patch("gateway.nifi_client_manager.registry") as registry:
        registry.get.return_value = None
        registry.active = "ghost"
        status = mgr.get_status()

    assert status["connections"]["ghost"]["url"] == "?"


def test_get_connection_info_returns_none_without_active_connection():
    mgr = NiFiClientManager()
    with patch("gateway.nifi_client_manager.registry") as registry:
        registry.active = ""
        assert mgr.get_connection_info() is None


def test_disconnect_unknown_client_is_noop():
    mgr = NiFiClientManager()
    mgr.disconnect("missing")
