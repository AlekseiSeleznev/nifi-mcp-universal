"""Shared helpers for NiFi dashboard API handlers."""

from __future__ import annotations

import hmac
import json
import re

from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from gateway.config import settings
from gateway.web_ui_content import DASHBOARD_HTML, _T

# Connection name: letters, digits, hyphens, underscores only
CONN_NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,62}$")
MAX_JSON_BODY_BYTES = 256 * 1024
MAX_MULTIPART_BODY_BYTES = 3 * 1024 * 1024


def json_response(data, status_code: int = 200) -> Response:
    body = json.dumps(data, ensure_ascii=False, default=str)
    return Response(body, status_code=status_code, media_type="application/json")


def error_response(message: str, status_code: int = 400, *, ok: bool | None = None) -> Response:
    payload = {"error": str(message)}
    if ok is not None:
        payload["ok"] = ok
    return json_response(payload, status_code)


def enforce_content_length(request: Request, max_bytes: int) -> JSONResponse | None:
    header = request.headers.get("content-length")
    if not header:
        return None
    try:
        content_length = int(header)
    except ValueError:
        return JSONResponse({"error": "invalid content-length"}, status_code=400)
    if content_length > max_bytes:
        return JSONResponse({"error": f"request body too large (max {max_bytes} bytes)"}, status_code=413)
    return None


def check_api_auth(request: Request) -> JSONResponse | None:
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


def render_dashboard(lang: str = "ru") -> str:
    if lang not in _T:
        lang = "ru"
    t = _T.get(lang, _T["ru"])
    html = DASHBOARD_HTML
    for k, v in t.items():
        html = html.replace("{{" + k + "}}", v)
    html = html.replace("{{lang}}", lang)
    html = html.replace("{{ru_on}}", "on" if lang == "ru" else "")
    html = html.replace("{{en_on}}", "on" if lang == "en" else "")
    html = html.replace("{{t_json}}", json.dumps(t, ensure_ascii=False))
    return html
