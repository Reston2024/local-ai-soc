#Requires -Version 5.1
<#
.SYNOPSIS
    End-to-end verification of the Malcolm NSM → local-ai-soc alert pipeline.

.DESCRIPTION
    Triggers a known-bad Suricata alert by curling testmynids.org from IPFire,
    waits for the alert to propagate through Malcolm → OpenSearch → MalcolmCollector,
    then polls the local-ai-soc events API until the alert appears or a 3-minute
    timeout is reached.

    Requires:
    - local-ai-soc running on localhost:8000 with MALCOLM_ENABLED=True
    - Malcolm running on 192.168.1.22 with port 9200 exposed
    - SSH access to root@192.168.1.1 (IPFire)
    - SSH access to opsadmin@192.168.1.22 (Malcolm)

.PARAMETER ApiBase
    Base URL of local-ai-soc API. Default: http://localhost:8000

.PARAMETER PollIntervalSeconds
    Seconds between event API polls. Default: 15

.PARAMETER TimeoutSeconds
    Max seconds to wait for alert to appear. Default: 180

.EXAMPLE
    .\e2e-malcolm-verify.ps1
    .\e2e-malcolm-verify.ps1 -TimeoutSeconds 300

.NOTES
    Phase 27 P27-T06 — end-to-end pipeline verification.
#>

[CmdletBinding()]
param(
    [string]$ApiBase          = "http://localhost:8000",
    [int]$PollIntervalSeconds = 15,
    [int]$TimeoutSeconds      = 180
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$IPFireHost    = "root@192.168.1.1"
$MalcolmHost   = "opsadmin@192.168.1.22"
$TestUrl       = "http://testmynids.org/uid/index.html"

Write-Host "=== Malcolm NSM End-to-End Verification ===" -ForegroundColor Cyan
Write-Host "API base:        $ApiBase"
Write-Host "Poll interval:   $PollIntervalSeconds s"
Write-Host "Timeout:         $TimeoutSeconds s"
Write-Host ""

# ---------------------------------------------------------------------------
# Step 1: Verify local-ai-soc is healthy
# ---------------------------------------------------------------------------
Write-Host "[1/5] Checking local-ai-soc health..." -ForegroundColor Cyan
try {
    $health = Invoke-RestMethod -Uri "$ApiBase/health" -Method GET -TimeoutSec 10
    Write-Host "  Status: $($health.status)" -ForegroundColor Green
} catch {
    Write-Host "ERROR: local-ai-soc is not reachable at $ApiBase/health" -ForegroundColor Red
    Write-Host "  Start with: uv run uvicorn backend.main:create_app --factory"
    exit 1
}

# ---------------------------------------------------------------------------
# Step 2: Verify MalcolmCollector is running (check collector status)
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "[2/5] Checking MalcolmCollector status..." -ForegroundColor Cyan
try {
    $collectorStatus = Invoke-RestMethod -Uri "$ApiBase/api/telemetry/malcolm/status" -Method GET -TimeoutSec 10 -ErrorAction SilentlyContinue
    if ($collectorStatus.running) {
        Write-Host "  MalcolmCollector: running" -ForegroundColor Green
        Write-Host "  Alerts ingested so far: $($collectorStatus.alerts_ingested)"
    } else {
        Write-Host "  WARNING: MalcolmCollector status endpoint unavailable or not running." -ForegroundColor Yellow
        Write-Host "  Continuing - will verify by checking events after trigger."
    }
} catch {
    Write-Host "  (No collector status endpoint - continuing)" -ForegroundColor Yellow
}

# ---------------------------------------------------------------------------
# Step 3: Trigger Suricata alert from IPFire
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "[3/5] Triggering Suricata alert via IPFire ($IPFireHost)..." -ForegroundColor Cyan
$TriggerTimestamp = (Get-Date).ToUniversalTime()
Write-Host "  Trigger time (UTC): $($TriggerTimestamp.ToString('o'))"

$sshTrigger = & ssh.exe $IPFireHost "curl -s $TestUrl > /dev/null 2>&1 && echo TRIGGERED"
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: SSH to IPFire failed. Cannot trigger alert." -ForegroundColor Red
    Write-Host "  Check SSH access: ssh $IPFireHost"
    exit 1
}
Write-Host "  Alert trigger: $TestUrl" -ForegroundColor Green
Write-Host "  SSH result: $sshTrigger"

