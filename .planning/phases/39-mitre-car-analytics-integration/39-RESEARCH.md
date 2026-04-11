# Phase 39: MITRE CAR Analytics Integration - Research

**Researched:** 2026-04-11
**Domain:** MITRE CAR catalog ingestion, SQLite reference store, detection-time enrichment, Svelte 5 expandable rows
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **CAR data source:** Bundle full JSON snapshot of CAR catalog in `backend/data/car_analytics.json` — committed to repo, no GitHub dependency at runtime. Full catalog (~102 analytics as of research date, context says ~130), not curated subset. Seed into DB at startup.
- **Storage:** SQLite table, not DuckDB — consistent with all other reference/catalog data (STIX, IOC store, playbooks). DuckDB remains for time-series events only.
- **Enrichment timing:** CAR lookup happens synchronously at detection time — same pattern as Phase 33 IOC matching. `attack_technique` ID from fired Sigma rule → SQLite SELECT → matched analytics attached to detection record. If no `attack_technique` → `car_analytics` field is null/omitted.
- **CAR data embedded** as nested object(s) directly in the GET /api/detections response — no separate endpoint.
- **Expandable row:** Click a detection row to expand inline panel below the row — not a side drawer, not a separate tab.
- **All four CAR fields shown:** ID + title + description, log sources required, analyst guidance/notes, implementation pseudocode.
- **Two outbound links:** CAR analytic link (car.mitre.org/analytics/CAR-XXXX-XX-XXX) + ATT&CK technique link (attack.mitre.org/techniques/TXXXX).
- **Match scope:** Show all CAR analytics that match the technique, not just one. Each analytic as a separate card, ordered by analytic ID.
- **P39-T05 included:** CAR analytics also appear in the investigation evidence panel (not DetectionsView only).

### Claude's Discretion
- Exact SQLite schema for the car_analytics table (columns, indexes)
- Exact JSON structure of the bundled snapshot (transformation from raw CAR YAML format)
- How to display multiple CAR analytics in the expanded row (stacked cards vs tabs vs accordion)
- How CAR analytics surface in the investigation evidence panel (new section, or appended to existing technique evidence)
- Whether to add a `car_analytic_ids` TEXT column to the detections table or compute at query time via JOIN

### Deferred Ideas (OUT OF SCOPE)
- CAR catalog refresh/update mechanism (scripts/update_car.py) — future phase
- CAR analytics in HuntingView — future phase
- CAR pseudocode → Sigma rule auto-generation — separate, complex phase
- CAR coverage heatmap — future phase
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| P39-T01 | Ingest CAR analytics catalog into new SQLite table | CARStore DDL pattern from AttackStore; seed from bundled JSON at startup |
| P39-T02 | Map Sigma rule ATT&CK technique IDs to CAR analytic IDs at detection time | `attack_technique` field already on detections table; sync lookup in `save_detections()` after technique tagging |
| P39-T03 | Enrich GET /api/detections response with matched CAR analytic(s) as `car_analytics` field | JOIN at query time in `detect.py` `_query()` function; embed list of analytic dicts |
| P39-T04 | Update DetectionsView to show expandable row with CAR analytic panel | New $state expandedId + `{#if d.id === expandedId}` row approach; no prior pattern exists |
| P39-T05 | Add CAR analytic section to investigation evidence panel | Inject car_analytics via attack_technique lookup in `/api/investigate` POST response |
</phase_requirements>

---

## Summary

Phase 39 is a pure enrichment layer: ingest 102 CAR analytics from a pre-bundled JSON snapshot into SQLite, then surface matched analytics wherever a detection has an `attack_technique` tag. The data pipeline mirrors Phase 34 (AttackStore) exactly — a standalone store class that takes `sqlite3.Connection`, its own DDL, a startup seed function, and sync query methods. The detection enrichment mirrors Phase 33 (IOC matching) — a synchronous lookup in `save_detections()` that runs inside the `asyncio.to_thread()` block already serializing SQLite writes.

