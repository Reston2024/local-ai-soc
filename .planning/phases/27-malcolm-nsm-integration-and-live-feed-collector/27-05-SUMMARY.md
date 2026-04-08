---
phase: 27-malcolm-nsm-integration-and-live-feed-collector
plan: "05"
subsystem: scripts
tags: [chroma, sync, powershell, malcolm, nsm]
dependency_graph:
  requires: ["27-01"]
  provides: ["scripts/sync-chroma-corpus.ps1"]
  affects: ["data/chroma-remote-corpus/"]
tech_stack:
  added: []
  patterns:
    - "Windows OpenSSH (ssh.exe/scp.exe) for remote tar + scp transfer"
    - "$MyInvocation.MyCommand.Path for script-relative project root resolution"
key_files:
  created:
    - scripts/sync-chroma-corpus.ps1
  modified: []
decisions:
  - "Used $MyInvocation.MyCommand.Path instead of $PSScriptRoot for reliable project root resolution (plan noted this as the preferred fallback)"
  - "Output dir data/chroma-remote-corpus/ kept separate from data/chroma/ to avoid overwriting locally-indexed events"
metrics:
  duration: "5m"
  completed_date: "2026-04-07"
  tasks_completed: 1
  files_changed: 1
---

# Phase 27 Plan 05: ChromaDB Corpus Sync Script Summary

**One-liner:** PowerShell script that SSHes to Malcolm NSM, tars /var/lib/chromadb, SCPs the archive locally, and extracts it to data/chroma-remote-corpus/ with -DryRun preview support.

## What Was Built

`scripts/sync-chroma-corpus.ps1` — a 4-step ChromaDB corpus sync script:

1. SSH to opsadmin@192.168.1.22 and tar /var/lib/chromadb to /tmp/chroma-corpus.tar.gz
2. SCP the archive to $env:TEMP\chroma-corpus.tar.gz
3. Prepare the local data/chroma-remote-corpus/ directory (creates if absent, reports file count if overwriting)
4. Extract the archive and report "SYNC COMPLETE: N files synced" with sqlite3 collection count

The -DryRun switch prints the full plan (SSH command, SCP command, tar extract command, output paths, current local corpus state) without connecting to the remote host. The script is idempotent: re-running overwrites in place.

## Commits

| Task | Name | Commit | Files |
| ---- | ---- | ------ | ----- |
| 1 | Write scripts/sync-chroma-corpus.ps1 | 661a698 | scripts/sync-chroma-corpus.ps1 |

## Verification

`-DryRun` run output (confirmed exit 0):
```
=== ChromaDB Corpus Sync ===
Remote: opsadmin@192.168.1.22:/var/lib/chromadb
Local:  C:\Users\Admin\AI-SOC-Brain\data\chroma-remote-corpus

[DRY RUN] Would execute:
  ssh opsadmin@192.168.1.22 "tar czf /tmp/chroma-corpus.tar.gz -C /var/lib chromadb"
  scp opsadmin@192.168.1.22:/tmp/chroma-corpus.tar.gz "..."
  tar xzf "..." -C "C:\Users\Admin\AI-SOC-Brain\data\chroma-remote-corpus"

[DRY RUN] No files transferred.
```

## Deviations from Plan

None — plan executed exactly as written. The plan's own NOTE recommended using `$MyInvocation.MyCommand.Path` over `$PSScriptRoot`; that substitution was applied as directed.

## Self-Check: PASSED

- scripts/sync-chroma-corpus.ps1: FOUND
- Commit 661a698: FOUND
- -DryRun exit code 0: CONFIRMED
