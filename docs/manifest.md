# Project Manifest

Generated: 2026-04-14
Branch: main
Status: v1.0 complete (30 phases) — v1.1 complete (Phases 31-44) — Phase 45 complete (Agentic Investigation) — Phase 46 complete (Playbook Library Expansion: 30 playbooks, multi-source, category filtering)

---

## Infrastructure

### Desktop — SOC Brain (Windows 11, RTX 5080)

All AI inference, detection, correlation, and analysis run here.

### supportTAK-server — Dumb Pipe (Ubuntu, GMKtec N150, 192.168.1.22)

Raw telemetry collection and indexing only. No AI.

| Component | Status |
|-----------|--------|
| Malcolm NSM (17 containers) | Running |
| OpenSearch (7.4 GB RAM) | Active — 22M+ syslog, 71K alerts |
| Logstash | Active |
| Filebeat | Active |
| Zeek | Running — 0 output (no SPAN port) |
| pcap-capture, Strelka, etc. | Idle — no PCAP feed |

**Malcolm telemetry collection status (2026-04-09):**
- Collecting: IPFire syslog (22M+ docs), Suricata EVE alerts (71K docs)
- NOT collecting: EVE TLS (156K docs), EVE DNS (71K), EVE fileinfo (6K), EVE anomaly (1K) — Phase 31 expands this
- Zeek: 0 docs — hardware blocked (need managed switch with SPAN port)

---

## File Tree