The CAR YAML schema is well-defined: `id`, `title`, `description`, `coverage` (list with `technique`, `subtechniques`, `tactics`, `coverage` fields), and `implementations` (list with `code`, `type`, `description`). The bundled JSON snapshot must be pre-processed from raw YAML into a flat-lookup-friendly format keyed by technique ID. The 102-analytic catalog is small enough that an in-process dictionary lookup is viable, but a SQLite JOIN query is more consistent with the project pattern and handles future catalog growth.

The frontend work introduces a new expandable row pattern in DetectionsView — the first inline expansion in the project. The Svelte 5 pattern is straightforward: one `$state<string | null>` for the expanded detection ID, toggled on row click, with a conditional `<tr class="car-panel-row">` injected after the matching data row inside the `{#each}` loop. The investigation evidence panel (P39-T05) adds a new section to the `POST /api/investigate` response at negligible backend cost.

**Primary recommendation:** Implement CARStore as a standalone class in `backend/services/car/car_store.py`, seed from `backend/data/car_analytics.json` at startup, do CAR lookup in `save_detections()` storing result as JSON in a new `car_analytics` column on the detections table, and surface it via the existing GET /api/detect endpoint.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| sqlite3 | stdlib | CAR analytics table | Matches all other reference data stores in project |
| PyYAML | 6.0.3 | Parse raw CAR YAML files during bundle generation | Already a project dependency (pyproject.toml line 26) |
| json (stdlib) | stdlib | Serialize/deserialize CAR data in SQLite TEXT columns | Project-wide pattern for JSON blobs in SQLite |
| asyncio.to_thread | stdlib | Wrap sync SQLite reads in async context | Mandatory pattern per CLAUDE.md |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| httpx | pinned | Download CAR YAML files from GitHub (bundle generation only, not runtime) | Only needed if generating the bundle from scratch |
| pathlib | stdlib | Locate `backend/data/car_analytics.json` at startup seed | Standard for all data file paths |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| SQLite TEXT column for `car_analytics` on detections | New JOIN table `detection_car_analytics` | JOIN table is cleaner for large datasets, but TEXT blob on detections is simpler and consistent with how `matched_event_ids` is stored — prefer TEXT column per existing pattern |
| In-process dict lookup at query time | SQLite `car_analytics` table query | Dict would require rebuilding on every restart; SQLite is persistent and consistent with all other reference data |

**Installation:** No new dependencies required. PyYAML 6.0.3 is already installed.

---

## Architecture Patterns

### Recommended Project Structure
```
backend/
├── services/
│   └── car/
│       ├── __init__.py
│       └── car_store.py         # CARStore class + DDL + seed helper
├── data/
│   └── car_analytics.json       # Pre-bundled CAR catalog (102 analytics)
│   └── builtin_playbooks.py     # Existing — reference pattern
tests/
└── unit/
    └── test_car_store.py        # Wave 0 stubs for P39-T01, P39-T02
```

### Pattern 1: CARStore — Mirrors AttackStore
**What:** Standalone class wrapping `sqlite3.Connection`, owns DDL, provides `get_analytics_for_technique(technique_id) -> list[dict]`.
**When to use:** Consistent with `AttackStore` and `IocStore` — all reference data stores share this pattern.
**Example:**
```python
# Source: backend/services/attack/attack_store.py — copy this pattern exactly
class CARStore:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        self._conn.executescript(DDL)
        self._conn.commit()

    def analytic_count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM car_analytics").fetchone()[0]

    def get_analytics_for_technique(self, technique_id: str) -> list[dict]:
        """
        Return all CAR analytics that cover the given ATT&CK technique ID.
        technique_id should be normalized uppercase, e.g. "T1059".
        Includes sub-technique parent lookup (T1059.001 → T1059).
        Returns list of dicts, ordered by analytic_id ASC.
        """
        parent_id = technique_id.split(".")[0].upper()
        rows = self._conn.execute(
            """
            SELECT analytic_id, title, description, log_sources,
                   analyst_notes, pseudocode, coverage_level
            FROM car_analytics
            WHERE technique_id = ?
            ORDER BY analytic_id ASC
            """,
            (parent_id,),
        ).fetchall()
        return [dict(row) for row in rows]
```

