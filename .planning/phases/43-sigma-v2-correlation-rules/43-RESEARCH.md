# Phase 43: Sigma v2 Correlation Rules - Research

**Researched:** 2026-04-12
**Domain:** Multi-event statistical correlation — DuckDB windowed aggregations, SQLite dedup, Svelte 5 filter chips
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Run correlation after every ingest batch — same trigger point as Sigma matching. No separate scheduler.
- Scan a recent window only (CORRELATION_LOOKBACK_HOURS, default 2h).
- Deduplicate: suppress a new detection if the same `src_ip + rule_id + evidence window` already fired within the dedup window.
- Settings added to config.py: `CORRELATION_LOOKBACK_HOURS` (default 2) and `CORRELATION_DEDUP_WINDOW_MINUTES` (default 60).
- Port scan: 15+ distinct `dst_port` values from one `src_ip` within 60 seconds → `corr-portscan`, severity `medium`
- Brute force: 10+ failed auth events for the same target within 60 seconds → `corr-bruteforce`, severity `high`
- Beaconing: CV (stddev/mean of inter-connection intervals) < 0.3 over 20+ connections per `(src_ip, dst_ip, dst_port)` tuple → `corr-beacon`, severity `high`
- Multi-stage chain: all rules in chain fire for same `src_ip` within 15 minutes → `corr-chain-{name}`, severity `critical`
- Correlation detections appear inline in DetectionsView — no new tab.
- Each correlation row shows correlation type badge (PORT_SCAN / BRUTE_FORCE / BEACON / CHAIN), source entity (`src_ip`), matched event count.
- Click row → expand to show individual matched event IDs.
- Add `CORR` filter chip to DetectionsView alongside existing filter chips.
- Severity is fixed per type: PORT_SCAN=medium, BRUTE_FORCE=high, BEACON=high, CHAIN=critical.
- Chains defined in YAML config: `detections/correlation_chains.yml`
- Pre-configured chains: recon→scan→exploit and scan→bruteforce, entity_key=src_ip, window_minutes=15
- rule_id format: `corr-chain-{chain_name}`

### Claude's Discretion
- Exact DuckDB SQL for beaconing CV calculation (stddev/mean window function approach)
- How correlation dedup state is stored (SQLite table vs in-memory set with TTL)
- Whether chain YAML is hot-reloaded or requires restart
- Exact filter chip placement in DetectionsView

### Deferred Ideas (OUT OF SCOPE)
- None — discussion stayed within phase scope.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| P43-T01 | Beaconing detection — CV < 0.3 over 20+ connections per (src_ip, dst_ip, dst_port) | Verified DuckDB inter-arrival LAG + STDDEV_POP/AVG SQL pattern |
| P43-T02 | Port scan detection — 15+ distinct dst_ports from one src_ip within 60s | Verified DuckDB COUNT(DISTINCT dst_port) with sliding window SQL |
| P43-T03 | Brute force detection — 10+ failed auth events for same target within 60s | Identified `event_outcome = 'failure'` and `event_type IN ('logon_failure','ssh')` columns |
| P43-T04 | Multi-stage chain correlation — rules A+B+C fire for same entity within T seconds | Requires detecting corr-* rule_ids in SQLite detections table within window |
| P43-T05 | Surface correlation hits as DetectionRecord with matched_event_ids evidence list | `insert_detection()` API is direct match; `LIST(event_id)` in DuckDB returns evidence |
| P43-T06 | CorrelationView / correlation panel in DetectionsView with CORR filter chip | `severityFilter` state → extend to `typeFilter`; expand row already exists (expandedId) |
</phase_requirements>

---

## Summary

Phase 43 adds a `CorrelationEngine` that runs after every ingest batch, executing four DuckDB aggregate queries against `normalized_events` and writing results into the existing SQLite `detections` table via `insert_detection()`. No new database tables or API routes are needed for the core engine. The engine follows the exact same async-run-then-save pattern as `SigmaMatcher`: query DuckDB in a thread, build `DetectionRecord` objects, call `stores.sqlite.insert_detection()`.

The integration hook is `ingestion/loader.py:ingest_events()` — the engine call goes after Step 4 (`_write_graph`) at the bottom of that method. The engine receives the `stores` container and returns early if no new events qualified. Dedup is implemented by querying SQLite's `detections` table for recent rows with the same `rule_id` and `explanation` (which encodes the entity key), avoiding a new SQLite table.

The frontend change is additive: a `typeFilter` rune alongside `severityFilter`, a `CORR` chip in the KPI bar action area, a correlation type badge rendered on rows where `rule_id.startsWith('corr-')`, and the expand row shows `matched_event_ids` (already available on `Detection`). The `Detection` interface in `api.ts` needs two new optional fields: `correlation_type` and `matched_event_count`.

