# Phase 21: Evidence Provenance - Research

**Researched:** 2026-04-01
**Domain:** Chain-of-custody records, SQLite schema extension, FastAPI provenance endpoints, Svelte 5 ProvenanceView
**Confidence:** HIGH

---

## Summary

Phase 21 adds a defensible chain-of-custody layer across all four artefact classes that the system already produces: ingested events, Sigma detections, AI Copilot responses, and playbook runs. Every provenance record contains a SHA-256 fingerprint of the raw input, the tool/template version that processed it, the operator who triggered it, and the identifiers of downstream artefacts it produced or consumed.

The implementation is purely additive. All four provenance tables are new SQLite tables bolted onto the existing `graph.db` schema via the proven `ALTER TABLE ... ADD COLUMN` / `CREATE TABLE IF NOT EXISTS` pattern. No existing tables are modified destructively. The LLM audit trail already captures `prompt_hash` and `response_hash` in `logs/llm_audit.jsonl`; P21-T03 promotes these into a queryable SQLite table (`llm_audit_provenance`) rather than replacing the log file. Ingest and detection provenance require small additions to the hot paths in `loader.py` and `matcher.py` respectively.

The Svelte dashboard uses a flat `View` type union in `App.svelte`. Adding `'provenance'` to the union and a new nav item under an existing group (recommended: "Investigate") is the correct pattern — no routing library is involved.

**Primary recommendation:** One new SQLite table per artefact class (`ingest_provenance`, `detection_provenance`, `llm_audit_provenance`, `playbook_run_provenance`). Four new GET endpoints under `/api/provenance/`. One new Svelte view `ProvenanceView.svelte`. Reuse the `asyncio.to_thread()` pattern for all SQLite I/O.

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| P21-T01 | Ingest provenance — SHA-256 of raw bytes, parser name+version, operator_id; SQLite `ingest_provenance` table; `GET /api/provenance/ingest/{event_id}` | loader.py ingest_file() is the insertion point; file is on disk when SHA-256 is computed; parser type name is already logged; operator flows from auth middleware |
| P21-T02 | Detection provenance — Sigma rule SHA-256, rule title, pySigma backend version, field_map version; `GET /api/provenance/detection/{id}` | matcher.py match_rule() creates DetectionRecord; rule YAML is already loaded via SigmaRule.from_yaml(); pySigma==1.2.0 pinned in pyproject.toml |
| P21-T03 | AI response provenance — model_id, prompt_template_name, prompt_template_sha256, response_sha256, operator_id, grounding_event_ids; `GET /api/provenance/llm/{audit_id}` | llm_audit.jsonl already records prompt_hash, response_hash, model; missing: audit_id, prompt_template_name, grounding_event_ids, operator_id — need to add these to both the log and a new SQLite table |
| P21-T04 | Playbook run provenance — playbook_file_sha256, playbook_version, trigger_event_ids, operator_id_who_approved; `GET /api/provenance/playbook/{run_id}` | playbook_runs table exists in SQLite but has no SHA-256 or operator columns; additive ALTER TABLE or new provenance table is the path |
| P21-T05 | Provenance API + ProvenanceView tab — all 4 GET endpoints, Svelte ProvenanceView, hash copy-to-clipboard, transformation timeline | App.svelte View type union is the nav extension point; existing views provide the Svelte 5 rune pattern to copy |
</phase_requirements>

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python `hashlib` | stdlib | SHA-256 of raw bytes and template strings | Zero dependencies; already imported in ollama_client.py (`_sha256_short`) |
| `sqlite3` | stdlib | Provenance table storage | Project uses SQLiteStore with persistent `self._conn`; additive DDL is the established pattern |
| FastAPI `APIRouter` | 0.115.12 | Provenance GET endpoints | Matches all existing API modules in `backend/api/` |
| Pydantic `BaseModel` | 2.12.5 | Response models for provenance records | All API responses use Pydantic models |
| `importlib.metadata` | stdlib | Runtime version introspection for pySigma | `importlib.metadata.version('pySigma')` returns `'1.2.0'` on this install |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `asyncio.to_thread()` | stdlib | Wrap synchronous SQLite calls | All SQLite I/O from async route handlers — project convention |
| `logging.getLogger("llm_audit")` | stdlib | Existing structured audit logger | Reuse for emit-side; SQLite table is the query-side |
| Svelte 5 `$state`, `$derived`, `$effect` | dashboard | Frontend reactive state | Only runes — no writable() stores |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Single `provenance` table with `artefact_type` discriminator | Four separate tables | Single table is simpler but produces wide NULL-heavy rows and complicates type-safe API responses; four narrow tables are consistent with project style (detections, playbook_runs, etc.) |
| Appending provenance columns to existing tables (detections, playbook_runs) | New separate provenance tables | Modifying existing tables risks breaking callers; provenance is a read-heavy audit concern and benefits from isolation |
| JSONL file for all provenance | SQLite tables | JSONL cannot be queried by foreign key; SQLite tables support `GET /api/provenance/ingest/{event_id}` lookups |