### Pattern 2: Startup Seed — Mirrors seed_builtin_playbooks()
**What:** Async seed function called in lifespan, checks if table empty, inserts from bundled JSON.
**When to use:** Idempotent startup seeding — same as CISA playbooks.
**Example:**
```python
# Source: backend/api/playbooks.py seed_builtin_playbooks() — copy this pattern
async def seed_car_analytics(car_store: CARStore) -> None:
    """Seed CAR analytics from bundled JSON on startup. Idempotent."""
    if car_store.analytic_count() > 0:
        log.info("CAR analytics already seeded — skipping")
        return
    data_path = Path(__file__).parent.parent / "data" / "car_analytics.json"
    analytics = json.loads(data_path.read_text(encoding="utf-8"))
    await asyncio.to_thread(car_store.bulk_insert, analytics)
    log.info("CAR analytics seeded: %d analytics", car_store.analytic_count())
```

### Pattern 3: Detection-Time CAR Lookup — Mirrors _apply_ioc_matching()
**What:** Synchronous lookup inside the `asyncio.to_thread()` block in `save_detections()`. Runs after ATT&CK technique tagging.
**When to use:** Called only when `attack_technique` is not None on the detection.
**Example:**
```python
# Source: backend/services/intel/ioc_store.py _apply_ioc_matching() pattern
# In matcher.py save_detections() _sync_save() inner function:
if det.attack_technique and car_store:
    car_hits = car_store.get_analytics_for_technique(det.attack_technique)
    car_json = json.dumps(car_hits) if car_hits else None
    conn.execute(
        "UPDATE detections SET car_analytics = ? WHERE id = ?",
        (car_json, det.id),
    )
```

### Pattern 4: Expandable Row in Svelte 5
**What:** `$state<string | null>` tracking the expanded detection ID. Toggle on row click. Inject a second `<tr>` into the `{#each}` loop when expanded.
**When to use:** First expandable row in the project — this pattern will be referenced by future phases.
**Example:**
```svelte
<!-- Svelte 5 runes pattern — no stores -->
let expandedId = $state<string | null>(null)

function toggleExpand(id: string) {
  expandedId = expandedId === id ? null : id
}

{#each detections as d}
  <tr
    class:expanded={expandedId === getDetectionId(d)}
    onclick={() => toggleExpand(getDetectionId(d))}
    style="cursor: pointer;"
  >
    <!-- existing cells + chevron in Actions column -->
    <td class="actions-cell">
      <span class="chevron">{expandedId === getDetectionId(d) ? '▾' : '▸'}</span>
      <!-- existing investigate button -->
    </td>
  </tr>
  {#if expandedId === getDetectionId(d) && d.car_analytics?.length}
    <tr class="car-panel-row">
      <td colspan="7" class="car-panel-cell">
        {#each d.car_analytics as analytic}
          <!-- CAR analytic card -->
        {/each}
      </td>
    </tr>
  {/if}
{/each}
```

