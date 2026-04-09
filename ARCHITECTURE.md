# ARCHITECTURE.md
# AI-SOC-Brain — Local AI Cybersecurity Investigation Platform

**Version:** 1.31 | **Date:** 2026-04-09 | **Status:** v1.0 complete, v1.1 executing (Phases 31-36)

---

## System Overview

A single-analyst, local-first cybersecurity investigation platform. Two physical machines. The Ubuntu box is a dumb pipe — raw telemetry collection and indexing only. All AI inference, detection, correlation, and analysis runs on the Windows desktop.

```
  supportTAK-server (Ubuntu, GMKtec N150, 192.168.1.22)
  ┌──────────────────────────────────────────────────┐
  │  Malcolm NSM (17 containers)                     │
  │  ├─ OpenSearch  (7.4 GB RAM) — log indexing      │
  │  ├─ Logstash   — log processing pipeline         │
  │  ├─ Filebeat   — log shipping                    │
  │  ├─ Arkime     — network session indexing        │
  │  └─ 13 idle containers (pcap-capture, Zeek,      │
  │       Strelka, NetBox, Keycloak, etc.)            │
  │       ^ Idle because there is no SPAN port.       │
  │         Zeek produces 0 logs.                     │
  └─────────────────┬────────────────────────────────┘
                    │ syslog + EVE JSON + beats
                    │ (22M+ syslog, 71K alerts so far)
                    ▼
  Desktop (Windows 11, Intel Core Ultra 9 285K, RTX 5080 16 GB)
  ┌──────────────────────────────────────────────────────────────┐
  │  Browser (http://localhost:5173 dev | https://localhost prod) │
  │                          │                                    │
  │             ┌────────────▼────────────┐                      │
  │             │   Caddy (Docker)         │  TLS termination     │
  │             └────────────┬────────────┘                      │
  │                          │ HTTP  localhost:8000               │
  │             ┌────────────▼──────────────────────────┐        │
  │             │         FastAPI Backend                 │        │
  │             │                                        │        │
  │             │  /health  /api/events  /api/ingest     │        │
  │             │  /api/detect  /api/graph  /api/query   │        │
  │             │  /api/investigate  /api/investigations │        │
  │             │  /api/playbooks  /api/operators        │        │
  │             │  /api/recommendations  /api/receipts   │        │
  │             └──┬──────────┬──────────────┬──────────┘        │
  │                │          │              │                    │
  │        HTTP REST      embed/SQL         SQL                   │
  │                │          │              │                    │
  │       ┌────────▼┐   ┌────▼────┐   ┌────▼─────────┐          │
  │       │ Ollama  │   │ Chroma  │   │  DuckDB │SQLite│         │
  │       │ :11434  │   │ embed   │   │  events │graph │         │
  │       │ native  │   │ persist │   │ columnar│edges │         │
  │       └─────────┘   └─────────┘   └──────────────┘          │
  │       qwen3:14b                                               │
  │       mxbai-embed-large                                       │
  │       50-80+ tok/s GPU (Blackwell sm_120)                     │
  └──────────────────────────────────────────────────────────────┘
```

**Key constraint:** The Ubuntu box does NOT do AI. The 20-30x GPU throughput advantage on the desktop makes inference there the only rational choice. See ADR-030.

---

## Layer Definitions