**Installation:** No new packages required. All dependencies are stdlib or already installed.

---

## Architecture Patterns

### Recommended Project Structure
```
backend/
  api/
    provenance.py          # new: GET /api/provenance/* endpoints
  stores/
    sqlite_store.py        # extend: new tables + accessor methods
  models/
    provenance.py          # new: Pydantic response models
dashboard/src/
  views/
    ProvenanceView.svelte  # new: P21-T05 view
  lib/
    api.ts                 # extend: provenance namespace
```

### Pattern 1: Additive SQLite DDL via CREATE TABLE IF NOT EXISTS

**What:** New provenance tables added in `__init__` of `SQLiteStore`, alongside the existing backward-compatible migration guard.

**When to use:** Any new SQLite table in this project.

**Example:**
```python
# In _DDL (append to end of the string before closing triple-quote),
# or applied in __init__ via executescript for isolation:
CREATE TABLE IF NOT EXISTS ingest_provenance (
    prov_id         TEXT PRIMARY KEY,
    event_id        TEXT NOT NULL,          -- FK to normalized_events (DuckDB)
    raw_sha256      TEXT NOT NULL,          -- SHA-256 of the raw bytes ingested
    source_file     TEXT NOT NULL,
    parser_name     TEXT NOT NULL,          -- e.g. "EVTXParser"
    parser_version  TEXT,                   -- importlib.metadata version if available
    operator_id     TEXT,                   -- from OperatorContext
    ingested_at     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_ingest_prov_event ON ingest_provenance (event_id);
```

The idempotency guard (`CREATE TABLE IF NOT EXISTS`) means re-applying _DDL on existing databases is safe. This matches the existing `risk_score` ALTER TABLE guard in `__init__`.

### Pattern 2: SHA-256 at Ingest Entry Point

**What:** Compute `hashlib.sha256(raw_bytes).hexdigest()` once at the top of `ingest_file()`, before parsing, while the original file bytes are still on disk.

**When to use:** P21-T01. The file is available via `file_path` before the parser runs.

**Example:**
```python
# In loader.py, before calling get_parser():
import hashlib, pathlib

def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()

# Inside ingest_file(), after os.path.exists() check:
raw_sha256 = await asyncio.to_thread(_sha256_file, file_path)
```

This is a pure blocking file-read — wrapping in `asyncio.to_thread()` is required per project convention.

### Pattern 3: Detection Provenance at match_rule() boundary

**What:** After `matcher.py` produces a `DetectionRecord`, record provenance into `detection_provenance` with the Sigma rule's YAML SHA-256, pySigma version, and field_map version.

**When to use:** P21-T02. The `SigmaRule` object is in scope at the `match_rule()` call site.

**Example:**
```python
import hashlib, importlib.metadata

def _rule_sha256(rule: SigmaRule) -> str:
    """Hash the original rule YAML text."""
    # SigmaRule stores the original YAML text via rule.source (pySigma >= 1.0)
    # If not available, serialize rule.to_dict() deterministically.
    src = getattr(rule, "source", None)
    text = src if isinstance(src, str) else str(rule)
    return hashlib.sha256(text.encode()).hexdigest()

PYSIGMA_VERSION = importlib.metadata.version("pySigma")
```

