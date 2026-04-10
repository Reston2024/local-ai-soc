# Phase 33: Threat Intelligence Platform — Research

**Researched:** 2026-04-09
**Domain:** IOC feed ingestion, SQLite ioc_store, DuckDB column migration, Svelte 5 UI rewrite
**Confidence:** HIGH (all findings verified against live project code or official feed URLs)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- 3 feeds only: Feodo Tracker (CSV, C2 IPs), CISA KEV (JSON, CVEs), ThreatFox (CSV export, IPs/domains/hashes)
- Feed sync via background asyncio task — one task per feed, mirrors MalcolmCollector pattern
- Each feed: SQLite cursor key `intel.feodo.last_sync`, `intel.cisa_kev.last_sync`, `intel.threatfox.last_sync`
- Sync is upsert: same IOC value+type — update confidence/last_seen, never duplicate
- At-ingest matching: check `src_ip` and `dst_ip` after normalization; tag matching events with `ioc_matched`, `ioc_confidence`, `ioc_actor_tag`
- Retroactive matching: when a feed sync adds new IOC, run DuckDB scan against last 30 days
- No on-demand matching — fully automatic
- Static scoring: Feodo/ThreatFox C2 = 50 pts, CISA KEV = 40 pts
- Confidence decay: daily job, 5 pts/week, floor 0, midnight UTC
- ThreatIntelView: primary = IOC hit list (events, not IOCs), sorted risk score descending
- Compact header strip: one row per feed (name, last sync, IOC count, status)
- Empty state: strip visible + "No IOC matches yet — feeds syncing hourly."
- Row click: inline expansion (same pattern as HuntingView OSINT panel)
- Risk badge: >=75 red, 50-74 orange, 25-49 yellow, <25 grey
- Risk score displayed in ThreatIntelView ONLY — not propagated to other views this phase
- Zero API keys for MVP — hard constraint

### Claude's Discretion
- Exact SQLite DDL for `ioc_store`, `ioc_enrichment_cache`, `ioc_relationships` tables
- Feed worker concurrency model (one asyncio task per feed vs single scheduler loop)
- Retroactive scan batch size and timeout handling for large event sets
- ThreatIntelView Svelte component internal structure (tabs vs single scroll)
- Feodo CSV column mapping (field names change occasionally)

### Deferred Ideas (OUT OF SCOPE)
- MISP/TAXII 2.1 ingestion (Phase 34)
- AlienVault OTX, URLhaus, Blocklist.de, PhishTank, Emerging Threats, Greynoise, MalwareBazaar (Phase 34)
- IOC revocation / false-positive marking UI
- PassiveDNS pivot (CIRCL.lu)
- Certificate intelligence (crt.sh)
- Risk score in EventsView / DetectionsView / HuntingView
- IOC relationship graph in GraphView
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| P33-T01 | Feodo Tracker CSV feed worker (hourly sync, C2 IPs) | Feed format verified — 6 columns, dst_ip is the IOC value |
| P33-T02 | CISA KEV JSON feed worker (hourly sync, CVEs) | Feed schema verified — 11 fields per vuln entry |
| P33-T03 | ThreatFox CSV export feed worker (hourly sync, IPs/domains/hashes) | CSV export accessible without auth — 15 columns |
| P33-T04 | SQLite ioc_store DDL + CRUD (upsert_ioc, get_ioc, list_iocs) | DDL designed from osint_cache pattern |
| P33-T05 | DuckDB migration: 3 new columns on normalized_events | Migration pattern confirmed from _ECS_MIGRATION_COLUMNS |
| P33-T06 | At-ingest IOC matching hook in loader.py | Hook point: ingest_events() after normalize, before DuckDB INSERT |
| P33-T07 | Retroactive IOC scan (DuckDB 30-day window) | DuckDB INTERVAL syntax confirmed from events.py patterns |
| P33-T08 | Confidence decay background job (daily, midnight UTC, APScheduler) | APScheduler already in main.py for KPI snapshot |
| P33-T09 | GET /api/intel/ioc-hits endpoint + GET /api/intel/feeds endpoint | Router pattern confirmed from main.py deferred router block |
| P33-T10 | ThreatIntelView.svelte rewrite (hit list + feed strip + inline expansion) | HuntingView expandRow pattern directly replicable |
| P33-T14 | NormalizedEvent model + INSERT SQL updated for 3 new columns | loader.py _INSERT_SQL and to_duckdb_row() need extension |
| P33-T15 | Feed sync tasks registered in lifespan (main.py) | asyncio.ensure_future pattern confirmed |
| P33-T16 | intel router registered in main.py deferred-router block | Pattern confirmed |
</phase_requirements>

---

## Summary

Phase 33 integrates three no-key threat intelligence feeds into a SQLite-backed ioc_store, hooks automatic IOC matching into the existing ingest pipeline, and rewrites ThreatIntelView from a stub into a live hit-list console. All three technical areas have direct precedents in the existing codebase: the feed workers mirror MalcolmCollector's asyncio loop, the ioc_store DDL mirrors the osint_cache table, and the ThreatIntelView expansion UI mirrors HuntingView's expandRow pattern.

One important finding: the CONTEXT.md stated ThreatFox requires no API key. The ThreatFox REST API (`/api/v1/`) now requires a free Auth-Key (as of 2025). However, the ThreatFox CSV export endpoint (`https://threatfox.abuse.ch/export/csv/ip-port/recent/`) is accessible without authentication and provides the same IOC data (15 columns including ioc_value, ioc_type, malware_printable, confidence_level, tags). **Use the CSV export endpoint, not the REST API, for ThreatFox.** This maintains the zero-key constraint.

