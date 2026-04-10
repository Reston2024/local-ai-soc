# Phase 34: MITRE ATT&CK + Actor Intelligence + Asset Inventory — Context

**Gathered:** 2026-04-10
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 34 delivers three concrete capabilities that turn detection data into understanding:

1. **Asset inventory** — every normalized event upserts src_ip/dst_ip into an asset table. AssetsView shows hostname, risk score, last seen, and alert count. Click → detail panel with event timeline, associated detections, and OSINT enrichment.
2. **ATT&CK tagging + actor matching** — DetectionRecords are tagged with ATT&CK technique IDs from Sigma rule tags. A TTP-overlap scorer surfaces top-3 candidate threat actor groups with confidence %.
3. **ATT&CK coverage heatmap** — dedicated "ATT&CK Coverage" view under Intelligence. Simplified 14-column grid (one tactic per column), heat-scaled by coverage count. Click a tactic column to expand an inline technique list.

**Requirements in scope (Phase 34):**
- P34-T01: Download and parse MITRE ATT&CK Enterprise JSON → SQLite (attack_techniques, attack_groups, attack_software)
- P34-T02: Auto-tag DetectionRecords with ATT&CK technique IDs on detection fire (from Sigma rule tags)
- P34-T03: Actor profile matching — score each ATT&CK group by TTP overlap %, surface top-3 candidates with confidence
- P34-T04: ATT&CK coverage heatmap — GET /api/attack/coverage + ATT&CK Coverage view
- P34-T07: Asset store upsert pipeline — on every normalized event upsert src_ip/dst_ip as assets
- P34-T08: Assets API — GET /api/assets, GET /api/assets/{id}, POST /api/assets/{id}/tag
- P34-T09: AssetsView.svelte — live asset table with detail panel

**Out of scope (Phase 35):**
- P34-T05: Campaign clustering (shared infra + TTP + time window grouping)
- P34-T06: Diamond Model view / CampaignView.svelte
- P34-T10: UEBA baseline engine (nightly behavioral baselines, real-time anomaly detection)
- P34-T11: CampaignView nav item + actor profile cards (actor matching ships Phase 34 as scoring only)

</domain>

<decisions>
## Implementation Decisions

### Asset Table Content (AssetsView rows)

Each row in the asset table shows exactly four fields:
- **hostname** — from NormalizedEvent.hostname (may be IP string if no hostname resolved)
- **risk score** — computed from alert count + severity distribution + IOC match status; same 0–100 scale as IOC confidence
- **last seen** — timestamp of most recent event for this asset
- **alert count** — count of DetectionRecords with src_ip or dst_ip matching this asset

No additional columns (open ports, OS, services) in Phase 34. Row click opens the inline detail panel — no navigation away.

### Asset Detail Panel

Inline expansion (same pattern as HuntingView OSINT panel and ThreatIntelView IOC expansion). Three content blocks:
1. **Event timeline** — last 10 events for this asset (timestamp, event_type, severity), scrollable
2. **Associated detections** — DetectionRecords referencing this asset's IPs (rule_name, severity, timestamp)
3. **OSINT enrichment** — call existing GET /api/osint/{ip} for the asset's primary IP; reuse the HuntingView OSINT panel component or its display pattern

No Diamond Model panel in the detail view (Phase 35, requires campaign data).

### Internal / External Asset Classification

Tagging logic applied at asset upsert time:
- **RFC1918 + loopback** → tag `"internal"` (192.168.x.x, 10.x.x.x, 172.16-31.x.x, 127.x.x.x)
- **All other IPs** → tag `"external"` — also flagged as IOC candidate if `ioc_matched=True` exists for this asset in the last 30 days
- Tag stored in asset record; displayed as a small chip next to hostname in the table row

Classification uses Python `ipaddress` module (already imported in backend/services/osint.py — reuse the `_sanitize_ip` private IP check pattern).

### Actor Matching Approach

