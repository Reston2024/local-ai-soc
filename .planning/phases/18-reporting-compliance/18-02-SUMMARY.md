---
phase: 18-reporting-compliance
plan: "02"
subsystem: api
tags: [mitre-attack, analytics, coverage-matrix, fastapi, sqlite]

# Dependency graph
requires:
  - phase: 17-playbooks
    provides: playbooks table with trigger_conditions JSON column
  - phase: 12-api-hardening
    provides: detections table with attack_technique and attack_tactic columns

provides:
  - GET /api/analytics/mitre-coverage endpoint returning tactic→technique→{sources,status} matrix
  - SQLiteStore.get_detection_techniques() — detections with non-null attack_technique
  - SQLiteStore.get_playbook_trigger_conditions() — flat list of trigger_conditions JSON strings
  - MITRE_TACTICS ordered constant (14-tactic Enterprise ATT&CK v14 list)

affects: [18-05-mitre-heatmap-ui, future-hunt-results-integration]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "asyncio.to_thread() wrapping synchronous SQLiteStore reads in async route handlers"
    - "Regex ^T\\d{4} for parsing MITRE technique IDs from freeform trigger_condition strings"
    - "Status priority ladder: detected > hunted > playbook_covered > not_covered"

key-files:
  created:
    - backend/api/analytics.py
    - tests/unit/test_analytics_mitre.py
  modified:
    - backend/stores/sqlite_store.py
    - backend/main.py

key-decisions:
  - "Used existing shared-connection pattern (self._conn.execute) for new store methods instead of plan's factory pattern — actual codebase uses a stored connection object, not a _conn() factory; changing to a factory would be an architectural refactor out of scope"
  - "Routed techniques with unknown tactic to 'other' bucket rather than dropping them — preserves coverage data integrity for non-standard tactic strings"
  - "analytics_router registered via deferred try/except in main.py (consistent with other Phase 17/18 routers) rather than hard import at module level"

patterns-established:
  - "Analytics routers follow same deferred-import/graceful-degradation pattern as playbooks and reports routers"
  - "Store helper methods for analytics queries are synchronous and wrapped via asyncio.to_thread at the route layer"

requirements-completed: [P18-T02]

# Metrics
duration: 2min
completed: 2026-03-31
---

# Phase 18 Plan 02: MITRE ATT&CK Coverage Analytics API Summary

**FastAPI analytics router with GET /api/analytics/mitre-coverage cross-referencing detection attack_technique columns and playbook trigger_conditions JSON to produce a tactic-keyed coverage matrix with detected/playbook_covered/not_covered status.**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-31T18:51:05Z
- **Completed:** 2026-03-31T18:52:47Z
- **Tasks:** 1 (combined store methods + router + tests)
- **Files modified:** 4

## Accomplishments

- Added `get_detection_techniques()` and `get_playbook_trigger_conditions()` to `SQLiteStore` using the existing shared-connection pattern
- Created `backend/api/analytics.py` with `MITRE_TACTICS` constant (14 tactics, Enterprise ATT&CK v14 order) and `GET /api/analytics/mitre-coverage`
- Coverage sources correctly populated: detections → "detected", playbook trigger_conditions matching `^T\d{4}` → "playbook_covered", with multi-source deduplication
- Response always returns `{"tactics": [...], "coverage": {...}}` even with empty database (200 OK, empty coverage dict)
- 3 unit tests pass covering empty state, detection-only, and playbook-only coverage scenarios
- Router registered in `main.py` after reports_router using deferred try/except pattern

## Task Commits

Each task was committed atomically:

1. **Task 1: Store helpers + analytics router + tests + main.py registration** - `bd5e02f` (feat)

## Files Created/Modified

- `backend/api/analytics.py` — FastAPI router with MITRE_TACTICS constant and /api/analytics/mitre-coverage GET endpoint
- `tests/unit/test_analytics_mitre.py` — 3 unit tests: empty coverage, detection appears in coverage, playbook adds coverage
- `backend/stores/sqlite_store.py` — Added get_detection_techniques() and get_playbook_trigger_conditions() methods
- `backend/main.py` — Registered analytics_router via deferred try/except after reports_router

## Decisions Made

- **Existing connection pattern preserved:** The plan's `<interfaces>` block showed a `_conn()` factory method, but the actual `SQLiteStore` uses a stored connection attribute `self._conn`. New methods follow the existing `self._conn.execute(...)` pattern to avoid architectural changes. (See Deviations.)
- **"other" tactic bucket:** Techniques with attack_tactic not in MITRE_TACTICS are bucketed under "other" rather than dropped, preserving coverage data for non-standard or custom tactic strings.
- **Deferred router registration:** Consistent with other Phase 17/18 routers, the analytics router is registered via try/except deferred import, enabling graceful degradation if the module is absent.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Used actual SQLiteStore connection pattern instead of plan's interface-block factory pattern**
- **Found during:** Task 1 (reading sqlite_store.py before implementation)
- **Issue:** The plan's `<interfaces>` block described `def _conn(self) -> sqlite3.Connection:` as a factory/context-manager returning a new connection each call. The actual `SQLiteStore.__init__` creates `self._conn = sqlite3.connect(...)` and stores it as an instance attribute (shared connection, not factory). All 30+ existing methods call `self._conn.execute(...)` directly. Using `with self._conn() as conn:` would fail with `TypeError: 'sqlite3.Connection' object is not callable`.
- **Fix:** Implemented new methods using `self._conn.execute(...)` directly, matching every other method in the class.
- **Files modified:** backend/stores/sqlite_store.py
- **Verification:** `uv run pytest tests/unit/test_analytics_mitre.py -v` — 3/3 pass; `uv run python -c "from backend.api.analytics import router; ..."` confirms route path.
- **Committed in:** bd5e02f (task commit)

---

**Total deviations:** 1 auto-fixed (1 bug — interface spec mismatch)
**Impact on plan:** Essential fix for correctness. The plan's interface block described an ideal pattern not present in the codebase. Following the actual pattern ensures the new methods work identically to all existing store methods. No scope creep.

## Issues Encountered

None — aside from the connection pattern deviation, execution followed the plan exactly.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- MITRE coverage API is ready for the frontend heatmap (plan 05)
- The "hunted" source bucket is reserved and will be populated when hunt result integration is implemented
- The `other` tactic bucket will surface techniques with non-standard tactic strings for future cleanup

## Self-Check: PASSED

All created files verified on disk. Task commit bd5e02f confirmed in git log.

---
*Phase: 18-reporting-compliance*
*Completed: 2026-03-31*
