"""Security tests — cert upload size limits, connection name validation, credential masking."""
from __future__ import annotations

import io
import tempfile
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from starlette.testclient import TestClient
from starlette.applications import Starlette
from starlette.routing import Route

from gateway.nifi_registry import ConnectionInfo


# ──────────────────────────────────────────────
#  Helpers
# ──────────────────────────────────────────────

def _make_app():
    """Minimal app with dashboard endpoints for security testing."""
    from gateway.web_ui import api_connect, api_edit, api_disconnect, api_test
    return Starlette(routes=[
        Route("/api/connect", api_connect, methods=["POST"]),
        Route("/api/edit", api_edit, methods=["POST"]),
        Route("/api/disconnect", api_disconnect, methods=["POST"]),
        Route("/api/test", api_test, methods=["POST"]),
    ])


# ──────────────────────────────────────────────
#  Connection name validation
# ──────────────────────────────────────────────

class TestConnectionNameValidation:
    """Tests use JSON body (not multipart) since form data goes to JSON branch."""

    def _post_connect(self, body: dict) -> object:
        app = _make_app()
        client = TestClient(app, raise_server_exceptions=False)
        return client.post("/api/connect",
                           json=body,
                           headers={"Content-Type": "application/json"})

    def test_valid_name_accepted(self):
        conn = ConnectionInfo(name="valid-name", url="https://nifi")
        with patch("gateway.web_ui.registry") as mock_reg, \
             patch("gateway.web_ui.client_manager") as mock_mgr:
            mock_reg.get.return_value = conn
            mock_mgr.connect.return_value = None
            resp = self._post_connect({
                "name": "valid-name", "url": "https://nifi",
                "auth_method": "none"
            })
        assert resp.status_code == 200

    def test_path_traversal_name_rejected(self):
        resp = self._post_connect({"name": "../evil", "url": "https://nifi"})
        assert resp.status_code in (400, 422)

    def test_empty_name_rejected(self):
        resp = self._post_connect({"name": "", "url": "https://nifi"})
        assert resp.status_code in (400, 422)

    def test_slash_in_name_rejected(self):
        resp = self._post_connect({"name": "foo/bar", "url": "https://nifi"})
        assert resp.status_code in (400, 422)

    def test_missing_url_rejected(self):
        resp = self._post_connect({"name": "my-conn", "url": ""})
        assert resp.status_code in (400, 422)


# ──────────────────────────────────────────────
#  Cert upload size limits
# ──────────────────────────────────────────────

class TestCertUploadSizeLimits:
    def _big_cert(self, size_bytes: int) -> bytes:
        return b"X" * size_bytes

    def test_cert_too_large_rejected(self):
        app = _make_app()
        client = TestClient(app, raise_server_exceptions=True)
        big_cert = self._big_cert(2 * 1024 * 1024)  # 2 MB — over limit
        with patch("gateway.web_ui.CERTS_DIR", "/tmp/test-certs"):
            resp = client.post("/api/connect", files={
                "cert_file": ("big.p12", io.BytesIO(big_cert), "application/octet-stream"),
            }, data={
                "name": "test-conn", "url": "https://nifi",
                "auth_method": "certificate_p12"
            })
        assert resp.status_code == 400
        assert "too large" in resp.json().get("error", "").lower()

    def test_key_too_large_rejected(self):
        app = _make_app()
        client = TestClient(app, raise_server_exceptions=True)
        big_key = self._big_cert(2 * 1024 * 1024)  # 2 MB
        with patch("gateway.web_ui.CERTS_DIR", "/tmp/test-certs"):
            resp = client.post("/api/connect", files={
                "key_file": ("big.key", io.BytesIO(big_key), "application/octet-stream"),
            }, data={
                "name": "test-conn", "url": "https://nifi",
                "auth_method": "certificate_pem"
            })
        assert resp.status_code == 400
        assert "too large" in resp.json().get("error", "").lower()


# ──────────────────────────────────────────────
#  Sensitive data masking in registry
# ──────────────────────────────────────────────

class TestSensitiveDataMasking:
    def test_knox_password_masked_in_safe_dict(self):
        conn = ConnectionInfo(
            name="test", url="https://nifi",
            knox_password="super-secret-123"
        )
        safe = conn.to_safe_dict()
        assert safe["knox_password"] == "***"

    def test_knox_token_masked_in_safe_dict(self):
        conn = ConnectionInfo(
            name="test", url="https://nifi",
            knox_token="eyJhbGciOiJSUzI1NiJ9.secret"
        )
        safe = conn.to_safe_dict()
        assert safe["knox_token"] == "***"

    def test_cert_password_masked_in_safe_dict(self):
        conn = ConnectionInfo(
            name="test", url="https://nifi",
            cert_password="keystore-pass"
        )
        safe = conn.to_safe_dict()
        assert safe["cert_password"] == "***"

    def test_non_sensitive_fields_not_masked(self):
        conn = ConnectionInfo(
            name="prod", url="https://nifi.example.com/nifi-api",
            auth_method="basic", knox_user="admin"
        )
        safe = conn.to_safe_dict()
        assert safe["name"] == "prod"
        assert safe["url"] == "https://nifi.example.com/nifi-api"
        assert safe["knox_user"] == "admin"

    def test_to_dict_excludes_runtime_fields(self):
        conn = ConnectionInfo(name="a", url="https://nifi", connected=True, nifi_version="2.0.0")
        d = conn.to_dict()
        assert "connected" not in d
        assert "nifi_version" not in d


# ──────────────────────────────────────────────
#  Redact sensitive from read/write tools
# ──────────────────────────────────────────────

class TestRedactSensitiveDeep:
    def _redact(self, obj):
        from gateway.tools.read_tools import _redact_sensitive
        return _redact_sensitive(obj)

    def test_password_in_nested_object(self):
        data = {"component": {"properties": {"password": "secret"}}}
        result = self._redact(data)
        assert result["component"]["properties"]["password"] == "***REDACTED***"

    def test_token_in_list(self):
        data = [{"token": "abc123"}, {"token": "xyz456"}]
        result = self._redact(data)
        assert result[0]["token"] == "***REDACTED***"
        assert result[1]["token"] == "***REDACTED***"

    def test_kerberos_keytab_redacted(self):
        data = {"kerberosKeytab": "/path/to/keytab"}
        result = self._redact(data)
        assert result["kerberosKeytab"] == "***REDACTED***"

    def test_ssl_keystore_passwd_redacted(self):
        data = {"sslKeystorePasswd": "changeit"}
        result = self._redact(data)
        assert result["sslKeystorePasswd"] == "***REDACTED***"

    def test_url_not_redacted(self):
        data = {"url": "https://nifi.example.com"}
        result = self._redact(data)
        assert result["url"] == "https://nifi.example.com"

    def test_large_list_truncated(self):
        data = list(range(250))
        result = self._redact(data)
        assert len(result) == 201  # 200 items + truncation marker
        assert result[-1].get("truncated") is True
        assert result[-1]["omitted_count"] == 50
