$base = "http://localhost:8000"
$pass = 0
$fail = 0

function ok($msg) { Write-Host "  [PASS] $msg" -ForegroundColor Green; $script:pass++ }
function fail($msg, $err) { Write-Host "  [FAIL] $msg -- $err" -ForegroundColor Red; $script:fail++ }

Write-Host ""
Write-Host "=== AI-SOC-Brain Phase 1 Verification ===" -ForegroundColor Cyan
Write-Host ""

# 1. Health
try {
    $r = Invoke-RestMethod "$base/health" -TimeoutSec 8
    if ($r.status -in @('healthy','degraded')) { ok "Backend /health status=$($r.status)" }
    else { fail "Backend /health" "status=$($r.status)" }
} catch { fail "Backend /health" $_.Exception.Message }

# 2. Health components
try {
    $r = Invoke-RestMethod "$base/health" -TimeoutSec 5
    $missing = @('duckdb','chroma','sqlite') | Where-Object { -not $r.components.$_ }
    if ($missing) { fail "Health components" "Missing: $($missing -join ',')" }
    else { ok "Health components (duckdb+chroma+sqlite)" }
} catch { fail "Health components" $_.Exception.Message }

# 3. OpenAPI
try {
    $r = Invoke-RestMethod "$base/openapi.json" -TimeoutSec 5
    $count = $r.paths.PSObject.Properties.Name.Count
    if ($count -ge 10) { ok "OpenAPI has $count routes" }
    else { fail "OpenAPI routes" "Only $count routes" }
} catch { fail "OpenAPI" $_.Exception.Message }

# 4. Events API
try {
    $r = Invoke-RestMethod "$base/api/events" -TimeoutSec 10
    if ($r.PSObject.Properties.Name -contains 'events') { ok "Events API (total=$($r.total))" }
    else { fail "Events API" "No 'events' field" }
} catch { fail "Events API" $_.Exception.Message }

# 5. Detections API
try {
    $r = Invoke-RestMethod "$base/api/detect" -TimeoutSec 10
    if ($r.PSObject.Properties.Name -contains 'detections') { ok "Detections API" }
    else { fail "Detections API" "No 'detections' field" }
} catch { fail "Detections API" $_.Exception.Message }

# 6. Graph entities API
try {
    $r = Invoke-RestMethod "$base/api/graph/entities" -TimeoutSec 10
    if ($r.PSObject.Properties.Name -contains 'entities') { ok "Graph entities API (count=$($r.total))" }
    else { fail "Graph entities API" "No 'entities' field" }
} catch { fail "Graph entities API" $_.Exception.Message }

# 7. Export CSV
try {
    $csvOut = & curl.exe -s -o NUL -w "%{http_code}" "$base/api/export/events/csv" 2>&1
    $csvStatus = $csvOut.Trim()
    if ($csvStatus -eq "200") { ok "Export CSV (status=200)" }
    else { fail "Export CSV" "HTTP $csvStatus" }
} catch { fail "Export CSV" $_.Exception.Message }

# 8. Ingest upload route exists
try {
    $r = Invoke-RestMethod "$base/openapi.json" -TimeoutSec 5
    if ($r.paths.'/api/ingest/upload') { ok "Ingest upload route registered" }
    else { fail "Ingest upload route" "Not in OpenAPI paths" }
} catch { fail "Ingest upload route" $_.Exception.Message }

# 9. Query ask route exists
try {
    $r = Invoke-RestMethod "$base/openapi.json" -TimeoutSec 5
    if ($r.paths.'/api/query/ask') { ok "Query ask route registered" }
    else { fail "Query ask route" "Not in OpenAPI paths" }
} catch { fail "Query ask route" $_.Exception.Message }

# 10. Unit tests
try {
    $out = & 'C:\Users\Admin\AI-SOC-Brain\.venv\Scripts\python.exe' '-m' 'pytest' 'tests/unit/' 'tests/sigma_smoke/' '-q' '--tb=short' 2>&1
    $summary = ($out | Select-Object -Last 3) -join " "
    Write-Host "    $summary" -ForegroundColor DarkGray
    if (($out -join "`n") -match ' failed' -or ($out -join "`n") -match 'ERROR') {
        fail "Unit tests" $summary
    } else { ok "Unit tests pass" }
} catch { fail "Unit tests" $_.Exception.Message }

# 11. Dashboard built
if (Test-Path 'C:\Users\Admin\AI-SOC-Brain\dashboard\dist\index.html') {
    ok "Dashboard dist/index.html built"
} else { fail "Dashboard build" "dist/index.html missing" }

# 12. Ingest fixture and verify events appear
try {
    $fixtureFile = 'C:\Users\Admin\AI-SOC-Brain\fixtures\security_events.ndjson'
    # Use curl.exe (always available on Windows 10+) to avoid .NET type loading issues
    $curlOut = & curl.exe -s -w "`n%{http_code}" -X POST "$base/api/ingest/upload" -F "file=@$fixtureFile" 2>&1
    $lines = $curlOut -split "`n"
    $statusCode = ($lines | Select-Object -Last 1).Trim()
    $body = ($lines | Select-Object -SkipLast 1) -join ""
    if ($statusCode -eq "200" -or $statusCode -eq "201" -or $statusCode -eq "202") {
        ok "Fixture file uploaded (HTTP $statusCode)"
        Write-Host "    Response: $body" -ForegroundColor DarkGray
        Start-Sleep -Seconds 4
        $after = Invoke-RestMethod "$base/api/events" -TimeoutSec 10
        Write-Host "    Events after ingest: total=$($after.total)" -ForegroundColor DarkGray
        if ($after.total -gt 0) { ok "Events ingested into DuckDB (total=$($after.total))" }
        else { fail "Events after ingest" "total=0 (ingest may be async, check logs)" }
    } else { fail "Fixture upload" "HTTP $statusCode -- $body" }
} catch { fail "Fixture upload" $_.Exception.Message }

Write-Host ""
Write-Host "=== Results: $pass passed, $fail failed ===" -ForegroundColor $(if ($fail -eq 0) { 'Green' } elseif ($fail -le 2) { 'Yellow' } else { 'Red' })
Write-Host ""
