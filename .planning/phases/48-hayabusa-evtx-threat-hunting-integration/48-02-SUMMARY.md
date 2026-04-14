---
phase: 48-hayabusa-evtx-threat-hunting-integration
plan: "02"
subsystem: ingestion
tags: [tdd, hayabusa, evtx, threat-hunting, sqlite, wave-1]
dependency_graph:
  requires:
    - 48-01 (test stubs — importorskip scaffolding)
  provides:
    - ingestion/hayabusa_scanner.py
    - backend/stores/sqlite_store.py (detection_source, hayabusa_scanned_files, is_already_scanned, mark_scanned)
    - ingestion/loader.py (_run_hayabusa_scan + ingest_file wiring)
  affects:
    - All EVTX file ingestion (hayabusa scan runs after parse block)
    - SQLite detections table (detection_source column added)
    - Dedup logic (hayabusa_scanned_files prevents double-scanning same SHA-256)
tech_stack:
  added: []
  patterns:
    - "scan_evtx() generator: Hayabusa subprocess + JSONL temp file + finally cleanup"
    - "hayabusa_record_to_detection(): maps JSONL dict to DetectionRecord with MITRE tag filtering"
    - "is_already_scanned() + mark_scanned(): SHA-256 dedup table pattern"
    - "asyncio.to_thread(_run_hayabusa_scan) wired non-fatally in ingest_file()"
    - "INSERT OR IGNORE for idempotent dedup table insertions"
key_files:
  created:
    - ingestion/hayabusa_scanner.py
  modified:
    - backend/stores/sqlite_store.py
    - ingestion/loader.py
    - tests/unit/test_hayabusa_scanner.py
    - tests/integration/test_hayabusa_e2e.py
decisions:
  - "structlog not installed — use backend.core.logging.get_logger() consistently (same as all other modules)"
  - "IngestionResult gets hayabusa_findings: int = 0 field (not dict extra) for type safety"
  - "Hayabusa scan wired as non-fatal (try/except) so EVTX parse is never aborted by scan failure"
  - "detection_source default='sigma' in insert_detection() ensures 100% backward compat with all existing callers (matcher.py, correlation engine, anomaly scorer)"
  - "scan_evtx accepts exit codes 0 and 1 as success — Hayabusa returns 1 for 'no results' on clean EVTXes"
metrics:
  duration: "10 minutes"
  completed: "2026-04-14T20:35:34Z"
  tasks_completed: 2
  files_created: 1
  files_modified: 4
---

# Phase 48 Plan 02: Hayabusa EVTX Threat Hunting — Wave 1 Implementation Summary

HayabusaScanner module + SQLite dedup table + detection_source migration + loader wiring: Hayabusa's 4,000+ rule corpus runs against every ingested EVTX file, findings stored as detections with detection_source='hayabusa', SHA-256 dedup prevents rescanning.

## Objective

Wave 1 implementation: Turn all 6 TDD unit test stubs GREEN by creating ingestion/hayabusa_scanner.py, extending SQLiteStore with the hayabusa_scanned_files dedup table and detection_source migration, and wiring _run_hayabusa_scan into ingest_file() for .evtx files.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create ingestion/hayabusa_scanner.py | 7d09fbe | ingestion/hayabusa_scanner.py, tests/unit/test_hayabusa_scanner.py |
| 2 | Extend SQLiteStore + wire loader.py | cab9145 | backend/stores/sqlite_store.py, ingestion/loader.py, tests/unit/test_hayabusa_scanner.py, tests/integration/test_hayabusa_e2e.py |

## What Was Built

### ingestion/hayabusa_scanner.py (NEW, 155 lines)

