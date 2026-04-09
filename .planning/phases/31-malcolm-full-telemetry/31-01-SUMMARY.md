---
phase: 31-malcolm-full-telemetry
plan: "01"
subsystem: ingestion/malcolm
tags: [schema, normalization, eve, tls, dns, fileinfo, anomaly, duckdb, tdd]
dependency_graph:
  requires: []
  provides:
    - NormalizedEvent with 55-column to_duckdb_row() (dns_*, tls_*, file_*, http_* fields)
    - DuckDB 26-entry _ECS_MIGRATION_COLUMNS (idempotent ADD COLUMN migration)
    - loader.py _INSERT_SQL with 55 ? placeholders
    - MalcolmCollector _normalize_tls/_normalize_dns/_normalize_fileinfo/_normalize_anomaly
    - MalcolmCollector _poll_and_ingest() polling 6 EVE sources
  affects:
    - ingestion/loader.py (INSERT SQL column count)
    - backend/models/event.py (NormalizedEvent schema)
    - backend/stores/duckdb_store.py (migration columns)
    - ingestion/jobs/malcolm_collector.py (normalizers + poll loop)
tech_stack:
  added: []
  patterns:
    - 3-level field fallback (nested ECS -> arkime-flat -> fully-flat)
    - json.dumps() for dns_answers list storage
    - Separate SQLite cursor key per EVE type
key_files:
  created:
    - tests/unit/test_normalized_event.py
  modified:
    - backend/models/event.py
    - backend/stores/duckdb_store.py
    - ingestion/loader.py
    - ingestion/jobs/malcolm_collector.py
    - tests/unit/test_malcolm_collector.py
    - tests/unit/test_normalized_event_ecs.py
decisions:
  - "dns_answers stored as json.dumps() string (TEXT column) — avoids array type in DuckDB"
  - "event_type_filter and event_dataset_filter are independent in _build_query()"
  - "tls_validation_status mapped from boolean established: True=valid, False=failed, None=None"
metrics:
  duration: "9 minutes"
  completed_date: "2026-04-09"
  tasks_completed: 3
  files_modified: 6
---

# Phase 31 Plan 01: Malcolm EVE Protocol Telemetry — Schema Expansion Summary

**One-liner:** NormalizedEvent expanded from 35 to 55 columns with dns_*/tls_*/file_*/http_* EVE protocol fields, matching DuckDB migration and loader INSERT SQL, plus four new normalizers and 6-source poll loop in MalcolmCollector.

## What Was Built

All three sync points were updated atomically to support 20 new EVE protocol fields:

1. **NormalizedEvent** (`backend/models/event.py`) — 20 new Optional fields added at positions 35-54 in `to_duckdb_row()`. OCSF_CLASS_UID_MAP extended with `tls=4001`, `file_transfer=1001`, `anomaly=4001`.

2. **DuckDB Store** (`backend/stores/duckdb_store.py`) — `_ECS_MIGRATION_COLUMNS` expanded from 6 to 26 entries. The existing `try/except` idempotency pattern safely handles re-runs.

3. **Loader** (`ingestion/loader.py`) — `_INSERT_SQL` now has 55 column names and 55 `?` placeholders (was 35).

4. **MalcolmCollector** (`ingestion/jobs/malcolm_collector.py`) — Four new normalizer methods with 3-level field fallback, expanded `_poll_and_ingest()` polling 6 sources (alerts, tls, dns, fileinfo, anomaly, syslog) with separate cursor keys, and 4 new counters in `status()`.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 0 (RED) | Write failing test stubs | fbf323e | tests/unit/test_normalized_event.py, tests/unit/test_malcolm_collector.py |
| 1 (GREEN) | Expand NormalizedEvent + OCSF + DuckDB + loader | 0119fd1 | backend/models/event.py, backend/stores/duckdb_store.py, ingestion/loader.py, tests/unit/test_normalized_event_ecs.py |
| 2 (GREEN) | Add four EVE normalizers + expand poll loop | b6b5a4d | ingestion/jobs/malcolm_collector.py, tests/unit/test_malcolm_collector.py |

## Verification Results

- `to_duckdb_row()` length: **55** (verified)
- `_INSERT_SQL` placeholder count: **55** (verified)
- `_ECS_MIGRATION_COLUMNS` count: **26** (6 original + 20 new, verified)
- OCSF map: `tls=4001`, `file_transfer=1001`, `anomaly=4001` (verified)
- All 12 unit tests in test_normalized_event.py + test_malcolm_collector.py: **PASS**
- Full unit suite (881 tests): **PASS**

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated test_normalized_event_ecs.py column count assertion**
- **Found during:** Task 1
- **Issue:** `test_to_duckdb_row_includes_new_fields` asserted `len(row) == 35` which would fail after expanding to 55 columns.
- **Fix:** Updated assertion to `len(row) == 55` with explanatory comment noting Phase 31 expansion. ECS field positions 29-34 unchanged.
- **Files modified:** `tests/unit/test_normalized_event_ecs.py`
- **Commit:** 0119fd1

## Self-Check: PASSED

- tests/unit/test_normalized_event.py: FOUND
- backend/models/event.py: FOUND
- .planning/phases/31-malcolm-full-telemetry/31-01-SUMMARY.md: FOUND
- Commit fbf323e (Task 0 RED stubs): FOUND
- Commit 0119fd1 (Task 1 schema sync): FOUND
- Commit b6b5a4d (Task 2 normalizers): FOUND
