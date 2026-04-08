# Phase 27: Malcolm NSM Integration and Live Feed Collector — Research

**Researched:** 2026-04-07
**Domain:** OpenSearch polling, async collectors, FastAPI endpoint extension, PowerShell automation
**Confidence:** HIGH (all findings derived from direct source inspection)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Infrastructure — Expose OpenSearch to LAN (P27-T01)**
- SSH to opsadmin@192.168.1.22 and add `- "9200:9200"` port mapping to Malcolm's OpenSearch
  service in docker-compose.yml (Option A — no extra proxy)
- Verification: `curl -sk -u "admin:Adam1000!" https://192.168.1.22:9200/_cat/indices` from Windows

**MalcolmCollector (P27-T02)**
- New file `ingestion/jobs/malcolm_collector.py` — do NOT modify FirewallCollector
- httpx with `verify=False` — do NOT add opensearch-py
- Polls two index patterns:
  - `arkime_sessions3-*` filtered by `event.dataset:alert` → source_type "suricata_eve"
  - `malcolm_beats_syslog_*` → source_type "ipfire_syslog"
- Cursor tracking in SQLite system_kv: `malcolm.alerts.last_timestamp`, `malcolm.syslog.last_timestamp`
- Field mapping: src_ip/dst_ip/src_port/dst_port from network fields; detection_source from
  alert.signature; raw_event JSON-serialized truncated to 8KB
- Poll interval from settings.MALCOLM_POLL_INTERVAL (default 30s)
- Exponential backoff on consecutive failures
- Heartbeat to system_kv key `malcolm.last_heartbeat` each cycle

**Settings (P27-T03)**
```
MALCOLM_OPENSEARCH_URL: str = "https://192.168.1.22:9200"
MALCOLM_OPENSEARCH_USER: str = "admin"
MALCOLM_OPENSEARCH_PASS: str = ""
MALCOLM_OPENSEARCH_VERIFY_SSL: bool = False
MALCOLM_POLL_INTERVAL: int = 30
MALCOLM_ENABLED: bool = False
```
- `.env.example` updated with all MALCOLM_* vars
- Registered in `backend/main.py` lifespan under `if settings.MALCOLM_ENABLED:` guard

**Recommendation Dispatch Validation (P27-T04)**
- New POST /api/recommendations/{id}/dispatch endpoint:
  1. Requires status == "approved"
  2. Re-validates artifact against contracts/recommendation.schema.json (jsonschema)
  3. Returns 200 `{"dispatched": true, "artifact": <validated_artifact>}` on success
  4. Returns 422 `{"error": "schema_validation_failed", "detail": <errors>}` on failure
  5. Does NOT make HTTP calls to firewall (future phase)
- Svelte dashboard adds "Dispatch" button on approved recommendation cards

**ChromaDB Corpus Sync (P27-T05)**
- PowerShell script `scripts/sync-chroma-corpus.ps1`:
  1. SSH to opsadmin@192.168.1.22, tar /var/lib/chromadb
  2. SCP tar to local temp directory
  3. Extract to data/chroma-remote-corpus/ (separate from data/chroma/)
  4. Log collection count pre/post sync
- Remote corpus kept separate — no merge with local data/chroma/

**End-to-End Verification (P27-T06)**
- PowerShell script `scripts/e2e-malcolm-verify.ps1`:
  1. SSH to IPFire root@192.168.1.1, run `curl -s http://testmynids.org/uid/index.html > /dev/null`
  2. Wait 90 seconds for Suricata → EVE → SCP → Malcolm → OpenSearch pipeline
  3. Poll GET /api/events?severity=high until alert appears or 3min timeout
  4. Report pass/fail with timestamp
- Verification gate: alert must appear within 2 × MALCOLM_POLL_INTERVAL after reaching OpenSearch

**Hard Stops**
- ADR-E02: Ollama on supportTAK-server binds to 127.0.0.1 — do not attempt LAN Ollama calls
- Never dispatch raw LLM output — only schema-validated, analyst-approved artifacts
- SSL verify=False is intentional — do not treat as a bug

### Claude's Discretion
- Exact OpenSearch query DSL for timestamp-based pagination (search_after vs range query)
- Error handling strategy for partial OpenSearch response (retry vs skip batch)
- NormalizedEvent field mapping specifics for Malcolm's field naming conventions
- Test fixture strategy for MalcolmCollector unit tests (mock httpx responses)
- Svelte component structure for Dispatch button (inline on RecommendationCard vs modal)

