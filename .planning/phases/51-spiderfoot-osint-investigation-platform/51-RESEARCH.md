# Phase 51 Research: SpiderFoot OSINT Investigation Platform

**Date:** 2026-04-16
**Phase:** 51 — SpiderFoot OSINT Investigation Platform
**Research type:** Ecosystem (HOW to implement)

---

## Executive Summary

SpiderFoot must run in Docker on the Windows 11 host (NOT native Python install) due to severe Windows dependency issues. Integration uses its REST API exclusively — not library import. DNSTwist uses its Python library API directly (`import dnstwist; dnstwist.run(...)`). Scan results are read from SpiderFoot's REST API rather than its SQLite directly. Long-running scans are managed with a FastAPI BackgroundTask + SQLite job table pattern. MISP cross-reference is a post-scan pass against the existing Phase 50 MispWorker store.

---

## Standard Stack

| Concern | Choice | Rationale |
|---|---|---|
| SpiderFoot deployment | Docker (`smicallef/spiderfoot` or `ctdc/spiderfoot`) | Native Windows install is broken on Python 3.10+ with lxml/pygexf/PyYAML failures |
| SpiderFoot integration | REST API via `httpx` async client | More reliable than Python library import; survives crashes, upgrades, restarts |
| SpiderFoot client lib | Direct `httpx` calls (NOT `spiderfoot-client` PyPI package) | `spiderfoot-client` is thin wrapper with limited active maintenance; raw httpx is simpler |
| DNSTwist integration | `import dnstwist; dnstwist.run(...)` Python library | Cleaner than subprocess; returns list of dicts; pip-installable; version 20250130 |
| DNSTwist install | `pip install dnstwist[full]` via uv | `[full]` adds ssdeep/TLSH similarity — useful for phishing infrastructure detection |
| Scan job tracking | New SQLite table `osint_investigations` in existing `data/graph.sqlite3` | Avoid a new DB file; fits the graph store's entity-relationship purpose |
| Result storage | SpiderFoot REST API retrieval + our SQLite `osint_findings` table | Avoid direct SpiderFoot SQLite access (fragile, breaks across upgrades) |
| Background execution | `asyncio.create_task()` + polling loop inside the task | BackgroundTasks in FastAPI don't survive server restart; task tracks state in SQLite |
| Frontend graph | Existing InvestigationView with a new OSINT panel | Reuse existing D3/force-graph or similar already in codebase |
| MISP cross-reference | Query existing `ioc_cache` SQLite table after scan completes | Phase 50 already maintains this table; no new service needed |

---

## Architecture Patterns

### Pattern 1: SpiderFoot as a Sidecar Service

SpiderFoot runs as a Docker container alongside Caddy. The FastAPI backend communicates with it via HTTP on `host.docker.internal:5001` (from inside Docker) or `localhost:5001` (from the Windows host process, which is where FastAPI runs natively).

```
Windows host:
  FastAPI (uvicorn, native Python) → http://localhost:5001 → SpiderFoot Docker
  Docker:
    Caddy container (existing)
    SpiderFoot container (new, port 5001)
```

Docker command:
```bash
docker run -d --name spiderfoot \
  -p 5001:5001 \
  -v C:/Users/Admin/spiderfoot-data:/var/lib/spiderfoot \
  --security-opt no-new-privileges \
  smicallef/spiderfoot
```

FastAPI connects from the Windows host process to `http://localhost:5001` — no `host.docker.internal` needed since FastAPI is native, not containerized.

### Pattern 2: Scan Lifecycle via REST API

SpiderFoot's REST API (CherryPy-based, port 5001) exposes these endpoints used in this integration:

| Endpoint | Method | Purpose |
|---|---|---|
| `GET /ping` | GET | Health check — SpiderFoot alive? |
| `POST /startscan` | POST | Create and start scan |
| `GET /scanstatus?id=<id>` | GET | Poll scan state |
| `GET /scansummary?id=<id>&by=type` | GET | Results summary by event type |
| `GET /scaneventresults?id=<id>&eventType=<type>` | GET | Events of one type |
| `GET /scanviz?id=<id>` | GET | Graph JSON (nodes/edges) |
| `POST /stopscan` | POST | Cancel scan (body: `id=<id>`) |
| `POST /scandelete` | POST | Delete scan record |
| `GET /modules` | GET | List available modules |

