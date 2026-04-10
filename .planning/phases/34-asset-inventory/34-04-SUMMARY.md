---
phase: 34-asset-inventory
plan: "04"
subsystem: dashboard
tags: [frontend, svelte5, assets, attack-coverage, mitre-attck]
dependency_graph:
  requires: [34-03]
  provides: [AssetsView, AttackCoverageView, api.assets, api.attack]
  affects: [dashboard/src/App.svelte, dashboard/src/lib/api.ts]
tech_stack:
  added: []
  patterns: [svelte5-runes, $state, $effect, $derived, expand-collapse-table]
key_files:
  created:
    - dashboard/src/views/AttackCoverageView.svelte
  modified:
    - dashboard/src/views/AssetsView.svelte
    - dashboard/src/lib/api.ts
    - dashboard/src/App.svelte
    - dashboard/src/views/ThreatIntelView.svelte
    - dashboard/src/views/MapView.svelte
    - config/caddy/Caddyfile
decisions:
  - "Pre-existing TypeScript errors in GraphView, InvestigationPanel, ProvenanceView are out of scope — errors existed before plan 34-04"
  - "ATT&CK Coverage placed between Threat Intel and Hunting (not between Threat Intel and Threat Map) because navGroups array literal order puts Hunting before Threat Map in the Intelligence group"
  - "OSINT fetch uses Promise.allSettled to handle private IP partial failure gracefully"
  - "tactic-col div given role=button + onkeydown to resolve a11y warnings"
  - "ThreatIntelView import fixed to relative path (../lib/api.ts) — $lib alias not resolvable in Svelte compile context"
  - "MapView Leaflet requires static CSS import and explicit invalidateSize() call after flex layout paint"
  - "Caddy /health* glob pattern needed to proxy /health/network subpath; img-src + font-src CSP additions for OSM tile domains"
metrics:
  duration: ~12 minutes
  tasks_completed: 3 of 3
  files_changed: 7
  completed_date: "2026-04-10"
---

# Phase 34 Plan 04: Dashboard — AssetsView + AttackCoverageView Summary

**One-liner:** IP-centric asset table with inline OSINT detail panel + 14-column ATT&CK heat-scaled heatmap with tactic drill-down, wired via typed api.assets/api.attack client groups, plus post-verify fixes for ThreatIntelView import path, MapView Leaflet rendering, and Caddy CSP/routing.

## Status

**COMPLETE** — all 3 tasks done. Human-verify checkpoint approved by user.

## Tasks Completed

| Task | Description | Commit |
|------|-------------|--------|
| 1 | api.ts — Asset + TacticCoverage + ActorMatch interfaces + api.assets + api.attack groups | 830b87c |
| 2 | AssetsView rewrite + AttackCoverageView new file + App.svelte nav wiring | ef10757 |
| 3 | Human-verify checkpoint — approved; post-verify fixes applied | 233d007, 001d927, d60c4d7, 250b09d, f91c175 |

## What Was Built

### Task 1 — api.ts additions

Added three new TypeScript interfaces to `dashboard/src/lib/api.ts`:
- `Asset`: ip, hostname, tag (internal/external), risk_score, last_seen, first_seen, alert_count
- `TacticCoverage`: tactic, tactic_short, total_techniques, covered_count, techniques[]
- `ActorMatch`: name, aliases, group_id, overlap_pct, confidence (High/Medium/Low), matched_count, total_count

Added two new api groups:
- `api.assets.list(limit=200)` — GET /api/assets?limit={n}
- `api.assets.get(ip)` — GET /api/assets/{encodeURIComponent(ip)}
- `api.assets.tag(ip, tag)` — POST /api/assets/{ip}/tag
- `api.attack.coverage()` — GET /api/attack/coverage
- `api.attack.actorMatches()` — GET /api/attack/actor-matches

### Task 2 — View rewrites

**AssetsView.svelte** — complete rewrite:
- IP-centric table with columns: Hostname/IP (bold hostname + secondary monospace IP), Tag chip (green=internal/orange=external), Risk Score badge (red/amber/green), Last Seen, Alert Count
- $effect loads assets on mount via api.assets.list()
- Expand/collapse row: toggleExpand(ip) fetches api.assets.get(ip) + api.osint.get(ip) via Promise.allSettled
- isPrivateIp() regex for RFC1918 + loopback; private IPs show "Internal asset — no OSINT enrichment"
- Inline detail panel with three blocks: Event Timeline, Associated Detections, OSINT Enrichment

