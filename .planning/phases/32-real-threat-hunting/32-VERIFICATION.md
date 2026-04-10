---
phase: 32-real-threat-hunting
verified: 2026-04-09T11:00:00Z
status: passed
score: 11/11 must-haves verified
re_verification: false
human_verification:
  - test: "Leaflet map visual rendering"
    expected: "World map with OpenStreetMap tiles renders in browser, markers appear on the map, clicking a marker opens OSINT side panel"
    why_human: "Cannot verify visual tile rendering, marker interactivity, or map zoom/pan in a headless environment"
  - test: "Hunt query end-to-end with Ollama"
    expected: "POST /api/hunts/query with a natural-language string calls Ollama foundation-sec:8b, returns ranked event rows"
    why_human: "Requires live Ollama instance with foundation-sec:8b model; unit tests mock the Ollama client"
  - test: "OSINT enrichment with real API keys"
    expected: "GET /api/osint/8.8.8.8 returns abuseipdb/virustotal/shodan sections when keys are configured"
    why_human: "External API keys are not set in CI; graceful-skip logic tested in unit tests but live response cannot be verified headlessly"
---

# Phase 32: Real Threat Hunting Verification Report

**Phase Goal:** Implement real threat hunting capabilities — NL→SQL hunt engine, passive OSINT enrichment (AbuseIPDB, VirusTotal, MaxMind, Shodan, WHOIS), HuntingView frontend with presets and OSINT panels, and Leaflet IP threat trace map.
**Verified:** 2026-04-09T11:00:00Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | POST /api/hunts/query accepts NL string, returns ranked event rows | VERIFIED | `backend/api/hunting.py` route calls `HuntEngine.run()`, returns `rows`/`row_count`; `_rank_results()` sorts by severity/ts |
| 2 | SQL validator blocks DDL, multi-statement, non-normalized_events tables, ATTACH, COPY | VERIFIED | `validate_hunt_sql()` in `hunt_engine.py` implements 7-rule whitelist; 9 unit tests pass (17 total pass) |
| 3 | Hunt metadata persists in SQLite `hunts` table | VERIFIED | `sqlite_store.py` contains `hunts` DDL + `save_hunt`/`get_hunt`/`list_hunts` methods; `asyncio.to_thread(self._sqlite.save_hunt, ...)` called in `HuntEngine.run()` |
| 4 | GET /api/hunts/presets returns 6 preset hunt definitions with MITRE tags | VERIFIED | `PRESET_HUNTS` constant has 6 entries (T1059.001, T1071, T1078, T1218, T1021, T1003); `/presets` route defined before `/{hunt_id}/results` to avoid path conflict |
| 5 | GET /api/hunts/{hunt_id}/results retrieves stored results by hunt_id | VERIFIED | Route calls `sqlite.get_hunt(hunt_id)`, returns 404 if None, parses `results_json` |
| 6 | Hunting and OSINT routers registered in main.py with verify_token auth | VERIFIED | Lines 609-621 in `main.py` confirm both routers use `dependencies=[Depends(verify_token)]` |
| 7 | GET /api/osint/{ip} returns WHOIS, AbuseIPDB, MaxMind geo, VirusTotal, Shodan data | VERIFIED | `OsintService.enrich()` runs all 5 sources concurrently via `asyncio.gather`; `osint_api.py` returns `dataclasses.asdict(result)` |
| 8 | OSINT results cached 24h in SQLite; optional API keys cause graceful skip | VERIFIED | `_is_cache_valid()` TTL logic; `_async_none()` coroutine used when key is empty string; 8 unit tests pass |
| 9 | HuntingView.svelte wired — NL input, results table, OSINT panel, presets, history | VERIFIED | `runHunt()` calls `api.hunts.query()`; results table renders `results.rows`; `expandRow()` calls `api.osint.get()`; 6 preset cards call `runHunt(hunt.query)`; `huntHistory` tracks last 10 |
| 10 | MapView.svelte with Leaflet — severity-coloured markers, OSINT panel, 60s refresh | VERIFIED | Dynamic Leaflet import in `onMount`; `circleMarker` with `SEV_COLORS`; `setInterval(loadMarkers, 60_000)` cleared in `onDestroy`; OpenStreetMap attribution present |
| 11 | "Threat Map" accessible from sidebar; MapView registered in App.svelte | VERIFIED | `App.svelte` imports `MapView`, adds `'map'` to View type union, nav item `{ id: 'map', label: 'Threat Map' }`, renders `<MapView />` in view switcher |