Core Hayabusa integration module:
- **HAYABUSA_BIN**: `shutil.which("hayabusa") or shutil.which("hayabusa.exe")` at module level; logs warning if absent
- **_LEVEL_MAP**: `crit→critical, high→high, med/medium→medium, low→low, info→informational`
- **scan_evtx(evtx_path)**: Generator that runs `hayabusa json-timeline -f {path} -L -o {tmp} -w -q -C --min-level medium`, parses JSONL output, yields dicts; accepts exit codes 0/1; cleans up tmp in finally; returns nothing when HAYABUSA_BIN is None
- **hayabusa_record_to_detection(rec, evtx_path, case_id)**: Maps JSONL record to DetectionRecord; filters MitreTags to only `T####` entries (len>=5, excludes G#### and S####); explanation = "[Hayabusa] {title}: {k=v details}" format

### backend/stores/sqlite_store.py (MODIFIED)

Three additions:
1. `_HAYABUSA_DDL`: CREATE TABLE IF NOT EXISTS hayabusa_scanned_files (id AUTOINCREMENT, file_sha256 UNIQUE, file_path, scanned_at, findings)
2. Phase 48 migration in `__init__`: idempotent ALTER TABLE detections ADD COLUMN detection_source TEXT DEFAULT 'sigma'
3. `is_already_scanned(file_sha256)` and `mark_scanned(file_sha256, file_path, findings)` methods
4. `insert_detection()` extended with `detection_source: str = 'sigma'` parameter (backward-compatible default)

### ingestion/loader.py (MODIFIED)

- Import: `from ingestion.hayabusa_scanner import scan_evtx, hayabusa_record_to_detection`
- `IngestionResult` dataclass: added `hayabusa_findings: int = 0` field
- `_run_hayabusa_scan()` sync helper: checks dedup → iterates scan_evtx → inserts detections with `detection_source='hayabusa'` → calls mark_scanned
- `ingest_file()` Phase 48 block: `if suffix == .evtx: result.hayabusa_findings = await asyncio.to_thread(_run_hayabusa_scan, ...)` wrapped non-fatally

## Verification Results

```
tests/unit/test_hayabusa_scanner.py -v
  test_record_mapping        PASSED
  test_level_normalization   PASSED
  test_mitre_tag_filter      PASSED
  test_no_binary             PASSED
  test_dedup_skip            PASSED
  test_migration_idempotent  PASSED
  6 passed in 0.09s

Full unit suite: 1127 passed, 11 pre-existing failures (playbooks/auth), 0 new regressions
```

```
grep -n "detection_source" backend/stores/sqlite_store.py
  501: Phase 48 migration block
  504: ALTER TABLE detections ADD COLUMN detection_source TEXT DEFAULT 'sigma'
  809: detection_source: str = "sigma" param in insert_detection()
  832: INSERT SQL includes detection_source column
  841: detection_source in values tuple

grep -n "_run_hayabusa_scan|hayabusa_scanner" ingestion/loader.py
  43: import scan_evtx, hayabusa_record_to_detection
  346: def _run_hayabusa_scan(...)
  535: asyncio.to_thread(_run_hayabusa_scan, ...)
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] structlog not installed — replaced with project logger**
- **Found during:** Task 1 (module import failed with ModuleNotFoundError: structlog)
- **Issue:** Plan specified `import structlog; log = structlog.get_logger()` but structlog is not in the project dependencies
- **Fix:** Used `from backend.core.logging import get_logger; log = get_logger(__name__)` — consistent with all other modules in the codebase
- **Files modified:** ingestion/hayabusa_scanner.py
- **Commit:** 7d09fbe

**2. [Rule 2 - Missing Field] IngestionResult lacked hayabusa_findings field**
- **Found during:** Task 2 (plan used `result["hayabusa_findings"]` but IngestionResult is a dataclass not a dict)
- **Issue:** Plan's pseudocode assumed dict access but IngestionResult is a typed dataclass with no extra/dict field
- **Fix:** Added `hayabusa_findings: int = 0` field to IngestionResult dataclass; used `result.hayabusa_findings = count` for type safety
- **Files modified:** ingestion/loader.py
- **Commit:** cab9145

## Decisions Made

- `get_logger(__name__)` used (not structlog) — project standard already set by all backend modules
- `hayabusa_findings: int = 0` added to IngestionResult dataclass for type safety over dict access
- Hayabusa scan block in ingest_file() wrapped in try/except — EVTX parse pipeline must never be aborted by Hayabusa failures
- `INSERT OR IGNORE` used in mark_scanned() for fully idempotent dedup (concurrent scan-then-mark safe)

## Self-Check: PASSED

- FOUND: ingestion/hayabusa_scanner.py
- FOUND: backend/stores/sqlite_store.py (detection_source column, hayabusa_scanned_files, is_already_scanned, mark_scanned, insert_detection with detection_source param)
- FOUND: ingestion/loader.py (_run_hayabusa_scan, import, ingest_file wiring)
- FOUND: commit 7d09fbe (Task 1)
- FOUND: commit cab9145 (Task 2)
- FOUND: 6/6 unit tests PASSED
