# Phase 36: Zeek Full Telemetry — Research

**Researched:** 2026-04-10
**Domain:** Zeek NSM log normalization, Malcolm OpenSearch, DuckDB schema migration
**Confidence:** HIGH (all findings derived from direct codebase inspection)

---

## Summary

Phase 36 expands the Malcolm collector from its current 6-type EVE-based poll (alerts, syslog, TLS, DNS, fileinfo, anomaly) to 26+ Zeek log types captured via the now-active SPAN port. The SPAN port is confirmed working — 6,321 Zeek documents in `arkime_sessions3-260410`. All Zeek logs land in the same `arkime_sessions3-*` index as Suricata events; they are differentiated by the `event.type` field (e.g. `"conn"`, `"dns"`, `"http"`, `"ssl"`).

The implementation pattern is fully established in `ingestion/jobs/malcolm_collector.py`. Each Zeek log type maps to: (1) a `_normalize_<type>()` method, (2) a cursor key in SQLite KV, (3) a `_fetch_index()` call in `_poll_and_ingest()`, and (4) an `_<type>_ingested` counter on the collector. New fields go into `NormalizedEvent`, `_ECS_MIGRATION_COLUMNS` in `duckdb_store.py`, and `_INSERT_SQL` in `loader.py`. The Svelte `ZEEK_CHIPS` array already exists in `EventsView.svelte` with 8 chips — it just needs its divider label updated and potentially more chips added.

**Primary recommendation:** Follow the exact Phase 31 pattern. Add fields in batches by semantic group (conn/weird, HTTP/SSL/x509/files/notice, kerberos/ntlm/ssh, smb/rdp/dce_rpc, dhcp/dns/software/known, sip/ftp/smtp/socks/tunnel/pe). Upgrade `NormalizedEvent` with new columns positioned after the 58 existing slots. Keep `_ECS_MIGRATION_COLUMNS` as the single DDL migration source. Bump `FIELD_MAP_VERSION` to `"22"`.

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| P36-T01 | Verify SPAN port delivering packets — 6321 docs confirmed | SPAN active; `arkime_sessions3-260410` confirmed; use `event.type` filter to classify log types present |
| P36-T02 | Add conn normalizer — TCP/UDP/ICMP, conn_state, duration, bytes | Zeek conn log: `network.transport`, `event.duration`, `source.bytes`, `destination.bytes`, `network.community_id`; conn_state is a Zeek enum (S0, SF, REJ, RSTO…) |
| P36-T03 | Add weird normalizer — severity: high | Zeek weird log: `zeek.weird.name`, `zeek.weird.addl`, `zeek.weird.peer`; always severity=high |
| P36-T04 | Add http, ssl, x509, files, notice normalizers | HTTP: `http.request.method`, `url.original`, `http.response.status_code`, `user_agent.original`; SSL: `tls.*` (existing columns); x509: cert subject/issuer/validity; files: `file.*`; notice: `zeek.notice.note`, `zeek.notice.msg` |
| P36-T05 | Add kerberos, ntlm, ssh normalizers | Kerberos: `zeek.kerberos.request_type`, `zeek.kerberos.client`, `zeek.kerberos.service`; NTLM: `zeek.ntlm.domain`, `zeek.ntlm.username`; SSH: `zeek.ssh.version`, `zeek.ssh.auth_success` |
| P36-T06 | Add smb_mapping, smb_files, rdp, dce_rpc normalizers | SMB: `zeek.smb_mapping.path`, `zeek.smb_files.action`, `zeek.smb_files.name`; RDP: `zeek.rdp.cookie`, `zeek.rdp.security_protocol`; DCE-RPC: `zeek.dce_rpc.endpoint`, `zeek.dce_rpc.operation` |
| P36-T07 | Add dhcp, dns (Zeek), software, known_hosts, known_services normalizers | DHCP: `zeek.dhcp.hostname`, `zeek.dhcp.assigned_ip`; DNS: reuses existing dns_* columns; software: `zeek.software.name`, `zeek.software.version`; known_hosts/services: host/port/proto inventory |
| P36-T08 | Add remaining: sip, ftp, smtp, socks, tunnel, pe | SIP: `zeek.sip.method`, `zeek.sip.uri`; FTP: `zeek.ftp.command`, `zeek.ftp.reply_code`; SMTP: `zeek.smtp.from`, `zeek.smtp.to`, `zeek.smtp.subject`; SOCKS/tunnel: proxy metadata; PE: `zeek.pe.compile_ts`, `zeek.pe.is_packed` |
| P36-T09 | Expand NormalizedEvent with conn_state, duration, bytes | Add 4 new fields: `conn_state TEXT`, `conn_duration FLOAT`, `conn_orig_bytes INTEGER`, `conn_resp_bytes INTEGER` — positions 59-62 in to_duckdb_row() |
| P36-T10 | Update EventsView chips | ZEEK_CHIPS already exists with 8 chips (Connection/HTTP/SSL/SMB/Auth/SSH/SMTP/DHCP); add missing: Weird/Files/Notice/FTP/SMTP/RDP; update divider label from "Phase 36" to "Zeek" |
| P36-T11 | Update Sigma field_map.py for all new Zeek fields | Add conn_state, conn_duration, zeek.ssh.auth_success, zeek.kerberos.client, zeek.ntlm.username, smb path/action, rdp.security_protocol; bump FIELD_MAP_VERSION 21→22 |
| P36-T12 | End-to-end smoke test — 15+ Zeek log types in DuckDB | Verify 15+ distinct event_type values from Zeek appear in normalized_events via SELECT DISTINCT event_type |
</phase_requirements>

