---
phase: 42-streaming-behavioral-profiles
plan: 03
subsystem: api
tags: [anomaly, behavioral-profiling, fastapi, river, halftspace-trees, synthetic-detection, duckdb]

requires:
  - phase: 42-02
    provides: AnomalyScorer with score_one/learn_one/save_model, anomaly_score FLOAT column in DuckDB

provides:
  - GET /api/anomaly — list events by anomaly_score descending with min_score filter
  - GET /api/anomaly/entity — per-(subnet, process) score profile with sparkline
  - GET /api/anomaly/trend — score time-series for entity_key over N hours
  - AnomalyScorer wired into main.py lifespan (app.state.anomaly_scorer)
  - Synthetic detection creation when anomaly_score > ANOMALY_THRESHOLD (rule_id='anomaly-*')

affects:
  - 42-04-frontend
  - ingestion pipeline (loader.py enrichment)
  - DetectionsView (synthetic anomaly detections appear)

tech-stack:
  added: []
  patterns:
    - "Deferred try/except router registration pattern for new API modules"
    - "Synthetic detection creation in synchronous enrichment batch (in asyncio.to_thread context)"
    - "_apply_anomaly_scoring accepts optional sqlite_store + anomaly_threshold for detection creation"
    - "Test stubs with _make_app_with_mock_stores() factory + dependency_overrides for auth bypass"

key-files:
  created:
    - backend/api/anomaly.py
  modified:
    - backend/main.py
    - ingestion/loader.py
    - backend/api/ingest.py
    - tests/unit/test_anomaly_api.py

key-decisions:
  - "DuckDB INTERVAL syntax uses f-string interpolation for hours param (not parameterized placeholder) since hours is validated as int 1-168 via FastAPI Query"
  - "anomaly_router registered via deferred try/except block (consistent with other Phase 39-41 routers)"
  - "AnomalyScorer wrapped in try/except in lifespan — app degrades gracefully if scorer fails to init"
  - "Wave 0 test stubs fixed to use mocked DuckDB stores + dependency_overrides for verify_token bypass"

patterns-established:
  - "Synthetic detection: direct SQLite insert_detection() call inside asyncio.to_thread context (same as IOC matching)"
  - "Scorer wired via app.state._anomaly_scorer_for_ingester, read by ingest.py via getattr with None fallback"

requirements-completed:
  - P42-T04

duration: 18min
completed: 2026-04-12
---

# Phase 42 Plan 03: Anomaly API + Synthetic Detection Summary

**Three FastAPI anomaly endpoints (list/entity/trend) + AnomalyScorer wired into main.py lifespan + synthetic detections created at ingest when score > ANOMALY_THRESHOLD**

## Performance

- **Duration:** 18 min
- **Started:** 2026-04-12T15:08:00Z
- **Completed:** 2026-04-12T15:26:00Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- Created `backend/api/anomaly.py` with 3 endpoints: GET /api/anomaly, /api/anomaly/entity, /api/anomaly/trend
- Wired AnomalyScorer into `main.py` lifespan (Phase 42 block 7f) — scorer active in production
- Updated `_apply_anomaly_scoring()` in loader.py to create synthetic detections when score exceeds ANOMALY_THRESHOLD
- Wired `anomaly_scorer` through `ingest.py` `_get_loader()` so all file/batch ingest uses behavioral profiling
- Fixed Wave 0 TDD stubs with proper auth mocking — all 6 test_anomaly_api.py tests GREEN
- 1058 total unit tests green, zero regressions

## Task Commits

1. **Task 1: Create anomaly API endpoints** - `8ca9a78` (feat)
2. **Task 2: Wire AnomalyScorer into main.py + synthetic detection creation** - `776ae7b` (feat)

**Plan metadata:** [to be committed]

## Files Created/Modified

- `backend/api/anomaly.py` — Three anomaly endpoints using stores.duckdb.fetch_df(); DuckDB INTERVAL uses f-string (hours validated as int)
- `backend/main.py` — Phase 42 lifespan block 7f: AnomalyScorer init, anomaly_router deferred registration
- `ingestion/loader.py` — `_apply_anomaly_scoring()` extended with sqlite_store + anomaly_threshold params; synthetic detection creation; `_apply_enrichment_batch` passes sqlite_store ref and ANOMALY_THRESHOLD
- `backend/api/ingest.py` — `_get_loader()` passes `_anomaly_scorer_for_ingester` from app.state to IngestionLoader
- `tests/unit/test_anomaly_api.py` — Fixed all 6 stubs: proper auth override + mocked DuckDB stores; stub 6 tests `_apply_anomaly_scoring` directly

## Decisions Made

- DuckDB INTERVAL for trend endpoint uses `INTERVAL '{hours} hours'` f-string (hours is a Query-validated int 1-168, injection-safe)
- `/trend` returns a plain JSON list (not wrapped dict) to match Wave 0 test contract
- AnomalyScorer init wrapped in try/except so app starts cleanly even if river package issue occurs
- Deferred router registration pattern (try/except import) used for anomaly_router — consistent with Phases 39-41

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Wave 0 test stubs missing auth mocking — caused 401/422 failures**
- **Found during:** Task 1 (creating anomaly API)
- **Issue:** test_anomaly_api.py stubs created bare FastAPI() apps with no auth override and no `app.state.stores`, causing 401 on all API stubs once anomaly.py was importable
- **Fix:** Rewrote stubs to use `_make_app_with_mock_stores()` factory with `dependency_overrides[verify_token]` + AsyncMock DuckDB store; stub 6 rewritten to test `_apply_anomaly_scoring()` directly with monkeypatched scorer
- **Files modified:** tests/unit/test_anomaly_api.py
- **Verification:** All 6 tests GREEN (was 5 failing, 1 SKIP)
- **Committed in:** 8ca9a78 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - bug in Wave 0 test stubs)
**Impact on plan:** Required fix to make tests meaningful. No scope creep — same test contract, proper mocking added.

## Issues Encountered

None beyond the test stub auth issue documented above.

## Next Phase Readiness

- Plan 42-04 (Frontend AnomalyView) can now call all three endpoints
- Synthetic detections with `rule_id` prefixed `anomaly-` will appear in DetectionsView immediately
- AnomalyScorer is live in production pipeline — all ingested events get behavioral scoring

---
*Phase: 42-streaming-behavioral-profiles*
*Completed: 2026-04-12*
