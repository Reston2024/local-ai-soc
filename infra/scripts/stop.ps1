#!/usr/bin/env pwsh
$InfraDir = $PSScriptRoot | Split-Path -Parent
Set-Location $InfraDir

Write-Host "Stopping AI SOC Brain Wave 1 stack..." -ForegroundColor Yellow
docker compose down
Write-Host "Done." -ForegroundColor Green
