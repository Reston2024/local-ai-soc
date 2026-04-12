# Phase 40: Atomic Red Team Validation - Research

**Researched:** 2026-04-12
**Domain:** Atomic Red Team YAML catalog ingestion, SQLite reference store, FastAPI endpoints, Svelte 5 browse/validate UI
**Confidence:** HIGH — all patterns verified against existing codebase; ART YAML structure verified against live GitHub source

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **Storage:** SQLite (not DuckDB) — consistent with all prior catalogs (IOC, STIX, CAR, playbooks). DuckDB remains for time-series events only.
- **Catalog scope:** Full catalog (~330 technique directories, 1000+ tests). No filtering by platform or tactic.
- **Pre-generated JSON bundle:** `scripts/generate_atomics_bundle.py` runs once, commits `backend/data/atomics.json`. No GitHub dependency at runtime. Same pattern as CAR (`scripts/generate_car_bundle.py` → `backend/data/car_analytics.json`).
- **Startup seed pattern:** AtomicsStore seeded in lifespan, same as CARStore/AttackStore/PlaybookStore.
- **PowerShell format:** `Invoke-AtomicTest T1059.001 -TestNumbers 1` — standard ART format.
- **Three commands per test:** Prereq check command, test command, cleanup command — each with its own copy button. Displayed inline in the test row/card (not a modal).
- **Validation window:** 5 minutes. PASS = Sigma detection record exists with matching ATT&CK technique within window.
- **Validation trigger:** Manual Validate button per test row. Backend checks last 5 minutes. Inline pass/fail result.
- **No automatic polling.**
- **AtomicsView layout:** Grouped by ATT&CK technique. Collapsible technique header rows → individual atomic test rows beneath.
- **Per-test row shows:** test name, supported platforms (chip-style), coverage badge, 3 copy buttons (Prereq / Test / Cleanup).
- **Coverage badges live in AtomicsView only** — AttackCoverageView stays unchanged.
- **Badge states:** green = atomic validated (Sigma detection confirmed), yellow = Sigma rule exists for technique but not validated, red = no coverage.

### Claude's Discretion
- Exact SQLite schema for atomics tables (columns, indexes)
- JSON field mapping from ART YAML to storage schema
- How technique coverage status (yellow/green/red) is computed — whether via JOIN with detections table or a separate validation_results table
- Nav group placement for AtomicsView (Respond or Intelligence)
- Exact CSS for platform chips and coverage badge colors

### Deferred Ideas (OUT OF SCOPE)
- Automatic polling after copy (spinner until detection appears)
- Augmenting AttackCoverageView heatmap with validation badges
- Scheduled/recurring atomic test runs
- Integration with AtomicsView in HuntingView
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| P40-T01 | Ingest Atomic Red Team test catalog (atomics YAML) into SQLite | Bundle script pattern from generate_car_bundle.py; AtomicsStore DDL pattern from CARStore; startup seed pattern from seed_car_analytics() |
| P40-T02 | Add GET /api/atomics endpoint returning ATT&CK-mapped test catalog | Router pattern from backend/api/detect.py; asyncio.to_thread wrapper for SQLite reads |
| P40-T03 | Add AtomicsView tab — browse tests by technique (grouped/collapsible), see detection coverage status | DetectionsView expandable row pattern; AttackCoverageView badge visual language |
| P40-T04 | "Run Atomic" button generating Invoke-AtomicTest PowerShell command with copy-to-clipboard; show prereq/test/cleanup commands | ART YAML executor.command, executor.cleanup_command, dependencies[].get_prereq_command fields; Invoke-AtomicTest format |
| P40-T05 | POST /api/atomics/validate — 5-minute window, PASS = Sigma detection fired for matching technique | detections table query by attack_technique + created_at; SQLite datetime comparison pattern |
| P40-T06 | Detection coverage badge per ATT&CK technique — green/yellow/red | JOIN atomics_techniques against sigma rules (from matcher) + validation_results table |
</phase_requirements>

---

## Summary

