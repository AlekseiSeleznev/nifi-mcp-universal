"""Multi-NiFi connection registry with JSON persistence."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path

log = logging.getLogger(__name__)

STATE_FILE = os.environ.get("NIFI_MCP_STATE_FILE", "/data/nifi_state.json")

_SENSITIVE_FIELDS = {"cert_password", "knox_password", "knox_token", "knox_cookie", "knox_passcode"}


@dataclass
class ConnectionInfo:
    name: str
    url: str
    auth_method: str = "none"  # certificate_p12, certificate_pem, knox_token, knox_cookie, knox_passcode, basic, none
    cert_path: str = ""        # relative inside /data/certs/, e.g. "myconn/keystore.p12"
    cert_password: str = ""
    cert_key_path: str = ""    # PEM key file (for certificate_pem)
    knox_token: str = ""
    knox_cookie: str = ""
    knox_passcode: str = ""
    knox_user: str = ""
    knox_password: str = ""
    knox_gateway_url: str = ""
    verify_ssl: bool = True
    readonly: bool = True
    # Runtime (not persisted)
    connected: bool = False
    nifi_version: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("connected", None)
        d.pop("nifi_version", None)
        return d

    def to_safe_dict(self) -> dict:
        """Return dict with sensitive fields masked (for API responses)."""
        d = asdict(self)
        for k in _SENSITIVE_FIELDS:
            if d.get(k):
                d[k] = "***"
        d["connected"] = self.connected
        d["nifi_version"] = self.nifi_version
        return d


class ConnectionRegistry:
    def __init__(self) -> None:
        self._connections: dict[str, ConnectionInfo] = {}
        self._active: str = ""

    @property
    def active(self) -> str:
        return self._active

    @active.setter
    def active(self, name: str) -> None:
        self._active = name

    def add(self, conn: ConnectionInfo) -> None:
        self._connections[conn.name] = conn
        if not self._active:
            self._active = conn.name
        self.save()

    def remove(self, name: str) -> ConnectionInfo | None:
        conn = self._connections.pop(name, None)
        if conn and self._active == name:
            self._active = next(iter(self._connections), "")
        if conn:
            self.save()
        return conn

    def get(self, name: str) -> ConnectionInfo | None:
        return self._connections.get(name)

    def list_all(self) -> list[ConnectionInfo]:
        return list(self._connections.values())

    def save(self) -> None:
        state = {
            "active": self._active,
            "connections": [c.to_dict() for c in self._connections.values()],
        }
        try:
            path = Path(STATE_FILE)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(state, indent=2, ensure_ascii=False))
        except Exception:
            log.exception("Failed to save state to %s", STATE_FILE)

    def load(self) -> list[dict]:
        try:
            path = Path(STATE_FILE)
            if path.exists():
                state = json.loads(path.read_text())
                self._active = state.get("active", "")
                conns = state.get("connections", [])
                for d in conns:
                    # Filter out unknown fields gracefully
                    known = {f.name for f in ConnectionInfo.__dataclass_fields__.values()}
                    filtered = {k: v for k, v in d.items() if k in known}
                    self._connections[filtered["name"]] = ConnectionInfo(**filtered)
                log.info("Loaded %d connections from state", len(conns))
                return conns
        except Exception:
            log.exception("Failed to load state from %s", STATE_FILE)
        return []


registry = ConnectionRegistry()
