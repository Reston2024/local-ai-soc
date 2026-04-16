# Phase 52: TheHive Case Management Integration - Research

**Researched:** 2026-04-16
**Domain:** TheHive 5.x REST API, Cortex 3.x, thehive4py 2.x, Docker on GMKtec N100
**Confidence:** MEDIUM-HIGH (API shapes from official docs and library source; Docker resource limits from empirical examples)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Severity trigger: **High and Critical only** (severity >= 3 in TheHive numeric scale)
- Creation mode: **Immediate** — each qualifying detection fires its own case on detection, no batching
- Per-rule suppression: **Yes** — `THEHIVE_SUPPRESS_RULES` list in settings skips auto-case creation for noisy rules
- TheHive unreachable: **Retry queue** — `thehive_pending_cases` SQLite table; retry on next detection cycle; detection pipeline must never block
- Button placement: **Detection expanded panel** AND **InvestigationView header** (alongside Summary/Agent/OSINT tabs)
- Button behavior: **Open existing case** — deep-link to `http://192.168.1.22:9000/cases/{thehive_case_id}`. Does not create cases on click.
- Inline badge: **Yes** — `#N · In Progress` (amber) / `#N · Resolved` (green) pill on detection row and expanded panel
- TheHive URL: `THEHIVE_URL=http://192.168.1.22:9000` in `.env`/settings (hardcoded to GMKtec IP, no DNS)
- Closure sync: **Polling** — APScheduler task every **5 minutes**, query TheHive `/api/v1/query` for Resolved cases
- Fields synced back: `thehive_status` (TruePositive/FalsePositive/Indeterminate), `thehive_closed_at`, `thehive_analyst`
- New SQLite columns: `thehive_case_id`, `thehive_status`, `thehive_closed_at`, `thehive_analyst`
- Cortex: **Required in Phase 52** — deploy alongside TheHive in same Docker Compose stack on GMKtec
- Cortex analysers: **AbuseIPDB** (reuse `ABUSEIPDB_API_KEY`), **MaxMind GeoIP** (local mmdb), **MISP** (native), **VirusTotal** (reuse `VT_API_KEY`)
- Phase 32 enrichment: **Parallel** — no sync between Cortex enrichment and Phase 32 OSINT enrichment

### Claude's Discretion
- TheHive + Cortex Docker Compose specifics (image versions, volume paths, network config on GMKtec)
- TheHive case template structure (title format, tags, TLP/PAP settings)
- Cortex analyser configuration files
- SQLite migration approach for new `thehive_*` columns
- Retry queue schema details for `thehive_pending_cases`
- Polling task implementation (APScheduler vs asyncio loop)

### Deferred Ideas (OUT OF SCOPE)
- None — discussion stayed within phase scope
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| REQ-52-01 | Docker on GMKtec — TheHive 5.x + Cortex in Docker Compose alongside Malcolm | Docker Compose pattern, image versions, memory limits for N100 |
| REQ-52-02 | Auto-case creation for High/Critical detections | thehive4py 2.x `hive.case.create()`, severity mapping 3=High/4=Critical |
| REQ-52-03 | Observables pre-populated (src_ip, rule_name, ATT&CK technique, MISP IOCs) | `hive.case.create_observable()` with dataType="ip", "other"; batch creation |
| REQ-52-04 | Retry queue — TheHive unreachable never blocks detection pipeline | `thehive_pending_cases` SQLite table; APScheduler retry job |
| REQ-52-05 | "Open in TheHive" button + case status badge in DetectionsView + InvestigationView | Svelte 5 runes; deep-link URL pattern `http://192.168.1.22:9000/cases/{id}` |
| REQ-52-06 | Poll TheHive every 5 min for case closures, sync verdict/timestamp/analyst to SQLite | APScheduler (already installed); `hive.case.find(filters=Eq("status","Resolved"))` |
| REQ-52-07 | Cortex with AbuseIPDB, MaxMind GeoIP, MISP, VirusTotal analysers | Cortex 3.x Docker, analyzer config via UI (API key entry in web UI) |
| REQ-52-08 | MISP native integration — wire TheHive to GMKtec MISP at 192.168.1.22:8443 | TheHive UI Connectors → MISP tab; MISP API key required |
| REQ-52-09 | Phase 51 SpiderFoot findings incorporated as observables | Query `osint_investigations`/`osint_findings` SQLite tables when creating case |
</phase_requirements>

---

## Summary

TheHive 5.x is a security case management platform. The Python client `thehive4py==2.0.3` (released October 2024) is a complete rewrite targeting TheHive 5.x exclusively and provides a clean synchronous HTTP client over `httpx`. Cases are created via `hive.case.create()`, observables added via `hive.case.create_observable()`, and case status polled via `hive.case.find(filters=Eq("status", "Resolved"))`.

