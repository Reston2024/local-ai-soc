---
phase: 34-asset-inventory
plan: "03"
subsystem: api
tags: [fastapi, mitre-attack, stix, sqlite, asset-inventory, attack-coverage]

# Dependency graph
requires:
  - phase: 34-asset-inventory plan 01
    provides: AttackStore SQLite CRUD, scan_rules_dir_for_coverage, actor_matches()
  - phase: 34-asset-inventory plan 02
    provides: AssetStore SQLite CRUD, list_assets/get_asset/set_tag

provides:
  - GET /api/assets — list all observed assets with ip/hostname/tag/last_seen/alert_count/risk_score
  - GET /api/assets/{ip} — single asset detail, 404 if not found
  - POST /api/assets/{ip}/tag — override asset tag (internal|external)
  - GET /api/attack/coverage — per-tactic ATT&CK heatmap data using MITRE_TACTICS order
  - GET /api/attack/actor-matches — top-3 threat actor groups by TTP overlap with confidence
  - bootstrap_attack_data() — startup STIX download task (idempotent)
  - AttackStore.list_techniques_by_tactic() — SELECT by tactic slug for coverage endpoint

affects: [34-asset-inventory, frontend-dashboard, attack-heatmap-view, assets-view]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "ip:path path parameter used for IPv4 addresses with dots"
    - "asyncio.to_thread() wraps all synchronous AttackStore/AssetStore calls"
    - "bootstrap_attack_data launched via asyncio.ensure_future() in lifespan"
    - "STIX bootstrap skips if technique_count() > 0 (idempotent seed check)"

key-files:
  created:
    - backend/api/assets.py
    - backend/api/attack.py
    - tests/unit/test_attack_api.py
  modified:
    - backend/main.py
    - backend/services/attack/attack_store.py

key-decisions:
  - "attack.py imports MITRE_TACTICS from backend.api.analytics — no duplication"
  - "actor-matches queries detection_techniques via attack_store._conn (shared SQLite connection)"
  - "coverage endpoint returns [] when attack_store absent or rules dir missing — no crash"
  - "bootstrap_attack_data is module-level async fn (not nested) for testability"
  - "list_techniques_by_tactic added to AttackStore (missing method needed by coverage endpoint)"

patterns-established:
  - "Router registration follows try/except pattern for graceful degradation"
  - "app.state.asset_store and app.state.attack_store initialized in lifespan sharing sqlite_store._conn"

requirements-completed: [P34-T03, P34-T04, P34-T08]

# Metrics
duration: 4min
completed: 2026-04-10
---

# Phase 34 Plan 03: Asset Inventory API Summary

**Two new FastAPI routers exposing asset inventory and ATT&CK heatmap/actor-matching data, with STIX bootstrap task wired into app lifespan**

## Performance

- **Duration:** 4 min
- **Started:** 2026-04-10T11:20:03Z
- **Completed:** 2026-04-10T11:24:23Z
- **Tasks:** 3
- **Files modified:** 5 (3 created, 2 modified)

## Accomplishments
- Created `backend/api/assets.py` with GET /api/assets, GET /api/assets/{ip:path}, POST /api/assets/{ip:path}/tag — all auth-gated
- Created `backend/api/attack.py` with GET /api/attack/coverage (per-tactic heatmap) and GET /api/attack/actor-matches (top-3 groups)
- Added `AttackStore.list_techniques_by_tactic()` method (needed by coverage endpoint, missing from Plan 01)
- Wired `AssetStore`, `AttackStore`, and `bootstrap_attack_data` into `main.py` lifespan
- All 7 assets+attack API tests pass; 938 total unit tests green

## Task Commits

Each task was committed atomically:

1. **Task 1: Wave 0 attack API test stubs** - `b782fd7` (test)
2. **Task 2: Assets and Attack API routers** - `0f9ab38` (feat)
3. **Task 3: Wire stores, bootstrap, routers in main.py** - `16c3840` (feat)

## Files Created/Modified
- `tests/unit/test_attack_api.py` — 4 Wave 0 stubs for coverage and actor-matches endpoints
- `backend/api/assets.py` — 3 endpoints: list/detail/tag for asset inventory
- `backend/api/attack.py` — 2 endpoints: ATT&CK coverage heatmap + actor matching
- `backend/services/attack/attack_store.py` — added `list_techniques_by_tactic()` method
- `backend/main.py` — AssetStore/AttackStore imports, bootstrap fn, lifespan init, router registrations

## Decisions Made
- `{ip:path}` path parameter used in assets.py to handle IPv4 addresses (dots in path segments)
- `actor-matches` endpoint queries `detection_techniques` via `attack_store._conn` (shared connection avoids extra state lookups)
- `bootstrap_attack_data` defined as module-level async function, not nested in lifespan, for clarity
- MITRE_TACTICS imported from `backend.api.analytics` — no duplication per plan instruction
- Coverage endpoint returns `[]` rather than raising if `attack_store` not initialized or rules dir absent

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Added `list_techniques_by_tactic()` to AttackStore**
- **Found during:** Task 2 (attack.py coverage endpoint)
- **Issue:** Plan's coverage endpoint calls `attack_store.list_techniques_by_tactic(tactic)` but Plan 01 did not implement this method — it would cause AttributeError at runtime
- **Fix:** Added `list_techniques_by_tactic(tactic: str) -> list[dict]` to AttackStore with `SELECT tech_id, name FROM attack_techniques WHERE tactic=? ORDER BY tech_id`
- **Files modified:** `backend/services/attack/attack_store.py`
- **Verification:** All 7 coverage/assets tests pass
- **Committed in:** `0f9ab38` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 missing critical method)
**Impact on plan:** Required for correctness — coverage endpoint cannot function without this method.

## Issues Encountered
- Pre-existing `test_config.py::test_cybersec_model_default` failure confirmed out-of-scope (fails before any Plan 03 changes, excluded per deviation scope rules)

## User Setup Required
None - no external service configuration required beyond what was already set up.

## Next Phase Readiness
- All 5 API endpoints operational and auth-gated
- ATT&CK STIX bootstrap will self-seed on first startup with internet access
- Assets view and ATT&CK heatmap view (Plan 04) can now be built against these endpoints
- `app.state.asset_store` and `app.state.attack_store` available for any future routes

---
*Phase: 34-asset-inventory*
*Completed: 2026-04-10*
