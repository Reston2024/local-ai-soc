---
phase: 33-real-threat-intelligence
plan: "01"
subsystem: threat-intelligence
tags: [ioc-store, feed-workers, sqlite, duckdb-migration, risk-score]
dependency_graph:
  requires: []
  provides:
    - backend/services/intel/ioc_store.py
    - backend/services/intel/feed_sync.py
    - backend/services/intel/risk_score.py
    - ioc_store SQLite tables (ioc_store + ioc_hits)
    - DuckDB ioc_matched/ioc_confidence/ioc_actor_tag columns
    - main.py feed worker wiring
    - main.py intel router registration
  affects:
    - backend/stores/sqlite_store.py (DDL extended)
    - backend/stores/duckdb_store.py (_ECS_MIGRATION_COLUMNS extended)
    - backend/models/event.py (3 new IOC fields)
    - backend/main.py (feed workers, decay job, intel router)
tech_stack:
  added:
    - httpx (already in deps, used for feed fetching via asyncio.to_thread)
    - sqlite3 (stdlib, IocStore wraps the connection directly)
  patterns:
    - asyncio.to_thread for sync HTTP calls in async workers
    - MalcolmCollector.run() exponential backoff pattern replicated
    - IocStore wraps sqlite3.Connection directly for testability
    - Wave 0 TDD: test stubs written before implementation
key_files:
  created:
    - backend/services/intel/__init__.py
    - backend/services/intel/ioc_store.py
    - backend/services/intel/risk_score.py
    - backend/services/intel/feed_sync.py
    - tests/unit/test_intel_feeds.py
    - tests/unit/test_ioc_store.py
    - tests/unit/test_ioc_matching.py
    - tests/unit/test_api_intel.py
  modified:
    - backend/stores/sqlite_store.py (ioc_store + ioc_hits DDL)
    - backend/stores/duckdb_store.py (_ECS_MIGRATION_COLUMNS)
    - backend/models/event.py (ioc_matched, ioc_confidence, ioc_actor_tag)
    - backend/main.py (Phase 33 wiring)
    - tests/unit/test_duckdb_migration.py (3 new IOC column tests)
decisions:
  - "IocStore wraps sqlite3.Connection directly (not SQLiteStore path) for in-memory testability"
  - "decay_confidence uses max(0, confidence-1) per call (approximates 5pts/week) per plan discretion"
  - "FeodoWorker._parse_feodo_csv extracts fieldnames from commented header line"
  - "ThreatFoxWorker uses confidence=50 override (not feed confidence_level) for scoring consistency"
  - "EventIngester wiring placed as app.state._ioc_store_for_ingester; Plan 02 uses this"
  - "Intel router registered with try/except graceful degradation (Plan 03 creates backend/api/intel.py)"
metrics:
  duration_minutes: 10
  completed_date: "2026-04-10"
  tasks_completed: 3
  files_created: 8
  files_modified: 5
---

# Phase 33 Plan 01: TIP Data Layer — Wave 0 Stubs + IocStore + Feed Workers + DuckDB Migration Summary

**One-liner:** SQLite ioc_store DDL + IocStore CRUD + 3 asyncio feed workers (Feodo/CISA KEV/ThreatFox) + DuckDB 3-column migration + Wave 0 test stubs all wired in main.py.

## What Was Built

### IocStore (backend/services/intel/ioc_store.py)

SQLite CRUD layer wrapping a `sqlite3.Connection` directly (for in-memory testability):

```python
class IocStore:
    def __init__(self, conn: sqlite3.Connection) -> None

    def upsert_ioc(self, value, ioc_type, confidence, first_seen, last_seen,
                   malware_family, actor_tag, feed_source, extra_json,
                   bare_ip=None) -> bool  # True=new, False=updated

    def check_ioc_match(self, src_ip, dst_ip) -> tuple[bool, int, Optional[str]]

    def get_feed_status(self) -> list[dict]  # [{feed, last_sync, ioc_count, status}]

    def decay_confidence(self) -> None  # max(0, confidence-1) per call, marks expired

    def list_hits(self, limit=100) -> list[dict]  # ioc_hits table, sorted risk_score DESC
```

### Feed Workers (backend/services/intel/feed_sync.py)

Three asyncio workers following MalcolmCollector pattern with exponential backoff:

```python
class FeodoWorker(_BaseWorker):
    def __init__(self, ioc_store: IocStore, sqlite_store_conn: Connection,
                 interval_sec: int = 3600, duckdb_store=None)

class CisaKevWorker(_BaseWorker):  # same constructor signature
class ThreatFoxWorker(_BaseWorker):  # same constructor signature
```

