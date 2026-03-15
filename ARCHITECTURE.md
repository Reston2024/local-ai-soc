# ARCHITECTURE.md
# AI-SOC-Brain — Local Windows Desktop AI Cybersecurity Brain

**Version:** 1.0 | **Date:** 2026-03-15 | **Status:** LOCKED

---

## System Overview

A single-analyst, local-first cybersecurity investigation workstation. No cloud. No external services. All inference, storage, and visualization runs on the Windows desktop.

```
                         Browser (https://localhost)
                                  │
                    ┌─────────────▼─────────────┐
                    │     Caddy (Docker)          │  TLS termination, reverse proxy
                    └─────────────┬─────────────┘
                                  │ HTTP  localhost:8000
                    ┌─────────────▼─────────────────────────────┐
                    │          FastAPI Backend                    │  native Python 3.12
                    │                                            │
                    │  /health  /query  /ingest  /detect         │
                    │  /graph   /events /export                  │
                    └──┬─────────┬──────────┬──────────┬────────┘
                       │         │          │          │
               HTTP REST      embed       SQL        SQL
                       │         │          │          │
              ┌────────▼┐  ┌────▼────┐  ┌──▼───┐  ┌──▼──────┐
              │ Ollama  │  │ Chroma  │  │DuckDB│  │ SQLite  │
              │ :11434  │  │ embed   │  │events│  │  graph  │
              │ native  │  │ persist │  │ store│  │  edges  │
              └─────────┘  └─────────┘  └──────┘  └─────────┘
              qwen3:14b
              mxbai-embed-large
```

**Total running processes:** Ollama (native Windows service), FastAPI/Uvicorn (native Python), Caddy (Docker container)

---

## Layer Definitions

| Layer | Technology | Runtime | Justification |
|-------|-----------|---------|---------------|
| **LLM Inference** | Ollama 0.13+ | Native Windows | Direct CUDA to RTX 5080. Docker GPU passthrough adds WSL2 complexity for <5% perf gain. |
| **Backend API** | FastAPI 0.135 + Uvicorn 0.41 | Native Python 3.12 | In-process access to all embedded DBs. Async SSE/WebSocket for LLM streaming. Best SecOps/ML ecosystem. |
| **Structured Storage** | DuckDB 1.5.0 | Embedded in-process | Columnar analytics, 24-core parallel, CSV/JSON/Parquet native reads. Single-writer + read-only pool. |
| **Vector Storage** | Chroma (PersistentClient) | Embedded in-process | Hybrid BM25+semantic search. No external server. Pinned version. Native client only (no LangChain wrapper). |
| **Graph/State Storage** | SQLite WAL | Embedded in-process | Graph edge tables, detection state, case metadata. Battle-tested, zero-config, WAL concurrent reads. |
| **HTTPS Proxy** | Caddy 2.9 | Docker (~40MB) | Auto-TLS for localhost. Only container needed. |
| **Dashboard** | Svelte 5 SPA | Static files | 39% faster than React 19, 2.5x smaller bundles. Cytoscape.js (graph), D3.js (timeline). |
| **Detection** | pySigma + custom DuckDB backend | Embedded in-process | Sigma YAML → DuckDB SQL. Field mapping pipeline. |
| **Telemetry** | osquery (Phase 6) | Native Windows | SQL-powered host instrumentation. |

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
└── graph.sqlite3          # Entity nodes + edges + detection state (WAL)
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
CREATE INDEX idx_events_hostname ON normalized_events(hostname);
CREATE INDEX idx_events_process ON normalized_events(process_name);
CREATE INDEX idx_events_case ON normalized_events(case_id);
```

### SQLite Schema (Graph + Detection State)

```sql
-- Entity nodes
CREATE TABLE entities (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,           -- host, user, process, file, network, domain, ip, detection, artifact, incident, attack_technique
    name TEXT NOT NULL,
    attributes JSON,
    case_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Relationship edges
CREATE TABLE edges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_type TEXT NOT NULL,
    source_id TEXT NOT NULL,
    edge_type TEXT NOT NULL,      -- executed_by, ran_on, accessed, connected_to, resolved_to, triggered, maps_to, part_of
    target_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    properties JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source_type, source_id, edge_type, target_type, target_id)
);
CREATE INDEX idx_edges_source ON edges(source_type, source_id);
CREATE INDEX idx_edges_target ON edges(target_type, target_id);

