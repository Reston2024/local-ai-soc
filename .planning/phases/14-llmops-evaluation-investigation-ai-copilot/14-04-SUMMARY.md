---
phase: 14-llmops-evaluation-investigation-ai-copilot
plan: "04"
subsystem: api
tags: [fastapi, pydantic, duckdb, sqlite, timeline, investigation]

# Dependency graph
requires:
  - phase: 14-llmops-evaluation-investigation-ai-copilot
    provides: Wave-0 test stubs for timeline API (test_investigation_timeline.py)
provides:
  - GET /api/investigations/{id}/timeline endpoint (unified chronological evidence timeline)
  - TimelineItem Pydantic model (event/detection/edge/playbook)
  - merge_and_sort_timeline() pure function (unit-testable, 4 sources)
affects:
  - dashboard/src/lib/api.ts (timeline client call)
  - InvestigationView (timeline data consumer)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - TDD RED-GREEN — Wave-0 stub tests turned green by implementation
    - merge_and_sort_timeline() as pure function with safe None defaults for optional sources
    - asyncio.to_thread() wrapping sync SQLite store calls
    - Deferred try/except router registration pattern in main.py

key-files:
  created:
    - backend/api/timeline.py
  modified:
    - backend/main.py

key-decisions:
  - "14-04: Used get_detections_by_case(case_id) from SQLiteStore (not get_detections with limit param — that method does not exist)"
  - "14-04: SQLite edges table (not graph_edges) used for edge rows — src/dst mapped from source_id/target_id columns with fallback to src_label/dst_label"
  - "14-04: playbook_rows always empty in Phase 14 with inline comment noting deferral to future phase"
  - "14-04: merge_and_sort_timeline() accepts None for all optional list params — safe for callers that omit edge/playbook args"
  - "14-04: DuckDB fetch_all called with list param [investigation_id] not tuple — matches store signature"

patterns-established:
  - "Timeline merger pattern: pure function accepting 4 typed lists, sorted by timestamp key — testable without I/O"
  - "Safe SQLite edge fallback: try/except around _get_edge_rows_sync returns [] on any schema error"

requirements-completed:
  - P14-T03

# Metrics
duration: 8min
completed: 2026-03-27
---

# Phase 14 Plan 04: Investigation Timeline Endpoint Summary

**GET /api/investigations/{id}/timeline assembling DuckDB events + SQLite detections + SQLite edges into chronological unified timeline via pure merge_and_sort_timeline() function**

## Performance

- **Duration:** 8 min
- **Started:** 2026-03-27T11:49:17Z
- **Completed:** 2026-03-27T11:57:00Z
- **Tasks:** 1 (TDD: RED confirmed, GREEN implemented)
- **Files modified:** 2

## Accomplishments
- Created `backend/api/timeline.py` (259 lines) with TimelineItem Pydantic model, merge_and_sort_timeline() pure function, and FastAPI router
- Implemented GET /api/investigations/{id}/timeline — fetches from DuckDB normalized_events, SQLite detections, and SQLite edges with graceful fallback
- All 3 Wave-0 stub tests in test_investigation_timeline.py turned GREEN
- timeline_router registered in main.py via deferred try/except pattern (was already present from 14-03 prep commit)

## Task Commits

Each task was committed atomically:

1. **Task 1: TimelineItem, merge_and_sort_timeline (4 sources), GET endpoint** - `cb76b1e` (feat)

## Files Created/Modified
- `backend/api/timeline.py` - TimelineItem model, merge_and_sort_timeline(), _get_edge_rows_sync(), GET /api/investigations/{id}/timeline endpoint
- `backend/main.py` - timeline_router registered via deferred try/except (was already present in prior 14-03 commit)

## Decisions Made
- Used `get_detections_by_case(case_id)` — the SQLiteStore has this method rather than the generic `get_detections(case_id=None, limit=200)` described in the plan
- The SQLite schema uses an `edges` table (not `graph_edges`) with `source_id`/`target_id` columns; `_get_edge_rows_sync` queries this table with src/dst fallback key mapping for forward-compat with callers passing `src_label`/`dst_label` dicts
- `merge_and_sort_timeline()` signature uses `list[tuple] | None` and `list[dict] | None` for all params to handle None from callers
- `DuckDB.fetch_all()` takes `list` not `tuple` for params — called with `[investigation_id]`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Adapted edge table name and column names to actual SQLite schema**
- **Found during:** Task 1 (reading sqlite_store.py)
- **Issue:** Plan references `graph_edges` table with `src_label`/`dst_label` columns; actual schema has `edges` table with `source_id`/`target_id` columns
- **Fix:** `_get_edge_rows_sync` queries `edges` table; column mapping in `merge_and_sort_timeline` tries `src_label` first then falls back to `source_id` (forward-compat)
- **Files modified:** backend/api/timeline.py
- **Verification:** Tests pass; safe fallback on exception means no runtime error if schema differs
- **Committed in:** cb76b1e (Task 1 commit)

**2. [Rule 1 - Bug] Used correct SQLiteStore detection method signature**
- **Found during:** Task 1 (reading sqlite_store.py)
- **Issue:** Plan mentions `get_detections(case_id, limit)` but SQLiteStore only has `get_detections_by_case(case_id)` — no limit param, no generic `get_detections`
- **Fix:** Called `asyncio.to_thread(stores.sqlite.get_detections_by_case, investigation_id)`
- **Files modified:** backend/api/timeline.py
- **Verification:** Method exists in sqlite_store.py at line 470; tests pass
- **Committed in:** cb76b1e (Task 1 commit)

---

**Total deviations:** 2 auto-fixed (both Rule 1 - Bug, adapting to actual store API vs plan description)
**Impact on plan:** Both fixes necessary for correctness. No scope creep.

## Issues Encountered
- `test_investigation_chat.py` was already failing (Wave-0 stub for `backend/api/chat` — a different future plan). Pre-existing, out of scope.

## Self-Check

Verified files exist:
- `backend/api/timeline.py` — FOUND (259 lines)
- `backend/main.py` — timeline_router block present at line 338

Verified commit:
- `cb76b1e` — FOUND in git log

## Self-Check: PASSED

## Next Phase Readiness
- GET /api/investigations/{id}/timeline is live and returns empty items for unknown IDs (not 404)
- InvestigationView can call this endpoint to populate its chronological evidence panel
- Chat API stub (test_investigation_chat.py) is still RED — that's the next TDD target in plan 14-05 or 14-06

---
*Phase: 14-llmops-evaluation-investigation-ai-copilot*
*Completed: 2026-03-27*
