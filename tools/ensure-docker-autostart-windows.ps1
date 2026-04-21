#Requires -Version 5.1
<#
.SYNOPSIS
    Ensures Docker Desktop is configured to start automatically at Windows login.

.DESCRIPTION
    nifi-mcp-universal runs entirely inside Docker containers (restart: always).
    If Docker Desktop does not start at login, the gateway container will not
    come back after a reboot.

    This script:
      1. Verifies Docker Desktop is installed.
      2. Adds (or updates) the "Docker Desktop" autostart entry in:
         HKCU:\Software\Microsoft\Windows\CurrentVersion\Run
      3. Optionally starts Docker Desktop right now if it is not running.

    Called automatically by setup.sh on Windows install.
    Safe to re-run at any time (idempotent).

.PARAMETER StartNow
    If specified, starts Docker Desktop immediately when it is not running.
    Default: $true

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File tools\ensure-docker-autostart-windows.ps1
    powershell -ExecutionPolicy Bypass -File tools\ensure-docker-autostart-windows.ps1 -StartNow $false
#>
param(
    [bool]$StartNow = $true
)

$ErrorActionPreference = "Stop"
$LogPrefix = "[nifi-mcp-universal]"

function Write-Log {
    param([string]$Message, [string]$Level = "INFO")
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "$timestamp [$Level] $LogPrefix $Message"
    Write-Host $line
    # Also append to temp log for diagnostics
    $logFile = Join-Path $env:TEMP "nifi-mcp-docker-autostart.log"
    try { Add-Content -Path $logFile -Value $line -ErrorAction SilentlyContinue } catch {}
}

# ── 1. Locate Docker Desktop executable ──────────────────────────────────────

$dockerDesktopPaths = @(
    "$env:ProgramFiles\Docker\Docker\Docker Desktop.exe",
    "${env:ProgramFiles(x86)}\Docker\Docker\Docker Desktop.exe",
    "$env:LOCALAPPDATA\Programs\Docker\Docker\Docker Desktop.exe"
)

$dockerDesktopExe = $null
foreach ($path in $dockerDesktopPaths) {
    if (Test-Path $path) {
        $dockerDesktopExe = $path
        break
    }
}

if (-not $dockerDesktopExe) {
    Write-Log "Docker Desktop not found in standard locations." "WARN"
    Write-Log "Searched:" "WARN"
    $dockerDesktopPaths | ForEach-Object { Write-Log "  $_" "WARN" }
    Write-Log "Install Docker Desktop from https://www.docker.com/products/docker-desktop/" "WARN"
    Write-Log "Then re-run this script." "WARN"
    exit 1
}

Write-Log "Docker Desktop found: $dockerDesktopExe"

# ── 2. Add / update autostart registry entry ─────────────────────────────────

$regPath = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"
$regKey  = "Docker Desktop"
$regValue = "`"$dockerDesktopExe`""

try {
    $existing = Get-ItemProperty -Path $regPath -Name $regKey -ErrorAction SilentlyContinue
    if ($existing) {
        $currentValue = $existing.$regKey
        if ($currentValue -eq $regValue) {
            Write-Log "Autostart entry already correct — no changes needed."
        } else {
            Set-ItemProperty -Path $regPath -Name $regKey -Value $regValue
            Write-Log "Autostart entry updated (was: $currentValue)."
        }
    } else {
        New-ItemProperty -Path $regPath -Name $regKey -Value $regValue -PropertyType String -Force | Out-Null
        Write-Log "Autostart entry created: $regKey = $regValue"
    }
} catch {
    Write-Log "Failed to write registry entry: $_" "ERROR"
    Write-Log "Try running as the current user (not elevated admin) or set manually:" "ERROR"
    Write-Log "  Docker Desktop -> Settings -> General -> 'Start Docker Desktop when you log in'" "ERROR"
    exit 1
}

Write-Log "Docker Desktop will now start automatically at login."

# ── 3. Start Docker Desktop now if not running ───────────────────────────────

if ($StartNow) {
    $dockerRunning = $false
    try {
        $result = & docker info 2>&1
        if ($LASTEXITCODE -eq 0) {
            $dockerRunning = $true
        }
    } catch {}

    if ($dockerRunning) {
        Write-Log "Docker daemon is already running — nothing to start."
    } else {
        Write-Log "Docker daemon is not running. Starting Docker Desktop..."
        try {
            Start-Process -FilePath $dockerDesktopExe -WindowStyle Hidden
            Write-Log "Docker Desktop started. It may take 30-60 seconds to be ready."
            Write-Log "Run 'docker info' to check when the daemon is available."
        } catch {
            Write-Log "Could not start Docker Desktop automatically: $_" "WARN"
            Write-Log "Please start Docker Desktop manually from the Start Menu." "WARN"
        }
    }
}

Write-Log "Done."
exit 0