Actor profile matching runs on demand (not at ingest — it's too slow for hot path):
- Input: set of ATT&CK technique IDs from all DetectionRecords in the last 30 days
- For each ATT&CK group in attack_groups table: compute `overlap = |detected_techniques ∩ group_techniques| / |group_techniques|`
- Return top-3 groups by overlap %, with confidence label: ≥60% = High, 30–59% = Medium, <30% = Low
- Endpoint: GET /api/attack/actor-matches → called by AssetsView or a sidebar widget (Claude's discretion on placement)
- ATT&CK group data comes from the STIX Enterprise JSON download (P34-T01). Group → techniques mapping via `uses` relationships in STIX JSON.

Actor matching output is advisory only — no automatic tagging of events or assets. Analyst sees: actor name, aliases, country, confidence %, TTP overlap count.

### ATT&CK Heatmap Format

**Layout:** Simplified grid — 14 tactic columns (one per ATT&CK Enterprise tactic in order: Reconnaissance → Impact), technique counts per column.

**Each cell shows:**
- Tactic short name (e.g. "Exec", "Persist", "PrivEsc")
- Count badge: `3 / 67` (covered rules / total techniques in tactic)

**Click behaviour:** Tactic column expands inline below the header row. Expanded list shows each technique name + covered (checkmark) or not covered (dash). No navigation away from ATT&CK Coverage view.

**Heat scale (colour):**
- 0 rules → dark grey `#333`
- 1–2 rules → dim orange `#7a4400`
- 3–9 rules → medium orange `#c96a00`
- 10+ rules → bright red-orange `#e84a00`
Mirrors MITRE Navigator colour scheme. Uses existing severity colour variables where possible.

**Location:** Own view — new sidebar nav entry "ATT&CK Coverage" under the Intelligence group (below Threat Intel, above Threat Map). New file: `dashboard/src/views/AttackCoverageView.svelte`.

### UEBA

Fully deferred to Phase 35. No UEBA logic, no entity_baselines table, no anomaly detection in Phase 34. Clean boundary.

### Claude's Discretion

- Exact SQLite DDL for `assets`, `attack_techniques`, `attack_groups`, `attack_group_techniques` tables
- Whether actor matching endpoint is called from AssetsView header or a dedicated sidebar widget
- STIX JSON download strategy (bundle at startup vs scheduled refresh — prefer startup download with 24h SQLite cache)
- Asset risk score formula (combine alert count + IOC match + detection severity; exact weights)
- ATT&CK Coverage view placement of the expanded technique list (below column header vs slide-in panel)

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets

- **`backend/services/intel/ioc_store.py`** — IocStore SQLite CRUD pattern is the exact template for AssetStore. `upsert_ioc()` → `upsert_asset()`. Same `asyncio.to_thread()` write pattern.
- **`backend/services/osint.py`** — `_sanitize_ip()` private IP detection (RFC1918 + loopback check) used for internal/external asset classification. Import directly — don't rewrite.
- **`dashboard/src/views/HuntingView.svelte`** — `expandRow()` / `expandedIp` inline expansion pattern. AssetsView detail panel and ATT&CK tactic drill-down use same approach.
- **`dashboard/src/views/ThreatIntelView.svelte`** — `IocHit` row expansion with risk badge and inline card. AssetsView rows follow identical expand/collapse UX.
- **`backend/api/intel.py`** — `Depends(verify_token)` auth pattern for new API routers.
- **`backend/stores/sqlite_store.py`** — `osint_cache` and `ioc_store` DDL patterns. New tables (`assets`, `attack_techniques`, `attack_groups`) follow same `CREATE TABLE IF NOT EXISTS` convention.
- **`ingestion/loader.py`** — `_apply_ioc_matching()` called synchronously inside `asyncio.to_thread()` after normalize. Asset upsert follows same pattern — call `asset_store.upsert_asset(event)` in same sync block.
- **`backend/main.py`** — lifespan task registration (`asyncio.ensure_future()`), store instantiation on `app.state`, router registration with `include_router(..., prefix="/api", dependencies=[Depends(verify_token)])`.

### Established Patterns

- **SQLite writes:** All through `asyncio.to_thread(store.method, ...)` — never direct await
- **Background tasks:** `asyncio.create_task()` or `asyncio.ensure_future()` in lifespan; loop with `asyncio.sleep(interval)`
- **DuckDB migration:** `ALTER TABLE normalized_events ADD COLUMN IF NOT EXISTS {name} {type}` in `_ECS_MIGRATION_COLUMNS` list in `duckdb_store.py`
- **Auth:** All new API routers use `dependencies=[Depends(verify_token)]` in `include_router()` call
- **Svelte 5:** `$state()`, `$derived()`, `$effect()` — not stores; typed with generics e.g. `$state<Asset[] | null>(null)`
- **api.ts typed client:** New view methods follow pattern in `api.intel.iocHits()` — typed interface + fetch with Bearer header

### Integration Points

- **Asset upsert in loader.py:** After `_apply_ioc_matching()`, call `asset_store.upsert_asset(src_ip=event.src_ip, dst_ip=event.dst_ip, hostname=event.hostname, ...)`. Asset upsert is sync (runs inside `asyncio.to_thread()` block already).
- **ATT&CK tagging in detections:** `detections/matcher.py` fires `DetectionRecord` — on each match, look up Sigma rule tags for `attack.tXXXX` patterns, write technique IDs to `detection_techniques` join table in SQLite.
- **STIX JSON source:** MITRE ATT&CK Enterprise STIX 2.1 bundle (single JSON file, ~15MB). Fetch on startup from GitHub raw content URL (github.com/mitre/cti). Cache in SQLite — refresh only if >24h stale.
- **Coverage heatmap data:** GET /api/attack/coverage reads `attack_techniques` (all techniques + tactic) JOIN `detection_techniques` (matched rule count) and returns coverage per tactic. No DuckDB needed — pure SQLite query.
- **New API routers:** `backend/api/assets.py`, `backend/api/attack.py` registered in `main.py`.
- **New Svelte views:** `AssetsView.svelte`, `AttackCoverageView.svelte` added to `App.svelte` routing + sidebar nav.

</code_context>

<specifics>
## Specific Requirements

- **Asset table is IP-centric, not hostname-centric** — primary key is IP address. Hostname is a display label that may be null. Multiple hostnames for one IP → keep most recent.
- **ATT&CK STIX download is startup-time only** — no hot-reload. If SQLite already has techniques (>0 rows), skip download. Force-refresh via `scripts/` CLI if needed.
- **Actor matching is NOT at-ingest** — too expensive. On-demand endpoint only. No background worker for actor matching in Phase 34.
- **Coverage heatmap uses Sigma rule ATT&CK tags only** — not fired detections. A rule is "covered" if it exists in `detections/rules/` and its tags include `attack.tXXXX`. Coverage ≠ detections triggered.
- **Internal/external tag is computed at upsert, not query time** — stored in asset record.
- **No open_ports, OS fingerprinting, or service discovery** — Phase 34 asset data comes exclusively from normalized events (src_ip, dst_ip, hostname fields). No active scanning.

</specifics>

<deferred>
## Deferred Ideas

- **Campaign clustering (Phase 35)** — background worker groups DetectionRecords into campaigns by shared infra + TTP + time window. Requires campaign table + campaign_events join.
- **Diamond Model view (Phase 35)** — CampaignView.svelte four-quadrant layout populated from campaign + ATT&CK + TI data.
- **UEBA baseline engine (Phase 35)** — nightly asyncio task computes behavioral baselines per user/host. Real-time anomaly check on each new event creates DetectionRecord on trigger. SQLite entity_baselines table.
- **Actor profile cards (Phase 35)** — full CampaignView nav item with actor cards showing aliases, country, targets, tools, TTPs, MITRE page link. Phase 34 actor matching is score-only, no rich profile UI.
- **ATT&CK sub-technique drill-down** — expanded tactic panel shows sub-techniques (T1059.001 etc). Phase 34 shows technique level only (T1059).
- **Coverage trend over time** — chart showing coverage % per tactic across weeks. Future.
- **Asset timeline beyond 10 events** — pagination or infinite scroll on asset detail panel event timeline. Phase 34 shows last 10 only.
- **Open port / service inventory** — requires active scanning (nmap integration) or passive Zeek service detection (Phase 36). Not from normalized events alone.

</deferred>

---

*Phase: 34-mitre-attack-actor-asset*
*Context gathered: 2026-04-10*
