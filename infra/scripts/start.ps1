#!/usr/bin/env pwsh
# Wave 1 start script — brings up full stack via Docker Compose
$ErrorActionPreference = 'Stop'

$InfraDir = $PSScriptRoot | Split-Path -Parent
Set-Location $InfraDir

Write-Host "=== AI SOC Brain Wave 1 — Starting Stack ===" -ForegroundColor Cyan

# Ensure dashboard is built
if (-not (Test-Path '../frontend/dist')) {
    Write-Host "Building frontend..." -ForegroundColor Yellow
    Push-Location '../frontend'
    npm install --silent
    npm run build
    Pop-Location
}

Write-Host "Starting services..." -ForegroundColor Yellow
docker compose up -d --build

Write-Host "Waiting for backend health..." -ForegroundColor Yellow
$retries = 0
do {
    Start-Sleep -Seconds 3
    $retries++
    try {
        $r = Invoke-RestMethod 'https://localhost/health' -SkipCertificateCheck -TimeoutSec 3
        if ($r.status -eq 'ok') { break }
    } catch {}
} while ($retries -lt 10)

Write-Host ""
Write-Host "=== Stack Ready ===" -ForegroundColor Green
Write-Host "  Frontend:  https://localhost" -ForegroundColor White
Write-Host "  Backend:   http://localhost:8000/health" -ForegroundColor White
Write-Host "  OpenSearch: http://localhost:9200" -ForegroundColor White
Write-Host ""
Write-Host "Load fixtures: Invoke-RestMethod -Method Post https://localhost/fixtures/load -SkipCertificateCheck" -ForegroundColor DarkGray
