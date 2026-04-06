# Phase 26: Graph Schema Versioning and Perimeter Entities — Research

**Researched:** 2026-04-06
**Domain:** SQLite graph schema migration, graph constants, FastAPI endpoint, Cytoscape.js dashboard rendering
**Confidence:** HIGH

---

## Summary

Phase 26 is a purely additive schema and constant extension. The graph subsystem already has a stable foundation: `graph/schema.py` holds typed lists of ENTITY_TYPES and EDGE_TYPES; `backend/stores/sqlite_store.py` runs all migrations inline in `__init__` via idempotent `ALTER TABLE ... ADD COLUMN` wrapped in try/except; `backend/api/graph.py` exposes standard CRUD and traversal endpoints; and `dashboard/src/views/GraphView.svelte` renders nodes with Cytoscape.js using a `typeColors` dict keyed on `entity.type`.

The schema-versioning mechanism (P26-T01) will use the existing `system_kv` table (`key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at TEXT NOT NULL`) — already present in the DDL — as the store for `graph_schema_version`. This avoids adding a dedicated table; the pattern matches how the project already stores small key-value metadata. The new GET `/api/graph/schema-version` endpoint is a minimal addition to `backend/api/graph.py`. Migration sets the key to `"1.0.0"` for pre-existing installs (idempotent: INSERT OR IGNORE) and to `"2.0.0"` for fresh installs.

The two new perimeter node types (`firewall_zone`, `network_segment`) and three new edge types (`blocks`, `permits`, `traverses`) are constant additions to `graph/schema.py` — no DB DDL changes are required because entities and edges are schema-agnostic (type is stored as a TEXT field). The IPFire syslog parser exists (`ingestion/parsers/ipfire_syslog_parser.py`) and currently produces `NormalizedEvent` objects but does NOT create graph entities or edges. P26-T03 requires a new graph-emission step in the parser or the ingest loader to create `firewall_zone` nodes and `blocks`/`permits`/`traverses` edges from IPFire events. The dashboard extension is a CSS-style addition to `typeColors` in `GraphView.svelte` plus optional Cytoscape selector rules for the new edge types.

**Primary recommendation:** Use `system_kv` for version storage, keep all migration logic in `SQLiteStore.__init__` using the existing try/except INSERT OR IGNORE pattern, extend `graph/schema.py` constants only (no DDL), and add graph-emission logic to the IPFire parser path rather than the normalizer.

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| P26-T01 | `graph_schema_version` in graph metadata (SQLite); current version "2.0.0"; migration defaults pre-existing installs to "1.0.0"; GET /api/graph/schema-version returns current version | `system_kv` table confirmed present in DDL; INSERT OR IGNORE pattern confirmed; new route in `graph.py` router |
| P26-T02 | `firewall_zone` node (zone_name, zone_color [RED/GREEN/ORANGE/BLUE], interface) and `network_segment` node (cidr, zone, description) added to `graph/schema.py` constants; existing types unchanged | ENTITY_TYPES list confirmed; additive append is safe; no DDL changes needed |
| P26-T03 | `blocks`, `permits`, `traverses` edge types added; edges created by IPFire syslog parser on ingest; existing edge types unchanged | EDGE_TYPES list confirmed; IPFire parser exists and produces NormalizedEvent; graph-emission step needs to be added (loader.py or parser hook) |
| P26-T04 | Migration uses ALTER TABLE ADD COLUMN only (never DROP/MODIFY); migration test asserts no existing columns/tables removed; Malcolm/OpenSearch parser test asserts existing field preservation | Existing migration pattern confirmed (try/except ALTER TABLE); test pattern exists in test_sqlite_store.py and test_duckdb_migration.py |
| P26-T05 | Dashboard graph rendering — firewall_zone nodes with zone-color coding; network_segment nodes as subnet bubbles; new edge types with distinct styles; human visual verification checkpoint | `typeColors` dict in GraphView.svelte confirmed; Cytoscape.js selector pattern confirmed; human-verify checkpoint required |
</phase_requirements>

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| sqlite3 (stdlib) | Python 3.12 | Graph entity/edge persistence | Already the project's graph store |
| FastAPI | current (project) | New schema-version endpoint | All API routes are FastAPI |
| Cytoscape.js | current (npm) | Graph rendering with perimeter node styles | Already used in GraphView.svelte via `cytoscape` and `cytoscape-fcose`/`cytoscape-dagre` |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pydantic (BaseModel) | current (project) | Schema-version response model | If a typed response model is needed for the endpoint |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `system_kv` for version storage | Dedicated `graph_metadata` table | New table is heavier; `system_kv` is already present and purpose-built for key-value metadata |
| Inline migration in `__init__` | Alembic or standalone migration script | Alembic adds overhead; project pattern is inline idempotent migrations |