### Deferred Ideas (OUT OF SCOPE)
- Actual HTTP dispatch to firewall executor — future phase
- Malcolm WebSocket real-time feed — future optimization
- Bidirectional ChromaDB sync — future
- Malcolm dashboard integration (Kibana/OpenSearch Dashboards embed) — out of scope
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| P27-T01 | Expose Malcolm OpenSearch (port 9200) to LAN via docker-compose port mapping on 192.168.1.22 | SSH commands documented; verification curl command specified in CONTEXT.md |
| P27-T02 | MalcolmCollector in ingestion/jobs/malcolm_collector.py — polls OpenSearch, normalizes to NormalizedEvent, tracks timestamp cursor in SQLite KV | FirewallCollector pattern fully read; SQLiteStore.set_kv/get_kv API confirmed; NormalizedEvent schema confirmed; httpx already in deps |
| P27-T03 | Settings integration — MALCOLM_* pydantic-settings fields in backend/core/config.py + main.py lifespan registration | Settings class pattern confirmed from config.py; FIREWALL_ENABLED guard pattern confirmed from main.py |
| P27-T04 | Recommendation dispatch validation — POST /api/recommendations/{id}/dispatch | recommendations.py router confirmed; RecommendationArtifact model + jsonschema already wired; _run_approval_gate pattern available for reuse |
| P27-T05 | ChromaDB corpus sync script (scripts/sync-chroma-corpus.ps1) | Windows PowerShell SSH/SCP patterns confirmed; target path data/chroma-remote-corpus/ decided |
| P27-T06 | End-to-end verification script (scripts/e2e-malcolm-verify.ps1) | Trigger mechanism (testmynids.org curl on IPFire), polling pattern, timeout logic defined |
</phase_requirements>

---

## Summary

Phase 27 connects the local AI-SOC-Brain platform to a live Malcolm NSM instance at 192.168.1.22 via its OpenSearch API. All work is additive — no existing schemas, parsers, or store interfaces change. The central deliverable is a new async background collector (`MalcolmCollector`) that follows the exact same structural pattern as the existing `FirewallCollector`: polling loop, exponential backoff, heartbeat via `SQLiteStore.set_kv()`, and ingestion via `IngestionLoader.ingest_events()`. The key difference is that the data source is a remote HTTPS OpenSearch cluster rather than local files, requiring httpx HTTP calls with `verify=False` and timestamp-cursor pagination.

The second major deliverable is a new dispatch endpoint added to the existing recommendations router. The infrastructure for this endpoint already exists: `RecommendationArtifact` already validates against `contracts/recommendation.schema.json` via jsonschema inside its `model_validator`. The endpoint only needs to load the approved record, reconstruct the `RecommendationArtifact`, and return it — the pydantic model does the schema validation automatically. This is intentionally a no-op dispatch (no firewall HTTP call).

The two PowerShell scripts (corpus sync and e2e verification) are straightforward automation. The project runs on Windows with Python 3.12 via uv; SSH/SCP use Windows's built-in OpenSSH client (`ssh.exe`/`scp.exe`) and the Malcolm host is Ubuntu 22.04 reachable at 192.168.1.22.

**Primary recommendation:** Follow the FirewallCollector implementation exactly as the structural template. Read `ingestion/jobs/firewall_collector.py` and `backend/main.py` lifespan section 8b as the authoritative blueprint — every structural choice in MalcolmCollector should mirror those files.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| httpx | 0.28.1 (pinned) | HTTP client for OpenSearch REST calls | Already in pyproject.toml; used by FastAPI ecosystem; async-capable; supports verify=False |
| jsonschema | (transitive via chromadb/pydantic) | JSON Schema validation for dispatch endpoint | Already imported in backend/models/recommendation.py; no new dep needed |
| pydantic-settings | 2.13.1 | MALCOLM_* settings fields | Project standard for all config; already in use |
| asyncio.to_thread | stdlib | Wrap blocking httpx.get() calls | Project convention for all blocking I/O — see FirewallCollector._read_new_lines |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Python OpenSSH (ssh.exe / scp.exe) | Windows built-in | SSH to Malcolm server, SCP corpus tar | Used in .ps1 scripts; Windows 10/11 ships OpenSSH client by default |
| FastAPI TestClient | via fastapi | Integration tests for dispatch endpoint | Same pattern as test_recommendation_api.py |
| pytest-asyncio (auto mode) | 1.3.0 | Async test support for MalcolmCollector tests | pyproject.toml already sets asyncio_mode = "auto" |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| httpx with verify=False | opensearch-py | opensearch-py is a heavy dep; httpx already present; verify=False is intentional for self-signed certs |
| SQLite KV cursor | file-based cursor / in-memory | SQLite KV is already established pattern in this codebase for heartbeat/cursor tracking |
| search_after pagination | range query on @timestamp | search_after is more reliable for deep pagination past 10K docs; range query is simpler for first page |

**Installation:** No new dependencies. All required libraries are already in pyproject.toml.

---

## Architecture Patterns

### Recommended Project Structure for New Files

```
ingestion/
  jobs/
    __init__.py              # Existing — no changes needed
    firewall_collector.py    # Existing — reference template only
    malcolm_collector.py     # NEW — MalcolmCollector class

backend/
  core/
    config.py                # MODIFY — add MALCOLM_* settings fields
  main.py                    # MODIFY — add MalcolmCollector lifespan block
  api/
    recommendations.py       # MODIFY — add /dispatch route

scripts/
  sync-chroma-corpus.ps1     # NEW — ChromaDB corpus sync
  e2e-malcolm-verify.ps1     # NEW — end-to-end alert verification

tests/
  unit/
    test_malcolm_collector.py    # NEW — unit tests (mock httpx)
    test_dispatch_endpoint.py    # NEW — dispatch route tests
```