### Anti-Patterns to Avoid
- **Storing CAR data in DuckDB:** DuckDB is for time-series events only. All reference data is SQLite. Using DuckDB here would violate the single-writer pattern without benefit.
- **Fetching CAR data from GitHub at runtime:** The bundled JSON must be committed to the repo. Network calls at startup make the app fragile.
- **Separate `/api/car` endpoint for the enrichment:** The user decision is clear — embed `car_analytics` nested in the detection response. A separate endpoint forces two round-trips in the frontend.
- **Using Svelte stores instead of runes:** CLAUDE.md explicitly forbids `writable()` and `svelte:store`. Use `$state()`.
- **Tabs for multiple CAR analytics:** Context.md specifically calls out stacked cards as the correct pattern — tabs hide content analysts need to compare.
- **Returning only the first CAR match:** Some techniques (e.g. T1059) have 4+ CAR entries. All must be returned.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Technique-to-analytic mapping | Custom dict built at app startup | SQLite `car_analytics` table with `technique_id` index | Persistent across restarts, queryable, consistent with project pattern |
| CAR YAML → JSON transformation | Custom parser | PyYAML (already installed) + one-time script | YAML parsing edge cases handled by PyYAML; script runs once during bundle generation, not at runtime |
| Expandable table rows | Custom accordion component | Native `<tr>` injection pattern in Svelte 5 `{#each}` | No additional dependencies; keeps table structure valid HTML |

**Key insight:** The entire phase is an assembly job — all primitive operations (SQLite store class, startup seed, detection enrichment, nested API response, Svelte 5 state management) have exact prior-art patterns in the codebase.

---

## Common Pitfalls

### Pitfall 1: Technique ID Normalization
**What goes wrong:** CAR YAML uses `T1053` (uppercase, no sub-technique prefix), detections store `T1053.005` (sub-technique). A literal match returns zero rows.
**Why it happens:** MITRE CAR coverage maps to parent technique only. Sigma rules often tag the sub-technique.
**How to avoid:** In `get_analytics_for_technique()`, always normalize: `parent_id = technique_id.split(".")[0].upper()` before the SELECT query.
**Warning signs:** CAR lookup returns empty list even for well-known techniques like T1059.

### Pitfall 2: SQLite Row Factory Not Set
**What goes wrong:** `sqlite3.Row` objects returned from `_conn.execute().fetchall()` — but `CARStore.__init__` takes an existing connection from `SQLiteStore`. If `row_factory` not set on that shared connection, `dict(row)` calls fail.
**Why it happens:** `SQLiteStore.__init__` does set `self._conn.row_factory = sqlite3.Row` (line 367 of sqlite_store.py), so the shared connection already has row_factory set. No issue in production. But in unit tests that create a bare `sqlite3.connect()`, row_factory must be set manually.
**How to avoid:** In test helper `_make_conn()`, always set `conn.row_factory = sqlite3.Row` (see test_attack_store.py line 38 — copy exactly).
**Warning signs:** `TypeError: 'sqlite3.Row' object is not subscriptable` in unit tests.

### Pitfall 3: car_analytics Column Missing from detections Table at Detection Time
**What goes wrong:** `UPDATE detections SET car_analytics = ? WHERE id = ?` fails because the column doesn't exist yet.
**Why it happens:** The `detections` table DDL in `_DDL` (sqlite_store.py) does not include `car_analytics`. The column must be added via an idempotent `ALTER TABLE` migration in `SQLiteStore.__init__`.
**How to avoid:** Add the migration block to `SQLiteStore.__init__` (lines ~373-417 pattern) before the `CARStore` is initialized:
```python
try:
    self._conn.execute(
        "ALTER TABLE detections ADD COLUMN car_analytics TEXT"
    )
    self._conn.commit()
except Exception:
    pass  # column already exists — idempotent
```
**Warning signs:** `sqlite3.OperationalError: table detections has no column named car_analytics`.

### Pitfall 4: JSON Serialization of car_analytics in detect.py Response
**What goes wrong:** The `_query()` function in `detect.py` returns raw SQLite row dicts. The `car_analytics` column is a TEXT JSON blob — it must be `json.loads()`-ed before returning, not returned as a raw string.
**Why it happens:** The existing `matched_event_ids` column has the same pattern — it's a JSON string that is parsed in `_query()` (detect.py lines 91-96). The same treatment is needed for `car_analytics`.
**How to avoid:** In `_query()`, after `d = dict(row)`, add:
```python
if d.get("car_analytics"):
    try:
        d["car_analytics"] = json.loads(d["car_analytics"])
    except Exception:
        d["car_analytics"] = None
```
**Warning signs:** Frontend receives `car_analytics` as a string instead of an array.