Phase 40 adds threat simulation validation to the SOC Brain by ingesting the Atomic Red Team test catalog and closing the loop between red team test execution and detection pipeline confirmation. The implementation follows the exact same patterns as Phase 39 (MITRE CAR) — pre-generated JSON bundle, AtomicsStore class wrapping SQLite, startup seed, new API router, new Svelte view.

The Atomic Red Team catalog (github.com/redcanaryco/atomic-red-team) contains approximately 330 technique directories covering both parent techniques (T1003) and sub-techniques (T1003.001). Each directory contains one YAML file with an `atomic_tests` array. The key generation challenge is the `#{variable}` substitution markers in executor commands — these must be preserved as-is for the copy-to-clipboard output, since Invoke-AtomicRedTeam handles substitution at runtime. Input argument defaults can optionally be surfaced in the UI tooltip but are not substituted server-side.

The validation query is a SQLite lookup: `SELECT id FROM detections WHERE attack_technique LIKE ? AND created_at > ?` with a 5-minute cutoff. Coverage badge logic follows a three-tier hierarchy: validated (green) > sigma_exists (yellow) > no_coverage (red). A separate `atomics_validation_results` table is the right approach for tracking which technique+test combinations have been validated, keyed on (technique_id, test_number), so results persist across page reloads.

**Primary recommendation:** Follow CARStore → generate_car_bundle.py exactly. The only structural difference is that ART uses a nested array (`atomic_tests[]`) rather than per-file one-entry-per-analytic. Flatten at bundle generation time: one JSON entry per atomic test, not per technique.

---

## Standard Stack

### Core (all pre-installed in this project)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| sqlite3 | stdlib | AtomicsStore CRUD | Every prior reference store uses raw sqlite3, not SQLiteStore ORM |
| pyyaml | project dep | Parse ART YAML files during bundle generation | Same as CAR bundle generator |
| urllib.request | stdlib | HTTP fetch from GitHub raw URLs | Used in generate_car_bundle.py (httpx not installed) |
| asyncio.to_thread | stdlib | Wrap synchronous SQLite reads in async handlers | Established pattern throughout codebase |
| FastAPI APIRouter | project dep | New /api/atomics router | Same as all other API modules |

### Frontend (Svelte 5, pre-installed)
| Item | Purpose |
|------|---------|
| $state, $derived, $effect | Runes — no Svelte stores |
| navigator.clipboard.writeText() | Copy-to-clipboard for command strings |
| Relative imports (not `$lib`) | See commit 233d007 — project convention |

### No New Dependencies Required
All required libraries are already available in the project. Bundle generation uses the same `urllib.request` + `yaml` approach as the CAR bundle generator.

**Installation:**
```bash
# Nothing to install — all dependencies already present
```

---

## Architecture Patterns

### Recommended Project Structure (new files only)
```
scripts/
└── generate_atomics_bundle.py    # One-time bundle generation

backend/
├── data/
│   └── atomics.json              # Pre-generated bundle (committed)
└── services/
    └── atomics/
        ├── __init__.py
        └── atomics_store.py      # AtomicsStore + seed_atomics()

backend/api/
└── atomics.py                    # GET /api/atomics, POST /api/atomics/validate

dashboard/src/views/
└── AtomicsView.svelte            # Browse + validate UI

tests/unit/
└── test_atomics_store.py         # Wave 0 TDD stubs (8 stubs)
```

### Pattern 1: Bundle Generation Script
**What:** Python script fetching ART YAML from GitHub via the atomics directory listing API, parsing each T{id}.yaml, flattening into one JSON entry per atomic test.
**When to use:** Run once to generate `backend/data/atomics.json`. Committed to repo. Never runs at production startup.