Note: `rule.source` availability should be verified during Wave 0 testing. If absent, `yaml.dump(rule.to_dict())` is the deterministic fallback.

### Pattern 4: LLM Audit Provenance — Promote Log to Table

**What:** The existing `llm_audit.jsonl` already records `prompt_hash`, `response_hash`, `model`, `event_type`, `status`, `operator_id`. P21-T03 requires an additional `audit_id`, `prompt_template_name`, `prompt_template_sha256`, and `grounding_event_ids`. These fields are added to each `_audit_log.info()` call in `ollama_client.py` AND written to a new `llm_audit_provenance` SQLite table.

**When to use:** All LLM generate() and stream_generate() calls.

**Key decision — grounding_event_ids storage:** Store as a JSON array in the `llm_audit_provenance` table (`TEXT` column, `json.dumps(list[str])`). This is consistent with how `matched_event_ids` is stored in the `detections` table. A separate junction table is not warranted for a single-analyst tool.

**Key decision — prompt_template_sha256:** Prompts are Python module-level string constants (e.g., `SYSTEM` and `build_prompt()` in `prompts/analyst_qa.py`). Compute SHA-256 of the module source file at import time using `hashlib.sha256(Path(inspect.getfile(module)).read_bytes()).hexdigest()`. Cache the result as a module-level constant so it is computed once per process.

```python
# In prompts/analyst_qa.py (or a shared prompts/__init__.py):
import hashlib, inspect, pathlib

def _module_sha256() -> str:
    src = pathlib.Path(inspect.getfile(_module_sha256)).read_bytes()
    return hashlib.sha256(src).hexdigest()

TEMPLATE_SHA256 = _module_sha256()
TEMPLATE_NAME = "analyst_qa"
```

### Pattern 5: Playbook Run Provenance

**What:** At playbook run creation, record `playbook_file_sha256` (SHA-256 of the playbook YAML/JSON definition stored in the `steps` column), `playbook_version` (from `playbooks.version`), `trigger_event_ids` (JSON array), `operator_id_who_approved` (from OperatorContext).

**When to use:** P21-T04. The `playbook_runs` table already exists with `run_id`, `playbook_id`, `investigation_id`, `steps_completed`. The provenance data goes in a new `playbook_run_provenance` table rather than widening the existing table.

### Pattern 6: Svelte 5 View Registration

**What:** Add `'provenance'` to the `View` type union in `App.svelte`, add a nav item, conditionally render `ProvenanceView`, and import the component.

**When to use:** P21-T05. Every existing view follows the same pattern.

**Example:**
```typescript
// App.svelte - extend View type:
type View =
  | 'detections' | 'investigation' | 'events' | 'graph' | 'query' | 'ingest'
  | 'intel' | 'hunting' | 'playbooks' | 'reports' | 'assets'
  | 'provenance'          // add this

// Nav group — recommend adding to existing "Investigate" group or a new "Audit" group:
{ id: 'provenance', label: 'Provenance', color: '#f59e0b' }

// Template — in the view-switch block:
{:else if currentView === 'provenance'}
  <ProvenanceView />
```

```svelte
<!-- ProvenanceView.svelte skeleton using Svelte 5 runes -->
<script lang="ts">
  import { api } from '../lib/api.ts'

  let activeTab = $state<'ingest' | 'detection' | 'llm' | 'playbook'>('ingest')
  let searchId = $state('')
  let result = $state<any>(null)
  let loading = $state(false)
  let error = $state<string | null>(null)

  async function lookup() {
    loading = true
    error = null
    try {
      result = await api.provenance[activeTab](searchId)
    } catch (e: any) {
      error = e.message
    } finally {
      loading = false
    }
  }

  function copyHash(hash: string) {
    navigator.clipboard.writeText(hash)
  }
</script>
```