The Feodo Tracker CSV recommended URL (`/downloads/ipblocklist_recommended.csv`) returns 404. The working URL is `/downloads/ipblocklist.csv`. The column `dst_ip` is the C2 server IP (not `ip_address`).

**Primary recommendation:** Build three independent feed workers as asyncio tasks, each following the MalcolmCollector `run()` pattern with exponential backoff. Use the ThreatFox CSV export rather than the REST API to avoid key requirement.

---

## Feed Format Analysis

### Feodo Tracker CSV

**URL:** `https://feodotracker.abuse.ch/downloads/ipblocklist.csv`
**Confidence:** HIGH — verified by direct fetch

| Column | Content | Use |
|--------|---------|-----|
| `first_seen_utc` | ISO datetime string | `first_seen` in ioc_store |
| `dst_ip` | C2 server IP address | `ioc_value` — this IS the IOC |
| `dst_port` | C2 port number | store in `extra_json` |
| `c2_status` | `online` / `offline` | store in `extra_json` |
| `last_online` | date string | `last_seen` in ioc_store |
| `malware` | malware family name (Emotet, QakBot, etc.) | `malware_family` in ioc_store |

IOC type mapping: all Feodo entries are `ioc_type = "ip"`. Initial confidence score: **50** (C2 designation).

Comment lines start with `#` — skip with `if line.startswith("#")`.

### CISA KEV JSON

**URL:** `https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json`
**Confidence:** HIGH — verified by direct fetch

Top-level structure:
```json
{
  "title": "CISA Known Exploited Vulnerabilities Catalog",
  "catalogVersion": "...",
  "dateReleased": "...",
  "count": N,
  "vulnerabilities": [...]
}
```

Per-vulnerability fields:
| Field | Use |
|-------|-----|
| `cveID` | `ioc_value` (e.g. "CVE-2024-12345") |
| `vendorProject` | store in `extra_json` |
| `product` | store in `extra_json` |
| `vulnerabilityName` | `actor_tag` / description |
| `dateAdded` | `first_seen` |
| `shortDescription` | store in `extra_json` |
| `requiredAction` | store in `extra_json` |
| `dueDate` | store in `extra_json` |
| `knownRansomwareCampaignUse` | store in `extra_json` (Yes/No/Known) |
| `notes` | store in `extra_json` |
| `cwes` | store in `extra_json` (array) |

IOC type mapping: `ioc_type = "cve"`. Initial confidence score: **40** (CISA KEV designation).

### ThreatFox CSV Export

**URL:** `https://threatfox.abuse.ch/export/csv/ip-port/recent/`
**Confidence:** HIGH — verified by direct fetch, no auth required

The CSV export provides 15 columns:

| Column | Use |
|--------|-----|
| `first_seen_utc` | `first_seen` |
| `ioc_id` | discard (ThreatFox internal) |
| `ioc_value` | `ioc_value` (IP:port format for ip-port type) |
| `ioc_type` | maps to ioc_store `ioc_type` (`ip_port`, `domain`, etc.) |
| `threat_type` | store in `extra_json` |
| `fk_malware` | store in `extra_json` (malware slug) |
| `malware_alias` | store in `extra_json` |
| `malware_printable` | `malware_family` |
| `last_seen_utc` | `last_seen` |
| `confidence_level` | `confidence` (0-100 integer) |
| `is_compromised` | store in `extra_json` |
| `reference` | store in `extra_json` |
| `tags` | `actor_tag` (pipe-separated string) |
| `anonymous` | discard |
| `reporter` | store in `extra_json` |

**Note on ioc_value parsing for ip-port type:** ThreatFox CSV delivers values like `145.239.200.154:4000`. For IOC matching against `src_ip`/`dst_ip`, extract just the IP portion: `ioc_value.split(":")[0]`. Store the full `ip:port` string as the canonical `ioc_value`, but index the bare IP for lookup.

IOC type mapping: use `ioc_type` column directly. Initial confidence score: **50** (C2 botnet designation).

**Alternative URLs for other IOC types** (all no-auth CSV export):
- `https://threatfox.abuse.ch/export/csv/domains/recent/` — domain IOCs
- `https://threatfox.abuse.ch/export/csv/urls/recent/` — URL IOCs

For Phase 33, fetch only `ip-port` export to keep scope tight. Domains/URLs can be added in Phase 34.

---

## Standard Stack

### Core (no new dependencies — all already installed)
| Library | Version | Purpose |
|---------|---------|---------|
| `httpx` | current | HTTP fetches for all 3 feeds (sync, called via asyncio.to_thread) |
| `sqlite3` | stdlib | ioc_store backend (same as osint_cache) |
| `csv` | stdlib | Parse Feodo Tracker and ThreatFox CSV responses |
| `json` | stdlib | Parse CISA KEV JSON response |
| `asyncio` | stdlib | Background task loop (asyncio.ensure_future) |
| `apscheduler` | current | Midnight decay job (already in main.py for KPI snapshot) |

No new pip dependencies required. `httpx` is already a project dependency. APScheduler is already imported in `main.py`.

---

## Architecture Patterns

### Recommended Package Structure
```
backend/services/intel/
├── __init__.py
├── feed_sync.py        # Feed worker classes (FeodoWorker, CisaKevWorker, ThreatFoxWorker)
├── ioc_store.py        # SQLite CRUD: upsert_ioc, get_ioc, list_iocs, list_hits
└── risk_score.py       # Score computation (50/40 base) + decay logic

backend/api/
└── intel.py            # GET /api/intel/ioc-hits, GET /api/intel/feeds

tests/unit/
└── test_intel_feeds.py     # Feed worker unit tests (mock httpx)
└── test_ioc_store.py       # SQLite CRUD tests (:memory:)
└── test_ioc_matching.py    # At-ingest matching tests
```