```python
# Source: modeled after scripts/generate_car_bundle.py
GITHUB_API_URL = "https://api.github.com/repos/redcanaryco/atomic-red-team/contents/atomics"
RAW_BASE_URL = "https://raw.githubusercontent.com/redcanaryco/atomic-red-team/master/atomics"
OUTPUT_PATH = Path(__file__).parent.parent / "backend" / "data" / "atomics.json"

# ART YAML top-level structure:
# attack_technique: T1059.001
# display_name: 'Command and Scripting Interpreter: PowerShell'
# atomic_tests:
#   - name: "Test name"
#     auto_generated_guid: "uuid"
#     description: "..."
#     supported_platforms: [windows, linux, macos]
#     input_arguments:              # optional dict
#       param_name:
#         description: "..."
#         type: url|string|path|integer
#         default: "value"
#     dependencies:                 # optional list
#       - description: "..."
#         prereq_command: "script"
#         get_prereq_command: "script"
#     dependency_executor_name: powershell|sh
#     executor:
#       name: powershell|command_prompt|bash|sh|manual
#       elevation_required: true|false
#       command: "... #{variable} ..."   # KEEP #{} markers as-is
#       cleanup_command: "..."           # optional
#       steps: "..."                     # manual executor only

def _parse_art_yaml(technique_id: str, content: bytes) -> list[dict]:
    raw = yaml.safe_load(content)
    technique_id = raw.get("attack_technique", technique_id)
    display_name = raw.get("display_name", "")
    entries = []
    for i, test in enumerate(raw.get("atomic_tests", []), start=1):
        executor = test.get("executor", {}) or {}
        deps = test.get("dependencies", []) or []
        prereq_cmd = ""
        if deps:
            dep_executor = test.get("dependency_executor_name", "powershell")
            prereq_cmd = "\n---\n".join(d.get("get_prereq_command", "") for d in deps if d)
        input_args = test.get("input_arguments", {}) or {}
        entries.append({
            "technique_id": technique_id,
            "display_name": display_name,
            "test_number": i,
            "test_name": test.get("name", ""),
            "auto_generated_guid": test.get("auto_generated_guid", ""),
            "description": test.get("description", "").strip(),
            "supported_platforms": json.dumps(test.get("supported_platforms", [])),
            "executor_name": executor.get("name", ""),
            "elevation_required": executor.get("elevation_required", False),
            "command": executor.get("command", "") or executor.get("steps", ""),
            "cleanup_command": executor.get("cleanup_command", ""),
            "prereq_command": prereq_cmd,
            "input_arguments": json.dumps(input_args),
        })
    return entries
```

### Pattern 2: AtomicsStore (mirrors CARStore exactly)
**What:** SQLite CRUD class with DDL, bulk_insert, seed function. Separate table for validation results.
**When to use:** All reads from async handlers via asyncio.to_thread().

