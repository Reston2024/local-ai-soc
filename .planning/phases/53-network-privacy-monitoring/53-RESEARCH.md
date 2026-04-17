# Phase 53: Network Privacy Monitoring - Research

**Researched:** 2026-04-17
**Domain:** Zeek HTTP log analysis, blocklist enrichment, privacy signal detection, triage pipeline integration
**Confidence:** HIGH (core architecture), MEDIUM (Zeek field availability in Malcolm), MEDIUM (blocklist parsing)

---

## Summary

Phase 53 adds two complementary privacy-violation detection streams that run against the existing Zeek HTTP telemetry already indexed in Malcolm/OpenSearch. Both streams share a common blocklist enrichment layer (EasyPrivacy + Disconnect.me) and surface findings through the existing `detection_source` tagging mechanism and the Sigma/correlation detection pipeline.

**Cookie exfiltration detection** works by querying DuckDB for `http` events (event_type='http', detection_source='zeek_http') where `request_body_len` is large AND the destination domain matches known tracker domains in the blocklist. Because Zeek's `_normalize_http()` does not currently capture `request_body_len`, `referrer`, or `cookie` fields, a schema extension is required first. Alternatively, raw_event JSON extraction via DuckDB `json_extract()` can avoid schema changes if Zeek stores those fields in the raw Malcolm document.

**Tracking pixel detection** works by querying DuckDB for `http` events with small `response_body_len` (< 100 bytes), `resp_mime_types` containing `image/gif` or `image/png`, and the destination domain matching the blocklist. The `referrer` field (already in Zeek HTTP log) is essential to establish the email-open correlation.

**Primary recommendation:** Extend `_normalize_http()` to capture 4 new fields (`http_referrer`, `http_request_body_len`, `http_response_body_len`, `http_resp_mime_type`), add those columns to DuckDB, build a `PrivacyBlocklistStore` following the existing IocStore pattern, add a `PrivacyWorker` following the `_BaseWorker` feed pattern, and detect via Python scanner (not new Sigma rules) using DuckDB queries — surfacing findings as detection records with `detection_source='privacy'`.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| httpx | already installed | Fetch EasyPrivacy/Disconnect.me lists | Already used by feed_sync.py |
| sqlite3 (stdlib) | stdlib | PrivacyBlocklistStore domain table | Matches IocStore, AttackStore patterns |
| duckdb | already installed | Query normalized_events for detections | Project write queue pattern |
| pydantic-settings | already installed | PRIVACY_* config settings | Matches all other phase settings |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| re (stdlib) | stdlib | Parse Adblock Plus `||domain^` rules | EasyPrivacy uses Adblock+ format |
| json (stdlib) | stdlib | Parse Disconnect.me services.json | Disconnect list is JSON |
| asyncio.to_thread | stdlib | Wrap synchronous blocklist DB ops | Mandatory per CLAUDE.md |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Custom regex parser | adblockparser PyPI package | adblockparser adds a dep; regex is 5 lines and handles the `||domain^` pattern used by EasyPrivacy |
| python-abp | Custom regex | python-abp is the official Adblock parser but 180KB dep for a simple extraction |
| New NormalizedEvent fields | DuckDB json_extract on raw_event | json_extract avoids schema churn but is 10-100x slower in DuckDB queries; new columns are correct |

**Installation:** No new packages required. All dependencies already present.

---

## Architecture Patterns

### Recommended Project Structure
```
backend/services/intel/
├── feed_sync.py            # Add PrivacyWorker class here (follows _BaseWorker)
├── privacy_blocklist.py    # NEW: PrivacyBlocklistStore + blocklist parsing
├── ioc_store.py            # Reference pattern
└── misp_sync.py            # Reference pattern

backend/api/
├── privacy.py              # NEW: GET /api/privacy/hits, GET /api/privacy/feeds

tests/unit/
├── test_privacy_blocklist.py    # NEW: Wave 0 stubs
├── test_privacy_detection.py    # NEW: Wave 0 stubs

detections/
└── field_map.py            # Add http_referrer, http_request_body_len, etc.

ingestion/jobs/
└── malcolm_collector.py    # Extend _normalize_http() with 4 new fields
```

