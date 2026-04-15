# Phase 50: MISP Threat Intelligence Integration - Research

**Researched:** 2026-04-14
**Domain:** MISP Docker deployment, PyMISP REST API, IOC schema mapping, scheduled sync
**Confidence:** HIGH (Docker/API patterns), MEDIUM (resource estimates on N100+Malcolm coexistence)

---

## Summary

Phase 50 adds MISP as the structured threat intelligence backbone, completing work deferred from Phase 33. The existing Phase 33 foundation is solid: `ioc_store` SQLite table (value, type, confidence, feed_source, extra_json columns), `IocStore` CRUD class, `_BaseWorker` background task pattern, and `retroactive_ioc_scan` in `ingestion/loader.py`. Phase 50 is an additive extension — a new `MispWorker` following the same `_BaseWorker` pattern, a new `MispSyncService` using PyMISP, and ThreatIntelView API extensions for MISP-sourced context.

MISP's official Docker image (`ghcr.io/misp/misp-docker/misp-core:latest`) requires MariaDB + Redis/Valkey as companion services. On the GMKtec N100 (16 GB RAM) running Malcolm, MISP's idle footprint of ~2–3 GB total across all containers is feasible with memory limits applied to Redis (256 MB cap) and MariaDB buffer pool tuning. The critical risk is N100 CPU saturation when MISP runs correlation jobs alongside Malcolm's OpenSearch indexing — schedule MISP feed fetches during off-peak windows.

PyMISP (`pip install pymisp`) wraps MISP's REST API cleanly. Authentication uses a 40-character hex API key passed as the `Authorization` header. The primary sync path is: `misp.search(controller='attributes', type_attribute=['ip-dst','ip-src','domain','url','md5','sha256'], to_ids=True, pythonify=True)` → normalize each `MISPAttribute` to the existing `ioc_store` schema → `IocStore.upsert_ioc()`. MISP feeds (CIRCL OSINT, abuse.ch MalwareBazaar, etc.) are enabled/cached via `misp.enable_feed(feed_id)` + `misp.cache_feeds()`.

**Primary recommendation:** Deploy MISP on GMKtec via `docker-compose.yml` with capped memory limits; implement `MispWorker` extending `_BaseWorker`; sync IOC attributes nightly via PyMISP `search()`; surface MISP source distinctly in `ioc_source` field; add `/api/intel/misp-events` endpoint for event context in ThreatIntelView.

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| DOCKER-01 | MISP Docker on GMKtec (Malcolm already running there) | Official `ghcr.io/misp/misp-docker/misp-core:latest` image + MariaDB + Redis; memory limits keep total under 3 GB idle |
| PHASE33-01 | Extend Phase 33 IOC pipeline | `MispWorker` follows existing `_BaseWorker` pattern; `upsert_ioc()` called with `feed_source='misp'` |
| VIEW-01 | Surface MISP intel in ThreatIntelView with confidence + event context | New `/api/intel/misp-events` endpoint; `extra_json` column stores MISP event_id + tags + TLP for drilldown |
</phase_requirements>

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `pymisp` | `>=2.4.198` (latest stable) | Python wrapper for MISP REST API | Official MISP project library; handles auth, serialization, pythonify |
| `ghcr.io/misp/misp-docker/misp-core` | `latest` | MISP application container | Official production image; GHCR, no build required |
| `mariadb` | `10.11` | MISP database | Required MISP dependency; 10.11 is the tested LTS version |
| `valkey/valkey` | `7.2` | MISP cache/job queue | Redis-compatible; used by official misp-docker compose |
| `apscheduler` | `3.11.2` (already in pyproject.toml) | Scheduled MISP sync job | Already installed; AsyncIOScheduler pattern already used in `backend/main.py` |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `httpx` | `0.28.1` (already in pyproject.toml) | Direct REST fallback | If PyMISP is blocked by Python version constraints; PyMISP uses `requests` internally |
| `requests` | transitive via pymisp | PyMISP internal HTTP | No direct use; PyMISP handles this |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `pymisp` | Raw `httpx` calls | PyMISP handles auth, pagination, pythonify objects — raw httpx means reimplementing all that; only use httpx if pymisp install fails |
| `ghcr.io/misp/misp-docker` | `ghcr.io/nukib/misp` (NUKIB image) | NUKIB is single-container (no separate MariaDB/Redis), simpler but less maintained; prefer official |
| `mariadb:10.11` | `mysql:8.0` | Either works; misp-docker uses MariaDB, stay consistent |
| APScheduler cron | `asyncio.sleep` loop like existing workers | APScheduler already used in main.py for midnight KPI job; MISP sync is a daily/hourly job, fits APScheduler cron trigger better than hot loop |

