"""Dashboard — web UI for NiFi MCP connection management."""

from __future__ import annotations

import hmac
import logging

from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, Response

from gateway.config import settings
from gateway.nifi_registry import ConnectionInfo, registry
from gateway.nifi_client_manager import client_manager, _build_client, CERTS_DIR
from gateway.web_ui_content import DASHBOARD_HTML, _T, render_docs
from gateway.web_ui_helpers import (
    CONN_NAME_RE,
    MAX_JSON_BODY_BYTES,
    enforce_content_length,
    error_response,
    json_response,
    render_dashboard,
)
from gateway.web_ui_services import connect_from_request, edit_from_request, test_from_request

log = logging.getLogger(__name__)


def _check_api_auth(request: Request) -> JSONResponse | None:
    """Verify Bearer token on dashboard API endpoints."""
    if not settings.api_key:
        return None
    auth = request.headers.get("Authorization", "")
    token = auth[7:] if auth.lower().startswith("bearer ") else ""
    if not hmac.compare_digest(token, settings.api_key):
        return JSONResponse(
            {"error": "unauthorized"},
            status_code=401,
            headers={"WWW-Authenticate": 'Bearer realm="nifi-mcp"'},
        )
    return None


async def dashboard_page(request: Request) -> HTMLResponse:
    lang = request.query_params.get("lang", "ru")
    return HTMLResponse(render_dashboard(lang))


async def api_status(request: Request) -> JSONResponse:
    denied = _check_api_auth(request)
    if denied:
        return denied
    return JSONResponse(client_manager.get_status())


async def api_connections(request: Request) -> JSONResponse:
    denied = _check_api_auth(request)
    if denied:
        return denied
    conns = registry.list_all()
    return JSONResponse([c.to_safe_dict() for c in conns])


async def api_connect(request: Request) -> Response:
    denied = _check_api_auth(request)
    if denied:
        return denied
    return await connect_from_request(
        request,
        registry=registry,
        client_manager=client_manager,
        certs_dir=CERTS_DIR,
        conn_name_re=CONN_NAME_RE,
        connection_info_cls=ConnectionInfo,
    )


async def api_disconnect(request: Request) -> Response:
    denied = _check_api_auth(request)
    if denied:
        return denied
    too_large = enforce_content_length(request, MAX_JSON_BODY_BYTES)
    if too_large:
        return too_large
    body = await request.json()
    name = body.get("name", "").strip()
    if not name:
        return error_response("name is required", 400)
    removed = registry.remove(name)
    if not removed:
        return error_response(f"'{name}' not found", 404)
    client_manager.disconnect(name)
    return json_response({"ok": True})


async def api_edit(request: Request) -> Response:
    denied = _check_api_auth(request)
    if denied:
        return denied
    return await edit_from_request(
        request,
        registry=registry,
        client_manager=client_manager,
        certs_dir=CERTS_DIR,
        conn_name_re=CONN_NAME_RE,
        connection_info_cls=ConnectionInfo,
        build_client=_build_client,
    )


async def api_switch(request: Request) -> Response:
    denied = _check_api_auth(request)
    if denied:
        return denied
    too_large = enforce_content_length(request, MAX_JSON_BODY_BYTES)
    if too_large:
        return too_large
    body = await request.json()
    name = body.get("name", "").strip()
    if not name:
        return error_response("name is required", 400)
    try:
        client_manager.switch(name)
    except ValueError as e:
        return error_response(str(e), 400)
    registry.active = name
    registry.save()
    return json_response({"ok": True})


async def api_test(request: Request) -> Response:
    denied = _check_api_auth(request)
    if denied:
        return denied
    return await test_from_request(
        request,
        build_client=_build_client,
        connection_info_cls=ConnectionInfo,
        certs_dir=CERTS_DIR,
    )
