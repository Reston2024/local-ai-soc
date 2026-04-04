# Phase 23: Firewall Telemetry Ingestion - Research

**Researched:** 2026-04-03
**Domain:** Syslog/EVE JSON parsing, asyncio UDP networking, background collector jobs
**Confidence:** HIGH (core patterns verified against existing codebase; external format docs MEDIUM)

---

## Summary

Phase 23 adds perimeter visibility by ingesting IPFire firewall syslog and Suricata EVE JSON telemetry into the existing NormalizedEvent pipeline. All four requirements follow patterns already established in the codebase: parsers extend `BaseParser`, collectors follow the `OsqueryCollector` pattern, settings follow `pydantic-settings` with `extra="ignore"`, and writes go through `store.execute_write()`.

The primary new engineering challenge is the UDP syslog listener for IPFire. Python's `asyncio.DatagramProtocol` via `loop.create_datagram_endpoint()` is the correct approach on Windows — `reuse_port` is not available on Windows and must not be used. The alternative (and preferred) path for this SOC deployment is **file-based tailing of the IPFire remote syslog** (rsyslog writes to a local file; the collector tails it), which matches the proven `OsqueryCollector` tail-and-parse pattern exactly and avoids all UDP socket complications.

The EVE JSON parser is simpler: Suricata writes NDJSON to a file (`/var/log/suricata/eve.json` or a configured path), and the existing `JsonParser` already handles NDJSON files. A dedicated `SuricataEveParser` is needed only to apply domain-specific field mapping (severity scale inversion, MITRE extraction from `alert.metadata`).

**Primary recommendation:** Implement both parsers as `BaseParser` subclasses with no extension registration (used programmatically, like `OsqueryParser`). Implement the collector as a file-tail loop mirroring `OsqueryCollector`. Use `system_kv` for heartbeat `last_seen` storage (the key `firewall.last_heartbeat` is a clean fit). The status endpoint pattern follows the existing `/api/health` and model-status patterns in the codebase.

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| P23-T01 | IPFire syslog parser — `ingestion/parsers/ipfire_syslog_parser.py`; RFC 3164/5424 parsing; maps FORWARDFW/INPUTFW/DROP fields to NormalizedEvent; preserves raw line in `raw_event`; unit tests | IPFire log format verified from community sources; RFC 3164 parsing well-covered by stdlib `re`; field map documented below |
| P23-T02 | Suricata EVE JSON parser — `ingestion/parsers/suricata_eve_parser.py`; alert/flow/dns/http event types; MITRE from `alert.metadata`; severity 1=critical..4=low; unit tests | Existing `suricata_eve_sample.ndjson` fixture already in `fixtures/`; EVE JSON format documented from official Suricata docs |
| P23-T03 | Firewall collector job — `ingestion/jobs/firewall_collector.py`; configurable via settings; exponential backoff on failure; missed heartbeat detection; events via `IngestionLoader.ingest_events()` | `OsqueryCollector` is the direct template; `ingestion/jobs/` directory does not yet exist (Wave 0 creates it) |
| P23-T04 | Heartbeat normalisation — `event_type="heartbeat"`; `last_seen` in `system_kv`; `GET /api/firewall/status` → connected/degraded/offline; configurable threshold | `system_kv` + `get_kv`/`set_kv` already implemented in `SQLiteStore`; pattern verified |
</phase_requirements>

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `asyncio` (stdlib) | Python 3.12 | Background collector event loop | Project standard — all async I/O |
| `re` (stdlib) | Python 3.12 | RFC 3164/5424 syslog regex parsing | No external dep needed; patterns are stable |
| `json` (stdlib) | Python 3.12 | EVE JSON NDJSON parsing | Already used by all parsers |
| `pydantic-settings` | existing pin | New settings fields for firewall config | Existing pattern in `backend/core/config.py` |
| `FastAPI` | existing pin | `GET /api/firewall/status` endpoint | Existing pattern |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `datetime` (stdlib) | Python 3.12 | Timestamp parsing (RFC 3164 has no year; EVE JSON ISO-8601) | All parsers need it |
| `asyncio.to_thread` | Python 3.12 | Wrapping blocking file I/O in collector | Required by CLAUDE.md convention |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| File-tail for syslog | UDP `DatagramProtocol` listener | UDP works but requires firewall to send to the SOC host's port; file-tail is simpler and matches existing pattern; UDP listener blocks on Windows reuse_port |
| Custom syslog regex | `syslog` stdlib module | stdlib `syslog` is for *writing* syslog, not parsing; regex is the right tool |
| Custom EVE parsing | Reuse `JsonParser` directly | `JsonParser` lacks EVE-specific severity inversion and MITRE extraction; dedicated parser is cleaner |

**Installation:** No new packages required. All dependencies are in the existing stack.

