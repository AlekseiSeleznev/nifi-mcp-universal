# CLAUDE.md — Claude Code Deployment Guide

This document tells Claude Code (the agent) exactly how to install and deploy
**nifi-mcp-universal** on a fresh machine, with no errors and survival across reboots.

## What This Project Is

**nifi-mcp-universal** is an MCP (Model Context Protocol) gateway for Apache NiFi.
It exposes a single `http://localhost:8085/mcp` endpoint that AI assistants
(Claude Code, Cursor) use to manage and inspect one or more NiFi instances
simultaneously — querying flows, managing processors, controller services,
parameter contexts, and connections via 66 MCP tools.

Key properties:

- **Multi-NiFi**: one gateway manages many NiFi instances; each AI session works
  with its own active connection (per-session routing).
- **Read-only by default**: all write-operations require an explicit `readonly=false`
  when connecting.
- **No NiFi platform on host required**: the gateway is a self-contained Docker
  container; NiFi runs elsewhere (cloud, VM, bare-metal).
- **7 auth methods**: Certificate P12/PEM, Knox JWT/Cookie/Passcode, Basic Auth, No Auth.
- **NiFi 1.x and 2.x** with auto-version detection.

---

## Architecture

```
AI Client (Claude Code / Cursor)
    │  HTTP :8085/mcp (Streamable HTTP)
    ▼
┌──────────────────────────────────────────────┐
│  nifi-mcp-universal  (Python gateway)        │
│  ├─ MCP tool dispatch  (66 tools)            │
│  ├─ Per-session NiFi connection routing      │
│  ├─ Multi-NiFi connection registry           │
│  ├─ Certificate store  /data/certs/          │
│  ├─ State persistence  /data/nifi_state.json │
│  └─ Dashboard  :8085/dashboard               │
└──────────────────────────────────────────────┘
         │  HTTPS/HTTP (configurable per conn)
         ▼
   Apache NiFi 1.x / 2.x
   (anywhere — cloud, VM, bare-metal, localhost)
```

The gateway is a **single Docker container** (`nifi-mcp-gateway`).
There is no local NiFi container — this gateway connects to existing NiFi instances
over the network.

---

## Installation Decision Tree

### What does the user need?

1. **Just the MCP gateway** → `./setup.sh` — works on Linux, macOS, Windows.
2. **Post-reboot auto-start** →
   - Linux: `setup.sh` installs a systemd service automatically.
   - Windows: `setup.sh` runs `tools/ensure-docker-autostart-windows.ps1` to add a
     registry `Run` key for Docker Desktop (idempotent, survives user-disabling the checkbox).
   - macOS: Docker Desktop "Start Docker Desktop when you log in" (default ON).
3. **Secure NiFi (mTLS / P12)** → upload certificate via Dashboard after setup.
4. **Knox / CDP NiFi** → provide Knox token, cookie, or passcode when connecting.
5. **Protected MCP endpoint** → set `NIFI_MCP_API_KEY` in `.env`.

There are no optional build-time features — setup is the same for all use cases.
Auth method and NiFi URL are configured at runtime via the Dashboard or MCP tools.

---

## Linux Installation (Ubuntu 22.04+ / Debian 12+)

### Required prerequisites (Claude must check or install these first)

```bash
# 1. git
sudo apt update && sudo apt install -y git

# 2. Docker Engine + Docker Compose v2
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
# IMPORTANT: User must log out and back in, OR run:
newgrp docker
# Verify:
docker compose version   # must show v2.x
```

### Install steps

```bash
git clone https://github.com/AlekseiSeleznev/nifi-mcp-universal.git
cd nifi-mcp-universal
./setup.sh
```

### What setup.sh does on Linux (line by line)

1. **cd to repo root** — `cd "$(dirname "$0")"` — works regardless of where it's called from.

2. **Checks prerequisites**:
   - `docker` binary present → fail with install link if not.
   - Docker daemon running (`docker info`) → fail with `sudo systemctl start docker` hint.
   - Docker Compose v2 (`docker compose version`) → fail if only v1 is present.
   - Claude CLI (`claude`) → warn if absent; MCP won't be auto-registered (non-fatal).