| Layer | Technology | Runtime | Version | Justification |
|-------|-----------|---------|---------|---------------|
| **LLM Inference** | Ollama + qwen3:14b | Native Windows | 0.18.2 | Direct CUDA to RTX 5080. Docker GPU passthrough adds WSL2 complexity for negligible gain. |
| **Embeddings** | mxbai-embed-large | Via Ollama | ID: 468836162de7 | MTEB retrieval 64.68. Loads/unloads automatically via Ollama API. |
| **Backend API** | FastAPI + Uvicorn | Native Python 3.12 | 0.115.12 / 0.34.3 | In-process access to all embedded DBs. Async SSE/WebSocket for LLM streaming. |
| **Structured Storage** | DuckDB | Embedded in-process | 1.3.0 | Columnar analytics, 24-core parallel, CSV/JSON/Parquet native reads. |
| **Vector Storage** | Chroma PersistentClient | Embedded in-process | 1.5.5 | Hybrid BM25+semantic search. No HTTP mode. No LangChain wrapper. |
| **Graph/State Storage** | SQLite WAL | Embedded in-process | stdlib | Graph edges, detection state, case metadata, playbook runs. |
| **HTTPS Proxy** | Caddy 2.9-alpine | Docker (~40MB) | sha256:b4e39523... | Auto-TLS for localhost. Only container on desktop. |
| **Dashboard** | Svelte 5 SPA | Static files | ^5.28.0 | Runes-based reactivity. Cytoscape.js + fCoSE, D3.js. |
| **Detection** | pySigma + custom DuckDB backend | Embedded in-process | 1.2.0 | Sigma YAML → DuckDB SQL. Custom field mapping pipeline. |
| **NSM Collection** | Malcolm (Ubuntu box) | Docker (17 containers) | Latest | Dumb pipe only. Collects and indexes; does not analyze. |

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

**Honest status as of 2026-04-09:**
- Collecting: syslog (22M+ docs), EVE alerts (71K docs)
- NOT collecting: EVE TLS (156K docs), DNS (71K), fileinfo (6K), anomaly (1K) — Phase 31 fixes this
- Zeek: 0 docs — no SPAN port. Requires managed switch hardware.

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

## AI Capabilities — Honest Assessment

| Capability | Status | Notes |
|-----------|--------|-------|
| RAG Q&A (QueryView) | Working | SSE streaming, citation verification |
| Investigation chat copilot | Working | Per-investigation context |
| LLM explanation (POST /api/explain) | Working | Detection/event explanations |
| triage.py build_prompt() | Working | Structured triage prompt from detection list |
| explain_engine.py | Working | Evidence context builder from detections |
| OllamaClient | Production-grade | Streaming, SHA-256 provenance, model drift detection, citation verification |
| **Auto-triage loop** | **NOT YET WIRED** | POST /api/detect/run fires Sigma, saves DetectionRecords — does NOT call AI. Phase 35 closes this gap. |

---

## Malcolm Theater — Honest Container Accounting

17 Malcolm containers run on the Ubuntu box. Most produce nothing useful without a PCAP source.

| Container | Status | Reason |
|-----------|--------|--------|
| OpenSearch | Active | Indexing syslog + EVE alerts |
| Logstash | Active | Processing log pipelines |
| Filebeat | Active | Shipping logs |
| Arkime viewer | Active | Web UI for sessions |
| malcolm-api | Active | Malcolm API |
| Arkime capture | Idle | No SPAN port → no packets |
| pcap-capture | Idle | No SPAN port |
| Zeek | Idle | 0 logs — no packet source |
| Strelka (scanner, frontend, backend, redis, coordinator) | Idle | No files to scan without PCAP |
| NetBox | Running | Network documentation, no active population |
| Keycloak | Running | Auth (unused in current config) |
| freq-server | Running | Frequency analysis (unused without Zeek) |

**Root cause:** No managed switch with SPAN/mirror port. Hardware cost: ~$50-80. Phase 36 is blocked on this.

**RAM cost of idle containers:** ~630 MB wasted. Accepted trade-off — Malcolm is the fastest path to Zeek telemetry once hardware arrives.

---

## API Surface

### Implemented (v1.0)

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

