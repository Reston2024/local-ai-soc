# Phase 35: SOC Completeness — Context

**Gathered:** 2026-04-10
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 35 closes all remaining professional gaps and theatre:

1. **AI auto-triage loop** — Background worker polls untriaged detections every 60s, calls Ollama, stores results with provenance. Analyst sees results in a top panel on DetectionsView. Eliminates the idle-AI problem.
2. **Fix broken flows** — explain.py silent failures → structured errors; playbook runs wired into investigation timeline; EventsView event_type filter chips from real data; Sigma field_map covers DNS/HTTP/TLS Zeek fields.
3. **Overview/Home view** — New landing view with full Malcolm telemetry dashboard (EVE counts + bar charts), system health, latest triage, top rules, and scorecard counts.
4. **BETA badge cleanup** — Remove beta tags from completed Intelligence features (Threat Intel, ATT&CK Coverage, Hunting, Threat Map). Keep beta on Playbooks and Recommendations.
5. **End-to-end smoke test** — Ingest Malcolm sample, verify EVE types in EventsView, hunt results, IOC matching, asset inventory.

**Requirements in scope:**
- P35-T01: Fix explain.py — structured error response when investigation context is empty
- P35-T02: Wire playbook_runs into investigation timeline (real rows from SQLite)
- P35-T03: EventsView event_type filter chips from real NormalizedEvent.event_type values
- P35-T04: Remove BETA badges from Threat Intel, ATT&CK Coverage, Hunting, Threat Map
- P35-T05: New Overview view — Malcolm telemetry summary + system health + triage + stats
- P35-T06: field_map.py covers dns_query, http_user_agent, tls_ja3 for Zeek-matched Sigma rules
- P35-T07: End-to-end smoke test (ingest → EVE chips → hunt → IOC → assets)
- P35-T08: triage_results SQLite table + triaged_at column on detections
- P35-T09: POST /api/triage/run — pulls untriaged detections, builds prompt, calls Ollama, stores result
- P35-T10: Auto-triage background worker (60s poll) + Triage panel in DetectionsView

</domain>

<decisions>
## Implementation Decisions

### AI Triage Panel (T08–T10)