# ---------------------------------------------------------------------------
# Step 4: Wait for pipeline propagation
# ---------------------------------------------------------------------------
$PipelineWaitSeconds = 90
Write-Host ""
Write-Host "[4/5] Waiting $PipelineWaitSeconds s for pipeline propagation..." -ForegroundColor Cyan
Write-Host "  (Suricata → EVE → SCP → Malcolm → OpenSearch → MalcolmCollector)"
for ($i = $PipelineWaitSeconds; $i -gt 0; $i -= 10) {
    Write-Host "  $i seconds remaining..." -ForegroundColor DarkGray
    Start-Sleep -Seconds ([Math]::Min(10, $i))
}

# ---------------------------------------------------------------------------
# Step 5: Poll events API until alert appears
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "[5/5] Polling $ApiBase/api/events for new suricata_eve alerts..." -ForegroundColor Cyan
$StartPoll    = Get-Date
$AlertFound   = $false
$Elapsed      = 0

while ($Elapsed -lt $TimeoutSeconds) {
    try {
        $eventsResp = Invoke-RestMethod `
            -Uri "$ApiBase/api/events?source_type=suricata_eve&limit=20" `
            -Method GET `
            -TimeoutSec 15

        $newAlerts = $eventsResp.items | Where-Object {
            $itemTs = [datetime]::Parse($_.timestamp)
            $itemTs.ToUniversalTime() -gt $TriggerTimestamp
        }

        if ($newAlerts -and $newAlerts.Count -gt 0) {
            $AlertFound = $true
            Write-Host ""
            Write-Host "  ALERT FOUND: $($newAlerts.Count) new suricata_eve event(s)" -ForegroundColor Green
            $newAlerts | Select-Object -First 3 | ForEach-Object {
                Write-Host "    timestamp=$($_.timestamp) severity=$($_.severity) source=$($_.detection_source)"
            }
            break
        }
    } catch {
        Write-Host "  Poll error: $_" -ForegroundColor Yellow
    }

    $Elapsed = [int]((Get-Date) - $StartPoll).TotalSeconds
    Write-Host "  No new alerts yet. Elapsed: $Elapsed s / $TimeoutSeconds s"
    if ($Elapsed -lt $TimeoutSeconds) {
        Start-Sleep -Seconds $PollIntervalSeconds
    }
}

$TotalElapsed = [int]((Get-Date) - $TriggerTimestamp).TotalSeconds

# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "=== RESULT ===" -ForegroundColor Cyan
if ($AlertFound) {
    Write-Host "PASS: Alert appeared in local-ai-soc within $TotalElapsed seconds." -ForegroundColor Green
    Write-Host ""
    Write-Host "Next step: Open Svelte dashboard and navigate to Events/Detections view."
    Write-Host "Confirm the suricata_eve alert is visible with correct source and timestamp."
    exit 0
} else {
    Write-Host "FAIL: No new suricata_eve alerts appeared within $TimeoutSeconds seconds (plus $PipelineWaitSeconds s wait)." -ForegroundColor Red
    Write-Host ""
    Write-Host "Troubleshooting checklist:"
    Write-Host "  1. Is MALCOLM_ENABLED=True in .env and local-ai-soc restarted?"
    Write-Host "  2. Is port 9200 accessible: curl -sk -u admin:Adam1000! https://192.168.1.22:9200/_cluster/health"
    Write-Host "  3. Did Suricata actually fire? SSH to $MalcolmHost and check:"
    Write-Host "     curl -sk -u admin:Adam1000! https://localhost:9200/arkime_sessions3-*/_count"
    Write-Host "  4. Check MalcolmCollector logs: search for 'MalcolmCollector' in application logs"
    exit 1
}