**Installation (new dependency only):**
```bash
uv add pymisp
```

---

## Architecture Patterns

### Recommended Project Structure (additions only)

```
backend/
└── services/
    └── intel/
        ├── ioc_store.py          # EXISTING — no changes needed
        ├── feed_sync.py          # EXISTING — add MispWorker class
        └── misp_sync.py          # NEW — MispSyncService (PyMISP wrapper)
backend/api/
    └── intel.py                  # EXISTING — add /misp-events + /misp-feeds endpoints
infra/
    └── misp/
        ├── docker-compose.misp.yml   # NEW — MISP stack (separate from main compose)
        ├── .env.misp.template        # NEW — MISP secrets template
        └── customize_misp.sh         # NEW — post-start MISP config (enable feeds)
```

### Pattern 1: MispWorker extending _BaseWorker

**What:** New `MispWorker` class in `feed_sync.py` follows identical `_BaseWorker` pattern already used by `FeodoWorker`, `CisaKevWorker`, and `ThreatFoxWorker`.
**When to use:** Recurring background sync (hourly or 6-hourly) pulling new/updated attributes from MISP.
**Example:**
```python
# Source: Pattern derived from existing backend/services/intel/feed_sync.py
class MispWorker(_BaseWorker):
    """Syncs IOC attributes from self-hosted MISP instance."""

    _kv_key = "intel.misp.last_sync"
    _feed_name = "misp"

    def __init__(self, ioc_store, sqlite_store_conn, interval_sec=21600,
                 duckdb_store=None, misp_url="", misp_key=""):
        super().__init__(ioc_store, sqlite_store_conn, interval_sec, duckdb_store)
        self._misp_url = misp_url
        self._misp_key = misp_key

    async def _sync(self) -> bool:
        from backend.services.intel.misp_sync import MispSyncService
        svc = MispSyncService(self._misp_url, self._misp_key)
        try:
            attributes = await asyncio.to_thread(svc.fetch_ioc_attributes)
        except Exception as exc:
            log.warning("MISP sync failed: %s", exc)
            return False
        for attr in attributes:
            is_new = self._ioc_store.upsert_ioc(
                value=attr["value"],
                ioc_type=attr["ioc_type"],
                confidence=attr["confidence"],
                first_seen=attr["first_seen"],
                last_seen=attr["last_seen"],
                malware_family=attr["malware_family"],
                actor_tag=attr["actor_tag"],
                feed_source="misp",
                extra_json=attr["extra_json"],
            )
            if is_new:
                await self._trigger_retroactive_scan(
                    ioc_value=attr["value"],
                    ioc_type=attr["ioc_type"],
                    bare_ip=None,
                    confidence=attr["confidence"],
                )
        _kv_set(self._conn, self._kv_key, _now_iso())
        return True
```

### Pattern 2: MispSyncService (synchronous, called via asyncio.to_thread)

**What:** Thin synchronous wrapper around PyMISP. Called via `asyncio.to_thread()` per CLAUDE.md convention because PyMISP uses the blocking `requests` library.
**When to use:** All PyMISP calls — PyMISP is synchronous, never call directly from async context.

