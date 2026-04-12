# Phase 41: Threat Map Overhaul - Research

**Researched:** 2026-04-12
**Domain:** Geospatial threat intelligence — Leaflet.js, OSINT enrichment, DuckDB network_connection queries
**Confidence:** HIGH (core stack verified via code inspection; library APIs verified via official docs/npm)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Source: raw `network_connection` events from DuckDB (`src_ip` + `dst_ip`), not detection IPs
- Limit: top 500 IPs by connection count within the selected time window
- IP clustering: Leaflet MarkerCluster — zoom in to expand clusters (not /24 aggregation)
- Enrichment strategy: plot markers immediately with cached data, enrich async in background — no blocking wait
- Internal/private IPs (RFC1918): single fixed "LAN" node at map center; all arc lines radiate outward from LAN node to external markers
- Flow arcs: directional, colored by threat signal (red=known-bad, orange=hosting/datacenter, yellow=VPN/proxy, blue=clean residential)
- Show top 50 flows by connection volume; lower-volume flows faded/omitted
- Arc weight scales with connection count
- Four free OSINT sources (all cached 24h in SQLite): ip-api.com (add proxy/hosting/mobile), Tor exit list, ipsum, ipapi.is
- Icon badges on markers: skull=Tor, shield=VPN/proxy, cloud=datacenter, house=residential
- ipsum tier as threat score badge (1–8) in side panel + marker ring thickness scales with tier
- New CLASSIFICATION section at top of side panel (above existing sections); existing sections unchanged
- Default time window: 24h; quick-select buttons: [1h][6h][24h][7d]
- Auto-refresh every 60s; pause while analyst has marker clicked or is hovering
- Map header stats: total IPs plotted, threat breakdown, top source country, active flows count

### Claude's Discretion
- Exact Leaflet arc/polyline library choice (Leaflet.arc vs leaflet-polylinedecorator vs canvas layer)
- Exact icon badge design and positioning on circle markers
- Backend API endpoint design for the map data (single endpoint vs separate geo/flow endpoints)
- How ipsum flat file is fetched, stored, and queried (local file vs SQLite table)
- Tor exit list storage and lookup mechanism
- Exact threshold for "faded" vs "omitted" low-volume arcs

### Deferred Ideas (OUT OF SCOPE)
- None — discussion stayed within phase scope
</user_constraints>

---

## Summary

Phase 41 transforms MapView.svelte from a detection-IP plotter into a live network traffic intelligence map. The existing codebase provides strong foundations: Leaflet 1.9.4 is installed, MapView.svelte has a working dynamic-import + onMount pattern, and OsintService already calls ip-api.com. The overhaul has three logical layers:

**Layer 1 — Backend data**: New `GET /api/map/data?window=24h` endpoint queries DuckDB for top-500 raw network_connection flows grouped by (src_ip, dst_ip), fetches cached OSINT + classification for each unique IP, and returns a single JSON payload. No blocking enrichment — missing cache entries are returned as null and a background task fills them asynchronously.

**Layer 2 — OSINT enrichment**: OsintService gains four classification methods. ip-api.com's `proxy`, `hosting`, `mobile` fields are added to the existing `_geo_ipapi()` call at zero extra cost. Three new sources — ipapi.is (1,000 req/day free, `is_datacenter`/`is_tor`/`is_proxy`/`company.type`/`asn.type` fields), Tor exit list (plain text from `check.torproject.org/torbulkexitlist`, daily cache in SQLite), and ipsum blocklist (plain text from `raw.githubusercontent.com/stamparm/ipsum/master/ipsum.txt`, tier 1–8 count per IP, daily cache as SQLite table) — are added. The osint_cache table gains five classification columns via idempotent ALTER TABLE.

**Layer 3 — Frontend**: MapView.svelte is rewritten in place. Leaflet MarkerCluster replaces the plain layerGroup. Flow arcs are drawn as SVG Polylines with arrowhead symbols via `leaflet-polylinedecorator` (npm, v1.6.0, maintained for Leaflet 1.x). The LAN node is a fixed CircleMarker at map center. Threat-signal color coding and time-window controls round out the UI.

