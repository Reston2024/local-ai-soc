# Phase 48: Hayabusa EVTX Threat Hunting Integration - Research

**Researched:** 2026-04-14
**Domain:** Hayabusa CLI integration, Windows EVTX threat hunting, DuckDB/SQLite detection schema extension, Svelte 5 frontend badge/filter patterns
**Confidence:** HIGH (CLI behavior), HIGH (codebase schema), MEDIUM (exact JSON field names — verified via multiple sources but not run live)

---

## Summary

Hayabusa is a Rust-based, Sigma-rule-backed EVTX threat hunting binary by Yamato-Security. It ships its own 4,000+ rule corpus targeting Windows event logs, runs as a native Windows executable with no Python runtime dependency, and emits JSONL output via the `json-timeline` subcommand. Phase 48 wires Hayabusa into the existing EVTX ingest pipeline: immediately after `EvtxParser` finishes (inside `IngestionLoader.ingest_file`), a new `HayabusaScanner` service calls `hayabusa.exe json-timeline` as a subprocess, parses the JSONL output, maps findings to `DetectionRecord` objects, and persists them in the existing SQLite `detections` table with a new `detection_source = 'hayabusa'` column. A deduplification table (`hayabusa_scanned_files`) prevents re-scanning. DetectionsView gains a HAYABUSA chip filter alongside the existing CORR / ANOMALY / SIGMA chips.

**Primary recommendation:** Run Hayabusa synchronously at ingest time (not as a scheduled job) using `asyncio.to_thread(subprocess.run, ...)` to keep the ingest pipeline single-pass and avoid a separate scheduler. Gate execution on binary availability so the rest of ingest is unaffected if Hayabusa is absent.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `subprocess` (stdlib) | Python 3.12 built-in | Launch hayabusa.exe as child process | No deps; asyncio.to_thread wraps blocking call |
| `json` (stdlib) | Python 3.12 built-in | Parse JSONL lines from stdout/output file | Built-in, zero overhead |
| `pathlib.Path` (stdlib) | Python 3.12 built-in | Temp output file management | Already used throughout codebase |
| `tempfile` (stdlib) | Python 3.12 built-in | Write hayabusa output to temp file | Safer than stdout pipe for large EVTX |
| `shutil.which` (stdlib) | Python 3.12 built-in | Detect hayabusa.exe on PATH at startup | Zero-dep binary discovery |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Hayabusa binary | v2.x (2.18+ preferred) | The actual scanner | Must be on PATH as `hayabusa.exe` |
| pydantic (existing) | Already pinned in project | Validate/deserialize hayabusa records | Use existing `DetectionRecord` model |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Temp file output | stdout pipe via asyncio subprocess | Pipe is more memory-efficient but hayabusa buffers its own stdout; temp file is simpler and avoids large-buffer issues on Windows |
| Ingest-time (sync) | Scheduled background job (APScheduler) | Background job adds dependency and complexity; ingest-time is simpler and keeps findings immediately available |
| SQLite `hayabusa_scanned_files` table | DuckDB flag column on ingest_provenance | SQLite is already used for detections and provenance; keeps hayabusa state consistent with detection layer |

**Installation:** No Python installation needed. Hayabusa is a standalone Windows binary. User must download `hayabusa-x.y.z-win-x64.exe`, rename to `hayabusa.exe`, and place on PATH.

---

## Architecture Patterns

### Recommended Project Structure
```
ingestion/
  hayabusa_scanner.py   # new: HayabusaScanner service
backend/
  stores/
    sqlite_store.py     # add: hayabusa_scanned_files table + migration
  models/
    event.py            # unchanged (DetectionRecord already sufficient)
  api/
    detect.py           # unchanged (detections query already works)
dashboard/src/
  views/
    DetectionsView.svelte  # add: HAYABUSA chip + badge
  lib/
    api.ts              # add: detection_source field to Detection interface
```

### Pattern 1: Subprocess Invocation with Temp File Output

**What:** Run `hayabusa.exe json-timeline` as a subprocess, writing JSONL to a temp file. Read and parse the temp file after the process completes.