-- Detection records
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
```

---

## Data Flow

### Evidence Ingestion
```
Raw file (EVTX/JSON/CSV) → Parser → Normalizer → Loader:
    └→ DuckDB: INSERT normalized event rows (batched, deduplicated)
    └→ Chroma: embed event text + metadata (model: mxbai-embed-large)
    └→ SQLite: INSERT entity edges (process→user, process→file, etc.)
    └→ Detection trigger: run Sigma matchers against new events
```

### Analyst Query (RAG)
```
Question → POST /query →
    → Chroma: similarity search (top-10 relevant chunks)
    → DuckDB: structured context (related events, timeline)
    → Context assembly
    → Ollama /api/generate (stream=true, model=qwen3:14b)
    → Response with citations → Citation verification layer
    → SSE stream to dashboard
```

### Detection
```
On ingestion (or POST /detect/run):
    → pySigma DuckDB backend: compile Sigma YAML → SQL WHERE clauses
    → Run compiled SQL against DuckDB events
    → Write detection records to SQLite
    → Write detection→event edges to SQLite
    → ATT&CK enrichment from Sigma tags
```

### Graph Query
```
Analyst clicks entity →
    → GET /graph/entity/{id}?depth=2
    → SQLite: traverse edges from entity
    → DuckDB: fetch entity attributes
    → Build subgraph (nodes + edges + attributes)
    → Cytoscape.js renders in dashboard
```

---

## Component Decisions

| Component | Decision | Phase | Rationale |
|-----------|----------|-------|-----------|
| ollama/ollama | **USE NOW** | 1 | Core LLM runtime, native GPU |
| chroma-core/chroma | **USE NOW** | 1 | Embedded vector store |
| langchain-ai/langgraph | **USE NOW** | 3 | RAG orchestration, human-in-the-loop |
| SigmaHQ/sigma + pySigma + sigma-cli | **USE NOW** | 3 | Detection rule ecosystem |
| osquery/osquery | **USE NOW** | 6 | Endpoint telemetry |
| open-webui/open-webui | **DEFER** | 6+ | Optional companion chat UI |
| Velocidex/velociraptor | **DEFER** | if multi-host | Fleet tool, overkill single desktop |
| wazuh/wazuh | **REJECT** | — | 8+ vCPU Java fleet SIEM, zero unique value |

---

## LLM Strategy

| Model | VRAM | Role |
|-------|------|------|
| `qwen3:14b` (Q8) | ~14 GB | Primary: analyst Q&A, triage, correlation |
| `deepseek-r1:14b` (Q4_K_M) | ~8 GB | Alternative: explicit chain-of-thought reasoning |
| `mxbai-embed-large` | ~1.2 GB | Embeddings: MTEB retrieval 64.68 |

**Rule:** Never load two reasoning models simultaneously. Embedding model loads/unloads automatically via Ollama API.

---

## Internal Boundaries

| Boundary | Protocol | Notes |
|----------|----------|-------|
| Dashboard ↔ FastAPI | HTTP REST + SSE + WebSocket | JSON over HTTPS via Caddy |
| FastAPI ↔ Ollama | HTTP REST to localhost:11434 | httpx async, chunked streaming |
| FastAPI ↔ DuckDB | In-process Python API | No network. Single writer + read-only pool. |
| FastAPI ↔ Chroma | In-process Python API | PersistentClient, no HTTP mode |
| FastAPI ↔ SQLite | In-process Python API | WAL mode |
| Caddy ↔ FastAPI | HTTP reverse proxy | Caddy terminates TLS, proxies to :8000 |
| Docker containers ↔ Ollama | http://host.docker.internal:11434 | OLLAMA_HOST=0.0.0.0 required |

---

## Anti-Patterns (Explicitly Rejected)

| Anti-Pattern | Reason Rejected |
|---|---|
| Microservice-ifying the backend | Single desktop, one user. Network overhead = pure waste. |
| LangChain chains | Deprecated upstream. LangGraph 1.0 is the replacement. |
| Storing everything as vectors | Structured data (IPs, timestamps, PIDs) needs SQL, not cosine similarity. |
| Building dashboard before APIs | APIs must be stable before UI is built against them. |
| Monolithic prompt templates | Each use-case (triage, hunt, summary) has different context and output needs. |
| Docker for Ollama | WSL2 GPU passthrough adds complexity; native gets direct CUDA. |
| PostgreSQL/Neo4j/Kafka/Elastic | None justified for single-desktop single-analyst scope. |
