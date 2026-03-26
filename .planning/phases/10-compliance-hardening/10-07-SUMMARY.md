---
phase: 10-compliance-hardening
plan: "07"
subsystem: scripts/firewall
tags: [firewall, hardening, compliance, T-03, powershell]
dependency_graph:
  requires: [10-05, 10-06]
  provides: [firewall-scripts-T03]
  affects: [scripts/status.ps1]
tech_stack:
  added: []
  patterns: [idempotent-firewall-rule, preflight-check, non-blocking-warning]
key_files:
  created:
    - scripts/configure-firewall.ps1
    - scripts/verify-firewall.ps1
  modified:
    - scripts/status.ps1
decisions:
  - "verify-firewall.ps1 does not require Admin elevation — Get-NetFirewallRule is readable by standard users"
  - "status.ps1 preflight is non-blocking — firewall issues warn but do not prevent status output"
  - "configure-firewall.ps1 uses idempotent remove+create pattern to avoid duplicate rule accumulation"
metrics:
  duration: "~5 minutes"
  completed: "2026-03-26"
  tasks_completed: 2
  tasks_total: 2
  files_created: 2
  files_modified: 1
---

# Phase 10 Plan 07: Firewall Hardening Scripts (T-03) Summary

Windows Firewall scripts implementing THREAT_MODEL.md control T-03: BLOCK rule for all inbound TCP 11434, ALLOW rule for 127.0.0.1 and 172.16.0.0/12, with preflight integration into status.ps1.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create configure-firewall.ps1 | 325dae4 | scripts/configure-firewall.ps1 |
| 2 | Create verify-firewall.ps1 + status.ps1 preflight | 0b1bbff | scripts/verify-firewall.ps1, scripts/status.ps1 |

## What Was Built

### scripts/configure-firewall.ps1
- Requires Administrator elevation (exits 1 with clear error if not elevated)
- Idempotent: removes existing rules by display name before recreating
- Creates BLOCK rule: inbound TCP 11434 from RemoteAddress=Any
- Creates ALLOW rule: inbound TCP 11434 from 127.0.0.1 and 172.16.0.0/12

### scripts/verify-firewall.ps1
- No Admin elevation required (read-only Get-NetFirewallRule calls)
- Checks both block and allow rules exist and are Enabled=True
- Exit 0: COMPLIANT; Exit 1: NON-COMPLIANT with remediation guidance

### scripts/status.ps1 (modified)
- Added non-blocking firewall preflight section after banner, before service checks
- Calls verify-firewall.ps1 and emits Write-Warning if non-compliant
- status.ps1 continues normally regardless of firewall check result

## Decisions Made

1. verify-firewall.ps1 omits Admin elevation check — `Get-NetFirewallRule` is available to standard users on Windows, so requiring elevation would make it unusable in status.ps1 without sudo friction.
2. status.ps1 integration is strictly non-blocking — the script warnings but does not exit early, preserving existing behavior for all other status checks.
3. Idempotency via display-name-based remove — avoids duplicate rule accumulation when script is re-run after configuration drift.

## Deviations from Plan

None — plan executed exactly as written.

## Verification

```
grep -c "New-NetFirewallRule" scripts/configure-firewall.ps1  → 2
grep -c "Get-NetFirewallRule" scripts/verify-firewall.ps1     → 2
grep -c "verify-firewall"     scripts/status.ps1              → 1
```

All checks passed.

## Self-Check: PASSED

- scripts/configure-firewall.ps1 exists: FOUND
- scripts/verify-firewall.ps1 exists: FOUND
- status.ps1 contains verify-firewall reference: FOUND
- commits 325dae4 and 0b1bbff: FOUND