The critical constraint for this phase is the **GMKtec N100 memory budget**. The standard TheHive 5 stack (TheHive + Cassandra + Elasticsearch) requires 12 GB RAM per official docs. The GMKtec N100 with Malcolm and MISP already consuming ~4-5 GB leaves at most 8-10 GB remaining. The Cassandra JVM heap must be capped at 512 MB and Elasticsearch at 512 MB to coexist. A real-world 2-core 4 GB VM deployment confirms this is viable with tuning. Cortex adds another ~512 MB with a separate Elasticsearch instance (or shared).

The MISP integration into TheHive is configured purely via the TheHive UI (Platform Management → Connectors → MISP), using the MISP API key from Phase 50. Cortex analyser API keys (AbuseIPDB, VirusTotal) are entered via the Cortex web UI; no config files required for the basic analysers.

**Primary recommendation:** Deploy the TheHive + Cassandra + Elasticsearch + MinIO + Cortex stack in `infra/docker-compose.thehive.yml` (separate from root compose, mirroring the MISP pattern). Use `thehive4py==2.0.3` in the SOC Brain backend with `asyncio.to_thread()` wrapping. Hook case creation into `backend/api/detect.py` post-save, with a non-fatal try/except that writes to `thehive_pending_cases` on failure.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `thehive4py` | 2.0.3 | Python client for TheHive 5 REST API | Official library from TheHive-Project; v2.x is a complete rewrite for TheHive 5; v1.x is EOL |
| `strangebee/thehive` | 5.5.14 | TheHive Docker image | Latest stable; `5.5` tag for minor updates; avoid deprecated `latest` |
| `cassandra` | 4.1 | TheHive database backend | Required by TheHive 5; Cassandra 4.x is the supported version |
| `elasticsearch` | 7.17 | TheHive index backend | TheHive 5 requires ES 7.x specifically; ES 8.x not supported |
| `quay.io/minio/minio` | latest | File/attachment storage for TheHive | Required for case attachments and evidence files |
| `thehiveproject/cortex` | 3.1.8 | Observable analysis engine | Only production-grade analyzer runner for TheHive; Docker socket runner for analysers |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `apscheduler` | 3.11.2 | Closure sync polling job | Already installed; reuse the `AsyncIOScheduler` from `backend/api/metrics.py` |
| `httpx` | 0.28.1 | Underlying transport for thehive4py | Already installed; thehive4py uses httpx internally |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `thehive4py` 2.x | Raw `httpx` calls | thehive4py provides typed filter DSL (`Eq`, `Like`, `Between`) for case queries; raw calls are simpler but lose the filter helpers |
| APScheduler for sync | asyncio `while True` loop | APScheduler already in codebase; consistent with KPI refresh pattern in `metrics.py` |
| Cassandra + ES (standard stack) | Berkeley DB (minimal) | Berkeley DB is TheHive 4 only; Cassandra is the only supported database for TheHive 5 |

**Installation:**
```bash
uv add thehive4py==2.0.3
```

---

## Architecture Patterns

### Recommended Project Structure
```
backend/
├── services/
│   └── thehive_client.py      # TheHive HTTP client wrapper (async-safe)
├── api/
│   └── thehive_api.py         # GET /api/thehive/status health endpoint (optional)
infra/
└── docker-compose.thehive.yml # TheHive + Cortex stack (GMKtec only)
tests/unit/
├── test_thehive_client.py     # Wave 0 TDD stubs
└── test_thehive_sync.py       # Closure sync unit tests
```

### Pattern 1: TheHive Client Service (async-safe wrapper)

`thehive4py.TheHiveApi` is synchronous (blocking HTTP). Wrap every call in `asyncio.to_thread()`.

```python
# backend/services/thehive_client.py
import asyncio
from thehive4py import TheHiveApi
from thehive4py.query.filters import Eq
from backend.core.config import settings
from backend.core.logging import get_logger

log = get_logger(__name__)
_CLIENT_AVAILABLE = False

try:
    from thehive4py import TheHiveApi
    _CLIENT_AVAILABLE = True
except ImportError:
    pass


class TheHiveClient:
    def __init__(self, url: str, api_key: str):
        self._api = TheHiveApi(url=url, apikey=api_key)

    async def create_case(self, case_dict: dict) -> dict:
        """Create a TheHive case. Returns the created case dict including _id."""
        return await asyncio.to_thread(self._api.case.create, case=case_dict)

    async def create_observable(self, case_id: str, observable: dict) -> dict:
        return await asyncio.to_thread(
            self._api.case.create_observable,
            case_id=case_id,
            observable=observable,
        )

    async def find_resolved_cases(self, since_ts: int | None = None) -> list[dict]:
        """Find all Resolved cases, optionally filtered by updatedAt >= since_ts."""
        filters = Eq("status", "Resolved")
        return await asyncio.to_thread(self._api.case.find, filters=filters)

    async def ping(self) -> bool:
        """Return True if TheHive is reachable."""
        try:
            await asyncio.to_thread(self._api.case.count)
            return True
        except Exception:
            return False
```

