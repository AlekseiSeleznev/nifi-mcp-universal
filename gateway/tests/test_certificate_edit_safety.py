"""Certificate replacements preserve saved credentials until validation succeeds."""

import re
from unittest.mock import AsyncMock, MagicMock

import pytest

from gateway.nifi_registry import ConnectionInfo, ConnectionRegistry
from gateway.web_ui_services import connect_from_request, edit_from_request


CONN_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,62}$")


def _upload(filename, data):
    upload = MagicMock(filename=filename)
    upload.read = AsyncMock(return_value=data)
    return upload


def _request(**fields):
    request = MagicMock()
    request.headers = {"content-type": "multipart/form-data"}
    request.form = AsyncMock(return_value={
        "old_name": "saved", "name": "saved", "url": "https://synthetic.example.test",
        **fields,
    })
    return request


@pytest.fixture
def saved_connection(tmp_path, monkeypatch):
    monkeypatch.setattr("gateway.nifi_registry.STATE_FILE", str(tmp_path / "state.json"))
    monkeypatch.setattr("gateway.nifi_registry.settings.persist_secrets_in_state", True)
    certs = tmp_path / "certs"
    (certs / "saved").mkdir(parents=True)
    (certs / "saved/client.p12").write_bytes(b"original-certificate")
    (certs / "saved/client.key").write_bytes(b"original-key")
    registry = ConnectionRegistry()
    registry.add(ConnectionInfo(
        name="saved", url="https://synthetic.example.test", auth_method="certificate_p12",
        cert_path="saved/client.p12", cert_key_path="saved/client.key", cert_password="synthetic-original",
    ))
    return registry, certs


def _client():
    client = MagicMock()
    client.get_version_info.return_value = {"about": {"version": "2.8.0"}}
    return client


async def _edit(request, registry, certs, *, build_client=None, manager=None):
    return await edit_from_request(
        request, registry=registry, client_manager=manager or MagicMock(),
        certs_dir=str(certs), conn_name_re=CONN_RE, connection_info_cls=ConnectionInfo,
        build_client=build_client or MagicMock(return_value=_client()),
    )


def _assert_original_survives(registry, certs):
    restored = ConnectionRegistry()
    restored.load()
    for source in (registry, restored):
        conn = source.get("saved")
        assert conn.cert_path == "saved/client.p12"
        assert conn.cert_key_path == "saved/client.key"
        assert conn.cert_password == "synthetic-original"
    assert (certs / "saved/client.p12").read_bytes() == b"original-certificate"
    assert (certs / "saved/client.key").read_bytes() == b"original-key"
    assert sorted(path.name for path in (certs / "saved").iterdir()) == ["client.key", "client.p12"]


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["build", "request"])
async def test_failed_replacement_preserves_original_files_and_saved_paths(saved_connection, failure):
    registry, certs = saved_connection
    client = _client()
    build = MagicMock(return_value=client)
    if failure == "build":
        build.side_effect = ValueError("synthetic invalid password")
    else:
        client.get_version_info.side_effect = RuntimeError("synthetic validation failure")
    response = await _edit(_request(
        cert_file=_upload("client.p12", b"replacement-certificate"),
        key_file=_upload("client.key", b"replacement-key"), cert_password="synthetic-new",
    ), registry, certs, build_client=build)
    assert response.status_code == 502
    _assert_original_survives(registry, certs)


@pytest.mark.asyncio
async def test_successful_replacement_persists_new_paths_without_overwriting_originals(saved_connection):
    registry, certs = saved_connection
    response = await _edit(_request(
        cert_file=_upload("../client.p12", b"replacement-certificate"),
        key_file=_upload("../client.key", b"replacement-key"), cert_password="synthetic-new",
    ), registry, certs)
    assert response.status_code == 200
    restored = ConnectionRegistry()
    restored.load()
    conn = restored.get("saved")
    assert conn.cert_path != "saved/client.p12"
    assert conn.cert_key_path != "saved/client.key"
    assert (certs / conn.cert_path).read_bytes() == b"replacement-certificate"
    assert (certs / conn.cert_key_path).read_bytes() == b"replacement-key"
    assert conn.cert_password == "synthetic-new"
    assert (certs / "saved/client.p12").read_bytes() == b"original-certificate"
    assert (certs / "saved/client.key").read_bytes() == b"original-key"


@pytest.mark.asyncio
async def test_oversize_second_upload_removes_first_candidate(saved_connection):
    registry, certs = saved_connection
    response = await _edit(_request(
        cert_file=_upload("client.p12", b"replacement-certificate"),
        key_file=_upload("client.key", b"x" * (1024 * 1024 + 1)),
    ), registry, certs)
    assert response.status_code == 400
    _assert_original_survives(registry, certs)