```
ai-soc-brain/
│
├── backend/                          ← FastAPI application (Python 3.12)
│   ├── __init__.py
│   ├── main.py                       ← App factory: create_app() + lifespan context
│   ├── api/
│   │   ├── __init__.py
│   │   ├── chat.py                   ← POST /api/investigations/{id}/chat — SSE AI copilot
│   │   ├── correlate.py              ← GET /api/correlate — event correlation clustering
│   │   ├── detect.py                 ← POST /api/detect/run, GET /api/detect
│   │   ├── events.py                 ← GET/POST /api/events, POST /api/events/search
│   │   ├── explain.py                ← POST /api/explain — LLM explanation generation
│   │   ├── export.py                 ← GET /api/export — NDJSON export
│   │   ├── firewall.py               ← GET /api/firewall/status — collector heartbeat
│   │   ├── graph.py                  ← GET /api/graph/global, /api/graph/{id}, etc.
│   │   ├── health.py                 ← GET /health — unauthenticated status check
│   │   ├── ingest.py                 ← POST /api/ingest, POST /api/ingest/file, GET /api/ingest/status/{job_id}
│   │   ├── investigate.py            ← POST /api/investigate — unified investigation endpoint
│   │   ├── investigations.py         ← POST/GET /api/investigations
│   │   ├── metrics.py                ← GET /api/metrics — SOC metrics and KPIs
│   │   ├── operators.py              ← GET/POST/PATCH/DELETE /api/operators — RBAC
│   │   ├── playbooks.py              ← All /api/playbooks + /api/playbook-runs routes
│   │   ├── query.py                  ← POST /api/query, POST /api/query/ask/stream — SSE
│   │   ├── receipts.py               ← POST /api/receipts — execution receipt ingestion
│   │   ├── recommendations.py        ← GET/POST /api/recommendations — AI artifact store
│   │   ├── reports.py                ← /api/reports — PDF generation, MITRE heatmap, TheHive export
│   │   ├── score.py                  ← POST /api/score — entity risk scoring
│   │   ├── telemetry.py              ← GET /api/telemetry — osquery live telemetry
│   │   ├── timeline.py               ← GET /api/investigations/{id}/timeline
│   │   └── top_threats.py            ← GET /api/top-threats — top scored entities
│   ├── causality/
│   │   ├── __init__.py
│   │   ├── attack_chain_builder.py   ← ATT&CK kill chain reconstruction
│   │   ├── causality_routes.py       ← GET /api/causality endpoints
│   │   ├── engine.py                 ← Parent/child process causality engine
│   │   ├── entity_resolver.py        ← Hostname/user/process entity resolution
│   │   ├── mitre_mapper.py           ← MITRE ATT&CK technique tagging
│   │   └── scoring.py                ← Detection-level scoring
│   ├── core/
│   │   ├── __init__.py
│   │   ├── auth.py                   ← Bearer token auth (verify_token FastAPI dependency)
│   │   ├── config.py                 ← Pydantic-settings Settings singleton
│   │   ├── deps.py                   ← Stores container dataclass
│   │   └── logging.py                ← structlog + rotating file handler + LLM audit logger
│   ├── data/
│   │   └── builtin_playbooks.py      ← 5 NIST IR playbooks seeded on startup
│   ├── intelligence/
│   │   ├── __init__.py
│   │   ├── anomaly_rules.py          ← Statistical anomaly detection rules
│   │   ├── explain_engine.py         ← LLM-based explanation generation
│   │   └── risk_scorer.py            ← Entity risk scoring model
│   ├── investigation/
│   │   ├── __init__.py
│   │   ├── artifact_store.py         ← Saved investigation artifact management
│   │   ├── case_manager.py           ← Case lifecycle management
│   │   ├── hunt_engine.py            ← Threat hunt query engine (stub — Phase 32)
│   │   ├── investigation_routes.py   ← Investigation sub-routes
│   │   ├── tagging.py                ← Entity and event tagging
│   │   └── timeline_builder.py       ← Attack timeline construction
│   ├── models/
│   │   ├── __init__.py
│   │   ├── event.py                  ← NormalizedEvent Pydantic model + field definitions
│   │   └── playbook.py               ← PlaybookStep, Playbook, PlaybookRun, PlaybookCreate, PlaybookRunAdvance
│   ├── services/
│   │   ├── __init__.py
│   │   └── ollama_client.py          ← Ollama HTTP client (generate + embed + LLM audit log + digest verification)
│   └── stores/
│       ├── __init__.py
│       ├── chroma_store.py           ← ChromaDB PersistentClient wrapper
│       ├── duckdb_store.py           ← DuckDB store with write queue pattern + external access disabled
│       └── sqlite_store.py           ← SQLite store (graph, detections, cases, playbook runs, operators)
│
├── ingestion/                        ← Event parsing and normalization pipeline
│   ├── __init__.py
│   ├── entity_extractor.py           ← Entity/edge extraction for graph
│   ├── loader.py                     ← Batch ingest + Chroma embed coordinator
│   ├── normalizer.py                 ← Field normalization, severity mapping, injection scrubbing
│   ├── osquery_collector.py          ← osquery live telemetry collector
│   ├── registry.py                   ← Parser registry
│   ├── jobs/
│   │   ├── firewall_collector.py     ← FirewallCollector — IPFire/Suricata file-tail asyncio task
│   │   └── malcolm_collector.py      ← MalcolmCollector — OpenSearch poll (30s cycle)
│   └── parsers/
│       ├── __init__.py
│       ├── base.py                   ← Parser base class
│       ├── csv_parser.py             ← CSV event parser
│       ├── evtx_parser.py            ← Windows EVTX parser (pyevtx-rs)
│       ├── ipfire_syslog_parser.py   ← IPFire RFC 3164 syslog → NormalizedEvent
│       ├── json_parser.py            ← JSON/NDJSON event parser
│       ├── osquery_parser.py         ← osquery result log parser
│       └── suricata_eve_parser.py    ← Suricata EVE JSON → NormalizedEvent
│
├── detections/                       ← Sigma rule matching
│   ├── __init__.py
│   ├── backends/
│   │   └── __init__.py
│   ├── field_map.py                  ← Sigma field → DuckDB column mapping
│   ├── matcher.py                    ← Custom DuckDB SQL backend for Sigma
│   ├── pipelines/
│   │   └── __init__.py
│   └── sigma/
│       └── meta/
│           ├── auth_failure_burst.yml ← Meta-detection: auth burst
│           ├── llm_token_spike.yml    ← Meta-detection: LLM token spikes
│           └── collection_delete.yml  ← Meta-detection: ChromaDB deletion
│
├── correlation/                      ← Event clustering
│   ├── __init__.py
│   └── clustering.py                 ← Union-Find + temporal window correlation
│
├── graph/                            ← Graph schema and traversal
│   ├── __init__.py
│   ├── builder.py                    ← Cytoscape node/edge builder
│   └── schema.py                     ← Graph schema constants (entity types, edge types, schema_version)
│
├── prompts/                          ← LLM prompt templates
│   ├── __init__.py
│   ├── analyst_qa.py                 ← build_prompt() → (system_str, user_str) tuple
│   ├── evidence_explain.py
│   ├── incident_summary.py
│   ├── investigation_summary.py
│   ├── threat_hunt.py
│   └── triage.py                     ← build_prompt() for detection triage (not yet auto-called — Phase 35)
│
├── contracts/
│   └── recommendation.schema.json   ← JSON Schema v1.0.0 for recommendation artifacts
│
├── dashboard/                        ← Svelte 5 SPA (npm project)
│   ├── src/
│   │   ├── App.svelte                ← Root layout + view router + navigation state
│   │   ├── main.ts                   ← Entry point
│   │   ├── components/
│   │   │   ├── InvestigationPanel.svelte  ← Investigation panel component
│   │   │   └── graph/
│   │   │       └── ThreatGraph.svelte     ← DEAD CODE — unreachable from active view tree
│   │   ├── lib/
│   │   │   └── api.ts                ← Typed API client — all fetch calls go through here
│   │   └── views/
│   │       ├── AssetsView.svelte     ← Entity inventory — "Discover Assets" disabled (Phase 34)
│   │       ├── DetectionsView.svelte ← Sigma alert feed + "Investigate →" navigation
│   │       ├── EventsView.svelte     ← Normalized event table, search
│   │       ├── GraphView.svelte      ← Cytoscape.js fCoSE attack graph
│   │       ├── HuntingView.svelte    ← ALL BUTTONS DISABLED — stub only (Phase 32)
│   │       ├── IngestView.svelte     ← File upload ingestion + status polling
│   │       ├── InvestigationView.svelte  ← Timeline, attack chain, AI copilot chat, "Run Playbook"
│   │       ├── PlaybooksView.svelte  ← SOAR playbook library + step execution
│   │       ├── QueryView.svelte      ← Semantic + DuckDB hybrid search (SSE streaming)
│   │       ├── ReportsView.svelte    ← PDF, MITRE heatmap, TheHive export
│   │       ├── SettingsView.svelte   ← Operator CRUD, RBAC management
│   │       └── ThreatIntelView.svelte ← STUB — fake feed data, "BETA" badge (Phase 33)
│   ├── package.json                  ← cytoscape-fcose@^2.2.0, cytoscape-dagre@^2.5.0
│   └── vite.config.ts
│
├── tests/                            ← pytest test suite (938+ passing)
│   ├── conftest.py
│   ├── unit/                         ← Unit tests (no I/O)
│   │   ├── test_anomaly_rules.py
│   │   ├── test_api_endpoints.py
│   │   ├── test_api_extended.py
│   │   ├── test_auth.py
│   │   ├── test_causality_modules.py
│   │   ├── test_chroma_store.py
│   │   ├── test_config.py
│   │   ├── test_csv_parser.py
│   │   ├── test_duckdb_store.py
│   │   ├── test_entity_extractor.py
│   │   ├── test_eval_models.py
│   │   ├── test_evtx_parser.py
│   │   ├── test_explain_api.py
│   │   ├── test_explain_engine.py
│   │   ├── test_export_api.py
│   │   ├── test_graph_api.py
│   │   ├── test_ingest_api.py
│   │   ├── test_investigation_chat.py
│   │   ├── test_investigation_timeline.py
│   │   ├── test_investigation_utils.py
│   │   ├── test_json_parser.py
│   │   ├── test_loader.py
│   │   ├── test_malcolm_collector.py
│   │   ├── test_matcher.py
│   │   ├── test_metrics_api.py
│   │   ├── test_metrics_service.py
│   │   ├── test_normalizer.py
│   │   ├── test_ollama_audit.py
│   │   ├── test_ollama_client.py
│   │   ├── test_operators_api.py
│   │   ├── test_osquery_collector.py
│   │   ├── test_playbooks.py
│   │   ├── test_rate_limiting.py
│   │   ├── test_recommendations.py
│   │   ├── test_receipts.py
│   │   ├── test_risk_scorer.py
│   │   ├── test_score_api.py
│   │   ├── test_sqlite_store.py
│   │   ├── test_timeline_builder.py
│   │   └── test_top_threats_api.py
│   ├── security/                     ← Security-focused tests
│   │   ├── test_auth.py
│   │   ├── test_auth_hardening.py
│   │   ├── test_injection.py
│   │   ├── test_injection_hardening.py
│   │   └── test_sigma_hardening.py
│   ├── integration/
│   │   ├── test_backend_health.py
│   │   ├── test_investigation_roundtrip.py
│   │   └── test_osquery_pipeline.py
│   ├── eval/
│   │   └── fixtures/
│   │       └── injection_b64_bypass.json  ← Adversarial eval fixture
│   └── sigma_smoke/
│       ├── test_sigma_matcher.py
│       └── test_meta_rules.py        ← 3 meta-rule parse tests
│
├── .github/
│   └── workflows/
│       └── ci.yml                    ← CI: ruff + pytest (≥70% coverage) + pip-audit + gitleaks + frontend
│
├── scripts/                          ← PowerShell + Python management scripts
│   ├── _check-health.ps1
│   ├── _e2e-verify.ps1
│   ├── _start-backend.ps1
│   ├── configure-acls.ps1            ← data/ directory ACL hardening
│   ├── configure-firewall.ps1        ← Block port 11434 except localhost+Docker NIC
│   ├── eval_models.py                ← LLM evaluation script
│   ├── load-scenario.py              ← Load APT scenario fixture
│   ├── seed_siem_data.py             ← Seed SIEM test data
│   ├── smoke-test-phase1.ps1
│   ├── smoke-test-phase8.ps1
│   ├── start.cmd / start.ps1         ← Start FastAPI + Caddy
│   ├── status.cmd / status.ps1       ← Show service health
│   ├── stop.cmd / stop.ps1           ← Stop all services
│   └── verify-firewall.ps1           ← Verify firewall rule config
│
├── fixtures/                         ← Test fixture data
│   └── ndjson/
│       ├── sample_events.ndjson
│       └── apt_scenario.ndjson       ← 15-event APT "Operation NightCrawler" scenario
│
├── config/
│   ├── caddy/
│   │   └── Caddyfile                 ← Security headers: CSP, X-Frame-Options, etc.
│   ├── osquery/
│   │   └── osquery.conf              ← 4 scheduled queries (process, network, user, file)
│   └── .env.example                  ← Template with all required settings documented
│
├── docs/
│   ├── ADR-020-hf-model.md           ← ADR: HuggingFace embedding model selection
│   ├── ADR-030-ai-recommendation-governance.md
│   ├── ADR-031-transport-contract-reference.md
│   ├── ADR-032-executor-failure-reference.md
│   ├── decision-log.md               ← Redirect → DECISION_LOG.md (root)
│   ├── manifest.md                   ← This file
│   └── reproducibility.md            ← Redirect → REPRODUCIBILITY_RECEIPT.md (root)
│
├── .planning/
│   └── v1.0-v1.0-MILESTONE-AUDIT.md ← v1.0 final audit — all 59 requirements, 8/8 E2E flows
│
├── ARCHITECTURE.md                   ← System design, two-box architecture, data flow
├── CLAUDE.md                         ← Claude Code conventions for this repo
├── DECISION_LOG.md                   ← ADR-001 through ADR-033
├── PROJECT.md                        ← Project brief
├── README.md                         ← Quick start, features, phase history
├── REPRODUCIBILITY_RECEIPT.md        ← Pinned dependency versions + two-box infrastructure
├── STATE.md                          ← Live project state — all 30 phases + v1.1 status
├── THREAT_MODEL.md                   ← Threat model for local desktop deployment
├── docker-compose.yml                ← Caddy container definition (digest-pinned)
├── pyproject.toml                    ← Python deps with exact pins
└── uv.lock                           ← Source of truth for Python dependency versions
```