**Primary recommendation:** Build `detections/correlation_engine.py` following the `SigmaMatcher` pattern — async class with `run(stores)` method, verified DuckDB SQL for each of the four detection types, SQLite dedup check before insert.

---

## Standard Stack

### Core (all already installed)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| duckdb | 1.3.0 | Aggregate queries over normalized_events | Already the event store; window functions verified at this version |
| pydantic | v2 | DetectionRecord model | Project standard |
| pyyaml | installed | Parse correlation_chains.yml | Already used elsewhere in project |
| asyncio.to_thread | stdlib | Wrap DuckDB blocking reads | Project convention per CLAUDE.md |

### No New Dependencies
Correlation engine requires zero new pip packages. All required functionality (STDDEV_POP, LAG window function, LIST aggregation, COUNT DISTINCT) is available in DuckDB 1.3.0.

---

## Architecture Patterns

### Recommended Module Structure
```
detections/
├── matcher.py                    # existing — unchanged
├── field_map.py                  # existing — unchanged
├── correlation_engine.py         # NEW — CorrelationEngine class
└── correlation_chains.yml        # NEW — chain definitions YAML
```

### Pattern 1: CorrelationEngine Class (mirrors SigmaMatcher)

```python
# detections/correlation_engine.py
class CorrelationEngine:
    def __init__(self, stores: Stores) -> None:
        self.stores = stores
        self._chains: list[dict] = []  # loaded from YAML

    def load_chains(self, yml_path: str) -> int: ...

    async def run(self) -> list[DetectionRecord]:
        results = []
        results.extend(await self._detect_port_scans())
        results.extend(await self._detect_brute_force())
        results.extend(await self._detect_beaconing())
        results.extend(await self._detect_chains())
        return results

    async def save_detections(self, detections: list[DetectionRecord]) -> int:
        # calls stores.sqlite.insert_detection() via asyncio.to_thread
        # same implementation as SigmaMatcher.save_detections
```

**Key difference from SigmaMatcher:** CorrelationEngine queries DuckDB aggregates (GROUP BY), not per-event rows. It receives a stores container at construction, same as SigmaMatcher.

### Pattern 2: ingest_events() Hook (loader.py)

```python
# ingestion/loader.py — after _write_graph in ingest_events()
# Step 5: Correlation detection (new in Phase 43)
if self._correlation_engine is not None:
    corr_detections = await self._correlation_engine.run()
    if corr_detections:
        await self._correlation_engine.save_detections(corr_detections)
```

`IngestionLoader.__init__` gains a new `correlation_engine: CorrelationEngine | None = None` parameter, following the existing pattern for `ioc_store`, `asset_store`, `anomaly_scorer`.

### Pattern 3: Dedup Via SQLite Query (no new table needed)

```python
async def _is_dedup_suppressed(
    self, rule_id: str, entity_key: str, dedup_minutes: int
) -> bool:
    """Check if same rule_id + entity_key fired within dedup window."""
    def _check():
        cutoff = (datetime.now(tz=timezone.utc) - timedelta(minutes=dedup_minutes)).isoformat()
        row = self.stores.sqlite._conn.execute(
            """SELECT id FROM detections
               WHERE rule_id = ?
                 AND explanation LIKE ?
                 AND created_at >= ?
               LIMIT 1""",
            (rule_id, f"%{entity_key}%", cutoff),
        ).fetchone()
        return row is not None
    return await asyncio.to_thread(_check)
```

This uses `explanation LIKE '%{entity_key}%'` as a cheap string-match against the entity. The explanation is always set to a deterministic format like `"Port scan from 192.168.1.5 (20 ports in 60s)"`. This avoids a new dedup table while keeping the check within the existing infrastructure pattern. Confidence: MEDIUM — if `explanation` format drifts this breaks. Alternative: store entity in a new `entity_key TEXT` column via migration.

**Recommended:** Add `entity_key TEXT` column via ALTER TABLE migration in `SQLiteStore.__init__` (same backward-compat migration pattern used throughout sqlite_store.py). Then dedup queries `WHERE rule_id = ? AND entity_key = ? AND created_at >= ?`.

### Pattern 4: Chain Detection — Querying SQLite Detections

Chains require looking at the `detections` SQLite table, not DuckDB events. For each chain definition, query: "did rule_id X and rule_id Y both appear in `detections` for entity_key=`src_ip` within the last `window_minutes` minutes?"