---

## Standard Stack

### Core (already in project)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| httpx | project dep | HTTP calls to Malcolm OpenSearch (verify=False for self-signed TLS) | Already used in MalcolmCollector._http_search() |
| duckdb | project dep | normalized_events schema storage | Single-writer pattern via execute_write() |
| pydantic | project dep | NormalizedEvent model | All parsers use it |
| asyncio.to_thread | stdlib | Wraps all blocking I/O | CLAUDE.md requirement |

### No New Dependencies Required
Phase 36 adds normalizer methods and schema columns only. No new pip packages needed — the entire implementation follows the patterns already in place from Phase 31.

---

## Architecture Patterns

### The Phase 31 Normalizer Pattern (established, HIGH confidence)

Every Zeek log type follows this exact 5-step pattern:

**Step 1 — Add `_normalize_<type>()` method to `MalcolmCollector`:**
```python
def _normalize_conn(self, doc: dict) -> NormalizedEvent | None:
    src_ip = (
        (doc.get("source") or {}).get("ip")
        or doc.get("src_ip")
        or doc.get("srcip")
    )
    if not src_ip:
        return None  # Drop events with no source IP

    # Extract Zeek-specific fields
    network_obj = doc.get("network") or {}
    conn_state = (
        (doc.get("zeek") or {}).get("conn", {}).get("state")
        or doc.get("zeek.conn.state")
        or network_obj.get("state")
    )
    duration_raw = (
        network_obj.get("duration")
        or doc.get("event", {}).get("duration")
    )

    raw_ts = doc.get("@timestamp", "")
    try:
        ts = datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        ts = datetime.now(timezone.utc)

    return NormalizedEvent(
        event_id=str(uuid4()),
        timestamp=ts,
        ingested_at=datetime.now(timezone.utc),
        source_type="zeek",
        hostname=(doc.get("observer") or {}).get("hostname") or "malcolm",
        event_type="conn",
        severity="info",
        detection_source="zeek_conn",
        raw_event=json.dumps(doc)[:8192],
        src_ip=str(src_ip),
        dst_ip=str((doc.get("destination") or {}).get("ip") or doc.get("dst_ip") or ""),
        src_port=int(p) if (p := (doc.get("source") or {}).get("port")) else None,
        dst_port=int(p) if (p := (doc.get("destination") or {}).get("port")) else None,
        network_protocol=str(network_obj.get("transport") or "").lower() or None,
        conn_state=str(conn_state) if conn_state else None,
        conn_duration=float(duration_raw) if duration_raw is not None else None,
        conn_orig_bytes=int(ob) if (ob := network_obj.get("bytes")) else None,
    )
```

**Step 2 — Add counter and cursor key to `_poll_and_ingest()`:**
```python
# In __init__:
self._conn_ingested: int = 0

# In _poll_and_ingest():
conn_hits = await self._fetch_index(
    "arkime_sessions3-*",
    "malcolm.conn.last_timestamp",
    event_type_filter="conn",
)
conn_batch = [e for h in conn_hits if (e := self._normalize_conn(h.get("_source", {})))]
if conn_batch and self._loader:
    await self._loader.ingest_events(conn_batch)
    self._conn_ingested += len(conn_batch)
```

