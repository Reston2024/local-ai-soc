# ARCHITECTURE.md
# AI-SOC-Brain — Local AI Cybersecurity Investigation Platform

> **This document covers v1.2 — Phases 1–54 complete (as of 2026-04-17).**
> v1.0 (Phases 1–30), v1.1 (Phases 31–46), and v1.2 (Phases 47–54) are all complete.
> See STATUS.md for the phase completion log and current metrics.

**Version:** 1.54 | **Date:** 2026-04-17 | **Status:** v1.2 in progress — Phases 1–54 complete

---

## System Overview

A single-analyst, local-first cybersecurity investigation platform. Four physical devices. The GMKtec box is a dumb pipe — raw telemetry collection and indexing only, plus threat intelligence and case management services. All AI inference, detection, correlation, and analysis runs on the Windows desktop.

```
  GMKtec N150 (Ubuntu, 192.168.1.22)                  Netgear GS308E
  ┌──────────────────────────────────────────────┐    ┌──────────────┐
  │  Malcolm NSM (17 containers)                  │    │  Port 1→5    │
  │  ├─ OpenSearch  (7.4 GB RAM) — log indexing   │    │  SPAN tap    │
  │  ├─ Logstash   — log processing pipeline      │◀───│  for Zeek    │
  │  ├─ Filebeat   — log shipping                 │    └──────────────┘
  │  ├─ Arkime     — network session indexing     │
  │  ├─ Zeek       — network protocol logs (LIVE) │
  │  ├─ MISP :8443 — 4,568 IOCs, 6h sync         │
  │  ├─ TheHive :9000 — case management           │
  │  ├─ Cortex :9001 — MISP connector             │
  │  └─ SpiderFoot :9002 — OSINT investigation    │
  └──────────────────────┬───────────────────────┘
                         │ syslog + EVE JSON + Zeek +
                         │ beats + IOC API + case API
                         ▼
  Desktop (Windows 11, Intel Core Ultra 9 285K, 96 GB, RTX 5080 16 GB)
  ┌──────────────────────────────────────────────────────────────────┐
  │  Browser (http://localhost:5173 dev | https://localhost prod)     │
  │                          │                                        │
  │             ┌────────────▼────────────┐                          │
  │             │   Caddy (Docker)         │  TLS termination         │
  │             └────────────┬────────────┘                          │
  │                          │ HTTP  localhost:8001                   │
  │             ┌────────────▼──────────────────────────────┐        │
  │             │         FastAPI Backend                     │        │
  │             │                                            │        │
  │             │  /health  /api/events  /api/ingest         │        │
  │             │  /api/detect  /api/graph  /api/query       │        │
  │             │  /api/investigate /api/investigations      │        │
  │             │  /api/playbooks  /api/operators            │        │
  │             │  /api/recommendations  /api/receipts       │        │
  │             │  /api/hunts  /api/intel  /api/feedback     │        │
  │             │  /api/investigate/auto  /api/hayabusa      │        │
  │             │  /api/chainsaw  /api/misp  /api/thehive    │        │
  │             │  /api/spiderfoot  /api/rerank              │        │
  │             └──┬──────────┬──────────────┬──────────────┘        │
  │                │          │              │                        │
  │        HTTP REST      embed/SQL         SQL                       │
  │                │          │              │                        │
  │       ┌────────▼┐   ┌────▼────┐   ┌────▼─────────┐              │
  │       │ Ollama  │   │ Chroma  │   │  DuckDB │SQLite│             │
  │       │ :11434  │   │ :8200   │   │  events │graph │             │
  │       │ native  │   │ remote  │   │ columnar│edges │             │
  │       └─────────┘   └─────────┘   └──────────────┘              │
  │       qwen3:14b                                                   │
  │       bge-m3 embed (Ollama/Vulkan)                                │
  │       50-80+ tok/s GPU (Blackwell sm_120)                         │
  │                                                                   │
  │       ┌─────────────────────────────────────────┐                │
  │       │  Reranker :8100                          │                │
  │       │  BAAI/bge-reranker-v2-m3 (CUDA torch)   │                │
  │       └─────────────────────────────────────────┘                │
  └──────────────────────────────────────────────────────────────────┘

  IPFire (192.168.1.1) — syslog + Suricata EVE → GMKtec/Malcolm
```