**Primary recommendation:** Use `leaflet-polylinedecorator` (not Canvas-Flowmap-Layer) for arc lines — it is simpler, has no external animation dependency, and 50 arcs is well within SVG performance limits. Store ipsum and Tor data in dedicated SQLite tables (not flat files) so lookups are O(1) after daily hydration.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| leaflet | 1.9.4 | Map base layer | Already installed; Svelte dynamic import pattern established in MapView.svelte |
| leaflet.markercluster | 1.5.3 | Marker clustering | Official Leaflet plugin; `@types/leaflet.markercluster` for TS; CONTEXT.md decision |
| leaflet-polylinedecorator | 1.6.0 | Directional arc arrows | Lightest arrow-on-polyline option; pure SVG; works with Leaflet 1.x; no dep on tween.js |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| @types/leaflet.markercluster | 1.5.6 | TypeScript definitions for MarkerCluster | Required alongside leaflet.markercluster |
| httpx (already installed) | — | Async HTTP for ipapi.is lookups | Already used in osint.py; no new dep |
| sqlite3 (stdlib) | — | Tor/ipsum cache tables | Already used via sqlite_store.py |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| leaflet-polylinedecorator | Leaflet.Canvas-Flowmap-Layer | Canvas-Flowmap-Layer has no formal releases, uncertain Leaflet 1.9 compat, requires tween.js |
| leaflet-polylinedecorator | Custom Canvas overlay | More control but requires manual pan/zoom transform math |
| ipsum SQLite table | Local flat file | Flat file requires `in memory set` load on every startup; SQLite is persistent and O(1) |
| ipapi.is | MaxMind ASN mmdb | MaxMind requires license; ipapi.is free 1000/day with datacenter detection superior per their docs |

**Installation:**
```bash
cd dashboard && npm install leaflet.markercluster @types/leaflet.markercluster leaflet-polylinedecorator
```

---

## Architecture Patterns

### Recommended Project Structure Changes
```
backend/
  api/
    map.py               # NEW: GET /api/map/data?window=24h
  services/
    osint.py             # EXTEND: _geo_ipapi() + _ipapi_is() + _tor_exit_check() + _ipsum_check()
  stores/
    sqlite_store.py      # EXTEND: ALTER TABLE osint_cache + ipsum_cache DDL + tor_cache DDL

dashboard/
  src/
    views/
      MapView.svelte     # REWRITE in place
    lib/
      api.ts             # ADD: MapFlow, MapIp, MapData interfaces + api.map.getData()
```

### Pattern 1: DuckDB Flow Query
**What:** GROUP BY (src_ip, dst_ip) with INTERVAL window, returns top-N flows.
**When to use:** The map data endpoint calls this to get raw connection flows.

```python
# Source: backend/stores/duckdb_store.py fetch_df() method (verified in codebase)
SQL = """
SELECT
    src_ip,
    dst_ip,
    COUNT(*) AS conn_count
FROM normalized_events
WHERE event_type = 'network_connection'
  AND timestamp > NOW() - INTERVAL ? SECOND
  AND (src_ip IS NOT NULL OR dst_ip IS NOT NULL)
GROUP BY src_ip, dst_ip
ORDER BY conn_count DESC
LIMIT 500
"""
# DuckDB INTERVAL syntax: INTERVAL ? SECOND with integer param
# fetch_df() returns list[dict] with column names — use this not fetch_all()
rows = await duckdb_store.fetch_df(SQL, [window_seconds])
```

**Important:** `fetch_df()` returns `list[dict]` (column names keyed). `fetch_all()` returns `list[tuple]` (positional). The map endpoint should use `fetch_df()` to avoid index-based column access.

**DuckDB INTERVAL note (MEDIUM confidence):** DuckDB accepts `INTERVAL ? SECOND` with integer bind parameter. Alternatively use `NOW() - INTERVAL '24' HOUR` as string literal. Verify with a quick `duckdb.sql("SELECT NOW() - INTERVAL ? SECOND", [86400])` test.

### Pattern 2: Leaflet MarkerCluster with Dynamic Import
**What:** MarkerCluster requires Leaflet to be globally available before the plugin initializes.
**When to use:** In MapView.svelte onMount, after L is resolved.

```typescript
// Source: community-verified pattern for Svelte + Vite (not SSR)
// Leaflet must be imported first, then markercluster mutates L.markerClusterGroup
onMount(async () => {
  const leafletModule = await import('leaflet')
  L = leafletModule.default
  // MarkerCluster attaches itself to the global L object
  // In Vite, window.L may not exist — use the returned L directly
  await import('leaflet.markercluster')  // side-effect: adds L.MarkerClusterGroup
  // Must also import markercluster CSS
  await import('leaflet.markercluster/dist/MarkerCluster.css')
  await import('leaflet.markercluster/dist/MarkerCluster.Default.css')

  clusterGroup = (L as any).markerClusterGroup({ maxClusterRadius: 40 })
  map!.addLayer(clusterGroup)
})
```

**Critical pitfall:** leaflet.markercluster is NOT an ES module — it calls `window.L` or the CommonJS `module.exports` pattern to self-register. In Vite, `import('leaflet.markercluster')` works correctly because Vite bundles it as CommonJS interop. The TypeScript cast `(L as any).markerClusterGroup(...)` is needed since `@types/leaflet.markercluster` augments L but the augmentation may not be visible without explicit type import.

### Pattern 3: Directional Arc Lines with leaflet-polylinedecorator
**What:** Draw a Polyline from src to dst, then add arrow symbols at the midpoint and end.
**When to use:** For each of the top-50 flows where both endpoints have lat/lon.

