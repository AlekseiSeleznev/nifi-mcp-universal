"""Tests for shared tool helpers in gateway.tools.common."""

from __future__ import annotations

import json

from gateway.tools.common import json_text, redact_sensitive


def test_redact_sensitive_nested_and_truncation():
    payload = {
        "token": "abc",
        "nested": {"password": "secret", "ok": "yes"},
        "items": [{"name": f"i{i}"} for i in range(5)],
    }
    redacted = redact_sensitive(payload, max_items=3)
    assert redacted["token"] == "***REDACTED***"
    assert redacted["nested"]["password"] == "***REDACTED***"
    assert redacted["nested"]["ok"] == "yes"
    assert redacted["items"][-1]["truncated"] is True


def test_json_text_returns_single_textcontent_with_json():
    result = json_text({"ok": True, "count": 2})
    assert len(result) == 1
    parsed = json.loads(result[0].text)
    assert parsed["ok"] is True
    assert parsed["count"] == 2
