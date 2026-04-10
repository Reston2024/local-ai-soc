# Phase 33: Threat Intelligence Platform — Context

**Gathered:** 2026-04-09
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 33 delivers a working Threat Intelligence Platform with three concrete capabilities:

1. **IOC feed ingestion** — 3 free no-key feeds sync hourly into a local SQLite ioc_store
2. **Automatic IOC matching** — every normalized event is checked against ioc_store at ingest;
   new IOCs retroactively search 30 days of historical events
3. **ThreatIntelView console** — replaces the dead stub with a live IOC hit list, compact feed
   health strip, inline row expansion, and risk-scored sorting

**Out of scope (Phase 34):**
- MISP/TAXII 2.1 ingestion (taxii2-client + STIX parsing — separate integration pattern)
- AlienVault OTX, PhishTank, Emerging Threats, Blocklist.de, MISP community (next feed expansion)
- IOC lifecycle management UI (revocation, false-positive marking)
- PassiveDNS pivot, certificate intelligence (crt.sh)

</domain>

<decisions>
## Implementation Decisions

### Feed Selection (Phase 33 only)

3 feeds — all free, no API key required:

| Feed | Source | IOC Types | Sync |
|------|--------|-----------|------|
| **Feodo Tracker** | CSV | C2 IPs (banking trojans, ransomware) | Hourly |
| **CISA KEV** | JSON | Known exploited CVEs | Hourly |
| **ThreatFox** | REST | IPs, domains, hashes + actor tags, malware family | Hourly |

- Feeds sync via background asyncio task (one task per feed, mirrors MalcolmCollector pattern)
- Each feed gets its own SQLite cursor key: `intel.feodo.last_sync`, `intel.cisa_kev.last_sync`, `intel.threatfox.last_sync`
- Sync is upsert: same IOC value+type → update confidence/last_seen, never duplicate

### IOC Matching

- **At-ingest matching:** After each event is normalized, check `src_ip` and `dst_ip` against
  ioc_store (SQLite indexed lookup). Tag matching events: `ioc_matched=True`, `ioc_confidence`,
  `ioc_actor_tag` fields added to NormalizedEvent + DuckDB column migration.
- **Retroactive matching on new IOC:** When a feed sync adds a new IOC entry, run a DuckDB
  scan against the last 30 days of events for that IOC value. Tag any hits retroactively.
  Retroactive scan runs as async background task after each sync completes.
- **No on-demand matching** — matching is fully automatic; analyst never triggers it manually.

### IOC Lifecycle / Confidence Decay

- **Static scoring at ingest:** Score set when IOC is ingested from feed (based on feed source
  weight — Feodo/ThreatFox C2 = 50pts, CISA KEV = 40pts)
- **Confidence decay:** Background daily task decays all active IOC scores by 5 points/week,
  floor at 0. Score never goes negative.
- **IOC status:** `active` (default), `expired` (score hits 0), `revoked` (future — Phase 34)
- Decay job runs at midnight UTC alongside feed sync tasks

### ThreatIntelView Layout

- **Primary content:** IOC hit list — table of events where src_ip/dst_ip/hash matched an
  IOC, sorted by risk score descending (highest risk first, no minimum threshold filter)
- **Compact header strip:** Above the hit list, one row per feed showing:
  feed name | last sync timestamp | IOC count | sync status (ok/stale/error)
  Not the main focus — ambient status only
- **Empty state:** Feed header strip visible + neutral message:
  "No IOC matches yet — feeds syncing hourly." No onboarding prompt.
- **Row click → inline expansion** (same pattern as HuntingView OSINT panel):
  Expanded row shows IOC record fields (feed source, actor_tag, malware_family, TLP,
  first_seen, last_seen, confidence score) + matched event's key fields (timestamp, hostname,
  src_ip, dst_ip, event_type). No navigation away from ThreatIntelView.

### Risk Score Display

- **Location:** ThreatIntelView hit list ONLY — not propagated to EventsView, DetectionsView,
  or HuntingView rows in this phase
- **Visual:** Coloured number badge using existing severity colour scheme:
  - ≥75: red (critical)
  - 50–74: orange (high)
  - 25–49: yellow (medium)
  - <25: grey (low)
- **Default sort:** Score descending — highest risk events appear at top of hit list

### Claude's Discretion

- Exact SQLite DDL for `ioc_store`, `ioc_enrichment_cache`, `ioc_relationships` tables
- Feed worker concurrency model (one asyncio task per feed vs single scheduler loop)
- Retroactive scan batch size and timeout handling for large event sets
- ThreatIntelView Svelte component internal structure (tabs vs single scroll)
- Feodo CSV column mapping (field names change occasionally)

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets

- **`backend/services/osint.py`** — rate limiter pattern (asyncio.Lock + interval sleep) is
  the exact template for feed sync workers. `_abuse_lock`, `_vt_lock` etc. → `_feodo_lock`,
  `_threatfox_lock`. Copy the pattern, not the service.