### Pattern 1: Feed Worker (asyncio task with backoff)

Exact replica of `MalcolmCollector.run()` from `ingestion/jobs/malcolm_collector.py` lines 738-754:

```python
class FeodoWorker:
    def __init__(self, sqlite_store, interval_sec: int = 3600) -> None:
        self._sqlite = sqlite_store
        self._interval = interval_sec
        self._running = False
        self._consecutive_failures = 0
        self._iocs_ingested = 0

    async def run(self) -> None:
        """Main sync loop. Cancellation propagates via CancelledError."""
        self._running = True
        backoff = self._interval
        try:
            while True:
                await asyncio.sleep(backoff)
                success = await self._sync()
                if success:
                    self._consecutive_failures = 0
                    backoff = self._interval
                else:
                    self._consecutive_failures += 1
                    backoff = min(self._interval * (2 ** self._consecutive_failures), 3600)
        except asyncio.CancelledError:
            self._running = False
            raise

    async def _sync(self) -> bool:
        """Fetch CSV, upsert IOCs, trigger retroactive scan. Returns True on success."""
        try:
            rows = await asyncio.to_thread(self._fetch_csv)
            new_iocs = []
            for row in rows:
                is_new = await asyncio.to_thread(self._sqlite.upsert_ioc, ...)
                if is_new:
                    new_iocs.append(row["dst_ip"])
            if new_iocs:
                asyncio.create_task(self._retroactive_scan(new_iocs))
            await asyncio.to_thread(
                self._sqlite.set_kv, "intel.feodo.last_sync",
                datetime.now(timezone.utc).isoformat()
            )
            return True
        except Exception as exc:
            log.warning("FeodoWorker sync failed", error=str(exc))
            return False
```

### Pattern 2: SQLite Write (asyncio.to_thread wrapper)

All SQLite writes follow the same pattern as `set_osint_cache` in `sqlite_store.py` lines 1619-1632:

```python
# In ioc_store.py (standalone module, not inside SQLiteStore)
def upsert_ioc(conn, ioc_value: str, ioc_type: str, ...) -> bool:
    """Returns True if this was a NEW ioc_value (not an update). Runs in thread."""
    existing = conn.execute(
        "SELECT ioc_id FROM ioc_store WHERE ioc_value = ? AND ioc_type = ?",
        (ioc_value, ioc_type)
    ).fetchone()
    is_new = existing is None
    conn.execute(
        "INSERT OR REPLACE INTO ioc_store (...) VALUES (...)",
        (...)
    )
    conn.commit()
    return is_new
```

Callers use: `await asyncio.to_thread(upsert_ioc, conn, ioc_value, ...)`

### Pattern 3: DuckDB Column Migration

From `duckdb_store.py` lines 218-246, `_ECS_MIGRATION_COLUMNS`. Three new entries to append:

```python
# Append to _ECS_MIGRATION_COLUMNS list in duckdb_store.py:
    # Phase 33: IOC matching columns
    ("ioc_matched",     "BOOLEAN"),
    ("ioc_confidence",  "INTEGER"),
    ("ioc_actor_tag",   "TEXT"),
```

DuckDB does NOT support `ADD COLUMN IF NOT EXISTS` — idempotency is via `try/except` in `initialise_schema()`. The existing loop at lines 312-319 handles all entries in `_ECS_MIGRATION_COLUMNS` automatically; just append the 3 new tuples.

The `DEFAULT FALSE` for `ioc_matched` cannot be set in the migration ALTER TABLE — DuckDB ignores DEFAULT in ALTER. Add it to `_CREATE_EVENTS_TABLE` DDL string as a permanent column so new installs get the default, but existing installs get the column via migration (will be NULL until an event is matched).

### Pattern 4: At-Ingest IOC Matching Hook

**Exact location:** `ingestion/loader.py`, method `ingest_events()`, lines 329-361.

**Hook point:** After `events = [normalize_event(e) for e in events]` (line 329) and BEFORE `new_events = await self._deduplicate(events)` (line 331).

```python
# In IngestionLoader.ingest_events(), after normalize, before deduplicate:
events = await self._apply_ioc_matching(events)
```

The `_apply_ioc_matching` method calls `check_ioc_match(ip)` for each event's `src_ip` and `dst_ip`:

```python
async def _apply_ioc_matching(
    self, events: list[NormalizedEvent]
) -> list[NormalizedEvent]:
    """Check each event's IPs against ioc_store. Tag matches in-place."""
    from backend.services.intel.ioc_store import check_ioc_match
    for event in events:
        matched, confidence, actor_tag = False, None, None
        for ip in [event.src_ip, event.dst_ip]:
            if ip:
                result = await asyncio.to_thread(
                    check_ioc_match, self._stores.sqlite._conn, ip
                )
                if result:
                    matched = True
                    confidence = result["confidence"]
                    actor_tag = result["actor_tag"]
                    break
        if matched:
            event.ioc_matched = True
            event.ioc_confidence = confidence
            event.ioc_actor_tag = actor_tag
    return events
```

**Why loader.py not malcolm_collector.py:** `IngestionLoader.ingest_events()` is the single convergence point for ALL event sources (Malcolm, Firewall, osquery, file uploads). Hooking here means every source gets IOC matching without per-collector changes.

### Pattern 5: Retroactive Scan

Runs as an asyncio background task spawned after each feed sync:

```python
async def _retroactive_scan(self, ioc_values: list[str], duckdb_store) -> None:
    """For new IOCs, find matching events in last 30 days and tag them."""
    for ioc_value in ioc_values:
        sql = """
            UPDATE normalized_events
            SET ioc_matched = TRUE,
                ioc_confidence = ?,
                ioc_actor_tag = ?
            WHERE timestamp >= NOW() - INTERVAL 30 DAYS
            AND (src_ip = ? OR dst_ip = ?)
            AND (ioc_matched IS NULL OR ioc_matched = FALSE)
        """
        await duckdb_store.execute_write(sql, [confidence, actor_tag, ioc_value, ioc_value])
```

**Batch size:** Process up to 500 new IOCs per sync; beyond that, limit retroactive scan to avoid blocking the write queue. Log a warning if truncated.

**DuckDB INTERVAL syntax:** `NOW() - INTERVAL 30 DAYS` is valid DuckDB SQL — confirmed from DuckDB documentation patterns.

### Pattern 6: lifespan Registration in main.py

Follows the `asyncio.ensure_future` pattern used for MalcolmCollector (lines 297-309):

```python
# In lifespan(), after MalcolmCollector block:
# 8d. Threat intelligence feed workers (Phase 33)
intel_tasks: list[asyncio.Task] = []
try:
    from backend.services.intel.feed_sync import FeodoWorker, CisaKevWorker, ThreatFoxWorker
    _feodo = FeodoWorker(sqlite_store=sqlite_store, interval_sec=3600)
    _cisa = CisaKevWorker(sqlite_store=sqlite_store, duckdb_store=duckdb_store, interval_sec=3600)
    _threatfox = ThreatFoxWorker(sqlite_store=sqlite_store, interval_sec=3600)
    intel_tasks = [
        asyncio.ensure_future(_feodo.run()),
        asyncio.ensure_future(_cisa.run()),
        asyncio.ensure_future(_threatfox.run()),
    ]
    app.state.intel_workers = (_feodo, _cisa, _threatfox)
    log.info("Threat intel feed workers started")
except ImportError as exc:
    log.warning("Intel feed workers not available: %s", exc)
    app.state.intel_workers = None
```

Add cancellation in shutdown block (same as osquery/firewall/malcolm tasks).

### Pattern 7: Intel Router Registration

Use the deferred-router pattern (try/except ImportError) already established in main.py lines 457-625:

```python
try:
    from backend.api.intel import router as intel_router
    app.include_router(intel_router, prefix="/api", dependencies=[Depends(verify_token)])
    log.info("Intel router mounted at /api/intel")
except ImportError as exc:
    log.warning("Intel router not available: %s", exc)
```

---

## SQLite ioc_store DDL

Modeled on `osint_cache` DDL in `sqlite_store.py` lines 281-286. Added to `_DDL` string in SQLiteStore:

```sql
CREATE TABLE IF NOT EXISTS ioc_store (
    ioc_id          TEXT PRIMARY KEY,          -- uuid4
    ioc_value       TEXT NOT NULL,             -- the indicator value
    ioc_type        TEXT NOT NULL,             -- "ip", "cve", "domain", "hash", "ip_port"
    feed_source     TEXT NOT NULL,             -- "feodo", "cisa_kev", "threatfox"
    confidence      INTEGER NOT NULL DEFAULT 50,
    status          TEXT NOT NULL DEFAULT 'active',  -- "active", "expired"
    malware_family  TEXT,
    actor_tag       TEXT,
    tlp             TEXT DEFAULT 'white',
    first_seen      TEXT NOT NULL,
    last_seen       TEXT,
    extra_json      TEXT,                      -- feed-specific fields as JSON blob
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_ioc_store_value_type
    ON ioc_store (ioc_value, ioc_type);

CREATE INDEX IF NOT EXISTS idx_ioc_store_value
    ON ioc_store (ioc_value);

CREATE INDEX IF NOT EXISTS idx_ioc_store_status
    ON ioc_store (status);

CREATE INDEX IF NOT EXISTS idx_ioc_store_feed
    ON ioc_store (feed_source);

CREATE TABLE IF NOT EXISTS ioc_hits (
    hit_id          TEXT PRIMARY KEY,          -- uuid4
    event_id        TEXT NOT NULL,             -- FK to normalized_events.event_id
    ioc_id          TEXT NOT NULL,             -- FK to ioc_store.ioc_id
    ioc_value       TEXT NOT NULL,             -- denormalized for fast retrieval
    matched_field   TEXT NOT NULL,             -- "src_ip" or "dst_ip"
    risk_score      INTEGER NOT NULL DEFAULT 0,
    actor_tag       TEXT,
    malware_family  TEXT,
    feed_source     TEXT NOT NULL,
    matched_at      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_ioc_hits_event
    ON ioc_hits (event_id);

CREATE INDEX IF NOT EXISTS idx_ioc_hits_score
    ON ioc_hits (risk_score DESC);

CREATE INDEX IF NOT EXISTS idx_ioc_hits_matched_at
    ON ioc_hits (matched_at DESC);
```

**DDL placement:** Add to `_DDL` constant string in `sqlite_store.py`, after `osint_cache` table (line ~286). The `executescript()` call at line 322 applies all `_DDL` idempotently on every startup.

**Migration for existing installs:** Because tables use `CREATE TABLE IF NOT EXISTS`, adding the new tables to `_DDL` is safe for existing databases.

---

## NormalizedEvent Model Update

Three new optional fields added to `backend/models/event.py`:

```python
# In NormalizedEvent (Pydantic BaseModel)
ioc_matched:    Optional[bool]  = Field(None)
ioc_confidence: Optional[int]   = Field(None)
ioc_actor_tag:  Optional[str]   = Field(None)
```

The `to_duckdb_row()` method must include these three fields (they map to the new DuckDB columns). The `_INSERT_SQL` in `loader.py` must include these three column names and `?` placeholders.

---

## API Endpoints

### GET /api/intel/ioc-hits

