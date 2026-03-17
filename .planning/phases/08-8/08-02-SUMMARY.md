---
phase: 08-8
plan: "02"
subsystem: api
tags: [telemetry, osquery, fastapi, endpoint, config]

# Dependency graph
requires:
  - phase: 08-8
    provides: OsqueryCollector (08-01) that populates app.state.osquery_collector
provides:
  - GET /api/telemetry/osquery/status endpoint returning 200 always
  - config/osquery/osquery.conf with 4 scheduled queries (process, network, user, file)
  - README.md with osquery install + ACL + verification instructions
affects:
  - dashboard osquery status display
  - integration tests (TestTelemetryAPI xfail stub now resolvable)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Deferred router mount with try/except ImportError (graceful degradation)"
    - "app.state settings preference over module singleton for test overridability"

key-files:
  created:
    - backend/api/telemetry.py
    - config/osquery/osquery.conf
    - config/osquery/README.md
  modified:
    - backend/main.py

key-decisions:
  - "Endpoint always returns 200 — enabled field reflects config, never an error status"
  - "telemetry router mounted via deferred try/except block (matches causality/investigation pattern)"
  - "osquery.conf logger_path set to Windows default C:\\Program Files\\osquery\\log"

patterns-established:
  - "Telemetry API pattern: read from app.state, fallback to module-level settings singleton"

requirements-completed: []

# Metrics
duration: 1min
completed: 2026-03-17
---

# Phase 8 Plan 02: Telemetry Status API + osquery Configuration Summary

**FastAPI GET /api/telemetry/osquery/status endpoint (always 200) + osquery.conf with 4 scheduled queries (process/network/user/file events)**

## Performance

- **Duration:** 1 min
- **Started:** 2026-03-17T18:47:45Z
- **Completed:** 2026-03-17T18:49:36Z
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments
- Created `backend/api/telemetry.py` with `GET /telemetry/osquery/status` that always returns 200
- Mounted telemetry router in `backend/main.py` using the project's deferred try/except pattern
- Created `config/osquery/osquery.conf` with 4 snapshot queries at 30–120s intervals
- All 66 unit tests pass (0 failures)

## Task Commits

Each task was committed atomically:

1. **Task 1: Create backend/api/telemetry.py** - `e5092a2` (feat)
2. **Task 2: Mount telemetry router in backend/main.py** - `a17460e` (feat)
3. **Task 3: Create config/osquery/osquery.conf** - `1dfb419` (feat)

## Files Created/Modified
- `backend/api/telemetry.py` - Telemetry router with osquery status endpoint
- `backend/main.py` - Added telemetry router deferred mount block
- `config/osquery/osquery.conf` - osquery scheduled queries config (4 queries)
- `config/osquery/README.md` - Install, ACL fix, and verification instructions

## Decisions Made
- Endpoint always returns HTTP 200 — the `enabled` field in the JSON body reflects configuration state, so callers never get a 503/404 just because osquery is disabled
- Used the same deferred try/except ImportError mount pattern as causality and investigation routers for consistency
- The telemetry.py module reads `request.app.state.settings` first (allows test overrides) then falls back to the module-level `settings` singleton

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required (osquery is optional, controlled by OSQUERY_ENABLED).

## Next Phase Readiness
- Telemetry status endpoint is live at `/api/telemetry/osquery/status`
- Integration test stub `TestTelemetryAPI.test_telemetry_osquery_status_returns_200` (currently xfail) will pass once the backend is running
- Ready for Phase 8 Plan 03

---
*Phase: 08-8*
*Completed: 2026-03-17*
