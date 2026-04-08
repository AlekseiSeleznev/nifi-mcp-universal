"""Tests for gateway.nifi_registry — ConnectionInfo and ConnectionRegistry."""
from __future__ import annotations

import json
import pytest
from pathlib import Path

from gateway.nifi_registry import ConnectionInfo, ConnectionRegistry, _SENSITIVE_FIELDS


class TestConnectionInfo:
    def test_defaults(self):
        conn = ConnectionInfo(name="test", url="https://nifi.example.com")
        assert conn.auth_method == "none"
        assert conn.readonly is True
        assert conn.verify_ssl is True
        assert conn.connected is False
        assert conn.nifi_version == ""

    def test_to_dict_excludes_runtime_fields(self):
        conn = ConnectionInfo(name="x", url="https://x", connected=True, nifi_version="2.0.0")
        d = conn.to_dict()
        assert "connected" not in d
        assert "nifi_version" not in d
        assert d["name"] == "x"
        assert d["url"] == "https://x"

    def test_to_safe_dict_masks_sensitive(self):
        conn = ConnectionInfo(
            name="x",
            url="https://x",
            knox_token="my-secret-jwt",
            knox_password="hunter2",
            cert_password="certpass",
        )
        d = conn.to_safe_dict()
        assert d["knox_token"] == "***"
        assert d["knox_password"] == "***"
        assert d["cert_password"] == "***"

    def test_to_safe_dict_keeps_connected_and_version(self):
        conn = ConnectionInfo(name="x", url="https://x", connected=True, nifi_version="1.23.2")
        d = conn.to_safe_dict()
        assert d["connected"] is True
        assert d["nifi_version"] == "1.23.2"

    def test_to_safe_dict_empty_sensitive_not_masked(self):
        conn = ConnectionInfo(name="x", url="https://x")
        d = conn.to_safe_dict()
        # Empty strings should not be masked to "***"
        assert d["knox_token"] != "***"
        assert d["knox_password"] != "***"

    def test_sensitive_fields_constant(self):
        """Ensure the constant includes expected fields."""
        assert "cert_password" in _SENSITIVE_FIELDS
        assert "knox_password" in _SENSITIVE_FIELDS
        assert "knox_token" in _SENSITIVE_FIELDS
        assert "knox_cookie" in _SENSITIVE_FIELDS


class TestConnectionRegistry:
    def test_add_sets_active_to_first(self, registry):
        conn = ConnectionInfo(name="alpha", url="https://a")
        registry.add(conn)
        # We bypass save — monkeypatch save to no-op
        assert registry.active == "alpha"

    def test_add_second_does_not_change_active(self, tmp_path, registry, monkeypatch):
        monkeypatch.setattr(registry, "save", lambda: None)
        registry.add(ConnectionInfo(name="alpha", url="https://a"))
        registry.add(ConnectionInfo(name="beta", url="https://b"))
        assert registry.active == "alpha"

    def test_remove_returns_conn(self, registry, monkeypatch):
        monkeypatch.setattr(registry, "save", lambda: None)
        conn = ConnectionInfo(name="x", url="https://x")
        registry._connections["x"] = conn
        registry._active = "x"
        result = registry.remove("x")
        assert result is conn

    def test_remove_nonexistent_returns_none(self, registry, monkeypatch):
        monkeypatch.setattr(registry, "save", lambda: None)
        result = registry.remove("ghost")
        assert result is None

    def test_remove_active_switches_to_next(self, registry, monkeypatch):
        monkeypatch.setattr(registry, "save", lambda: None)
        registry._connections["a"] = ConnectionInfo(name="a", url="https://a")
        registry._connections["b"] = ConnectionInfo(name="b", url="https://b")
        registry._active = "a"
        registry.remove("a")
        assert registry.active == "b"

    def test_get_returns_connection(self, registry):
        conn = ConnectionInfo(name="x", url="https://x")
        registry._connections["x"] = conn
        assert registry.get("x") is conn

    def test_get_missing_returns_none(self, registry):
        assert registry.get("missing") is None

    def test_list_all(self, registry):
        registry._connections["a"] = ConnectionInfo(name="a", url="https://a")
        registry._connections["b"] = ConnectionInfo(name="b", url="https://b")
        result = registry.list_all()
        assert len(result) == 2

    def test_active_setter(self, registry):
        registry._connections["z"] = ConnectionInfo(name="z", url="https://z")
        registry.active = "z"
        assert registry.active == "z"

    def test_save_creates_file(self, tmp_path, monkeypatch):
        monkeypatch.setenv("NIFI_MCP_STATE_FILE", str(tmp_path / "state.json"))
        import gateway.nifi_registry as reg_mod
        monkeypatch.setattr(reg_mod, "STATE_FILE", str(tmp_path / "state.json"))

        reg = ConnectionRegistry()
        conn = ConnectionInfo(name="saved", url="https://s")
        reg._connections["saved"] = conn
        reg._active = "saved"
        reg.save()

        data = json.loads((tmp_path / "state.json").read_text())
        assert data["active"] == "saved"
        assert any(c["name"] == "saved" for c in data["connections"])

    def test_load_reads_file(self, tmp_path, monkeypatch):
        state_path = tmp_path / "state.json"
        state_path.write_text(json.dumps({
            "active": "loaded",
            "connections": [
                {"name": "loaded", "url": "https://l", "auth_method": "none",
                 "cert_path": "", "cert_password": "", "cert_key_path": "",
                 "knox_token": "", "knox_cookie": "", "knox_passcode": "",
                 "knox_user": "", "knox_password": "", "knox_gateway_url": "",
                 "verify_ssl": True, "readonly": True}
            ]
        }))

        import gateway.nifi_registry as reg_mod
        monkeypatch.setattr(reg_mod, "STATE_FILE", str(state_path))

        reg = ConnectionRegistry()
        reg.load()
        assert reg.active == "loaded"
        assert reg.get("loaded") is not None

    def test_load_missing_file_returns_empty(self, tmp_path, monkeypatch):
        import gateway.nifi_registry as reg_mod
        monkeypatch.setattr(reg_mod, "STATE_FILE", str(tmp_path / "nonexistent.json"))
        reg = ConnectionRegistry()
        result = reg.load()
        assert result == []

    def test_load_ignores_unknown_fields(self, tmp_path, monkeypatch):
        """Unknown fields in persisted state should be silently dropped."""
        state_path = tmp_path / "state.json"
        state_path.write_text(json.dumps({
            "active": "x",
            "connections": [
                {"name": "x", "url": "https://x", "auth_method": "none",
                 "cert_path": "", "cert_password": "", "cert_key_path": "",
                 "knox_token": "", "knox_cookie": "", "knox_passcode": "",
                 "knox_user": "", "knox_password": "", "knox_gateway_url": "",
                 "verify_ssl": True, "readonly": True,
                 "future_unknown_field": "ignored"}
            ]
        }))
        import gateway.nifi_registry as reg_mod
        monkeypatch.setattr(reg_mod, "STATE_FILE", str(state_path))
        reg = ConnectionRegistry()
        reg.load()  # must not raise
        assert reg.get("x") is not None