**When to use:** Any time an EVTX file is ingested. Gate on `shutil.which("hayabusa")` returning non-None.

**Example:**
```python
# ingestion/hayabusa_scanner.py
import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Iterator

HAYABUSA_BIN = shutil.which("hayabusa") or shutil.which("hayabusa.exe")

def scan_evtx(evtx_path: str) -> Iterator[dict]:
    """Run hayabusa against one EVTX file; yield parsed JSONL records."""
    if not HAYABUSA_BIN:
        return  # binary not available — silent skip

    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        cmd = [
            HAYABUSA_BIN,
            "json-timeline",
            "-f", evtx_path,        # single file
            "-L",                   # JSONL output (not JSON array)
            "-o", tmp_path,         # write to temp file
            "-w",                   # --no-wizard (suppress interactive prompts)
            "-q",                   # --quiet (suppress banner)
            "-C",                   # --clobber (overwrite temp file if exists)
            "--min-level", "low",   # capture low+ severity (skip informational noise)
        ]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,            # 5-minute ceiling per file
        )
        if result.returncode not in (0, 1):
            # Exit code 1 = no detections found (normal); 0 = found detections
            # Any other code = error
            return

        out_path = Path(tmp_path)
        if not out_path.exists():
            return

        for line in out_path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if line:
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    pass
    finally:
        Path(tmp_path).unlink(missing_ok=True)
```

### Pattern 2: JSONL Record to DetectionRecord Mapping

**What:** Map Hayabusa's JSONL fields to the existing `DetectionRecord` / `insert_detection` schema.

**Hayabusa JSONL fields (verified via official docs and ElasticStack integration guide):**

| Hayabusa Field | Type | Maps To |
|----------------|------|---------|
| `Timestamp` | str ISO-8601 | `created_at` (informational, not stored separately) |
| `Computer` | str | logged but not in DetectionRecord |
| `Channel` | str | stored in `explanation` context |
| `EventID` | int | stored in `explanation` context |
| `Level` | str: `crit`/`high`/`med`/`low`/`info` | `severity` (needs normalization) |
| `RuleTitle` | str | `rule_name` |
| `RuleFile` | str | `rule_id` (use filename as stable ID, or hash it) |
| `MitreTactics` | list[str] | `attack_tactic` (join first element) |
| `MitreTags` | list[str] | `attack_technique` (first `T####` entry) |
| `OtherTags` | list[str] | ignore or append to explanation |
| `Details` | dict | serialize key fields into `explanation` |
| `EvtxFile` | str | confirm matches source evtx_path |

**Level normalization:**
```python
_LEVEL_MAP = {
    "crit": "critical",
    "high": "high",
    "med": "medium",
    "medium": "medium",
    "low": "low",
    "info": "informational",
}
```

**Example mapping function:**
```python
from uuid import uuid4
from backend.models.event import DetectionRecord

def hayabusa_record_to_detection(
    rec: dict,
    evtx_path: str,
    case_id: str | None = None,
) -> DetectionRecord:
    level_raw = (rec.get("Level") or "med").lower()
    severity = _LEVEL_MAP.get(level_raw, "medium")

    mitre_tags = rec.get("MitreTags") or []
    attack_technique = next(
        (t for t in mitre_tags if t.upper().startswith("T") and len(t) >= 5),
        None,
    )
    mitre_tactics = rec.get("MitreTactics") or []
    attack_tactic = mitre_tactics[0] if mitre_tactics else None

    details = rec.get("Details") or {}
    detail_str = " | ".join(f"{k}={v}" for k, v in details.items() if v)
    rule_title = rec.get("RuleTitle", "Hayabusa Detection")
    explanation = f"[Hayabusa] {rule_title}: {detail_str}" if detail_str else f"[Hayabusa] {rule_title}"

    # Use RuleFile as a stable rule_id; prefix with "hayabusa-" to avoid collision
    rule_file = rec.get("RuleFile", "unknown")
    rule_id = f"hayabusa-{rule_file}"

    return DetectionRecord(
        id=str(uuid4()),
        rule_id=rule_id,
        rule_name=rule_title,
        severity=severity,
        matched_event_ids=[],   # hayabusa doesn't emit our event_ids
        attack_technique=attack_technique,
        attack_tactic=attack_tactic,
        explanation=explanation,
        case_id=case_id,
    )
```