### Pattern 1: MalcolmCollector Class Structure

**What:** Mirrors FirewallCollector exactly — asyncio polling loop, backoff, heartbeat, ingest via loader.

**When to use:** Every new background collector in this codebase follows this pattern.

```python
# Source: ingestion/jobs/firewall_collector.py (direct inspection)
class MalcolmCollector:
    def __init__(
        self,
        loader,         # IngestionLoader instance
        sqlite_store,   # SQLiteStore instance
        interval_sec: int = 30,
        opensearch_url: str = "https://192.168.1.22:9200",
        opensearch_user: str = "admin",
        opensearch_pass: str = "",
        verify_ssl: bool = False,
    ) -> None:
        self._loader = loader
        self._sqlite = sqlite_store
        self._interval = interval_sec
        self._url = opensearch_url
        self._auth = (opensearch_user, opensearch_pass)
        self._verify_ssl = verify_ssl
        self._consecutive_failures: int = 0
        self._running: bool = False
        self._alerts_ingested: int = 0
        self._syslog_ingested: int = 0

    async def run(self) -> None:
        """Main polling loop — mirrors FirewallCollector.run() exactly."""
        self._running = True
        backoff = self._interval
        try:
            while True:
                await asyncio.sleep(backoff)
                success = await self._poll_and_ingest()
                if success:
                    self._consecutive_failures = 0
                    backoff = self._interval
                else:
                    self._consecutive_failures += 1
                    backoff = min(self._interval * (2 ** self._consecutive_failures), 300)
        except asyncio.CancelledError:
            self._running = False
            raise

    def status(self) -> dict:
        return {
            "running": self._running,
            "alerts_ingested": self._alerts_ingested,
            "syslog_ingested": self._syslog_ingested,
            "consecutive_failures": self._consecutive_failures,
        }
```

### Pattern 2: OpenSearch Timestamp Cursor Query (Recommended DSL)

**What:** Use a range query on `@timestamp` with the last-seen value as the lower bound. On first run (no cursor), fetch the last 5 minutes only to avoid bulk-ingesting 53K/628K historical docs.

**When to use:** Every poll cycle, for both index patterns.

```python
# Source: Claude's discretion — based on OpenSearch/Elasticsearch Query DSL principles
# verified via direct index knowledge from CONTEXT.md
def _build_query(last_ts: str | None, event_dataset_filter: bool = False) -> dict:
    """
    Build a range query for new documents since last_ts.
    Falls back to last-5-minutes if no cursor (first run protection).
    """
    from datetime import datetime, timezone, timedelta
    if last_ts is None:
        # First run: only fetch events from last 5 minutes
        since = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
    else:
        since = last_ts

    must_clauses = [{"range": {"@timestamp": {"gt": since}}}]
    if event_dataset_filter:
        must_clauses.append({"term": {"event.dataset": "alert"}})

    return {
        "query": {"bool": {"must": must_clauses}},
        "sort": [{"@timestamp": "asc"}],
        "size": 500,  # batch size — tune based on poll interval
    }
```

**Alternative — search_after for deep pagination:**
If a single poll returns exactly `size` docs (more may exist), re-issue the query using `search_after` with the last document's sort values. This is important if bursts produce > 500 events in one interval.

```python
# Source: Claude's discretion — OpenSearch pagination pattern
async def _fetch_page(self, index: str, query: dict, search_after=None) -> list[dict]:
    if search_after:
        query = {**query, "search_after": search_after}
    resp = await asyncio.to_thread(
        self._http_get,
        f"{self._url}/{index}/_search",
        query,
    )
    return resp.get("hits", {}).get("hits", [])

def _http_get(self, url: str, body: dict) -> dict:
    """Synchronous httpx call — runs in asyncio.to_thread."""
    import httpx
    r = httpx.post(url, json=body, auth=self._auth, verify=self._verify_ssl, timeout=30.0)
    r.raise_for_status()
    return r.json()
```

### Pattern 3: Lifespan Registration (main.py)

**What:** Conditional collector startup under feature flag — mirrors the FIREWALL_ENABLED block in main.py section 8b exactly.

```python
# Source: backend/main.py lines 249-275 (direct inspection)
malcolm_task: asyncio.Task | None = None
if settings.MALCOLM_ENABLED:
    try:
        from ingestion.jobs.malcolm_collector import MalcolmCollector as _MCCollector
        from ingestion.loader import IngestionLoader as _MCLoader
        _mc_loader = _MCLoader(stores=stores, ollama_client=ollama)
        _mc_collector = _MCCollector(
            loader=_mc_loader,
            sqlite_store=sqlite_store,
            interval_sec=settings.MALCOLM_POLL_INTERVAL,
            opensearch_url=settings.MALCOLM_OPENSEARCH_URL,
            opensearch_user=settings.MALCOLM_OPENSEARCH_USER,
            opensearch_pass=settings.MALCOLM_OPENSEARCH_PASS,
            verify_ssl=settings.MALCOLM_OPENSEARCH_VERIFY_SSL,
        )
        malcolm_task = asyncio.ensure_future(_mc_collector.run())
        app.state.malcolm_collector = _mc_collector
        log.info("MalcolmCollector started", url=settings.MALCOLM_OPENSEARCH_URL)
    except ImportError as exc:
        log.warning("MalcolmCollector not available — skipping: %s", exc)
        app.state.malcolm_collector = None
else:
    log.info("Malcolm collection disabled (MALCOLM_ENABLED=False)")
    app.state.malcolm_collector = None
```