# Analysis
POST /api/score
GET  /api/top-threats
POST /api/explain
GET  /api/metrics
GET  /api/correlate
GET  /api/causality

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
```

### Planned (v1.1)

```
POST /api/hunts           (Phase 32 — HuntingView backend)
GET  /api/hunts           (Phase 32)
GET  /api/intel/iocs      (Phase 33 — IOC matching)
POST /api/intel/check     (Phase 33)
GET  /api/assets          (Phase 34 — auto-derived from telemetry)
POST /api/triage/run      (Phase 35 — auto-triage background worker)
```

---

## Dashboard Views (v1.0)

| View | File | Status |
|------|------|--------|
| Detections | `DetectionsView.svelte` | Ready — Sigma alert feed, ATT&CK tactic/technique |
| Investigation | `InvestigationView.svelte` | Ready — timeline, attack chain, AI chat copilot, "Run Playbook" |
| Attack Graph | `GraphView.svelte` | Ready — Cytoscape.js fCoSE, risk-scored nodes, Dijkstra paths |
| Playbooks | `PlaybooksView.svelte` | Ready — library browser (MODE A) + step execution (MODE B) |
| Events | `EventsView.svelte` | Ready — normalized event table, search |
| Query | `QueryView.svelte` | Ready — SSE streaming RAG |
| Ingest | `IngestView.svelte` | Ready — file upload, progress polling |
| Reports | `ReportsView.svelte` | Ready — PDF, MITRE heatmap, TheHive export |
| Settings / Operators | `SettingsView.svelte` | Ready — operator CRUD, RBAC |
| Assets | `AssetsView.svelte` | Partial — "Discover Assets" permanently disabled (Phase 34) |
| Threat Intel | `ThreatIntelView.svelte` | Stub — fake feed data, "BETA" badge (Phase 33) |
| Hunting | `HuntingView.svelte` | Stub — all buttons disabled (Phase 32) |

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
| FastAPI ↔ DuckDB | In-process Python API | No network. Single writer queue + read-only pool. `WEB_CONCURRENCY=1` enforced. |
| FastAPI ↔ Chroma | In-process Python API | PersistentClient, no HTTP mode, no LangChain wrapper |
| FastAPI ↔ SQLite | In-process Python API | WAL mode |
| FastAPI ↔ Malcolm/OpenSearch | HTTPS REST to 192.168.1.22:9200 | MalcolmCollector polls every 30s; optional |
| Caddy ↔ FastAPI | HTTP reverse proxy | Caddy terminates TLS, proxies to :8000 |
| Desktop ↔ Ubuntu | LAN (192.168.1.0/24) | Malcolm telemetry only. Ubuntu never receives AI output. |

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
| ollama/ollama | Native Windows | Direct CUDA. No WSL2 complexity. |
| chroma-core/chroma | Embedded PersistentClient | No server process. Version pinned. |
| pySigma + custom DuckDB backend | Custom backend | No mature DuckDB backend exists upstream. |
| cytoscape-fcose | Attack graph layout | Force-directed with compound graph support. |
| Ubuntu Malcolm box | Dumb pipe only | 20-30x throughput disadvantage vs desktop GPU. See ADR-030. |
| Zeek telemetry | Deferred | No SPAN port. Zeek containers produce 0 logs. See ADR-031. |
| Auto-triage | Not yet wired | Phase 35. Documents the gap honestly. See ADR-033. |
| Wazuh | Rejected | 8+ vCPU Java fleet SIEM; zero unique value for single desktop. |
| Neo4j | Rejected | JVM server, 4+ GB RAM; SQLite edge tables sufficient at desktop scale. |
| PostgreSQL/Kafka/Elastic | Rejected | None justified for single-user desktop analytics. |

---

## LLM Strategy

| Model | VRAM | Role |
|-------|------|------|
| `qwen3:14b` (Q8) | ~14 GB | Primary: analyst Q&A, triage, correlation, investigation chat |
| `deepseek-r1:14b` (Q4_K_M) | ~8 GB | Alternative: explicit chain-of-thought reasoning |
| `mxbai-embed-large` | ~1.2 GB | Embeddings: MTEB retrieval 64.68 |

**Rule:** Never load two reasoning models simultaneously. Embedding model loads/unloads automatically via Ollama API.

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