### Pitfall 5: car_store Not Available in matcher.py save_detections()
**What goes wrong:** `SigmaMatcher` doesn't have access to `CARStore` because it's initialized before the store is attached.
**Why it happens:** `SigmaMatcher` currently receives `stores` (which has `stores.sqlite`), but `CARStore` is a separate object on `app.state.car_store`. The matcher doesn't have app.state access.
**How to avoid:** Either (a) pass `car_store` as an optional param to `SigmaMatcher.__init__`, or (b) do the CAR lookup in `save_detections()` directly using `stores.sqlite._conn` (since `CARStore` only wraps a connection, you can call the query inline). Option (b) is simplest — avoids changing the `SigmaMatcher` constructor signature.
**Warning signs:** `AttributeError: 'Stores' object has no attribute 'car_store'`.

### Pitfall 6: Multiple Technique Mappings per CAR Analytic
**What goes wrong:** Some CAR analytics cover multiple ATT&CK techniques. If the table has one row per analytic, a technique-indexed lookup may miss some analytics or return duplicates.
**Why it happens:** The CAR YAML `coverage` field is a list — one analytic may list T1053 and T1574. The recommended schema stores one row per (analytic_id, technique_id) pair.
**How to avoid:** Schema should have `analytic_id + technique_id` as a composite natural key, or use a separate join table. The simplest approach: deduplicate in `get_analytics_for_technique()` by `analytic_id` if multiple rows per analytic are possible.
**Warning signs:** Same analytic appearing twice in the expanded panel.

---

## Code Examples

Verified patterns from official sources:

### CARStore DDL (recommended schema)
```python
# Source: backend/services/attack/attack_store.py DDL pattern
DDL = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS car_analytics (
    analytic_id      TEXT NOT NULL,
    technique_id     TEXT NOT NULL,   -- parent technique, e.g. T1059 (not T1059.001)
    title            TEXT NOT NULL,
    description      TEXT NOT NULL DEFAULT '',
    log_sources      TEXT NOT NULL DEFAULT '',   -- human-readable text from coverage + implementations
    analyst_notes    TEXT NOT NULL DEFAULT '',   -- from description + implementation descriptions
    pseudocode       TEXT NOT NULL DEFAULT '',   -- first Pseudocode implementation code block
    coverage_level   TEXT NOT NULL DEFAULT '',   -- Low / Moderate / High
    platforms        TEXT NOT NULL DEFAULT '',   -- JSON array e.g. ["Windows"]
    PRIMARY KEY (analytic_id, technique_id)
);

CREATE INDEX IF NOT EXISTS idx_car_technique ON car_analytics (technique_id);
CREATE INDEX IF NOT EXISTS idx_car_analytic  ON car_analytics (analytic_id);
"""
```

### CAR YAML Schema (verified from github.com/mitre-attack/car)
```yaml
# Source: https://raw.githubusercontent.com/mitre-attack/car/master/analytics/CAR-2020-09-001.yaml
id: CAR-2020-09-001
title: Scheduled Task - FileAccess
description: |
  In order to gain persistence...
platforms:
  - Windows
coverage:
  - technique: T1053          # parent technique
    subtechniques:
      - T1053.005
    tactics:
      - TA0002
    coverage: Low             # Low / Moderate / High
implementations:
  - name: Pseudocode - Windows task file creation
    description: This is a pseudocode representation...
    code: |
      files = search File:Create
      ...
    data_model: CAR native
    type: Pseudocode           # Pseudocode / Splunk / LogPoint / EQL / etc.
data_model_references:
  - file/create/file_path
```