**POST /startscan parameters:**
- `scanname` — human-readable label
- `scantarget` — IP, domain, email, ASN, etc.
- `modulelist` — comma-separated module names (empty = use `usecase`)
- `typelist` — event types to collect (empty = all)
- `usecase` — `all`, `footprint`, `investigate`, `passive`

**Scan status values:** `RUNNING`, `FINISHED`, `ABORT-REQUESTED`, `ABORTED`, `ERROR-FAILED`

**Response from /startscan:** Returns a scan ID string used for all subsequent calls.

### Pattern 3: Async Scan Management

SpiderFoot scans take minutes to hours. Use an asyncio background task with a timeout ceiling:

```python
# In FastAPI route handler:
async def start_investigation(target: str, usecase: str = "investigate"):
    scan_id = await spiderfoot_client.start_scan(target, usecase)
    # Store job in SQLite immediately
    await store_job(scan_id, target, status="RUNNING")
    # Launch background poller — non-blocking
    asyncio.create_task(poll_scan_to_completion(scan_id, timeout_seconds=1800))
    return {"job_id": scan_id, "status": "RUNNING"}

async def poll_scan_to_completion(scan_id: str, timeout_seconds: int = 1800):
    deadline = asyncio.get_event_loop().time() + timeout_seconds
    while asyncio.get_event_loop().time() < deadline:
        await asyncio.sleep(15)  # poll every 15s
        status = await spiderfoot_client.get_status(scan_id)
        if status in ("FINISHED", "ERROR-FAILED", "ABORTED"):
            await harvest_results(scan_id)
            await update_job_status(scan_id, status)
            return
    # Timeout: request abort
    await spiderfoot_client.stop_scan(scan_id)
    await update_job_status(scan_id, "TIMEOUT")
```

### Pattern 4: DNSTwist Library Integration

```python
import asyncio
import dnstwist

async def run_dnstwist(domain: str, threads: int = 8) -> list[dict]:
    """Run dnstwist in a thread (CPU-bound). Returns registered lookalike domains."""
    def _run() -> list[dict]:
        return dnstwist.run(
            domain=domain,
            registered=True,   # Only return domains that have DNS records
            threads=threads,
            mxcheck=True,      # Check MX records (phishing email infra)
            format="null",     # Internal format — returns list of dicts
        )
    return await asyncio.to_thread(_run)
```

Return dict keys per domain: `fuzzer`, `domain`, `dns_a`, `dns_aaaa`, `dns_ns`, `dns_mx`, `geoip`, `banner_http`, `banner_smtp`, `ssdeep`, `tlsh`, `phash`, `whois_registrar`, `whois_created`.

### Pattern 5: SQLite Job and Findings Tables

Add to existing `data/graph.sqlite3` (WAL mode already enabled):

```sql
-- Investigation jobs
CREATE TABLE IF NOT EXISTS osint_investigations (
    id TEXT PRIMARY KEY,           -- SpiderFoot scan ID
    target TEXT NOT NULL,
    target_type TEXT,              -- ip, domain, email, asn
    usecase TEXT DEFAULT 'investigate',
    status TEXT DEFAULT 'RUNNING', -- RUNNING/FINISHED/ERROR-FAILED/ABORTED/TIMEOUT
    started_at TEXT NOT NULL,
    completed_at TEXT,
    result_summary JSON,           -- top-level counts by event type
    error TEXT
);

-- Individual OSINT findings from SpiderFoot
CREATE TABLE IF NOT EXISTS osint_findings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    investigation_id TEXT NOT NULL REFERENCES osint_investigations(id),
    event_type TEXT NOT NULL,      -- IP_ADDRESS, DOMAIN_NAME, etc.
    data TEXT NOT NULL,            -- the finding value
    source_module TEXT,
    confidence REAL,
    created_at TEXT NOT NULL,
    misp_hit INTEGER DEFAULT 0,    -- 1 if cross-referenced against MISP
    misp_event_ids TEXT            -- JSON array of matching MISP event IDs
);

-- DNSTwist lookalike domain findings
CREATE TABLE IF NOT EXISTS dnstwist_findings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    investigation_id TEXT NOT NULL REFERENCES osint_investigations(id),
    seed_domain TEXT NOT NULL,
    fuzzer TEXT,
    lookalike_domain TEXT NOT NULL,
    dns_a TEXT,
    dns_mx TEXT,
    whois_registrar TEXT,
    whois_created TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_osint_findings_inv ON osint_findings(investigation_id);
CREATE INDEX IF NOT EXISTS idx_dnstwist_findings_inv ON dnstwist_findings(investigation_id);
```

