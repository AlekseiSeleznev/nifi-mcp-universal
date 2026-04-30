#!/usr/bin/env bash
set -euo pipefail

# ── nifi-mcp-universal setup ──────────────────────────────────────
# One-command gateway setup: creates .env, builds Docker image,
# starts the container, and optionally registers the MCP server in Codex.
# Works on Linux, macOS, and Windows (Git Bash / WSL).

cd "$(dirname "$0")"

DEFAULT_PORT=8085
NAME="nifi-universal"
ENV_PORT_KEY="NIFI_MCP_PORT"
CONTAINER="nifi-mcp-gateway"
SETUP_CI="${MCP_SETUP_CI:-0}"
HAS_CODEX=0
CODEX_REGISTERED=0
CODEX_REGISTRATION_SKIPPED=0
SERVICE_NAME="nifi-mcp-universal"

env_val() { grep "^$1=" "$2" 2>/dev/null | head -1 | cut -d= -f2-; }

ensure_env_key() {
  local key="$1" file="$2"
  if ! grep -q "^${key}=" "$file" 2>/dev/null; then
    echo "${key}=" >> "$file"
  fi
}

ok()   { echo "[+] $*"; }
info() { echo "[i] $*"; }
warn() { echo "[!] $*"; }
fail() { echo "[ERROR] $*" >&2; exit 1; }

register_codex() {
  local port="$1"
  local api_key="$2"

  [ "$HAS_CODEX" -eq 1 ] || return 0

  if [ -n "${api_key:-}" ] && [ "${NIFI_MCP_API_KEY:-}" != "${api_key}" ]; then
    warn "NIFI_MCP_API_KEY is set in .env, but the same value is not exported in the current shell."
    warn "Skipping Codex registration for the authenticated MCP endpoint."
    warn "Export NIFI_MCP_API_KEY and use CODEX.md for the authenticated registration flow."
    CODEX_REGISTRATION_SKIPPED=1
    return 0
  fi

  echo ""
  echo "=== Optional Codex registration ==="
  codex mcp remove "$NAME" >/dev/null 2>&1 || true

  if [ -n "${api_key:-}" ]; then
    if codex mcp add "$NAME" --url "http://localhost:${port}/mcp" --bearer-token-env-var NIFI_MCP_API_KEY; then
      ok "Registered '${NAME}' in Codex with bearer-token env var NIFI_MCP_API_KEY"
    else
      warn "Codex registration failed. Gateway install completed; see CODEX.md for manual registration."
      CODEX_REGISTRATION_SKIPPED=1
      return 0
    fi
  else
    if codex mcp add "$NAME" --url "http://localhost:${port}/mcp"; then
      ok "Registered '${NAME}' in Codex"
    else
      warn "Codex registration failed. Gateway install completed; see CODEX.md for manual registration."
      CODEX_REGISTRATION_SKIPPED=1
      return 0
    fi
  fi

  if codex mcp get "$NAME" --json >/dev/null 2>&1; then
    ok "'${NAME}' is present in 'codex mcp get ${NAME} --json'"
    CODEX_REGISTERED=1
  else
    warn "Codex registration verification failed. Gateway install completed; see CODEX.md for manual registration."
    CODEX_REGISTRATION_SKIPPED=1
  fi
}

install_codex_skills() {
  local installer="$(pwd)/tools/install-codex-skills.sh"
  if [ -x "$installer" ]; then
    echo ""
    echo "=== Installing bundled Codex skills ==="
    if "$installer"; then
      ok "Bundled Codex skills installed"
    else
      warn "Bundled Codex skill installation failed. Gateway install will continue."
      warn "Run manually later: ./tools/install-codex-skills.sh"
    fi
  else
    warn "tools/install-codex-skills.sh not found — skipping Codex skill installation"
  fi
}

echo ""
echo "=== Checking prerequisites ==="

if command -v docker >/dev/null 2>&1; then
  ok "docker found: $(docker --version 2>/dev/null | head -1)"
else
  fail "Docker not found. Install Docker Engine: https://docs.docker.com/get-docker/"
fi

if ! docker info >/dev/null 2>&1; then
  fail "Docker daemon is not running. Start Docker and try again.
  Linux:   sudo systemctl start docker
  macOS:   open Docker Desktop
  Windows: start Docker Desktop"
fi
ok "Docker daemon is running"

if docker compose version >/dev/null 2>&1; then
  ok "docker compose v2 found: $(docker compose version 2>/dev/null | head -1)"
