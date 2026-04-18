#Requires -Version 7.0
<#
.SYNOPSIS
    Lean service launcher — starts only what isn't already running.
.DESCRIPTION
    Called by the Windows Task Scheduler "AI-SOC-Brain Startup" task at logon.
    Checks each port / URL before starting so re-runs are safe (idempotent).
    Does NOT rebuild the dashboard.

    Services managed:
        8001  FastAPI backend  (uvicorn backend.main:app)
        8100  Reranker         (scripts\start_reranker.py)
        11434 Ollama           (ollama serve)
        80    Caddy            (docker compose up -d)
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Continue'    # non-fatal — log and continue on errors

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$VenvPython  = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
$LogsDir     = Join-Path $ProjectRoot 'logs'
$DataDir     = Join-Path $ProjectRoot 'data'
$LogFile     = Join-Path $LogsDir 'startup.log'

# Ensure directories exist
New-Item -ItemType Directory -Force -Path $LogsDir | Out-Null
New-Item -ItemType Directory -Force -Path $DataDir | Out-Null

function Write-Log([string]$msg) {
    $ts = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss')
    $line = "[$ts] $msg"
    Write-Host $line
    Add-Content -Path $LogFile -Value $line -Encoding UTF8
}

function Test-Port([int]$port) {
    try {
        $tcp = New-Object System.Net.Sockets.TcpClient
        $tcp.Connect('127.0.0.1', $port)
        $tcp.Close()
        return $true
    } catch {
        return $false
    }
}

function Test-Http([string]$url) {
    try {
        $null = Invoke-RestMethod -Uri $url -TimeoutSec 3 -ErrorAction Stop
        return $true
    } catch {
        return $false
    }
}

Write-Log "=== AI-SOC-Brain startup sequence begin ==="

# ---------------------------------------------------------------------------
# 1. Ollama
# ---------------------------------------------------------------------------
if (Test-Http 'http://localhost:11434') {
    Write-Log "Ollama: already running"
} else {
    Write-Log "Ollama: starting..."
    $ollamaExe = "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe"
    if (Test-Path $ollamaExe) {
        Start-Process -FilePath $ollamaExe -ArgumentList 'serve' -WindowStyle Hidden
        # Wait up to 20 s
        $deadline = (Get-Date).AddSeconds(20)
        while ((Get-Date) -lt $deadline -and -not (Test-Http 'http://localhost:11434')) {
            Start-Sleep -Seconds 2
        }
        if (Test-Http 'http://localhost:11434') {
            Write-Log "Ollama: started OK"
        } else {
            Write-Log "Ollama: did not respond within 20 s — AI features may be degraded"
        }
    } else {
        Write-Log "Ollama: binary not found at $ollamaExe — skipping"
    }
}

# ---------------------------------------------------------------------------
# 2. FastAPI backend (port 8001)
# ---------------------------------------------------------------------------
if (Test-Port 8001) {
    Write-Log "Backend: already running on port 8001"
} else {
    Write-Log "Backend: starting on port 8001..."
    if (-not (Test-Path $VenvPython)) {
        Write-Log "Backend: ERROR — venv not found at $VenvPython"
    } else {
        $backendLog    = Join-Path $LogsDir 'backend.log'
        $backendErrLog = Join-Path $LogsDir 'backend-err.log'
        $proc = Start-Process -FilePath $VenvPython `
            -ArgumentList @('-m', 'uvicorn', 'backend.main:app',
                            '--host', '127.0.0.1', '--port', '8001',
                            '--workers', '1', '--log-level', 'info') `
            -WorkingDirectory $ProjectRoot `
            -PassThru -WindowStyle Hidden `
            -RedirectStandardOutput $backendLog `
            -RedirectStandardError  $backendErrLog
        $proc.Id | Out-File (Join-Path $ProjectRoot '.backend.pid') -Encoding ascii
        # Wait up to 15 s for health
        $deadline = (Get-Date).AddSeconds(15)
        while ((Get-Date) -lt $deadline -and -not (Test-Http 'http://localhost:8001/health')) {
            Start-Sleep -Seconds 2
        }
        if (Test-Http 'http://localhost:8001/health') {
            Write-Log "Backend: started OK (PID $($proc.Id))"
        } else {
            Write-Log "Backend: process launched (PID $($proc.Id)) but /health not yet responding"
        }
    }
}

# ---------------------------------------------------------------------------
# 3. Reranker (port 8100)
# ---------------------------------------------------------------------------
if (Test-Port 8100) {
    Write-Log "Reranker: already running on port 8100"
} else {
    Write-Log "Reranker: starting on port 8100..."
    $rerankerScript = Join-Path $ProjectRoot 'scripts\start_reranker.py'
    if (-not (Test-Path $rerankerScript)) {
        Write-Log "Reranker: start_reranker.py not found — skipping"
    } elseif (-not (Test-Path $VenvPython)) {
        Write-Log "Reranker: venv not found — skipping"
    } else {
        $rrLog    = Join-Path $LogsDir 'reranker.log'
        $rrErrLog = Join-Path $LogsDir 'reranker-err.log'
        $rrProc = Start-Process -FilePath $VenvPython `
            -ArgumentList @('scripts\start_reranker.py') `
            -WorkingDirectory $ProjectRoot `
            -PassThru -WindowStyle Hidden `
            -RedirectStandardOutput $rrLog `
            -RedirectStandardError  $rrErrLog
        Write-Log "Reranker: started (PID $($rrProc.Id)) — health at http://127.0.0.1:8100/health"
    }
}

# ---------------------------------------------------------------------------
# 4. Docker Desktop + Caddy (docker compose up -d)
# ---------------------------------------------------------------------------
try {
    $null = docker info 2>&1
    Write-Log "Docker: running — starting Caddy via docker compose..."
    Push-Location $ProjectRoot
    $composeOut = docker compose up -d 2>&1
    Pop-Location
    Write-Log "Docker compose: $composeOut"
} catch {
    Write-Log "Docker: not available or not running — Caddy skipped"
}

Write-Log "=== AI-SOC-Brain startup sequence complete ==="
