---
phase: 52-thehive-case-management-integration
plan: "01"
subsystem: testing
tags: [thehive4py, tdd, wave0, case-management, sqlite, observables]

requires:
  - phase: 51-spiderfoot-osint-investigation-platform
    provides: per-test skipif guard pattern for optional service stubs

provides:
  - Wave 0 TDD stubs for TheHiveClient (5 tests) defining severity mapping, suppress list, observables, retry queue, ping behavior
  - Wave 0 TDD stubs for TheHive sync (3 tests) defining drain_pending_cases, sync_thehive_closures, error tolerance contracts
  - thehive4py==2.0.3 installed as project dependency

affects:
  - 52-02-PLAN (implements backend/services/thehive_client.py — will turn stubs GREEN)
  - 52-03-PLAN (implements backend/services/thehive_sync.py — will turn stubs GREEN)

tech-stack:
  added: [thehive4py==2.0.3]
  patterns:
    - Per-test skipif guard (if not _TH_AVAILABLE: pytest.skip()) rather than module-level pytestmark
    - Separate availability flags per source module (_TH_AVAILABLE for client, _TH_SYNC_AVAILABLE for sync)
    - In-memory sqlite3 for retry queue and closure sync tests — no SQLiteStore wrapper needed

key-files:
  created:
    - tests/unit/test_thehive_client.py
    - tests/unit/test_thehive_sync.py
  modified:
    - pyproject.toml (thehive4py==2.0.3 added)
    - uv.lock

key-decisions:
  - "52-01: Per-test skipif guard (not module-level pytestmark) so individual tests can fail RED independently when source exists but broken — matches Phase 44/45/48 pattern"
  - "52-01: Separate _TH_AVAILABLE and _TH_SYNC_AVAILABLE flags for two different source modules"
  - "52-01: test_enqueue_on_failure uses in-memory sqlite3 with thehive_pending_cases DDL pre-created — mirrors Plan 52-03 schema contract"
  - "52-01: test_ping_returns_false_when_unreachable patches client._api.case.find — assumes TheHiveApi instance stored as _api attribute on TheHiveClient"

patterns-established:
  - "Phase 52 TDD stub pattern: if not _TH_AVAILABLE: pytest.skip() at top of each test function"

requirements-completed:
  - REQ-52-01
  - REQ-52-02
  - REQ-52-03
  - REQ-52-04
  - REQ-52-06

duration: 12min
completed: 2026-04-16
---

# Phase 52 Plan 01: TheHive Case Management — Wave 0 TDD Stubs Summary

**thehive4py==2.0.3 installed; 8 Wave 0 stubs across 2 test files defining contracts for TheHiveClient severity mapping, observable builder, retry queue enqueue, ping, and closure sync with error tolerance**

## Performance

- **Duration:** 12 min
- **Started:** 2026-04-16T14:49:00Z
- **Completed:** 2026-04-16T15:01:01Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Installed thehive4py==2.0.3 as a project dependency (confirmed importable, version 2.0.3)
- Created `test_thehive_client.py` with 5 stubs covering: severity numeric scale mapping (high→3, critical→4), suppress list bypass, ip+other observables, SQLite retry queue enqueue on failure, and ping returning False when unreachable
- Created `test_thehive_sync.py` with 3 stubs covering: drain_pending_cases emptying thehive_pending_cases table after successful create_case calls, sync_thehive_closures writing resolutionStatus+assignee back to detections, and error tolerance (no raise on connection failure)
- All 8 stubs SKIP cleanly; full suite remains at 1177 passing, zero new failures

## Task Commits

Each task was committed atomically:

1. **Task 1: Install thehive4py and create test_thehive_client.py stubs** - `511eb6e` (test)
2. **Task 2: Create test_thehive_sync.py stubs** - `fdb279a` (test)

**Plan metadata:** (see final commit below)

## Files Created/Modified

- `tests/unit/test_thehive_client.py` — 5 Wave 0 stubs for TheHiveClient (build_case_payload, _maybe_create_thehive_case, build_observables, ping)
- `tests/unit/test_thehive_sync.py` — 3 Wave 0 stubs for drain_pending_cases and sync_thehive_closures
- `pyproject.toml` — thehive4py==2.0.3 added to dependencies
- `uv.lock` — lockfile updated with thehive4py and its dependencies

## Decisions Made

- Per-test skipif guard (not module-level pytestmark) so individual tests can fail RED independently when source module exists but is broken — matches Phase 44/45/48 established pattern
- Separate `_TH_AVAILABLE` and `_TH_SYNC_AVAILABLE` flags for the two source modules (thehive_client.py vs thehive_sync.py), so each test file independently tracks its own source availability
- `test_enqueue_on_failure` creates in-memory SQLite with `thehive_pending_cases` DDL matching the schema that Plan 52-02 will create — establishes the retry queue contract
- `test_ping_returns_false_when_unreachable` patches `client._api.case.find` — implies TheHiveClient wraps TheHiveApi as `self._api`; Plan 52-02 must implement accordingly

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required for stubs.

## Next Phase Readiness

- Plan 52-02 can now implement `backend/services/thehive_client.py` (TheHiveClient, build_case_payload, build_observables, _maybe_create_thehive_case) and turn all 5 stubs GREEN
- Plan 52-03 can implement `backend/services/thehive_sync.py` (drain_pending_cases, sync_thehive_closures) and turn all 3 sync stubs GREEN
- thehive4py==2.0.3 API confirmed importable — TheHiveApi.case attribute is the correct handle for ping test

---
*Phase: 52-thehive-case-management-integration*
*Completed: 2026-04-16*
