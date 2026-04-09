# Phase 31: Malcolm Real Telemetry + Evidence Archive — Research

**Researched:** 2026-04-08
**Domain:** Suricata EVE JSON normalizers, DuckDB schema migration, Ubuntu evidence archiver, FastAPI NDJSON server, Svelte 5 filter chips
**Confidence:** HIGH (core patterns from codebase) / MEDIUM (Suricata field paths in Malcolm OpenSearch)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Expand `_poll_and_ingest()` in `ingestion/jobs/malcolm_collector.py` to poll all 5 EVE types from `arkime_sessions3-*` (alert already done; add tls, dns, fileinfo, anomaly)
- Each EVE type gets its own `_normalize_<type>()` method mirroring `_normalize_alert()` pattern
- Each EVE type gets its own SQLite cursor key (e.g., `malcolm.tls.last_timestamp`)
- `event_type` field values: `"tls"`, `"dns_query"`, `"file_transfer"`, `"anomaly"`
- NormalizedEvent: ~20 new fields added via `_ECS_MIGRATION_COLUMNS` try/except pattern
- Evidence archive: daily gzip per log type, `{YYYY-MM-DD}.log.gz` / `{YYYY-MM-DD}.json.gz`
- Archive root: `EVIDENCE_ARCHIVE_PATH` env var (default `/mnt/evidence`)
- SHA256 at write time, stored in `checksums/{YYYY-MM-DD}.sha256`
- Ubuntu normalization pipeline: tails live syslog + EVE → ECS NDJSON → HTTP endpoint
- Desktop polls `GET /normalized/latest` every 60s using SQLite cursor tracking
- EventsView filter chips: All | Alert | TLS | DNS | File | Anomaly | Syslog (single-select)
- httpx + verify=False (locked from Phase 27)
- SQLite cursor-per-index pattern (locked from Phase 27)
- Svelte 5 runes: `$state()`, `$derived()`, `$effect()` — NOT stores
- DuckDB: ALL writes via `store.execute_write(sql, params)`
- NO AI on Ubuntu — pure format conversion only

### Claude's Discretion
- Exact FastAPI route structure for Ubuntu normalization HTTP server
- Whether to run EvidenceArchiver as asyncio task within the same process or separate systemd unit
- NDJSON batch size and flush interval for the Ubuntu endpoint
- How to handle gaps in EVE SCP delivery (skip silently vs backfill)

### Deferred Ideas (OUT OF SCOPE)
- Zeek full telemetry (Phase 36) — requires managed switch with SPAN port
- Remove theater containers from Ubuntu (17 idle Malcolm containers + Ollama) — infrastructure cleanup task
- Bidirectional archive sync (replicating Ubuntu evidence archive to desktop)
- Malcolm WebSocket real-time feed (replace polling with push)
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| P31-T01 | Add `_normalize_tls()` to MalcolmCollector | Suricata EVE TLS field paths documented; pattern from `_normalize_alert()` |
| P31-T02 | Add `_normalize_dns()` to MalcolmCollector | Suricata EVE DNS field paths documented; dns.queries[0].rrname pattern |
| P31-T03 | Add `_normalize_fileinfo()` to MalcolmCollector | Suricata EVE fileinfo field paths documented; fileinfo.filename/md5/sha256 |
| P31-T04 | Add `_normalize_anomaly()` to MalcolmCollector | Suricata EVE anomaly.type / anomaly.event field paths documented |
| P31-T05 | Expand `_poll_and_ingest()` with 4 new EVE type poll loops | Pattern identical to existing alert/syslog poll loops; 4 new cursor keys |
| P31-T06 | Add ~20 new columns to NormalizedEvent + DuckDB migration | `_ECS_MIGRATION_COLUMNS` list extension; try/except ADD COLUMN pattern confirmed |
| P31-T07 | `EvidenceArchiver` class on Ubuntu — daily gzip + SHA256 | Python gzip + hashlib pattern; write-once append-only design documented |
| P31-T08 | Ubuntu normalization HTTP server (FastAPI) | FastAPI FileResponse / StreamingResponse for gzip NDJSON; route structure recommended |
| P31-T09 | Desktop polls Ubuntu `GET /normalized/latest` every 60s | httpx + SQLite cursor tracking pattern; identical to OpenSearch poll pattern |
| P31-T10 | EventsView filter chips (Svelte 5) | `$state()` single-select chip pattern; `$effect()` triggers re-fetch on change |
| P31-T11 | `GET /api/events?event_type=` exact-match filter | Already implemented as ILIKE in events.py; change to exact match for chip use case |
</phase_requirements>

---

## Summary

Phase 31 has three completely independent workstreams that can be planned and executed in parallel:

**Workstream A — Malcolm EVE expansion (desktop side):** The existing `MalcolmCollector._normalize_alert()` and `_normalize_syslog()` are clean templates. Adding 4 new normalizers is additive and low-risk. The DuckDB migration follows the identical `_ECS_MIGRATION_COLUMNS` try/except pattern already proven in Phase 20. The only research uncertainty is exact field paths in Malcolm's OpenSearch index (Malcolm may prefix fields differently from raw Suricata EVE). The safe strategy is to probe multiple paths with `or` fallbacks, exactly as `_normalize_alert()` does for src_ip/dst_ip.

