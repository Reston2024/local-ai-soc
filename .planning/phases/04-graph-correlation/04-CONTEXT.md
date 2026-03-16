# Phase 4: Graph + Correlation - Context

**Gathered:** 2026-03-15
**Status:** Ready for planning
**Source:** PRD Express Path (user-provided requirements)

<domain>
## Phase Boundary

Phase 4 delivers **case management and investigation report export** — a full case lifecycle from alert → case → evidence collection → export package. This replaces the original roadmap "queryable graph" scope for this phase; that graph expansion work is deferred.

Deliverables:
1. `backend/src/cases/` module — data model, in-memory store, evidence collector, report builder
2. REST API: `GET/POST /cases`, `GET /cases/{id}`, `POST /cases/{id}/add-alert`, `POST /cases/{id}/export`
3. Automatic case creation from alerts (configurable, off by default)
4. Export package: structured JSON/NDJSON bundle + SHA-256 hashes manifest
5. PDF export: honest scaffold with blocker documented if not feasible
6. Frontend case tab: Cases list + Case detail (Overview / Timeline / Graph / Evidence) + Export button
7. Documentation updates: `docs/decision-log.md`, `docs/manifest.md`, `docs/reproducibility.md`
8. Tests: case creation, add-alert, export payload, IOC extraction, API compatibility

</domain>

<decisions>
## Implementation Decisions

### Backend Module Layout
- Module root: `backend/src/cases/`
- Files: `__init__.py`, `models.py`, `store.py`, `evidence.py`, `report.py`
- No DuckDB or Chroma for Phase 4 — in-memory store (same pattern as events/alerts in routes.py)

### Case Data Model
Locked fields on `Case`:
- `id: str` (UUID)
- `title: str`
- `severity: str` (info / low / medium / high / critical)
- `status: str` (open / investigating / closed)
- `created_at: str` (ISO timestamp)
- `alerts: list[str]` (alert IDs)
- `events: list[str]` (event IDs)
- `graph_nodes: list[dict]`
- `graph_edges: list[dict]`
- `analyst_notes: str` (free text, default "")

### API Endpoints
All endpoints in `backend/src/api/routes.py` (existing pattern — no new router file unless planner judges it cleaner):
- `GET /cases` → list all cases
- `POST /cases` → create case (`{title, severity}` body)
- `GET /cases/{id}` → case detail with full evidence
- `POST /cases/{id}/add-alert` → attach alert + its event to case
- `POST /cases/{id}/export` → generate and return export package as JSON

### Evidence Collector
`backend/src/cases/evidence.py` — `collect_evidence(case) -> dict`:
- Gathers from in-memory `_events`, `_alerts` (via import from routes or passed in)
- Returns: `timeline`, `alerts`, `events`, `graph`, `iocs` (extracted IPs, domains, ports)
- IOC extraction: scan event `src_ip`, `dst_ip`, `query`, `port` fields

### Report Builder
`backend/src/cases/report.py` — `build_report(case, evidence) -> dict`:
Sections (all as dict keys, text or structured):
- `executive_summary`
- `incident_overview`
- `timeline`
- `attack_path` (graph nodes/edges)
- `indicators_of_compromise`
- `evidence_collected`
- `analyst_interpretation` (placeholder string)
- `recommended_response`

### Export Package Structure
`POST /cases/{id}/export` returns JSON with keys:
- `case_summary` (dict)
- `timeline` (list)
- `alerts` (list)
- `events` (list — NDJSON lines as list of dicts)
- `graph` (dict with nodes/edges)
- `evidence_metadata` (dict — collection timestamp, counts)
- `hashes` (dict — SHA-256 of each section's JSON serialization)

### PDF Export
- Attempt `reportlab` or `weasyprint` if already available in venv
- If neither available: return `{"pdf": null, "reason": "PDF export requires reportlab — run: uv add reportlab", "json_export_available": true}` in the export response
- Document the blocker in `docs/reproducibility.md`
- Do NOT add `reportlab` to `pyproject.toml` in Phase 4

### Frontend Case Tab
New Svelte component at `frontend/src/components/cases/`:
- `CaseList.svelte` — table of cases with severity badge + status + export button
- `CaseDetail.svelte` — tabbed view: Overview | Timeline | Graph | Evidence
- Wire into `App.svelte` as a new tab/panel alongside existing graph + timeline
- Export button calls `POST /cases/{id}/export` and triggers browser download of the JSON

### Compatibility
- All existing routes (`/events`, `/alerts`, `/graph`, `/timeline`, `/health`, `/ingest`, `/ingest/syslog`, `/events/stream`, `/search`) must remain unchanged
- All 41 existing tests must continue to pass

### Claude's Discretion
- Whether to use a `CasesRouter` (separate APIRouter) or inline in routes.py
- Svelte component file naming within the cases/ dir
- In-memory store structure (list vs dict keyed by ID)

</decisions>

<specifics>
## Specific Ideas

- Evidence collector should be importable standalone: `from backend.src.cases.evidence import collect_evidence`
- The `hashes.txt` equivalent in the export is `hashes` dict (SHA-256 of JSON bytes per section) — no actual file I/O needed
- IOC extraction regex: IPv4 pattern for IPs, domain pattern (`\w[\w.-]+\.\w{2,}`) for DNS queries
- Frontend: `api.ts` needs `getCases()`, `createCase(title, severity)`, `addAlertToCase(caseId, alertId)`, `exportCase(caseId)` functions
- `POST /cases/{id}/add-alert` body: `{"alert_id": "<uuid>"}` — backend resolves the alert → attaches its event_id too

</specifics>

<deferred>
## Deferred Ideas

- Graph query service (2-hop expansion, path queries) → Phase 5
- Event clustering (Union-Find + temporal window) → Phase 5
- Alert aggregation into investigation threads → Phase 5
- SQLite persistence for cases → Phase 5
- Full PDF export (requires reportlab installation) → Phase 5
- Case sharing / collaboration features → Phase 5+
- Automatic case creation from alerts (configurable trigger) → Phase 5

</deferred>

---

*Phase: 04-graph-correlation*
*Context gathered: 2026-03-15 via PRD Express Path*