**Key constraint:** The GMKtec box does NOT do AI. The 20-30x GPU throughput advantage on the desktop makes inference there the only rational choice. See ADR-030.

---

## Layer Definitions

| Layer | Technology | Runtime | Version | Justification |
|-------|-----------|---------|---------|---------------|
| **LLM Inference** | Ollama + qwen3:14b | Native Windows | 0.18.2+ | Direct CUDA/Vulkan to RTX 5080. Docker GPU passthrough adds WSL2 complexity for negligible gain. |
| **Embeddings** | bge-m3 (via Ollama) | Native Windows | — | MTEB multilingual embedding. Replaces mxbai-embed-large from Phase 54. |
| **Reranker** | BAAI/bge-reranker-v2-m3 | Native Python (CUDA) | torch 2.11+cu128 | Cross-encoder reranking of RAG results. Runs on port :8100. Requires manual start after reboot. |
| **Backend API** | FastAPI + Uvicorn | Native Python 3.12 | 0.115.12 / 0.34.3 | In-process access to all embedded DBs. Async SSE/WebSocket for LLM streaming. |
| **Structured Storage** | DuckDB | Embedded in-process | 1.3.0 | Columnar analytics, 24-core parallel, CSV/JSON/Parquet native reads. |
| **Vector Storage** | Chroma HttpClient | Remote :8200 (GMKtec) | 1.5.5 | Hybrid BM25+semantic search. Remote mode as of Phase 54. No LangChain wrapper. |
| **Graph/State Storage** | SQLite WAL | Embedded in-process | stdlib | Graph edges, detection state, case metadata, playbook runs. |
| **HTTPS Proxy** | Caddy 2.9-alpine | Docker (~40MB) | sha256:b4e39523... | Auto-TLS for localhost. Only container on desktop. |
| **Dashboard** | Svelte 5 SPA | Static files | ^5.28.0 | Runes-based reactivity. Cytoscape.js + fCoSE, D3.js. |
| **Detection** | pySigma + custom DuckDB backend | Embedded in-process | 1.2.0 | Sigma YAML → DuckDB SQL. Custom field mapping pipeline. |
| **NSM Collection** | Malcolm (GMKtec box) | Docker (17 containers) | Latest | Dumb pipe only. Collects and indexes; does not analyze. |
| **EVTX Threat Hunting** | Hayabusa binary | Subprocess | Latest | Fast Windows event log threat hunting. Phase 48. |
| **EVTX Log Analysis** | Chainsaw binary | Subprocess | Latest | Rule-based Windows event log analysis. Phase 49. |
| **Threat Intelligence** | MISP | Docker (GMKtec) | Latest | 4,568 IOCs synced via pymisp; 6h sync cycle. Phase 50. |
| **Case Management** | TheHive + Cortex | Docker (GMKtec) | Latest | Auto-cases from detections; MISP connector. Phase 52. |
| **OSINT** | SpiderFoot | Docker (GMKtec) | Latest | OSINT investigation scan API integrated in InvestigationView. Phase 51. |
| **Agentic Investigation** | smolagents + Ollama | Embedded in-process | 1.24.0+ | 7-tool agentic pipeline for automated investigation. Phase 45. |
| **Online ML** | River | Embedded in-process | 0.21.0+ | Analyst feedback → online TP/FP classifier; entity anomaly scoring. Phase 44. |

---

## Data Architecture

### Normalized Event Schema (Central Contract)

All evidence parsers produce `NormalizedEvent` records. This schema is the contract between ingestion, detection, RAG, and graph layers.

**Core fields:** `event_id` (UUID), `timestamp`, `ingested_at`, `source_type`, `source_file`
**Entity fields:** `hostname`, `username`, `process_name`, `process_id`, `parent_process_name`, `parent_process_id`, `file_path`, `file_hash_sha256`, `command_line`
**Network fields:** `src_ip`, `src_port`, `dst_ip`, `dst_port`, `domain`, `url`
**Classification:** `event_type`, `severity`, `confidence`, `detection_source`, `attack_technique`, `attack_tactic`
**Provenance:** `raw_event`, `tags[]`, `case_id`

### Storage Layout

```
data/
├── events.duckdb          # All normalized events (columnar)
├── chroma/                # Vector embeddings (PersistentClient)
│   └── [collection files]
└── graph.sqlite3          # Entity nodes + edges + detections + cases + playbook runs (WAL)
```