### Pattern 1: Blocklist Store (follows IocStore)
**What:** SQLite table mapping domains to blocklist categories. Populated by a background worker.
**When to use:** Whenever a detection needs to check a domain against a privacy list.

```python
# Source: follows backend/services/intel/ioc_store.py pattern
class PrivacyBlocklistStore:
    """Wraps sqlite3.Connection directly — same pattern as IocStore, AttackStore."""

    _DDL = """
    CREATE TABLE IF NOT EXISTS privacy_blocklist (
        domain      TEXT PRIMARY KEY,
        category    TEXT NOT NULL,   -- 'easyprivacy', 'disconnect_email', 'disconnect_advertising'
        company     TEXT,
        last_seen   TEXT NOT NULL,
        updated_at  TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_privacy_domain ON privacy_blocklist (domain);
    CREATE TABLE IF NOT EXISTS privacy_hits (
        id              TEXT PRIMARY KEY,
        event_id        TEXT NOT NULL,
        src_ip          TEXT,
        dst_domain      TEXT NOT NULL,
        hit_type        TEXT NOT NULL,  -- 'cookie_exfil', 'tracking_pixel'
        category        TEXT NOT NULL,
        confidence      INTEGER NOT NULL,
        raw_http_uri    TEXT,
        http_referrer   TEXT,
        body_len        INTEGER,
        created_at      TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS privacy_feed_meta (
        feed        TEXT PRIMARY KEY,
        last_sync   TEXT,
        domain_count INTEGER DEFAULT 0
    );
    """
```

### Pattern 2: PrivacyWorker (follows _BaseWorker)
**What:** Background asyncio task that fetches and refreshes blocklists on a configurable interval.
**When to use:** Matches the exact pattern of FeodoWorker, CisaKevWorker, ThreatFoxWorker in feed_sync.py.

```python
# Source: backend/services/intel/feed_sync.py _BaseWorker pattern
class PrivacyWorker(_BaseWorker):
    """Fetches EasyPrivacy + Disconnect.me lists and populates privacy_blocklist."""
    _kv_key = "privacy.last_sync"
    _feed_name = "easyprivacy"

    async def _fetch(self) -> None:
        # EasyPrivacy
        resp = await asyncio.to_thread(
            httpx.get, "https://easylist.to/easylist/easyprivacy.txt", timeout=30
        )
        domains = _parse_easyprivacy(resp.text)
        # Disconnect.me
        resp2 = await asyncio.to_thread(
            httpx.get,
            "https://raw.githubusercontent.com/disconnectme/disconnect-tracking-protection/master/services.json",
            timeout=30
        )
        dc_domains = _parse_disconnect(resp2.text)
        # Upsert all into privacy_blocklist
        ...
```

### Pattern 3: Blocklist Parsing

**EasyPrivacy format:** Adblock Plus syntax. Domain-blocking rules use the `||` anchor prefix: `||tracker.example.com^`. Extraction via regex:

```python
# Source: verified from EasyList GitHub (easylist/easylist) + adblockparser PyPI docs
import re

_DOMAIN_RULE = re.compile(r'^\|\|([a-z0-9.\-]+)\^')

def _parse_easyprivacy(text: str) -> list[str]:
    """Extract domains from EasyPrivacy Adblock+ format. ~22,000 domains."""
    domains = []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith('!') or not line:  # comment or blank
            continue
        m = _DOMAIN_RULE.match(line)
        if m:
            domains.append(m.group(1).lower())
    return domains
```

**Disconnect.me format:** JSON with nested structure. Categories include Email, EmailAggressive, Advertising, Analytics, Social:

```python
# Source: verified from github.com/disconnectme/disconnect-tracking-protection services.json
import json

def _parse_disconnect(text: str) -> list[tuple[str, str]]:
    """Returns list of (domain, category) from Disconnect services.json."""
    data = json.loads(text)
    results = []
    for category, companies in data.get("categories", {}).items():
        for company_dict in companies:
            for company_name, company_data in company_dict.items():
                for url, domains in company_data.items():
                    for d in domains:
                        results.append((d.lower(), category))
    return results
```

Key Disconnect categories: `Email`, `EmailAggressive`, `Advertising`, `Analytics`, `Social`, `Content`, `Disconnect`.

### Pattern 4: Privacy Detection Scanner
**What:** A scanner function (not a Sigma rule) that queries DuckDB for privacy violations and inserts detection records. Runs on a configurable interval via APScheduler, matching how `_auto_triage_loop` works.

```python
# Source: backend/api/triage.py _run_triage pattern + backend/ingestion/loader.py

async def run_privacy_scan(app) -> dict:
    """Scan recent HTTP events for cookie exfil and tracking pixels."""
    store: DuckDBStore = app.state.duckdb_store
    privacy_store: PrivacyBlocklistStore = app.state.privacy_store
    sqlite_store = app.state.sqlite_store

    # Cookie exfil: large request body to known tracker domain
    cookie_hits = await store.fetch_all("""
        SELECT event_id, src_ip, dst_ip, domain, http_uri,
               http_referrer, http_request_body_len, timestamp
        FROM normalized_events
        WHERE event_type = 'http'
          AND http_request_body_len > 4096
          AND ingested_at > NOW() - INTERVAL '1 hour'
    """)

    # Tracking pixel: tiny GET response from known tracker to image MIME
    pixel_hits = await store.fetch_all("""
        SELECT event_id, src_ip, dst_ip, domain, http_uri,
               http_referrer, http_response_body_len, http_resp_mime_type, timestamp
        FROM normalized_events
        WHERE event_type = 'http'
          AND http_response_body_len > 0
          AND http_response_body_len < 200
          AND http_resp_mime_type IN ('image/gif', 'image/png', 'image/jpeg')
          AND ingested_at > NOW() - INTERVAL '1 hour'
    """)
    ...
```

### Anti-Patterns to Avoid
- **Writing Sigma YAML rules for privacy detection:** Sigma/pySigma backend operates on DuckDB text-match patterns. Privacy detection requires numeric body-length comparisons (`http_request_body_len > 4096`) that Sigma's DuckDB backend does not support without extensions. Use Python scanner instead.
- **Querying raw_event JSON with json_extract in DuckDB for every event:** 10-100x slower than normalized columns. Extend schema.
- **Treating Zeek `cookie` field as cookie value:** Zeek's `cookie` field in http.log contains only the **variable names** extracted from cookies (a space-separated list), not values. Cookie exfil detection should use `request_body_len` size heuristics, not cookie value inspection.
- **Using adblockparser package for parsing:** Dependency for a 5-line regex. Keep stdlib.
- **Blocking asyncio event loop with synchronous SQLite writes:** All privacy_store writes go through `asyncio.to_thread()`.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Blocklist fetch + backoff | Custom retry loop | `_BaseWorker.run()` pattern from feed_sync.py | Already handles exponential backoff, CancelledError, failure logging |
| Background scheduling | Custom thread/asyncio.create_task | APScheduler already in main.py | Consistent with triage, MISP sync scheduling |
| Detection record creation | Custom SQL INSERT | `sqlite_store.insert_detection()` | Handles MISP enrichment, TheHive hook, all extra columns |
| HTTP fetching | Manual urllib | httpx already in project | Timeouts, redirects handled |
| Domain normalization | Custom lowercase/strip | Simple `.lower().strip('.')` | No library needed |

**Key insight:** Privacy detection is structurally identical to IOC matching (blocklist lookup) + anomaly detection (threshold query). Reuse both patterns rather than building a third system.

---

## Critical Findings: Zeek HTTP Fields

### What Zeek http.log Actually Contains (HIGH confidence)
Source: Zeek official documentation (docs.zeek.org/en/master/logs/http.html, base/protocols/http/main.zeek.html)

