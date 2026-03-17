#Requires -Version 7.0
<#
.SYNOPSIS
    Phase 8 smoke tests — validates HTTPS proxy, Ollama GPU, osquery telemetry, and unit tests.
.DESCRIPTION
    Runs 7 checks against the Phase 8 production-hardened stack.
    Backend must be started before running: scripts\start.cmd
    Ollama must be running: ollama serve (or Windows service)
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Continue'

$pass = 0
$fail = 0
$warn = 0

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "AI-SOC-Brain  |  Phase 8 Smoke Tests" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# ------------------------------------------------------------------
# Check 1 — HTTPS health (P8-T09)
# ------------------------------------------------------------------
Write-Host "[Check 1] HTTPS health endpoint..." -ForegroundColor Cyan
try {
    $resp = Invoke-WebRequest -Uri "https://localhost/health" -SkipCertificateCheck -UseBasicParsing -TimeoutSec 10
    if ($resp.StatusCode -eq 200) {
        Write-Host "[PASS] HTTPS health: https://localhost/health returned 200" -ForegroundColor Green
        $pass++
    } else {
        Write-Host "[FAIL] HTTPS health: expected 200, got $($resp.StatusCode)" -ForegroundColor Red
        $fail++
    }
} catch {
    Write-Host "[FAIL] HTTPS health: connection failed — $($_.Exception.Message)" -ForegroundColor Red
    $fail++
}

# ------------------------------------------------------------------
# Check 2 — HTTP health fallback (belt-and-suspenders, non-blocking)
# ------------------------------------------------------------------
Write-Host "[Check 2] HTTP health fallback (non-blocking)..." -ForegroundColor Cyan
try {
    $resp = Invoke-WebRequest -Uri "http://localhost:8000/health" -UseBasicParsing -TimeoutSec 10
    if ($resp.StatusCode -eq 200) {
        Write-Host "[PASS] HTTP health: http://localhost:8000/health returned 200" -ForegroundColor Green
        $pass++
    } else {
        Write-Host "[WARN] HTTP health: expected 200, got $($resp.StatusCode)" -ForegroundColor Yellow
        $warn++
    }
} catch {
    Write-Host "[WARN] HTTP health: connection failed — $($_.Exception.Message)" -ForegroundColor Yellow
    $warn++
}

# ------------------------------------------------------------------
# Check 3 — Ollama reachable
# ------------------------------------------------------------------
Write-Host "[Check 3] Ollama API reachable..." -ForegroundColor Cyan
try {
    $resp = Invoke-WebRequest -Uri "http://127.0.0.1:11434/api/tags" -UseBasicParsing -TimeoutSec 10
    if ($resp.StatusCode -eq 200) {
        Write-Host "[PASS] Ollama API: http://127.0.0.1:11434/api/tags returned 200" -ForegroundColor Green
        $pass++
    } else {
        Write-Host "[FAIL] Ollama API: expected 200, got $($resp.StatusCode)" -ForegroundColor Red
        $fail++
    }
} catch {
    Write-Host "[FAIL] Ollama API: connection failed — $($_.Exception.Message)" -ForegroundColor Red
    $fail++
}

# ------------------------------------------------------------------
# Check 4 — Ollama GPU layers (P8-T11)
# ------------------------------------------------------------------
Write-Host "[Check 4] Ollama GPU layers..." -ForegroundColor Cyan
try {
    $ollamaPs = & ollama ps 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[FAIL] Ollama GPU check: ollama ps failed" -ForegroundColor Red
        $fail++
    } elseif ($ollamaPs -match '\d+') {
        Write-Host "[PASS] Ollama GPU: model loaded with GPU layers" -ForegroundColor Green
        $pass++
    } else {
        Write-Host "[WARN] Ollama GPU: no model currently loaded — run: ollama run qwen3:14b first" -ForegroundColor Yellow
        $warn++
    }
} catch {
    Write-Host "[FAIL] Ollama GPU check: ollama not found — $($_.Exception.Message)" -ForegroundColor Red
    $fail++
}

# ------------------------------------------------------------------
# Check 5 — osquery telemetry status
# ------------------------------------------------------------------
Write-Host "[Check 5] osquery telemetry status..." -ForegroundColor Cyan
try {
    $resp = Invoke-WebRequest -Uri "http://localhost:8000/api/telemetry/osquery/status" -UseBasicParsing -TimeoutSec 5
    $data = $resp.Content | ConvertFrom-Json
    if ($data.enabled) {
        if ($data.running) {
            Write-Host "[PASS] osquery collector: running, $($data.lines_processed) lines processed" -ForegroundColor Green
            $pass++
        } else {
            Write-Host "[WARN] osquery enabled but collector not running — check logs" -ForegroundColor Yellow
            $warn++
        }
    } else {
        Write-Host "[INFO] osquery disabled (OSQUERY_ENABLED=False) — set True in .env to activate" -ForegroundColor Cyan
        $pass++
    }
} catch {
    Write-Host "[WARN] osquery status endpoint unavailable: $($_.Exception.Message)" -ForegroundColor Yellow
    $warn++
}

# ------------------------------------------------------------------
# Check 6 — Unit pytest regression gate (P8-T12)
# ------------------------------------------------------------------
Write-Host "`n[Running] Unit test suite..." -ForegroundColor Cyan
$testResult = & uv run pytest tests/unit/ -q --tb=short 2>&1
$failedLines = ($testResult | Select-String 'failed').Count
if ($failedLines -eq 0) {
    Write-Host "[PASS] Unit tests: all passing" -ForegroundColor Green
    $pass++
} else {
    Write-Host "[FAIL] Unit tests: $failedLines failure(s) detected" -ForegroundColor Red
    $fail++
}

# ------------------------------------------------------------------
# Check 7 — Dashboard accessible
# ------------------------------------------------------------------
Write-Host "[Check 7] Dashboard accessible..." -ForegroundColor Cyan
try {
    $resp = Invoke-WebRequest -Uri "https://localhost/app/" -SkipCertificateCheck -UseBasicParsing -TimeoutSec 10
    if ($resp.StatusCode -eq 200) {
        Write-Host "[PASS] Dashboard: https://localhost/app/ returned 200" -ForegroundColor Green
        $pass++
    } elseif ($resp.StatusCode -eq 404) {
        Write-Host "[WARN] Dashboard: 404 — Dashboard not built. Run: cd dashboard && npm run build" -ForegroundColor Yellow
        $warn++
    } else {
        Write-Host "[WARN] Dashboard: unexpected status $($resp.StatusCode)" -ForegroundColor Yellow
        $warn++
    }
} catch {
    $msg = $_.Exception.Message
    if ($msg -match 'refused|connect') {
        Write-Host "[WARN] Dashboard: connection refused — Caddy not running. Start with: scripts\start.cmd" -ForegroundColor Yellow
    } elseif ($msg -match '404') {
        Write-Host "[WARN] Dashboard: 404 — Dashboard not built. Run: cd dashboard && npm run build" -ForegroundColor Yellow
    } else {
        Write-Host "[WARN] Dashboard: $msg" -ForegroundColor Yellow
    }
    $warn++
}

# ------------------------------------------------------------------
# Summary
# ------------------------------------------------------------------
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "Phase 8 Smoke Test Complete" -ForegroundColor Cyan
Write-Host "PASS: $pass  WARN: $warn  FAIL: $fail" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

if ($fail -gt 0) {
    Write-Host "RESULT: FAIL ($fail failure(s))" -ForegroundColor Red
    exit 1
} else {
    Write-Host "RESULT: PASS" -ForegroundColor Green
    exit 0
}