**NOTE on `matched_event_ids`:** Hayabusa produces its own timeline; it does not reference our DuckDB `event_id` UUIDs. Leave `matched_event_ids` as `[]` for Hayabusa detections. This is acceptable — the detection is sourced independently from the rule corpus, not from our normalized events.

### Pattern 3: Detection Source Column (Migration)

**What:** Add `detection_source TEXT DEFAULT 'sigma'` column to the `detections` table. Use the established `ALTER TABLE ... ADD COLUMN` idempotent migration pattern used in phases 35–43.

**Where:** `backend/stores/sqlite_store.py` — in the `_run_migrations()` method.

```python
# Phase 48 migration — detection_source to distinguish Hayabusa vs Sigma vs Correlation
try:
    self._conn.execute(
        "ALTER TABLE detections ADD COLUMN detection_source TEXT DEFAULT 'sigma'"
    )
    self._conn.commit()
except Exception:
    pass  # column already exists — idempotent
```

Then in `insert_detection`, add `detection_source` to the INSERT statement.

### Pattern 4: Hayabusa-Scanned Files Deduplication

**What:** Track which EVTX files have already been scanned by Hayabusa using a SQLite table.

```sql
CREATE TABLE IF NOT EXISTS hayabusa_scanned_files (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    file_sha256  TEXT NOT NULL UNIQUE,
    file_path    TEXT NOT NULL,
    scanned_at   TEXT NOT NULL,
    findings     INTEGER NOT NULL DEFAULT 0
);
```

**Lookup before scanning:**
```python
def is_already_scanned(self, raw_sha256: str) -> bool:
    row = self._conn.execute(
        "SELECT 1 FROM hayabusa_scanned_files WHERE file_sha256 = ?",
        (raw_sha256,),
    ).fetchone()
    return row is not None

def mark_scanned(self, raw_sha256: str, file_path: str, findings: int) -> None:
    self._conn.execute(
        "INSERT OR IGNORE INTO hayabusa_scanned_files "
        "(file_sha256, file_path, scanned_at, findings) VALUES (?, ?, ?, ?)",
        (raw_sha256, file_path, _now_iso(), findings),
    )
    self._conn.commit()
```

The `raw_sha256` is already computed by `IngestionLoader.ingest_file()` before calling the parser. Pass it through to `HayabusaScanner`.

### Pattern 5: IngestionLoader Integration

**What:** Call HayabusaScanner after the existing EVTX parse step, only for `.evtx` files.

**Where in loader.py:** After the `asyncio.to_thread(self._ingest_events, ...)` call, before returning the result.

```python
# ingestion/loader.py — inside ingest_file(), after existing parse block
if Path(file_path).suffix.lower() == ".evtx":
    hayabusa_count = await asyncio.to_thread(
        _run_hayabusa_scan,
        file_path,
        raw_sha256,
        case_id,
        self._stores,
    )
    result.hayabusa_findings = hayabusa_count
```

`_run_hayabusa_scan` is a sync function (run in thread) that:
1. Checks `sqlite_store.is_already_scanned(raw_sha256)` — skip if True
2. Calls `scan_evtx(evtx_path)` generator
3. Maps each record to `DetectionRecord`
4. Calls `sqlite_store.insert_detection(...)` with `detection_source='hayabusa'`
5. Calls `sqlite_store.mark_scanned(raw_sha256, file_path, count)`

### Pattern 6: Frontend DetectionsView Filter Chip

**What:** Add a HAYABUSA chip to the existing type-filter chip bar.

**Current filter logic (DetectionsView.svelte):**
- `CORR`: `d.rule_id?.startsWith('corr-')`
- `ANOMALY`: `d.rule_id?.startsWith('anomaly-')`
- `SIGMA`: not corr- and not anomaly-

**New logic:** Add `detection_source` field to `Detection` interface and use it for filtering.

