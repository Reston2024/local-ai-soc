---
phase: 09-intelligence-analyst-augmentation
plan: "03"
subsystem: intelligence-api
tags: [fastapi, risk-scoring, sqlite, api-endpoints]
dependency_graph:
  requires: [09-01, 09-02]
  provides: [score-api, top-threats-api]
  affects: [backend/main.py, dashboard]
tech_stack:
  added: []
  patterns: [deferred-router-mount, try-except-graceful-degradation, asyncio-to-thread-sqlite]
key_files:
  created:
    - backend/api/score.py
    - backend/api/top_threats.py
  modified:
    - backend/main.py
decisions:
  - "Used Request object pattern (request.app.state.stores) instead of plan's get_sqlite_store() generator — deps.py only exposes get_stores(), not individual store accessors"
  - "Imported score_entity at module level in score.py so test mock patch('backend.api.score.score_entity') works correctly"
  - "Top-threats gracefully handles missing app.state.stores (unit tests without lifespan) by wrapping _fetch_top_threats in try/except"
metrics:
  duration_seconds: 150
  completed_date: "2026-03-26"
  tasks_completed: 2
  tasks_total: 2
  files_created: 2
  files_modified: 1
requirements: [P9-T04, P9-T06, P9-T08]
---

# Phase 9 Plan 03: Score and Top-Threats API Endpoints Summary

**One-liner:** POST /api/score and GET /api/top-threats FastAPI routers exposing the risk scoring engine with SQLite write-back and graceful empty-result handling.

## What Was Built

Two FastAPI router files wired into main.py via deferred try/except mounts:

1. **POST /api/score** (`backend/api/score.py`) — Accepts an optional `detection_id`, fetches the detection from SQLite, scores it via `score_detection()`, persists the `risk_score` back to the detections row, then optionally scores matched DuckDB events via `score_entity()`. Always returns HTTP 200 with `scored_entities`, `top_entity`, `top_score`, and `enriched_nodes`.

2. **GET /api/top-threats** (`backend/api/top_threats.py`) — Queries SQLite `detections` table ordered by `risk_score DESC` with a `?limit=` param (default 10, max 100). Returns `{"threats": [...], "total": N}`. Always returns HTTP 200 with empty list when SQLite is unavailable.

3. **main.py** — Added two deferred router mount blocks after the existing telemetry block, following the established `try: ... except ImportError` pattern.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create POST /api/score router | ac4749b | backend/api/score.py |
| 2 | Create GET /api/top-threats + wire both in main.py | 3db667f | backend/api/top_threats.py, backend/main.py |

## Verification Results

- `uv run pytest tests/unit/test_score_api.py tests/unit/test_top_threats_api.py` — all 6 show XPASS(strict) as expected
- `uv run pytest tests/unit/ -q` — 82 passed, 6 xfailed (other endpoints), 6 xpassed (ours), 0 errors
- `python -c "from backend.main import create_app; ..."` confirms `['/api/score', '/api/top-threats']` in routes

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] plan's get_sqlite_store() / get_duckdb_store() generators do not exist**
- **Found during:** Task 1 implementation
- **Issue:** The plan code template called `next(get_sqlite_store())` and `next(get_duckdb_store())`, but `backend/core/deps.py` only exports `get_stores()` which returns a `Stores` container (not individual store generators)
- **Fix:** Used `request.app.state.stores.sqlite` and `request.app.state.stores.duckdb` directly via the `Request` parameter, consistent with how `detect.py`, `correlate.py`, and `graph.py` access stores
- **Files modified:** backend/api/score.py, backend/api/top_threats.py
- **Commit:** ac4749b, 3db667f

**2. [Rule 1 - Bug] score_entity not importable at patch target backend.api.score.score_entity**
- **Found during:** Task 1 TDD verification
- **Issue:** Test mock `patch("backend.api.score.score_entity", return_value=75)` requires `score_entity` to be a module-level name in `backend.api.score`. Original plan code had it as a local import inside `_compute_scores()`.
- **Fix:** Added `score_entity` to the module-level import from `backend.intelligence.risk_scorer` and removed the redundant local import inside the function
- **Files modified:** backend/api/score.py
- **Commit:** ac4749b

## Self-Check: PASSED

- backend/api/score.py: FOUND
- backend/api/top_threats.py: FOUND
- Commit ac4749b: FOUND
- Commit 3db667f: FOUND
