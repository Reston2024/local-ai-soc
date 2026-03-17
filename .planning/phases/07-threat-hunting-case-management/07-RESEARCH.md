# Phase 7: Threat Hunting & Case Management Layer — Research

**Researched:** 2026-03-17
**Domain:** Case management, threat hunting, SQLite persistence, DuckDB query engine, Svelte 5 frontend panels
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Backend Module Structure (LOCKED)**
- New package: `backend/investigation/`
- Required files (exact names locked by PRD):
  - `case_manager.py` — CRUD for investigation cases
  - `timeline_builder.py` — timeline reconstruction from events + alerts
  - `hunt_engine.py` — threat hunting query execution
  - `artifact_store.py` — forensic artifact capture and retrieval
  - `tagging.py` — tag management across cases and entities

**Case Data Model (LOCKED)**
Case records must support exactly these fields:
- `case_id` — unique identifier
- `case_status` — investigation state (open / in-progress / closed)
- `related_alerts` — list of alert IDs linked to this case
- `related_entities` — list of entity IDs (host, IP, user, process, domain)
- `timeline_events` — ordered list of timeline entries
- `analyst_notes` — free-text analyst observations
- `tags` — analyst-applied labels
- `artifacts` — collected forensic items

**Timeline Reconstruction (LOCKED)**
Each timeline event must include:
- `timestamp` — event time (ISO 8601)
- `event_source` — telemetry source identifier
- `entity_references` — list of entity IDs involved
- `related_alerts` — alerts associated with this timeline event
- `confidence_score` — float 0.0–1.0 for automated entries

**Threat Hunting Queries (LOCKED)**
Hunt engine must support at minimum:
- Find hosts communicating with a suspicious IP
- Identify processes spawned by PowerShell
- Detect unusual authentication patterns
- Search for indicators of compromise across telemetry sources

**Storage (LOCKED)**
- Case data: SQLite (project already has SQLiteStore)
- Artifacts: file-system under `data/artifacts/` with metadata in SQLite
- All DuckDB reads via `store.fetch_all()` (asyncio.to_thread wrapper per CLAUDE.md)
- All DuckDB writes via `store.execute_write()` (write queue pattern per CLAUDE.md)

**API Endpoints (LOCKED)**
New endpoints required (prefix `/api`):
- `POST /api/cases` — create case
- `GET /api/cases` — list cases
- `GET /api/cases/{case_id}` — get case detail
- `PATCH /api/cases/{case_id}` — update case (status, notes, tags)
- `POST /api/cases/{case_id}/artifacts` — attach artifact
- `GET /api/cases/{case_id}/timeline` — get reconstructed timeline
- `POST /api/hunt` — execute threat hunting query
- `GET /api/hunt/templates` — list available hunt templates

**Dashboard Panels (LOCKED)**
- Investigation panel: case list, case detail, timeline view
- Hunt panel: query input, results, pivot-to-case action
- Must use Svelte 5 runes (`$state()`, `$derived()`, `$effect()`) — NO stores
- Must call API via `src/lib/api.ts` typed client only

**AI-Assisted Summaries (LOCKED)**
- Read-only mode: summaries generated via existing Ollama client
- No analyst edits to AI output — display only
- Triggered per-case via existing `POST /api/investigate/{alert_id}/summary` pattern

### Claude's Discretion
- Specific SQLite schema DDL (column types, indexes)
- Pagination strategy for large case lists
- Artifact file naming convention under `data/artifacts/`
- Hunt query syntax (SQL vs structured params)
- Component layout within dashboard panels
- Error handling granularity for artifact upload failures

### Deferred Ideas (OUT OF SCOPE)
- Multi-analyst collaboration / case assignment
- External SIEM export (Splunk, QRadar format)
- Automated case creation from detection triggers
- Case severity scoring ML model
</user_constraints>

---

## Summary

Phase 7 builds the investigation workflow layer on top of the Phase 6 causality engine. The core challenge is persisting structured case data (SQLite), executing ad-hoc threat hunting queries (DuckDB), reconstructing event timelines (aggregating from DuckDB normalized_events + causality output), and storing forensic artifacts (filesystem + SQLite metadata). The phase is self-contained in `backend/investigation/` and follows every established project convention exactly.

The SQLite store already has `cases` and `detections` tables with the right schema primitives. Phase 7 extends this with new tables for investigation cases (separate from the graph-oriented `cases` table), timeline entries, artifacts, and tags. The key architectural decision is whether to add tables to the existing `graph.db` SQLite database or create a new `investigation.db`. Because the schema is additive and the store class is synchronous (called via `asyncio.to_thread`), adding new tables to `graph.db` via migration is the simplest path — no new file, no new startup wiring.

The hunt engine is pure DuckDB SQL. The four required query templates map directly to `normalized_events` columns that already exist (hostname, dst_ip, parent_process_name, event_type, username). The timeline builder is an aggregation query that joins DuckDB events with in-memory alert data (from `_alerts` in the existing routes) and calls `find_causal_chain` from Phase 6 to score confidence.

