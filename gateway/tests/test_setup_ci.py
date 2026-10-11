"""Exercise the real POSIX installer with isolated external commands."""
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys

import pytest

pytestmark = pytest.mark.skipif(sys.platform == "win32" or not shutil.which("bash"), reason="POSIX command stubs require a POSIX host")


def run_setup(tmp_path, platform="Linux", fail_build=False):
    root = Path(__file__).resolve().parents[2]
    repo = tmp_path / "repo with spaces"
    repo.mkdir()
    shutil.copy2(root / "setup.sh", repo)
    shutil.copy2(root / ".env.example", repo)
    shutil.copy2(root / "docker-compose.yml", repo)
    commands = tmp_path / "bin"
    commands.mkdir()
    state = tmp_path / "calls.jsonl"
    stub = tmp_path / "external.py"
    stub.write_text('''import json, os, sys
name, *args = sys.argv[1:]
with open(os.environ["SETUP_TEST_CALLS"], "a") as out:
    out.write(json.dumps([name, *args]) + "\\n")
if name == "uname":
    print(os.environ["SETUP_TEST_PLATFORM"])
elif name == "docker":
    if args[:2] == ["buildx", "bake"] and os.environ["SETUP_TEST_FAIL"] == "1":
        sys.exit(7)
    if args == ["--version"] or args == ["compose", "version"]:
        print("test version")
elif name == "curl":
    print("{}")
''')
    for name in ("docker", "curl", "codex", "uname", "sleep"):
        command = commands / name
        command.write_text(f"#!/bin/sh\nexec {shlex.quote(sys.executable)} {shlex.quote(str(stub))} {name} \"$@\"\n")
        command.chmod(0o755)
    env = os.environ.copy()
    env.update(PATH=str(commands) + os.pathsep + env["PATH"], MCP_SETUP_CI="1", SETUP_TEST_CALLS=str(state), SETUP_TEST_PLATFORM=platform, SETUP_TEST_FAIL=str(int(fail_build)), NIFI_MCP_API_KEY="")
    result = subprocess.run([shutil.which("bash"), str(repo / "setup.sh")], env=env, cwd=repo, text=True, capture_output=True, timeout=15)
    calls = [json.loads(line) for line in state.read_text().splitlines()]
    return result, calls


def test_linux_ci_grants_only_host_network_before_start(tmp_path):
    result, calls = run_setup(tmp_path)
    assert result.returncode == 0, result.stderr
    build = ["docker", "buildx", "bake", "-f", "docker-compose.yml", "--allow=network.host", "--load", "gateway"]
    start = ["docker", "compose", "up", "-d", "--no-build", "--remove-orphans"]
    assert calls.count(build) == calls.count(start) == 1
    assert calls.index(build) < calls.index(start)
    assert not any(call[:3] == ["docker", "compose", "up"] and "--build" in call for call in calls)
    assert not any("security.insecure" in item for call in calls for item in call)


def test_linux_ci_build_failure_never_starts_gateway(tmp_path):
    result, calls = run_setup(tmp_path, fail_build=True)
    assert result.returncode == 7
    assert not any(call[:3] == ["docker", "compose", "up"] for call in calls)
    assert not any(call[:3] == ["codex", "mcp", "add"] for call in calls)


@pytest.mark.parametrize("platform", ["Darwin", "MINGW64_NT"])
def test_non_linux_installer_keeps_compose_build_path(tmp_path, platform):
    result, calls = run_setup(tmp_path, platform=platform)
    assert result.returncode == 0, result.stderr
    assert ["docker", "compose", "up", "-d", "--build", "--remove-orphans"] in calls
    assert not any(call[:3] == ["docker", "buildx", "bake"] for call in calls)