---

## Architecture Patterns

### Recommended Project Structure
```
ingestion/
├── parsers/
│   ├── ipfire_syslog_parser.py   # NEW — P23-T01
│   └── suricata_eve_parser.py    # NEW — P23-T02
├── jobs/
│   ├── __init__.py               # NEW — empty, creates package
│   └── firewall_collector.py     # NEW — P23-T03
└── osquery_collector.py          # EXISTING — reference template

backend/
├── api/
│   └── firewall.py               # NEW — P23-T04 status endpoint
└── core/
    └── config.py                 # MODIFIED — add firewall settings

fixtures/
├── syslog/
│   └── ipfire_sample.log         # NEW — IPFire syslog fixture lines
└── suricata_eve_sample.ndjson    # EXISTING — already has alert/flow/dns/http samples

tests/unit/
├── test_ipfire_syslog_parser.py  # NEW — P23-T01 unit tests
├── test_suricata_eve_parser.py   # NEW — P23-T02 unit tests
└── test_firewall_collector.py    # NEW — P23-T03/T04 unit tests
```

### Pattern 1: Parser Following BaseParser Contract
**What:** Both new parsers extend `BaseParser` with `supported_extensions = []` (programmatic use, not extension-based registry). They have a `parse(file_path, case_id)` generator AND a `parse_line(line, source_file, case_id)` / `parse_record(record, ...)` convenience method for the live collector.
**When to use:** Any new telemetry source that doesn't match a standard file extension.

```python
# Pattern verified against ingestion/parsers/osquery_parser.py
class IPFireSyslogParser(BaseParser):
    supported_extensions: list[str] = []   # Not extension-based

    def parse(self, file_path: str, case_id: str | None = None) -> Iterator[NormalizedEvent]:
        with open(file_path, encoding="utf-8", errors="replace") as fh:
            for lineno, raw_line in enumerate(fh, 1):
                raw_line = raw_line.strip()
                if not raw_line:
                    continue
                event = self.parse_line(raw_line, source_file=file_path, case_id=case_id)
                if event:
                    yield event

    def parse_line(self, raw_line: str, source_file: str = "ipfire_syslog",
                   case_id: str | None = None) -> NormalizedEvent | None:
        ...
```

### Pattern 2: Collector Job Following OsqueryCollector Template
**What:** Async class with `run()` loop, `_ingest_new_lines()`, `_read_new_lines()` (blocking, via `asyncio.to_thread`), exponential backoff on consecutive failures, `status()` method.
**When to use:** Any live streaming/polling collector that tails a file.

```python
# Pattern from ingestion/osquery_collector.py — adapt directly
class FirewallCollector:
    def __init__(self, syslog_path: Path, eve_path: Path,
                 loader: IngestionLoader, sqlite_store, interval_sec: int = 5):
        self._syslog_path = syslog_path
        self._eve_path = eve_path
        self._loader = loader          # use ingest_events() not raw execute_write
        self._sqlite = sqlite_store    # for set_kv("firewall.last_heartbeat", ...)
        self._interval = interval_sec
        self._syslog_offset: int = 0
        self._eve_offset: int = 0
        self._consecutive_failures: int = 0
        self._running: bool = False

    async def run(self) -> None:
        self._running = True
        backoff = self._interval
        try:
            while True:
                await asyncio.sleep(backoff)
                success = await self._ingest_new_data()
                if success:
                    self._consecutive_failures = 0
                    backoff = self._interval
                else:
                    self._consecutive_failures += 1
                    backoff = min(self._interval * (2 ** self._consecutive_failures), 300)
        except asyncio.CancelledError:
            self._running = False
            raise
```

### Pattern 3: Settings Extension
**What:** Add new fields to `Settings` class in `backend/core/config.py`. All new fields have sensible defaults so the app starts without firewall present.

```python
# In Settings class — matches existing OSQUERY_* pattern exactly
FIREWALL_ENABLED: bool = False          # Default OFF — app starts without firewall
FIREWALL_SYSLOG_PATH: str = "/var/log/remote/ipfire/messages"  # rsyslog writes here
FIREWALL_EVE_PATH: str = "/var/log/remote/ipfire/suricata/eve.json"
FIREWALL_SYSLOG_HOST: str = "0.0.0.0"  # For future UDP listener if needed
FIREWALL_SYSLOG_PORT: int = 514
FIREWALL_HEARTBEAT_THRESHOLD_SECONDS: int = 120   # degraded after 2 min
FIREWALL_OFFLINE_THRESHOLD_SECONDS: int = 300     # offline after 5 min
FIREWALL_POLL_INTERVAL: int = 5
FIREWALL_CONSECUTIVE_FAILURE_LIMIT: int = 5       # alert threshold
```