Cancel in shutdown block (after firewall_task cancel):
```python
if malcolm_task is not None and not malcolm_task.done():
    malcolm_task.cancel()
    try:
        await malcolm_task
    except asyncio.CancelledError:
        pass
```

### Pattern 4: Dispatch Endpoint

**What:** POST /api/recommendations/{id}/dispatch — load approved record, reconstruct RecommendationArtifact (pydantic validates against JSON schema automatically), return 200 or 422.

```python
# Source: backend/api/recommendations.py + backend/models/recommendation.py (direct inspection)
@router.post("/{recommendation_id}/dispatch")
async def dispatch_recommendation(
    recommendation_id: str, request: Request
) -> JSONResponse:
    stores = request.app.state.stores
    rows = await stores.duckdb.fetch_all(_SELECT_BY_ID, [recommendation_id])
    if not rows:
        raise HTTPException(status_code=404, detail="Recommendation not found")

    rec = _row_to_dict(rows[0])

    if rec.get("status") != "approved":
        raise HTTPException(status_code=409, detail="Recommendation must be approved before dispatch")

    # Reconstruct full artifact — RecommendationArtifact.model_validator runs jsonschema
    try:
        artifact = RecommendationArtifact(**rec)
    except (ValueError, Exception) as exc:
        return JSONResponse(
            status_code=422,
            content={"error": "schema_validation_failed", "detail": str(exc)},
        )

    return JSONResponse(
        status_code=200,
        content={"dispatched": True, "artifact": artifact.model_dump(mode="json")},
    )
```

**Key insight:** `RecommendationArtifact` already calls `jsonschema.validate()` inside its `model_validator`. No separate jsonschema call is needed in the route — just instantiating the model performs the full schema check.

### Pattern 5: Malcolm Field Mapping

**What:** Map Malcolm/OpenSearch document fields to NormalizedEvent fields.

```python
# Source: CONTEXT.md + direct inspection of suricata_eve_parser.py and ipfire_syslog_parser.py
# Malcolm arkime_sessions3-* alert document field paths (Suricata-derived):
MALCOLM_ALERT_FIELD_MAP = {
    # NormalizedEvent field -> Malcolm doc path
    "timestamp":        "@timestamp",
    "src_ip":           "source.ip",          # ECS-style; fallback: "src_ip"
    "dst_ip":           "destination.ip",     # ECS-style; fallback: "dest_ip"
    "src_port":         "source.port",        # fallback: "src_port"
    "dst_port":         "destination.port",   # fallback: "dest_port"
    "detection_source": "rule.name",          # or "alert.signature"
    "severity":         "event.severity",     # integer 1-4; map same as SuricataEveParser
    "network_protocol": "network.transport",  # or "proto"
}

# Malcolm malcolm_beats_syslog_* (IPFire iptables syslog via Filebeat/Logstash):
MALCOLM_SYSLOG_FIELD_MAP = {
    "timestamp":   "@timestamp",
    "hostname":    "host.name",   # or "log.syslog.hostname"
    "src_ip":      "source.ip",
    "dst_ip":      "destination.ip",
    "src_port":    "source.port",
    "dst_port":    "destination.port",
    "raw_event":   "_source",     # full JSON, truncated to 8KB
}
```

**NOTE — LOW confidence on exact Malcolm field paths:** Malcolm applies Logstash/Zeek enrichment that may rename fields. The planner should note that the first implementation pass may need field path corrections after observing real documents via `curl -sk -u "admin:Adam1000!" https://192.168.1.22:9200/arkime_sessions3-*/_search?size=1`. Always fall back to `_source.get("src_ip") or _source.get("source", {}).get("ip")` pattern with cascading lookups.

### Anti-Patterns to Avoid