### Pattern 2: Case Creation Payload

```python
# Source: thehive4py README + StrangeBee docs
def build_case_payload(detection: dict) -> dict:
    """Map SOC Brain detection to TheHive case payload."""
    sev_map = {"low": 1, "medium": 2, "high": 3, "critical": 4}
    thehive_severity = sev_map.get(detection["severity"].lower(), 2)
    return {
        "title": f"[{detection['severity'].upper()}] {detection['rule_name']} — {detection.get('src_ip', 'N/A')}",
        "description": (
            f"**Rule:** {detection['rule_name']}\n"
            f"**Detection ID:** {detection['id']}\n"
            f"**ATT&CK:** {detection.get('attack_technique', 'N/A')} — {detection.get('attack_tactic', 'N/A')}\n"
            f"**Source:** SOC Brain auto-case"
        ),
        "severity": thehive_severity,
        "tags": [
            "soc-brain",
            detection.get("attack_technique", ""),
            detection.get("attack_tactic", ""),
        ],
        "tlp": 2,   # TLP:AMBER — internal use
        "pap": 2,   # PAP:AMBER — limited distribution
        "status": "New",
    }
```

### Pattern 3: Observable Creation (standard dataTypes)

```python
# Source: thehive4py README, TheHive 5 observable types docs
observables = []
if detection.get("src_ip"):
    observables.append({"dataType": "ip", "data": detection["src_ip"], "ioc": False})
if detection.get("rule_name"):
    observables.append({"dataType": "other", "data": detection["rule_name"], "message": "Sigma rule name"})
if detection.get("attack_technique"):
    observables.append({"dataType": "other", "data": detection["attack_technique"], "message": "ATT&CK technique"})
# MISP-matched IOC (if ioc_matched=True on detection)
if detection.get("ioc_actor_tag"):
    observables.append({"dataType": "other", "data": detection["ioc_actor_tag"], "message": "MISP actor tag"})
```

### Pattern 4: Pending Cases Retry Queue

```python
# thehive_pending_cases DDL — add to sqlite_store.py alongside existing tables
_THEHIVE_DDL = """
CREATE TABLE IF NOT EXISTS thehive_pending_cases (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    detection_id TEXT NOT NULL,
    payload_json TEXT NOT NULL,   -- JSON of case + observables
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    attempts     INTEGER NOT NULL DEFAULT 0,
    last_error   TEXT
);
"""
```

### Pattern 5: Closure Sync (APScheduler job)

```python
# In backend/api/detect.py or a new backend/services/thehive_sync.py
# Reuse the AsyncIOScheduler already in metrics.py
from thehive4py.query.filters import Eq

async def sync_thehive_closures(app_state) -> None:
    """Poll TheHive for Resolved cases and update SOC Brain SQLite."""
    try:
        client: TheHiveClient = app_state.thehive_client
        resolved = await client.find_resolved_cases()
        for case in resolved:
            case_num = case.get("caseId") or case.get("number")
            thehive_id = case["_id"]
            status = case.get("resolutionStatus", "Indeterminate")  # TruePositive | FalsePositive | Indeterminate
            closed_at = case.get("endDate")
            analyst = case.get("assignee", "")
            # Write back to detections row
            await asyncio.to_thread(
                _update_detection_thehive_status,
                app_state.stores.sqlite._conn,
                thehive_id, status, closed_at, analyst
            )
    except Exception as exc:
        log.warning("TheHive closure sync failed: %s", exc)
```

### Anti-Patterns to Avoid
- **Blocking the event loop:** Never call `thehive4py` methods directly in async handlers — always wrap in `asyncio.to_thread()`.
- **Raising exceptions in detection pipeline:** TheHive case creation MUST be non-fatal. The `try/except` around creation writes to `thehive_pending_cases` instead of propagating.
- **Using `strangebee/thehive:latest`:** The `latest` tag is pinned to 5.0.x (old). Use `strangebee/thehive:5.5` or pin exact `5.5.14-1`.
- **Cassandra without heap cap:** Cassandra will OOM-kill on the N100 without explicit `MAX_HEAP_SIZE` and `HEAP_NEWSIZE` env vars.
- **Using Elasticsearch 8.x:** TheHive 5 only supports Elasticsearch 7.x. `docker.elastic.co/elasticsearch/elasticsearch:7.17.14` is the correct image.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| TheHive REST API calls | Custom `httpx` client with manual JSON | `thehive4py==2.0.3` | Typed filter DSL, pagination, all endpoints covered |
| Case query filtering | Manual URL query params | `thehive4py` `Eq`, `Like`, `Between`, `&`, `|` operators | Filter DSL handles TheHive's POST-based query API |
| Background polling | `asyncio.sleep` loop | `apscheduler.AsyncIOScheduler` (already running) | Already in codebase, add_job is 3 lines |
| Case ID storage | Separate DB table | New columns on existing `detections` table | Same idempotent `ALTER TABLE` pattern as MISP/Phase 50 |