### Anti-Patterns to Avoid
- **Modifying existing table columns in place:** The detections and playbook_runs tables have callers throughout the codebase. Any column addition must use `ALTER TABLE ... ADD COLUMN` with a DEFAULT, not schema recreation.
- **Synchronous SQLite from async handlers:** All SQLite reads/writes from FastAPI route handlers must go through `asyncio.to_thread()`.
- **Computing SHA-256 after parsing:** For ingest provenance, compute the file SHA-256 before parsing begins — parser may normalize, strip, or decode bytes.
- **Blocking the event loop with file hashing:** Large EVTX files (100MB+) must be hashed in `asyncio.to_thread()`.
- **Storing grounding_event_ids in a junction table:** Overkill for a single-analyst tool; JSON array in the row is consistent with how `matched_event_ids` works in detections.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| SHA-256 hashing | Custom hash implementation | `hashlib.sha256()` (stdlib) | Constant-time, battle-tested; `_sha256_short()` already exists in ollama_client.py as a pattern |
| Runtime version lookup | Hardcoded version strings | `importlib.metadata.version('pySigma')` | Survives dependency upgrades; confirmed returns `'1.2.0'` in this venv |
| Auth context extraction | Custom token parsing | `OperatorContext` from `require_role()` dependency | Auth middleware is already wired; every route can receive `ctx: OperatorContext = Depends(require_role("analyst", "admin"))` |
| Clipboard copy | Custom JS clipboard | `navigator.clipboard.writeText()` | Browser Web API; no dependency required |
| Date formatting | Custom ISO formatter | `datetime.now(tz=timezone.utc).isoformat()` via `_now_iso()` | Already defined in sqlite_store.py |