### Pattern 4: Heartbeat via system_kv
**What:** `SQLiteStore.set_kv("firewall.last_heartbeat", iso_timestamp)` on every heartbeat event. Status endpoint reads it and computes state from recency.

```python
# Uses existing SQLiteStore.get_kv / set_kv — verified in sqlite_store.py lines 1454-1471
async def get_firewall_status(stores: Stores, settings: Settings) -> dict:
    last_seen_str = await asyncio.to_thread(
        stores.sqlite.get_kv, "firewall.last_heartbeat"
    )
    if last_seen_str is None:
        return {"status": "offline", "last_seen": None}
    last_seen = datetime.fromisoformat(last_seen_str)
    age_seconds = (datetime.now(tz=timezone.utc) - last_seen).total_seconds()
    if age_seconds < settings.FIREWALL_HEARTBEAT_THRESHOLD_SECONDS:
        state = "connected"
    elif age_seconds < settings.FIREWALL_OFFLINE_THRESHOLD_SECONDS:
        state = "degraded"
    else:
        state = "offline"
    return {"status": state, "last_seen": last_seen_str, "age_seconds": age_seconds}
```

### Pattern 5: Lifespan Integration
**What:** Conditional start of `FirewallCollector` task in `backend/main.py` lifespan, mirroring the osquery block at lines 193-216.

```python
# In lifespan() — after stores and loader are initialised
firewall_task: asyncio.Task | None = None
if settings.FIREWALL_ENABLED:
    from ingestion.jobs.firewall_collector import FirewallCollector
    _fw_collector = FirewallCollector(
        syslog_path=Path(settings.FIREWALL_SYSLOG_PATH),
        eve_path=Path(settings.FIREWALL_EVE_PATH),
        loader=loader,
        sqlite_store=sqlite_store,
        interval_sec=settings.FIREWALL_POLL_INTERVAL,
    )
    firewall_task = asyncio.ensure_future(_fw_collector.run())
    app.state.firewall_collector = _fw_collector
else:
    app.state.firewall_collector = None
```

### Anti-Patterns to Avoid
- **Direct `duckdb.connect()` in collector:** Use `loader.ingest_events()` or `store.execute_write()` only — never open a new DuckDB connection in the collector.
- **Using `reuse_port=True` in UDP listener on Windows:** Not supported. Use file-tail pattern instead.
- **Registering parsers in the extension registry:** IPFire and Suricata parsers are programmatic — `supported_extensions = []` keeps them out of the file-upload path.
- **Blocking the event loop in `run()`:** All file I/O must go through `asyncio.to_thread()`.
- **Fatal errors on missing files:** Collector must log and continue — firewall may not be available at startup.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| RFC 3164 timestamp parsing | Custom date parser | `datetime.strptime` with fallback | RFC 3164 has no year; pattern is `%b %d %H:%M:%S` with current-year inference |
| Exponential backoff | Custom sleep math | Simple `min(interval * 2**n, max_backoff)` | Already validated in osquery pattern; no external lib needed |
| Key-value persistence for heartbeat | New SQLite table | `SQLiteStore.set_kv()` / `get_kv()` | `system_kv` table already exists with upsert semantics |
| Batch ingest coordination | Direct DuckDB writes | `IngestionLoader.ingest_events()` | Handles dedup, Chroma embed, graph extraction, provenance — free features |
| Event deduplication | Custom hash check | `IngestionLoader.ingest_events()` dedup step | Already implemented in loader |

**Key insight:** The `IngestionLoader.ingest_events()` method is the correct integration point for the collector — not raw `execute_write()`. Using it means heartbeat events automatically get Chroma embeddings and graph extraction, and the deduplication layer prevents re-ingesting the same heartbeat on restart.

---

## IPFire Syslog Format

### RFC 3164 Header + iptables Log Prefix

IPFire uses standard Linux kernel iptables logging via syslog. Log lines arrive as RFC 3164 syslog messages with the iptables `LOG` target prefix in the message body.

**Verified format from community sources (MEDIUM confidence — community posts, not official docs):**

```
Aug 10 18:44:55 ipfire kernel: FORWARDFW IN=green0 OUT=red0 MAC=d0:xx:xx:xx:xx:xx SRC=192.168.1.100 DST=54.230.45.152 LEN=60 TOS=0x00 PREC=0x00 TTL=63 ID=6995 DF PROTO=TCP SPT=34995 DPT=443 WINDOW=14600 RES=0x00 SYN URGP=0
```

```
Sep 16 13:05:50 ipfire kernel: DROP_CTINVALID IN=blue0 OUT= MAC=xx SRC=10.1.3.51 DST=10.1.3.1 LEN=52 TOS=0x00 PREC=0x00 TTL=64 ID=56182 DF PROTO=TCP SPT=42400 DPT=800 WINDOW=1542 RES=0x00 ACK PSH FIN URGP=0
```

