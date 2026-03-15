#Requires -Version 7.0
<#
.SYNOPSIS
    Stop AI-SOC-Brain services.
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Continue'

$ProjectRoot = Split-Path -Parent $PSScriptRoot

function Write-Step([string]$msg) { Write-Host "  ► $msg" -ForegroundColor Cyan }
function Write-OK([string]$msg)   { Write-Host "  ✓ $msg" -ForegroundColor Green }
function Write-Warn([string]$msg) { Write-Host "  ⚠ $msg" -ForegroundColor Yellow }

Write-Host ""
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host "  AI-SOC-Brain  |  Stopping services" -ForegroundColor White
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host ""

# Stop FastAPI backend
Write-Step "Stopping FastAPI backend"
$backendPid = Join-Path $ProjectRoot '.backend.pid'
if (Test-Path $backendPid) {
    $pid = Get-Content $backendPid -ErrorAction SilentlyContinue
    if ($pid -and (Get-Process -Id $pid -ErrorAction SilentlyContinue)) {
        Stop-Process -Id $pid -Force
        Write-OK "Backend stopped (PID $pid)"
    } else {
        Write-Warn "Backend process not found (PID $pid)"
    }
    Remove-Item $backendPid -Force
} else {
    # Try to find by port
    $procs = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
    if ($procs) {
        foreach ($p in $procs) {
            Stop-Process -Id $p.OwningProcess -Force -ErrorAction SilentlyContinue
            Write-OK "Killed process on port 8000 (PID $($p.OwningProcess))"
        }
    } else {
        Write-Warn "No backend process found"
    }
}

# Stop Caddy
Write-Step "Stopping Caddy (Docker)"
Push-Location $ProjectRoot
docker compose down 2>&1 | Out-Null
Pop-Location
Write-OK "Caddy stopped"

Write-Host ""
Write-Host "  All services stopped." -ForegroundColor Green
Write-Host ""
