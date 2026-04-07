"""Multi-NiFi client manager with per-session routing."""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field

from gateway.config import settings
from gateway.nifi_registry import ConnectionInfo, registry
from gateway.nifi.client import NiFiClient
from gateway.nifi.auth import KnoxAuthFactory

log = logging.getLogger(__name__)

CERTS_DIR = "/data/certs"


@dataclass
class SessionState:
    conn_name: str
    last_access: float = field(default_factory=time.time)


def _normalize_nifi_url(url: str) -> str:
    """Normalize NiFi URL to always end with /nifi-api.

    Users typically enter:
      https://host:port
      https://host:port/nifi
      https://host:port/nifi-api
    All should resolve to https://host:port/nifi-api
    """
    url = url.rstrip("/")
    if url.endswith("/nifi-api"):
        return url
    if url.endswith("/nifi"):
        return url[:-5] + "/nifi-api"
    return url + "/nifi-api"


def _build_client(conn: ConnectionInfo) -> NiFiClient:
    """Build a NiFiClient from ConnectionInfo."""
    cert_path_abs = ""
    cert_key_abs = ""
    if conn.cert_path:
        cert_path_abs = os.path.join(CERTS_DIR, conn.cert_path)
    if conn.cert_key_path:
        cert_key_abs = os.path.join(CERTS_DIR, conn.cert_key_path)

    p12_path = cert_path_abs if conn.auth_method == "certificate_p12" else None
    p12_password = conn.cert_password if conn.auth_method == "certificate_p12" else None
    client_cert = cert_path_abs if conn.auth_method == "certificate_pem" else None
    client_key = cert_key_abs if conn.auth_method == "certificate_pem" else None

    verify: bool | str = conn.verify_ssl

    auth = KnoxAuthFactory(
        gateway_url=conn.knox_gateway_url,
        token=conn.knox_token if conn.auth_method == "knox_token" else None,
        cookie=conn.knox_cookie if conn.auth_method == "knox_cookie" else None,
        user=conn.knox_user if conn.auth_method == "basic" else None,
        password=conn.knox_password if conn.auth_method == "basic" else None,
        token_endpoint=None,
        passcode_token=conn.knox_passcode if conn.auth_method == "knox_passcode" else None,
        verify=verify,
        p12_path=p12_path,
        p12_password=p12_password,
        client_cert=client_cert,
        client_key=client_key,
    )
    session = auth.build_session()
    return NiFiClient(
        _normalize_nifi_url(conn.url),
        session,
        timeout_seconds=settings.http_timeout,
    )


class NiFiClientManager:
    def __init__(self) -> None:
        self._clients: dict[str, NiFiClient] = {}
        self._sessions: dict[str, SessionState] = {}

    # --- Client lifecycle ---

    def connect(self, conn: ConnectionInfo) -> None:
        """Build NiFi client and validate connection."""
        if conn.name in self._clients:
            log.info("Client %s already exists, skipping", conn.name)
            return

        log.info("Building client for %s (%s)", conn.name, conn.url)
        client = _build_client(conn)

        # Validate by fetching version
        try:
            info = client.get_version_info()
            version = info.get("about", {}).get("version", "unknown")
            conn.nifi_version = version
            log.info("Connected to %s — NiFi %s", conn.name, version)
        except Exception as e:
            log.warning("Cannot verify %s: %s", conn.name, e)
            conn.nifi_version = "unknown"

        self._clients[conn.name] = client
        conn.connected = True

    def disconnect(self, name: str) -> None:
        client = self._clients.pop(name, None)
        if client:
            try:
                client.session.close()
            except Exception:
                pass
            conn = registry.get(name)
            if conn:
                conn.connected = False
            log.info("Client %s disconnected", name)

        to_remove = [sid for sid, s in self._sessions.items() if s.conn_name == name]
        for sid in to_remove:
            del self._sessions[sid]

    def close_all(self) -> None:
        for name in list(self._clients):
            self.disconnect(name)

    # --- Session routing ---

    def get_active_name(self, session_id: str | None = None) -> str:
        if session_id and session_id in self._sessions:
            state = self._sessions[session_id]
            state.last_access = time.time()
            return state.conn_name
        return registry.active

    def switch(self, conn_name: str, session_id: str | None = None) -> None:
        if conn_name not in self._clients:
            raise ValueError(f"NiFi '{conn_name}' is not connected")
        if session_id:
            self._sessions[session_id] = SessionState(conn_name=conn_name)
        else:
            registry.active = conn_name

    def get_client(self, session_id: str | None = None) -> NiFiClient:
        name = self.get_active_name(session_id)
        if not name:
            raise RuntimeError("No active NiFi connection. Use connect_nifi first.")
        client = self._clients.get(name)
        if not client:
            raise RuntimeError(f"NiFi '{name}' is not connected")
        return client

    def get_connection_info(self, session_id: str | None = None) -> ConnectionInfo | None:
        name = self.get_active_name(session_id)
        return registry.get(name) if name else None

    # --- Maintenance ---

    def cleanup_sessions(self) -> int:
        now = time.time()
        expired = [
            sid for sid, s in self._sessions.items()
            if now - s.last_access > settings.session_timeout
        ]
        for sid in expired:
            del self._sessions[sid]
        return len(expired)

    # --- Status ---

    def get_status(self) -> dict:
        clients_status = {}
        for name, client in self._clients.items():
            conn = registry.get(name)
            clients_status[name] = {
                "url": conn.url if conn else "?",
                "auth_method": conn.auth_method if conn else "?",
                "readonly": conn.readonly if conn else True,
                "nifi_version": conn.nifi_version if conn else "",
            }
        return {
            "connections": clients_status,
            "sessions": len(self._sessions),
            "active_default": registry.active,
        }


client_manager = NiFiClientManager()
