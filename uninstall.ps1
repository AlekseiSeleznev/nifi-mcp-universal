$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $RepoRoot

$ImageName = "nifi-mcp-gateway"
$LogPath = Join-Path $env:TEMP "nifi-mcp-docker-autostart.log"

function Write-Ok([string]$Message) { Write-Host "[+] $Message" }
function Write-Info([string]$Message) { Write-Host "[i] $Message" }
function Write-Warn([string]$Message) { Write-Host "[!] $Message" }

Write-Host ""
Write-Host "=== Removing nifi-mcp-universal runtime artifacts ==="

$codexCmd = Get-Command codex -ErrorAction SilentlyContinue
if ($null -ne $codexCmd) {
    try { & codex mcp remove nifi-universal *> $null } catch {}
    Write-Ok "Removed local Codex registration (if it existed)"
} else {
    Write-Info "codex CLI not found — skipping Codex cleanup"
}

$dockerCmd = Get-Command docker -ErrorAction SilentlyContinue
if ($null -ne $dockerCmd) {
    & docker compose version *> $null
    if ($LASTEXITCODE -eq 0) {
        if (Test-Path "docker-compose.override.yml") {
            & docker compose down -v --remove-orphans --rmi local *> $null
        } else {
            & docker compose -f docker-compose.yml -f docker-compose.windows.yml down -v --remove-orphans --rmi local *> $null
        }
        & docker image rm $ImageName *> $null
        Write-Ok "Removed project Docker resources (container, volume, local image)"
    } else {
        Write-Warn "docker compose is unavailable — skipping Docker cleanup"
    }
} else {
    Write-Warn "docker is unavailable — skipping Docker cleanup"
}

if (Test-Path "docker-compose.override.yml") {
    $overrideText = Get-Content "docker-compose.override.yml" -Raw
    if ($overrideText.StartsWith("# Auto-generated for ")) {
        Remove-Item "docker-compose.override.yml" -Force
        Write-Ok "Removed generated docker-compose.override.yml"
    }
}

if (Test-Path $LogPath) {
    Remove-Item $LogPath -Force -ErrorAction SilentlyContinue
    Write-Ok "Removed Windows autostart log file"
}

Write-Host ""
Write-Host "Project-scoped cleanup completed."
Write-Host "If you want to remove the repository directory too, delete it manually after this script exits."
Write-Host ""