### DuckDB Schema

```sql
CREATE TABLE normalized_events (
    event_id TEXT PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL,
    ingested_at TIMESTAMP NOT NULL,
    source_type TEXT NOT NULL,
    source_file TEXT,
    hostname TEXT, username TEXT,
    process_name TEXT, process_id INTEGER,
    parent_process_name TEXT, parent_process_id INTEGER,
    file_path TEXT, file_hash_sha256 TEXT, command_line TEXT,
    src_ip TEXT, src_port INTEGER, dst_ip TEXT, dst_port INTEGER,
    domain TEXT, url TEXT,
    event_type TEXT, severity TEXT, confidence FLOAT,
    detection_source TEXT, attack_technique TEXT, attack_tactic TEXT,
    raw_event TEXT, tags TEXT[], case_id TEXT
);
CREATE INDEX idx_events_timestamp ON normalized_events(timestamp);
CREATE INDEX idx_events_hostname   ON normalized_events(hostname);
CREATE INDEX idx_events_process    ON normalized_events(process_name);
CREATE INDEX idx_events_case       ON normalized_events(case_id);
```

### SQLite Schema (Graph + Detection + Playbook State)

```sql
CREATE TABLE entities (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,   -- host, user, process, file, network, domain, ip,
                          --   detection, artifact, incident, attack_technique,
                          --   firewall_zone, network_segment
    name TEXT NOT NULL,
    attributes JSON,
    case_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE edges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_type TEXT NOT NULL,
    source_id   TEXT NOT NULL,
    edge_type   TEXT NOT NULL,
    target_type TEXT NOT NULL,
    target_id   TEXT NOT NULL,
    properties  JSON,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source_type, source_id, edge_type, target_type, target_id)
);

CREATE TABLE detections (
    id TEXT PRIMARY KEY,
    rule_id TEXT NOT NULL,
    rule_name TEXT NOT NULL,
    severity TEXT NOT NULL,
    matched_event_ids TEXT NOT NULL,  -- JSON array
    attack_technique TEXT,
    attack_tactic TEXT,
    explanation TEXT,
    case_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE playbooks (
    playbook_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    trigger_conditions JSON,
    steps JSON,
    version TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE playbook_runs (
    run_id TEXT PRIMARY KEY,
    playbook_id TEXT NOT NULL,
    investigation_id TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    steps_completed JSON,
    analyst_notes TEXT
);
```

---

## Data Flow

### Malcolm Telemetry → Desktop

```
supportTAK-server (Ubuntu):
    IPFire syslog → Filebeat → Logstash → OpenSearch (malcolm_beats_syslog_*)
    Suricata EVE alerts → Logstash → OpenSearch (arkime_sessions3-*)

Desktop (every 30 seconds):
    MalcolmCollector → GET https://192.168.1.22:9200/_search →
        → ECS field normalization → NormalizedEvent →
        → DuckDB: INSERT normalized events
        → Chroma: embed event text
        → SQLite: INSERT entity edges
```

**Status as of 2026-04-17:**
- Collecting: syslog (22M+ docs), EVE alerts, EVE TLS, DNS, fileinfo, anomaly (Phase 31 complete)
- Zeek: LIVE — Netgear GS308E SPAN port active. Full network protocol logs (Phase 36 complete)
- MISP IOC sync: 4,568 IOCs on 6h cycle (Phase 50 complete)
- TheHive: auto-cases from detections (Phase 52 complete)

### File Ingestion

```
Raw file (EVTX/JSON/CSV) → Parser → Normalizer → IngestionLoader:
    ├→ DuckDB: INSERT normalized event rows (batched, deduplicated)
    ├→ Chroma: embed event text + metadata (model: mxbai-embed-large)
    ├→ SQLite: INSERT entity edges (process→user, process→file, etc.)
    └→ Detection trigger: run Sigma matchers against new events
```

### Analyst Query (RAG)

```
Question → POST /api/query/ask/stream →
    → Chroma: similarity search (top-10 relevant chunks)
    → DuckDB: structured context (related events, timeline)
    → Context assembly + injection scrub
    → Ollama /api/generate (stream=true, model=qwen3:14b)
    → Response with citations → Citation verification layer
    → SSE stream to dashboard
```

