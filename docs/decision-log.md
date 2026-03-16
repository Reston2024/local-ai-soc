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

## Phase 5: Suricata EVE Parsing + Threat Scoring + ATT&CK Tagging — 2026-03-16

| Field | Value |
|-------|-------|
| Date | 2026-03-16 |
| Phase | Phase 5 Dashboard |
| Branch | feature/ai-soc-phase3-detection |
| Status | Implemented |

### Decisions

| # | Component | Decision | Reason | Impact |
|---|-----------|----------|--------|--------|
| 1 | **`dest_ip` → `dst_ip` mapping** | EVE uses `dest_ip`/`dest_port` (Snort convention), not `dst_ip`/`dst_port`. Parser explicitly maps `data.get("dest_ip")` → `dst_ip`. | Normalized schema uses `dst_ip`. Failing to do this leaves `dst_ip` as `None` for all Suricata events and suppresses graph IP nodes — a silent data loss trap. | Parser `suricata_parser.py` contains explicit `dst_ip = data.get("dest_ip")` mapping. Tests assert `dst_ip` is populated after parsing. |
| 2 | **Suricata severity is inverted** | EVE severity `1` = critical (highest priority), `4` = low (lowest). Mapping: `{1: "critical", 2: "high", 3: "medium", 4: "low"}`. | This is the Snort convention, opposite of common intuition. Common mistake: treating `1` as low. | Tests explicitly assert `severity=1` → `"critical"`. Inverted map documented in `_SEVERITY_MAP` constant. |
| 3 | **Threat scoring is additive integer 0–100** | Simple deterministic formula over ML model. Components: suricata severity (40/30/20/10) + sigma hit (+20) + recurrence (+10) + graph connectivity (+10). Capped at 100. | ML model deferred — no training data available. Deterministic formula is auditable, reproducible, and tunable without retraining. No floating-point, no weights to tune. | `threat_scorer.py` `score_alert()` returns `int` in `[0, 100]`. Every component is independently testable. |
| 4 | **`score_alert` graph_connectivity defaults to `None`/skip** | `score_alert()` accepts `graph_data: dict | None = None`; when `None`, the +10 graph connectivity component is skipped. | Calling `build_graph()` inside `_store_event()` for every event would be O(n²) for batch ingestion. Correct tradeoff: connectivity scoring available for on-demand calls, skipped for batch ingest. | Batch ingest scores are capped at 90 (missing graph component). On-demand callers can pass pre-built graph data to reach 100. |
| 5 | **Deferred import for `threat_scorer` + `attack_mapper` in `routes.py`** | Module-level imports fail at backend startup if modules are absent during incremental development. Deferred import with `try/except ImportError` inside `_store_event()`. | Mirrors `sigma_loader.py` pattern — graceful degradation. Backend stays startable even if Phase 5 modules are partially written. | If import fails, scoring and tagging are silently skipped. Warning logged. No runtime crash. |
| 6 | **ATT&CK tagging is a static 5-entry lookup** | Full ATT&CK coverage (700+ techniques) deferred. Static mapping covers five most actionable categories. Returns `[]` for unmapped events — no guessing. | 700+ technique corpus requires ongoing maintenance and a mapping heuristic that would produce false confidence. Static 5-entry map is accurate for what it covers. | `attack_mapper.py` module docstring documents the coverage boundary explicitly. Unmapped events get empty `attack_tags`. |
| 7 | **Suricata Docker service is scaffolded with Windows blocker** | `jasonish/suricata` requires `--net=host` and Linux kernel capabilities (`net_admin`, `net_raw`, `sys_nice`) that Docker Desktop for Windows (WSL2 backend) does not provide. NFQUEUE kernel module unavailable. | Cannot run live network capture on Windows Docker. Scaffold added to `docker-compose.yml` with documented blocker; validation uses `fixtures/suricata_eve_sample.ndjson` only. | Live Suricata capture is Linux-only. Windows development uses fixture files. Scaffold remains for production Linux deployment. |
| 8 | **`alert` event_type = `alert.signature`, not `"alert"`** | For Suricata alert events, `event_type` is set to the rule signature string (e.g., `"ET MALWARE CobaltStrike Beacon"`), not the generic `"alert"`. | Allows Sigma rules and enrichment logic to match on the specific signature text rather than a generic bucket. Sigma rules can target `event_type contains "CobaltStrike"`. | All Suricata alert events carry the full signature as their `event_type`. Generic `"alert"` is never stored for Suricata events. |
