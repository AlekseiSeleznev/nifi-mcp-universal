"""Multi-NiFi connection registry with JSON persistence."""

from __future__ import annotations

import json
import logging
import os
import tempfile
import threading
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

from gateway.config import settings

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
        if not settings.persist_secrets_in_state:
            for k in _SENSITIVE_FIELDS:
                d[k] = ""
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
        self._lock = threading.RLock()

    @property
    def active(self) -> str:
        with self._lock:
            return self._active

    @active.setter
    def active(self, name: str) -> None:
        with self._lock:
            self._active = name

    def add(self, conn: ConnectionInfo) -> None:
        with self._lock:
            self._connections[conn.name] = conn
            if not self._active:
                self._active = conn.name
        self.save()

    def remove(self, name: str) -> ConnectionInfo | None:
        with self._lock:
            conn = self._connections.pop(name, None)
            if conn and self._active == name:
                self._active = next(iter(self._connections), "")
        if conn:
            self.save()
        return conn

    def get(self, name: str) -> ConnectionInfo | None:
        with self._lock:
            return self._connections.get(name)

    def list_all(self) -> list[ConnectionInfo]:
        with self._lock:
            return list(self._connections.values())

    def save(self) -> None:
        with self._lock:
            state = {
                "active": self._active,
                "connections": [c.to_dict() for c in self._connections.values()],
            }
        try:
            path = Path(STATE_FILE)
            path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp_path = tempfile.mkstemp(dir=str(path.parent), prefix=path.name, suffix=".tmp")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(state, f, indent=2, ensure_ascii=False)
                os.replace(tmp_path, path)
            except Exception:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                raise
        except Exception:
            log.exception("Failed to save state to %s", STATE_FILE)

    def load(self) -> list[dict]:
        try:
            path = Path(STATE_FILE)
            if path.exists():
                state = json.loads(path.read_text())
                conns = state.get("connections", [])
                with self._lock:
                    self._active = state.get("active", "")
                    for d in conns:
                        # Filter out unknown fields gracefully
                        known = {f.name for f in fields(ConnectionInfo)}
                        filtered = {k: v for k, v in d.items() if k in known}
                        self._connections[filtered["name"]] = ConnectionInfo(**filtered)
                log.info("Loaded %d connections from state", len(conns))
                return conns
        except Exception:
            log.exception("Failed to load state from %s", STATE_FILE)
        return []


registry = ConnectionRegistry()