**Step 3 — Add new columns to `NormalizedEvent` in `backend/models/event.py`:**
```python
# Phase 36: Zeek conn/protocol fields — positions 59-62 in to_duckdb_row()
conn_state: Optional[str] = None
conn_duration: Optional[float] = None
conn_orig_bytes: Optional[int] = None
conn_resp_bytes: Optional[int] = None
# ... additional fields per log type
```

**Step 4 — Add entries to `_ECS_MIGRATION_COLUMNS` in `backend/stores/duckdb_store.py`:**
```python
# Phase 36: Zeek full telemetry columns
("conn_state",        "TEXT"),
("conn_duration",     "FLOAT"),
("conn_orig_bytes",   "INTEGER"),
("conn_resp_bytes",   "INTEGER"),
# ... etc
```

**Step 5 — Extend `_INSERT_SQL` in `ingestion/loader.py` and `to_duckdb_row()` in `event.py`:**
Add new column names to INSERT list and matching `?` placeholders. Add new field values to the return tuple in `to_duckdb_row()`. These MUST stay in sync — same order, same count.

### Recommended Project Structure (additions to existing layout)

```
ingestion/jobs/malcolm_collector.py   # add _normalize_conn/weird/http/ssl/x509/
                                      # files/notice/kerberos/ntlm/ssh/smb/rdp/
                                      # dce_rpc/dhcp/dns_zeek/software/known_hosts/
                                      # known_services/sip/ftp/smtp/socks/tunnel/pe()
backend/models/event.py               # add conn_state, conn_duration, conn_orig_bytes,
                                      # conn_resp_bytes + 10-15 more new fields
backend/stores/duckdb_store.py        # extend _ECS_MIGRATION_COLUMNS
ingestion/loader.py                   # extend _INSERT_SQL column list + ? count
detections/field_map.py               # add ~20 new Zeek field mappings
dashboard/src/views/EventsView.svelte # update ZEEK_CHIPS + divider label
```

### Malcolm OpenSearch Field Structure (Malcolm/ECS hybrid)

Malcolm stores Zeek data as ECS-mapped fields plus `zeek.*` namespace for protocol-specific data. Both paths must be checked with `or` fallbacks:

```python
# Pattern for all Zeek protocol-specific fields:
zeek_obj = doc.get("zeek") or {}
protocol_obj = zeek_obj.get("conn") or {}   # or "http", "ssl", "dns", etc.

field_value = (
    protocol_obj.get("state")              # Nested ECS/Zeek: zeek.conn.state
    or doc.get("zeek.conn.state")          # Dotted flat fallback
    or doc.get("state")                    # Arkime flat fallback
)
```

Malcolm sometimes flattens nested ECS objects; always check both nested dict and dotted-key flat forms.

### Zeek Log Type → event.type Mapping

| Zeek Log | event.type Value | source_type | detection_source |
|----------|-----------------|-------------|------------------|
| conn.log | `"conn"` | `"zeek"` | `"zeek_conn"` |
| weird.log | `"weird"` | `"zeek"` | `"zeek_weird"` |
| http.log | `"http"` | `"zeek"` | `"zeek_http"` |
| ssl.log | `"ssl"` | `"zeek"` | `"zeek_ssl"` |
| x509.log | `"x509"` | `"zeek"` | `"zeek_x509"` |
| files.log | `"files"` | `"zeek"` | `"zeek_files"` |
| notice.log | `"notice"` | `"zeek"` | `"zeek_notice"` |
| dns.log | `"dns_query"` | `"zeek"` | `"zeek_dns"` |
| dhcp.log | `"dhcp"` | `"zeek"` | `"zeek_dhcp"` |
| ssh.log | `"ssh"` | `"zeek"` | `"zeek_ssh"` |
| kerberos.log | `"kerberos_tgs_request"` | `"zeek"` | `"zeek_kerberos"` |
| ntlm.log | `"ntlm_auth"` | `"zeek"` | `"zeek_ntlm"` |
| smb_mapping.log | `"smb_mapping"` | `"zeek"` | `"zeek_smb_mapping"` |
| smb_files.log | `"smb_files"` | `"zeek"` | `"zeek_smb_files"` |
| rdp.log | `"rdp"` | `"zeek"` | `"zeek_rdp"` |
| dce_rpc.log | `"dce_rpc"` | `"zeek"` | `"zeek_dce_rpc"` |
| software.log | `"software"` | `"zeek"` | `"zeek_software"` |
| known_hosts.log | `"known_host"` | `"zeek"` | `"zeek_known_hosts"` |
| known_services.log | `"known_service"` | `"zeek"` | `"zeek_known_services"` |
| intel.log | `"intel"` | `"zeek"` | `"zeek_intel"` |
| sip.log | `"sip"` | `"zeek"` | `"zeek_sip"` |
| ftp.log | `"ftp"` | `"zeek"` | `"zeek_ftp"` |
| smtp.log | `"smtp"` | `"zeek"` | `"zeek_smtp"` |
| socks.log | `"socks"` | `"zeek"` | `"zeek_socks"` |
| tunnel.log | `"tunnel"` | `"zeek"` | `"zeek_tunnel"` |
| pe.log | `"pe"` | `"zeek"` | `"zeek_pe"` |

