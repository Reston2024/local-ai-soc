#Requires -Version 5.1
<#
.SYNOPSIS
    Restrict data/ directory ACLs to the current user only.

.DESCRIPTION
    Removes inherited permissions and Everyone/Users groups from the data/
    directory. Grants full control only to the current logged-in user.

    Implements compliance control REQ-02 (data directory access restriction).
    Must be run as Administrator.

.PARAMETER WhatIf
    Show what changes would be made without applying them.

.EXAMPLE
    pwsh scripts/configure-acls.ps1
    pwsh scripts/configure-acls.ps1 -WhatIf
#>
param(
    [switch]$WhatIf
)

# Check for Administrator elevation
$currentPrincipal = [Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
if (-not $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Error "This script must be run as Administrator."
    exit 1
}

$DataDir = Join-Path $PSScriptRoot "..\data"
$DataDir = [System.IO.Path]::GetFullPath($DataDir)

if (-not (Test-Path $DataDir)) {
    Write-Warning "data/ directory not found at: $DataDir"
    Write-Warning "Create it first by running the backend."
    exit 0
}

$username = "$env:USERDOMAIN\$env:USERNAME"
if (-not $env:USERDOMAIN) { $username = $env:USERNAME }

Write-Host "[*] Configuring ACLs for: $DataDir" -ForegroundColor Cyan
Write-Host "    Grant full control to: $username" -ForegroundColor Gray
Write-Host "    Remove: Everyone, Users (inherited)" -ForegroundColor Gray

if ($WhatIf) {
    Write-Host "[WhatIf] Would run:" -ForegroundColor Yellow
    Write-Host "  icacls `"$DataDir`" /inheritance:d /grant:r `"${username}:(OI)(CI)F`" /remove `"Everyone`" /remove `"Users`"" -ForegroundColor Yellow
    exit 0
}

# Disable inheritance and set explicit permissions
icacls "$DataDir" /inheritance:d /grant:r "${username}:(OI)(CI)F" /remove "Everyone" /remove "Users" /T /Q
if ($LASTEXITCODE -ne 0) {
    Write-Error "icacls failed with exit code $LASTEXITCODE"
    exit 1
}

Write-Host "[+] ACLs configured successfully for $DataDir" -ForegroundColor Green