### RFC 3164 Header Fields
| Field | Example | Notes |
|-------|---------|-------|
| Month | `Aug` | Abbreviated month name |
| Day | `10` | 1 or 2 digits |
| Time | `18:44:55` | HH:MM:SS |
| Hostname | `ipfire` | Firewall hostname |
| Process | `kernel:` | Always `kernel:` for iptables |

### iptables Log Body Fields
| Field | Maps To | Notes |
|-------|---------|-------|
| Log prefix (e.g. `FORWARDFW`) | `event_type`, `detection_source` | Chain name; also encodes action |
| `IN=` | `tags` (interface) or custom field | Ingress interface (e.g. `green0`, `red0`, `blue0`) |
| `OUT=` | `tags` | Egress interface (may be empty for INPUT chain) |
| `SRC=` | `src_ip` | Source IP |
| `DST=` | `dst_ip` | Destination IP |
| `PROTO=` | `network_protocol` | TCP, UDP, ICMP |
| `SPT=` | `src_port` | Source port (TCP/UDP only) |
| `DPT=` | `dst_port` | Destination port (TCP/UDP only) |
| `LEN=` | (discard or raw_event) | Packet length |

### Log Prefix → Action Mapping
| Prefix | Action | event_outcome |
|--------|--------|--------------|
| `FORWARDFW` | Forwarded (allowed) | `success` |
| `INPUTFW` | Input (allowed) | `success` |
| `DROP_*` (e.g. `DROP_CTINVALID`, `DROP_INPUT`) | Dropped | `failure` |
| `REJECT_*` | Rejected | `failure` |

**Note on zones:** IPFire uses colour-coded zones. Interface names encode zone: `green0` = LAN, `red0` = WAN/internet, `blue0` = WiFi/DMZ, `orange0` = DMZ. Map these to `tags` field as `zone:green` etc.

### Parsing Strategy
```python
# Regex for RFC 3164 header
_RFC3164_RE = re.compile(
    r'^(?P<month>\w{3})\s+(?P<day>\d{1,2})\s+(?P<time>\d{2}:\d{2}:\d{2})\s+'
    r'(?P<host>\S+)\s+kernel:\s+(?P<body>.+)$'
)
# Regex for iptables key=value pairs
_KV_RE = re.compile(r'(\w+)=(\S*)')
# Extract log prefix (first word before space or IN=)
_PREFIX_RE = re.compile(r'^(\S+)\s+IN=')
```

**Year inference:** RFC 3164 omits the year. Use `datetime.now().year`; handle December→January rollover by checking if parsed date is more than 30 days in the future and subtracting 1 year.

---

## Suricata EVE JSON Format

### Common Fields (All Event Types)
| Field | Type | Maps To |
|-------|------|---------|
| `timestamp` | ISO-8601 string | `timestamp` |
| `flow_id` | int | `tags` as `flow_id:N` |
| `event_type` | string | `event_type` (mapped) |
| `src_ip` | string | `src_ip` |
| `src_port` | int | `src_port` |
| `dest_ip` | string | `dst_ip` |
| `dest_port` | int | `dst_port` |
| `proto` | string | `network_protocol` |
| `host` | string | `hostname` (sensor hostname) |

### Alert Event Fields
| Field | Type | Maps To | Notes |
|-------|------|---------|-------|
| `alert.action` | string | `event_outcome` | "allowed" → "success"; "blocked" → "failure" |
| `alert.signature_id` | int | `tags` as `sid:N` | |
| `alert.signature` | string | `detection_source` | Rule message |
| `alert.category` | string | `tags` | |
| `alert.severity` | int | `severity` | **1=critical, 2=high, 3=medium, 4=low** |
| `alert.metadata` | dict[str, list[str]] | see MITRE below | Optional; rule-dependent |

**Severity mapping (verified HIGH — from Suricata schema, confirmed by existing fixture):**
```python
_EVE_SEVERITY_MAP = {1: "critical", 2: "high", 3: "medium", 4: "low"}
```

**MITRE ATT&CK in `alert.metadata`:** The metadata field is a dict of lists (each value is a list even for single items). MITRE fields are **not standardised across all rulesets** — they appear in ET Pro/ET Open rules as:
- `mitre_attack_id` → technique (e.g. `["T1071.001"]`)
- `mitre_tactic_id` → tactic (e.g. `["TA0011"]`)
- `mitre_tactic_name` → tactic name (e.g. `["Command and Control"]`)
- `attack_target`, `affected_product`, `malware_family` — other common metadata