Note: `dns_query` reuses existing OCSF_CLASS_UID_MAP entry (4003). New event types `conn`, `http`, `ssl`, etc. need entries added to OCSF_CLASS_UID_MAP in `event.py`.

### New NormalizedEvent Fields to Add (Phase 36)

The current schema ends at position 57 (ioc_actor_tag). Phase 36 adds columns 58–72+:

| Field Name | Type | Zeek Source |
|------------|------|-------------|
| `conn_state` | TEXT | `zeek.conn.state` / conn_state |
| `conn_duration` | FLOAT | `event.duration` / network.duration |
| `conn_orig_bytes` | INTEGER | `source.bytes` |
| `conn_resp_bytes` | INTEGER | `destination.bytes` |
| `zeek_notice_note` | TEXT | `zeek.notice.note` |
| `zeek_notice_msg` | TEXT | `zeek.notice.msg` |
| `zeek_weird_name` | TEXT | `zeek.weird.name` |
| `ssh_auth_success` | BOOLEAN | `zeek.ssh.auth_success` |
| `ssh_version` | INTEGER | `zeek.ssh.version` |
| `kerberos_client` | TEXT | `zeek.kerberos.client` |
| `kerberos_service` | TEXT | `zeek.kerberos.service` |
| `ntlm_domain` | TEXT | `zeek.ntlm.domain` |
| `ntlm_username` | TEXT | `zeek.ntlm.username` |
| `smb_path` | TEXT | `zeek.smb_mapping.path` |
| `smb_action` | TEXT | `zeek.smb_files.action` |
| `rdp_cookie` | TEXT | `zeek.rdp.cookie` |
| `rdp_security_protocol` | TEXT | `zeek.rdp.security_protocol` |

The exact column count depends on which fields are included during planning. Keep it to the highest-value fields (the ones that power Sigma rules or chip filters).

### EventsView ZEEK_CHIPS — Current State and Changes Needed

Current state (already wired, active since Phase 35-01):
```typescript
const ZEEK_CHIPS = [
  { label: 'Connection', value: 'conn' },
  { label: 'HTTP',       value: 'http' },
  { label: 'SSL',        value: 'ssl' },
  { label: 'SMB',        value: 'smb' },   // needs split into smb_mapping/smb_files or keep 'smb'
  { label: 'Auth',       value: 'auth' },  // not a real event_type — needs fixing
  { label: 'SSH',        value: 'ssh' },
  { label: 'SMTP',       value: 'smtp' },
  { label: 'DHCP',       value: 'dhcp' },
]
```

Issues to fix:
- `value: 'auth'` does not match any normalizer event_type — consider `'kerberos_tgs_request'` or split into Kerberos/NTLM chips, or use a multi-value filter
- `value: 'smb'` does not match `smb_mapping` or `smb_files` — pick one or add both
- Divider label still says "Phase 36" — update to "Zeek"
- New chips to add: Weird, Notice, RDP, FTP, Files (optional — keep chip row manageable)

