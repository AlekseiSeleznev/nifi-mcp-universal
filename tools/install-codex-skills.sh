#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

SKILL_NAME="nifi-flow-layout"
SOURCE_DIR="$(pwd)/skills/${SKILL_NAME}"
TARGET_ROOT="${CODEX_SKILLS_DIR:-${HOME}/.codex/skills}"
TARGET_DIR="${TARGET_ROOT}/${SKILL_NAME}"
TMP_DIR="${TARGET_ROOT}/.${SKILL_NAME}.tmp.$$"

ok() { echo "[+] $*"; }
fail() { echo "[ERROR] $*" >&2; exit 1; }

[ -d "$SOURCE_DIR" ] || fail "Bundled skill not found: ${SOURCE_DIR}"
[ -f "$SOURCE_DIR/SKILL.md" ] || fail "Bundled skill is missing SKILL.md: ${SOURCE_DIR}"

mkdir -p "$TARGET_ROOT"
rm -rf "$TMP_DIR"
mkdir -p "$TMP_DIR"
cp -R "$SOURCE_DIR"/. "$TMP_DIR"/
chmod +x "$TMP_DIR/scripts/nifi_layout.py" "$TMP_DIR/scripts/nifi_visual_check.cjs" 2>/dev/null || true
rm -rf "$TARGET_DIR"
mv "$TMP_DIR" "$TARGET_DIR"

ok "Installed Codex skill '${SKILL_NAME}' to ${TARGET_DIR}"
ok "Self-test: python3 ${TARGET_DIR}/scripts/nifi_layout.py --mode self-test"