---

## Active API Endpoints (v1.0)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /health | None | Status check — always unauthenticated |
| GET | /openapi.json | None | OpenAPI spec |
| GET | /docs | None | Swagger UI |
| GET/POST | /api/events | Bearer | List / ingest single event |
| POST | /api/events/search | Bearer | Search events by field |
| POST | /api/ingest | Bearer | Batch event ingest with source label |
| POST | /api/ingest/file | Bearer | Ingest from uploaded file |
| GET | /api/ingest/status/{job_id} | Bearer | Ingest job status |
| POST | /api/query/ask/stream | Bearer | Semantic RAG query — SSE stream |
| POST | /api/query | Bearer | Semantic + DuckDB hybrid search (non-streaming compat) |
| POST | /api/detect/run | Bearer | Run Sigma rules against stored events |
| GET | /api/detect | Bearer | List detection results |
| GET | /api/graph/global | Bearer | All entities + edges |
| GET | /api/graph/{investigation_id} | Bearer | Investigation subgraph |
| GET | /api/graph/entity/{entity_id} | Bearer | Entity neighbours |
| GET | /api/graph/entities | Bearer | Entity list |
| GET | /api/graph/traverse/{entity_id} | Bearer | BFS traversal from entity |
| GET | /api/graph/case/{case_id} | Bearer | Entities for a case |
| GET | /api/export | Bearer | Export events as NDJSON |
| POST | /api/score | Bearer | Entity risk scoring |
| GET | /api/top-threats | Bearer | Top-scored threat entities |
| POST | /api/explain | Bearer | LLM explanation for detection/event |
| GET/POST | /api/investigations | Bearer | List / create investigations |
| GET | /api/investigations/{id}/timeline | Bearer | Investigation timeline |
| POST | /api/investigations/{id}/chat | Bearer | AI copilot chat (SSE stream) |
| GET | /api/metrics | Bearer | SOC metrics and KPIs |
| GET | /api/correlate | Bearer | Event correlation clusters |
| GET | /api/causality | Bearer | Process causality graph |
| POST | /api/investigate | Bearer | Unified investigation pipeline |
| GET | /api/telemetry | Bearer | osquery live telemetry status |
| GET/POST | /api/playbooks | Bearer | List / create playbooks |
| GET | /api/playbooks/{id} | Bearer | Get playbook by ID |
| GET | /api/playbooks/{id}/runs | Bearer | Run history for playbook |
| POST | /api/playbooks/{id}/run/{inv_id} | Bearer | Start a playbook run |
| PATCH | /api/playbook-runs/{run_id}/step/{n} | Bearer | Analyst confirms step N |
| PATCH | /api/playbook-runs/{run_id}/cancel | Bearer | Cancel a run |
| GET | /api/playbook-runs/{run_id} | Bearer | Fetch run state |
| GET | /api/playbook-runs/{run_id}/stream | Bearer | SSE stream of step events |
| GET/POST | /api/operators | Bearer | Operator CRUD (RBAC management) |
| GET/PATCH/DELETE | /api/operators/{id} | Bearer | Single operator management |
| GET/POST | /api/recommendations | Bearer | AI recommendation artifact store |
| POST | /api/receipts | Bearer | Firewall execution receipt ingestion |
| GET | /api/firewall/status | Bearer | FirewallCollector heartbeat |