Recommended chip value alignment:
```typescript
{ label: 'Connection', value: 'conn' },
{ label: 'HTTP',       value: 'http' },
{ label: 'SSL',        value: 'ssl' },
{ label: 'SSH',        value: 'ssh' },
{ label: 'SMB',        value: 'smb_files' },
{ label: 'Kerberos',   value: 'kerberos_tgs_request' },
{ label: 'NTLM',       value: 'ntlm_auth' },
{ label: 'RDP',        value: 'rdp' },
{ label: 'DHCP',       value: 'dhcp' },
{ label: 'SMTP',       value: 'smtp' },
{ label: 'Weird',      value: 'weird' },
{ label: 'Notice',     value: 'notice' },
```

### DuckDB Migration Pattern (HIGH confidence, from duckdb_store.py)

DuckDB does NOT support `ADD COLUMN IF NOT EXISTS`. Idempotency is via `try/except`:

```python
# In _ECS_MIGRATION_COLUMNS (extend existing list):
# Phase 36: Zeek full telemetry columns
("conn_state",             "TEXT"),
("conn_duration",          "FLOAT"),
("conn_orig_bytes",        "INTEGER"),
("conn_resp_bytes",        "INTEGER"),
("zeek_notice_note",       "TEXT"),
("zeek_notice_msg",        "TEXT"),
("zeek_weird_name",        "TEXT"),
("ssh_auth_success",       "BOOLEAN"),
("ssh_version",            "INTEGER"),
("kerberos_client",        "TEXT"),
("kerberos_service",       "TEXT"),
("ntlm_domain",            "TEXT"),
("ntlm_username",          "TEXT"),
("smb_path",               "TEXT"),
("smb_action",             "TEXT"),
("rdp_cookie",             "TEXT"),
("rdp_security_protocol",  "TEXT"),
```

The loop in `initialise_schema()` already handles these automatically — no additional code needed in `DuckDBStore`.

### OCSF_CLASS_UID_MAP Additions

Add these entries in `backend/models/event.py`:
```python
# Zeek telemetry types added Phase 36
"conn":                   4001,   # Network Activity
"http":                   4002,   # HTTP Activity
"ssl":                    4001,   # Network Activity (TLS)
"x509":                   4001,
"files":                  1001,   # File System Activity
"notice":                 2001,   # Security Finding
"weird":                  2001,   # Security Finding
"ssh":                    3002,   # Authentication
"smb_mapping":            4001,
"smb_files":              1001,
"rdp":                    3002,
"dce_rpc":                4001,
"dhcp":                   4001,
"software":               5001,   # Inventory Info (approximate)
"known_host":             5001,
"known_service":          5001,
"intel":                  2001,
"sip":                    4001,
"ftp":                    4001,
"smtp":                   4002,   # Email Activity
"socks":                  4001,
"tunnel":                 4001,
"pe":                     1001,
```

### Sigma field_map.py Additions (FIELD_MAP_VERSION → "22")

```python
# Phase 36: Zeek full telemetry field mappings
"zeek.conn.state":              "conn_state",
"network.community_id":         "detection_source",  # approximate
"zeek.weird.name":              "zeek_weird_name",
"zeek.notice.note":             "zeek_notice_note",
"zeek.notice.msg":              "zeek_notice_msg",
"zeek.ssh.auth_success":        "ssh_auth_success",
"zeek.ssh.version":             "ssh_version",
"zeek.kerberos.client":         "kerberos_client",
"zeek.kerberos.service":        "kerberos_service",
"zeek.ntlm.username":           "ntlm_username",
"zeek.ntlm.domain":             "ntlm_domain",
"zeek.smb_mapping.path":        "smb_path",
"zeek.smb_files.action":        "smb_action",
"zeek.rdp.security_protocol":   "rdp_security_protocol",
"zeek.rdp.cookie":              "rdp_cookie",
```

### Anti-Patterns to Avoid

