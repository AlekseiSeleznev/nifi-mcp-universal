#!/usr/bin/env bash
set -euo pipefail

# ── nifi-mcp-universal setup ──────────────────────────────────────
# One-command setup: creates .env, builds Docker image, starts
# the container, and registers the MCP server in Claude Code.
# Works on Linux, macOS, and Windows (Git Bash / WSL).

cd "$(dirname "$0")"

DEFAULT_PORT=8085
NAME="nifi-universal"
ENV_PORT_KEY="NIFI_MCP_PORT"
CONTAINER="nifi-mcp-gateway"

# ── Helpers ──────────────────────────────────────────────────────
env_val() { grep "^$1=" "$2" 2>/dev/null | head -1 | cut -d= -f2-; }

# ensure_env KEY VALUE FILE — add or update KEY=VALUE in FILE (idempotent)
ensure_env() {
  local key="$1" value="$2" file="$3"
  if grep -q "^${key}=" "$file" 2>/dev/null; then
    # Key exists — update only if the current value is empty or a placeholder
    local cur
    cur=$(env_val "$key" "$file")
    if [ -z "$cur" ] || echo "$cur" | grep -q "^#\|example\|change"; then
      sed -i "s|^${key}=.*|${key}=${value}|" "$file"
    fi
  else
    echo "${key}=${value}" >> "$file"
  fi
}

ok()   { echo "[+] $*"; }
info() { echo "[i] $*"; }
warn() { echo "[!] $*"; }
fail() { echo "[ERROR] $*" >&2; exit 1; }

# ── 1. Prerequisites ─────────────────────────────────────────────
echo ""
echo "=== Checking prerequisites ==="

# Docker binary
if command -v docker >/dev/null 2>&1; then
  ok "docker found: $(docker --version 2>/dev/null | head -1)"
else
  fail "Docker not found. Install Docker Engine: https://docs.docker.com/get-docker/"
fi

# Docker daemon running
if ! docker info >/dev/null 2>&1; then
  fail "Docker daemon is not running. Start Docker and try again.
  Linux:  sudo systemctl start docker
  macOS:  open Docker Desktop
  Windows: start Docker Desktop"
fi
ok "Docker daemon is running"

# Docker Compose v2 (plugin, not standalone docker-compose)
if docker compose version >/dev/null 2>&1; then
  ok "docker compose v2 found: $(docker compose version 2>/dev/null | head -1)"
else
  fail "Docker Compose v2 not found. Install the Compose plugin:
  https://docs.docker.com/compose/install/
  NOTE: This setup requires 'docker compose' (v2), not 'docker-compose' (v1)."
fi

# Claude CLI
if command -v claude >/dev/null 2>&1; then
  ok "claude CLI found: $(claude --version 2>/dev/null | head -1 || echo 'version unknown')"
  CLAUDE_FOUND=1
else
  warn "Claude Code CLI not found. MCP will NOT be registered automatically."
  warn "Install Claude Code: https://claude.ai/download"
  warn "After installing, run manually:"
  warn "  claude mcp add --transport http -s user ${NAME} http://localhost:${DEFAULT_PORT}/mcp"
  CLAUDE_FOUND=0
fi

echo ""

# ── 2. Detect OS ────────────────────────────────────────────────
OS="linux"
case "$(uname -s)" in
  Darwin*)                OS="macos"   ;;
  MINGW*|MSYS*|CYGWIN*)  OS="windows" ;;
esac

# macOS / Windows: network_mode:host not supported, need bridge + port mapping
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

# ── 3. Create .env ──────────────────────────────────────────────
if [ ! -f .env ]; then
  cp .env.example .env
  ok "Created .env from .env.example (port ${DEFAULT_PORT})"
else
  info ".env already exists, keeping it"
fi

PORT=$(env_val "$ENV_PORT_KEY" .env 2>/dev/null || true)
PORT=${PORT:-$DEFAULT_PORT}

# ── 4. Check port availability ──────────────────────────────────
if command -v ss >/dev/null 2>&1; then
  PORT_IN_USE=$(ss -tlnp "sport = :${PORT}" 2>/dev/null | grep -c ":${PORT}" || true)
elif command -v lsof >/dev/null 2>&1; then
  PORT_IN_USE=$(lsof -ti ":${PORT}" 2>/dev/null | wc -l | tr -d ' ' || echo 0)
else
  PORT_IN_USE=0
fi

if [ "${PORT_IN_USE}" -gt 0 ]; then
  warn "Port ${PORT} appears to be in use by another process."
  warn "If it's the old container, it will be replaced. Otherwise check what's using port ${PORT}."
  printf "Continue anyway? [y/N] "
  read -r REPLY
  case "$REPLY" in
    [yY]|[yY][eE][sS]) info "Continuing..." ;;
    *) fail "Aborted. To use a different port, edit NIFI_MCP_PORT in .env and re-run." ;;
  esac
