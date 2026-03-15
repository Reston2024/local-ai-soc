# Architecture Research

**Domain:** Local Windows desktop AI cybersecurity investigation platform
**Researched:** 2026-03-14
**Confidence:** HIGH

## System Overview

```
                         Browser (localhost:443)
                                |
                         [HTTPS / WSS]
                                |
                    +-----------+-----------+
                    |     Caddy (Docker)    |  reverse proxy, TLS termination
                    +-----------+-----------+
                                |
                         [HTTP / WS]
                    localhost:8000
                                |
         +----------------------+----------------------+
         |              FastAPI Backend                 |  native Python process
         |                                             |
         |  /query   /ingest   /detect   /graph        |
         |  /events  /health   /ws/stream              |
         +--+--------+--------+--------+-----------+---+
            |        |        |        |           |
      [HTTP REST]  [embed]  [SQL]   [SQL]    [HTTP REST]
            |        |        |        |           |
   +--------+  +-----+--+  +-+----+ +-+------+  +-+----------+
   | Ollama |  | Chroma  |  |DuckDB| |SQLite  |  | osquery    |
   | native |  | embed   |  |events| |graph   |  | native     |
   | :11434 |  | persist |  |store | |edges   |  | :7727 (?)  |
   +--------+  +---------+  +------+ +--------+  +------------+
```

### Layer Summary

| Layer | Components | Runtime |
|-------|-----------|---------|
| **Presentation** | Browser dashboard (React/Svelte SPA) | Served as static files via Caddy or FastAPI |
| **TLS Termination** | Caddy reverse proxy | Docker container |
| **API / Orchestration** | FastAPI backend | Native Python (uv) |
| **AI Inference** | Ollama (LLM + embedding models) | Native Windows process |
| **Vector Retrieval** | Chroma (PersistentClient, embedded mode) | In-process with FastAPI |
| **Structured Storage** | DuckDB (events/evidence), SQLite (graph edges, config) | In-process with FastAPI |
| **Detection** | pySigma rule compiler + Python matching engine | In-process with FastAPI |
| **Correlation / Graph** | Python graph builder over DuckDB/SQLite edge tables | In-process with FastAPI |
| **Ingestion** | Python pipeline (parsers, normalizers, loaders) | In-process with FastAPI (async tasks) |
| **Host Telemetry** | osquery | Native Windows process |

## Component Responsibilities

| Component | Responsibility | Owns | Talks To |
|-----------|---------------|------|----------|
| **Caddy** | TLS termination, HTTPS for localhost, reverse proxy to FastAPI | TLS certificates, routing rules | FastAPI (upstream) |
| **FastAPI Backend** | API gateway, orchestration, business logic, WebSocket streaming | All API contracts, prompt orchestration | Ollama, Chroma, DuckDB, SQLite, osquery |
| **Ollama** | LLM inference and embedding generation | Model weights, VRAM management | Nothing (passive server) |
| **Chroma** | Vector storage and similarity search over evidence/notes | Vector indices, embedding persistence | Nothing (embedded library) |
| **DuckDB** | Structured event storage, analytical queries, evidence metadata | Normalized event tables, case metadata | Nothing (embedded library) |
| **SQLite** | Graph edge tables, detection state, configuration | Entity-relationship edges, detection results | Nothing (embedded library) |
| **pySigma Engine** | Compile Sigma rules to Python-native detection functions | Compiled rule cache, pipeline configs | DuckDB (reads events to match) |
| **Ingestion Pipeline** | Parse, normalize, and load evidence from files/osquery | Parser registry, normalization schema | DuckDB (write), Chroma (write), SQLite (write edges) |
| **Graph Layer** | Build and query entity-relationship graphs from stored data | Graph query interface, traversal logic | SQLite (edges), DuckDB (entity attributes) |
| **Dashboard** | Visual investigation surface for analyst | UI state, visualization rendering | FastAPI (HTTP + WebSocket) |
| **osquery** | Live host telemetry collection | Host process/network/file snapshots | FastAPI (polled via osqueryi or thrift) |

## Recommended Project Structure

