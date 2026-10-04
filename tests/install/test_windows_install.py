"""Run the real installer in PowerShell with isolated external commands.

These tests cover installer control flow, not Docker Desktop's Linux VM.
CI runs them with both Windows PowerShell 5.1 and PowerShell 7.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


SHELLS = [name for name in ("pwsh", "powershell") if shutil.which(name)]
pytestmark = pytest.mark.skipif(not SHELLS, reason="PowerShell is unavailable")


@pytest.fixture(params=SHELLS or ["pwsh"])
def installer(tmp_path, request):
    root = Path(__file__).resolve().parents[2]
    repo = tmp_path / "repo with spaces"
    repo.mkdir()
    for name in ("install.ps1", ".env.example", "docker-compose.yml", "docker-compose.windows.yml"):
        shutil.copy2(root / name, repo / name)
    (repo / "tools").mkdir()
    shutil.copy2(root / "tools/install-codex-skills.ps1", repo / "tools")
    shutil.copytree(root / "skills", repo / "skills")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    stub = tmp_path / "external.py"
    stub.write_text('''import json, os, pathlib, sys
command, *args = sys.argv[1:]
state = pathlib.Path(os.environ["INSTALL_TEST_STATE"])
with (state / "calls.jsonl").open("a") as out:
    out.write(json.dumps([command, *args]) + "\\n")
failure = os.environ.get("INSTALL_TEST_FAILURE", "")
if command == "docker":
    if args == ["--version"]:
        print("Docker version test")
    elif args == ["info"] and failure == "daemon":
        sys.exit(7)
    elif args == ["compose", "version"] and failure == "compose":
        sys.exit(8)
    elif "up" in args and failure == "build":
        sys.exit(9)
elif command == "codex":
    if args == ["--version"]:
        print("codex-cli test")
    elif args[:2] == ["mcp", "add"]:
        if failure == "codex-add":
            sys.exit(10)
        (state / "registered.json").write_text(json.dumps(args))
    elif args[:2] == ["mcp", "get"] and failure == "codex-get":
        sys.exit(11)
''', encoding="utf-8")
    for name in ("docker", "codex"):
        if sys.platform == "win32":
            command = bin_dir / (name + ".cmd")
            command.write_text(f'@echo off\n"{sys.executable}" "{stub}" {name} %*\nexit /b %errorlevel%\n')
        else:
            import shlex
            command = bin_dir / name
            command.write_text(f'#!/bin/sh\nexec {shlex.quote(sys.executable)} {shlex.quote(str(stub))} {name} "$@"\n')
            command.chmod(0o755)
    harness = tmp_path / "run.ps1"
    harness.write_text('''$ErrorActionPreference = "Stop"
function Get-Command {
    param([string]$Name, [string]$ErrorAction)
    if ($Name -eq "codex" -and $env:INSTALL_TEST_FAILURE -eq "missing-codex") { return $null }
    Microsoft.PowerShell.Core\\Get-Command @PSBoundParameters
}
function Invoke-WebRequest {
    if ($env:INSTALL_TEST_FAILURE -eq "health") { throw "Synthetic health failure" }
    return [pscustomobject]@{ StatusCode = 200 }
}
function Start-Sleep {}
. (Join-Path $PSScriptRoot "repo with spaces/install.ps1")
''', encoding="utf-8")
    env = os.environ.copy()
    env.update({
        "PATH": str(bin_dir) + os.pathsep + env.get("PATH", ""),
        "MCP_SETUP_CI": "1",
        "CODEX_SKILLS_DIR": str(tmp_path / "installed-skills"),
        "INSTALL_TEST_STATE": str(tmp_path),
        "NIFI_MCP_API_KEY": "",
    })

    def run(failure="", existing_env=None, api_key=""):
        if existing_env is not None:
            (repo / ".env").write_text(existing_env, encoding="utf-8")
        env.update(INSTALL_TEST_FAILURE=failure, NIFI_MCP_API_KEY=api_key)
        result = subprocess.run(
            [shutil.which(request.param), "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", str(harness)],
            cwd=repo, env=env, capture_output=True, text=True, timeout=45,
        )
        calls = [json.loads(line) for line in (tmp_path / "calls.jsonl").read_text().splitlines()]
        return result, calls, repo, tmp_path

    return run


def test_fresh_install_creates_env_registers_mcp_and_installs_skill(installer):
    result, calls, repo, state = installer()
    assert result.returncode == 0, result.stderr
    assert "is ready!" in result.stdout
    assert (repo / ".env").exists()
    assert ["docker", "compose", "-f", "docker-compose.yml", "-f", "docker-compose.windows.yml", "up", "-d", "--build", "--remove-orphans"] in calls
    registered = json.loads((state / "registered.json").read_text())
    assert registered == ["mcp", "add", "nifi-universal", "--url", "http://localhost:8085/mcp"]
    assert (state / "installed-skills/nifi-flow-layout/SKILL.md").exists()


@pytest.mark.parametrize("failure", ["daemon", "compose", "build", "health"])
def test_install_stops_on_runtime_failure(installer, failure):
    result, calls, _, _ = installer(failure)
    assert result.returncode != 0
    assert "is ready!" not in result.stdout
    assert not any(call[:3] == ["codex", "mcp", "add"] for call in calls)
    if failure == "build":
        assert "Container started" not in result.stdout


@pytest.mark.parametrize("failure", ["codex-add", "codex-get"])
def test_codex_failure_is_reported_without_failing_gateway_install(installer, failure):
    result, calls, _, _ = installer(failure)
    assert result.returncode == 0, result.stderr
    assert "Codex registration failed" in result.stdout
    assert "Registered 'nifi-universal'" not in result.stdout
    if failure == "codex-add":
        assert not any(call[:3] == ["codex", "mcp", "get"] for call in calls)


def test_install_succeeds_without_codex(installer):
    result, calls, _, state = installer("missing-codex")
    assert result.returncode == 0, result.stderr
    assert "codex CLI not found" in result.stdout
    assert not any(call[0] == "codex" for call in calls)
    assert (state / "installed-skills/nifi-flow-layout/SKILL.md").exists()


@pytest.mark.parametrize("exported", [False, True])
def test_existing_auth_and_port_are_preserved(installer, exported):
    value = "synthetic-installer-test-value"
    original = f"NIFI_MCP_PORT=18085\nNIFI_MCP_API_KEY={value}\n"
    result, calls, repo, state = installer(existing_env=original, api_key=value if exported else "")
    assert result.returncode == 0, result.stderr
    assert (repo / ".env").read_text() == original
    assert value not in result.stdout + result.stderr
    if exported:
        registered = json.loads((state / "registered.json").read_text())
        assert registered[-2:] == ["--bearer-token-env-var", "NIFI_MCP_API_KEY"]
        assert "http://localhost:18085/mcp" in registered
    else:
        assert "Skipping Codex registration" in result.stdout
        assert not any(call[:3] == ["codex", "mcp", "remove"] for call in calls)