Full Zeek http.log field list relevant to Phase 53:

| Zeek Field | Type | Description |
|------------|------|-------------|
| `ts` | time | Connection start time |
| `uid` | string | Connection UID |
| `id.orig_h` | addr | Source IP |
| `id.resp_h` | addr | Destination IP |
| `method` | string | HTTP method (GET, POST) |
| `host` | string | Value of HOST header |
| `uri` | string | URI of the request |
| `referrer` | string | Value of Referer header (spelled correctly) |
| `version` | string | HTTP protocol version |
| `user_agent` | string | Value of User-Agent header |
| `origin` | string | Value of Origin header |
| `request_body_len` | count | Actual uncompressed size of request body |
| `response_body_len` | count | Actual uncompressed size of response body |
| `status_code` | count | HTTP response status code |
| `status_msg` | string | Status message from server |
| `cookie` | string | Cookie variable names (NOT values — just names extracted) |
| `resp_mime_types` | vector of strings | MIME types of server response |
| `orig_mime_types` | vector of strings | MIME types of client body |
| `tags` | set of string | Tags associated with this request |

**Critical fact:** Zeek `cookie` field contains only extracted cookie **variable names**, not values. Example: if request has `Cookie: sessionid=abc123; csrftoken=xyz`, the `cookie` field contains `"sessionid csrftoken"`. This means Zeek-based cookie exfil detection must use `request_body_len` as the size heuristic, not cookie value inspection.

### What Malcolm Exposes in OpenSearch (MEDIUM confidence)
Source: Malcolm query cheat sheet, Corelight ECS mapping, Malcolm documentation patterns.

Malcolm/Arkime maps Zeek fields to `zeek.http.*` in OpenSearch. The ECS equivalent fields are also preserved. Based on the `_normalize_http()` code, the fields already extracted are:
- `http_method` ← `http.request.method`
- `http_uri` ← `url.original`
- `http_status_code` ← `http.response.status_code`
- `http_user_agent` ← `user_agent.original`
- `domain` ← `destination.domain`

**Fields NOT yet extracted by `_normalize_http()` that are needed for Phase 53:**
- `http_referrer` ← `zeek.http.referrer` or `http.request.referrer`
- `http_request_body_len` ← `zeek.http.request_body_len`
- `http_response_body_len` ← `zeek.http.response_body_len`
- `http_resp_mime_type` ← `zeek.http.resp_mime_types[0]` (take first entry)

All four of these fields exist in the raw Malcolm OpenSearch document. The triple-fallback pattern from Phase 36 must be used: nested dict → dotted flat key → Arkime flat key.

### Suricata EVE JSON HTTP Fields (MEDIUM confidence)
Source: Suricata EVE JSON format documentation, GitHub source.

Suricata's EVE JSON `http` event includes `cookie` as a configurable custom field. It is NOT logged by default — requires `extended: yes` + `custom: [cookie]` in suricata.yaml. Malcolm's Suricata configuration may or may not enable it.

**Recommendation:** Do NOT rely on Suricata EVE JSON for cookie data. Zeek `request_body_len` is more reliable and is always present. For cookie exfil, use Zeek HTTP log's `request_body_len` threshold query.

---

## Common Pitfalls

### Pitfall 1: Schema Column Count Desync
**What goes wrong:** Adding columns to NormalizedEvent.to_duckdb_row() without updating the DuckDB INSERT SQL in loader.py causes the entire ingest pipeline to fail at startup.
**Why it happens:** to_duckdb_row() returns a positional tuple; INSERT SQL must match exactly.
**How to avoid:** Add all 4 new columns (http_referrer, http_request_body_len, http_response_body_len, http_resp_mime_type) in a single plan. Follow the Phase 36-01 pattern: "All N columns added in single plan to prevent INSERT_SQL/to_duckdb_row desync."
**Warning signs:** DuckDB raises "Binder Error: VALUES list size mismatch" or "Expected N values but got M" at startup.

