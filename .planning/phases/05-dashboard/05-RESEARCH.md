# Phase 5: Suricata Detection + ATT&CK Scoring — Research

**Researched:** 2026-03-16
**Domain:** Suricata EVE JSON, threat scoring, ATT&CK tagging, FastAPI model extension, Svelte 5 UI
**Confidence:** HIGH (all findings verified against codebase + official Suricata docs)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- Suricata infra: add to docker-compose.yml if feasible; if not (Windows/resource) scaffold with documented blocker and validate with fixture EVE JSON only
- Config: `infra/suricata/` (suricata.yaml, rules/)
- EVE JSON log path: `/var/log/suricata/eve.json`
- New parser: `backend/src/parsers/suricata_parser.py` with `parse_eve_line(line: str) -> dict`
- Handles: alert, flow, dns, http, tls; falls back gracefully for unknown types
- Wired via `source=IngestSource.suricata` (new enum value)
- Vector: add `suricata_eve` file source + `normalise_suricata` transform + `backend_suricata` sink
- EVE field mapping is LOCKED (see table below — verbatim from CONTEXT.md)
- `IngestSource.suricata = "suricata"` — add to `backend/src/api/models.py`
- Threat scoring model is LOCKED (additive, 0–100, stored as `Alert.threat_score: int = 0`)
- ATT&CK tagging is LOCKED (static lookup table, 5 mappings, returns `[]` for unmapped)
- `Alert` extension is LOCKED: add `threat_score: int = 0` and `attack_tags: list[dict] = []`
- All existing endpoints unchanged; `GET /alerts` extended with new fields
- UI: threat score badge (green/yellow/red), ATT&CK pill badges, highlight score > 60
- Fixture: `fixtures/suricata_eve_sample.ndjson` with one of each event type
- Feature branch: `feature/ai-soc-phase5-suricata`

**Locked EVE field mapping:**
| EVE field | Normalized field |
|-----------|-----------------|
| `timestamp` | `timestamp` |
| `src_ip` | `src_ip` |
| `src_port` | `port` (source port; dest_port in `raw`) |
| `dest_ip` | `dst_ip` |
| `dest_port` | stored in `raw.dest_port` |
| `proto` | `protocol` |
| `hostname` / `dns.rrname` | `query` (DNS) or stored in `raw` |
| `alert.signature` | `event_type` for alert events |
| `alert.category` | `raw.category` |
| `alert.severity` | mapped to normalized severity (1→critical, 2→high, 3→medium, 4→low) |
| `flow_id` | `raw.flow_id` |
| host value from `host` field | `host` |

**Locked threat scoring model:**
```
base_score = 0
+ suricata_severity_points:  critical=40, high=30, medium=20, low=10, none=0
+ sigma_hit: +20 if event has any sigma-matched alert
+ recurrence: +10 if same host/IP seen >=3 times in event store
+ graph_connectivity: +10 if host/IP node has >=3 edges in graph
Score capped at 100
```
Model file: `backend/src/detection/threat_scorer.py` — `score_alert(alert, events, graph_data) -> int`

**Locked ATT&CK mappings:**
- category "DNS Request" or event_type "dns_query" → `{"tactic": "Command and Control", "technique": "T1071.004"}`
- category "Potentially Bad Traffic" or suspicious outbound → `{"tactic": "Exfiltration", "technique": "T1048"}`
- category "Network Trojan" → `{"tactic": "Command and Control", "technique": "T1095"}`
- Sigma rule `suspicious_dns_query` → `{"tactic": "Command and Control", "technique": "T1071.004"}`
- high-severity syslog → `{"tactic": "Impact", "technique": "T1499"}`

### Claude's Discretion
- Whether `GET /threats` endpoint is added (add if straightforward)
- Exact color thresholds for threat score badge
- Whether scoring runs synchronously in `_store_event` (prefer sync — simpler)
- Suricata docker-compose service: use `jasonish/suricata` or document blocker
- Test fixture design (event counts, specific signatures used)

### Deferred Ideas (OUT OF SCOPE)
- Full ATT&CK framework coverage
- Machine learning-based threat scoring
- Suricata rule management UI
- Live Suricata rule update pipeline
- PCAP capture and analysis
- AI Q&A / `/query` endpoint with Ollama (now Phase 6)
- Full dashboard tab navigation (Phase 6)
- Case management module (Phase 6)
- D3.js timeline performance optimization (Phase 6)
- Cytoscape dagre layout polish (Phase 6)
</user_constraints>

---

## Summary

Phase 5 adds Suricata EVE JSON as a new ingestion source, extends the `Alert` model with threat scoring and ATT&CK tagging, and surfaces this data in the existing Svelte 5 dashboard. All work is additive — no existing tests break.

The codebase already has a clean pattern for adding parsers (`syslog_parser.py`), extending the `IngestSource` enum, and calling detection/enrichment from `_store_event()`. Phase 5 follows all three patterns. The `_store_event()` function in `routes.py` is the single integration point where scoring and ATT&CK tagging are called after rule evaluation.

The `jasonish/suricata` Docker image requires `--net=host` and kernel capabilities (`net_admin`, `net_raw`, `sys_nice`) that are unavailable in Docker Desktop for Windows. The correct call is: scaffold the service config in `infra/suricata/` and `docker-compose.yml` with a documented blocker comment, then validate entirely via `fixtures/suricata_eve_sample.ndjson`. This is fully supported by the project architecture since the `/ingest` endpoint accepts batched events from any source.