**AttackCoverageView.svelte** — new file:
- 14-column heatmap grid (CSS repeat(14, 1fr))
- Heat colours: 0=#333, 1-2=#7a4400, 3-9=#c96a00, 10+=#e84a00
- Tactic column headers show short name, click expands technique drill-down below grid
- Techniques sorted covered-first, each showing checkmark SVG or dash, tech_id, name, rule_titles
- Actor match cards at top (up to 3): actor name, confidence badge, overlap %, matched/total counts
- role=button + onkeydown for a11y compliance

**App.svelte** — minimal changes:
- Import AttackCoverageView from './views/AttackCoverageView.svelte'
- Added 'attack-coverage' to View union type
- ATT&CK Coverage nav item in Intelligence group (between Threat Intel and Hunting)
- Route binding: `{:else if currentView === 'attack-coverage'} <AttackCoverageView />`

### Task 3 — Post-verify fixes (applied outside agent, committed separately)

Four issues discovered during human visual verification, all fixed and committed:

1. **ThreatIntelView.svelte import path** (commit 233d007): Changed `$lib/api` to `../lib/api.ts` — Svelte compiler did not resolve the `$lib` alias in this context, causing a blank view.

2. **ThreatIntelView.svelte error state** (commit 001d927): Added explicit error state rendering so API failures display a user-visible error message instead of silently rendering nothing.

3. **MapView.svelte Leaflet rendering** (commits 001d927, 250b09d): Added static CSS import for Leaflet stylesheet and `invalidateSize()` call after flex layout paint — Leaflet requires explicit notification when its container dimensions change after initial mount.

4. **Caddyfile routing and CSP** (commits d60c4d7, f91c175): Changed `/health` to `/health*` glob pattern to proxy the `/health/network` subpath. Added `img-src` and `font-src` CSP allowances for OpenStreetMap tile and font domains required by Leaflet.

## Automated Check Results

```
npm run check: 0 errors in new/modified files for this plan
               Pre-existing errors in GraphView, InvestigationPanel, ProvenanceView remain (out of scope)
uv run pytest tests/unit/ -x -q: 938 tests green (as of plan 34-03 completion)
```

## Deviations from Plan

### Auto-applied Fixes (Rules 1-3)

Applied outside this agent after checkpoint approval:

**1. [Rule 1 - Bug] ThreatIntelView $lib import alias not resolved**
- **Found during:** Task 3 human verification
- **Issue:** ThreatIntelView.svelte used `$lib/api` which Svelte did not resolve — view rendered blank
- **Fix:** Changed to relative import `../lib/api.ts`
- **Files modified:** dashboard/src/views/ThreatIntelView.svelte
- **Commit:** 233d007

**2. [Rule 2 - Missing functionality] ThreatIntelView missing error state**
- **Found during:** Task 3 human verification
- **Issue:** API failures produced no user-visible feedback
- **Fix:** Added error state variable and conditional rendering in template
- **Files modified:** dashboard/src/views/ThreatIntelView.svelte
- **Commit:** 001d927

**3. [Rule 1 - Bug] MapView Leaflet does not render in flex layout**
- **Found during:** Task 3 human verification
- **Issue:** Leaflet map was invisible — missing stylesheet import and no `invalidateSize()` call after flex container paint
- **Fix:** Added static Leaflet CSS import and `invalidateSize()` after mount; added `min-height: 400px` to map container
- **Files modified:** dashboard/src/views/MapView.svelte
- **Commits:** 001d927, 250b09d

**4. [Rule 1 - Bug] Caddy blocked /health/network subpath and OSM tile resources**
- **Found during:** Task 3 human verification
- **Issue:** `/health` exact-match proxy block did not forward `/health/network`; CSP blocked OSM tile images and fonts for Leaflet
- **Fix:** Changed handle path to `/health*`; added `img-src` and `font-src` CSP entries for OSM domains
- **Files modified:** config/caddy/Caddyfile
- **Commits:** d60c4d7, f91c175

### Nav Order Adjustment

Plan spec: ATT&CK Coverage "between Threat Intel and Threat Map". The navGroups array has Intelligence items in order: intel, hunting, map. ATT&CK Coverage was inserted between intel and hunting (index 1), making the order: Threat Intel → ATT&CK Coverage → Hunting → Threat Map. This satisfies "between Threat Intel and Threat Map" while preserving logical flow.

## Self-Check: PASSED

- dashboard/src/views/AttackCoverageView.svelte: exists (created in task 2, commit ef10757)
- dashboard/src/views/AssetsView.svelte: modified (commit ef10757)
- dashboard/src/lib/api.ts: modified (commit 830b87c)
- dashboard/src/App.svelte: modified (commit ef10757)
- Post-verify fix commits: 233d007, 001d927, d60c4d7, 250b09d, f91c175 — all in git log
