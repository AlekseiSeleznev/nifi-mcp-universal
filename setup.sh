#!/usr/bin/env bash
set -euo pipefail

# ── nifi-mcp-universal setup ──────────────────────────────────────
# One-command setup: creates .env, builds Docker image, starts
# the container, and registers the MCP server in Claude Code.

cd "$(dirname "$0")"

PORT=8085
NAME="nifi-universal"

# ── 1. Prerequisites ─────────────────────────────────────────────
command -v docker >/dev/null 2>&1 || { echo "❌ Docker is not installed. Install it first: https://docs.docker.com/get-docker/"; exit 1; }
docker compose version >/dev/null 2>&1 || { echo "❌ Docker Compose V2 is not available."; exit 1; }

# ── 2. Create .env from example if not exists ────────────────────
if [ ! -f .env ]; then
  cp .env.example .env
  echo "✅ Created .env from .env.example (port $PORT)"
else
  echo "ℹ️  .env already exists, keeping it"
  PORT=$(grep -oP 'NIFI_MCP_PORT=\K\d+' .env 2>/dev/null || echo "$PORT")
fi

# ── 3. Build & start ────────────────────────────────────────────
echo "🔨 Building and starting container..."
docker compose up -d --build --remove-orphans

# ── 4. Wait for healthy ─────────────────────────────────────────
echo "⏳ Waiting for gateway to be healthy..."
for i in $(seq 1 30); do
  if curl -sf "http://localhost:${PORT}/health" >/dev/null 2>&1; then
    echo "✅ Gateway is healthy on port $PORT"
    break
  fi
  if [ "$i" -eq 30 ]; then
    echo "❌ Gateway did not become healthy within 30s"
    echo "   Check logs: docker logs nifi-mcp-gateway"
    exit 1
  fi
  sleep 1
done

# ── 5. Register in Claude Code ──────────────────────────────────
if command -v claude >/dev/null 2>&1; then
  # Remove old registration if exists
  claude mcp remove "$NAME" -s user 2>/dev/null || true
  claude mcp add --transport http -s user "$NAME" "http://localhost:${PORT}/mcp"
  echo "✅ Registered '$NAME' in Claude Code (user scope)"
  echo ""
  echo "🎉 Done! Run 'claude' and use /mcp to verify the connection."
else
  echo ""
  echo "⚠️  Claude Code CLI not found. Add the MCP server manually:"
  echo ""
  echo "   claude mcp add --transport http -s user $NAME http://localhost:${PORT}/mcp"
  echo ""
  echo "   Or add to ~/.claude.json:"
  echo '   "mcpServers": {'
  echo "     \"$NAME\": {"
  echo '       "type": "http",'
  echo "       \"url\": \"http://localhost:${PORT}/mcp\""
  echo '     }'
  echo '   }'
fi

echo ""
echo "📊 Dashboard: http://localhost:${PORT}/dashboard"