### Pitfall 2: EasyPrivacy List Size (~22,000 domains)
**What goes wrong:** Loading all ~22,000 domains into an in-memory set for every detection query causes memory pressure and slow startup.
**Why it happens:** EasyPrivacy is large compared to Feodo/ThreatFox.
**How to avoid:** Store in SQLite with an indexed `domain` TEXT column. Query with `SELECT 1 FROM privacy_blocklist WHERE domain = ?` — SQLite index lookup is O(log n), suitable for batch scanning.

### Pitfall 3: False Positives on Cookie Exfil Threshold
**What goes wrong:** `request_body_len > 4096` fires on every POST form submission and API call, flooding the detection queue.
**Why it happens:** Many legitimate POST requests exceed 4KB.
**How to avoid:** Combine three conditions: (1) request_body_len > 4096, (2) dst_domain matches privacy blocklist, (3) src_ip is an internal LAN IP (RFC 1918). Without the blocklist domain check, the rule is useless. The blocklist check is the primary signal; body length is secondary.

### Pitfall 4: Tracking Pixel MIME Type Not Set
**What goes wrong:** `resp_mime_types` is empty vector for many HTTP events because Zeek only sets it when it can detect the content type.
**Why it happens:** Tracking pixels from tracker CDNs often respond with `Content-Type: image/gif` but Zeek may log an empty `resp_mime_types` if it doesn't buffer the response.
**How to avoid:** Include a fallback condition: if `resp_mime_types` is empty but `response_body_len < 200` AND domain is in the blocklist, still flag as candidate. Two-tier detection: high-confidence (MIME confirmed) and medium-confidence (size only).

### Pitfall 5: Disconnect.me List Structure Nested Deeply
**What goes wrong:** The `services.json` categories contain companies containing URLs containing lists of domains — three levels of nesting. Partial iteration misses entries.
**Why it happens:** The JSON structure is: `{categories: {Email: [{CompanyName: {url: [domains]}}]}}`.
**How to avoid:** Use the verified `_parse_disconnect()` function pattern above which correctly iterates all four levels.

### Pitfall 6: Referrer Field Absent for Direct Email Clients
**What goes wrong:** Native email clients (Apple Mail, Outlook) do not include a Referer header when loading tracking pixels.
**Why it happens:** Referer is optional in HTTP. Email clients suppress it.
**How to avoid:** Referrer correlation is supplementary evidence, not a required signal. Detection should fire on domain match + tiny image response without requiring Referer. When Referer IS present (webmail case), it upgrades confidence.

### Pitfall 7: DuckDB NOW() in Interval Query
**What goes wrong:** DuckDB uses `CURRENT_TIMESTAMP` not `NOW()` in some contexts; `INTERVAL '1 hour'` syntax is correct in DuckDB but `NOW() - INTERVAL 1 HOUR` (MySQL syntax) fails.
**Why it happens:** DuckDB SQL dialect differences.
**How to avoid:** Use `CURRENT_TIMESTAMP - INTERVAL '1 hour'` or pass a cutoff timestamp as a parameter. Verified DuckDB supports `INTERVAL '1 hour'` ANSI syntax.

---

## Code Examples

Verified patterns from official sources and project codebase:

### Normalize Extended HTTP Fields in _normalize_http()
```python
# Source: backend/ingestion/jobs/malcolm_collector.py _normalize_http (Phase 36 pattern)
# Triple-fallback: nested dict → dotted flat key → Arkime flat key

def _normalize_http(self, doc: dict) -> NormalizedEvent | None:
    # ... existing code ...
    http_obj = (doc.get("http") or {})
    req_obj = http_obj.get("request") or {}
    resp_obj = http_obj.get("response") or {}
    zeek_http = (doc.get("zeek") or {}).get("http") or {}

    return NormalizedEvent(
        # ... existing fields ...
        # New Phase 53 fields:
        http_referrer=(
            req_obj.get("referrer")
            or zeek_http.get("referrer")
            or doc.get("zeek.http.referrer")
        ),
        http_request_body_len=_safe_int(
            req_obj.get("body", {}).get("bytes")
            or zeek_http.get("request_body_len")
            or doc.get("zeek.http.request_body_len")
        ),
        http_response_body_len=_safe_int(
            resp_obj.get("body", {}).get("bytes")
            or zeek_http.get("response_body_len")
            or doc.get("zeek.http.response_body_len")
        ),
        http_resp_mime_type=(
            (zeek_http.get("resp_mime_types") or [None])[0]
            or doc.get("zeek.http.resp_mime_types")
        ),
    )
```

