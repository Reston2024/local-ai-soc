#Requires -Version 7.0
#Requires -RunAsAdministrator
<#
.SYNOPSIS
    Register Windows Task Scheduler task to auto-start AI-SOC-Brain at logon.
.DESCRIPTION
    Creates (or updates) a Task Scheduler task named "AI-SOC-Brain Startup"
    that runs scripts\start-services.ps1 when the current user logs in.

    Must be run as Administrator (elevated PowerShell).
    Safe to re-run — idempotent.

USAGE
    pwsh -ExecutionPolicy Bypass -File scripts\install-startup-tasks.ps1
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$TaskName    = 'AI-SOC-Brain Startup'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$ScriptPath  = Join-Path $ProjectRoot 'scripts\start-services.ps1'
$PwshExe     = (Get-Command pwsh -ErrorAction SilentlyContinue)?.Source
if (-not $PwshExe) { $PwshExe = 'pwsh.exe' }

Write-Host ""
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host "  AI-SOC-Brain  |  Installing startup task" -ForegroundColor White
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host ""

# Validate script exists
if (-not (Test-Path $ScriptPath)) {
    Write-Host "  ✗ start-services.ps1 not found at $ScriptPath" -ForegroundColor Red
    exit 1
}

# Build task components
$action  = New-ScheduledTaskAction `
    -Execute $PwshExe `
    -Argument "-NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$ScriptPath`"" `
    -WorkingDirectory $ProjectRoot

$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME

$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 10) `
    -MultipleInstances IgnoreNew `
    -RunOnlyIfNetworkAvailable:$false

$principal = New-ScheduledTaskPrincipal `
    -UserId $env:USERNAME `
    -LogonType Interactive `
    -RunLevel Highest

# Remove existing task if present (idempotent update)
if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Write-Host "  ► Removing existing task '$TaskName'..." -ForegroundColor Cyan
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

Write-Host "  ► Registering task '$TaskName'..." -ForegroundColor Cyan
Register-ScheduledTask `
    -TaskName  $TaskName `
    -Action    $action `
    -Trigger   $trigger `
    -Settings  $settings `
    -Principal $principal `
    -Description "Starts AI-SOC-Brain services (backend, reranker, Caddy) at user logon." `
    | Out-Null

# Confirm
$task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($task) {
    Write-Host "  ✓ Task registered successfully" -ForegroundColor Green
    Write-Host ""
    Write-Host "  Task name  : $TaskName" -ForegroundColor White
    Write-Host "  Runs as    : $env:USERNAME" -ForegroundColor White
    Write-Host "  Trigger    : At logon" -ForegroundColor White
    Write-Host "  Script     : $ScriptPath" -ForegroundColor White
    Write-Host ""
    Write-Host "  To remove  : pwsh -File scripts\uninstall-startup-tasks.ps1" -ForegroundColor Gray
    Write-Host "  To test    : Start-ScheduledTask -TaskName '$TaskName'" -ForegroundColor Gray
} else {
    Write-Host "  ✗ Task registration failed — check permissions" -ForegroundColor Red
    exit 1
}

Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host ""