@pytest.mark.asyncio
async def test_upload_write_failure_removes_partial_candidate(saved_connection, monkeypatch):
    registry, certs = saved_connection
    monkeypatch.setattr("gateway.web_ui_services.os.chmod", MagicMock(side_effect=OSError("synthetic chmod failure")))
    response = await _edit(_request(cert_file=_upload("client.p12", b"replacement-certificate")), registry, certs)
    assert response.status_code == 502
    _assert_original_survives(registry, certs)


@pytest.mark.asyncio
async def test_failed_connect_after_validation_restores_original_credentials(saved_connection):
    registry, certs = saved_connection
    manager = MagicMock()
    manager.connect.side_effect = [RuntimeError("synthetic connect failure"), None]
    response = await _edit(_request(
        cert_file=_upload("client.p12", b"replacement-certificate"), cert_password="synthetic-new",
    ), registry, certs, manager=manager)
    assert response.status_code == 502
    _assert_original_survives(registry, certs)


@pytest.mark.asyncio
async def test_failed_rollback_does_not_report_a_connected_client(saved_connection):
    registry, certs = saved_connection
    registry.get("saved").connected = True
    registry.get("saved").nifi_version = "2.8.0"
    manager = MagicMock()
    manager.connect.side_effect = RuntimeError("synthetic connect failure")
    response = await _edit(_request(cert_password="synthetic-new"), registry, certs, manager=manager)
    assert response.status_code == 502
    assert not registry.get("saved").connected
    assert registry.get("saved").nifi_version == ""
    _assert_original_survives(registry, certs)


@pytest.mark.asyncio
async def test_duplicate_connect_rejects_upload_before_changing_existing_certificate(saved_connection):
    registry, certs = saved_connection
    upload = _upload("client.p12", b"replacement-certificate")
    response = await connect_from_request(
        _request(cert_file=upload), registry=registry, client_manager=MagicMock(),
        certs_dir=str(certs), conn_name_re=CONN_RE, connection_info_cls=ConnectionInfo,
    )
    assert response.status_code == 409
    upload.read.assert_not_called()
    _assert_original_survives(registry, certs)


@pytest.mark.asyncio
async def test_second_upload_read_failure_removes_first_candidate(saved_connection):
    registry, certs = saved_connection
    key = _upload("client.key", b"")
    key.read.side_effect = OSError("synthetic upload read failure")
    response = await _edit(_request(
        cert_file=_upload("client.p12", b"replacement-certificate"), key_file=key,
    ), registry, certs)
    assert response.status_code == 502
    assert b"synthetic upload read failure" not in response.body
    _assert_original_survives(registry, certs)


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["connect", "oversize", "read"])
async def test_new_connection_failure_removes_its_candidate_files(saved_connection, failure):
    registry, certs = saved_connection
    manager = MagicMock()
    key = _upload("client.key", b"replacement-key")
    if failure == "connect":
        manager.connect.side_effect = RuntimeError("synthetic connect failure")
    elif failure == "oversize":
        key.read.return_value = b"x" * (1024 * 1024 + 1)
    else:
        key.read.side_effect = OSError("synthetic read failure")
    response = await connect_from_request(
        _request(name="new", cert_file=_upload("client.p12", b"replacement-certificate"), key_file=key),
        registry=registry, client_manager=manager, certs_dir=str(certs),
        conn_name_re=CONN_RE, connection_info_cls=ConnectionInfo,
    )
    assert response.status_code == (400 if failure == "oversize" else 502)
    assert registry.get("new") is None
    assert not list((certs / "new").iterdir())
    _assert_original_survives(registry, certs)


@pytest.mark.asyncio
async def test_failed_activation_keeps_in_memory_password_when_persistence_is_disabled(saved_connection, monkeypatch):
    registry, certs = saved_connection
    monkeypatch.setattr("gateway.nifi_registry.settings.persist_secrets_in_state", False)
    manager = MagicMock()
    manager.connect.side_effect = [RuntimeError("synthetic connect failure"), None]
    response = await _edit(_request(
        cert_file=_upload("client.p12", b"replacement-certificate"), cert_password="synthetic-new",
    ), registry, certs, manager=manager)
    assert response.status_code == 502
    restored = registry.get("saved")
    assert restored.cert_password == "synthetic-original"
    assert restored.cert_path == "saved/client.p12"
    assert (certs / restored.cert_path).read_bytes() == b"original-certificate"
    assert sorted(path.name for path in (certs / "saved").iterdir()) == ["client.key", "client.p12"]