### Bundle Generation Script (run once, output committed to repo)
```python
# Source: Pattern consistent with existing data bundling approach
import yaml, json
from pathlib import Path

analytics_dir = Path("analytics")  # CAR repo checkout
output = []

for yml_path in sorted(analytics_dir.glob("CAR-*.yaml")):
    raw = yaml.safe_load(yml_path.read_text(encoding="utf-8"))
    analytic_id = raw.get("id", "")
    title = raw.get("title", "")
    description = raw.get("description", "").strip()
    platforms = raw.get("platforms", [])

    for cov in raw.get("coverage", []):
        technique = cov.get("technique", "").upper()
        if not technique:
            continue

        # Extract pseudocode
        pseudocode = ""
        log_sources = ""
        for impl in raw.get("implementations", []):
            if impl.get("type") == "Pseudocode" and not pseudocode:
                pseudocode = impl.get("code", "").strip()
            # Log source info comes from data_model_references + implementation descriptions
        log_sources = ", ".join(raw.get("data_model_references", []))

        output.append({
            "analytic_id": analytic_id,
            "technique_id": technique,
            "title": title,
            "description": description,
            "log_sources": log_sources,
            "analyst_notes": "",  # CAR does not have a separate 'notes' field
            "pseudocode": pseudocode,
            "coverage_level": cov.get("coverage", ""),
            "platforms": json.dumps(platforms),
        })

Path("backend/data/car_analytics.json").write_text(
    json.dumps(output, indent=2), encoding="utf-8"
)
```

### TypeScript Interface Extension
```typescript
// Source: dashboard/src/lib/api.ts Detection interface (line 33)
// Add to existing Detection interface:
export interface CARAnalytic {
  analytic_id: string         // e.g. "CAR-2020-09-001"
  technique_id: string        // e.g. "T1053"
  title: string
  description: string
  log_sources: string
  analyst_notes: string
  pseudocode: string
  coverage_level: string      // "Low" | "Moderate" | "High"
  platforms: string           // JSON array string, parse on use
}

// Extend Detection:
export interface Detection {
  // ... existing fields ...
  car_analytics?: CARAnalytic[] | null
}
```

### Svelte 5 Expandable Row Pattern
```svelte
<!-- Source: Svelte 5 runes docs — $state reactive primitive -->
<!-- In script block: -->
let expandedId = $state<string | null>(null)

<!-- In template, inside {#each detections as d}: -->
<tr
  onclick={() => {
    const id = getDetectionId(d)
    expandedId = expandedId === id ? null : id
  }}
  class:row-expanded={expandedId === getDetectionId(d)}
  style="cursor: pointer;"
>
  <!-- existing cells unchanged -->
  <td class="actions-cell">
    <span class="expand-chevron" aria-label="expand">
      {expandedId === getDetectionId(d) ? '▾' : '▸'}
    </span>
    <!-- existing buttons -->
  </td>
</tr>
{#if expandedId === getDetectionId(d)}
  <tr class="car-panel-row">
    <td colspan="7" class="car-panel-cell">
      {#if d.car_analytics?.length}
        {#each d.car_analytics as analytic}
          <div class="car-card">
            <div class="car-card-header">
              <span class="car-id-badge">{analytic.analytic_id}</span>
              <span class="car-title">{analytic.title}</span>
              <span class="car-coverage coverage-{analytic.coverage_level.toLowerCase()}">{analytic.coverage_level}</span>
              <a href="https://car.mitre.org/analytics/{analytic.analytic_id}" target="_blank" rel="noopener noreferrer" class="car-link">CAR ↗</a>
              <a href="https://attack.mitre.org/techniques/{analytic.technique_id}" target="_blank" rel="noopener noreferrer" class="car-link">ATT&CK ↗</a>
            </div>
            <p class="car-description">{analytic.description}</p>
            {#if analytic.log_sources}
              <div class="car-section"><span class="car-label">Log Sources:</span> {analytic.log_sources}</div>
            {/if}
            {#if analytic.pseudocode}
              <pre class="car-pseudocode">{analytic.pseudocode}</pre>
            {/if}
          </div>
        {/each}
      {:else}
        <span class="car-no-analytics">No CAR analytics available for {d.attack_technique ?? 'this detection'}.</span>
      {/if}
    </td>
  </tr>
{/if}
```

