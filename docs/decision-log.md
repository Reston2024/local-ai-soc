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
