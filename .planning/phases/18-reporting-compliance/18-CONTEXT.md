# Phase 18: Reporting & Compliance — Context

**Gathered:** 2026-03-31
**Status:** Ready for planning
**Source:** Roadmap requirements (P18-T01–T04) + external A/93 review (strategic suggestions assessed)

<domain>
## Phase Boundary

Deliver executive and operational reporting capabilities aligned to NIST CSF 2.0, CIS Controls v8, and SOC 2 Type II evidence requirements. Phase 18 closes the last major functional gap: the analyst can investigate, detect, correlate, graph, and execute playbooks — but cannot yet produce auditable reports or trend analytics. This phase makes the platform audit-ready.

No new detection, ingestion, or AI capabilities are introduced — this is reporting and compliance only.

**Not in scope:** SigmaHQ rules sync (future detection phase), multi-agent LLM upgrade (Phase 19+), GraphRAG/NetworkX analytics (Phase 19+), MCP tool-calling (Phase 19+), YARA ingestion (future).

</domain>

<decisions>
## Implementation Decisions

### 1. Report Generation API (P18-T01)

**Locked decisions:**
- `POST /api/reports/investigation/{id}` generates a structured investigation report containing: timeline, entities, detections, AI Copilot chat history, playbook run audit trail
- `POST /api/reports/executive` generates a period summary (date range, alert volume, MTTD/MTTR trends, top tactics, false positive rate)
- Reports stored as JSON records in a new `reports` table in SQLite (graph.sqlite3) — consistent with how playbook runs are stored
- PDF rendering: **WeasyPrint** (pure Python, no cloud, handles HTML→PDF well; fallback: reportlab). WeasyPrint is preferred because it allows HTML/CSS templating which is much easier to maintain than low-level reportlab primitives
- `GET /api/reports` lists generated reports; `GET /api/reports/{id}` fetches a report; `GET /api/reports/{id}/pdf` returns the rendered PDF bytes

### 2. MITRE ATT&CK Coverage Heatmap (P18-T02)

**Locked decisions:**
- `GET /api/analytics/mitre-coverage` returns a matrix keyed by tactic → technique → coverage status
- Coverage status values: `detected` (appears in detections table), `hunted` (appears in hunt results), `playbook_covered` (appears in playbook trigger_conditions), `not_covered`
- A technique can appear in multiple buckets — the response includes a `sources` list per technique
- Svelte `ReportingView.svelte` renders an ATT&CK navigator-style grid: tactic columns, technique cells, colour-coded by coverage (green/blue/yellow/grey)
- The external review specifically validated this as a gap for 2026 SOC standards; implement it fully

### 3. Trend Charts and KPI History (P18-T03)

**Locked decisions:**
- New DuckDB table: `daily_kpi_snapshots(snapshot_date, mttd_minutes, mttr_minutes, mttc_minutes, alert_volume, false_positive_count, investigation_count, detection_count)`
- APScheduler daily job (runs at midnight) computes and upserts the daily snapshot — uses the existing metrics logic from `/api/metrics`
- `GET /api/analytics/trends?metric=mttd&days=30` returns time-series JSON array `[{date, value}]`
- Multiple metrics in one call: `?metric=mttd,mttr,alert_volume`
- ReportingView renders trend lines using **D3.js SVG charts** — D3 is already bundled via the dashboard; no new dependency
- The `APScheduler` job must not block the FastAPI event loop — use `asyncio.to_thread` or a background thread

### 4. Compliance Evidence Export (P18-T04)

**Locked decisions:**
- `GET /api/reports/compliance?framework=nist-csf` generates a structured evidence package mapping each NIST CSF 2.0 subcategory to artefacts in the system
- Evidence sources: detections (IDENTIFY/DETECT), investigations (RESPOND), playbook runs (RESPOND/RECOVER), KPI snapshots (GOVERN/DETECT)
- Export format: ZIP file containing JSON evidence files + `summary.html` (human-readable)
- The `?framework=` parameter is designed for extensibility — implement `nist-csf` as the primary framework
- **TheHive/Cortex format** (suggested by A/93 external review): implement `?framework=thehive` as a secondary option that exports investigations as TheHive Alert/Case JSON records — this is a high-value addition given the review's explicit recommendation and the `?framework=` parameter already accommodates it
- Both framework exports return `application/zip` with `Content-Disposition: attachment`