**Extraction pattern:**
```python
metadata = alert.get("metadata") or {}
# metadata values are lists; take first element
technique = (metadata.get("mitre_attack_id") or [None])[0]
tactic = (metadata.get("mitre_tactic_name") or [None])[0]
```

### DNS Event Fields
| Field | Maps To |
|-------|---------|
| `dns.rrname` | `domain` |
| `dns.rrtype` | `tags` as `dns_type:A` |
| `dns.type` | `event_type` → `"dns_query"` |

### HTTP Event Fields
| Field | Maps To |
|-------|---------|
| `http.hostname` | `domain` |
| `http.url` | `url` |
| `http.http_method` | `tags` as `method:GET` |
| `http.status` | `event_outcome` (2xx → success, 4xx/5xx → failure) |

### Flow Event Fields
| Field | Maps To |
|-------|---------|
| `flow.state` | `event_outcome` (closed → success) |
| `flow.bytes_toserver` + `flow.bytes_toclient` | (discard or raw_event) |

### Event Type → NormalizedEvent event_type Mapping
| EVE `event_type` | `NormalizedEvent.event_type` | OCSF class_uid |
|-----------------|------------------------------|----------------|
| `alert` | `"network_connect"` (if flow) or `"detection"` | 4001 |
| `flow` | `"network_connect"` | 4001 |
| `dns` | `"dns_query"` | 4003 |
| `http` | `"network_connect"` | 4001 |
| `tls` | `"network_connect"` | 4001 |
| `heartbeat` | `"heartbeat"` | None |

---

## Common Pitfalls

