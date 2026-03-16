#!/usr/bin/env pwsh
$InfraDir = $PSScriptRoot | Split-Path -Parent
Set-Location $InfraDir

Write-Host "=== AI SOC Brain Wave 1 — Status ===" -ForegroundColor Cyan
docker compose ps
Write-Host ""

Write-Host "Backend health:" -ForegroundColor Yellow
try {
    $r = Invoke-RestMethod 'http://localhost:8000/health' -TimeoutSec 3
    Write-Host "  $($r | ConvertTo-Json)" -ForegroundColor Green
} catch {
    Write-Host "  UNREACHABLE" -ForegroundColor Red
}

Write-Host "HTTPS (via Caddy):" -ForegroundColor Yellow
try {
    $r = Invoke-RestMethod 'https://localhost/health' -SkipCertificateCheck -TimeoutSec 3
    Write-Host "  $($r | ConvertTo-Json)" -ForegroundColor Green
} catch {
    Write-Host "  UNREACHABLE (is Caddy running?)" -ForegroundColor Red
}

Write-Host "OpenSearch:" -ForegroundColor Yellow
try {
    $r = Invoke-RestMethod 'http://localhost:9200' -TimeoutSec 3
    Write-Host "  cluster: $($r.cluster_name) status: $($r.tagline)" -ForegroundColor Green
} catch {
    Write-Host "  UNREACHABLE (Wave 1 scaffold — not required)" -ForegroundColor DarkGray
}
