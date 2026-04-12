# Phase 41: Threat Map Overhaul - Context

**Gathered:** 2026-04-12
**Status:** Ready for planning

<domain>
## Phase Boundary

Transform the threat map from a basic detection-IP plotter into a live geospatial intelligence surface. Source all raw network_connection events from DuckDB (not just Sigma-fired detection IPs), differentiate inbound vs outbound flows with directional arc lines, and enrich every IP with VPN/proxy/Tor/hosting classification using four free sources. Analysts see the full traffic picture with flow context — not just alerts.

</domain>

<decisions>
## Implementation Decisions

### Data source and volume
- Source: raw network_connection events from DuckDB (src_ip + dst_ip), not detection IPs
- Limit: top 500 IPs by connection count within the selected time window
- IP clustering: Leaflet MarkerCluster — zoom in to expand clusters (not /24 aggregation)
- Enrichment strategy: plot markers immediately with cached data, enrich async in background — no blocking wait

### Internal host handling
- Internal/private IPs (RFC1918) are plotted as a single fixed "LAN" node at map center
- All arc lines from internal hosts radiate outward from the LAN node to external IP markers
- LAN node styled distinctly (different color/shape from external markers)

### Flow arc lines
- Draw directional arc lines src→dst when both endpoints have geo coordinates
- Arc lines colored by threat signal:
  - Red = known-bad (AbuseIPDB/ipsum/blocklist hit)
  - Orange = hosting/datacenter ASN
  - Yellow = VPN/proxy detected
  - Blue = clean residential ISP
- Show top 50 flows by connection volume; lower-volume flows faded/omitted
- Arc weight scales with connection count

### VPN/proxy/Tor/hosting detection
- Four free sources (all results cached 24h in SQLite):
  1. **ip-api.com** — add `proxy,hosting,mobile` to existing fields param (already integrated, zero extra cost)
  2. **Tor exit list** — cache `check.torproject.org/torbulkexitlist` daily, local lookup only
  3. **ipsum blocklist** — stamparm/ipsum daily flat file (30+ blocklists aggregated), local lookup only, tiered 1–8
  4. **ipapi.is** — returns `is_datacenter`, `is_tor`, `is_proxy`, `asn_type`; better datacenter detection than MaxMind
- Display: icon badge overlaid on circle marker (skull=Tor, shield=VPN/proxy, cloud=datacenter, house=residential)
- ipsum tier displayed as threat score badge (1–8) in side panel + marker ring thickness scales with tier

### Side panel enrichment
- New CLASSIFICATION section at top of side panel (above existing geo/abuse sections):
  - IP type badge (Tor / VPN / Datacenter / Residential / ISP)
  - ipsum tier score if flagged (1–8 threat score badge)
  - ASN type from ipapi.is
- Existing sections unchanged (geo, AbuseIPDB, VirusTotal, Shodan, WHOIS)

### Time window and refresh
- Default: last 24h
- Header quick-select buttons: [1h] [6h] [24h] [7d]
- Auto-refresh every 60s; pause refresh while analyst has a marker clicked or is hovering
- Map header shows all four stats:
  - Total IPs plotted (e.g. "342 IPs plotted")
  - Threat breakdown (e.g. "12 Tor · 34 VPN/Proxy · 89 Datacenter")
  - Top source country by connection volume (e.g. "Top source: CN (2,341 connections)")
  - Active flows count (e.g. "50 flows shown")

### Claude's Discretion
- Exact Leaflet arc/polyline library choice (Leaflet.arc vs leaflet-polylinedecorator vs canvas layer)
- Exact icon badge design and positioning on circle markers
- Backend API endpoint design for the map data (single endpoint vs separate geo/flow endpoints)
- How ipsum flat file is fetched, stored, and queried (local file vs SQLite table)
- Tor exit list storage and lookup mechanism
- Exact threshold for "faded" vs "omitted" low-volume arcs

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `dashboard/src/views/MapView.svelte` — full existing map implementation; rewrite in place, preserve Leaflet init pattern, markerLayer, onMount/onDestroy lifecycle
- `backend/services/osint.py` — OsintService with ip-api.com already integrated; extend `_geo_ipapi()` to add proxy/hosting/mobile fields; add new `_ipapi_is()` and `_tor_exit_check()` and `_ipsum_check()` methods
- `backend/api/osint_api.py` — GET /api/osint/{ip} already cached; extend cache schema to include classification fields
- `backend/stores/sqlite_store.py` — osint_cache table already exists; add classification columns (ip_type, ipsum_tier, is_tor, is_proxy, is_datacenter) via idempotent ALTER TABLE

### Established Patterns
- Svelte 5 runes: `$state`, `$derived`, `$effect` — no stores
- Relative imports in Svelte (not `$lib` alias)
- asyncio.to_thread() for all SQLite reads in backend
- Idempotent ALTER TABLE in sqlite_store.py for schema migration (try/except pattern)
- OSINT enrichment cached 24h in SQLite — same cache extended for new classification fields
- Rate limiting per source already in osint.py (ip-api.com: 1.5s, etc.) — add rate limiters for ipapi.is

### Integration Points
- `backend/stores/duckdb_store.py` — new query: `SELECT src_ip, dst_ip, COUNT(*) as conn_count FROM events WHERE event_type='network_connection' AND created_at > now()-INTERVAL ? AND (src_ip IS NOT NULL OR dst_ip IS NOT NULL) GROUP BY src_ip, dst_ip ORDER BY conn_count DESC LIMIT 500`
- `backend/api/` — new endpoint `GET /api/map/data?window=24h` returns top-500 flows + geo + classification for all unique IPs
- `dashboard/src/lib/api.ts` — add MapFlow, MapIp, MapData interfaces + api.map.getData()
- `dashboard/src/App.svelte` — no nav change needed; MapView already in nav

</code_context>

<specifics>
## Specific Ideas

- The LAN node at map center radiating arc lines outward is the key visual — makes the "your network talking to the world" story immediately clear
- Threat signal coloring on arcs (red/orange/yellow/blue) means the analyst can see danger without clicking anything
- ipsum tier as ring thickness is a subtle but effective density signal — thick red ring = multiply-listed known-bad IP

</specifics>

<deferred>
## Deferred Ideas

- None — discussion stayed within phase scope

</deferred>

---

*Phase: 41-threat-map-overhaul*
*Context gathered: 2026-04-12*