```python
# Source: PyMISP GitHub + CIRCL automation docs
# File: backend/services/intel/misp_sync.py

from pymisp import PyMISP, MISPAttribute
from datetime import datetime, timezone

# MISP attribute type → ioc_store ioc_type mapping
MISP_TYPE_MAP = {
    "ip-src":  "ip",
    "ip-dst":  "ip",
    "domain":  "domain",
    "hostname": "domain",
    "url":     "url",
    "md5":     "md5",
    "sha1":    "sha1",
    "sha256":  "sha256",
    "email-src": "email",
    "filename": "filename",
}

# Confidence mapping: MISP threat_level_id (1=High, 2=Med, 3=Low, 4=Undef)
THREAT_LEVEL_CONFIDENCE = {1: 90, 2: 70, 3: 50, 4: 30}

class MispSyncService:
    def __init__(self, url: str, key: str, ssl: bool = False):
        # ssl=False for self-signed certs on LAN MISP instance
        self._misp = PyMISP(url, key, ssl)

    def fetch_ioc_attributes(
        self,
        to_ids: bool = True,
        limit: int = 5000,
        last: str = "1d",   # fetch attributes updated in last 1 day
    ) -> list[dict]:
        """
        Pull IDS-flagged attributes from MISP, normalize to ioc_store schema.
        Call via asyncio.to_thread() — PyMISP uses blocking requests library.
        """
        results = self._misp.search(
            controller="attributes",
            type_attribute=list(MISP_TYPE_MAP.keys()),
            to_ids=to_ids,
            last=last,
            limit=limit,
            pythonify=True,
        )
        normalized = []
        for attr in results:
            if not isinstance(attr, MISPAttribute):
                continue
            ioc_type = MISP_TYPE_MAP.get(attr.type)
            if not ioc_type:
                continue
            # Confidence from event threat_level_id or fallback to 50
            confidence = 50
            if hasattr(attr, "Event") and attr.Event:
                tl = getattr(attr.Event, "threat_level_id", 4)
                confidence = THREAT_LEVEL_CONFIDENCE.get(int(tl), 50)
            # Store MISP event context in extra_json for ThreatIntelView drilldown
            extra = {
                "misp_event_id": getattr(attr, "event_id", None),
                "misp_attr_uuid": str(attr.uuid),
                "misp_category": attr.category,
                "misp_tags": [t.name for t in getattr(attr, "Tag", [])],
                "misp_comment": attr.comment or "",
            }
            normalized.append({
                "value": attr.value,
                "ioc_type": ioc_type,
                "confidence": confidence,
                "first_seen": attr.first_seen.isoformat() if attr.first_seen else None,
                "last_seen": attr.last_seen.isoformat() if attr.last_seen else None,
                "malware_family": None,  # set from event info if available
                "actor_tag": None,
                "extra_json": json.dumps(extra),
            })
        return normalized
```

### Pattern 3: MISP Docker Compose (separate file, not merged into root compose)

**What:** Deploy MISP as a separate `docker-compose.misp.yml` on the GMKtec. The FastAPI backend (running on the Windows host) calls MISP via HTTP to `http://192.168.1.22:8080` (or whatever port is exposed).
**When to use:** Keeps MISP infrastructure isolated from the Caddy-only root `docker-compose.yml`. Malcolm and MISP run independently on the GMKtec.

```yaml
# Source: Official misp-docker + oneuptime deployment guide
# File: infra/misp/docker-compose.misp.yml
services:
  misp-db:
    image: mariadb:10.11
    restart: unless-stopped
    environment:
      MYSQL_ROOT_PASSWORD: "${MISP_DB_ROOT_PASSWORD}"
      MYSQL_DATABASE: misp
      MYSQL_USER: misp
      MYSQL_PASSWORD: "${MISP_DB_PASSWORD}"
    volumes:
      - misp_db_data:/var/lib/mysql
    command: >
      --innodb_buffer_pool_size=256M
      --innodb_io_capacity=200
      --innodb_flush_log_at_trx_commit=2
    healthcheck:
      test: ["CMD", "mysqladmin", "status", "-u", "root", "-p${MISP_DB_ROOT_PASSWORD}"]
      interval: 15s
      retries: 5

  misp-redis:
    image: valkey/valkey:7.2
    restart: unless-stopped
    command: valkey-server --maxmemory 256mb --maxmemory-policy allkeys-lru
    volumes:
      - misp_cache_data:/data

  misp-core:
    image: ghcr.io/misp/misp-docker/misp-core:latest
    restart: unless-stopped
    ports:
      - "8080:80"   # HTTP only for LAN access; no public exposure
    depends_on:
      misp-db:
        condition: service_healthy
      misp-redis:
        condition: service_started
    environment:
      BASE_URL: "http://192.168.1.22:8080"
      MYSQL_HOST: misp-db
      MYSQL_USER: misp
      MYSQL_PASSWORD: "${MISP_DB_PASSWORD}"
      MYSQL_DATABASE: misp
      REDIS_HOST: misp-redis
      ADMIN_EMAIL: "${MISP_ADMIN_EMAIL}"
      ADMIN_PASSWORD: "${MISP_ADMIN_PASSWORD}"
      ENCRYPTION_KEY: "${MISP_ENCRYPTION_KEY}"
      # Disable email (no mail server needed for single-user)
      NUM_WORKERS_DEFAULT: 2
      NUM_WORKERS_PRIO: 2
      NUM_WORKERS_CACHE: 2
      NUM_WORKERS_EMAIL: 0
      NUM_WORKERS_UPDATE: 1
    volumes:
      - misp_files:/var/www/MISP/app/files
      - misp_config:/var/www/MISP/app/Config
      - ./customize_misp.sh:/var/www/MISP/app/files/customize_misp.sh:ro
    healthcheck:
      test: ["CMD", "curl", "-sf", "http://localhost/users/heartbeat"]
      interval: 30s
      timeout: 10s
      retries: 5
      start_period: 120s  # MISP takes 60-90s to initialize on N100

volumes:
  misp_db_data:
  misp_cache_data:
  misp_files:
  misp_config:
```

