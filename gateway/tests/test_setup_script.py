"""Black-box tests for setup.sh using stubbed external commands."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import textwrap

import pytest


pytestmark = pytest.mark.skipif(
    sys.platform == "win32",
    reason="Windows CI validates setup.sh via dedicated static/smoke checks; subprocess bash resolution is WSL-specific.",
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _write_executable(path: Path, content: str) -> None:
    path.write_text(textwrap.dedent(content), encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IEXEC)


def _make_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    root = _repo_root()

    for rel in ("setup.sh", "install.ps1", "uninstall.sh", "uninstall.ps1", ".env.example", "docker-compose.yml", "docker-compose.windows.yml"):
        src = root / rel
        dst = repo / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

    tools_dir = repo / "tools"
    tools_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(root / "tools" / "ensure-docker-autostart-windows.ps1", tools_dir / "ensure-docker-autostart-windows.ps1")
    shutil.copy2(root / "tools" / "install-codex-skills.sh", tools_dir / "install-codex-skills.sh")
    shutil.copy2(root / "tools" / "install-codex-skills.ps1", tools_dir / "install-codex-skills.ps1")
    shutil.copytree(root / "skills", repo / "skills")
    return repo


def _make_stub_bin(tmp_path: Path, *, include_codex: bool = True) -> Path:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()

    _write_executable(
        bin_dir / "docker",
        """\
        #!/usr/bin/env bash
        set -euo pipefail
        case "${1:-}" in
          --version)
            echo "Docker version 27.0.0, build test"
            ;;
          info)
            echo "Server: fake-docker"
            ;;
          compose)
            case "${2:-}" in
              version)
                echo "Docker Compose version v2.30.0"
                ;;
              up|down|config|logs)
                exit 0
                ;;
              *)
                exit 0
                ;;
            esac
            ;;
          inspect)
            echo "healthy"
            ;;
          ps)
            exit 0
            ;;
          image)
            exit 0
            ;;
          *)
            exit 0
            ;;
        esac
        """,
    )

    _write_executable(
        bin_dir / "curl",
        """\
        #!/usr/bin/env bash
        set -euo pipefail
        echo '{"status":"ok"}'
        """,
    )

    if include_codex:
        _write_executable(
            bin_dir / "codex",
            """\
            #!/usr/bin/env bash
            set -euo pipefail
            state_dir="${FAKE_STATE_DIR:?}"
            state_file="${state_dir}/codex-mcp.json"

            if [ "${1:-}" = "--version" ]; then
              echo "codex-cli 0.0.test"
              exit 0
            fi

            if [ "${1:-}" != "mcp" ]; then
              exit 1
            fi

            sub="${2:-}"
            case "$sub" in
              add)
                name="${3:-}"
                shift 3
                url=""
                bearer=""
                while [ $# -gt 0 ]; do
                  case "$1" in
                    --url)
                      url="${2:-}"
                      shift 2
                      ;;
                    --bearer-token-env-var)
                      bearer="${2:-}"
                      shift 2
                      ;;
                    *)
                      shift
                      ;;
                  esac
                done
                printf '{"name":"%s","transport":{"type":"streamable_http","url":"%s","bearer_token_env_var":"%s"}}\n' "$name" "$url" "$bearer" > "$state_file"
                ;;
              remove)
                rm -f "$state_file"
                ;;
              get)
                name="${3:-}"
                [ -n "$name" ] || exit 1
                [ -f "$state_file" ] || exit 1
                cat "$state_file"
                ;;
              list)
                if [ -f "$state_file" ]; then
                  printf '[%s]\n' "$(cat "$state_file")"
                else
                  echo '[]'
                fi
                ;;
              *)
                exit 1
                ;;
            esac
            """,
        )

    return bin_dir


def _run_setup(repo: Path, bin_dir: Path, *, extra_env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}{os.pathsep}/usr/bin{os.pathsep}/bin"
    env["FAKE_STATE_DIR"] = str(bin_dir)
    env["MCP_SETUP_CI"] = "1"
    env["CODEX_SKILLS_DIR"] = str(bin_dir / "codex-skills")
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        ["bash", "setup.sh"],
        cwd=repo,
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


def test_setup_registers_codex_server_when_auth_disabled(tmp_path: Path):
    repo = _make_repo(tmp_path)
    bin_dir = _make_stub_bin(tmp_path)

    result = _run_setup(repo, bin_dir)

    assert result.returncode == 0, result.stderr
    state = json.loads((bin_dir / "codex-mcp.json").read_text(encoding="utf-8"))
    assert state["name"] == "nifi-universal"
    assert state["transport"]["url"] == "http://localhost:8085/mcp"
    assert state["transport"]["bearer_token_env_var"] == ""
    assert "Registered 'nifi-universal' in Codex" in result.stdout
    assert (bin_dir / "codex-skills" / "nifi-flow-layout" / "SKILL.md").exists()


def test_setup_registers_bearer_env_var_when_api_key_is_exported(tmp_path: Path):
    repo = _make_repo(tmp_path)
    (repo / ".env").write_text("NIFI_MCP_PORT=8085\nNIFI_MCP_API_KEY=secret\n", encoding="utf-8")
    bin_dir = _make_stub_bin(tmp_path)

    result = _run_setup(repo, bin_dir, extra_env={"NIFI_MCP_API_KEY": "secret"})

    assert result.returncode == 0, result.stderr
    state = json.loads((bin_dir / "codex-mcp.json").read_text(encoding="utf-8"))
    assert state["transport"]["bearer_token_env_var"] == "NIFI_MCP_API_KEY"


def test_setup_succeeds_without_codex_cli(tmp_path: Path):
    repo = _make_repo(tmp_path)
    bin_dir = _make_stub_bin(tmp_path, include_codex=False)

    result = _run_setup(repo, bin_dir)

    assert result.returncode == 0, result.stderr
    assert "codex CLI not found" in result.stdout


def test_setup_skips_codex_registration_when_api_key_is_not_exported(tmp_path: Path):
    repo = _make_repo(tmp_path)
    (repo / ".env").write_text("NIFI_MCP_PORT=8085\nNIFI_MCP_API_KEY=secret\n", encoding="utf-8")
    bin_dir = _make_stub_bin(tmp_path)

    result = _run_setup(repo, bin_dir)

    assert result.returncode == 0, result.stderr
    assert "Skipping Codex registration" in result.stdout
    assert not (bin_dir / "codex-mcp.json").exists()
