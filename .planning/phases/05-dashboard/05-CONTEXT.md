# Phase 5: Dashboard — Context

**Gathered:** 2026-03-16
**Status:** Ready for planning
**Source:** PRD Express Path (user-provided requirements)

<domain>
## Phase Boundary

Phase 5 delivers **Suricata-backed network detection and ATT&CK-aware threat scoring** on top of the existing pipeline (Phases 1–4). The existing dashboard already supports graph/timeline/evidence workflows. This phase is additive — no regressions to any prior phase.

Deliverables:
1. **Suricata EVE JSON ingestion** — normalize 5 event types (alert, flow, dns, http, tls) into the existing schema
2. **OpenSearch indexing** — Suricata events indexed via existing `opensearch_sink.py` path
3. **Graph enrichment** — Suricata-derived nodes and edges integrated into the existing graph
4. **Threat scoring model** — first-pass score combining Suricata severity + Sigma hits + recurrence + graph connectivity
5. **ATT&CK-style tagging** — simplified mapping table; alerts/events tagged where clearly applicable
6. **API extensions** — `GET /alerts` includes `threat_score` + `attack_tags`; graph reflects Suricata entities
7. **UI additions** — threat score + ATT&CK tags in alert/evidence views; visual affordance for high-score threats
8. **Tests** — Suricata normalization, scoring, ATT&CK tagging, graph enrichment, API compatibility
9. **Docs** — decision log, manifest, reproducibility (Suricata start path, EVE test data, validation steps)

</domain>

<decisions>
## Implementation Decisions

### Suricata Infra
- Add Suricata service to `infra/docker-compose.yml` if feasible for the environment
- If live runtime not possible (Windows/resource constraints): scaffold service config with documented blocker; validate entirely with fixture EVE JSON
- Config location: `infra/suricata/` (suricata.yaml, rules/)
- EVE JSON log path: `/var/log/suricata/eve.json` (standard location)

### Suricata EVE Ingestion Path
- New parser: `backend/src/parsers/suricata_parser.py`
- Entry point: `parse_eve_line(line: str) -> dict` — accepts one EVE JSON line
- Handles event types: `alert`, `flow`, `dns`, `http`, `tls`
- Falls back to generic normalization for unknown types (no crash)
- Wired into existing `/ingest` endpoint via `source=IngestSource.suricata` (add new enum value)
- Vector pipeline: add `suricata_eve` file source watching EVE JSON + sink to `/ingest`

### EVE Field Normalization (LOCKED)
Mapping to normalized schema:
| EVE field | Normalized field |
|-----------|-----------------|
| `timestamp` | `timestamp` |
| `src_ip` | `src_ip` |
| `src_port` | `port` (source port; dest_port in `raw`) |
| `dest_ip` | `dst_ip` |
| `dest_port` | stored in `raw.dest_port` |
| `proto` | `protocol` |
| `hostname` / `dns.rrname` | `query` (DNS) or stored in `raw` |
| `alert.signature` | `event_type` for alert events |
| `alert.category` | `raw.category` |
| `alert.severity` | mapped to normalized severity (1→critical, 2→high, 3→medium, 4→low) |
| `flow_id` | `raw.flow_id` |
| host value from `host` field | `host` |

### IngestSource Extension
Add `suricata = "suricata"` to `IngestSource` enum in `backend/src/api/models.py`.

### Threat Scoring Model (LOCKED)
Simple additive model, score range 0–100:
```
base_score = 0
+ suricata_severity_points:  critical=40, high=30, medium=20, low=10, none=0
+ sigma_hit: +20 if event has any sigma-matched alert
+ recurrence: +10 if same host/IP seen ≥3 times in event store
+ graph_connectivity: +10 if host/IP node has ≥3 edges in graph
```
Score capped at 100. Stored on `Alert` as `threat_score: int` (default 0).
Model lives in: `backend/src/detection/threat_scorer.py` — `score_alert(alert, events, graph_data) -> int`
Scoring is called inside `_store_event` after detection rules run.

### ATT&CK-Style Tagging (LOCKED — simplified mapping table)
Static lookup table in `backend/src/detection/attack_mapper.py`:
- Maps Suricata alert categories + Sigma rule IDs + event types to ATT&CK tactic/technique labels
- Examples:
  - category "DNS Request" or event_type "dns_query" → `{"tactic": "Command and Control", "technique": "T1071.004"}`
  - category "Potentially Bad Traffic" or suspicious outbound → `{"tactic": "Exfiltration", "technique": "T1048"}`
  - category "Network Trojan" → `{"tactic": "Command and Control", "technique": "T1095"}`
  - Sigma rule `suspicious_dns_query` → `{"tactic": "Command and Control", "technique": "T1071.004"}`
  - high-severity syslog → `{"tactic": "Impact", "technique": "T1499"}`
- Returns `[]` (empty list) for unmapped events — no guessing
- Field on `Alert`: `attack_tags: list[dict]` (default `[]`)
- Document clearly: "simplified static mapping, not full ATT&CK coverage"