**Primary recommendation:** Add three new tables to SQLiteStore (`investigation_cases`, `case_artifacts`, `case_tags`), put all new logic in `backend/investigation/`, mount a new `investigation_router` in `main.py` following the exact same deferred-import + `asyncio.to_thread` pattern as `causality_routes.py`.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python sqlite3 | stdlib | Case/artifact metadata persistence | Already used in SQLiteStore; no new dep |
| DuckDB | pinned in pyproject.toml | Hunt query execution against normalized_events | Established single-writer pattern |
| FastAPI | pinned | New investigation router | Same router pattern as causality_routes.py |
| Pydantic v2 | pinned | Case/artifact/timeline Pydantic models | All existing models use Pydantic v2 |
| pathlib.Path | stdlib | Artifact file storage under data/artifacts/ | Zero deps, cross-platform |
| uuid4 | stdlib | case_id / artifact_id generation | Matches existing pattern (sqlite_store.py L131) |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| asyncio.to_thread | stdlib | Wrap all SQLite and DuckDB blocking calls | Every route handler that touches a store |
| httpx (AsyncClient) | pinned | Ollama LLM calls for AI summaries | Same pattern as causality_routes.py L256 |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Extending SQLiteStore | New SQLAlchemy ORM | ORM adds 0 value here; raw sqlite3 is already established pattern |
| Filesystem artifacts | Storing in DuckDB BLOB | Filesystem is faster for large files; SQLite metadata keeps it queryable |
| New investigation.db file | Add tables to graph.db | Both work; same file is simpler (no new lifespan wiring needed) |

**Installation:** No new packages required. All dependencies already in the project.

---

## Architecture Patterns

### Recommended Project Structure
```
backend/investigation/
├── __init__.py          # Empty package marker
├── case_manager.py      # Case CRUD (SQLite via asyncio.to_thread)
├── timeline_builder.py  # Timeline reconstruction from DuckDB + causality
├── hunt_engine.py       # DuckDB SQL hunt query templates
├── artifact_store.py    # File save/read + SQLite metadata
├── tagging.py           # Tag CRUD for cases and entities
└── investigation_routes.py  # FastAPI APIRouter (mounted in main.py)
```

### Pattern 1: New Tables via SQLiteStore Migration
**What:** Add `investigation_cases`, `case_artifacts`, `case_tags` tables to the existing `graph.db` via `executescript` extension of `_DDL` in `sqlite_store.py`.
**When to use:** When extending persistent case data storage.

The existing `cases` table in `graph.db` is used by the graph system for case-scoping entities and detections. Phase 7 needs a richer investigation case model (status workflow, notes, related_alerts JSON array, timeline_events JSON array, tags). The cleanest approach is a separate `investigation_cases` table that references the same case_id namespace.