**Primary recommendation:** Implement parser → model extension → scorer → ATT&CK mapper → route wiring → UI badges as five sequential deliverables. Use TDD: write `test_phase5.py` stubs first, then implement each deliverable until all tests pass.

---

## Standard Stack

### Core (no new dependencies required)

| Component | Current Version | Purpose | Notes |
|-----------|----------------|---------|-------|
| FastAPI + Pydantic | already installed | Model extension, routes | Adding fields to `Alert` is non-breaking with defaults |
| Python stdlib `json` | stdlib | EVE JSON parsing | Each EVE line is valid JSON; `json.loads()` is sufficient |
| Python stdlib `uuid` | stdlib | Alert IDs | Same as existing `rules.py` pattern |
| Svelte 5 | already installed | Badge rendering | Runes pattern already established |

### No New Python Packages Needed
The EVE parser uses only `json` (stdlib) and `datetime` (stdlib). No `suricata-update`, `pysuricata`, or other packages are needed. HIGH confidence — verified by reading the existing codebase.

### Fixture Only (no Docker needed for tests)
Suricata EVE JSON fixture data is sufficient to test all deliverables. The full Suricata container is a runtime enhancement only.

---

## Architecture Patterns

### Existing Pattern: Adding a Parser

The `syslog_parser.py` pattern is the canonical template:
- Module-level function: `parse_X_line(line: str) -> dict`
- Returns a raw dict compatible with `normalize()` in `normalizer.py`
- `normalize()` already maps: `event`, `event_type`, `host`, `src_ip`, `dst_ip`, `query`, `port`, `protocol`, `severity`, `user`, `raw`
- Unknown fields go into `raw=raw` (the full input dict is passed as `raw`)

```python
# Pattern from syslog_parser.py — suricata_parser.py follows same shape
def parse_eve_line(line: str) -> dict:
    """Parse a single Suricata EVE JSON line.

    Returns a raw dict compatible with normalize() — same keys as syslog_parser.
    Falls back to a generic dict for unknown event_type values (no crash).
    """
    data = json.loads(line)
    event_type = data.get("event_type", "unknown")
    # ... map EVE fields to normalized keys ...
    return result
```

### Existing Pattern: Extending IngestSource Enum

`IngestSource` is in `backend/src/api/models.py` at line 20–24. Add one line:

```python
class IngestSource(str, Enum):
    fixture = "fixture"
    syslog = "syslog"
    vector = "vector"
    api = "api"
    suricata = "suricata"   # Phase 5 addition
```

**Critical:** `HealthResponse.ingestion_sources` returns `sorted(_active_sources)` — adding a new enum value automatically makes it visible in `/health` without any other changes. The `routes.py` `ingest_batch` handler already handles unknown source strings gracefully via `try/except ValueError`.

### Existing Pattern: Extending Alert Model

`Alert` is in `backend/src/api/models.py` at lines 80–87. All existing tests use:
```python
Alert(id=..., timestamp=..., rule=..., severity=..., event_id=..., description=...)
```
Adding `threat_score: int = 0` and `attack_tags: list[dict] = []` with defaults does not break any existing test. Both fields appear in `GET /alerts` automatically via `model_dump()`.

```python
class Alert(BaseModel):
    id: str
    timestamp: str
    rule: str
    severity: str
    event_id: str
    description: str
    # Phase 5 additions — both have defaults, no existing test breaks
    threat_score: int = 0
    attack_tags: list[dict] = Field(default_factory=list)
```

### Existing Pattern: Wiring into _store_event()

`_store_event()` in `routes.py` is the single integration point. The Phase 3 pattern of adding Sigma rule evaluation shows exactly how to add new processing steps after rule evaluation:

```python
def _store_event(event: NormalizedEvent) -> list[Alert]:
    """Persist event + run detection. Returns triggered alerts."""
    _events.append(event.model_dump())
    _active_sources.add(event.source.value)
    new_alerts = evaluate(event)
    # Phase 3: Sigma rules
    for sigma_fn in _SIGMA_RULES:
        try:
            result = sigma_fn(event)
            if result is not None:
                new_alerts.append(result)
        except Exception:
            pass

    # Phase 5: Score alerts and add ATT&CK tags — AFTER all detection
    from backend.src.detection.threat_scorer import score_alert
    from backend.src.detection.attack_mapper import map_attack_tags
    for alert in new_alerts:
        alert.threat_score = score_alert(alert, _events, _alerts)
        alert.attack_tags = map_attack_tags(alert, event)

    _alerts.extend(a.model_dump() for a in new_alerts)
    # ... SSE push, OpenSearch index ...
    return new_alerts
```

**Import strategy to avoid circular imports:** Use deferred (local) imports inside the function body, exactly as `sigma_loader.py` uses `from backend.src.api.models import Alert as _Alert` inside the inner function. Both `threat_scorer.py` and `attack_mapper.py` import only `Alert` and `NormalizedEvent` from `models.py` — no circular dependency.

### Graph Enrichment: No Changes Required