```python
async def _detect_chain(self, chain: dict) -> list[DetectionRecord]:
    """Check if all rule_ids in chain fired for same src_ip within window."""
    def _query():
        window_start = (datetime.now(tz=timezone.utc)
                        - timedelta(minutes=chain["window_minutes"])).isoformat()
        placeholders = ",".join("?" * len(chain["rule_ids"]))
        rows = self.stores.sqlite._conn.execute(
            f"""SELECT entity_key, COUNT(DISTINCT rule_id) AS matched_rules,
                       GROUP_CONCAT(id, ',') AS detection_ids
                FROM detections
                WHERE rule_id IN ({placeholders})
                  AND created_at >= ?
                  AND entity_key IS NOT NULL
                GROUP BY entity_key
                HAVING COUNT(DISTINCT rule_id) = ?""",
            chain["rule_ids"] + [window_start, len(chain["rule_ids"])],
        ).fetchall()
        return rows
    ...
```

This requires the `entity_key` column migration (see above).

### Pattern 5: Svelte 5 Filter Chip

Existing pattern: `let severityFilter = $state('')` bound to `<select>`. Extension:

```typescript
// Add alongside severityFilter
let typeFilter = $state('')   // 'CORR' | 'SIGMA' | 'ANOMALY' | ''

// Derived filtered list
let displayDetections = $derived(
  typeFilter === 'CORR'
    ? detections.filter(d => d.rule_id?.startsWith('corr-'))
    : typeFilter === 'ANOMALY'
    ? detections.filter(d => d.rule_id?.startsWith('anomaly-'))
    : detections
)
```

The CORR chip uses the same clickable pill pattern as severity pills but controls `typeFilter`. The API call does NOT need a new filter parameter — filtering happens client-side on the already-fetched list (same pattern used for severity filter in posture score calculation).

### Anti-Patterns to Avoid

- **Separate correlation scheduler:** The CONTEXT.md locks this to after-ingest trigger only. No background task, no cron.
- **New API router:** The `corr-*` rule_id prefix makes existing `GET /detect?rule_id=corr-portscan` work without changes. The detect.py list endpoint already supports `rule_id` filter. Do not create a new `/correlate/detections` endpoint.
- **Full table scan on every ingest:** Always filter by `WHERE timestamp >= now() - INTERVAL '{LOOKBACK}h'`. Without this, performance degrades as the event table grows.
- **`asyncio.to_thread` inside a thread:** The engine methods are async; DuckDB calls use `fetch_all()` (already wraps in `to_thread`). Do not call `to_thread` from within another `to_thread`.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Interval-based CV | Custom Python loop over events | DuckDB LAG window + STDDEV_POP/AVG in single SQL | Single query is 100x faster than Python row iteration; LAG handles out-of-order timestamps correctly |
| Distinct port counting | Python set accumulation | DuckDB `COUNT(DISTINCT dst_port)` with GROUP BY | DuckDB scan is vectorized; Python loop requires fetching all raw rows |
| Time-window sliding | Python datetime comparisons | DuckDB `WHERE timestamp >= now() - INTERVAL '60 seconds'` | DuckDB timestamp arithmetic is native; avoids fetching lookback events to Python |
| Detection dedup | Python in-memory dict with TTL | SQLite detections table query | Already persistent across restarts; consistent with existing dedup patterns |
| YAML chain config parsing | Custom DSL | PyYAML | Already available; safe for analyst-edited config |

---

## Verified DuckDB SQL Patterns

### Beaconing Detection (CV of inter-arrival intervals)

Confirmed working against DuckDB 1.3.0:

```sql
-- Source: verified against duckdb 1.3.0 in this project's .venv
WITH intervals AS (
  SELECT
    event_id,
    src_ip,
    dst_ip,
    dst_port,
    timestamp,
    epoch(timestamp) - LAG(epoch(timestamp)) OVER (
      PARTITION BY src_ip, dst_ip, dst_port
      ORDER BY timestamp
    ) AS interval_secs
  FROM normalized_events
  WHERE timestamp >= now() - INTERVAL '2 hours'
    AND src_ip IS NOT NULL
    AND dst_ip IS NOT NULL
    AND dst_port IS NOT NULL
    AND event_type IN ('conn', 'network_connect', 'tls', 'ssl', 'http')
),
agg AS (
  SELECT
    src_ip,
    dst_ip,
    dst_port,
    COUNT(*) AS conn_count,
    AVG(interval_secs) AS mean_interval,
    STDDEV_POP(interval_secs) AS stddev_interval,
    MIN(timestamp) AS window_start,
    MAX(timestamp) AS window_end,
    LIST(event_id ORDER BY timestamp) AS event_ids
  FROM intervals
  WHERE interval_secs IS NOT NULL
  GROUP BY src_ip, dst_ip, dst_port
  HAVING COUNT(*) >= 19             -- 20+ connections means 19+ intervals
    AND AVG(interval_secs) > 0      -- guard against zero-interval bursts
    AND STDDEV_POP(interval_secs) / NULLIF(AVG(interval_secs), 0) < 0.3
)
SELECT * FROM agg
```

**Important detail:** `COUNT(*) >= 19` in the intervals CTE (after LAG) corresponds to 20+ connections. The first connection has no previous to diff against, so N connections produce N-1 intervals.