### Pattern 6: SpiderFoot Module Selection for No-API-Key Use

Use `usecase=investigate` as the default. This enables:
- **sfp_ripe** — BGP ASN lookup (no key)
- **sfp_whois** — WHOIS for domains and netblocks (no key)
- **sfp_dns** — DNS resolution and enumeration (no key)
- **sfp_dnsresolve** — Reverse DNS (no key)
- **sfp_ssl** — TLS certificate inspection (no key)
- **sfp_crt** — Certificate transparency (crt.sh, no key)
- **sfp_bgpview** — BGPView ASN/prefix data (no key)
- **sfp_blacklist** — Various IP blacklists (no key)
- **sfp_similar** — Domain similarity detection (no key)
- **sfp_robtex** — Passive DNS via Robtex (no key)
- **sfp_hackertarget** — HackerTarget passive DNS (no key, rate-limited)
- **sfp_threatcrowd** — ThreatCrowd historical data (no key)
- **sfp_urlscan** — URLScan.io (no key for basic lookups)

Avoid `usecase=all` in production — runs 200+ modules including many that make active network contact and require API keys, causing noise and delays.

### Pattern 7: MISP Cross-Reference

After SpiderFoot scan harvests findings, run a cross-reference pass against the Phase 50 `ioc_cache` table:

```python
async def misp_crossref(findings: list[dict], sqlite_store) -> list[dict]:
    """Tag each finding with MISP event IDs if the IOC exists in local MISP cache."""
    for finding in findings:
        ioc_value = finding["data"]
        # Query the ioc_cache table Phase 50 already maintains
        rows = await asyncio.to_thread(
            sqlite_store.query_ioc_cache, ioc_value
        )
        if rows:
            finding["misp_hit"] = True
            finding["misp_event_ids"] = [r["event_uuid"] for r in rows]
    return findings
```

No new MISP API calls needed — the Phase 50 sync worker already populates `ioc_cache` every 6 hours.

### Pattern 8: API Endpoints

```
POST /api/osint/investigate
  Body: { "target": "1.2.3.4", "usecase": "investigate" }
  Response: { "job_id": "abc123", "status": "RUNNING" }

GET /api/osint/investigate/{job_id}
  Response: { "status": "FINISHED", "summary": {...}, "findings": [...] }

GET /api/osint/investigations
  Response: [ { "id": ..., "target": ..., "status": ..., "started_at": ... } ]

DELETE /api/osint/investigate/{job_id}
  Effect: stop if running, delete from SpiderFoot, mark deleted in SQLite

POST /api/osint/dnstwist
  Body: { "domain": "example.com" }
  Response: { "lookalikes": [...] }  (synchronous, completes in seconds-minutes)
```

---

## Don't Hand-Roll