`build_graph()` in `builder.py` already reads `_events` and `_alerts` from the in-memory store. Suricata events normalized to `NormalizedEvent` with valid `host`, `src_ip`, `dst_ip`, `query`, `event_type` fields will automatically produce nodes and edges via `_extract_nodes()` and `_extract_edges()`. The `event_type` field must be one of: `dns`, `dns_query`, `connection` for specific edges to be emitted. The EVE parser should map Suricata event types accordingly.

### EVE Event Type → Normalized event_type Mapping

| Suricata event_type | Normalized event_type | Graph impact |
|--------------------|----------------------|-------------|
| `alert` | `alert.signature` value (e.g. "ET MALWARE CobaltStrike") | produces host node |
| `flow` | `connection` | produces src_ip→dst_ip edge |
| `dns` | `dns_query` | produces host→domain edge |
| `http` | `http_request` | produces host node |
| `tls` | `tls_session` | produces host node |
| unknown | `suricata_{event_type}` | produces host node |

### Recommended Project Structure (new files only)

```
backend/src/
  parsers/
    suricata_parser.py    # NEW: parse_eve_line(line) -> dict
  detection/
    threat_scorer.py      # NEW: score_alert(alert, events, graph_data) -> int
    attack_mapper.py      # NEW: map_attack_tags(alert, event) -> list[dict]

infra/
  suricata/
    suricata.yaml         # NEW: scaffold config (documented blocker)
    rules/
      local.rules         # NEW: empty placeholder

fixtures/
  suricata_eve_sample.ndjson  # NEW: 5+ EVE lines (one per event type)

backend/src/tests/
  test_phase5.py          # NEW: TDD stubs + implementation tests
```

### Anti-Patterns to Avoid

- **Do not import `threat_scorer` or `attack_mapper` at module level in `routes.py`**: This creates circular import risk since `routes.py` already imports from `models.py` and detection modules. Use deferred imports inside `_store_event()`.
- **Do not modify `_alert()` helper in `rules.py`**: The existing `_alert()` function creates Alert with the old fields; the new fields have defaults and are set after creation in `_store_event()`. Do not push scoring logic into individual rule functions.
- **Do not change GraphEdge src/dst naming**: Phase 4 locked `src`/`dst` (not `source`/`target`). `ThreatGraph.svelte` maps `e.src` and `e.dst` to Cytoscape's `source`/`target` — changing this breaks the graph view.
- **Do not use `suricata_event_type` as the normalized `event_type` field for alert events**: For alert events, use `alert.signature` as the event_type so existing enrichment and Sigma rules can match on it. This is what the CONTEXT.md field mapping specifies.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| EVE JSON parsing | Custom streaming parser | `json.loads()` per line | EVE is newline-delimited JSON; each line is a complete valid JSON object |
| ATT&CK taxonomy lookup | Full ATT&CK STIX/TAXII integration | Static dict in `attack_mapper.py` | Scope is 5 mappings; full coverage is explicitly deferred |
| Severity normalization | Float-based risk model | Simple additive int 0–100 | Model is LOCKED; complexity is explicitly deferred |
| Docker networking for Suricata | Custom bridge or host networking workaround | Document blocker, use fixture only | Windows Docker Desktop lacks `NFQUEUE` kernel module; not fixable |

---

## Common Pitfalls

### Pitfall 1: Suricata Severity is Inverted (1 = High, Not Low)
**What goes wrong:** Developer assumes 1 = lowest priority (like HTTP status codes or syslog DEBUG=7).
**Why it happens:** Suricata follows Snort convention where severity 1 = highest priority alert (critical malware), severity 4 = lowest priority (informational). This is the opposite of common intuition.
**How to avoid:** CONTEXT.md and research both confirm: `1→critical, 2→high, 3→medium, 4→low`. Assert this in tests.
**Warning signs:** Alert severity shows "low" when EVE says `"severity": 1`.

### Pitfall 2: EVE Uses `dest_ip` / `dest_port`, Not `dst_ip` / `dst_port`
**What goes wrong:** Parser maps `data.get("dst_ip")` which returns None; dst_ip is always None in parsed events.
**Why it happens:** Suricata EVE uses `dest_ip` (not `dst_ip`) and `dest_port` (not `dst_port`). The normalized schema uses `dst_ip`.
**How to avoid:** In `parse_eve_line`, explicitly map: `dst_ip = data.get("dest_ip")`. Store `dest_port` in raw.
**Warning signs:** All Suricata connection events have None dst_ip in the graph — no IP nodes emitted.

### Pitfall 3: Alert Model Extension Breaks Existing _alert() Factory
**What goes wrong:** Existing `_alert()` helper in `rules.py` creates Alert objects; if Alert gains required fields without defaults, all existing tests fail.
**Why it happens:** Pydantic raises ValidationError when required fields are missing at construction time.
**How to avoid:** Both `threat_score` and `attack_tags` MUST have defaults (`= 0` and `= Field(default_factory=list)`). Verified this is the CONTEXT.md design.
**Warning signs:** All 41 existing tests fail with `ValidationError: threat_score field required`.

### Pitfall 4: Deferred Import vs Module-Level Import in routes.py
**What goes wrong:** Adding `from backend.src.detection.threat_scorer import score_alert` at module level in `routes.py` causes `ImportError` at backend startup if `threat_scorer.py` doesn't exist yet (during incremental development).
**Why it happens:** `routes.py` loads at startup; module-level imports run immediately.
**How to avoid:** Use `try/except ImportError` guard at module level (same pattern as `_SIGMA_RULES` load) OR use deferred import inside `_store_event()`. The deferred import inside the function is cleaner for Phase 5 since it mirrors the Sigma approach of graceful degradation.
**Warning signs:** Backend fails to start during early plan execution.

