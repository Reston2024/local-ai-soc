# Stack Research

**Domain:** Local-first Windows desktop AI cybersecurity investigation platform
**Researched:** 2026-03-14
**Confidence:** HIGH

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Ollama | 0.17+ (native Windows) | Local LLM serving with CUDA | Native Windows install avoids WSL2/GPU passthrough. RTX 5080 requires v0.17+ for CUDA 12.8 / Blackwell support. Under 5% perf difference vs WSL2 -- use native for simplicity. Intel CPU (no AMD iGPU conflict). **Confidence: HIGH** |
| FastAPI | 0.135.x | Backend API server | Standard Python async API framework. SSE support for streaming LLM responses. 15-20K RPS baseline. Python ecosystem has best SecOps/ML library coverage. **Confidence: HIGH** |
| Uvicorn | 0.41.0 | ASGI server | Lightning-fast ASGI server for FastAPI. Install with `[standard]` for uvloop+httptools. Python 3.14 supported since 0.38.0. **Confidence: HIGH** |
| DuckDB | 1.5.0 | Structured event storage & analytics | Zero-server columnar DB. Reads CSV/JSON/Parquet natively. Parallel execution on 24 cores. Out-of-core processing for datasets exceeding RAM. No Postgres needed for single-desktop analytics. **Confidence: HIGH** |
| ChromaDB | 1.5.5 | Vector storage for RAG | Python-native, no external server. Hybrid search (BM25 + semantic) added in 2025. SPANN index for scale. Custom embedding functions via decorator. Lightweight enough for desktop. **Confidence: HIGH** |
| Svelte 5 | 5.x (latest) | Browser dashboard UI | 39% faster than React 19 on benchmarks, 2.5x smaller bundles, 20% less memory. Ideal for real-time security dashboards with high-frequency data updates. No virtual DOM overhead for graph/timeline rendering. Single-dev project -- Svelte's simpler mental model accelerates development. **Confidence: MEDIUM** (ecosystem smaller than React, but sufficient for this use case) |
| Cytoscape.js | 3.30+ | Graph/network visualization | Industry standard for network graph visualization. MIT licensed. Strong cybersecurity adoption (attack graphs, network topology, threat propagation). react-cytoscapejs wrapper available but Svelte integration is straightforward via direct API. Handles up to ~10K elements. **Confidence: HIGH** |
| Caddy | 2.9+ (Docker) | Localhost HTTPS reverse proxy | Auto-TLS with internal CA for localhost. Simpler config than nginx. Docker container proxies to native backend. Volumes must persist `/data` for cert survival across restarts. **Confidence: HIGH** |

### LLM Model Recommendations (RTX 5080, 16 GB VRAM)

| Model | Size | Purpose | Why | Confidence |
|-------|------|---------|-----|------------|
| **qwen3:14b** (Q8) | ~14 GB | Primary reasoning / analyst Q&A | Best all-around for 16 GB VRAM. Strong reasoning + code understanding. Fits entirely in VRAM at Q8 quantization. Excellent for multi-step cybersecurity analysis, log interpretation, threat correlation. | HIGH |
| **deepseek-r1:14b** | ~14 GB | Alternative reasoning (chain-of-thought) | "Thinking" model with explicit step-by-step reasoning. Better for complex logic puzzles and technical reasoning. Swap in when qwen3 reasoning is insufficient. | MEDIUM |
| **mxbai-embed-large** | ~1.2 GB | Embedding model for RAG | MTEB retrieval score 64.68 vs nomic-embed-text's 53.01. 1024 dimensions. Better on context-heavy queries (security events are context-heavy). 1.2 GB fits alongside any reasoning model. | HIGH |

