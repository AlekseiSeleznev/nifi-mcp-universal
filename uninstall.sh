#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

SERVICE_NAME="nifi-mcp-universal"
IMAGE_NAME="nifi-mcp-gateway"

ok()   { echo "[+] $*"; }
info() { echo "[i] $*"; }
warn() { echo "[!] $*"; }

echo ""
echo "=== Removing nifi-mcp-universal runtime artifacts ==="

if command -v codex >/dev/null 2>&1; then
  codex mcp remove nifi-universal >/dev/null 2>&1 || true
  ok "Removed local Codex registration (if it existed)"
else
  info "codex CLI not found — skipping Codex cleanup"
fi

if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  docker compose down -v --remove-orphans --rmi local >/dev/null 2>&1 || true
  docker image rm "$IMAGE_NAME" >/dev/null 2>&1 || true
  ok "Removed project Docker resources (container, volume, local image)"
else
  warn "docker compose is unavailable — skipping Docker cleanup"
fi

if [ -f docker-compose.override.yml ] && grep -q "^# Auto-generated for " docker-compose.override.yml 2>/dev/null; then
  rm -f docker-compose.override.yml
  ok "Removed generated docker-compose.override.yml"
fi

if command -v systemctl >/dev/null 2>&1; then
  sudo systemctl disable --now "${SERVICE_NAME}" >/dev/null 2>&1 || true
  sudo rm -f "/etc/systemd/system/${SERVICE_NAME}.service" >/dev/null 2>&1 || true
  sudo systemctl daemon-reload >/dev/null 2>&1 || true
  ok "Removed Linux systemd unit (if it existed)"
fi

echo ""
echo "Project-scoped cleanup completed."
echo "If you want to remove the repository directory too, delete it manually after this script exits."
echo ""