- **Don't create separate index per Zeek log type.** All Zeek logs are in `arkime_sessions3-*`. Use `event_type_filter` parameter of `_fetch_index()`.
- **Don't redefine `_fetch_index()` or `_build_query()`.** They already handle all cases.
- **Don't add a separate source_type per Zeek log.** Use `source_type="zeek"` uniformly across all normalizers — only `event_type` and `detection_source` distinguish them.
- **Don't mix SMB chips.** `value: 'smb'` in ZEEK_CHIPS will return zero results — use `smb_mapping` or `smb_files`.
- **Don't store arrays in DuckDB columns.** Keep `dns_answers` pattern (JSON string) for any multi-value fields (e.g. smtp.to recipients).
- **Don't forget to update `_INSERT_SQL` column count.** The `?` placeholder count must exactly match `to_duckdb_row()` tuple length. A count mismatch causes silent DuckDB errors.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| OpenSearch auth | Custom auth handler | httpx `auth=(user, pass)` tuple | Already working in `_http_search()` |
| SSL verification bypass | Custom SSL context | `verify=False` in httpx call | Already done — Malcolm uses self-signed cert |
| Cursor tracking | File/memory cursors | SQLite KV via `get_kv`/`set_kv` | Established pattern, survives restarts |
| Batch ingestion | Direct DuckDB INSERT | `self._loader.ingest_events(batch)` | Handles dedup, Chroma embed, IOC match, asset upsert |
| DuckDB migrations | CREATE TABLE with all columns | `_ECS_MIGRATION_COLUMNS` try/except ALTER | DuckDB has no ADD COLUMN IF NOT EXISTS |

---

## Common Pitfalls

### Pitfall 1: event.type vs zeek.log_type vs source.dataset
**What goes wrong:** `_fetch_index()` is called with `event_type_filter="conn"` but Malcolm indexes some Zeek conn records under `event.type = "flow"` or has no `event.type` at all.
**Why it happens:** Malcolm uses ECS `event.type` but not uniformly — some log types use `event.dataset = "zeek.conn"` instead.
**How to avoid:** If initial polls return zero results for a log type, add a secondary query using `event.dataset` filter. Check `doc.get("event", {}).get("dataset")` in normalizers as fallback indicator.
**Warning signs:** `_conn_ingested` stays 0 after several poll cycles despite SPAN being active.

### Pitfall 2: Flat vs Nested Field Access
**What goes wrong:** Zeek fields accessed as `doc["zeek"]["conn"]["state"]` crash with `KeyError`; accessing as `doc.get("zeek.conn.state")` returns None because Malcolm uses nested dicts, not dotted keys.
**Why it happens:** Malcolm ECS mapping is inconsistent — some fields are nested objects, some are dotted flat strings depending on the Zeek package version.
**How to avoid:** Always use the triple-fallback pattern: `(doc.get("zeek") or {}).get("conn", {}).get("state") or doc.get("zeek.conn.state") or doc.get("state")`.

### Pitfall 3: _INSERT_SQL / to_duckdb_row() Desync
**What goes wrong:** Adding new columns to NormalizedEvent but forgetting to update both `_INSERT_SQL` in `loader.py` and the return tuple in `to_duckdb_row()` in `event.py`. Symptoms: silent DuckDB "column count mismatch" errors, or new fields always NULL.
**Why it happens:** Three locations must stay in sync: model field, `_INSERT_SQL` column list, `to_duckdb_row()` tuple.
**How to avoid:** Make all three changes in the same commit. Write a test that verifies `len(NormalizedEvent(...).to_duckdb_row())` equals the `?` count in `_INSERT_SQL`.

### Pitfall 4: Auth Chip value='auth' Returns No Results
**What goes wrong:** The existing ZEEK_CHIPS has `{ label: 'Auth', value: 'auth' }` but no normalizer produces `event_type='auth'`.
**Why it happens:** The chip was added as a placeholder in Phase 31 with an approximate value.
**How to avoid:** Replace `'auth'` with actual event_type values: `'kerberos_tgs_request'` and `'ntlm_auth'`, or add a backend multi-value filter (out of scope for this phase — just fix the value).

### Pitfall 5: 500 Document Fetch Limit Missed
**What goes wrong:** `_build_query()` has `"size": 500` hardcoded. High-traffic conn.log may accumulate thousands of events between 30s polls, causing cursor to stall at the 500-event page boundary.
**Why it happens:** The limit was acceptable for alerts; conn.log is orders of magnitude more verbose.
**How to avoid:** For conn.log specifically, consider increasing size to 1000 or implementing pagination. Alternatively, accept the 500/cycle limit for phase 36 and note it as a known limitation.

### Pitfall 6: status() Dict Missing New Counters
**What goes wrong:** New `_<type>_ingested` counters added to `__init__` but not returned in `status()`.
**Why it happens:** Easy to forget since status() is manual.
**How to avoid:** Add all new counters to `status()` return dict in same commit.