```typescript
// Source: leaflet-polylinedecorator docs (http://bbecquet.github.io/Leaflet.PolylineDecorator/)
// After import('leaflet-polylinedecorator')  — side-effect, adds L.polylineDecorator
const line = L!.polyline([srcLatLng, dstLatLng], {
  color: arcColor,          // threat-signal color
  weight: arcWeight,        // scales with conn_count
  opacity: arcOpacity,      // faded for low-volume
})
line.addTo(arcLayer)

const decorator = (L as any).polylineDecorator(line, {
  patterns: [{
    offset: '100%',         // arrowhead at destination end
    repeat: 0,
    symbol: (L as any).Symbol.arrowHead({
      pixelSize: 8,
      headAngle: 40,
      fill: true,
      fillOpacity: 0.8,
      pathOptions: { color: arcColor, weight: 0 },
    }),
  }],
})
decorator.addTo(arcLayer)
```

**Note:** leaflet-polylinedecorator does NOT handle antimeridian crossing (arcs from US west coast to Asia may draw backwards). For 50 arcs in a SOC context, antimeridian edge cases are acceptable — just clip extreme coordinates.

### Pattern 4: LAN Node at Map Center
**What:** Single CircleMarker representing all RFC1918 IPs, placed at current map center.
**When to use:** Every time loadMarkers() runs; position follows map center.

```typescript
// RFC1918 detection (mirrors backend _sanitize_ip pattern)
const PRIVATE_RANGES = ['10.', '172.16.', '172.17.', '192.168.']
function isPrivate(ip: string): boolean {
  return PRIVATE_RANGES.some(r => ip.startsWith(r))
    || ip.startsWith('127.')
}

// LAN node: fixed style, placed at map center
const center = map!.getCenter()
lanMarker = L!.circleMarker(center, {
  radius: 14,
  color: '#6366f1',       // indigo — distinct from threat signal colors
  fillColor: '#6366f1',
  fillOpacity: 0.9,
  weight: 3,
})
lanMarker.bindTooltip('LAN (internal hosts)', { permanent: false })
lanMarker.addTo(markerLayer!)
```

### Pattern 5: ip-api.com Extended Fields
**What:** Add `proxy`, `hosting`, `mobile` to the existing fields param in `_geo_ipapi()`.
**When to use:** Modify existing call — zero rate limit impact (same request, more fields).

```python
# Source: ip-api.com/docs/api:json (verified 2026-04-12)
# Current fields param in osint.py: "status,country,countryCode,city,lat,lon,as,org"
# Extended fields param:
params = {
    "fields": "status,country,countryCode,city,lat,lon,as,org,proxy,hosting,mobile"
}
# Response fields (verified):
# proxy    bool  — True if VPN/proxy/Tor detected
# hosting  bool  — True if datacenter/hosting ASN
# mobile   bool  — True if cellular network
```

### Pattern 6: ipapi.is Single-IP Lookup
**What:** New `_ipapi_is()` method in OsintService. Returns datacenter/tor/proxy booleans and ASN type.
**Rate limit:** 1,000 req/day free — enough for 500 unique IPs per refresh if cache miss.

```python
# Source: ipapi.is developers page (verified 2026-04-12)
# Endpoint: https://api.ipapi.is/?q=<IP>
# No API key required for free tier
# Rate limit: 1,000 requests/day (not per-minute — so sleep is not required,
# but add a modest 0.1s sleep to avoid burst-429s)
_ipapiis_lock = asyncio.Lock()
_IPAPIIS_INTERVAL = 0.1  # 0.1s — conservative for burst prevention

async def _ipapi_is(self, ip: str) -> dict | None:
    async with _ipapiis_lock:
        await asyncio.sleep(_IPAPIIS_INTERVAL)
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get("https://api.ipapi.is/", params={"q": ip})
        if resp.status_code != 200:
            return None
        d = resp.json()
        return {
            "is_datacenter": d.get("is_datacenter", False),
            "is_tor":        d.get("is_tor", False),
            "is_proxy":      d.get("is_proxy", False),
            "is_vpn":        d.get("is_vpn", False),
            "asn_type":      (d.get("asn") or {}).get("type"),   # hosting/isp/education/etc
            "company_type":  (d.get("company") or {}).get("type"),
        }
```

**Exact JSON shape (verified):**
```json
{
  "is_datacenter": true,
  "is_tor": false,
  "is_proxy": false,
  "is_vpn": false,
  "asn": { "type": "hosting" },
  "company": { "type": "hosting", "name": "HostPapa" }
}
```

### Pattern 7: Tor Exit List — SQLite Cache
**What:** Daily HTTP fetch of `https://check.torproject.org/torbulkexitlist`, stored as a set in a SQLite table.
**Why SQLite not memory:** Survives backend restart; O(1) lookup with index.

