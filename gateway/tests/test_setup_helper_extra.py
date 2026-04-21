from __future__ import annotations

import pytest

from gateway.nifi.setup_helper import SetupGuide, get_jdbc_driver_troubleshooting, validate_config_or_exit


class TestSetupGuideOutput:
    def test_check_and_report_valid_clean_config(self, monkeypatch, capsys):
        monkeypatch.setenv("NIFI_MCP_NIFI_API_BASE", "https://nifi.example.com/nifi-api")
        monkeypatch.setenv("NIFI_MCP_KNOX_TOKEN", "token")
        monkeypatch.setenv("NIFI_MCP_VERIFY_SSL", "true")
        monkeypatch.setenv("NIFI_MCP_NIFI_READONLY", "true")

        assert SetupGuide.check_and_report() is True
        out = capsys.readouterr().out
        assert "Configuration is valid!" in out
        assert "Authentication" in out

    def test_check_and_report_valid_with_warnings(self, monkeypatch, capsys):
        monkeypatch.setenv("NIFI_MCP_NIFI_API_BASE", "https://nifi.example.com/nifi-api")
        monkeypatch.delenv("NIFI_MCP_KNOX_TOKEN", raising=False)
        monkeypatch.setenv("NIFI_MCP_VERIFY_SSL", "false")

        assert SetupGuide.check_and_report() is True
        out = capsys.readouterr().out
        assert "valid (with warnings)" in out

    def test_check_and_report_invalid_config(self, monkeypatch, capsys):
        monkeypatch.delenv("NIFI_MCP_NIFI_API_BASE", raising=False)
        monkeypatch.delenv("NIFI_API_BASE", raising=False)

        assert SetupGuide.check_and_report() is False
        out = capsys.readouterr().out
        assert "Configuration is INVALID" in out
        assert "get_setup_instructions" in out

    @pytest.mark.parametrize(
        ("env_name", "env_value", "expected"),
        [
            ("KNOX_TOKEN", "token", "Knox JWT Token"),
            ("KNOX_COOKIE", "cookie", "Knox Cookie"),
            ("KNOX_USER", "admin", "Basic Auth"),
        ],
    )
    def test_check_and_report_prints_each_auth_mode(self, monkeypatch, capsys, env_name, env_value, expected):
        monkeypatch.setenv("NIFI_MCP_NIFI_API_BASE", "https://nifi.example.com/nifi-api")
        monkeypatch.delenv("NIFI_MCP_KNOX_TOKEN", raising=False)
        monkeypatch.delenv("KNOX_TOKEN", raising=False)
        monkeypatch.delenv("KNOX_COOKIE", raising=False)
        monkeypatch.delenv("KNOX_USER", raising=False)
        monkeypatch.delenv("KNOX_PASSWORD", raising=False)
        if env_name == "KNOX_USER":
            monkeypatch.setenv("KNOX_PASSWORD", "secret")
        monkeypatch.setenv(env_name, env_value)

        SetupGuide.check_and_report()

        out = capsys.readouterr().out
        assert expected in out

    def test_validate_config_or_exit_exits_when_invalid(self, monkeypatch, capsys):
        monkeypatch.delenv("NIFI_MCP_NIFI_API_BASE", raising=False)
        monkeypatch.delenv("NIFI_API_BASE", raising=False)

        with pytest.raises(SystemExit) as exc:
            validate_config_or_exit()

        assert exc.value.code == 1
        out = capsys.readouterr().out
        assert "NiFi MCP Server Not Configured" in out

    def test_validate_config_or_exit_prints_warnings_without_exit(self, monkeypatch, capsys):
        monkeypatch.setenv("NIFI_MCP_NIFI_API_BASE", "https://nifi.example.com/nifi-api")
        monkeypatch.setenv("NIFI_MCP_VERIFY_SSL", "false")

        validate_config_or_exit()

        out = capsys.readouterr().out
        assert "Configuration warnings detected" in out

    def test_validate_config_or_exit_clean_valid_config_prints_nothing(self, monkeypatch, capsys):
        monkeypatch.setenv("NIFI_MCP_NIFI_API_BASE", "https://nifi.example.com/nifi-api")
        monkeypatch.setenv("NIFI_MCP_KNOX_TOKEN", "token")
        monkeypatch.setenv("NIFI_MCP_VERIFY_SSL", "true")
        monkeypatch.setenv("NIFI_MCP_NIFI_READONLY", "true")

        validate_config_or_exit()

        assert "Configuration warnings detected" not in capsys.readouterr().out

    def test_missing_config_and_jdbc_troubleshooting_messages_are_populated(self):
        missing = SetupGuide.get_missing_config_message()
        troubleshooting = get_jdbc_driver_troubleshooting()

        assert "README.md" in missing
        assert "JDBC Driver Requirement" in troubleshooting
        assert "CaptureChangeMySQL" in troubleshooting