### DuckDB Cookie Exfil Query
```python
# Source: project DuckDB query pattern (duckdb_store.fetch_all)
COOKIE_EXFIL_SQL = """
    SELECT event_id, src_ip, domain, http_uri,
           http_referrer, http_request_body_len, timestamp
    FROM normalized_events
    WHERE event_type = 'http'
      AND http_request_body_len > ?
      AND domain IS NOT NULL
      AND ingested_at > CURRENT_TIMESTAMP - INTERVAL '1 hour'
    ORDER BY timestamp DESC
    LIMIT 500
"""
# Then filter results: domain IN privacy_blocklist (SQLite lookup)
# Threshold: 4096 bytes default, configurable PRIVACY_COOKIE_EXFIL_THRESHOLD_BYTES
```

### DuckDB Tracking Pixel Query
```python
# Source: project DuckDB query pattern
TRACKING_PIXEL_SQL = """
    SELECT event_id, src_ip, domain, http_uri,
           http_referrer, http_response_body_len, http_resp_mime_type, timestamp
    FROM normalized_events
    WHERE event_type = 'http'
      AND http_response_body_len > 0
      AND http_response_body_len < ?
      AND (
          http_resp_mime_type IN ('image/gif', 'image/png', 'image/jpeg', 'image/webp')
          OR http_resp_mime_type IS NULL  -- fallback: use body_len alone if MIME absent
      )
      AND domain IS NOT NULL
      AND ingested_at > CURRENT_TIMESTAMP - INTERVAL '1 hour'
    ORDER BY timestamp DESC
    LIMIT 500
"""
# Threshold: 200 bytes default, configurable PRIVACY_PIXEL_MAX_BODY_BYTES
```

