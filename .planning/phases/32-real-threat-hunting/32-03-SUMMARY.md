---
phase: 32-real-threat-hunting
plan: "03"
subsystem: ui
tags: [svelte5, typescript, hunting, osint, threat-hunting, api-client]

# Dependency graph
requires:
  - phase: 32-01
    provides: POST /api/hunts/query, GET /api/hunts/presets, GET /api/hunts/{id}/results backend
  - phase: 32-02
    provides: GET /api/osint/{ip} passive OSINT enrichment backend

provides:
  - Fully wired HuntingView.svelte with hunt query input, results table, OSINT panel, presets, history
  - TypeScript interfaces for HuntPreset, HuntRow, HuntResult, HuntHistoryItem, OsintResult and sub-types
  - api.hunts.query(), api.hunts.presets(), api.hunts.getResults() typed functions
  - api.osint.get() typed function

affects:
  - 32-real-threat-hunting
  - dashboard ui

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Svelte 5 runes ($state/$derived) for all reactive state — no stores
    - Per-row OSINT expansion pattern: expandedIp $state drives inline OSINT panel
    - Hunt history accumulated in $state array, capped at 10, clickable to replay

key-files:
  created: []
  modified:
    - dashboard/src/views/HuntingView.svelte
    - dashboard/src/lib/api.ts

key-decisions:
  - "Existing Detection interface (more complete, phase 22) kept — plan proposed simpler version that would conflict"
  - "Private IP check in expandRow() handles loopback + RFC1918 ranges before calling api.osint.get()"
  - "history-item uses role=button + onkeydown for a11y (svelte-check warns on non-interactive div with click)"
  - "osint-row backend 400 error caught silently — error displayed as 'No OSINT data available' rather than crash"

patterns-established:
  - "Preset hunt queries embedded in frontend match PRESET_HUNTS in hunt_engine.py exactly (query text)"
  - "expandedIp === row.src_ip pattern for per-row OSINT toggle — single expanded row at a time"

requirements-completed:
  - P32-T04
  - P32-T05
  - P32-T06

# Metrics
duration: 18min
completed: 2026-04-09
---

# Phase 32 Plan 03: Hunting UI Wire-Up Summary

**HuntingView.svelte fully wired to hunt backend — NL query input, live results table with per-row OSINT enrichment panel, 6 preset cards, and hunt history replay**

## Performance

- **Duration:** 18 min
- **Started:** 2026-04-09T10:10:00Z
- **Completed:** 2026-04-09T10:28:00Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Added 9 TypeScript interfaces (HuntPreset, HuntRow, HuntResult, HuntHistoryItem, OsintWhois, OsintAbuseIPDB, OsintGeo, OsintVirusTotal, OsintShodan, OsintResult) to api.ts
- Added api.hunts and api.osint sub-objects with 4 typed functions to api.ts
- Rewrote HuntingView.svelte — removed all disabled/BETA placeholders, fully functional hunting interface
- Results table shows ts, hostname, severity badge (colored), event_type, src_ip, dst_ip, process_name, user_name
- Per-row OSINT expansion panel (GEO/ABUSE/VT/WHOIS/SHODAN sections) triggered by clicking src_ip row
- All 6 preset hunt cards functional — onclick fires runHunt() with exact backend query text
- Hunt history panel tracks last 10 queries with row count, clickable to replay

## Task Commits

Each task was committed atomically:

1. **Task 0: Add hunt and OSINT typed functions to api.ts** - `6c7c85c` (feat)
2. **Task 1: Wire HuntingView.svelte** - `0522390` (feat)

## Files Created/Modified
- `dashboard/src/lib/api.ts` - Added HuntPreset/HuntRow/HuntResult/HuntHistoryItem/OsintResult interfaces and api.hunts + api.osint functions
- `dashboard/src/views/HuntingView.svelte` - Complete rewrite from disabled placeholder to fully functional hunting UI

## Decisions Made
- Kept existing (more complete) Detection interface from Phase 22 rather than replacing with plan's simpler version
- Private IP check in expandRow() handles RFC1918 + loopback before backend call to avoid unnecessary requests
- OSINT fetch errors caught silently with fallback message — prevents UI crash on 400 (private IP) errors
- Hunt history div uses role="button" + onkeydown for a11y compliance (svelte a11y lint)

## Deviations from Plan

None - plan executed exactly as written. The existing Detection interface was more complete than the plan proposed; rather than replacing it, the new hunt interfaces were added alongside it (no conflict).

## Issues Encountered
- Pre-existing svelte-check errors in GraphView.svelte, InvestigationPanel.svelte, ProvenanceView.svelte (10 errors, 3 warnings) — all out of scope, unchanged by this plan. No new errors introduced.

## User Setup Required
None - no external service configuration required. Hunt and OSINT backend endpoints were wired in Plans 32-01 and 32-02.

## Next Phase Readiness
- Hunting UI is fully functional: analyst can type NL queries, click preset cards, view results with OSINT enrichment, and replay history
- Phase 32 frontend work complete — ready for any remaining 32-0x plans or Phase 33
- OSINT enrichment requires API keys (AbuseIPDB, VirusTotal, Shodan) set in backend config for non-null results; GeoIP works without keys

---
*Phase: 32-real-threat-hunting*
*Completed: 2026-04-09*
