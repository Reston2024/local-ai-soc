---
phase: 09-intelligence-analyst-augmentation
plan: "02"
subsystem: persistence
tags: [sqlite, schema-migration, crud, tdd]
dependency_graph:
  requires: [09-00]
  provides: [saved_investigations table, risk_score column, save_investigation(), list_saved_investigations(), get_saved_investigation()]
  affects: [backend/stores/sqlite_store.py, tests/unit/test_sqlite_store.py]
tech_stack:
  added: []
  patterns: [ALTER TABLE idempotent migration, synchronous sqlite3 CRUD]
key_files:
  created: []
  modified:
    - backend/stores/sqlite_store.py
    - tests/unit/test_sqlite_store.py
decisions:
  - "Used uuid4().hex (32-char hex string) as investigation ID — consistent with existing uuid4() usage in store"
  - "ALTER TABLE migration wrapped in try/except — idempotent for existing databases"
  - "saved_investigations DDL added to _DDL string (executescript) so table is created on every fresh init"
  - "Removed strict=True xfail markers after implementation — tests pass cleanly rather than XPASS(strict) FAILED"
metrics:
  duration: "5 minutes"
  completed_date: "2026-03-25"
  tasks_completed: 1
  files_modified: 2
---

# Phase 9 Plan 02: SQLiteStore saved_investigations Schema and CRUD Summary

SQLiteStore extended with saved_investigations table (graph snapshot persistence) and backward-compatible risk_score migration on detections table.

## What Was Built

- `saved_investigations` table added to `_DDL` string with columns: `id TEXT PRIMARY KEY`, `detection_id TEXT`, `graph_snapshot TEXT NOT NULL`, `metadata TEXT`, `created_at TEXT NOT NULL`, plus a `idx_saved_inv_detection` index.
- Backward-compatible `ALTER TABLE detections ADD COLUMN risk_score INTEGER DEFAULT 0` migration in `__init__`, wrapped in try/except for idempotency on existing databases.
- Three new CRUD methods on `SQLiteStore`:
  - `save_investigation(detection_id, graph_snapshot, metadata) -> str` — inserts snapshot row, returns `uuid4().hex` ID
  - `list_saved_investigations() -> list[dict]` — returns all records newest-first, metadata deserialized
  - `get_saved_investigation(investigation_id) -> dict | None` — returns full record with graph_snapshot deserialized, or None

## Test Results

- `tests/unit/test_sqlite_store.py::TestSavedInvestigations` — all 3 tests PASS (previously xfail stubs)
- Full unit suite: **82 passed, 12 xfailed, 4 xpassed, 0 failed**

## Commits

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Extend SQLiteStore schema and add saved_investigations CRUD | 42ab930 | backend/stores/sqlite_store.py, tests/unit/test_sqlite_store.py |

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check: PASSED

- `backend/stores/sqlite_store.py` — FOUND
- `tests/unit/test_sqlite_store.py` — FOUND
- Commit `42ab930` — FOUND