**Recommended DDL (Claude's discretion):**
```sql
CREATE TABLE IF NOT EXISTS investigation_cases (
    case_id         TEXT PRIMARY KEY,
    title           TEXT NOT NULL,
    description     TEXT DEFAULT '',
    case_status     TEXT NOT NULL DEFAULT 'open',
    related_alerts  TEXT DEFAULT '[]',   -- JSON array of alert IDs
    related_entities TEXT DEFAULT '[]',  -- JSON array of entity IDs
    timeline_events TEXT DEFAULT '[]',   -- JSON array of timeline entries
    analyst_notes   TEXT DEFAULT '',
    tags            TEXT DEFAULT '[]',   -- JSON array of tag strings
    artifacts       TEXT DEFAULT '[]',   -- JSON array of artifact IDs
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS case_artifacts (
    artifact_id     TEXT PRIMARY KEY,
    case_id         TEXT NOT NULL,
    filename        TEXT NOT NULL,
    file_path       TEXT NOT NULL,       -- absolute path under data/artifacts/{case_id}/
    file_size       INTEGER,
    mime_type       TEXT,
    description     TEXT DEFAULT '',
    created_at      TEXT NOT NULL,
    FOREIGN KEY (case_id) REFERENCES investigation_cases (case_id)
);

CREATE TABLE IF NOT EXISTS case_tags (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id         TEXT NOT NULL,
    tag             TEXT NOT NULL,
    created_at      TEXT NOT NULL,
    UNIQUE(case_id, tag),
    FOREIGN KEY (case_id) REFERENCES investigation_cases (case_id)
);

CREATE INDEX IF NOT EXISTS idx_inv_cases_status ON investigation_cases (case_status);
CREATE INDEX IF NOT EXISTS idx_artifacts_case   ON case_artifacts (case_id);
CREATE INDEX IF NOT EXISTS idx_tags_case        ON case_tags (case_id);
```

**IMPORTANT:** The existing `SQLiteStore.__init__` runs `_DDL` via `executescript` at startup. The new tables should be added to `_DDL` so they are created on first run and on subsequent runs (all `CREATE TABLE IF NOT EXISTS`). No migration runner needed.

### Pattern 2: Investigation Router (Deferred Import Pattern)
**What:** New `APIRouter` in `backend/investigation/investigation_routes.py`, mounted in `main.py` using the same deferred import + `try/except ImportError` guard as `causality_routes.py`.
**When to use:** All 8 new endpoints.

```python
# In backend/investigation/investigation_routes.py
from fastapi import APIRouter, HTTPException, Request
import asyncio

investigation_router = APIRouter(prefix="/api", tags=["investigation"])

@investigation_router.post("/cases")
async def create_case(request: Request, body: dict):
    sqlite = request.app.state.stores.sqlite
    # call case_manager functions via asyncio.to_thread
    result = await asyncio.to_thread(create_investigation_case, sqlite, body)
    return result
```

```python
# In backend/main.py — add alongside causality_router mount
try:
    from backend.investigation.investigation_routes import investigation_router
    app.include_router(investigation_router)
except ImportError:
    log.warning("Investigation module not available — skipping router mount")
```

### Pattern 3: Hunt Engine (DuckDB SQL Templates)
**What:** `hunt_engine.py` defines named query templates as Python dataclasses. Each template has a `name`, `description`, `sql`, and `param_schema`. Execution calls `duckdb_store.fetch_df(sql, params)`.
**When to use:** `POST /api/hunt` and `GET /api/hunt/templates`.

```python
# Source: DuckDB store pattern from backend/stores/duckdb_store.py
from dataclasses import dataclass

@dataclass
class HuntTemplate:
    name: str
    description: str
    sql: str
    param_keys: list[str]   # expected keys in params dict

HUNT_TEMPLATES: dict[str, HuntTemplate] = {
    "suspicious_ip_comms": HuntTemplate(
        name="suspicious_ip_comms",
        description="Find hosts communicating with a suspicious IP",
        sql="""
            SELECT DISTINCT hostname, src_ip, dst_ip, timestamp, event_type
            FROM normalized_events
            WHERE dst_ip = ?
            ORDER BY timestamp DESC
            LIMIT 200
        """,
        param_keys=["dst_ip"],
    ),
    "powershell_children": HuntTemplate(
        name="powershell_children",
        description="Identify processes spawned by PowerShell",
        sql="""
            SELECT hostname, process_name, process_id, parent_process_name,
                   command_line, timestamp
            FROM normalized_events
            WHERE parent_process_name ILIKE '%powershell%'
            ORDER BY timestamp DESC
            LIMIT 200
        """,
        param_keys=[],
    ),
    "unusual_auth": HuntTemplate(
        name="unusual_auth",
        description="Detect unusual authentication patterns (high frequency per host/user)",
        sql="""
            SELECT hostname, username, COUNT(*) AS cnt,
                   MIN(timestamp) AS first_seen, MAX(timestamp) AS last_seen
            FROM normalized_events
            WHERE event_type = 'authentication'
            GROUP BY hostname, username
            HAVING cnt > ?
            ORDER BY cnt DESC
            LIMIT 100
        """,
        param_keys=["threshold"],
    ),
    "ioc_search": HuntTemplate(
        name="ioc_search",
        description="Search for a specific IOC value across all telemetry fields",
        sql="""
            SELECT event_id, timestamp, hostname, username, process_name,
                   src_ip, dst_ip, domain, file_hash_sha256, event_type, severity
            FROM normalized_events
            WHERE hostname ILIKE ?
               OR username ILIKE ?
               OR dst_ip = ?
               OR src_ip = ?
               OR domain ILIKE ?
               OR file_hash_sha256 = ?
            ORDER BY timestamp DESC
            LIMIT 500
        """,
        param_keys=["ioc_value"],  # single value, repeated 6 times as params
    ),
}
```

**Execution pattern:**
```python
# Source: duckdb_store.fetch_df — asyncio.to_thread wrapper
async def execute_hunt(duckdb_store, template_name: str, params: dict) -> list[dict]:
    tmpl = HUNT_TEMPLATES.get(template_name)
    if not tmpl:
        raise ValueError(f"Unknown hunt template: {template_name!r}")
    # Build positional param list
    if template_name == "ioc_search":
        ioc = params.get("ioc_value", "")
        param_list = [f"%{ioc}%", f"%{ioc}%", ioc, ioc, f"%{ioc}%", ioc]
    elif template_name == "unusual_auth":
        param_list = [int(params.get("threshold", 10))]
    elif template_name == "suspicious_ip_comms":
        param_list = [params.get("dst_ip", "")]
    else:
        param_list = None
    return await duckdb_store.fetch_df(tmpl.sql, param_list)
```

### Pattern 4: Timeline Builder
**What:** `timeline_builder.py` fetches events from DuckDB ordered by timestamp for a case's related_alerts/entities, then optionally runs `find_causal_chain` for confidence scoring.
**When to use:** `GET /api/cases/{case_id}/timeline`.

The timeline reconstruction joins the Phase 6 causality engine output with raw event data. The key insight: `build_causality_sync` already returns a `chain` (ordered events) with `techniques` and temporal bounds. For a case that has multiple alerts, the timeline is the union of all causal chains, deduplicated by event_id and sorted by timestamp.

```python
# Pseudocode — source logic from causality/engine.py + duckdb_store.fetch_df
async def build_timeline(case_id: str, duckdb_store, sqlite_store) -> list[dict]:
    # 1. Get case's related_alerts from SQLite
    case = await asyncio.to_thread(sqlite_store.get_investigation_case, case_id)
    alert_ids = case.get("related_alerts", [])

    # 2. Fetch all events for the case from DuckDB (ordered by timestamp)
    rows = await duckdb_store.fetch_df(
        "SELECT * FROM normalized_events WHERE case_id = ? ORDER BY timestamp ASC",
        [case_id]
    )

    # 3. Build timeline entries with confidence scoring
    timeline = []
    for row in rows:
        entry = {
            "timestamp": row["timestamp"].isoformat() if row["timestamp"] else "",
            "event_source": row.get("source_type", "unknown"),
            "entity_references": _extract_entity_refs(row),
            "related_alerts": _find_related_alerts(row["event_id"], alerts),
            "confidence_score": _score_confidence(row, alert_ids),
        }
        timeline.append(entry)
    return timeline
```

**Confidence scoring logic (suggested):**
- `1.0` if event_id appears in a Sigma detection's `matched_event_ids`
- `0.8` if event is part of a causality chain
- `0.5` for events in the case's time window but not in a chain
- `0.3` for events with matching entity but outside time window

### Pattern 5: Artifact Storage
**What:** `artifact_store.py` saves uploaded file bytes to `data/artifacts/{case_id}/{artifact_id}_{filename}`, writes metadata to SQLite `case_artifacts`.
**When to use:** `POST /api/cases/{case_id}/artifacts`.

```python
# File naming convention (Claude's discretion)
# data/artifacts/{case_id}/{artifact_id}_{safe_filename}
# e.g. data/artifacts/abc-123/def-456_memory_dump.raw

from pathlib import Path
import aiofiles  # NOT in project — use sync write in asyncio.to_thread instead

async def save_artifact(data_dir: str, case_id: str, artifact_id: str,
                        filename: str, content: bytes, sqlite_store) -> dict:
    artifact_dir = Path(data_dir) / "artifacts" / case_id
    artifact_dir.mkdir(parents=True, exist_ok=True)
    safe_name = f"{artifact_id}_{filename}"
    file_path = artifact_dir / safe_name

    def _write():
        file_path.write_bytes(content)

    await asyncio.to_thread(_write)
    # Write metadata to SQLite
    await asyncio.to_thread(
        sqlite_store.insert_artifact,
        artifact_id, case_id, filename, str(file_path), len(content)
    )
    return {"artifact_id": artifact_id, "filename": filename, "file_size": len(content)}
```

**CRITICAL:** Do NOT use `aiofiles` — it is not in the project. Use `asyncio.to_thread` with `pathlib.Path.write_bytes()` per CLAUDE.md convention.

### Anti-Patterns to Avoid
- **`writable()` stores in Svelte:** Use `$state()` runes. This project enforces Svelte 5 runes everywhere.
- **Direct DuckDB write from investigation routes:** Always go through `store.execute_write()` queue. Never call `duckdb.connect()` directly in route handlers.
- **Blocking SQLite in async handlers:** Always `await asyncio.to_thread(sqlite_store.some_method, ...)`.
- **Adding `aiofiles` dep:** Not in project. Use `asyncio.to_thread` + stdlib file I/O.
- **New SQLite file for investigation:** Add tables to existing `graph.db` via `_DDL` extension. Avoids new lifespan wiring.
- **Module-level imports of investigation modules:** Use `try/except ImportError` deferred import pattern (mirrors `causality_routes.py`). This ensures startup does not fail if the module has a stub.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Case ID generation | Custom ID scheme | `str(uuid4())` | Already the project standard (sqlite_store.py:131) |
| SQL injection protection | String formatting in SQL | DuckDB parameterized queries (`?` placeholders) | DuckDB supports parameterized queries; already used in duckdb_store.fetch_all |
| JSON array serialization in SQLite | Custom delimiter format | `json.dumps(list)` / `json.loads(str)` | Already the project pattern (sqlite_store.py:186, 399) |
| Entity normalization | Custom normalizer | `resolve_canonical_id` from `backend/causality/entity_resolver.py` | Already handles host/user/process/ip/domain/file normalization |
| Causal chain building | Custom BFS | `find_causal_chain` from `backend/causality/attack_chain_builder.py` | Phase 6 delivers this with cycle detection and depth cap |
| MITRE technique mapping | Static lookup | `map_techniques` from `backend/causality/mitre_mapper.py` | 27-entry catalog already built |
| Confidence scoring for chains | Custom formula | `score_chain` from `backend/causality/scoring.py` | Additive 0-100 model already built |
| AI investigation summaries | New LLM integration | `format_prompt` from `prompts/investigation_summary.py` + existing Ollama pattern in `causality_routes.py` | Already implemented and proven |

**Key insight:** Phase 7 is 80% wiring existing Phase 6 components together under a structured case model. The heavy lifting (BFS chain, MITRE mapping, confidence scoring, entity normalization) is already done.

---

## Common Pitfalls

### Pitfall 1: SQLite `cases` Table Conflict
**What goes wrong:** The existing `graph.db` has a `cases` table. Naming the new Phase 7 table `cases` will collide silently (CREATE TABLE IF NOT EXISTS succeeds because the table already exists, but with the wrong schema for Phase 7 purposes).
**Why it happens:** The Phase 1 SQLiteStore already created a `cases` table for graph-scoping purposes. Its schema is `(id, name, description, status, created_at)` — missing all Phase 7 fields.
**How to avoid:** Name the new table `investigation_cases`. Do NOT alter or rename the existing `cases` table — it is used by entities and detections foreign keys.
**Warning signs:** Creating a case via `POST /api/cases` succeeds but `GET /api/cases/{id}` returns only 5 fields instead of the full Phase 7 model.

### Pitfall 2: DuckDB `fetch_df` Returns Column-Keyed Dicts
**What goes wrong:** `duckdb_store.fetch_df()` returns `list[dict]` with string column keys. `duckdb_store.fetch_all()` returns `list[tuple]`. Hunt engine code that uses `fetch_all` and tries to index by column name will break.
**Why it happens:** Two different helper methods exist; `fetch_df` is the dict-returning variant.
**How to avoid:** Hunt engine should always use `duckdb_store.fetch_df()` — it returns `list[dict]` with column names as keys, ready for JSON serialization.
**Warning signs:** `TypeError: tuple indices must be integers or slices, not str` in hunt endpoint.

### Pitfall 3: Artifact File Path on Windows
**What goes wrong:** `Path("data/artifacts") / case_id / filename` on Windows will use backslashes, which may cause issues when storing the path string in SQLite and then reconstructing it on the frontend.
**Why it happens:** `pathlib.Path` on Windows uses `WindowsPath` with `\` separators.
**How to avoid:** Always store artifact paths as `str(path).replace("\\", "/")` or use `path.as_posix()` when writing to SQLite. On read, use `Path(stored_string)` which handles both separators.
**Warning signs:** Artifact download endpoint returns 404 because stored path has wrong separator.

### Pitfall 4: Case `related_alerts` Out of Sync with In-Memory `_alerts`
**What goes wrong:** The existing `_alerts` list in `backend/src/api/routes.py` is in-memory only. When a case links to alert IDs via `related_alerts` in SQLite, those IDs may not match IDs in `_alerts` after a backend restart.
**Why it happens:** `_alerts` is populated only during the current backend session from ingested events.
**How to avoid:** When building timeline or case detail responses, gracefully handle missing alerts — return the alert ID with `{"id": alert_id, "found": false}` rather than raising 404. Document this limitation: alerts are session-persistent only until Phase 8 or until DuckDB detection persistence is added.
**Warning signs:** `GET /api/cases/{id}` returns 500 when trying to hydrate a case's `related_alerts`.

### Pitfall 5: `asyncio.to_thread` Nesting
**What goes wrong:** Calling `asyncio.to_thread(some_func)` where `some_func` itself calls `asyncio.to_thread(...)` or any async coroutine will fail.
**Why it happens:** The function passed to `asyncio.to_thread` runs in a thread, not the event loop. Awaiting coroutines inside a thread is not valid.
**How to avoid:** All functions passed to `asyncio.to_thread` must be fully synchronous. Separate async orchestration (in the route handler) from sync computation (in the `investigation/` module functions).
**Warning signs:** `RuntimeError: no running event loop` or `RuntimeError: This event loop is already running`.

### Pitfall 6: PATCH Route Body Handling
**What goes wrong:** FastAPI PATCH with a `dict` body will silently ignore unknown fields if using raw `dict` instead of a Pydantic model. Partial update logic that only updates non-None fields needs explicit handling.
**Why it happens:** PATCH semantics require field-level merging, not full replacement.
**How to avoid:** Define a `CaseUpdateRequest` Pydantic model with all fields Optional. In the route handler, build an UPDATE SQL that only sets fields present in the request body.
**Warning signs:** PATCH to update only `case_status` also clears `analyst_notes` to empty string.

---

## Code Examples

Verified patterns from existing project code:

### Creating a Record in SQLite (existing pattern)
```python
# Source: backend/stores/sqlite_store.py:132
def create_case(self, name: str, description: str = "", case_id: Optional[str] = None) -> str:
    cid = case_id or str(uuid4())
    self._conn.execute(
        "INSERT OR IGNORE INTO cases (id, name, description, status, created_at) VALUES (?, ?, ?, 'active', ?)",
        (cid, name, description, _now_iso()),
    )
    self._conn.commit()
    return cid
```

### DuckDB fetch_df (hunt query pattern)
```python
# Source: backend/stores/duckdb_store.py:240
rows = await duckdb_store.fetch_df(
    "SELECT DISTINCT hostname FROM normalized_events WHERE dst_ip = ?",
    ["192.168.1.100"]
)
# rows is list[dict] with column names as keys
```

### Async route with asyncio.to_thread (existing pattern)
```python
# Source: backend/causality/causality_routes.py:33-56
@investigation_router.post("/cases")
async def create_case_endpoint(request: Request, body: dict):
    sqlite = request.app.state.stores.sqlite
    result = await asyncio.to_thread(sqlite.create_investigation_case, body)
    return result
```

### Deferred import guard (required for new router in main.py)
```python
# Source: backend/causality/causality_routes.py:12-15 (pattern)
try:
    from backend.investigation.investigation_routes import investigation_router
    app.include_router(investigation_router)
except ImportError:
    log.warning("Investigation module not available")
```

### Svelte 5 runes — component state (required pattern)
```typescript
// Source: project convention from CLAUDE.md
<script lang="ts">
  import { getCases, createCase } from '$lib/api'

  let cases = $state<CaseItem[]>([])
  let loading = $state(false)
  let selectedCaseId = $state<string | null>(null)

  const selectedCase = $derived(cases.find(c => c.case_id === selectedCaseId) ?? null)

  $effect(() => {
    loading = true
    getCases().then(data => {
      cases = data
      loading = false
    })
  })
</script>
```

### JSON array field in SQLite (existing pattern)
```python
# Source: backend/stores/sqlite_store.py:398-399 (matched_event_ids pattern)
json.dumps(related_alerts),    # on write
json.loads(d["related_alerts"])  # on read — wrap in try/except json.JSONDecodeError
```

---

## Integration Points — Detailed

### How Phase 7 connects to Phase 6

| Phase 7 Module | Calls | Phase 6 Source |
|----------------|-------|----------------|
| `timeline_builder.py` | `find_causal_chain(event_id, events, max_depth=5)` | `backend/causality/attack_chain_builder.py` |
| `timeline_builder.py` | `score_chain(chain_events, chain_alerts, techniques)` | `backend/causality/scoring.py` |
| `timeline_builder.py` | `map_techniques(sigma_tags, event_type, category)` | `backend/causality/mitre_mapper.py` |
| `case_manager.py` | `resolve_canonical_id(event, entity_type)` | `backend/causality/entity_resolver.py` |
| `investigation_routes.py` | `app.state.stores.sqlite` | `backend/stores/sqlite_store.py` |
| `hunt_engine.py` | `app.state.stores.duckdb` | `backend/stores/duckdb_store.py` |
| `investigation_routes.py` | `from backend.src.api.routes import _events, _alerts` | `backend/src/api/routes.py` (in-memory) |

### How Phase 7 connects to existing SQLiteStore

The existing `SQLiteStore` class in `backend/stores/sqlite_store.py` already handles `cases`, `entities`, `edges`, `detections`. Phase 7 adds methods to it for:
- `create_investigation_case(title, description, case_id=None) -> str`
- `get_investigation_case(case_id) -> dict | None`
- `list_investigation_cases(status=None) -> list[dict]`
- `update_investigation_case(case_id, updates: dict) -> None`
- `insert_artifact(artifact_id, case_id, filename, file_path, file_size) -> None`
- `get_artifacts_by_case(case_id) -> list[dict]`

These are added as new methods to the existing class. The `_DDL` string is extended with the new table DDL.

### How Phase 7 stores connect to `app.state`

The `app.state.stores` object is a `Stores` dataclass defined in `backend/core/deps.py`. It has `.duckdb`, `.chroma`, `.sqlite` attributes. No changes needed — investigation routes access `request.app.state.stores.sqlite` and `request.app.state.stores.duckdb` directly (same as the graph routes in `backend/api/graph.py`).

---

## API Response Shapes (recommended)

### POST /api/cases response
```json
{
  "case_id": "uuid",
  "title": "string",
  "case_status": "open",
  "created_at": "ISO8601"
}
```

### GET /api/cases response (paginated)
```json
{
  "cases": [...],
  "total": 42,
  "limit": 20,
  "offset": 0
}
```

### GET /api/cases/{case_id} response
```json
{
  "case_id": "uuid",
  "title": "string",
  "description": "string",
  "case_status": "open|in-progress|closed",
  "related_alerts": ["alert-id-1", ...],
  "related_entities": ["host:workstation01", ...],
  "timeline_events": [],
  "analyst_notes": "string",
  "tags": ["ransomware", "lateral-movement"],
  "artifacts": ["artifact-id-1"],
  "created_at": "ISO8601",
  "updated_at": "ISO8601"
}
```

### GET /api/cases/{case_id}/timeline response
```json
{
  "case_id": "uuid",
  "timeline": [
    {
      "timestamp": "ISO8601",
      "event_source": "sysmon",
      "entity_references": ["host:ws01", "process:powershell.exe"],
      "related_alerts": ["alert-id"],
      "confidence_score": 0.9
    }
  ],
  "total_events": 42
}
```

### POST /api/hunt response
```json
{
  "template": "suspicious_ip_comms",
  "params": {"dst_ip": "192.168.1.100"},
  "results": [...],
  "result_count": 12,
  "executed_at": "ISO8601"
}
```

### GET /api/hunt/templates response
```json
{
  "templates": [
    {
      "name": "suspicious_ip_comms",
      "description": "Find hosts communicating with a suspicious IP",
      "param_keys": ["dst_ip"]
    }
  ]
}
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| In-memory `_cases` list (Phase 5 FR-5.8) | SQLite persistence via investigation_cases table | Phase 7 | Cases survive backend restart |
| No structured timeline | timeline_builder.py aggregating DuckDB + causality chain | Phase 7 | Analyst can reconstruct attack timeline |
| No hunt queries | hunt_engine.py with 4 DuckDB SQL templates | Phase 7 | Hypothesis-driven hunting without SQL knowledge |
| No artifact capture | artifact_store.py (filesystem + SQLite metadata) | Phase 7 | Forensic items can be attached to cases |

**Deprecated/outdated:**
- The Phase 1 `FR-5.8` basic case management (from requirements) described a simpler name/description/archive model. Phase 7 supersedes it with a full investigation case model. The simple `cases` table in `graph.db` remains (used by entity/detection scoping) but Phase 7's `investigation_cases` is the analyst-facing case store.

---

## Open Questions

1. **In-memory `_alerts` persistence**
   - What we know: `_alerts` in `backend/src/api/routes.py` is in-memory only. After restart, alerts are gone.
   - What's unclear: When a case references `related_alerts`, those alert IDs may not resolve after restart.
   - Recommendation: Case detail endpoint should return alert IDs even when the alert cannot be hydrated. Mark unresolvable IDs with `"found": false` in the response. This is a known limitation to document in the API.

2. **Hunt query against DuckDB when events not in `normalized_events`**
   - What we know: Some events flow through the in-memory `_events` list (legacy path in `backend/src/api/routes.py`) and may not reach `normalized_events` DuckDB table.
   - What's unclear: Completeness of the `normalized_events` table depends on which ingestion paths were used.
   - Recommendation: Hunt engine queries `normalized_events` only. Document that hunt results reflect persisted events. The planner should note this as a known gap.

3. **FastAPI multipart upload for artifacts**
   - What we know: The project already uses multipart upload in `POST /ingest` (see `backend/api/ingest.py`).
   - What's unclear: Whether the existing multipart pattern uses `UploadFile` from FastAPI.
   - Recommendation: Use FastAPI's `UploadFile` + `File(...)` dependency injection (standard FastAPI pattern). Read bytes with `await file.read()` then write synchronously via `asyncio.to_thread`.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (auto mode, set in pyproject.toml) |
| Config file | `pyproject.toml` — `[tool.pytest.ini_options]` with `asyncio_mode = "auto"` |
| Quick run command | `uv run pytest backend/src/tests/test_phase7.py -x` |
| Full suite command | `uv run pytest backend/src/tests/ -v` |

### Phase Requirements → Test Map

Phase 7 follows the established wave-based TDD pattern:
- Wave 0: Write `test_phase7.py` with all tests as `xfail` stubs (imports deferred inside test methods)
- Waves 1-3: Implement modules; tests transition from xfail to xpass
- Wave 4: Frontend build verification

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| P7-T01 | `create_investigation_case` returns a case_id string | unit | `uv run pytest backend/src/tests/test_phase7.py::TestCaseManager::test_create_case_returns_id -x` | ❌ Wave 0 |
| P7-T02 | `list_investigation_cases` returns empty list on fresh db | unit | `uv run pytest backend/src/tests/test_phase7.py::TestCaseManager::test_list_cases_empty -x` | ❌ Wave 0 |
| P7-T03 | `update_investigation_case` changes status correctly | unit | `uv run pytest backend/src/tests/test_phase7.py::TestCaseManager::test_update_case_status -x` | ❌ Wave 0 |
| P7-T04 | `POST /api/cases` returns 200 with case_id | integration | `uv run pytest backend/src/tests/test_phase7.py::TestCaseAPI::test_create_case_endpoint -x` | ❌ Wave 0 |
| P7-T05 | `GET /api/cases` returns list | integration | `uv run pytest backend/src/tests/test_phase7.py::TestCaseAPI::test_list_cases_endpoint -x` | ❌ Wave 0 |
| P7-T06 | `GET /api/cases/{case_id}` returns case detail | integration | `uv run pytest backend/src/tests/test_phase7.py::TestCaseAPI::test_get_case_detail -x` | ❌ Wave 0 |
| P7-T07 | `PATCH /api/cases/{case_id}` updates status field | integration | `uv run pytest backend/src/tests/test_phase7.py::TestCaseAPI::test_patch_case_status -x` | ❌ Wave 0 |
| P7-T08 | Hunt template `suspicious_ip_comms` produces valid SQL result | unit | `uv run pytest backend/src/tests/test_phase7.py::TestHuntEngine::test_suspicious_ip_template -x` | ❌ Wave 0 |
| P7-T09 | Hunt template `powershell_children` produces valid SQL result | unit | `uv run pytest backend/src/tests/test_phase7.py::TestHuntEngine::test_powershell_children_template -x` | ❌ Wave 0 |
| P7-T10 | `GET /api/hunt/templates` returns 4 templates | integration | `uv run pytest backend/src/tests/test_phase7.py::TestHuntAPI::test_list_hunt_templates -x` | ❌ Wave 0 |
| P7-T11 | `POST /api/hunt` with valid template returns results list | integration | `uv run pytest backend/src/tests/test_phase7.py::TestHuntAPI::test_execute_hunt -x` | ❌ Wave 0 |
| P7-T12 | `build_timeline` returns list of timeline entries with required fields | unit | `uv run pytest backend/src/tests/test_phase7.py::TestTimelineBuilder::test_timeline_entry_shape -x` | ❌ Wave 0 |
| P7-T13 | `GET /api/cases/{case_id}/timeline` returns timeline payload | integration | `uv run pytest backend/src/tests/test_phase7.py::TestTimelineAPI::test_get_timeline -x` | ❌ Wave 0 |
| P7-T14 | `save_artifact` writes file and returns artifact_id | unit | `uv run pytest backend/src/tests/test_phase7.py::TestArtifactStore::test_save_artifact -x` | ❌ Wave 0 |
| P7-T15 | `POST /api/cases/{case_id}/artifacts` returns artifact metadata | integration | `uv run pytest backend/src/tests/test_phase7.py::TestArtifactAPI::test_upload_artifact -x` | ❌ Wave 0 |
| P7-T16 | `npm run build` exits 0 after Phase 7 Svelte components added | build | `cd frontend && npm run build` | ❌ Wave 4 |

### Sampling Rate
- **Per task commit:** `uv run pytest backend/src/tests/test_phase7.py -x`
- **Per wave merge:** `uv run pytest backend/src/tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `backend/src/tests/test_phase7.py` — 16 xfail stubs covering P7-T01 through P7-T16
- [ ] `backend/investigation/__init__.py` — empty package marker
- [ ] `backend/investigation/case_manager.py` — stub module (minimal class, no implementation)
- [ ] `backend/investigation/hunt_engine.py` — stub module
- [ ] `backend/investigation/timeline_builder.py` — stub module
- [ ] `backend/investigation/artifact_store.py` — stub module
- [ ] `backend/investigation/tagging.py` — stub module
- [ ] `backend/investigation/investigation_routes.py` — stub router (empty `investigation_router`)
- [ ] SQLiteStore `_DDL` extension — 3 new tables (`investigation_cases`, `case_artifacts`, `case_tags`)

---

## Sources

### Primary (HIGH confidence)
- `backend/stores/sqlite_store.py` — existing DDL, CRUD patterns, JSON array handling confirmed
- `backend/stores/duckdb_store.py` — `fetch_df`, `fetch_all`, `execute_write` API confirmed
- `backend/causality/engine.py` — `build_causality_sync` signature and return shape confirmed
- `backend/causality/entity_resolver.py` — `resolve_canonical_id` API confirmed
- `backend/causality/causality_routes.py` — deferred import + `asyncio.to_thread` pattern confirmed
- `backend/main.py` — router mounting pattern, `app.state.stores` availability confirmed
- `backend/models/event.py` — `NormalizedEvent` fields (used for hunt query column mapping) confirmed
- `.planning/phases/07-threat-hunting-case-management/07-CONTEXT.md` — all locked decisions

### Secondary (MEDIUM confidence)
- `.planning/REQUIREMENTS.md` — FR-5.8, FR-6.8 requirements for context on prior case management scope
- `.planning/STATE.md` — key decisions for causality engine patterns, Svelte 5 constraints
- `backend/src/tests/test_phase6.py` — xfail + deferred import test pattern confirmed

### Tertiary (LOW confidence)
- None — all research is grounded in existing project source files

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all dependencies confirmed in existing project; no new packages required
- Architecture patterns: HIGH — every pattern is a direct extension of Phase 6 patterns already in use
- Pitfalls: HIGH — all pitfalls identified from actual code inspection (sqlite_store.py schema, DuckDB helper method differences, Windows Path behavior)
- Hunt SQL templates: HIGH — column names verified against `duckdb_store.py` `_CREATE_EVENTS_TABLE` DDL
- Svelte 5 frontend: HIGH — rune pattern and api.ts extension approach confirmed from existing code

**Research date:** 2026-03-17
**Valid until:** 2026-04-17 (stable tech stack; no fast-moving dependencies)