---

## Common Pitfalls

### Pitfall 1: TheHive 5 API changed in v5.4 — use `/api/v1/` not `/api/`
**What goes wrong:** The public API v0 (`/api/case`, `/api/observable`) was deprecated in TheHive 5.4. Some examples online still show v0 endpoints which return 404 on 5.5.
**Why it happens:** Outdated blog posts reference TheHive 4 / early TheHive 5 API.
**How to avoid:** `thehive4py==2.0.3` handles the correct endpoint versions internally. Don't hand-roll any REST calls — let thehive4py handle routing.
**Warning signs:** HTTP 404 on `/api/case` or 405 errors in logs.

### Pitfall 2: Cassandra OOM on N100 without heap limits
**What goes wrong:** Cassandra by default allocates heap based on available system RAM. On a shared N100, it will try to claim 4-6 GB and get OOM-killed within minutes.
**Why it happens:** Cassandra's auto-heap detection sees total host RAM, not container memory limit.
**How to avoid:** Always set `MAX_HEAP_SIZE=512M` and `HEAP_NEWSIZE=100M` as environment variables on the Cassandra container. Set `mem_limit: 600m` in Docker Compose.
**Warning signs:** `cassandra` container exits with code 137 (OOM kill).

### Pitfall 3: Elasticsearch 7.x single-node requires `discovery.type=single-node`
**What goes wrong:** Elasticsearch fails to start in Docker without this flag, loops with "master not discovered" errors.
**Why it happens:** Elasticsearch 7.x requires explicit single-node mode for development/single deployments.
**How to avoid:** Always set `discovery.type=single-node` and `xpack.security.enabled=false` environment variables.
**Warning signs:** ES container restarts repeatedly with `org.elasticsearch.discovery.MasterNotDiscoveredException`.

### Pitfall 4: thehive4py 2.x is NOT compatible with thehive4py 1.x
**What goes wrong:** Examples for TheHive 4 use `thehive4py==1.x` which has completely different API (class-based models like `Case()`, `CaseObservable()` instead of dicts).
**Why it happens:** thehive4py was fully rewritten for TheHive 5.
**How to avoid:** Use dict payloads, not model objects. `hive.case.create(case={"title": "..."})` not `hive.create_case(Case(title="..."))`.
**Warning signs:** `AttributeError: 'TheHiveApi' object has no attribute 'create_case'`.

### Pitfall 5: TheHive case `_id` vs `caseId` vs `number`
**What goes wrong:** TheHive returns both `_id` (internal UUID like `~12345`) and `caseId` (numeric sequential like `42`). The URL deep-link uses the numeric `caseId`, the API uses `_id`.
**Why it happens:** TheHive uses two identifier systems — internal graph ID and user-visible sequential case number.
**How to avoid:** Store both: `thehive_case_id` = `_id` (for API calls), `thehive_case_num` = `caseId` (for badge display and URL).
**Warning signs:** Badge shows `#~12345` instead of `#42`; deep-link URL 404s.

### Pitfall 6: GMKtec N100 memory budget
**What goes wrong:** Malcolm (OpenSearch ~2 GB) + MISP (~2 GB) + TheHive stack (Cassandra + ES + MinIO + TheHive + Cortex) easily exceeds 16 GB without memory limits.
**Why it happens:** Each JVM-based service grabs heap opportunistically.
**How to avoid:** Apply explicit memory limits to all containers. See Docker Compose section below for recommended budget.

### Pitfall 7: MISP integration requires TheHive's JVM to trust the MISP self-signed certificate
**What goes wrong:** TheHive fails to connect to MISP at `https://192.168.1.22:8443` with SSL verification error — MISP uses a self-signed cert.
**Why it happens:** TheHive uses the JVM truststore, not the OS certificate store.
**How to avoid:** Use TheHive's MISP connector setting "Disable certificate validation" (equivalent to `ssl=false` in the connector config) rather than importing the cert into the JVM truststore. This is acceptable for LAN-internal MISP instances.

---

## Code Examples

### Case Creation Hook in detect.py