```typescript
// api.ts — add to Detection interface
detection_source?: string | null  // 'sigma' | 'hayabusa' | 'correlation' | null
```

```typescript
// DetectionsView.svelte — add HAYABUSA chip
let hayabusaCount = $derived(
  detections.filter(d => d.detection_source === 'hayabusa').length
)

// In displayDetections derived:
: typeFilter === 'HAYABUSA'
  ? detections.filter(d => d.detection_source === 'hayabusa')
```

**Badge:** Use a distinct color (e.g., amber/orange) for Hayabusa detections since they represent a pre-built rule corpus distinct from our custom Sigma rules.

### Anti-Patterns to Avoid

- **Piping hayabusa stdout directly:** On Windows with large EVTX files, stdout buffering can deadlock. Write to a temp file instead.
- **Sharing `asyncio.subprocess.create_subprocess_exec` across threads:** Use blocking `subprocess.run` inside `asyncio.to_thread()` — consistent with CLAUDE.md's blocking I/O pattern.
- **Using DuckDB for hayabusa scan tracking:** Keep detection-layer state in SQLite, consistent with existing detections/provenance tables.
- **Modifying `matched_event_ids` to include non-existent event IDs:** Hayabusa detections won't have corresponding DuckDB event_ids; leave the list empty rather than fabricating IDs.
- **Running Hayabusa before checking binary availability:** Always guard with `shutil.which("hayabusa")` and gracefully skip if not found.
- **Blocking the event loop:** `subprocess.run` is blocking — MUST be wrapped in `asyncio.to_thread()`.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Windows event log Sigma matching | Custom EVTX Sigma engine | Hayabusa binary | Hayabusa has 4,000+ tuned rules; hand-rolling would take months |
| MITRE ATT&CK technique extraction | Custom tag parser | Hayabusa's `MitreTags` field | Already normalized in output |
| EVTX threat timeline | Custom timeline builder | Hayabusa `json-timeline` output | Hayabusa's timeline is the point of this phase |
| Binary process management | Custom process pool | `subprocess.run` + `asyncio.to_thread` | Standard Python pattern, already used in project |
| Detection type routing | Custom detection type system | `detection_source` column | Simple string column is sufficient |

**Key insight:** The entire value of Hayabusa is the pre-built rule corpus. Resist any temptation to re-parse Hayabusa's JSONL into NormalizedEvents — Hayabusa detections are a separate finding type, not a second ingest pass.

---

## Common Pitfalls

### Pitfall 1: Hayabusa Wizard Interactive Prompts Block Subprocess
**What goes wrong:** `hayabusa json-timeline` shows an interactive scan wizard by default (asking which rule set to enable). The subprocess hangs waiting for stdin input that never comes.
**Why it happens:** Hayabusa added the wizard in v2.x for UX; it defaults to interactive unless suppressed.
**How to avoid:** Always pass `-w` (`--no-wizard`) flag. Also pass `-q` (`--quiet`) to suppress the banner.
**Warning signs:** `subprocess.run` never returns; no JSONL output file is created.

### Pitfall 2: Non-Zero Exit Code on No Detections
**What goes wrong:** Hayabusa exits with code 1 when no detections are found, which looks like an error.
**Why it happens:** Exit code 1 = "no detections" (not an error); exit code 0 = "detections found".
**How to avoid:** Accept exit codes 0 and 1 as success. Only raise on 2+.
**Warning signs:** All scans appear to fail even on clean EVTX files.

### Pitfall 3: Temp File Left on Disk After Exception
**What goes wrong:** If the subprocess throws or the parser crashes mid-stream, the temp JSONL file is never deleted.
**Why it happens:** `tempfile.NamedTemporaryFile(delete=False)` requires explicit cleanup.
**How to avoid:** Always use `try/finally` to unlink the temp file. See Pattern 1 code above.
**Warning signs:** Temp directory fills up with `.jsonl` files.

