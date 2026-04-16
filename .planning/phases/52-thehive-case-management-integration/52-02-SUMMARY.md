---
phase: 52-thehive-case-management-integration
plan: "02"
subsystem: thehive-integration
tags: [thehive, case-management, sqlite, docker, cortex]
dependency_graph:
  requires: [52-01]
  provides: [thehive-client-service, thehive-sqlite-schema, thehive-infra]
  affects: [backend/services, backend/stores, infra]
tech_stack:
  added: [thehive4py==2.0.3, strangebee/thehive:5.5, thehiveproject/cortex:3.1.8]
  patterns: [asyncio.to_thread, lazy-import, idempotent-migration, retry-queue]
key_files:
  created:
    - backend/services/thehive_client.py
    - infra/docker-compose.thehive.yml
  modified:
    - backend/core/config.py
    - backend/stores/sqlite_store.py
decisions:
  - _maybe_create_thehive_case is synchronous (not async) — Wave 0 stubs test with synchronous mock_client; Plan 52-03 wiring into detect.py can use asyncio.to_thread wrapper
  - thehive_pending_cases uses detection_json TEXT column (combined JSON blob) not separate detection_id + payload_json — Wave 0 test creates minimal schema with detection_json; production DDL matches
  - ping() is synchronous — used for health checks from non-async contexts; async ping can wrap with asyncio.to_thread if needed
  - _THEHIVE_PENDING_DDL uses detection_json to store combined detection_id + payload for retry processing
metrics:
  duration: "~9 minutes"
  completed: "2026-04-16"
  tasks_completed: 3
  files_modified: 4
---

# Phase 52 Plan 02: TheHive Infrastructure Layer Summary

TheHive infrastructure layer: settings, SQLite schema migrations, async-safe Python client, and Docker Compose stack for GMKtec N100 deployment.

## What Was Built

**Task 1 — Settings + SQLite Schema:**
- Added 4 `THEHIVE_*` settings fields to `Settings` class (URL, API_KEY, ENABLED, SUPPRESS_RULES)
- Added `_THEHIVE_PENDING_DDL` for `thehive_pending_cases` retry queue table
- Added `_THEHIVE_COLUMNS` list for 5 `thehive_*` columns on detections table
- Both migrations applied idempotently in `SQLiteStore.__init__` via try/except ALTER TABLE pattern

**Task 2 — TheHiveClient Service:**
- `TheHiveClient` wraps `thehive4py.TheHiveApi` synchronously with `asyncio.to_thread` for async operations
- `ping()` is synchronous for health-check contexts (returns False, never raises)
- `create_case()`, `create_observable()`, `find_resolved_cases()` are async
- `build_case_payload()` maps `high→3`, `critical→4` (TheHive numeric scale), TLP=2, PAP=2
- `build_observables()` produces `ip` dataType for `src_ip`, `other` dataType for rule_name/ATT&CK/actor_tag
- `_maybe_create_thehive_case()` is synchronous fire-and-forget: checks severity + suppress_rules, enqueues to `thehive_pending_cases` on failure
- Lazy import pattern: `_CLIENT_AVAILABLE = False` allows module import without thehive4py installed
- All 5 Wave 0 stubs GREEN; 3 sync stubs still SKIP (deferred to Plan 52-03)

**Task 3 — Docker Compose:**
- `infra/docker-compose.thehive.yml` with 6 services: cassandra:4.1, elasticsearch:7.17.14 (for TheHive), minio:latest, strangebee/thehive:5.5, cortex_elasticsearch (separate ES:7.17.14 for Cortex), thehiveproject/cortex:3.1.8
- All JVM services memory-capped: Cassandra 600m, each ES 700m, TheHive 900m, Cortex 500m
- Cassandra healthcheck with `nodetool statusgossip`, 120s start_period (JVM warm-up)
- TheHive depends_on cassandra (service_healthy) + elasticsearch + minio
- Cortex Docker socket mount for analyser container execution
- 4 named volumes: thehive_cassandra, thehive_elasticsearch, thehive_minio, cortex_elasticsearch
- Header comment documents: run command, post-deploy Cortex/MISP setup, .env.thehive vars

## Commits

| Hash | Task | Description |
|------|------|-------------|
| a2ca61b | Task 1 | feat(52-02): add TheHive settings + SQLite schema migrations |
| 7933109 | Task 2 | feat(52-02): implement TheHiveClient service + case/observable builders |
| 1ab9a0a | Task 3 | feat(52-02): create infra/docker-compose.thehive.yml for GMKtec N100 |

## Test Results

- `tests/unit/test_thehive_client.py` — 5/5 GREEN
- `tests/unit/test_thehive_sync.py` — 3/3 SKIP (Plan 52-03 deferred)
- Full unit suite: 1182 passed, 7 skipped (1 pre-existing failure in test_metrics_api excluded)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Adapted _maybe_create_thehive_case to synchronous signature**
- **Found during:** Task 2 test execution
- **Issue:** Wave 0 stubs call `_maybe_create_thehive_case(mock_client, detection, suppress_rules=..., db_conn=...)` synchronously with client as first positional arg. Plan spec shows async version with different signature.
- **Fix:** Implemented as synchronous function matching test contract. Production wiring in Plan 52-03 will wrap in `asyncio.to_thread()` or call from non-async context.
- **Files modified:** `backend/services/thehive_client.py`
- **Commit:** 7933109

**2. [Rule 1 - Bug] Changed thehive_pending_cases schema to use detection_json column**
- **Found during:** Task 2 — `test_enqueue_on_failure` creates in-memory table with `detection_json TEXT NOT NULL` not `detection_id + payload_json`
- **Issue:** Plan spec and RESEARCH.md show `detection_id` and `payload_json` as separate columns; Wave 0 test creates minimal `detection_json` schema
- **Fix:** Updated `_THEHIVE_PENDING_DDL` and `_enqueue_pending_case()` to use `detection_json` (a JSON blob combining detection_id + case payload). Test passes; production retry processing reads from the same column.
- **Files modified:** `backend/stores/sqlite_store.py`, `backend/services/thehive_client.py`
- **Commit:** 7933109

## Self-Check: PASSED

- backend/services/thehive_client.py: FOUND
- infra/docker-compose.thehive.yml: FOUND
- 52-02-SUMMARY.md: FOUND
- Commit a2ca61b: FOUND
- Commit 7933109: FOUND
- Commit 1ab9a0a: FOUND
