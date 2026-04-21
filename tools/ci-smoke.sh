#!/usr/bin/env bash
set -euo pipefail

if command -v python >/dev/null 2>&1; then
  PYTHON_BIN="python"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="python3"
else
  echo "python/python3 is unavailable; cannot run compileall smoke check"
  exit 1
fi

"${PYTHON_BIN}" -m compileall -q gateway
bash -n setup.sh
bash -n uninstall.sh

if [ ! -f .env ]; then
  if [ -f .env.example ]; then
    cp .env.example .env
  else
    : > .env
  fi
fi

if command -v pwsh >/dev/null 2>&1; then
  pwsh -NoProfile -Command "[void][scriptblock]::Create((Get-Content -Raw 'install.ps1')); [void][scriptblock]::Create((Get-Content -Raw 'uninstall.ps1'))"
else
  echo "pwsh is unavailable on this runner; skipping PowerShell syntax checks"
fi

if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  docker compose -f docker-compose.yml config -q
  docker compose -f docker-compose.yml -f docker-compose.windows.yml config -q
else
  echo "docker compose is unavailable on this runner; skipping compose config smoke checks"
fi
