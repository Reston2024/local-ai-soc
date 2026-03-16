# Phase 3: Detection + RAG (Scoped) — Research

**Researched:** 2026-03-15
**Domain:** OpenSearch HTTP indexing + search, Sigma YAML rule loader, detection engine integration
**Confidence:** HIGH — all findings verified against existing codebase; no external libraries added

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- OpenSearch index name: `soc-events`
- Backend must write every ingested event to `soc-events` — unconditional (remove env-var SCAFFOLD gate)
- `docker-compose.yml` backend service must set `OPENSEARCH_URL=http://opensearch:9200` and `depends_on: opensearch` with a health wait
- Endpoint: `GET /search?q=<query_string>` backed by OpenSearch multi-field query
- Returns a JSON array of matching events (same schema as `/events`)
- Vector pipeline must have an OpenSearch sink writing all ingested events to `soc-events`
- Sigma directory: `backend/src/detection/sigma/` (YAML files)
- First rule file: `suspicious_dns.yml`
- Rule loader: `backend/src/detection/sigma_loader.py`
- Detection engine reads Sigma rules in addition to the existing Python rules in `rules.py`
- Sigma rule matches must produce `Alert` objects identical in schema to those from Python rules
- All Sigma-matched alerts appear in `GET /alerts`
- `rule` field on alert = Sigma rule ID from the YAML file
- `GET /graph`, `GET /timeline`, `GET /events` — unchanged behavior
- Docker Compose stack must continue to start cleanly with `docker compose up -d --build`
- All existing 32 tests (Wave 1 + Phase 2) must continue to pass

### Claude's Discretion
- Choice of OpenSearch client library (httpx-based from Phase 2 scaffold, or `opensearch-py`)
- Sigma YAML schema (use pySigma-compatible subset or custom minimal schema)
- Search response pagination (not required in Phase 3)
- How to handle OpenSearch unavailability gracefully (log + skip, do not crash ingestion)

### Deferred Ideas (OUT OF SCOPE)
- Full pySigma DuckDB backend (custom SQL base class extension)
- LangGraph RAG pipeline + POST /query SSE endpoint
- ATT&CK technique enrichment
- Contextual anomaly detector (per-entity baselines, z-score)
- Citation verification layer
- Sigma smoke test suite (10 rules against crafted events)
</user_constraints>

---

## Summary

Phase 3 activates two capabilities that were scaffolded in Phase 2 but left gated: unconditional OpenSearch indexing and a Sigma-based rule loader. The OpenSearch sink (`backend/src/ingestion/opensearch_sink.py`) is fully implemented but guarded by an `if not OPENSEARCH_URL` check — the only required change is removing that guard and setting the env var unconditionally in `docker-compose.yml`. The Vector OpenSearch sink block already exists in `infra/vector/vector.yaml` as a commented SCAFFOLD — it needs uncommenting. The existing `detections/` package already contains a full `SigmaMatcher` implementation that loads YAML rules and produces SQL — the Phase 3 `sigma_loader.py` needs to wrap this at the `backend/src/` layer to bridge `SigmaMatcher` into the in-memory alert pipeline used by `routes.py`. The `suspicious_dns.yml` rule should match against `event.query` field, which the existing `NormalizedEvent` model already has.

The 9 failing tests visible in the test suite are all integration tests that require a live backend at `localhost:8000` — the `pytestmark = skipif` guard in `test_backend_health.py` is supposed to skip them, but the backend is accessible during CI. These are pre-existing and not regressions introduced by Phase 3.

**Primary recommendation:** Keep all work within the existing in-memory `routes.py` pipeline — do not migrate to DuckDB store. Wire OpenSearch unconditionally, add a `GET /search` route, uncomment Vector sink, write `sigma_loader.py` as a thin wrapper over the existing `SigmaMatcher` that calls `evaluate()` via the `_RULES` extension pattern in `rules.py`.

---

## Codebase Reality Check

This is critical context for the planner — all findings come from reading actual files.

### What Already Exists (Do NOT re-implement)