**Installation:** No new packages required for backend. No new npm packages required for dashboard.

---

## Architecture Patterns

### Recommended Project Structure
```
graph/
  schema.py            # Add firewall_zone, network_segment to ENTITY_TYPES
                       # Add blocks, permits, traverses to EDGE_TYPES
backend/
  stores/
    sqlite_store.py    # Add graph_schema_version migration in __init__
                       # Add get_graph_schema_version() helper method
  api/
    graph.py           # Add GET /graph/schema-version endpoint
ingestion/
  parsers/
    ipfire_syslog_parser.py  # Add graph entity/edge emission helpers
                              # (or call from loader.py)
dashboard/src/
  views/
    GraphView.svelte   # Add firewall_zone, network_segment to typeColors
                       # Add Cytoscape selector rules for new edge types
tests/unit/
  test_graph_schema.py        # New: P26-T02 constants tests
  test_graph_schema_version.py # New: P26-T01 migration + endpoint tests
  test_perimeter_edges.py     # New: P26-T03 IPFire graph emission tests
  test_additive_migration.py  # New: P26-T04 no-drop assertion
```

### Pattern 1: system_kv for Schema Version Storage
**What:** Read/write `graph_schema_version` from the `system_kv` table using INSERT OR IGNORE (fresh install sets "2.0.0") and a separate UPDATE for upgrades.
**When to use:** Any time a lightweight metadata value needs to survive DB restarts without a dedicated table.
**Example:**
```python
# In SQLiteStore.__init__, after existing migrations:

# Fresh install: insert version 2.0.0 (only if key absent)
try:
    self._conn.execute(
        "INSERT OR IGNORE INTO system_kv (key, value, updated_at) VALUES (?, ?, ?)",
        ("graph_schema_version", "2.0.0", _now_iso()),
    )
    self._conn.commit()
except Exception:
    pass

# Pre-existing install: if key present but value is old, leave it at 1.0.0
# (no UPDATE — the migration rule is: first write wins)
```
**Pre-existing install default:** If `system_kv` row for `graph_schema_version` was absent (pre-existing DB), the INSERT OR IGNORE will SET it. But the requirement says pre-existing installs must default to "1.0.0". This requires a two-step approach:
1. Check if `entities` table has any rows (proxy for existing install).
2. If rows exist AND no version key present, INSERT "1.0.0".
3. If rows absent AND no version key present, INSERT "2.0.0".

A simpler and more robust approach: always INSERT OR IGNORE "1.0.0" first, then if this is a clean schema run (all tables were just created), UPDATE to "2.0.0". The cleanest implementation: insert "1.0.0" always via INSERT OR IGNORE, then add a separate upgrade path that bumps to "2.0.0" when all phase-26 types are confirmed present.

**Simplest correct approach:** The planner should implement: INSERT OR IGNORE "1.0.0" on every startup. Add a second migration block that checks if the perimeter types are now in schema constants and updates to "2.0.0" — but this is logic complexity. **Recommended:** Insert "1.0.0" as the safe default, then immediately override to "2.0.0" using REPLACE (INSERT OR REPLACE). For brand-new databases this sets "2.0.0"; for existing databases that already have the key at any value it leaves it alone with INSERT OR IGNORE. **Final recommendation:** Use INSERT OR IGNORE "1.0.0" (safe default for any pre-existing install), then immediately call `get_graph_schema_version()` and if it equals "1.0.0" AND no graph data existed before phase 26, bump to "2.0.0". Since we cannot reliably detect this at runtime, the safest correct interpretation is: INSERT OR IGNORE "1.0.0" always, and ship a separate startup-time upgrade that sets "2.0.0" only when the current version is "1.0.0" AND all new constants are registered. For simplicity, the planner may implement: fresh DB gets "2.0.0" (no entities row yet), pre-existing gets "1.0.0" (entities present).

