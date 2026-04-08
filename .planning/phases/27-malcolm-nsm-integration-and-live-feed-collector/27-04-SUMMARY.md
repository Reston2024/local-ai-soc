---
phase: 27-malcolm-nsm-integration-and-live-feed-collector
plan: "04"
subsystem: recommendations-dispatch
tags: [fastapi, recommendations, dispatch, schema-validation, svelte, api-ts, adr-030]
dependency_graph:
  requires: [27-02, 27-03, backend/api/recommendations.py, backend/models/recommendation.py]
  provides: [POST /api/recommendations/{id}/dispatch, dispatchRecommendation() TypeScript function, RecommendationsView.svelte]
  affects: [dashboard Respond nav group, recommendation approval workflow]
tech_stack:
  added: []
  patterns: [FastAPI JSONResponse route, RecommendationArtifact pydantic model_validator, Svelte 5 runes $state/$props, authHeaders() api.ts pattern]
key_files:
  created:
    - dashboard/src/views/RecommendationsView.svelte
  modified:
    - backend/api/recommendations.py
    - dashboard/src/lib/api.ts
    - dashboard/src/App.svelte
    - tests/unit/test_dispatch_endpoint.py
decisions:
  - "Rewrite wave-0 stubs with mock-DuckDB fixture pattern (same as test_recommendation_api.py) instead of create_app() — avoids heavy integration overhead in unit tests"
  - "dispatch_recommendation route catches both pydantic.ValidationError and jsonschema.ValidationError — RecommendationArtifact model_validator wraps jsonschema errors as ValueError"
  - "Create RecommendationsView.svelte as new view (no existing recommendation card component found) — wired into App.svelte Respond nav group with beta tag"
  - "api.recommendations.{list, get, dispatch} namespace added to api object alongside standalone dispatchRecommendation() export — dual access pattern matches existing file conventions"
metrics:
  duration_seconds: 453
  completed_date: "2026-04-07"
  tasks_completed: 2
  tasks_total: 2
  files_changed: 5
---

# Phase 27 Plan 04: Recommendation Dispatch Endpoint + Svelte UI Summary

**One-liner:** POST /api/recommendations/{id}/dispatch with ADR-030 schema re-validation, 5 activated unit tests, and RecommendationsView.svelte with status-gated Dispatch button.

## What Was Built

### Task 1: POST /api/recommendations/{id}/dispatch route (TDD)

Added `dispatch_recommendation()` route to `backend/api/recommendations.py`:

- **404**: recommendation not found in DuckDB
- **409**: status != "approved" — returns `{"error": "not_approved", "detail": "..."}`
- **422**: `RecommendationArtifact(**rec)` pydantic validation fails — returns `{"error": "schema_validation_failed", "detail": [...]}`
- **200**: artifact passes schema — returns `{"dispatched": true, "recommendation_id": id, "artifact_type": type}`
- No outbound HTTP calls — dispatch is schema validation only (future phase)

Added `RecommendationArtifact` to imports in recommendations.py.

Rewrote wave-0 stubs in `tests/unit/test_dispatch_endpoint.py` with proper mock-DuckDB fixture pattern matching `test_recommendation_api.py`. All 5 tests activated and passing.

### Task 2: api.ts dispatchRecommendation() + RecommendationsView.svelte

Added to `dashboard/src/lib/api.ts`:
- `RecommendationItem`, `RecommendationsListResponse`, `DispatchResult` interfaces
- `dispatchRecommendation(id: string): Promise<DispatchResult>` exported function
- `api.recommendations.{list, get, dispatch}` namespace

Created `dashboard/src/views/RecommendationsView.svelte`:
- Lists all recommendations via `api.recommendations.list()`
- Status filter dropdown
- Per-card Dispatch button: only renders when `rec.status === 'approved'` and not yet dispatched
- Button shows "Dispatching..." during call, "Dispatched" (green) on success, inline error on failure
- Svelte 5 runes: `$state`, `$props`, `$effect` — no writable() stores

Wired into `App.svelte` under Respond nav group with beta tag.

## Verification Results

```
uv run pytest tests/unit/test_dispatch_endpoint.py -x -v
5 passed in 0.20s

uv run pytest tests/unit/ -q
867 passed, 1 skipped, 9 xfailed, 7 xpassed, 7 warnings in 20.16s
0 failures
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical Functionality] Created RecommendationsView.svelte (no existing component)**
- **Found during:** Task 2
- **Issue:** Plan said to find the existing recommendation card component — none existed in the Svelte dashboard. No `.svelte` file referenced "recommendation".
- **Fix:** Created `RecommendationsView.svelte` as a new full view with recommendation list, status filter, and Dispatch button on approved cards. Wired into App.svelte Respond nav group.
- **Files modified:** `dashboard/src/views/RecommendationsView.svelte` (created), `dashboard/src/App.svelte`
- **Commit:** e2fc915

**2. [Rule 1 - Bug] Stub tests used create_app() — would fail with real DB dependency**
- **Found during:** Task 1 (RED phase)
- **Issue:** Original wave-0 stubs called `create_app()` directly, which requires real DuckDB/SQLite stores. Would fail in unit test context.
- **Fix:** Rewrote tests using `AsyncMock` DuckDB fixture pattern identical to `test_recommendation_api.py`, giving full control over DB responses.
- **Files modified:** `tests/unit/test_dispatch_endpoint.py`
- **Commit:** 0ebec4c

## Commits

| Hash | Message |
|------|---------|
| 0ebec4c | feat(27-04): add POST /api/recommendations/{id}/dispatch route + 5 activated tests |
| e2fc915 | feat(27-04): add dispatchRecommendation() to api.ts + RecommendationsView with Dispatch button |

## Self-Check: PASSED

All files exist and commits verified:
- FOUND: backend/api/recommendations.py
- FOUND: tests/unit/test_dispatch_endpoint.py
- FOUND: dashboard/src/lib/api.ts
- FOUND: dashboard/src/views/RecommendationsView.svelte
- FOUND: commit 0ebec4c
- FOUND: commit e2fc915