### Pattern 4: Settings extension for MISP connection

**What:** Add MISP config to `backend/core/config.py` following existing pattern.
```python
# Add to Settings class in backend/core/config.py
MISP_ENABLED: bool = False          # OFF until MISP is deployed
MISP_URL: str = "http://192.168.1.22:8080"
MISP_KEY: str = ""                  # Set MISP_KEY in .env — 40-char hex
MISP_SSL_VERIFY: bool = False       # LAN self-signed cert
MISP_SYNC_INTERVAL_SEC: int = 21600 # 6 hours
MISP_SYNC_LAST_HOURS: int = 24      # Pull attrs updated in last N hours
```

### Pattern 5: ThreatIntelView API extension

**What:** Extend `backend/api/intel.py` with two new endpoints.
```python
@router.get("/misp-events", dependencies=[Depends(verify_token)])
async def get_misp_events(request: Request, limit: int = 50):
    """Return MISP event context for IOCs with feed_source='misp'."""
    # Query ioc_store WHERE feed_source='misp' ORDER BY confidence DESC LIMIT ?
    # Parse extra_json for misp_event_id, tags, category, comment
    ...

@router.get("/feeds/misp-status", dependencies=[Depends(verify_token)])
async def get_misp_feed_status(request: Request):
    """Return MISP connection health + last sync timestamp."""
    ...
```

### Anti-Patterns to Avoid

- **Calling PyMISP directly from async handlers:** PyMISP uses `requests` (blocking). Always wrap in `asyncio.to_thread()`.
- **Pulling ALL MISP events on every sync:** Use `last='24h'` or `timestamp` filter. Full pulls on a CIRCL feed with 100k+ events will timeout on the N100.
- **Merging MISP into the root docker-compose.yml:** MISP runs on the GMKtec (LAN), not on the Windows desktop. Keep separate compose file.
- **Setting `ssl=True` with a self-signed MISP cert:** Use `ssl=False` for LAN MISP instance or pass the cert path.
- **Using `cache_feeds()` synchronously in the background worker:** Feed caching is slow (downloads 80+ feeds). Run once via `customize_misp.sh` on first startup, then let MISP's built-in scheduler handle refreshes.
- **Storing MISP auth key in docker-compose.yml:** Put it in `.env.misp` (gitignored), ref via `${MISP_KEY}` in compose.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| MISP REST API client | Custom httpx calls for events/attributes | `pymisp.PyMISP` | PyMISP handles auth headers, pagination, response deserialization, pythonify objects, error codes |
| MISP attribute type normalization | Custom string mapping | `MISP_TYPE_MAP` dict (simple) + PyMISP's `MISPAttribute.type` | MISP has 100+ attribute types; only map the ~10 relevant to IOC matching |
| MISP Docker setup | Custom Dockerfile | `ghcr.io/misp/misp-docker/misp-core:latest` | Official image; maintained by MISP project team |
| Feed subscription | Writing MISP feed fetcher | `misp.enable_feed(id)` + `misp.cache_feeds()` via PyMISP | MISP handles feed downloading, format parsing, correlation |
| IOC confidence scoring | Custom score from MISP fields | Map `threat_level_id` (1–4) to confidence (90/70/50/30) | Simple and auditable; aligns with existing 0–100 scale in `ioc_store` |