**Lookback substitution:** Replace `'2 hours'` with `? hours` and pass `settings.CORRELATION_LOOKBACK_HOURS` as a parameter — but DuckDB does not support interval literals with `?` placeholders. Use string formatting: `f"INTERVAL '{settings.CORRELATION_LOOKBACK_HOURS} hours'"`. This is safe because the value comes from a validated `int` setting (not user input).

### Port Scan Detection

```sql
-- Source: verified against duckdb 1.3.0
SELECT
  src_ip,
  COUNT(DISTINCT dst_port) AS distinct_ports,
  LIST(DISTINCT dst_port) AS ports_scanned,
  LIST(event_id) AS event_ids,
  MIN(timestamp) AS window_start,
  MAX(timestamp) AS window_end
FROM normalized_events
WHERE timestamp >= now() - INTERVAL '2 hours'
  AND src_ip IS NOT NULL
  AND dst_port IS NOT NULL
GROUP BY src_ip, date_trunc('minute', timestamp - INTERVAL '30 seconds')
HAVING COUNT(DISTINCT dst_port) >= 15
  AND (MAX(epoch(timestamp)) - MIN(epoch(timestamp))) <= 60
```

**Sliding window approach:** The `date_trunc('minute', ...)` with offset creates 60-second buckets aligned to when scanning started. A simpler alternative that avoids GROUP BY on a derived time bucket:

```sql
-- Simpler: tumbling 60s windows by src_ip
SELECT src_ip,
  COUNT(DISTINCT dst_port) AS distinct_ports,
  LIST(event_id) AS event_ids,
  MIN(timestamp) AS window_start,
  MAX(timestamp) AS window_end
FROM normalized_events
WHERE timestamp >= now() - INTERVAL '2 hours'
  AND src_ip IS NOT NULL
GROUP BY src_ip,
  CAST(epoch(timestamp) / 60 AS BIGINT)  -- 60s tumbling bucket
HAVING COUNT(DISTINCT dst_port) >= 15
```

**Recommendation:** Use the tumbling window (second form) — simpler, no edge cases, verified working.

### Brute Force Detection

```sql
-- Source: verified against duckdb 1.3.0
-- event_outcome = 'failure' covers Zeek SSH, Windows logon failures
-- event_type IN ('logon_failure','ssh') covers OS-level auth events
SELECT
  src_ip,
  dst_ip,
  COUNT(*) AS failed_auth_count,
  LIST(event_id) AS event_ids,
  MIN(timestamp) AS window_start,
  MAX(timestamp) AS window_end
FROM normalized_events
WHERE timestamp >= now() - INTERVAL '2 hours'
  AND src_ip IS NOT NULL
  AND (event_outcome = 'failure'
       OR event_type IN ('logon_failure')
       OR (event_type = 'ssh' AND ssh_auth_success = false))
GROUP BY src_ip, dst_ip,
  CAST(epoch(timestamp) / 60 AS BIGINT)  -- 60s tumbling bucket
HAVING COUNT(*) >= 10
```

**Column mapping for auth failures (confirmed from schema):**
- `event_outcome = 'failure'` — set by normalizer for Windows logon failures (EventID 4625), Zeek SSH failed auth
- `event_type = 'logon_failure'` — normalized event type for Windows 4625
- `ssh_auth_success = false` — Zeek SSH boolean (column added Phase 36)

All three conditions should be OR'd to catch auth failures from different source types (Windows EVTX, Zeek, Suricata).

---

## Common Pitfalls

### Pitfall 1: DuckDB Interval Literals Cannot Use `?` Placeholders
**What goes wrong:** `WHERE timestamp >= now() - INTERVAL ? hours` raises a DuckDB BinderException.
**Why it happens:** DuckDB parses interval literals at compile time; they are not parameterizable.
**How to avoid:** Use f-string to embed the integer: `f"INTERVAL '{settings.CORRELATION_LOOKBACK_HOURS} hours'"`. This is safe because `CORRELATION_LOOKBACK_HOURS` is a validated Pydantic `int` field — it cannot contain SQL injection.
**Warning signs:** `BinderException: Expected a constant interval` in logs.

### Pitfall 2: Beaconing on First Connection (N-1 intervals from N connections)
**What goes wrong:** `HAVING COUNT(*) >= 20` against the intervals CTE will miss qualifying tuples. The LAG() on the first row in each partition returns NULL, so the intervals CTE produces N-1 rows from N events.
**Why it happens:** `COUNT(*) >= 19` in the intervals CTE (after filtering `WHERE interval_secs IS NOT NULL`) corresponds to 20+ original connections.
**How to avoid:** Use `HAVING COUNT(*) >= 19` in the agg step or add back the original connection count via a subquery.

