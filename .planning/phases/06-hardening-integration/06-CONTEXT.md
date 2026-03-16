# Phase 6: Threat Causality & Investigation Engine — Context

**Gathered:** 2026-03-16
**Status:** Ready for planning
**Source:** PRD Express Path (inline args)

<domain>
## Phase Boundary

This phase implements a Threat Causality Engine that reconstructs attack chains from correlated
security events and exposes them through the SOC dashboard. Analysts must be able to visually
trace threats end-to-end by resolving entities, linking related events, mapping detections to
MITRE ATT&CK, and generating investigation graphs that support interactive exploration.

Pipeline position: **Correlation → Causality Engine → Graph Model → Dashboard**

Full pipeline:
```
Telemetry → Ingestion → Detection → Correlation → Causality Engine → Graph Model → Dashboard
```

</domain>

<decisions>
## Implementation Decisions

### Entity Normalization (Locked)
- Normalize the following entity types: host, user, process, IP, domain, file, event, alert
- Each entity type must be resolved to a canonical ID form
- Entity resolution happens before causal chain construction

### Required Backend Modules (Locked)
- `backend/causality/engine.py` — main causality engine orchestrator
- `backend/causality/entity_resolver.py` — entity normalization and resolution
- `backend/causality/attack_chain_builder.py` — causal relationship construction
- `backend/causality/mitre_mapper.py` — MITRE ATT&CK tactic/technique mapping
- `backend/causality/scoring.py` — threat scoring for chains and entities

### Required API Endpoints (Locked)
- `GET /api/graph/{alert_id}` — graph data for a specific alert
- `GET /api/entity/{entity_id}` — entity details and related events
- `GET /api/attack_chain/{alert_id}` — full attack chain reconstruction
- `POST /api/query` — flexible investigation query endpoint

### Dashboard Capabilities (Locked)
- Render attack graphs with interactive node expansion
- Attack-path highlighting in the visualization
- Allow pivoting from alerts → entities → full attack chains
- Support timeline filtering
- Support graph traversal interactions

### AI Investigation Summaries (Locked)
- Generate AI-assisted investigation summaries
- Read-only mode (no modification of underlying data)
- Summaries must be accessible from investigation views

### Completion Criteria (Locked)
- Alerts generate attack graphs
- Events link into causal chains
- MITRE mappings appear in investigations
- Analysts can visually trace an attack path from first event to final detection

### Claude's Discretion
- Graph schema specifics (node/edge field names beyond what Phase 4 established)
- Internal engine data structures (intermediate representations)
- Scoring algorithm weights and thresholds
- Specific Svelte component names and file structure in dashboard
- Database storage strategy for causality graph (DuckDB vs in-memory)
- Test file organization and fixture data
- Documentation format (docstrings vs separate .md files)
- API response schemas (beyond the required endpoints)
- Import/module organization within backend/causality/

</decisions>

<specifics>
## Specific Ideas

### Pipeline Architecture
The causality engine sits between correlation and graph layers. It must consume correlated event
clusters and produce investigation-ready graph structures. The engine should be callable both
on-demand (per alert) and in bulk (for all recent alerts).

### MITRE ATT&CK Integration
- mitre_mapper.py must map detection fields to ATT&CK techniques
- Tactics: Initial Access, Execution, Persistence, Privilege Escalation, Defense Evasion,
  Credential Access, Discovery, Lateral Movement, Collection, Exfiltration, Impact
- Must handle cases where technique is unknown (graceful degradation)

### Attack Chain Reconstruction
- attack_chain_builder.py must follow event→entity→event relationships
- Temporal ordering is required (earliest event first)
- Must handle multi-hop chains (event A causes event B causes event C)
- Must detect and handle cycles/loops in causal graphs

### Investigation Query API
- POST /api/query must support flexible filtering (by entity, time range, technique, severity)
- Response must include pagination for large result sets
- Must return graph-compatible format (nodes + edges)

### Dashboard Integration
- Use existing Svelte 5 runes patterns (no stores/writable)
- Graph visualization: D3.js or a lightweight graph library is preferred
- Node types should have visual distinction (host=blue, alert=red, user=green, etc.)
- Attack paths should have a distinct highlight color

</specifics>

<deferred>
## Deferred Ideas

- Case management integration (assign investigations to analysts)
- Export of attack chain to STIX/TAXII format
- Multi-tenant investigation isolation
- Real-time streaming updates to graph via WebSocket
- Automated remediation suggestions
- Integration with external threat intelligence APIs
- Persistent storage of resolved attack chains (Phase 6 computes on-demand)
- The original roadmap Phase 6 scope (osquery, IOC matching, operational scripts,
  reproducibility receipt, security hardening) — this PRD supersedes that definition.

</deferred>

---

*Phase: 06-hardening-integration (scope redefined: Threat Causality & Investigation Engine)*
*Context gathered: 2026-03-16 via PRD Express Path*
