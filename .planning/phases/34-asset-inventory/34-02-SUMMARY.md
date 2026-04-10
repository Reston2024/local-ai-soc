---
phase: 34-asset-inventory
plan: "02"
subsystem: database
tags: [sqlite, asset-inventory, ip-classification, rfc1918, ingestion-pipeline]

requires:
  - phase: 33-real-threat-intelligence
    provides: IocStore, _apply_ioc_matching, asyncio.to_thread pattern in loader.py
  - phase: 34-asset-inventory/34-01
    provides: attack_store.py location, SQLite patterns for attack subsystem

provides:
  - AssetStore SQLite CRUD (upsert/list/get/tag/count) backed by assets table
  - _classify_ip() RFC1918+loopback→internal, else external
  - _apply_asset_upsert() sync ingestion helper called in loader.py to_thread block
  - Wave 0 test stubs for AssetStore (4 tests) and assets API (3 tests)
  - loader.py extended with optional asset_store parameter

affects:
  - 34-asset-inventory/34-03 (assets API — uses AssetStore)
  - 34-asset-inventory/34-04 (AssetsView Svelte — consumes assets API)
  - ingestion/loader.py (asset_store wiring in main.py)

tech-stack:
  added: []
  patterns:
    - AssetStore wraps sqlite3.Connection directly (same as IocStore) for in-memory testability
    - _apply_asset_upsert is synchronous; called inside existing asyncio.to_thread block — no nested to_thread
    - ON CONFLICT(ip) DO UPDATE preserves first_seen, updates hostname (COALESCE) and last_seen

key-files:
  created:
    - backend/services/attack/asset_store.py
    - tests/unit/test_asset_store.py
    - tests/unit/test_assets_api.py
  modified:
    - ingestion/loader.py

key-decisions:
  - "detections table lacks src_ip/dst_ip columns — alert_count and risk_score computed as 0 until schema extended"
  - "_apply_ioc_batch refactored to handle both ioc_store and asset_store in a single to_thread block; block activates if either store is set"
  - "asset_store param in IngestionLoader is optional (None default) — backward-compatible with existing callers"
  - "_classify_ip checks loopback before private — consistent with osint.py pattern (loopback is both in Python 3.11+)"

patterns-established:
  - "AssetStore follows IocStore pattern: direct sqlite3.Connection constructor, all methods synchronous"
  - "Ingestion pipeline auto-classify and register IPs as assets using _apply_asset_upsert after IOC matching"

requirements-completed:
  - P34-T07

duration: 18min
completed: 2026-04-10
---

# Phase 34 Plan 02: Asset Data Layer Summary

**AssetStore SQLite CRUD with RFC1918 IP classification and loader.py ingestion integration, plus Wave 0 API test stubs**

## Performance

- **Duration:** 18 min
- **Started:** 2026-04-10T12:00:00Z
- **Completed:** 2026-04-10T12:18:00Z
- **Tasks:** 3
- **Files modified:** 3 created, 1 modified

## Accomplishments

- AssetStore class with upsert (ON CONFLICT DO UPDATE), list, get, set_tag, count — backed by in-memory-testable SQLite connection
- _classify_ip() correctly classifies RFC1918 (10/8, 172.16/12, 192.168/16) and loopback (127/8) as internal; all others external
- loader.py extended to call _apply_asset_upsert after IOC matching in single asyncio.to_thread block — every ingested event auto-registers src_ip and dst_ip as assets
- 7 Wave 0 test stubs (4 store + 3 API) all skip cleanly before implementation

## Task Commits

1. **Task 1: Wave 0 asset test stubs** - `2a9f4b0` (test)
2. **Task 2: AssetStore implementation** - `390cd9b` (feat)
3. **Task 3: Integrate asset upsert into loader.py** - `aae921c` (feat)

## Files Created/Modified

- `backend/services/attack/asset_store.py` - AssetStore class, _classify_ip(), _apply_asset_upsert(), _DDL for assets table
- `tests/unit/test_asset_store.py` - 4 Wave 0 unit stubs for AssetStore (all pass after Task 2)
- `tests/unit/test_assets_api.py` - 3 Wave 0 unit stubs for assets API (skip pending Plan 03)
- `ingestion/loader.py` - Added AssetStore import, asset_store param, _apply_asset_upsert call in _apply_ioc_batch

## Decisions Made

- **alert_count/risk_score = 0**: The detections SQLite table does not carry src_ip/dst_ip columns (stores matched_event_ids as JSON array). Alert count join from plan would fail. Returning 0 statically for Phase 34; schema extension deferred to a future phase.
- **Single to_thread block for both IOC and asset**: Refactored _apply_ioc_batch to loop over events and call both _apply_ioc_matching and _apply_asset_upsert per event, rather than two separate to_thread dispatches — avoids overhead and keeps logic co-located.
- **Optional asset_store**: IngestionLoader accepts asset_store=None (default) for backward compatibility with existing callers that don't have an AssetStore yet.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] detections table JOIN columns do not exist**
- **Found during:** Task 2 (AssetStore implementation)
- **Issue:** Plan's list_assets/get_asset SQL used `d.src_ip` and `d.dst_ip` in a subquery against the detections table, but the detections DDL (backend/stores/sqlite_store.py) only has id, rule_id, rule_name, severity, matched_event_ids, attack_technique, attack_tactic, explanation, case_id, created_at — no IP columns.
- **Fix:** Replaced subquery with literal `0 AS alert_count, 0 AS risk_score` in both list_assets and get_asset. Documented in docstring.
- **Files modified:** backend/services/attack/asset_store.py
- **Verification:** All 4 test_asset_store.py tests pass including test_upsert_dedup which calls get_asset
- **Committed in:** 390cd9b (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - Bug)
**Impact on plan:** Fix required for correctness — SQL would error at runtime. No scope change; alert_count field is present in API response, just returns 0 until detections schema adds IP columns.

## Issues Encountered

None beyond the deviation documented above.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- AssetStore is ready for Plan 03 (assets API router) to wire app.state.asset_store
- IngestionLoader constructor accepts asset_store parameter — main.py wiring in Plan 03 is the integration point
- Wave 0 API stubs in test_assets_api.py will activate (skip → pass) once backend/api/assets.py is created in Plan 03

---
*Phase: 34-asset-inventory*
*Completed: 2026-04-10*
