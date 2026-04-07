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

# ── 1. Prerequisites ─────────────────────────────────────────────
command -v docker >/dev/null 2>&1 || { echo "ERROR: Docker not found. Install: https://docs.docker.com/get-docker/"; exit 1; }
docker compose version >/dev/null 2>&1 || { echo "ERROR: Docker Compose V2 not found."; exit 1; }

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
  echo "[+] Created docker-compose.override.yml for ${OS}"
fi

# ── 3. Create .env ──────────────────────────────────────────────
if [ ! -f .env ]; then
  cp .env.example .env
  echo "[+] Created .env from .env.example (port ${DEFAULT_PORT})"
else
  echo "[i] .env already exists, keeping it"
fi

PORT=$(env_val "$ENV_PORT_KEY" .env 2>/dev/null || true)
PORT=${PORT:-$DEFAULT_PORT}

# ── 4. Build & start ───────────────────────────────────────────
echo "[*] Building and starting container..."
docker compose up -d --build --remove-orphans

# ── 5. Health check ─────────────────────────────────────────────
echo "[*] Waiting for gateway to be healthy..."
HEALTHY=0
for i in $(seq 1 30); do
  if curl -sf "http://localhost:${PORT}/health" >/dev/null 2>&1; then
    HEALTHY=1; break
  fi
  sleep 1
done

if [ "$HEALTHY" -eq 0 ]; then
  # Fallback: check docker health (curl may be absent on Windows)
  STATUS=$(docker inspect --format='{{.State.Health.Status}}' "$CONTAINER" 2>/dev/null || echo "unknown")
  [ "$STATUS" = "healthy" ] && HEALTHY=1
fi

if [ "$HEALTHY" -eq 1 ]; then
  echo "[+] Gateway is healthy on port ${PORT}"
else
  echo "[!] Gateway not healthy after 30s. Check: docker logs ${CONTAINER}"
  exit 1
fi

# ── 6. Register in Claude Code ──────────────────────────────────
if command -v claude >/dev/null 2>&1; then
  claude mcp remove "$NAME" -s user 2>/dev/null || true
  claude mcp add --transport http -s user "$NAME" "http://localhost:${PORT}/mcp"
  echo "[+] Registered '${NAME}' in Claude Code (user scope)"
  echo ""
  echo "Done! Run 'claude' and use /mcp to verify."
else
  echo ""
  echo "[i] Claude Code CLI not found. Register manually:"
  echo "    claude mcp add --transport http -s user ${NAME} http://localhost:${PORT}/mcp"
fi

echo ""
echo "Dashboard: http://localhost:${PORT}/dashboard"