**Workstream B — Ubuntu pipeline (new Python service):** Two components run on the N150: `EvidenceArchiver` (write-once gzip + SHA256) and a normalization HTTP server. Both are new Python files that run on Ubuntu and have no dependency on the desktop codebase. The archiver is simpler than it sounds: Python's `gzip.open()` + `hashlib.sha256()` + daily rotation via UTC midnight check. The HTTP server is a 2-route FastAPI app returning either a pre-compressed gzip file (FileResponse with correct Content-Type) or streaming from the live partial file.

**Workstream C — EventsView chip UI (dashboard side):** The existing `GET /api/events?event_type=` query parameter is already implemented in `backend/api/events.py` (line 65, 99: ILIKE match). Adding chip state in Svelte 5 requires only `$state<string>('all')` and `$effect()` that re-calls `api.events.list()` with the selected type. The `api.ts` `events.list()` function needs one new optional `event_type` parameter.

**Primary recommendation:** Plan as 3 parallel workstreams. Workstream A (EVE normalizers + schema) is the highest-value deliverable (235K ignored events). Workstream B (Ubuntu pipeline) is independent infrastructure. Workstream C (chip UI) is a small UI addition on top of an already-working filter parameter.

---

## Standard Stack

### Core (confirmed from codebase)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| httpx | pinned in pyproject.toml | OpenSearch + Ubuntu HTTP polling | Already project dependency; verify=False locked by Phase 27 |
| fastapi | pinned | Both desktop backend AND Ubuntu normalization server | Already used; same pattern both sides |
| pydantic-settings | pinned | Settings for new Ubuntu env vars | Same `BaseSettings` pattern as `backend/core/config.py` |
| gzip (stdlib) | 3.x stdlib | Evidence archive write + decompression | No dependency required; `gzip.open(path, 'wb')` |
| hashlib (stdlib) | 3.x stdlib | SHA256 chain of custody | `hashlib.sha256()` + `h.update(chunk)` pattern |
| duckdb | pinned | Schema migration for 20 new columns | `ALTER TABLE ... ADD COLUMN` in try/except |
| uvicorn | pinned | Ubuntu normalization server runtime | Same as desktop |

### New Fields — NormalizedEvent

Based on CONTEXT.md decisions + Suricata EVE schema (MEDIUM confidence — field names may vary in Malcolm):

**DNS fields** (event_type="dns_query", OCSF 4003):
```
dns_query       TEXT   — dns.queries[0].rrname (hostname queried)
dns_query_type  TEXT   — dns.queries[0].rrtype (A, AAAA, MX, etc.)
dns_rcode       TEXT   — dns.rcode (NOERROR, NXDOMAIN, etc.)
dns_answers     TEXT   — JSON-serialized dns.answers list
dns_ttl         INTEGER — dns.answers[0].ttl (first answer TTL)
```

**TLS fields** (event_type="tls", OCSF 4001):
```
tls_version          TEXT — tls.version (TLS 1.2, TLS 1.3, etc.)
tls_ja3              TEXT — tls.ja3.hash (client fingerprint)
tls_ja3s             TEXT — tls.ja3s.hash (server fingerprint)
tls_sni              TEXT — tls.sni (server name indication)
tls_cipher           TEXT — tls.cipher (negotiated cipher suite)
tls_cert_subject     TEXT — tls.subject
tls_validation_status TEXT — tls.session_resumed or cert validity note
```

**File fields** (event_type="file_transfer", OCSF 1001):
```
file_md5          TEXT    — fileinfo.md5
file_sha256_eve   TEXT    — fileinfo.sha256
file_mime_type    TEXT    — fileinfo.magic (MIME string)
file_size_bytes   INTEGER — fileinfo.size
```

**HTTP fields** (event_type used by HTTP normalizer, not a new type in Phase 31 but included per CONTEXT.md):
```
http_method       TEXT    — http.http_method
http_uri          TEXT    — http.url
http_status_code  INTEGER — http.status
http_user_agent   TEXT    — http.http_user_agent
```

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Python gzip stdlib | zstandard, lz4 | gzip is universal, sha256sum tools work directly, no extra deps |
| FastAPI on Ubuntu | Flask, aiohttp | FastAPI already a project dep; same pattern keeps Ubuntu code readable |
| FileResponse for gzip | StreamingResponse + manual read | FileResponse handles Content-Length, Range headers automatically |
| ILIKE event_type filter | Exact match (=) | Chip filter should use exact match; ILIKE currently used for fuzzy search |

---

## Architecture Patterns

### Recommended Project Structure (New Files)

