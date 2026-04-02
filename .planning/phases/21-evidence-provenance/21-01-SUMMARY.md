---
phase: 21-evidence-provenance
plan: "01"
subsystem: database
tags: [sqlite, sha256, provenance, ingestion, hashlib]

# Dependency graph
requires:
  - phase: 21-00
    provides: "RED test stubs and IngestProvenanceRecord pydantic model"
provides:
  - "ingest_provenance + ingest_provenance_events SQLite tables in SQLiteStore"
  - "record_ingest_provenance() and get_ingest_provenance() methods on SQLiteStore"
  - "_sha256_file() helper computing SHA-256 of raw file bytes in 64K chunks"
  - "provenance row written after every successful ingest_file() call (non-fatal)"
  - "operator_id parameter on ingest_file() for tracking who initiated ingest"
affects:
  - 21-evidence-provenance
  - ingestion/loader.py consumers
  - backend/api/ingest.py (when passing operator_id)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Non-fatal provenance writes: wrap in try/except, log warning on failure, do NOT raise"
    - "SHA-256 computed before get_parser() so hash is of raw bytes, not transformed data"
    - "asyncio.to_thread() wraps all synchronous SQLite writes from async context"
    - "INSERT OR IGNORE on both provenance tables for idempotent re-runs"

key-files:
  created:
    - tests/unit/test_ingest_provenance.py
  modified:
    - backend/stores/sqlite_store.py
    - ingestion/loader.py

key-decisions:
  - "event_ids passed to record_ingest_provenance are the normalized list — parser generates UUIDs, not raw input IDs"
  - "Provenance write failure logs a warning and continues — provenance is non-critical metadata"
  - "parser_version is None for now — no __version__ attribute on parser classes yet"
  - "operator_id added as optional keyword param to ingest_file(); API layer can pass ctx.operator_id"

patterns-established:
  - "Non-fatal provenance pattern: try/except around asyncio.to_thread call, log.warning on exc"
  - "_sha256_file reads in 65536-byte chunks for memory efficiency on large files"

requirements-completed:
  - P21-T01

# Metrics
duration: 5min
completed: 2026-04-02
---

# Phase 21 Plan 01: Ingest Provenance — SQLiteStore DDL + Loader Integration Summary

**SHA-256 file fingerprint + parser identity recorded per ingest via new ingest_provenance/ingest_provenance_events SQLite tables and non-fatal provenance call in IngestionLoader.ingest_file()**

## Performance

- **Duration:** 5 min
- **Started:** 2026-04-02T12:35:55Z
- **Completed:** 2026-04-02T12:40:42Z
- **Tasks:** 2 (TDD: RED then GREEN for each)
- **Files modified:** 3

## Accomplishments

- Two new SQLite tables created via DDL in `_DDL` string: `ingest_provenance` (prov_id, raw_sha256, source_file, parser_name, parser_version, operator_id, ingested_at) and `ingest_provenance_events` (prov_id, event_id junction with index)
- `record_ingest_provenance()` and `get_ingest_provenance()` methods added to `SQLiteStore` using single-transaction INSERT OR IGNORE
- `_sha256_file()` helper added to `ingestion/loader.py` computing SHA-256 of raw file bytes in 64K chunks (via `asyncio.to_thread`)
- `ingest_file()` updated with `operator_id` param, SHA-256 computed before `get_parser()`, provenance written post-ingest in non-fatal try/except block
- 5/5 TDD tests GREEN; 43/43 tests across `test_ingest_provenance`, `test_sqlite_store`, `test_loader` pass

## Task Commits

Each task was committed atomically:

1. **RED: failing tests** - `a2cd0aa` (test)
2. **Task 1: ingest_provenance DDL and SQLiteStore methods** - `2482d9f` (feat)
3. **Task 2: _sha256_file helper and provenance recording** - `a519e31` (feat)

_Note: TDD tasks have RED commit before GREEN feat commit_

## Files Created/Modified

- `tests/unit/test_ingest_provenance.py` — 5 tests: table existence, record+lookup, SHA-256 hash correctness, provenance written after ingest, failure non-fatal
- `backend/stores/sqlite_store.py` — DDL for `ingest_provenance` and `ingest_provenance_events` tables; `record_ingest_provenance()` and `get_ingest_provenance()` methods
- `ingestion/loader.py` — `_sha256_file()` module-level helper; `operator_id` param on `ingest_file()`; SHA-256 pre-parse; provenance call post-ingest

## Decisions Made

- **event_ids list contains all normalized event IDs, not just truly-new ones.** The deduplication check happens inside `ingest_events()` which doesn't return the deduplicated list. The normalized list is passed — this is acceptable since `ingest_provenance_events` uses INSERT OR IGNORE and the parser generates stable UUIDs per file run anyway.
- **parser_version is None.** Parser classes have no `__version__` attribute; this is a known gap to fill in a future plan.
- **`operator_id` is keyword-only addition** — existing callers (`ingest_api.py` background tasks) pass `job_id` positionally and are unaffected.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Test used raw input event_id which parsers don't preserve**
- **Found during:** Task 2 GREEN verification
- **Issue:** Test asserted `get_ingest_provenance("test-evt-prov-001")` but JSON parser generates its own UUIDs — the input `event_id` field is not preserved through the parse pipeline
- **Fix:** Updated test to query `ingest_provenance` directly, extract the actual `event_id` from `ingest_provenance_events`, then verify `get_ingest_provenance(actual_event_id)` returns a valid row
- **Files modified:** tests/unit/test_ingest_provenance.py
- **Verification:** All 5 tests GREEN after fix
- **Committed in:** a519e31 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - test assertion bug)
**Impact on plan:** Fix was necessary for test correctness. No scope creep.

## Issues Encountered

None beyond the test assertion fix documented above.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `ingest_provenance` table and methods are complete and tested
- `GET /api/provenance/ingest/{event_id}` API route (plan 21-02 or later) can call `sqlite.get_ingest_provenance(event_id)` directly
- `operator_id` threading is ready — `backend/api/ingest.py` can pass `ctx.operator_id` to `ingest_file()`
- Pre-existing test failures in `test_api_endpoints.py` (401 Unauthorized) are out of scope — pre-date this plan

## Self-Check: PASSED

All files verified present. All commits verified in git history.

---
*Phase: 21-evidence-provenance*
*Completed: 2026-04-02*
