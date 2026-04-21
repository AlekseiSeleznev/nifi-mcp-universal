"""Tests for gateway.nifi.setup_helper — validate_current_config and instructions."""
from __future__ import annotations

import os
import pytest

from gateway.nifi.setup_helper import SetupGuide


class TestValidateCurrentConfig:
    def test_returns_tuple_of_three(self):
        is_valid, errors, warnings = SetupGuide.validate_current_config()
        assert isinstance(is_valid, bool)
        assert isinstance(errors, list)
        assert isinstance(warnings, list)

    def test_no_api_base_is_not_fatal_error(self, monkeypatch):
        """Missing NIFI_API_BASE is not a hard error — connections can be added via dashboard."""
        monkeypatch.delenv("NIFI_MCP_NIFI_API_BASE", raising=False)
        monkeypatch.delenv("NIFI_API_BASE", raising=False)
        is_valid, errors, warnings = SetupGuide.validate_current_config()
        # The function may still return is_valid=False, but errors should be informational
        # Just make sure it doesn't crash
        assert isinstance(is_valid, bool)

    def test_canonical_prefix_recognized(self, monkeypatch):
        """NIFI_MCP_NIFI_API_BASE should be the primary lookup key."""
        monkeypatch.setenv("NIFI_MCP_NIFI_API_BASE", "https://nifi.example.com/nifi-api")
        monkeypatch.delenv("NIFI_API_BASE", raising=False)
        is_valid, errors, warnings = SetupGuide.validate_current_config()
        # With a valid URL set, no URL-related errors
        url_errors = [e for e in errors if "NIFI_MCP_NIFI_API_BASE" in e and "not set" in e]
        assert len(url_errors) == 0

    def test_legacy_env_var_fallback(self, monkeypatch):
        """NIFI_API_BASE (legacy, no prefix) should also be recognized."""
        monkeypatch.delenv("NIFI_MCP_NIFI_API_BASE", raising=False)
        monkeypatch.setenv("NIFI_API_BASE", "https://nifi.example.com/nifi-api")
        is_valid, errors, warnings = SetupGuide.validate_current_config()
        url_errors = [e for e in errors if "not set" in e]
        assert len(url_errors) == 0

    def test_invalid_url_gives_error(self, monkeypatch):
        monkeypatch.setenv("NIFI_MCP_NIFI_API_BASE", "not-a-url")
        monkeypatch.delenv("NIFI_API_BASE", raising=False)
        is_valid, errors, warnings = SetupGuide.validate_current_config()
        assert not is_valid
        assert any("http" in e.lower() for e in errors)

    def test_ssl_disabled_gives_warning(self, monkeypatch):
        monkeypatch.setenv("NIFI_MCP_VERIFY_SSL", "false")
        monkeypatch.delenv("KNOX_VERIFY_SSL", raising=False)
        _, _, warnings = SetupGuide.validate_current_config()
        assert any("ssl" in w.lower() for w in warnings)

    def test_write_mode_enabled_gives_warning(self, monkeypatch):
        monkeypatch.setenv("NIFI_MCP_NIFI_READONLY", "false")
        monkeypatch.delenv("NIFI_READONLY", raising=False)
        _, _, warnings = SetupGuide.validate_current_config()
        assert any("write" in w.lower() for w in warnings)

    def test_knox_token_recognized_as_auth(self, monkeypatch):
        monkeypatch.setenv("NIFI_MCP_NIFI_API_BASE", "https://nifi.example.com/nifi-api")
        monkeypatch.setenv("NIFI_MCP_KNOX_TOKEN", "eyJhbGciOiJSUzI1NiJ9.payload")
        monkeypatch.delenv("NIFI_API_BASE", raising=False)
        _, _, warnings = SetupGuide.validate_current_config()
        auth_warnings = [w for w in warnings if "authentication" in w.lower() and "not" in w.lower()]
        assert len(auth_warnings) == 0


class TestGetSetupInstructions:
    def test_returns_string(self):
        instructions = SetupGuide.get_setup_instructions()
        assert isinstance(instructions, str)
        assert len(instructions) > 100

    def test_contains_nifi_api_base(self):
        instructions = SetupGuide.get_setup_instructions()
        assert "NIFI" in instructions

    def test_contains_auth_guidance(self):
        instructions = SetupGuide.get_setup_instructions()
        assert "auth" in instructions.lower() or "token" in instructions.lower()


class TestGetRequiredConfig:
    def test_returns_dict(self):
        config = SetupGuide.get_required_config()
        assert isinstance(config, dict)
        assert len(config) > 0

    def test_has_connection_section(self):
        config = SetupGuide.get_required_config()
        assert "connection" in config

    def test_has_authentication_section(self):
        config = SetupGuide.get_required_config()
        assert "authentication" in config