Returns paginated list of IOC hit records for ThreatIntelView hit list.

```
GET /api/intel/ioc-hits?page=1&page_size=50&min_score=0
```

Response shape:
```json
{
  "hits": [
    {
      "hit_id": "...",
      "event_id": "...",
      "timestamp": "2026-04-09T10:00:00Z",
      "hostname": "sensor-01",
      "src_ip": "1.2.3.4",
      "dst_ip": "5.6.7.8",
      "event_type": "alert",
      "risk_score": 75,
      "actor_tag": "Emotet",
      "malware_family": "Emotet",
      "feed_source": "feodo",
      "ioc_value": "1.2.3.4",
      "matched_field": "src_ip",
      "matched_at": "2026-04-09T10:00:00Z"
    }
  ],
  "total": 42,
  "page": 1,
  "page_size": 50,
  "has_next": false
}
```

Implementation: Query `ioc_hits` SQLite table joined with event metadata (or DuckDB query for event timestamp/hostname). Sorted by `risk_score DESC, matched_at DESC`.

**Decision (Claude's discretion):** Query `ioc_hits` from SQLite for hit metadata, then batch-fetch event details from DuckDB by `event_id`. This avoids cross-store JOIN complexity.

### GET /api/intel/feeds

Returns feed health for ThreatIntelView header strip.

```
GET /api/intel/feeds
```

Response shape:
```json
{
  "feeds": [
    {
      "name": "Feodo Tracker",
      "feed_id": "feodo",
      "last_sync": "2026-04-09T09:00:00Z",
      "ioc_count": 287,
      "status": "ok"   // "ok" | "stale" | "error"
    }
  ]
}
```

Status logic:
- `ok` — last_sync within 2 hours
- `stale` — last_sync between 2 and 25 hours
- `error` — last_sync > 25 hours or never synced

Implementation: Read `intel.*.last_sync` keys from SQLite `system_kv`, count active IOCs per feed from `ioc_store`.

### Expanded Row Data (GET /api/intel/ioc-hits/{hit_id})

Optional endpoint for inline expansion details. Returns full IOC record + event record:

```json
{
  "hit": { ...hit fields... },
  "ioc": {
    "feed_source": "feodo",
    "actor_tag": null,
    "malware_family": "QakBot",
    "tlp": "white",
    "first_seen": "2026-01-10T00:00:00Z",
    "last_seen": "2026-04-08T00:00:00Z",
    "confidence": 50,
    "extra_json": { "dst_port": 443, "c2_status": "online" }
  },
  "event": {
    "timestamp": "2026-04-09T10:00:00Z",
    "hostname": "sensor-01",
    "src_ip": "1.2.3.4",
    "dst_ip": "185.244.31.12",
    "event_type": "alert"
  }
}
```

**Decision (Claude's discretion):** Implement expansion data inline in the list response (include `ioc` and `event` objects in each hit row). This eliminates the need for a per-hit detail endpoint and reduces API round trips on row click.

---

## ThreatIntelView Svelte Component

### Current State
Full stub — 137 lines, placeholder feed cards for 4 wrong feeds, no data fetching.

### Rewrite Strategy
- Keep file `dashboard/src/views/ThreatIntelView.svelte`
- Keep `.feed-card` CSS classes (reuse for compact header strip)
- Delete all stub content inside `<script>` and template

### State Variables (Svelte 5 runes)
```typescript
let hits = $state<IocHit[]>([])
let feeds = $state<FeedHealth[]>([])
let loading = $state(true)
let errorMsg = $state<string | null>(null)
let expandedHitId = $state<string | null>(null)
```

### expandRow Pattern (from HuntingView lines 85-111)

```typescript
// ThreatIntelView uses hit_id as expansion key (not src_ip like HuntingView)
function expandRow(hit_id: string) {
  if (expandedHitId === hit_id) {
    expandedHitId = null   // collapse if already open
  } else {
    expandedHitId = hit_id
  }
}
```

No async fetch on click — all IOC expansion data is embedded in the hit response from GET /api/intel/ioc-hits (per the "inline expansion data" decision above).

### Component Layout (single-scroll, no tabs)
```
[view-header]  "Threat Intelligence"  [ACTIVE badge]

[feed-strip]   Feodo: ok 287 IOCs | CISA KEV: ok 1147 IOCs | ThreatFox: ok 5823 IOCs

[empty-state OR hit-list]
  [table header: Time | Host | Src IP | Dst IP | Score | Actor | Feed]
  [table rows — click to expand]
  [expanded row: IOC panel (feed, malware, TLP, first/last seen, confidence) + event panel]
```

### Risk Score Badge CSS
Reuse existing `sev-badge` CSS pattern from HuntingView (confirmed same project):
```css
/* Add to ThreatIntelView <style> */
.score-badge { font-size: 10px; font-weight: 700; padding: 2px 6px; border-radius: 4px; }
.score-critical { background: rgba(239,68,68,0.15); color: #ef4444; }    /* >=75 */
.score-high     { background: rgba(249,115,22,0.15); color: #f97316; }   /* 50-74 */
.score-medium   { background: rgba(234,179,8,0.15);  color: #eab308; }   /* 25-49 */
.score-low      { background: rgba(148,163,184,0.1); color: var(--text-muted); }  /* <25 */
```

Helper function:
```typescript
function scoreClass(score: number): string {
  if (score >= 75) return 'score-critical'
  if (score >= 50) return 'score-high'
  if (score >= 25) return 'score-medium'
  return 'score-low'
}
```

### api.ts Additions
```typescript
export interface IocHit {
  hit_id: string
  event_id: string
  timestamp: string
  hostname: string | null
  src_ip: string | null
  dst_ip: string | null
  event_type: string | null
  risk_score: number
  actor_tag: string | null
  malware_family: string | null
  feed_source: string
  ioc_value: string
  matched_field: string
  matched_at: string
  // Inline expansion data
  ioc?: IocRecord
  event?: EventSummary
}

export interface FeedHealth {
  name: string
  feed_id: string
  last_sync: string | null
  ioc_count: number
  status: 'ok' | 'stale' | 'error'
}

// Add to api object:
intel: {
  listHits: (page?: number, pageSize?: number) =>
    fetchAuthenticated<{ hits: IocHit[], total: number, page: number, has_next: boolean }>(
      `/api/intel/ioc-hits?page=${page ?? 1}&page_size=${pageSize ?? 50}`
    ),
  feeds: () => fetchAuthenticated<{ feeds: FeedHealth[] }>('/api/intel/feeds'),
}
```

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead |
|---------|-------------|-------------|
| HTTP fetches with TLS | Custom urllib | `httpx` (already a dep) |
| Background task scheduling | Custom thread timer | `asyncio.ensure_future` + sleep loop (established pattern) |
| Midnight decay job scheduling | Custom cron | `apscheduler.AsyncIOScheduler` (already in main.py) |
| CSV parsing | Manual string splitting | `csv.DictReader` (stdlib) |
| SQLite upsert | Manual SELECT+INSERT | `INSERT OR REPLACE` with UNIQUE INDEX |
| Feed deduplication | In-memory set tracking | UNIQUE INDEX on `(ioc_value, ioc_type)` |

---

## Common Pitfalls

### Pitfall 1: Feodo URL Change
**What goes wrong:** The "recommended" URL (`/ipblocklist_recommended.csv`) returns 404.
**Prevention:** Use `/downloads/ipblocklist.csv` (the base blocklist). The column name for the IOC IP is `dst_ip`, not `ip` or `ip_address`.
**Warning sign:** httpx 404 on first sync attempt.

### Pitfall 2: ThreatFox REST API Now Requires Auth Key
**What goes wrong:** POST to `https://threatfox-api.abuse.ch/api/v1/` with `{"query":"get_iocs","days":1}` returns an auth error since ~2025.
**Prevention:** Use the no-auth CSV export at `https://threatfox.abuse.ch/export/csv/ip-port/recent/` instead. Maintains zero-key constraint.
**Warning sign:** 403 or `{"query_status": "no_auth"}` response.

### Pitfall 3: DuckDB ADD COLUMN IF NOT EXISTS Not Supported
**What goes wrong:** Trying `ALTER TABLE normalized_events ADD COLUMN IF NOT EXISTS ioc_matched BOOLEAN` fails — DuckDB doesn't support the `IF NOT EXISTS` clause for ALTER.
**Prevention:** Wrap each `execute_write(f"ALTER TABLE ... ADD COLUMN {col}")` in try/except (already the pattern in `_ECS_MIGRATION_COLUMNS` loop). Don't add `IF NOT EXISTS`.

### Pitfall 4: SQLite from Async Context Without to_thread
**What goes wrong:** Calling `sqlite_store.upsert_ioc()` directly in an async function blocks the event loop for potentially hundreds of ms during bulk IOC upserts.
**Prevention:** All SQLite writes use `await asyncio.to_thread(func, args)`. Feed workers that call upsert_ioc in a loop must still wrap each call.

### Pitfall 5: ThreatFox CSV ip_port Format Requires IP Extraction
**What goes wrong:** `ioc_value` in ThreatFox CSV is `"145.239.200.154:4000"`. Directly comparing to `src_ip`/`dst_ip` (which are bare IPs) never matches.
**Prevention:** For ip-port IOCs, extract the IP part: `lookup_ip = ioc_value.split(":")[0]`. Store the full `ip:port` as `ioc_value` but index and search on the bare IP.

### Pitfall 6: CISA KEV Sync is Idempotent by Design
**What goes wrong:** CISA KEV returns the full catalog every sync (~1100 entries). Naively inserting all on every sync causes spurious "new IOC" retroactive scans.
**Prevention:** `upsert_ioc()` must return a boolean indicating whether the row was genuinely new (not just updated). Only trigger retroactive scan for IOCs where `is_new = True`.

### Pitfall 7: ioc_hits Table as Source of Truth for ThreatIntelView
**What goes wrong:** Querying `normalized_events WHERE ioc_matched = TRUE` from DuckDB on every page load is slow at scale.
**Prevention:** The `ioc_hits` SQLite table is the authoritative fast-query source for ThreatIntelView. DuckDB's `ioc_matched` flag is the audit trail. GET /api/intel/ioc-hits queries SQLite `ioc_hits` only.

### Pitfall 8: Retroactive Scan Blocking Write Queue
**What goes wrong:** A large feed sync (ThreatFox has thousands of IOCs) triggers hundreds of DuckDB UPDATE statements sequentially, backing up the write queue for minutes.
**Prevention:** Cap retroactive scan at 500 new IOCs per sync. Log a warning if the batch is truncated. The UPDATE itself should use `WHERE src_ip IN (...)` or `WHERE dst_ip IN (...)` with batched lists to reduce round trips.

---

## Plan Breakdown Recommendation

### Suggested Wave Grouping

**Wave 1 — Data Layer (backend only, no UI impact)**

**Plan 33-01: SQLite ioc_store + NormalizedEvent model**
- Add ioc_store + ioc_hits DDL to `sqlite_store.py` `_DDL`
- Add `ioc_matched`, `ioc_confidence`, `ioc_actor_tag` fields to `NormalizedEvent` model
- Add 3 columns to `_ECS_MIGRATION_COLUMNS` in `duckdb_store.py`
- Update `_INSERT_SQL` and `to_duckdb_row()` in `loader.py`
- Add `upsert_ioc()`, `get_ioc()`, `check_ioc_match()`, `record_hit()`, `list_hits()` to `backend/services/intel/ioc_store.py`
- Tests: `tests/unit/test_ioc_store.py` (`:memory:` SQLite)

**Plan 33-02: Feed workers + at-ingest IOC matching**
- Create `backend/services/intel/feed_sync.py` (FeodoWorker, CisaKevWorker, ThreatFoxWorker)
- Hook `_apply_ioc_matching()` into `IngestionLoader.ingest_events()` in `loader.py`
- Register 3 feed tasks + decay job in `main.py` lifespan
- Tests: `tests/unit/test_intel_feeds.py` (mock httpx responses for all 3 feeds)
- Tests: `tests/unit/test_ioc_matching.py` (seed ioc_store, run ingest_events, verify ioc_matched flag)

**Wave 2 — API + UI**

**Plan 33-03: Intel API + ThreatIntelView rewrite**
- Create `backend/api/intel.py` (GET /api/intel/ioc-hits, GET /api/intel/feeds)
- Register intel router in `main.py` deferred block
- Add `IocHit`, `FeedHealth` interfaces to `api.ts`
- Rewrite `ThreatIntelView.svelte` (feed strip, hit list, inline expansion, risk badges)
- Tests: `tests/unit/test_api_intel.py` (mock ioc_store, verify endpoint shapes)

**Total: 3 plans, 2 waves**

This grouping ensures Wave 1 is fully testable without UI, and Wave 2 has stable data contracts to build against.

---

## Validation Architecture

> `workflow.nyquist_validation = true` in `.planning/config.json` — section required.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x + pytest-asyncio (auto mode set in pyproject.toml) |
| Config file | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| Quick run command | `uv run pytest tests/unit/test_intel_feeds.py tests/unit/test_ioc_store.py -x` |
| Full suite command | `uv run pytest tests/unit/ -x` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| P33-T01 | FeodoWorker._fetch_csv parses 6-column CSV, extracts dst_ip as ioc_value | unit | `uv run pytest tests/unit/test_intel_feeds.py::test_feodo_csv_parse -x` | Wave 0 |
| P33-T01 | FeodoWorker._sync returns True on success, updates cursor key | unit | `uv run pytest tests/unit/test_intel_feeds.py::test_feodo_sync_success -x` | Wave 0 |
| P33-T02 | CisaKevWorker parses CISA KEV JSON, extracts cveID as ioc_value | unit | `uv run pytest tests/unit/test_intel_feeds.py::test_cisa_kev_parse -x` | Wave 0 |
| P33-T03 | ThreatFoxWorker parses CSV export, extracts IP from ip:port ioc_value | unit | `uv run pytest tests/unit/test_intel_feeds.py::test_threatfox_csv_parse -x` | Wave 0 |
| P33-T04 | upsert_ioc returns True for new IOC, False for duplicate | unit | `uv run pytest tests/unit/test_ioc_store.py::test_upsert_ioc_new -x` | Wave 0 |
| P33-T04 | check_ioc_match returns dict with confidence/actor_tag for known IP | unit | `uv run pytest tests/unit/test_ioc_store.py::test_check_ioc_match_hit -x` | Wave 0 |
| P33-T04 | check_ioc_match returns None for unknown IP | unit | `uv run pytest tests/unit/test_ioc_store.py::test_check_ioc_match_miss -x` | Wave 0 |
| P33-T05 | DuckDB migration adds ioc_matched, ioc_confidence, ioc_actor_tag columns | unit | `uv run pytest tests/unit/test_duckdb_migration.py -x -k ioc` | Wave 0 (extend existing) |
| P33-T06 | ingest_events sets ioc_matched=True when event.src_ip matches ioc_store | unit | `uv run pytest tests/unit/test_ioc_matching.py::test_at_ingest_match -x` | Wave 0 |
| P33-T06 | ingest_events leaves ioc_matched=None when no match | unit | `uv run pytest tests/unit/test_ioc_matching.py::test_at_ingest_no_match -x` | Wave 0 |
| P33-T07 | Retroactive scan updates ioc_matched for events in last 30 days | unit | `uv run pytest tests/unit/test_ioc_matching.py::test_retroactive_scan -x` | Wave 0 |
| P33-T08 | Decay job reduces confidence by 5 per week, floors at 0 | unit | `uv run pytest tests/unit/test_ioc_store.py::test_confidence_decay -x` | Wave 0 |
| P33-T09 | GET /api/intel/ioc-hits returns expected shape with risk_score desc sort | unit | `uv run pytest tests/unit/test_api_intel.py::test_ioc_hits_endpoint -x` | Wave 0 |
| P33-T09 | GET /api/intel/feeds returns 3 feeds with status ok/stale/error | unit | `uv run pytest tests/unit/test_api_intel.py::test_feeds_endpoint -x` | Wave 0 |
| P33-T10 | ThreatIntelView renders feed strip + empty state (no hits) | manual | open /app in browser | N/A |
| P33-T10 | ThreatIntelView hit list sorts by risk_score desc | manual | open /app in browser | N/A |
| P33-T14 | NormalizedEvent has ioc_matched, ioc_confidence, ioc_actor_tag fields | unit | `uv run pytest tests/unit/test_ioc_matching.py::test_normalized_event_fields -x` | Wave 0 |
| P33-T15 | Feed tasks registered in lifespan, cancelled on shutdown | unit | Tested indirectly via feed worker unit tests | Wave 0 |
| P33-T16 | GET /api/intel/* returns 401 without auth token | unit | `uv run pytest tests/unit/test_api_intel.py::test_intel_requires_auth -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/unit/ -x -q` (full unit suite, ~30s)
- **Per wave merge:** `uv run pytest tests/unit/ tests/integration/ -x` (if integration tests available)
- **Phase gate:** Full unit suite green before `/gsd:verify-work`

### Wave 0 Gaps (files to create before implementation)

- [ ] `tests/unit/test_intel_feeds.py` — covers P33-T01, P33-T02, P33-T03 (mock httpx with `respx` or `unittest.mock.patch`)
- [ ] `tests/unit/test_ioc_store.py` — covers P33-T04, P33-T08 (`:memory:` SQLite)
- [ ] `tests/unit/test_ioc_matching.py` — covers P33-T06, P33-T07, P33-T14 (seed ioc_store, run loader)
- [ ] `tests/unit/test_api_intel.py` — covers P33-T09, P33-T16 (mock SQLite, test FastAPI TestClient)

**Existing test file to extend:**
- [ ] `tests/unit/test_duckdb_migration.py` — add test case for ioc_matched/ioc_confidence/ioc_actor_tag columns (P33-T05)

**Mock strategy for feed workers:** Use `unittest.mock.patch` on `httpx.get` (or `respx` if available) to return fixture CSV/JSON strings. Tests should not make real network calls.

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| ThreatFox REST API (no key) | ThreatFox REST API requires free Auth-Key | ~2025-05 | Use CSV export instead |
| ThreatFox REST API | ThreatFox CSV export at `/export/csv/ip-port/recent/` | Now | No key, same data, direct HTTP GET |
| Feodo `/ipblocklist_recommended.csv` | Feodo `/ipblocklist.csv` | Current | Recommended URL is 404 |
| IOC matching as separate step | Inline hook in IngestionLoader | Phase 33 | Single convergence point covers all sources |

**Deprecated/outdated:**
- ThreatFox REST API `{"query":"get_iocs","days":N}` — now requires Auth-Key. Replace with CSV export.
- CONTEXT.md stub feeds (MISP, OTX, URLhaus, Emerging Threats) — all out of scope for Phase 33.

---

## Open Questions

1. **ThreatFox CSV freshness for recent/ endpoint**
   - What we know: URL `https://threatfox.abuse.ch/export/csv/ip-port/recent/` is accessible and returns current data
   - What's unclear: Exact update frequency of the `recent/` export (likely every few hours based on feed description)
   - Recommendation: Fetch hourly and deduplicate via UNIQUE INDEX; any extra fetches are no-ops

2. **ioc_hits table + DuckDB ioc_matched flag — dual write coordination**
   - What we know: At-ingest matching needs to write both the DuckDB event row (with ioc_matched=True) and an ioc_hits SQLite row
   - What's unclear: If DuckDB INSERT fails after ioc_hits write, there's a brief inconsistency
   - Recommendation: Write DuckDB first (existing flow), write ioc_hits in `_apply_ioc_matching` return path only for events that ultimately get stored. Keep inconsistency risk low by inserting ioc_hits in a post-insert step after `_batch_insert_duckdb` confirms success.

3. **ThreatFox CSV domain and URL exports — Phase 33 scope**
   - What we know: Only `ip-port` export is in scope per decisions; domain matching would require checking `domain` field in NormalizedEvent
   - What's unclear: Whether matching domain IOCs against Suricata DNS query events is expected
   - Recommendation: Scope Phase 33 to IP-only matching (Feodo and ThreatFox ip-port). Domain IOC matching is Phase 34.

---

## Sources

### Primary (HIGH confidence)
- Live fetch: `https://feodotracker.abuse.ch/downloads/ipblocklist.csv` — 6-column CSV format verified
- Live fetch: `https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json` — 11-field JSON schema verified
- Live fetch: `https://threatfox.abuse.ch/export/csv/ip-port/recent/` — 15-column CSV, no auth required, verified
- Project codebase: `backend/stores/sqlite_store.py` lines 281-287 — osint_cache DDL pattern
- Project codebase: `backend/stores/sqlite_store.py` lines 1599-1641 — get/set_osint_cache pattern
- Project codebase: `backend/stores/duckdb_store.py` lines 218-246 — _ECS_MIGRATION_COLUMNS pattern
- Project codebase: `ingestion/jobs/malcolm_collector.py` lines 738-754 — run() asyncio loop pattern
- Project codebase: `ingestion/loader.py` lines 305-361 — ingest_events() hook point
- Project codebase: `dashboard/src/views/HuntingView.svelte` lines 85-111 — expandRow pattern
- Project codebase: `backend/main.py` lines 297-309, 457-625 — lifespan task registration + deferred router pattern

### Secondary (MEDIUM confidence)
- [ThreatFox Community API](https://threatfox.abuse.ch/api/) — API documentation (confirmed Auth-Key now required for REST endpoint)
- WebSearch results confirming ThreatFox Auth-Key requirement since 2025

### Tertiary (LOW confidence)
- None

---

## Metadata

**Confidence breakdown:**
- Feed formats: HIGH — all 3 feeds verified by direct fetch
- SQLite DDL: HIGH — modeled directly from existing osint_cache pattern in codebase
- DuckDB migration: HIGH — exact pattern confirmed from _ECS_MIGRATION_COLUMNS
- Ingest hook location: HIGH — loader.py ingest_events() flow traced completely
- asyncio task pattern: HIGH — MalcolmCollector.run() is the exact template
- ThreatIntelView UI: HIGH — HuntingView expandRow pattern is confirmed and directly replicable
- ThreatFox no-auth CSV: HIGH — verified by live fetch returning data

**Research date:** 2026-04-09
**Valid until:** 2026-05-09 (30 days — feeds are stable; ThreatFox URL change is the main risk)
