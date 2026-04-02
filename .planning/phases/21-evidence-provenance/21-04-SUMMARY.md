---
phase: 21-evidence-provenance
plan: "04"
subsystem: database
tags: [sqlite, provenance, playbook, sha256, audit]

# Dependency graph
requires:
  - phase: 21-evidence-provenance/21-01
    provides: SQLiteStore ingest_provenance pattern and record/get method conventions
  - phase: 21-evidence-provenance/21-02
    provides: SQLiteStore detection_provenance DDL and methods pattern

provides:
  - playbook_run_provenance SQLite table with idx_pb_prov_run index
  - SQLiteStore.record_playbook_provenance() inserts provenance with JSON trigger_event_ids
  - SQLiteStore.get_playbook_provenance(run_id) returns dict with deserialized list[str]
  - GET /api/provenance/playbook/{run_id} returns PlaybookProvenanceRecord or 404
  - Provenance written non-fatally in start_playbook_run() after playbook_runs INSERT

affects:
  - future playbook audit queries
  - provenance API consumers

# Tech tracking
tech-stack:
  added: []
  patterns:
    - playbook_file_sha256 computed as hashlib.sha256(steps_json.encode()).hexdigest() from the steps TEXT column
    - trigger_event_ids stored as JSON array in TEXT column, deserialized to list[str] on read
    - provenance write non-fatal: wrapped in try/except with log.warning, never blocks run creation

key-files:
  created: []
  modified:
    - backend/stores/sqlite_store.py
    - backend/api/playbooks.py
    - backend/api/provenance.py
    - tests/unit/test_playbook_provenance.py

key-decisions:
  - "21-04: operator_id_who_approved stored as NULL — not yet threaded through unauthenticated start_playbook_run route (consistent with 21-02 detection_provenance decision)"
  - "21-04: trigger_event_ids defaults to [] in start_playbook_run — route has no auth context so trigger IDs are not available; additive only, no breaking change to request model"
  - "21-04: steps column may be a Python list (already deserialized) — guarded with isinstance check before json.dumps call"

patterns-established:
  - "Playbook provenance pattern: DDL in _DDL, record_/get_ methods on SQLiteStore, non-fatal try/except write in route, GET endpoint on /api/provenance/ router"

requirements-completed:
  - P21-T04

# Metrics
duration: 15min
completed: 2026-04-02
---

# Phase 21 Plan 04: Playbook Run Provenance Summary

**playbook_run_provenance SQLite table with SHA-256 of playbook steps JSON, trigger event IDs, and approving operator; GET /api/provenance/playbook/{run_id} endpoint; 3/3 tests GREEN (P21-T04 satisfied)**

## Performance

- **Duration:** 15 min
- **Started:** 2026-04-02T12:50:24Z
- **Completed:** 2026-04-02T13:05:00Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Added `playbook_run_provenance` table to SQLiteStore DDL with `idx_pb_prov_run` index
- Implemented `record_playbook_provenance()` and `get_playbook_provenance()` methods with JSON list[str] deserialization
- Added provenance write to `start_playbook_run()` (non-fatal, wrapped in try/except)
- Added `GET /api/provenance/playbook/{run_id}` endpoint returning `PlaybookProvenanceRecord`

## Task Commits

Each task was committed atomically:

1. **RED: Add failing tests for playbook run provenance** - `bb6f77d` (test)
2. **Task 1: Add playbook_run_provenance DDL and methods to SQLiteStore** - `53b7126` (feat)
3. **Task 2: Write playbook run provenance in the run-creation route** - `f5d0542` (feat)

## Files Created/Modified

- `backend/stores/sqlite_store.py` - Added playbook_run_provenance DDL, record_playbook_provenance(), get_playbook_provenance()
- `backend/api/playbooks.py` - Added hashlib import, provenance write in start_playbook_run()
- `backend/api/provenance.py` - Added GET /api/provenance/playbook/{run_id} endpoint
- `tests/unit/test_playbook_provenance.py` - Replaced stubs with 3 real tests (table exists, roundtrip fields, API endpoint)

## Decisions Made

- `operator_id_who_approved` stored as NULL in the initial implementation — the `start_playbook_run` route has no auth context yet (consistent with the 21-02 decision for detection_provenance)
- `trigger_event_ids` defaults to `[]` — the unauthenticated run-creation path does not supply trigger IDs; the field is available for callers that do
- `steps` column defensive handling: guarded with `isinstance(steps_json, str)` check before encoding, since SQLiteStore's `get_playbook()` may return an already-deserialized list

## Deviations from Plan

None - plan executed exactly as written. The only minor adaptation was storing `operator_id_who_approved=None` because the route has no auth dependency, which is the same pattern used in Plan 21-02 and explicitly anticipated in the plan action text.

## Issues Encountered

- TDD helper `_make_store()` initially passed a `.db` file path to `SQLiteStore.__init__`, which treats its argument as a directory path — fixed to use `tempfile.mkdtemp()` instead (Rule 1 auto-fix during RED phase)

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- All 4 provenance tables complete: ingest, detection, LLM, playbook
- P21-T04 requirement satisfied
- Phase 21 evidence-provenance is now fully implemented across all 4 plan tracks

---
*Phase: 21-evidence-provenance*
*Completed: 2026-04-02*
