---
phase: 49-chainsaw-windows-event-log-analysis
plan: "02"
subsystem: ingestion/chainsaw
tags: [chainsaw, evtx, threat-hunting, sqlite, health]
dependency_graph:
  requires: [49-01, 48-02]
  provides: [chainsaw_scanner, chainsaw_dedup, chainsaw_health]
  affects: [ingestion/loader.py, backend/stores/sqlite_store.py, backend/api/health.py]
tech_stack:
  added: []
  patterns: [subprocess-scanner, sha256-dedup, non-fatal-pipeline-block, health-component]
key_files:
  created:
    - ingestion/chainsaw_scanner.py
  modified:
    - backend/stores/sqlite_store.py
    - ingestion/loader.py
    - backend/api/health.py
    - tests/unit/test_chainsaw_scanner.py
decisions:
  - "_extract_technique() helper used for MITRE technique extraction to handle both T1003 and T1003.001 sub-technique formats"
  - "int() cast on detection_count in _check_chainsaw() to prevent MagicMock serialization in unit tests (same fix needed in _check_hayabusa but pre-existing)"
  - "test_health_returns_200 pre-existing failure confirmed via git stash — out of scope, logged to deferred-items"
metrics:
  duration: "~15 minutes"
  completed: "2026-04-14T22:25:36Z"
  tasks_completed: 2
  tasks_total: 2
  files_created: 1
  files_modified: 4
---

# Phase 49 Plan 02: Chainsaw Backend Integration Summary

**One-liner:** Chainsaw EVTX scanner module with SHA-256 dedup, loader wiring, and /health component — all 7 unit stubs GREEN.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create ingestion/chainsaw_scanner.py | 820c538 | ingestion/chainsaw_scanner.py, tests/unit/test_chainsaw_scanner.py |
| 2 | SQLite dedup + loader wiring + health endpoint | 08a9d05 | backend/stores/sqlite_store.py, ingestion/loader.py, backend/api/health.py |

## What Was Built

### ingestion/chainsaw_scanner.py
- `CHAINSAW_BIN`: 3-step resolver (shutil.which + fallback to C:\Tools\chainsaw\)
- `_CHAINSAW_DIR`, `_SIGMA_DIR`, `_RULES_DIR`, `_MAPPING_FILE`: path resolution relative to binary parent
- `_LEVEL_MAP`: critical/high/medium/low/informational/info → normalized severity
- `scan_evtx()`: subprocess `chainsaw hunt` with --json output (JSON array, not JSONL)
- `chainsaw_record_to_detection()`: maps name/level/tags → DetectionRecord
- MITRE technique: `attack.t1003.001` → `T1003.001`, `attack.t1003` → `T1003`
- MITRE tactic: `attack.credential_access` → `Credential Access`
- `detection_source='chainsaw'`, `rule_id='chainsaw-{id}'`

### backend/stores/sqlite_store.py
- `_CHAINSAW_DDL`: CREATE TABLE IF NOT EXISTS chainsaw_scanned_files
- Table created in `SQLiteStore.__init__()` after Hayabusa DDL (idempotent)
- `is_chainsaw_scanned(sha256)` → bool
- `mark_chainsaw_scanned(sha256, path, findings)` → None (INSERT OR IGNORE)

### ingestion/loader.py
- `from ingestion.chainsaw_scanner import scan_evtx as chainsaw_scan_evtx, chainsaw_record_to_detection`
- `IngestionResult.chainsaw_findings: int = 0`
- `_run_chainsaw_scan()` sync helper (mirrors `_run_hayabusa_scan` pattern exactly)
- Non-fatal Chainsaw block in `ingest_file()` after Hayabusa block

### backend/api/health.py
- `_check_chainsaw()` async function (mirrors `_check_hayabusa` pattern)
- `asyncio.gather()` extended to 6 coroutines including `_check_chainsaw(request)`
- `components["chainsaw"]` included in /health response

## Unit Test Results

All 7 unit stubs now GREEN:

```
tests/unit/test_chainsaw_scanner.py - 7 passed
```

Full unit suite: 1146 passed, 1 pre-existing failure (test_health_returns_200 — confirmed pre-existing via git stash).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] MITRE sub-technique extraction returning None for attack.t1003.001**
- **Found during:** Task 1 test run
- **Issue:** Initial implementation used `t.split(".")[-1].upper()` with `len >= 4` check. For `attack.t1003.001`, last segment is `001` (3 chars), so it matched nothing.
- **Fix:** Replaced with `_extract_technique()` helper that checks the segment after `attack.` starts with t followed by 4 digits, then returns the full `t1003.001` portion uppercased.
- **Files modified:** ingestion/chainsaw_scanner.py
- **Commit:** 820c538

**2. [Rule 1 - Bug] int() cast on detection_count to prevent MagicMock JSON serialization**
- **Found during:** Task 2 full unit suite run
- **Issue:** `row.fetchone()[0]` in `_check_chainsaw()` returned a MagicMock in the unit test fixture, causing JSON serialization to fail with 500. Same pattern as `_check_hayabusa()` but the test was already failing before this plan.
- **Fix:** Added `int(row.fetchone()[0])` cast in `_check_chainsaw()`. The `_check_hayabusa()` pre-existing failure is deferred (out of scope).
- **Files modified:** backend/api/health.py
- **Commit:** 08a9d05

### Deferred Issues

**test_health_returns_200 pre-existing failure** — confirmed via `git stash` that this test was failing before Plan 49-02 started. The root cause is `_check_hayabusa()` returning a MagicMock `detection_count` value that cannot be JSON serialized. This is out of scope for Plan 49-02 and should be addressed in a dedicated fix.

## Self-Check: PASSED

- ingestion/chainsaw_scanner.py: FOUND
- backend/stores/sqlite_store.py: FOUND (modified)
- ingestion/loader.py: FOUND (modified)
- backend/api/health.py: FOUND (modified)
- Commit 820c538: FOUND
- Commit 08a9d05: FOUND
- All 7 unit tests: PASSED
