#Requires -Version 5.1
<#
.SYNOPSIS
    Deploy MISP on the GMKtec N100 via SSH.

.DESCRIPTION
    Copies infra/misp/ to the GMKtec, generates secrets, deploys the Docker
    Compose stack (mariadb + valkey + misp-core), waits for MISP to become
    healthy, then prints the next steps to retrieve the API key.

    Requires:
    - Docker installed on the GMKtec (opsadmin@192.168.1.22)
    - SSH key-based auth to opsadmin@192.168.1.22 (or password prompt)
    - infra/misp/docker-compose.misp.yml present locally

.PARAMETER GmktecHost
    SSH target. Default: opsadmin@192.168.1.22

.PARAMETER RemoteDir
    Directory on the GMKtec to deploy MISP into. Default: ~/misp

.PARAMETER AdminEmail
    MISP admin email. Default: admin@misp.local

.PARAMETER AdminPassword
    MISP admin password. Min 12 chars. Prompted if not provided.

.EXAMPLE
    .\scripts\deploy-misp.ps1
    .\scripts\deploy-misp.ps1 -AdminPassword "MyStr0ngPass!"

.NOTES
    Phase 50 — MISP Threat Intelligence Integration deployment script.
#>

[CmdletBinding()]
param(
    [string]$GmktecHost    = "opsadmin@192.168.1.22",
    [string]$RemoteDir     = "~/misp",
    [string]$AdminEmail    = "admin@misp.local",
    [string]$AdminPassword = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot  = Split-Path -Parent $PSScriptRoot
$InfraDir     = Join-Path $ProjectRoot "infra\misp"
$ComposeFile  = Join-Path $InfraDir "docker-compose.misp.yml"

Write-Host "=== MISP Deployment — GMKtec N100 ===" -ForegroundColor Cyan
Write-Host "Target:     $GmktecHost"
Write-Host "Remote dir: $RemoteDir"
Write-Host ""

# ---------------------------------------------------------------------------
# Step 1: Pre-flight checks
# ---------------------------------------------------------------------------
Write-Host "[1/6] Pre-flight checks..." -ForegroundColor Cyan

if (-not (Test-Path $ComposeFile)) {
    Write-Host "ERROR: $ComposeFile not found." -ForegroundColor Red
    exit 1
}

if (-not (Get-Command ssh.exe -ErrorAction SilentlyContinue)) {
    Write-Host "ERROR: ssh.exe not found. Install OpenSSH client (Windows Settings → Apps → Optional Features)." -ForegroundColor Red
    exit 1
}

if (-not (Get-Command scp.exe -ErrorAction SilentlyContinue)) {
    Write-Host "ERROR: scp.exe not found." -ForegroundColor Red
    exit 1
}

Write-Host "  compose file : $ComposeFile" -ForegroundColor Green
Write-Host "  ssh.exe      : $(Get-Command ssh.exe | Select-Object -ExpandProperty Source)" -ForegroundColor Green

# ---------------------------------------------------------------------------
# Step 2: SSH connectivity check
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "[2/6] Checking SSH connectivity to $GmktecHost..." -ForegroundColor Cyan

$sshCheck = & ssh.exe -o ConnectTimeout=10 -o BatchMode=yes $GmktecHost "echo SSH_OK" 2>&1
if ($LASTEXITCODE -ne 0 -or $sshCheck -notcontains "SSH_OK") {
    Write-Host "ERROR: Cannot SSH to $GmktecHost" -ForegroundColor Red
    Write-Host "  Run: ssh $GmktecHost" -ForegroundColor Yellow
    Write-Host "  If password auth: remove -o BatchMode=yes and retry, or set up SSH keys." -ForegroundColor Yellow
    exit 1
}
Write-Host "  SSH: OK" -ForegroundColor Green

# Check Docker is available on GMKtec
$dockerCheck = & ssh.exe $GmktecHost "docker info > /dev/null 2>&1 && echo DOCKER_OK" 2>&1
if ($dockerCheck -notcontains "DOCKER_OK") {
    Write-Host "ERROR: Docker not available on $GmktecHost" -ForegroundColor Red
    Write-Host "  Install Docker: https://docs.docker.com/engine/install/" -ForegroundColor Yellow
    exit 1
}
Write-Host "  Docker: OK" -ForegroundColor Green

# ---------------------------------------------------------------------------
# Step 3: Generate secrets
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "[3/6] Generating secrets..." -ForegroundColor Cyan

if ($AdminPassword -eq "") {
    $AdminPassword = Read-Host "MISP admin password (min 12 chars)"
    if ($AdminPassword.Length -lt 12) {
        Write-Host "ERROR: Password must be at least 12 characters." -ForegroundColor Red
        exit 1
    }
}

# Generate random secrets on the GMKtec (openssl available on Linux)
$secrets = & ssh.exe $GmktecHost "echo DB_ROOT=\$(openssl rand -hex 24); echo DB_PASS=\$(openssl rand -hex 24); echo ENC_KEY=\$(openssl rand -hex 32)" 2>&1
$dbRoot  = ($secrets | Where-Object { $_ -match "^DB_ROOT=" }) -replace "^DB_ROOT=", ""
$dbPass  = ($secrets | Where-Object { $_ -match "^DB_PASS=" }) -replace "^DB_PASS=", ""
$encKey  = ($secrets | Where-Object { $_ -match "^ENC_KEY=" }) -replace "^ENC_KEY=", ""

if (-not $dbRoot -or -not $dbPass -or -not $encKey) {
    Write-Host "ERROR: Failed to generate secrets on GMKtec." -ForegroundColor Red
    exit 1
}
Write-Host "  Secrets generated on GMKtec (not stored locally)" -ForegroundColor Green

# ---------------------------------------------------------------------------
# Step 4: Copy files and write .env.misp on GMKtec
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "[4/6] Copying compose files to $GmktecHost:$RemoteDir..." -ForegroundColor Cyan

& ssh.exe $GmktecHost "mkdir -p $RemoteDir"
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Could not create $RemoteDir on GMKtec." -ForegroundColor Red
    exit 1
}