3. **Detects OS** — `uname -s` → `linux`. No `docker-compose.override.yml` is created
   on Linux because `network_mode: host` in `docker-compose.yml` works natively.

4. **Creates `.env`** — copies `.env.example` to `.env` if it does not exist.
   If `.env` already exists it is left unchanged (idempotent).
   Sets default port `NIFI_MCP_PORT=8085`.

5. **Checks port availability** — uses `ss -tlnp` (or `lsof` fallback) to see if
   port 8085 (or custom port from `.env`) is occupied. Prompts to continue or abort.

6. **Builds and starts the container**:
   ```
   docker compose up -d --build --remove-orphans
   ```
   Uses `docker-compose.yml` which sets `network_mode: host` and `restart: always`.

7. **Health check loop** — polls `http://localhost:${PORT}/health` every second for
   up to 30 seconds. Falls back to `docker inspect --format='{{.State.Health.Status}}'`
   if curl is absent. Exits with error if unhealthy after 30s.

8. **Installs systemd service** (Linux-only, requires `systemctl`):
   - Service name: `nifi-mcp-universal`
   - Unit file: `/etc/systemd/system/nifi-mcp-universal.service`
   - `ExecStart`: `docker compose -f /abs/path/docker-compose.yml up -d --build`
   - `ExecStop`: `docker compose -f /abs/path/docker-compose.yml down`
   - `Type=oneshot`, `RemainAfterExit=yes`
   - `After=docker.service network-online.target`
   - `sudo systemctl daemon-reload && sudo systemctl enable nifi-mcp-universal.service`
   - Uses `--build` on start to recover from corrupted images after hard shutdown.
   - If `sudo` is not available, prints the unit file and manual commands as a warning.
   - Idempotent: skips if the file already exists with the correct path.

9. **Registers MCP in Claude Code**:
   ```bash
   claude mcp remove nifi-universal -s user 2>/dev/null || true  # idempotent
   claude mcp add --transport http -s user nifi-universal http://localhost:${PORT}/mcp
   ```
   Scope `user` means it works in all Claude Code sessions without re-registering.
   Verifies with `claude mcp list | grep nifi-universal`.

10. **Prints summary** — Dashboard URL, Health URL, MCP URL, example `connect_nifi` call.

### Verification

```bash
curl http://localhost:8085/health
# Expected: {"status": "ok", "connections": [], "sessions": 0}

# Open dashboard
xdg-open http://localhost:8085/dashboard
```

### Post-reboot survival on Linux

| Component | Mechanism |
|-----------|-----------|
| Docker daemon | systemd `docker.service` (auto-enabled by `get.docker.com` install) |
| Gateway container | `restart: always` in docker-compose.yml |
| systemd service | `nifi-mcp-universal.service` enabled by `setup.sh` — `docker compose up -d --build` |
| MCP registration | `~/.claude/.config.json` (user scope, persistent) |
| NiFi connections | `/data/nifi_state.json` in Docker volume `gw-data` (persistent) |
| Certificates | Docker volume `gw-data` at `/data/certs/` (persistent) |

**To verify after reboot:**
```bash
docker ps              # should show nifi-mcp-gateway
systemctl status nifi-mcp-universal
curl http://localhost:8085/health
```

**Note**: The systemd service uses `--build` which rebuilds the image on every boot
start. This adds ~10-15s but protects against corrupted layer caches after unclean
shutdown. The container itself also restarts via `restart: always` before the service
fires, so there is no gap in availability.

---

## Windows 11 Installation (Docker Desktop + Git Bash)

### Required prerequisites (Claude must verify)

1. **Docker Desktop 4.25+** with WSL2 backend
   - Download: https://www.docker.com/products/docker-desktop/
   - Enable: Settings → General → "Use WSL 2 based engine"
   - Enable: Settings → General → "Start Docker Desktop when you log in" (default ON)
