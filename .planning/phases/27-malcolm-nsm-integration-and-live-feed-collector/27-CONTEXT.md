# Phase 27: Malcolm NSM Integration and Live Feed Collector — Context

**Gathered:** 2026-04-07
**Status:** Ready for planning
**Source:** PRD Express Path (C:\Users\Admin\Downloads\soc-integration-prompt.md)

<domain>
## Phase Boundary

This phase connects local-ai-soc to a live Malcolm NSM instance on the LAN (192.168.1.22).
It delivers a polling collector that ingests Suricata alerts and IPFire syslog from Malcolm's
OpenSearch indices, wires recommendation dispatch validation into the existing approval flow,
syncs the remote ChromaDB corpus locally, and verifies the full alert pipeline end-to-end.

Nothing in this phase changes the existing DuckDB/Chroma/SQLite schema or event normalization
logic — all new behaviour is additive (new collector, new settings, new scripts).

</domain>

<decisions>
## Implementation Decisions

### Infrastructure — Expose OpenSearch to LAN (P27-T01)
- Locked: SSH to opsadmin@192.168.1.22 and expose OpenSearch port 9200 to LAN
- Preferred option: Add `- "9200:9200"` port mapping to Malcolm's OpenSearch service in
  docker-compose.yml on the Malcolm server (Option A — simpler, no extra proxy needed)
- OpenSearch already has TLS + internal auth — no extra security layer needed
- Verification: `curl -sk -u "admin:Adam1000!" https://192.168.1.22:9200/_cat/indices` from
  Windows host must return index list
- Internal OpenSearch credentials discoverable via:
  `docker exec malcolm-dashboards-helper-1 cat /var/local/curlrc/.opensearch.primary.curlrc`

### MalcolmCollector (P27-T02)
- Locked: New file `ingestion/jobs/malcolm_collector.py` — do NOT modify FirewallCollector
- Locked: Uses `httpx` (already a dependency via FastAPI ecosystem) with `verify=False` for
  self-signed TLS certs; do NOT use `opensearch-py` (adds a heavy dep for no gain over httpx)
- Locked: Polls two index patterns:
  - `arkime_sessions3-*` filtered by `event.dataset:alert` → Suricata alerts
  - `malcolm_beats_syslog_*` → IPFire syslog events
- Locked: Tracks last-seen `@timestamp` per index pattern in SQLite `system_kv` table
  (keys: `malcolm.alerts.last_timestamp`, `malcolm.syslog.last_timestamp`)
- Locked: Normalizes to NormalizedEvent — maps Malcolm fields to existing schema:
  - source_type: "suricata_eve" for alerts, "ipfire_syslog" for syslog
  - severity: mapped from event.severity or alert.severity field
  - src_ip, dst_ip, src_port, dst_port from network fields
  - detection_source: alert.signature for Suricata alerts
  - raw_event: JSON-serialized source doc (truncated to 8KB)
- Locked: Poll interval from settings.MALCOLM_POLL_INTERVAL (default 30s)
- Locked: Exponential backoff on consecutive failures (mirrors FirewallCollector pattern)
- Locked: Heartbeat event emitted each cycle to system_kv (`malcolm.last_heartbeat`)

### Settings (P27-T03)
- Locked: Add to `backend/core/config.py` (pydantic-settings):
  ```
  MALCOLM_OPENSEARCH_URL: str = "https://192.168.1.22:9200"
  MALCOLM_OPENSEARCH_USER: str = "admin"
  MALCOLM_OPENSEARCH_PASS: str = ""
  MALCOLM_OPENSEARCH_VERIFY_SSL: bool = False
  MALCOLM_POLL_INTERVAL: int = 30
  MALCOLM_ENABLED: bool = False  # opt-in; FirewallCollector pattern
  ```
- Locked: `.env.example` updated with all MALCOLM_* vars
- Locked: MalcolmCollector registered in `backend/main.py` lifespan under
  `if settings.MALCOLM_ENABLED:` guard (same pattern as FirewallCollector)

### Recommendation Dispatch Validation (P27-T04)
- Locked: The existing PATCH /api/recommendations/{id}/approve endpoint already validates
  gate conditions. Add a "dispatch" concept: a separate POST /api/recommendations/{id}/dispatch
  endpoint that:
  1. Requires status == "approved"
  2. Re-validates artifact against contracts/recommendation.schema.json (jsonschema)
  3. Returns 200 with {"dispatched": true, "artifact": <validated_artifact>} on success
  4. Returns 422 with {"error": "schema_validation_failed", "detail": <errors>} on failure
  5. Does NOT actually send to firewall (marked as future — no HTTP call out to firewall executor)