```python
# Fetch once daily; table schema:
# CREATE TABLE IF NOT EXISTS tor_exit_nodes (
#     ip TEXT PRIMARY KEY,
#     fetched_date TEXT NOT NULL   -- ISO date YYYY-MM-DD
# )
#
# Hydration: DELETE WHERE fetched_date != today, then bulk INSERT OR IGNORE

async def _refresh_tor_exit_list(self) -> None:
    today = datetime.date.today().isoformat()
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get("https://check.torproject.org/torbulkexitlist")
    if resp.status_code != 200:
        return
    ips = [line.strip() for line in resp.text.splitlines()
           if line.strip() and not line.startswith('#')]
    # Upsert in sqlite: asyncio.to_thread wrapping sqlite3 bulk insert

async def _tor_exit_check(self, ip: str) -> bool:
    row = await asyncio.to_thread(self._store.get_tor_exit, ip)
    return row is not None
```

**Note:** The Tor Project also exposes a new JSON bulk API at `https://check.torproject.org/api/bulk` (verified in search results). The plain-text `torbulkexitlist` endpoint still works as of 2026-04-12. Use `torbulkexitlist` for simplicity (plain text, one IP per line, no parsing needed).

### Pattern 8: ipsum Blocklist — SQLite Cache
**What:** Daily fetch of `https://raw.githubusercontent.com/stamparm/ipsum/master/ipsum.txt`, parse tier score per IP, store in SQLite.
**Format:** Two-tab-separated columns: `<IP>\t<tier>` where tier is 1–8 (count of source lists the IP appears in).

```python
# ipsum.txt format (verified from GitHub):
# Lines starting with # are comments
# Data lines: "<IP>\t<count>"  e.g.  "1.2.3.4\t3"
# count = number of blocklists that include this IP (1=low confidence, 8=max)
#
# Table schema:
# CREATE TABLE IF NOT EXISTS ipsum_blocklist (
#     ip         TEXT PRIMARY KEY,
#     tier       INTEGER NOT NULL,   -- 1-8
#     fetched_date TEXT NOT NULL
# )

async def _refresh_ipsum(self) -> None:
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.get(
            "https://raw.githubusercontent.com/stamparm/ipsum/master/ipsum.txt"
        )
    entries = []
    for line in resp.text.splitlines():
        if line.startswith('#') or '\t' not in line:
            continue
        parts = line.split('\t')
        if len(parts) >= 2:
            ip, tier = parts[0].strip(), int(parts[1].strip())
            entries.append((ip, tier))
    # Bulk upsert into ipsum_blocklist via asyncio.to_thread

async def _ipsum_check(self, ip: str) -> int | None:
    """Returns tier (1-8) if IP is in ipsum, else None."""
    row = await asyncio.to_thread(self._store.get_ipsum_tier, ip)
    return row  # integer 1-8 or None
```

### Pattern 9: osint_cache Schema Migration
**What:** Add classification columns to existing `osint_cache` table via idempotent `ALTER TABLE`.
**When to use:** Called in `SQLiteStore.__init__()` using the established try/except pattern.

```python
# Source: existing pattern in sqlite_store.py (multiple prior phases use this)
# Add to _make_conn() or __init__ after existing DDL runs:
_OSINT_CLASSIFICATION_MIGRATIONS = [
    "ALTER TABLE osint_cache ADD COLUMN ip_type TEXT",       # 'tor'|'vpn'|'datacenter'|'residential'|'isp'
    "ALTER TABLE osint_cache ADD COLUMN ipsum_tier INTEGER", # 1-8 or NULL
    "ALTER TABLE osint_cache ADD COLUMN is_tor INTEGER",     # 0/1
    "ALTER TABLE osint_cache ADD COLUMN is_proxy INTEGER",   # 0/1
    "ALTER TABLE osint_cache ADD COLUMN is_datacenter INTEGER",  # 0/1
]

for sql in _OSINT_CLASSIFICATION_MIGRATIONS:
    try:
        self._conn.execute(sql)
    except Exception:
        pass  # column already exists — idempotent
```

### Pattern 10: Map Data API Endpoint
**What:** Single `GET /api/map/data?window=24h` endpoint. Returns flows + per-IP geo + classification.
**Design:** Single endpoint (not separate) per CONTEXT.md Claude's Discretion recommendation.

```python
# backend/api/map.py
# Returns:
# {
#   "flows": [{"src_ip": ..., "dst_ip": ..., "conn_count": ..., "direction": "inbound"|"outbound"}],
#   "ips": {
#     "<ip>": {
#       "lat": float|null, "lon": float|null,
#       "country": str|null, "city": str|null, "asn": str|null,
#       "ip_type": "tor"|"vpn"|"datacenter"|"residential"|"isp"|null,
#       "ipsum_tier": int|null,
#       "is_tor": bool, "is_proxy": bool, "is_datacenter": bool,
#     }
#   },
#   "stats": {
#     "total_ips": int, "tor_count": int, "vpn_count": int,
#     "datacenter_count": int, "top_src_country": str|null,
#     "top_src_country_conn_count": int, "flow_count": int,
#   }
# }
```