---

## CAR Data Reality Check

The CONTEXT.md says "~130 analytics." The GitHub repository as of research date has **102 YAML files**. The discrepancy is acceptable — the bundled count is whatever the catalog contains at bundle generation time. The important facts:

| Property | Value | Source |
|----------|-------|--------|
| Total YAML files in CAR repo | 102 | github.com/mitre-attack/car/tree/master/analytics |
| Date range | CAR-2013-01-002 to CAR-2022-03-001 | Directory listing |
| Top-level YAML fields | id, title, description, platforms, coverage, implementations, data_model_references | Verified from 3 analytics |
| "notes" field | Does NOT exist in CAR YAML | Verified against CAR-2013-04-002.yaml and CAR-2020-09-001.yaml |
| Multiple techniques per analytic | YES — `coverage` is a list | CAR-2014-02-001 maps T1543, T1574, T1569 |
| Implementation types | Pseudocode, Splunk, LogPoint, EQL, others | Verified from CAR-2020-09-001.yaml |
| CAR analytic URL pattern | `https://car.mitre.org/analytics/{analytic_id}/` | car.mitre.org verified |

**Important implication for schema:** The "analyst_notes" column requested in CONTEXT.md does not map to a distinct CAR YAML field. The closest mapping is the `description` field (which provides detection rationale) combined with implementation `description` sub-fields. The `analyst_notes` column should be populated from the implementation descriptions (non-pseudocode implementations) or left empty. The planner should use `description` as the primary guidance field.

---

## State of the Art

| Old Approach | Current Approach | Impact |
|--------------|------------------|--------|
| Inline dict lookup at query time | SQLite `car_analytics` table with compound PK | Persistent, indexed, consistent with project |
| One row per analytic (single technique) | One row per (analytic_id, technique_id) pair | Handles multi-technique analytics correctly |
| Global fetch of all CAR at page load | Nested enrichment in detection response | Zero extra API calls; data available when row is expanded |

**No deprecated patterns identified in this domain.** The CAR repository has not had a major schema change since 2020.

---

## Open Questions

1. **Should `car_analytics` be stored as a column on `detections` or computed via JOIN at query time?**
   - What we know: IOC matching stores results on `normalized_events` columns (`ioc_matched`, `ioc_confidence`). ATT&CK technique tagging uses a separate `detection_techniques` join table. Both patterns exist.
   - What's unclear: Column on detections is simpler for the detect.py `_query()` function; join table is more normalized.
   - Recommendation: Store as TEXT column on `detections` (JSON array of dicts) — mirrors `matched_event_ids` pattern, single query, no JOIN complexity. The planner should decide based on implementation simplicity preference.

2. **How should CAR analytics appear in the investigation evidence panel?**
   - What we know: The `POST /api/investigate` response has keys: detection, events, graph, timeline, attack_chain, techniques, entity_clusters, summary. None of these is dedicated to CAR.
   - What's unclear: Should `car_analytics` be a new top-level key, or attached to the `detection` sub-object?
   - Recommendation: Add `car_analytics` as a new top-level key in the investigate response, populated by doing the same CAR lookup when the detection has an `attack_technique`. Frontend reads it as a separate panel in InvestigationView.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (asyncio mode: auto) |