### Pattern 2: Existing Migration Pattern (ALTER TABLE ADD COLUMN)
**What:** All backward-compatible column additions use a bare `try: ALTER TABLE ADD COLUMN / except: pass` block inside `__init__`.
**When to use:** Adding optional columns to existing tables that may or may not have been created with them.
**Example (from existing code, lines 306-323):**
```python
# Backward-compatible migration: add risk_score to detections if absent
try:
    self._conn.execute(
        "ALTER TABLE detections ADD COLUMN risk_score INTEGER DEFAULT 0"
    )
    self._conn.commit()
except Exception:
    pass  # column already exists — idempotent
```
Note: Phase 26 does NOT require any ALTER TABLE for the perimeter types because entities and edges store their type as a TEXT field — the schema is already type-agnostic.

### Pattern 3: GET /api/graph/schema-version Endpoint
**What:** Minimal read-only endpoint reading `system_kv`.
**Example:**
```python
@router.get("/schema-version")
async def get_schema_version(request: Request) -> JSONResponse:
    stores = request.app.state.stores
    def _read():
        row = stores.sqlite._conn.execute(
            "SELECT value FROM system_kv WHERE key = 'graph_schema_version'"
        ).fetchone()
        return row[0] if row else "1.0.0"
    version = await asyncio.to_thread(_read)
    return JSONResponse(content={"graph_schema_version": version})
```
**Route ordering:** This endpoint must be registered BEFORE `GET /{investigation_id}` in `graph.py` to avoid the wildcard route consuming `/schema-version`. Current `graph.py` already has fixed-path routes (`/global`, `/entities`, `/traverse/{entity_id}`, `/case/{case_id}`) declared before the catch-all `/{investigation_id}` — the new `/schema-version` must follow the same placement rule.

### Pattern 4: IPFire Graph Emission
**What:** After parsing an IPFire syslog line, emit graph entities (firewall_zone source, ip destination) and an edge (blocks/permits/traverses).
**How the IPFire parser currently works:** `parse_line()` returns a `NormalizedEvent` with `src_ip`, `dst_ip`, `event_outcome` ("success"/"failure"), `detection_source` (prefix like FORWARDFW/DROP_*), and `tags` containing zone labels. The `_ZONE_MAP` dict maps interface names to zone names.
**Entity creation approach:** The graph emission should NOT happen inside the parser itself (parsers return NormalizedEvents only). The correct place is either:
- In `ingestion/loader.py` after IPFire events are normalized, OR
- As a new method `emit_graph_entities(event, sqlite_store)` called from the ingest pipeline.

The entity_extractor (`ingestion/entity_extractor.py`) is already the canonical place for event→graph entity extraction. Check whether it handles `source_type == "ipfire_syslog"`.

**Zone color mapping:** The `_ZONE_MAP` in the parser maps `green0→green`, `red0→red`, `blue0→blue`, `orange0→orange`. The P26-T02 zone_color enum is `RED/GREEN/ORANGE/BLUE` (uppercase). The attributes dict for a `firewall_zone` node should store `zone_color` as uppercase.

**Edge type selection:**
- `event_outcome == "success"` and prefix in `{FORWARDFW, INPUTFW}` → `permits` or `traverses`
- `event_outcome == "failure"` (DROP_*, REJECT_*) → `blocks`
- Traversal (forwarded between two interfaces) → `traverses`

### Pattern 5: Dashboard Cytoscape.js Node Styling
**What:** Add new entries to the `typeColors` record and optionally add Cytoscape selectors for new edge types.
**Current typeColors (GraphView.svelte lines 43-55):**
```typescript
const typeColors: Record<string, string> = {
  host: '#58a6ff',
  user: '#3fb950',
  process: '#d29922',
  file: '#8b949e',
  ip: '#ffa657',
  domain: '#bc8cff',
  network_connection: '#f85149',
  detection: '#f85149',
  artifact: '#6e7681',
  incident: '#e3b341',
  attack_technique: '#ff6b6b',
}
```
**New entries needed:**
```typescript
firewall_zone: '#e05252',     // RED zone default (or use zone_color attribute)
network_segment: '#1a7f64',   // subnet green
```
For zone-color coding, a single static color for `firewall_zone` is sufficient if the specific zone color is rendered via a CSS class or node label. Cytoscape can use a function selector `(ele) => zoneColorMap[ele.data('attributes')?.zone_color] ?? '#e05252'` for richer coding.

