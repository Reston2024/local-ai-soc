---
phase: 32-real-threat-hunting
plan: 01
subsystem: api
tags: [duckdb, sqlite, fastapi, ollama, threat-hunting, nlp-to-sql, mitre-attack]

requires:
  - phase: 31-malcolm-full-telemetry
    provides: normalized_events DuckDB table with 55-column schema, SQLiteStore, OllamaClient

provides:
  - NL→SQL hunt engine (validate_hunt_sql + HuntEngine.run())
  - SQLite hunts table for hunt persistence
  - POST /api/hunts/query — NL threat hunt endpoint
  - GET /api/hunts/presets — 6 MITRE-tagged preset hunt definitions
  - GET /api/hunts/{hunt_id}/results — stored result retrieval

affects: [32-02, 32-03, 32-04, dashboard-integration]

tech-stack:
  added: []
  patterns:
    - "validate_hunt_sql: whitelist-based SQL safety with 7 rejection rules before DuckDB execution"
    - "HuntEngine: per-request instantiation, stores injected via constructor (not singletons)"
    - "Deferred router try/except pattern: hunting router added after notifications router in create_app()"

key-files:
  created:
    - backend/services/hunt_engine.py
    - backend/api/hunting.py
    - tests/unit/test_hunt_engine.py
  modified:
    - backend/stores/sqlite_store.py
    - backend/main.py
    - backend/core/config.py

key-decisions:
  - "Multi-statement check runs BEFORE DDL check — semicolon in 'SELECT ... ; DROP TABLE x' must be caught as multi-statement, not DDL"
  - "COPY and ATTACH checks precede first-keyword check — these are non-SELECT SQL without triggering the SELECT rule"
  - "GET /api/hunts/presets defined BEFORE /{hunt_id}/results in router to prevent 'presets' being captured as hunt_id path param"
  - "OSINT API keys (ABUSEIPDB_API_KEY, VT_API_KEY, SHODAN_API_KEY, GEOIP_DB_PATH) added to config.py — all optional with empty string defaults"

patterns-established:
  - "SQL validator: check multi-statement first, then forbidden keywords, then first-token SELECT, then table whitelist"
  - "Hunt results ranked by (severity_rank, ts_descending) before persistence — ranking is immutable in stored results"

requirements-completed: [P32-T01, P32-T02, P32-T03, P32-T07]

duration: 3min
completed: 2026-04-09
---

# Phase 32 Plan 01: Real Threat Hunting — Hunt Engine Summary

**NL→SQL threat hunting engine with 7-rule SQL safety validator, DuckDB execution, severity-ranked results, SQLite persistence, and 3 authenticated FastAPI endpoints**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-04-09T09:30:02Z
- **Completed:** 2026-04-09T09:33:22Z
- **Tasks:** 3 (Task 0 TDD RED, Task 1 TDD GREEN, Task 2 API)
- **Files modified:** 6

## Accomplishments

- validate_hunt_sql blocks DDL, DML, ATTACH, COPY, multi-statement, non-normalized_events tables, and system tables
- HuntEngine.run() translates natural language to DuckDB SQL via Ollama, executes read-only, ranks by severity/recency, persists to SQLite
- 3 API endpoints registered under /api/hunts with verify_token auth; 6 MITRE-tagged preset hunt definitions (T1059.001, T1071, T1078, T1218, T1021, T1003)
- SQLite hunts table added with idempotent DDL (CREATE IF NOT EXISTS); save_hunt/get_hunt/list_hunts methods added to SQLiteStore
- 891 unit tests pass (9 new hunt tests + 882 prior — no regressions)

## Task Commits

1. **Task 0: Write failing test stubs for hunt engine** — `5887250` (test)
2. **Task 1: Implement hunt engine service + SQLite schema** — `7602e54` (feat)
3. **Task 2: Implement hunting API router and register in main.py** — `d573c6c` (feat)

## Files Created/Modified

- `backend/services/hunt_engine.py` — validate_hunt_sql, _rank_results, HuntResult dataclass, HuntEngine class, PRESET_HUNTS constant
- `backend/api/hunting.py` — FastAPI router: POST /hunts/query, GET /hunts/presets, GET /hunts/{id}/results
- `tests/unit/test_hunt_engine.py` — 9 unit tests covering all validator rules, ranking, and dataclass fields
- `backend/stores/sqlite_store.py` — hunts table DDL appended to _DDL, save_hunt/get_hunt/list_hunts methods added
- `backend/main.py` — hunting router registered in create_app() deferred try/except block
- `backend/core/config.py` — ABUSEIPDB_API_KEY, VT_API_KEY, SHODAN_API_KEY, GEOIP_DB_PATH added to Settings

## Decisions Made

- Multi-statement semicolon check must precede DDL keyword check: `"SELECT...; DROP TABLE x"` should raise "multiple statements" not "DDL not allowed" — ordering matters for UX clarity
- `GET /api/hunts/presets` placed before `GET /api/hunts/{hunt_id}/results` in router to avoid FastAPI capturing "presets" as a hunt_id path parameter
- OSINT keys added to config.py now (empty defaults) so Phase 32 subsequent plans can use them without modifying config again

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Reordered SQL validator checks to fix multi-statement test failure**
- **Found during:** Task 1 (TDD GREEN — running tests after implementation)
- **Issue:** `validate_hunt_sql("SELECT * FROM normalized_events; DROP TABLE x")` raised "DDL not allowed" instead of "multiple statements not allowed" because DDL check ran before semicolon check
- **Fix:** Moved multi-statement (semicolon) check to first position in validate_hunt_sql, before ATTACH/COPY/DDL checks
- **Files modified:** backend/services/hunt_engine.py
- **Verification:** All 9 tests pass after reorder
- **Committed in:** `7602e54` (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - validator ordering bug)
**Impact on plan:** Required for correct error messaging to analyst. No scope creep.

## Issues Encountered

None beyond the auto-fixed validator ordering issue above.

## User Setup Required

None — all new settings have empty string defaults and are optional. No external service configuration required for basic hunt functionality (Ollama must be running for NL→SQL translation, but that was already required).

## Next Phase Readiness

- Hunt engine API is live and auth-gated — ready for Phase 32-02 (OSINT enrichment)
- OSINT config fields (VT_API_KEY, ABUSEIPDB_API_KEY, SHODAN_API_KEY) are pre-wired in Settings
- SQLite hunts table exists; Phase 32-04 dashboard can query /api/hunts endpoints immediately

---
*Phase: 32-real-threat-hunting*
*Completed: 2026-04-09*