---

## Code Examples

### Verified: _fetch_index usage from Phase 31
```python
# Source: ingestion/jobs/malcolm_collector.py lines 656-669
tls_hits = await self._fetch_index(
    "arkime_sessions3-*",
    "malcolm.tls.last_timestamp",
    event_dataset_filter=False,
    event_type_filter="tls",
)
```
Phase 36 reuses this exact call signature with new event_type_filter values.

### Verified: _ECS_MIGRATION_COLUMNS extension from Phase 33
```python
# Source: backend/stores/duckdb_store.py lines 246-249
# Phase 33: IOC matching columns
("ioc_matched",          "BOOLEAN DEFAULT FALSE"),
("ioc_confidence",       "INTEGER"),
("ioc_actor_tag",        "TEXT"),
```
Phase 36 appends more entries after line 249 in the same list.

### Verified: NormalizedEvent field positions
```
Current to_duckdb_row() positions: 0-57 (58 elements)
Phase 36 adds: positions 58-74+ (exact count TBD by planner)
```

### Verified: loader.py _INSERT_SQL structure
```python
# Source: ingestion/loader.py lines 60-93
# Pattern: column names in INSERT, then matching ? placeholders
# Phase 36: extend both lists by the same count
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `source_type="suricata_eve"` for all Malcolm events | `source_type="zeek"` for Zeek events | Phase 36 | Enables filtering Zeek vs Suricata in EventsView |
| 6 event types from Malcolm | 26+ event types | Phase 36 | Full network visibility |
| ZEEK_CHIPS disabled/dashed | ZEEK_CHIPS active (Phase 35-01) | Phase 35 | Chips are already clickable — just need correct event_type values to match |
| `FIELD_MAP_VERSION = "21"` | `FIELD_MAP_VERSION = "22"` | Phase 36 | After adding new Zeek field mappings |

---

## Open Questions

1. **Which event.type values does Malcolm actually use for Zeek conn vs flow?**
   - What we know: `_build_query()` filters on `event.type` via `event_type_filter`
   - What's unclear: Malcolm may index conn.log under `"flow"` not `"conn"` depending on the ECS normalization pipeline version
   - Recommendation: In plan 1 or plan 2, perform a quick OpenSearch aggregation query to confirm the actual `event.type` values present. Query: `GET arkime_sessions3-*/_search?size=0` with `{"aggs": {"types": {"terms": {"field": "event.type", "size": 50}}}}`

2. **How verbose is conn.log at SPAN capture rate?**
   - What we know: 6,321 total docs since switch install; SPAN mirrors port 1 only (one LAN segment)
   - What's unclear: How many of those 6,321 are conn vs other types; at what rate new conn events accumulate
   - Recommendation: Accept 500-event page limit for Phase 36. Document known limitation. If conn.log saturates, address in Phase 37.

3. **Does _build_query() need a `event.dataset` filter fallback?**
   - What we know: Current implementation filters on `event.type` only
   - What's unclear: Whether all Zeek log types set `event.type` or only `event.dataset`
   - Recommendation: Add `event.dataset` as a secondary option in the query builder if `event_type_filter` returns zero results after phase goes live.

---

## Validation Architecture

**nyquist_validation:** enabled (config.json `workflow.nyquist_validation: true`)

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (uv run pytest) |
| Config file | pyproject.toml (pytest-asyncio mode: auto) |
| Quick run command | `uv run pytest tests/unit/test_malcolm_collector.py tests/unit/test_normalized_event.py -x` |
| Full suite command | `uv run pytest` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| P36-T01 | SPAN confirmed — 6321 docs | manual | n/a — already verified | ✅ (done) |
| P36-T02 | _normalize_conn() extracts conn_state, duration, bytes | unit | `uv run pytest tests/unit/test_malcolm_collector.py::test_normalize_conn -x` | ❌ Wave 0 |
| P36-T03 | _normalize_weird() sets severity=high | unit | `uv run pytest tests/unit/test_malcolm_collector.py::test_normalize_weird -x` | ❌ Wave 0 |
| P36-T04 | _normalize_http/ssl/x509/files/notice() extract fields | unit | `uv run pytest tests/unit/test_malcolm_collector.py -k "http or ssl or x509 or files or notice" -x` | ❌ Wave 0 |
| P36-T05 | _normalize_kerberos/ntlm/ssh() extract auth fields | unit | `uv run pytest tests/unit/test_malcolm_collector.py -k "kerberos or ntlm or ssh" -x` | ❌ Wave 0 |
| P36-T06 | _normalize_smb/rdp/dce_rpc() extract lateral movement fields | unit | `uv run pytest tests/unit/test_malcolm_collector.py -k "smb or rdp or dce_rpc" -x` | ❌ Wave 0 |
| P36-T07 | _normalize_dhcp/dns_zeek/software/known_hosts/known_services() | unit | `uv run pytest tests/unit/test_malcolm_collector.py -k "dhcp or software or known" -x` | ❌ Wave 0 |
| P36-T08 | _normalize_sip/ftp/smtp/socks/tunnel/pe() | unit | `uv run pytest tests/unit/test_malcolm_collector.py -k "sip or ftp or smtp or socks or tunnel or pe" -x` | ❌ Wave 0 |
| P36-T09 | NormalizedEvent has conn_state/duration/bytes fields; to_duckdb_row() tuple count matches _INSERT_SQL | unit | `uv run pytest tests/unit/test_normalized_event.py -k "conn" -x` | ❌ Wave 0 |
| P36-T10 | ZEEK_CHIPS values match normalizer event_type strings | unit (TypeScript/manual) | `cd dashboard && npm run check` | ✅ (npm check) |
| P36-T11 | SIGMA_FIELD_MAP contains new Zeek field keys | unit | `uv run pytest tests/unit/test_field_map.py -x` | ✅ (extend existing) |
| P36-T12 | 15+ distinct Zeek event_type values in DuckDB | smoke/integration | `uv run pytest tests/unit/test_malcolm_collector.py::test_poll_zeek_cursor_keys -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/unit/test_malcolm_collector.py tests/unit/test_normalized_event.py tests/unit/test_field_map.py -x`
- **Per wave merge:** `uv run pytest`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/unit/test_malcolm_collector.py` — add 20+ new test functions for each Zeek normalizer method (file exists, needs extension)
- [ ] `tests/unit/test_normalized_event.py` — add test for conn_state/duration/bytes fields + to_duckdb_row() length check (file exists, needs extension)
- [ ] `tests/unit/test_field_map.py` — add test cases for new Zeek field entries (file exists, needs extension)

