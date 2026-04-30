$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $RepoRoot

$DefaultPort = 8085
$ServerName = "nifi-universal"
$ServiceName = "nifi-mcp-universal"
$SetupCI = if ($env:MCP_SETUP_CI) { $env:MCP_SETUP_CI } else { "0" }
$CodexRegistered = $false
$CodexSkipped = $false

function Write-Ok([string]$Message) { Write-Host "[+] $Message" }
function Write-Info([string]$Message) { Write-Host "[i] $Message" }
function Write-Warn([string]$Message) { Write-Host "[!] $Message" }
function Fail([string]$Message) { throw $Message }

function Get-EnvValue([string]$Key, [string]$Path) {
    if (-not (Test-Path $Path)) { return "" }
    $line = Get-Content $Path | Where-Object { $_ -match "^${Key}=" } | Select-Object -First 1
    if (-not $line) { return "" }
    return $line.Substring($Key.Length + 1)
}

function Ensure-EnvKey([string]$Key, [string]$Path) {
    if (-not (Test-Path $Path)) { return }
    $existing = Get-Content $Path | Where-Object { $_ -match "^${Key}=" } | Select-Object -First 1
    if (-not $existing) {
        Add-Content -Path $Path -Value "${Key}="
    }
}

function Install-CodexSkills {
    $installer = Join-Path $RepoRoot "tools/install-codex-skills.ps1"
    if (Test-Path $installer) {
        Write-Host ""
        Write-Host "=== Installing bundled Codex skills ==="
        try {
            & $installer
            Write-Ok "Bundled Codex skills installed"
        } catch {
            Write-Warn "Bundled Codex skill installation failed. Gateway install will continue."
            Write-Warn "Run manually later: .\\tools\\install-codex-skills.ps1"
        }
    } else {
        Write-Warn "tools/install-codex-skills.ps1 not found — skipping Codex skill installation"
    }
}

Write-Host ""
Write-Host "=== Checking prerequisites ==="

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Fail "Docker not found. Install Docker Desktop and try again."
}
Write-Ok "docker found: $((docker --version | Select-Object -First 1))"

docker info *> $null
if ($LASTEXITCODE -ne 0) {
    Fail "Docker daemon is not running. Start Docker Desktop and try again."
}
Write-Ok "Docker daemon is running"

docker compose version *> $null
if ($LASTEXITCODE -ne 0) {
    Fail "Docker Compose v2 not found. This setup requires 'docker compose' (v2)."
}
Write-Ok "docker compose v2 found"

$codexCmd = Get-Command codex -ErrorAction SilentlyContinue
if ($null -ne $codexCmd) {
    Write-Ok "codex CLI found: $((codex --version | Select-Object -First 1))"
} else {
    Write-Warn "codex CLI not found — gateway installation will continue without MCP auto-registration."
    Write-Warn "Use CODEX.md for optional Codex registration or AGENTS.md for any other MCP client."
}

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Ok "Created .env from .env.example"
} else {
    Write-Info ".env already exists, keeping it"
}

Ensure-EnvKey "NIFI_MCP_API_KEY" ".env"

$Port = Get-EnvValue "NIFI_MCP_PORT" ".env"
if (-not $Port) { $Port = "$DefaultPort" }
$ApiKey = Get-EnvValue "NIFI_MCP_API_KEY" ".env"
if ($ApiKey) {
    Write-Info "Using existing NIFI_MCP_API_KEY from .env"
} else {
    Write-Ok "MCP/dashboard bearer auth is disabled by default (NIFI_MCP_API_KEY is empty)"
}

Write-Host ""
Write-Host "=== Building and starting container ==="
docker compose -f docker-compose.yml -f docker-compose.windows.yml up -d --build --remove-orphans
Write-Ok "Container started"

Write-Host ""
Write-Host "=== Waiting for gateway to be healthy ==="
$Healthy = $false
for ($i = 0; $i -lt 30; $i++) {
    try {
        $resp = Invoke-WebRequest -Uri "http://localhost:$Port/health" -UseBasicParsing -TimeoutSec 2
        if ($resp.StatusCode -eq 200) {
            $Healthy = $true
            break
        }
    } catch {}
    Start-Sleep -Seconds 1
}

if (-not $Healthy) {
    Write-Warn "Gateway not healthy after 30s."
    Write-Warn "Check logs: docker compose -f docker-compose.yml -f docker-compose.windows.yml logs nifi-mcp-gateway"
    exit 1
}
Write-Ok "Gateway is healthy on port $Port"

if ($SetupCI -ne "1" -and (Test-Path "tools/ensure-docker-autostart-windows.ps1")) {
    Write-Info "Ensuring Docker Desktop is set to start at login..."
    try {
        & powershell -ExecutionPolicy Bypass -File "tools/ensure-docker-autostart-windows.ps1" *> $null
        Write-Ok "Docker Desktop autostart configured"
    } catch {
        Write-Warn "Could not configure Docker Desktop autostart automatically."
        Write-Warn "Please enable it manually in Docker Desktop settings."
    }
}

if ($null -ne $codexCmd) {
    if ($ApiKey -and $env:NIFI_MCP_API_KEY -ne $ApiKey) {
        Write-Warn "NIFI_MCP_API_KEY is set in .env, but the same value is not exported in the current shell."
        Write-Warn "Skipping Codex registration for the authenticated MCP endpoint."
        $CodexSkipped = $true
    } else {
        try { & codex mcp remove $ServerName *> $null } catch {}
        try {
            if ($ApiKey) {
                & codex mcp add $ServerName --url "http://localhost:$Port/mcp" --bearer-token-env-var NIFI_MCP_API_KEY
            } else {
                & codex mcp add $ServerName --url "http://localhost:$Port/mcp"
            }
            & codex mcp get $ServerName --json *> $null
            $CodexRegistered = $true
            Write-Ok "Registered '$ServerName' in Codex"
        } catch {
            $CodexSkipped = $true
            Write-Warn "Codex registration failed. Gateway install completed; see CODEX.md for manual registration."
        }
    }
}

Install-CodexSkills

Write-Host ""
Write-Host "============================================"
Write-Host " nifi-mcp-universal is ready!"
Write-Host "============================================"
Write-Host ""
Write-Host "  Dashboard:  http://localhost:$Port/dashboard"
Write-Host "  Health:     http://localhost:$Port/health"
Write-Host "  MCP URL:    http://localhost:$Port/mcp"
Write-Host ""
Write-Host "Next steps:"
Write-Host "  1. Open the Dashboard and add your first NiFi connection"
Write-Host "  2. Use AGENTS.md for generic MCP client onboarding"
Write-Host "  3. Use CODEX.md for optional Codex registration, skills, and cleanup"
if ($CodexRegistered) {
    Write-Host "  4. Verify Codex registration: codex mcp get $ServerName --json"
} elseif ($CodexSkipped -or $null -ne $codexCmd) {
    Write-Host "  4. Codex registration was skipped or needs manual follow-up; see CODEX.md"
}
Write-Host "  5. Skill self-test: python3 ~/.codex/skills/nifi-flow-layout/scripts/nifi_layout.py --mode self-test"
Write-Host ""
