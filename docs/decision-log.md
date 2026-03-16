# Decision Log

## Wave 1 Foundation — 2026-03-15

| Field | Value |
|-------|-------|
| Date | 2026-03-15 |
| Phase | Wave 1 Foundation |
| Status | Implemented |

### Decisions

| Component | Decision | Reason | Impact |
|-----------|----------|--------|--------|
| **Svelte 5** | Use Svelte 5 with runes (`$state`, `$props`) | Modern reactive primitives, eliminates store boilerplate, future-proof | Breaking change from Svelte 4 — no `writable()` stores |
| **Cytoscape.js** | Threat graph visualization | Mature graph library, handles large node/edge sets, extensible layouts | Requires DOM mount, server-side rendering not supported |
| **D3.js** | Event timeline rendering | Most powerful time-series SVG library; direct DOM manipulation | Learning curve; keep D3 isolated in timeline component |
| **FastAPI** | Backend API framework | Typed request/response models via Pydantic, async-ready, auto OpenAPI docs | Python 3.12+ required; async must be used carefully with sync routes |
| **Vector** | Telemetry ingest pipeline | High-performance Rust binary; supports NDJSON file sources + HTTP sinks; Wave 2 extensible | Wave 1 scaffold only — routes fixtures to backend `/events` endpoint |
| **Caddy** | HTTPS reverse proxy | Automatic TLS (self-signed for localhost), simple config, no cert management | Requires `tls internal` for localhost; browsers may warn on first visit |
| **Docker Compose** | Service orchestration | Single command to start full stack; isolates service dependencies | Requires Docker Desktop on Windows |
| **OpenSearch** | Search/analytics store | Elastic-compatible; designed for security analytics (SIEM use cases); Wave 2 target | **Wave 1 scaffold only** — backend does NOT yet write to OpenSearch. In-memory store used for Phase 1. Wave 2 will wire event indexing. |
| **In-memory store** | Phase 1 persistence | Simplest possible persistence for foundation; avoids database setup complexity | Not durable across restarts; must be replaced in Wave 2 with DuckDB or OpenSearch |

## Phase 2 Ingestion — 2026-03-15

| Field | Value |
|-------|-------|
| Date | 2026-03-15 |
| Phase | Phase 2 Ingestion Pipeline |
| Branch | feature/ai-soc-phase2-ingestion |
| Status | Implemented |

### Decisions

| Component | Decision | Reason | Impact |
|-----------|----------|--------|--------|
| **Enrichment pipeline** | Extract enrichment into `ingestion/enricher.py` before detection | Separates labeling (enricher) from alerting (rules); enrichments become reusable across all rule types | Detection rules now read `event.enrichments` tags — simpler, testable in isolation |
| **Syslog parser (3 formats)** | Support RFC3164, RFC5424, CEF in `ingestion/syslog_parser.py` | Covers the three dominant firewall/network telemetry formats without external parsers | Pure Python; no external syslog library dependency |
| **`POST /ingest` batch endpoint** | Separate from `POST /events` (single-event Wave 1) | Vector sends batches; batch endpoint reduces HTTP overhead; explicit `source` label in body | `/events` preserved for backward compat; `/ingest` is the Phase 2+ primary path |
| **`POST /ingest/syslog` plain-text** | Accept raw syslog line as `text/plain` body | Vector `codec: text` sink sends raw lines; backend does the parsing so Vector config stays simple | CEF and RFC3164 both land here; backend classifies format |
| **`GET /events/stream` SSE** | Server-Sent Events for live browser push | Standard Web API; works through Caddy proxy; no WebSocket complexity; heartbeat every 15s | `EventSourceResponse` from `sse-starlette` (already in deps); frontend uses polling as primary, SSE as optional upgrade |
| **OpenSearch sink as env-var-activated scaffold** | `OPENSEARCH_URL` env var gates indexing | OpenSearch not always running in dev; env-var activation avoids startup failures | Silent no-op when unset; Phase 3 enables unconditionally once health confirmed |
| **Vector syslog on port 6514 TCP** | Use IANA syslog-tls port 6514, not 514 | Port 514 requires root on Linux; 6514 avoids privilege escalation in container | Clients must target 6514 for TCP syslog; UDP 514 still used for legacy compat |
| **`IngestSource` enum on `NormalizedEvent`** | Track event provenance in schema | Auditing: analysts need to know if an event came from fixture/syslog/vector/api | Source label preserved all the way to `/events` response and `/graph` nodes |