All three test files already exist — Wave 0 work is additive only (no new files needed, just new test functions).

---

## Sources

### Primary (HIGH confidence)
- `ingestion/jobs/malcolm_collector.py` — complete normalizer pattern for all existing EVE types; cursor key naming; poll loop structure
- `backend/models/event.py` — NormalizedEvent schema, `to_duckdb_row()` column order (58 positions), OCSF_CLASS_UID_MAP
- `backend/stores/duckdb_store.py` — `_ECS_MIGRATION_COLUMNS` list, migration loop, DuckDB try/except idempotency
- `ingestion/loader.py` — `_INSERT_SQL` column list and `?` count (must stay in sync with event.py)
- `detections/field_map.py` — `SIGMA_FIELD_MAP` structure, `FIELD_MAP_VERSION = "21"`
- `dashboard/src/views/EventsView.svelte` — `ZEEK_CHIPS` array, chip UI pattern, `selectedChip` reactive filter
- `tests/unit/test_malcolm_collector.py` — established test pattern for all normalizer methods

### Secondary (MEDIUM confidence)
- Malcolm NSM documentation (ECS field mappings): Zeek logs are ECS-normalized with `zeek.*` namespace for protocol-specific fields
- Zeek log format documentation: conn.log fields include ts, uid, id.orig_h, id.resp_h, proto, service, duration, orig_bytes, resp_bytes, conn_state

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all implementation uses existing dependencies
- Architecture (normalizer pattern): HIGH — exact pattern verified in existing code
- DuckDB migration pattern: HIGH — `_ECS_MIGRATION_COLUMNS` mechanism is confirmed and working
- Zeek field names in Malcolm: MEDIUM — field names verified against ECS spec and Malcolm docs; actual nested vs flat varies by Malcolm version; fallback pattern handles this
- ZEEK_CHIPS fix needed: HIGH — `value: 'auth'` confirmed to not match any event_type

**Research date:** 2026-04-10
**Valid until:** 2026-05-10 (stable codebase; only changes if Malcolm version updates)
