"""Tests for gateway.web_ui — dashboard docs, auth guard, and core API endpoints."""

from __future__ import annotations

import io
from unittest.mock import MagicMock, patch

from starlette.applications import Starlette
from starlette.responses import HTMLResponse
from starlette.routing import Route
from starlette.testclient import TestClient


def _build_app():
    from gateway.web_ui import (
        dashboard_page,
        render_docs,
        api_status,
        api_connections,
        api_connect,
        api_disconnect,
        api_edit,
        api_switch,
        api_test,
    )

    async def dashboard_docs(request):
        return HTMLResponse(render_docs(request.query_params.get("lang", "ru")))

    return Starlette(routes=[
        Route("/dashboard", dashboard_page),
        Route("/dashboard/docs", dashboard_docs),
        Route("/api/status", api_status),
        Route("/api/connections", api_connections),
        Route("/api/connect", api_connect, methods=["POST"]),
        Route("/api/disconnect", api_disconnect, methods=["POST"]),
        Route("/api/edit", api_edit, methods=["POST"]),
        Route("/api/switch", api_switch, methods=["POST"]),
        Route("/api/test", api_test, methods=["POST"]),
    ])


class TestDashboardDocs:
    def test_dashboard_returns_html(self):
        app = _build_app()
        with patch("gateway.web_ui.settings") as ms:
            ms.api_key = ""
            client = TestClient(app)
            resp = client.get("/dashboard")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]
        assert "nifi-mcp-universal" in resp.text

    def test_docs_ru_are_synced_with_actual_port_and_tool_count(self):
        app = _build_app()
        with patch("gateway.web_ui.settings") as ms:
            ms.api_key = ""
            client = TestClient(app)
            resp = client.get("/dashboard/docs?lang=ru")
        assert resp.status_code == 200
        assert "66 MCP tools" in resp.text
        assert "http://localhost:8085/dashboard" in resp.text
        assert "http://localhost:8085/mcp" in resp.text
        assert "docs/mcp-tool-catalog.md" in resp.text
        assert "codex mcp add nifi-universal --url http://localhost:8085/mcp" in resp.text
        assert "CODEX.md" in resp.text
        assert "AGENTS.md" in resp.text
        legacy_brand = "Cl" "aude"
        assert legacy_brand not in resp.text
        assert "Подключение MCP-клиента" in resp.text
        assert "Codex (опционально)" in resp.text

    def test_docs_en_are_synced_with_actual_port_and_tool_count(self):
        app = _build_app()
        with patch("gateway.web_ui.settings") as ms:
            ms.api_key = ""
            client = TestClient(app)
            resp = client.get("/dashboard/docs?lang=en")
        assert resp.status_code == 200
        assert "66 MCP tools" in resp.text
        assert "http://localhost:8085/dashboard" in resp.text
        assert "http://localhost:8085/mcp" in resp.text
        assert "docs/mcp-tool-catalog.md" in resp.text
        assert "codex mcp add nifi-universal --url http://localhost:8085/mcp" in resp.text
        assert "CODEX.md" in resp.text
        assert "AGENTS.md" in resp.text
        legacy_brand = "Cl" "aude"
        assert legacy_brand not in resp.text
        assert "MCP Client Setup" in resp.text
        assert "Codex (Optional)" in resp.text
        assert "Подключиться к NiFi" not in resp.text

    def test_dashboard_contains_mobile_layout_basics(self):
        app = _build_app()
        with patch("gateway.web_ui.settings") as ms:
            ms.api_key = ""
            client = TestClient(app)
            resp = client.get("/dashboard?lang=en")
        assert resp.status_code == 200
        assert '<meta name="viewport" content="width=device-width,initial-scale=1">' in resp.text
        assert "@media(max-width:900px)" in resp.text
        assert "@media(max-width:600px)" in resp.text

    def test_dashboard_does_not_embed_api_key(self):
        app = _build_app()
        with patch("gateway.web_ui.settings") as ms:
            ms.api_key = "my-super-secret-key"
            client = TestClient(app)
            resp = client.get("/dashboard")
        assert resp.status_code == 200
        assert "my-super-secret-key" not in resp.text