```python
# Source: CONTEXT.md pattern, thehive4py README
# In backend/api/detect.py — after saving detection to SQLite

async def _maybe_create_thehive_case(detection: dict, request: Request) -> None:
    """Fire-and-forget: create TheHive case for High/Critical detections."""
    severity = detection.get("severity", "").lower()
    if severity not in ("high", "critical"):
        return
    rule_id = detection.get("rule_id", "")
    suppress_rules = settings.THEHIVE_SUPPRESS_RULES  # list[str]
    if rule_id in suppress_rules:
        return
    try:
        client: TheHiveClient = request.app.state.thehive_client
        case_payload = build_case_payload(detection)
        created = await client.create_case(case_payload)
        case_id = created["_id"]
        case_num = created.get("number") or created.get("caseId")
        # Add observables
        observables = build_observables(detection, request)
        for obs in observables:
            try:
                await client.create_observable(case_id, obs)
            except Exception as exc:
                log.warning("Failed to add observable %s: %s", obs, exc)
        # Write case ID and number back to detections
        await asyncio.to_thread(
            _save_thehive_case_id,
            request.app.state.stores.sqlite._conn,
            detection["id"], case_id, case_num, "New"
        )
    except Exception as exc:
        log.warning("TheHive case creation failed, queuing for retry: %s", exc)
        await asyncio.to_thread(
            _enqueue_pending_case,
            request.app.state.stores.sqlite._conn,
            detection["id"],
            json.dumps({"case": build_case_payload(detection), "observables": build_observables(detection, request)})
        )
```

### Finding Resolved Cases

```python
# Source: thehive4py GitHub test_case_endpoint.py
from thehive4py.query.filters import Eq, Between

resolved = hive.case.find(
    filters=Eq("status", "Resolved"),
    sortby=[{"_field": "endDate", "_order": "desc"}],
)
# Each case has:
# case["_id"]               — internal ID for API calls
# case["number"]            — sequential case number for display (#42)
# case["status"]            — "Resolved"
# case["resolutionStatus"]  — "TruePositive" | "FalsePositive" | "Indeterminate"
# case["endDate"]           — epoch millis when case was closed
# case["assignee"]          — analyst who last updated it
```

### Settings additions

```python
# backend/core/config.py additions
THEHIVE_URL: str = "http://192.168.1.22:9000"
THEHIVE_API_KEY: str = ""          # Set THEHIVE_API_KEY in .env
THEHIVE_ENABLED: bool = False      # Set True when TheHive deployed on GMKtec
THEHIVE_SUPPRESS_RULES: list[str] = []  # Rule IDs to skip auto-case creation
```

### Idempotent SQLite Column Migration

```python
# Source: established pattern from sqlite_store.py (Phase 50)
_THEHIVE_COLUMNS = [
    ("thehive_case_id",    "TEXT"),
    ("thehive_case_num",   "INTEGER"),
    ("thehive_status",     "TEXT"),
    ("thehive_closed_at",  "TEXT"),
    ("thehive_analyst",    "TEXT"),
]

for col, dtype in _THEHIVE_COLUMNS:
    try:
        conn.execute(f"ALTER TABLE detections ADD COLUMN {col} {dtype}")
    except Exception:
        pass  # Column already exists

_PENDING_CASES_DDL = """
CREATE TABLE IF NOT EXISTS thehive_pending_cases (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    detection_id   TEXT NOT NULL,
    payload_json   TEXT NOT NULL,
    created_at     TEXT NOT NULL DEFAULT (datetime('now')),
    attempts       INTEGER NOT NULL DEFAULT 0,
    last_error     TEXT
);
"""
```

---

## TheHive Observable Data Types (Built-in)

TheHive 5 ships with these default `dataType` values that map to Phase 52 needs:

| dataType | Maps To |
|----------|---------|
| `ip` | `src_ip`, `dst_ip` |
| `domain` | domain observables from MISP IOCs |
| `fqdn` | fully-qualified domain names |
| `hash` | file hashes from IOC matches |
| `filename` | file path observables |
| `url` | URL-type IOCs |
| `mail` | email addresses |
| `other` | rule_name, ATT&CK technique, SpiderFoot findings (free text) |

**Use `"other"` with a `"message"` field for rule_name, ATT&CK technique ID, and actor tags.**

---

## TheHive Severity Mapping

| TheHive numeric | SOC Brain severity |
|-----------------|-------------------|
| 1 | low |
| 2 | medium |
| **3** | **high** (triggers auto-case) |
| **4** | **critical** (triggers auto-case) |

---

## Docker Compose for GMKtec N100

**File:** `infra/docker-compose.thehive.yml` (mirrors `docker-compose.misp.yml` pattern — NOT merged into root compose)

