"""Pydantic settings — environment variables with NIFI_MCP_ prefix."""

from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Gateway
    port: int = 8080
    log_level: str = "INFO"
    api_key: str = ""

    # Default NiFi connection (optional, auto-connect on start)
    nifi_api_base: str = ""
    nifi_readonly: bool = True
    verify_ssl: bool = True

    # Default auth
    nifi_client_p12: str = ""
    nifi_client_p12_password: str = ""
    knox_token: str = ""
    knox_cookie: str = ""
    knox_user: str = ""
    knox_password: str = ""
    knox_gateway_url: str = ""
    knox_passcode_token: str = ""

    # HTTP
    http_timeout: int = 30
    session_timeout: int = 28800  # 8 hours

    # State persistence
    state_file: str = "/data/nifi_state.json"

    model_config = {"env_prefix": "NIFI_MCP_", "env_file": ".env", "extra": "ignore"}


settings = Settings()