| POST | /api/feedback | Bearer | Submit TP/FP analyst verdict; fires async Chroma embed + River learn_one |
| GET | /api/feedback/similar | Bearer | Chroma k-NN top 3 similar confirmed incidents |
| GET | /api/anomaly/score | Bearer | Entity behavioral anomaly score (River) |
| GET | /api/anomaly/trend | Bearer | Entity score trend over time |
| GET | /api/triage/run | Bearer | Auto AI triage background worker |
| GET | /api/intel/iocs | Bearer | IOC matching against live feeds |
| GET | /api/assets | Bearer | Auto-derived asset inventory |
| GET | /api/hunts | Bearer | Threat hunt query results |
| GET | /api/threat-map | Bearer | Geolocated attacker IP data |

**Phase 45+:** `/api/investigate/auto` (agentic investigation pipeline)

**Auth:** All `/api/*` routes require `Authorization: Bearer <token>`. `AUTH_TOKEN` must be 32+ chars or `dev-only-bypass`. Implemented in `backend/core/auth.py`.

---

## Dashboard Views

| View | File | Status | Description |
|------|------|--------|-------------|
| Detections | DetectionsView.svelte | Ready | Sigma alert feed, ATT&CK tactic/technique |
| Events | EventsView.svelte | Ready | Normalized event table, search |
| Investigation | InvestigationView.svelte | Ready | Timeline, attack chain, AI copilot, "Run Playbook" |
| Query | QueryView.svelte | Ready | SSE streaming RAG Q&A |
| Ingest | IngestView.svelte | Ready | File upload ingestion, status polling |
| Assets | AssetsView.svelte | Ready | Auto-derived entity inventory from telemetry |
| Graph | GraphView.svelte | Ready | Cytoscape.js fCoSE, Dijkstra paths, MITRE overlay |
| Playbooks | PlaybooksView.svelte | Ready | Library browser + step execution with audit trail |
| Reports | ReportsView.svelte | Ready | PDF, MITRE heatmap, KPI trends, TheHive export |
| Settings | SettingsView.svelte | Ready | Operator CRUD, RBAC |
| Threat Intel | ThreatIntelView.svelte | Ready | IOC matching, live feed enrichment |
| Hunting | HuntingView.svelte | Ready | Rule-based hunt queries, live event search |
| Threat Map | ThreatMapView.svelte | Ready | Geolocated attacker IPs, OSINT enrichment |
| Overview | OverviewView.svelte | Ready | SOC KPIs + feedback KPIs (verdicts, TP/FP rates, classifier accuracy) |

