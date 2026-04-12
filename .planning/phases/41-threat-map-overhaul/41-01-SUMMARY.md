---
phase: 41-threat-map-overhaul
plan: 01
subsystem: testing
tags: [pytest, tdd, wave-0, stubs, map-api, osint, threat-map]

# Dependency graph
requires:
  - phase: 40-atomic-red-team-validation
    provides: skipif-importerror guard pattern for Wave 0 TDD stubs
provides:
  - 5 RED TDD stubs for map API (WINDOW_TO_SECONDS, detect_direction, build_map_stats, flow query, endpoint shape)
  - 6 RED TDD stubs for OSINT classification (ipapi.is, ipsum tier, Tor exit, cache migration, ipsum parser, geo fields)
affects:
  - 41-02 (must satisfy test_window_mapping, test_direction_detection, test_flow_query_structure, test_stats_aggregation, test_map_endpoint_response_shape)
  - 41-03 (must satisfy test_geo_ipapi_extended_fields, test_ipapi_is_parse, test_ipsum_tier_lookup, test_tor_exit_check, test_osint_cache_schema_migration, test_ipsum_parser)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "skipif-importerror guard pattern for Wave 0 TDD stubs — per-module guards allow clean SKIP before implementation"
    - "Mixed guard strategies: pytestmark for module-wide skip, @pytest.mark.skipif for individual tests with different guards"

key-files:
  created:
    - tests/unit/test_map_api.py
    - tests/unit/test_osint_classification.py
  modified: []

key-decisions:
  - "test_map_api.py uses pytestmark skipif-importerror guard — all 5 stubs SKIP as a unit when backend/api/map.py absent"
  - "test_osint_classification.py uses mixed guards — separate try/except blocks for OsintService methods vs SQLiteStore vs ipsum parser (different files, different availability)"
  - "test_window_mapping and test_direction_detection will activate as GREEN immediately once Plan 02 adds the pure-logic functions"
  - "test_ipsum_parser deferred to test_osint_classification.py despite map.py origin — tests OSINT classification pipeline end-to-end"

patterns-established:
  - "Wave 0 stubs always SKIP (not ERROR) — import guards wrap all module-level symbols that do not exist yet"
  - "Per-stub pytest.skip() call is idiomatic for stubs that test async/I/O behavior not yet implemented"

requirements-completed:
  - P41-T01
  - P41-T02
  - P41-T03
  - P41-T04
  - P41-T05
  - P41-T06
  - P41-T07

# Metrics
duration: 2min
completed: 2026-04-12
---

# Phase 41 Plan 01: Threat Map Overhaul Summary

**11 Wave 0 TDD stubs created across 2 files — 5 map API contracts and 6 OSINT classification contracts, all SKIP cleanly against 1028 existing passing tests**

## Performance

- **Duration:** 2 min
- **Started:** 2026-04-12T13:01:37Z
- **Completed:** 2026-04-12T13:03:14Z
- **Tasks:** 3
- **Files modified:** 2

## Accomplishments
- Created tests/unit/test_map_api.py with 5 behavioral contracts for Plan 02 (WINDOW_TO_SECONDS mapping, RFC1918 direction detection, flow query structure, stats aggregation, endpoint shape)
- Created tests/unit/test_osint_classification.py with 6 behavioral contracts for Plan 03 (ip-api extended fields, ipapi.is parsing, ipsum tier lookup, Tor exit check, schema migration, ipsum parser)
- Full unit suite confirmed: 1028 passed, 13 skipped (includes 11 new stubs), 0 failures, 0 errors

## Task Commits

Each task was committed atomically:

1. **Task 1: Write test_map_api.py — 5 RED stubs** - `92a4f0e` (test)
2. **Task 2: Write test_osint_classification.py — 6 RED stubs** - `3464433` (test)
3. **Task 3: Verify full suite baseline** - no commit (verification only, no files changed)

**Plan metadata:** (docs commit below)

## Files Created/Modified
- `tests/unit/test_map_api.py` - 5 Wave 0 RED stubs for map data layer; skipif-importerror pytestmark guard
- `tests/unit/test_osint_classification.py` - 6 Wave 0 RED stubs for OSINT classification extension; mixed per-guard strategy

## Decisions Made
- test_map_api.py uses module-level `pytestmark = pytest.mark.skipif(not _MAP_AVAILABLE, ...)` — consistent with test_atomics_api.py and test_car_analytics.py patterns from prior phases
- test_osint_classification.py uses 3 separate import guards (_OSINT_CLASSIFY_AVAILABLE, _SQLITE_AVAILABLE, _IPSUM_PARSER_AVAILABLE) since the 6 stubs span 3 different source files with independent availability
- test_window_mapping and test_direction_detection have real assertions (not pytest.skip) — they will turn GREEN immediately when Plan 02 delivers the pure-logic functions without any async/I/O dependencies

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None. A linter added `parse_ipsum_line` to the test_map_api.py import guard during Task 2; this is correct since test_ipsum_parser in test_osint_classification.py imports from backend.api.map, and having the symbol in the guard is harmless.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Plan 02 should implement backend/api/map.py with WINDOW_TO_SECONDS dict, detect_direction(), build_map_stats(), get_network_flows(), and GET /api/map/data endpoint
- Plan 03 should implement OsintService._ipapi_is(), OsintService._ipsum_check(), SQLiteStore.get_ipsum_tier(), SQLiteStore.get_tor_exit(), ALTER TABLE migrations on osint_cache, and parse_ipsum_line() in map.py
- All 11 stubs are well-defined behavioral contracts with explicit pytest.skip() messages citing the implementing plan

---
*Phase: 41-threat-map-overhaul*
*Completed: 2026-04-12*