- **SpiderFoot module logic** — Do not re-implement WHOIS, passive DNS, CT log querying, BGP lookups. SpiderFoot's 200+ modules handle this. Use the REST API.
- **Domain permutation algorithms** — Do not implement typosquatting fuzzing manually. Use `dnstwist` library's built-in fuzzers (bitsquatting, homoglyph, transposition, vowel-swap, addition, subdomain, hyphenation, etc.).
- **Graph visualization of OSINT relationships** — Do not build a custom graph renderer for Phase 51. Use SpiderFoot's `GET /scanviz` endpoint to retrieve the relationship graph data and render it with whatever force-graph/D3 component is already in InvestigationView.
- **SpiderFoot authentication** — Do not implement digest auth unless required. SpiderFoot runs unauthenticated by default on localhost (no `passwd` file). Keep it localhost-only.
- **Windows-native SpiderFoot install** — Do not attempt native Python install. lxml, pygexf, PyYAML build failures on Python 3.10+ make this unreliable. Docker is the only supported path for this project.

---

## Common Pitfalls

### 1. SpiderFoot Windows Native Install Failures (HIGH CONFIDENCE)
SpiderFoot explicitly dropped Windows `.exe` support after v2.12. On Python 3.10+ (project uses 3.12), `pip install -r requirements.txt` fails with:
- `lxml` wheel build error — requires pre-installed C compiler
- `pygexf` uses legacy `setup.py install` (deprecated in Python 3.12)
- `PyYAML` build failures with subprocess exit code 1

**Fix:** Use Docker exclusively. Mount a volume at `/var/lib/spiderfoot` for persistence.

### 2. SpiderFoot Scans Hang Indefinitely (HIGH CONFIDENCE)
Issues #1151 and #1811 on the SpiderFoot GitHub confirm scans can hang in `RUNNING` state permanently when modules stall waiting on external services. The UI shows "WAITING FOR THE SCAN TO INITIALIZE" or just keeps generating.

**Fix:** Hard timeout ceiling in the poll loop (30 minutes max). Call `POST /stopscan` on timeout. Never `asyncio.wait_for` — use deadline-based polling (Phase 45 pattern).

### 3. SpiderFoot REST API Uses CherryPy, Not JSON Bodies (HIGH CONFIDENCE)
POST endpoints (`/startscan`, `/stopscan`) use `application/x-www-form-urlencoded`, not JSON. `httpx` must send `data={}` not `json={}`.

```python
# CORRECT:
resp = await client.post(
    "http://localhost:5001/startscan",
    data={
        "scanname": "Investigation of 1.2.3.4",
        "scantarget": "1.2.3.4",
        "usecase": "investigate",
        "modulelist": "",
        "typelist": "",
    }
)

# WRONG (silently returns empty/error):
resp = await client.post("http://localhost:5001/startscan", json={...})
```

### 4. DNSTwist Blocks the Event Loop (HIGH CONFIDENCE)
`dnstwist.run()` spawns daemon threads internally but the call itself is synchronous and can take 30-120 seconds for a domain with many permutations. Never call from async context directly.

**Fix:** Always wrap in `asyncio.to_thread()`. Set `threads=8` to bound parallelism.

### 5. SpiderFoot Scan Results Are Paginated by Event Type (MEDIUM CONFIDENCE)
`GET /scaneventresults` returns results for ONE event type at a time. To harvest all findings, iterate over all event types from `GET /eventtypes` and fetch each separately. `GET /scansummary?by=type` first gives counts to skip empty types.

### 6. SpiderFoot /startscan Returns Scan ID in Unexpected Format (MEDIUM CONFIDENCE)
The `/startscan` response is a string scan ID (not JSON). Parse with `resp.text.strip()` not `resp.json()`.

### 7. DNSTwist `registered=True` Can Still Return Unresolvable Domains (MEDIUM CONFIDENCE)
The `registered` filter uses DNS lookups which can fail transiently. Always check that `dns_a` or `dns_ns` is non-empty before treating a finding as confirmed registered.

### 8. MISP Cross-Reference on Large Finding Sets (LOW CONFIDENCE)
SpiderFoot `usecase=investigate` on a well-connected IP can return thousands of findings. Running `query_ioc_cache` per-finding in sequence will be slow. Use a single `WHERE data IN (...)` bulk query pattern against the ioc_cache table.