- Locked: Svelte dashboard adds "Dispatch" button on approved recommendation cards
  (button calls POST /api/recommendations/{id}/dispatch, shows success/error toast)
- Constraint: NEVER send raw LLM output to firewall — only schema-validated artifacts

### ChromaDB Corpus Sync (P27-T05)
- Locked: PowerShell script `scripts/sync-chroma-corpus.ps1` that:
  1. SSHs to opsadmin@192.168.1.22 and tars /var/lib/chromadb
  2. SCPs the tar to local temp directory
  3. Extracts to data/chroma-remote-corpus/ (separate from local data/chroma/)
  4. Logs collection count pre/post sync
- Decision (Claude's discretion): Keep remote corpus in a separate Chroma directory
  (data/chroma-remote-corpus/) rather than merging with local embeddings — avoids
  overwriting locally-indexed events with remote content
- Verification: After sync, `chroma_store.list_collections()` on the remote dir shows
  expected collection(s) with ~387 documents

### End-to-End Verification (P27-T06)
- Locked: PowerShell script `scripts/e2e-malcolm-verify.ps1` that:
  1. Triggers Suricata alert: SSH to IPFire root@192.168.1.1, run
     `curl -s http://testmynids.org/uid/index.html > /dev/null`
  2. Waits 90 seconds (Suricata → EVE → SCP → Malcolm → OpenSearch pipeline)
  3. Polls GET /api/events?severity=high (or similar) until alert appears or 3min timeout
  4. Reports pass/fail with timestamp
- Verification gate: Alert must appear in local-ai-soc within 2 × MALCOLM_POLL_INTERVAL
  after appearing in Malcolm OpenSearch

### Claude's Discretion
- Exact OpenSearch query DSL for timestamp-based pagination (search_after vs range query)
- Error handling strategy for partial OpenSearch response (retry vs skip batch)
- NormalizedEvent field mapping specifics for Malcolm's field naming conventions
- Test fixture strategy for MalcolmCollector unit tests (mock httpx responses)
- Svelte component structure for Dispatch button (inline on RecommendationCard vs modal)

</decisions>

<specifics>
## Specific References

### Malcolm OpenSearch Index Patterns
- Suricata alerts: `arkime_sessions3-*` with filter `event.dataset:alert` — 53K docs
- IPFire syslog: `malcolm_beats_syslog_*` — 628K docs
- ISM retention: 30-day hot-to-delete (malcolm-retention policy)

### Auth
- nginx proxy basic auth: `admin:Adam1000!` (used via Authorization header or -u flag)
- Internal OpenSearch credentials: from curlrc file at
  `/var/local/curlrc/.opensearch.primary.curlrc` on malcolm-dashboards-helper-1 container
- TLS: self-signed — always `verify=False` in httpx calls

### Existing Pattern to Mirror
- `ingestion/jobs/firewall_collector.py` — the MalcolmCollector must follow the same:
  - asyncio polling loop with backoff
  - heartbeat via SQLiteStore.set_kv()
  - ingest via IngestionLoader.ingest_events()
  - status() method returning dict

### Contracts
- Local: `contracts/recommendation.schema.json`
- Remote (for reference): `contracts/execution-receipt.schema.json` on firewall repo

### Constraints (hard stops)
- ADR-E02: Ollama on supportTAK-server binds to 127.0.0.1 — do not attempt LAN Ollama calls
- Never dispatch raw LLM output — only schema-validated, analyst-approved artifacts
- SSL verify=False is intentional and documented — do not treat as a bug

</specifics>

<deferred>
## Deferred Ideas

- Actual HTTP dispatch to firewall executor (POST to firewall API) — future phase
- Malcolm WebSocket real-time feed (instead of polling) — future optimization
- Bidirectional sync of ChromaDB (push local embeddings to remote) — future
- Malcolm dashboard integration (Kibana/OpenSearch Dashboards embed) — out of scope

</deferred>

---

*Phase: 27-malcolm-nsm-integration-and-live-feed-collector*
*Context gathered: 2026-04-07 via PRD Express Path*