```python
# Source: mirrors backend/services/car/car_store.py
DDL = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS atomics (
    technique_id          TEXT NOT NULL,
    display_name          TEXT NOT NULL DEFAULT '',
    test_number           INTEGER NOT NULL,
    test_name             TEXT NOT NULL,
    auto_generated_guid   TEXT NOT NULL DEFAULT '',
    description           TEXT NOT NULL DEFAULT '',
    supported_platforms   TEXT NOT NULL DEFAULT '[]',  -- JSON array string
    executor_name         TEXT NOT NULL DEFAULT '',
    elevation_required    INTEGER NOT NULL DEFAULT 0,  -- 0/1 bool
    command               TEXT NOT NULL DEFAULT '',
    cleanup_command       TEXT NOT NULL DEFAULT '',
    prereq_command        TEXT NOT NULL DEFAULT '',
    input_arguments       TEXT NOT NULL DEFAULT '{}',  -- JSON dict string
    PRIMARY KEY (technique_id, test_number)
);

CREATE TABLE IF NOT EXISTS atomics_validation_results (
    technique_id   TEXT NOT NULL,
    test_number    INTEGER NOT NULL,
    verdict        TEXT NOT NULL,         -- 'pass' | 'fail'
    validated_at   TEXT NOT NULL,         -- ISO-8601
    detection_id   TEXT,                  -- matched detection.id if pass
    PRIMARY KEY (technique_id, test_number)
);

CREATE INDEX IF NOT EXISTS idx_atomics_technique ON atomics (technique_id);
"""

class AtomicsStore:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        self._conn.executescript(DDL)
        self._conn.commit()

    def atomic_count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM atomics").fetchone()[0]

    def bulk_insert(self, tests: list[dict]) -> None:
        """Idempotent INSERT OR IGNORE."""
        self._conn.executemany("""INSERT OR IGNORE INTO atomics
            (technique_id, display_name, test_number, test_name, auto_generated_guid,
             description, supported_platforms, executor_name, elevation_required,
             command, cleanup_command, prereq_command, input_arguments)
            VALUES (:technique_id, :display_name, :test_number, :test_name,
                    :auto_generated_guid, :description, :supported_platforms,
                    :executor_name, :elevation_required, :command, :cleanup_command,
                    :prereq_command, :input_arguments)""", tests)
        self._conn.commit()

    def list_techniques(self) -> list[dict]:
        """Return distinct technique_id + display_name, ordered."""
        rows = self._conn.execute(
            "SELECT DISTINCT technique_id, display_name FROM atomics ORDER BY technique_id"
        ).fetchall()
        return [dict(r) for r in rows]

    def get_tests_for_technique(self, technique_id: str) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM atomics WHERE technique_id = ? ORDER BY test_number",
            (technique_id,)
        ).fetchall()
        return [dict(r) for r in rows]

    def save_validation_result(self, technique_id: str, test_number: int,
                                verdict: str, detection_id: str | None) -> None:
        self._conn.execute("""INSERT OR REPLACE INTO atomics_validation_results
            (technique_id, test_number, verdict, validated_at, detection_id)
            VALUES (?, ?, ?, datetime('now'), ?)""",
            (technique_id, test_number, verdict, detection_id))
        self._conn.commit()

    def get_validation_results(self) -> dict[tuple, dict]:
        """Return {(technique_id, test_number): {verdict, validated_at, detection_id}}."""
        rows = self._conn.execute(
            "SELECT technique_id, test_number, verdict, validated_at, detection_id "
            "FROM atomics_validation_results"
        ).fetchall()
        return {(r["technique_id"], r["test_number"]): dict(r) for r in rows}
```

### Pattern 3: Validation Query (POST /api/atomics/validate)
**What:** Check whether a Sigma detection record exists for the technique within the last 5 minutes.
**When to use:** Analyst clicks Validate after running the PowerShell command.

```python
# Source: backend/stores/sqlite_store.py detections table schema
# detections.attack_technique is a TEXT column (e.g. "T1059.001" or "T1059")
# detections.created_at is TEXT ISO-8601

def _check_detection_sync(conn, technique_id: str, cutoff_iso: str) -> str | None:
    """Return detection ID if found, else None. Run in asyncio.to_thread."""
    parent = technique_id.split(".")[0].upper()
    row = conn.execute(
        """SELECT id FROM detections
           WHERE (attack_technique = ? OR attack_technique LIKE ? OR attack_technique = ?)
             AND created_at > ?
           ORDER BY created_at DESC LIMIT 1""",
        (technique_id, f"{parent}.%", parent, cutoff_iso)
    ).fetchone()
    return row["id"] if row else None
```

### Pattern 4: Invoke-AtomicTest Command Generation
**What:** Build the PowerShell command string from technique_id + test_number.
**When to use:** Displayed inline in UI; analyst copies and runs manually.

```
# Standard Invoke-AtomicRedTeam format:
Invoke-AtomicTest T1059.001 -TestNumbers 1

# Prerequisites check:
Invoke-AtomicTest T1059.001 -TestNumbers 1 -CheckPrereqs

# Cleanup:
Invoke-AtomicTest T1059.001 -TestNumbers 1 -Cleanup
```

The three copy-button commands are computed client-side (or server-side string format) — no complex substitution needed. The `command` and `cleanup_command` fields from the YAML are shown as reference (what the PS module will execute), but the actual button copies the `Invoke-AtomicTest ...` invocation, not the raw command.

### Pattern 5: Coverage Badge Computation
**What:** Per-technique three-state coverage badge.
**When to use:** Rendered in AtomicsView technique header row.

