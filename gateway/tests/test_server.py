"""Tests for gateway.server — health endpoint, auth detection, OAuth endpoints."""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from starlette.testclient import TestClient
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.responses import JSONResponse

from gateway.server import (
    health_check,
    oauth_protected_resource,
    oauth_authorization_server,
    oauth_token,
    _detect_auth_method,
)


# ──────────────────────────────────────────────
#  _detect_auth_method
# ──────────────────────────────────────────────

class TestDetectAuthMethod:
    def test_none_when_no_creds(self, monkeypatch):
        monkeypatch.setattr("gateway.server.settings.nifi_client_p12", "")
        monkeypatch.setattr("gateway.server.settings.knox_token", "")
        monkeypatch.setattr("gateway.server.settings.knox_cookie", "")
        monkeypatch.setattr("gateway.server.settings.knox_passcode_token", "")
        monkeypatch.setattr("gateway.server.settings.knox_user", "")
        monkeypatch.setattr("gateway.server.settings.knox_password", "")
        assert _detect_auth_method() == "none"

    def test_certificate_p12_priority(self, monkeypatch):
        monkeypatch.setattr("gateway.server.settings.nifi_client_p12", "/path/to/cert.p12")
        monkeypatch.setattr("gateway.server.settings.knox_token", "token")
        assert _detect_auth_method() == "certificate_p12"

    def test_knox_token(self, monkeypatch):
        monkeypatch.setattr("gateway.server.settings.nifi_client_p12", "")
        monkeypatch.setattr("gateway.server.settings.knox_token", "my-token")
        monkeypatch.setattr("gateway.server.settings.knox_cookie", "")
        monkeypatch.setattr("gateway.server.settings.knox_passcode_token", "")
        monkeypatch.setattr("gateway.server.settings.knox_user", "")
        monkeypatch.setattr("gateway.server.settings.knox_password", "")
        assert _detect_auth_method() == "knox_token"

    def test_knox_cookie(self, monkeypatch):
        monkeypatch.setattr("gateway.server.settings.nifi_client_p12", "")
        monkeypatch.setattr("gateway.server.settings.knox_token", "")
        monkeypatch.setattr("gateway.server.settings.knox_cookie", "my-cookie")
        monkeypatch.setattr("gateway.server.settings.knox_passcode_token", "")
        monkeypatch.setattr("gateway.server.settings.knox_user", "")
        monkeypatch.setattr("gateway.server.settings.knox_password", "")
        assert _detect_auth_method() == "knox_cookie"

    def test_knox_passcode(self, monkeypatch):
        monkeypatch.setattr("gateway.server.settings.nifi_client_p12", "")
        monkeypatch.setattr("gateway.server.settings.knox_token", "")
        monkeypatch.setattr("gateway.server.settings.knox_cookie", "")
        monkeypatch.setattr("gateway.server.settings.knox_passcode_token", "my-passcode")
        monkeypatch.setattr("gateway.server.settings.knox_user", "")
        monkeypatch.setattr("gateway.server.settings.knox_password", "")
        assert _detect_auth_method() == "knox_passcode"

    def test_basic_auth(self, monkeypatch):
        monkeypatch.setattr("gateway.server.settings.nifi_client_p12", "")
        monkeypatch.setattr("gateway.server.settings.knox_token", "")
        monkeypatch.setattr("gateway.server.settings.knox_cookie", "")
        monkeypatch.setattr("gateway.server.settings.knox_passcode_token", "")
        monkeypatch.setattr("gateway.server.settings.knox_user", "admin")
        monkeypatch.setattr("gateway.server.settings.knox_password", "secret")
        assert _detect_auth_method() == "basic"


# ──────────────────────────────────────────────
#  Simple endpoint tests using minimal app
# ──────────────────────────────────────────────

def _make_test_app():
    """Create a minimal Starlette app for testing endpoints."""
    async def _health(request):
        return await health_check(request)

    async def _oauth_resource(request):
        return await oauth_protected_resource(request)

    async def _oauth_server(request):
        return await oauth_authorization_server(request)

    async def _oauth_token(request):
        return await oauth_token(request)

    return Starlette(routes=[
        Route("/health", _health),
        Route("/.well-known/oauth-protected-resource", _oauth_resource),
        Route("/.well-known/oauth-authorization-server", _oauth_server),
        Route("/oauth/token", _oauth_token, methods=["POST"]),
    ])


class TestHealthEndpoint:
    def test_health_returns_ok(self):
        with patch("gateway.server.client_manager") as mock_mgr:
            mock_mgr.get_status.return_value = {"connections": {}, "sessions": 0, "active_default": ""}
            app = _make_test_app()
            client = TestClient(app, raise_server_exceptions=True)
            resp = client.get("/health")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"

    def test_health_includes_connection_status(self):
        status = {"connections": {"a": {}}, "sessions": 1, "active_default": "a"}
        with patch("gateway.server.client_manager") as mock_mgr:
            mock_mgr.get_status.return_value = status
            app = _make_test_app()
            client = TestClient(app, raise_server_exceptions=True)
            resp = client.get("/health")

        data = resp.json()
        assert "connections" in data
        assert data["sessions"] == 1


class TestOAuthEndpoints:
    def test_oauth_protected_resource(self):
        with patch("gateway.server.client_manager") as mock_mgr:
            mock_mgr.get_status.return_value = {}
            app = _make_test_app()
            client = TestClient(app, raise_server_exceptions=True)
            resp = client.get("/.well-known/oauth-protected-resource")

        assert resp.status_code == 200
        data = resp.json()
        assert "resource" in data
        assert "authorization_servers" in data

    def test_oauth_authorization_server(self):
        with patch("gateway.server.client_manager") as mock_mgr:
            mock_mgr.get_status.return_value = {}
            app = _make_test_app()
            client = TestClient(app, raise_server_exceptions=True)
            resp = client.get("/.well-known/oauth-authorization-server")

        assert resp.status_code == 200
        data = resp.json()
        assert "issuer" in data
        assert "token_endpoint" in data
        assert "grant_types_supported" in data

    def test_oauth_token_no_api_key_returns_error(self):
        with patch("gateway.server.settings") as mock_settings:
            mock_settings.api_key = ""
            app = _make_test_app()
            client = TestClient(app, raise_server_exceptions=True)
            resp = client.post("/oauth/token")

        assert resp.status_code == 400
        data = resp.json()
        assert "error" in data

    def test_oauth_token_with_api_key_returns_token(self):
        with patch("gateway.server.settings") as mock_settings:
            mock_settings.api_key = "my-secret-key"
            app = _make_test_app()
            client = TestClient(app, raise_server_exceptions=True)
            resp = client.post("/oauth/token")

        assert resp.status_code == 200
        data = resp.json()
        assert data["access_token"] == "my-secret-key"
        assert data["token_type"] == "Bearer"
