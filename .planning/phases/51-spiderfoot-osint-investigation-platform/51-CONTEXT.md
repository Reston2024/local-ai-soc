# Phase 51: SpiderFoot OSINT Investigation Platform - Context

**Gathered:** 2026-04-16
**Status:** Ready for planning

<domain>
## Phase Boundary

Analyst-triggered attacker infrastructure mapping via SpiderFoot (Docker, local) and DNSTwist (Python library). Given a seed IP/domain extracted from a detection, SpiderFoot orchestrates 200+ modules to build a full entity relationship map. DNSTwist auto-runs on discovered domains to find typosquatting infrastructure. Results surfaced as a third tab in InvestigationView. SpiderFoot runs on the Windows host via Docker Desktop. No paid API keys required.

This phase does NOT replace Phase 32's reactive per-IP enrichment — it is a deliberate, analyst-triggered deep investigation tool.

</domain>

<decisions>
## Implementation Decisions

### Where Results Live
- Third tab in InvestigationView: **Summary | Agent | OSINT** — follows Phase 45 tab pattern exactly
- Pre-populated seed: `src_ip` from the current detection (not a dropdown, not free text)
- On-demand only — tab shows seed + Run button, analyst controls when to launch
- No auto-start on tab open (consistent with Agent tab behavior)

### Scan Scope & Infrastructure
- Two modes, analyst chooses via radio buttons before hitting Run:
  - **Quick** — passive modules only, ~2 min, no API keys needed
  - **Full** — all available modules, up to 30 min
- SpiderFoot Docker container runs on **Windows host (Docker Desktop)**, NOT the GMKtec
  - Keeps heavy scanning on the RTX 5080 machine; GMKtec already loaded with 17 Malcolm containers
- **30-minute hard ceiling** on all scans: call `/stopscan`, show partial results with yellow warning banner
  - Matches Phase 45 timeout pattern (banner above results: "Scan stopped — 30-min limit reached. Partial results shown.")
- Results cached in SQLite (`osint_findings` table) by scan_id — re-opening same investigation shows prior scan without re-running

### Result Presentation
- **List view by default** — entities grouped by type (IPs, Domains, ASNs, Certificates, Emails, etc.)
- **Graph toggle** available — reuse Cytoscape.js from GraphView for relationship visualization
- **MISP cross-reference inline**: any entity matching a Phase 50 `ioc_cache` entry gets a red ⚠ badge
  - Bulk lookup at scan completion — no extra MISP API calls, query local SQLite only
- **Live SSE streaming** while scan runs — entities appear as found, don't wait for completion
  - Analyst can start reading results during a 30-min full scan
  - Completed entity groups stack as scan progresses

### DNSTwist Integration
- **Auto-runs for every domain SpiderFoot discovers** — zero extra analyst clicks
- Results appear in the domain entity's expanded detail row (collapsible, like Phase 45 step cards)
- Shows **registered domains only**, sorted by fuzzy-match similarity score
  - Unregistered permutations filtered out — not actionable
- DNSTwist runs as async background task after SpiderFoot surfaces each domain (non-blocking)

### Claude's Discretion
- Exact SpiderFoot module list for Quick vs Full modes
- Cytoscape layout algorithm for the graph toggle (dagre or fcose)
- Exact SSE event format for streaming entities
- `osint_findings` table schema details
- SpiderFoot Docker Compose file specifics (port, volume path, restart policy)
- Error state UX if SpiderFoot container is not running (friendly message + link to start it)

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `dashboard/src/views/InvestigationView.svelte` — `activeTab = $state<'summary' | 'agent'>('summary')` — extend to `'summary' | 'agent' | 'osint'`; tab-btn pattern already established
- `backend/api/osint_api.py` — existing `GET /api/osint/{ip}` for Phase 32 reactive enrichment — new `POST /api/osint/investigate` is a sibling route on the same router
- `backend/services/osint.py` — `OsintService` exists; `SpiderFootClient` is a peer service
- `backend/api/investigations.py` — SSE `EventSourceResponse` + async generator pattern is the model for streaming scan results
- `dashboard/src/views/GraphView.svelte` — Cytoscape.js already set up with fcose/dagre; reuse for graph toggle in OSINT tab
- Phase 44 `ioc_cache` SQLite table — bulk MISP cross-reference at scan completion, no new API

### Established Patterns
- On-demand tab with Run button (Phase 45 Agent tab) — OSINT tab follows exactly
- SSE streaming for long-running operations (Phase 45, QueryView)
- Timeout + force-stop with yellow warning banner (Phase 45 `agentError` pattern)
- Result caching in SQLite keyed by identifier (Phase 32 OSINT cache)
- `asyncio.to_thread()` for blocking sync calls (DNSTwist library is synchronous)

### Integration Points
- `InvestigationView.svelte` — add third tab; `detection.src_ip` pre-populates the seed field
- `backend/api/osint_api.py` — add `POST /api/osint/investigate` route
- `backend/stores/sqlite_store.py` — add `osint_findings` table + `osint_scans` table
- `backend/main.py` — no new router needed (osint router already registered)
- `docker-compose.yml` or new `docker-compose.spiderfoot.yml` — SpiderFoot container definition

</code_context>

<specifics>
## Specific Ideas

- Tab order: Summary | Agent | OSINT (OSINT last — it's the deepest investigation tool)
- Quick mode should complete in under 2 minutes to feel responsive
- The red ⚠ MISP badge should be visible in the collapsed entity row without expanding
- DNSTwist results in domain expanded row: "3 lookalike domains registered" collapsed, expand to see list

</specifics>

<deferred>
## Deferred Ideas

- None — discussion stayed within phase scope

</deferred>

---

*Phase: 51-spiderfoot-osint-investigation-platform*
*Context gathered: 2026-04-16*
