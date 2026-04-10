---
phase: 33-real-threat-intelligence
plan: "02"
subsystem: ingestion-pipeline
tags: [ioc-matching, threat-intel, duckdb, sqlite, ingest, retroactive-scan]
dependency_graph:
  requires: [33-01]
  provides: [at-ingest-ioc-matching, retroactive-ioc-scan, ioc-hits-recording]
  affects: [backend/models/event.py, ingestion/loader.py, backend/services/intel/ioc_store.py]
tech_stack:
  added: []
  patterns: [sync-in-thread IOC check, asyncio.to_thread retroactive scan, EventIngester alias]
key_files:
  created: []
  modified:
    - backend/models/event.py
    - ingestion/loader.py
    - backend/services/intel/ioc_store.py
    - tests/unit/test_normalized_event.py
    - tests/unit/test_normalized_event_ecs.py
decisions:
  - "_apply_ioc_matching is synchronous and calls _record_hit directly — safe because it only runs inside asyncio.to_thread() batch wrapper in ingest_events()"
  - "retroactive_ioc_scan uses asyncio.to_thread() for both execute_write and _record_hit — it is async and called from event loop context via asyncio.create_task()"
  - "EventIngester = IngestionLoader alias — preserves all existing code using IngestionLoader while satisfying main.py Plan 01 wiring contract"
  - "Row access in retroactive_ioc_scan handles both dict-like (real DuckDB) and tuple (test mock) rows for test compatibility"
  - "_record_hit added to IocStore (was referenced in plan but missing from Plan 01 implementation — auto-fixed Rule 3)"
metrics:
  duration_minutes: 20
  completed_date: "2026-04-10"
  tasks_completed: 2
  files_modified: 5
---

# Phase 33 Plan 02: IOC Matching Pipeline Summary

IOC matching wired into at-ingest pipeline and retroactive scan added — every event is checked against the threat store at ingest, historical events are back-filled when new IOCs arrive.

## What Was Built

### Task 1: Extend NormalizedEvent + _INSERT_SQL + to_duckdb_row()

**Files modified:** `backend/models/event.py`, `ingestion/loader.py`

- `to_duckdb_row()` updated from 55 to 58 elements — 3 IOC fields appended at positions 55-57
- `_INSERT_SQL` updated from 55 to 58 columns + matching `?` placeholders
- IOC fields already existed on the model (added in Plan 01); only the tuple return and INSERT SQL needed updating

**to_duckdb_row() column count:** 58

| Position | Field | Notes |
|----------|-------|-------|
| 55 | `ioc_matched` | `False` when `None` (default) |
| 56 | `ioc_confidence` | `int \| None` |
| 57 | `ioc_actor_tag` | `str \| None` |

### Task 2: _apply_ioc_matching() + retroactive_ioc_scan() + ioc_hits recording + feed_sync update

**Files modified:** `ingestion/loader.py`, `backend/services/intel/ioc_store.py`

#### _apply_ioc_matching() function signature

```python
def _apply_ioc_matching(event: NormalizedEvent, ioc_store: IocStore) -> NormalizedEvent:
```

- Module-level synchronous function in `ingestion/loader.py`
- Calls `ioc_store.check_ioc_match(event.src_ip, event.dst_ip)`
- On match: sets `ioc_matched=True`, `ioc_confidence`, `ioc_actor_tag` and calls `ioc_store._record_hit()` directly
- Safe to call `_record_hit()` synchronously here — only ever called from inside `asyncio.to_thread()` context

#### retroactive_ioc_scan() function signature

```python
async def retroactive_ioc_scan(
    ioc_value: str,
    ioc_type: str,
    bare_ip: str | None,
    confidence: int,
    ioc_store: IocStore,
    duckdb_store: Any,
) -> int:
```

- Async module-level function in `ingestion/loader.py`
- Queries `normalized_events WHERE timestamp >= now() - INTERVAL '30 days'` for IP matches
- For each hit: calls `asyncio.to_thread(duckdb_store.execute_write, "UPDATE normalized_events SET ioc_matched=TRUE ...")` and `asyncio.to_thread(ioc_store._record_hit, ...)`
- Returns count of rows updated

#### EventIngester constructor signature

```python
# EventIngester = IngestionLoader (alias)
def __init__(
    self,
    stores: Stores,
    ollama_client: OllamaClient,
    ioc_store: IocStore | None = None,
) -> None:
```

