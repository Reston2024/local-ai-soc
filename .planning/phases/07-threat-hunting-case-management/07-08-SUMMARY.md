---
phase: 07-threat-hunting-case-management
plan: 08
subsystem: scripts/docs
tags: [ops, scripts, documentation, powershell, windows]
dependency_graph:
  requires: []
  provides: [scripts/start.cmd, scripts/stop.cmd, scripts/status.cmd]
  affects: [REPRODUCIBILITY_RECEIPT.md, README.md]
tech_stack:
  added: []
  patterns: [cmd-wrapper-pattern, pwsh-fallback-error]
key_files:
  created:
    - scripts/start.cmd
    - scripts/stop.cmd
    - scripts/status.cmd
  modified:
    - REPRODUCIBILITY_RECEIPT.md
    - README.md
decisions:
  - ".cmd wrappers use %~dp0 for directory-relative .ps1 invocation — works from any cwd"
  - "where pwsh.exe >nul 2>&1 check avoids external dependency; errorlevel tested immediately"
  - "winget install Microsoft.PowerShell as actionable error — no guesswork for user"
metrics:
  duration: "4 minutes"
  completed: "2026-03-17"
  tasks: 2
  files: 5
---

# Phase 7 Plan 08: .cmd Wrappers + PS7 Docs Summary

.cmd wrappers (start/stop/status) that auto-detect pwsh and re-invoke PS7 scripts, with README.md and REPRODUCIBILITY_RECEIPT.md updated to surface the PowerShell 7 prerequisite prominently.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create .cmd wrappers for start, stop, status | c8839d2 | scripts/start.cmd, stop.cmd, status.cmd |
| 2 | Update REPRODUCIBILITY_RECEIPT.md and README.md | 38cbce4 | REPRODUCIBILITY_RECEIPT.md, README.md |

## What Was Built

**Task 1 — .cmd wrappers:**
Three `.cmd` files added to `scripts/`. Each follows the same pattern:
1. `where pwsh.exe >nul 2>&1` — silent check if pwsh is on PATH
2. If absent: print `ERROR: PowerShell 7 (pwsh) not found.` with `winget install Microsoft.PowerShell` and exit 1
3. If present: `pwsh -NoLogo -File "%~dp0<script>.ps1" %*` — directory-relative invocation, args forwarded

This allows users running cmd.exe or PowerShell 5.1 to run `scripts\start.cmd` without knowing about the PS7 requirement.

**Task 2 — Documentation updates:**
- `REPRODUCIBILITY_RECEIPT.md` Step 8 now shows both Option A (`.cmd` wrapper) and Option B (`pwsh -File` direct), with a note containing `winget install Microsoft.PowerShell`.
- `README.md` fully rewritten: reflects Phase 7 complete status, Prerequisites table with bold PowerShell 7 row, Quick Start using `scripts\start.cmd`, Management Scripts table, and Development section.

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check: PASSED

Files verified:
- FOUND: scripts/start.cmd
- FOUND: scripts/stop.cmd
- FOUND: scripts/status.cmd
- FOUND: REPRODUCIBILITY_RECEIPT.md (contains pwsh + winget install Microsoft.PowerShell)
- FOUND: README.md (contains PowerShell 7 bold row + winget install Microsoft.PowerShell)

Commits verified:
- FOUND: c8839d2 (feat(07-08): .cmd wrappers)
- FOUND: 38cbce4 (docs(07-08): doc updates)
