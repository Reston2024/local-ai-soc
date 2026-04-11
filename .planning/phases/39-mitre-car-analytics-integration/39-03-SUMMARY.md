---
phase: 39-mitre-car-analytics-integration
plan: "03"
subsystem: api
tags: [fastapi, car-analytics, detections, investigation, mitre-att&ck]

# Dependency graph
requires:
  - phase: 39-mitre-car-analytics-integration
    provides: "Plan 02 — CARStore DDL, bulk_insert, car_analytics TEXT column on detections, CAR lookup in matcher._sync_save()"

provides:
  - "GET /api/detect response: car_analytics field deserialized from TEXT to list[dict] (or null on parse failure)"
  - "POST /api/investigate response: top-level car_analytics key with matching CAR analytic dicts"

affects:
  - dashboard
  - frontend/src/lib/api.ts

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "json.loads() TEXT blob deserialization for car_analytics in detect.py _query() — same pattern as matched_event_ids"
    - "asyncio.to_thread lambda for synchronous SQLite query inside async FastAPI handler"
    - "Subtechnique normalization: T1059.001.split('.')[0].upper() → T1059 for CAR table lookup"

key-files:
  created: []
  modified:
    - backend/api/detect.py
    - backend/api/investigate.py

key-decisions:
  - "39-03: car_analytics parsing in detect.py mirrors matched_event_ids pattern exactly — null on exception, not empty list, to distinguish 'no CAR data' from 'empty list'"
  - "39-03: CAR lookup uses attack_technique.split('.')[0].upper() to strip subtechnique suffix before querying car_analytics table (T1059.001 → T1059)"
  - "39-03: Silent except in investigate.py CAR lookup — missing table (fresh install before seed) logs at DEBUG, never raises, always returns []"

patterns-established:
  - "CAR enrichment: strip subtechnique suffix before querying car_analytics.technique_id"

requirements-completed:
  - P39-T03
  - P39-T05

# Metrics
duration: 8min
completed: 2026-04-11
---

# Phase 39 Plan 03: CAR Analytics API Surface Summary

**car_analytics TEXT blob deserialized in GET /api/detect and injected as top-level key in POST /api/investigate investigation response**

## Performance

- **Duration:** 8 min
- **Started:** 2026-04-11T23:19:00Z
- **Completed:** 2026-04-11T23:27:25Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- `detect.py` `_query()` now parses `car_analytics` TEXT column via `json.loads()` — consumers get a list, not a raw JSON string
- `investigate.py` adds `"car_analytics": []` to the initial result dict and populates it with a SQLite lookup using `detection.attack_technique` after detection is loaded
- Subtechnique suffix stripped before CAR lookup (T1059.001 → T1059) to match CAR table `technique_id` format
- Silent fallback to `[]` in investigate.py when car_analytics table is absent (fresh install before seed)
- 1020 unit tests remain green after both changes

## Task Commits

Each task was committed atomically:

1. **Task 1: Parse car_analytics in detect.py _query()** - `35d168d` (feat)
2. **Task 2: Add car_analytics section to investigation response** - `0dc8fd3` (feat)

**Plan metadata:** (docs: complete plan — committed after summary)

## Files Created/Modified
- `backend/api/detect.py` - Added json.loads() deserialization for car_analytics TEXT column in _query() loop
- `backend/api/investigate.py` - Added car_analytics: [] to result dict + CAR lookup block after detection load

## Decisions Made
- car_analytics parsing in detect.py uses `None` fallback on exception (not `[]`) to signal malformed data vs absent data, consistent with the plan spec
- CAR lookup in investigate.py uses `asyncio.to_thread(lambda: ...)` — same pattern used for other synchronous SQLite access in the file
- Subtechnique suffix stripped with `split(".")[0].upper()` before querying `car_analytics.technique_id`

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Both API surfaces now expose CAR analytics data to the frontend
- Plan 39-04 can wire up the frontend to display car_analytics in the investigation evidence panel and detection list

---
*Phase: 39-mitre-car-analytics-integration*
*Completed: 2026-04-11*