---

## Test Baseline (2026-04-12)

```
uv run pytest tests/unit/ tests/security/ tests/sigma_smoke/ -q
1081+ passed
```

Coverage target: ≥70% (enforced in CI).

---

## Component Status by Phase

### Phases 1-17 (Foundation through SOAR)
Fully documented in ARCHITECTURE.md and DECISION_LOG.md.

### Phase 18: Reporting & Compliance
- `backend/api/reports.py` — PDF generation, MITRE ATT&CK heatmap, D3 KPI trends, NIST CSF 2.0, TheHive ZIP export

### Phase 19: Identity & RBAC
- `backend/api/operators.py` — operator CRUD endpoints
- `backend/stores/sqlite_store.py` — operators table with bcrypt-hashed passwords
- `dashboard/src/views/SettingsView.svelte` — operator management UI

### Phase 20: Schema Standardisation
- ECS/OCSF field alignment in `NormalizedEvent`
- DuckDB column renames for schema consistency

### Phase 21: Evidence Provenance
- SHA-256 content hashing on all events at ingest
- `backend/api/receipts.py` — receipt ingestion and chain-of-custody propagation
- Provenance chain: hash → case_id → detection_id → receipt

### Phase 22: AI Lifecycle Hardening
- `backend/services/ollama_client.py` — SHA-256 provenance, model drift detection, grounding scores, confidence tracking
- `backend/intelligence/explain_engine.py` — evidence context builder

