"""Starlette ASGI app with MCP transport and dashboard."""

from __future__ import annotations

import asyncio
import logging
import os
import uuid
from contextlib import asynccontextmanager

from starlette.applications import Starlette
from starlette.routing import Mount, Route
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse
from mcp.server.streamable_http import StreamableHTTPServerTransport

from gateway.config import settings
from gateway.nifi_registry import ConnectionInfo, registry
from gateway.nifi_client_manager import client_manager, CERTS_DIR
from gateway.mcp_server import server as mcp_server

log = logging.getLogger(__name__)

_transports: dict[str, StreamableHTTPServerTransport] = {}
_session_tasks: dict[str, asyncio.Task] = {}


async def _session_cleanup_loop() -> None:
    """Background task: purge expired idle sessions every 5 minutes."""
    while True:
        await asyncio.sleep(300)
        try:
            removed = client_manager.cleanup_sessions()
            if removed:
                log.info("Cleaned up %d expired sessions", removed)
        except Exception:
            log.exception("Session cleanup failed")


@asynccontextmanager
async def lifespan(app: Starlette):
    log.info("Starting nifi-mcp-universal on port %d", settings.port)

    saved = registry.load()
    for cfg in saved:
        try:
            conn = registry.get(cfg["name"])
            if conn:
                client_manager.connect(conn)
                log.info("Restored connection to '%s'", conn.name)
        except Exception:
            log.exception("Failed to restore '%s'", cfg["name"])

    # Auto-connect default from env
    if settings.nifi_api_base and not registry.list_all():
        conn = ConnectionInfo(
            name="default",
            url=settings.nifi_api_base,
            auth_method=_detect_auth_method(),
            readonly=settings.nifi_readonly,
            verify_ssl=settings.verify_ssl,
            knox_token=settings.knox_token,
            knox_cookie=settings.knox_cookie,
            knox_passcode=settings.knox_passcode_token,
            knox_user=settings.knox_user,
            knox_password=settings.knox_password,
            knox_gateway_url=settings.knox_gateway_url,
            cert_path=settings.nifi_client_p12.replace(CERTS_DIR + "/", "") if settings.nifi_client_p12 else "",
            cert_password=settings.nifi_client_p12_password,
        )
        registry.add(conn)
        try:
            client_manager.connect(conn)
            log.info("Connected to default NiFi")
        except Exception:
            log.exception("Failed to connect to default NiFi")

    # Start background session cleanup
    cleanup_task = asyncio.create_task(_session_cleanup_loop())

    yield

    cleanup_task.cancel()
    try:
        await cleanup_task
    except (asyncio.CancelledError, Exception):
        pass

    for task in _session_tasks.values():
        task.cancel()
    for task in _session_tasks.values():
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass
    _session_tasks.clear()
    _transports.clear()
    client_manager.close_all()
    log.info("Shutdown complete")


def _detect_auth_method() -> str:
    if settings.nifi_client_p12:
        return "certificate_p12"
    if settings.knox_token:
        return "knox_token"
    if settings.knox_cookie:
        return "knox_cookie"
    if settings.knox_passcode_token:
        return "knox_passcode"
    if settings.knox_user and settings.knox_password:
        return "basic"
    return "none"


async def health_check(request: Request) -> JSONResponse:
    return JSONResponse({"status": "ok", **client_manager.get_status()})


async def oauth_protected_resource(request: Request) -> JSONResponse:
    base = str(request.base_url).rstrip("/")
    return JSONResponse({
        "resource": base,
        "authorization_servers": [base],
        "bearer_methods_supported": ["header"],
    })


async def oauth_authorization_server(request: Request) -> JSONResponse:
    base = str(request.base_url).rstrip("/")
    return JSONResponse({
        "issuer": base,
        "token_endpoint": f"{base}/oauth/token",
        "grant_types_supported": ["client_credentials"],
        "token_endpoint_auth_methods_supported": ["none"],
    })


async def oauth_token(request: Request) -> JSONResponse:
    if not settings.api_key:
        return JSONResponse({"error": "invalid_request"}, status_code=400)
    return JSONResponse({
        "access_token": settings.api_key,
        "token_type": "Bearer",
        "expires_in": 86400,
    })


async def _run_session(transport: StreamableHTTPServerTransport, ready: asyncio.Event):
    async with transport.connect() as (read_stream, write_stream):
        ready.set()
        await mcp_server.run(
            read_stream, write_stream, mcp_server.create_initialization_options()
        )


async def handle_mcp(scope, receive, send):
    request = Request(scope, receive)

    if settings.api_key:
        auth = request.headers.get("Authorization", "")
        token = auth[7:] if auth.lower().startswith("bearer ") else ""
        if token != settings.api_key:
            response = JSONResponse({"error": "unauthorized"}, status_code=401,
                                    headers={"WWW-Authenticate": 'Bearer realm="nifi-mcp"'})
            await response(scope, receive, send)
            return

    session_id = request.headers.get("mcp-session-id")
    transport = _transports.get(session_id) if session_id else None

    if transport is None or transport.is_terminated:
        new_id = session_id or uuid.uuid4().hex
        transport = StreamableHTTPServerTransport(mcp_session_id=new_id)
        ready = asyncio.Event()
        task = asyncio.create_task(_run_session(transport, ready))
        await ready.wait()
        _transports[new_id] = transport
        _session_tasks[new_id] = task

    await transport.handle_request(scope, receive, send)


# ── Dashboard routes (lazy import) ─────────────────────────────────

async def dashboard_docs(request: Request) -> HTMLResponse:
    from gateway.web_ui import render_docs
    lang = request.query_params.get("lang", "ru")
    return HTMLResponse(render_docs(lang))


def _dashboard_routes():
    from gateway.web_ui import (
        dashboard_page, api_status, api_connections, api_connect, api_disconnect,
        api_edit, api_switch, api_test,
    )
    return [
        Route("/dashboard", dashboard_page),
        Route("/dashboard/docs", dashboard_docs),
        Route("/api/status", api_status),
        Route("/api/connections", api_connections),
        Route("/api/connect", api_connect, methods=["POST"]),
        Route("/api/disconnect", api_disconnect, methods=["POST"]),
        Route("/api/edit", api_edit, methods=["POST"]),
        Route("/api/switch", api_switch, methods=["POST"]),
        Route("/api/test", api_test, methods=["POST"]),
    ]


_inner = Starlette(
    lifespan=lifespan,
    routes=[
        Route("/health", health_check),
        Route("/.well-known/oauth-protected-resource", oauth_protected_resource),
        Route("/.well-known/oauth-authorization-server", oauth_authorization_server),
        Route("/oauth/token", oauth_token, methods=["POST"]),
        Mount("/mcp", app=handle_mcp),
        *_dashboard_routes(),
    ],
)


async def app(scope, receive, send):
    if scope["type"] == "http" and scope["path"] == "/mcp":
        await handle_mcp(scope, receive, send)
    else:
        await _inner(scope, receive, send)