This is **analyst-initiated only**. There is no automatic triage loop. Phase 35 will add `POST /api/triage/run` and a background worker that calls AI on every new detection batch.

### Detection

```
On ingestion or POST /api/detect/run:
    → pySigma DuckDB backend: compile Sigma YAML → SQL WHERE clauses
    → Run compiled SQL against DuckDB events
    → Write detection records to SQLite
    → Write detection→event edges to SQLite
    → ATT&CK enrichment from Sigma tags
    [Phase 35: → POST /api/triage/run → AI analysis → DetectionRecord update]
```

### Graph Query

```
Analyst clicks entity →
    → GET /api/graph/entity/{id}?depth=2        (subgraph)
    → GET /api/graph/global                      (full graph)
    → GET /api/graph/{investigation_id}          (investigation subgraph)
    → SQLite: traverse edges from entity
    → DuckDB: fetch entity attributes
    → GraphView.svelte: Cytoscape.js fCoSE layout renders
    → Node tap → entity panel → "Investigate case" navigation
    → Two-click Dijkstra → attack path highlighted (thick red edges)
```

### Investigation Chat (AI Copilot)

```
Analyst types question →
    → POST /api/investigations/{id}/chat (SSE stream)
    → Chroma: similarity search (top-10 relevant events)
    → DuckDB: timeline + structured context
    → Injection scrub on question
    → Ollama /api/generate (qwen3:14b, stream=true)
    → SSE token stream → InvestigationView chat bubble
```

---

## AI Capabilities

| Capability | Status | Notes |
|-----------|--------|-------|
| RAG Q&A (QueryView) | Working | SSE streaming, citation verification |
| Investigation chat copilot | Working | Per-investigation context |
| LLM explanation (POST /api/explain) | Working | Detection/event explanations |
| triage.py build_prompt() | Working | Structured triage prompt from detection list |
| explain_engine.py | Working | Evidence context builder from detections |
| OllamaClient | Production-grade | Streaming, SHA-256 provenance, model drift detection, citation verification |
| Auto-triage loop | Working | POST /api/triage/run — background worker fires AI on every new detection batch (Phase 35) |
| Agentic investigation | Working | smolagents 7-tool pipeline, POST /api/investigate/auto (Phase 45) |
| bge-m3 reranker | Working | Cross-encoder reranking of RAG results at :8100 (Phase 54) |
| Analyst feedback classifier | Working | River online ML, TP/FP verdicts, k-NN similar cases (Phase 44) |
| Streaming behavioral profiles | Working | River entity anomaly scoring, score trend sparklines (Phase 42) |
| Privacy monitoring | Planned | Phase 53 — network privacy monitoring (not yet started) |

---

## Infrastructure — Four-Device Lab

| Node | Hardware | IP | Role |
|------|----------|----|------|
| Desktop | Core Ultra 9 285K · 96 GB DDR5 · RTX 5080 16 GB · 3.4 TB NVMe | 192.168.1.x | SOC Brain — all AI inference, detection, analysis |
| GMKtec N150 | N150 · 16 GB DDR5 | 192.168.1.22 | Malcolm NSM · MISP · TheHive · Cortex · SpiderFoot |
| IPFire | Embedded router | 192.168.1.1 | Firewall/router — syslog + Suricata EVE → Malcolm |
| Netgear GS308E | Managed switch | — | Port 1→5 SPAN tap for Zeek (active since Phase 36) |

## Malcolm NSM — Container Accounting

17 Malcolm containers run on the GMKtec box.

| Container | Status | Notes |
|-----------|--------|-------|
| OpenSearch | Active | Indexing syslog + EVE alerts + Zeek logs |
| Logstash | Active | Processing log pipelines |
| Filebeat | Active | Shipping logs |
| Arkime viewer | Active | Web UI for sessions |
| malcolm-api | Active | Malcolm API |
| Zeek | **Active** | Live Zeek flow logs via Netgear GS308E SPAN (Phase 36) |
| Arkime capture | Active | Packet capture from SPAN port |
| pcap-capture | Active | Packet capture (SPAN active) |
| Strelka (scanner, frontend, backend, redis, coordinator) | Running | File analysis — no active feed |
| NetBox | Running | Network documentation |
| Keycloak | Running | Auth (unused in current config) |
| freq-server | Running | Frequency analysis (feeds Zeek log enrichment) |

