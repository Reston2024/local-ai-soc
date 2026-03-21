# Phase 9: Intelligence & Analyst Augmentation — Context

**Gathered:** 2026-03-17
**Status:** Ready for planning
**Source:** PRD Express Path (inline command arguments)

<domain>
## Phase Boundary

This phase transforms the existing Phase 8 SOC investigation platform into an intelligent SOC assistant. The system already has: ingestion, normalization, storage, correlation engine, graph engine, timeline reconstruction, MITRE mapping, investigation API (`/api/investigate`), and Cytoscape dashboard. Phase 9 builds the intelligence layer ON TOP of this foundation without breaking any existing capability.

**Core transformation:** data-driven tool → analyst-augmenting assistant that prioritizes, explains, and surfaces critical paths automatically.

</domain>

<decisions>
## Implementation Decisions

### NON-NEGOTIABLE CONSTRAINTS (Locked)
- Do NOT refactor working Phase 8 systems unless strictly required
- Do NOT remove any existing capability
- All new features integrate with existing pipeline (DuckDB/SQLite/Chroma, investigation API)
- All AI outputs must be evidence-backed — grounded in stored events/detections
- No hallucinated context passed to Ollama — only structured evidence from DuckDB/SQLite
- Phase 8 tests must remain passing (66 unit tests, 4 xpassed)

### Risk Scoring Engine (Locked)
- Assign numeric risk scores (0.0–1.0 or 0–100) to: events, entities, attack paths
- Scoring factors: MITRE technique severity, process lineage depth, external network behavior, anomaly indicators, detection count per entity
- Output: ranked detection alerts, ranked graph nodes by risk
- Risk scores stored in SQLite alongside detection records (not DuckDB — SQLite is the right store for derived metadata)

### Anomaly / Prioritization Layer (Locked)
- Flag unusual process parent-child relationships (e.g., winword.exe spawning powershell.exe)
- Flag unusual external connections (non-standard ports, known C2 CIDR ranges)
- Flag process chains that deviate from expected Windows process tree norms
- Anomaly rules implemented as a configurable ruleset (not ML — deterministic, auditable)

### AI Analyst — Ollama Integration (Locked)
- Use existing `OllamaClient` (backend/services/ollama_client.py or equivalent)
- Generate three types of output:
  1. Attack chain explanation — describe what happened step by step
  2. Investigation summary — "what happened, why it matters, next steps"
  3. Entity Q&A — analyst can ask about a specific entity or event
- Grounding protocol: serialize structured evidence (top N events, graph nodes, MITRE techniques) into prompt context before Ollama call
- Model: qwen3:14b (already pulled)
- All Ollama calls async via existing httpx client pattern

### Investigation Explanation Engine (Locked)
- Generate three structured sections: "What Happened", "Why It Matters", "Recommended Next Steps"
- Must be derived from actual graph + timeline data (no free-form generation from scratch)
- "Why It Matters" maps detected techniques to MITRE impact descriptions
- "Recommended Next Steps" generates containment/investigation actions based on technique + severity

### API Extensions (Locked)
- `POST /api/score` — accepts event_ids or detection_id, returns risk-scored entities
- `POST /api/explain` — accepts detection_id or investigation context, returns Ollama explanation
- `GET /api/top-threats` — returns top N ranked detections + entities by risk score
- All endpoints return HTTP 200 with structured JSON (never 404/500 for missing data — return empty gracefully)

### Dashboard Upgrade (Locked)
- Risk score visualization: color-coded score badge on each graph node (green/yellow/orange/red)
- Highlighted attack path: visually distinguished edges along the highest-risk path in Cytoscape
- "Top Suspicious Entities" panel: ranked list with score + reason
- AI explanation panel: collapsible panel showing generated explanation with "regenerate" button
- Must integrate into existing `InvestigationPanel.svelte` (not a new tab)

### Case Management — Minimal (Locked)
- Save investigation: store graph snapshot (JSON) + detection metadata + timestamp in SQLite
- Simple retrieval: GET endpoint returns saved investigations list + detail
- Schema: `saved_investigations` table in existing graph.sqlite3
- NOT a full case management system — that is Phase 7. This is snapshot saving only.

### Claude's Discretion
- Exact scoring formula weights (MITRE weight vs. process lineage weight vs. network weight)
- Whether anomaly rules are defined in code or a YAML config file
- Specific Ollama prompt templates (subject to evidence grounding requirement)
- Whether attack path highlighting uses a new Cytoscape style or extends existing severity-border style
- Implementation of risk score persistence: computed on-the-fly vs. cached in SQLite
- Streaming vs. single-response for Ollama explain endpoint

</decisions>

<specifics>
## Specific Technical References

### Existing Code to Reuse
- `backend/services/ollama_client.py` or similar — existing Ollama httpx client
- `backend/api/investigate.py` — investigation orchestrator (scoring integrates here)
- `correlation/clustering.py` — entity clustering (feeds anomaly detection)
- `backend/causality/scoring.py` — Phase 6 scoring module (may already exist, check first)
- `backend/stores/sqlite_store.py` — extend with `saved_investigations` table
- `dashboard/src/components/InvestigationPanel.svelte` — extend, don't replace

### APT Scenario Fixture (use for verification)
- `fixtures/ndjson/apt_scenario.ndjson` — 15 events, Operation NightCrawler
- Detection IDs available after `POST /api/detect/run`
- Expected: `svchosts.exe` and `185.220.101.45` should be highest-risk entities

### MITRE Severity Mapping (use for scoring)
- critical techniques (T1003.001 LSASS, T1071.001 C2) → score 0.9+
- high techniques (T1547.001 persistence, T1059.001 PowerShell) → score 0.7–0.9
- medium techniques (T1033 discovery, T1087.002 enum) → score 0.4–0.7
- low techniques → score 0.1–0.4

### Process Anomaly Baselines (for anomaly layer)
Known-bad parent-child pairs that should always flag:
- Office apps spawning shells: winword/excel/powershell spawning cmd/powershell/wscript
- System processes spawned by non-system parents
- Masquerading: process names resembling svchost/lsass/csrss but in unexpected paths

</specifics>

<deferred>
## Deferred Ideas

- ML-based anomaly detection (clustering/baseline learning) — deterministic rules only in Phase 9
- Full streaming Ollama via SSE to dashboard (acceptable but not required — single-response is fine)
- Multi-model support (use qwen3:14b only)
- Graph-based path scoring algorithms (PageRank, centrality) — beyond scope for Phase 9
- Integration with external threat intel feeds (VirusTotal, MISP) — future phase

</deferred>

---

*Phase: 09-intelligence-analyst-augmentation*
*Context gathered: 2026-03-17 via PRD Express Path*