### Pitfall 1: RFC 3164 Year Ambiguity
**What goes wrong:** Parsed timestamps are in the wrong year (e.g. December log lines appear as next year's January when processed in January).
**Why it happens:** RFC 3164 syslog omits the year from the timestamp.
**How to avoid:** Infer current year, then check: if parsed_date > now + 30_days, subtract 1 year.
**Warning signs:** Timestamps appear far in the future; deduplication misses events.

### Pitfall 2: EVE JSON Fields Use `dest_ip` Not `dst_ip`
**What goes wrong:** Suricata uses `dest_ip`/`dest_port` while `NormalizedEvent` uses `dst_ip`/`dst_port`.
**Why it happens:** Different naming conventions between Suricata and the project schema.
**How to avoid:** Explicit field mapping in `SuricataEveParser` — do not reuse the generic `FieldMapper`.
**Warning signs:** `dst_ip` is always `None` on ingested EVE events.

### Pitfall 3: iptables Log Prefix Variants
**What goes wrong:** Parser fails to extract action/chain from unfamiliar prefix like `DROP_CTINVALID`, `REJECT_INPUT`, `OUTGOINGFW`.
**Why it happens:** IPFire uses dynamic prefix names based on custom rule names.
**How to avoid:** Parse the prefix as a string; extract action by checking if prefix contains "DROP", "REJECT" (case-insensitive). Do not hardcode the full set.
**Warning signs:** `event_outcome` is `None` on many events.

### Pitfall 4: Empty `OUT=` Field in INPUT Chain Logs
**What goes wrong:** Regex fails or raises `ValueError` when `OUT=` has no value.
**Why it happens:** INPUT chain logs have `OUT=` with empty value (the packet didn't leave an interface).
**How to avoid:** Use `re.findall(r'(\w+)=(\S*)') ` which correctly captures empty values, or strip trailing empty values after split.
**Warning signs:** Parse errors on inbound-only firewall logs.

### Pitfall 5: Collector Holds Reference to Stale IngestionLoader
**What goes wrong:** After app restart (in test), the loader has a closed store reference.
**Why it happens:** `FirewallCollector` holds `loader` at construction time.
**How to avoid:** Tests mock `loader.ingest_events` as `AsyncMock` — never use a real loader in unit tests.
**Warning signs:** `RuntimeError: DuckDB closed` in collector tests.

### Pitfall 6: Heartbeat Status Returns "offline" at Cold Start
**What goes wrong:** `GET /api/firewall/status` returns `"offline"` before any heartbeat is received, even if the collector is running.
**Why it happens:** `system_kv` has no `firewall.last_heartbeat` key until the first heartbeat event is ingested.
**How to avoid:** Status endpoint distinguishes between `None` (never seen = "offline") vs stale (was seen, now stale = "degraded"/"offline"). Document this in API response with a `never_seen` flag.
**Warning signs:** Analyst confusion — firewall "offline" even immediately after connecting.

### Pitfall 7: EVE alert.metadata Values Are Lists
**What goes wrong:** `metadata["mitre_attack_id"]` returns `["T1071.001"]` not `"T1071.001"`.
**Why it happens:** Suricata stores all metadata values as lists (even single-value fields).
**How to avoid:** Always use `(metadata.get("field") or [None])[0]` pattern.
**Warning signs:** `attack_technique` stored as `"['T1071.001']"` (stringified list).

---

## Code Examples

### IPFire Syslog Line Parsing
```python
# Source: verified against community.ipfire.org forum examples + RFC 3164 spec
import re
from datetime import datetime, timezone

_RFC3164_RE = re.compile(
    r'^(?P<month>\w{3})\s+(?P<day>\d{1,2})\s+(?P<time>\d{2}:\d{2}:\d{2})\s+'
    r'(?P<host>\S+)\s+kernel:\s+(?P<body>.+)$'
)
_KV_RE = re.compile(r'(\w+)=(\S*)')

def _parse_ipfire_line(raw_line: str, ingested_at: datetime) -> dict | None:
    m = _RFC3164_RE.match(raw_line.strip())
    if not m:
        return None
    # Year inference: RFC 3164 omits year
    year = ingested_at.year
    try:
        ts = datetime.strptime(
            f"{year} {m['month']} {m['day']} {m['time']}",
            "%Y %b %d %H:%M:%S"
        ).replace(tzinfo=timezone.utc)
        # Handle Dec/Jan rollover
        if ts > ingested_at.replace(tzinfo=timezone.utc) + timedelta(days=30):
            ts = ts.replace(year=year - 1)
    except ValueError:
        ts = ingested_at

    body = m['body']
    kv = dict(_KV_RE.findall(body))
    prefix = body.split()[0] if body else ""

    action = "drop" if ("DROP" in prefix.upper() or "REJECT" in prefix.upper()) else "allow"
    return {
        "prefix": prefix, "kv": kv, "ts": ts,
        "host": m["host"], "action": action,
    }
```

### Suricata EVE JSON Alert Parsing (MITRE Extraction)
```python
# Source: Suricata 8.0 documentation + verified against fixtures/suricata_eve_sample.ndjson
_EVE_SEVERITY_MAP = {1: "critical", 2: "high", 3: "medium", 4: "low"}

def _map_alert(record: dict, ingested_at: datetime, source_file: str,
               case_id: str | None) -> NormalizedEvent:
    alert = record.get("alert") or {}
    metadata = alert.get("metadata") or {}

    severity_int = alert.get("severity", 3)
    severity = _EVE_SEVERITY_MAP.get(severity_int, "medium")

    # MITRE: metadata values are lists; take first element
    technique = (metadata.get("mitre_attack_id") or [None])[0]
    tactic = (metadata.get("mitre_tactic_name") or [None])[0]

    action = alert.get("action", "")
    outcome = "success" if action == "allowed" else "failure" if action == "blocked" else None

    return NormalizedEvent(
        event_id=str(uuid4()),
        timestamp=_parse_eve_ts(record.get("timestamp"), ingested_at),
        ingested_at=ingested_at,
        source_type="suricata_eve",
        source_file=source_file,
        hostname=record.get("host"),
        src_ip=record.get("src_ip"),
        src_port=record.get("src_port"),
        dst_ip=record.get("dest_ip"),      # NOTE: dest_ip not dst_ip
        dst_port=record.get("dest_port"),
        network_protocol=record.get("proto"),
        event_type="network_connect",
        severity=severity,
        detection_source=alert.get("signature"),
        attack_technique=technique,
        attack_tactic=tactic,
        event_outcome=outcome,
        ocsf_class_uid=4001,
        raw_event=json.dumps(record, default=str)[:8192],
        case_id=case_id,
        tags=f"suricata:alert:sid:{alert.get('signature_id', '')}",
    )
```

### Collector Exponential Backoff
```python
# Source: adapted from ingestion/osquery_collector.py pattern
_MAX_BACKOFF = 300  # 5 minutes cap

async def run(self) -> None:
    self._running = True
    backoff = self._interval
    try:
        while True:
            await asyncio.sleep(backoff)
            success = await self._ingest_new_data()
            if success:
                self._consecutive_failures = 0
                backoff = self._interval
            else:
                self._consecutive_failures += 1
                backoff = min(self._interval * (2 ** min(self._consecutive_failures, 8)), _MAX_BACKOFF)
                if self._consecutive_failures >= self._failure_alert_limit:
                    log.warning(
                        "Firewall consecutive failures exceeded threshold",
                        failures=self._consecutive_failures,
                    )
    except asyncio.CancelledError:
        self._running = False
        raise
```

### system_kv Heartbeat Write (async-safe)
```python
# Source: verified against backend/stores/sqlite_store.py lines 1461-1471
# SQLiteStore.set_kv is synchronous — must use asyncio.to_thread
async def _record_heartbeat(self) -> None:
    now_iso = datetime.now(tz=timezone.utc).isoformat()
    await asyncio.to_thread(
        self._sqlite.set_kv, "firewall.last_heartbeat", now_iso
    )
```

---

## IPFire Syslog Fixture Lines

Fixture file `fixtures/syslog/ipfire_sample.log` should contain at minimum:

```
# FORWARDFW — TCP allowed through firewall
Aug 10 18:44:55 ipfire kernel: FORWARDFW IN=green0 OUT=red0 MAC=d0:50:99:aa:bb:cc SRC=192.168.1.100 DST=54.230.45.152 LEN=60 TOS=0x00 PREC=0x00 TTL=63 ID=6995 DF PROTO=TCP SPT=34995 DPT=443 WINDOW=14600 RES=0x00 SYN URGP=0
# DROP — UDP dropped
Sep 16 13:05:50 ipfire kernel: DROP_INPUT IN=red0 OUT= MAC=d0:50:99:aa:bb:01 SRC=203.0.113.50 DST=192.168.1.1 LEN=28 TOS=0x00 PREC=0x00 TTL=64 ID=100 PROTO=UDP SPT=12345 DPT=514 LEN=8
# INPUTFW — ICMP
Oct 05 09:30:00 ipfire kernel: INPUTFW IN=green0 OUT= MAC=d0:50:99:aa:bb:02 SRC=192.168.1.5 DST=192.168.1.1 LEN=84 TOS=0x00 PREC=0x00 TTL=64 ID=200 PROTO=ICMP TYPE=8 CODE=0 ID=12345 SEQ=1
# Heartbeat marker (custom prefix IPFire sends for keepalive, or synthesised by collector)
Oct 05 09:30:00 ipfire kernel: HEARTBEAT src=ipfire
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| UDP syslog listener in Python | File-tail on rsyslog-written file | Established pattern | No Windows port-binding issues; no socket permissions |
| Raw DuckDB writes in collector | `IngestionLoader.ingest_events()` | Established in Phase 8 | Free dedup, Chroma embed, graph extraction |
| Custom KV store for state | `system_kv` table | Phase 22 | Reuse existing infrastructure |

**Deprecated/outdated:**
- `OsqueryCollector._build_row()` hardcoded 29-column tuple: The new collector should use `to_duckdb_row()` (35 columns as of Phase 20) via `ingest_events()`, avoiding the brittle row-building pattern. However the new collector should call `loader.ingest_events()` not write directly — this sidesteps the column count issue entirely.

---

## Open Questions

1. **Does the IPFire instance actually send syslog to a remote path, or does the collector need UDP?**
   - What we know: The requirements mention `FIREWALL_SYSLOG_HOST` and `FIREWALL_SYSLOG_PORT` settings, implying UDP listener capability is expected.
   - What's unclear: Whether Phase 23 needs to implement both file-tail AND UDP, or just one.
   - Recommendation: Implement file-tail (simpler, Windows-compatible, matches pattern). Add `FIREWALL_SYSLOG_HOST`/`PORT` settings as stubs for future UDP implementation. The collector can check: if `syslog_path` exists, tail it; otherwise warn that UDP is not yet implemented.

2. **Heartbeat event source — who generates it?**
   - What we know: P23-T04 requires `event_type="heartbeat"` events in NormalizedEvent.
   - What's unclear: Does IPFire send explicit heartbeat syslog lines, or does the collector synthesise them based on successful polling cycles?
   - Recommendation: Collector synthesises a heartbeat `NormalizedEvent` each polling cycle when it successfully reads data (or on a configurable timer). This is independent of whether any actual log lines were new in that cycle.

3. **EVE JSON alert.metadata MITRE field names across ruleset versions**
   - What we know: ET Open/Pro rules use `mitre_attack_id` and `mitre_tactic_id`; the existing fixture has no MITRE metadata (uses standard ET fields only).
   - What's unclear: Whether the specific IPFire's Suricata ruleset includes MITRE metadata.
   - Recommendation: Implement MITRE extraction defensively (optional fields, graceful absence). Add fixture records WITH and WITHOUT MITRE metadata in test suite.

---

## Validation Architecture

> `workflow.nyquist_validation` is `true` in `.planning/config.json` — section included.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest + pytest-asyncio (auto mode) |
| Config file | `pyproject.toml` (pytest-asyncio mode = auto) |
| Quick run command | `uv run pytest tests/unit/test_ipfire_syslog_parser.py tests/unit/test_suricata_eve_parser.py tests/unit/test_firewall_collector.py -x` |
| Full suite command | `uv run pytest` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| P23-T01 | IPFire parser produces NormalizedEvent from FORWARDFW line | unit | `uv run pytest tests/unit/test_ipfire_syslog_parser.py -x` | Wave 0 |
| P23-T01 | IPFire parser maps src_ip/dst_ip/proto/action correctly | unit | same file | Wave 0 |
| P23-T01 | IPFire parser handles DROP/REJECT action variants | unit | same file | Wave 0 |
| P23-T01 | IPFire parser preserves raw line in raw_event | unit | same file | Wave 0 |
| P23-T01 | IPFire parser handles ICMP (no SPT/DPT) | unit | same file | Wave 0 |
| P23-T02 | Suricata parser maps alert severity 1→critical, 4→low | unit | `uv run pytest tests/unit/test_suricata_eve_parser.py -x` | Wave 0 |
| P23-T02 | Suricata parser extracts MITRE technique from alert.metadata | unit | same file | Wave 0 |
| P23-T02 | Suricata parser handles dns, flow, http event types | unit | same file | Wave 0 |
| P23-T02 | Suricata parser maps dest_ip to dst_ip | unit | same file | Wave 0 |
| P23-T03 | Collector reads new syslog lines and calls ingest_events | unit (async, mock) | `uv run pytest tests/unit/test_firewall_collector.py -x` | Wave 0 |
| P23-T03 | Collector skips gracefully when files are absent | unit (async, mock) | same file | Wave 0 |
| P23-T03 | Collector applies exponential backoff on consecutive failures | unit (async, mock) | same file | Wave 0 |
| P23-T04 | Heartbeat event has event_type="heartbeat" | unit | same file | Wave 0 |
| P23-T04 | Status endpoint returns connected/degraded/offline by recency | unit | `uv run pytest tests/unit/test_firewall_collector.py -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/unit/test_ipfire_syslog_parser.py tests/unit/test_suricata_eve_parser.py tests/unit/test_firewall_collector.py -x`
- **Per wave merge:** `uv run pytest`
- **Phase gate:** Full suite green (currently 825 tests + new phase tests) before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/unit/test_ipfire_syslog_parser.py` — covers P23-T01 (new file)
- [ ] `tests/unit/test_suricata_eve_parser.py` — covers P23-T02 (new file)
- [ ] `tests/unit/test_firewall_collector.py` — covers P23-T03 + P23-T04 (new file)
- [ ] `ingestion/jobs/__init__.py` — package init (new directory)
- [ ] `fixtures/syslog/ipfire_sample.log` — syslog fixture lines (directory exists, is empty)

---

## Sources

### Primary (HIGH confidence)
- `ingestion/osquery_collector.py` — direct template for `FirewallCollector`
- `ingestion/parsers/osquery_parser.py` — programmatic parser pattern
- `ingestion/parsers/base.py` — `BaseParser` interface
- `ingestion/loader.py` — `IngestionLoader.ingest_events()` integration point
- `backend/stores/sqlite_store.py` lines 1454-1471 — `get_kv`/`set_kv` verified
- `backend/core/config.py` — settings extension pattern
- `backend/main.py` lines 193-216 — lifespan collector integration pattern
- `backend/models/event.py` — `NormalizedEvent` schema (35 columns)
- `fixtures/suricata_eve_sample.ndjson` — existing EVE fixture (alert/flow/dns/http)

### Secondary (MEDIUM confidence)
- [IPFire community forum: FORWARDFW format](https://community.ipfire.org/t/the-log-shows-forwardfw-i-do-not-understand/10339) — example syslog lines with field breakdown
- [IPFire forum: FORWARDFW fields](https://forum.ipfire.org/viewtopic.php?t=19242) — confirmed SRC/DST/SPT/DPT/IN/OUT field names
- [Suricata EVE JSON Output docs (8.0)](https://docs.suricata.io/en/suricata-8.0.0/output/eve/eve-json-format.html) — event type structure (403 on fetch; data cross-verified via DeepWiki summary)
- [DeepWiki Suricata EVE JSON summary](https://deepwiki.com/victorjulien/suricata/7.1-eve-json-output) — alert severity scale, metadata structure
- [Python asyncio UDP docs](https://docs.python.org/3/library/asyncio-protocol.html) — `create_datagram_endpoint`, Windows `reuse_port` limitation

### Tertiary (LOW confidence)
- [Python asyncio `reuse_port` Windows limitation](https://bugs.python.org/issue37228) — confirmed not supported on Windows; single source but consistent with docs

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries already in project, no new deps
- Architecture patterns: HIGH — direct derivation from `OsqueryCollector` template
- IPFire log format: MEDIUM — community forum examples, not official docs; real device testing will validate
- Suricata EVE format: MEDIUM — official docs (403 fetch) verified via secondary source; existing fixture cross-validates alert/flow/dns/http structure
- MITRE metadata fields: LOW — `mitre_attack_id`/`mitre_tactic_name` are ET Pro conventions, not Suricata core; may differ in actual deployment ruleset

**Research date:** 2026-04-03
**Valid until:** 2026-05-03 (stable domain; syslog format changes infrequently)