```
ingestion/jobs/
  malcolm_collector.py         # MODIFY — add 4 normalizers + 4 poll loops

backend/models/
  event.py                     # MODIFY — add 20 new fields + to_duckdb_row() positions

backend/stores/
  duckdb_store.py              # MODIFY — extend _ECS_MIGRATION_COLUMNS list + _INSERT_SQL

backend/core/
  config.py                    # MODIFY — add UBUNTU_PIPELINE_URL, UBUNTU_POLL_INTERVAL

backend/api/
  events.py                    # MODIFY — event_type filter: ILIKE → exact match

dashboard/src/views/
  EventsView.svelte            # MODIFY — add chip row above table

dashboard/src/lib/
  api.ts                       # MODIFY — add event_type param to events.list()

# New Ubuntu-side files (deployed to N150, NOT in desktop backend):
ubuntu_pipeline/
  archiver.py                  # EvidenceArchiver — daily gzip + SHA256
  normalizer.py                # ECS field mapping for syslog + EVE
  server.py                    # FastAPI app — 3 routes
  settings.py                  # pydantic-settings for Ubuntu env vars
  requirements.txt             # fastapi, uvicorn, httpx, pydantic-settings
  evidence-archiver.service    # systemd unit
  normalizer-server.service    # systemd unit
```

### Pattern 1: EVE Type Normalizer (Clone of _normalize_alert)

**What:** Each new EVE type gets a `_normalize_<type>(self, doc: dict) -> NormalizedEvent | None` method. Same structure as `_normalize_alert()`: extract common fields (timestamp, src_ip, dst_ip, hostname), extract type-specific fields, return NormalizedEvent or None.

**When to use:** Adding tls, dns, fileinfo, anomaly normalizers.

**Example — DNS normalizer skeleton:**
```python
def _normalize_dns(self, doc: dict) -> NormalizedEvent | None:
    """Normalize an arkime_sessions3-* dns document to NormalizedEvent."""
    # Common fields (identical to _normalize_alert pattern)
    src_ip = (
        (doc.get("source") or {}).get("ip")
        or doc.get("src_ip")
        or doc.get("srcip")
    )
    dst_ip = (
        (doc.get("destination") or {}).get("ip")
        or doc.get("dst_ip")
        or doc.get("dstip")
    )
    hostname = (
        (doc.get("observer") or {}).get("hostname")
        or (doc.get("agent") or {}).get("hostname")
        or "malcolm"
    )
    raw_ts = doc.get("@timestamp", "")
    try:
        ts = datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        ts = datetime.now(timezone.utc)

    # DNS-specific fields — probe multiple paths (Malcolm may flatten)
    dns_obj = doc.get("dns") or {}
    queries = dns_obj.get("queries") or []
    answers = dns_obj.get("answers") or []

    dns_query = (
        queries[0].get("rrname") if queries else None
        or doc.get("dns_query")  # flat fallback
        or doc.get("rrname")
    )
    dns_query_type = (
        queries[0].get("rrtype") if queries else None
        or doc.get("dns_query_type")
    )
    dns_rcode = dns_obj.get("rcode") or doc.get("dns_rcode")
    dns_ttl = answers[0].get("ttl") if answers else None
    dns_answers_raw = json.dumps(answers)[:2048] if answers else None

    raw_event = json.dumps(doc)[:8192]

    return NormalizedEvent(
        event_id=str(uuid4()),
        timestamp=ts,
        ingested_at=datetime.now(timezone.utc),
        source_type="suricata_eve",
        hostname=hostname,
        event_type="dns_query",
        severity="info",
        detection_source="suricata_dns",
        raw_event=raw_event,
        src_ip=str(src_ip) if src_ip else None,
        dst_ip=str(dst_ip) if dst_ip else None,
        domain=dns_query,  # reuse existing domain field
        dns_query=dns_query,
        dns_query_type=dns_query_type,
        dns_rcode=dns_rcode,
        dns_ttl=int(dns_ttl) if dns_ttl is not None else None,
        dns_answers=dns_answers_raw,
        ocsf_class_uid=4003,
    )
```

**Important:** DNS normalizer should NOT return None on missing src_ip (unlike alert) — DNS queries are valuable even without network context.

### Pattern 2: DuckDB Migration Extension

**What:** Append 20 new column definitions to `_ECS_MIGRATION_COLUMNS` list in `duckdb_store.py`. The existing `initialise_schema()` loop already handles try/except for each column. Also update `_INSERT_SQL` in `loader.py` and `to_duckdb_row()` in `event.py`.

**When to use:** Every new field in NormalizedEvent.

**Key pattern (from duckdb_store.py lines 291-298):**
```python
for col_name, col_type in _ECS_MIGRATION_COLUMNS:
    try:
        await self.execute_write(
            f"ALTER TABLE normalized_events ADD COLUMN {col_name} {col_type}"
        )
    except Exception:
        log.debug("ECS column already exists — skipping", column=col_name)
```
DuckDB does NOT support `ADD COLUMN IF NOT EXISTS` — try/except is the only idempotency mechanism.

**Update `_INSERT_SQL` in loader.py:** Add all 20 new column names to the INSERT and extend the VALUES `?` list. Current tuple has 35 elements (positions 0-34). Phase 31 extends to 55 elements (positions 35-54).

### Pattern 3: EvidenceArchiver — Write-Once Gzip

**What:** Python class that keeps one open `gzip.GzipFile` per log type per day. On new line received: write raw bytes. At UTC midnight: close file, hash finalized file with SHA256, write checksum file.

**When to use:** Ubuntu-side only. Never on desktop.

