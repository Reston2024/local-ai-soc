---
phase: 53-network-privacy-monitoring
plan: "03"
subsystem: privacy-scanner
tags: [tdd, wave-3, privacy, detection, scanner, api, apscheduler]
dependency_graph:
  requires: [53-02]
  provides: [PRIV-05, PRIV-06, PRIV-07, PRIV-08, PRIV-09, PRIV-10]
  affects: [backend/api/privacy.py, backend/main.py]
tech_stack:
  added: []
  patterns: [module-level-patchable-helpers, synchronous-scan-for-testability, graceful-degradation-api]
key_files:
  created:
    - backend/api/privacy.py
  modified:
    - backend/main.py
    - tests/unit/test_privacy_detection.py
    - tests/unit/test_privacy_api.py
decisions:
  - "run_privacy_scan() is synchronous (not async) — Wave-0 stubs call without await; async _privacy_scan_loop wraps via asyncio.to_thread"
  - "_query_http_events() and _is_tracker() exposed as module-level functions — test stubs patch these directly (backend.api.privacy._query_http_events); pure async approach would not be patchable without asyncio overhead"
  - "router alias added as privacy_router — test stubs import 'router', plan wiring uses 'privacy_router'; both names exported from same object"
  - "fetch_all returns list[tuple] not list[dict] in production — _query_http_events builds dict via column description; tests patch at helper level so tuple vs dict is transparent to tests"
  - "Wave-0 stubs rewritten as real tests — stubs had @pytest.mark.skip + assert False; converted to concrete tests patching module-level helpers; no stub infrastructure needed once implementation exists"
metrics:
  duration: "~5 minutes"
  completed_date: "2026-04-17"
  tasks_completed: 2
  tasks_total: 2
  files_created: 1
  files_modified: 3
---

# Phase 53 Plan 03: Privacy Scanner and API Endpoints Summary

**One-liner:** Synchronous run_privacy_scan() with module-level patchable helpers, cookie exfil + tracking pixel detection paths, SQLite detection insertion, and /api/privacy/hits + /api/privacy/feeds endpoints wired into main.py.

## What Was Built

### Task 1: backend/api/privacy.py — Scanner + API endpoints (commit d02dffc)

New module `backend/api/privacy.py` (~230 lines):

- `_query_http_events(duckdb_store, sql, threshold)` — synchronous module-level helper; runs SQL against DuckDB read connection; returns list of dicts; patchable by unit tests
- `_is_tracker(privacy_store, domain)` — synchronous module-level helper; calls `privacy_store.is_tracker(domain)`; patchable by unit tests
- `run_privacy_scan(app)` — synchronous scanner; two detection paths (cookie exfil + tracking pixel); returns list of detection dicts; calls `sqlite_store.insert_detection()` for each match; graceful on missing `app.state` attrs
- `run_privacy_scan_async(app)` — async wrapper via `asyncio.to_thread()`
- `_privacy_scan_loop(app, interval_sec=300)` — background loop (same pattern as `_auto_triage_loop`)
- `router` and `privacy_router` — same `APIRouter(prefix="/api/privacy")`
- `GET /api/privacy/hits` — queries detections WHERE detection_source='privacy', returns `{"hits": [...]}`
- `GET /api/privacy/feeds` — calls `privacy_store.get_feed_status()`, returns `{"feeds": [...]}`
- Wave-0 test stubs rewritten as real passing tests (PRIV-05..10 all GREEN)

### Task 2: Wire into main.py (commit f77c10b)

`backend/main.py` additions:

- **Block 7k** (after TheHive 7j): `PrivacyBlocklistStore` + `PrivacyWorker` init guarded by `PRIVACY_ENABLED` setting; `app.state.privacy_store` set (None if disabled or failed)
- **Privacy scan loop**: added after `_auto_triage_loop`, creates `asyncio.create_task(_priv_loop(app, interval_sec=300))` only when `privacy_store` is not None
- **Router registration**: deferred try/except block includes `privacy_router` at `/api/privacy`

## Verification Results

```
tests/unit/test_privacy_detection.py - 4 passed
  test_cookie_exfil_detection_fires_on_large_body_to_tracker  PASSED (PRIV-05)
  test_tracking_pixel_detection_fires_on_tiny_image_from_tracker PASSED (PRIV-06)
  test_no_false_positive_for_non_tracker_domain               PASSED (PRIV-07)
  test_detection_record_uses_privacy_source_tag               PASSED (PRIV-08)

tests/unit/test_privacy_api.py - 2 passed
  test_hits_endpoint_returns_list                             PASSED (PRIV-09)
  test_feeds_endpoint_returns_status                          PASSED (PRIV-10)

Route smoke check: ['/api/privacy/hits', '/api/privacy/feeds'] confirmed

Full unit suite: 1271 passed, 6 skipped, 10 xfailed, 8 xpassed
Pre-existing failures (integration/security/eval): 13 unchanged
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] run_privacy_scan() must be synchronous, not async**
- **Found during:** Task 1 (reading test stubs)
- **Issue:** Wave-0 stubs call `run_privacy_scan(mock_app)` without `await`; plan's code had `async def run_privacy_scan(app)`. Calling async without await returns a coroutine — scan never executes.
- **Fix:** Made `run_privacy_scan()` synchronous; added `run_privacy_scan_async()` wrapper for background loop
- **Files modified:** backend/api/privacy.py
- **Commit:** d02dffc

**2. [Rule 1 - Bug] Test stubs patch module-level helpers, not async coroutines**
- **Found during:** Task 1 (reading test stubs)
- **Issue:** Stubs patch `backend.api.privacy._query_http_events` and `backend.api.privacy._is_tracker` as synchronous module-level functions. Plan's code inlined DuckDB queries inside `run_privacy_scan()` with no patchable entry points.
- **Fix:** Extracted `_query_http_events()` and `_is_tracker()` as module-level synchronous functions; `run_privacy_scan()` calls them so tests can patch at the helper level
- **Files modified:** backend/api/privacy.py
- **Commit:** d02dffc

**3. [Rule 1 - Bug] Test stubs import `router` not `privacy_router`**
- **Found during:** Task 1 (reading `test_privacy_api.py`)
- **Issue:** Stubs do `from backend.api.privacy import router as privacy_router`. Plan's code only exported `privacy_router` (not `router`). This would cause `ImportError`.
- **Fix:** Exported `router = APIRouter(...)` and `privacy_router = router` (alias)
- **Files modified:** backend/api/privacy.py
- **Commit:** d02dffc

**4. [Rule 2 - Missing] Wave-0 stubs needed rewriting, not just creating implementation**
- **Found during:** Task 1 (running tests)
- **Issue:** Wave-0 stubs had `@pytest.mark.skip` + `pytest.skip()` in body + `assert False`. Even with implementation present, they would always SKIP. Plan said "turn GREEN" but didn't say to rewrite stubs.
- **Fix:** Rewrote stubs as real tests — removed `@pytest.mark.skip`, removed `pytest.skip()` calls, removed `assert False`, used concrete mock patterns matching the module-level helper API
- **Files modified:** tests/unit/test_privacy_detection.py, tests/unit/test_privacy_api.py
- **Commit:** d02dffc

## Self-Check: PASSED

- backend/api/privacy.py: FOUND
- backend/main.py (privacy_store): FOUND
- backend/main.py (privacy_router): FOUND
- backend/main.py (_privacy_scan_loop): FOUND
- Commit d02dffc: FOUND
- Commit f77c10b: FOUND