**Key insight:** The existing `_BaseWorker`/`IocStore` patterns were designed for extension. MISP integration is primarily a new data source adapter, not new infrastructure.

---

## Common Pitfalls

### Pitfall 1: MISP First-Start Takes 2-5 Minutes on N100
**What goes wrong:** `healthcheck` fails, `docker compose up` shows `misp-core` as unhealthy for several minutes. Operators assume it's broken.
**Why it happens:** MISP runs database migrations and PHP bootstrap on first start. N100 is slow at single-threaded PHP.
**How to avoid:** Set `start_period: 120s` in the healthcheck (already shown in pattern above). Monitor logs with `docker compose logs -f misp-core` and wait for `"Apache reporting ready"`.
**Warning signs:** `unhealthy` status in `docker ps` within the first 90 seconds — this is normal.

### Pitfall 2: PyMISP `ssl=True` Fails Against Self-Signed Cert
**What goes wrong:** `PyMISP(url, key, ssl=True)` raises `SSLError: certificate verify failed` against a LAN MISP instance with a self-signed cert.
**Why it happens:** MISP Docker default generates a self-signed TLS cert, but `ssl=True` requires a valid CA chain.
**How to avoid:** Use HTTP on port 8080 within the LAN (not exposed externally) and `ssl=False`, or pass the cert path: `PyMISP(url, key, ssl="/path/to/ca.pem")`. The existing Malcolm pattern uses `MALCOLM_OPENSEARCH_VERIFY_SSL: bool = False` for the same reason.
**Warning signs:** `SSLError` or `requests.exceptions.SSLError` in logs.

### Pitfall 3: `search()` Returns Empty When `to_ids=True` and Feeds Not Cached
**What goes wrong:** `misp.search(controller='attributes', to_ids=True)` returns zero results even after enabling feeds.
**Why it happens:** MISP feed attributes are not imported into the main database unless "Fetch and store" (not just "Cache") is run. Caching stores to Redis for correlation only; fetching imports into the DB.
**How to avoid:** In `customize_misp.sh`, run feed fetch after enabling feeds. Alternatively, use `misp.fetch_feed(feed_id)` for key feeds, not just `misp.cache_feeds()`.
**Warning signs:** Empty search results + Redis cache hit in MISP UI but no events in event list.

### Pitfall 4: N100 Memory Pressure When All Feeds Enabled
**What goes wrong:** MISP crashes or becomes unresponsive when all 80+ default feeds are cached simultaneously.
**Why it happens:** 80+ feeds in Redis can consume 1.2 GB+ of cache per MISP sizing docs. Combined with Malcolm's OpenSearch, the N100's 16 GB fills up.
**How to avoid:** Enable only 5–8 high-quality feeds: CIRCL OSINT, MalwareBazaar, Feodo (MISP format), ESET, abuse.ch URLhaus. Redis cap at 256 MB (`--maxmemory 256mb --maxmemory-policy allkeys-lru`). MariaDB buffer pool at 256 MB.
**Warning signs:** `docker stats` showing Redis at 256 MB cap + frequent evictions.

### Pitfall 5: Duplicate IOCs from Both Phase 33 Feeds and MISP
**What goes wrong:** Feodo IPs appear twice — once from `FeodoWorker` (feed_source='feodo') and once from `MispWorker` (feed_source='misp', if MISP has feodo feed enabled).
**Why it happens:** `ioc_store` PRIMARY KEY is `(ioc_value, ioc_type)` — same IP from two sources causes an upsert collision that overwrites `feed_source`.
**How to avoid:** The existing `upsert_ioc()` logic updates `feed_source` on conflict. For Phase 50, either (a) disable Feodo/ThreatFox as MISP feeds to avoid overlap, or (b) extend the schema to allow multi-source per IOC. Option (a) is simpler: keep Phase 33 workers for their direct feeds, configure MISP feeds only for sources not already covered (CIRCL OSINT, MalwareBazaar, URLhaus).
**Warning signs:** `feed_source` flipping between 'feodo' and 'misp' for the same IP in logs.

### Pitfall 6: PyMISP `pythonify=True` Returns List or Dict Depending on Count
**What goes wrong:** Code assumes `search()` returns a `list` but it returns a `dict` with `{"Attribute": [...]}` when `pythonify=False` (default).
**Why it happens:** Default `pythonify=False` returns raw API response dict. `pythonify=True` returns a Python list of `MISPAttribute` objects.
**How to avoid:** Always use `pythonify=True` in `MispSyncService`. Check `isinstance(attr, MISPAttribute)` before accessing attributes.
**Warning signs:** `AttributeError: 'dict' object has no attribute 'type'`.