| File | What It Does | Phase 3 Work |
|------|-------------|--------------|
| `backend/src/ingestion/opensearch_sink.py` | httpx PUT to `/{index}/_doc/{id}`, fully working | Remove `if not OPENSEARCH_URL` guard (line 51) |
| `detections/matcher.py` (742 lines) | Full `SigmaMatcher`: YAML load, SQL compile, match | Already works; `sigma_loader.py` wraps it |
| `detections/field_map.py` | 30+ Sigma→DuckDB column mappings | Already complete |
| `fixtures/sigma/` | 3 example Sigma YAML files | Use as reference for `suspicious_dns.yml` format |
| `tests/sigma_smoke/test_sigma_matcher.py` | 16 tests for field map + matcher | Must continue to pass |
| `backend/src/detection/rules.py` | `evaluate(event) -> list[Alert]`, `_RULES` list | Extend `_RULES` with Sigma-derived rules |

### What Does NOT Yet Exist (Build in Phase 3)

| File | Purpose |
|------|---------|
| `backend/src/detection/sigma/suspicious_dns.yml` | First Sigma rule for DNS detection |
| `backend/src/detection/sigma_loader.py` | Loads YAML from `sigma/`, produces callables for `_RULES` |
| `GET /search` endpoint in `routes.py` | New route: httpx → OpenSearch `_search` |

---

## Standard Stack

### Core (already in pyproject.toml — no new dependencies needed)

| Library | Version | Purpose | Status |
|---------|---------|---------|--------|
| `httpx` | 0.28.1 | OpenSearch HTTP calls (PUT index, POST search) | Already in deps |
| `PyYAML` | 6.0.3 | Parse Sigma YAML files | Already in deps |
| `pySigma` | 0.11.0+ | SigmaRule.from_yaml() | Already in deps, verified importable |

**No new pip dependencies required for Phase 3.** The `opensearch-py` client is unnecessary — the existing httpx-based `opensearch_sink.py` is sufficient. `sigma_loader.py` should NOT require pySigma at the `backend/src/` layer; it reads YAML directly and delegates SQL compilation to `detections/` package if needed, or just does field-level matching against `NormalizedEvent` in-memory.

### Sigma YAML Schema (pySigma-compatible subset)

Based on the existing `fixtures/sigma/*.yml` files and what `SigmaMatcher` parses:

```yaml
title: <string>
id: <UUID>
status: test | stable | experimental
description: <string>
logsource:
    product: windows       # ignored in our custom loader — we match on event fields
    category: process_creation | dns_query | network_connection
detection:
    selection:
        <FieldName>: <value>         # exact match
        <FieldName>|contains: <value>  # substring
    condition: selection
level: critical | high | medium | low | informational
tags:
    - attack.<tactic>
    - attack.t<TTTT>.<NNN>
falsepositives:
    - <string>
```