- **`backend/stores/sqlite_store.py`** — `osint_cache` DDL (lines 281+) shows the table
  creation pattern. `ioc_store` follows same convention. `get_osint_cache`/`set_osint_cache`
  are the read/write pattern for `get_ioc`/`upsert_ioc`.
- **`ingestion/jobs/malcolm_collector.py`** — `system_kv` cursor key pattern
  (`malcolm.alerts.last_timestamp`) → feed sync uses `intel.feodo.last_sync` etc.
- **`dashboard/src/views/HuntingView.svelte`** — inline row expansion (expandRow, expandedIp,
  OSINT side panel) is the UX pattern to replicate for IOC hit expansion in ThreatIntelView.
- **`dashboard/src/views/ThreatIntelView.svelte`** — full stub, completely replace. Keep the
  file, rewrite contents. Feed grid HTML structure is partially reusable for the header strip.
- **`backend/api/events.py`** — DuckDB query pattern for `GET /api/events` — retroactive
  IOC scan uses same `fetch_all()` + WHERE clause approach.

### Established Patterns

- **SQLite write queue:** All SQLite writes go through `asyncio.to_thread(store.method, ...)`.
  ioc_store upserts follow the same pattern — never write SQLite from async context directly.
- **Background tasks:** `asyncio.create_task()` in lifespan → collector task loop with
  `asyncio.sleep(interval)`. MalcolmCollector is the reference implementation.
- **DuckDB migration:** `ALTER TABLE normalized_events ADD COLUMN IF NOT EXISTS {name} {type}`.
  `ioc_matched BOOLEAN DEFAULT FALSE`, `ioc_confidence INTEGER`, `ioc_actor_tag TEXT` added
  to `_ECS_MIGRATION_COLUMNS` list in `duckdb_store.py`.
- **Auth:** All new API endpoints use `dependencies=[Depends(verify_token)]` in router
  registration. ThreatIntelView fetches from authenticated endpoints — `api.ts` sends
  Bearer header on all calls already.

### Integration Points

- **Ingest pipeline:** `ingestion/loader.py` or `malcolm_collector.py` — after normalization,
  call `check_ioc_match(event.src_ip, event.dst_ip)` against SQLite ioc_store before DuckDB
  write. Returns `(matched, confidence, actor_tag)` tuple.
- **DuckDB:** 3 new columns on `normalized_events` via migration. Retroactive scan reads these
  columns to find previously-matched events.
- **New backend service:** `backend/services/intel/` package — `feed_sync.py` (workers),
  `ioc_store.py` (SQLite CRUD), `risk_score.py` (0-100 computation + decay)
- **New API:** `GET /api/intel/ioc-hits` (hit list for ThreatIntelView), `GET /api/intel/feeds`
  (feed health for header strip). Registered in `main.py` with auth.
- **App.svelte:** ThreatIntelView already imported and routed — no nav changes needed.

</code_context>

<specifics>
## Specific Requirements

- **Zero API keys for MVP feeds** — Feodo, CISA KEV, ThreatFox all work without registration.
  This is a hard constraint for Phase 33. Optional-key sources (AbuseIPDB, VirusTotal) are
  already handled in the existing OSINT service.
- **Retroactive = last 30 days** — not all-time. DuckDB scan scoped to
  `WHERE timestamp >= now() - INTERVAL 30 DAYS` to bound query cost.
- **Decay is daily, not real-time** — midnight UTC background job. Score at hit time is
  the score frozen in the ioc_hit record; decay only affects future lookups.
- **ThreatIntelView hit list = events, not IOCs** — the table rows are matched events, not
  the raw IOC records. Analyst sees: timestamp, hostname, src_ip, dst_ip, risk score, actor_tag.
  IOC details are in the expanded row.

</specifics>

<deferred>
## Deferred Ideas

- **MISP/TAXII 2.1 ingestion (Phase 34)** — taxii2-client + STIX 2.1 pattern parsing is a
  separate integration pattern. Ships as its own plan once Phase 33 feeds are stable.
- **Remaining 7 feeds (Phase 34):** AlienVault OTX, URLhaus, Blocklist.de, PhishTank,
  Emerging Threats, Greynoise community, MalwareBazaar
- **IOC revocation / false-positive marking** — analyst marks an IOC as false positive →
  suppressed from future matching. Requires UI controls not in Phase 33 scope.
- **PassiveDNS pivot** — `GET /api/intel/passivedns/{domain}` querying CIRCL.lu. Future.
- **Certificate intelligence** — crt.sh historical cert lookup. Future.
- **Risk score in EventsView/DetectionsView/HuntingView** — deferred. Start with
  ThreatIntelView only. Expand surface area once score quality is validated in production.
- **IOC relationship graph** — from/to entity relationships visualized in GraphView. Future.

</deferred>

---

*Phase: 33-real-threat-intelligence*
*Context gathered: 2026-04-09*