**Score:** 11/11 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/services/hunt_engine.py` | NL→SQL engine with HuntEngine, validate_hunt_sql, PRESET_HUNTS | VERIFIED | 280 lines; all exports present; full implementation |
| `backend/api/hunting.py` | FastAPI router with 3 hunt endpoints | VERIFIED | 128 lines; routes POST /query, GET /presets, GET /{id}/results |
| `backend/services/osint.py` | OsintService with 5 lookup methods + rate limiters | VERIFIED | 373 lines; `_vt_lock`, `_abuse_lock`, `_shodan_lock` at module level |
| `backend/api/osint_api.py` | GET /api/osint/{ip} endpoint | VERIFIED | 46 lines; imports OsintService, returns dataclasses.asdict |
| `tests/unit/test_hunt_engine.py` | 9 unit tests for SQL validator and ranking | VERIFIED | 9 tests, all pass |
| `tests/unit/test_osint_service.py` | 8 unit tests for cache TTL and IP sanitization | VERIFIED | 8 tests, all pass |
| `dashboard/src/views/HuntingView.svelte` | Functional hunting UI — no placeholders | VERIFIED | No unconditional `disabled` attrs; no BETA/Coming Soon badge; full query/results/OSINT/presets/history |
| `dashboard/src/lib/api.ts` | Hunt and OSINT typed interfaces + api.hunts/api.osint | VERIFIED | `HuntPreset`, `HuntResult`, `OsintResult` interfaces present; `api.hunts.query()`, `api.osint.get()` at lines 711-727 |
| `dashboard/src/views/MapView.svelte` | Leaflet map with markers, OSINT panel, auto-refresh | VERIFIED | Dynamic import, OSM tiles + attribution, `circleMarker`, `setInterval`, OSINT panel |
| `dashboard/src/App.svelte` | MapView imported, 'map' view type, Threat Map nav item | VERIFIED | Lines 20, 25, 118, 280-281 confirm all integrations |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `backend/api/hunting.py` | `backend/services/hunt_engine.py` | `HuntEngine.run(query, analyst_id)` | WIRED | `HuntEngine` instantiated with stores; `engine.run(body.query, ...)` called |
| `backend/services/hunt_engine.py` | `backend/stores/duckdb_store.py` | `store.fetch_all(validated_sql)` | WIRED | `await self._duckdb.fetch_all(sql)` at line 247 |
| `backend/services/hunt_engine.py` | `backend/stores/sqlite_store.py` | `save_hunt()` | WIRED | `asyncio.to_thread(self._sqlite.save_hunt, ...)` at lines 263-271 |
| `backend/api/osint_api.py` | `backend/services/osint.py` | `OsintService.enrich(ip)` | WIRED | `service.enrich(ip)` called, result serialized |
| `backend/services/osint.py` | `backend/stores/sqlite_store.py` | `osint_cache` read/write | WIRED | `get_osint_cache` at line 139, `set_osint_cache` at lines 200-206 |
| `HuntingView.svelte` hunt button | `api.hunts.query()` | onclick handler calling api.ts | WIRED | `runHunt()` calls `api.hunts.query(q)` at line 66 |
| Result row onclick | `api.osint.get(ip)` | `expandedIp` state → GET /api/osint/{ip} | WIRED | `expandRow()` calls `api.osint.get(ip)` at line 104 |
| `MapView.svelte` | `GET /api/detections` | `api.detections.list({ limit: 200 })` | WIRED | Line 31 — correct namespace (api.detections not api.detect) |
| Marker click | `api.osint.get(ip)` | Leaflet marker onclick → selectIp → OSINT panel | WIRED | `marker.on('click', () => selectIp(ip))` at line 69; `selectIp` calls `api.osint.get(ip)` at line 89 |
| MapView Leaflet | OpenStreetMap tiles | `L.tileLayer('https://{s}.tile.openstreetmap.org/...')` | WIRED | Line 105-108; attribution string present |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| P32-T01 | 32-01 | POST /api/hunts/query + GET endpoints | SATISFIED | `backend/api/hunting.py` implements all 3 routes |
| P32-T02 | 32-01 | NL→SQL hunt query engine | SATISFIED | `HuntEngine.run()` with Ollama generate + `validate_hunt_sql` |
| P32-T03 | 32-01 | SQLite hunt result persistence | SATISFIED | `hunts` table in `sqlite_store.py`; `save_hunt` called on every hunt |
| P32-T04 | 32-03 | Wire HuntingView.svelte — remove disabled, connect to API | SATISFIED | No unconditional disabled; results table renders `results.rows` |
| P32-T05 | 32-03 | Preset hunt cards functional | SATISFIED | 6 preset cards have `onclick={() => runHunt(hunt.query)}` |
| P32-T06 | 32-03 | Hunt history panel | SATISFIED | `huntHistory` state tracks last 10 hunts, clickable to replay |
| P32-T07 | 32-01 | Register hunting router in main.py with auth | SATISFIED | `app.include_router(..., dependencies=[Depends(verify_token)])` at line 611 |
| P32-T08 | 32-02 | OSINT enrichment service — 5 sources, rate-limited, 24h cache | SATISFIED | `OsintService` with `_vt_lock`/`_abuse_lock`/`_shodan_lock`; `osint_cache` SQLite table |
| P32-T09 | 32-02 | GET /api/osint/{ip} endpoint | SATISFIED | `osint_api.py` route; registered in `main.py` with auth |
| P32-T10 | 32-04 | Leaflet world map with severity-coloured IP markers | SATISFIED | `MapView.svelte` with circleMarker, SEV_COLORS, geo null guard |
| P32-T11 | 32-04 | Threat Map sidebar nav, 60s auto-refresh | SATISFIED | Nav item in App.svelte; `setInterval(loadMarkers, 60_000)` in onMount |

### Anti-Patterns Found

None detected. No TODO/FIXME/PLACEHOLDER/stub comments in any phase-32 files. No empty return stubs in backend routes. No unconditional `disabled` attributes on frontend hunt inputs. No `(window as any).L` in MapView.svelte.

### Human Verification Required

#### 1. Leaflet Map Visual Rendering

**Test:** Run `cd dashboard && npm run dev`, navigate to http://localhost:5173, click "Threat Map" in the sidebar
**Expected:** World map renders with OpenStreetMap tiles; zoom/pan works; "© OpenStreetMap contributors" attribution visible at bottom-right; if detections with src_ip exist, severity-coloured circle markers appear; clicking a marker opens OSINT side panel on the right
**Why human:** Cannot verify tile rendering, interactivity, or visual correctness in a headless environment

#### 2. Hunt Query End-to-End with Ollama

**Test:** With Ollama running (foundation-sec:8b model loaded), POST to /api/hunts/query with `{"query": "Show all critical events in the last hour"}`
**Expected:** Returns `{"hunt_id": "...", "sql": "SELECT ...", "rows": [...], "row_count": N}` where SQL is a valid DuckDB SELECT on normalized_events
**Why human:** Requires live Ollama instance; unit tests mock the client; actual SQL generation quality cannot be verified headlessly

#### 3. OSINT Enrichment with Real API Keys

**Test:** Set `ABUSEIPDB_API_KEY`, `VT_API_KEY`, `SHODAN_API_KEY` in environment; GET /api/osint/8.8.8.8
**Expected:** Response includes non-null `abuseipdb`, `virustotal`, `shodan` sections; second request within 24h returns `cached: true`
**Why human:** External API keys not available in verification environment; graceful-skip unit tested but live enrichment requires keys

### Gaps Summary

No gaps. All 11 requirements satisfied. All 10 artifacts exist with substantive implementations. All key links verified as wired. All 10 documented commits confirmed in git log (5887250 through d65dc98). 17 unit tests pass (9 hunt engine + 8 OSINT service). Three items require human verification for visual/integration behavior that cannot be tested headlessly.

---

_Verified: 2026-04-09T11:00:00Z_
_Verifier: Claude (gsd-verifier)_