**Model loading strategy:** Only one reasoning model loaded at a time (~14 GB). Embedding model (~1.2 GB) loads separately and can coexist briefly but should be called via Ollama's API (loads/unloads automatically). Never load two 14B models simultaneously.

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| LangGraph | 1.0+ | RAG orchestration, agent workflows | Use for structured RAG pipelines: query rewriting, document grading, multi-step retrieval. Human-in-the-loop patterns built in. Do NOT use LangChain chains -- use LangGraph graphs directly. **Confidence: HIGH** |
| langchain-ollama | latest | Ollama LLM/embedding integration | LangChain's Ollama integration for ChatOllama and OllamaEmbeddings. Thin wrapper, not heavy LangChain dependency. **Confidence: HIGH** |
| langchain-chroma | latest | Chroma vector store integration | LangChain-compatible Chroma wrapper for use within LangGraph pipelines. **Confidence: HIGH** |
| pySigma | 1.1.1 | Sigma rule parsing & conversion | Parse Sigma YAML rules into structured detection logic. Convert to DuckDB SQL queries for matching against ingested events. Requires Python >= 3.10. **Confidence: HIGH** |
| sigma-cli | 2.0.1 | Sigma rule management CLI | List, validate, convert Sigma rules from command line. Use alongside pySigma for rule management workflows. **Confidence: HIGH** |
| python-evtx | latest | Windows .evtx log parsing | Pure Python parser for Windows Event Log files. Cross-platform. Outputs XML/JSON. Standard DFIR tool. **Confidence: HIGH** |
| DuckDB Python API | 1.5.0 | SQL analytics from Python | Direct Python API -- `import duckdb`. Query DataFrames, CSV, JSON, Parquet without loading into memory. **Confidence: HIGH** |
| Pydantic | 2.x | Data validation & schemas | FastAPI's native validation layer. Define normalized event schemas, API request/response models. **Confidence: HIGH** |
| httpx | 0.28+ | Async HTTP client | For Ollama API calls from FastAPI backend. Async-native, connection pooling. Prefer over requests for async code. **Confidence: HIGH** |
| python-multipart | latest | File upload handling | Required by FastAPI for file upload endpoints (evidence bundles, log files). **Confidence: HIGH** |

### Frontend Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Svelte | 5.x | UI framework | All dashboard components. Use SvelteKit only if SSR needed (likely not -- SPA served by FastAPI is simpler). **Confidence: MEDIUM** |
| Cytoscape.js | 3.30+ | Graph visualization | Attack graphs, entity relationship graphs, threat propagation visualization. Direct JS API from Svelte components. **Confidence: HIGH** |
| D3.js | 7.x | Timeline visualization | Timeline view of events. D3's time scales and axis handling are unmatched. Use for timeline only -- Cytoscape handles graphs. **Confidence: HIGH** |
| Vite | 6.x | Build tool | Dev server and bundler for Svelte frontend. Fast HMR. Output static assets served by FastAPI/Caddy. **Confidence: HIGH** |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| uv | Python package manager | Already installed (0.10.6). Use `uv pip install` and `uv venv`. Faster than pip. |
| Docker Compose | Service orchestration | Caddy + Open WebUI containers. Backend and Ollama run native. |
| Ruff | Python linting & formatting | Single tool replaces black + isort + flake8. Fast (Rust-based). |
| pytest | Testing | Standard Python test framework. Use with pytest-asyncio for FastAPI tests. |
| PowerShell | Startup/shutdown scripts | Windows-native scripting for service management. |

## Component Evaluation

Classification of every component from the evaluate list.

### USE NOW

| Component | Rationale |
|-----------|-----------|
| **ollama/ollama** | Core LLM runtime. Native Windows install, RTX 5080 CUDA support confirmed. Install v0.17+ for Blackwell GPU. Phase 1 task 1. |
| **langchain-ai/langgraph** | RAG orchestration framework. v1.0 is stable, production-ready. Human-in-the-loop patterns match project requirements. Use LangGraph directly (not legacy LangChain chains). Phase 1. |
| **chroma-core/chroma** | Vector store for RAG. v1.5.5 is mature. Hybrid search (BM25+semantic), SPANN index. Python-native, no server needed. Phase 1. |
| **SigmaHQ/sigma + pySigma + sigma-cli** | Detection content ecosystem. pySigma 1.1.1 parses rules; write a custom DuckDB backend to convert Sigma rules to SQL. sigma-cli 2.0.1 for rule management. Phase 2-3 (after event storage is working). |
| **osquery/osquery** | Endpoint telemetry via SQL. v5.22.1. Windows support mature. Lightweight agent. Install in Phase 2 when ingestion pipeline is ready. Pairs with DuckDB for analytics. |