### Pitfall 5: Graph Connectivity Score Requires graph_data to be Pre-Built
**What goes wrong:** `score_alert(alert, _events, _alerts)` is called inside `_store_event()`, but calling `build_graph(_events, _alerts)` inside `score_alert()` for every single event is O(n) per event = O(n²) total ingestion cost.
**Why it happens:** The graph connectivity check (`+10 if host/IP node has >=3 edges`) requires the current graph state.
**How to avoid:** Pass `_alerts` (not a pre-built graph) to `score_alert()`; `score_alert()` computes edge count by counting existing alerts for the same host/IP rather than building the full graph. This is O(n) per event but avoids the full graph build. Alternatively, pass `None` for `graph_data` and skip the connectivity check (score 0 for that component).
**Recommendation:** Accept `graph_data: dict | None = None` in `score_alert()`; when None, skip the `+10` graph connectivity component. This keeps scoring fast and correct.
**Warning signs:** Ingesting 100 events takes 10+ seconds due to graph rebuild per event.

### Pitfall 6: IngestSource enum expansion and existing test `source_label_preserved`
**What goes wrong:** Adding `suricata` enum value could affect test that checks `source == "syslog"` if route handler changes default source.
**Why it happens:** `ingest_batch()` falls back to `IngestSource.api` for unknown source strings. Adding `suricata` doesn't affect existing behavior.
**How to avoid:** Only add the enum value; don't change fallback logic.
**Warning signs:** `test_source_label_preserved` fails after enum extension.

---

## Suricata EVE JSON — Verified Field Reference

### Common Fields (All EVE Events)
| EVE Field | Type | Notes |
|-----------|------|-------|
| `timestamp` | string | ISO 8601, e.g., `"2024-01-15T12:34:56.789012+0000"` |
| `event_type` | string | `"alert"`, `"flow"`, `"dns"`, `"http"`, `"tls"`, `"anomaly"`, `"fileinfo"` |
| `flow_id` | integer | Unique flow identifier; correlates events across types |
| `src_ip` | string | Source IP address |
| `src_port` | integer | Source port (absent for ICMP) |
| `dest_ip` | string | Destination IP (NOT `dst_ip`) |
| `dest_port` | integer | Destination port (NOT `dst_port`) |
| `proto` | string | `"TCP"`, `"UDP"`, `"ICMP"` |
| `host` | string | Hostname of the sensor (from suricata.yaml `host-id`) |

### Alert-Specific Fields (`event_type: "alert"`)
| EVE Field | Type | Notes |
|-----------|------|-------|
| `alert.signature` | string | Rule message, e.g., `"ET MALWARE CobaltStrike Beacon"` |
| `alert.signature_id` | integer | Snort/Suricata SID |
| `alert.category` | string | Rule category, e.g., `"Malware Command and Control Activity Detected"` |
| `alert.severity` | integer | **1=critical, 2=high, 3=medium, 4=low** (Snort convention, inverted from intuition) |
| `alert.action` | string | `"allowed"` or `"blocked"` (IPS mode only) |
| `alert.gid` | integer | Generator ID (almost always 1) |
| `alert.rev` | integer | Rule revision |

### DNS-Specific Fields (`event_type: "dns"`)
| EVE Field | Type | Notes |
|-----------|------|-------|
| `dns.type` | string | `"query"` or `"answer"` |
| `dns.rrname` | string | The queried hostname, e.g., `"malware.example.com"` |
| `dns.rrtype` | string | Record type: `"A"`, `"AAAA"`, `"CNAME"`, `"MX"`, `"TXT"` |
| `dns.rdata` | string | Answer data (responses only) |
| `dns.id` | integer | DNS transaction ID |

### HTTP-Specific Fields (`event_type: "http"`)
| EVE Field | Type | Notes |
|-----------|------|-------|
| `http.hostname` | string | HTTP Host header value |
| `http.url` | string | Request URI |
| `http.http_method` | string | `"GET"`, `"POST"`, etc. |
| `http.status` | integer | HTTP response code |
| `http.length` | integer | Response body length |

### TLS-Specific Fields (`event_type: "tls"`)
| EVE Field | Type | Notes |
|-----------|------|-------|
| `tls.subject` | string | Certificate subject |
| `tls.issuerdn` | string | Certificate issuer |
| `tls.sni` | string | Server Name Indication |
| `tls.fingerprint` | string | Certificate SHA1 fingerprint |
| `tls.version` | string | TLS version string |

### Flow-Specific Fields (`event_type: "flow"`)
| EVE Field | Type | Notes |
|-----------|------|-------|
| `flow.pkts_toserver` | integer | Packets toward server |
| `flow.pkts_toclient` | integer | Packets toward client |
| `flow.bytes_toserver` | integer | Bytes toward server |
| `flow.bytes_toclient` | integer | Bytes toward client |
| `flow.start` | string | Flow start timestamp |
| `flow.end` | string | Flow end timestamp |