```
AI-SOC-Brain/
├── backend/                    # FastAPI application
│   ├── main.py                 # App factory, lifespan, middleware
│   ├── api/                    # Route modules
│   │   ├── query.py            # /query - analyst Q&A with RAG
│   │   ├── ingest.py           # /ingest - file upload and ingestion triggers
│   │   ├── detect.py           # /detect - detection status, rule management
│   │   ├── graph.py            # /graph - entity graph queries
│   │   ├── events.py           # /events - event search, timeline
│   │   └── health.py           # /health - component health checks
│   ├── services/               # Business logic layer
│   │   ├── llm.py              # Ollama client wrapper (streaming, retries)
│   │   ├── retrieval.py        # Chroma search + context assembly
│   │   ├── detection.py        # pySigma rule execution orchestration
│   │   ├── correlation.py      # Event clustering, relatedness scoring
│   │   └── graph_builder.py    # Entity graph construction and queries
│   ├── models/                 # Pydantic schemas (request/response/internal)
│   ├── stores/                 # Data access layer
│   │   ├── duckdb_store.py     # DuckDB connection, event read/write
│   │   ├── chroma_store.py     # Chroma collection management
│   │   └── sqlite_store.py     # SQLite graph edge tables
│   └── core/                   # Config, logging, dependencies
│       ├── config.py           # Settings from .env
│       ├── logging.py          # Structured logging setup
│       └── deps.py             # FastAPI dependency injection
├── ingestion/                  # Parsers and normalizers
│   ├── parsers/                # Format-specific parsers
│   │   ├── evtx.py             # Windows EVTX log parser
│   │   ├── json_ndjson.py      # JSON/NDJSON parser
│   │   ├── csv_parser.py       # CSV parser
│   │   ├── osquery.py          # osquery result parser
│   │   ├── sigma_rules.py      # Sigma YAML rule ingestion
│   │   └── ioc_lists.py        # IOC hash/URL/domain lists
│   ├── normalizer.py           # Unified event schema normalization
│   └── loader.py               # Write to DuckDB + embed to Chroma
├── detections/                 # Sigma rules and detection logic
│   ├── rules/                  # Sigma YAML rule files
│   ├── pipelines/              # pySigma pipeline configs
│   ├── compiler.py             # Sigma-to-Python compilation
│   └── matcher.py              # Run compiled detections against events
├── correlation/                # Correlation and clustering
│   ├── clustering.py           # Event clustering algorithms
│   ├── scoring.py              # Relatedness scoring
│   └── aggregation.py          # Alert aggregation for related events
├── graph/                      # Graph layer
│   ├── schema.py               # Entity and edge type definitions
│   ├── builder.py              # Graph construction from events/detections
│   ├── query.py                # Graph traversal and path queries
│   └── layout.py               # Graph layout hints for dashboard
├── prompts/                    # LLM prompt templates
│   ├── analyst_qa.py           # Analyst question answering
│   ├── triage.py               # Triage assessment
│   ├── threat_hunt.py          # Threat hunting queries
│   ├── incident_summary.py     # Incident summarization
│   └── evidence_explain.py     # Evidence explanation
├── dashboard/                  # Browser-based UI
│   ├── package.json
│   ├── src/
│   │   ├── components/         # UI components
│   │   ├── views/              # Page-level views
│   │   ├── stores/             # Client-side state
│   │   └── api/                # FastAPI client SDK
│   └── public/
├── config/                     # Configuration files
│   ├── caddy/
│   │   └── Caddyfile           # Reverse proxy config
│   └── .env.example            # Environment variable template
├── scripts/                    # PowerShell startup/shutdown
│   ├── start.ps1               # Launch all components
│   ├── stop.ps1                # Graceful shutdown
│   └── smoke-test.ps1          # Component health verification
├── tests/                      # Test suite
│   ├── unit/
│   ├── integration/
│   └── fixtures/
├── fixtures/                   # Sample data for development
├── docker-compose.yml          # Caddy (and optionally other containers)
└── pyproject.toml              # Python project config (uv)
```

### Structure Rationale