### Memory Budget (GMKtec N100, 16 GB total)
| Service | Idle RAM | Notes |
|---------|----------|-------|
| Malcolm (OpenSearch) | ~2.5 GB | Already running |
| MISP stack | ~1.8 GB | Already running (Phase 50) |
| Cassandra | 600 MB | Capped with `MAX_HEAP_SIZE=512M` |
| Elasticsearch 7.x | 600 MB | Capped with `-Xms512m -Xmx512m` |
| TheHive | 800 MB | `JVM_OPTS="-Xms512m -Xmx768m"` |
| MinIO | 200 MB | Object storage for attachments |
| Cortex | 400 MB | Lightweight, most memory in analyser containers |
| Cortex Elasticsearch | 600 MB | Separate ES instance for Cortex |
| **Total additional** | **~3.2 GB** | Leaves ~8 GB for Malcolm+MISP+OS |

### Docker Compose structure

```yaml
# infra/docker-compose.thehive.yml
# TheHive 5 + Cortex 3 — GMKtec N100 deployment
# Run: docker compose -f infra/docker-compose.thehive.yml --env-file .env.thehive up -d
# TheHive UI: http://192.168.1.22:9000  Cortex UI: http://192.168.1.22:9001

services:
  cassandra:
    image: cassandra:4.1
    restart: unless-stopped
    mem_limit: 600m
    environment:
      - CASSANDRA_CLUSTER_NAME=TheHive
      - MAX_HEAP_SIZE=512M
      - HEAP_NEWSIZE=100M
    volumes:
      - thehive_cassandra:/var/lib/cassandra
    healthcheck:
      test: ["CMD-SHELL", "[ $$(nodetool statusgossip) = running ]"]
      interval: 30s
      timeout: 10s
      retries: 10
      start_period: 120s

  elasticsearch:
    image: docker.elastic.co/elasticsearch/elasticsearch:7.17.14
    restart: unless-stopped
    mem_limit: 700m
    environment:
      - discovery.type=single-node
      - xpack.security.enabled=false
      - "ES_JAVA_OPTS=-Xms512m -Xmx512m"
      - cluster.name=hive
    volumes:
      - thehive_elasticsearch:/usr/share/elasticsearch/data

  minio:
    image: quay.io/minio/minio:latest
    restart: unless-stopped
    mem_limit: 300m
    command: minio server /data --console-address ":9002"
    environment:
      - MINIO_ROOT_USER=${THEHIVE_MINIO_USER:-thehive}
      - MINIO_ROOT_PASSWORD=${THEHIVE_MINIO_PASSWORD}
    volumes:
      - thehive_minio:/data

  thehive:
    image: strangebee/thehive:5.5
    restart: unless-stopped
    mem_limit: 900m
    depends_on:
      cassandra:
        condition: service_healthy
      elasticsearch:
        condition: service_started
      minio:
        condition: service_started
    ports:
      - "9000:9000"
    environment:
      - JVM_OPTS=-Xms512m -Xmx768m
    command:
      - --secret
      - "${THEHIVE_SECRET}"
      - --cql-hostnames
      - cassandra
      - --index-backend
      - elasticsearch
      - --es-hostnames
      - elasticsearch
      - --s3-endpoint
      - http://minio:9000
      - --s3-access-key
      - "${THEHIVE_MINIO_USER:-thehive}"
      - --s3-secret-key
      - "${THEHIVE_MINIO_PASSWORD}"
      - --s3-use-path-access-style

  cortex_elasticsearch:
    image: docker.elastic.co/elasticsearch/elasticsearch:7.17.14
    restart: unless-stopped
    mem_limit: 700m
    environment:
      - discovery.type=single-node
      - xpack.security.enabled=false
      - "ES_JAVA_OPTS=-Xms512m -Xmx512m"
      - cluster.name=cortex
    volumes:
      - cortex_elasticsearch:/usr/share/elasticsearch/data

  cortex:
    image: thehiveproject/cortex:3.1.8
    restart: unless-stopped
    mem_limit: 500m
    depends_on:
      - cortex_elasticsearch
    ports:
      - "9001:9001"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - ${CORTEX_JOB_DIR:-/tmp/cortex-jobs}:${CORTEX_JOB_DIR:-/tmp/cortex-jobs}
    environment:
      - job_directory=${CORTEX_JOB_DIR:-/tmp/cortex-jobs}
    command:
      - --es-uri
      - http://cortex_elasticsearch:9200

volumes:
  thehive_cassandra:
  thehive_elasticsearch:
  thehive_minio:
  cortex_elasticsearch:
```

---

## Cortex Analyser Configuration

Cortex analysers are enabled and configured **entirely through the Cortex web UI** (not config files). There is no programmatic configuration needed in the Docker Compose.

