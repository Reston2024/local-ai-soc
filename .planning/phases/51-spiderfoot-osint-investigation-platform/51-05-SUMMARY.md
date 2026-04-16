---
plan: 51-05
status: complete
completed_at: "2026-04-16"
tests_passing: 1177
tests_skipped: 4
regressions: 0
---

# Plan 51-05 Summary: Wave 3 — Unit Tests + Integration Verification

## What Was Done

Completed all Wave 3 TDD work for Phase 51: replaced all assert-False stubs with
real test implementations, added DNSTwist service tests, and verified zero regressions
across the full unit suite.

### Task 1: test_spiderfoot_client.py — 5 tests GREEN

Replaced deferred @pytest.mark.skip stubs with real implementations using
`unittest.mock.patch` and `AsyncMock`. Key tests:
- `test_ping_returns_false_when_unreachable` — live socket to port 19999 (not running)
- `test_start_scan_uses_form_encoding` — mocks httpx.AsyncClient, verifies `data=` kwarg
- `test_get_status_extracts_index_6` — mocks GET response, verifies index[6] extraction
- `test_stop_scan_posts_form_id` — verifies scan-id in post call args
- `test_spiderfoot_client_has_expected_methods` — all 8 methods present

### Task 2: test_osint_investigate_api.py — 9 tests GREEN

Rewrote stub file with FastAPI TestClient using dependency overrides. Key decisions:
- `TestClient(app, raise_server_exceptions=False)` without context manager — avoids
  lifespan DuckDB file-lock errors in unit tests
- `sqlite3.connect(":memory:", check_same_thread=False)` — allows asyncio.to_thread
  to access the in-memory SQLite from worker threads
- `app.state.stores = _make_mock_stores()` — bypasses DuckDB/Chroma/Ollama startup
- `app.dependency_overrides[verify_token]` — bypasses JWT auth

Also fixed a pre-existing routing bug: `GET /investigations` was shadowed by
`GET /{ip}` (registered first). Moved `/investigations` before `/{ip}` in
`backend/api/osint_api.py`.

Tests implemented:
- 503 when SpiderFoot not reachable
- 202 + job_id when scan starts
- GET /{job_id} returns status dict
- GET /investigations returns list
- POST /dnstwist returns lookalikes
- GET /{job_id} includes dnstwist_findings key
- get_findings_since() cursor test
- SSE stream returns text/event-stream content-type
- /health includes spiderfoot in components dict

### Task 3: test_dnstwist_service.py — 3 tests GREEN

New file testing `run_dnstwist()`:
- Registered-domain filtering (dns_a/dns_ns check) with patched dnstwist.run
- Graceful ImportError fallback via sys.modules injection
- RuntimeError handling — returns [] on scan failure

### Task 4: Full suite verification

- 1177 passed, 4 skipped, 9 xfailed, 7 xpassed
- 1 pre-existing failure (test_metrics_api::test_endpoint_accessible_at_api_metrics_kpis) — confirmed pre-existing via git stash
- Zero new regressions
- Phase 32 OSINT tests (test_osint_service.py + test_osint_classification.py) — all 20 GREEN

## Files Modified

- `tests/unit/test_spiderfoot_client.py` — complete rewrite (stubs → real tests)
- `tests/unit/test_osint_investigate_api.py` — complete rewrite (stubs → real tests)
- `tests/unit/test_dnstwist_service.py` — new file (3 tests)
- `backend/api/osint_api.py` — routing fix: /investigations before /{ip}

## Key Decisions

- `check_same_thread=False` on in-memory SQLite is required whenever asyncio.to_thread
  accesses a connection created in the main thread (unit test fixture context)
- `raise_server_exceptions=False` with no context manager is the correct pattern for
  lifespan-free unit testing with create_app()
- Health test checks `data["components"]["spiderfoot"]` not `data["spiderfoot"]` —
  health response wraps all checks under the "components" key
- `GET /investigations` must be registered before `GET /{ip}` in FastAPI — literal
  path segments always win but only when registered first
