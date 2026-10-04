"""Dashboard probes own temporary uploads without retaining or overwriting keys."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from gateway.nifi_registry import ConnectionInfo
from gateway.web_ui_services import test_from_request as probe


@pytest.mark.asyncio
@pytest.mark.parametrize("outcome", ["success", "build_failure", "request_failure", "missing_url", "oversize_key"])
async def test_probe_preserves_existing_files_and_removes_its_uploads(tmp_path, outcome):
    directory = tmp_path / "__test__"
    directory.mkdir()
    certificate = directory / "client.pem"
    key = directory / "client.key"
    certificate.write_bytes(b"existing-certificate")
    key.write_bytes(b"existing-key")

    def upload(filename, data):
        return MagicMock(filename=filename, read=AsyncMock(return_value=data))

    request = MagicMock()
    request.headers = {"content-type": "multipart/form-data"}
    request.form = AsyncMock(return_value={
        "url": "" if outcome == "missing_url" else "https://synthetic.example.test",
        "auth_method": "certificate_pem",
        "cert_file": upload("client.pem", b"probe-certificate"),
        "key_file": upload("client.key", b"x" * (1024 * 1024 + 1) if outcome == "oversize_key" else b"probe-key"),
    })
    client = MagicMock()
    client.get_version_info.return_value = {"about": {"version": "2.8.0"}}
    if outcome == "request_failure":
        client.get_version_info.side_effect = RuntimeError("synthetic request failure")

    def build(conn):
        assert (tmp_path / conn.cert_path).read_bytes() == b"probe-certificate"
        assert (tmp_path / conn.cert_key_path).read_bytes() == b"probe-key"
        if outcome == "build_failure":
            raise ValueError("synthetic certificate failure")
        return client

    response = await probe(request, build_client=build, connection_info_cls=ConnectionInfo, certs_dir=str(tmp_path))
    assert response.status_code == {"success": 200, "build_failure": 502, "request_failure": 502,
                                    "missing_url": 400, "oversize_key": 400}[outcome]
    assert certificate.read_bytes() == b"existing-certificate"
    assert key.read_bytes() == b"existing-key"
    assert sorted(path.name for path in directory.iterdir()) == ["client.key", "client.pem"]
    if outcome in {"success", "request_failure"}:
        client.session.close.assert_called_once()


@pytest.mark.asyncio
async def test_cancelled_upload_removes_already_staged_certificate(tmp_path):
    request = MagicMock()
    request.headers = {"content-type": "multipart/form-data"}
    request.form = AsyncMock(return_value={
        "url": "https://synthetic.example.test", "auth_method": "certificate_pem",
        "cert_file": MagicMock(filename="client.pem", read=AsyncMock(return_value=b"synthetic-certificate")),
        "key_file": MagicMock(filename="client.key", read=AsyncMock(side_effect=asyncio.CancelledError)),
    })
    build = MagicMock()
    with pytest.raises(asyncio.CancelledError):
        await probe(request, build_client=build, connection_info_cls=ConnectionInfo, certs_dir=str(tmp_path))
    build.assert_not_called()
    assert not [path for path in tmp_path.rglob("*") if path.is_file()]
