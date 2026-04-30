import subprocess
from pathlib import Path

_ROOT_GUIDE = "CL" + "AUDE.md"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def test_ci_smoke_scripts_exist():
    repo = _repo_root()
    shell_script = repo / "tools" / "ci-smoke.sh"
    ps_script = repo / "tools" / "ci-smoke.ps1"
    catalog_generator = repo / "tools" / "generate_tool_catalog.py"
    catalog_doc = repo / "docs" / "mcp-tool-catalog.md"
    codex_doc = repo / "CODEX.md"
    agents_doc = repo / "AGENTS.md"
    install_ps = repo / "install.ps1"
    uninstall_sh = repo / "uninstall.sh"
    uninstall_ps = repo / "uninstall.ps1"
    skill_installer_sh = repo / "tools" / "install-codex-skills.sh"
    skill_installer_ps = repo / "tools" / "install-codex-skills.ps1"

    assert shell_script.exists()
    assert ps_script.exists()
    assert catalog_generator.exists()
    assert catalog_doc.exists()
    assert codex_doc.exists()
    assert agents_doc.exists()
    assert install_ps.exists()
    assert uninstall_sh.exists()
    assert uninstall_ps.exists()
    assert skill_installer_sh.exists()
    assert skill_installer_ps.exists()
    assert shell_script.read_text(encoding="utf-8").startswith("#!/usr/bin/env bash")
    assert skill_installer_sh.read_text(encoding="utf-8").startswith("#!/usr/bin/env bash")
    assert uninstall_sh.read_text(encoding="utf-8").startswith("#!/usr/bin/env bash")
    assert ps_script.stat().st_size > 0


def test_ci_workflow_uses_smoke_scripts():
    ci_workflow = (_repo_root() / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    assert "./tools/ci-smoke.sh" in ci_workflow
    assert "./tools/ci-smoke.ps1" in ci_workflow
    assert "./tests/smoke/mcp-smoke.ps1" in ci_workflow
    assert "--cov-fail-under=100" in ci_workflow


def test_dashboard_module_split_assets_exist():
    repo = _repo_root()
    web_ui = repo / "gateway" / "gateway" / "web_ui.py"
    web_ui_content = repo / "gateway" / "gateway" / "web_ui_content.py"
    dashboard_arch = repo / "docs" / "dashboard-architecture.md"
    dashboard_image = repo / "docs" / "images" / "nifi.png"

    assert web_ui_content.exists()
    assert dashboard_arch.exists()
    assert dashboard_image.exists()
    text = web_ui.read_text(encoding="utf-8")
    assert "from gateway.web_ui_content import DASHBOARD_HTML, _T, render_docs" in text


def test_tool_common_helpers_exist():
    repo = _repo_root()
    common_helpers = repo / "gateway" / "gateway" / "tools" / "common.py"
    assert common_helpers.exists()


def test_tool_service_modules_exist():
    repo = _repo_root()
    tools_dir = repo / "gateway" / "gateway" / "tools"
    assert (tools_dir / "read_service.py").exists()
    assert (tools_dir / "write_service.py").exists()


def test_legacy_guide_removed_and_runbooks_referenced():
    repo = _repo_root()

    readme = (repo / "README.md").read_text(encoding="utf-8")
    assert "CODEX.md" in readme
    assert "AGENTS.md" in readme
    assert "![Dashboard](docs/images/nifi.png)" in readme
    assert "English Quick Reference" not in readme
    assert "v1.0.0" in readme
    assert "Codex-first" not in readme
    assert readme.rstrip().endswith("## Лицензия\n\n[MIT](LICENSE)")


def test_repo_text_files_do_not_reference_legacy_branding():
    repo = _repo_root()
    allowed_suffixes = {".md", ".py", ".sh", ".yml", ".yaml", ".ps1"}
    offending = []
    legacy_brand = "Cl" "aude"
    legacy_brand_lower = legacy_brand.lower()

    # The client-specific root guide may retain brand-specific notes.
    # README.md and docs/* are treated as user-facing documentation.
    allow_list = {
        _ROOT_GUIDE, "README.md",
        "gateway/tests/test_ci_assets.py",
    }

    tracked_files = subprocess.run(
        ["git", "ls-files"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()

    for relative_path in tracked_files:
        if relative_path in allow_list:
            continue
        if relative_path.startswith("docs/"):
            continue
        path = repo / relative_path
        if path.suffix not in allowed_suffixes:
            continue
        text = path.read_text(encoding="utf-8")
        if legacy_brand in text or legacy_brand_lower in text:
            offending.append(relative_path)

    assert not offending, f"Unexpected legacy-brand references: {offending}"