---

## Code Examples

Verified patterns from PyMISP docs and MISP REST API:

### Initialize PyMISP (synchronous — call via asyncio.to_thread)
```python
# Source: https://github.com/MISP/PyMISP + https://www.circl.lu/doc/misp/automation/
from pymisp import PyMISP
misp = PyMISP(
    url="http://192.168.1.22:8080",
    key="<40-char-hex-authkey>",      # from MISP UI: Global Actions > My Profile > Auth Keys
    ssl=False,                          # LAN instance, self-signed cert
)
```

### Search IOC Attributes
```python
# Source: PyMISP GitHub examples + MISP automation docs
# Returns list of MISPAttribute when pythonify=True
attributes = misp.search(
    controller="attributes",
    type_attribute=["ip-dst", "ip-src", "domain", "url", "md5", "sha256"],
    to_ids=True,        # Only IDS-flagged indicators
    last="24h",         # Updated in last 24 hours — incremental sync
    limit=5000,
    pythonify=True,
)
# Each attribute: attr.value, attr.type, attr.category, attr.event_id,
#                 attr.first_seen, attr.last_seen, attr.comment, attr.Tag[]
```

### Enable and Fetch a Feed
```python
# Source: MISP automation docs + PyMISP api.py
feeds = misp.get_feeds()           # List all feeds with their IDs
misp.enable_feed(feed_id)          # Enable by numeric ID
misp.fetch_feed(feed_id)           # Download and import into MISP DB (slow, one-time)
misp.cache_feeds()                 # Cache all enabled feeds to Redis
```

### Direct REST call via httpx (fallback if pymisp unavailable)
```python
# Source: MISP REST API docs (https://deepwiki.com/MISP/MISP/4.4-rest-api)
# Authorization header format: "Authorization: <40-char-key>"
import httpx
headers = {
    "Authorization": "<misp_api_key>",
    "Accept": "application/json",
    "Content-Type": "application/json",
}
r = httpx.post(
    "http://192.168.1.22:8080/attributes/restSearch",
    headers=headers,
    json={"returnFormat": "json", "type": "ip-dst", "to_ids": True, "last": "24h"},
    timeout=30,
    verify=False,
)
attrs = r.json()["response"]["Attribute"]
```

### MISP attribute → ioc_store schema mapping
```python
# MISP type → ioc_store ioc_type
MISP_TYPE_MAP = {
    "ip-src":   "ip",
    "ip-dst":   "ip",
    "domain":   "domain",
    "hostname": "domain",
    "url":      "url",
    "md5":      "md5",
    "sha1":     "sha1",
    "sha256":   "sha256",
    "email-src": "email",
    "filename": "filename",
}

# MISP threat_level_id → confidence score (existing 0-100 scale)
# 1=High threat (90 confidence), 2=Medium (70), 3=Low (50), 4=Undefined (30)
THREAT_LEVEL_CONFIDENCE = {1: 90, 2: 70, 3: 50, 4: 30}
```

### ioc_store `extra_json` MISP context schema
```json
{
  "misp_event_id": "123",
  "misp_attr_uuid": "5e8b3a2c-...",
  "misp_category": "Network activity",
  "misp_tags": ["tlp:white", "misp-galaxy:threat-actor=APT29"],
  "misp_comment": "C2 server observed in campaign"
}
```

### customize_misp.sh (post-start automation)
```bash
#!/bin/bash
# File: infra/misp/customize_misp.sh
# Runs on MISP container startup to enable recommended feeds
# Called by MISP's internal hook system

# Enable CIRCL OSINT feed (feed ID 1 in default MISP)
/var/www/MISP/app/cake Admin enableFeeds 1

# Enable MalwareBazaar (abuse.ch)
/var/www/MISP/app/cake Admin enableFeeds 3

# Enable URLhaus
/var/www/MISP/app/cake Admin enableFeeds 2
```

---

## MISP Docker Compose — Memory Budget for N100

Based on official sizing docs and Docker deployment guides:

| Service | Idle RAM | Peak RAM | Config |
|---------|----------|----------|--------|
| `misp-core` (PHP/Apache) | 600 MB | 1.2 GB | 2 workers |
| `mariadb:10.11` | 300 MB | 512 MB | `innodb_buffer_pool_size=256M` |
| `valkey/valkey:7.2` | 50 MB | 256 MB | `--maxmemory 256mb` |
| **MISP total** | **~950 MB** | **~2 GB** | — |
| Malcolm (OpenSearch+Zeek) | ~6 GB | ~10 GB | Already running |
| **Available headroom** | **~7 GB** | — | 16 GB total - 2 GB MISP - 6 GB Malcolm - 2 GB OS |

**Conclusion:** Feasible with memory limits applied. Risk is N100 CPU contention during feed fetch — schedule MISP sync with `interval_sec=21600` (every 6 hours) and stagger from Malcolm's peak ingestion.

---

## Network Connectivity

The GMKtec runs Malcolm and will run MISP. The Windows desktop host runs the FastAPI backend.

```
Windows Desktop (192.168.1.x)
  FastAPI (native, port 8000)
    │
    │  HTTP calls to GMKtec LAN IP
    ▼
GMKtec (192.168.1.22)
  Docker network: Malcolm containers
  Docker network: MISP stack (misp-core port 8080, MariaDB+Redis internal)
    misp-core → http://192.168.1.22:8080
```

**Connection pattern:**
- FastAPI calls `http://192.168.1.22:8080` (MISP_URL in .env)
- MISP containers communicate internally via Docker bridge (`misp-db`, `misp-redis` hostnames)
- No `host.docker.internal` needed — FastAPI is native, MISP is on a separate LAN machine
- MISP port 8080 is LAN-only; NOT exposed through Caddy on the desktop

**Settings key:**
```
MISP_URL=http://192.168.1.22:8080   # In .env on Windows desktop host
MISP_KEY=<40-char-hex>              # From MISP UI after first login
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| MISP required full server install (bare metal) | Official Docker image `ghcr.io/misp/misp-docker` (production-ready) | 2023-2024 | Can run on mini PC alongside other services |
| `python-cybox`/`python-stix` for STIX parsing | PyMISP with built-in MISP core format support | ~2020 | No separate STIX library needed for MISP feeds |
| MISP using Redis 6 | MISP using Valkey 7.2 (Redis-compatible) | 2024 | `valkey/valkey:7.2` in official misp-docker |
| `mysql:5.7` | `mariadb:10.11` | 2023 | MariaDB is now the tested default in misp-docker |

**Deprecated/outdated:**
- `docker.io/coolacid/misp-docker`: Unmaintained, use official GHCR image
- `python-misp`: Old unofficial client, use `pymisp` (official)
- MISP API v1 URL format (`/events/index.json`): Use REST API with `/events/restSearch` + `returnFormat=json`

---

## Open Questions

1. **GMKtec MISP first-run performance**
   - What we know: N100 has 4 E-cores, slow at single-threaded PHP; MISP startup requires DB migrations
   - What's unclear: Actual startup time in minutes on N100 with Malcolm already consuming ~4 CPU%
   - Recommendation: Plan task to document first-run time; set `start_period: 180s` (3 min) in healthcheck to be safe

2. **MISP API key retrieval automation**
   - What we know: Auth key available in MISP UI after first login (Global Actions > My Profile > Auth Keys)
   - What's unclear: Can `customize_misp.sh` emit the auto-generated admin API key for scripted setup?
   - Recommendation: Manual step in deployment task — analyst logs into MISP at `http://192.168.1.22:8080`, copies API key to `.env`

3. **Feed import vs. feed cache distinction**
   - What we know: `cache_feeds()` stores to Redis (correlation only); `fetch_feed()` imports into MariaDB (enables `search()` queries)
   - What's unclear: Whether `search(last='24h')` returns feed-imported attributes or only manually-added events
   - Recommendation: Research task in Wave 0 — verify with a test MISP instance; fallback is direct feed HTTP pull bypassing MISP entirely (same pattern as Phase 33 workers)

