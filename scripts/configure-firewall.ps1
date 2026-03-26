#Requires -Version 5.1
<#
.SYNOPSIS
    Configure Windows Firewall to restrict Ollama port 11434 to localhost and Docker NIC range.

.DESCRIPTION
    Creates an inbound BLOCK rule for TCP port 11434 from all sources, then creates
    ALLOW rules for 127.0.0.1 and the Docker NIC range (172.16.0.0/12).

    Implements THREAT_MODEL.md control T-03.
    Must be run as Administrator.

.EXAMPLE
    pwsh scripts/configure-firewall.ps1
#>

# Check for Administrator elevation
$currentPrincipal = [Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
if (-not $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Error "This script must be run as Administrator. Re-run from an elevated PowerShell prompt."
    exit 1
}

$RuleNameBlock  = "AI-SOC-Brain: Block Ollama 11434 (all)"
$RuleNameAllow  = "AI-SOC-Brain: Allow Ollama 11434 (localhost + Docker)"

Write-Host "[*] Configuring Ollama port 11434 firewall rules..." -ForegroundColor Cyan

# Remove existing rules if present (idempotent)
Get-NetFirewallRule -DisplayName $RuleNameBlock -ErrorAction SilentlyContinue | Remove-NetFirewallRule
Get-NetFirewallRule -DisplayName $RuleNameAllow -ErrorAction SilentlyContinue | Remove-NetFirewallRule

# Block inbound 11434 from all
New-NetFirewallRule `
    -DisplayName $RuleNameBlock `
    -Direction Inbound `
    -Protocol TCP `
    -LocalPort 11434 `
    -Action Block `
    -RemoteAddress Any `
    -Enabled True `
    -Profile Any `
    -Description "AI-SOC-Brain T-03: Block Ollama API from all remote sources" `
    | Out-Null

# Allow inbound 11434 from localhost and Docker NIC range (172.16.0.0/12)
New-NetFirewallRule `
    -DisplayName $RuleNameAllow `
    -Direction Inbound `
    -Protocol TCP `
    -LocalPort 11434 `
    -Action Allow `
    -RemoteAddress @("127.0.0.1", "172.16.0.0/12") `
    -Enabled True `
    -Profile Any `
    -Description "AI-SOC-Brain T-03: Allow Ollama API from localhost and Docker NIC range" `
    | Out-Null

Write-Host "[+] Firewall rules configured successfully." -ForegroundColor Green
Write-Host "    Block rule: '$RuleNameBlock'" -ForegroundColor Gray
Write-Host "    Allow rule: '$RuleNameAllow'" -ForegroundColor Gray
Write-Host ""
Write-Host "[i] Run 'pwsh scripts/verify-firewall.ps1' to verify the configuration." -ForegroundColor Cyan
