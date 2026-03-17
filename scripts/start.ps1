#Requires -Version 7.0
<#
.SYNOPSIS
    Start AI-SOC-Brain services.
.DESCRIPTION
    Starts FastAPI backend (uvicorn) and Caddy Docker container.
    Ollama must be started separately (it runs as a Windows service/tray app).
#>

param(
    [switch]$SkipBuild,
    [switch]$DevMode
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$VenvPython  = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
$LogsDir     = Join-Path $ProjectRoot 'logs'
$DataDir     = Join-Path $ProjectRoot 'data'

function Write-Step([string]$msg) {
    Write-Host "  ► $msg" -ForegroundColor Cyan
}
function Write-OK([string]$msg) {
    Write-Host "  ✓ $msg" -ForegroundColor Green
}
function Write-Warn([string]$msg) {
    Write-Host "  ⚠ $msg" -ForegroundColor Yellow
}
function Write-Fail([string]$msg) {
    Write-Host "  ✗ $msg" -ForegroundColor Red
}

Write-Host ""
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host "  AI-SOC-Brain  |  Starting services" -ForegroundColor White
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host ""

# --- Pre-flight checks ---
Write-Step "Pre-flight checks"

if (-not (Test-Path $VenvPython)) {
    Write-Fail "Python venv not found at $VenvPython"
    Write-Host "  Run: uv venv --python 3.12 && uv pip install -e ." -ForegroundColor Gray
    exit 1
}
Write-OK "Python venv found"

# Ensure data dirs exist
New-Item -ItemType Directory -Force -Path $LogsDir | Out-Null
New-Item -ItemType Directory -Force -Path $DataDir | Out-Null
Write-OK "Data directories ready"

# Check Docker
try {
    $null = docker info 2>&1
    Write-OK "Docker running"
} catch {
    Write-Fail "Docker not running. Start Docker Desktop first."
    exit 1
}

# Check Ollama (non-fatal — backend degrades gracefully)
try {
    $ollamaResp = Invoke-RestMethod -Uri 'http://localhost:11434' -TimeoutSec 3 -ErrorAction SilentlyContinue
    Write-OK "Ollama running: $ollamaResp"
} catch {
    Write-Warn "Ollama not responding at localhost:11434 — AI features will be degraded"
    Write-Warn "Start Ollama: C:\Users\Admin\AppData\Local\Programs\Ollama\ollama.exe serve"
}

# --- Build dashboard (unless skipped) ---
$DashboardDist = Join-Path $ProjectRoot 'dashboard\dist\index.html'
if (-not $SkipBuild -and (Test-Path (Join-Path $ProjectRoot 'dashboard\package.json'))) {
    Write-Step "Building dashboard"
    Push-Location (Join-Path $ProjectRoot 'dashboard')
    try {
        npm run build 2>&1 | Out-Null
        if (Test-Path $DashboardDist) {
            Write-OK "Dashboard built → dashboard/dist/"
        } else {
            Write-Warn "Dashboard build may have failed (dist/index.html missing)"
        }
    } catch {
        Write-Warn "Dashboard build failed: $_"
    }
    Pop-Location
} elseif ($SkipBuild) {
    Write-OK "Dashboard build skipped (-SkipBuild)"
} else {
    Write-Warn "No dashboard/package.json found — skipping build"
}

# --- Start FastAPI backend ---
Write-Step "Starting FastAPI backend"

$backendLog = Join-Path $LogsDir 'backend-stdout.log'
$backendPid = Join-Path $ProjectRoot '.backend.pid'

# Kill existing if running
if (Test-Path $backendPid) {
    $oldPid = Get-Content $backendPid -ErrorAction SilentlyContinue
    if ($oldPid -and (Get-Process -Id $oldPid -ErrorAction SilentlyContinue)) {
        Write-Warn "Stopping existing backend process (PID $oldPid)"
        Stop-Process -Id $oldPid -Force -ErrorAction SilentlyContinue
        # Wait long enough for DuckDB to release its file lock on Windows.
        # Stop-Process -Force terminates immediately; the OS still holds the
        # file handle for a short window.  1.5 s is sufficient in practice.
        Start-Sleep -Milliseconds 1500
    }
    Remove-Item $backendPid -Force
}

if ($DevMode) {
    # Dev mode: visible window, local-only bind.
    # NOTE: --reload is intentionally OMITTED.  DuckDB requires a single
    # process (single-writer pattern); uvicorn --reload spawns a subprocess
    # that would open a second DuckDB connection and deadlock.
    $proc = Start-Process -FilePath $VenvPython -ArgumentList @(
        '-m', 'uvicorn', 'backend.main:app',
        '--host', '127.0.0.1', '--port', '8000',
        '--workers', '1', '--log-level', 'info'
    ) -WorkingDirectory $ProjectRoot -PassThru -WindowStyle Normal -RedirectStandardOutput $backendLog
} else {
    # Production mode: hidden window, local-only bind, single worker.
    # Use backend.main:app (module-level instance) — avoids double create_app()
    # that --factory would cause alongside the module-level app = create_app().
    $proc = Start-Process -FilePath $VenvPython -ArgumentList @(
        '-m', 'uvicorn', 'backend.main:app',
        '--host', '127.0.0.1', '--port', '8000',
        '--workers', '1', '--log-level', 'info'
    ) -WorkingDirectory $ProjectRoot -PassThru -WindowStyle Hidden -RedirectStandardOutput $backendLog
}

$proc.Id | Out-File $backendPid
Start-Sleep -Seconds 2

# Verify backend started
try {
    $health = Invoke-RestMethod -Uri 'http://localhost:8000/health' -TimeoutSec 5 -ErrorAction Stop
    Write-OK "Backend started (PID $($proc.Id)) — status: $($health.status)"
} catch {
    Write-Warn "Backend started but /health not yet responding — check logs\backend-stdout.log"
}

# --- Start Caddy via Docker Compose ---
Write-Step "Starting Caddy (Docker)"

Push-Location $ProjectRoot
try {
    docker compose up -d --wait 2>&1 | Out-Null
    Write-OK "Caddy started"
} catch {
    Write-Warn "Docker Compose failed: $_ — try: docker compose up -d"
}
Pop-Location

# --- Summary ---
Write-Host ""
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host "  Services started" -ForegroundColor Green
Write-Host ""
Write-Host "  Dashboard  → https://localhost" -ForegroundColor White
Write-Host "  Backend    → http://localhost:8000" -ForegroundColor White
Write-Host "  API docs   → http://localhost:8000/docs" -ForegroundColor White
Write-Host ""
Write-Host "  To stop:  .\scripts\stop.ps1" -ForegroundColor Gray
Write-Host "  Status:   .\scripts\status.ps1" -ForegroundColor Gray
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host ""