```
Priority order (highest wins):
1. GREEN  — atomics_validation_results has verdict='pass' for any test of this technique_id
2. YELLOW — detections table has attack_technique matching this technique (any time, not just 5 min)
            OR Sigma rules are loaded that tag this technique (check via AttackStore.list_techniques_by_tactic)
3. RED    — neither
```

**Recommendation (Claude's Discretion):** Use a JOIN approach in GET /api/atomics:
- Query `atomics_validation_results` for all validated technique_ids → green set
- Query `detections GROUP BY attack_technique` (all time) for detected technique_ids → yellow set
- Return badge status per technique inline in the API response

This avoids a separate per-technique roundtrip from the frontend.

### Pattern 6: AtomicsView Layout (Svelte 5)
**What:** Grouped collapsible technique rows → per-test sub-rows with 3 copy buttons + Validate.
**When to use:** New AtomicsView.svelte.

```typescript
// Mirrors DetectionsView expandedId pattern (Phase 39)
let expandedTechniqueId = $state<string | null>(null)
// Per-test validation state
let validationResults = $state<Record<string, 'pass' | 'fail' | 'checking' | null>>({})

// Key for validation result dict: `${technique_id}:${test_number}`
function validationKey(technique_id: string, test_number: number): string {
  return `${technique_id}:${test_number}`
}

async function handleValidate(technique_id: string, test_number: number) {
  const key = validationKey(technique_id, test_number)
  validationResults = { ...validationResults, [key]: 'checking' }
  try {
    const result = await api.atomics.validate(technique_id, test_number)
    validationResults = { ...validationResults, [key]: result.verdict }
  } catch {
    validationResults = { ...validationResults, [key]: 'fail' }
  }
}
```

### Anti-Patterns to Avoid

- **Substituting `#{variable}` markers server-side:** Do not attempt to replace input argument defaults in the command string. Invoke-AtomicRedTeam handles this at runtime. Store and display the raw command with `#{variable}` markers intact.
- **Storing all three commands as one field:** Store `command`, `cleanup_command`, `prereq_command` as separate columns — each has its own copy button.
- **Using DuckDB for atomics:** All reference data is SQLite. The decision is locked.
- **Fetching atomics from GitHub at runtime:** Bundle must be pre-generated and committed. No runtime HTTP dependency.
- **Keying validation_results on technique_id alone:** Key on (technique_id, test_number) so different tests for the same technique can have independent validation verdicts.
- **Using `$lib` alias in Svelte imports:** Use relative imports (`../lib/api.ts`). See commit 233d007.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Copy to clipboard | Custom flash/toast | `navigator.clipboard.writeText()` | Browser API, handles permissions gracefully |
| YAML parsing | Custom parser | `pyyaml` (already installed) | ART YAML has multi-line strings, edge cases |
| GitHub file listing | Recursive crawl | GitHub API `contents/atomics` endpoint | Returns JSON array of directory entries |
| SQLite idempotent insert | Custom duplicate check | `INSERT OR IGNORE` with PRIMARY KEY | Standard SQLite pattern used in CARStore |
| Validation result persistence | In-memory dict | Separate `atomics_validation_results` table | Survives page reload; required for badge state |

---

## Common Pitfalls

### Pitfall 1: ART `atomics/` Directory Contains Non-Technique Entries
**What goes wrong:** The GitHub API listing of `atomics/` includes an `Indexes` directory (and potentially `used_guids.txt`). Parsing these as technique YAML fails.
**Why it happens:** The directory listing is not filtered by default.
**How to avoid:** Filter entries: only process directories where `name` starts with `T` and matches the pattern `T\d{4}(\.\d{3})?`.
**Warning signs:** YAML parse error for `Indexes/index.yaml` or a non-technique file.

### Pitfall 2: `#{variable}` Substitution Markers in Commands
**What goes wrong:** Commands like `powershell.exe "... '#{mimurl}' ..."` look broken in the UI.
**Why it happens:** ART uses `#{param_name}` syntax that Invoke-AtomicRedTeam replaces at runtime.
**How to avoid:** Display the raw command with markers. Optionally show a tooltip with default values from `input_arguments`. Do not substitute.
**Warning signs:** Any server-side string replacement of `#{}`.

### Pitfall 3: `executor` Is `None` for Manual Executors
**What goes wrong:** `executor.get("command", "")` raises `AttributeError` because `executor` is a dict with `name: manual` and `steps` instead of `command`.
**Why it happens:** Manual tests describe steps in prose rather than runnable commands.
**How to avoid:** `command = executor.get("command", "") or executor.get("steps", "")`. Store steps in the `command` column for manual tests.
**Warning signs:** KeyError or empty command column for tests with `executor.name == "manual"`.

### Pitfall 4: `sqlite3.Row` row_factory Must Be Set
**What goes wrong:** `dict(row)` raises `TypeError` because `sqlite3.Row` is not iterable as a dict without row_factory.
**Why it happens:** `sqlite3.connect()` default row factory is a plain tuple.
**How to avoid:** Set `conn.row_factory = sqlite3.Row` in AtomicsStore constructor (or at connection creation). Established pattern from test_car_store.py.
**Warning signs:** `TypeError` when calling `dict(row)` in store methods.

### Pitfall 5: Validation Query — Technique ID Mismatch
**What goes wrong:** Detection recorded as `T1059.001` (sub-technique), atomic test identified as `T1059.001` — but query uses exact match only, missing detections recorded at parent level or vice versa.
**Why it happens:** Sigma rules tag at sub-technique level; some tag at parent level.
**How to avoid:** Query covers both: exact match on `technique_id` AND `attack_technique LIKE 'T1059.%'` AND parent exact match. See Pattern 3 SQL above.
**Warning signs:** Validation returning FAIL when detection clearly fired.

### Pitfall 6: ART Catalog Scale — API Rate Limiting
**What goes wrong:** Bundle generator makes 330 HTTP requests to GitHub raw CDN and hits rate limits.
**Why it happens:** GitHub raw CDN allows many requests but GitHub API has 60 req/hour unauthenticated.
**How to avoid:** Use raw CDN (`raw.githubusercontent.com`) for YAML content fetches — not the API. Use GitHub API only for directory listing. Add 0.5s throttle every 20 files (same as CAR bundle generator).
**Warning signs:** HTTP 429 responses during bundle generation.

### Pitfall 7: `dependencies` Is Empty List or `None`
**What goes wrong:** `test.get("dependencies", []) or []` evaluates to `[]` but some tests have `dependencies: null` in YAML.
**Why it happens:** ART YAML authors sometimes write `dependencies: null` instead of omitting the key.
**How to avoid:** Always `deps = test.get("dependencies") or []` (handles both `None` and missing key).
**Warning signs:** `TypeError: 'NoneType' is not iterable` during bundle generation.

---

## Code Examples

### GET /api/atomics response shape
```python
# Source: inferred from CARStore pattern + AtomicsStore design
# Returns grouped structure for efficient frontend rendering
{
  "techniques": [
    {
      "technique_id": "T1059.001",
      "display_name": "Command and Scripting Interpreter: PowerShell",
      "coverage": "validated",  # "validated" | "detected" | "none"
      "tests": [
        {
          "test_number": 1,
          "test_name": "Mimikatz",
          "supported_platforms": ["windows"],
          "executor_name": "command_prompt",
          "elevation_required": true,
          "command": "powershell.exe \"IEX (New-Object ...) '#{mimurl}'\"",
          "cleanup_command": "",
          "prereq_command": "",
          "invoke_command": "Invoke-AtomicTest T1059.001 -TestNumbers 1",
          "invoke_prereq": "Invoke-AtomicTest T1059.001 -TestNumbers 1 -CheckPrereqs",
          "invoke_cleanup": "Invoke-AtomicTest T1059.001 -TestNumbers 1 -Cleanup",
          "validation": null  # null | {verdict: "pass"|"fail", validated_at: "..."}
        }
      ]
    }
  ],
  "total_techniques": 220,
  "total_tests": 1050
}
```

### POST /api/atomics/validate request/response
```python
# Request body
{ "technique_id": "T1059.001", "test_number": 1 }

# Response
{ "verdict": "pass",  "detection_id": "abc123", "checked_at": "2026-04-12T14:30:00Z" }
# or
{ "verdict": "fail", "detection_id": null, "checked_at": "2026-04-12T14:30:00Z" }
```

### api.ts interfaces (Phase 40 additions)
```typescript
// Source: follows CARAnalytic interface pattern in api.ts
export interface AtomicTest {
  test_number: number
  test_name: string
  supported_platforms: string[]
  executor_name: string
  elevation_required: boolean
  command: string
  cleanup_command: string
  prereq_command: string
  invoke_command: string
  invoke_prereq: string
  invoke_cleanup: string
  validation: { verdict: 'pass' | 'fail'; validated_at: string } | null
}

export interface AtomicTechnique {
  technique_id: string
  display_name: string
  coverage: 'validated' | 'detected' | 'none'
  tests: AtomicTest[]
}

export interface AtomicsResponse {
  techniques: AtomicTechnique[]
  total_techniques: number
  total_tests: number
}

export interface ValidationResult {
  verdict: 'pass' | 'fail'
  detection_id: string | null
  checked_at: string
}
```

### main.py lifespan addition
```python
# After 7d. Phase 39 CAR block — Phase 40 atomics
from backend.services.atomics.atomics_store import AtomicsStore, seed_atomics
atomics_store = AtomicsStore(sqlite_store._conn)
app.state.atomics_store = atomics_store
log.info("AtomicsStore initialised (Phase 40)")
asyncio.ensure_future(seed_atomics(atomics_store))
log.info("Atomics seed task scheduled (Phase 40)")
```

---

## State of the Art

| Old Approach | Current Approach | Impact |
|--------------|-----------------|--------|
| Runtime GitHub fetch | Pre-generated JSON bundle committed to repo | No runtime dependency, instant startup seed |
| Modal for command display | Inline row expansion with 3 copy buttons | Red team workflow — always visible cleanup |
| DuckDB for all data | SQLite for reference catalogs, DuckDB for events | Write queue contention eliminated for catalog data |

---

## Open Questions

1. **Should `GET /api/atomics` return all tests in one response, or paginate?**
   - What we know: CAR returns all 158 entries unbounded. Atomics is ~1050 entries.
   - What's unclear: Frontend performance rendering 1050 rows (most collapsed).
   - Recommendation: Return all in one call (same as CAR). Frontend renders only expanded technique rows — collapsed rows are just headers. No pagination needed.

2. **Nav group for AtomicsView — Respond or Intelligence?**
   - What we know: Claude's Discretion.
   - Recommendation: **Intelligence** group (alongside ATT&CK Coverage, Hunting). Rationale: browsing what you can simulate is an intelligence/preparation activity, not a response activity. "Respond" is for active incident playbooks.

3. **Does `prereq_command` store `get_prereq_command` or `prereq_command` from YAML?**
   - What we know: ART dependencies have two fields: `prereq_command` (checks if prereq met) and `get_prereq_command` (installs the prereq).
   - Recommendation: Store `get_prereq_command` in the `prereq_command` column — this is the command analysts actually run to set up the test environment. The check command is less useful for copy-paste UX.

---

## Validation Architecture

`nyquist_validation` is enabled in `.planning/config.json`.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x (uv run pytest) |
| Config file | pyproject.toml (pytest-asyncio mode: auto) |
| Quick run command | `uv run pytest tests/unit/test_atomics_store.py -x` |
| Full suite command | `uv run pytest tests/unit/ -x` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| P40-T01 | AtomicsStore DDL creates `atomics` + `atomics_validation_results` tables | unit | `uv run pytest tests/unit/test_atomics_store.py::test_atomics_table_exists -x` | ❌ Wave 0 |
| P40-T01 | bulk_insert populates atomics; atomic_count() returns correct count | unit | `uv run pytest tests/unit/test_atomics_store.py::test_bulk_insert -x` | ❌ Wave 0 |
| P40-T01 | seed_atomics() skips if already seeded (idempotent) | unit | `uv run pytest tests/unit/test_atomics_store.py::test_seed_idempotent -x` | ❌ Wave 0 |
| P40-T01 | generate_atomics_bundle.py parses YAML and flattens to per-test entries | unit | `uv run pytest tests/unit/test_atomics_store.py::test_bundle_parse -x` | ❌ Wave 0 |
| P40-T02 | GET /api/atomics returns 200 with techniques + tests structure | unit | `uv run pytest tests/unit/test_atomics_api.py::test_get_atomics -x` | ❌ Wave 0 |
| P40-T05 | POST /api/atomics/validate returns pass when detection exists within 5 min | unit | `uv run pytest tests/unit/test_atomics_api.py::test_validate_pass -x` | ❌ Wave 0 |
| P40-T05 | POST /api/atomics/validate returns fail when no detection in window | unit | `uv run pytest tests/unit/test_atomics_api.py::test_validate_fail -x` | ❌ Wave 0 |
| P40-T06 | save_validation_result() persists verdict; get_validation_results() retrieves it | unit | `uv run pytest tests/unit/test_atomics_store.py::test_validation_persistence -x` | ❌ Wave 0 |
| P40-T03 | AtomicsView browse/badge rendering | manual | Browser: navigate to Atomics view, expand T1059 group | N/A |
| P40-T04 | Copy-to-clipboard produces correct Invoke-AtomicTest string | manual | Browser: click Prereq/Test/Cleanup copy buttons, verify clipboard content | N/A |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/unit/test_atomics_store.py tests/unit/test_atomics_api.py -x`
- **Per wave merge:** `uv run pytest tests/unit/ -x`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/unit/test_atomics_store.py` — 4 stubs covering P40-T01 DDL, bulk_insert, idempotent seed, bundle parse
- [ ] `tests/unit/test_atomics_api.py` — 3 stubs covering P40-T02 catalog endpoint, P40-T05 validate pass/fail
- [ ] `backend/services/atomics/__init__.py` — empty init for module
- [ ] `backend/data/atomics.json` — generated by `uv run python scripts/generate_atomics_bundle.py` in Wave 0

*(8 total stubs across 2 test files — matches CARStore Wave 0 stub count of 8)*

---

## Sources

### Primary (HIGH confidence)
- `backend/services/car/car_store.py` — CARStore exact implementation pattern
- `scripts/generate_car_bundle.py` — Bundle generation exact pattern
- `backend/stores/sqlite_store.py` — detections table schema (attack_technique, created_at columns)
- `backend/main.py` — Lifespan init block; CARStore wiring at lines 312-318
- `dashboard/src/App.svelte` — navGroups array structure; View union type
- `dashboard/src/lib/api.ts` — CARAnalytic interface; Detection interface; api patterns
- `dashboard/src/views/DetectionsView.svelte` — expandedId collapsible row pattern
- `tests/unit/test_car_store.py` — Wave 0 stub test structure to replicate
- Raw GitHub: `https://raw.githubusercontent.com/redcanaryco/atomic-red-team/master/atomics/T1059.001/T1059.001.yaml` — ART YAML structure verified

### Secondary (MEDIUM confidence)
- GitHub API `https://api.github.com/repos/redcanaryco/atomic-red-team/contents/atomics` — ~330 total entries in atomics directory (includes Indexes subdir)
- Invoke-AtomicRedTeam wiki `https://github.com/redcanaryco/invoke-atomicredteam/wiki` — standard command format `Invoke-AtomicTest T1059.001 -TestNumbers 1`

### Tertiary (LOW confidence)
- Total test count estimate (~1000+) derived from 330 directories × average ~3 tests each — actual count determined when bundle is generated

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new dependencies, all patterns from existing codebase
- Architecture: HIGH — direct clone of Phase 39 CARStore pattern, verified against live code
- ART YAML structure: HIGH — verified against live raw GitHub source (T1059.001.yaml)
- Pitfalls: HIGH — derived from codebase patterns and direct YAML inspection
- Test count estimate: LOW — approximate, verified by running bundle generator

**Research date:** 2026-04-12
**Valid until:** 2026-05-12 (ART catalog grows slowly; patterns are internal codebase-stable)