### Pitfall 4: `insert_detection` Missing `detection_source` Parameter
**What goes wrong:** After the SQLite schema migration, calling the old `insert_detection` signature without `detection_source` leaves all Hayabusa detections as `'sigma'` (the DEFAULT).
**Why it happens:** The existing `insert_detection` method doesn't have a `detection_source` parameter.
**How to avoid:** Add `detection_source: str = 'sigma'` parameter to `insert_detection` and update the INSERT SQL.
**Warning signs:** Frontend HAYABUSA filter chip shows 0 detections even after a Hayabusa scan.

### Pitfall 5: Hayabusa Scans the Same File Repeatedly
**What goes wrong:** Every time an already-ingested EVTX file is re-uploaded (or the app restarts and re-scans), Hayabusa runs again, creating duplicate detections.
**Why it happens:** No deduplication exists by default.
**How to avoid:** The `hayabusa_scanned_files` table keyed on `file_sha256` prevents re-scanning. The SHA-256 is already computed in `ingest_file()`.
**Warning signs:** Detection count doubles after re-ingest.

### Pitfall 6: JSONL MitreTags May Contain Non-Technique Strings
**What goes wrong:** `MitreTags` can contain Group IDs (G####) or Software IDs (S####) alongside Technique IDs (T####).
**Why it happens:** Hayabusa includes all Sigma tag types in this field.
**How to avoid:** Filter `MitreTags` for entries starting with `T` and length >= 5 when extracting `attack_technique`. Ignore G#### and S#### entries.
**Warning signs:** `attack_technique = "G0016"` appearing in detections.

### Pitfall 7: `typeFilter === 'SIGMA'` Catches Hayabusa Detections
**What goes wrong:** The existing SIGMA chip filter uses a negative condition (`not corr- and not anomaly-`). After Phase 48, Hayabusa detections with `rule_id = 'hayabusa-...'` would also appear under SIGMA.
**Why it happens:** The SIGMA filter is a catch-all for non-CORR, non-ANOMALY detections.
**How to avoid:** Redefine SIGMA filter as `d.detection_source === 'sigma'` (or `d.rule_id` doesn't start with `corr-`, `anomaly-`, or `hayabusa-`). Preferred: use the new `detection_source` field.
**Warning signs:** Hayabusa detections appear in both SIGMA and HAYABUSA filter views.

---

## Code Examples

### Verified Pattern: asyncio.to_thread for blocking subprocess
```python
# Source: CLAUDE.md — "use asyncio.to_thread() for all blocking I/O"
import asyncio, subprocess

async def run_hayabusa_async(cmd: list[str]) -> subprocess.CompletedProcess:
    return await asyncio.to_thread(
        subprocess.run,
        cmd,
        capture_output=True,
        text=True,
        timeout=300,
    )
```

### Verified Pattern: SQLite idempotent migration
```python
# Source: backend/stores/sqlite_store.py — existing Phase 43 migration pattern
try:
    self._conn.execute(
        "ALTER TABLE detections ADD COLUMN detection_source TEXT DEFAULT 'sigma'"
    )
    self._conn.commit()
except Exception:
    pass  # already exists
```

### Verified Pattern: Existing insert_detection call site
```python
# Source: detections/matcher.py save_detections()
self.stores.sqlite.insert_detection(
    detection_id=det.id,
    rule_id=det.rule_id or "",
    rule_name=det.rule_name or "",
    severity=det.severity,
    matched_event_ids=det.matched_event_ids,
    attack_technique=det.attack_technique,
    attack_tactic=det.attack_tactic,
    explanation=det.explanation,
    case_id=det.case_id,
    # Phase 48: add detection_source="hayabusa"
)
```

### Verified Pattern: Svelte 5 derived filter chip
```typescript
// Source: DetectionsView.svelte — existing corrCount/$derived pattern
let hayabusaCount = $derived(
  detections.filter(d => d.detection_source === 'hayabusa').length
)
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Manual Sigma field mapping (our custom matcher.py) | Hayabusa pre-built 4,000+ rule corpus | Phase 48 | Detection surface expands massively for Windows EVTX |
| EVTX-only ingest (event storage) | EVTX ingest + Hayabusa rule execution | Phase 48 | Same file produces both NormalizedEvents and threat findings |
| Detection type implicit (rule_id prefix) | Detection type explicit (detection_source column) | Phase 48 | Frontend filter by source becomes authoritative |

**Deprecated/outdated:**
- The `typeFilter === 'SIGMA'` catch-all negative filter: Replaced by explicit `detection_source === 'sigma'` after Phase 48 introduces a second non-Sigma, non-CORR, non-ANOMALY source.

---

## Open Questions

1. **Hayabusa binary path on this machine**
   - What we know: Must be on PATH as `hayabusa` or `hayabusa.exe`; `shutil.which()` handles discovery
   - What's unclear: Whether the user has already installed it at a known path
   - Recommendation: Document the setup step; implement graceful skip if not found; log a startup warning

2. **Hayabusa rule corpus location**
   - What we know: Hayabusa bundles rules inside its binary (embedded) or downloads them via `hayabusa update-rules`
   - What's unclear: Whether the rules directory is at a known relative path or embedded
   - Recommendation: Use bundled rules (no `--rules-dir` flag needed for default behavior); document `hayabusa update-rules` as an optional step

3. **Performance on large EVTX files**
   - What we know: Hayabusa is Rust-based and fast; the 5-minute timeout should be adequate
   - What's unclear: Whether 100MB+ Security.evtx files cause issues in the 300s timeout window
   - Recommendation: Make timeout configurable via `settings`; start at 300s

4. **`--min-level` flag behavior on older Hayabusa versions**
   - What we know: `--min-level low` is documented in v2.x
   - What's unclear: Whether v2.6–v2.17 uses `low` vs `informational` as the lowest level string
   - Recommendation: Default to `--min-level medium` to reduce noise; make it a `settings` variable

---

## Validation Architecture

`nyquist_validation: true` in `.planning/config.json` — section required.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (uv run pytest) |
| Config file | pyproject.toml (pytest-asyncio mode: auto) |
| Quick run command | `uv run pytest tests/unit/test_hayabusa_scanner.py -x` |
| Full suite command | `uv run pytest tests/unit/ -x` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| HAY-01 | JSONL record maps to DetectionRecord correctly | unit | `uv run pytest tests/unit/test_hayabusa_scanner.py::test_record_mapping -x` | Wave 0 |
| HAY-02 | Level normalization (crit/high/med/low/info → schema values) | unit | `uv run pytest tests/unit/test_hayabusa_scanner.py::test_level_normalization -x` | Wave 0 |
| HAY-03 | MitreTags filters out non-T#### entries | unit | `uv run pytest tests/unit/test_hayabusa_scanner.py::test_mitre_tag_filter -x` | Wave 0 |
| HAY-04 | Binary absent → scan_evtx yields nothing (no crash) | unit | `uv run pytest tests/unit/test_hayabusa_scanner.py::test_no_binary -x` | Wave 0 |
| HAY-05 | Already-scanned file (by SHA-256) is skipped | unit | `uv run pytest tests/unit/test_hayabusa_scanner.py::test_dedup_skip -x` | Wave 0 |
| HAY-06 | detection_source migration is idempotent | unit | `uv run pytest tests/unit/test_hayabusa_scanner.py::test_migration_idempotent -x` | Wave 0 |
| HAY-07 | DetectionsView HAYABUSA chip filters by detection_source | manual | Open UI, check chip shows count and filters | N/A |
| HAY-08 | Hayabusa scanner runs end-to-end with real binary + sample EVTX | integration | `uv run pytest tests/integration/test_hayabusa_e2e.py -x -m "hayabusa"` | Wave 0 (skipped if binary absent) |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/unit/test_hayabusa_scanner.py -x`
- **Per wave merge:** `uv run pytest tests/unit/ -x`
- **Phase gate:** Full unit suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/unit/test_hayabusa_scanner.py` — covers HAY-01 through HAY-06
- [ ] `tests/integration/test_hayabusa_e2e.py` — covers HAY-08 (pytest.mark.hayabusa; skipped if `shutil.which("hayabusa")` is None)

---

## Codebase-Specific Integration Notes

These are findings from reading the actual source — critical for the planner.

### DetectionRecord model has no `detection_source` field
`backend/models/event.py` `DetectionRecord` does not have a `detection_source` field. The field only needs to exist in SQLite. No model change is needed — the source is passed as a parameter to `insert_detection`, not carried in the Pydantic model.

### `insert_detection` currently accepts `entity_key` but not `detection_source`
The method signature in `sqlite_store.py` line 774 must be extended with `detection_source: str = 'sigma'`. The INSERT SQL must include the new column.

### Existing `detection_source` in `NormalizedEvent` is separate
`NormalizedEvent` has a `detection_source` field (position [23] in `to_duckdb_row`) that refers to how the event was sourced (e.g., from IOC matching). This is stored in `normalized_events` (DuckDB), not `detections` (SQLite). No collision — same name, different table, different meaning. Planner should note this clearly in task descriptions to avoid confusion.

### SHA-256 is already computed in `ingest_file()`
`IngestionLoader.ingest_file()` computes `raw_sha256 = await asyncio.to_thread(_sha256_file, file_path)` before parsing. This value should be passed to `HayabusaScanner.scan()` to avoid computing it twice.

### `SIGMA` chip in DetectionsView uses negative filter — must be updated
Current line 49: `detections.filter(d => !d.rule_id?.startsWith('corr-') && !d.rule_id?.startsWith('anomaly-'))`. After Phase 48, add `&& !d.rule_id?.startsWith('hayabusa-')` or preferably switch to `d.detection_source === 'sigma'`.

### `ingest_provenance` table already tracks files by SHA-256
The `ingest_provenance` table (SQLite) records `raw_sha256` and `source_file`. However, it is keyed by `prov_id` (UUID), not by `raw_sha256` alone. Querying it for "has this SHA been scanned by Hayabusa?" requires an additional column or a separate table. Use the separate `hayabusa_scanned_files` table (Pattern 4) for clarity.

---

## Sources

### Primary (HIGH confidence)
- Hayabusa GitHub Wiki — Usage Examples: https://github.com/Yamato-Security/hayabusa/wiki/Usage-Examples
- Hayabusa GitHub Wiki — Running Hayabusa: https://github.com/Yamato-Security/hayabusa/wiki/Running-Hayabusa
- Hayabusa ElasticStack import doc (field names): https://github.com/Yamato-Security/hayabusa/blob/main/doc/ElasticStackImport/ElasticStackImport-English.md
- Hayabusa AnalysisWithJQ doc (field structure): https://github.com/Yamato-Security/hayabusa/blob/main/doc/AnalysisWithJQ-English.md
- Project codebase: `detections/matcher.py`, `backend/stores/sqlite_store.py`, `ingestion/loader.py`, `backend/models/event.py`, `dashboard/src/views/DetectionsView.svelte`, `dashboard/src/lib/api.ts` (read directly)

### Secondary (MEDIUM confidence)
- Black Hills InfoSec Hayabusa walkthrough: https://www.blackhillsinfosec.com/wrangling-windows-event-logs-with-hayabusa-sof-elk-part-1/
- MitreTags/MitreTactics/OtherTags field names confirmed by multiple web sources but not verified against a live binary output

### Tertiary (LOW confidence)
- Exit code 1 = "no detections" behavior: mentioned in community sources but not confirmed in official changelog; validate by running `hayabusa json-timeline` on a clean EVTX

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — stdlib subprocess, asyncio.to_thread, tempfile are project-standard patterns
- CLI flags (-w, -q, -L, -o, -f): HIGH — confirmed via official wiki
- JSONL field names (RuleTitle, Level, Computer, MitreTactics, MitreTags): MEDIUM — confirmed via multiple authoritative secondary sources (ElasticStack doc, JQ analysis doc)
- Exit code behavior: LOW — community-sourced, validate with live binary
- Architecture patterns: HIGH — derived from reading actual codebase
- Frontend patterns: HIGH — derived from reading actual DetectionsView.svelte

**Research date:** 2026-04-14
**Valid until:** 2026-05-14 (Hayabusa releases frequently; re-verify CLI flags if binary version changes significantly)