else
  fail "Docker Compose v2 not found. Install the Compose plugin:
  https://docs.docker.com/compose/install/
  NOTE: This setup requires 'docker compose' (v2), not 'docker-compose' (v1)."
fi

if command -v codex >/dev/null 2>&1; then
  HAS_CODEX=1
  ok "codex CLI found: $(codex --version 2>/dev/null | head -1 || echo 'version unknown')"
else
  warn "codex CLI not found — gateway installation will continue without MCP auto-registration."
  warn "Use CODEX.md for optional Codex registration or AGENTS.md for any other MCP client."
fi

echo ""

OS="linux"
case "$(uname -s)" in
  Darwin*)               OS="macos"   ;;
  MINGW*|MSYS*|CYGWIN*)  OS="windows" ;;
esac

if [ "$OS" != "linux" ] && [ ! -f docker-compose.override.yml ]; then
  cat > docker-compose.override.yml <<EOF
# Auto-generated for ${OS} — bridge network (host mode unsupported)
services:
  gateway:
    network_mode: bridge
    ports:
      - "\${${ENV_PORT_KEY}:-${DEFAULT_PORT}}:\${${ENV_PORT_KEY}:-${DEFAULT_PORT}}"
    extra_hosts:
      - "host.docker.internal:host-gateway"
EOF
  ok "Created docker-compose.override.yml for ${OS}"
fi

if [ ! -f .env ]; then
  cp .env.example .env
  ok "Created .env from .env.example"
else
  info ".env already exists, keeping it"
fi

ensure_env_key "NIFI_MCP_API_KEY" .env

PORT=$(env_val "$ENV_PORT_KEY" .env 2>/dev/null || true)
PORT=${PORT:-$DEFAULT_PORT}
API_KEY=$(env_val "NIFI_MCP_API_KEY" .env 2>/dev/null || true)

if [ -n "${API_KEY:-}" ]; then
  info "Using existing NIFI_MCP_API_KEY from .env"
else
  ok "MCP/dashboard bearer auth is disabled by default (NIFI_MCP_API_KEY is empty)"
fi

if command -v ss >/dev/null 2>&1; then
  PORT_IN_USE=$(ss -tlnp "sport = :${PORT}" 2>/dev/null | grep -c ":${PORT}" || true)
elif command -v lsof >/dev/null 2>&1; then
  PORT_IN_USE=$(lsof -ti ":${PORT}" 2>/dev/null | wc -l | tr -d ' ' || echo 0)
else
  PORT_IN_USE=0
fi

if [ "${PORT_IN_USE}" -gt 0 ]; then
  warn "Port ${PORT} appears to be in use by another process."
  warn "If it belongs to an old gateway container, it will be replaced."
  if [ "$SETUP_CI" = "1" ]; then
    info "MCP_SETUP_CI=1: continuing without interactive prompt"
  else
    printf "Continue anyway? [y/N] "
    read -r REPLY
    case "$REPLY" in
      [yY]|[yY][eE][sS]) info "Continuing..." ;;
      *) fail "Aborted. To use a different port, edit NIFI_MCP_PORT in .env and re-run." ;;
    esac
  fi
fi

echo ""
echo "=== Building and starting container ==="
info "Using port ${PORT} (restart: always — survives reboot)"
docker compose up -d --build --remove-orphans
ok "Container started"

echo ""
echo "=== Waiting for gateway to be healthy ==="
HEALTHY=0
for _i in $(seq 1 30); do
  if curl --max-time 2 -sf "http://localhost:${PORT}/health" >/dev/null 2>&1; then
    HEALTHY=1
    break
  fi
  printf "."
  sleep 1
done
[ "$HEALTHY" -eq 0 ] && echo ""

if [ "$HEALTHY" -eq 0 ]; then
  STATUS=$(docker inspect --format='{{.State.Health.Status}}' "$CONTAINER" 2>/dev/null || echo "unknown")
  [ "$STATUS" = "healthy" ] && HEALTHY=1
fi

if [ "$HEALTHY" -eq 1 ]; then
  echo ""
  HEALTH_RESPONSE=$(curl --max-time 2 -s "http://localhost:${PORT}/health" 2>/dev/null || echo "{}")
  ok "Gateway is healthy on port ${PORT}"
  info "Health: ${HEALTH_RESPONSE}"
else
  echo ""
  warn "Gateway not healthy after 30s."
  warn "Check logs: docker compose logs ${CONTAINER}"
  warn "Check port: docker ps"
  exit 1