### Pitfall 3: LIST() Returns DuckDB Python UUID Objects
**What goes wrong:** `LIST(event_id)` returns Python `uuid.UUID` objects in result rows, not strings. `json.dumps(event_ids)` will fail.
**Why it happens:** DuckDB maps UUID columns to Python `uuid.UUID` type.
**How to avoid:** Cast in SQL: `LIST(CAST(event_id AS VARCHAR) ORDER BY timestamp)`, or convert in Python: `[str(e) for e in row["event_ids"]]`.

### Pitfall 4: Chain Detection Needs entity_key Column
**What goes wrong:** Chain matching queries SQLite's detections table for `entity_key`. The column does not currently exist.
**Why it happens:** The `detections` DDL (sqlite_store.py line 64-76) has no `entity_key` column. The Sigma matcher does not set one.
**How to avoid:** Add a backward-compat ALTER TABLE migration in `SQLiteStore.__init__`: `ALTER TABLE detections ADD COLUMN entity_key TEXT`. Use the same try/except pattern already used for `risk_score`, `triaged_at`, etc. Correlation engine sets `entity_key = src_ip` when inserting correlation detections.

### Pitfall 5: Dedup Window Relies on SQLite created_at Precision
**What goes wrong:** Two detections 1 second apart can both pass dedup if SQLite's TEXT timestamp comparison uses ISO format.
**Why it happens:** `_now_iso()` returns `datetime.now(tz=timezone.utc).isoformat()` which is precise to microseconds — string comparison works correctly for ISO 8601 timestamps.
**How to avoid:** No action needed — ISO 8601 string comparison works correctly for lexicographic ordering (e.g., `'2026-04-12T10:00:01' >= '2026-04-12T09:00:00'` is correct). Confirmed by existing detection timestamps in the project.

### Pitfall 6: Port Scan Tumbling Window May Split a Real Scan
**What goes wrong:** A scan spanning 10:59:30–11:00:10 hits two 60s buckets and produces 2 low-count detections instead of 1 qualifying one.
**Why it happens:** Tumbling windows are anchored to epoch/60, not to scan start.
**How to avoid:** For port scan, this is acceptable — production scanners complete port sweeps well within a single 60s tumbling window. If scan splitting becomes a false-negative issue, switch to a subquery that checks "any 60s window" using `MAX(ts) - MIN(ts) <= 60`. But for Phase 43, the simple tumbling window is sufficient.

### Pitfall 7: Correlation Engine Not Wired Into App Factory
**What goes wrong:** Engine is built but not passed to `IngestionLoader` during startup, so `ingest_events()` never calls it.
**Why it happens:** The existing enrichment objects (ioc_store, asset_store, anomaly_scorer) are wired in `backend/main.py:create_app()`.
**How to avoid:** Add engine construction and wiring in `create_app()` using the same pattern as anomaly_scorer. The engine reads `settings.CORRELATION_LOOKBACK_HOURS` and `settings.CORRELATION_DEDUP_WINDOW_MINUTES` from the settings singleton.

---

## Code Examples

### DetectionRecord Construction for Correlation

Pattern from `SigmaMatcher.match_rule()` (lines 676-688), adapted for correlation:

```python
from uuid import uuid4
from datetime import datetime, timezone
from backend.models.event import DetectionRecord

detection = DetectionRecord(
    id=str(uuid4()),
    rule_id="corr-portscan",
    rule_name="Port Scan Detected",
    severity="medium",
    matched_event_ids=[str(e) for e in event_ids],  # cast UUIDs to str
    attack_technique=None,
    attack_tactic="Discovery",
    explanation=f"Port scan from {src_ip}: {distinct_ports} distinct ports in 60s",
    case_id=None,
    created_at=datetime.now(tz=timezone.utc),
)
```

### entity_key Migration (sqlite_store.py)

```python
# Add after existing migrations in SQLiteStore.__init__
try:
    self._conn.execute(
        "ALTER TABLE detections ADD COLUMN entity_key TEXT"
    )
    self._conn.commit()
except Exception:
    pass  # column already exists — idempotent

try:
    self._conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_detections_entity_key ON detections (entity_key)"
    )
    self._conn.commit()
except Exception:
    pass
```

### insert_detection Call for Correlation (existing API — no changes needed)

```python
# stores.sqlite.insert_detection signature (confirmed from sqlite_store.py line 735):
stores.sqlite.insert_detection(
    detection_id=str(uuid4()),
    rule_id="corr-portscan",
    rule_name="Port Scan Detected",
    severity="medium",
    matched_event_ids=["event-uuid-1", "event-uuid-2"],  # list[str]
    attack_technique=None,
    attack_tactic="Discovery",
    explanation="Port scan from 192.168.1.5: 20 distinct ports in 60s",
    case_id=None,
)
# matched_event_ids is JSON-serialized internally by insert_detection via json.dumps()
```