4. **Phase 33 feed overlap strategy**
   - What we know: Feodo and ThreatFox workers already run, same IPs may appear in MISP feeds
   - What's unclear: Whether to disable MISP's Feodo/ThreatFox feeds or allow upsert overwrite
   - Recommendation: Disable MISP's feodo/threatfox feeds in `customize_misp.sh`; enable only sources not covered by Phase 33 (CIRCL OSINT, MalwareBazaar, URLhaus)

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 (pytest-asyncio 1.3.0, mode: auto) |
| Config file | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| Quick run command | `uv run pytest tests/unit/test_misp_sync.py -x -q` |
| Full suite command | `uv run pytest tests/unit/ -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DOCKER-01 | MISP compose file is valid YAML with required services | manual smoke | `docker compose -f infra/misp/docker-compose.misp.yml config` | Wave 0 |
| PHASE33-01 | `MispWorker._sync()` upserts attributes into ioc_store | unit | `uv run pytest tests/unit/test_misp_sync.py::test_misp_worker_sync -x` | Wave 0 |
| PHASE33-01 | `MispSyncService.fetch_ioc_attributes()` normalizes MISP types correctly | unit | `uv run pytest tests/unit/test_misp_sync.py::test_attribute_type_mapping -x` | Wave 0 |
| PHASE33-01 | Confidence mapping from threat_level_id is correct | unit | `uv run pytest tests/unit/test_misp_sync.py::test_confidence_mapping -x` | Wave 0 |
| VIEW-01 | `/api/intel/misp-events` returns MISP-sourced IOCs with extra_json | unit | `uv run pytest tests/unit/test_intel_api.py::test_misp_events_endpoint -x` | Wave 0 |
| PHASE33-01 | Retroactive scan triggered for new MISP IOC | unit | `uv run pytest tests/unit/test_misp_sync.py::test_retroactive_trigger -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/unit/test_misp_sync.py -x -q`
- **Per wave merge:** `uv run pytest tests/unit/ -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/unit/test_misp_sync.py` — covers PHASE33-01 unit tests (MispSyncService, MispWorker, type mapping, confidence mapping)
- [ ] `tests/unit/test_intel_api.py` — covers VIEW-01 (new MISP endpoints in intel.py)
- [ ] `infra/misp/docker-compose.misp.yml` — compose file for MISP stack
- [ ] `infra/misp/.env.misp.template` — secrets template
- [ ] `backend/services/intel/misp_sync.py` — MispSyncService class
- [ ] PyMISP install: `uv add pymisp`

---

## Sources

### Primary (HIGH confidence)
- `github.com/MISP/misp-docker` — official Docker image registry, service architecture, environment variables
- `deepwiki.com/MISP/misp-docker/4.2-docker-compose-configuration` — full compose service breakdown, health checks
- `circl.lu/doc/misp/automation/` — REST API endpoints, attribute fields, authorization header format
- `github.com/MISP/PyMISP` — PyMISP installation, method signatures, `pythonify` pattern
- `circl.lu/doc/misp/categories-and-types/` — authoritative MISP attribute type list and categories
- `circl.lu/doc/misp/managing-feeds/` — feed caching vs. fetching distinction

### Secondary (MEDIUM confidence)
- `oneuptime.com/blog/post/2026-02-08-how-to-run-misp-in-docker-for-threat-intelligence/view` — confirmed 4 GB minimum, Redis 256 MB cap recommendation
- `misp-project.org/sizing-your-misp-instance/` — 8–16 GB RAM recommendation for production; minimal at 2 GB for training
- `deepwiki.com/MISP/MISP/4.4-rest-api` — Authorization header format (`Authorization: <key>`) confirmed
- `misp-project.org/feeds/` — CIRCL OSINT feed confirmed as default; 80+ feeds available; three formats (MISP, CSV, freetext)

### Tertiary (LOW confidence)
- Memory estimates for N100 + Malcolm coexistence: extrapolated from MISP sizing docs and Malcolm known footprint; not directly benchmarked on N100 hardware

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — official MISP docs + PyMISP GitHub confirm image names, library name, API patterns
- Architecture: HIGH — extends existing verified _BaseWorker pattern; MISP REST API endpoints confirmed
- Pitfalls: MEDIUM — Docker/SSL pitfalls from official docs; memory pitfalls from sizing docs; feed import vs. cache distinction needs empirical verification
- Resource estimates: MEDIUM — MISP sizing docs give ranges; N100+Malcolm coexistence is estimated

**Research date:** 2026-04-14
**Valid until:** 2026-07-14 (90 days — MISP and misp-docker are actively maintained but API is stable)
