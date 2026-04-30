from __future__ import annotations

import shutil
import subprocess
import sys
import os
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def test_bundled_nifi_flow_layout_skill_assets_exist_and_are_universal():
    repo = _repo_root()
    skill = repo / "skills" / "nifi-flow-layout"

    assert (skill / "SKILL.md").exists()
    assert (skill / "scripts" / "nifi_layout.py").exists()
    assert (skill / "scripts" / "nifi_visual_check.cjs").exists()
    assert (skill / "references" / "layout-rules.md").exists()

    combined = "\n".join(
        path.read_text(encoding="utf-8")
        for path in [
            skill / "SKILL.md",
            skill / "scripts" / "nifi_layout.py",
            skill / "scripts" / "nifi_visual_check.cjs",
            skill / "references" / "layout-rules.md",
            repo / "docs" / "nifi-flow-layout.md",
        ]
    )
    for forbidden in ("PUIG", "puig", "178.236", "nifi-claas"):
        assert forbidden not in combined

    assert "Processor: `350x130`" in combined
    assert "Connection label width: `240`" in combined
    assert "Playwright is required" in combined


def test_bundled_nifi_layout_self_test_passes():
    script = _repo_root() / "skills" / "nifi-flow-layout" / "scripts" / "nifi_layout.py"

    result = subprocess.run(
        [sys.executable, str(script), "--mode", "self-test"],
        cwd=_repo_root(),
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "self-test ok" in result.stdout


def test_codex_skill_installer_copies_skill_and_installed_self_test_passes(tmp_path: Path):
    repo = _repo_root()
    target_root = tmp_path / "codex-skills"
    env = {**os.environ, "HOME": str(tmp_path), "CODEX_SKILLS_DIR": str(target_root)}

    if sys.platform == "win32":
        pwsh = shutil.which("pwsh") or shutil.which("powershell")
        assert pwsh, "PowerShell is required to test install-codex-skills.ps1 on Windows"
        cmd = [pwsh, "-NoLogo", "-NoProfile", "-File", str(repo / "tools" / "install-codex-skills.ps1")]
    else:
        bash = shutil.which("bash")
        assert bash, "bash is required to test install-codex-skills.sh"
        cmd = [bash, str(repo / "tools" / "install-codex-skills.sh")]

    result = subprocess.run(
        cmd,
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    installed = target_root / "nifi-flow-layout"
    assert (installed / "SKILL.md").exists()

    self_test = subprocess.run(
        [sys.executable, str(installed / "scripts" / "nifi_layout.py"), "--mode", "self-test"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    assert self_test.returncode == 0, self_test.stderr


def test_visual_check_script_syntax_when_node_is_available():
    node = shutil.which("node")
    if not node:
        return

    script = _repo_root() / "skills" / "nifi-flow-layout" / "scripts" / "nifi_visual_check.cjs"
    result = subprocess.run(
        [node, "--check", str(script)],
        cwd=_repo_root(),
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
