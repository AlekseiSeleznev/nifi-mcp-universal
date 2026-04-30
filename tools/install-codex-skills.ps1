$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$SkillName = "nifi-flow-layout"
$SourceDir = Join-Path $RepoRoot "skills/$SkillName"

if ($env:CODEX_SKILLS_DIR) {
    $TargetRoot = $env:CODEX_SKILLS_DIR
} else {
    $TargetRoot = Join-Path $HOME ".codex/skills"
}
$TargetDir = Join-Path $TargetRoot $SkillName
$TmpDir = Join-Path $TargetRoot (".$SkillName.tmp." + [System.Guid]::NewGuid().ToString("N"))

if (-not (Test-Path $SourceDir -PathType Container)) {
    throw "Bundled skill not found: $SourceDir"
}
if (-not (Test-Path (Join-Path $SourceDir "SKILL.md") -PathType Leaf)) {
    throw "Bundled skill is missing SKILL.md: $SourceDir"
}

New-Item -Path $TargetRoot -ItemType Directory -Force | Out-Null
if (Test-Path $TmpDir) { Remove-Item -LiteralPath $TmpDir -Recurse -Force }
New-Item -Path $TmpDir -ItemType Directory -Force | Out-Null
Copy-Item -Path (Join-Path $SourceDir "*") -Destination $TmpDir -Recurse -Force
if (Test-Path $TargetDir) { Remove-Item -LiteralPath $TargetDir -Recurse -Force }
Move-Item -LiteralPath $TmpDir -Destination $TargetDir

Write-Host "[+] Installed Codex skill '$SkillName' to $TargetDir"
Write-Host "[+] Self-test: python3 $TargetDir/scripts/nifi_layout.py --mode self-test"