### DEFER

| Component | Rationale | When to Reconsider |
|-----------|-----------|-------------------|
| **open-webui/open-webui** | Excellent Ollama frontend (90K+ GitHub stars, RAG built-in). But this project needs a custom investigation dashboard, not a chat UI. Open WebUI's value is convenience -- it does not replace the custom graph/timeline/evidence UI. | Defer to Phase 4+. Consider as optional "analyst chat" companion alongside the custom dashboard. Run in Docker with `host.docker.internal:11434` for Ollama access. Low effort to add later. |
| **Velocidex/velociraptor** | Powerful DFIR tool but designed for fleet management (agent/server model). Overkill for single desktop. osquery covers the endpoint telemetry need with less complexity. | Reconsider only if the project expands to multi-host investigation. Velociraptor can embed osquery, so migration path exists. |

### REJECT

| Component | Rationale |
|-----------|-----------|
| **wazuh/wazuh** | Server components (manager + indexer + dashboard) consume 8+ vCPU and 8+ GB RAM even for small deployments. Java-based indexer alone uses 70% CPU under load. Designed for fleet SIEM, not single-desktop investigation. The project already has DuckDB for storage, Sigma for detections, and osquery for telemetry -- Wazuh adds no unique value that justifies its resource cost. |

## Installation

```bash
# Create project virtual environment
uv venv .venv
source .venv/Scripts/activate  # Windows Git Bash

# Core backend
uv pip install fastapi==0.135.0 "uvicorn[standard]==0.41.0" pydantic>=2.0

# LLM & RAG
uv pip install langgraph langchain-ollama langchain-chroma chromadb

# Data & Analytics
uv pip install duckdb==1.5.0

# Security tooling
uv pip install pySigma sigma-cli python-evtx

# HTTP client
uv pip install httpx python-multipart

# Dev tools
uv pip install ruff pytest pytest-asyncio

# Ollama (native Windows -- not pip)
# Download from https://ollama.com/download and run OllamaSetup.exe
# Then: ollama pull qwen3:14b
# Then: ollama pull mxbai-embed-large

# Frontend (separate directory)
npm create svelte@latest frontend
cd frontend
npm install cytoscape d3
npm install -D @sveltejs/adapter-static vite
```

