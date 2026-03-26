#Requires -Version 5.1
<#
.SYNOPSIS
    Verify AI-SOC-Brain Ollama firewall rules are correctly configured.

.DESCRIPTION
    Checks that the block and allow rules for port 11434 exist and are enabled.
    Returns exit code 0 if rules are correct, 1 if misconfigured or missing.
    Does NOT require Administrator elevation to check rules.

.EXAMPLE
    pwsh scripts/verify-firewall.ps1
#>

$RuleNameBlock = "AI-SOC-Brain: Block Ollama 11434 (all)"
$RuleNameAllow = "AI-SOC-Brain: Allow Ollama 11434 (localhost + Docker)"

$allGood = $true

Write-Host "[*] Checking Ollama firewall rules..." -ForegroundColor Cyan

# Check block rule
$blockRule = Get-NetFirewallRule -DisplayName $RuleNameBlock -ErrorAction SilentlyContinue
if ($null -eq $blockRule) {
    Write-Warning "  [FAIL] Block rule '$RuleNameBlock' NOT FOUND"
    Write-Warning "         Run: pwsh scripts/configure-firewall.ps1 (as Administrator)"
    $allGood = $false
} elseif ($blockRule.Enabled -ne "True") {
    Write-Warning "  [FAIL] Block rule exists but is DISABLED"
    $allGood = $false
} else {
    Write-Host "  [OK]   Block rule: $RuleNameBlock (Enabled)" -ForegroundColor Green
}

# Check allow rule
$allowRule = Get-NetFirewallRule -DisplayName $RuleNameAllow -ErrorAction SilentlyContinue
if ($null -eq $allowRule) {
    Write-Warning "  [FAIL] Allow rule '$RuleNameAllow' NOT FOUND"
    $allGood = $false
} elseif ($allowRule.Enabled -ne "True") {
    Write-Warning "  [FAIL] Allow rule exists but is DISABLED"
    $allGood = $false
} else {
    Write-Host "  [OK]   Allow rule: $RuleNameAllow (Enabled)" -ForegroundColor Green
}

if ($allGood) {
    Write-Host "[+] Firewall configuration: COMPLIANT (T-03)" -ForegroundColor Green
    exit 0
} else {
    Write-Host "[-] Firewall configuration: NON-COMPLIANT" -ForegroundColor Red
    Write-Host "    To fix: run 'pwsh scripts/configure-firewall.ps1' as Administrator" -ForegroundColor Yellow
    exit 1
}
