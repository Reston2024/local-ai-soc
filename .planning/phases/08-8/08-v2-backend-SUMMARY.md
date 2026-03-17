---
phase: 08
plan: v2-backend
subsystem: backend-causality-investigate
tags: [causality, investigation, detection, correlation, duckdb, sqlite]
dependency_graph:
  requires: [duckdb_store, sqlite_store, causality_engine, correlation_clustering, sigma_matcher]
  provides: [investigate_endpoint, correlate_endpoint, detect_run_endpoint, causality_duckdb_wired]
  affects: [frontend_investigation_panel, frontend_attack_chain]
tech_stack:
  added: []
  patterns: [DuckDB-fetch_df, async-clustering, deferred-router-import]
key_files:
  created:
    - backend/api/correlate.py
    - backend/api/investigate.py
  modified:
    - backend/causality/entity_resolver.py
    - backend/causality/causality_routes.py
    - backend/api/detect.py
    - backend/investigation/timeline_builder.py
    - backend/main.py
decisions:
  - causality_router_prefix: Changed from /api to /causality (mounted at /api) to avoid conflict with graph.py /graph routes
  - entity_columns: Use NormalizedEvent field names (hostname/username/process_name/domain) not legacy (host/user/process/query)
  - duckdb_fetch_df: Use fetch_df for investigate endpoint (returns keyed dicts) instead of fetch_all + manual column zip
metrics:
  duration: "~30 minutes"
  completed: "2026-03-17"
  tasks: 7
  files_changed: 7
---

# Phase 8 v2 Backend: Causality Engine DuckDB Wiring + New Endpoints Summary

Wire the causality engine to DuckDB/SQLite and add detect/run, correlate, and investigate endpoints that read from real storage instead of empty in-memory lists.

## What Was Done

### Task 1 — Fix entity_resolver.py
Updated `FIELD_MAP` to use correct NormalizedEvent field names:
- `host` → `hostname`
- `user` → `username`
- `process` → `process_name`
- `domain` → `domain` (was `query`, the old DNS log field)

### Task 2 — Rewrite causality_routes.py
- Removed dead import `from backend.src.api.routes import _events, _alerts`
- All 5 endpoints now read from `request.app.state.stores` (DuckDB + SQLite)
- Added `_fetch_events_for_detection()` helper: fetches events by `matched_event_ids`
- Added `_fetch_recent_events()` helper: fallback to latest 500 events
- Engine receives events with `id` alias key (BFS uses `event.get("id")`)
- Renamed router prefix `/api` → `/causality` (mounted at `/api` in main.py)
  making all paths `/api/causality/...` instead of `/api/...`
- `query` endpoint now executes real DuckDB SQL filters

### Task 3 — POST /api/detect/run
New endpoint in `backend/api/detect.py`:
- Instantiates `SigmaMatcher(stores=stores)`
- Loads rules from `fixtures/sigma` and `rules/sigma` directories (if they exist)
- Calls async `run_all(case_id)` and saves detections to SQLite
- Returns count + full detection records

### Task 4 — POST /api/correlate
New file `backend/api/correlate.py`:
- Calls `cluster_events_by_entity(stores, event_ids=[])` (all events)
- Calls `cluster_events_by_time(stores, window_minutes=window_minutes)`
- Both functions are already async and accept `Stores` as first arg
- Returns entity clusters and temporal clusters with full metadata

### Task 5 — POST /api/investigate
New file `backend/api/investigate.py`:
- Central investigation workflow endpoint
- Accepts `detection_id` or `entity_id` in request body
- Fetches detection from SQLite, then matched events from DuckDB
- Falls back to entity search if no detection_id provided
- Expands scope via `cluster_events_by_entity` (finds related events)
- Builds Cytoscape-format graph (typed nodes: host/user/process/ip/file/domain/technique)
- Returns: `detection`, `events`, `graph`, `timeline`, `attack_chain`, `techniques`, `entity_clusters`, `summary`

### Task 6 — Fix timeline_builder.py fallback
Added fallback in `build_timeline()`:
- If no events found with `case_id` match, fetch events whose `event_id` appears
  in the case's linked detection records (`matched_event_ids`)
- Ensures timeline is populated for detections created before case assignment

### Task 7 — Mount new routers in main.py
- Fixed causality router mount: `include_router(causality_router, prefix="/api")`
- Added `correlate_router` mount at `/api/correlate`
- Added `investigate_router` mount at `/api/investigate`

## Verification

```
OK /api/detect/run
OK /api/investigate
OK /api/correlate
Total routes: 45
```

Unit tests: 66 passed, 4 xpassed, 0 failures.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing] `_get_stores` helper needed in detect.py**
- **Found during:** Task 3
- **Issue:** detect.py didn't have a store accessor helper
- **Fix:** Added `_get_stores(request)` helper inline
- **Files modified:** `backend/api/detect.py`

**2. [Rule 1 - Bug] `SigmaMatcher.__init__` takes `stores: Stores` not separate args**
- **Found during:** Task 3
- **Issue:** Plan's code snippet used `duckdb_store=` and `sqlite_store=` kwargs
  but actual SigmaMatcher takes `stores: Stores`
- **Fix:** Used `SigmaMatcher(stores=stores)` instead
- **Files modified:** `backend/api/detect.py`

**3. [Rule 1 - Bug] clustering functions are async, not sync**
- **Found during:** Task 4
- **Issue:** Plan suggested `asyncio.to_thread(cluster_events_by_entity, stores.duckdb)`
  but functions are already async coroutines and take `Stores` not `DuckDBStore`
- **Fix:** Directly awaited `await cluster_events_by_entity(stores, event_ids=[])`
- **Files modified:** `backend/api/correlate.py`

**4. [Rule 1 - Bug] `get_detection` returns dict not Pydantic model**
- **Found during:** Task 5
- **Issue:** Plan called `detection.model_dump()` but SQLite `get_detection()` returns `dict`
- **Fix:** Used `detection` directly without `.model_dump()`
- **Files modified:** `backend/api/investigate.py`

**5. [Rule 2 - Missing] fetch_df is better fit for investigate endpoint**
- **Found during:** Task 5
- **Issue:** `fetch_all` returns tuples needing manual column mapping;
  `fetch_df` already returns keyed dicts
- **Fix:** Used `fetch_df` for investigate queries to get column-named dicts directly
- **Files modified:** `backend/api/investigate.py`

## Self-Check: PASSED

All key files exist:
- `backend/api/correlate.py` - created
- `backend/api/investigate.py` - created
- `backend/causality/causality_routes.py` - rewritten (no longer imports `_events`/`_alerts`)
- `backend/causality/entity_resolver.py` - field names fixed

All commits exist: e58c08a, 039e3a0, fef4600, e19341b, 8f4061e, b187048
