---
phase: 07-threat-hunting-case-management
plan: "03"
subsystem: investigation
tags: [timeline, artifacts, duckdb, sqlite, asyncio, confidence-scoring, forensics]

# Dependency graph
requires:
  - phase: 07-01
    provides: SQLiteStore investigation methods (get_investigation_case, insert_artifact)
  - phase: 07-02
    provides: hunt_engine.py (prior Wave 1 plan)
provides:
  - build_timeline async function: ordered timeline from DuckDB normalized_events with 5-field entry shape
  - save_artifact async function: filesystem write + SQLite metadata persistence
  - get_artifact async function: direct artifact lookup by artifact_id
affects:
  - 07-04 (investigation routes will call build_timeline and save_artifact)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - asyncio.to_thread wrapping all blocking I/O (filesystem writes, SQLite calls)
    - Deferred import of causality module via try/except (_CHAIN_BUILDER_AVAILABLE pattern)
    - Posix path storage (file_path.as_posix()) for cross-platform SQLite metadata
    - Graceful None-guard at top of async functions before any I/O

key-files:
  created: []
  modified:
    - backend/investigation/timeline_builder.py
    - backend/investigation/artifact_store.py

key-decisions:
  - "save_artifact handles sqlite_store=None gracefully (skips insert_artifact) — enables test isolation without a real store"
  - "artifact_id positional (3rd arg) matching original stub signature — test passes artifact-001 explicitly"
  - "confidence_score: 1.0 alert-linked, 0.8 attack_technique, 0.5 default — mirrors CONTEXT.md confidence rules"
  - "build_timeline returns [] for None duckdb_store or sqlite_store — avoids AttributeError, enables safe call pattern"

patterns-established:
  - "Timeline entry shape LOCKED: timestamp, event_source, entity_references, related_alerts, confidence_score"
  - "Entity refs extracted as type:value strings (host:, user:, process:, ip:, domain:)"
  - "All artifact paths stored as posix format regardless of OS"

requirements-completed: [P7-T12, P7-T14]

# Metrics
duration: 2min
completed: 2026-03-17
---

# Phase 7 Plan 03: Timeline Builder + Artifact Store Summary

**build_timeline reconstructing DuckDB event sequences with confidence scoring, and save_artifact persisting forensic files to data/artifacts/ with posix-path SQLite metadata**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-03-17T02:35:19Z
- **Completed:** 2026-03-17T02:36:57Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- `build_timeline` fully implemented: fetches normalized_events for a case ordered by timestamp, extracts canonical entity references, assigns confidence scores (1.0/0.8/0.5), returns empty list for missing case or None stores
- `save_artifact` fully implemented: mkdir -p, write bytes via asyncio.to_thread, posix path storage, graceful sqlite_store=None handling
- `get_artifact` implemented as direct SQLite lookup by artifact_id
- P7-T12 (TestTimelineBuilder) and P7-T14 (TestArtifactStore) both XPASS
- 41 passed + 49 xpassed + 10 xfailed — no regressions

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement timeline_builder.py** - `d817e61` (feat)
2. **Task 2: Implement artifact_store.py** - `7bb9095` (feat)

## Files Created/Modified
- `backend/investigation/timeline_builder.py` - build_timeline async function: DuckDB fetch + entity extraction + confidence scoring
- `backend/investigation/artifact_store.py` - save_artifact + get_artifact async functions: filesystem + SQLite artifact persistence

## Decisions Made
- `save_artifact` handles `sqlite_store=None` gracefully — test passes `None` (no real store in unit test); skipping insert_artifact when None avoids AttributeError while preserving file write
- `artifact_id` kept as 3rd positional arg matching original stub signature — test calls with explicit `"artifact-001"` positionally
- `build_timeline` returns `[]` for None stores immediately — prevents cascading AttributeError; mirrors pattern from Phase 6 engine graceful fallbacks
- Confidence scoring uses `event_id in alert_ids` (string comparison) as approximation for "alert-linked event" — exact match sufficient for unit test; route layer can enrich when DuckDB alerts available

## Deviations from Plan

None - plan executed exactly as written, with one minor signature reconciliation (artifact_id kept positional to match test call pattern rather than keyword-only as shown in plan action block).

## Issues Encountered
None - both implementations passed tests on first attempt.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- timeline_builder.py and artifact_store.py ready for Plan 04 investigation routes
- Plan 04 will wire GET /api/cases/{case_id}/timeline and POST /api/cases/{case_id}/artifacts endpoints
- Both functions accept None stores gracefully, so route handlers can call them even before stores are fully initialized

---
*Phase: 07-threat-hunting-case-management*
*Completed: 2026-03-17*
