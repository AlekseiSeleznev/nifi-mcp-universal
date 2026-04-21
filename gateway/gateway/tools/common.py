"""Shared helpers for NiFi tool handlers."""

from __future__ import annotations

import json
from typing import Any

from mcp.types import TextContent


_REDACT_KEYS = {"password", "passcode", "token", "secret", "kerberoskeytab", "sslkeystorepasswd"}


def redact_sensitive(obj: Any, max_items: int = 200) -> Any:
    """Redact known secret-like keys recursively and truncate large lists."""
    if isinstance(obj, dict):
        return {
            k: ("***REDACTED***" if k.lower() in _REDACT_KEYS else redact_sensitive(v, max_items))
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        if len(obj) > max_items:
            return [redact_sensitive(x, max_items) for x in obj[:max_items]] + [
                {"truncated": True, "omitted_count": len(obj) - max_items}
            ]
        return [redact_sensitive(x, max_items) for x in obj]
    return obj


def json_text(data: Any) -> list[TextContent]:
    """Return MCP text response containing JSON-serialized payload."""
    return [TextContent(type="text", text=json.dumps(data, indent=2, ensure_ascii=False, default=str))]