```python
import gzip
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

class EvidenceArchiver:
    def __init__(self, archive_root: str):
        self._root = Path(archive_root)
        self._handles: dict[str, gzip.GzipFile] = {}  # type -> open handle
        self._current_date: str = ""

    def _rotate_if_needed(self):
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if today != self._current_date:
            self._close_all()
            self._current_date = today

    def _close_all(self):
        for log_type, handle in list(self._handles.items()):
            handle.close()
            # Compute SHA256 of the closed file
            if self._current_date:
                path = self._get_path(log_type, self._current_date)
                self._write_checksum(path, self._current_date)
        self._handles.clear()

    def _get_path(self, log_type: str, date: str) -> Path:
        return self._root / "raw" / log_type / f"{date}.json.gz"

    def _write_checksum(self, path: Path, date: str):
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        checksum_dir = self._root / "checksums"
        checksum_dir.mkdir(parents=True, exist_ok=True)
        checksum_file = checksum_dir / f"{date}.sha256"
        # Append (multiple log types per date)
        with open(checksum_file, "a") as cf:
            cf.write(f"{h.hexdigest()}  {path.name}\n")

    def write_line(self, log_type: str, raw_bytes: bytes):
        """Append raw bytes to today's archive. Thread-safe via caller serialization."""
        self._rotate_if_needed()
        if log_type not in self._handles:
            path = self._get_path(log_type, self._current_date)
            path.parent.mkdir(parents=True, exist_ok=True)
            self._handles[log_type] = gzip.open(str(path), "ab")
        self._handles[log_type].write(raw_bytes + b"\n")
        self._handles[log_type].flush()
```

**Key insight:** `gzip.open(path, "ab")` appends to existing gzip file. SHA256 is computed AFTER close, not during writes. This means the checksum covers the final compressed bytes.

### Pattern 4: Ubuntu FastAPI Normalization Server

**What:** 3-route FastAPI app. Serves pre-compressed gzip NDJSON files.

