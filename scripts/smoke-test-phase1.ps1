#Requires -Version 7.0
<#
.SYNOPSIS
    Phase 1 smoke tests — validates all key API endpoints and system health.
.DESCRIPTION
    Runs a battery of API tests against the running backend.
    Backend must be started before running: .\scripts\start.ps1
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Continue'

$BaseUrl = "http://localhost:8000"
$Pass = 0
$Fail = 0
$Tests = [System.Collections.Generic.List[hashtable]]::new()

function Test-Endpoint {
    param(
        [string]$Name,
        [string]$Url,
        [string]$Method = 'GET',
        [object]$Body = $null,
        [scriptblock]$Assert = $null,
        [int]$Timeout = 10
    )
    $result = @{ name = $Name; passed = $false; detail = '' }
    try {
        $params = @{
            Uri        = $Url
            Method     = $Method
            TimeoutSec = $Timeout
        }
        if ($Body) {
            $params.Body        = ($Body | ConvertTo-Json)
            $params.ContentType = 'application/json'
        }
        $resp = Invoke-RestMethod @params
        if ($Assert) {
            $assertResult = & $Assert $resp
            if ($assertResult) {
                $result.passed = $true
                $result.detail = "OK"
            } else {
                $result.detail = "Assertion failed"
            }
        } else {
            $result.passed = $true
            $result.detail = "HTTP 200"
        }
    } catch {
        $result.detail = $_.Exception.Message -replace "`n", " "
    }
    $Tests.Add($result)
}

Write-Host ""
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host "  AI-SOC-Brain  |  Phase 1 Smoke Tests" -ForegroundColor White
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host ""

# --- Health ---
Test-Endpoint "GET /health" "$BaseUrl/health" -Assert {
    param($r) $r.status -in @('healthy', 'degraded', 'unhealthy')
}

Test-Endpoint "GET /health — has components" "$BaseUrl/health" -Assert {
    param($r) $r.components -ne $null
}

# --- Events ---
Test-Endpoint "GET /api/events" "$BaseUrl/api/events" -Assert {
    param($r) $r.events -is [array] -and $r.total -ge 0
}

Test-Endpoint "GET /api/events?limit=5" "$BaseUrl/api/events?limit=5" -Assert {
    param($r) $r.events.Count -le 5
}

# --- Detections ---
Test-Endpoint "GET /api/detections" "$BaseUrl/api/detections" -Assert {
    param($r) $r.detections -is [array]
}

# --- Graph ---
Test-Endpoint "GET /api/graph/entities" "$BaseUrl/api/graph/entities" -Assert {
    param($r) $r.entities -is [array]
}

# --- Ingest endpoints exist ---
Test-Endpoint "GET /api/ingest/jobs" "$BaseUrl/api/ingest/jobs" -Assert {
    param($r) $r -ne $null
}

# --- Export ---
Test-Endpoint "GET /api/export/events.csv" "$BaseUrl/api/export/events.csv" -Assert {
    param($r) $r -ne $null
}

# --- OpenAPI docs ---
Test-Endpoint "GET /docs" "$BaseUrl/docs"
Test-Endpoint "GET /openapi.json" "$BaseUrl/openapi.json" -Assert {
    param($r) $r.info.title -ne $null
}

# --- Query endpoint exists ---
$queryBody = @{ question = "test connectivity"; context_events = @() }
Test-Endpoint "POST /api/query/ask (connection test)" "$BaseUrl/api/query/ask" -Method POST -Body $queryBody -Timeout 30

# --- Sigma detection test ---
Test-Endpoint "GET /api/detections/rules" "$BaseUrl/api/detections/rules" -Assert {
    param($r) $r -ne $null
}

# --- Results ---
Write-Host "  Results:" -ForegroundColor White
Write-Host ""
foreach ($t in $Tests) {
    if ($t.passed) {
        Write-Host "  ✓ $($t.name)" -ForegroundColor Green
        $Pass++
    } else {
        Write-Host "  ✗ $($t.name)" -ForegroundColor Red -NoNewline
        Write-Host " — $($t.detail)" -ForegroundColor DarkGray
        $Fail++
    }
}

$Total = $Pass + $Fail
Write-Host ""
Write-Host "  Score: $Pass/$Total passed" -ForegroundColor $(if ($Fail -eq 0) { 'Green' } elseif ($Fail -le 2) { 'Yellow' } else { 'Red' })
Write-Host ""

if ($Fail -gt 0) {
    Write-Host "  To investigate failures:" -ForegroundColor Gray
    Write-Host "  1. Check backend is running: .\scripts\status.ps1" -ForegroundColor Gray
    Write-Host "  2. Check logs: Get-Content .\logs\backend-stdout.log -Tail 50" -ForegroundColor Gray
    Write-Host "  3. API docs:   http://localhost:8000/docs" -ForegroundColor Gray
    Write-Host ""
    exit 1
} else {
    Write-Host "  All smoke tests passed! ✓" -ForegroundColor Green
    Write-Host ""
    exit 0
}