**SPAN port:** Netgear GS308E arrived 2026-04-10. Port 1→5 mirror active. Zeek producing live network protocol logs as of Phase 36.

---

## API Surface

### Implemented (v1.0 — v1.2)

```
GET  /health
GET  /openapi.json
GET  /docs

# Events
GET/POST /api/events
POST     /api/events/search
POST     /api/ingest
POST     /api/ingest/file
GET      /api/ingest/status/{job_id}

# Detection
POST /api/detect/run
GET  /api/detect

# Query / RAG
POST /api/query/ask/stream    (SSE)
POST /api/query               (non-streaming compat)

# Graph
GET  /api/graph/global
GET  /api/graph/{investigation_id}
GET  /api/graph/entity/{entity_id}
GET  /api/graph/entities
GET  /api/graph/traverse/{entity_id}
GET  /api/graph/case/{case_id}

# Investigations
GET/POST /api/investigations
GET      /api/investigations/{id}/timeline
POST     /api/investigations/{id}/chat     (SSE)
POST     /api/investigate
POST     /api/investigate/auto             (Phase 45 — agentic pipeline)

# Analysis
POST /api/score
GET  /api/top-threats
POST /api/explain
GET  /api/metrics
GET  /api/correlate
GET  /api/causality
POST /api/triage/run                       (Phase 35 — auto-triage background worker)

# Playbooks
GET/POST /api/playbooks
GET      /api/playbooks/{id}
GET      /api/playbooks/{id}/runs
POST     /api/playbooks/{id}/run/{investigation_id}
PATCH    /api/playbook-runs/{run_id}/step/{n}
PATCH    /api/playbook-runs/{run_id}/cancel
GET      /api/playbook-runs/{run_id}
GET      /api/playbook-runs/{run_id}/stream    (SSE)

# Operators / RBAC
GET/POST         /api/operators
GET/PATCH/DELETE /api/operators/{id}

# Workflow
GET/POST /api/recommendations
POST     /api/receipts
GET      /api/export
GET      /api/telemetry

# Malcolm / Firewall
GET /api/firewall/status

# Threat Hunting (Phase 32)
POST /api/hunts
GET  /api/hunts

# Threat Intelligence (Phase 33)
GET  /api/intel/iocs
POST /api/intel/check

# Asset Inventory (Phase 34)
GET  /api/assets

# Analyst Feedback Loop (Phase 44)
POST /api/feedback
GET  /api/feedback/similar
GET  /api/anomaly/score
GET  /api/anomaly/trend

# EVTX Threat Hunting (Phases 48-49)
POST /api/hayabusa/scan
POST /api/chainsaw/scan

# MISP Integration (Phase 50)
GET  /api/misp/iocs
POST /api/misp/sync

# SpiderFoot OSINT (Phase 51)
POST /api/spiderfoot/scan
GET  /api/spiderfoot/scan/{scan_id}

# TheHive Case Management (Phase 52)
POST /api/thehive/cases
GET  /api/thehive/cases

# Reranker (Phase 54)
POST /api/rerank
```

### Planned (v1.2+)

```
# Phase 53 — Network privacy monitoring (not yet started)
```

---

## Dashboard Views (v1.2)

| View | File | Status |
|------|------|--------|
| Detections | `DetectionsView.svelte` | Ready — Sigma alert feed, ATT&CK tactic/technique, Sigma v2 CORR chips |
| Investigation | `InvestigationView.svelte` | Ready — timeline, attack chain, AI chat copilot, "Run Playbook", SpiderFoot OSINT, TheHive case push |
| Attack Graph | `GraphView.svelte` | Ready — Cytoscape.js fCoSE, risk-scored nodes, Dijkstra paths |
| Playbooks | `PlaybooksView.svelte` | Ready — 30+ playbook library (CISA/NIST/DART/community); step execution SSE |
| Events | `EventsView.svelte` | Ready — normalized event table, search |
| Query | `QueryView.svelte` | Ready — SSE streaming RAG with bge-m3 + reranker |
| Ingest | `IngestView.svelte` | Ready — file upload, Hayabusa/Chainsaw scan triggers |
| Reports | `ReportsView.svelte` | Ready — PDF, MITRE heatmap, TheHive export |
| Settings / Operators | `SettingsView.svelte` | Ready — operator CRUD, RBAC |
| Assets | `AssetsView.svelte` | Ready — auto-derived asset inventory from telemetry (Phase 34) |
| Threat Intel | `ThreatIntelView.svelte` | Ready — MISP IOC feed, IOC matching, geolocated threat map (Phase 33/50) |
| Hunting | `HuntingView.svelte` | Ready — HuntingView API, live hunt queries, Hayabusa/Chainsaw integration (Phase 32/48/49) |