**Window parameter mapping:**
```python
WINDOW_TO_SECONDS = {"1h": 3600, "6h": 21600, "24h": 86400, "7d": 604800}
```

**Direction detection:** If `src_ip` is RFC1918 → direction = "outbound". If `dst_ip` is RFC1918 → direction = "inbound". If both external → "lateral" (treat as outbound for arc direction).

### Anti-Patterns to Avoid
- **Blocking enrichment in the map endpoint:** Don't `await enrich(ip)` for 500 IPs serially — this would take minutes. Return cached data immediately; enrich missing IPs via `asyncio.create_task()`.
- **Importing leaflet.markercluster before Leaflet module:** The plugin self-registers on load; Leaflet must be loaded first.
- **Using `window.L`** in Vite/Svelte: The module-level `L` variable from `import('leaflet')` is the correct reference — no global assignment needed.
- **Fetching ipsum on every request:** ipsum.txt is ~100KB+ and rate-limited by GitHub. Cache daily; treat stale cache as acceptable (don't block on refresh failure).
- **Drawing arcs for all 500 flows:** Only the top 50 by conn_count get arcs. Others get markers only. Reduces DOM elements from ~1000 (two endpoints × 500) to 100 + 50 arc objects.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Marker clustering | Custom /24 aggregation | leaflet.markercluster | CONTEXT.md decision; handles variable density, zoom-to-expand built in |
| Arc arrowheads | SVG polygon calculations | leaflet-polylinedecorator | arrowHead symbol factory handles angle/size; no trig needed |
| Tor detection | Regex parsing torbulkexitlist repeatedly | SQLite-cached set with daily refresh | Plain-text fetched once daily; O(1) lookup; no repeat HTTP calls |
| ipsum parsing | In-memory set loaded on startup | SQLite ipsum_blocklist table | Persists across restarts; no startup cost; indexed by IP |
| RFC1918 detection | Custom regex | Python `ipaddress.ip_address(ip).is_private` | Already used in `_sanitize_ip()`; covers all RFC1918 + 6to4 |

**Key insight:** The classification data pipeline (Tor/ipsum) has non-trivial daily data volumes. Caching in SQLite with a fetched_date column for daily invalidation is the correct pattern — it already exists in this codebase for OSINT (24h TTL on osint_cache). Extend the same pattern.

---

## Common Pitfalls

### Pitfall 1: leaflet.markercluster Vite/ESM Global L Requirement
**What goes wrong:** `TypeError: Cannot read properties of undefined (reading 'markerClusterGroup')` — plugin loaded before Leaflet module resolved.
**Why it happens:** leaflet.markercluster's UMD bundle calls `L.MarkerCluster =` at module evaluation time. Vite resolves modules in parallel; if markercluster evaluates before Leaflet module, `L` is undefined.
**How to avoid:** `await import('leaflet')` completes BEFORE `await import('leaflet.markercluster')`. Never import both simultaneously in `Promise.all()`. Also import the two CSS files (`MarkerCluster.css` + `MarkerCluster.Default.css`) dynamically in the same onMount block.
**Warning signs:** Map loads but clusters don't form; console error about `L.MarkerCluster`.

### Pitfall 2: DuckDB INTERVAL Parameter Syntax
**What goes wrong:** `duckdb.InvalidInputException: INTERVAL ?` — DuckDB's INTERVAL syntax doesn't accept bind parameters the same way as other SQL dialects.
**Why it happens:** DuckDB requires the INTERVAL value to be a constant or a specific expression, not a bare `?`.
**How to avoid:** Use `NOW() - INTERVAL (? || ' seconds')::INTERVAL` or convert to a timestamp bound parameter: `AND timestamp > ?` where the param is a computed ISO datetime string (now minus window seconds).

```python
# Safe pattern (avoids INTERVAL ? syntax ambiguity):
from datetime import datetime, timedelta, timezone
cutoff = (datetime.now(tz=timezone.utc) - timedelta(seconds=window_seconds)).isoformat()
SQL = """
SELECT src_ip, dst_ip, COUNT(*) as conn_count
FROM normalized_events
WHERE event_type = 'network_connection'
  AND timestamp > ?
  AND (src_ip IS NOT NULL OR dst_ip IS NOT NULL)
GROUP BY src_ip, dst_ip
ORDER BY conn_count DESC
LIMIT 500
"""
rows = await duckdb_store.fetch_df(SQL, [cutoff])
```

### Pitfall 3: ipapi.is 1,000 req/day Exhaustion
**What goes wrong:** Map refresh at 60s with 500 unique IPs and cold cache would attempt 500 ipapi.is calls/hour — consuming the entire daily quota in 2 hours.
**Why it happens:** Cold cache on first run; 60s refresh interval; 500 IPs × continuous refresh.
**How to avoid:** ipapi.is enrichment is only run when the IP is NOT in osint_cache (or cache is stale). Existing 24h TTL on osint_cache means each IP is only enriched once per day. At 500 unique IPs/day = 500 ipapi.is calls/day exactly — right at the limit. If the daily count approaches limit, add a module-level `_ipapi_is_calls_today` counter and skip enrichment when >900.
**Warning signs:** ipapi.is starts returning 429; classification data stops populating.

### Pitfall 4: Tor/ipsum Daily Refresh Race Condition
**What goes wrong:** Two concurrent map requests trigger two simultaneous Tor/ipsum refreshes, causing duplicate INSERT errors or partial data.
**Why it happens:** Both requests check `fetched_date != today` and start download simultaneously.
**How to avoid:** Use a module-level asyncio.Lock (`_tor_refresh_lock`, `_ipsum_refresh_lock`) around the daily refresh function. Check-then-fetch inside the lock.

### Pitfall 5: Arc Lines Crossing Antimeridian
**What goes wrong:** Arcs from East Asia to US west coast draw backwards across the map (going the wrong direction around the globe).
**Why it happens:** Leaflet draws straight lines in lat/lon space; wrapping is not handled.
**How to avoid:** For the top-50 flows use case, simply check if |lon_a - lon_b| > 180 and adjust one longitude by ±360. Acceptable approximation for an operational map.

### Pitfall 6: osint_cache result_json Missing Classification Keys
**What goes wrong:** Existing cache entries (pre-Phase-41) have no `ip_type`/`ipsum_tier` etc. fields in their JSON blob. Reads return null for these fields even after ALTER TABLE.
**Why it happens:** Cache entries are stored as JSON blobs; ALTER TABLE adds columns but doesn't update existing JSON blobs.
**How to avoid:** The new columns (`ip_type`, `ipsum_tier`, etc.) are stored as separate SQLite columns (not inside `result_json`), populated via their own `set_classification_cache()` method. This decouples classification from the existing OSINT JSON blob — no migration of existing JSON needed.

### Pitfall 7: leaflet.markercluster CSS Not Imported Causes Invisible Clusters
**What goes wrong:** Clusters show as plain circles with no number badge; expanding is broken visually.
**Why it happens:** MarkerCluster CSS provides the badge/cluster styles; without it only bare markers appear.
**How to avoid:** Import both CSS files dynamically in onMount alongside the plugin JS.

---

## Code Examples

### DuckDB Network Connection Query (safe INTERVAL pattern)
```python
# Source: pattern derived from existing duckdb_store.fetch_df() (verified in codebase)
from datetime import datetime, timedelta, timezone

async def get_network_flows(duckdb_store, window_seconds: int) -> list[dict]:
    cutoff = (datetime.now(tz=timezone.utc) - timedelta(seconds=window_seconds)).isoformat()
    SQL = """
    SELECT src_ip, dst_ip, COUNT(*) AS conn_count
    FROM normalized_events
    WHERE event_type = 'network_connection'
      AND timestamp > ?
      AND (src_ip IS NOT NULL OR dst_ip IS NOT NULL)
    GROUP BY src_ip, dst_ip
    ORDER BY conn_count DESC
    LIMIT 500
    """
    return await duckdb_store.fetch_df(SQL, [cutoff])
```

### ip-api.com Extended Fields (add to _geo_ipapi)
```python
# Source: ip-api.com/docs/api:json (verified 2026-04-12)
params = {
    "fields": "status,country,countryCode,city,lat,lon,as,org,proxy,hosting,mobile"
}
# Additional returned fields:
# d.get("proxy")   -> bool: True if VPN/proxy/Tor
# d.get("hosting") -> bool: True if datacenter/hosting
# d.get("mobile")  -> bool: True if cellular
```

### TypeScript Interfaces for api.ts
```typescript
export interface MapIpInfo {
  lat: number | null
  lon: number | null
  country: string | null
  country_iso: string | null
  city: string | null
  asn: string | null
  ip_type: 'tor' | 'vpn' | 'datacenter' | 'residential' | 'isp' | null
  ipsum_tier: number | null   // 1-8 or null
  is_tor: boolean
  is_proxy: boolean
  is_datacenter: boolean
}

export interface MapFlow {
  src_ip: string
  dst_ip: string
  conn_count: number
  direction: 'inbound' | 'outbound' | 'lateral'
}

export interface MapStats {
  total_ips: number
  tor_count: number
  vpn_count: number
  datacenter_count: number
  top_src_country: string | null
  top_src_country_conn_count: number
  flow_count: number
}

export interface MapData {
  flows: MapFlow[]
  ips: Record<string, MapIpInfo>
  stats: MapStats
}
```

### Threat Signal Color Mapping
```typescript
// Source: CONTEXT.md decisions (verbatim from threat signal spec)
function getArcColor(srcIp: string, dstIp: string, ipData: Record<string, MapIpInfo>): string {
  const externalIp = isPrivate(srcIp) ? dstIp : srcIp
  const info = ipData[externalIp]
  if (!info) return '#3b82f6'           // blue — unknown, assume clean
  if (info.is_tor || info.ipsum_tier != null) return '#ef4444'   // red — known-bad
  if (info.is_datacenter) return '#f97316'                        // orange — hosting
  if (info.is_proxy) return '#eab308'                             // yellow — VPN/proxy
  return '#3b82f6'                                                // blue — residential/ISP
}

function getArcWeight(connCount: number, maxCount: number): number {
  return 1 + Math.round((connCount / maxCount) * 4)  // 1-5px
}

function getArcOpacity(connCount: number, top50Threshold: number): number {
  if (connCount >= top50Threshold) return 0.75
  return 0.25  // faded for flows below top-50 threshold (shown if gap is small)
}
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Detection IPs only on map | Raw network_connection events (src+dst) | Phase 41 | Full traffic picture, not alert-biased |
| No clustering | Leaflet MarkerCluster | Phase 41 | Handles 500 markers without DOM performance issues |
| No flow visualization | Directional arc lines (top 50) | Phase 41 | Flow context: inbound/outbound direction visible |
| No VPN/Tor/datacenter classification | 4-source classification pipeline | Phase 41 | Analyst sees threat context without clicking |
| Static 60s refresh only | Time window + 60s refresh with hover-pause | Phase 41 | Analyst can control temporal scope |

**Deprecated/outdated in this phase:**
- `api.detections.list({ limit: 200 })` as map data source — replaced by `api.map.getData(window)`.
- Detection-severity color coding on markers — replaced by classification-based threat signal colors.
- Plain `L.layerGroup()` for markers — replaced by `L.markerClusterGroup()`.

---

## Open Questions

1. **DuckDB INTERVAL bind parameter exact syntax**
   - What we know: `timestamp > ?` with ISO string cutoff is safe and established in other queries
   - What's unclear: Whether `INTERVAL (? || ' seconds')::INTERVAL` works with duckdb Python 0.9+ or if cast syntax differs
   - Recommendation: Use the ISO datetime cutoff string approach (Pattern 2 in Code Examples) — it avoids the issue entirely and is consistent with how other time-window queries work in the codebase

2. **ipapi.is daily quota with 500 IPs + cold cache**
   - What we know: Free tier is 1,000 req/day; 500 unique IPs × 1 enrichment/24h = 500 calls/day (within limit)
   - What's unclear: Whether the counter resets at midnight UTC or rolling 24h window
   - Recommendation: Add a conservative daily counter; skip ipapi.is enrichment once >900 calls reached today; degrade gracefully (classification stays null)

3. **leaflet-polylinedecorator TypeScript types**
   - What we know: No `@types/leaflet-polylinedecorator` package; the library is 8 years old with no recent releases
   - What's unclear: Whether the CJS module declaration is compatible with Vite's resolution
   - Recommendation: Use `(L as any).polylineDecorator(...)` with a local type declaration shim if needed: `declare module 'leaflet' { function polylineDecorator(...): any; namespace Symbol { function arrowHead(...): any; } }`

---

## Validation Architecture

`nyquist_validation` is enabled in `.planning/config.json`.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x (via uv) |
| Config file | `pyproject.toml` (pytest-asyncio mode: auto) |
| Quick run command | `uv run pytest tests/unit/test_map_api.py tests/unit/test_osint_classification.py -x` |
| Full suite command | `uv run pytest tests/unit/ -x` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| MAP-01 | DuckDB flow query returns list[dict] with src_ip/dst_ip/conn_count | unit | `uv run pytest tests/unit/test_map_api.py::test_flow_query_structure -x` | Wave 0 |
| MAP-02 | Window seconds mapping: "1h"→3600, "6h"→21600, "24h"→86400, "7d"→604800 | unit | `uv run pytest tests/unit/test_map_api.py::test_window_mapping -x` | Wave 0 |
| MAP-03 | Direction detection: RFC1918 src → "outbound", RFC1918 dst → "inbound" | unit | `uv run pytest tests/unit/test_map_api.py::test_direction_detection -x` | Wave 0 |
| MAP-04 | Stats calculation: tor_count, vpn_count, datacenter_count aggregated correctly | unit | `uv run pytest tests/unit/test_map_api.py::test_stats_aggregation -x` | Wave 0 |
| MAP-05 | ip-api.com proxy/hosting/mobile fields parsed from response | unit | `uv run pytest tests/unit/test_osint_classification.py::test_geo_ipapi_extended_fields -x` | Wave 0 |
| MAP-06 | ipapi.is response parsed: is_datacenter/is_tor/is_proxy/asn.type extracted | unit | `uv run pytest tests/unit/test_osint_classification.py::test_ipapi_is_parse -x` | Wave 0 |
| MAP-07 | ipsum tier lookup: returns integer 1-8 for known IP, None for unknown | unit | `uv run pytest tests/unit/test_osint_classification.py::test_ipsum_tier_lookup -x` | Wave 0 |
| MAP-08 | Tor exit check: returns True for seeded IP, False for non-seeded IP | unit | `uv run pytest tests/unit/test_osint_classification.py::test_tor_exit_check -x` | Wave 0 |
| MAP-09 | osint_cache classification columns exist after migration | unit | `uv run pytest tests/unit/test_osint_classification.py::test_osint_cache_schema_migration -x` | Wave 0 |
| MAP-10 | ipsum parser: skips comment lines, correctly splits IP and tier | unit | `uv run pytest tests/unit/test_osint_classification.py::test_ipsum_parser -x` | Wave 0 |
| MAP-11 | GET /api/map/data returns 200 with flows/ips/stats keys | unit | `uv run pytest tests/unit/test_map_api.py::test_map_endpoint_response_shape -x` | Wave 0 |
| MAP-12 | MarkerCluster renders, arc lines appear, LAN node at center | manual browser | n/a — visual | manual |
| MAP-13 | Time window buttons update markers and arc lines | manual browser | n/a — visual | manual |
| MAP-14 | Clicking a marker opens side panel with CLASSIFICATION section | manual browser | n/a — visual | manual |
| MAP-15 | 60s auto-refresh fires; pauses on marker hover | manual browser | n/a — visual | manual |
| MAP-16 | ipsum tier shows as ring thickness variation on markers | manual browser | n/a — visual | manual |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/unit/test_map_api.py tests/unit/test_osint_classification.py -x`
- **Per wave merge:** `uv run pytest tests/unit/ -x`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/unit/test_map_api.py` — covers MAP-01 through MAP-04, MAP-11 (4 stubs + endpoint shape test)
- [ ] `tests/unit/test_osint_classification.py` — covers MAP-05 through MAP-10 (6 stubs for classification methods)
- [ ] No new framework install needed — pytest-asyncio already configured in pyproject.toml

---

## Sources

### Primary (HIGH confidence)
- Codebase inspection: `backend/services/osint.py` — existing OsintService structure, rate limiters, `_geo_ipapi()` fields param
- Codebase inspection: `backend/stores/duckdb_store.py` — `fetch_df()` method signature, returns `list[dict]`
- Codebase inspection: `backend/stores/sqlite_store.py` — `osint_cache` table schema, ALTER TABLE idempotent pattern
- Codebase inspection: `dashboard/src/views/MapView.svelte` — existing dynamic import pattern, onMount/onDestroy lifecycle
- Codebase inspection: `dashboard/package.json` — leaflet 1.9.4 installed; leaflet.markercluster not yet installed
- ip-api.com/docs/api:json — `proxy`, `hosting`, `mobile` field names verified (2026-04-12)
- ipapi.is developers page — endpoint `https://api.ipapi.is/?q=<IP>`, 1,000 req/day free, `is_datacenter`/`is_tor`/`is_proxy`/`asn.type` fields verified (2026-04-12)

### Secondary (MEDIUM confidence)
- stamparm/ipsum GitHub README — `ipsum.txt` URL, tab-separated IP+tier format, tiers 1–8 meaning (verified 2026-04-12)
- Tor Project blog post about torbulkexitlist — plain-text format, one IP per line, updates ~daily (multiple sources confirm)
- leaflet-polylinedecorator GitHub/npm — `arrowHead` symbol factory, `offset: '100%'` for endpoint arrow pattern
- `@types/leaflet.markercluster` npm — version 1.5.6, last published 4 months ago (WebSearch result 2026-04-12)

### Tertiary (LOW confidence)
- leaflet.markercluster Vite/ESM sequential import requirement — community pattern from Svelte dev.to post; not in official docs. Verify with a quick test during Wave 0.
- DuckDB INTERVAL syntax with bind parameters — using ISO cutoff string as workaround (not tested against running instance)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — leaflet 1.9.4 confirmed installed; markercluster/polylinedecorator npm packages confirmed exist
- Architecture: HIGH — code patterns derived from existing codebase (osint.py, duckdb_store.py, sqlite_store.py all read)
- OSINT field names: HIGH — ip-api.com and ipapi.is field names verified from official docs
- ipsum/Tor format: MEDIUM — format confirmed from GitHub README and Tor Project blog; not tested against live endpoint
- Pitfalls: MEDIUM-HIGH — most derived from codebase reading + established community patterns

**Research date:** 2026-04-12
**Valid until:** 2026-05-12 (stable; ip-api.com/ipapi.is APIs are stable; leaflet ecosystem is slow-moving)