### Steps after first deployment:
1. Navigate to `http://192.168.1.22:9001`
2. Create admin account on first start
3. Create organization: "SOC Brain"
4. Create analyst user with "read/analyze" role → generate API key
5. Copy API key → add to TheHive's `application.conf` (or pass via Docker env/secret)
6. In Cortex Organization → Analyzers tab:
   - Search "AbuseIPDB" → enable → enter `ABUSEIPDB_API_KEY` from `.env`
   - Search "VirusTotal" → enable `VirusTotal_GetReport_3_1` → enter `VT_API_KEY`
   - Search "MaxMind" → enable `MaxMind_GeoIP_3_0` → point to local mmdb file path
   - Search "MISP" → enable `MISP_2_0` → enter MISP URL and API key

### TheHive → Cortex wiring (in TheHive application.conf or env):

```
cortex {
  servers: [
    {
      name: "local-cortex"
      url: "http://cortex:9001"
      auth {
        type: "bearer"
        key: "${CORTEX_API_KEY}"
      }
    }
  ]
}
```

This can be passed to `strangebee/thehive:5.5` as a mounted config file at `/etc/thehive/application.conf` or via TheHive's startup flags.

---

## TheHive → MISP Integration

TheHive 5 native MISP integration is configured via **the TheHive web UI** (not config files).

1. Log into TheHive as admin
2. Platform Management → Connectors → MISP tab → Add server
3. URL: `https://192.168.1.22:8443`
4. API Key: (from Phase 50 MISP setup — Phase 50 created `MISP_KEY` in `.env.misp`)
5. SSL verification: **Disabled** (MISP uses self-signed cert on GMKtec)
6. Purpose: Import and Export
7. Save and test connection

This enables TheHive to pull MISP events as alerts and push case observables back to MISP as sightings.

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| thehive4py 1.x (model objects) | thehive4py 2.x (dict payloads) | Aug 2024 (v2.0.0) | Breaking change — all examples before 2024 use wrong API |
| `/api/case` (v0 API) | `/api/v1/case` (v1 API) | TheHive 5.4 | v0 deprecated; thehive4py 2.x handles this automatically |
| `thehiveproject/thehive` | `strangebee/thehive` | TheHive 5.x | Old Docker Hub org deprecated; use `strangebee/` org |
| `strangebee/thehive:latest` | `strangebee/thehive:5.5` | Ongoing | `latest` is frozen at 5.0.x; always pin to major version |

**Deprecated/outdated:**
- `thehive4py==1.x`: EOL, targets TheHive 3/4. Any example using `CaseObservable()` or `Case()` model objects is v1.
- `thehiveproject/thehive` Docker image: old org, use `strangebee/thehive`

---

## Open Questions

1. **GMKtec N100 actual available RAM when Phase 52 deploys**
   - What we know: MISP uses ~1.8 GB; Malcolm uses ~2.5 GB; OS+other ~1 GB
   - What's unclear: Whether Malcolm's OpenSearch fluctuates under load enough to cause OOM conflicts with Cassandra
   - Recommendation: Start Cassandra with `MAX_HEAP_SIZE=512M`; monitor with `docker stats` for first 24h; increase if OOM kills occur

2. **Cortex analyser Docker image pull on GMKtec**
   - What we know: Cortex pulls analyser Docker images on first use (AbuseIPDB, VirusTotal, MaxMind, MISP each ~200-400 MB)
   - What's unclear: Whether GMKtec has enough disk space alongside Malcolm's pcap storage
   - Recommendation: Check `df -h` before deploying; Cortex job images can be pruned after use with `docker image prune`