**State management:** Svelte 5 runes only — `$state()`, `$derived()`, `$effect()`. No writable stores.

**Navigation state** lifted to `App.svelte`:
- `graphFocusEntityId` — entity to centre when switching to Graph view
- `handleOpenInGraph(entityId)` — InvestigationView → Graph
- `handleNavigateInvestigation(caseId)` — Graph → InvestigationView
- `handleRunPlaybook(investigationId)` — InvestigationView → PlaybooksView

---

## Internal Boundaries

| Boundary | Protocol | Notes |
|----------|----------|-------|
| Dashboard ↔ FastAPI | HTTP REST + SSE | JSON over HTTPS via Caddy |
| FastAPI ↔ Ollama | HTTP REST to localhost:11434 | httpx async, chunked streaming |
| FastAPI ↔ Reranker | HTTP REST to localhost:8100 | Cross-encoder reranking service (Phase 54) |
| FastAPI ↔ DuckDB | In-process Python API | No network. Single writer queue + read-only pool. `WEB_CONCURRENCY=1` enforced. |
| FastAPI ↔ Chroma | HTTP to 192.168.1.22:8200 | Remote HttpClient mode (Phase 54). No LangChain wrapper. |
| FastAPI ↔ SQLite | In-process Python API | WAL mode |
| FastAPI ↔ Malcolm/OpenSearch | HTTPS REST to 192.168.1.22:9200 | MalcolmCollector polls every 30s; optional |
| FastAPI ↔ MISP | HTTPS REST to 192.168.1.22:8443 | pymisp client; 6h IOC sync cycle (Phase 50) |
| FastAPI ↔ TheHive | HTTP to 192.168.1.22:9000 | thehive4py; auto-case creation from detections (Phase 52) |
| FastAPI ↔ Cortex | HTTP to 192.168.1.22:9001 | MISP connector; analyser triggers (Phase 52) |
| FastAPI ↔ SpiderFoot | HTTP to 192.168.1.22:9002 | OSINT scan API (Phase 51) |
| FastAPI ↔ Hayabusa/Chainsaw | Subprocess | Binary invoked on EVTX files (Phases 48–49) |
| Caddy ↔ FastAPI | HTTP reverse proxy | Caddy terminates TLS, proxies to :8001 |
| Desktop ↔ GMKtec | LAN (192.168.1.0/24) | Malcolm telemetry + MISP + TheHive + Chroma. GMKtec never receives AI output. |

---

## Security Architecture

### Auth

`AUTH_TOKEN` must be 32+ chars (or `dev-only-bypass` for local dev). `model_validator(mode="after")` in `Settings` rejects weak tokens at startup — fail-fast before the server accepts any connections.

### DuckDB Lockdown

`SET enable_external_access = false` applied to every connection at init. Disables `COPY TO 'http://...'`, `LOAD 'httpfs'`, and all network-facing DuckDB extensions. Blocks SQL-injection-to-exfiltration attack chain.

### Prompt Security

Evidence in system turn, question in user turn. `_normalize_for_scrub()` applies Unicode NFC + base64 decode heuristic before regex pattern matching. `body.question` scrubbed before prompt construction.

### Ollama Model Integrity

`verify_model_digest()` called at startup. `OLLAMA_ENFORCE_DIGEST=True` blocks startup on model mismatch. Default is warn-only — logs actual digest for audit trail.

### Caddy Supply Chain

`docker-compose.yml` pins Caddy image by `sha256:b4e3952384eb...` (fixed in Phase 30). Not just by tag.

---

## Component Decisions

