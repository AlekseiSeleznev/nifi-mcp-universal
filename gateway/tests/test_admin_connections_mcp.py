"""Connection registration through MCP with real certificate and state handling."""

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID
import pytest
import requests

from gateway import mcp_server, nifi_client_manager, nifi_registry
from gateway.config import settings
from gateway.tools import admin


def _payload(result):
    return json.loads(result[0].text)


@pytest.fixture
def connection_runtime(tmp_path, monkeypatch):
    registry = nifi_registry.ConnectionRegistry()
    manager = nifi_client_manager.NiFiClientManager()
    monkeypatch.setattr(nifi_registry, "STATE_FILE", str(tmp_path / "state.json"))
    monkeypatch.setattr(nifi_client_manager, "CERTS_DIR", str(tmp_path / "certs"))
    monkeypatch.setattr(settings, "persist_secrets_in_state", True)
    monkeypatch.setattr(admin, "registry", registry)
    monkeypatch.setattr(nifi_client_manager, "registry", registry)
    monkeypatch.setattr(admin, "client_manager", manager)
    monkeypatch.setattr(mcp_server, "client_manager", manager)
    token = mcp_server._current_session_id.set("certificate-session")
    yield
    manager.close_all()
    mcp_server._current_session_id.reset(token)


@pytest.fixture
def certificate_backend(tmp_path, monkeypatch):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "synthetic.example.test")])
    now = datetime.now(timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(subject).issuer_name(subject)
            .public_key(key.public_key()).serial_number(1)
            .not_valid_before(now).not_valid_after(now + timedelta(days=1))
            .sign(key, hashes.SHA256()))
    cert_pem = cert.public_bytes(serialization.Encoding.PEM)
    key_pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                serialization.NoEncryption())
    cert_dir = tmp_path / "certs" / "synthetic"
    cert_dir.mkdir(parents=True)
    (cert_dir / "client.p12").write_bytes(pkcs12.serialize_key_and_certificates(
        b"synthetic", key, cert, None,
        serialization.BestAvailableEncryption(b"synthetic-certificate-password")))
    (cert_dir / "client.crt").write_bytes(cert_pem)
    (cert_dir / "client.key").write_bytes(key_pem)

    def request(session, method, url, **kwargs):
        assert method == "GET"
        assert url == "https://synthetic.example.test/nifi-api/flow/about"
        assert session.cert, "The backend requires the supplied client certificate"
        assert Path(session.cert[0]).read_bytes() == cert_pem
        assert Path(session.cert[1]).read_bytes() == key_pem
        response = requests.Response()
        response.status_code = 200
        response._content = b'{"about": {"version": "2.11.0"}}'
        return response

    monkeypatch.setattr(requests.Session, "request", request)


@pytest.mark.asyncio
async def test_mcp_p12_registration_retains_credentials_for_saved_probe_after_reload(
    connection_runtime, certificate_backend, monkeypatch,
):
    result = _payload(await mcp_server.call_tool("connect_nifi", {
        "name": "certificate", "url": "https://synthetic.example.test",
        "auth_method": "certificate_p12", "cert_path": "synthetic/client.p12",
        "cert_password": "synthetic-certificate-password",
    }))
    assert result == {"ok": True, "name": "certificate", "nifi_version": "2.11.0"}

    restored = nifi_registry.ConnectionRegistry()
    restored.load()
    monkeypatch.setattr(admin, "registry", restored)
    monkeypatch.setattr(nifi_client_manager, "registry", restored)
    probe = _payload(await mcp_server.call_tool("test_nifi_connection", {"name": "certificate"}))
    assert probe == {"ok": True, "nifi_version": "2.11.0"}
    listed = _payload(await mcp_server.call_tool("list_nifi_connections", {}))
    assert listed[0]["cert_path"] == "synthetic/client.p12"
    assert listed[0]["cert_password"] == "***"
    schema = next(t.inputSchema for t in await mcp_server.list_tools() if t.name == "connect_nifi")
    assert {"cert_path", "cert_password"} <= schema["properties"].keys()


@pytest.mark.asyncio
async def test_mcp_pem_registration_uses_certificate_and_key(connection_runtime, certificate_backend):
    result = _payload(await mcp_server.call_tool("connect_nifi", {
        "name": "certificate", "url": "https://synthetic.example.test",
        "auth_method": "certificate_pem", "cert_path": "synthetic/client.crt",
        "cert_key_path": "synthetic/client.key",
    }))
    assert result == {"ok": True, "name": "certificate", "nifi_version": "2.11.0"}
    listed = _payload(await mcp_server.call_tool("list_nifi_connections", {}))
    assert listed[0]["cert_key_path"] == "synthetic/client.key"
    schema = next(t.inputSchema for t in await mcp_server.list_tools() if t.name == "connect_nifi")
    assert "cert_key_path" in schema["properties"]


@pytest.mark.asyncio
@pytest.mark.parametrize("credentials", [
    {"auth_method": "certificate_p12", "cert_path": "synthetic/client.p12",
     "cert_password": "synthetic-certificate-password"},
    {"auth_method": "certificate_pem", "cert_path": "synthetic/client.crt",
     "cert_key_path": "synthetic/client.key"},
], ids=["p12", "pem"])
async def test_mcp_certificate_probe_by_url_uses_credentials_without_registering(
    connection_runtime, certificate_backend, credentials,
):
    result = _payload(await mcp_server.call_tool("test_nifi_connection", {
        "url": "https://synthetic.example.test", **credentials,
    }))
    assert result == {"ok": True, "nifi_version": "2.11.0"}
    assert _payload(await mcp_server.call_tool("list_nifi_connections", {})) == []
    schema = next(t.inputSchema for t in await mcp_server.list_tools() if t.name == "test_nifi_connection")
    assert {"cert_path", "cert_password", "cert_key_path"} <= schema["properties"].keys()


@pytest.mark.asyncio
async def test_mcp_duplicate_registration_preserves_original_connection_and_session(
    connection_runtime, certificate_backend,
):
    await mcp_server.call_tool("connect_nifi", {
        "name": "certificate", "url": "https://synthetic.example.test",
        "auth_method": "certificate_p12", "cert_path": "synthetic/client.p12",
        "cert_password": "synthetic-certificate-password",
    })
    await mcp_server.call_tool("switch_nifi", {"name": "certificate"})
    original = _payload(await mcp_server.call_tool("list_nifi_connections", {}))
    status = _payload(await mcp_server.call_tool("get_server_status", {}))

    result = _payload(await mcp_server.call_tool("connect_nifi", {
        "name": " certificate ", "url": "https://replacement.example.test", "auth_method": "none",
    }))
    assert "already registered" in result.get("error", "")
    assert "switch_nifi" in result["error"]
    assert _payload(await mcp_server.call_tool("list_nifi_connections", {})) == original
    assert _payload(await mcp_server.call_tool("get_server_status", {})) == status
    assert _payload(await mcp_server.call_tool("get_nifi_version", {})) == {
        "version_info": {"about": {"version": "2.11.0"}},
        "parsed_version": "2.11.0", "is_nifi_2x": True,
    }
    assert _payload(await mcp_server.call_tool("test_nifi_connection", {"name": "certificate"})) == {
        "ok": True, "nifi_version": "2.11.0",
    }