fi

if [ "$OS" = "linux" ] && [ "$SETUP_CI" != "1" ] && command -v systemctl >/dev/null 2>&1; then
  SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
  WORK_DIR="$(pwd)"
  SERVICE_CONTENT="[Unit]
Description=${SERVICE_NAME} (Docker Compose)
Requires=docker.service
After=docker.service network-online.target
Wants=network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/usr/bin/docker compose -f ${WORK_DIR}/docker-compose.yml up -d --remove-orphans
ExecStop=/usr/bin/docker compose -f ${WORK_DIR}/docker-compose.yml down
TimeoutStartSec=300

[Install]
WantedBy=multi-user.target"
  SERVICE_UPDATED=0
  if [ ! -f "$SERVICE_FILE" ] || ! diff -q "$SERVICE_FILE" <(printf '%s\n' "$SERVICE_CONTENT") >/dev/null 2>&1; then
    if printf '%s\n' "$SERVICE_CONTENT" | sudo tee "$SERVICE_FILE" > /dev/null 2>&1; then
      sudo systemctl daemon-reload
      SERVICE_UPDATED=1
    else
      warn "Could not install systemd service automatically (sudo is unavailable)."
      warn "See README.md for the manual Linux autostart instructions."
    fi
  fi
  if [ "$SERVICE_UPDATED" -eq 1 ]; then
    info "systemd service file written: ${SERVICE_NAME}"
  else
    info "systemd service already up to date: ${SERVICE_NAME}"
  fi
  if sudo systemctl enable --now "${SERVICE_NAME}.service" >/dev/null 2>&1; then
    ok "systemd service enabled and started: ${SERVICE_NAME} (auto-start on boot without forced rebuild)"
  else
    warn "Could not enable/start systemd service automatically (sudo is unavailable)."
    warn "Run manually: sudo systemctl enable --now ${SERVICE_NAME}.service"
  fi
fi

if [ "$OS" = "windows" ] && [ "$SETUP_CI" != "1" ]; then
  PS_SCRIPT="$(pwd)/tools/ensure-docker-autostart-windows.ps1"
  if [ -f "$PS_SCRIPT" ]; then
    info "Ensuring Docker Desktop is set to start at login..."
    if powershell -ExecutionPolicy Bypass -File "$PS_SCRIPT" 2>/dev/null; then
      ok "Docker Desktop autostart configured"
    else
      warn "Could not configure Docker Desktop autostart automatically."
      warn "Please enable manually: Docker Desktop -> Settings -> General ->"
      warn "  'Start Docker Desktop when you log in'"
    fi
  else
    warn "tools/ensure-docker-autostart-windows.ps1 not found — skipping autostart setup"
  fi
fi

register_codex "$PORT" "${API_KEY:-}"
install_codex_skills

echo ""
echo "============================================"
echo " nifi-mcp-universal is ready!"
echo "============================================"
echo ""
echo "  Dashboard:  http://localhost:${PORT}/dashboard"
echo "  Health:     http://localhost:${PORT}/health"
echo "  MCP URL:    http://localhost:${PORT}/mcp"
echo ""
echo "Next steps:"
echo "  1. Open the Dashboard and add your first NiFi connection"
echo "  2. Use AGENTS.md for generic MCP client onboarding"
echo "  3. Use CODEX.md for optional Codex registration, skills, and cleanup"
if [ "$CODEX_REGISTERED" -eq 1 ]; then
  echo "  4. Verify Codex registration: codex mcp get ${NAME} --json"
elif [ "$HAS_CODEX" -eq 1 ] || [ "$CODEX_REGISTRATION_SKIPPED" -eq 1 ]; then
  echo "  4. Codex registration was skipped or needs manual follow-up; see CODEX.md"
fi
echo "  5. Skill self-test: python3 ~/.codex/skills/nifi-flow-layout/scripts/nifi_layout.py --mode self-test"
echo ""
echo "Runbooks:"
echo "  - README.md : neutral install, Windows/Linux specifics, troubleshooting"
echo "  - CODEX.md  : optional Codex registration, bundled skills, verification, cleanup"
echo "  - AGENTS.md : manual onboarding for any streamable HTTP MCP client"
echo "  - docs/nifi-flow-layout.md : universal NiFi flow layout skill usage"
echo ""
echo "After reboot: container auto-starts with Docker."
if [ "$CODEX_REGISTERED" -eq 1 ]; then
  echo "             Codex registration stays in the local Codex config."
fi
echo ""