| Component | Decision | Rationale |
|-----------|----------|-----------|
| ollama/ollama | Native Windows | Direct CUDA/Vulkan. No WSL2 complexity. |
| chroma-core/chroma | Remote HttpClient (:8200 on GMKtec) | Offloads vector storage to GMKtec. Phase 54. |
| pySigma + custom DuckDB backend | Custom backend | No mature DuckDB backend exists upstream. |
| cytoscape-fcose | Attack graph layout | Force-directed with compound graph support. |
| GMKtec Malcolm box | Dumb pipe + services host | 20-30x throughput disadvantage vs desktop GPU. Hosts MISP/TheHive/Cortex/SpiderFoot. See ADR-030. |
| Zeek telemetry | Live (Phase 36) | Netgear GS308E SPAN active. Zeek producing logs. |
| Auto-triage | Working (Phase 35) | Background worker + POST /api/triage/run with full audit logging and analyst override. |
| MISP | Docker on GMKtec | Threat intelligence platform. 4,568 IOCs via pymisp. Phase 50. |
| TheHive + Cortex | Docker on GMKtec | Case management + analyser orchestration. Phase 52. |
| SpiderFoot | Docker on GMKtec | OSINT investigation. Phase 51. |
| Hayabusa + Chainsaw | Subprocess binaries | Fast EVTX threat hunting. No JVM or extra services. Phases 48-49. |
| smolagents | Embedded in-process | Agentic investigation without LangChain overhead. Phase 45. |
| River | Embedded in-process | Online ML for analyst feedback loop. Lightweight; no sklearn/tensorflow. Phase 44. |
| BAAI/bge-reranker-v2-m3 | Separate CUDA service | Cross-encoder reranking improves RAG precision. Phase 54. |
| Wazuh | Rejected | 8+ vCPU Java fleet SIEM; zero unique value for single desktop. |
| Neo4j | Rejected | JVM server, 4+ GB RAM; SQLite edge tables sufficient at desktop scale. |
| PostgreSQL/Kafka/Elastic | Rejected | None justified for single-user desktop analytics. |

---

## LLM Strategy

| Model | VRAM | Role |
|-------|------|------|
| `qwen3:14b` (Q8) | ~14 GB | Primary: analyst Q&A, triage, correlation, investigation chat |
| `deepseek-r1:14b` (Q4_K_M) | ~8 GB | Alternative: explicit chain-of-thought reasoning |
| `bge-m3` (via Ollama) | ~1.5 GB | Embeddings: multilingual, replaces mxbai-embed-large (Phase 54) |
| `BAAI/bge-reranker-v2-m3` | ~1 GB CUDA | Reranker: cross-encoder RAG re-ranking at :8100 (Phase 54) |

**Rule:** Never load two reasoning models simultaneously. Embedding model loads/unloads automatically via Ollama API. Reranker runs as a separate persistent service on the desktop (requires manual start after reboot).

---

## Anti-Patterns (Explicitly Rejected)

| Anti-Pattern | Reason Rejected |
|---|---|
| Microservice-ifying the backend | Single desktop, one user. Network overhead = waste. |
| LangChain chains | Deprecated upstream. Direct httpx + LangGraph 1.0 used instead. |
| Storing everything as vectors | Structured data (IPs, timestamps, PIDs) needs SQL, not cosine similarity. |
| Docker for Ollama | WSL2 GPU passthrough adds complexity; native CUDA wins. |
| AI on Ubuntu box | 20-30x slower. Adds interpretation layer between raw data and analyst. |
| PostgreSQL/Neo4j/Kafka/Elastic | None justified for single-desktop single-analyst scope. |
| Auto-triage without transparency | Phase 35 adds it with full audit logging and analyst override capability. |

---

## Known Tech Debt (Non-Blocking)

| Item | Severity | Notes |
|------|----------|-------|
| Dead code: `getGraph()`, `getGraphCorrelate()` in api.ts + ThreatGraph.svelte | Low | Unreachable from active view tree. No runtime risk. |
| Detect endpoint pagination mismatch | Low | P28-T05: api.ts sends page/page_size, backend expects limit/offset. Default path works. No UI code exercises custom pagination. |
| Phase 11 VERIFICATION.md stale | Low | Gap was resolved in Phase 30 (Caddy digest pinned). VERIFICATION.md not re-run. |
| 21 phases with partial Nyquist validation | Low | Test-first adopted from Phase 23.5 onward. Earlier phases have retrospective coverage. |
| Phase 22/30 UI items (confidence badge, citation tags) | Low | human_needed; requires active AI Copilot session. Code confirmed correct by inspection. |
