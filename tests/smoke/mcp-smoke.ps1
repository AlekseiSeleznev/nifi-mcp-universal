#requires -Version 7.0

$ErrorActionPreference = "Stop"

function Resolve-ProjectRoot {
    $scriptRoot = Split-Path -Parent $PSCommandPath
    return (Resolve-Path (Join-Path $scriptRoot ".." "..")).Path
}

function Get-HeaderValue {
    param(
        [Parameter(Mandatory = $true)] $Headers,
        [Parameter(Mandatory = $true)] [string] $Name
    )

    foreach ($key in $Headers.Keys) {
        if ([string]::Equals([string]$key, $Name, [System.StringComparison]::OrdinalIgnoreCase)) {
            $value = $Headers[$key]
            if ($value -is [array]) {
                return [string]$value[0]
            }
            return [string]$value
        }
    }
    return $null
}

function ConvertFrom-McpBody {
    param([Parameter(Mandatory = $true)] [string] $Body)

    if ($Body.TrimStart().StartsWith("event:")) {
        $dataLines = @()
        foreach ($line in ($Body -split "`r?`n")) {
            if ($line.StartsWith("data:")) {
                $dataLines += $line.Substring(5).Trim()
            }
        }
        if ($dataLines.Count -eq 0) {
            throw "MCP SSE response did not contain data lines"
        }
        return ($dataLines[-1] | ConvertFrom-Json -Depth 100)
    }

    return ($Body | ConvertFrom-Json -Depth 100)
}

function Test-Health {
    param([Parameter(Mandatory = $true)] [string] $HealthUrl)

    try {
        $response = Invoke-RestMethod -Uri $HealthUrl -Method Get -TimeoutSec 3
        return ($response.status -eq "ok")
    } catch {
        return $false
    }
}

function Wait-Health {
    param(
        [Parameter(Mandatory = $true)] [string] $HealthUrl,
        [int] $TimeoutSeconds = 30
    )

    $deadline = [DateTimeOffset]::UtcNow.AddSeconds($TimeoutSeconds)
    while ([DateTimeOffset]::UtcNow -lt $deadline) {
        if (Test-Health -HealthUrl $HealthUrl) {
            return
        }
        Start-Sleep -Milliseconds 500
    }
    throw "Gateway health endpoint did not become ready: $HealthUrl"
}

function Find-Python {
    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($null -ne $python) {
        return $python.Source
    }

    $python3 = Get-Command python3 -ErrorAction SilentlyContinue
    if ($null -ne $python3) {
        return $python3.Source
    }

    throw "python/python3 is unavailable; cannot start local gateway"
}

function Start-LocalGateway {
    param(
        [Parameter(Mandatory = $true)] [string] $ProjectRoot,
        [Parameter(Mandatory = $true)] [string] $Port
    )

    $pythonExe = Find-Python
    $gatewayDir = Join-Path $ProjectRoot "gateway"
    $stateDir = Join-Path ([System.IO.Path]::GetTempPath()) ("nifi-mcp-smoke-" + [System.Guid]::NewGuid().ToString("N"))
    New-Item -Path $stateDir -ItemType Directory -Force | Out-Null
    $stateFile = Join-Path $stateDir "nifi_state.json"

    $psi = [System.Diagnostics.ProcessStartInfo]::new()
    $psi.FileName = $pythonExe
    $psi.WorkingDirectory = $gatewayDir
    $psi.UseShellExecute = $false
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.ArgumentList.Add("-m")
    $psi.ArgumentList.Add("gateway")
    $psi.Environment["NIFI_MCP_PORT"] = $Port
    $psi.Environment["NIFI_MCP_STATE_FILE"] = $stateFile
    $psi.Environment["NIFI_MCP_API_KEY"] = ""
    $psi.Environment["NIFI_MCP_NIFI_API_BASE"] = ""
    $psi.Environment["NIFI_MCP_LOG_LEVEL"] = "INFO"

    $process = [System.Diagnostics.Process]::Start($psi)
    if ($null -eq $process) {
        throw "Failed to start local gateway process"
    }

    return @{
        Process = $process
        StateDir = $stateDir
    }
}

function Stop-LocalGateway {
    param($Gateway)

    if ($null -eq $Gateway) {
        return
    }

    $process = $Gateway.Process
    if ($null -ne $process -and -not $process.HasExited) {
        $process.Kill($true)
        $process.WaitForExit(5000) | Out-Null
    }

    if ($Gateway.StateDir -and (Test-Path $Gateway.StateDir)) {
        Remove-Item -LiteralPath $Gateway.StateDir -Recurse -Force -ErrorAction SilentlyContinue
    }
}