### 9. SpiderFoot Container Requires Restart After Config Changes (LOW CONFIDENCE)
If analyst adds API keys to SpiderFoot settings (e.g., Shodan, VirusTotal), the container must be restarted for changes to take effect. SpiderFoot reads settings at startup.

---

## Code Examples

### SpiderFoot Client (httpx, form-encoded)

```python
import asyncio
import httpx
from backend.core.logging import get_logger

log = get_logger(__name__)

SPIDERFOOT_BASE = "http://localhost:5001"

class SpiderFootClient:
    def __init__(self, base_url: str = SPIDERFOOT_BASE):
        self._base = base_url.rstrip("/")

    async def ping(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5) as c:
                r = await c.get(f"{self._base}/ping")
            return r.status_code == 200
        except Exception:
            return False

    async def start_scan(self, target: str, usecase: str = "investigate") -> str:
        """Returns scan ID string."""
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.post(
                f"{self._base}/startscan",
                data={
                    "scanname": f"AI-SOC: {target}",
                    "scantarget": target,
                    "usecase": usecase,
                    "modulelist": "",
                    "typelist": "",
                },
            )
        r.raise_for_status()
        return r.text.strip()

    async def get_status(self, scan_id: str) -> str:
        """Returns status string: RUNNING, FINISHED, ERROR-FAILED, ABORTED, etc."""
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(f"{self._base}/scanstatus", params={"id": scan_id})
        r.raise_for_status()
        data = r.json()
        # scanstatus returns list: [scan_id, name, target, created, started,
        #   ended, status, module_count, event_count]
        return data[6] if isinstance(data, list) and len(data) > 6 else "UNKNOWN"

    async def get_summary(self, scan_id: str) -> list[dict]:
        """Returns list of {type, count} dicts."""
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.get(
                f"{self._base}/scansummary",
                params={"id": scan_id, "by": "type"},
            )
        r.raise_for_status()
        return r.json()  # list of [type, count, ...] arrays

    async def get_events(self, scan_id: str, event_type: str) -> list[list]:
        """Returns list of event rows for a given event type."""
        async with httpx.AsyncClient(timeout=60) as c:
            r = await c.get(
                f"{self._base}/scaneventresults",
                params={"id": scan_id, "eventType": event_type, "filterfp": "1"},
            )
        r.raise_for_status()
        return r.json()

    async def get_graph(self, scan_id: str) -> dict:
        """Returns graph JSON with nodes and edges."""
        async with httpx.AsyncClient(timeout=60) as c:
            r = await c.get(f"{self._base}/scanviz", params={"id": scan_id})
        r.raise_for_status()
        return r.json()

    async def stop_scan(self, scan_id: str) -> None:
        async with httpx.AsyncClient(timeout=10) as c:
            await c.post(f"{self._base}/stopscan", data={"id": scan_id})

    async def delete_scan(self, scan_id: str) -> None:
        async with httpx.AsyncClient(timeout=10) as c:
            await c.post(f"{self._base}/scandelete", data={"id": scan_id})
```

### DNSTwist Integration

```python
import asyncio
import dnstwist
from backend.core.logging import get_logger

log = get_logger(__name__)

async def run_dnstwist(domain: str, threads: int = 8) -> list[dict]:
    """Run dnstwist permutation scan in thread pool. Returns registered lookalikes."""
    def _scan() -> list[dict]:
        try:
            results = dnstwist.run(
                domain=domain,
                registered=True,
                threads=threads,
                mxcheck=True,
                format="null",    # returns list of dicts (not formatted string)
            )
            # Filter: only confirmed registered (has DNS A or NS record)
            return [
                r for r in results
                if r.get("dns_a") or r.get("dns_ns")
            ]
        except Exception as exc:
            log.warning("dnstwist scan failed", domain=domain, error=str(exc))
            return []

    return await asyncio.to_thread(_scan)
```

### Scan Poller (Background Task Pattern)