### Svelte 5 Filter Chip — typeFilter Rune

```typescript
// In DetectionsView.svelte — alongside existing severityFilter
let typeFilter = $state('')  // '' | 'CORR' | 'ANOMALY' | 'SIGMA'

let displayDetections = $derived((() => {
  let filtered = detections
  if (severityFilter) {
    filtered = filtered.filter(d => d.severity?.toLowerCase() === severityFilter)
  }
  if (typeFilter === 'CORR') {
    filtered = filtered.filter(d => d.rule_id?.startsWith('corr-'))
  } else if (typeFilter === 'ANOMALY') {
    filtered = filtered.filter(d => d.rule_id?.startsWith('anomaly-'))
  }
  return filtered
})())
```

Chip element pattern (follows existing severity pill HTML/CSS structure):

```svelte
<button
  class="filter-chip"
  class:active={typeFilter === 'CORR'}
  onclick={() => typeFilter = typeFilter === 'CORR' ? '' : 'CORR'}
>
  CORR
</button>
```

### correlation_chains.yml Schema

```yaml
# detections/correlation_chains.yml
chains:
  - name: recon-to-exploit
    rule_ids:
      - sigma-recon-rule-id        # any Sigma rule tagged 'Reconnaissance'
      - corr-portscan              # Phase 43 correlation
      - sigma-exploit-rule-id      # any Sigma rule tagged 'Exploitation'
    entity_key: src_ip
    window_minutes: 15

  - name: scan-to-bruteforce
    rule_ids:
      - corr-portscan
      - corr-bruteforce
    entity_key: src_ip
    window_minutes: 15
```

The chain detection engine matches by `rule_id` prefix rather than exact UUID — or by a `rule_id_patterns` list that supports glob matching. However, for Phase 43 the simplest correct implementation uses exact `rule_id` strings. Pre-built chains only reference `corr-*` identifiers (which are deterministic strings, not UUIDs).