class TestDashboardApiAuth:
    def test_status_requires_bearer_when_api_key_set(self):
        app = _build_app()
        with patch("gateway.web_ui.settings") as ms:
            ms.api_key = "secret-token"
            client = TestClient(app)
            resp = client.get("/api/status")
        assert resp.status_code == 401
        assert resp.json()["error"] == "unauthorized"

    def test_status_allows_bearer_when_api_key_set(self):
        app = _build_app()
        with patch("gateway.web_ui.settings") as ms, \
             patch("gateway.web_ui.client_manager") as mock_mgr:
            ms.api_key = "secret-token"
            mock_mgr.get_status.return_value = {"connections": {}, "sessions": 0, "active_default": ""}
            client = TestClient(app)
            resp = client.get("/api/status", headers={"Authorization": "Bearer secret-token"})
        assert resp.status_code == 200
        assert resp.json()["sessions"] == 0

    def test_status_auth_uses_compare_digest(self):
        app = _build_app()
        calls = []

        def fake_compare_digest(left, right):
            calls.append((left, right))
            return True

        with patch("gateway.web_ui.settings") as ms, \
             patch("gateway.web_ui.client_manager") as mock_mgr, \
             patch("gateway.web_ui.hmac.compare_digest", side_effect=fake_compare_digest):
            ms.api_key = "secret-token"
            mock_mgr.get_status.return_value = {"connections": {}, "sessions": 0, "active_default": ""}
            client = TestClient(app)
            resp = client.get("/api/status", headers={"Authorization": "Bearer secret-token"})

        assert resp.status_code == 200
        assert calls == [("secret-token", "secret-token")]

    def test_remaining_api_endpoints_deny_without_bearer(self):
        app = _build_app()
        cases = [
            ("get", "/api/connections", None),
            ("post", "/api/disconnect", {}),
            ("post", "/api/edit", {}),
            ("post", "/api/switch", {}),
            ("post", "/api/test", {}),
        ]
        with patch("gateway.web_ui.settings") as ms:
            ms.api_key = "secret-token"
            client = TestClient(app)
            for method, path, payload in cases:
                kwargs = {"json": payload} if payload is not None else {}
                response = getattr(client, method)(path, **kwargs)
                assert response.status_code == 401


class TestDashboardApiValidation:
    def test_connect_missing_name_returns_400(self):
        app = _build_app()
        with patch("gateway.web_ui.settings") as ms:
            ms.api_key = ""
            client = TestClient(app)
            resp = client.post("/api/connect", json={"url": "https://nifi"})
        assert resp.status_code == 400

    def test_disconnect_missing_name_returns_400(self):
        app = _build_app()
        with patch("gateway.web_ui.settings") as ms:
            ms.api_key = ""
            client = TestClient(app)
            resp = client.post("/api/disconnect", json={})
        assert resp.status_code == 400

    def test_disconnect_and_switch_reject_too_large_body(self):
        app = _build_app()
        headers = {"content-length": str(256 * 1024 + 1), "content-type": "application/json"}
        with patch("gateway.web_ui.settings") as ms:
            ms.api_key = ""
            client = TestClient(app)
            disconnect_resp = client.post("/api/disconnect", headers=headers, content=b"{}")
            switch_resp = client.post("/api/switch", headers=headers, content=b"{}")
        assert disconnect_resp.status_code == 413
        assert switch_resp.status_code == 413