**New edge type styles:** Add Cytoscape selectors for `blocks`, `permits`, `traverses` in `buildCytoStyle()`.

### Anti-Patterns to Avoid
- **Adding a dedicated `graph_metadata` table:** `system_kv` already exists for this purpose.
- **Modifying existing ENTITY_TYPES or EDGE_TYPES entries:** Phase 26 is strictly additive. Only append new items.
- **Emitting graph entities inside the parser `parse_line()` method:** Parsers must remain side-effect-free and only return `NormalizedEvent` objects. Graph emission belongs in the ingest pipeline.
- **Using UPDATE instead of INSERT OR IGNORE for version seeding:** The fresh-install vs. pre-existing distinction depends on INSERT OR IGNORE to leave existing values untouched.
- **Placing `/schema-version` route after `/{investigation_id}`:** The wildcard route would intercept it. Placement must be before the catch-all.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Schema version storage | Custom `graph_schema_version` table | `system_kv` table (already in DDL) | Table already exists; same pattern as other KV metadata |
| Graph versioning migration | Alembic, Flask-Migrate | Inline try/except ALTER TABLE in __init__ | Established project pattern; no migration framework dependency |
| Graph rendering | Custom canvas/SVG renderer | Cytoscape.js (already installed) | Already used in both graph components; supports custom selectors |
| Node color by attribute | Manual DOM manipulation | Cytoscape selector function `(ele) => ...` | Cytoscape supports function-based style properties |

**Key insight:** The graph schema is intentionally type-agnostic — entities and edges store their type as free-text. "Schema" in phase 26 means constants, not DDL constraints. The only DDL change is the `system_kv` INSERT for version tracking.

---

## Common Pitfalls

### Pitfall 1: Route Order — /schema-version vs /{investigation_id}
**What goes wrong:** FastAPI matches routes in declaration order. If `GET /{investigation_id}` is declared before `GET /schema-version`, requests to `/api/graph/schema-version` will be routed to `get_investigation_graph()` with `investigation_id="schema-version"`, returning an empty graph response instead of the version JSON.
**Why it happens:** The existing `/{investigation_id}` wildcard catches all single-path-segment routes.
**How to avoid:** Declare `@router.get("/schema-version")` before the `@router.get("/{investigation_id}")` decorator in `graph.py`. The current file ends with the catch-all at line 382 — insert the new endpoint before that line.
**Warning signs:** A test for `GET /api/graph/schema-version` that receives `{"case_id": "schema-version", "entities": [], ...}` instead of `{"graph_schema_version": "..."}`.

### Pitfall 2: INSERT OR IGNORE Version Seeding — Fresh vs. Pre-existing Install
**What goes wrong:** Using `INSERT OR REPLACE` (or `INSERT OR IGNORE "2.0.0"`) on every startup would overwrite a pre-existing install's "1.0.0" version with "2.0.0".
**Why it happens:** `INSERT OR REPLACE` deletes and re-inserts; `INSERT OR IGNORE "2.0.0"` sets "2.0.0" for fresh installs but leaves pre-existing alone only if the key already exists.
**How to avoid:** Use `INSERT OR IGNORE "1.0.0"` as the unconditional default (leaves any existing value untouched). Then detect fresh install (entities table is empty) and update to "2.0.0". Alternatively, accept that any install running phase 26 for the first time will start at "1.0.0" and bump to "2.0.0" as a second migration step.
**Warning signs:** Migration test that creates a pre-existing DB, runs migration, and asserts version == "1.0.0" fails because it was overwritten with "2.0.0".