# SCP compose file and customize script
& scp.exe "$ComposeFile" "${GmktecHost}:${RemoteDir}/docker-compose.misp.yml"
& scp.exe "$InfraDir\customize_misp.sh" "${GmktecHost}:${RemoteDir}/customize_misp.sh"

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: SCP failed." -ForegroundColor Red
    exit 1
}
Write-Host "  Files copied: docker-compose.misp.yml, customize_misp.sh" -ForegroundColor Green

# Write .env.misp directly on the GMKtec (never stored on Windows host)
$envContent = @"
GMKTEC_IP=192.168.1.22
MISP_DB_ROOT_PASSWORD=$dbRoot
MISP_DB_PASSWORD=$dbPass
MISP_ADMIN_EMAIL=$AdminEmail
MISP_ADMIN_PASSWORD=$AdminPassword
MISP_ENCRYPTION_KEY=$encKey
"@

$envContent | & ssh.exe $GmktecHost "cat > $RemoteDir/.env.misp && chmod 600 $RemoteDir/.env.misp"
Write-Host "  .env.misp written on GMKtec (chmod 600)" -ForegroundColor Green

# ---------------------------------------------------------------------------
# Step 5: Deploy stack
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "[5/6] Deploying MISP stack (this takes 2-4 minutes on N100)..." -ForegroundColor Cyan

$deployCmd = "cd $RemoteDir && docker compose -f docker-compose.misp.yml --env-file .env.misp up -d 2>&1"
$deployOut = & ssh.exe $GmktecHost $deployCmd
Write-Host $deployOut

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: docker compose up failed." -ForegroundColor Red
    Write-Host "  Debug: ssh $GmktecHost 'cd $RemoteDir && docker compose -f docker-compose.misp.yml logs'" -ForegroundColor Yellow
    exit 1
}
Write-Host "  Stack started" -ForegroundColor Green

# ---------------------------------------------------------------------------
# Step 6: Wait for MISP healthcheck
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "[6/6] Waiting for MISP to become healthy (up to 5 minutes)..." -ForegroundColor Cyan
Write-Host "  PHP migrations + DB init take 60-120s on N100..."

$maxWait  = 300
$interval = 15
$elapsed  = 0
$healthy  = $false

while ($elapsed -lt $maxWait) {
    Start-Sleep -Seconds $interval
    $elapsed += $interval

    $status = & ssh.exe $GmktecHost "docker inspect --format='{{.State.Health.Status}}' misp-misp-core-1 2>/dev/null || docker inspect --format='{{.State.Health.Status}}' \$(docker ps -qf name=misp-core) 2>/dev/null" 2>&1
    $status = $status | Select-Object -Last 1

    if ($status -eq "healthy") {
        $healthy = $true
        Write-Host "  MISP healthy after ${elapsed}s" -ForegroundColor Green
        break
    }

    Write-Host "  Status: $status — ${elapsed}s / ${maxWait}s" -ForegroundColor DarkGray
}

# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "=== RESULT ===" -ForegroundColor Cyan

if ($healthy) {
    Write-Host "PASS: MISP is up and healthy at http://192.168.1.22:8080" -ForegroundColor Green
    Write-Host ""
    Write-Host "Next steps:" -ForegroundColor Cyan
    Write-Host "  1. Open http://192.168.1.22:8080 in browser"
    Write-Host "  2. Log in with: $AdminEmail / <your password>"
    Write-Host "  3. Go to Administration → List Auth Keys → + Add authentication key"
    Write-Host "  4. Copy the 40-char hex key"
    Write-Host "  5. Add to your local .env file:"
    Write-Host "       MISP_ENABLED=True"
    Write-Host "       MISP_URL=http://192.168.1.22:8080"
    Write-Host "       MISP_KEY=<40-char-key>"
    Write-Host "  6. Restart the backend"
    Write-Host "  7. Enable feeds in MISP UI: Administration → Feeds → enable CIRCL OSINT + MalwareBazaar"
    Write-Host ""
    Write-Host "After feed sync, run: .\scripts\verify-misp.ps1  (or check Threat Intel tab)"
    exit 0
} else {
    Write-Host "WARNING: MISP did not report healthy within ${maxWait}s." -ForegroundColor Yellow
    Write-Host "  It may still be starting. Check status:" -ForegroundColor Yellow
    Write-Host "    ssh $GmktecHost 'docker ps && docker logs \$(docker ps -qf name=misp-core) --tail 30'"
    Write-Host ""
    Write-Host "  Once healthy, follow the Next steps above."
    exit 0
}