- **backend/**: FastAPI is the central orchestrator. The `api/services/stores` layering enforces separation of HTTP concerns from business logic from data access. This is critical because multiple services (RAG, detection, graph) share the same data stores.
- **ingestion/**: Separate from backend because parsers are stateless transformation functions. They can be invoked from API routes or from CLI scripts. Keeping them out of `backend/` prevents circular imports.
- **detections/**: Isolated because Sigma rules are their own ecosystem. The compiler converts YAML to Python match functions; the matcher runs them. This boundary lets you update rules without touching backend code.
- **graph/**: Separate because graph logic is complex enough to warrant its own module. The graph layer reads from both DuckDB (entity attributes) and SQLite (edges) and provides a unified query interface.
- **prompts/**: Prompt templates are versioned artifacts, not code. Separating them makes prompt engineering independent of backend releases.

## Data Flow

### End-to-End Investigation Flow

```
Evidence Sources                    Storage Layer                   Analysis Layer              Presentation
================                    =============                   ==============              ============

EVTX files    ─┐
JSON/CSV/NDJSON┤
osquery results┤     ┌──────────┐   ┌──────────┐
Sigma rules   ─┤────>│Ingestion │──>│ DuckDB   │──┐
IOC lists     ─┤     │Pipeline  │   │ (events) │  │  ┌──────────┐   ┌──────────┐
Analyst notes ─┘     │          │   └──────────┘  ├─>│Detection │──>│          │
                     │          │                  │  │+ Sigma   │   │ FastAPI  │   ┌──────────┐
                     │          │   ┌──────────┐  │  └──────────┘   │ API      │──>│Dashboard │
                     │          │──>│ Chroma   │──┤                  │          │   │ (browser)│
                     │          │   │ (vectors)│  │  ┌──────────┐   │          │   └──────────┘
                     │          │   └──────────┘  ├─>│Correlation│──>│          │
                     │          │                  │  │+ Graph   │   │          │
                     │          │   ┌──────────┐  │  └──────────┘   │          │
                     │          │──>│ SQLite   │──┘                  │          │
                     └──────────┘   │ (edges)  │     ┌──────────┐   │          │
                                    └──────────┘  ┌─>│ Ollama   │──>│          │
                                                  │  │ (LLM)    │   └──────────┘
                                    Analyst Query─┘  └──────────┘
```

### Key Data Flows

**1. Evidence Ingestion Flow**

```
Raw file (EVTX/JSON/CSV)
    -> Parser (format-specific, produces normalized dicts)
    -> Normalizer (apply unified schema: timestamp, host, user, process, etc.)
    -> Loader:
        -> DuckDB: INSERT normalized event rows
        -> Chroma: embed event text + metadata, store vector
        -> SQLite: INSERT entity edges (process->file, user->host, etc.)
    -> Detection trigger: run Sigma matchers against new events
    -> Correlation trigger: update clustering for affected time window
```

**2. Analyst Query (RAG) Flow**

```
Analyst types question in dashboard
    -> POST /query {question, filters}
    -> FastAPI retrieval service:
        -> Chroma similarity search (top-k relevant evidence chunks)
        -> DuckDB SQL query (structured context: related events, timeline)
        -> Assemble context window from both sources
    -> Ollama /api/generate (stream=true):
        -> System prompt + context + question
        -> Stream tokens back via SSE/WebSocket
    -> Response includes: answer text + cited evidence IDs
    -> Dashboard renders answer with clickable evidence links
```

**3. Detection Flow**

```
On ingestion (or scheduled scan):
    -> pySigma compiler loads Sigma YAML rules
    -> Compiler produces Python match functions (cached)
    -> Matcher iterates new DuckDB events against compiled rules
    -> Matches produce detection records:
        -> SQLite: INSERT detection with matched rule, severity, ATT&CK technique
        -> SQLite: INSERT edges (detection->event, detection->technique)
    -> Dashboard polls /detect endpoint for new findings
```

**4. Graph Query Flow**

```
Analyst clicks entity in dashboard (e.g., a process)
    -> GET /graph/entity/{id}?depth=2
    -> Graph query service:
        -> SQLite: traverse edges from entity (process->file, process->network, etc.)
        -> DuckDB: fetch entity attributes (timestamps, metadata)
        -> Build subgraph response (nodes + edges + attributes)
    -> Dashboard renders node-link visualization
    -> Analyst can expand nodes, filter by type, trace paths
```

## Native vs. Container Decisions

| Component | Runtime | Justification |
|-----------|---------|---------------|
| **Ollama** | **Native Windows** | Requires direct CUDA/GPU access. RTX 5080 needs native driver. Docker GPU passthrough on Windows requires WSL2 with additional complexity and performance overhead. Non-negotiable. |
| **FastAPI** | **Native Python (uv)** | In-process access to DuckDB, Chroma, SQLite (all embedded). No network overhead for DB calls. Simpler debugging. 96GB RAM is more than sufficient. Docker adds no value here. |
| **DuckDB** | **Embedded (in-process)** | Zero-server embedded database. Runs inside FastAPI process. Containerizing would require client-server mode, adding latency and complexity for no benefit. |
| **Chroma** | **Embedded (PersistentClient)** | Same rationale as DuckDB. PersistentClient mode writes to disk, survives restarts, no separate server needed at desktop scale. |
| **SQLite** | **Embedded (in-process)** | Standard library in Python. Graph edge tables are lightweight. No reason to externalize. |
| **Caddy** | **Docker container** | Caddy in Docker isolates TLS certificate management. Official Caddy Docker image is tiny (~40MB). Easy to configure via Caddyfile mount. The one component that benefits from containerization. |
| **osquery** | **Native Windows** | Must run with system-level access to query host processes, network connections, file hashes. Cannot be containerized meaningfully on Windows. |
| **Dashboard** | **Static files (served by Caddy or FastAPI)** | Built SPA is just HTML/JS/CSS. No runtime needed. Served as static assets. |
| **pySigma** | **Embedded (in-process)** | Python library. Runs inside FastAPI process alongside detection logic. |

**Summary: Only Caddy runs in Docker. Everything else is native or in-process.**

## Architectural Patterns

### Pattern 1: Embedded Database Composition

**What:** Multiple embedded databases (DuckDB, Chroma, SQLite) running in the same Python process, each handling what it is best at.
**When to use:** Single-user desktop applications where network overhead between services is pure waste.
**Trade-offs:**
- Pro: Zero network latency for DB calls, simple deployment, no connection pooling needed
- Pro: Single process means shared memory, no serialization overhead for internal data exchange
- Con: Single process failure takes down all stores (mitigated by structured error handling and WAL mode)
- Con: Cannot scale horizontally (irrelevant for single-desktop scope)

```python
# backend/core/deps.py - Dependency injection for embedded stores
from contextlib import asynccontextmanager
import duckdb
import chromadb
import sqlite3

class Stores:
    def __init__(self, data_dir: str):
        self.duckdb = duckdb.connect(f"{data_dir}/events.duckdb")
        self.chroma = chromadb.PersistentClient(path=f"{data_dir}/chroma")
        self.sqlite = sqlite3.connect(f"{data_dir}/graph.sqlite3")

    def close(self):
        self.duckdb.close()
        self.sqlite.close()
        # Chroma PersistentClient has no explicit close

# Used via FastAPI lifespan
@asynccontextmanager
async def lifespan(app):
    stores = Stores(settings.data_dir)
    app.state.stores = stores
    yield
    stores.close()
```

### Pattern 2: Service Layer Orchestration

**What:** Thin API routes delegate to service classes that orchestrate across stores. Routes handle HTTP; services handle logic.
**When to use:** When multiple API endpoints share business logic and multiple stores need coordinated access.
**Trade-offs:**
- Pro: Testable without HTTP (unit test services directly)
- Pro: Services can call each other without HTTP round-trips
- Con: Slightly more boilerplate than putting logic in routes

```python
# backend/services/retrieval.py
class RetrievalService:
    def __init__(self, stores: Stores, llm_client: OllamaClient):
        self.stores = stores
        self.llm = llm_client

    async def answer_query(self, question: str, filters: dict):
        # 1. Vector search for relevant evidence
        chunks = self.stores.chroma.query(question, n_results=10)

        # 2. Structured context from DuckDB
        events = self.stores.duckdb.sql(
            "SELECT * FROM events WHERE ..."
        ).fetchall()

        # 3. Assemble context and call LLM
        context = self._build_context(chunks, events)
        async for token in self.llm.stream(question, context):
            yield token
```

### Pattern 3: Parser Registry for Ingestion

**What:** Each evidence format has a parser class implementing a common interface. A registry maps file types to parsers. New formats require only a new parser file.
**When to use:** When supporting multiple input formats that all normalize to the same schema.
**Trade-offs:**
- Pro: Adding PCAP or Sysmon parsers later requires zero changes to existing code
- Pro: Each parser is independently testable with fixture files
- Con: Slight indirection (registry lookup) but negligible

```python
# ingestion/parsers/base.py
from typing import Iterator
from backend.models.event import NormalizedEvent

class BaseParser:
    supported_extensions: list[str]

    def parse(self, file_path: str) -> Iterator[NormalizedEvent]:
        raise NotImplementedError

# ingestion/parsers/evtx.py
class EvtxParser(BaseParser):
    supported_extensions = [".evtx"]

    def parse(self, file_path: str) -> Iterator[NormalizedEvent]:
        # python-evtx library to read EVTX
        ...
```

### Pattern 4: Compiled Detection Rules

**What:** Sigma YAML rules are compiled once into Python match functions via pySigma, then cached. At detection time, events are checked against compiled functions, not re-parsed YAML.
**When to use:** When running hundreds of detection rules against thousands of events. Compilation amortizes the cost.
**Trade-offs:**
- Pro: Detection runs at Python-native speed, not YAML-parsing speed
- Pro: Compiled rules can be serialized and cached across restarts
- Con: Compilation step adds complexity; must invalidate cache when rules change

```python
# detections/compiler.py
from sigma.rule import SigmaRule
from sigma.backends.python import PythonBackend
from sigma.pipelines.windows import windows_pipeline

class SigmaCompiler:
    def __init__(self):
        self.pipeline = windows_pipeline()
        self.backend = PythonBackend(self.pipeline)
        self._cache = {}

    def compile_rule(self, rule_path: str):
        rule = SigmaRule.from_yaml(open(rule_path).read())
        compiled = self.backend.convert_rule(rule)
        self._cache[rule_path] = compiled
        return compiled
```

**Note on pySigma backend choice:** pySigma does not ship a "PythonBackend" out of the box. The actual approach is to use `sigma-cli` or pySigma to convert Sigma rules into DuckDB SQL queries (since DuckDB is the event store), then run those queries directly. Alternatively, convert to a dict-matching function. This is a design decision to resolve during implementation -- the key architectural point is that compilation happens once and matching happens many times.

### Pattern 5: Graph as Derived View (Not Primary Store)

**What:** The graph is built from events and detections stored in DuckDB/SQLite, not maintained as a separate primary store. Entity nodes and relationship edges are derived during ingestion and updated incrementally.
**When to use:** When you want graph capabilities without the operational overhead of a dedicated graph database (Neo4j).
**Trade-offs:**
- Pro: No additional infrastructure; SQLite edge tables are simple and fast for desktop scale
- Pro: Graph is always consistent with source data (derived, not duplicated)
- Con: Complex graph algorithms (community detection, PageRank) require manual implementation or networkx
- Con: If graph queries become the bottleneck, migration to a proper graph DB is a future option

```python
# graph/schema.py
ENTITY_TYPES = [
    "host", "user", "process", "file",
    "network_connection", "domain", "ip_address",
    "detection", "artifact", "incident", "attack_technique"
]

EDGE_TYPES = [
    "executed_by",      # process -> user
    "ran_on",           # process -> host
    "accessed",         # process -> file
    "connected_to",     # process -> network_connection
    "resolved_to",      # domain -> ip_address
    "triggered",        # event -> detection
    "maps_to",          # detection -> attack_technique
    "part_of",          # detection -> incident
]

# SQLite schema
CREATE_EDGES = """
CREATE TABLE IF NOT EXISTS edges (
    id INTEGER PRIMARY KEY,
    source_type TEXT NOT NULL,
    source_id TEXT NOT NULL,
    edge_type TEXT NOT NULL,
    target_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    properties JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source_type, source_id, edge_type, target_type, target_id)
);
CREATE INDEX IF NOT EXISTS idx_edges_source ON edges(source_type, source_id);
CREATE INDEX IF NOT EXISTS idx_edges_target ON edges(target_type, target_id);
"""
```

## Build Order and Dependency Graph

The build order is driven by data flow dependencies: you cannot query what you have not stored, you cannot detect what you have not ingested, you cannot visualize what you have not correlated.

### Dependency Graph

```
Phase 1: Foundation
    Ollama install + model pull
    FastAPI skeleton + health endpoint
    Caddy Docker + HTTPS
    DuckDB schema + connection
    Chroma setup + embedding model
        |
        v
Phase 2: Ingestion Pipeline
    Normalized event schema (Pydantic)
    EVTX parser
    JSON/NDJSON/CSV parsers
    Loader (DuckDB + Chroma write)
    /ingest API endpoint
        |
        v
Phase 3: RAG Query Engine         Phase 3b: Detection Engine (parallel)
    Prompt templates                  pySigma rule compilation
    Chroma retrieval                  Sigma rule loading
    DuckDB context queries            Matcher against DuckDB events
    Ollama streaming integration      /detect API endpoint
    /query API endpoint               SQLite detection records
        |                                |
        +----------------+---------------+
                         |
                         v
Phase 4: Graph + Correlation
    SQLite edge tables + schema
    Edge extraction during ingestion (retrofit)
    Graph query service
    Correlation / clustering
    /graph API endpoint
        |
        v
Phase 5: Dashboard
    Project scaffold (React or Svelte)
    API client layer
    Query panel (chat with RAG)
    Detection panel
    Timeline view
    Graph visualization (node-link)
    Evidence drilldown
        |
        v
Phase 6: Integration + Hardening
    osquery integration
    Live telemetry polling
    ATT&CK enrichment
    Smoke tests for all components
    Startup/shutdown scripts
    Structured logging
```

### Build Order Rationale

| Order | Phase | Why This Position |
|-------|-------|-------------------|
| 1 | Foundation | Everything depends on Ollama, FastAPI, and stores being operational. Without the data layer, nothing can be built on top. |
| 2 | Ingestion | You need data in the stores before you can query, detect, or visualize. Ingestion is the gateway for all evidence. |
| 3 | RAG + Detection (parallel) | These are independent consumers of stored data. RAG reads from Chroma + DuckDB. Detection reads from DuckDB. They can be built in parallel by different work streams. |
| 4 | Graph + Correlation | Depends on both ingestion (for entity extraction) and detection (for linking detections to entities). Must come after both are functional. |
| 5 | Dashboard | Requires all API endpoints to exist. Building UI before APIs are stable means constant rework. |
| 6 | Integration + Hardening | osquery, ATT&CK enrichment, and operational tooling are polish. Core investigation workflow must work first. |

## Integration Points: Risk Assessment

### High Risk

| Integration | Risk | Why | Mitigation |
|-------------|------|-----|------------|
| **Ollama streaming -> FastAPI SSE/WebSocket** | Token streaming reliability, connection drops, timeout handling | LLM inference can take 10-60 seconds. HTTP timeouts, client disconnects, and partial responses are common failure modes. | Use WebSocket for dashboard streaming (persistent connection). Implement heartbeat. Set Ollama `keep_alive` to avoid model unload. Add request cancellation. |
| **pySigma rule compilation** | No native "Python backend" in pySigma | pySigma backends target SIEMs (Splunk, Elastic, etc.), not in-process Python matching. Need custom approach. | Strategy A: Write a custom pySigma backend that generates DuckDB SQL WHERE clauses. Strategy B: Convert rules to dict-matching Python functions manually. Strategy A is cleaner. |
| **EVTX parsing on Windows** | python-evtx library reliability on large files | EVTX files can be multi-GB. Parser must handle corrupt records, streaming reads, and memory efficiency. | Use `python-evtx` with streaming iteration. Test with real-world EVTX files early. Have fallback to `evtx` Rust-based library via `evtx` Python bindings. |

### Medium Risk

| Integration | Risk | Mitigation |
|-------------|------|------------|
| **Chroma embedding model selection** | Wrong model = poor retrieval quality | Use `nomic-embed-text` via Ollama for embeddings (keeps everything local). Benchmark retrieval quality early with cybersecurity-domain test queries. |
| **DuckDB concurrent access** | DuckDB has single-writer semantics | FastAPI is async but DuckDB writes are synchronous. Use a write queue or ensure ingestion writes happen in a dedicated thread. Read-only analytical queries can happen concurrently. |
| **Graph edge extraction quality** | Garbage in, garbage out | Edge extraction from normalized events must be precise. If the normalizer maps fields incorrectly, the graph is meaningless. Invest in normalizer testing with fixture data. |
| **Dashboard graph rendering performance** | Large graphs (1000+ nodes) lag in browser | Use progressive loading (expand on click, not load all). Use WebGL-based renderer (e.g., Sigma.js or react-force-graph). Limit initial query depth to 2 hops. |

### Low Risk

| Integration | Risk | Mitigation |
|-------------|------|------------|
| **Caddy reverse proxy** | Straightforward config | Standard Caddyfile with reverse_proxy directive. Well-documented. |
| **FastAPI + Pydantic** | Mature, well-documented | Use Pydantic v2 for performance. Standard patterns. |
| **SQLite for graph edges** | Battle-tested | WAL mode for concurrent reads. Simple schema. |

## Scaling Considerations

This is a single-desktop, single-analyst system. "Scaling" means handling larger datasets, not more users.

| Concern | At 10K events | At 1M events | At 10M events |
|---------|---------------|--------------|---------------|
| **DuckDB query speed** | Instant (<10ms) | Fast (<100ms for scans, <10ms for indexed) | May need partitioning by time window. Columnar format handles this well. |
| **Chroma search** | Instant | Fast with HNSW index | May need collection sharding by evidence type. Monitor embedding insert throughput. |
| **Graph traversal** | Instant | Fast with indexed edges | Consider migrating to networkx in-memory graph or DuckDB graph extension if SQLite becomes bottleneck. |
| **LLM context window** | Not an issue | Context assembly must be selective (top-k, not all) | Same as 1M. RAG quality depends on retrieval precision, not volume. |
| **Ingestion throughput** | Seconds | Minutes (acceptable for batch) | Use DuckDB COPY for bulk loads. Batch Chroma inserts (100+ at a time). |

### First Bottleneck: LLM Inference Speed

With RTX 5080 (16GB VRAM), quantized models (Q4_K_M) in the 7-14B parameter range will give 30-80 tokens/sec. This is the primary bottleneck for interactive Q&A. Mitigation: use streaming to give perceived responsiveness.

### Second Bottleneck: Ingestion of Large EVTX Files

Multi-GB EVTX files with millions of records will take minutes to parse and load. Mitigation: async background ingestion with progress reporting to dashboard.

## Anti-Patterns

### Anti-Pattern 1: Microservice-ifying a Desktop App

**What people do:** Split every component (LLM, detection, graph, ingestion) into separate Docker containers with REST APIs between them.
**Why it is wrong:** On a single desktop, inter-container network calls add latency, complexity, and debugging difficulty for zero benefit. You do not need horizontal scaling. You have one user.
**Do this instead:** Embedded databases, in-process libraries, single FastAPI process. The only container is Caddy for TLS.

### Anti-Pattern 2: Using LangChain as the Orchestration Layer

**What people do:** Wrap everything in LangChain chains, agents, and retrievers because "that is how RAG is done."
**Why it is wrong:** LangChain adds massive dependency weight, abstracts away control you need for cybersecurity (citation tracking, evidence provenance, deterministic retrieval), and changes API frequently. For a security tool, you need to know exactly what context the LLM sees.
**Do this instead:** Direct Ollama HTTP client + direct Chroma queries + manual context assembly. It is ~100 lines of code instead of a framework dependency.

### Anti-Pattern 3: Storing Everything as Vectors

**What people do:** Embed every event into Chroma and rely solely on vector similarity for all queries.
**Why it is wrong:** Structured cybersecurity data (timestamps, IP addresses, process IDs, hash values) needs exact matching, range queries, and aggregation -- not fuzzy similarity search. Vectors are for semantic search over unstructured text.
**Do this instead:** DuckDB for structured queries (WHERE, GROUP BY, time ranges). Chroma for semantic search over analyst notes, evidence descriptions, and unstructured text. Use both together in RAG context assembly.

### Anti-Pattern 4: Building the Dashboard First

**What people do:** Start with the UI because it is visible and satisfying.
**Why it is wrong:** Without stable APIs, the dashboard is built against imaginary contracts. Every API change forces UI rework. You cannot demo a dashboard that shows empty panels.
**Do this instead:** Build backend + ingestion + load fixture data first. Build dashboard last, when APIs are stable and you have real data to display.

### Anti-Pattern 5: Monolithic Prompt Templates

**What people do:** One giant prompt template for all query types.
**Why it is wrong:** Triage, threat hunting, evidence explanation, and incident summarization have different context needs, output formats, and system instructions. A single template either underfits all use cases or overfits one.
**Do this instead:** Separate prompt templates per use case. Each template specifies what context to retrieve, how to format it, and what output structure to expect.

## Internal Boundaries

| Boundary | Communication | Protocol | Notes |
|----------|---------------|----------|-------|
| Dashboard <-> FastAPI | HTTP REST + WebSocket | JSON over HTTPS (via Caddy) | WebSocket for LLM streaming; REST for everything else |
| FastAPI <-> Ollama | HTTP REST | JSON over HTTP to localhost:11434 | Streaming via chunked response. Use `httpx` async client. |
| FastAPI <-> DuckDB | In-process function call | Python API (duckdb module) | No network. Direct method calls. |
| FastAPI <-> Chroma | In-process function call | Python API (chromadb module) | PersistentClient, no HTTP. |
| FastAPI <-> SQLite | In-process function call | Python API (sqlite3 module) | WAL mode for concurrent reads. |
| FastAPI <-> osquery | Local socket or CLI | osqueryi CLI or Thrift (port 7727) | Poll-based, not streaming. |
| Caddy <-> FastAPI | HTTP reverse proxy | HTTP to localhost:8000 | Caddy terminates TLS, proxies to uvicorn. |
| Docker containers <-> Ollama | HTTP via host bridge | host.docker.internal:11434 | Only relevant if any future service runs in Docker. |

## Normalized Event Schema (Core Data Contract)

This schema is the central contract between ingestion, storage, detection, and graph layers. All parsers must produce records conforming to this schema.

```python
# backend/models/event.py
from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class NormalizedEvent(BaseModel):
    event_id: str                          # UUID, generated at ingestion
    timestamp: datetime                    # When the event occurred
    ingested_at: datetime                  # When we ingested it
    source_type: str                       # "evtx", "osquery", "json", "csv", "analyst_note"
    source_file: Optional[str]             # Original file path

    # Entity fields (all optional, populated per source)
    hostname: Optional[str]
    username: Optional[str]
    process_name: Optional[str]
    process_id: Optional[int]
    parent_process_name: Optional[str]
    parent_process_id: Optional[int]
    file_path: Optional[str]
    file_hash_sha256: Optional[str]
    command_line: Optional[str]

    # Network fields
    src_ip: Optional[str]
    src_port: Optional[int]
    dst_ip: Optional[str]
    dst_port: Optional[int]
    domain: Optional[str]
    url: Optional[str]

    # Classification
    event_type: Optional[str]              # "process_create", "network_connect", "file_write", etc.
    severity: Optional[str]               # "info", "low", "medium", "high", "critical"
    confidence: Optional[float]           # 0.0-1.0
    detection_source: Optional[str]       # "sigma:rule_id", "anomaly:clustering", "analyst"
    attack_technique: Optional[str]       # MITRE ATT&CK ID (e.g., "T1059.001")
    attack_tactic: Optional[str]          # MITRE ATT&CK tactic

    # Provenance
    raw_event: Optional[str]              # Original event text (for evidence drilldown)
    tags: list[str] = []                  # Analyst tags, IOC matches, etc.
    case_id: Optional[str]                # Associated case/incident

    # For embedding
    def to_embedding_text(self) -> str:
        """Produce text representation for vector embedding."""
        parts = [f"[{self.event_type}]" if self.event_type else ""]
        if self.hostname: parts.append(f"host:{self.hostname}")
        if self.username: parts.append(f"user:{self.username}")
        if self.process_name: parts.append(f"process:{self.process_name}")
        if self.command_line: parts.append(f"cmd:{self.command_line}")
        if self.file_path: parts.append(f"file:{self.file_path}")
        if self.dst_ip: parts.append(f"dst:{self.dst_ip}:{self.dst_port}")
        if self.domain: parts.append(f"domain:{self.domain}")
        return " | ".join(filter(None, parts))
```

## Sources

- [Chroma official site](https://www.trychroma.com/) - Client modes, recent features (sparse vector search, BM25)
- [DuckDB streaming patterns](https://duckdb.org/2025/10/13/duckdb-streaming-patterns) - Materialized view pattern, insert throughput
- [pySigma PyPI](https://pypi.org/project/pySigma/) - Modular backend architecture, pipeline design
- [Sigma backends documentation](https://sigmahq.io/docs/digging-deeper/backends) - Backend and pipeline architecture
- [ML Journey - Serve Local LLMs as API](https://mljourney.com/how-to-serve-local-llms-as-an-api-fastapi-ollama/) - Ollama + FastAPI integration patterns
- [Ollama-FastAPI-Integration-Demo](https://github.com/darcyg32/Ollama-FastAPI-Integration-Demo) - Streaming, JSON responses
- [MISP Project](https://www.misp-project.org/) - Threat intelligence platform architecture reference
- [Neo4j CTI analysis](https://neo4j.com/blog/developer/cyber-threat-intelligence-analysis/) - Graph visualization for cybersecurity (reference for what we are building without Neo4j)
- [FastAPI production architecture 2025](https://medium.com/@abhinav.dobhal/building-production-ready-fastapi-applications-with-service-layer-architecture-in-2025-f3af8a6ac563) - Service layer pattern

---
*Architecture research for: AI-SOC-Brain - Local Windows Desktop AI Cybersecurity Investigation Platform*
*Researched: 2026-03-14*