### Pitfall 3: Perimeter Edge Emission — Side Effects in Parser
**What goes wrong:** Adding `sqlite_store.insert_edge(...)` calls inside `IPFireSyslogParser.parse_line()` breaks the parser's pure-function contract, makes it impossible to test in isolation, and creates a circular dependency (parser → stores).
**Why it happens:** It seems convenient to emit graph edges at parse time.
**How to avoid:** Keep the parser side-effect-free. Add a separate `extract_ipfire_graph_entities(event: NormalizedEvent, sqlite: SQLiteStore) -> None` function in `ingestion/entity_extractor.py` or a new `graph/perimeter_extractor.py`, called from the ingest pipeline after normalization.
**Warning signs:** `IPFireSyslogParser.__init__` accepting a `SQLiteStore` argument.

### Pitfall 4: Zone Color Attribute vs. Node Type
**What goes wrong:** The dashboard's `typeColors` dict is keyed on `entity.type` (e.g., "firewall_zone"). If zone-color coding requires rendering RED zones red and GREEN zones green, a single static color for all `firewall_zone` nodes is insufficient.
**Why it happens:** The type-based color map doesn't have access to node attributes.
**How to avoid:** Use a Cytoscape style function: `'background-color': (ele) => ZONE_COLOR_MAP[ele.data('attributes')?.zone_color?.toUpperCase()] ?? '#e05252'`. Add a `ZONE_COLOR_MAP` constant in the Svelte component.
**Warning signs:** All firewall_zone nodes render the same color regardless of zone attribute.

### Pitfall 5: Malcolm/OpenSearch Compatibility — No Field Removal
**What goes wrong:** Adding a new parser or changing NormalizedEvent field mappings in a way that renames or removes existing fields breaks downstream Malcolm/OpenSearch indexing.
**Why it happens:** Malcolm consumes the same field names from NormalizedEvent's `raw_event` or ECS-mapped fields.
**How to avoid:** Phase 26 only APPENDS to `ENTITY_TYPES`, `EDGE_TYPES`, and adds new node attributes stored in the `attributes` JSON blob. No NormalizedEvent fields are removed or renamed. The existing IPFire parser fields (`src_ip`, `dst_ip`, `event_type`, etc.) remain unchanged. The test for this (P26-T04) should assert that all pre-existing `NormalizedEvent` field names are still present after the IPFire parser change.
**Warning signs:** `test_ipfire_syslog_parser.py` assertions on field names start failing.

---

## Code Examples

### Seeding graph_schema_version (two-step migration)
```python
# In SQLiteStore.__init__, after existing ALTER TABLE migrations:

# Step 1: default for pre-existing installs (INSERT OR IGNORE — leaves existing untouched)
try:
    self._conn.execute(
        "INSERT OR IGNORE INTO system_kv (key, value, updated_at) VALUES (?, ?, ?)",
        ("graph_schema_version", "1.0.0", _now_iso()),
    )
    self._conn.commit()
except Exception:
    pass

# Step 2: fresh installs have no entities yet — upgrade to 2.0.0
try:
    entity_count = self._conn.execute("SELECT COUNT(*) FROM entities").fetchone()[0]
    if entity_count == 0:
        self._conn.execute(
            "UPDATE system_kv SET value = ?, updated_at = ? WHERE key = ? AND value = ?",
            ("2.0.0", _now_iso(), "graph_schema_version", "1.0.0"),
        )
        self._conn.commit()
except Exception:
    pass
```

### get_graph_schema_version() helper
```python
def get_graph_schema_version(self) -> str:
    row = self._conn.execute(
        "SELECT value FROM system_kv WHERE key = 'graph_schema_version'"
    ).fetchone()
    return row[0] if row else "1.0.0"
```

### graph/schema.py additions
```python
# Appended to ENTITY_TYPES list:
"firewall_zone",      # IPFire/netfilter zone (zone_name, zone_color, interface)
"network_segment",    # IP subnet/CIDR block (cidr, zone, description)

# Appended to EDGE_TYPES list:
"blocks",     # firewall_zone → ip/network_segment: zone blocks this traffic
"permits",    # firewall_zone → ip/network_segment: zone permits this traffic
"traverses",  # ip → firewall_zone → ip: traffic crossed this zone boundary
```

### Dashboard typeColors addition (GraphView.svelte)
```typescript
const typeColors: Record<string, string> = {
  // ... existing entries unchanged ...
  firewall_zone: '#e05252',      // zone node — base red; overridden per zone_color
  network_segment: '#1a7f64',    // subnet node — green
}

// Zone-color map for firewall_zone nodes
const ZONE_COLORS: Record<string, string> = {
  RED: '#e05252',
  GREEN: '#3fb950',
  ORANGE: '#d29922',
  BLUE: '#58a6ff',
}
```