### Phase 23: Firewall Telemetry
- `ingestion/parsers/ipfire_syslog_parser.py` — RFC 3164 IPFire format
- `ingestion/parsers/suricata_eve_parser.py` — EVE JSON: alert/flow/dns/http
- `ingestion/jobs/firewall_collector.py` — file-tail asyncio collector with exponential backoff
- `backend/api/firewall.py` — heartbeat endpoint

### Phase 23.5: Security Hardening (expert panel — 18 findings)
- `backend/core/config.py` — AUTH_TOKEN startup validator (32+ chars)
- `ingestion/normalizer.py` — NFC + base64 decode heuristic scrubbing
- `backend/stores/duckdb_store.py` — enable_external_access=false
- `backend/stores/chroma_store.py` — delete_collection() gated by _admin_override
- `backend/services/ollama_client.py` — verify_model_digest()
- `detections/sigma/meta/` — 3 meta-detection rules
- Caddy Caddyfile — CSP, X-Frame-Options, X-Content-Type-Options, Referrer-Policy

### Phase 24: Recommendation Artifact Store
- `backend/api/recommendations.py` — AI recommendation CRUD
- `contracts/recommendation.schema.json` — JSON Schema v1.0.0
- `docs/ADR-030-ai-recommendation-governance.md`
- `docs/ADR-031-transport-contract-reference.md`
- `docs/ADR-032-executor-failure-reference.md`