```yaml
# docker-compose.yml (Caddy only -- backend and Ollama run native)
services:
  caddy:
    image: caddy:2.9-alpine
    ports:
      - "443:443"
      - "80:80"
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile
      - caddy_data:/data
      - caddy_config:/config
    extra_hosts:
      - "host.docker.internal:host-gateway"

volumes:
  caddy_data:
  caddy_config:
```

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| DuckDB | SQLite | If you only need key-value or simple row storage. DuckDB is strictly better for analytical queries (columnar, parallel, SQL analytics functions). Use SQLite only for app metadata/config if needed. |
| DuckDB | PostgreSQL | If you need concurrent multi-user write access or need PostGIS spatial queries. Not needed for single-desktop single-user. |
| ChromaDB | Pinecone | If you need managed cloud vector search. Rejected by project constraints (local-first). |
| ChromaDB | Qdrant | If you need filtering performance at >1M vectors. ChromaDB's SPANN index handles desktop scale. Qdrant requires a separate server process. |
| Svelte 5 | React 19 | If you need the largest component ecosystem (enterprise grids, charting libraries). React's ecosystem is 10x larger. Choose React if hiring/team familiarity is a factor. For single-dev cybersecurity dashboard with Cytoscape.js + D3.js, Svelte's performance advantage and simpler DX win. |
| LangGraph | LlamaIndex | If you want tighter RAG-specific abstractions. LangGraph is more flexible for custom agent workflows (query rewriting, evidence grading, multi-step retrieval). LangGraph 1.0's human-in-the-loop patterns directly serve this project's requirements. |
| Cytoscape.js | vis.js / Sigma.js | If you need WebGL rendering for >10K nodes. Cytoscape.js handles typical investigation graphs (hundreds to low thousands of nodes) well. vis.js is less maintained. Sigma.js is WebGL-first but less flexible for styled node types. |
| Caddy | nginx | If you need complex routing rules or existing nginx configs. Caddy's auto-TLS and simpler Caddyfile syntax make it the clear choice for localhost HTTPS. |
| mxbai-embed-large | nomic-embed-text | If you need maximum speed and minimal memory (0.5 GB vs 1.2 GB). nomic-embed-text is faster but scores 53.01 vs 64.68 on MTEB retrieval. For security event retrieval where precision matters, mxbai-embed-large is worth the extra 700 MB. |
| qwen3:14b | deepseek-r1:14b | If you need explicit chain-of-thought reasoning traces. DeepSeek-R1 shows its reasoning steps, which aids explainability. Consider as secondary model for complex threat analysis. |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| PostgreSQL | Server process, connection management, backup complexity -- all unnecessary for single-user desktop analytics. | DuckDB (zero-server, columnar, 24-core parallel) |
| Neo4j | Heavy JVM-based graph database. Overkill when graph visualization (Cytoscape.js) + relational queries (DuckDB) cover the need. Graph DB only justified if you need recursive graph traversals at scale. | DuckDB for storage + Cytoscape.js for visualization |
| Kafka | Message queue for distributed systems. Single-process Python backend with DuckDB does not need pub/sub infrastructure. | Direct function calls or Python asyncio queues |
| Elasticsearch | Heavy JVM-based search. DuckDB's full-text search + ChromaDB's hybrid search cover all search needs for desktop scale. | DuckDB (structured search) + ChromaDB (semantic search) |
| Wazuh | 8+ vCPU, 8+ GB RAM for central components. Java indexer alone consumes 70% CPU. Fleet SIEM architecture for single desktop. | osquery (telemetry) + pySigma (detections) + DuckDB (storage) |
| LangChain chains (legacy) | LangChain's chain abstraction is deprecated in favor of LangGraph. Chains are linear; graphs handle branching, loops, human-in-the-loop. | LangGraph 1.0 graphs |
| Flask / Django | Synchronous frameworks. LLM streaming requires async. FastAPI's native async + SSE support is required. | FastAPI + Uvicorn |
| Pinecone / cloud vector DBs | Violates local-first constraint. Sends data to cloud. | ChromaDB (local, Python-native) |
| Docker for Ollama | WSL2 GPU passthrough adds complexity. Native Windows Ollama gets direct CUDA access. Under 5% perf difference. | Native Ollama on Windows |
| Next.js / SvelteKit SSR | Server-side rendering adds complexity with no benefit for a localhost-only dashboard. Static SPA served by FastAPI is simpler. | Svelte 5 SPA with Vite, served as static assets |

## Version Compatibility

| Package | Compatible With | Notes |
|---------|-----------------|-------|
| FastAPI 0.135.x | Starlette >=0.46.0, Pydantic >=2.0 | Starlette 1.0.0rc1 powers async core |
| Uvicorn 0.41.0 | Python >=3.10, Python 3.14 supported | Install `[standard]` for uvloop+httptools |
| ChromaDB 1.5.5 | Python >=3.9 | Hybrid search requires 1.5.0+ |
| DuckDB 1.5.0 | Python >=3.8 | LTS releases every other version starting v1.4 |
| LangGraph 1.0 | langchain-core >=0.3 | `langgraph.prebuilt` deprecated, use `langchain.agents` |
| pySigma 1.1.1 | Python >=3.10 | Need custom DuckDB backend (write one) |
| Ollama 0.17+ | CUDA 12.8 for RTX 5080 | Intel CPU avoids AMD iGPU conflict bug |
| Svelte 5 | Vite 6.x | Use `@sveltejs/adapter-static` for SPA output |
| Cytoscape.js 3.30+ | Any modern browser | No framework dependency -- works with Svelte directly |
| python-evtx | Python 3.x | Pure Python, no native dependencies |

## Architecture Notes for Roadmap

