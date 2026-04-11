"""Tests for gateway.config — Settings defaults and env-var overrides."""
from __future__ import annotations

import os
import importlib
import pytest


def _reload_settings(env: dict):
    """Re-import Settings with specific env vars set."""
    import gateway.config as cfg_mod
    with pytest.MonkeyPatch().context() as mp:
        for k, v in env.items():
            mp.setenv(k, v)
        # Re-instantiate (don't reload module to avoid side-effects)
        from gateway.config import Settings
        return Settings()


class TestSettingsDefaults:
    def test_port_default(self):
        from gateway.config import Settings
        s = Settings()
        assert s.port == 8085

    def test_log_level_default(self):
        from gateway.config import Settings
        s = Settings()
        assert s.log_level == "INFO"

    def test_api_key_empty_by_default(self):
        from gateway.config import Settings
        s = Settings()
        assert s.api_key == ""

    def test_nifi_api_base_empty_by_default(self):
        from gateway.config import Settings
        s = Settings()
        assert s.nifi_api_base == ""

    def test_nifi_readonly_default_true(self):
        from gateway.config import Settings
        s = Settings()
        assert s.nifi_readonly is True

    def test_verify_ssl_default_true(self):
        from gateway.config import Settings
        s = Settings()
        assert s.verify_ssl is True

    def test_http_timeout_default(self):
        from gateway.config import Settings
        s = Settings()
        assert s.http_timeout == 30

    def test_session_timeout_default(self):
        from gateway.config import Settings
        s = Settings()
        assert s.session_timeout == 28800  # 8 hours

    def test_state_file_default(self):
        from gateway.config import Settings
        s = Settings()
        assert s.state_file == "/data/nifi_state.json"

    def test_auth_fields_empty_by_default(self):
        from gateway.config import Settings
        s = Settings()
        assert s.nifi_client_p12 == ""
        assert s.nifi_client_p12_password == ""
        assert s.knox_token == ""
        assert s.knox_cookie == ""
        assert s.knox_user == ""
        assert s.knox_password == ""
        assert s.knox_gateway_url == ""
        assert s.knox_passcode_token == ""


class TestSettingsEnvVarOverrides:
    def test_port_override(self, monkeypatch):
        monkeypatch.setenv("NIFI_MCP_PORT", "9999")
        from gateway.config import Settings
        s = Settings()
        assert s.port == 9999

    def test_api_key_override(self, monkeypatch):
        monkeypatch.setenv("NIFI_MCP_API_KEY", "secret123")
        from gateway.config import Settings
        s = Settings()
        assert s.api_key == "secret123"

    def test_nifi_api_base_override(self, monkeypatch):
        monkeypatch.setenv("NIFI_MCP_NIFI_API_BASE", "https://mycluster/nifi-api")
        from gateway.config import Settings
        s = Settings()
        assert s.nifi_api_base == "https://mycluster/nifi-api"

    def test_nifi_readonly_false(self, monkeypatch):
        monkeypatch.setenv("NIFI_MCP_NIFI_READONLY", "false")
        from gateway.config import Settings
        s = Settings()
        assert s.nifi_readonly is False

    def test_verify_ssl_false(self, monkeypatch):
        monkeypatch.setenv("NIFI_MCP_VERIFY_SSL", "false")
        from gateway.config import Settings
        s = Settings()
        assert s.verify_ssl is False

    def test_knox_token_override(self, monkeypatch):
        monkeypatch.setenv("NIFI_MCP_KNOX_TOKEN", "jwt.token.here")
        from gateway.config import Settings
        s = Settings()
        assert s.knox_token == "jwt.token.here"

    def test_http_timeout_override(self, monkeypatch):
        monkeypatch.setenv("NIFI_MCP_HTTP_TIMEOUT", "60")
        from gateway.config import Settings
        s = Settings()
        assert s.http_timeout == 60

    def test_env_prefix_is_nifi_mcp(self, monkeypatch):
        """Vars without the prefix must NOT be picked up."""
        monkeypatch.setenv("PORT", "1234")
        from gateway.config import Settings
        s = Settings()
        assert s.port != 1234

    def test_extra_env_vars_ignored(self, monkeypatch):
        """Unknown env vars with the prefix must not raise."""
        monkeypatch.setenv("NIFI_MCP_UNKNOWN_KEY", "value")
        from gateway.config import Settings
        s = Settings()  # should not raise
        assert s is not None
