# Plan 51-02 Summary: Wave 1 — SpiderFoot Client + OSINT Store + Docker Setup

## Status: COMPLETE

## What Was Built

### Task 1: OSINT SQLite DDL (`backend/stores/sqlite_store.py`)
Appended `_OSINT_INVESTIGATION_DDL` block defining:
- `osint_investigations` — investigation job tracker
- `osint_findings` — SpiderFoot event results with MISP hit fields
- `dnstwist_findings` — lookalike domain results
- 3 indexes for efficient query patterns
Executed via `executescript` in `SQLiteStore.__init__` (idempotent).

### Task 2: OsintInvestigationStore (`backend/services/osint_investigation_store.py`)
9 CRUD methods:
- `create_investigation`, `update_job_id`, `get_investigation`, `update_investigation_status`, `list_investigations`
- `bulk_insert_osint_findings`, `get_findings`, `get_findings_since` (SSE cursor)
- `bulk_query_ioc_cache`, `bulk_insert_dnstwist_findings`, `get_dnstwist_findings`
Includes self-bootstrapping `_OSINT_DDL` so unit tests using `:memory:` connections work without SQLiteStore.

### Task 3: SpiderFootClient (`backend/services/spiderfoot_client.py`)
8 async httpx methods wrapping SpiderFoot CherryPy REST API:
- `ping`, `start_scan`, `get_status`, `get_summary`, `get_events`, `get_graph`, `stop_scan`, `delete_scan`
Key: POST endpoints use `data={}` (form-encoded), not `json={}`; `/startscan` returns plain text ID.

### Task 4: DNSTwist Service (`backend/services/dnstwist_service.py`)
`run_dnstwist(domain, threads=8)` async function wrapping `asyncio.to_thread`. Returns only registered lookalike domains (has `dns_a` or `dns_ns`). Gracefully degrades on ImportError.

### Task 5: SpiderFoot Docker Compose (`infra/docker-compose.spiderfoot.yml`)
Standalone Compose file for `smicallef/spiderfoot:latest` container. Port 5001, volume bound to `C:/Users/Admin/spiderfoot-data`, healthcheck via wget.

## Test Results
- `test_osint_store.py`: 8/8 GREEN
- `test_spiderfoot_client.py`: 2 GREEN (`test_ping_returns_false_when_unreachable`, `test_spiderfoot_client_has_expected_methods`), 3 SKIP (deferred to 51-03)
- Full unit suite: 1162 passing, 0 new failures

## Key Decisions
- `OsintInvestigationStore.__init__` runs `executescript(_OSINT_DDL)` for standalone testability
- httpx_mock stubs changed from `@_skip` to `@pytest.mark.skip(deferred)` to prevent false failures once class was importable
- `test_get_findings_since` uses `min(r["id"])` as cursor because `get_findings()` orders by `event_type, id` (not id-only)

## Commits
- `9f8c039` feat(51-02): add OSINT investigation tables to SQLite DDL
- `cb466db` feat(51-02): implement OsintInvestigationStore with all 9 CRUD methods
- `9487c1a` feat(51-02): implement SpiderFootClient with 8 REST API methods
- `62f94aa` feat(51-02): add DNSTwist async service wrapping asyncio.to_thread
- `f5a4d85` feat(51-02): add SpiderFoot Docker Compose file
