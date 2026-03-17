---
phase: 07-threat-hunting-case-management
plan: "01"
subsystem: database
tags: [sqlite, case-management, crud, investigation, tagging]

# Dependency graph
requires:
  - phase: 07-00
    provides: SQLiteStore DDL extensions (investigation_cases, case_artifacts, case_tags tables) and 6 stub methods + test_phase7.py xfail stubs

provides:
  - Full SQLiteStore investigation CRUD (create/get/list/update_investigation_case, insert_artifact, get_artifacts_by_case)
  - CaseManager class operating on raw sqlite3.Connection
  - tagging.py module (add_tag, remove_tag, list_tags, add_tags_to_case)
  - P7-T01, P7-T02, P7-T03 XPASS

affects:
  - 07-02 (hunt engine uses sqlite_store patterns)
  - 07-03 (timeline_builder + artifact_store build on same sqlite layer)
  - 07-04 (investigation REST routes use CaseManager)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "CaseManager accepts raw sqlite3.Connection as first arg — enables :memory: unit tests without SQLiteStore instantiation"
    - "JSON array fields (related_alerts, related_entities, timeline_events, tags, artifacts) stored as TEXT, deserialized on read via _parse_case()"
    - "update_investigation_case builds dynamic SET clause from updates dict keys — partial update with no unmentioned field clobbering"
    - "tagging.py uses INSERT OR IGNORE for idempotent tag insertion"

key-files:
  created:
    - backend/investigation/case_manager.py
    - backend/investigation/tagging.py
  modified:
    - backend/stores/sqlite_store.py

key-decisions:
  - "CaseManager operates on raw sqlite3.Connection (not SQLiteStore) to match test interface and enable :memory: testing"
  - "tagging.py is a standalone module with free functions (add_tag/remove_tag/list_tags) — not a class — to simplify asyncio.to_thread wrapping in route handlers"
  - "_parse_case() helper centralizes JSON deserialization for all array fields across get and list methods"

patterns-established:
  - "Pattern 1: CaseManager raw-conn interface — future Plan 03/04 code passes sqlite_store._conn directly"
  - "Pattern 2: Dynamic SET clause for partial updates — avoids overwriting unspecified fields"

requirements-completed: [P7-T01, P7-T02, P7-T03]

# Metrics
duration: 8min
completed: 2026-03-17
---

# Phase 7 Plan 01: CaseManager CRUD + Tagging Module Summary

**SQLite-backed investigation case CRUD via CaseManager (raw-conn interface) + tagging.py free-function module; P7-T01/T02/T03 XPASS**

## Performance

- **Duration:** 8 min
- **Started:** 2026-03-17T02:30:00Z
- **Completed:** 2026-03-17T02:38:00Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- SQLiteStore stub methods replaced with full implementations: create/get/list/update_investigation_case, insert_artifact, get_artifacts_by_case
- CaseManager class fully implemented using raw sqlite3.Connection (matching test interface)
- tagging.py implemented with add_tag (INSERT OR IGNORE idempotent), remove_tag, list_tags, add_tags_to_case
- P7-T01 (test_create_case_returns_id), P7-T02 (test_list_cases_empty), P7-T03 (test_update_case_status) all XPASS
- No regressions: 41 passed, 47 xpassed, 12 xfailed

## Task Commits

1. **Tasks 1 + 2: SQLiteStore methods + CaseManager + tagging.py** - `c0ada4b` (feat)

## Files Created/Modified

- `backend/stores/sqlite_store.py` - Replaced 6 NotImplementedError stubs with full implementations; added _parse_investigation_case static helper
- `backend/investigation/case_manager.py` - Full CaseManager CRUD class operating on raw sqlite3.Connection
- `backend/investigation/tagging.py` - add_tag, remove_tag, list_tags, add_tags_to_case free functions

## Decisions Made

- CaseManager uses raw sqlite3.Connection (not SQLiteStore) as the first method argument — this matches the test_phase7.py TestCaseManager tests which create :memory: databases directly. Route handlers will pass sqlite_store._conn.
- tagging.py is free functions rather than a class to make asyncio.to_thread() call patterns straightforward.
- _parse_case() helper consolidates JSON array field deserialization so both get_investigation_case and list_investigation_cases share the same logic.

## Deviations from Plan

The plan action block described CaseManager delegating to SQLiteStore methods, but the test file uses raw sqlite3.Connection objects passed directly. Implemented the raw-conn pattern to match the actual test interface. This is a minor interface adaptation, not an architectural change.

None — plan executed with one minor interface adaptation to match test expectations (raw sqlite3.Connection vs SQLiteStore delegation).

## Issues Encountered

None. Tests passed on first implementation attempt.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- CaseManager and tagging module ready for Plan 02 (hunt engine) and Plan 03 (timeline builder, artifact store, REST routes)
- Route handlers in Plan 04 will call `asyncio.to_thread(tagging.add_tag, sqlite_store._conn, case_id, tag)` per the pattern established here

---
*Phase: 07-threat-hunting-case-management*
*Completed: 2026-03-17*