2. **Git for Windows** (provides Git Bash + git command)
   - Download: https://gitforwindows.org/
   - Alternative: WSL2 with Ubuntu

### Install steps (in Git Bash or WSL2)

```bash
git clone https://github.com/AlekseiSeleznev/nifi-mcp-universal.git
cd nifi-mcp-universal
./setup.sh
```

### What setup.sh does on Windows

1. **Detects OS** — `uname -s` matches `MINGW*|MSYS*|CYGWIN*` → `OS=windows`.

2. **Creates `docker-compose.override.yml`** (only if it doesn't exist):
   ```yaml
   services:
     gateway:
       network_mode: bridge
       ports:
         - "${NIFI_MCP_PORT:-8085}:${NIFI_MCP_PORT:-8085}"
       extra_hosts:
         - "host.docker.internal:host-gateway"
   ```
   This replaces `network_mode: host` (unsupported on Docker Desktop) with bridge
   networking and explicit port mapping. `host.docker.internal` resolves to the
   Windows host — use this if NiFi runs on the same machine.

3. **Configures Docker Desktop autostart** (Windows-only):
   - Runs `tools/ensure-docker-autostart-windows.ps1` via `powershell -ExecutionPolicy Bypass`.
   - The script adds/updates `HKCU:\Software\Microsoft\Windows\CurrentVersion\Run`
     key `Docker Desktop` pointing to the Docker Desktop executable.
   - If Docker daemon is not running, it optionally starts Docker Desktop immediately.
   - Idempotent: re-running is safe.

4. Steps 3–9 are otherwise identical to Linux (create `.env`, check port, build,
   health check, register MCP). Systemd step (step 8) is skipped on Windows.

### Post-reboot survival on Windows

| Component | Mechanism |
|-----------|-----------|
| Docker Desktop | Registry autostart key set by `tools/ensure-docker-autostart-windows.ps1` during setup |
| Gateway container | `restart: always` — starts automatically when Docker Desktop starts |
| MCP registration | `~/.claude/.config.json` or `%USERPROFILE%\.claude\.config.json` (persistent) |
| NiFi connections | Docker volume `gw-data` → `nifi_state.json` (persistent) |
| Certificates | Docker volume `gw-data` → `/data/certs/` (persistent) |

There is no Windows Scheduled Task needed for this project (unlike onec-mcp-universal)
because there is no host-side export service — the gateway runs entirely in Docker.
Docker Desktop autostart is ensured via a registry `Run` key configured at install time.

### Verification after reboot (Windows PowerShell)

```powershell
docker ps
# Should show nifi-mcp-gateway running

# Check the port
Test-NetConnection localhost -Port 8085

# Or curl in Git Bash:
curl http://localhost:8085/health
```

### Common Windows issues

| Problem | Solution |
|---------|----------|
| `git: command not found` | Install Git for Windows |
| `docker: command not found` | Install Docker Desktop |
| Docker daemon not running | Start Docker Desktop from taskbar |
| Port 8085 occupied | Change `NIFI_MCP_PORT=8086` in `.env`, re-run `./setup.sh` |
| `host.docker.internal` not resolved | Update Docker Desktop to 4.25+ |
| Container won't start after reboot | Re-run `powershell -ExecutionPolicy Bypass -File tools\ensure-docker-autostart-windows.ps1` or enable manually: Docker Desktop → Settings → General → "Start Docker Desktop when you log in" |

---

## How Claude Code Should Install This

When user says "install nifi-mcp-universal from GitHub":

1. **Check git** — if not installed, instruct user.
2. **Check docker** — if not installed:
   - Linux: `curl -fsSL https://get.docker.com | sh && sudo usermod -aG docker $USER`
   - Windows: install Docker Desktop from docker.com
3. **Check docker daemon running** — if not: `sudo systemctl start docker` (Linux)
   or start Docker Desktop (Windows).
4. **Clone the repo**:
   ```bash
   git clone https://github.com/AlekseiSeleznev/nifi-mcp-universal.git
   cd nifi-mcp-universal
   ```
5. **Run setup.sh**:
   ```bash
   ./setup.sh
   ```
6. **Verify health**:
   ```bash
   curl http://localhost:8085/health
   ```
7. **Tell the user**:
   - Dashboard: `http://localhost:8085/dashboard`
   - Restart Claude Code so the MCP server is loaded
   - Run `/mcp` in Claude Code to verify `nifi-universal` appears
   - Add first NiFi connection via Dashboard or with `connect_nifi` tool

---

## Project Structure

```
├── gateway/                        # Python MCP gateway (Docker container)
│   ├── gateway/
│   │   ├── __main__.py             # Entry point (uvicorn)
│   │   ├── config.py               # Settings (pydantic-settings, NIFI_MCP_ prefix)
│   │   ├── server.py               # Starlette ASGI: /health, /mcp, /dashboard, /api/*
│   │   ├── mcp_server.py           # MCP tool dispatch
│   │   ├── nifi_registry.py        # Connection registry (JSON persistence)
│   │   ├── nifi_client_manager.py  # Multi-NiFi client manager + per-session routing
│   │   ├── web_ui.py               # Dashboard HTML/CSS/JS (bilingual RU/EN)
│   │   └── nifi/                   # NiFi REST client + auth
│   │       ├── client.py           # NiFi REST API wrappers (GET/PUT/POST/DELETE)
│   │       ├── auth.py             # KnoxAuthFactory (7 auth methods)
│   │       ├── flow_builder.py     # Flow pattern helpers
│   │       └── best_practices.py   # Best-practices guide
│   │   └── tools/
│   │       ├── admin.py            # connect/disconnect/switch/list/status/test
│   │       ├── read_tools.py       # 25 read-only MCP tools
│   │       └── write_tools.py      # 35 write MCP tools
│   ├── tests/                      # 330 pytest tests (no real NiFi required)
│   ├── Dockerfile
│   └── requirements.txt
├── tools/
│   └── ensure-docker-autostart-windows.ps1  # Adds Docker Desktop Run key in HKCU registry
├── docker-compose.yml              # Main (Linux, network_mode: host)
├── docker-compose.windows.yml      # Windows/macOS reference override
├── setup.sh                        # One-command setup (idempotent)
├── .env.example                    # Configuration template
└── README.md                       # User-facing documentation (RU + EN)
```

---

## Key Configuration (.env)

All variables use the `NIFI_MCP_` prefix (pydantic-settings auto-reads them).

```bash
# ── Gateway ────────────────────────────────────────
NIFI_MCP_PORT=8085            # Gateway listen port (default 8085)
NIFI_MCP_LOG_LEVEL=INFO       # DEBUG / INFO / WARNING / ERROR

# Optional: protect the /mcp endpoint with a Bearer token
# NIFI_MCP_API_KEY=your-secret-token

# ── Default NiFi connection (optional auto-connect on start) ──
# If set, gateway connects to this NiFi on first start when no saved state exists
# NIFI_MCP_NIFI_API_BASE=https://nifi.example.com/nifi-api
# NIFI_MCP_NIFI_READONLY=true    # true = read-only (safe default)
# NIFI_MCP_VERIFY_SSL=true       # false to skip cert check (dev only)

# ── Auth for the default connection ────────────────
# Certificate P12:
# NIFI_MCP_NIFI_CLIENT_P12=/data/certs/default/keystore.p12
# NIFI_MCP_NIFI_CLIENT_P12_PASSWORD=changeit

# Knox JWT token:
# NIFI_MCP_KNOX_TOKEN=eyJ...

# Knox Cookie:
# NIFI_MCP_KNOX_COOKIE=hadoop-jwt=eyJ...

# Knox Passcode:
# NIFI_MCP_KNOX_PASSCODE_TOKEN=your-passcode
# NIFI_MCP_KNOX_GATEWAY_URL=https://knox.example.com:8443/gateway

# Basic auth (via Knox token endpoint):
# NIFI_MCP_KNOX_USER=admin
# NIFI_MCP_KNOX_PASSWORD=admin
# NIFI_MCP_KNOX_GATEWAY_URL=https://knox.example.com:8443/gateway

# ── HTTP ──────────────────────────────────────────
NIFI_MCP_HTTP_TIMEOUT=30      # NiFi request timeout in seconds
NIFI_MCP_SESSION_TIMEOUT=28800 # Idle session cleanup (8 hours)
```

The `state_file` variable (`NIFI_MCP_STATE_FILE`) defaults to `/data/nifi_state.json`
inside the container. Persisted in Docker volume `gw-data`. Override for host-side testing.

---

## Running Tests

Tests are in `gateway/tests/` and run without Docker or a real NiFi instance.
All HTTP calls to NiFi are mocked.

```bash
cd gateway
pip install -r requirements.txt pytest pytest-asyncio
python3 -m pytest tests/ -q
# Expected: 330 passed
```

Run a specific module:

```bash
python3 -m pytest tests/test_nifi_auth.py -v
```

### Test coverage by file

| File | What it tests |
|------|--------------|
| `test_config.py` | Settings defaults, env-var overrides, `NIFI_MCP_` prefix |
| `test_nifi_registry.py` | `ConnectionInfo`, `ConnectionRegistry` (add/remove/get/save/load) |
| `test_nifi_registry_extra.py` | Persistence, active management, unknown field filtering |
| `test_nifi_client_manager.py` | URL normalization, connect/disconnect, session routing, cleanup |
| `test_session_cleanup.py` | Session cleanup, last-access updates, status counts |
| `test_nifi_client.py` | NiFiClient REST wrappers, version detection |
| `test_nifi_auth.py` | `KnoxAuthFactory` — all 7 auth methods |
| `test_tools_admin.py` | `connect_nifi`, `disconnect_nifi`, `switch_nifi`, list/status/test |
| `test_tools_read.py` | 25 read-only MCP tools, credential redaction, error handling |
| `test_tools_write.py` | 35 write MCP tools, read-only guard, tool dispatch |
| `test_mcp_server.py` | `list_tools`, `call_tool` dispatch, error handling |
| `test_server.py` | `/health` endpoint, OAuth endpoints, Bearer auth detection |
| `test_best_practices.py` | `NiFiBestPractices`, `analyze_flow_request`, `SetupGuide` |
| `test_best_practices_extra.py` | `SmartFlowBuilder`, root PG id extraction, flow validation |
| `test_setup_helper.py` | `validate_current_config`, env prefix compatibility |
| `test_security.py` | Cert upload size limits, connection name validation, credential masking |

---

## Design Decisions

### Per-session routing
Each MCP session (identified by `Mcp-Session-Id` header) gets its own active NiFi
connection pointer. Two concurrent Claude Code windows can work on different NiFi
instances simultaneously. Sessions idle for 8 hours (`NIFI_MCP_SESSION_TIMEOUT`) are
automatically cleaned up by a background task that runs every 5 minutes.

### Connection state persistence
`ConnectionRegistry` saves all connections to `/data/nifi_state.json` (Docker volume).
On startup, saved connections are restored and reconnected automatically. Sensitive
fields (`cert_password`, `knox_password`, `knox_token`, `knox_cookie`, `knox_passcode`)
are never returned via API — they are masked as `***` in all responses.

### Read-only by default
All connections default to `readonly=True`. Write-operations (`start_processor`,
`delete_connection`, `empty_connection_queue`, etc.) check this flag and return a
tool error if readonly is active. This prevents accidental production changes.

### NiFi URL normalization
Users may enter `https://nifi.example.com:8443`, `.../nifi`, or `.../nifi-api`.
`_normalize_nifi_url()` in `nifi_client_manager.py` normalizes all three forms to
`https://nifi.example.com:8443/nifi-api` before building the client.

### Auth method detection
When a default connection is built from env vars, `_detect_auth_method()` in
`server.py` inspects which credentials are set (P12 path → `certificate_p12`,
Knox token → `knox_token`, etc.) and picks the appropriate auth method automatically.

### Certificate storage
Certificates uploaded via Dashboard are stored inside the Docker volume at
`/data/certs/{connection-name}/`. Paths stored in `nifi_state.json` are relative
to `/data/certs/` so they survive container rebuilds as long as the volume is intact.

### Network mode
- **Linux**: `network_mode: host` — container shares the host network stack.
  The gateway reaches NiFi at any host-accessible address with no extra config.
- **Windows/macOS**: bridge network with explicit port mapping. NiFi on the same host
  is reachable at `host.docker.internal`.

### MCP transport
Uses `StreamableHTTPServerTransport` from the MCP SDK (version ≥ 1.9.0).
Supports optional Bearer token auth (`NIFI_MCP_API_KEY`). OAuth discovery endpoints
(`/.well-known/oauth-protected-resource`, `/.well-known/oauth-authorization-server`)
are implemented for clients that perform OAuth discovery before connecting.

### Systemd service on Linux
The systemd service uses `Type=oneshot` + `RemainAfterExit=yes` with
`docker compose up -d --build`. The `--build` flag ensures the image is rebuilt
from the Dockerfile on every boot start, protecting against corrupted layer caches
after an unclean shutdown. The container's own `restart: always` provides fast
recovery from crashes without waiting for a systemd restart.

---

## NiFi Version Compatibility

| Feature | NiFi 1.x | NiFi 2.x |
|---------|----------|----------|
| All 25 read-only tools | Yes | Yes |
| All 35 write tools | Yes | Yes |
| Parameter contexts | Yes (≥ 1.15) | Yes |
| Knox / CDP auth | Yes | Yes |
| Basic auth | Yes | Yes |
| mTLS (P12/PEM) | Yes | Yes |
| Version auto-detect | Yes | Yes |

Version is detected by calling `/nifi-api/system-diagnostics` and reading the
`systemDiagnostics.aggregateSnapshot.versionInfo.niFiVersion` field.

---

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/mcp` | POST | MCP Streamable HTTP transport |
| `/health` | GET | Health check + connection count + session count |
| `/dashboard` | GET | Web UI (bilingual RU/EN) |
| `/dashboard/docs` | GET | Embedded documentation |
| `/api/status` | GET | JSON status of all connections |
| `/api/connections` | GET | List all registered connections |
| `/api/connect` | POST | Add / connect a NiFi instance (multipart or JSON) |
| `/api/disconnect` | POST | Disconnect and remove a NiFi instance |
| `/api/edit` | POST | Edit connection properties |
| `/api/switch` | POST | Switch active connection for a session |
| `/api/test` | POST | Test a connection without saving |
| `/.well-known/oauth-protected-resource` | GET | OAuth resource metadata |
| `/.well-known/oauth-authorization-server` | GET | OAuth server metadata |
| `/oauth/token` | POST | Token endpoint (returns `NIFI_MCP_API_KEY` as access token) |

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| MCP not in `/mcp` | `docker ps` — check container is running; `claude mcp list` |
| Port 8085 in use | Change `NIFI_MCP_PORT` in `.env`, re-run `./setup.sh` |
| SSL error from NiFi | Use `verify_ssl=false` or upload CA cert via Dashboard |
| Write tools denied | Connect with `readonly=false` |
| Container not starting after reboot (Linux) | `sudo systemctl status nifi-mcp-universal` |
| Container not starting after reboot (Windows) | Enable "Start Docker Desktop when you log in" |
| Connection lost after gateway restart | Connections auto-restore from `/data/nifi_state.json` |
| Cert upload fails | Max 10 MB; must be valid P12/PEM; name must be alphanumeric |

```bash
# View gateway logs
docker compose logs nifi-mcp-gateway

# Re-run setup (safe, idempotent)
./setup.sh

# Manually re-register MCP
claude mcp remove nifi-universal -s user 2>/dev/null || true
claude mcp add --transport http -s user nifi-universal http://localhost:8085/mcp

# Rebuild and restart
docker compose down && docker compose up -d --build
```