### 5. ReportingView Svelte Component

**Locked decisions:**
- `ReportingView.svelte` is currently a stub (`ReportsView.svelte`) — replace/rename it
- Four tabs: **Reports** (list + generate investigation/executive), **ATT&CK Coverage** (heatmap), **Trends** (time-series charts), **Compliance Export** (framework selector + download button)
- All four tabs connect to the new API endpoints above
- Use Svelte 5 runes (`$state`, `$derived`, `$effect`) — no writable stores

### Claude's Discretion

- Whether WeasyPrint or reportlab for PDF (WeasyPrint recommended above; Claude can fall back to reportlab if WeasyPrint install is problematic on Windows via uv)
- HTML template design for investigation/executive PDF reports
- Exact D3 chart type (line chart preferred for trends; grouped bar acceptable for alert volume)
- APScheduler version and exact job configuration
- Whether to add a `GET /api/reports/compliance?framework=cis-controls` stub (acceptable if clearly marked as stub)
- Order of plan waves within the phase

</decisions>

<specifics>
## Specific References

**Files known to need changes:**
- `backend/stores/sqlite_store.py` — add `reports` table DDL + CRUD methods
- `backend/api/` — new `reports.py` router (report generation + PDF + compliance export)
- `backend/api/` — new `analytics.py` router (MITRE coverage + trends)
- `backend/stores/duckdb_store.py` — add `daily_kpi_snapshots` table DDL + snapshot write method
- `backend/main.py` — register new routers + APScheduler lifespan setup
- `dashboard/src/views/ReportsView.svelte` — full replacement (was stub)
- `dashboard/src/lib/api.ts` — new typed methods for reports + analytics endpoints

**External review grade (A/93):** validates current direction, no Phase 18 scope changes needed
- "Feature Completeness: A — agentic & multi-agent layer would push to A+" → not Phase 18
- MITRE ATT&CK heatmap explicitly called out as a 2026 gap → P18-T02 directly addresses it
- TheHive/Cortex export recommended → included in P18-T04 as secondary framework

**Libraries:**
- WeasyPrint: `pip install weasyprint` — pure Python HTML→PDF; Windows-compatible
- APScheduler: `pip install apscheduler` — in-process scheduler; already used in some Python SOC stacks
- D3.js: already in `dashboard/node_modules` (bundled with Cytoscape dependencies or installable)

**Compliance framework reference:**
- NIST CSF 2.0 functions: GOVERN, IDENTIFY, PROTECT, DETECT, RESPOND, RECOVER
- CIS Controls v8: 18 control groups — Implementation Group 1 covers minimum viable controls
- SOC 2 Type II: CC6–CC9 (availability, confidentiality, security) most relevant for local SOC tooling

</specifics>

<deferred>
## Deferred Ideas

- SigmaHQ community rules sync (future detection enhancement phase)
- LLM model upgrade to qwen3.5 variants (anytime config change, not a phase)
- Multi-agent crew (investigator → validator → summarizer) — Phase 19+
- GraphRAG / NetworkX centrality analysis — Phase 19+
- MCP tool-calling support — Phase 19+
- YARA file artifact ingestion — future ingestion phase
- CIS Controls v8 compliance export (stub only, full mapping deferred)
- SOC 2 Type II evidence template (requires audit firm guidance to be accurate)
- Velociraptor import parser (fleet telemetry — out of scope per REQUIREMENTS.md)
- Multi-user / role-based access (single analyst scope)

</deferred>

---

*Phase: 18-reporting-compliance*
*Context gathered: 2026-03-31 — roadmap requirements + external A/93 review (suggestions assessed: none change P18 scope; TheHive export incorporated into P18-T04)*
