# Phase 3: Detection + RAG - Context

**Gathered:** 2026-03-15
**Status:** Ready for planning
**Source:** PRD Express Path (user-provided requirements)

<domain>
## Phase Boundary

Phase 3 delivers two concrete capabilities on top of the Phase 2 ingestion pipeline:

1. **OpenSearch integration** — events written to a live `soc-events` index, queryable via a backend search endpoint.
2. **Sigma-based detection** — a YAML Sigma rule directory, a loader, and at least one working rule (`suspicious_dns.yml`) whose matches appear in `/alerts`.

Phase 3 does NOT attempt the full pySigma DuckDB backend, LangGraph RAG pipeline, or ATT&CK enrichment service from the original ROADMAP — those are deferred to Phase 4+. This keeps the phase shippable in a single session.

</domain>

<decisions>
## Implementation Decisions

### OpenSearch Indexing
- OpenSearch index name: `soc-events`
- Backend must write every ingested event to `soc-events` (unconditional — remove the env-var SCAFFOLD gate from Phase 2)
- `docker-compose.yml` backend service must have `OPENSEARCH_URL=http://opensearch:9200` set and `depends_on: opensearch` with a health wait

### Search Endpoint
- Endpoint: `GET /search?q=<query_string>`
- Searches the `soc-events` OpenSearch index using a multi-field query string
- Returns a JSON array of matching events (same schema as `/events`)
- Source of truth: OpenSearch (not in-memory store)

### Vector → OpenSearch Sink
- Vector pipeline must have an OpenSearch sink writing all ingested syslog/fixture events directly to OpenSearch
- Sink target: `http://opensearch:9200` on the `soc-events` index

### Sigma Rules
- Directory: `backend/src/detection/sigma/` (YAML files)
- First rule file: `suspicious_dns.yml` — matches events where `query` matches suspicious domain patterns
- Rule loader: `backend/src/detection/sigma_loader.py` — scans directory, loads YAML, compiles to matcher-compatible form
- Detection engine reads Sigma rules **in addition to** the existing Python rules in `rules.py`

### Alerts Integration
- Sigma rule matches must produce `Alert` objects identical in schema to those from Python rules
- All Sigma-matched alerts appear in `GET /alerts` response
- `rule` field on alert = Sigma rule ID from the YAML file

### Compatibility
- `GET /graph`, `GET /timeline`, `GET /events` — unchanged behavior
- Docker Compose stack must continue to start cleanly with `docker compose up -d --build`
- All existing 32 tests (Wave 1 + Phase 2) must continue to pass

### Claude's Discretion
- Choice of OpenSearch client library (httpx-based from Phase 2 scaffold, or `opensearch-py`)
- Sigma YAML schema (use pySigma-compatible subset or custom minimal schema)
- Search response pagination (not required in Phase 3)
- How to handle OpenSearch unavailability gracefully (log + skip, do not crash ingestion)

</decisions>

<specifics>
## Specific Ideas

- Phase 2 already has `backend/src/ingestion/opensearch_sink.py` as a scaffold — unconditionally activate it
- Phase 2 `infra/vector/vector.yaml` already has a commented-out `opensearch_events` sink block — uncomment and wire it
- The `suspicious_dns.yml` Sigma rule should match the same domain patterns already in `enricher.py` (`SUSPICIOUS_DOMAINS` set) so existing test fixtures fire it
- `sigma_loader.py` should fail gracefully if `pySigma` is not installed — log a warning and skip (avoids adding a heavy dependency before it's needed)
- Tests: at minimum `test_search_endpoint` (happy path + empty result) and `test_sigma_loader` (load rule, confirm rule ID present)

</specifics>

<deferred>
## Deferred Ideas

- Full pySigma DuckDB backend (custom SQL base class extension) → Phase 4
- LangGraph RAG pipeline + POST /query SSE endpoint → Phase 4
- ATT&CK technique enrichment → Phase 4
- Contextual anomaly detector (per-entity baselines, z-score) → Phase 4
- Citation verification layer → Phase 4
- Sigma smoke test suite (10 rules against crafted events) → Phase 4

</deferred>

---

*Phase: 03-detection-rag*
*Context gathered: 2026-03-15 via PRD Express Path*