function Invoke-McpJsonRpc {
    param(
        [Parameter(Mandatory = $true)] [string] $McpUrl,
        [Parameter(Mandatory = $true)] [string] $Method,
        [object] $Params = $null,
        [string] $SessionId = $null,
        [string] $ApiKey = $null,
        [object] $Id = 1
    )

    $headers = @{
        "Accept" = "application/json, text/event-stream"
        "Content-Type" = "application/json"
    }
    if ($SessionId) {
        $headers["Mcp-Session-Id"] = $SessionId
    }
    if ($ApiKey) {
        $headers["Authorization"] = "Bearer $ApiKey"
    }

    $payload = [ordered]@{
        jsonrpc = "2.0"
        method = $Method
    }
    if ($null -ne $Id) {
        $payload.id = $Id
    }
    if ($null -ne $Params) {
        $payload.params = $Params
    }

    $body = $payload | ConvertTo-Json -Depth 100 -Compress
    $response = Invoke-WebRequest -Uri $McpUrl -Method Post -Headers $headers -Body $body -TimeoutSec 15

    if ($null -eq $Id) {
        return @{
            Response = $null
            SessionId = (Get-HeaderValue -Headers $response.Headers -Name "mcp-session-id")
            StatusCode = [int]$response.StatusCode
        }
    }

    return @{
        Response = (ConvertFrom-McpBody -Body $response.Content)
        SessionId = (Get-HeaderValue -Headers $response.Headers -Name "mcp-session-id")
        StatusCode = [int]$response.StatusCode
    }
}

$projectRoot = Resolve-ProjectRoot
$mcpUrl = if ($env:MCP_URL) { $env:MCP_URL } else { "http://localhost:8085/mcp" }
$healthUrl = if ($env:HEALTH_URL) { $env:HEALTH_URL } else { "http://localhost:8085/health" }
$apiKey = if ($env:NIFI_MCP_API_KEY) { $env:NIFI_MCP_API_KEY } else { $null }
$localGateway = $null

try {
    if (-not (Test-Health -HealthUrl $healthUrl)) {
        $uri = [System.Uri]$mcpUrl
        if (-not ($uri.Host -in @("localhost", "127.0.0.1", "::1"))) {
            throw "MCP_URL is not local and health is unavailable; refusing to start a local replacement for $mcpUrl"
        }

        $port = if ($uri.Port -gt 0) { [string]$uri.Port } else { "8085" }
        Write-Host "Gateway is not ready; starting local safe gateway on port $port"
        $localGateway = Start-LocalGateway -ProjectRoot $projectRoot -Port $port
        Wait-Health -HealthUrl $healthUrl -TimeoutSeconds 30
    }

    Write-Host "Health OK: $healthUrl"

    $initializeParams = @{
        protocolVersion = "2025-06-18"
        capabilities = @{}
        clientInfo = @{
            name = "nifi-mcp-pwsh-smoke"
            version = "0.1.0"
        }
    }
    $init = Invoke-McpJsonRpc -McpUrl $mcpUrl -Method "initialize" -Params $initializeParams -ApiKey $apiKey -Id 1
    if ($null -ne $init.Response.error) {
        throw "initialize returned error: $($init.Response.error | ConvertTo-Json -Depth 20 -Compress)"
    }
    if ($init.Response.result.serverInfo.name -ne "nifi-mcp-universal") {
        throw "Unexpected MCP server name: $($init.Response.result.serverInfo.name)"
    }

    $sessionId = $init.SessionId
    if (-not $sessionId) {
        throw "initialize response did not include Mcp-Session-Id"
    }
    Write-Host "MCP initialize OK"

    [void](Invoke-McpJsonRpc -McpUrl $mcpUrl -Method "notifications/initialized" -SessionId $sessionId -ApiKey $apiKey -Id $null)

    $tools = Invoke-McpJsonRpc -McpUrl $mcpUrl -Method "tools/list" -Params @{} -SessionId $sessionId -ApiKey $apiKey -Id 2
    if ($null -ne $tools.Response.error) {
        throw "tools/list returned error: $($tools.Response.error | ConvertTo-Json -Depth 20 -Compress)"
    }

    $toolNames = @($tools.Response.result.tools | ForEach-Object { $_.name })
    foreach ($required in @("list_nifi_connections", "connect_nifi", "get_root_process_group")) {
        if ($toolNames -notcontains $required) {
            throw "tools/list did not include required tool '$required'"
        }
    }

    Write-Host "MCP tools/list OK: $($toolNames.Count) tools"
} finally {
    Stop-LocalGateway -Gateway $localGateway
}