**Location:** Top panel in DetectionsView — collapsible. The worker result surfaces on the same view where detections live (the analyst's primary workspace).

**Content format:** Summary line (severity_summary + detection count + timestamp). Click to expand full result_text. Identical inline-expand pattern to IOC hit rows in ThreatIntelView and OSINT panels in HuntingView.

**In-progress indicator:** Spinner/pulse animation in the panel header while the background worker is mid-Ollama call. When result lands, panel updates automatically (poll via $effect or short interval).

**Manual trigger:** "Run Triage Now" button in the panel header alongside the spinner. Calls POST /api/triage/run directly. Allows analyst to get immediate triage after ingesting new evidence without waiting 60s.

**Panel states:**
- Loading/running: spinner + "Triaging X detections…"
- Result ready: severity_summary line, detection count, model name, timestamp — expand for full text
- No untriaged: "No new detections to triage" with last-run time

### Overview / Home View (T05)

**Structure:** New "Overview" nav item — first item under Monitor group, replacing Detections as the default landing view. App loads to Overview. Analyst sees the full SOC picture first, then navigates to Detections.

**Content blocks (all in last 24h window):**
1. **Telemetry counts + bar chart** — Malcolm EVE type breakdown: Alert, DNS, TLS, HTTP, Connection, Anomaly. Each type as a horizontal bar scaled to the max count. Pure DuckDB `COUNT GROUP BY event_type`.
2. **Scorecard row** — Total events, Total detections, IOC matches, Assets discovered (4 number tiles, 24h window).
3. **System health** — API health dot + network device dots (Router, Firewall, GMKtec) as larger indicators than the sidebar dots. Reuses /health and /health/network calls already in App.svelte.
4. **Latest triage result** — Same triage panel as DetectionsView (or a compact read-only version). If no triage run yet, show "No triage results yet."
5. **Top detected rules** — Top 5 Sigma rule names by detection count in last 24h. Simple table: rule name + count + severity badge.

**Layout:** Two-column grid (left: telemetry + scorecard; right: health + triage + top rules). Standard card components consistent with existing view patterns.

**Auto-refresh:** 60s interval (same as Threat Map). No manual refresh button needed.

### BETA Badge Removal (T04)

**Remove beta tag from:** Threat Intel, ATT&CK Coverage, Hunting, Threat Map.
- These are complete and functional as of Phases 32, 33, 34.

**Keep beta on:** Playbooks, Recommendations.
- Not revisited in recent phases; may have rough edges; beta serves as disclaimer.

**Implementation:** In App.svelte navGroups, remove `beta: true` from the four Intelligence items. Leave Playbooks and Recommendations with `beta: true`.

### Playbook Timeline Rows (T02)

**Format:** `"Playbook: [playbook_name] — [status]"` with a status color chip (green=completed, amber=running, grey=cancelled). Consistent with detection row format in the timeline. No step-level detail — name + status is sufficient for investigation context.

**Data source:** `playbook_runs` SQLite table, queried by `investigation_id`. Return rows where `investigation_id = case_id`. The `timeline.py` merge_and_sort_timeline() function already accepts `playbook_rows` param (was always empty — now populated).

### Broken Flow Fixes (Claude's Discretion on implementation details)

**explain.py (T01):** When `_assemble_investigation()` returns `{}` (detection not found or no events), return `ExplainResponse` with structured error fields: `what_happened="No investigation context found for detection_id: {id}"`, `why_it_matters="Unable to retrieve evidence context."`, `recommended_next_steps="Verify the detection ID exists and events have been ingested."`. No silent `{}` pass-through.

**field_map.py (T06):** Add `dns.query.name` → `dns_query`, `http.user_agent` → `http_user_agent`, `tls.client.ja3` → `tls_ja3` (plus any existing Zeek-relevant Sigma field aliases). Follow existing pattern in field_map.py.

**EventsView chips (T03):** Chips for DNS, HTTP, TLS, Connection, Alert, Anomaly, Auth, File, SMB. Active (not disabled/dashed) for the chips where NormalizedEvent.event_type values exist in DuckDB. Phase 31 added Zeek chips as disabled — enable them all now that the switch is active.

### Claude's Discretion

- Exact Overview layout grid (CSS grid vs flex, breakpoints)
- Polling interval for triage panel refresh (suggest 15s — faster than auto-triage 60s worker but not noisy)
- Triage panel collapse/expand persistence (sessionStorage or in-memory state)
- Whether triage panel shows model name (probably yes for provenance)
- SQL queries for Overview scorecard tiles (24h window boundary)

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets

- **`dashboard/src/views/ThreatIntelView.svelte`** — Inline expand pattern (`expandedId`, `toggleExpand()`, detail row with `colspan`). Triage panel row expansion follows identical pattern.
- **`dashboard/src/views/HuntingView.svelte`** — `expandRow()` / OSINT panel for per-row inline expansion. Same expand/collapse UX.
- **`backend/services/intel/ioc_store.py`** — SQLite CRUD template for `triage_results` table. `IocStore.__init__` DDL pattern.
- **`ingestion/loader.py`** — `asyncio.to_thread()` pattern for SQLite writes. Triage store writes follow same pattern.
- **`backend/api/detect.py`** — DetectionRecord SQLite queries. `triaged_at` column addition follows existing migration pattern.
- **`backend/api/playbooks.py`** — `playbook_runs` table and `PlaybookRun` model already exist. timeline.py needs to query this table by `investigation_id`.
- **`backend/api/timeline.py`** — `playbook_rows` parameter already present (always `[]`). Wire in real query — `playbook_runs WHERE investigation_id = ?`.
- **`backend/api/explain.py`** — `_assemble_investigation()` returns `{}` on miss. Add structured error response before calling `generate_explanation()`.
- **`backend/intelligence/explain_engine.py`** — `build_evidence_context()` and `generate_explanation()` — check behavior when passed `{}`.
- **`dashboard/src/App.svelte`** — `navGroups` array with `beta: true` flags. Remove from 4 items. Add 'overview' view type. Change `currentView` default from `'detections'` to `'overview'`.
- **`detections/field_map.py`** — Sigma field → DuckDB column mapping. Add dns/http/tls entries.

### Established Patterns

- **Background workers:** `asyncio.create_task()` in lifespan loop with `asyncio.sleep(60)` — same as IOC feed workers.
- **SQLite DDL:** `CREATE TABLE IF NOT EXISTS` in store `__init__`. `ALTER TABLE … ADD COLUMN IF NOT EXISTS` for `triaged_at` on detections.
- **API auth:** `dependencies=[Depends(verify_token)]` in `include_router()`.
- **Svelte 5:** `$state()`, `$effect()`, `$derived()` — no writable stores.
- **Triage prompt:** `prompts/triage.build_prompt()` already exists per roadmap spec — researcher should verify signature.

### Integration Points

- **POST /api/triage/run:** New endpoint in `backend/api/triage.py`. Queries `detections WHERE triaged_at IS NULL`, builds prompt, calls `app.state.ollama.generate()`, stores result, sets `triaged_at`. Registered in `main.py`.
- **Auto-triage worker:** `asyncio.create_task(_auto_triage_loop(app))` in lifespan. Calls `POST /api/triage/run` internally (or imports the logic directly to avoid HTTP overhead).
- **Overview view:** New `dashboard/src/views/OverviewView.svelte`. New DuckDB endpoint `GET /api/telemetry/summary` (event type counts last 24h). Top rules from existing `GET /api/detect` or a new analytics query.
- **Triage panel in DetectionsView:** `GET /api/triage/latest` returns most recent `triage_results` row. Panel polls every 15s.

</code_context>

<specifics>
## Specific Requirements

- **Triage panel on DetectionsView is non-blocking** — analyst can still scroll detections while triage runs. Panel is a separate collapsible region at the top, not a modal or overlay.
- **Overview is the new landing view** — `currentView` default changes from `'detections'` to `'overview'` in App.svelte.
- **BETA removal is surgical** — only the 4 Intelligence items. Do not touch Playbooks or Recommendations `beta: true` flags.
- **playbook timeline rows use name + status badge** — no step-level detail. Status chip: green/amber/grey.
- **Overview auto-refreshes every 60s** — same pattern as MapView.
- **Triage panel shows model name** — for provenance (analyst needs to know which model triaged).

</specifics>

<deferred>
## Deferred Ideas

- **Campaign clustering** — background worker grouping DetectionRecords by shared infra + TTP + time window. Future phase.
- **Diamond Model view (CampaignView)** — four-quadrant layout. Requires campaign data. Future phase.
- **UEBA baseline engine** — nightly baselines per user/host + real-time anomaly check. Future phase.
- **Actor profile cards** — rich actor UI with aliases, country, targets, tools. Phase 34 actor matching is score-only.
- **ATT&CK sub-technique drill-down** — T1059.001 level in coverage view. Future.
- **Trend arrows in telemetry** — vs prior 24h comparison. Overview shows counts only (no trends) in Phase 35.

</deferred>

---

*Phase: 35-soc-completeness*
*Context gathered: 2026-04-10*
