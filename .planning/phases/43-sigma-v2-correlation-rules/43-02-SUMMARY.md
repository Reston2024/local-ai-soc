---
plan: 43-02
phase: 43
subsystem: detections
tags: [correlation, port-scan, brute-force, beaconing, duckdb, statistical-detection]
dependency_graph:
  requires: [43-01]
  provides: [detections/correlation_engine.py, entity_key column on detections]
  affects: [ingestion/loader.py, backend/stores/sqlite_store.py, backend/main.py]
tech_stack:
  added: []
  patterns: [asyncio.to_thread, DuckDB window queries, tumbling 60s bucket, CV beaconing, dedup-by-entity]
key_files:
  created:
    - detections/correlation_engine.py
  modified:
    - backend/models/event.py
    - backend/core/config.py
    - backend/stores/sqlite_store.py
    - ingestion/loader.py
    - backend/main.py
    - backend/api/ingest.py
    - tests/unit/test_correlation_engine.py
decisions:
  - "entity_key added to DetectionRecord model as Optional[str] for correlation dedup key"
  - "save_detections() uses getattr(det, entity_key, None) for backward compat with existing callers"
  - "Step 5 in ingest_events() is non-fatal (try/except) to prevent correlation errors aborting ingest"
  - "ANOMALY_DEDUP_WINDOW_MINUTES added to config alongside CORRELATION_* settings"
  - "Behavioral tests replace @_skip stubs for port_scan/brute_force/beaconing/record/dedup"
metrics:
  duration: "~25 minutes"
  completed: "2026-04-12"
  tasks_completed: 2
  tasks_total: 2
  files_changed: 7
  tests_added: 5
  tests_total: 1064
---

# Phase 43 Plan 02: Core correlation engine — port scan, brute force, beaconing

**One-liner:** CorrelationEngine class with DuckDB window queries detecting port scans (15+ dst_ports/60s), brute force (10+ auth failures/60s), and beaconing (CV < 0.3 over 20+ connections), wired into ingest pipeline with entity_key dedup.

## Tasks Completed

| Task | Description | Commit | Files |
|------|-------------|--------|-------|
| 1 | CorrelationEngine + behavioral tests GREEN | 570a7d2, b262455 | detections/correlation_engine.py, tests/unit/test_correlation_engine.py, backend/models/event.py, backend/core/config.py |
| 2 | SQLite migration, loader hook, main.py wiring | 6dcb31e | backend/stores/sqlite_store.py, ingestion/loader.py, backend/main.py, backend/api/ingest.py |

## What Was Built

### CorrelationEngine (`detections/correlation_engine.py`)

Three async detection methods backed by DuckDB window queries:

- `_detect_port_scans()`: Groups by `src_ip, CAST(epoch(timestamp)/60 AS BIGINT)` — returns `DetectionRecord(rule_id='corr-portscan', severity='medium')` when `COUNT(DISTINCT dst_port) >= 15`
- `_detect_brute_force()`: Filters `event_outcome='failure' OR event_type='logon_failure' OR (event_type='ssh' AND ssh_auth_success=false)` — returns `DetectionRecord(rule_id='corr-bruteforce', severity='high')` when `COUNT(*) >= 10` in 60s
- `_detect_beaconing()`: Uses LAG() window function to compute inter-arrival intervals, then filters `STDDEV_POP/AVG < 0.3` with `COUNT >= 19` — returns `DetectionRecord(rule_id='corr-beacon', severity='high')`

The `run()` method calls all three + `_detect_chains()` (stub for Plan 43-03) and filters via `_is_dedup_suppressed()` before returning.

`save_detections()` persists via `asyncio.to_thread` calling `sqlite.insert_detection()` with the new `entity_key` kwarg.

### Config Changes (`backend/core/config.py`)
- `CORRELATION_LOOKBACK_HOURS: int = 2` — DuckDB INTERVAL for lookback window
- `CORRELATION_DEDUP_WINDOW_MINUTES: int = 60` — suppress repeat alerts within window
- `ANOMALY_DEDUP_WINDOW_MINUTES: int = 60` — was missing from Phase 42 config

### SQLite Migration (`backend/stores/sqlite_store.py`)
- `ALTER TABLE detections ADD COLUMN entity_key TEXT` (try/except pattern)
- `insert_detection()` gains `entity_key: Optional[str] = None` parameter and includes it in INSERT SQL

### Pipeline Wiring (`ingestion/loader.py`)
- `IngestionLoader.__init__()` gains `correlation_engine=None` parameter
- Step 5 added to `ingest_events()`: calls `engine.run()` then `save_detections()` if engine is wired, wrapped in try/except (non-fatal)

### App Lifespan (`backend/main.py`, `backend/api/ingest.py`)
- Block 7g initialises `CorrelationEngine(stores=stores)` and stores in `app.state`
- `_get_loader()` in `ingest.py` passes `_correlation_engine_for_ingester` to the loader

## Test Results

```
tests/unit/test_correlation_engine.py: 6 passed, 3 skipped
  PASSED: test_correlation_engine_module_exists
  PASSED: test_port_scan_detection
  PASSED: test_brute_force_detection
  PASSED: test_beaconing_cv_detection
  PASSED: test_detection_record_created
  PASSED: test_dedup_suppresses_repeat
  SKIPPED: test_chain_detection (Plan 43-03)
  SKIPPED: test_chain_yaml_loading (Plan 43-03)
  SKIPPED: test_ingest_hook_calls_correlation (Plan 43-03)

Full suite: 1064 passed, 6 skipped — zero regressions (was 1059 before plan)
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Config] ANOMALY_DEDUP_WINDOW_MINUTES added**
- **Found during:** Task 1 (config.py editing)
- **Issue:** Plan mentioned this setting as an example for placement location but it wasn't in config.py
- **Fix:** Added alongside CORRELATION_* settings
- **Files modified:** backend/core/config.py

**2. [Rule 1 - Bug] Test file restoration after linter revert**
- **Found during:** Task 1 test execution
- **Issue:** An automated linter reverted the test file working copy to the old stub version after each Write. The committed version was correct; working copy was being overwritten.
- **Fix:** Used `git checkout tests/unit/test_correlation_engine.py` to restore committed version
- **Impact:** None — committed version was correct throughout

## Self-Check: PASSED

- [x] `detections/correlation_engine.py` exists and importable
- [x] `CORRELATION_LOOKBACK_HOURS` in config.py: verified via grep
- [x] `CORRELATION_DEDUP_WINDOW_MINUTES` in config.py: verified via grep
- [x] `entity_key TEXT` migration in sqlite_store.py: committed
- [x] `insert_detection()` includes entity_key: committed
- [x] `correlation_engine=None` in IngestionLoader: committed
- [x] Step 5 in `ingest_events()`: committed
- [x] Block 7g in main.py: committed
- [x] All 6 target tests GREEN: confirmed via pytest output
- [x] 1064 total unit tests green: confirmed
- [x] Commits exist: 570a7d2, b262455, 6dcb31e
