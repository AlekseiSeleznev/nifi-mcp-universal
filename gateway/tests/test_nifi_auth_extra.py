from __future__ import annotations

import base64
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pytest

from gateway.nifi.auth import KnoxAuthFactory


def _factory(**kwargs) -> KnoxAuthFactory:
    defaults = dict(
        gateway_url="https://gateway.example.com",
        token=None,
        cookie=None,
        user=None,
        password=None,
        token_endpoint=None,
        passcode_token=None,
        verify=True,
    )
    defaults.update(kwargs)
    return KnoxAuthFactory(**defaults)


class _TempFile:
    def __init__(self, name: str):
        self.name = name
        self.data = b""

    def write(self, data: bytes):
        self.data += data

    def flush(self):
        return None

    def close(self):
        return None


def test_extract_p12_success(monkeypatch, tmp_path: Path):
    p12 = tmp_path / "client.p12"
    p12.write_bytes(b"P12")

    certificate = MagicMock()
    certificate.public_bytes.return_value = b"CERT"
    private_key = MagicMock()
    private_key.private_bytes.return_value = b"KEY"
    temp_files = [_TempFile(str(tmp_path / "cert.crt")), _TempFile(str(tmp_path / "key.key"))]

    factory = _factory(p12_path=str(p12), p12_password="secret")
    with patch("builtins.open", mock_open(read_data=b"P12")), \
         patch("gateway.nifi.auth.tempfile.NamedTemporaryFile", side_effect=temp_files), \
         patch("gateway.nifi.auth.atexit.register") as register, \
         patch("gateway.nifi.auth.os.chmod") as chmod, \
         patch("cryptography.hazmat.primitives.serialization.pkcs12.load_key_and_certificates", return_value=(private_key, certificate, None)):
        cert_path, key_path = factory._extract_p12()

    assert cert_path.endswith("cert.crt")
    assert key_path.endswith("key.key")
    assert factory._tmp_files == [cert_path, key_path]
    register.assert_called_once()
    assert chmod.call_count == 2


def test_extract_p12_registers_cleanup_only_once(tmp_path: Path):
    p12 = tmp_path / "client.p12"
    p12.write_bytes(b"P12")

    certificate = MagicMock()
    certificate.public_bytes.return_value = b"CERT"
    private_key = MagicMock()
    private_key.private_bytes.return_value = b"KEY"
    temp_files = [
        _TempFile(str(tmp_path / "cert1.crt")),
        _TempFile(str(tmp_path / "key1.key")),
        _TempFile(str(tmp_path / "cert2.crt")),
        _TempFile(str(tmp_path / "key2.key")),
    ]

    factory = _factory(p12_path=str(p12), p12_password="secret")
    with patch("builtins.open", mock_open(read_data=b"P12")), \
         patch("gateway.nifi.auth.tempfile.NamedTemporaryFile", side_effect=temp_files), \
         patch("gateway.nifi.auth.atexit.register") as register, \
         patch("gateway.nifi.auth.os.chmod"), \
         patch("cryptography.hazmat.primitives.serialization.pkcs12.load_key_and_certificates", return_value=(private_key, certificate, None)):
        factory._extract_p12()
        factory._extract_p12()

    register.assert_called_once()


def test_extract_p12_import_error(monkeypatch, tmp_path: Path):
    factory = _factory(p12_path=str(tmp_path / "missing.p12"))

    real_import = __import__

    def fake_import(name, *args, **kwargs):
        if name == "cryptography.hazmat.primitives.serialization":
            raise ImportError("missing")
        return real_import(name, *args, **kwargs)

    with patch("builtins.__import__", side_effect=fake_import):
        with pytest.raises(RuntimeError, match="cryptography package is required"):
            factory._extract_p12()


def test_cleanup_tmp_files_ignores_os_errors():
    factory = _factory()
    factory._tmp_files = ["/tmp/a", "/tmp/b"]
    with patch("gateway.nifi.auth.os.unlink", side_effect=[OSError("x"), None]) as unlink:
        factory._cleanup_tmp_files()
    assert unlink.call_count == 2


def test_build_session_sets_client_cert(monkeypatch):
    factory = _factory()
    monkeypatch.setattr(factory, "_resolve_client_cert", lambda: ("/tmp/cert", "/tmp/key"))
    session = factory.build_session()
    assert session.cert == ("/tmp/cert", "/tmp/key")


def test_resolve_client_cert_uses_p12_extraction(monkeypatch):
    factory = _factory(p12_path="/tmp/client.p12")
    monkeypatch.setattr(factory, "_extract_p12", lambda: ("/tmp/cert", "/tmp/key"))
    assert factory._resolve_client_cert() == ("/tmp/cert", "/tmp/key")


def test_fetch_knox_token_decodes_base64_jwt():
    token = "a.b.c"
    encoded = base64.b64encode(token.encode()).decode()
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json.side_effect = ValueError("not json")
    response.text = encoded

    factory = _factory(user="u", password="p", gateway_url="https://gateway.example.com")
    with patch("requests.get", return_value=response):
        assert factory._fetch_knox_token() == token


def test_fetch_knox_token_returns_original_text_when_base64_is_not_jwt():
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json.side_effect = ValueError("not json")
    response.text = base64.b64encode(b"not-a-jwt").decode()

    factory = _factory(user="u", password="p", gateway_url="https://gateway.example.com")
    with patch("requests.get", return_value=response):
        assert factory._fetch_knox_token() == response.text


def test_exchange_passcode_requires_token_endpoint():
    factory = _factory(gateway_url="", passcode_token="pc", token_endpoint=None)
    with pytest.raises(RuntimeError, match="requires token_endpoint"):
        factory._exchange_passcode_for_jwt()


def test_exchange_passcode_text_fallback():
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json.side_effect = ValueError("not json")
    response.text = "jwt-token"
    factory = _factory(passcode_token="pc", gateway_url="https://gateway.example.com")

    with patch("requests.get", return_value=response):
        assert factory._exchange_passcode_for_jwt() == "jwt-token"