### Phase 25: Receipt Ingestion
- `backend/api/receipts.py` — receipt ingestion → case state propagation
- failure_taxonomy → case-state transitions

### Phase 26: Graph Schema Versioning
- `graph/schema.py` — schema_version constant, firewall_zone and network_segment entity types
- `backend/stores/sqlite_store.py` — migration support

### Phase 27: Malcolm NSM Integration
- `ingestion/jobs/malcolm_collector.py` — MalcolmCollector polls OpenSearch at 192.168.1.22:9200 every 30s
- ECS field normalization from OpenSearch hits to NormalizedEvent
- Status: collecting syslog (22M+ docs) and EVE alerts (71K docs)
- NOT collecting: EVE TLS/DNS/fileinfo/anomaly (Phase 31), Zeek (Phase 36)

### Phase 28: Dashboard Integration Fixes
- INT-01: QueryView SSE URL fixed (`/api/query/ask/stream`)
- INT-02: EventsView event search shape fixed (`res.events`)
- INT-03: Ingest status route added (`/api/ingest/status/{job_id}`)
- INT-04: SettingsView nav wired (`/api/operators`)

### Phases 29-30: Verifiers + Final Sign-Off
- VERIFICATION.md created for all 30 phases
- Sigma guard on startup
- Caddy image digest-pinned in docker-compose.yml

### Phases 31-36: Malcolm Telemetry + Real Data
- Phase 31: EVE JSON ingestion, Malcolm collector expanded
- Phase 32: HuntingView backend API, live hunt queries
- Phase 33: IOC matching, OSINT feed enrichment
- Phase 34: Auto-derived asset inventory from telemetry
- Phase 35: Auto AI triage background loop, `/api/triage/run`
- Phase 36: Zeek full telemetry via Netgear GS308E SPAN port (port 1→5)

### Phases 37-40: Content + Intelligence
- Phase 37: Analyst report templates, structured case export
- Phase 38: Expanded CISA playbook library
- Phase 39: CAR analytics in DetectionsView — MITRE CAR description + MODERATE/MODERATE/HIGH coverage badges
- Phase 40: Threat Map — geolocated OSINT attacker map, IP enrichment via ipinfo.io

### Phases 41-44: Behavioral AI + Feedback
- Phase 41: Anomaly baseline engine — DuckDB sliding-window statistical baselines, severity heat map
- Phase 42: Streaming behavioral profiles — River online anomaly scoring, score trend sparklines in AnomalyView
- Phase 43: Sigma v2 correlation rules — port scan (15+ ports/60s), brute force (10+ fails/60s), beaconing (CV<0.3/20+ connections), multi-stage chain detection via YAML config; CORR filter chips in DetectionsView
- Phase 44: Analyst feedback loop — TP/FP ghost buttons in expand panel, verdict badge on collapsed rows, Unreviewed filter chip, toast notification, River LogisticRegression online classifier, Chroma k-NN similar confirmed incidents in InvestigationView, 5 feedback KPI tiles in OverviewView

---

*Manifest last updated: 2026-04-12 (v1.1 complete — 44 phases)*