| Config file | pyproject.toml |
| Quick run command | `uv run pytest tests/unit/test_car_store.py -x -q` |
| Full suite command | `uv run pytest tests/unit/ -x -q` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| P39-T01 | CARStore DDL creates `car_analytics` table | unit | `uv run pytest tests/unit/test_car_store.py::test_car_store_table_exists -x` | ❌ Wave 0 |
| P39-T01 | `bulk_insert()` seeds 102 analytics from list | unit | `uv run pytest tests/unit/test_car_store.py::test_bulk_insert_seeding -x` | ❌ Wave 0 |
| P39-T01 | `analytic_count()` returns correct count after seed | unit | `uv run pytest tests/unit/test_car_store.py::test_analytic_count -x` | ❌ Wave 0 |
| P39-T02 | `get_analytics_for_technique("T1059")` returns non-empty list | unit | `uv run pytest tests/unit/test_car_store.py::test_get_analytics_for_technique -x` | ❌ Wave 0 |
| P39-T02 | Sub-technique lookup `T1059.001` resolves to parent `T1059` | unit | `uv run pytest tests/unit/test_car_store.py::test_subtechnique_normalization -x` | ❌ Wave 0 |
| P39-T02 | No-match technique returns empty list | unit | `uv run pytest tests/unit/test_car_store.py::test_no_match_returns_empty -x` | ❌ Wave 0 |
| P39-T03 | Detection with `attack_technique` returns `car_analytics` field | unit | `uv run pytest tests/unit/test_car_store.py::test_detection_enrichment_field -x` | ❌ Wave 0 |
| P39-T03 | Detection without `attack_technique` omits `car_analytics` | unit | `uv run pytest tests/unit/test_car_store.py::test_detection_no_technique_null -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/unit/test_car_store.py -x -q`
- **Per wave merge:** `uv run pytest tests/unit/ -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/unit/test_car_store.py` — covers P39-T01, P39-T02, P39-T03 (8 stubs listed above)
- [ ] `backend/services/car/__init__.py` — empty init file for module
- [ ] `backend/services/car/car_store.py` — CARStore class (Wave 0: stubs, Wave 1: implementation)
- [ ] `backend/data/car_analytics.json` — bundled CAR catalog (must be generated + committed in Wave 0/Task 1)

---

## Sources

### Primary (HIGH confidence)
- `backend/services/attack/attack_store.py` — CARStore design copies this exactly
- `backend/services/intel/ioc_store.py` — IocStore pattern for detection-time enrichment
- `backend/main.py` lifespan (lines 162-310) — startup seed wiring pattern
- `backend/api/detect.py` — detection query and response enrichment target
- `backend/stores/sqlite_store.py` — SQLiteStore migration pattern (lines 373-417)
- `backend/api/playbooks.py` `seed_builtin_playbooks()` — startup seed function pattern
- `dashboard/src/views/DetectionsView.svelte` — current table structure, no expansion yet
- `dashboard/src/views/PlaybooksView.svelte` — ATT&CK chip visual pattern (lines 316-328)
- https://raw.githubusercontent.com/mitre-attack/car/master/analytics/CAR-2020-09-001.yaml — CAR YAML schema verified
- https://raw.githubusercontent.com/mitre-attack/car/master/analytics/CAR-2013-04-002.yaml — Confirmed no 'notes' field

### Secondary (MEDIUM confidence)
- https://github.com/mitre-attack/car/tree/master/analytics — 102 analytics confirmed via directory listing
- https://car.mitre.org/analytics/CAR-2020-09-001/ — URL pattern for outbound links verified

### Tertiary (LOW confidence)
- N/A

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all dependencies already in project; CAR YAML schema verified from source
- Architecture: HIGH — every pattern has exact prior-art in the codebase (Phases 33/34/38)
- Pitfalls: HIGH — all identified from direct code inspection of existing patterns
- CAR data schema: HIGH — verified directly from YAML source files in GitHub

**Research date:** 2026-04-11
**Valid until:** 2026-07-11 (CAR catalog stable since 2022; MITRE rarely changes schema)