### Alert Model Extension (LOCKED)
`Alert` in `backend/src/api/models.py` gains two new optional fields:
- `threat_score: int = 0`
- `attack_tags: list[dict] = []` (each dict: `{tactic: str, technique: str}`)
Both fields included in `GET /alerts` response.

### Graph Enrichment from Suricata
Suricata events feed into the existing `build_graph()` function via the in-memory event store — no special path needed. The graph builder already reads `_events` + `_alerts`; Suricata events in that store will generate appropriate nodes (host, ip, domain) and edges (dns_query, connection) automatically.
No graph builder changes required unless Phase 4 graph builder is not yet merged.

### API Preservation (LOCKED)
All existing endpoints unchanged:
- `GET /health`, `GET /events`, `GET /timeline`, `GET /graph`
- `GET /alerts` — extended with `threat_score` and `attack_tags` fields
- `GET /search`, `POST /events`, `POST /fixtures/load`
- `POST /ingest`, `POST /ingest/syslog`, `GET /events/stream`

Optional new endpoint (Claude's discretion): `GET /threats` — returns alerts sorted by `threat_score` desc, filtered to score > 0.

### UI Additions
Extend existing dashboard (additive only):
- Alert cards/rows: show `threat_score` as a numeric badge (color: green <30, yellow 30–60, red >60)
- Alert detail / EvidencePanel: show `attack_tags` as pill badges (`tactic: technique`)
- Visual affordance: alerts with `threat_score > 60` get a red highlight/border
- No new navigation tabs required — extend existing EvidencePanel and alert display
- `api.ts`: update `getAlerts()` return type to include `threat_score` and `attack_tags`

### Fixture Data
New fixture file: `fixtures/suricata_eve_sample.ndjson`
Must contain at least one of each event type: alert, flow, dns, http, tls.
Used in tests and documented in reproducibility guide.

### Vector Pipeline Extension
Add to `infra/vector/vector.yaml`:
- `suricata_eve` file source (watching `eve.json`)
- Transform: `normalise_suricata` (add `source: "suricata"`)
- Sink: `backend_suricata` → `POST /ingest` with `source=suricata`
- SCAFFOLD if file path not available in dev; document with comment

### Claude's Discretion
- Whether `GET /threats` endpoint is added (add if straightforward, skip if it bloats scope)
- Exact color thresholds for threat score badge
- Whether scoring runs synchronously in `_store_event` or deferred (sync is simpler; prefer it)
- Suricata docker-compose service: use `jasonish/suricata` image or document blocker if Windows incompatible
- Test fixture design (event counts, specific signatures used)

</decisions>

<specifics>
## Specific Ideas

- Suricata severity mapping: EVE uses integers 1–4 (1=high severity in Suricata, counterintuitively). Map 1→critical, 2→high, 3→medium, 4→low.
- `IngestSource.suricata` value = `"suricata"` (string)
- `parse_eve_line` should return a dict compatible with existing `normalize()` in `normalizer.py` — same keys as other parsers
- ATT&CK tags should display as `"{tactic} · {technique}"` in the UI
- Threat score of 0 = no badge (don't show zero scores)
- Phase 5 feature branch: `feature/ai-soc-phase5-suricata`
- EVE sample fixture should be realistic enough to trigger at least one Sigma rule match

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `backend/src/parsers/suricata_parser.py` — **to be created**; follows same pattern as `syslog_parser.py`
- `backend/src/ingestion/opensearch_sink.py` — already active; Suricata events will flow through it automatically
- `backend/src/detection/rules.py` — add `score_alert()` call after existing rule evaluation
- `frontend/src/components/panels/EvidencePanel.svelte` — extend to show `attack_tags` + `threat_score`
- `frontend/src/lib/api.ts` — update `getAlerts()` return type

### Established Patterns
- Parser pattern: `parse_X_line(line: str) -> dict` returning normalized-compatible keys
- IngestSource enum: add value, update health response
- Detection rules: function returning `Alert | None`, collected in `_RULES` list
- Frontend: Svelte 5 runes, no stores; components receive props

### Integration Points
- `backend/src/api/routes.py` `_store_event()` — call `score_alert()` + `map_attack_tags()` after rule evaluation
- `backend/src/api/models.py` — extend `Alert` + `IngestSource`
- `infra/vector/vector.yaml` — add suricata source + sink
- `infra/docker-compose.yml` — add suricata service (or document scaffold)

</code_context>

<deferred>
## Deferred Ideas

- Full ATT&CK framework coverage (all tactics/techniques) — future phase
- Machine learning-based threat scoring — future phase
- Suricata rule management UI — future phase
- Live Suricata rule update pipeline — future phase
- PCAP capture and analysis — future phase
- AI Q&A / `/query` endpoint with Ollama — original Phase 5 roadmap deliverable, now Phase 6
- Full dashboard tab navigation (Q&A, Cases, Detections tabs) — Phase 6
- Case management module — Phase 6 (already deferred from Phase 4)
- D3.js timeline 10K event performance optimization — Phase 6
- Cytoscape progressive disclosure + dagre layout polish — Phase 6

</deferred>

---

*Phase: 05-dashboard*
*Context gathered: 2026-03-16 via PRD Express Path*