- `IngestionLoader.__init__()` now accepts `ioc_store: IocStore | None = None`
- `EventIngester = IngestionLoader` alias added at module bottom
- Backward-compatible (default `None` — existing code unaffected)

#### Worker constructor signatures (feed_sync.py)

All three workers (`FeodoWorker`, `CisaKevWorker`, `ThreatFoxWorker`) inherit from `_BaseWorker`:

```python
def __init__(
    self,
    ioc_store: IocStore,
    sqlite_store_conn: sqlite3.Connection,
    interval_sec: int = 3600,
    duckdb_store: DuckDBStore | None = None,
) -> None:
```

`_trigger_retroactive_scan()` implemented in `_BaseWorker` — calls `asyncio.create_task(retroactive_ioc_scan(...))` when `_duckdb_store is not None` and the IOC is new.

#### _record_hit() added to IocStore

Plan 01 referenced `ioc_store._record_hit()` but did not implement it. Added in Task 2 (Rule 3 auto-fix — blocking issue):

```python
def _record_hit(
    self,
    event_timestamp: str,
    hostname: Optional[str],
    src_ip: Optional[str],
    dst_ip: Optional[str],
    ioc_value: str,
    ioc_type: str,
    ioc_source: str,
    risk_score: int,
    actor_tag: Optional[str],
    malware_family: Optional[str],
) -> None:
```

Inserts into `ioc_hits` SQLite table. Synchronous — callers use `asyncio.to_thread()` when calling from async context.

#### upsert_ioc() returns bool — confirmed

From `33-01-SUMMARY.md` and verified in `ioc_store.py`:
- `True` — new row inserted (triggers retroactive scan in feed workers)
- `False` — existing row updated (no retroactive scan triggered)

## Threading Model

| Function | Context | SQLite calls |
|----------|---------|-------------|
| `_apply_ioc_matching()` | Sync, runs inside `asyncio.to_thread()` | Direct (safe) |
| `retroactive_ioc_scan()` | Async, runs on event loop | `asyncio.to_thread()` wrappers |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added missing _record_hit() to IocStore**
- **Found during:** Task 2 implementation
- **Issue:** Plan 02 references `ioc_store._record_hit()` throughout the at-ingest flow, but the method was not implemented in Plan 01's `ioc_store.py`
- **Fix:** Added `_record_hit()` synchronous method to `IocStore` that INSERTs into the `ioc_hits` table
- **Files modified:** `backend/services/intel/ioc_store.py`
- **Commit:** 3365885

**2. [Rule 1 - Bug] Updated tuple-count assertions in existing tests**
- **Found during:** Task 1 (full unit suite run)
- **Issue:** `test_normalized_event.py::test_new_fields_in_duckdb_row` and `test_normalized_event_ecs.py::test_to_duckdb_row_includes_new_fields` asserted `len(row) == 55` — correct before but wrong after extending to 58
- **Fix:** Updated both tests to assert `len(row) == 58` and added assertions for positions 55-57
- **Files modified:** `tests/unit/test_normalized_event.py`, `tests/unit/test_normalized_event_ecs.py`
- **Commit:** 3365885

## Verification Results

```
uv run pytest tests/unit/test_ioc_matching.py -v → 4 passed
uv run pytest tests/unit/ (excl. pre-existing test_config.py failure) → 914 passed
python -c "from ingestion.loader import _apply_ioc_matching, retroactive_ioc_scan" → OK
python -c "...len(e.to_duckdb_row()) == 58..." → OK
python -c "FeodoWorker.__init__ has duckdb_store param" → OK
python -c "EventIngester.__init__ has ioc_store param" → OK
```

Pre-existing failure: `test_config.py::test_cybersec_model_default` — asserts `OLLAMA_CYBERSEC_MODEL == "foundation-sec:8b"` but env has `llama3:latest`. Existed before Plan 02, unrelated to IOC matching changes.

## Self-Check: PASSED

- `backend/models/event.py` — exists, ioc fields + 58-element tuple
- `ingestion/loader.py` — exists, _apply_ioc_matching + retroactive_ioc_scan + EventIngester
- `backend/services/intel/ioc_store.py` — exists, _record_hit method added
- Task 1 commit: `6f0d702`
- Task 2 commit: `3365885`
