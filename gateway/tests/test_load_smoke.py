"""Lightweight load-smoke tests for dashboard and session routing paths."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock, patch

from starlette.applications import Starlette
from starlette.routing import Route
from starlette.testclient import TestClient


def _build_dashboard_app():
    from gateway.web_ui import dashboard_page, api_status, api_connections

    return Starlette(routes=[
        Route("/dashboard", dashboard_page),
        Route("/api/status", api_status),
        Route("/api/connections", api_connections),
    ])


def test_dashboard_high_frequency_status_and_connections_smoke():
    app = _build_dashboard_app()
    fake_conn = MagicMock()
    fake_conn.to_safe_dict.return_value = {"name": "prod", "connected": True}

    with patch("gateway.web_ui.settings") as ms, \
         patch("gateway.web_ui.client_manager") as cm, \
         patch("gateway.web_ui.registry") as reg:
        ms.api_key = ""
        cm.get_status.return_value = {"connections": {"prod": {"readonly": True}}, "sessions": 0, "active_default": "prod"}
        reg.list_all.return_value = [fake_conn]

        with TestClient(app) as client:
            for _ in range(120):
                status = client.get("/api/status")
                conns = client.get("/api/connections")
                assert status.status_code == 200
                assert conns.status_code == 200


def test_concurrent_session_switching_smoke():
    from gateway.nifi_client_manager import NiFiClientManager

    manager = NiFiClientManager()
    manager._clients["a"] = MagicMock()
    manager._clients["b"] = MagicMock()

    def _switch(i: int) -> bool:
        target = "a" if i % 2 == 0 else "b"
        sid = f"s{i % 20}"
        manager.switch(target, session_id=sid)
        active = manager.get_active_name(session_id=sid)
        return active in {"a", "b"}

    with ThreadPoolExecutor(max_workers=10) as ex:
        results = list(ex.map(_switch, range(400)))

    assert all(results)
    assert manager.get_status()["sessions"] == 20


def test_mixed_dashboard_and_api_traffic_smoke():
    app = _build_dashboard_app()
    fake_conn = MagicMock()
    fake_conn.to_safe_dict.return_value = {"name": "prod", "connected": True}

    with patch("gateway.web_ui.settings") as ms, \
         patch("gateway.web_ui.client_manager") as cm, \
         patch("gateway.web_ui.registry") as reg:
        ms.api_key = ""
        cm.get_status.return_value = {"connections": {"prod": {"readonly": True}}, "sessions": 0, "active_default": "prod"}
        reg.list_all.return_value = [fake_conn]

        with TestClient(app) as client:
            for _ in range(80):
                html = client.get("/dashboard?lang=en")
                status = client.get("/api/status")
                conns = client.get("/api/connections")
                assert html.status_code == 200
                assert status.status_code == 200
                assert conns.status_code == 200
