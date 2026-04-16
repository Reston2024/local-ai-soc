#Requires -Version 5.1
<#
.SYNOPSIS
    Incremental backup of AI-SOC-Brain data to drive F:.
.NOTES
    Register the daily task: powershell -ExecutionPolicy Bypass -File backup-soc-brain.ps1 -Register
    Run manually:           powershell -ExecutionPolicy Bypass -File backup-soc-brain.ps1
#>
[CmdletBinding()]
param(
    [switch]$Register
)

$SourceData  = "C:\Users\Admin\AI-SOC-Brain\data"
$SourceInfra = "C:\Users\Admin\AI-SOC-Brain\infra"
$DestRoot    = "F:\SOC-Brain-Backup"
$DestData    = "$DestRoot\data"
$DestConfig  = "$DestRoot\config"
$LogDir      = "$DestRoot\logs"
$LogFile     = "$LogDir\backup-$(Get-Date -Format 'yyyy-MM-dd').log"
$ScriptPath  = $MyInvocation.MyCommand.Path

if ($Register) {
    $action   = New-ScheduledTaskAction -Execute "powershell.exe" `
                    -Argument "-ExecutionPolicy Bypass -WindowStyle Hidden -File `"$ScriptPath`""
    $trigger  = New-ScheduledTaskTrigger -Daily -At "02:00"
    $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopOnIdleEnd
    Register-ScheduledTask -TaskName "SOC-Brain-Backup" -Action $action `
        -Trigger $trigger -Settings $settings -RunLevel Highest -Force | Out-Null
    Write-Host "Scheduled task 'SOC-Brain-Backup' registered - runs daily at 02:00 AM." -ForegroundColor Green
    exit 0
}

New-Item -ItemType Directory -Path $DestData, $DestConfig, $LogDir -Force | Out-Null

$ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
Add-Content $LogFile "[$ts] SOC-Brain backup started"
Write-Host "[$ts] SOC-Brain backup started" -ForegroundColor Cyan

# Mirror data dir - incremental, skip locks/temps
Write-Host "Backing up data..." -ForegroundColor Cyan
robocopy $SourceData $DestData /MIR /Z /NP /R:2 /W:5 /LOG+:$LogFile /XF "*.lock" "*.tmp"

# Mirror infra configs - exclude all .env files (secrets stay on host only)
Write-Host "Backing up infra configs..." -ForegroundColor Cyan
robocopy $SourceInfra $DestConfig /MIR /Z /NP /R:2 /W:5 /LOG+:$LogFile /XF ".env" ".env.*" "*.env"

# Prune logs older than 7 days
Get-ChildItem $LogDir -Filter "backup-*.log" |
    Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-7) } |
    Remove-Item -Force

$destGB = [math]::Round(
    (Get-ChildItem $DestData -Recurse -File | Measure-Object -Property Length -Sum).Sum / 1GB, 2
)
$ts2 = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
Add-Content $LogFile "[$ts2] Backup complete - $destGB GB on F:"
Write-Host ""
Write-Host "Done: $destGB GB mirrored to $DestRoot" -ForegroundColor Green
Write-Host "Log: $LogFile" -ForegroundColor DarkGray
