---
phase: 52-thehive-case-management-integration
plan: "03"
subsystem: api
tags: [thehive, case-management, apscheduler, sqlite, detection-pipeline]

# Dependency graph
requires:
  - phase: 52-02
    provides: TheHiveClient, _maybe_create_thehive_case, build_case_payload, build_observables, thehive_pending_cases SQLite table
  - phase: 51
    provides: OsintInvestigationStore for SpiderFoot observable enrichment

provides:
  - backend/services/thehive_sync.py: sync_thehive_closures + drain_pending_cases (synchronous)
  - backend/api/detect.py: fire-and-forget _maybe_create_thehive_case hook post save_detections
  - backend/api/health.py: _check_thehive() health component in optional_keys
  - backend/main.py: TheHiveClient on app.state.thehive_client + APScheduler 300s sync jobs

affects:
  - phase-53-network-privacy-monitoring
  - any phase that extends the detection pipeline

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Synchronous sync helpers (sync_thehive_closures/drain_pending_cases) called via APScheduler lambda wrappers — avoids async scheduler complexity"
    - "Fire-and-forget TheHive case creation via asyncio.create_task(asyncio.to_thread(sync_wrapper))"
    - "Dedicated AsyncIOScheduler for TheHive jobs (not coupled to metrics.py scheduler)"
    - "30s start_date offset on drain job to avoid simultaneous DB lock with sync job"

key-files:
  created:
    - backend/services/thehive_sync.py
  modified:
    - backend/api/detect.py
    - backend/api/health.py
    - backend/main.py

key-decisions:
  - "sync_thehive_closures/drain_pending_cases are synchronous — Wave 0 tests call them directly without an event loop; production APScheduler wraps with lambdas"
  - "drain_pending_cases handles both detection_json schemas: raw detection dict (Wave 0 test) and nested payload dict (production _enqueue_pending_case format)"
  - "_thehive_scheduler is a dedicated AsyncIOScheduler separate from _daily_snapshot_scheduler and metrics.py's scheduler — avoids coupling"
  - "asyncio.to_thread(client.ping) in _check_thehive() — ping() is synchronous, health endpoint is async"
  - "TheHive disabled/unreachable status never degrades overall health (added to optional_keys)"
  - "SpiderFoot observable enrichment queries OsintInvestigationStore by target=src_ip for FINISHED investigations; returns up to 5 findings as other dataType observables"

patterns-established:
  - "Optional service health check: getattr(request.app.state, 'service_client', None) + optional_keys exclusion"
  - "APScheduler lambda wrapper: lambda: sync_func(client, conn) avoids partial/functools coupling issues"

requirements-completed: [REQ-52-02, REQ-52-04, REQ-52-06, REQ-52-09]

# Metrics
duration: 15min
completed: 2026-04-16
---

# Phase 52 Plan 03: TheHive Pipeline Wiring Summary

**TheHive detection pipeline closed: High/Critical detections auto-create cases via fire-and-forget hook, closure sync + retry drain on 300s APScheduler intervals, and health panel reflects TheHive status — all 8 Wave 0 stubs GREEN.**

## Performance

- **Duration:** 15 min
- **Started:** 2026-04-16T15:13:00Z
- **Completed:** 2026-04-16T15:18:17Z
- **Tasks:** 2
- **Files modified:** 4 (1 created, 3 modified)

## Accomplishments

- `thehive_sync.py` implements `sync_thehive_closures` + `drain_pending_cases` as synchronous functions; handles both the production pending_cases schema (nested payload dict) and the Wave 0 test schema (raw detection dict at top level)
- `detect.py` fires `_maybe_create_thehive_case_wrapper` via `asyncio.create_task(asyncio.to_thread(...))` after `save_detections` for High/Critical detections; enriches with SpiderFoot findings from `OsintInvestigationStore` when `osint_store` is on `app.state`
- `health.py` adds `_check_thehive()` (pings synchronous `client.ping()` via `asyncio.to_thread`), included in `asyncio.gather` and `optional_keys` so TheHive disabled/unreachable never degrades overall health
- `main.py` wires `TheHiveClient` on `app.state.thehive_client` (THEHIVE_ENABLED guard), dedicated `AsyncIOScheduler` with `sync_thehive_closures` (300s) and `drain_pending_cases` (300s+30s offset) jobs, full try/except for non-fatal startup