- **Importing FirewallCollector inside MalcolmCollector:** They are independent — MalcolmCollector is standalone.
- **Calling opensearch-py:** Not in deps, intentionally excluded. Use httpx.
- **Merging remote Chroma corpus into data/chroma/:** Sync only to data/chroma-remote-corpus/ to avoid corrupting local event embeddings.
- **Dispatching without status == "approved" check:** The dispatch endpoint MUST gate on status first, before schema validation.
- **Raw httpx calls in async context without asyncio.to_thread:** Project convention requires all blocking I/O in asyncio.to_thread. httpx synchronous client must be called via asyncio.to_thread.
- **First-run bulk ingestion:** Without a cursor guard on first run, the collector would attempt to ingest 53K alerts immediately. Always default to "last 5 minutes" on first run.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| JSON Schema validation | Custom field-by-field checks | `RecommendationArtifact` pydantic model (already validates via jsonschema in model_validator) | Model already does full Draft 2020-12 validation including allOf cross-field constraints |
| Timestamp parsing | Custom ISO-8601 parser | `datetime.fromisoformat()` with `.replace("Z", "+00:00")` | Established pattern in SuricataEveParser._parse_eve_timestamp() |
| Exponential backoff | Custom backoff library | `min(interval * (2 ** failures), 300)` — already in FirewallCollector.run() | One-liner that caps at 5 minutes; matches existing pattern |
| OpenSearch auth | Custom auth header builder | httpx `auth=(user, pass)` tuple | httpx handles Basic auth natively |
| Async blocking-call wrapper | Custom thread pool | `await asyncio.to_thread(fn, ...)` | Project-wide convention; never call blocking code directly in async |

**Key insight:** The recommendation schema validation is entirely handled by instantiating `RecommendationArtifact`. The dispatch endpoint is essentially: load record → construct model → return 200 or catch ValueError → return 422. No custom validation logic needed.

---

## Common Pitfalls

### Pitfall 1: First-Run Bulk Ingestion Flood

**What goes wrong:** On first startup with MALCOLM_ENABLED=True and no cursor in SQLite, a range query with no lower bound (or `gt: epoch`) matches all 53K alerts and 628K syslog events. This floods DuckDB and hangs the ingest pipeline.

**Why it happens:** SQLiteStore.get_kv("malcolm.alerts.last_timestamp") returns None on first run.

**How to avoid:** In `_build_query()`, when `last_ts is None`, set the range lower bound to `now - 5 minutes` (or a configurable lookback). Document this as "initial catchup window."

**Warning signs:** First poll takes > 30 seconds; DuckDB write queue depth spikes.

### Pitfall 2: Malcolm OpenSearch TLS Certificate Rejection

**What goes wrong:** httpx raises `httpx.ConnectError: [SSL: CERTIFICATE_VERIFY_FAILED]`.

**Why it happens:** Malcolm uses self-signed certificates. verify=True is httpx's default.

**How to avoid:** Always pass `verify=False` when `settings.MALCOLM_OPENSEARCH_VERIFY_SSL` is False. Add `# noqa: S501` or equivalent comment noting this is intentional.

**Warning signs:** httpx.ConnectError in collector logs on first run.

### Pitfall 3: OpenSearch Port 9200 Not Exposed After Docker Restart

**What goes wrong:** Malcolm docker-compose.yml port mapping is correct but OpenSearch is unreachable after Malcolm auto-restarts (it reverts to previous config).

**Why it happens:** Malcolm's `docker-compose.yml` may be regenerated from templates by Malcolm's management scripts.

**How to avoid:** Note in P27-T01 task that the port mapping may need to be re-applied if Malcolm updates. The e2e verification script (P27-T06) implicitly catches this — run it before declaring the phase complete.

**Warning signs:** curl verification returns connection refused after Malcolm update.

### Pitfall 4: RecommendationArtifact Instantiation Fails for Old Records

**What goes wrong:** Approved recommendations created before Phase 24 may have NULL fields (e.g., `model_run_id`) that fail `RecommendationArtifact` validation, making them undispatchable.

**Why it happens:** The `status` column can be "approved" for records that pre-date the full schema enforcement in pydantic.

**How to avoid:** The dispatch endpoint's `except ValueError` catch handles this — it returns 422 with the validation detail. Log the failing recommendation_id so the analyst can investigate. Do not silently swallow the error.

**Warning signs:** POST /dispatch returns 422 for a record the analyst believes is valid.

### Pitfall 5: asyncio.to_thread Missing for httpx Sync Client

**What goes wrong:** httpx synchronous `.post()` blocks the event loop during the OpenSearch poll, freezing all other FastAPI requests for the poll duration (potentially seconds).

**Why it happens:** httpx has both sync (`httpx.Client`) and async (`httpx.AsyncClient`) interfaces. The project convention for any blocking I/O is `asyncio.to_thread`.

**How to avoid:** Either use `httpx.AsyncClient` with `async with` in the async poll method, or use `httpx.Client` wrapped in `asyncio.to_thread`. The async client approach is cleaner for collectors.

**Warning signs:** API request latency spikes every 30 seconds (correlated with poll interval).

### Pitfall 6: Duplicate Event Ingestion on Cursor Loss

**What goes wrong:** If Malcolm restarts and SQLite cursor is lost (or set_kv fails), the collector re-ingests already-seen events.

**Why it happens:** Cursor is stored in SQLite; if SQLite is deleted or corrupted, cursor resets.

**How to avoid:** `loader.ingest_events()` routes through `INSERT OR IGNORE` in DuckDB (confirmed in `loader.py` `_INSERT_SQL`). Duplicates are silently skipped by event_id deduplication. The cursor should be updated *after* successful ingest of a batch, not before.

