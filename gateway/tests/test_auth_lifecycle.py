"""Real temporary certificate files and sanitized error-boundary regressions."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID

from gateway.nifi.auth import KnoxAuthFactory
from gateway.nifi.client import NiFiError
from gateway.tools import admin, read_tools, write_tools


@pytest.fixture
def factory(tmp_path):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "synthetic.example.test")])
    now = datetime.now(timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
            .public_key(key.public_key()).serial_number(1)
            .not_valid_before(now).not_valid_after(now + timedelta(days=1))
            .sign(key, hashes.SHA256()))
    path = tmp_path / "synthetic.p12"
    path.write_bytes(pkcs12.serialize_key_and_certificates(
        b"test", key, cert, None, serialization.BestAvailableEncryption(b"synthetic")))
    return KnoxAuthFactory("", None, None, None, None, None, None, True,
                           p12_path=str(path), p12_password="synthetic")


def test_session_close_removes_real_extracted_key_and_certificate(factory):
    session = factory.build_session()
    paths = tuple(session.cert)
    assert all(Path(path).is_file() for path in paths)
    session.close()
    session.close()
    assert not any(Path(path).exists() for path in paths)
    assert not factory._cleanup_registered
    assert not factory._tmp_files


def test_failed_auth_setup_closes_the_http_session(factory):
    factory.p12_password = "synthetic-wrong"
    with patch.object(requests.Session, "close") as close:
        with pytest.raises(ValueError):
            factory.build_session()
    close.assert_called_once()
    assert not factory._tmp_files


def test_partial_certificate_extraction_is_removed(factory):
    paths = []
    def failing_chmod(path, mode):
        paths.append(path)
        raise OSError("synthetic permission failure")
    with patch("gateway.nifi.auth.os.chmod", side_effect=failing_chmod):
        with pytest.raises(OSError):
            factory.build_session()
    assert paths and not any(Path(path).exists() for path in paths)
    assert not factory._tmp_files


def test_certificate_cleanup_runs_even_when_http_close_fails(factory):
    session = factory.build_session()
    paths = tuple(session.cert)
    with patch.object(requests.Session, "close", side_effect=RuntimeError("synthetic")):
        with pytest.raises(RuntimeError):
            session.close()
    assert not any(Path(path).exists() for path in paths)


@pytest.mark.asyncio
@pytest.mark.parametrize("boundary", ["probe", "read", "write"])
async def test_backend_payloads_are_not_exposed_in_results_or_logs(boundary, caplog):
    marker = "synthetic-private-backend-body"
    error = NiFiError("synthetic", 500, marker)
    if boundary == "probe":
        with patch.object(admin, "_build_client", side_effect=error):
            result = await admin.handle("test_nifi_connection", {"url": "https://synthetic.example"}, None)
    elif boundary == "read":
        with patch.object(read_tools, "dispatch_read_tool", side_effect=error):
            result = await read_tools.handle("get_nifi_version", {}, MagicMock())
    else:
        with patch.object(write_tools, "dispatch_write_tool", side_effect=error):
            result = await write_tools.handle("update_processor_config", {}, MagicMock(), False)
    assert marker not in str(result)
    assert marker not in caplog.text
    assert all(record.exc_info is None for record in caplog.records)