The `suspicious_dns.yml` rule must use a field that maps to `event.query` in `NormalizedEvent`. Since `sigma_loader.py` will not use the full `SigmaMatcher`/DuckDB path (that's deferred to Phase 4), it should do direct Python attribute matching against `NormalizedEvent`.

---

## Architecture Patterns

### Pattern 1: OpenSearch Sink — Remove the Guard

The existing `opensearch_sink.py` already works. The only change:

```python
# BEFORE (Phase 2 scaffold — lines 46-52):
def try_index(event: NormalizedEvent) -> bool:
    if not OPENSEARCH_URL:   # <-- REMOVE THIS GUARD
        return False
    ...

# AFTER (Phase 3):
def try_index(event: NormalizedEvent) -> bool:
    # Always attempt; fail gracefully if OS unreachable
    client = _get_client()
    ...
```

`OPENSEARCH_URL` is still read from the environment — but the guard is removed. The function already has a try/except that returns `False` on any connection error, so unavailability is already handled gracefully.

### Pattern 2: GET /search Route

Uses the same httpx client pattern already in `opensearch_sink.py`. The search endpoint POSTs to OpenSearch's `_search` API:

```python
# In routes.py — new endpoint
@router.get("/search")
def search_events(q: str = ""):
    """Search soc-events index via OpenSearch simple_query_string."""
    if not q:
        return []
    from backend.src.ingestion.opensearch_sink import OPENSEARCH_URL, INDEX_NAME, _get_client
    client = _get_client()
    if client is None or not OPENSEARCH_URL:
        return []
    url = f"{OPENSEARCH_URL}/{INDEX_NAME}/_search"
    payload = {
        "query": {
            "simple_query_string": {
                "query": q,
                "fields": ["host", "src_ip", "dst_ip", "event_type", "query",
                           "user", "protocol"],
                "default_operator": "AND"
            }
        },
        "size": 100
    }
    try:
        r = client.post(url, json=payload)
        if r.status_code != 200:
            return []
        hits = r.json().get("hits", {}).get("hits", [])
        return [h["_source"] for h in hits]
    except Exception:
        return []
```

**Why `simple_query_string`:** Lenient syntax — does not raise errors on bad user input. Correct for an analyst-facing search box. `query_string` would throw on syntax errors in untrusted input.

**Why httpx (not opensearch-py):** `opensearch-py` adds a heavy dependency when the Phase 2 scaffold already has a working httpx-based client. Consistency with existing code. Can upgrade to `opensearch-py` in Phase 4+ if bulk ops are needed.

### Pattern 3: Vector OpenSearch Sink — Uncomment

The commented block in `infra/vector/vector.yaml` (lines 136-148) is ready to activate:

```yaml
# BEFORE (commented):
# opensearch_events:
#   type: elasticsearch
#   inputs:
#     - normalise_fixture
#     - normalise_syslog
#   endpoint: "${OPENSEARCH_URL:-http://opensearch:9200}"
#   index: "soc-events-%Y-%m-%d"
#   mode: bulk

# AFTER (uncommented):
opensearch_events:
  type: elasticsearch
  inputs:
    - normalise_fixture
    - normalise_syslog
  endpoint: "${OPENSEARCH_URL:-http://opensearch:9200}"
  index: "soc-events"   # CHANGE: use fixed index name matching backend (not date-suffixed)
  mode: bulk
```

**Important:** Change the index from `"soc-events-%Y-%m-%d"` to `"soc-events"` to match the `INDEX_NAME` constant in `opensearch_sink.py`. Date-suffixed indices require index aliases for cross-date search — unnecessary complexity for Phase 3.

Vector uses `type: elasticsearch` for OpenSearch (they share the same REST API). This is correct and already confirmed by the scaffold comment.

### Pattern 4: sigma_loader.py — Direct NormalizedEvent Matching

The key architectural decision: `sigma_loader.py` at the `backend/src/detection/` layer does NOT use `SigmaMatcher` (which targets DuckDB SQL). Instead, it:

1. Reads YAML from `backend/src/detection/sigma/`
2. Parses each rule with `yaml.safe_load()`
3. Compiles each rule to a Python callable `(NormalizedEvent) -> Alert | None`
4. Returns callables that `rules.py` appends to `_RULES`

This matches exactly how `rules.py` works — all rules are `(NormalizedEvent) -> Alert | None` callables.

```python
# backend/src/detection/sigma_loader.py
import uuid
import yaml
import logging
from pathlib import Path
from backend.src.api.models import NormalizedEvent, Alert

logger = logging.getLogger(__name__)

_SIGMA_DIR = Path(__file__).parent / "sigma"

def _make_rule_fn(rule_id: str, rule_title: str, level: str,
                  conditions: dict) -> callable:
    """Compile a parsed Sigma detection block into a NormalizedEvent -> Alert | None callable."""
    def rule_fn(event: NormalizedEvent) -> Alert | None:
        selection = conditions.get("selection", {})
        for field, value in selection.items():
            # Map Sigma 'query' field to event.query
            ev_val = _get_event_field(event, field)
            if ev_val is None:
                return None
            if isinstance(value, list):
                if not any(str(v).lower() in str(ev_val).lower() for v in value):
                    return None
            else:
                if str(value).lower() not in str(ev_val).lower():
                    return None
        # All conditions matched
        return Alert(
            id=str(uuid.uuid4()),
            timestamp=event.timestamp,
            rule=rule_id,
            severity=_map_level(level),
            event_id=event.id,
            description=f"Sigma rule '{rule_title}' matched",
        )
    return rule_fn

def load_sigma_rules() -> list[callable]:
    """Scan sigma/ dir, load YAML rules, return list of rule callables."""
    ...
```

**Why not use `SigmaMatcher` here:** `SigmaMatcher` compiles to DuckDB SQL and requires a `Stores` object with a live DuckDB connection. The Phase 3 API still uses in-memory store in `routes.py`. The full SQL-backed path is Phase 4.

**Graceful pySigma absence:** The loader uses `yaml.safe_load()` directly, not `SigmaRule.from_yaml()`, so pySigma is not required at this layer.

### Pattern 5: Integrating Sigma Rules into evaluate()

Two options — use option B:

**Option A (modify rules.py):** Add sigma rules directly to `_RULES` list at module load. Couples rules.py to sigma_loader.py.

**Option B (routes.py loads both):** `routes.py` imports `evaluate` from `rules.py` AND loads sigma rules separately, merging results. Keeps `rules.py` unchanged.

```python
# In routes.py _store_event():
from backend.src.detection.sigma_loader import load_sigma_rules as _load_sigma
_SIGMA_RULES = _load_sigma()   # module-level load on startup

def _store_event(event: NormalizedEvent) -> list[Alert]:
    ...
    new_alerts = evaluate(event)  # existing Python rules
    # Run Sigma rules
    for sigma_rule_fn in _SIGMA_RULES:
        result = sigma_rule_fn(event)
        if result is not None:
            new_alerts.append(result)
    _alerts.extend(a.model_dump() for a in new_alerts)
    ...
```

This leaves `rules.py` untouched (preserving all existing tests) and adds Sigma alerts through the same pipeline.

### Pattern 6: suspicious_dns.yml Structure

Based on the existing `enricher.py` `SUSPICIOUS_DOMAINS` set and fixture data, the rule must match on `query` field containing suspicious domain patterns:

```yaml
title: Suspicious DNS Query
id: d4e5f6a7-b8c9-0d1e-2f3a-4b5c6d7e8f9a
status: test
description: Detects DNS queries to known suspicious domains
author: AI-SOC-Brain
date: 2026-03-15
tags:
    - attack.command_and_control
    - attack.t1071.004
logsource:
    product: network
    category: dns
detection:
    selection:
        query|contains:
            - suspicious-domain.test
            - malware.example
            - c2.evil.test
    condition: selection
level: high
falsepositives:
    - Internal test environments
```

The `query` field maps directly to `NormalizedEvent.query`. The fixture event `{"query": "suspicious-domain.test"}` will match this rule. This overlaps with the existing Python rule `rule_suspicious_dns` — that is intentional per CONTEXT.md ("existing test fixtures fire it") and the test expects both Python and Sigma alerts to appear.

### Pattern 7: docker-compose.yml Changes

Three changes needed:

1. Uncomment `OPENSEARCH_URL=http://opensearch:9200` in backend environment
2. Add `depends_on` for backend → opensearch with condition `service_healthy`
3. Add healthcheck to opensearch service

```yaml
# backend service:
environment:
  - PYTHONUNBUFFERED=1
  - OPENSEARCH_URL=http://opensearch:9200   # uncomment this line

depends_on:
  opensearch:
    condition: service_healthy

# opensearch service (add healthcheck):
healthcheck:
  test: ["CMD-SHELL", "curl -sf http://localhost:9200/_cluster/health || exit 1"]
  interval: 15s
  timeout: 10s
  retries: 5
  start_period: 30s
```

The `start_period: 30s` is important — OpenSearch 2.x takes ~20-25s to start. Without it, Docker marks it unhealthy before it is ready.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| YAML parsing | Custom parser | `yaml.safe_load()` | Already in deps, handles anchors/aliases |
| OpenSearch HTTP | opensearch-py client | `httpx.Client` (already in opensearch_sink.py) | No new dep; Phase 2 scaffold already works |
| Multi-field text search | Custom tokenizer | `simple_query_string` query type | Handles boolean operators, field-specific queries, no crash on bad input |
| Sigma YAML structure | Custom schema validation | Read `detection.selection` dict directly | pySigma does this already at the detections/ layer; sigma_loader.py doesn't need it |

---

## Common Pitfalls

### Pitfall 1: Date-Suffixed Vector Index vs Fixed Backend Index
**What goes wrong:** Vector's scaffold uses `index: "soc-events-%Y-%m-%d"`. Backend uses `INDEX_NAME = "soc-events"`. Search hits only one day's index, or search misses Vector-indexed events.
**How to avoid:** Change Vector sink to `index: "soc-events"` (fixed). Both Vector and backend write to the same index.
**Warning signs:** `/search?q=test` returns results from backend-indexed events but not from syslog/fixture events ingested via Vector.

### Pitfall 2: OpenSearch Not Ready When Backend Starts
**What goes wrong:** Backend starts, tries to index an event on first request, OpenSearch is still initializing (takes ~25s), connection refused → try_index returns False but the log is swamped with errors.
**How to avoid:** `depends_on: opensearch: condition: service_healthy` with a proper healthcheck and `start_period: 30s`.
**Warning signs:** `docker compose logs backend | grep "OpenSearch sink error"` showing errors in first 30 seconds.

### Pitfall 3: Sigma Rule Field Names Don't Map to NormalizedEvent
**What goes wrong:** `suspicious_dns.yml` uses Sigma field name `QueryName` (Windows DNS Sysmon field), but `NormalizedEvent` has `query`. The loader checks `_get_event_field(event, "QueryName")` → None → rule never matches.
**How to avoid:** Use `query` as the Sigma field name in `suspicious_dns.yml` (our custom schema) OR build a small field-name resolver in `sigma_loader.py` that falls back to `SIGMA_FIELD_MAP` from `detections/field_map.py`.
**Warning signs:** `test_sigma_loader_dns_rule_fires` fails with 0 alerts.

### Pitfall 4: Sigma Alerts Duplicate Existing Python Alerts
**What goes wrong:** Both `rule_suspicious_dns` (Python) and the Sigma `suspicious_dns.yml` rule fire for the same event, producing duplicate alerts in `/alerts`. The existing test `test_suspicious_dns_fires_alert` still passes (it only checks presence, not count), but an analyst sees duplicate alerts.
**How to avoid:** This is acceptable per CONTEXT.md ("existing test fixtures fire it"). Document it. If deduplication is needed, add rule-name uniqueness check in `_store_event`. Do not attempt this in Phase 3.
**Warning signs:** `/alerts` returns 2 alerts for a single suspicious DNS event.

### Pitfall 5: _SIGMA_RULES Module-Level Load Fails Silently
**What goes wrong:** `sigma_loader.py` is imported at routes.py module load time. If `sigma/` directory is missing or YAML is malformed, it raises an exception that crashes the FastAPI app before it starts.
**How to avoid:** Wrap `load_sigma_rules()` in try/except; return empty list on any error; log a warning.
**Warning signs:** `uvicorn` exits immediately on startup with an import error.

### Pitfall 6: opensearch_sink.py URL Format
**What goes wrong:** The existing `try_index` uses `PUT /{index}/_doc/{event.id}`. This requires `event.id` to be URL-safe. `NormalizedEvent.id` is a UUID string — safe. But if `event.id` contains slashes or special chars from upstream, the PUT fails with 400.
**How to avoid:** `event.id` is always a UUID (set in `normalizer.py`). No change needed. Just verify normalizer always sets a UUID, not the raw upstream value.

---

## Code Examples

### OpenSearch simple_query_string Request Body
```json
POST /soc-events/_search
{
  "query": {
    "simple_query_string": {
      "query": "suspicious-domain",
      "fields": ["host", "src_ip", "dst_ip", "event_type", "query", "user", "protocol"],
      "default_operator": "AND"
    }
  },
  "size": 100
}
```
Source: OpenSearch docs (simple_query_string is lenient, no error on bad syntax)

### Sigma YAML Minimal Structure (verified from fixtures/sigma/*.yml)
```yaml
title: <string>
id: <UUID string>
status: test
logsource:
    product: <string>
    category: <string>
detection:
    selection:
        <field>: <value>         # OR list of values
        <field>|contains: <val>
    condition: selection
level: high | medium | low | critical | informational
```

### sigma_loader.py Field Resolution (handles Sigma canonical names)
```python
_FIELD_TO_EVENT_ATTR = {
    "query": "query",
    "QueryName": "query",      # Sigma DNS canonical
    "host": "host",
    "src_ip": "src_ip",
    "dst_ip": "dst_ip",
    "event_type": "event_type",
    "user": "user",
    "port": "port",
}

def _get_event_field(event: NormalizedEvent, field_name: str):
    attr = _FIELD_TO_EVENT_ATTR.get(field_name, field_name.lower())
    return getattr(event, attr, None)
```

### Vector opensearch_events Sink (uncommented and corrected)
```yaml
opensearch_events:
  type: elasticsearch
  inputs:
    - normalise_fixture
    - normalise_syslog
  endpoint: "${OPENSEARCH_URL:-http://opensearch:9200}"
  index: "soc-events"
  mode: bulk
```

---

## Test Architecture

### Existing Test Count
- `backend/src/tests/smoke_test.py`: 7 tests (Wave 1)
- `backend/src/tests/test_phase2.py`: 25 tests (Phase 2)
- `tests/sigma_smoke/test_sigma_matcher.py`: 16 tests
- `tests/unit/` (3 files): ~76 tests
- **Total passing (unit only, no backend required): 124**

The 9 integration tests in `tests/integration/test_backend_health.py` require a live backend. They pass when the backend is running but the `skipif` guard does not fire because `backend_available()` returns True when the backend is already running. These are pre-existing failures when backend is not running — not Phase 3 regressions.

**The "32 existing tests" referenced in CONTEXT.md refers to the Wave 1 + Phase 2 test files:**
- `smoke_test.py`: 7 tests
- `test_phase2.py`: 25 tests
- **Total: 32**

### Phase 3 Test Map

| ID | Behavior | Test Type | File | Automated Command |
|----|----------|-----------|------|-------------------|
| P3-T1 | `GET /search?q=` returns array | unit (TestClient) | `backend/src/tests/test_phase3.py` | `pytest backend/src/tests/test_phase3.py -x` |
| P3-T2 | `GET /search?q=` with empty q returns [] | unit (TestClient) | `backend/src/tests/test_phase3.py` | `pytest backend/src/tests/test_phase3.py -x` |
| P3-T3 | `sigma_loader` loads `suspicious_dns.yml`, returns ≥1 callable | unit | `backend/src/tests/test_phase3.py` | `pytest backend/src/tests/test_phase3.py -x` |
| P3-T4 | Sigma rule callable fires Alert for suspicious DNS event | unit | `backend/src/tests/test_phase3.py` | `pytest backend/src/tests/test_phase3.py -x` |
| P3-T5 | Sigma rule `id` is used as alert `rule` field | unit | `backend/src/tests/test_phase3.py` | `pytest backend/src/tests/test_phase3.py -x` |
| P3-T6 | Sigma alert appears in `GET /alerts` | unit (TestClient) | `backend/src/tests/test_phase3.py` | `pytest backend/src/tests/test_phase3.py -x` |
| P3-T7 | All 32 existing tests continue to pass | regression | `backend/src/tests/` | `pytest backend/src/tests/ -x` |
| P3-T8 | opensearch_sink.try_index is called unconditionally | unit (mock) | `backend/src/tests/test_phase3.py` | `pytest backend/src/tests/test_phase3.py -x` |

**Note:** Tests P3-T1 and P3-T2 (search endpoint) will pass even when OpenSearch is not running — the endpoint returns `[]` gracefully on connection failure, which is the correct behavior to test. The actual OpenSearch query can be tested via a separate integration test when the stack is running.

### Validation Architecture

| Property | Value |
|----------|-------|
| Framework | pytest 8.3.5 + pytest-asyncio |
| Config file | `pyproject.toml` → `[tool.pytest.ini_options]` |
| Quick run command | `uv run pytest backend/src/tests/ -x -q` |
| Full suite command | `uv run pytest -x -q` |

**Per task commit:** `uv run pytest backend/src/tests/ -x -q`
**Per wave merge:** `uv run pytest -x -q`
**Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `backend/src/tests/test_phase3.py` — 8 new tests covering P3-T1 through P3-T8
- [ ] `backend/src/detection/sigma/` directory — create with `suspicious_dns.yml`
- [ ] `backend/src/detection/sigma_loader.py` — new file

*(Existing test infrastructure in place; only new test file needed)*

---

## State of the Art

| Old Approach | Current Approach | Impact |
|--------------|------------------|--------|
| `opensearch-py` client | httpx direct HTTP (already in codebase) | No new dep; simpler for single-index use |
| Date-suffixed OS indices | Single `soc-events` index | Simpler search, no alias management |
| pySigma SQL backend for detection | Direct Python attribute matching on NormalizedEvent | Avoids DuckDB dependency in in-memory pipeline; full SQL backend deferred to Phase 4 |

---

## Open Questions

1. **`_SIGMA_RULES` reloading**
   - What we know: Rules are loaded at module import time in `routes.py`
   - What's unclear: If a new `.yml` file is added, does the backend need restart?
   - Recommendation: Accept reload-on-restart for Phase 3. Hot-reload is Phase 4.

2. **9 integration test failures**
   - What we know: `tests/integration/test_backend_health.py` has 9 tests expecting `/api/events`, `/api/detections`, `/api/graph/entities` routes that don't exist yet (no `/api` prefix in current `routes.py`)
   - What's unclear: Were these written for a future API version?
   - Recommendation: These are pre-existing failures. Phase 3 should NOT add an `/api` prefix — doing so would break the 32 existing tests. Leave integration tests failing. Document as known issue.

3. **Vector → OpenSearch auth**
   - What we know: `docker-compose.yml` has `DISABLE_SECURITY_PLUGIN=true` for OpenSearch
   - What's unclear: Does Vector's `type: elasticsearch` sink require auth headers with `DISABLE_SECURITY_PLUGIN=true`?
   - Recommendation: No auth needed when security plugin is disabled. The existing scaffold had no auth configured. Proceed without.

---

## Sources

### Primary (HIGH confidence — read from actual codebase)
- `backend/src/ingestion/opensearch_sink.py` — exact guard to remove, httpx client pattern
- `backend/src/detection/rules.py` — `_RULES` list extension pattern, `Alert` construction
- `backend/src/api/models.py` — `Alert`, `NormalizedEvent` schemas, exact field names
- `backend/src/api/routes.py` — `_store_event` pattern, `_SIGMA_RULES` integration point
- `infra/vector/vector.yaml` — exact commented block to uncomment (lines 136-148)
- `infra/docker-compose.yml` — exact env var to uncomment, service topology
- `detections/matcher.py` — `SigmaMatcher` architecture (not needed in Phase 3 path)
- `fixtures/sigma/*.yml` — confirmed Sigma YAML schema used in this project
- `tests/sigma_smoke/test_sigma_matcher.py` — 16 tests that must continue passing
- `backend/src/ingestion/enricher.py` — `SUSPICIOUS_DOMAINS` set (reuse in suspicious_dns.yml)

### Secondary (MEDIUM confidence — WebSearch verified against official docs)
- OpenSearch `simple_query_string` query — lenient syntax, fields array, default_operator param
  Source: https://docs.opensearch.org/latest/query-dsl/full-text/simple-query-string/
- Vector `type: elasticsearch` works with OpenSearch — confirmed by existing scaffold comment
- OpenSearch 2.x startup time ~25s — informs `start_period: 30s` in healthcheck

---

## Metadata

**Confidence breakdown:**
- OpenSearch sink activation: HIGH — exact lines identified in codebase
- Search endpoint pattern: HIGH — httpx pattern already in sink; query DSL from official docs
- Vector sink uncomment: HIGH — exact block in vector.yaml identified
- sigma_loader.py design: HIGH — pattern derived from existing rules.py + NormalizedEvent schema
- suspicious_dns.yml: HIGH — domain list from enricher.py, YAML format from fixtures/sigma/
- docker-compose changes: HIGH — exact service topology from file; healthcheck timing from OS docs

**Research date:** 2026-03-15
**Valid until:** 2026-04-15 (stable infrastructure; OpenSearch 2.13 API stable)