**Warning signs:** DuckDB event count grows unexpectedly after restarts without new network traffic.

---

## Code Examples

### OpenSearch Search Request via httpx

```python
# Source: Claude's discretion — based on OpenSearch REST API (well-known standard)
# Verified pattern: httpx 0.28.1 is pinned in pyproject.toml
import httpx

def _search_opensearch(url: str, index: str, query: dict, auth: tuple, verify: bool) -> dict:
    """Synchronous OpenSearch search — call via asyncio.to_thread."""
    endpoint = f"{url}/{index}/_search"
    with httpx.Client(verify=verify, timeout=30.0) as client:
        resp = client.post(endpoint, json=query, auth=auth)
        resp.raise_for_status()
        return resp.json()
```

### Timestamp Cursor Read/Write Pattern

```python
# Source: backend/stores/sqlite_store.py lines 1481-1498 (direct inspection)
# Pattern used by FirewallCollector via asyncio.to_thread
async def _update_cursor(self, key: str, value: str) -> None:
    await asyncio.to_thread(self._sqlite.set_kv, key, value)

async def _read_cursor(self, key: str) -> str | None:
    return await asyncio.to_thread(self._sqlite.get_kv, key)
```

### Heartbeat Pattern (mirrors FirewallCollector exactly)

```python
# Source: ingestion/jobs/firewall_collector.py lines 128-144 (direct inspection)
async def _emit_heartbeat(self) -> None:
    iso_str = datetime.now(timezone.utc).isoformat()
    await asyncio.to_thread(self._sqlite.set_kv, "malcolm.last_heartbeat", iso_str)
    heartbeat_event = NormalizedEvent(
        event_id=str(uuid4()),
        timestamp=datetime.now(timezone.utc),
        ingested_at=datetime.now(timezone.utc),
        source_type="malcolm_heartbeat",
        hostname="malcolm",
        event_type="heartbeat",
        severity="info",
        detection_source="malcolm_collector",
        raw_event=json.dumps({"type": "heartbeat", "ts": iso_str}),
    )
    await self._loader.ingest_events([heartbeat_event])
```

### pydantic-settings Field Addition (config.py)

```python
# Source: backend/core/config.py (direct inspection) — append after FIREWALL_* block
# Malcolm NSM live telemetry collector
MALCOLM_ENABLED: bool = False
MALCOLM_OPENSEARCH_URL: str = "https://192.168.1.22:9200"
MALCOLM_OPENSEARCH_USER: str = "admin"
MALCOLM_OPENSEARCH_PASS: str = ""
MALCOLM_OPENSEARCH_VERIFY_SSL: bool = False
MALCOLM_POLL_INTERVAL: int = 30
```

### PowerShell SSH Pattern (Windows built-in OpenSSH)

```powershell
# Source: Claude's discretion — standard Windows OpenSSH client usage
# Windows 10/11 ships ssh.exe and scp.exe in C:\Windows\System32\OpenSSH\
# Use -o StrictHostKeyChecking=no for unattended automation on known hosts

$result = ssh -o StrictHostKeyChecking=no opsadmin@192.168.1.22 "docker exec malcolm-dashboards-helper-1 cat /var/local/curlrc/.opensearch.primary.curlrc"

# SCP a file from remote:
scp -o StrictHostKeyChecking=no opsadmin@192.168.1.22:/tmp/chroma.tar.gz "$env:TEMP\chroma.tar.gz"
```

### NormalizedEvent Mapping for Suricata Alerts from Malcolm

```python
# Source: ingestion/parsers/suricata_eve_parser.py (direct inspection) — reuse field logic
# Malcolm's arkime_sessions3-* docs are Suricata EVE records enriched by Zeek/Logstash.
# They share field semantics but may use ECS paths (source.ip) rather than EVE paths (src_ip).

_SEVERITY_MAP = {1: "critical", 2: "high", 3: "medium", 4: "low"}

def _map_alert_doc(doc: dict) -> NormalizedEvent:
    src = doc.get("_source", {})
    sev_int = src.get("event", {}).get("severity") or src.get("alert", {}).get("severity", 4)
    return NormalizedEvent(
        event_id=str(uuid4()),
        timestamp=_parse_ts(src.get("@timestamp")),
        ingested_at=datetime.now(timezone.utc),
        source_type="suricata_eve",
        hostname=src.get("host", {}).get("name") or src.get("host"),
        src_ip=src.get("source", {}).get("ip") or src.get("src_ip"),
        dst_ip=src.get("destination", {}).get("ip") or src.get("dest_ip"),
        src_port=_safe_int(src.get("source", {}).get("port") or src.get("src_port")),
        dst_port=_safe_int(src.get("destination", {}).get("port") or src.get("dest_port")),
        severity=_SEVERITY_MAP.get(int(sev_int) if sev_int else 4, "low"),
        detection_source=src.get("rule", {}).get("name") or src.get("alert", {}).get("signature"),
        event_type="detection",
        network_protocol=src.get("network", {}).get("transport") or src.get("proto"),
        raw_event=json.dumps(src, default=str)[:8192],
    )
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| opensearch-py SDK | httpx direct REST calls | Phase 27 decision (CONTEXT.md) | Removes heavy dep; requires manual query DSL |
| Real-time WebSocket feed | Polling with cursor | Phase 27 decision (deferred) | Simpler to implement; 30s latency acceptable |
| Merge remote Chroma into local | Separate directory data/chroma-remote-corpus/ | Phase 27 decision | Preserves local event embeddings |

---

## Open Questions

1. **Exact Malcolm ECS field paths for alerts**
   - What we know: Malcolm enriches Suricata EVE with Zeek and Logstash, likely applying ECS field renaming (source.ip, destination.ip, rule.name)
   - What's unclear: Whether Malcolm 26.02.0 applies consistent ECS naming or has a mix
   - Recommendation: The planner should include a "discover fields" subtask in Wave 0 — run `curl -sk -u "admin:Adam1000!" https://192.168.1.22:9200/arkime_sessions3-*/_search?size=1 | python -m json.tool` and capture one real document. Use cascading field lookups (`src.get("source", {}).get("ip") or src.get("src_ip")`) as defensive defaults.

