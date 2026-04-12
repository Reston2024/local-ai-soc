---
phase: 41-threat-map-overhaul
plan: "04"
subsystem: frontend
tags: [svelte, leaflet, markercluster, threat-map, visualization]
dependency_graph:
  requires: [41-02, 41-03]
  provides: [MapView-rewrite, threat-map-UI]
  affects: [dashboard/src/views/MapView.svelte]
tech_stack:
  added: [leaflet.markercluster@1.5.3, "@types/leaflet.markercluster@1.5.6", leaflet-polylinedecorator@1.6.0]
  patterns: [sequential-await-imports, svelte5-runes, markercluster, polylinedecorator-arrowheads, LAN-node-pattern]
key_files:
  created: []
  modified:
    - dashboard/src/views/MapView.svelte
    - dashboard/package.json
    - dashboard/package-lock.json
decisions:
  - "Sequential await imports: Leaflet first, then markercluster, then polylinedecorator — L must resolve before plugins attach to it"
  - "LAN node uses L.circleMarker (not L.marker) — added to clusterGroup so it participates in cluster bounds"
  - "arcLayer is a plain L.layerGroup (not clusterGroup) — arcs must not be clustered, only external IP markers cluster"
  - "side-panel positioned absolute over map canvas (not flex sibling) — avoids map canvas resize/invalidateSize jitter"
  - "refreshPaused on mouseover; cleared on mouseout only when selectedIp !== ip — prevents flicker when moving cursor between marker and panel"
  - "antimeridian guard adjusts dLon by ±360 when |sLon - dLon| > 180 — prevents lines wrapping wrong way across 180th meridian"
  - "topFlows limited to 50 by conn_count sort — prevents rendering thousands of arcs/decorators on busy sensors"
metrics:
  duration_minutes: 6
  completed_date: "2026-04-12T13:17:46Z"
  tasks_completed: 2
  tasks_total: 2
  files_changed: 3
  unit_tests: 1044
---

# Phase 41 Plan 04: MapView Threat-Map Rewrite Summary

**One-liner:** Full MapView.svelte rewrite with LeafletMarkerCluster, LAN-node-to-world arc lines via leaflet-polylinedecorator, threat signal coloring, classification side panel, time window controls, and auto-refresh with hover pause.

## What Was Built

### Task 1: Install npm packages (commit 62fc8cd)
Installed three Leaflet extension packages into `dashboard/package.json`:
- `leaflet.markercluster@1.5.3` — cluster external IP markers at low zoom
- `@types/leaflet.markercluster@1.5.6` — TypeScript types for the above
- `leaflet-polylinedecorator@1.6.0` — adds arrowhead symbols to polylines

### Task 2: Rewrite MapView.svelte (commit 4b91724)
Replaced the previous Phase 32 implementation (detection-dot-plot using OSINT API) with a purpose-built threat intelligence map surface. 581 lines.

**Architecture:**
- `clusterGroup` (L.markerClusterGroup) holds the LAN node and all external IP circleMarkers
- `arcLayer` (L.layerGroup) holds polylines + polylineDecorator arrowheads for top-50 flows
- State is Svelte 5 runes (`$state`) — no writable() stores

**Visual elements:**
- LAN node: indigo circleMarker (radius 14, `#6366f1`) at map center, tooltip "LAN (internal hosts)"
- External IPs: circleMarkers colored by threat signal (red=tor/ipsum, orange=datacenter, yellow=vpn/proxy, blue=clean); ring weight scales with ipsum_tier (1→2, 8→6)
- Arc lines: L.polyline connecting [LAN coords] ↔ [external IP coords], weight 1-5px proportional to conn_count
- Arrowheads: L.polylineDecorator at 100% offset (destination end), pixelSize 8, headAngle 40

**Header stats bar:** total_ips, tor_count, vpn_count, datacenter_count, top_src_country, flow_count — live from MapStats.

**Time window buttons:** [1h][6h][24h][7d] — clicking sets selectedWindow and calls loadMapData(), active button highlighted with indigo border.

**Side panel (320px, absolute positioned over map right edge):**
- CLASSIFICATION section first: ip_type badge (color-coded) + ipsum tier badge, then Tor/VPN/DC flags
- GEO section: country, city, lat/lon
- ASN section: ASN string

**Auto-refresh:** 60s setInterval; pauses when `refreshPaused` is true (set on marker click or mouseover; cleared on mouseout when no selectedIp, or on panel close button).

## Checkpoint

**Task 3: human-verify** — Auto-approved (auto_advance=true). Visual verification to be confirmed at next analyst session.

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check: PASSED

| Item | Status |
|------|--------|
| dashboard/src/views/MapView.svelte | FOUND |
| dashboard/package.json | FOUND |
| 41-04-SUMMARY.md | FOUND |
| commit 62fc8cd (npm packages) | FOUND |
| commit 4b91724 (MapView rewrite) | FOUND |
| TypeScript: 0 errors | PASSED |
| Unit tests: 1044 passed | PASSED |
