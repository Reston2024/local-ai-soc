#Requires -Version 7.0
#Requires -RunAsAdministrator
<#
.SYNOPSIS
    Remove the AI-SOC-Brain Windows Task Scheduler startup task.
.DESCRIPTION
    Unregisters the "AI-SOC-Brain Startup" scheduled task.
    Safe to run even if the task does not exist (idempotent).

USAGE
    pwsh -ExecutionPolicy Bypass -File scripts\uninstall-startup-tasks.ps1
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Continue'

$TaskName = 'AI-SOC-Brain Startup'

Write-Host ""
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host "  AI-SOC-Brain  |  Removing startup task" -ForegroundColor White
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host ""

if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "  ✓ Task '$TaskName' removed" -ForegroundColor Green
} else {
    Write-Host "  ℹ Task '$TaskName' not found — nothing to remove" -ForegroundColor Yellow
}

Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host ""