2. **Chroma version on Malcolm supportTAK-server**
   - What we know: Remote corpus expected to have ~387 documents; target at data/chroma-remote-corpus/
   - What's unclear: Whether the remote Chroma version (on supportTAK-server) is compatible with local chromadb==1.5.5 for reading the extracted directory
   - Recommendation: The sync script should log the collection names and document counts. If format is incompatible, Phase 27 deliverable is the sync script itself; Chroma access from Python is a separate follow-on step.

3. **Malcolm docker-compose.yml location on 192.168.1.22**
   - What we know: Malcolm runs 27 Docker containers; docker-compose.yml likely at /opt/malcolm/ or ~/malcolm/
   - What's unclear: Exact path — Malcolm documentation shows multiple install locations
   - Recommendation: P27-T01 task should include a discovery step: `ssh opsadmin@192.168.1.22 "find / -name docker-compose.yml -path '*/malcolm*' 2>/dev/null"` before editing.

---

## Validation Architecture

Nyquist validation is enabled (`workflow.nyquist_validation: true` in .planning/config.json).

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 + pytest-asyncio 1.3.0 |
| Config file | pyproject.toml (`[tool.pytest.ini_options]` asyncio_mode = "auto") |
| Quick run command | `uv run pytest tests/unit/test_malcolm_collector.py tests/unit/test_dispatch_endpoint.py -x` |
| Full suite command | `uv run pytest tests/unit/ -x` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| P27-T02 | MalcolmCollector queries OpenSearch with timestamp cursor | unit | `uv run pytest tests/unit/test_malcolm_collector.py::TestMalcolmCollectorCursorQuery -x` | Wave 0 |
| P27-T02 | MalcolmCollector normalizes alert doc to NormalizedEvent with source_type="suricata_eve" | unit | `uv run pytest tests/unit/test_malcolm_collector.py::TestAlertNormalization -x` | Wave 0 |
| P27-T02 | MalcolmCollector normalizes syslog doc to NormalizedEvent with source_type="ipfire_syslog" | unit | `uv run pytest tests/unit/test_malcolm_collector.py::TestSyslogNormalization -x` | Wave 0 |
| P27-T02 | Heartbeat stored in system_kv with key "malcolm.last_heartbeat" | unit | `uv run pytest tests/unit/test_malcolm_collector.py::TestHeartbeat -x` | Wave 0 |
| P27-T02 | Consecutive failures increase backoff (same pattern as FirewallCollector) | unit | `uv run pytest tests/unit/test_malcolm_collector.py::TestBackoff -x` | Wave 0 |
| P27-T02 | First-run protection: no cursor defaults to last-5-minutes range | unit | `uv run pytest tests/unit/test_malcolm_collector.py::TestFirstRunProtection -x` | Wave 0 |
| P27-T03 | MALCOLM_* fields present in Settings class | unit | `uv run pytest tests/unit/test_config.py -x -k malcolm` | Modify existing |
| P27-T04 | POST /api/recommendations/{id}/dispatch returns 200 for approved record | unit | `uv run pytest tests/unit/test_dispatch_endpoint.py::TestDispatchApproved -x` | Wave 0 |
| P27-T04 | POST /api/recommendations/{id}/dispatch returns 409 for non-approved record | unit | `uv run pytest tests/unit/test_dispatch_endpoint.py::TestDispatchNotApproved -x` | Wave 0 |
| P27-T04 | POST /api/recommendations/{id}/dispatch returns 422 for schema-invalid artifact | unit | `uv run pytest tests/unit/test_dispatch_endpoint.py::TestDispatchSchemaFail -x` | Wave 0 |
| P27-T04 | POST /api/recommendations/{id}/dispatch returns 404 for unknown recommendation | unit | `uv run pytest tests/unit/test_dispatch_endpoint.py::TestDispatchNotFound -x` | Wave 0 |