Source: [Suricata 7.0.11 EVE JSON Format](https://docs.suricata.io/en/suricata-7.0.11/output/eve/eve-json-format.html) — HIGH confidence.

---

## Code Examples

### parse_eve_line() — Complete Implementation Pattern

```python
# backend/src/parsers/suricata_parser.py
import json
from datetime import datetime, timezone

_SEVERITY_MAP = {1: "critical", 2: "high", 3: "medium", 4: "low"}


def parse_eve_line(line: str) -> dict:
    """Parse a single Suricata EVE JSON line into normalized-compatible dict.

    Handles: alert, flow, dns, http, tls.
    Falls back to generic normalization for unknown event_type (no crash).
    Always returns a dict suitable for normalize() in normalizer.py.
    """
    try:
        data = json.loads(line.strip())
    except (json.JSONDecodeError, ValueError):
        return {
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            "host": "unknown",
            "event_type": "parse_error",
            "severity": "info",
            "raw_format": "suricata_eve",
        }

    event_type = data.get("event_type", "unknown")
    # EVE uses dest_ip / dest_port; normalize to dst_ip (schema uses dst_ip)
    result: dict = {
        "timestamp": data.get("timestamp", ""),
        "host": data.get("host", "unknown"),
        "src_ip": data.get("src_ip"),
        "dst_ip": data.get("dest_ip"),      # NOTE: EVE uses dest_ip not dst_ip
        "port": data.get("src_port"),        # primary port = src_port per CONTEXT.md
        "protocol": data.get("proto", "").lower() if data.get("proto") else None,
        "severity": "info",
        "raw_format": "suricata_eve",
        # Full EVE record preserved in raw for downstream use
        "raw": data,
    }

    if event_type == "alert":
        alert = data.get("alert", {})
        result["event_type"] = alert.get("signature", "suricata_alert")
        sev_int = alert.get("severity", 3)
        result["severity"] = _SEVERITY_MAP.get(sev_int, "medium")
        result["raw"]["category"] = alert.get("category", "")
        result["raw"]["dest_port"] = data.get("dest_port")

    elif event_type == "dns":
        dns = data.get("dns", {})
        result["event_type"] = "dns_query"
        result["query"] = dns.get("rrname") or data.get("hostname")
        result["raw"]["dest_port"] = data.get("dest_port")

    elif event_type == "flow":
        result["event_type"] = "connection"
        result["dst_ip"] = data.get("dest_ip")
        result["raw"]["dest_port"] = data.get("dest_port")

    elif event_type == "http":
        http = data.get("http", {})
        result["event_type"] = "http_request"
        result["query"] = http.get("hostname") or http.get("url")
        result["raw"]["dest_port"] = data.get("dest_port")

    elif event_type == "tls":
        tls = data.get("tls", {})
        result["event_type"] = "tls_session"
        result["query"] = tls.get("sni") or tls.get("subject")
        result["raw"]["dest_port"] = data.get("dest_port")

    else:
        # Unknown event_type — generic fallback (no crash)
        result["event_type"] = f"suricata_{event_type}"
        result["raw"]["dest_port"] = data.get("dest_port")

    # flow_id for correlation
    if data.get("flow_id"):
        result["raw"]["flow_id"] = data["flow_id"]

    return result
```

### score_alert() — Implementation Pattern

```python
# backend/src/detection/threat_scorer.py

def score_alert(
    alert,          # Alert model instance
    events: list[dict],
    graph_data: dict | None = None,
) -> int:
    """Compute threat score 0-100 using additive model from CONTEXT.md.

    Components:
      + suricata_severity_points: critical=40, high=30, medium=20, low=10
      + sigma_hit: +20 if alert.rule matches UUID pattern (sigma-sourced)
      + recurrence: +10 if same host/IP seen >= 3 times in events
      + graph_connectivity: +10 if host/IP appears in >= 3 existing alerts
    """
    import re
    _UUID_PATTERN = re.compile(
        r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
        re.IGNORECASE,
    )
    # ... implementation ...
    return min(score, 100)
```

### attack_mapper.py — Implementation Pattern

```python
# backend/src/detection/attack_mapper.py
from backend.src.api.models import Alert, NormalizedEvent

# Static mapping table (simplified — not full ATT&CK coverage)
# Maps alert categories + event types + rule IDs to ATT&CK tactic/technique
_CATEGORY_MAP: dict[str, dict] = {
    "dns request": {"tactic": "Command and Control", "technique": "T1071.004"},
    "potentially bad traffic": {"tactic": "Exfiltration", "technique": "T1048"},
    "network trojan": {"tactic": "Command and Control", "technique": "T1095"},
}

_EVENT_TYPE_MAP: dict[str, dict] = {
    "dns_query": {"tactic": "Command and Control", "technique": "T1071.004"},
}

_RULE_MAP: dict[str, dict] = {
    # Sigma rule ID from suspicious_dns.yml
    "suspicious_dns_query": {"tactic": "Command and Control", "technique": "T1071.004"},
}

_SOURCE_SEVERITY_MAP: dict[tuple, dict] = {
    # (source, severity) -> tag
    ("syslog", "critical"): {"tactic": "Impact", "technique": "T1499"},
    ("syslog", "high"): {"tactic": "Impact", "technique": "T1499"},
}


def map_attack_tags(alert: Alert, event: NormalizedEvent) -> list[dict]:
    """Map alert to ATT&CK tactic/technique labels.

    Returns [] for unmapped events — no guessing.
    """
    # ... implementation using above maps ...
```

### Fixture Sample — suricata_eve_sample.ndjson

Each line is a complete EVE record. Must include one of each event type:

```json
{"timestamp":"2026-03-16T10:00:00.000000+0000","event_type":"alert","src_ip":"192.168.1.50","src_port":54321,"dest_ip":"203.0.113.100","dest_port":443,"proto":"TCP","alert":{"action":"allowed","gid":1,"signature_id":2014726,"rev":7,"signature":"ET MALWARE CobaltStrike Beacon","category":"Malware Command and Control Activity Detected","severity":1},"flow_id":123456789,"host":"suricata-sensor"}
{"timestamp":"2026-03-16T10:00:05.000000+0000","event_type":"dns","src_ip":"192.168.1.50","src_port":12345,"dest_ip":"8.8.8.8","dest_port":53,"proto":"UDP","dns":{"type":"query","id":1234,"rrname":"suspicious-domain.test","rrtype":"A"},"flow_id":123456790,"host":"suricata-sensor"}
{"timestamp":"2026-03-16T10:00:10.000000+0000","event_type":"flow","src_ip":"192.168.1.50","src_port":49152,"dest_ip":"198.51.100.1","dest_port":4444,"proto":"TCP","flow":{"pkts_toserver":5,"pkts_toclient":3,"bytes_toserver":400,"bytes_toclient":200,"start":"2026-03-16T10:00:08.000000+0000","end":"2026-03-16T10:00:10.000000+0000"},"flow_id":123456791,"host":"suricata-sensor"}
{"timestamp":"2026-03-16T10:00:15.000000+0000","event_type":"http","src_ip":"192.168.1.50","src_port":56789,"dest_ip":"203.0.113.200","dest_port":80,"proto":"TCP","http":{"hostname":"malware.example","url":"/stage2/payload.exe","http_method":"GET","status":200,"length":1048576},"flow_id":123456792,"host":"suricata-sensor"}
{"timestamp":"2026-03-16T10:00:20.000000+0000","event_type":"tls","src_ip":"192.168.1.50","src_port":55000,"dest_ip":"203.0.113.100","dest_port":443,"proto":"TCP","tls":{"subject":"C=US, ST=CA, O=Malicious Corp","issuerdn":"C=US, ST=CA, O=Malicious Corp","sni":"c2.evil.test","fingerprint":"ab:cd:ef:01:23:45:67:89:ab:cd:ef:01:23:45:67:89:ab:cd:ef:01","version":"TLS 1.2"},"flow_id":123456789,"host":"suricata-sensor"}
```

**Design rationale:**
- Alert has `severity: 1` (critical) to trigger `suricata_severity_points=40`
- DNS queries `suspicious-domain.test` — matches existing Sigma rule (triggers `+20 sigma_hit`)
- Flow connects to `198.51.100.1` — in existing `SUSPICIOUS_IPS` set
- HTTP event has `malware.example` hostname — matches `SUSPICIOUS_DOMAINS`
- All events share `host: "suricata-sensor"` and `src_ip: "192.168.1.50"` — triggers recurrence check

### Vector Pipeline Extension Pattern

The existing `vector.yaml` scaffold pattern:

```yaml
# Add inside sources: block
  # ---- SCAFFOLD: Suricata EVE JSON file source ----------------------------
  # Uncomment and set include path when Suricata is running.
  # On Windows with Docker Desktop, Suricata cannot run in Docker
  # (missing NFQUEUE kernel module). Use fixture data for testing.
  #
  # suricata_eve:
  #   type: file
  #   include:
  #     - /var/log/suricata/eve.json
  #   read_from: beginning
  #   data_dir: /tmp/vector-suricata-data
  # -------------------------------------------------------------------------

# Add inside transforms: block
  # normalise_suricata:
  #   type: remap
  #   inputs:
  #     - suricata_eve
  #   source: |
  #     .source = "suricata"

# Add inside sinks: block
  # backend_suricata:
  #   type: http
  #   inputs:
  #     - normalise_suricata
  #   uri: "http://backend:8000/ingest"
  #   method: post
  #   encoding:
  #     codec: json
  #   batch:
  #     max_events: 50
  #     timeout_secs: 5
  #   request:
  #     headers:
  #       Content-Type: application/json
```

### Docker-Compose Scaffold for Suricata

```yaml
  # ---- SCAFFOLD: Suricata IDS service ------------------------------------
  # BLOCKER: jasonish/suricata requires --net=host and Linux kernel
  # capabilities (net_admin, net_raw, sys_nice) that Docker Desktop for
  # Windows does not provide. The NFQUEUE kernel module is unavailable in
  # WSL2. Suricata cannot monitor host network interfaces from this config.
  #
  # For live Suricata detection, deploy on a Linux gateway/sensor host.
  # For this project: validate entirely with fixtures/suricata_eve_sample.ndjson.
  #
  # suricata:
  #   image: jasonish/suricata:latest
  #   cap_add:
  #     - net_admin
  #     - net_raw
  #     - sys_nice
  #   network_mode: host   # required for interface monitoring
  #   volumes:
  #     - ./suricata/suricata.yaml:/etc/suricata/suricata.yaml:ro
  #     - ./suricata/rules:/etc/suricata/rules:ro
  #     - suricata_logs:/var/log/suricata
  #   command: ["-c", "/etc/suricata/suricata.yaml", "-i", "eth0"]
  # -------------------------------------------------------------------------
```

### EvidencePanel.svelte Extension Pattern

The current `EvidencePanel.svelte` (35 lines) renders `selected.id`, `selected.type`, `selected.label`, etc. The addition follows the existing `{#if selected.X}` conditional pattern:

```svelte
<!-- Add after existing fields, before the {:else} block -->
{#if selected.threat_score && selected.threat_score > 0}
  <div class="field">
    <span class="key">Score</span>
    <span class="val">
      <span class="score-badge score-{selected.threat_score > 60 ? 'red' : selected.threat_score >= 30 ? 'yellow' : 'green'}">
        {selected.threat_score}
      </span>
    </span>
  </div>
{/if}

{#if selected.attack_tags && selected.attack_tags.length > 0}
  <div class="field field-column">
    <span class="key">ATT&CK</span>
    <div class="tags">
      {#each selected.attack_tags as tag}
        <span class="attack-pill">{tag.tactic} · {tag.technique}</span>
      {/each}
    </div>
  </div>
{/if}
```

### api.ts Extension Pattern

```typescript
// Update getAlerts() return type
export interface AlertItem {
  id: string
  timestamp: string
  rule: string
  severity: string
  event_id: string
  description: string
  threat_score: number          // Phase 5: default 0
  attack_tags: Array<{ tactic: string; technique: string }>  // Phase 5: default []
}

export async function getAlerts(): Promise<AlertItem[]> {
  const r = await fetch(`${BASE}/alerts`)
  return r.json()
}

// Optional: GET /threats — alerts sorted by score desc, score > 0
export async function getThreats(): Promise<AlertItem[]> {
  const r = await fetch(`${BASE}/threats`)
  return r.json()
}
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Suricata rules as pattern-only IDS | Suricata as event source feeding existing pipeline | Phase 5 | No separate rules engine; EVE events normalized like any other source |
| ATT&CK mapping via full TAXII/STIX | Static lookup table | Phase 5 | Scoped to 5 mappings; full coverage is Phase 6+ |
| Threat score as ML model output | Additive integer formula | Phase 5 | Simple, deterministic, testable; ML is explicitly deferred |

**What Phase 5 does NOT do (deferred):**
- Full ATT&CK matrix coverage — static 5-mapping table only
- Machine learning scoring
- PCAP analysis
- Live Suricata on Windows (scaffold only)

---

## Open Questions

1. **`score_alert()` graph_connectivity parameter**
   - What we know: Scoring should add +10 if host/IP has >=3 edges in graph
   - What's unclear: Building the graph inside `score_alert()` for every event is O(n²); but `_alerts` alone can approximate connectivity
   - Recommendation: Use `graph_data: dict | None = None`; when None skip the +10 (acceptable tradeoff vs. performance). Planner should design `score_alert` signature accordingly.

2. **`GET /threats` endpoint**
   - What we know: CONTEXT.md marks this as Claude's Discretion
   - What's unclear: Whether it adds meaningful value vs. just filtering `/alerts` client-side
   - Recommendation: Add it — it's 5 lines in routes.py and gives analysts a direct "highest priority alerts" view. Include in plan if scope permits.

3. **Alert left-rail in App.svelte shows `alert.rule` not `alert.description`**
   - What we know: `App.svelte` line 99 renders `alert.rule`; the alert left-rail shows 30 alerts max
   - What's unclear: Should the left-rail also show the threat score badge?
   - Recommendation: Yes — add the score badge to the left-rail alert item as well (same component pattern as EvidencePanel). Document in plan.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (auto mode, set in pyproject.toml) |
| Config file | `pyproject.toml` — `[tool.pytest.ini_options]` |
| Quick run command | `uv run pytest backend/src/tests/test_phase5.py -x` |
| Full suite command | `uv run pytest backend/src/tests/ -v` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| P5-T1 | `parse_eve_line` parses alert event correctly | unit | `pytest test_phase5.py::TestSuricataParser::test_parse_alert_event -x` | Wave 0 |
| P5-T2 | `parse_eve_line` parses dns event, maps `dest_ip` → `dst_ip` | unit | `pytest test_phase5.py::TestSuricataParser::test_parse_dns_event -x` | Wave 0 |
| P5-T3 | `parse_eve_line` parses flow event | unit | `pytest test_phase5.py::TestSuricataParser::test_parse_flow_event -x` | Wave 0 |
| P5-T4 | `parse_eve_line` parses http event | unit | `pytest test_phase5.py::TestSuricataParser::test_parse_http_event -x` | Wave 0 |
| P5-T5 | `parse_eve_line` parses tls event | unit | `pytest test_phase5.py::TestSuricataParser::test_parse_tls_event -x` | Wave 0 |
| P5-T6 | `parse_eve_line` handles unknown event_type gracefully (no crash) | unit | `pytest test_phase5.py::TestSuricataParser::test_parse_unknown_event_no_crash -x` | Wave 0 |
| P5-T7 | EVE severity 1 maps to "critical", 4 maps to "low" | unit | `pytest test_phase5.py::TestSuricataParser::test_severity_mapping -x` | Wave 0 |
| P5-T8 | `IngestSource.suricata` value is `"suricata"` | unit | `pytest test_phase5.py::TestModels::test_ingest_source_suricata -x` | Wave 0 |
| P5-T9 | `Alert.threat_score` defaults to 0, `Alert.attack_tags` defaults to `[]` | unit | `pytest test_phase5.py::TestModels::test_alert_new_fields_defaults -x` | Wave 0 |
| P5-T10 | All existing 41 tests still pass after model extension | regression | `uv run pytest backend/src/tests/ -v` | Existing |
| P5-T11 | `score_alert` returns 40 for critical suricata alert with no other factors | unit | `pytest test_phase5.py::TestThreatScorer::test_score_critical_suricata -x` | Wave 0 |
| P5-T12 | `score_alert` adds +20 for sigma-matched alert (UUID rule) | unit | `pytest test_phase5.py::TestThreatScorer::test_score_sigma_hit -x` | Wave 0 |
| P5-T13 | `score_alert` caps at 100 | unit | `pytest test_phase5.py::TestThreatScorer::test_score_capped_at_100 -x` | Wave 0 |
| P5-T14 | `map_attack_tags` returns C2/T1071.004 for dns_query event | unit | `pytest test_phase5.py::TestAttackMapper::test_dns_query_maps_to_c2 -x` | Wave 0 |
| P5-T15 | `map_attack_tags` returns `[]` for unmapped event | unit | `pytest test_phase5.py::TestAttackMapper::test_unmapped_returns_empty_list -x` | Wave 0 |
| P5-T16 | POST /ingest with `source=suricata` EVE lines accepted, alerts contain threat_score | integration | `pytest test_phase5.py::TestSuricataRoute::test_ingest_suricata_source -x` | Wave 0 |
| P5-T17 | GET /alerts response includes `threat_score` and `attack_tags` fields | integration | `pytest test_phase5.py::TestSuricataRoute::test_alerts_have_new_fields -x` | Wave 0 |
| P5-T18 | POST Suricata alert with critical severity, suspicious dns query → score >= 60 | integration | `pytest test_phase5.py::TestSuricataRoute::test_high_score_for_critical_alert -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest backend/src/tests/test_phase5.py -x`
- **Per wave merge:** `uv run pytest backend/src/tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `backend/src/tests/test_phase5.py` — covers P5-T1 through P5-T18
- [ ] `backend/src/parsers/suricata_parser.py` — P5-T1 through P5-T7
- [ ] `backend/src/detection/threat_scorer.py` — P5-T11 through P5-T13
- [ ] `backend/src/detection/attack_mapper.py` — P5-T14, P5-T15
- [ ] `fixtures/suricata_eve_sample.ndjson` — used in integration tests

---

## Sources

### Primary (HIGH confidence)
- [Suricata 7.0.11 EVE JSON Format](https://docs.suricata.io/en/suricata-7.0.11/output/eve/eve-json-format.html) — field names, severity scale, event types
- Codebase direct read: `backend/src/api/models.py` — existing Alert, IngestSource, NormalizedEvent models
- Codebase direct read: `backend/src/api/routes.py` — `_store_event()` integration pattern
- Codebase direct read: `backend/src/parsers/normalizer.py` — normalize() expected keys
- Codebase direct read: `backend/src/ingestion/syslog_parser.py` — parser pattern to follow
- Codebase direct read: `backend/src/detection/rules.py` — `_alert()` factory, `_RULES` list pattern
- Codebase direct read: `backend/src/detection/sigma_loader.py` — deferred import pattern for graceful degradation
- Codebase direct read: `backend/src/tests/test_phase2.py` — TestClient + in-memory store test pattern
- Codebase direct read: `backend/src/graph/builder.py` — graph enrichment via existing `_events`/`_alerts`
- Codebase direct read: `infra/vector/vector.yaml` — SCAFFOLD comment pattern for new sources
- Codebase direct read: `infra/docker-compose.yml` — existing service structure
- Codebase direct read: `frontend/src/components/panels/EvidencePanel.svelte` — prop pattern, conditional field rendering

### Secondary (MEDIUM confidence)
- [jasonish/suricata Docker image](https://hub.docker.com/r/jasonish/suricata/) — Windows blocker confirmed via WSL2 NFQUEUE constraint
- [Docker Desktop WSL2 backend](https://docs.docker.com/desktop/features/wsl/) — confirms kernel capability constraints

### Tertiary (LOW confidence)
- None needed — all critical findings verified against primary sources

---

## Metadata

**Confidence breakdown:**
- Suricata EVE field names: HIGH — verified against official docs
- Severity inversion (1=critical): HIGH — confirmed in CONTEXT.md + official docs
- `dest_ip` vs `dst_ip` naming: HIGH — confirmed in official docs
- Import/circular dependency strategy: HIGH — directly verified in existing codebase
- Windows Docker blocker: HIGH — confirmed via jasonish/docker-suricata README + WSL2 docs
- Test patterns: HIGH — directly read from test_phase2.py and test_phase4.py
- Standard stack (no new dependencies): HIGH — confirmed stdlib-only approach sufficient

**Research date:** 2026-03-16
**Valid until:** 2026-04-16 (Suricata EVE format is stable; codebase patterns are locked)