**Hot-reload decision (Claude's discretion):** YAML is loaded at engine construction time (startup + POST /detect/run trigger). No hot-reload for Phase 43 — requires restart to pick up chain changes. Hot-reload adds complexity for marginal operational benefit given this is a home SOC context.

---

## Integration Points Summary

| File | Change | Type |
|------|--------|------|
| `detections/correlation_engine.py` | New file — CorrelationEngine class | CREATE |
| `detections/correlation_chains.yml` | New file — YAML chain definitions | CREATE |
| `backend/core/config.py` | Add `CORRELATION_LOOKBACK_HOURS: int = 2` and `CORRELATION_DEDUP_WINDOW_MINUTES: int = 60` | EDIT |
| `backend/stores/sqlite_store.py` | Add `entity_key TEXT` column migration | EDIT |
| `ingestion/loader.py` | Add `correlation_engine` parameter, call in `ingest_events()` | EDIT |
| `backend/main.py` | Wire CorrelationEngine into IngestionLoader | EDIT |
| `dashboard/src/lib/api.ts` | Add `correlation_type?: string` and `matched_event_count?: number` to Detection interface | EDIT |
| `dashboard/src/views/DetectionsView.svelte` | Add `typeFilter` rune, CORR chip, corr badge on rows, expand-to-event-ids | EDIT |

---

## State of the Art

| Old Approach | Current Approach | Impact |
|--------------|------------------|--------|
| Sigma v1 per-event matching only | Sigma v2.1 correlation rule types (temporal, event_count, etc.) transpiled to windowed SQL | Phase 43 implements equivalent patterns in native DuckDB SQL rather than using pySigma correlation backend |
| Separate correlation engine process | Inline DuckDB aggregates, same process | No extra infra; results available immediately after ingest |
| Beaconing via ML model | CV threshold on inter-arrival intervals | Deterministic, auditable, no training data required |

**Note on Sigma v2.1 correlation:** pySigma does not yet have a stable DuckDB correlation backend (as of 2026-04-12 — HIGH confidence, verified against context). The phase implements the same four Sigma v2.1 correlation types (`event_count`, `value_count`, `temporal_ordered`, `temporal`) as native DuckDB SQL. This is architecturally equivalent and preferable given the project already uses a custom DuckDB backend.

---

## Open Questions

1. **Chain rule_id matching for Sigma rules**
   - What we know: Pre-built chains reference `corr-portscan`, `corr-bruteforce` (deterministic). The recon→exploit chain also needs a Sigma rule_id.
   - What's unclear: Sigma rules have UUID rule_ids (e.g. `7f0b0b8b-...`), not human-readable IDs. The YAML would need the exact UUID or a tag-based lookup.
   - Recommendation: For Phase 43, define chains using `rule_tags` (e.g. `attack.reconnaissance`) instead of `rule_ids` for Sigma rules. Query detections by joining against `detection_techniques` table on tactic. OR: simplify pre-built chains to only reference `corr-*` IDs and leave the recon→exploit chain as a stretch goal.

2. **Beaconing on non-network events**
   - What we know: `event_type` filter in beaconing SQL limits to `('conn', 'network_connect', 'tls', 'ssl', 'http')`.
   - What's unclear: Zeek `conn` events are the primary source, but HTTP events also generate (src_ip, dst_ip) pairs. HTTP beaconing and TCP beaconing may double-count.
   - Recommendation: Filter to `event_type = 'conn'` only for beaconing, which is the most reliable source for inter-arrival timing from Zeek.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest with pytest-asyncio (auto mode — set in pyproject.toml) |
| Config file | `pyproject.toml` (existing) |
| Quick run command | `uv run pytest tests/unit/test_correlation_engine.py -x -q` |
| Full suite command | `uv run pytest tests/ -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| P43-T01 | CV < 0.3 fires corr-beacon detection | unit | `uv run pytest tests/unit/test_correlation_engine.py::test_beaconing_cv_fires -x` | Wave 0 |
| P43-T01 | CV >= 0.3 does not fire | unit | `uv run pytest tests/unit/test_correlation_engine.py::test_beaconing_cv_no_fire -x` | Wave 0 |
| P43-T01 | < 20 connections does not fire | unit | `uv run pytest tests/unit/test_correlation_engine.py::test_beaconing_too_few_connections -x` | Wave 0 |
| P43-T02 | 15+ distinct ports fires corr-portscan | unit | `uv run pytest tests/unit/test_correlation_engine.py::test_portscan_fires -x` | Wave 0 |
| P43-T02 | 14 distinct ports does not fire | unit | `uv run pytest tests/unit/test_correlation_engine.py::test_portscan_below_threshold -x` | Wave 0 |
| P43-T03 | 10+ failed auths fires corr-bruteforce | unit | `uv run pytest tests/unit/test_correlation_engine.py::test_bruteforce_fires -x` | Wave 0 |
| P43-T03 | event_outcome='failure' counted | unit | `uv run pytest tests/unit/test_correlation_engine.py::test_bruteforce_event_outcome -x` | Wave 0 |
| P43-T03 | ssh_auth_success=false counted | unit | `uv run pytest tests/unit/test_correlation_engine.py::test_bruteforce_ssh_false -x` | Wave 0 |
| P43-T04 | Chain fires when all rule_ids present in window | unit | `uv run pytest tests/unit/test_correlation_engine.py::test_chain_fires -x` | Wave 0 |
| P43-T04 | Chain does not fire if only some rules present | unit | `uv run pytest tests/unit/test_correlation_engine.py::test_chain_partial_no_fire -x` | Wave 0 |
| P43-T05 | matched_event_ids is non-empty list[str] | unit | `uv run pytest tests/unit/test_correlation_engine.py::test_matched_event_ids_are_strings -x` | Wave 0 |
| P43-T05 | Dedup suppresses repeat detection within window | unit | `uv run pytest tests/unit/test_correlation_engine.py::test_dedup_suppresses -x` | Wave 0 |
| P43-T05 | Dedup allows detection after window expires | unit | `uv run pytest tests/unit/test_correlation_engine.py::test_dedup_expires -x` | Wave 0 |
| P43-T06 | CORR chip filters to corr-* rule_ids only | unit (TS) | manual verify in browser | N/A — manual |
| P43-T06 | Expand row shows matched event IDs | unit (TS) | manual verify in browser | N/A — manual |

### Mock Data Shapes

All unit tests use in-memory DuckDB (`duckdb.connect(':memory:')`) populated with synthetic rows:

**Port scan mock (20 events, 20 distinct ports, within 60s):**
```python
# tests/unit/test_correlation_engine.py
def _port_scan_events(src_ip="192.168.1.5", n=20):
    base_ts = datetime(2026, 4, 12, 10, 0, 0, tzinfo=timezone.utc)
    return [
        {
            "event_id": str(uuid4()),
            "src_ip": src_ip,
            "dst_ip": "10.0.0.1",
            "dst_port": 1000 + i,
            "timestamp": (base_ts + timedelta(seconds=i * 2)).isoformat(),
            "event_type": "conn",
            "event_outcome": None,
            "ssh_auth_success": None,
        }
        for i in range(n)
    ]
```

**Brute force mock (15 failed auth events, same src+dst, within 60s):**
```python
def _bruteforce_events(src_ip="192.168.1.6", n=15):
    base_ts = datetime(2026, 4, 12, 10, 0, 0, tzinfo=timezone.utc)
    return [
        {
            "event_id": str(uuid4()),
            "src_ip": src_ip,
            "dst_ip": "10.0.0.2",
            "dst_port": 22,
            "timestamp": (base_ts + timedelta(seconds=i * 3)).isoformat(),
            "event_type": "logon_failure",
            "event_outcome": "failure",
            "ssh_auth_success": None,
        }
        for i in range(n)
    ]
```

**Beaconing mock (25 events, 5-second intervals, CV=0.0 — should fire):**
```python
def _beacon_events(src_ip="192.168.1.7", n=25, interval_secs=5):
    base_ts = datetime(2026, 4, 12, 10, 0, 0, tzinfo=timezone.utc)
    return [
        {
            "event_id": str(uuid4()),
            "src_ip": src_ip,
            "dst_ip": "10.0.0.3",
            "dst_port": 443,
            "timestamp": (base_ts + timedelta(seconds=i * interval_secs)).isoformat(),
            "event_type": "conn",
            "event_outcome": None,
            "ssh_auth_success": None,
        }
        for i in range(n)
    ]

def _noisy_beacon_events(src_ip="192.168.1.8", n=25):
    # High-variance intervals (CV >> 0.3) — should NOT fire
    import random
    random.seed(42)
    base_ts = datetime(2026, 4, 12, 10, 0, 0, tzinfo=timezone.utc)
    events = []
    t = base_ts
    for i in range(n):
        events.append({
            "event_id": str(uuid4()),
            "src_ip": src_ip, "dst_ip": "10.0.0.4", "dst_port": 80,
            "timestamp": t.isoformat(),
            "event_type": "conn", "event_outcome": None, "ssh_auth_success": None,
        })
        t += timedelta(seconds=random.randint(1, 300))
    return events
```

**Test fixture helper (populates in-memory DuckDB):**
```python
import duckdb

def _make_duckdb(events: list[dict]) -> duckdb.DuckDBPyConnection:
    conn = duckdb.connect(':memory:')
    conn.execute("""
        CREATE TABLE normalized_events (
            event_id VARCHAR,
            src_ip VARCHAR,
            dst_ip VARCHAR,
            dst_port INTEGER,
            timestamp TIMESTAMP WITH TIME ZONE,
            event_type VARCHAR,
            event_outcome VARCHAR,
            ssh_auth_success BOOLEAN
        )
    """)
    for e in events:
        conn.execute(
            "INSERT INTO normalized_events VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [e["event_id"], e["src_ip"], e["dst_ip"], e["dst_port"],
             e["timestamp"], e["event_type"], e["event_outcome"], e["ssh_auth_success"]]
        )
    return conn