**Recommended route structure (Claude's Discretion):**
```python
from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from pathlib import Path
import json

app = FastAPI()
NORMALIZED_DIR = Path("/var/lib/soc-pipeline/normalized")

@app.get("/normalized/{date}")
async def get_normalized_date(date: str):
    """Return completed day's gzip NDJSON file."""
    path = NORMALIZED_DIR / f"{date}.ndjson.gz"
    if not path.exists():
        return JSONResponse({"error": "not found"}, status_code=404)
    return FileResponse(
        str(path),
        media_type="application/x-ndjson",
        headers={"Content-Encoding": "gzip"},
    )

@app.get("/normalized/latest")
async def get_normalized_latest():
    """Return today's partial gzip NDJSON (live polling target)."""
    from datetime import datetime, timezone
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return await get_normalized_date(today)

@app.get("/normalized/index")
async def get_normalized_index():
    """List available normalized files with sizes."""
    files = sorted(NORMALIZED_DIR.glob("*.ndjson.gz"))
    return {"dates": [f.stem.replace(".ndjson", "") for f in files]}
```

**Important:** `FileResponse` with `Content-Encoding: gzip` serves the pre-compressed file directly. The desktop client (httpx) must NOT auto-decompress — set `headers={"Accept-Encoding": "identity"}` on the desktop poll request, or decompress intentionally with `gzip.decompress()`.

**EvidenceArchiver deployment decision (Claude's Discretion recommendation):** Run as a separate systemd unit from the normalization server. The archiver writes raw bytes from syslog; the normalizer reads and converts. Keeping them separate avoids a single-process crash taking down both.

### Pattern 5: EventsView Filter Chips (Svelte 5 Runes)

**What:** A horizontal row of button chips above the event table. Single-select. "All" deselects the filter.

```svelte
<script lang="ts">
  import { onMount } from 'svelte'
  import { api } from '../lib/api.ts'

  const CHIP_OPTIONS = ['all', 'alert', 'tls', 'dns_query', 'file_transfer', 'anomaly', 'syslog'] as const
  type ChipFilter = typeof CHIP_OPTIONS[number]

  let selectedChip = $state<ChipFilter>('all')
  let events = $state<NormalizedEvent[]>([])
  let total = $state(0)
  let loading = $state(false)

  async function load() {
    loading = true
    try {
      const params: Parameters<typeof api.events.list>[0] = { offset, limit }
      if (selectedChip !== 'all') params.event_type = selectedChip
      const res = await api.events.list(params)
      events = res.events
      total = res.total
    } finally {
      loading = false
    }
  }

  $effect(() => {
    // Re-fetch whenever selectedChip changes
    void load()
  })
</script>

<div class="chip-row">
  {#each CHIP_OPTIONS as chip}
    <button
      class="chip"
      class:active={selectedChip === chip}
      onclick={() => { selectedChip = chip; offset = 0 }}
    >
      {chip === 'all' ? 'All' : chip}
    </button>
  {/each}
</div>
```

**Key insight:** `$effect()` runs on mount AND when `selectedChip` changes — no explicit subscription needed. Reset `offset = 0` when filter changes to avoid empty page results.

### Pattern 6: event_type Filter — Change ILIKE to Exact Match

Current `events.py` line 99:
```python
conditions.append("event_type ILIKE ?")
params.append(f"%{event_type}%")
```

For chip filtering, change to exact match (chip sends exact value like `"dns_query"`):
```python
conditions.append("event_type = ?")
params.append(event_type)
```

This is a behavior change — the existing `?event_type=` parameter changes from fuzzy to exact. Any existing callers passing fuzzy values must be updated. The chip sends exact values, which is correct.

### Anti-Patterns to Avoid

- **SHA256 before close:** Never compute the archive checksum while the gzip file is still open. The gzip footer (CRC32, file size) is written only on close. Compute SHA256 only after `handle.close()`.
- **DuckDB ADD COLUMN IF NOT EXISTS:** DuckDB does not support this syntax. Use try/except exclusively.
- **Svelte stores in Svelte 5:** Do not use `writable()` or `svelte:store`. Use `$state()` only.
- **opensearch-py:** Do not import. Use httpx directly (locked by Phase 27).
- **Parsing/AI on Ubuntu:** The Ubuntu normalizer does pure field rename/type coerce only. No Ollama calls, no inference, no severity reasoning.
- **StreamingResponse for gzip files:** Use `FileResponse` for pre-compressed files. `GZipMiddleware` does NOT compress `StreamingResponse` in Starlette.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Gzip file writing | Custom compression loop | `gzip.open(path, "ab")` | Handles gzip framing, CRC, compression level automatically |
| SHA256 streaming hash | Single-read hash | `hashlib.sha256()` + chunk iteration | Memory-safe for large files (same pattern as `loader.py:_sha256_file`) |
| NDJSON line protocol | Custom delimiters | `json.dumps(obj) + "\n"` | NDJSON is newline-separated JSON objects — trivially simple |
| DuckDB idempotent migration | IF NOT EXISTS | try/except per column | DuckDB doesn't support `ADD COLUMN IF NOT EXISTS` |
| HTTP auth for Ubuntu server | Custom middleware | Shared `AUTH_TOKEN` from desktop + Bearer header | Same token, same `authHeaders()` pattern in api.ts |

**Key insight:** The Ubuntu pipeline is intentionally dumb. Every component should be 50-100 lines max. Complexity is the enemy of forensic reliability.

---

## Common Pitfalls

### Pitfall 1: Malcolm Field Paths Differ from Raw Suricata EVE

**What goes wrong:** Malcolm ingests Suricata EVE JSON through Filebeat → OpenSearch. Filebeat may flatten nested objects (`tls.sni` → `tls_sni`) or Arkime's schema may rename fields (`dns.queries[0].rrname` → `dns_rrname` or `dns.rrname`).

**Why it happens:** Arkime has its own field schema. Malcolm maps Suricata fields to Arkime fields (similar to ECS mapping). The exact path depends on Malcolm version and field mapper configuration.

**How to avoid:** Write normalizers with multiple fallback paths using `or` chaining:
```python
dns_query = (
    (doc.get("dns") or {}).get("rrname")              # flat after Arkime map
    or ((doc.get("dns") or {}).get("queries") or [{}])[0].get("rrname")  # nested
    or doc.get("dns_rrname")                           # further flattened
    or doc.get("rrname")                               # fully flat
)
```
**Warning signs:** All new EVE events have `None` for all type-specific fields after ingestion.

### Pitfall 2: Open Gzip Handle SHA256 is Wrong

**What goes wrong:** Computing SHA256 on the gzip file while the handle is still open produces an invalid checksum — the gzip trailer (CRC32 + size) hasn't been written yet.

**Why it happens:** `gzip.GzipFile` buffers internally; the final bytes are only flushed and written on `close()`.

**How to avoid:** Always close the handle before computing SHA256. The `_close_all()` method must call `handle.close()` BEFORE `_write_checksum()`.

**Warning signs:** `gzip -t file.gz` reports CRC error; or `sha256sum` on the open vs closed file gives different results.

### Pitfall 3: DuckDB INSERT_SQL Column Count Mismatch

**What goes wrong:** After adding 20 new columns to `NormalizedEvent.to_duckdb_row()` and `_ECS_MIGRATION_COLUMNS`, the `_INSERT_SQL` in `loader.py` still has 35 columns. DuckDB raises a column count mismatch error on every INSERT.

**Why it happens:** Three places must be updated in sync: `event.py` (model fields + `to_duckdb_row()`), `duckdb_store.py` (`_ECS_MIGRATION_COLUMNS`), and `loader.py` (`_INSERT_SQL` column list + `?` count).

**How to avoid:** Update all three files in the same plan task. The `to_duckdb_row()` docstring lists positions — verify the new positions match the INSERT column order.

**Warning signs:** `duckdb.InvalidInputException: Binder Error: table has X columns but 55 values were supplied`.

### Pitfall 4: $effect Infinite Loop in Svelte 5

**What goes wrong:** If the `$effect()` in EventsView mutates `events` which is read inside the same effect, Svelte 5 creates an infinite re-render loop.

**Why it happens:** `$effect()` tracks all reactive reads. If `events` is read AND written in the same effect, it triggers itself.

**How to avoid:** The load function sets `events` as an assignment (write), not read. Keep the `$effect()` body as a plain `void load()` call — don't read any reactive state inside the effect body that load() also writes.

**Warning signs:** Browser console shows rapid repeated network requests to `/api/events`.

### Pitfall 5: Fileinfo SHA256 Field Name Conflict

**What goes wrong:** NormalizedEvent already has `file_hash_sha256` (the general field from Phase 2). The new `file_sha256_eve` field is a Suricata-specific EVE fileinfo SHA256. Using the wrong field name causes confusion.

**Why it happens:** `fileinfo.sha256` in Suricata EVE is the hash of the extracted file content. `file_hash_sha256` in NormalizedEvent is intended for any file hash from any source.

**How to avoid:** Per CONTEXT.md decision: new field is `file_sha256_eve` (TEXT). The fileinfo normalizer should populate BOTH: `file_hash_sha256=fileinfo_sha256` (for compatibility) AND `file_sha256_eve=fileinfo_sha256` (for explicit EVE provenance).

### Pitfall 6: Ubuntu Server Route Order — /normalized/latest vs /normalized/{date}

**What goes wrong:** FastAPI matches `/normalized/latest` as `date="latest"` if the literal route isn't declared before the parameterized route.

**Why it happens:** FastAPI resolves routes in declaration order. `/normalized/{date}` catches all paths including "latest".

**How to avoid:** Declare `/normalized/latest` BEFORE `/normalized/{date}` in the router. Alternatively, use a query parameter: `GET /normalized?date=latest`.

---

## Code Examples

### Suricata EVE TLS Fields (confirmed from official docs)

```python
# Source: https://github.com/OISF/suricata/blob/main/doc/userguide/output/eve/eve-json-format.rst
# TLS event _source in Malcolm OpenSearch — may be nested or flattened by Arkime
tls_obj = doc.get("tls") or {}
tls_version = tls_obj.get("version") or doc.get("tls_version")
tls_sni = tls_obj.get("sni") or doc.get("tls_sni")
tls_subject = tls_obj.get("subject") or doc.get("tls_subject")
tls_ja3 = (tls_obj.get("ja3") or {}).get("hash") or doc.get("tls_ja3_hash") or doc.get("tls_ja3")
tls_ja3s = (tls_obj.get("ja3s") or {}).get("hash") or doc.get("tls_ja3s_hash") or doc.get("tls_ja3s")
tls_cipher = tls_obj.get("cipher") or doc.get("tls_cipher")
```

### Suricata EVE DNS Fields (confirmed from official docs)

```python
# dns object structure in Suricata 7.x EVE JSON
# Note: Suricata 8.0 changed DNS logging (unified format v3)
dns_obj = doc.get("dns") or {}
# Queries array — take first entry
queries = dns_obj.get("queries") or []
q0 = queries[0] if queries else {}
dns_rrname = q0.get("rrname") or dns_obj.get("rrname") or doc.get("dns_rrname")
dns_rrtype = q0.get("rrtype") or dns_obj.get("rrtype") or doc.get("dns_rrtype")
dns_rcode = dns_obj.get("rcode") or doc.get("dns_rcode")
# Answers array
answers = dns_obj.get("answers") or []
dns_ttl = answers[0].get("ttl") if answers else None
```

### Suricata EVE Fileinfo Fields (confirmed from official docs)

```python
# fileinfo event object fields
fi = doc.get("fileinfo") or {}
fi_filename = fi.get("filename") or doc.get("fileinfo_filename")
fi_md5 = fi.get("md5") or doc.get("fileinfo_md5")
fi_sha256 = fi.get("sha256") or doc.get("fileinfo_sha256")
fi_magic = fi.get("magic") or doc.get("fileinfo_magic")  # MIME type string
fi_size = fi.get("size") or doc.get("fileinfo_size")
fi_state = fi.get("state")  # CLOSED | OPEN | TRUNCATED
# Note: md5/sha256 only present when state == CLOSED (file fully captured)
```

### Suricata EVE Anomaly Fields (confirmed from official docs)

```python
# anomaly event object fields
anom = doc.get("anomaly") or {}
anom_type = anom.get("type") or doc.get("anomaly_type")  # decode|stream|applayer
anom_event = anom.get("event") or doc.get("anomaly_event")  # event name string
anom_layer = anom.get("layer")  # applayer only
# Severity for anomaly is always "low" — anomalies are informational flags
```

### _ECS_MIGRATION_COLUMNS Extension (20 new columns)

```python
# Add to duckdb_store.py _ECS_MIGRATION_COLUMNS list
_EVE_MIGRATION_COLUMNS: list[tuple[str, str]] = [
    # DNS
    ("dns_query",         "TEXT"),
    ("dns_query_type",    "TEXT"),
    ("dns_rcode",         "TEXT"),
    ("dns_answers",       "TEXT"),
    ("dns_ttl",           "INTEGER"),
    # TLS
    ("tls_version",       "TEXT"),
    ("tls_ja3",           "TEXT"),
    ("tls_ja3s",          "TEXT"),
    ("tls_sni",           "TEXT"),
    ("tls_cipher",        "TEXT"),
    ("tls_cert_subject",  "TEXT"),
    ("tls_validation_status", "TEXT"),
    # File
    ("file_md5",          "TEXT"),
    ("file_sha256_eve",   "TEXT"),
    ("file_mime_type",    "TEXT"),
    ("file_size_bytes",   "INTEGER"),
    # HTTP (for future HTTP normalizer reuse)
    ("http_method",       "TEXT"),
    ("http_uri",          "TEXT"),
    ("http_status_code",  "INTEGER"),
    ("http_user_agent",   "TEXT"),
]
```

### api.ts events.list() with event_type param

```typescript
// Add to api.ts events.list() params interface
list: (params?: {
  offset?: number
  limit?: number
  hostname?: string
  severity?: string
  event_type?: string   // NEW — exact match, e.g. "dns_query", "tls", "alert"
}) => {
  const q = new URLSearchParams()
  // ... existing params ...
  if (params?.event_type && params.event_type !== 'all') {
    q.set('event_type', params.event_type)
  }
  return request<EventsListResponse>(`/api/events?${q}`)
}
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Poll alerts only from arkime_sessions3-* | Poll all 5 EVE types (alert, tls, dns, fileinfo, anomaly) | Phase 31 | 235K previously-ignored events now ingested |
| No evidence archiving | Write-once daily gzip + SHA256 chain of custody | Phase 31 | Forensic-grade evidence preservation |
| Desktop does all normalization | Ubuntu normalizes locally, desktop polls NDJSON | Phase 31 | Reduces desktop CPU during bulk ingest |
| EventsView shows all event types | Single-select chip filter | Phase 31 | Analyst can isolate DNS, TLS, file activity |
| Suricata 7.x DNS format (v2) | Suricata 8.x DNS format v3 (unified) | Suricata 8.0 | dns.queries[] array in v2 → may change in v3; probe both |

**Deprecated/outdated:**
- `event_type ILIKE ?` with `%{value}%` pattern: replaced by exact match `=` for chip filter use case. The fuzzy search endpoint (`/events/search`) remains unchanged.

---

## Open Questions

1. **Malcolm OpenSearch field path for EVE types**
   - What we know: Suricata raw EVE uses `tls.sni`, `dns.queries[0].rrname`, `fileinfo.filename` (nested)
   - What's unclear: Malcolm/Arkime may map these to flat fields like `tls_sni` or `suricata.dns.rrname` in the OpenSearch index
   - Recommendation: Write normalizers with 3-level fallback paths (nested, Arkime-flat, fully-flat). Log raw `doc` at DEBUG level for first 10 docs of each new type to verify field paths against live data.

2. **event.dataset filter for new EVE types**
   - What we know: Alert poll uses `{"term": {"event.dataset": "alert"}}` filter. `_build_query()` accepts `event_dataset_filter: bool`.
   - What's unclear: What value does Malcolm's `event.dataset` contain for tls/dns/fileinfo/anomaly docs?
   - Recommendation: For Phase 31, use `event_dataset_filter=False` for new types (no filter) and rely on timestamp cursor + `event.type` field in the doc for classification. Verify after first run.

3. **Ubuntu Python version**
   - What we know: Ubuntu N150 runs Python 3.x (likely 3.10 or 3.12)
   - What's unclear: Whether `uv` is available on Ubuntu or if pip-based install is needed
   - Recommendation: Use standard `pip install -r requirements.txt` for Ubuntu; don't assume `uv`.

4. **gzip.open() append mode thread safety**
   - What we know: `gzip.open(path, "ab")` opens for binary append
   - What's unclear: Whether concurrent writes from asyncio + systemd are safe
   - Recommendation: EvidenceArchiver should be single-threaded (not async). Run as blocking systemd service. Use asyncio.to_thread() if called from async context.

---

## Validation Architecture

`nyquist_validation: true` — all phase requirements must have automated test coverage.

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest + pytest-asyncio (auto mode set in pyproject.toml) |
| Config file | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| Quick run command | `uv run pytest tests/unit/test_malcolm_collector.py tests/unit/test_malcolm_normalizer.py tests/unit/test_duckdb_migration.py -x -q` |
| Full suite command | `uv run pytest tests/ -x -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| P31-T01 | `_normalize_tls()` extracts sni, ja3, version from doc | unit | `uv run pytest tests/unit/test_malcolm_normalizer.py::test_normalize_tls_extracts_sni -x` | ❌ Wave 0 |
| P31-T02 | `_normalize_dns()` extracts rrname, rcode from doc | unit | `uv run pytest tests/unit/test_malcolm_normalizer.py::test_normalize_dns_extracts_rrname -x` | ❌ Wave 0 |
| P31-T03 | `_normalize_fileinfo()` extracts filename, md5, size | unit | `uv run pytest tests/unit/test_malcolm_normalizer.py::test_normalize_fileinfo_extracts_fields -x` | ❌ Wave 0 |
| P31-T04 | `_normalize_anomaly()` extracts type, event string | unit | `uv run pytest tests/unit/test_malcolm_normalizer.py::test_normalize_anomaly_extracts_type -x` | ❌ Wave 0 |
| P31-T05 | `_poll_and_ingest()` calls all 4 new normalizers | unit | `uv run pytest tests/unit/test_malcolm_collector.py::test_poll_and_ingest_calls_all_eve_types -x` | ❌ Wave 0 |
| P31-T06 | DuckDB migration adds 20 new columns idempotently | unit | `uv run pytest tests/unit/test_duckdb_migration.py::test_eve_columns_added_idempotent -x` | ❌ Wave 0 |
| P31-T07 | EvidenceArchiver writes gzip + SHA256 checksum matches | unit | `uv run pytest tests/unit/test_evidence_archiver.py::test_archiver_sha256_matches -x` | ❌ Wave 0 |
| P31-T08 | Ubuntu server GET /normalized/{date} returns 200 | unit | `uv run pytest tests/unit/test_ubuntu_normalizer_server.py::test_get_normalized_date -x` | ❌ Wave 0 |
| P31-T09 | Desktop polls /normalized/latest, parses NDJSON | unit | `uv run pytest tests/unit/test_malcolm_collector.py::test_poll_ubuntu_normalized_latest -x` | ❌ Wave 0 |
| P31-T10 | EventsView chip filter sends ?event_type= param | manual | Open dashboard, select "DNS" chip, verify network request has event_type=dns_query | ❌ Wave 0 (manual) |
| P31-T11 | GET /api/events?event_type=dns_query returns only DNS events | unit | `uv run pytest tests/unit/test_api_endpoints.py::test_events_event_type_exact_match -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/unit/test_malcolm_normalizer.py tests/unit/test_malcolm_collector.py -x -q`
- **Per wave merge:** `uv run pytest tests/unit/ tests/sigma_smoke/ -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps (Test Files to Create)

- [ ] `tests/unit/test_malcolm_normalizer.py` — extend existing file with tests for `_normalize_tls()`, `_normalize_dns()`, `_normalize_fileinfo()`, `_normalize_anomaly()` using mock EVE docs with nested AND flat field paths
- [ ] `tests/unit/test_evidence_archiver.py` — new file covering: write_line() creates gzip, rotation closes handle before SHA256, SHA256 matches `sha256sum` output, write-once append behavior
- [ ] `tests/unit/test_ubuntu_normalizer_server.py` — new file covering: GET /normalized/{date} 200/404, GET /normalized/latest, GET /normalized/index; uses TestClient with tmp_path fixture
- [ ] `tests/unit/test_duckdb_migration.py` — extend existing file with test for 20 new EVE columns present after `initialise_schema()`, idempotent on double call
- [ ] `tests/unit/test_api_endpoints.py` — extend with test for `event_type` exact match (not ILIKE) behavior in GET /api/events

---

## Sources

### Primary (HIGH confidence)
- Codebase: `ingestion/jobs/malcolm_collector.py` — `_normalize_alert()` and `_normalize_syslog()` patterns, `_fetch_index()`, `_build_query()`, cursor tracking
- Codebase: `backend/stores/duckdb_store.py` — `_ECS_MIGRATION_COLUMNS` pattern, `execute_write()`, `initialise_schema()`
- Codebase: `backend/models/event.py` — `NormalizedEvent`, `to_duckdb_row()` position map, `OCSF_CLASS_UID_MAP`
- Codebase: `backend/api/events.py` — `event_type` ILIKE filter (lines 65, 99), existing WHERE clause builder
- Codebase: `dashboard/src/views/EventsView.svelte` — Svelte 5 runes usage (`$state`, `$effect`)
- Codebase: `dashboard/src/lib/api.ts` — `events.list()` typed function, `authHeaders()` pattern
- Codebase: `ingestion/loader.py` — `_INSERT_SQL` column list (35 columns, positions 0-34), `_sha256_file()` pattern
- Codebase: `tests/unit/test_duckdb_migration.py` — confirmed idempotent migration test pattern

### Secondary (MEDIUM confidence)
- Suricata official docs (GitHub RST): TLS, DNS, fileinfo, anomaly event object field names — https://github.com/OISF/suricata/blob/main/doc/userguide/output/eve/eve-json-format.rst
- FastAPI docs: FileResponse, StreamingResponse — https://fastapi.tiangolo.com/advanced/custom-response/
- Svelte 5 docs: `$state`, `$effect` runes — https://svelte.dev/docs/svelte/$effect
- Python stdlib: `gzip`, `hashlib` — standard library, no verification needed

### Tertiary (LOW confidence — needs field verification against live Malcolm)
- Exact Malcolm/Arkime OpenSearch field paths for TLS/DNS/fileinfo/anomaly — verified from raw Suricata EVE spec but Malcolm may remap; requires live inspection of `doc` structure

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries already in project, patterns confirmed from codebase
- Architecture: HIGH — all 6 patterns are clones or extensions of existing working code
- Pitfalls: MEDIUM — Malcolm field path uncertainty is the primary risk; all others are HIGH
- Suricata EVE field paths: MEDIUM — confirmed from official docs, uncertain how Malcolm maps them in OpenSearch

**Research date:** 2026-04-08
**Valid until:** 2026-05-08 (Malcolm field paths may change on Malcolm upgrade; Suricata stable)