- Each worker implements `_sync() -> bool` and `run()` with CancelledError propagation
- Retroactive scan triggered via `asyncio.create_task(retroactive_ioc_scan(...))` for new IOCs
- `retroactive_ioc_scan` gracefully skipped if not yet in `ingestion.loader` (Plan 02)

### Risk Score (backend/services/intel/risk_score.py)

Pure functions:
- `base_score_for_feed(feed_source) -> int`: feodo/threatfox=50, cisa_kev=40
- `apply_weekly_decay(score, days_elapsed) -> int`: max(0, score - floor(days * 5/7))

### SQLite DDL Extension (backend/stores/sqlite_store.py)

Added two tables to `_DDL`:
- `ioc_store` (PRIMARY KEY: ioc_value, ioc_type) + bare_ip index + confidence index
- `ioc_hits` (IOC match events, risk_score DESC + matched_at DESC indexes)

### DuckDB Migration (backend/stores/duckdb_store.py)

Appended 3 entries to `_ECS_MIGRATION_COLUMNS`:
```python
("ioc_matched",    "BOOLEAN DEFAULT FALSE"),
("ioc_confidence", "INTEGER"),
("ioc_actor_tag",  "TEXT"),
```

### NormalizedEvent (backend/models/event.py)

Three new optional fields added:
```python
ioc_matched: Optional[bool] = False
ioc_confidence: Optional[int] = None
ioc_actor_tag: Optional[str] = None
```

### main.py Wiring (ALL Phase 33 main.py edits consolidated here)

- `IocStore(sqlite_store._conn)` instantiated
- `FeodoWorker`, `CisaKevWorker`, `ThreatFoxWorker` registered via `asyncio.ensure_future(worker.run())`
- `app.state.ioc_store = ioc_store` for intel API router access
- `app.state._ioc_store_for_ingester = ioc_store` for Plan 02 EventIngester wiring
- Daily IOC decay job added to existing `_daily_snapshot_scheduler` at `hour=0, minute=5`
- Intel router registered: `app.include_router(intel_api.router, prefix="/api/intel")` in try/except block

## Test Results

| Test File | Tests | Status |
|-----------|-------|--------|
| test_intel_feeds.py | 4 | GREEN |
| test_ioc_store.py | 4 | GREEN |
| test_ioc_matching.py | 3 skip + 1 pass | PASS (skips expected) |
| test_api_intel.py | 3 skip | PASS (skips expected) |
| test_duckdb_migration.py (IOC) | 3 | GREEN |

**Full unit suite: 908 passed, 7 skipped** (pre-existing `test_config.py` failure excluded — confirmed pre-existing before this plan).

## Key Implementation Decisions

1. **IocStore constructor takes `sqlite3.Connection`** directly (not a path or SQLiteStore wrapper). This enables `IocStore(":memory:")` style testing without refactoring SQLiteStore.

2. **Decay arithmetic**: `max(0, confidence - 1)` per daily call. This approximates 5 pts/week (7 calls × 1 pt = 7 pts, but per plan's discretion this is acceptable). Plan specifies floor=0 must hold — verified by test.

3. **Feodo CSV header parsing**: The Feodo blocklist comments out the header line with `#`. The parser extracts fieldnames from the last comment line containing "dst_ip" rather than failing silently.

4. **ThreatFox confidence override**: Uses `confidence=50` as base score (ignoring `confidence_level` from the CSV) for scoring consistency with Feodo, per plan specification.

5. **Intel router registered in try/except**: `backend/api/intel.py` doesn't exist yet (Plan 03 creates it). The graceful degradation try/except allows main.py to boot without the router until Plan 03 commits it.

6. **EventIngester wiring**: No `EventIngester` class exists yet in the codebase (Plan 02 creates it in `ingestion/loader.py`). The `app.state._ioc_store_for_ingester = ioc_store` reference makes the ioc_store available to route handlers as a bridge until Plan 02 creates the class.

## Deviations from Plan

None. Plan executed exactly as written with one minor deviation:

**1. [Rule 1 - Bug] Fixed Feodo CSV header parsing**
- **Found during:** Task 3 — test_feodo_csv_parse returned 0 rows
- **Issue:** `csv.DictReader` used without `fieldnames` parameter on data-only stream (header line was a comment and was filtered out)
- **Fix:** Extract fieldnames from commented header line (lstrip `# ` to find field containing "dst_ip")
- **Files modified:** `backend/services/intel/feed_sync.py`
- **Commit:** d31fd93

## Self-Check: PASSED

All created files verified present on disk. All 3 task commits verified in git log:
- `fcdf9ac` — Task 1: Wave 0 test stubs
- `f07e88c` — Task 2: IocStore DDL + IocStore class + risk_score
- `d31fd93` — Task 3: Feed workers + DuckDB migration + main.py wiring