### Cytoscape selector for firewall_zone node rendering
```typescript
// In buildCytoStyle(), override background-color for firewall_zone nodes
{
  selector: 'node[type = "firewall_zone"]',
  style: {
    'background-color': (ele: any) =>
      ZONE_COLORS[(ele.data('attributes')?.zone_color ?? '').toUpperCase()] ?? '#e05252',
    'shape': 'diamond',
  }
},
{
  selector: 'node[type = "network_segment"]',
  style: {
    'background-color': '#1a7f64',
    'shape': 'roundrectangle',
  }
},
{
  selector: 'edge[edge_type = "blocks"]',
  style: { 'line-color': '#f85149', 'target-arrow-color': '#f85149', 'line-style': 'dashed' }
},
{
  selector: 'edge[edge_type = "permits"]',
  style: { 'line-color': '#3fb950', 'target-arrow-color': '#3fb950' }
},
{
  selector: 'edge[edge_type = "traverses"]',
  style: { 'line-color': '#ffa657', 'target-arrow-color': '#ffa657', 'line-style': 'dotted' }
},
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| No schema version tracking | `system_kv` key `graph_schema_version` | Phase 26 | Enables future migration guards |
| 11 entity types (host..attack_technique) | 13 types (+ firewall_zone, network_segment) | Phase 26 | Perimeter visibility in graph |
| 12 edge types (executed_by..related_to) | 15 types (+ blocks, permits, traverses) | Phase 26 | Firewall relationship edges |
| IPFire events create NormalizedEvent only | IPFire events also emit graph entities/edges | Phase 26 | Perimeter topology visible in investigation graph |

**Not deprecated:** All existing entity types, edge types, and SQLite table schemas remain valid. Zero removals.

---

## Open Questions

1. **Where exactly should IPFire graph emission logic live?**
   - What we know: `ingestion/entity_extractor.py` is the canonical extractor; `ingestion/loader.py` calls it after normalization.
   - What's unclear: Does `entity_extractor.py` already have a dispatch path for `source_type == "ipfire_syslog"`? A quick read of that file would confirm.
   - Recommendation: Read `ingestion/entity_extractor.py` during planning; if it has a `source_type` dispatch pattern, add `ipfire_syslog` there. Otherwise, add a dedicated `extract_perimeter_entities(event, sqlite)` function called from `loader.py`.

2. **Fresh vs. pre-existing install version detection**
   - What we know: The two-step migration (INSERT OR IGNORE "1.0.0", then UPDATE to "2.0.0" if entity count == 0) works correctly.
   - What's unclear: Is counting entities the right proxy? A fresh install run immediately after loading test fixtures would count > 0 and stay at "1.0.0".
   - Recommendation: Accept that any install with existing data starts at "1.0.0". The version string affects monitoring only — no behavior gating on it in phase 26.

3. **Malcolm/OpenSearch compatibility scope**
   - What we know: The requirement says "Malcolm/OpenSearch schema compatibility maintained." Malcolm is a network analysis framework that ingests Zeek/Suricata/iptables logs.
   - What's unclear: Whether the project has an active Malcolm integration or this is a forward-compatibility statement.
   - Recommendation: Interpret as "don't remove or rename any existing NormalizedEvent fields or ENTITY_TYPES/EDGE_TYPES entries." The P26-T04 test should assert all pre-phase-26 constants remain present.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest with pytest-asyncio (auto mode) |
| Config file | `pyproject.toml` |
| Quick run command | `uv run pytest tests/unit/test_graph_schema.py tests/unit/test_graph_schema_version.py tests/unit/test_perimeter_edges.py tests/unit/test_additive_migration.py -x` |
| Full suite command | `uv run pytest` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| P26-T01 | `system_kv` seeded with version on init; pre-existing install gets "1.0.0"; fresh install gets "2.0.0"; GET /api/graph/schema-version returns JSON with `graph_schema_version` | unit | `uv run pytest tests/unit/test_graph_schema_version.py -x` | Wave 0 |
| P26-T02 | `ENTITY_TYPES` contains `firewall_zone` and `network_segment`; `EDGE_TYPES` unchanged minus new additions; `is_valid_entity_type("firewall_zone")` returns True; existing types still present | unit | `uv run pytest tests/unit/test_graph_schema.py -x` | Wave 0 |
| P26-T03 | IPFire `blocks`/`permits`/`traverses` edges created correctly from DROP_*, FORWARDFW events; `firewall_zone` entity upserted with correct attributes; `is_valid_edge_type("blocks")` etc. return True | unit | `uv run pytest tests/unit/test_perimeter_edges.py -x` | Wave 0 |
| P26-T04 | All pre-existing ENTITY_TYPES still present after phase 26 additions; all pre-existing EDGE_TYPES still present; no SQLite columns or tables removed; IPFire NormalizedEvent field names unchanged | unit | `uv run pytest tests/unit/test_additive_migration.py -x` | Wave 0 |
| P26-T05 | Dashboard renders firewall_zone nodes with zone-color coding; network_segment as subnet bubbles; new edge types with distinct styles; no visual regression on existing types | human-verify | N/A — `autonomous: false`, human visual checkpoint | N/A |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/unit/test_graph_schema.py tests/unit/test_graph_schema_version.py tests/unit/test_perimeter_edges.py tests/unit/test_additive_migration.py -x`
- **Per wave merge:** `uv run pytest`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/unit/test_graph_schema.py` — covers P26-T02: constant additions and validation helpers
- [ ] `tests/unit/test_graph_schema_version.py` — covers P26-T01: version seeding, endpoint
- [ ] `tests/unit/test_perimeter_edges.py` — covers P26-T03: IPFire graph emission
- [ ] `tests/unit/test_additive_migration.py` — covers P26-T04: additive-only assertion

### P26-T05 Human Verification Checkpoint
P26-T05 requires **human visual verification** of the dashboard graph rendering. The planner MUST generate this as a plan with `autonomous: false` and checkpoint type `human-verify`. Acceptance criteria: analyst opens GraphView, creates/ingests a sample IPFire syslog line with FORWARDFW and DROP_* events, observes firewall_zone nodes rendered as diamonds with zone-appropriate colors, network_segment nodes as rounded rectangles, and blocks/permits/traverses edges with distinct styles. No existing node/edge types should change appearance.

---

## Sources

### Primary (HIGH confidence)
- Direct code reading of `graph/schema.py` — confirmed ENTITY_TYPES (11 items) and EDGE_TYPES (12 items) lists
- Direct code reading of `backend/stores/sqlite_store.py` (lines 30-323) — confirmed `system_kv` table DDL, existing migration pattern (try/except ALTER TABLE)
- Direct code reading of `backend/api/graph.py` — confirmed all existing endpoints, route ordering, and absence of `/schema-version`
- Direct code reading of `ingestion/parsers/ipfire_syslog_parser.py` — confirmed parser structure, `_ZONE_MAP`, `event_outcome` mapping, no graph emission
- Direct code reading of `dashboard/src/views/GraphView.svelte` (lines 1-120) — confirmed Cytoscape.js usage, `typeColors` dict, `buildCytoStyle()` structure, Svelte 5 rune pattern
- Direct code reading of `tests/unit/test_graph_api.py` — confirmed test harness pattern using `_build_app(tmp_path)` with real SQLiteStore
- Direct code reading of `tests/unit/test_sqlite_store.py` — confirmed migration test pattern

### Secondary (MEDIUM confidence)
- Dashboard `ThreatGraph.svelte` — secondary Cytoscape component; uses `NODE_COLORS` dict (subset of types); confirms Cytoscape API usage patterns

### Tertiary (LOW confidence)
- None — all findings are from direct code reading

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all confirmed by direct file reads; no external dependencies required
- Architecture: HIGH — migration pattern directly observed; route ordering pitfall confirmed by reading graph.py structure
- Pitfalls: HIGH — route ordering and INSERT OR IGNORE behavior are deterministic Python/SQLite semantics
- Dashboard extension: HIGH — Cytoscape.js selector pattern confirmed from existing component code

**Research date:** 2026-04-06
**Valid until:** 2026-05-06 (stable stack; SQLite/Cytoscape APIs are not fast-moving)