## Task Commits

1. **Task 1: Create thehive_sync.py** — `030036c` (feat)
2. **Task 2: Wire detection hook, health check, main.py APScheduler** — `955dfd8` (feat)

## Files Created/Modified

- `backend/services/thehive_sync.py` — sync_thehive_closures + drain_pending_cases + SQLite helpers
- `backend/api/detect.py` — TheHive fire-and-forget hook + _get_spiderfoot_observables helper
- `backend/api/health.py` — _check_thehive() function + gather + optional_keys addition
- `backend/main.py` — TheHiveClient on app.state + APScheduler 300s jobs + shutdown cleanup

## Decisions Made

- **sync vs async:** `sync_thehive_closures` and `drain_pending_cases` are **synchronous** — Wave 0 tests call them directly without an event loop. APScheduler uses lambda wrappers to call them. Avoids async scheduler/asyncio complexity.
- **dual schema in drain_pending_cases:** The `thehive_pending_cases.detection_json` column stores different shapes: Wave 0 tests insert a raw detection dict; production `_enqueue_pending_case` wraps in `{"detection_id": ..., "payload": {...}}`. Both handled gracefully via key presence check.
- **dedicated scheduler:** A new `AsyncIOScheduler` for TheHive jobs avoids coupling to the metrics.py scheduler (which starts lazily on first KPI request) and the daily snapshot scheduler.
- **optional_keys inclusion for thehive:** TheHive is an optional enrichment service, not core storage — its health status must not degrade overall "healthy" assessment.

## Deviations from Plan

**1. [Rule 1 - Adaptation] Synchronous function signatures for sync helpers**

- **Found during:** Task 1 (thehive_sync.py implementation)
- **Issue:** Plan action section showed async function signatures (`async def sync_thehive_closures(app_state)`) but Wave 0 test stubs call them synchronously: `sync_thehive_closures(mock_client, conn)` and `drain_pending_cases(mock_client, conn)` — the tests are the authoritative contract.
- **Fix:** Implemented as synchronous `sync_thehive_closures(thehive_client, conn)` matching test contract. APScheduler wraps with lambdas. Tests pass.
- **Files modified:** backend/services/thehive_sync.py
- **Verification:** 3/3 sync stubs GREEN

**2. [Rule 2 - Missing Critical] drain_pending_cases handles dual detection_json schema**

- **Found during:** Task 1 (examining Wave 0 test schema vs production _enqueue_pending_case schema)
- **Issue:** Wave 0 tests use `detection_json` as a raw detection dict; production `_enqueue_pending_case` stores `{"detection_id": ..., "payload": {"case": ..., "observables": [...]}}`. The plan only described the production format.
- **Fix:** Added dual-schema detection in `drain_pending_cases` — checks for `"payload"` key to distinguish formats; falls back to `build_case_payload(blob)` for the raw format.
- **Files modified:** backend/services/thehive_sync.py
- **Verification:** test_retry_queue_drains passes (uses raw format)

---

**Total deviations:** 2 auto-adapted (both necessary for test contract compliance)
**Impact on plan:** No scope creep. Both adaptations ensure the implementation correctly satisfies the Wave 0 test contracts while also handling the production schema.

## Issues Encountered

- Pre-existing `test_metrics_api.py::test_endpoint_accessible_at_api_metrics_kpis` failure confirmed via `git stash` — unrelated to Phase 52 changes (expects `/metrics/kpis` to return 404 but SPA 404 handler serves index.html). Logged as out-of-scope, not fixed.

## Next Phase Readiness

- TheHive integration fully wired: detection auto-case creation active when THEHIVE_ENABLED=True
- Phase 53 (Network Privacy Monitoring) can proceed — no dependencies on TheHive
- To activate: set `THEHIVE_ENABLED=True`, `THEHIVE_URL`, `THEHIVE_API_KEY` in `.env`

---
*Phase: 52-thehive-case-management-integration*
*Completed: 2026-04-16*