class TestDashboardApiLifecycle:
    def test_connection_lifecycle_connect_switch_list_disconnect(self):
        app = _build_app()

        mock_conn = MagicMock()
        mock_conn.to_safe_dict.return_value = {"name": "prod", "url": "https://nifi", "connected": True}

        with patch("gateway.web_ui.settings") as ms, \
             patch("gateway.web_ui.registry") as mock_reg, \
             patch("gateway.web_ui.client_manager") as mock_mgr:
            ms.api_key = ""
            mock_reg.list_all.return_value = [mock_conn]
            mock_reg.remove.return_value = object()
            mock_reg.active = ""
            client = TestClient(app)

            connect_resp = client.post(
                "/api/connect",
                json={"name": "prod", "url": "https://nifi.example.com/nifi-api", "auth_method": "none"},
            )
            assert connect_resp.status_code == 200
            assert connect_resp.json()["ok"] is True
            assert connect_resp.json()["name"] == "prod"
            mock_reg.add.assert_called_once()
            mock_mgr.connect.assert_called_once()

            switch_resp = client.post("/api/switch", json={"name": "prod"})
            assert switch_resp.status_code == 200
            assert switch_resp.json()["ok"] is True
            mock_mgr.switch.assert_called_once_with("prod")
            assert mock_reg.active == "prod"
            assert mock_reg.save.called

            list_resp = client.get("/api/connections")
            assert list_resp.status_code == 200
            assert list_resp.json()[0]["name"] == "prod"
            assert list_resp.json()[0]["connected"] is True

            disconnect_resp = client.post("/api/disconnect", json={"name": "prod"})
            assert disconnect_resp.status_code == 200
            assert disconnect_resp.json()["ok"] is True
            mock_mgr.disconnect.assert_called_once_with("prod")

    def test_test_endpoint_success_and_error(self):
        app = _build_app()

        fake_client = MagicMock()
        fake_client.get_version_info.return_value = {"about": {"version": "2.0.0"}}
        fake_client.session.close = MagicMock()

        with patch("gateway.web_ui.settings") as ms, patch("gateway.web_ui._build_client", return_value=fake_client):
            ms.api_key = ""
            client = TestClient(app)
            ok_resp = client.post("/api/test", json={"url": "https://nifi.example.com/nifi-api"})
        assert ok_resp.status_code == 200
        assert ok_resp.json() == {"ok": True, "nifi_version": "2.0.0"}
        fake_client.session.close.assert_called_once()

        with patch("gateway.web_ui.settings") as ms, patch("gateway.web_ui._build_client", side_effect=Exception("boom")):
            ms.api_key = ""
            client = TestClient(app)
            err_resp = client.post("/api/test", json={"url": "https://nifi.example.com/nifi-api"})
        assert err_resp.status_code == 502
        assert err_resp.json()["ok"] is False
        assert err_resp.json()["error"] == "connection test failed"

    def test_test_endpoint_supports_p12_multipart(self, tmp_path):
        app = _build_app()

        fake_client = MagicMock()
        fake_client.get_version_info.return_value = {"about": {"version": "2.8.0"}}
        fake_client.session.close = MagicMock()

        with patch("gateway.web_ui.settings") as ms, \
             patch("gateway.web_ui.CERTS_DIR", str(tmp_path)), \
             patch("gateway.web_ui._build_client", return_value=fake_client):
            ms.api_key = ""
            client = TestClient(app)
            resp = client.post(
                "/api/test",
                files={"cert_file": ("client.p12", io.BytesIO(b"P12DATA"), "application/octet-stream")},
                data={
                    "url": "https://nifi.example.com/nifi",
                    "auth_method": "certificate_p12",
                    "verify_ssl": "false",
                    "cert_password": "secret",
                },
            )

        assert resp.status_code == 200
        assert resp.json() == {"ok": True, "nifi_version": "2.8.0"}

    def test_connections_disconnect_not_found_and_switch_error_paths(self):
        app = _build_app()
        safe_conn = MagicMock()
        safe_conn.to_safe_dict.return_value = {"name": "prod"}
        with patch("gateway.web_ui.settings") as ms, \
             patch("gateway.web_ui.registry") as mock_reg, \
             patch("gateway.web_ui.client_manager") as mock_mgr:
            ms.api_key = ""
            mock_reg.list_all.return_value = [safe_conn]
            mock_reg.remove.return_value = None
            mock_mgr.switch.side_effect = ValueError("bad switch")
            client = TestClient(app)

            conns = client.get("/api/connections")
            assert conns.status_code == 200
            assert conns.json() == [{"name": "prod"}]

            not_found = client.post("/api/disconnect", json={"name": "ghost"})
            assert not_found.status_code == 404

            switch = client.post("/api/switch", json={"name": "ghost"})
            assert switch.status_code == 400


class TestDashboardErrorContract:
    def test_mutation_endpoints_return_json_error_payload(self):
        app = _build_app()
        cases = [
            ("/api/connect", {"url": "https://nifi.example.com/nifi-api"}, 400),
            ("/api/disconnect", {}, 400),
            ("/api/edit", {"name": "prod", "url": "https://nifi.example.com/nifi-api"}, 400),
            ("/api/switch", {}, 400),
            ("/api/test", {}, 400),
        ]

        with patch("gateway.web_ui.settings") as ms:
            ms.api_key = ""
            client = TestClient(app)
            for endpoint, payload, status_code in cases:
                resp = client.post(endpoint, json=payload)
                assert resp.status_code == status_code
                assert "application/json" in resp.headers["content-type"]
                assert isinstance(resp.json().get("error"), str)