### Sampling Rate

- **Per task commit:** `uv run pytest tests/unit/test_malcolm_collector.py tests/unit/test_dispatch_endpoint.py -x`
- **Per wave merge:** `uv run pytest tests/unit/ -x`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/unit/test_malcolm_collector.py` — covers P27-T02 (all collector behaviors)
- [ ] `tests/unit/test_dispatch_endpoint.py` — covers P27-T04 (all dispatch endpoint cases)

**Test fixture strategy (mock httpx — Claude's discretion):**

```python
# Pattern from tests/unit/test_firewall_collector.py (direct inspection)
# Use unittest.mock.MagicMock/AsyncMock for loader and sqlite_store.
# Use unittest.mock.patch on httpx.Client.post (or asyncio.to_thread) to return fixture JSON.

from unittest.mock import AsyncMock, MagicMock, patch

@pytest.mark.asyncio
async def test_alert_normalization():
    mock_loader = MagicMock()
    mock_loader.ingest_events = AsyncMock()
    mock_sqlite = MagicMock()
    mock_sqlite.get_kv = MagicMock(return_value="2026-04-06T00:00:00Z")
    mock_sqlite.set_kv = MagicMock()

    fake_response = {
        "hits": {
            "hits": [{
                "_source": {
                    "@timestamp": "2026-04-07T10:00:00Z",
                    "event": {"dataset": "alert", "severity": 2},
                    "source": {"ip": "192.168.1.100", "port": 34995},
                    "destination": {"ip": "1.2.3.4", "port": 443},
                    "rule": {"name": "ET MALWARE Test Signature"},
                    "network": {"transport": "TCP"},
                }
            }]
        }
    }

    with patch("ingestion.jobs.malcolm_collector.httpx") as mock_httpx:
        mock_httpx.Client.return_value.__enter__.return_value.post.return_value.json.return_value = fake_response
        # ... test collector._poll_and_ingest()
```

*(If no gaps: "None — existing test infrastructure covers all phase requirements")*
*Note: P27-T01 (port mapping), P27-T05 (PowerShell corpus sync), and P27-T06 (e2e verification) are not unit-testable — they are infrastructure/script tasks verified by manual execution against the live Malcolm server.*

---

## Sources

### Primary (HIGH confidence)

- `ingestion/jobs/firewall_collector.py` — complete FirewallCollector implementation; authoritative template
- `backend/main.py` — complete lifespan code; FIREWALL_ENABLED block at lines 249-275 is the exact registration template
- `backend/core/config.py` — Settings class; FIREWALL_* block at lines 60-69 is the exact settings template
- `backend/stores/sqlite_store.py` lines 1481-1498 — set_kv/get_kv API; synchronous, call via asyncio.to_thread
- `backend/models/event.py` — NormalizedEvent schema; all 35 DuckDB columns documented
- `backend/models/recommendation.py` — RecommendationArtifact with model_validator running jsonschema
- `contracts/recommendation.schema.json` — JSON Schema Draft 2020-12; allOf constraints documented
- `backend/api/recommendations.py` — existing PATCH /approve endpoint; _row_to_dict and _run_approval_gate helpers
- `ingestion/parsers/suricata_eve_parser.py` — Suricata field mapping; reuse severity map and timestamp parser
- `ingestion/parsers/ipfire_syslog_parser.py` — IPFire syslog field mapping reference
- `ingestion/loader.py` — INSERT OR IGNORE deduplication; ingest_events() signature
- `tests/unit/test_firewall_collector.py` — test structure template for MalcolmCollector unit tests
- `pyproject.toml` — httpx==0.28.1 pinned; jsonschema available transitively; no new deps needed
- `.planning/phases/27-malcolm-nsm-integration-and-live-feed-collector/27-CONTEXT.md` — all locked decisions

### Secondary (MEDIUM confidence)

- OpenSearch REST API search endpoint (`/{index}/_search` POST with JSON body, `sort` + `search_after` pagination) — well-established Elasticsearch-compatible standard
- Windows OpenSSH client (`ssh.exe`, `scp.exe`) available by default on Windows 10/11 — verified pattern for PowerShell automation

### Tertiary (LOW confidence)

- Exact Malcolm 26.02.0 field paths in arkime_sessions3-* and malcolm_beats_syslog_* — assumes ECS-aligned naming based on Malcolm documentation; actual field names should be verified by querying one real document before implementation

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries confirmed in pyproject.toml; no new deps
- Architecture: HIGH — FirewallCollector pattern fully read; MalcolmCollector is a direct structural clone with different data source
- Dispatch endpoint: HIGH — RecommendationArtifact already validates; route pattern confirmed from existing recommendations.py
- Malcolm field mapping: MEDIUM/LOW — cascading field lookups recommended; verify against real document in Wave 0
- PowerShell scripts: MEDIUM — standard Windows OpenSSH patterns; Malcolm docker-compose path needs discovery

**Research date:** 2026-04-07
**Valid until:** 2026-05-07 (stable project; Malcolm version pinned at 26.02.0)