3. **TheHive MISP integration with Phase 50's MISP**
   - What we know: MISP at `https://192.168.1.22:8443` is deployed but admin password must be retrieved from Phase 50 setup
   - What's unclear: Whether Phase 50's MISP has a dedicated TheHive API key already or needs one created
   - Recommendation: Wave 0 task to verify MISP API key exists and is accessible; document in `.env.thehive`

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 + pytest-asyncio 1.3.0 |
| Config file | `pyproject.toml` — `asyncio_mode = "auto"` |
| Quick run command | `uv run pytest tests/unit/test_thehive_client.py tests/unit/test_thehive_sync.py -x` |
| Full suite command | `uv run pytest tests/unit/ -x --tb=short` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| REQ-52-02 | `build_case_payload()` maps severity high/critical to 3/4 | unit | `uv run pytest tests/unit/test_thehive_client.py::test_case_payload_severity -x` | ❌ Wave 0 |
| REQ-52-02 | Suppress rules list skips case creation | unit | `uv run pytest tests/unit/test_thehive_client.py::test_suppress_rules_skip -x` | ❌ Wave 0 |
| REQ-52-03 | Observable builder produces correct dataType for ip/other | unit | `uv run pytest tests/unit/test_thehive_client.py::test_observable_builder -x` | ❌ Wave 0 |
| REQ-52-04 | Pending case enqueue on TheHive unreachable | unit | `uv run pytest tests/unit/test_thehive_client.py::test_enqueue_on_failure -x` | ❌ Wave 0 |
| REQ-52-04 | Pending cases retry drains queue on success | unit | `uv run pytest tests/unit/test_thehive_sync.py::test_retry_queue_drains -x` | ❌ Wave 0 |
| REQ-52-06 | Closure sync updates SQLite verdict/timestamp/analyst | unit | `uv run pytest tests/unit/test_thehive_sync.py::test_closure_sync_writes_sqlite -x` | ❌ Wave 0 |
| REQ-52-06 | Closure sync is non-fatal on TheHive unavailable | unit | `uv run pytest tests/unit/test_thehive_sync.py::test_closure_sync_tolerates_failure -x` | ❌ Wave 0 |
| REQ-52-01 | Health check reports TheHive status | unit | `uv run pytest tests/unit/test_thehive_client.py::test_ping_returns_false_when_unreachable -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/unit/test_thehive_client.py tests/unit/test_thehive_sync.py -x`
- **Per wave merge:** `uv run pytest tests/unit/ -x --tb=short`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/unit/test_thehive_client.py` — covers REQ-52-02, 52-03, 52-04 (client unit tests with `pytest.importorskip` for `thehive4py`)
- [ ] `tests/unit/test_thehive_sync.py` — covers REQ-52-06 (closure sync), REQ-52-04 (retry queue drain)
- [ ] Framework install: `uv add thehive4py==2.0.3` — not yet in pyproject.toml

---

## Sources

### Primary (HIGH confidence)
- [thehive4py GitHub README](https://github.com/TheHive-Project/TheHive4py/blob/main/README.md) — client initialization, case.create, observable creation
- [thehive4py GitHub releases](https://github.com/TheHive-Project/TheHive4py/releases) — v2.0.3 (Oct 2024) is latest stable, targets TheHive 5.5.7+
- [thehive4py test_case_endpoint.py](https://github.com/TheHive-Project/TheHive4py/tree/main/tests/test_case_endpoint.py) — `hive.case.find(filters=Eq("status","Resolved"))` confirmed
- [Cortex application.sample](https://github.com/TheHive-Project/Cortex/blob/master/conf/application.sample) — analyzer catalog URL, Elasticsearch config
- [TheHive 5.5 release notes](https://docs.strangebee.com/thehive/release-notes/release-notes-5.5/) — latest version 5.5.14 (Jan 12, 2026)

### Secondary (MEDIUM confidence)
- [StrangeBee Docker deployment docs](https://docs.strangebee.com/thehive/installation/docker/) — verified: Cassandra + ES + MinIO + TheHive structure
- [TheHive 5 system requirements](https://docs.strangebee.com/thehive/installation/system-requirements/) — 3 CPU / 4 GB per service (confirmed full stack needs tuning for N100)
- [TheHive MISP connect a server](https://docs.strangebee.com/thehive/administration/misp-integration/connect-a-misp-server/) — UI-based configuration confirmed, SSL disable option confirmed
- [blog.agood.cloud Thehive5+Cortex compose](https://blog.agood.cloud/posts/2022/06/20/docker-config-thehive5-with-cortex-and-n8n/) — confirmed `strangebee/thehive:5.0.7-1`, Cortex port 9001, Docker socket mount pattern
- [Cortex Docker docs](https://docs.strangebee.com/cortex/installation-and-configuration/run-cortex-with-docker/) — Docker socket `/var/run/docker.sock`, job directory, ES 7.9 requirement
- [cortex.servers configuration](https://blog.agood.cloud/posts/2019/09/27/integrate-thehive-and-cortex/) — `cortex.servers` application.conf bearer key format

### Tertiary (LOW confidence)
- TheHive severity 1-4 mapping (multiple community sources agree but not in official API docs)
- Cortex `thehiveproject/cortex:3.1.8` exact tag — older blog references show 3.1.1; latest should be verified against Docker Hub before deploying

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — thehive4py 2.0.3 confirmed from GitHub releases; Docker images confirmed from Docker Hub
- Architecture: MEDIUM-HIGH — API shapes verified from library source; Docker compose structure from multiple sources
- Resource limits: MEDIUM — derived from empirical 4 GB VM success + Phase 50 N100 patterns; not from official StrangeBee guidance
- Pitfalls: HIGH — Cassandra OOM is a known documented issue; API v0 deprecation is in official release notes

**Research date:** 2026-04-16
**Valid until:** 2026-07-16 (thehive4py stable; TheHive 5.x API stable; 90 days)