fi

# ── 5. Build & start ───────────────────────────────────────────
echo ""
echo "=== Building and starting container ==="
info "Using port ${PORT} (restart: always — survives reboot)"
docker compose up -d --build --remove-orphans
ok "Container started"

# ── 6. Health check ─────────────────────────────────────────────
echo ""
echo "=== Waiting for gateway to be healthy ==="
HEALTHY=0
for i in $(seq 1 30); do
  if curl -sf "http://localhost:${PORT}/health" >/dev/null 2>&1; then
    HEALTHY=1; break
  fi
  printf "."
  sleep 1
done
[ "$HEALTHY" -eq 0 ] && echo ""

if [ "$HEALTHY" -eq 0 ]; then
  # Fallback: check docker health (curl may be absent on Windows)
  STATUS=$(docker inspect --format='{{.State.Health.Status}}' "$CONTAINER" 2>/dev/null || echo "unknown")
  [ "$STATUS" = "healthy" ] && HEALTHY=1
fi

if [ "$HEALTHY" -eq 1 ]; then
  echo ""
  HEALTH_RESPONSE=$(curl -s "http://localhost:${PORT}/health" 2>/dev/null || echo "{}")
  ok "Gateway is healthy on port ${PORT}"
  info "Health: ${HEALTH_RESPONSE}"
else
  echo ""
  warn "Gateway not healthy after 30s."
  warn "Check logs: docker compose logs ${CONTAINER}"
  warn "Check port: docker ps"
  exit 1
fi

# ── 6b. Install systemd service (Linux) ─────────────────────────
if [ "$OS" = "linux" ] && command -v systemctl >/dev/null 2>&1; then
  SERVICE_NAME="nifi-mcp-universal"
  SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
  WORK_DIR="$(pwd)"
  if [ ! -f "$SERVICE_FILE" ] || ! grep -q "\-f ${WORK_DIR}/docker-compose.yml" "$SERVICE_FILE" 2>/dev/null; then
    SERVICE_CONTENT="[Unit]
Description=${SERVICE_NAME} (Docker Compose)
Requires=docker.service
After=docker.service network-online.target
Wants=network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/usr/bin/docker compose -f ${WORK_DIR}/docker-compose.yml up -d --build
ExecStop=/usr/bin/docker compose -f ${WORK_DIR}/docker-compose.yml down
TimeoutStartSec=300

[Install]
WantedBy=multi-user.target"
    if printf '%s\n' "$SERVICE_CONTENT" | sudo tee "$SERVICE_FILE" > /dev/null 2>&1; then
      sudo systemctl daemon-reload
      sudo systemctl enable "${SERVICE_NAME}.service"
      ok "systemd service installed: ${SERVICE_NAME} (auto-start on boot with image rebuild)"
    else
      warn "Could not install systemd service (no sudo). To install manually:"
      warn "  sudo tee ${SERVICE_FILE} > /dev/null << 'SVCEOF'"
      printf '%s\n' "$SERVICE_CONTENT"
      warn "SVCEOF"
      warn "  sudo systemctl daemon-reload && sudo systemctl enable ${SERVICE_NAME}.service"
    fi
  else
    info "systemd service already up to date: ${SERVICE_NAME}"
  fi
fi

# ── 7. Register in Claude Code ──────────────────────────────────
echo ""
echo "=== Registering MCP server ==="

if [ "$CLAUDE_FOUND" -eq 1 ]; then
  # Idempotent: remove old registration first (ignore errors)
  claude mcp remove "$NAME" -s user 2>/dev/null || true
  # Register with user scope so it works in ALL sessions after reboot
  claude mcp add --transport http -s user "$NAME" "http://localhost:${PORT}/mcp"
  ok "Registered '${NAME}' in Claude Code (scope: user — all sessions)"

  echo ""
  echo "=== Verifying registration ==="
  if claude mcp list 2>/dev/null | grep -q "$NAME"; then
    ok "'${NAME}' is present in 'claude mcp list'"
  else
    warn "'${NAME}' not found in 'claude mcp list' — check manually: claude mcp list"
  fi
else
  warn "Claude CLI not found — skipping MCP registration."
  warn "After installing Claude Code, run:"
  warn "  claude mcp add --transport http -s user ${NAME} http://localhost:${PORT}/mcp"
fi

# ── 8. Final summary ────────────────────────────────────────────
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
echo "  1. Open Claude Code and run /mcp to verify the server is listed"
echo "  2. Open the Dashboard to add your first NiFi connection"
echo "  3. Or use MCP tool directly:"
echo "       connect_nifi(name=\"prod\", url=\"https://nifi.example.com:8443\","
echo "                    auth_method=\"basic\", username=\"admin\", password=\"...\")"
echo ""
echo "After reboot: container auto-starts (restart: always)."
echo "             MCP stays registered (user scope)."
echo ""