### Insert Detection Record
```python
# Source: backend/stores/sqlite_store.py insert_detection() pattern
# detection_source='privacy' follows Phase 48/49 pattern (detection_source='hayabusa'/'chainsaw')
sqlite_store.insert_detection(DetectionRecord(
    id=str(uuid4()),
    rule_id=f"privacy-{hit_type}",   # 'privacy-cookie_exfil' or 'privacy-tracking_pixel'
    rule_name=f"Privacy: {label}",
    severity="medium",
    matched_event_ids=json.dumps([event_id]),
    created_at=datetime.now(timezone.utc).isoformat(),
    detection_source="privacy",
))
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Sigma rules for HTTP anomalies | Python scanner with DuckDB queries | Phase 48+ | Sigma backend can't do numeric comparisons on body length |
| In-memory blocklist sets | SQLite with indexed domain column | Phase 33 (IocStore pattern) | O(log n) lookup, survives restart |
| Fetch blocklists at detection time | Background worker + SQLite cache | Phase 33 | Decouples detection latency from network I/O |
| Single detection_source | Multi-source ('sigma','hayabusa','chainsaw') | Phase 48 | Enables per-source UI filtering |

**Deprecated/outdated:**
- EasyPrivacy in ABP format (old): Domain-only mirror at justdomains.github.io is stale/low-maintenance. Use the original `easyprivacy.txt` with regex extraction.

---

## Scope Assessment

Two detection types (cookie exfil + tracking pixel) is the right scope for one phase. They share the blocklist infrastructure, DuckDB schema extension, and detection pipeline. The work breaks cleanly into:

- **Wave 0 (Plan 1):** TDD stubs + schema extension stubs
- **Wave 1 (Plan 2):** PrivacyBlocklistStore + PrivacyWorker + _normalize_http() extension
- **Wave 2 (Plan 3):** Privacy scanner + detection insertion + API endpoint
- **Wave 3 (Plan 4):** Dashboard: new "Privacy" chip in DetectionsView + feed status in ThreatIntelView

Total: 4 plans, consistent with Phases 48-52 scope.

---

## Open Questions

1. **Are `request_body_len` and `response_body_len` present in Malcolm's OpenSearch Zeek HTTP documents?**
   - What we know: These fields exist in Zeek's native http.log. Malcolm ingests Zeek logs. The triple-fallback pattern (`zeek.http.request_body_len` → dotted → Arkime) should work.
   - What's unclear: Whether Malcolm's Logstash pipeline preserves these specific numeric fields or drops them.
   - Recommendation: Plan 2 should include a one-time manual validation step: query Malcolm OpenSearch for a recent `http` document and check for `zeek.http.request_body_len`. If absent, fall back to DuckDB `json_extract(raw_event, '$.zeek.http.request_body_len')` as secondary strategy.

2. **What is `resp_mime_types` in Malcolm OpenSearch — a string or array?**
   - What we know: Zeek logs it as a vector of strings. Malcolm/ECS may serialize as array or space-joined string.
   - What's unclear: Malcolm's exact serialization of vector fields.
   - Recommendation: Normalize to first element with `or [])[0]` pattern (same approach as dns_answers which uses `json.dumps(list)`). Store as TEXT in DuckDB.

3. **Is the EasyPrivacy list stable enough to cache for 24 hours?**
   - What we know: EasyPrivacy is maintained daily to weekly. The GitHub source is the canonical version. Using a 24-hour refresh cycle is standard practice (Feodo uses 1-hour).
   - Recommendation: Default `PRIVACY_BLOCKLIST_REFRESH_INTERVAL_SEC=86400` (24h). This is appropriate given the list's update cadence.

4. **Should privacy hits flow through TheHive auto-case creation?**
   - What we know: TheHive auto-case creation (Phase 52) is triggered for High/Critical severity detections in detect.py's ingest hook.
   - Recommendation: Privacy detections should default to `severity='medium'` to avoid flooding TheHive. Add `rule_id` prefix `privacy-` to `THEHIVE_SUPPRESS_RULES` default, or let operators opt-in via config.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest + pytest-asyncio |
| Config file | `pyproject.toml` (`[tool.pytest.ini_options]` asyncio_mode = "auto") |
| Quick run command | `uv run pytest tests/unit/test_privacy_blocklist.py tests/unit/test_privacy_detection.py -x` |
| Full suite command | `uv run pytest` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PRIV-01 | EasyPrivacy Adblock+ domains parsed correctly | unit | `pytest tests/unit/test_privacy_blocklist.py::test_parse_easyprivacy -x` | ❌ Wave 0 |
| PRIV-02 | Disconnect.me services.json parsed for all categories | unit | `pytest tests/unit/test_privacy_blocklist.py::test_parse_disconnect -x` | ❌ Wave 0 |
| PRIV-03 | PrivacyBlocklistStore upserts and retrieves domains | unit | `pytest tests/unit/test_privacy_blocklist.py::test_store_upsert -x` | ❌ Wave 0 |
| PRIV-04 | PrivacyWorker fetches and populates blocklist | unit | `pytest tests/unit/test_privacy_blocklist.py::test_worker_fetch -x` | ❌ Wave 0 |
| PRIV-05 | Cookie exfil detection fires on large body + tracker domain | unit | `pytest tests/unit/test_privacy_detection.py::test_cookie_exfil_detection -x` | ❌ Wave 0 |
| PRIV-06 | Tracking pixel detection fires on tiny image + tracker domain | unit | `pytest tests/unit/test_privacy_detection.py::test_tracking_pixel_detection -x` | ❌ Wave 0 |
| PRIV-07 | Non-tracker domains do NOT trigger detection | unit | `pytest tests/unit/test_privacy_detection.py::test_no_false_positive_non_tracker -x` | ❌ Wave 0 |
| PRIV-08 | Detection records inserted with detection_source='privacy' | unit | `pytest tests/unit/test_privacy_detection.py::test_detection_source_tag -x` | ❌ Wave 0 |
| PRIV-09 | GET /api/privacy/hits returns detection list | unit | `pytest tests/unit/test_privacy_api.py::test_hits_endpoint -x` | ❌ Wave 0 |
| PRIV-10 | GET /api/privacy/feeds returns blocklist feed status | unit | `pytest tests/unit/test_privacy_api.py::test_feeds_endpoint -x` | ❌ Wave 0 |
| PRIV-11 | _normalize_http() captures http_referrer, body lengths, mime type | unit | `pytest tests/unit/test_zeek_normalizers.py::test_normalize_http_extended -x` | ❌ Wave 0 |
| PRIV-12 | Privacy chip filters in DetectionsView | manual | Visual verification in browser | N/A |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/unit/test_privacy_blocklist.py tests/unit/test_privacy_detection.py -x`
- **Per wave merge:** `uv run pytest`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/unit/test_privacy_blocklist.py` — covers PRIV-01 through PRIV-04 (PrivacyBlocklistStore + parsing)
- [ ] `tests/unit/test_privacy_detection.py` — covers PRIV-05 through PRIV-08 (cookie exfil + pixel scanner)
- [ ] `tests/unit/test_privacy_api.py` — covers PRIV-09 through PRIV-10 (API endpoints)
- [ ] DuckDB schema migration for 4 new columns — part of Plan 2, no separate test file needed (tested via existing test_duckdb_store.py patterns)
- [ ] NormalizedEvent field additions — tested via `test_normalize_http_extended` added to existing `tests/unit/test_zeek_normalizers.py`

*(No new framework install needed — pytest-asyncio already configured)*

---

## Sources

### Primary (HIGH confidence)
- Zeek official docs (docs.zeek.org/en/master/scripts/base/protocols/http/main.zeek.html) - http.log field list, cookie field semantics
- github.com/disconnectme/disconnect-tracking-protection services.json - JSON structure verified by direct fetch
- github.com/easylist/easylist README - EasyPrivacy format and download URL
- `backend/services/intel/feed_sync.py` - _BaseWorker pattern, verified from project codebase
- `backend/services/intel/ioc_store.py` - PrivacyBlocklistStore design pattern
- `ingestion/jobs/malcolm_collector.py` - _normalize_http() existing fields + triple-fallback pattern
- `detections/field_map.py` - SIGMA_FIELD_MAP extension requirements
- `backend/stores/sqlite_store.py` - insert_detection() contract
- `backend/core/config.py` - Settings extension pattern

### Secondary (MEDIUM confidence)
- docs.suricata.io EVE JSON format - Cookie field is custom/extended, not default
- Malcolm documentation (malcolm.fyi) - zeek.http.* field naming convention in OpenSearch
- Suricata GitHub source (OISF/suricata http-keywords.rst) - http.cookie Suricata rule keyword

### Tertiary (LOW confidence)
- justdomains.github.io/blocklists - EasyPrivacy domain-only count (~22,000 domains) — confirms list size for SQLite sizing decisions

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - all dependencies already installed; pattern fully established by Phase 33/48
- Architecture: HIGH - direct extension of IocStore + _BaseWorker + insert_detection() patterns
- Zeek HTTP fields: MEDIUM - fields documented in Zeek official docs but Malcolm OpenSearch serialization of `request_body_len` and `resp_mime_types` needs runtime verification
- Blocklist parsing: HIGH for Disconnect.me (JSON structure verified), MEDIUM for EasyPrivacy (Adblock+ regex pattern is standard but list may evolve)
- Pitfalls: HIGH - all identified from direct project history (schema desync, Phase 36-01 note) and established network security practice

**Research date:** 2026-04-17
**Valid until:** 2026-05-17 (30 days — blocklist URLs are stable; Zeek API is stable)