**Process model (all native except Caddy):**
```
[Browser] --> [Caddy:443 (Docker)] --> [FastAPI:8000 (native)]
                                            |
                                            +--> [Ollama:11434 (native)] -- qwen3:14b / mxbai-embed-large
                                            +--> [DuckDB (embedded, in-process)]
                                            +--> [ChromaDB (embedded, in-process)]
```

**Why this matters:**
- DuckDB and ChromaDB are embedded (in-process) -- no separate servers to manage.
- Ollama runs as a native Windows service on port 11434.
- Caddy is the only Docker container -- reverse proxies HTTPS to FastAPI.
- FastAPI serves both the API and the static Svelte frontend build.
- Total running processes: Caddy (Docker), FastAPI (native Python), Ollama (native Windows service).

## Sources

- [Ollama Downloads](https://ollama.com/download) -- native Windows installer, version info
- [Ollama GPU Support](https://docs.ollama.com/gpu) -- RTX 5080 / Blackwell CUDA 12.8 requirement
- [Ollama RTX 5080 AMD iGPU bug](https://github.com/ollama/ollama/issues/11849) -- Intel CPU avoids this
- [Best LLMs for 16GB VRAM](https://medium.com/@rosgluk/best-llms-for-ollama-on-16gb-vram-gpu-c1bf6c3a10be) -- qwen3:14b recommendation
- [Best Local LLMs 16GB VRAM](https://localllm.in/blog/best-local-llms-16gb-vram) -- model performance benchmarks
- [Ollama Embedding Models](https://ollama.com/blog/embedding-models) -- mxbai-embed-large vs nomic-embed-text
- [Best Embedding Models 2026](https://elephas.app/blog/best-embedding-models) -- MTEB scores comparison
- [ChromaDB PyPI](https://pypi.org/project/chromadb/) -- v1.5.5, Python >=3.9
- [ChromaDB Embedding Functions](https://docs.trychroma.com/docs/embeddings/embedding-functions) -- custom embedding support
- [DuckDB Releases](https://github.com/duckdb/duckdb/releases) -- v1.5.0, LTS policy
- [DuckDB PyPI](https://pypi.org/project/duckdb/) -- Python package
- [LangChain/LangGraph 1.0 Announcement](https://blog.langchain.com/langchain-langgraph-1dot0/) -- November 2025 stable release
- [LangGraph GitHub](https://github.com/langchain-ai/langgraph) -- MIT license, human-in-the-loop
- [FastAPI Release Notes](https://fastapi.tiangolo.com/release-notes/) -- v0.135.x, SSE support
- [Uvicorn PyPI](https://pypi.org/project/uvicorn/) -- v0.41.0, Python 3.14 support
- [pySigma PyPI](https://pypi.org/project/pySigma/) -- v1.1.1, Python >=3.10
- [sigma-cli GitHub Releases](https://github.com/SigmaHQ/sigma-cli/releases) -- v2.0.1
- [python-evtx GitHub](https://github.com/williballenthin/python-evtx) -- pure Python EVTX parser
- [osquery Releases](https://github.com/osquery/osquery/releases) -- v5.22.1
- [osquery Windows Install](https://osquery.readthedocs.io/en/stable/installation/install-windows/) -- Chocolatey package
- [Cytoscape.js](https://js.cytoscape.org/) -- graph visualization library
- [react-cytoscapejs](https://github.com/plotly/react-cytoscapejs) -- React wrapper (Svelte uses direct API)
- [Svelte vs React 2026](https://devtrios.com/blog/svelte-vs-react-which-framework-should-you-choose/) -- performance benchmarks
- [Caddy Reverse Proxy Quick-Start](https://caddyserver.com/docs/quick-starts/reverse-proxy) -- configuration
- [Open WebUI GitHub](https://github.com/open-webui/open-webui) -- 90K+ stars, RAG built-in
- [Wazuh Server Requirements](https://documentation.wazuh.com/current/installation-guide/wazuh-server/index.html) -- resource usage
- [Velociraptor vs osquery](https://forum.getcybersecurityjobs.com/t/velociraptor-vs-osquery-for-rapid-host-triage/323) -- comparison

---
*Stack research for: Local-first Windows desktop AI cybersecurity investigation platform*
*Researched: 2026-03-14*