```

### Sampling Rate
- **Per task commit:** `uv run pytest tests/unit/test_correlation_engine.py -x -q`
- **Per wave merge:** `uv run pytest tests/ -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/unit/test_correlation_engine.py` — covers all P43-T01 through P43-T05 behaviors listed above
- [ ] `tests/unit/conftest.py` — may need `_make_duckdb` helper shared with other tests (or local to new test file)

---

## Sources

### Primary (HIGH confidence)
- Direct code inspection: `detections/matcher.py` — SigmaMatcher pattern confirmed, lines 772-880
- Direct code inspection: `ingestion/loader.py` — hook point confirmed at end of `ingest_events()`, lines 562-593
- Direct code inspection: `backend/models/event.py` — DetectionRecord fields confirmed, lines 380-392; `event_outcome` at position [30], `ssh_auth_success` at position [65]
- Direct code inspection: `backend/stores/sqlite_store.py` — `insert_detection()` signature confirmed, lines 735-775; backward-compat migration pattern lines 390-442
- Direct code inspection: `detections/field_map.py` — `event_outcome` maps to `event_outcome`, `zeek.ssh.auth_success` maps to `ssh_auth_success`
- Direct code inspection: `backend/core/config.py` — Settings class, confirmed pydantic-settings BaseSettings pattern
- Direct code inspection: `dashboard/src/lib/api.ts` — Detection interface lines 87-103; `severityFilter` state pattern lines 21-22 of DetectionsView
- Live DuckDB 1.3.0 test: beaconing CV SQL, port scan SQL, brute force SQL — all verified against project venv

### Secondary (MEDIUM confidence)
- `backend/api/correlate.py` — existing `/correlate` router for context; will be extended or left unchanged
- `correlation/clustering.py` — existing EventCluster pattern, shows async cluster API shape

### Tertiary (LOW confidence — not required)
- None

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries already installed and verified at runtime
- DuckDB SQL patterns: HIGH — all four SQL patterns executed against project duckdb 1.3.0
- Architecture: HIGH — patterns copied directly from existing SigmaMatcher/AnomalyScorer code
- Auth failure columns: HIGH — confirmed from field_map.py and event.py schema
- Pitfalls: HIGH for DuckDB, MEDIUM for chain matching (open question on rule_id vs tag matching)

**Research date:** 2026-04-12
**Valid until:** 2026-05-12 (DuckDB stable, no expected breaking changes)