```python
import asyncio
from datetime import datetime, timezone

TERMINAL_STATES = {"FINISHED", "ERROR-FAILED", "ABORTED"}

async def poll_to_completion(
    scan_id: str,
    client: SpiderFootClient,
    sqlite_store,
    timeout_seconds: int = 1800,
    poll_interval: int = 15,
) -> None:
    loop = asyncio.get_event_loop()
    deadline = loop.time() + timeout_seconds

    while loop.time() < deadline:
        await asyncio.sleep(poll_interval)
        try:
            status = await client.get_status(scan_id)
        except Exception as exc:
            log.warning("poll_status failed", scan_id=scan_id, error=str(exc))
            continue

        if status in TERMINAL_STATES:
            if status == "FINISHED":
                await harvest_and_store(scan_id, client, sqlite_store)
            await asyncio.to_thread(
                sqlite_store.update_investigation_status,
                scan_id, status,
                datetime.now(tz=timezone.utc).isoformat(),
            )
            return

    # Deadline exceeded
    await client.stop_scan(scan_id)
    await asyncio.to_thread(
        sqlite_store.update_investigation_status,
        scan_id, "TIMEOUT",
        datetime.now(tz=timezone.utc).isoformat(),
    )
```

### Harvest Results

```python
async def harvest_and_store(
    scan_id: str,
    client: SpiderFootClient,
    sqlite_store,
) -> None:
    """Fetch all findings from SpiderFoot and persist to osint_findings."""
    summary = await client.get_summary(scan_id)
    # summary is list of arrays: [eventtype, count, ...]
    # Only harvest types with results
    event_types = [row[0] for row in summary if row and int(row[1]) > 0]

    findings = []
    for etype in event_types:
        rows = await client.get_events(scan_id, etype)
        for row in rows:
            # row format: [module, type, data, source_event_id, confidence, ...]
            findings.append({
                "investigation_id": scan_id,
                "event_type": etype,
                "source_module": row[0] if len(row) > 0 else None,
                "data": row[2] if len(row) > 2 else "",
                "confidence": float(row[4]) if len(row) > 4 else 1.0,
            })

    # MISP cross-reference in bulk
    ioc_values = [f["data"] for f in findings]
    misp_hits = await asyncio.to_thread(
        sqlite_store.bulk_query_ioc_cache, ioc_values
    )
    misp_map = {hit["value"]: hit for hit in misp_hits}
    for f in findings:
        if f["data"] in misp_map:
            f["misp_hit"] = 1
            f["misp_event_ids"] = misp_map[f["data"]].get("event_ids", [])

    await asyncio.to_thread(sqlite_store.bulk_insert_osint_findings, findings)
```

### Frontend Integration Pattern (Svelte 5)

```typescript
// In InvestigationView — OSINT panel
let osintJob = $state<{ job_id: string; status: string } | null>(null);
let osintFindings = $state<OsintFinding[]>([]);

async function investigateTarget(target: string) {
  osintJob = await api.osint.startInvestigation(target, 'investigate');
  // Poll until terminal state
  while (osintJob && !['FINISHED','ERROR-FAILED','ABORTED','TIMEOUT'].includes(osintJob.status)) {
    await new Promise(r => setTimeout(r, 10_000));
    osintJob = await api.osint.getInvestigation(osintJob.job_id);
  }
  if (osintJob?.status === 'FINISHED') {
    const detail = await api.osint.getInvestigation(osintJob.job_id);
    osintFindings = detail.findings ?? [];
  }
}
```

---

## Key Questions Answered

### Q1: REST API vs Python library import — which is more reliable?
**REST API via httpx.** SpiderFoot's internal Python modules are not designed for external import — they're tightly coupled to the SpiderFoot event bus, plugin registry, and `SpiderFoot` class. The REST API is the documented integration surface. It also lets SpiderFoot run in its own process/container, crash-isolated from FastAPI.

### Q2: Scan lifecycle — trigger, poll, retrieve?
1. `POST /startscan` (form-encoded) → returns scan ID text
2. Poll `GET /scanstatus?id=X` every 15s → check field[6] for terminal state
3. On FINISHED: `GET /scansummary?id=X&by=type` → get counts per event type
4. For each non-zero type: `GET /scaneventresults?id=X&eventType=Y&filterfp=1`
5. Optionally: `GET /scanviz?id=X` for relationship graph JSON

