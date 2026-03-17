# Phase 7: Threat Hunting & Case Management Layer — Context

**Gathered:** 2026-03-17
**Status:** Ready for planning
**Source:** PRD Express Path (inline command args)

<domain>
## Phase Boundary

Phase 7 extends the Phase 6 Causality/Investigation Engine with a full Threat Hunting and Case Management layer. It sits between the causality engine and the dashboard:

```
Telemetry → Ingestion → Detection → Correlation → Causality Engine → Investigation Layer → Graph Model → Dashboard
```

This phase delivers the ability for analysts to move from individual alerts to structured, auditable investigations — creating cases, pivoting across entities, reconstructing timelines, running threat hunting queries, and attaching forensic artifacts.

**In scope:**
- `backend/investigation/` package with 5 modules
- Case data model (SQLite-backed, per project conventions)
- Threat hunting query engine (DuckDB SQL + entity pivot)
- Timeline reconstruction system
- Artifact storage subsystem
- Dashboard investigation panels (Svelte 5 runes)
- API endpoints for all case management operations
- Documentation for investigation workflows

**Out of scope (explicit PRD deferred):** None stated — PRD covers full phase scope.
**Depends on:** Phase 6 causality engine (`backend/causality/`), Phase 4 graph model, existing DuckDB + SQLite stores

</domain>

<decisions>
## Implementation Decisions

### Backend Module Structure (LOCKED)
- New package: `backend/investigation/`
- Required files (exact names locked by PRD):
  - `case_manager.py` — CRUD for investigation cases
  - `timeline_builder.py` — timeline reconstruction from events + alerts
  - `hunt_engine.py` — threat hunting query execution
  - `artifact_store.py` — forensic artifact capture and retrieval
  - `tagging.py` — tag management across cases and entities

### Case Data Model (LOCKED)
Case records must support exactly these fields:
- `case_id` — unique identifier
- `case_status` — investigation state (open / in-progress / closed)
- `related_alerts` — list of alert IDs linked to this case
- `related_entities` — list of entity IDs (host, IP, user, process, domain)
- `timeline_events` — ordered list of timeline entries
- `analyst_notes` — free-text analyst observations
- `tags` — analyst-applied labels
- `artifacts` — collected forensic items

### Timeline Reconstruction (LOCKED)
Each timeline event must include:
- `timestamp` — event time (ISO 8601)
- `event_source` — telemetry source identifier
- `entity_references` — list of entity IDs involved
- `related_alerts` — alerts associated with this timeline event
- `confidence_score` — float 0.0–1.0 for automated entries

### Threat Hunting Queries (LOCKED)
Hunt engine must support at minimum these query patterns:
- Find hosts communicating with a suspicious IP
- Identify processes spawned by PowerShell
- Detect unusual authentication patterns
- Search for indicators of compromise across telemetry sources

### Storage
- Case data: SQLite (project already has SQLiteStore — use it)
- Artifacts: file-system under `data/artifacts/` with metadata in SQLite
- All DuckDB reads via `store.fetch_all()` (asyncio.to_thread wrapper per CLAUDE.md)
- All DuckDB writes via `store.execute_write()` (write queue pattern per CLAUDE.md)

### API Endpoints
New endpoints required (prefix `/api`):
- `POST /api/cases` — create case
- `GET /api/cases` — list cases
- `GET /api/cases/{case_id}` — get case detail
- `PATCH /api/cases/{case_id}` — update case (status, notes, tags)
- `POST /api/cases/{case_id}/artifacts` — attach artifact
- `GET /api/cases/{case_id}/timeline` — get reconstructed timeline
- `POST /api/hunt` — execute threat hunting query
- `GET /api/hunt/templates` — list available hunt templates

### Dashboard Panels (LOCKED requirement)
- Investigation panel: case list, case detail, timeline view
- Hunt panel: query input, results, pivot-to-case action
- Must use Svelte 5 runes (`$state()`, `$derived()`, `$effect()`) — NO stores
- Must call API via `src/lib/api.ts` typed client only

### AI-Assisted Summaries (LOCKED)
- Read-only mode: summaries generated via existing Ollama client
- No analyst edits to AI output — display only
- Triggered per-case via existing `POST /api/investigate/{alert_id}/summary` pattern

### Claude's Discretion
- Specific SQLite schema DDL (column types, indexes)
- Pagination strategy for large case lists
- Artifact file naming convention under `data/artifacts/`
- Hunt query syntax (SQL vs structured params)
- Component layout within dashboard panels
- Error handling granularity for artifact upload failures

</decisions>

<specifics>
## Specific Ideas

### Integration Points
- `hunt_engine.py` queries DuckDB `normalized_events` table (existing schema)
- `timeline_builder.py` aggregates from DuckDB events + causality engine output
- `case_manager.py` uses SQLiteStore (already in `app.state.stores.sqlite`)
- `artifact_store.py` stores files under `data/artifacts/{case_id}/`

### Example Hunt Queries (DuckDB SQL patterns)
```sql
-- Hosts communicating with suspicious IP
SELECT DISTINCT hostname FROM normalized_events WHERE dst_ip = ?

-- Processes spawned by PowerShell
SELECT * FROM normalized_events
WHERE parent_process_name ILIKE '%powershell%'

-- Unusual auth patterns
SELECT hostname, username, COUNT(*) as cnt FROM normalized_events
WHERE event_type = 'authentication' GROUP BY hostname, username HAVING cnt > 10
```

### Existing Infrastructure to Reuse
- `backend/causality/entity_resolver.py` — entity normalization
- `backend/causality/scoring.py` — confidence scoring
- `backend/stores/sqlite_store.py` — case persistence
- `backend/stores/duckdb_store.py` — hunt queries
- `prompts/investigation_summary.py` — AI summary template

</specifics>

<deferred>
## Deferred Ideas

None — PRD covers phase scope.

Future considerations (not this phase):
- Multi-analyst collaboration / case assignment
- External SIEM export (Splunk, QRadar format)
- Automated case creation from detection triggers
- Case severity scoring ML model

</deferred>

---

*Phase: 07-threat-hunting-case-management*
*Context gathered: 2026-03-17 via PRD Express Path*
