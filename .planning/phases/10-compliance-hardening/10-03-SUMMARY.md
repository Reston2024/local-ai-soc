---
phase: 10-compliance-hardening
plan: "03"
subsystem: auth
tags: [auth, security, fastapi, bearer-token]
dependency_graph:
  requires: [backend/core/config.py, backend/main.py]
  provides: [backend/core/auth.py, verify_token dependency]
  affects: [all /api/* routes, tests/unit/test_auth.py, tests/security/test_auth.py]
tech_stack:
  added: []
  patterns: [HTTPBearer, open-mode bypass, Depends(verify_token) on include_router]
key_files:
  created:
    - backend/core/auth.py
  modified:
    - backend/core/config.py
    - backend/main.py
    - config/.env.example
    - tests/unit/test_auth.py
    - tests/security/test_auth.py
    - backend/models/event.py
    - backend/api/detect.py
decisions:
  - "AUTH_TOKEN='' (empty) means open/dev mode — all requests pass; non-empty means token required"
  - "Depends(verify_token) applied at include_router level (not per-route) to avoid per-route decorators"
  - "GraphEntity/GraphEdge/GraphResponse added to backend/models/event.py to fix pre-existing broken import in graph.py"
  - "test_health_endpoint_no_auth_required asserts != 401 (not == 200) because health returns 503 without live stores in test context"
metrics:
  duration: "~20 minutes"
  completed: "2026-03-26"
  tasks_completed: 2
  files_modified: 8
---

# Phase 10 Plan 03: Bearer Token Auth Layer Summary

Bearer token auth with open-mode bypass using `AUTH_TOKEN` env var and `HTTPBearer` FastAPI dependency, wired to all non-health routers via `Depends(verify_token)` at `include_router` level.

## Tasks Completed

| Task | Description | Commit |
|------|-------------|--------|
| 1 | Create backend/core/auth.py, add AUTH_TOKEN to config.py, update .env.example | 92275be |
| 2 | Wire verify_token to all non-health routers, convert xfail tests to real tests | 62aa7c7 |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Removed broken DetectionRecord import from detect.py**
- **Found during:** Task 2 (when verify test_health_endpoint_no_auth_required failed due to import error)
- **Issue:** `backend/api/detect.py` imported `DetectionRecord` from `backend.models.event` but that class doesn't exist in that module. The import was unused (only referenced in a docstring).
- **Fix:** Removed the unused `from backend.models.event import DetectionRecord` import line.
- **Files modified:** `backend/api/detect.py`
- **Commit:** 62aa7c7

**2. [Rule 1 - Bug] Added GraphEntity/GraphEdge/GraphResponse models to backend/models/event.py**
- **Found during:** Task 2 (create_app() failed on `from backend.api.graph import router` due to missing models)
- **Issue:** `backend/api/graph.py` imported `GraphEdge`, `GraphEntity`, `GraphResponse` from `backend.models.event` but those classes were never defined there (only existed in the deprecated `backend/src/api/models.py`). `graph.py` actively calls `GraphResponse.from_stores(...)` so a stub fix was not sufficient.
- **Fix:** Added all three Pydantic model classes to `backend/models/event.py`, including a `from_stores()` classmethod that maps raw SQLite store dicts to typed objects.
- **Files modified:** `backend/models/event.py`
- **Commit:** 62aa7c7

**3. [Adjustment] test_health_endpoint_no_auth_required asserts != 401, not == 200**
- **Reason:** The health endpoint returns HTTP 503 in the test context (no live DuckDB/Chroma/SQLite). The purpose of the security test is to verify auth is NOT blocking health — so checking `!= 401` and `!= 403` is the correct assertion. 200 vs 503 depends on live service availability, not on auth behavior.

## Test Results

- `tests/unit/test_auth.py`: 4 passed (converted from xfail stubs)
- `tests/security/test_auth.py`: 2 passed (converted from xfail stubs)
- Full suite (`tests/unit/ tests/security/`): 99 passed, 0 failed (up from 97 passed, 2 failed pre-plan)

## Self-Check: PASSED

Files created/modified:
- backend/core/auth.py: exists
- backend/core/config.py: AUTH_TOKEN field present
- backend/main.py: Depends(verify_token) on all non-health routers
- config/.env.example: AUTH_TOKEN section appended
- tests/unit/test_auth.py: 4 real async tests
- tests/security/test_auth.py: 2 real endpoint tests

Commits:
- 92275be: feat(10-03): create auth.py with verify_token and add AUTH_TOKEN to config
- 62aa7c7: feat(10-03): wire verify_token to all non-health routers and make auth tests GREEN
