#Requires -Version 7.0
<#
.SYNOPSIS
    Show AI-SOC-Brain service status.
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Continue'

$ProjectRoot = Split-Path -Parent $PSScriptRoot

function Check-Service([string]$name, [string]$url, [int]$timeout = 3) {
    try {
        $resp = Invoke-RestMethod -Uri $url -TimeoutSec $timeout -ErrorAction Stop
        $status = if ($resp.status) { $resp.status } else { "up" }
        Write-Host "  ✓ $name" -ForegroundColor Green -NoNewline
        Write-Host " — $status" -ForegroundColor Gray
        return $true
    } catch {
        Write-Host "  ✗ $name" -ForegroundColor Red -NoNewline
        Write-Host " — not responding ($url)" -ForegroundColor DarkGray
        return $false
    }
}

Write-Host ""
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host "  AI-SOC-Brain  |  Service Status" -ForegroundColor White
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host ""

Check-Service "FastAPI Backend" "http://localhost:8000/health"
Check-Service "Ollama"          "http://localhost:11434"

# Check Docker / Caddy
try {
    $containers = docker ps --format "{{.Names}}\t{{.Status}}" 2>$null
    if ($containers -match "caddy") {
        Write-Host "  ✓ Caddy (Docker)" -ForegroundColor Green -NoNewline
        $caddyLine = ($containers -split "`n") | Where-Object { $_ -match "caddy" }
        Write-Host " — $($caddyLine -replace '^[^\t]+\t', '')" -ForegroundColor Gray
    } else {
        Write-Host "  ✗ Caddy (Docker)" -ForegroundColor Red -NoNewline
        Write-Host " — not running" -ForegroundColor DarkGray
    }
} catch {
    Write-Host "  ✗ Docker" -ForegroundColor Red -NoNewline
    Write-Host " — not available" -ForegroundColor DarkGray
}

# Check Ollama models
Write-Host ""
Write-Host "  Ollama models:" -ForegroundColor Gray
try {
    $models = & "C:\Users\Admin\AppData\Local\Programs\Ollama\ollama.exe" list 2>&1
    $lines = ($models -split "`n") | Where-Object { $_ -match '\S' } | Select-Object -Skip 1
    if ($lines) {
        foreach ($line in $lines) {
            Write-Host "    $line" -ForegroundColor Gray
        }
    } else {
        Write-Host "    (none pulled yet)" -ForegroundColor DarkGray
    }
} catch {
    Write-Host "    (ollama not in PATH)" -ForegroundColor DarkGray
}

# PID file
$backendPid = Join-Path $ProjectRoot '.backend.pid'
if (Test-Path $backendPid) {
    $pid = Get-Content $backendPid
    Write-Host ""
    Write-Host "  Backend PID: $pid" -ForegroundColor Gray
}

Write-Host ""
Write-Host "  Dashboard: https://localhost" -ForegroundColor Gray
Write-Host "  API Docs:  http://localhost:8000/docs" -ForegroundColor Gray
Write-Host ""
