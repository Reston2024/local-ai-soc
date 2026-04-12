---
phase: 41-threat-map-overhaul
plan: 02
subsystem: api
tags: [fastapi, duckdb, typescript, network-flow, ipaddress, threat-map]

# Dependency graph
requires:
  - phase: 41-01
    provides: Wave 0 TDD stubs for map API (test_map_api.py)
provides:
  - backend/api/map.py with WINDOW_TO_SECONDS, detect_direction, parse_ipsum_line, build_map_stats, GET /data route
  - Map router registered in main.py at /api/map prefix
  - TypeScript MapIpInfo, MapFlow, MapStats, MapData interfaces + api.map.getData() in api.ts
affects:
  - 41-03 (OSINT classification columns needed for ip_type/ipsum_tier fields)
  - 41-04 (MapView.svelte rewrite consumes api.map.getData())

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "DuckDB flow query uses ISO datetime cutoff string param (not INTERVAL ? syntax)"
    - "ipaddress.ip_address() for RFC1918 classification — consistent with osint_api.py _sanitize_ip pattern"
    - "asyncio.to_thread(sqlite_store.get_osint_cache) for non-blocking OSINT cache reads"
    - "asyncio.ensure_future() for background enrichment of cache-miss IPs (fire-and-forget)"

key-files:
  created:
    - backend/api/map.py
  modified:
    - backend/main.py
    - dashboard/src/lib/api.ts
    - tests/unit/test_map_api.py

key-decisions:
  - "detect_direction treats both-private (internal-to-internal) as outbound — src node radiates from LAN"
  - "_resolve_ip_type fallback checks result_json for legacy ip-api.com proxy/hosting booleans (pre-Plan-03 cache)"
  - "build_map_stats uses _conn_total internal field for country weighting, stripped before HTTP response"
  - "map router registered with try/except in main.py lifespan — consistent with atomics/triage router pattern"
  - "MapFlow direction typed as union literal in TypeScript — prevents invalid direction values at compile time"

patterns-established:
  - "Map API pattern: DuckDB flow query → direction annotation → OSINT cache lookup → stats aggregation"
  - "IP classification: _is_private() used consistently for RFC1918+loopback+link-local detection"

requirements-completed: [P41-T01, P41-T02, P41-T05]

# Metrics
duration: 18min
completed: 2026-04-12
---

# Phase 41 Plan 02: Threat Map Data Layer Summary

**FastAPI GET /api/map/data endpoint returning top-500 network_connection flows with RFC1918 direction classification, DuckDB cutoff query, OSINT cache enrichment, and TypeScript MapFlow/MapIpInfo/MapStats interfaces**

## Performance

- **Duration:** 18 min
- **Started:** 2026-04-12T11:42:06Z
- **Completed:** 2026-04-12T12:00:00Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- Created `backend/api/map.py` with full flow query + direction classification + OSINT enrichment logic
- Registered map router at `/api/map` prefix in main.py lifespan (try/except pattern)
- Added 4 TypeScript interfaces (MapIpInfo, MapFlow, MapStats, MapData) and `api.map.getData()` to api.ts
- TDD: test_window_mapping, test_direction_detection, test_ipsum_parser, test_stats_aggregation all GREEN (4 pass, 2 appropriate SKIP for integration stubs)

## Task Commits

Each task was committed atomically:

1. **Task 1: Create backend/api/map.py** - `874109e` (feat)
2. **Task 2: Wire map router + add api.ts interfaces** - `61d7f17` (feat)

**Plan metadata:** (to be committed with SUMMARY.md)

## Files Created/Modified
- `backend/api/map.py` — WINDOW_TO_SECONDS, detect_direction, parse_ipsum_line, build_map_stats, GET /data endpoint
- `backend/main.py` — map_router import + app.include_router registration in lifespan
- `dashboard/src/lib/api.ts` — MapIpInfo, MapFlow, MapStats, MapData interfaces + api.map.getData()
- `tests/unit/test_map_api.py` — parse_ipsum_line import added, test_ipsum_parser + test_stats_aggregation implemented

## Decisions Made
- `detect_direction` treats both-private flows as "outbound" — consistent with LAN-node radiating model
- `_resolve_ip_type` fallback reads legacy ip-api.com fields from `result_json` blob to handle pre-Plan-03 cached data gracefully
- `build_map_stats` uses internal `_conn_total` field for country weighting (stripped before HTTP response)
- Map router uses try/except wrapping in main.py — matches atomics/triage pattern for graceful degradation

## Deviations from Plan

None - plan executed exactly as written.

The `test_stats_aggregation` stub was upgraded to a real assertion (not a deviation — Plan 02 explicitly implements `build_map_stats`). The `test_ipsum_parser` test was added alongside the guard import update since `parse_ipsum_line` was listed in the behavior spec for Task 1.

## Issues Encountered
None.

## Self-Check

- `backend/api/map.py` — FOUND
- `backend/main.py` map_router — FOUND (61d7f17)
- `dashboard/src/lib/api.ts` MapFlow — FOUND (61d7f17)
- 1033 unit tests pass, 0 failures

## Self-Check: PASSED

## Next Phase Readiness
- Plan 03 can now add `ip_type`, `ipsum_tier`, `is_tor`, `is_proxy`, `is_datacenter` columns to `osint_cache` — map.py handles None gracefully via `_resolve_ip_type` fallback
- Plan 04 (MapView.svelte rewrite) has the full TypeScript contract via `api.map.getData()` and the 4 interfaces
- No blockers

---
*Phase: 41-threat-map-overhaul*
*Completed: 2026-04-12*