### Q3: DNSTwist — library vs subprocess?
**Python library (`import dnstwist`).** The `dnstwist.run(**kwargs)` function returns `list[dict]` directly. No subprocess parsing, no temp files. Available via pip since the package moved to pure-library architecture.

### Q4: Result storage — SpiderFoot SQLite vs our SQLite?
**Our SQLite via REST API harvest.** Direct SpiderFoot SQLite access (`/var/lib/spiderfoot/*.db` inside the container) requires volume mounting and schema knowledge that changes between versions. The REST API is the stable contract. Harvest findings after scan completion and store in our `osint_findings` table.

### Q5: Windows compatibility?
**Docker only.** Native Python install fails on Python 3.10+ due to lxml and pygexf build failures. Issue #1941 documents a workaround requiring Python 3.9.12 — incompatible with the project's locked Python 3.12. Use:
```
docker run -p 5001:5001 -v C:/Users/Admin/spiderfoot-data:/var/lib/spiderfoot smicallef/spiderfoot
```

### Q6: Scan timeout/resource management?
- Default timeout: 30 minutes (1800s) — enough for `investigate` usecase on a single IP
- Poll interval: 15 seconds (enough responsiveness, low overhead)
- Use deadline-based polling (Phase 45 `run_investigation()` pattern), not `asyncio.wait_for`
- On timeout: call `POST /stopscan`, mark job `TIMEOUT` in SQLite
- Cancellation: expose `DELETE /api/osint/investigate/{job_id}` which calls `/stopscan`

### Q7: Modules without API keys?
Use `usecase=investigate` — this automatically selects ~60-80 modules covering:
- WHOIS, rDNS, forward DNS, zone transfers
- BGP/ASN via BGPView and RIPE
- Certificate transparency via crt.sh (sfp_crt)
- Passive DNS via Robtex, HackerTarget
- IP blacklists (abuse.ch, spamhaus, etc.)
- SSL/TLS certificate inspection
- HTTP headers and banner grabbing (active but non-intrusive)

Do NOT pass a `modulelist` — let `usecase` drive module selection.

### Q8: MISP cross-reference?
Query the existing `ioc_cache` table (Phase 50) after scan harvest. Use a bulk `WHERE value IN (...)` query to avoid N+1 per-finding queries. No new MISP API calls required — the Phase 50 MispWorker syncs every 6 hours.

---

## Confidence Levels

| Claim | Confidence | Source |
|---|---|---|
| SpiderFoot REST API uses CherryPy + form-encoded POST | HIGH | sfwebui.py source code inspection |
| /startscan returns plain text scan ID (not JSON) | HIGH | sfwebui.py code + marlinkcyber/spiderfoot-client source |
| Scan status values include RUNNING/FINISHED/ERROR-FAILED/ABORTED | HIGH | sfwebui.py code references |
| Native Windows install broken on Python 3.10+ | HIGH | Multiple GitHub issues (#1896, #1897, #1906, #1941) |
| Docker port 5001, data at /var/lib/spiderfoot | HIGH | Official Dockerfile + docker-compose.yml |
| dnstwist.run() returns list[dict] | HIGH | dnstwist.py source + PyPI documentation |
| dnstwist dict keys: fuzzer, domain, dns_a, dns_ns, dns_mx, etc. | HIGH | dnstwist.py source analysis |
| usecase=investigate enables ~60-80 no-key modules | MEDIUM | SpiderFoot docs + module README + community guides |
| /scanstatus response is array with status at index[6] | MEDIUM | sfwebui.py code inspection (format may vary by version) |
| SpiderFoot scans can hang indefinitely without timeout | HIGH | GitHub issues #1151, #1811 |
| MISP native SpiderFoot module exists (sfp_misp) | MEDIUM | Community discussions (not verified in master) |
| /scanviz returns JSON graph (not only GEXF) | MEDIUM | sfwebui.py has both JSON and GEXF paths via gexf param |
