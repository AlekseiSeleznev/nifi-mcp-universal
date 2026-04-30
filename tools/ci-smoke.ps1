$ErrorActionPreference = "Stop"

$pythonCmd = Get-Command python -ErrorAction SilentlyContinue
if ($null -ne $pythonCmd) {
    $pythonExe = "python"
} else {
    $python3Cmd = Get-Command python3 -ErrorAction SilentlyContinue
    if ($null -ne $python3Cmd) {
        $pythonExe = "python3"
    } else {
        throw "python/python3 is unavailable; cannot run compileall smoke check"
    }
}

& $pythonExe -m compileall -q gateway
& $pythonExe skills/nifi-flow-layout/scripts/nifi_layout.py --mode self-test

$bashCmd = Get-Command bash -ErrorAction SilentlyContinue
if ($null -ne $bashCmd) {
    bash -n setup.sh
    bash -n uninstall.sh
    bash -n tools/install-codex-skills.sh
} else {
    Write-Host "bash is unavailable; skipping setup.sh syntax check"
}

[void][scriptblock]::Create((Get-Content -Raw "install.ps1"))
[void][scriptblock]::Create((Get-Content -Raw "uninstall.ps1"))
[void][scriptblock]::Create((Get-Content -Raw "tools/install-codex-skills.ps1"))

if (-not (Test-Path ".env")) {
    if (Test-Path ".env.example") {
        Copy-Item ".env.example" ".env"
    } else {
        New-Item -Path ".env" -ItemType File -Force | Out-Null
    }
}

$dockerCmd = Get-Command docker -ErrorAction SilentlyContinue
if ($null -ne $dockerCmd) {
    & docker compose version *> $null
    if ($LASTEXITCODE -eq 0) {
        & docker compose -f docker-compose.yml config -q
        & docker compose -f docker-compose.yml -f docker-compose.windows.yml config -q
    } else {
        Write-Host "docker compose is unavailable on this runner; skipping compose config smoke checks"
    }
} else {
    Write-Host "docker is unavailable on this runner; skipping compose config smoke checks"
}
