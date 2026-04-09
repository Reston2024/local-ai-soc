---
phase: 32-real-threat-hunting
plan: "04"
subsystem: ui
tags: [svelte5, leaflet, openstreetmap, osint, geo-ip, threat-map, detection]

# Dependency graph
requires:
  - phase: 32-real-threat-hunting/32-02
    provides: OSINT enrichment service — GET /api/osint/{ip} with GeoLite2 lat/lon, AbuseIPDB, VirusTotal, WHOIS, Shodan
  - phase: 32-real-threat-hunting/32-03
    provides: Detection interface with src_ip field, api.ts typed client patterns
provides:
  - MapView.svelte: Leaflet.js world map plotting detection source IPs as severity-coloured markers
  - OSINT side panel with country, city, ASN, AbuseIPDB score, VirusTotal count, WHOIS, Shodan
  - "Threat Map" nav item in Intelligence group
  - 60-second auto-refresh via setInterval
affects: [future-threat-hunting-phases, dashboard-views, detection-enrichment]

# Tech tracking
tech-stack:
  added:
    - leaflet ^1.9.4 (world map tiles, circleMarker, layerGroup, tooltip)
    - "@types/leaflet ^1.9.21"
  patterns:
    - Dynamic Leaflet import in onMount (avoids SSR issues, ensures DOM ready)
    - Module-level typed L/map/markerLayer vars set in onMount — no (window as any).L
    - IP deduplication preserving highest severity + count for marker radius scaling
    - Promise.allSettled for concurrent geo fetches (graceful partial failure)
    - Guard check (!L || !map || !markerLayer) in loadMarkers for safe auto-refresh calls

key-files:
  created:
    - dashboard/src/views/MapView.svelte
  modified:
    - dashboard/src/App.svelte
    - dashboard/src/lib/api.ts
    - dashboard/package.json

key-decisions:
  - "api.detections.list() used (not api.detect.list() from plan pseudocode) — matches actual api.ts client"
  - "Detection interface extended with src_ip and created_at fields — required for map marker data"
  - "circleMarker radius = min(6 + detection_count, 14) — scales with frequency, caps at 14px"
  - "Promise.allSettled for geo fetches — private IPs throw 400 from OSINT backend, silently skipped"
  - "Threat Map placed in Intelligence nav group with BETA tag — consistent with hunting/intel pattern"

patterns-established:
  - "Pattern 1: Dynamic Leaflet import — await import('leaflet') + await import('leaflet/dist/leaflet.css') inside onMount"
  - "Pattern 2: Module-level L variable — declared as `let L: typeof import('leaflet') | null = null` at module scope, assigned inside onMount"
  - "Pattern 3: Geo null guard — check osint.geo?.latitude before plotting marker (prevents crash on null geo)"

requirements-completed:
  - P32-T10
  - P32-T11

# Metrics
duration: 15min
completed: 2026-04-09
---

# Phase 32 Plan 04: IP Threat Trace Map Summary

**Leaflet.js world map rendering detection source IPs as severity-coloured circle markers with one-click OSINT side panel, OpenStreetMap tiles, and 60-second auto-refresh**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-04-09T10:09:04Z
- **Completed:** 2026-04-09T10:24:00Z
- **Tasks:** 2 auto + 1 auto-approved checkpoint
- **Files modified:** 4

## Accomplishments

- MapView.svelte: Leaflet map with dynamic import pattern, OSM tiles + attribution, severity-coloured circleMarkers
- IP deduplication (highest severity wins), radius scales with detection count (min 6, max 14px)
- OSINT side panel: geo (country/city/ASN), AbuseIPDB confidence score, VirusTotal counts, WHOIS org/registrar, Shodan ports
- "Threat Map" nav item added to Intelligence group in sidebar with globe SVG icon and BETA tag
- Auto-refresh every 60 seconds via setInterval, cleaned up in onDestroy
- Null geo guard: IPs where GeoLite2 returns null lat/lon are silently skipped, no map crash

## Task Commits

Each task was committed atomically:

1. **Task 0: Install Leaflet and create MapView skeleton** - `b4b5b3f` (feat)
2. **Task 1: Full MapView — Leaflet map, markers, OSINT panel, auto-refresh, nav item** - `d65dc98` (feat)

**Plan metadata:** (see final commit below)

## Files Created/Modified

- `dashboard/src/views/MapView.svelte` - Leaflet world map with severity markers, OSINT side panel, auto-refresh
- `dashboard/src/App.svelte` - MapView import, 'map' View type, Threat Map nav item, view render block
- `dashboard/src/lib/api.ts` - Detection interface extended with `src_ip` and `created_at` fields
- `dashboard/package.json` - leaflet ^1.9.4 + @types/leaflet ^1.9.21 added

## Decisions Made

- **api.detections.list() not api.detect.list()**: Plan pseudocode used wrong api namespace; corrected to match actual api.ts client
- **Detection interface extended**: Added `src_ip?: string | null` and `created_at?: string` — required for map marker data extraction from detections response
- **circleMarker radius formula**: `Math.min(6 + count, 14)` — scales with detection frequency up to 14px cap
- **Promise.allSettled for geo fetches**: Private/loopback IPs return 400 from OSINT backend; allSettled + catch block handles gracefully
- **Threat Map in Intelligence nav group**: Consistent positioning with Hunting/Threat Intel, BETA tag signals feature maturity

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Corrected api namespace: api.detect.list() → api.detections.list()**
- **Found during:** Task 1 (MapView implementation)
- **Issue:** Plan pseudocode referenced `api.detect.list()` but actual api.ts exports `api.detections.list()`
- **Fix:** Used correct `api.detections.list({ limit: 200 })` in MapView loadMarkers()
- **Files modified:** dashboard/src/views/MapView.svelte
- **Verification:** svelte-check passes with 0 new errors
- **Committed in:** d65dc98 (Task 1 commit)

**2. [Rule 2 - Missing Critical] Extended Detection interface with src_ip and created_at**
- **Found during:** Task 0 (reviewing api.ts against plan requirements)
- **Issue:** Detection interface lacked `src_ip` field needed to extract IPs for map markers
- **Fix:** Added `src_ip?: string | null` and `created_at?: string` to Detection interface
- **Files modified:** dashboard/src/lib/api.ts
- **Verification:** svelte-check passes, MapView correctly types d.src_ip
- **Committed in:** b4b5b3f (Task 0 commit)

---

**Total deviations:** 2 auto-fixed (1 bug — wrong api namespace; 1 missing critical — interface field)
**Impact on plan:** Both fixes necessary for correctness. No scope creep.

## Issues Encountered

- Pre-existing svelte-check errors in GraphView, InvestigationPanel, ProvenanceView (10 errors) — all pre-existing, out of scope per deviation boundary rules. MapView introduced 0 new errors.

## User Setup Required

None - no external service configuration required. Leaflet uses OpenStreetMap tiles (no API key).

## Next Phase Readiness

- MapView is complete and integrated; Threat Map nav item is live in sidebar
- Ready for Phase 32-05 or any subsequent plan
- OSINT enrichment pipeline (Phase 32-02) provides the geo data for marker plotting

---
*Phase: 32-real-threat-hunting*
*Completed: 2026-04-09*