**Key insight:** This phase is almost entirely glue code. Every underlying primitive (hashing, versioning, auth, SQLite patterns, Svelte view registration) already exists in the project. The risk is in ensuring the provenance record is written atomically with the artefact it describes — failures must be non-fatal (log warning, don't block the primary operation).

---

## Common Pitfalls

### Pitfall 1: Provenance Write Failure Blocking Primary Operation
**What goes wrong:** If the `ingest_provenance` INSERT fails (e.g., SQLite locked), it should not fail the entire ingestion of 10,000 events.
**Why it happens:** Tight coupling of provenance write to the main ingestion transaction.
**How to avoid:** Wrap all provenance INSERT calls in `try/except` with `log.warning()`. Provenance is observability infrastructure — it must be non-fatal.
**Warning signs:** Integration tests where provenance INSERT exceptions propagate up to `ingest_file()`.

### Pitfall 2: SHA-256 of Parsed Data Instead of Raw Bytes
**What goes wrong:** Hashing the normalized event dict instead of the original file bytes. The hash will not be reproducible from the original evidence.
**Why it happens:** Ingest pipeline transforms data before the provenance record is written.
**How to avoid:** Compute `raw_sha256` at the very top of `ingest_file()`, before calling `get_parser()`.
**Warning signs:** Hash changes on re-ingest of the same file with a different parser.

### Pitfall 3: pySigma rule.source Attribute
**What goes wrong:** Assuming `SigmaRule` has a `.source` attribute containing the original YAML text. This is not documented in pySigma 1.x public API.
**Why it happens:** Attempting to hash the YAML source for detection provenance.
**How to avoid:** Check `hasattr(rule, 'source')` in Wave 0. Fallback: hash the `.yaml_path` file contents if the rule was loaded from disk (path is available in `load_rules_dir()` which calls `yml_path.read_text()`). Store the YAML text alongside loading, or hash the file path's content.
**Warning signs:** `AttributeError: 'SigmaRule' object has no attribute 'source'` at runtime.

### Pitfall 4: Duplicate llm_audit_provenance Rows
**What goes wrong:** Streaming generates multiple audit log entries (one per token batch). The `llm_audit_provenance` table should record one row per logical LLM call, not one per token.
**Why it happens:** `stream_generate()` emits multiple `_audit_log.info()` calls — start + complete/error.
**How to avoid:** Generate a single `audit_id = str(uuid4())` at the start of each `generate()` / `stream_generate()` call and pass it through. Write the provenance row only once at the `status="complete"` log point.
**Warning signs:** `llm_audit_provenance` has 2x the expected row count.

### Pitfall 5: Svelte SettingsView Already Has 'settings' in View type — adding 'provenance' is easy but test the nav rendering
**What goes wrong:** The current `App.svelte` View type does not include 'settings'. Looking at the nav groups, the SettingsView is imported and conditionally rendered but is not in `navGroups`. Check how SettingsView is triggered before copy-pasting the pattern for ProvenanceView.
**Why it happens:** Some views are accessed via event handlers, not nav buttons.
**How to avoid:** Add ProvenanceView as a proper nav item (recommended under "Investigate" or a new "Audit" group) with `currentView === 'provenance'` condition in the view switch.

### Pitfall 6: field_map_version Constant Missing
**What goes wrong:** The detection provenance record needs a `field_map_version` string. `detections/field_map.py` has no `VERSION` or `__version__` constant today.
**Why it happens:** No versioning was added to field_map.py in earlier phases.
**How to avoid:** Add `FIELD_MAP_VERSION = "20"` (matching the phase that last updated it) to `detections/field_map.py` as part of P21-T02's Wave 0.

---

## Code Examples

Verified patterns from existing codebase:

### SHA-256 file hashing (new — stdlib pattern)
```python
# Confirmed: hashlib is stdlib, available in Python 3.12
import hashlib

def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()
```

### pySigma version at runtime (confirmed working)
```python
import importlib.metadata
PYSIGMA_VERSION = importlib.metadata.version("pySigma")
# Returns: "1.2.0" on this install
```

### SQLite additive migration (from sqlite_store.py __init__)
```python
# Source: backend/stores/sqlite_store.py line 236-242
try:
    self._conn.execute(
        "ALTER TABLE detections ADD COLUMN risk_score INTEGER DEFAULT 0"
    )
    self._conn.commit()
except Exception:
    pass  # column already exists — idempotent
```

### asyncio.to_thread for SQLite (from loader.py)
```python
# Source: ingestion/loader.py _write_graph()
async def _some_async_method(self) -> int:
    def _sync_work() -> int:
        self._stores.sqlite.some_method(...)
        return 1
    return await asyncio.to_thread(_sync_work)
```

### require_role dependency (from backend/core/rbac.py)
```python
# Source: backend/core/rbac.py
from backend.core.rbac import require_role, OperatorContext

@router.get("/api/provenance/ingest/{event_id}")
async def get_ingest_provenance(
    event_id: str,
    request: Request,
    ctx: OperatorContext = Depends(require_role("analyst", "admin")),
) -> dict:
    ...
```

### Svelte 5 rune pattern (from existing views)
```typescript
// Confirmed pattern in App.svelte (Svelte 5)
let activeTab = $state<'ingest' | 'detection' | 'llm' | 'playbook'>('ingest')
let result = $state<ProvenanceRecord | null>(null)
```

### Prompt template SHA-256 (new — stdlib pattern)
```python
# prompts/analyst_qa.py — add to bottom of file
import hashlib
import inspect
import pathlib

def _compute_template_sha256() -> str:
    """Hash this module's source file for provenance tracking."""
    src = pathlib.Path(inspect.getfile(_compute_template_sha256)).read_bytes()
    return hashlib.sha256(src).hexdigest()

TEMPLATE_SHA256: str = _compute_template_sha256()
TEMPLATE_NAME: str = "analyst_qa"
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| llm_audit.jsonl (file only) | llm_audit.jsonl + `llm_audit_provenance` SQLite table | Phase 21 | JSONL stays for streaming/tailing; SQLite enables API queries |
| Detection stored with matched_event_ids only | Detection + `detection_provenance` with rule SHA-256 and version | Phase 21 | Enables reproducing a detection from original rule bytes |
| Ingest recorded in job tracker (in-memory) | Ingest + `ingest_provenance` persisted in SQLite | Phase 21 | Survives process restart; queryable by event_id |

**Deprecated/outdated:**
- `_sha256_short()` in ollama_client.py: This truncates to 16 hex chars for logging brevity. For provenance, full 64-char SHA-256 is required. Do not reuse `_sha256_short()` for provenance records.

---

## Open Questions

1. **Does `SigmaRule` expose the original YAML source text in pySigma 1.2.0?**
   - What we know: The matcher loads rules via `SigmaRule.from_yaml(yml_path.read_text())`. The path `yml_path` is a local variable in `load_rules_dir()`.
   - What's unclear: Whether pySigma 1.2.0 attaches the raw YAML to the rule object.
   - Recommendation: In Wave 0, check `hasattr(rule, 'source')` and `hasattr(rule, 'raw')`. Most reliable path: store the YAML text alongside the rule in a `dict[str, str]` keyed by rule_id inside `SigmaMatcher`, populated during `load_rules_dir()`.

2. **Should `ingest_provenance` be per-event or per-file?**
   - What we know: `ingest_file()` processes one file that produces N events. One SHA-256 covers all events from that file.
   - What's unclear: P21-T01 requires `GET /api/provenance/ingest/{event_id}`, implying a per-event lookup. But the raw SHA-256 is per-file.
   - Recommendation: One provenance row per file ingestion run, with `event_ids` stored as a JSON array. The GET endpoint does `SELECT * FROM ingest_provenance WHERE event_ids LIKE '%event_id%'` or uses a proper junction table `ingest_provenance_events(prov_id, event_id)`. The junction table is cleaner for large batches — recommend `ingest_provenance` + `ingest_provenance_events(prov_id TEXT, event_id TEXT, PRIMARY KEY(prov_id, event_id))`.

3. **What nav group does ProvenanceView belong to?**
   - What we know: Existing groups are Monitor, Investigate, Intelligence, Respond, Platform.
   - What's unclear: Provenance is audit/compliance, which doesn't map neatly.
   - Recommendation: Add to "Investigate" group (alongside Investigation and Attack Graph). Alternatively, add a new "Audit" group. Either works.

---

## Validation Architecture

> nyquist_validation is enabled in .planning/config.json.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest + pytest-asyncio (auto mode) |
| Config file | `pyproject.toml` (`[tool.pytest.ini_options]` asyncio_mode = "auto") |
| Quick run command | `uv run pytest tests/unit/test_provenance.py -x -q` |
| Full suite command | `uv run pytest tests/unit/ -x -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| P21-T01 | `ingest_provenance` table created in SQLiteStore | unit | `uv run pytest tests/unit/test_provenance.py::test_ingest_provenance_table_exists -x` | Wave 0 |
| P21-T01 | `_sha256_file()` returns 64-char hex string | unit | `uv run pytest tests/unit/test_provenance.py::test_sha256_file_hash -x` | Wave 0 |
| P21-T01 | `ingest_provenance` row written after `ingest_file()` completes | unit | `uv run pytest tests/unit/test_provenance.py::test_ingest_provenance_written -x` | Wave 0 |
| P21-T01 | `GET /api/provenance/ingest/{event_id}` returns 200 with sha256, parser_name | unit | `uv run pytest tests/unit/test_provenance.py::test_ingest_provenance_api -x` | Wave 0 |
| P21-T01 | Provenance INSERT failure does not abort ingestion | unit | `uv run pytest tests/unit/test_provenance.py::test_ingest_provenance_failure_nonfatal -x` | Wave 0 |
| P21-T02 | `detection_provenance` table created in SQLiteStore | unit | `uv run pytest tests/unit/test_provenance.py::test_detection_provenance_table_exists -x` | Wave 0 |
| P21-T02 | Detection provenance row contains pySigma version and rule_sha256 | unit | `uv run pytest tests/unit/test_provenance.py::test_detection_provenance_fields -x` | Wave 0 |
| P21-T02 | `GET /api/provenance/detection/{id}` returns 200 with rule_sha256, pysigma_version | unit | `uv run pytest tests/unit/test_provenance.py::test_detection_provenance_api -x` | Wave 0 |
| P21-T03 | `llm_audit_provenance` table created in SQLiteStore | unit | `uv run pytest tests/unit/test_provenance.py::test_llm_provenance_table_exists -x` | Wave 0 |
| P21-T03 | LLM provenance row written by `generate()` with audit_id, prompt_template_sha256, grounding_event_ids | unit | `uv run pytest tests/unit/test_provenance.py::test_llm_provenance_written -x` | Wave 0 |
| P21-T03 | Only one provenance row per logical LLM call (not per token) | unit | `uv run pytest tests/unit/test_provenance.py::test_llm_provenance_no_duplicate_rows -x` | Wave 0 |
| P21-T03 | `GET /api/provenance/llm/{audit_id}` returns 200 with model_id, response_sha256 | unit | `uv run pytest tests/unit/test_provenance.py::test_llm_provenance_api -x` | Wave 0 |
| P21-T04 | `playbook_run_provenance` table created in SQLiteStore | unit | `uv run pytest tests/unit/test_provenance.py::test_playbook_provenance_table_exists -x` | Wave 0 |
| P21-T04 | Playbook run provenance row contains playbook_file_sha256, operator_id | unit | `uv run pytest tests/unit/test_provenance.py::test_playbook_provenance_fields -x` | Wave 0 |
| P21-T04 | `GET /api/provenance/playbook/{run_id}` returns 200 with trigger_event_ids | unit | `uv run pytest tests/unit/test_provenance.py::test_playbook_provenance_api -x` | Wave 0 |
| P21-T05 | All 4 provenance endpoints return 401 without auth token | unit | `uv run pytest tests/unit/test_provenance.py::test_provenance_endpoints_require_auth -x` | Wave 0 |
| P21-T05 | ProvenanceView renders without JS errors (smoke) | manual | Open `https://localhost` → Provenance tab | N/A |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/unit/test_provenance.py -x -q`
- **Per wave merge:** `uv run pytest tests/unit/ -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/unit/test_provenance.py` — all 16 test stubs above; use `pytest.fail('NOT IMPLEMENTED')` pattern from Phase 19
- [ ] `backend/models/provenance.py` — Pydantic response models for all 4 artefact types (needed by both API and tests)
- [ ] `detections/field_map.py` — add `FIELD_MAP_VERSION = "20"` constant (required by P21-T02)

---

## Sources

### Primary (HIGH confidence)
- Direct code inspection — `backend/stores/sqlite_store.py` — full DDL, ALTER TABLE migration pattern, `insert_detection()` signature
- Direct code inspection — `ingestion/loader.py` — `ingest_file()` pipeline, `asyncio.to_thread()` pattern, no existing provenance writes
- Direct code inspection — `detections/matcher.py` — `match_rule()` creates DetectionRecord, `save_detections()` calls `sqlite.insert_detection()`
- Direct code inspection — `backend/services/ollama_client.py` — `_audit_log`, `_sha256_short()`, `operator_id` param on `generate()`/`embed()`
- Direct code inspection — `logs/llm_audit.jsonl` — confirmed fields: timestamp, event_type, model, prompt_hash, response_hash, status, operator_id
- Direct code inspection — `dashboard/src/App.svelte` — View type union, navGroups pattern, conditional view rendering
- Runtime verification — `importlib.metadata.version('pySigma')` returns `'1.2.0'`
- Runtime verification — `hashlib` and `importlib.metadata` confirmed available in Python 3.12 venv

### Secondary (MEDIUM confidence)
- `backend/core/logging.py` grep — confirmed `llm_audit` logger writes to `logs/llm_audit.jsonl` with JSON formatter
- `backend/core/auth.py` + `backend/core/rbac.py` — `OperatorContext` and `require_role()` are the correct auth dependency pattern
- `backend/models/event.py` — `NormalizedEvent` has no provenance fields; provenance is correctly separate

### Tertiary (LOW confidence)
- None — all findings verified from source code directly.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries are stdlib or already installed and tested
- Architecture: HIGH — all patterns copied from existing working code in the project
- Pitfalls: HIGH — identified from direct code reading (e.g., `_sha256_short` truncation, `SigmaRule.source` uncertainty, duplicate audit rows)
- Test map: HIGH — test file naming and pytest conventions match existing 50+ test files

**Research date:** 2026-04-01
**Valid until:** 2026-05-01 (stable dependencies; pySigma 1.2.0 pinned)
