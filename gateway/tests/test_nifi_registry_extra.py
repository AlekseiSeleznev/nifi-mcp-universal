"""Additional registry tests — persistence, unknown field filtering, active management."""
from __future__ import annotations

import json
import pytest
import tempfile
import os

from gateway.nifi_registry import ConnectionInfo, ConnectionRegistry


class TestConnectionRegistryPersistence:
    def test_save_and_reload(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            state_file = f.name

        os.environ["NIFI_MCP_STATE_FILE"] = state_file
        try:
            reg = ConnectionRegistry()
            # Patch the STATE_FILE variable inside the module
            import gateway.nifi_registry as reg_mod
            original = reg_mod.STATE_FILE
            reg_mod.STATE_FILE = state_file

            conn = ConnectionInfo(name="save-test", url="https://nifi.example.com/nifi-api", auth_method="basic")
            reg.add(conn)

            # Load into new registry instance
            reg2 = ConnectionRegistry()
            reg_mod.STATE_FILE = state_file
            reg2.load()

            reg_mod.STATE_FILE = original
            assert reg2.get("save-test") is not None
            assert reg2.get("save-test").url == "https://nifi.example.com/nifi-api"
        finally:
            os.unlink(state_file)
            os.environ.pop("NIFI_MCP_STATE_FILE", None)

    def test_load_filters_unknown_fields(self):
        """State file with unknown fields (from future versions) should load gracefully."""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            json.dump({
                "active": "test",
                "connections": [{
                    "name": "test",
                    "url": "https://nifi",
                    "auth_method": "none",
                    "unknown_future_field": "some-value",
                    "another_unknown": 123,
                }]
            }, f)
            state_file = f.name

        try:
            import gateway.nifi_registry as reg_mod
            original = reg_mod.STATE_FILE
            reg_mod.STATE_FILE = state_file
            reg = ConnectionRegistry()
            reg.load()
            reg_mod.STATE_FILE = original

            conn = reg.get("test")
            assert conn is not None
            assert conn.url == "https://nifi"
        finally:
            os.unlink(state_file)

    def test_load_empty_file_returns_empty_list(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            f.write("")
            state_file = f.name

        try:
            import gateway.nifi_registry as reg_mod
            original = reg_mod.STATE_FILE
            reg_mod.STATE_FILE = state_file
            reg = ConnectionRegistry()
            result = reg.load()
            reg_mod.STATE_FILE = original
            assert result == []
        finally:
            os.unlink(state_file)


class TestConnectionRegistryActiveManagement:
    def test_active_auto_set_on_first_add(self):
        reg = ConnectionRegistry()
        conn = ConnectionInfo(name="first", url="https://nifi")
        reg.add(conn)
        assert reg.active == "first"

    def test_active_not_overridden_on_second_add(self):
        reg = ConnectionRegistry()
        reg.add(ConnectionInfo(name="first", url="https://nifi"))
        reg.add(ConnectionInfo(name="second", url="https://nifi2"))
        assert reg.active == "first"

    def test_active_switches_to_next_on_remove(self):
        reg = ConnectionRegistry()
        reg.add(ConnectionInfo(name="a", url="https://a"))
        reg.add(ConnectionInfo(name="b", url="https://b"))
        reg._active = "a"
        reg.remove("a")
        assert reg.active == "b"

    def test_active_empty_when_last_removed(self):
        reg = ConnectionRegistry()
        reg.add(ConnectionInfo(name="only", url="https://nifi"))
        reg.remove("only")
        assert reg.active == ""

    def test_remove_nonexistent_returns_none(self):
        reg = ConnectionRegistry()
        result = reg.remove("ghost")
        assert result is None

    def test_get_nonexistent_returns_none(self):
        reg = ConnectionRegistry()
        assert reg.get("ghost") is None

    def test_list_all_empty(self):
        reg = ConnectionRegistry()
        assert reg.list_all() == []

    def test_list_all_returns_all(self):
        reg = ConnectionRegistry()
        reg.add(ConnectionInfo(name="a", url="https://a"))
        reg.add(ConnectionInfo(name="b", url="https://b"))
        names = [c.name for c in reg.list_all()]
        assert "a" in names
        assert "b" in names
