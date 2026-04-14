# Phase 49: Chainsaw Windows Event Log Analysis - Research

**Researched:** 2026-04-14
**Domain:** Chainsaw CLI integration, EVTX threat hunting, cross-tool deduplication, SQLite detection schema, Svelte 5 frontend filter patterns
**Confidence:** HIGH (codebase patterns — directly mirrors Phase 48), MEDIUM (Chainsaw JSON schema — verified via multiple integration sources but not run live), HIGH (installation — confirmed from releases page)

---

## Summary

Chainsaw (WithSecureLabs, Rust-based, v2.14.1 as of February 2025) is a complementary EVTX threat hunting binary that runs Sigma rules and its own native TOML-based "Chainsaw rules" against Windows event logs. Where Hayabusa (Phase 48) excels at timeline generation with pre-mapped MITRE tagging, Chainsaw's strengths are MFT/EVTX/journal parsing, lateral movement pattern detection, and antivirus alert extraction through its native rules format. Running both tools against the same EVTX provides near-complete coverage of Windows attacker TTPs.

The implementation directly mirrors Phase 48: a new `ingestion/chainsaw_scanner.py` follows the same subprocess + temp-file + generator + mapper pattern as `hayabusa_scanner.py`. Key differences are: (1) the CLI command is `hunt` (not `json-timeline`), (2) the JSON output schema is different — Chainsaw emits top-level `name`, `level`, `status`, `group`, `tags`, `timestamp`, `document` fields rather than Hayabusa's flat JSONL record, (3) deduplication uses a separate `chainsaw_scanned_files` SQLite table (same SHA-256 pattern, separate tool namespace), and (4) MITRE ATT&CK tags arrive in a `tags` list as `"attack.tXXXX"` strings requiring extraction.

**Primary recommendation:** Follow the Phase 48 pattern exactly. Create `ingestion/chainsaw_scanner.py` with `CHAINSAW_BIN`, `scan_evtx()` generator, and `chainsaw_record_to_detection()` mapper. Wire into `loader.py` inside a non-fatal `try/except` block after the Hayabusa block. Add `chainsaw_scanned_files` SQLite table. Add CHAINSAW chip to DetectionsView matching the HAYABUSA amber chip pattern.

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| CHA-01 | Chainsaw binary integration — scan_evtx() generator yields parsed JSON records from `chainsaw hunt --json` subprocess | subprocess + tempfile pattern from Phase 48; confirmed `hunt` subcommand + `--json` flag from official docs |
| CHA-02 | chainsaw_record_to_detection() maps Chainsaw JSON fields (name, level, tags, id) to DetectionRecord | JSON schema confirmed from Velociraptor integration + Wazuh integration docs |
| CHA-03 | SHA-256 file-level dedup via chainsaw_scanned_files SQLite table | Direct mirror of hayabusa_scanned_files DDL + is_already_scanned/mark_scanned pattern |
| CHA-04 | Non-fatal wiring in loader.py ingest_file() after Hayabusa block | Pattern established in Phase 48; loader.py structure confirmed |
| CHA-05 | detection_source='chainsaw' on all inserted detections | insert_detection() already accepts detection_source param; confirmed from Phase 48 |
| CHA-06 | CHAINSAW chip filter in DetectionsView matching HAYABUSA chip pattern | Phase 48 DetectionsView chip pattern confirmed from STATE.md key decisions |
| CHA-07 | chainsaw_findings: int field on IngestionResult dataclass | hayabusa_findings field pattern from loader.py confirmed |
</phase_requirements>

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `subprocess` (stdlib) | Python 3.12 built-in | Launch chainsaw.exe as child process | Identical pattern to Phase 48 hayabusa_scanner.py |
| `json` (stdlib) | Python 3.12 built-in | Parse JSON output file | Built-in, no overhead |
| `pathlib.Path` (stdlib) | Python 3.12 built-in | Temp output file path management | Used throughout codebase |
| `tempfile` (stdlib) | Python 3.12 built-in | Write chainsaw JSON output to temp file | Avoids stdout buffering issues on Windows |
| `shutil.which` (stdlib) | Python 3.12 built-in | Detect chainsaw.exe on PATH at startup | Zero-dep binary discovery; check both `chainsaw` and `chainsaw.exe` |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Chainsaw binary | v2.14.1 (latest Feb 2025) | The actual scanner | Must be at `C:\Tools\chainsaw\chainsaw.exe` or on PATH |
| Sigma rules | SigmaHQ/sigma (separate clone) | Detection rules for Chainsaw | Required alongside mapping file |
| Chainsaw mapping | `mappings/sigma-event-logs-all.yml` | Field translation for Sigma rules | Ships inside chainsaw_all_platforms zip |
| Chainsaw native rules | `rules/` directory | Built-in TOML-format rules | Ships inside chainsaw_all_platforms zip |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Separate `chainsaw_scanned_files` table | Shared `evtx_scanned_files` table with `tool` column | Shared table with `tool` column is cleaner long-term but requires migrating existing Hayabusa table; separate table mirrors Phase 48 exactly with zero migration risk |
| File-level SHA-256 dedup | Event-record-level dedup (evtx_file + record_id + rule_id) | Record-level would prevent a Hayabusa+Chainsaw match on the same event from creating two SQLite rows — but adds query complexity and requires parsing event_id from Chainsaw output which is buried in `document.data.Event.System.EventRecordID` |
| Ingest-time scan | Background scheduled scan | Ingest-time is simpler; keeps findings immediately available alongside Hayabusa results |

**Installation:**
```
# Download from: https://github.com/WithSecureLabs/chainsaw/releases
# Package: chainsaw_all_platforms+rules+examples.zip
# Extract to: C:\Tools\chainsaw\
# Result:
#   C:\Tools\chainsaw\chainsaw.exe
#   C:\Tools\chainsaw\rules\              (native Chainsaw TOML rules)
#   C:\Tools\chainsaw\mappings\           (sigma field mapping files)
#   C:\Tools\chainsaw\sigma\              (SigmaHQ rules — may need separate clone)
```

---

## Architecture Patterns

### Recommended Project Structure
```
ingestion/
  chainsaw_scanner.py      # new: mirrors hayabusa_scanner.py exactly
  hayabusa_scanner.py      # existing — Phase 48

backend/
  stores/
    sqlite_store.py        # add: _CHAINSAW_DDL + chainsaw_scanned_files table
                           # add: is_chainsaw_scanned() + mark_chainsaw_scanned()
  models/
    event.py               # unchanged — DetectionRecord is sufficient

dashboard/src/
  views/
    DetectionsView.svelte  # add: CHAINSAW chip (teal/cyan) + chainsawCount $derived
  lib/
    api.ts                 # Detection interface already has detection_source (Phase 48)

ingestion/
  loader.py                # add: chainsaw_findings to IngestionResult
                           # add: _run_chainsaw_scan() helper
                           # add: non-fatal chainsaw block after hayabusa block
```

### Pattern 1: Chainsaw Hunt Subprocess (mirrors Phase 48 exactly)

**What:** Run `chainsaw hunt <evtx_path> -s <sigma_dir> --mapping <mapping_yml> -r <rules_dir> --json -o <tmp_file> -q` as a subprocess, parse the JSON array output file after completion.

**When to use:** On every EVTX file ingestion, after Hayabusa scan, gated on `CHAINSAW_BIN` being non-None.

**Key difference from Hayabusa:** Chainsaw writes a JSON **array** (not JSONL) when using `--json -o <file>`. The output is a single `[{...}, {...}]` file, not newline-delimited records. Parse with `json.load()` not line-by-line.

**Example:**
```python
# ingestion/chainsaw_scanner.py
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Iterator
from uuid import uuid4

from backend.core.logging import get_logger
from backend.models.event import DetectionRecord

log = get_logger(__name__)

# Binary discovery — check PATH first, then well-known install location
CHAINSAW_BIN: str | None = (
    shutil.which("chainsaw")
    or shutil.which("chainsaw.exe")
    or (r"C:\Tools\chainsaw\chainsaw.exe"
        if Path(r"C:\Tools\chainsaw\chainsaw.exe").exists() else None)
)

# Rules and mapping paths relative to binary location
_CHAINSAW_DIR: Path | None = (
    Path(CHAINSAW_BIN).parent if CHAINSAW_BIN else None
)
_SIGMA_DIR: str | None = (
    str(_CHAINSAW_DIR / "sigma") if _CHAINSAW_DIR and (_CHAINSAW_DIR / "sigma").exists() else None
)
_RULES_DIR: str | None = (
    str(_CHAINSAW_DIR / "rules") if _CHAINSAW_DIR and (_CHAINSAW_DIR / "rules").exists() else None
)
_MAPPING_FILE: str | None = (
    str(_CHAINSAW_DIR / "mappings" / "sigma-event-logs-all.yml")
    if _CHAINSAW_DIR and (_CHAINSAW_DIR / "mappings" / "sigma-event-logs-all.yml").exists()
    else None
)

_LEVEL_MAP: dict[str, str] = {
    "critical": "critical",
    "high": "high",
    "medium": "medium",
    "low": "low",
    "informational": "informational",
    "info": "informational",
}

if not CHAINSAW_BIN:
    log.warning("chainsaw binary not found on PATH — Chainsaw EVTX scanning disabled")


def scan_evtx(evtx_path: str) -> Iterator[dict]:
    """Run Chainsaw hunt against one EVTX file. Yields parsed JSON records."""
    if not CHAINSAW_BIN:
        return

    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".json")
    os.close(tmp_fd)

    try:
        cmd = [CHAINSAW_BIN, "hunt", evtx_path]
        if _SIGMA_DIR:
            cmd += ["-s", _SIGMA_DIR]
        if _MAPPING_FILE:
            cmd += ["--mapping", _MAPPING_FILE]
        if _RULES_DIR:
            cmd += ["-r", _RULES_DIR]
        cmd += ["--json", "-o", tmp_path, "-q"]

        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

        if proc.returncode not in (0, 1):
            log.warning("Chainsaw returned unexpected exit code",
                        evtx_path=evtx_path, returncode=proc.returncode)
            return

        tmp = Path(tmp_path)
        if not tmp.exists() or tmp.stat().st_size == 0:
            return

        with tmp.open("r", encoding="utf-8", errors="replace") as fh:
            try:
                records = json.load(fh)  # JSON array, not JSONL
                if isinstance(records, list):
                    yield from records
            except json.JSONDecodeError:
                pass
    finally:
        Path(tmp_path).unlink(missing_ok=True)
```

### Pattern 2: Chainsaw JSON Record → DetectionRecord Mapping

**What:** Map Chainsaw's nested JSON structure to `DetectionRecord`. The key difference from Hayabusa: MITRE techniques are in the `tags` list as `"attack.tXXXX"` strings.

**Chainsaw JSON record schema (confirmed from Velociraptor + Wazuh integrations):**
```json
{
  "group": "Sigma",
  "kind": "individual",
  "name": "Mimikatz Detection",
  "level": "high",
  "status": "experimental",
  "timestamp": "2023-01-15T10:23:45Z",
  "authors": ["Florian Roth"],
  "tags": ["attack.credential_access", "attack.t1003"],
  "document": {
    "kind": "evtx",
    "data": {
      "Event": {
        "System": {
          "EventID": 4688,
          "EventRecordID": 12345,
          "Computer": "WORKSTATION-01",
          "Channel": "Security"
        },
        "EventData": {
          "CommandLine": "mimikatz.exe sekurlsa::logonpasswords",
          "NewProcessName": "C:\\temp\\mimikatz.exe"
        }
      }
    }
  }
}
```

**Field mapping:**
```python
def chainsaw_record_to_detection(
    rec: dict,
    evtx_path: str,
    case_id: str | None = None,
) -> DetectionRecord:
    """Map a Chainsaw JSON hunt record to DetectionRecord."""
    level_raw = (rec.get("level") or "medium").lower()
    severity = _LEVEL_MAP.get(level_raw, "medium")

    # MITRE techniques: tags list contains "attack.tXXXX" entries
    tags: list[str] = rec.get("tags") or []
    attack_technique: str | None = next(
        (t.split(".")[-1].upper()
         for t in tags
         if t.lower().startswith("attack.t") and len(t) >= 10),
        None,
    )

    # MITRE tactic: tags list also contains "attack.<tactic_name>" entries
    _KNOWN_TACTICS = {
        "initial_access", "execution", "persistence", "privilege_escalation",
        "defense_evasion", "credential_access", "discovery", "lateral_movement",
        "collection", "command_and_control", "exfiltration", "impact",
        "reconnaissance", "resource_development",
    }
    attack_tactic: str | None = next(
        (t.split("attack.")[-1].replace("_", " ").title()
         for t in tags
         if t.lower().startswith("attack.")
         and t.lower().split("attack.")[-1] in _KNOWN_TACTICS),
        None,
    )

    rule_name: str = rec.get("name") or "Chainsaw Detection"
    rule_id_raw: str = rec.get("id") or rec.get("name") or "unknown"
    rule_id = f"chainsaw-{rule_id_raw}"

    # Extract EventRecordID for cross-tool dedup potential
    try:
        event_record_id = str(
            rec["document"]["data"]["Event"]["System"]["EventRecordID"]
        )
        matched_ids = [event_record_id]
    except (KeyError, TypeError):
        matched_ids = []

    explanation = f"[Chainsaw] {rule_name} (level={level_raw}, status={rec.get('status', 'unknown')})"

    return DetectionRecord(
        id=str(uuid4()),
        rule_id=rule_id,
        rule_name=rule_name,
        severity=severity,
        matched_event_ids=matched_ids,
        attack_technique=attack_technique,
        attack_tactic=attack_tactic,
        explanation=explanation,
        case_id=case_id,
    )
```

### Pattern 3: SQLite Dedup Table (mirrors hayabusa_scanned_files)

**What:** Add `chainsaw_scanned_files` table to SQLite store using identical DDL to `hayabusa_scanned_files`. Add `is_chainsaw_scanned()` and `mark_chainsaw_scanned()` methods.

**DDL:**
```sql
CREATE TABLE IF NOT EXISTS chainsaw_scanned_files (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    file_sha256 TEXT NOT NULL UNIQUE,
    file_path   TEXT NOT NULL,
    scanned_at  TEXT NOT NULL,
    findings    INTEGER NOT NULL DEFAULT 0
);
```

**Note:** Both tools use file-level SHA-256 dedup. A file scanned by Hayabusa is NOT automatically skipped by Chainsaw — each tool has its own namespace. This is intentional: both tools may produce detections for the same EVTX file, but from different rules.

### Pattern 4: loader.py Non-Fatal Integration Block

**What:** Add Chainsaw block immediately after the Hayabusa block in `ingest_file()`. Follows exact same structure: `asyncio.to_thread(_run_chainsaw_scan, ...)` wrapped in `try/except`.

```python
# loader.py — after Phase 48 Hayabusa block
# Phase 49: Chainsaw EVTX threat hunting (non-fatal — failure must not abort pipeline)
if _Path(file_path).suffix.lower() == ".evtx":
    try:
        result.chainsaw_findings = await asyncio.to_thread(
            _run_chainsaw_scan, file_path, raw_sha256, case_id, self._stores
        )
    except Exception as exc:
        log.warning(
            "Chainsaw scan failed (non-fatal)", file_path=file_path, error=str(exc)
        )
```

### Pattern 5: IngestionResult Extension

```python
@dataclass
class IngestionResult:
    # ... existing fields ...
    hayabusa_findings: int = 0  # Phase 48
    chainsaw_findings: int = 0  # Phase 49
```

### Anti-Patterns to Avoid

- **Parsing Chainsaw output as JSONL:** Chainsaw's `--json -o <file>` produces a JSON **array**, not newline-delimited JSONL. Use `json.load()` not line-by-line iteration.
- **Assuming sigma rules are bundled:** Starting with Chainsaw v2, Sigma rules are no longer git submodules. The `chainsaw_all_platforms+rules+examples.zip` bundles them, but the rules directory must be verified at runtime. Use `_SIGMA_DIR` with `.exists()` guard.
- **Hardcoding the mapping file path:** The mapping path must be resolved relative to the binary directory at module load time, not hardcoded. Different installation layouts exist.
- **Cross-tool dedup at record level on insertion:** Don't try to suppress duplicate detections at insert time based on EventRecordID. Each tool has complementary rule coverage and the same underlying event generating both a Hayabusa and a Chainsaw detection is valuable (two independent corroborating signals). Frontend filtering by `detection_source` lets the analyst manage this.
- **Using `--no-progress` flag:** Chainsaw uses `-q` for quiet/suppress progress. The flag is `-q` not `--no-progress` (unlike some tools).

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| EVTX parsing | Custom Python EVTX parser | Chainsaw binary | EVTX format is complex binary; Chainsaw uses battle-tested `evtx` Rust crate |
| Sigma rule matching | Custom Python Sigma engine | Chainsaw + SigmaHQ rules | TAU engine inside Chainsaw handles field mapping, condition logic, aggregation |
| MITRE technique lookup | Hardcoded technique dictionary | Parse `tags` list from Chainsaw output | Chainsaw inherits MITRE mappings from Sigma rules |
| Field mapping | Custom EVTX field normalizer | `mappings/sigma-event-logs-all.yml` | WithSecure maintains this mapping for all Windows event log channels |

**Key insight:** Chainsaw is the parsing engine. The integration layer's job is only: invoke binary, parse JSON array, map to DetectionRecord, dedup, insert. No custom forensics logic needed.

---

## Common Pitfalls

### Pitfall 1: Missing Rules/Mapping Directory
**What goes wrong:** `chainsaw hunt` exits with code 1 and no output if no `-s`, `--mapping`, or `-r` flags are provided, or if the paths don't exist.
**Why it happens:** Chainsaw requires at least one rule source to produce detections.
**How to avoid:** Resolve `_SIGMA_DIR`, `_RULES_DIR`, `_MAPPING_FILE` at module load time via `Path.exists()` checks. If all are None, log a warning and return early from `scan_evtx()`.
**Warning signs:** Chainsaw returns exit code 1 with empty output file — distinguish from "no detections found" (also exit code 1 with empty output). Both are safe to treat as zero-findings.

### Pitfall 2: JSON Array vs JSONL Format
**What goes wrong:** Code iterates line-by-line expecting JSONL, but Chainsaw writes a JSON array `[{...}]`. The first line is `[` and fails `json.loads()`.
**Why it happens:** Different design choice from Hayabusa (which uses JSONL for streaming-friendly output).
**How to avoid:** Use `json.load(fh)` after confirming file is non-empty. Wrap in try/except JSONDecodeError.
**Warning signs:** Zero records parsed despite non-empty output file.

### Pitfall 3: MITRE Tags Not Prefixed Consistently
**What goes wrong:** Tags like `"attack.t1003.001"` need technique extraction as `"T1003.001"` (uppercase T). Some Sigma rules use `"attack.t1003"` (no sub-technique).
**Why it happens:** Chainsaw inherits Sigma rule tag format verbatim.
**How to avoid:** In `chainsaw_record_to_detection()`, split on `.` and take last component, then uppercase and prepend `T`. Filter by `len >= 4` (T + at least 3 digits).
**Warning signs:** `attack_technique` is None for records that clearly have ATT&CK tags.

### Pitfall 4: Chainsaw Exit Code 1 on No Matches
**What goes wrong:** Treating exit code 1 as an error and logging spurious warnings on clean EVTX files.
**Why it happens:** Chainsaw returns exit code 1 both for errors AND for "no detections found." Same behavior as Hayabusa.
**How to avoid:** Accept exit codes 0 and 1 as success, distinguish by checking output file size.

### Pitfall 5: Windows Path Quoting in Subprocess
**What goes wrong:** Paths with spaces (e.g., `C:\Users\Admin\My Events\test.evtx`) cause subprocess argument parsing errors on Windows.
**Why it happens:** Windows subprocess with `shell=False` and list args handles spaces correctly, but mixing string vs list invocation does not.
**How to avoid:** Always use list form `cmd = [CHAINSAW_BIN, "hunt", evtx_path, ...]` not string form. Never use `shell=True`.

### Pitfall 6: Frontend Filter Name Collision
**What goes wrong:** The CHAINSAW chip filter CSS class conflicts with HAYABUSA if using shared `badge-tool` class.
**Why it happens:** Phase 48 added `badge-hayabusa` class specifically to avoid cascade issues.
**How to avoid:** Use `badge-chainsaw` CSS class with distinct teal/cyan color. Mirror Phase 48's `detection_source === 'chainsaw'` comparison (not prefix-based).

---

## Code Examples

Verified patterns from Phase 48 (direct template) and Chainsaw documentation:

### Binary Discovery (mirrors Phase 48 exactly)
```python
# Source: Phase 48 hayabusa_scanner.py + shutil.which docs
CHAINSAW_BIN: str | None = (
    shutil.which("chainsaw")
    or shutil.which("chainsaw.exe")
    or (r"C:\Tools\chainsaw\chainsaw.exe"
        if Path(r"C:\Tools\chainsaw\chainsaw.exe").exists() else None)
)
```

### MITRE Technique Extraction from Tags
```python
# Chainsaw tags: ["attack.credential_access", "attack.t1003", "attack.t1003.001"]
# Source: Wazuh+Chainsaw integration (SOCFortress) + vanimpe.eu analysis
tags: list[str] = rec.get("tags") or []
attack_technique: str | None = next(
    (t.split(".")[-1].upper()   # "t1003.001" -> "T1003.001"
     for t in tags
     if t.lower().startswith("attack.t") and len(t.split(".")[-1]) >= 4),
    None,
)
```

### Chainsaw Hunt Command Construction
```python
# Source: Velociraptor Windows.EventLogs.Chainsaw artifact + WithSecure docs
cmd = [CHAINSAW_BIN, "hunt", evtx_path]
if _SIGMA_DIR:
    cmd += ["-s", _SIGMA_DIR]
if _MAPPING_FILE:
    cmd += ["--mapping", _MAPPING_FILE]
if _RULES_DIR:
    cmd += ["-r", _RULES_DIR]
cmd += ["--json", "-o", tmp_path, "-q"]
```

### SQLiteStore Chainsaw Methods (mirrors Phase 48)
```python
# Source: Phase 48 sqlite_store.py hayabusa_scanned_files pattern
def is_chainsaw_scanned(self, file_sha256: str) -> bool:
    row = self._conn.execute(
        "SELECT 1 FROM chainsaw_scanned_files WHERE file_sha256 = ?",
        (file_sha256,),
    ).fetchone()
    return row is not None

def mark_chainsaw_scanned(self, file_sha256: str, file_path: str, findings: int) -> None:
    self._conn.execute(
        "INSERT OR IGNORE INTO chainsaw_scanned_files "
        "(file_sha256, file_path, scanned_at, findings) VALUES (?, ?, ?, ?)",
        (file_sha256, file_path, _now_iso(), findings),
    )
    self._conn.commit()
```

### Frontend CHAINSAW Chip (mirrors Phase 48 HAYABUSA chip)
```svelte
<!-- Source: Phase 48 DetectionsView.svelte pattern (STATE.md 48-03 key decision) -->
<!-- detection_source === 'chainsaw' direct comparison (not prefix-based) -->
let chainsawCount = $derived(
  detections.filter(d => d.detection_source === 'chainsaw').length
);

<!-- Chip in filter bar alongside HAYABUSA chip -->
<button
  class="chip {typeFilter === 'chainsaw' ? 'active' : ''}"
  onclick={() => typeFilter = typeFilter === 'chainsaw' ? 'all' : 'chainsaw'}
>
  CHAINSAW ({chainsawCount})
</button>

<!-- Badge on detection row -->
{#if det.detection_source === 'chainsaw'}
  <span class="badge-chainsaw">CHAINSAW</span>
{/if}
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Chainsaw v1 (stdout JSONL) | Chainsaw v2 (JSON array file via `-o`) | v2.0 release | Output parsing changed from JSONL to JSON array |
| Sigma rules as git submodules | Separate clone required | Chainsaw v2 | Installation must account for rules being in separate directory |
| No quiet flag | `-q` suppresses progress bars | v2.x | Required for subprocess invocation to prevent stdout pollution |
| `--no-target-file-exists` flag | Automatic detection | v2.x | Chainsaw handles missing EVTX gracefully without special flags |

**Deprecated/outdated:**
- Chainsaw v1 `--stdout` flag: removed in v2; use `--json -o <file>` instead
- Chainsaw submodule sigma rules: no longer maintained as submodules; must download separately or use bundled zip

---

## Cross-Tool Deduplication Design

This is the most complex decision for Phase 49. Two strategies:

### Strategy A: File-Level Dedup Only (RECOMMENDED)
Each tool has its own `_scanned_files` table. Both tools can scan the same EVTX file and both can insert detections. A Hayabusa + Chainsaw match on the same underlying event creates two SQLite detection rows with `detection_source='hayabusa'` and `detection_source='chainsaw'` respectively.

**Pros:** Simple, mirrors Phase 48 exactly, preserves corroborating signals (two tools independently flagging the same event is HIGH confidence).
**Cons:** DetectionsView shows "duplicate" entries for the same event.
**Mitigation:** CHAINSAW chip filter lets analyst view only Chainsaw-unique findings.

### Strategy B: Rule-Level Dedup (future enhancement, NOT Phase 49)
Query existing detections before inserting: if `(rule_id LIKE 'hayabusa-%' OR rule_id LIKE 'chainsaw-%')` AND `EventRecordID` matches an existing detection's `matched_event_ids`, skip. Requires joining on JSON-serialized `matched_event_ids` field which is costly.

**Decision:** Use Strategy A (file-level dedup only) for Phase 49. Strategy B is a DEFERRED enhancement that can be added in a future cleanup phase.

---

## Open Questions

1. **Chainsaw rules directory detection at runtime**
   - What we know: `chainsaw_all_platforms+rules+examples.zip` bundles rules in `rules/` and `sigma/` subdirectories relative to the binary
   - What's unclear: Some installations may have custom layouts; sigma rules may be separately cloned to a different path
   - Recommendation: Resolve all paths relative to `CHAINSAW_BIN`'s parent directory at module load. Log a warning (not error) for each missing component. Scanner still runs with whatever subset is available.

2. **Chainsaw output file naming with `--output` flag**
   - What we know: v2.3.0 release notes mention "Output file name for JSON based output" as a feature
   - What's unclear: Whether `--output` specifies file or directory; whether `-o` is the short form
   - Recommendation: Use `tempfile.mkstemp(suffix=".json")` for temp file path and pass to `--output` flag. If Chainsaw creates the file in a directory, adjust to pass the full temp file path.

3. **MITRE tactic tag format**
   - What we know: Tags include `"attack.credential_access"`, `"attack.lateral_movement"` etc.
   - What's unclear: Whether all Sigma rules consistently include tactic tags or only technique tags
   - Recommendation: Extract tactic from tags list using known tactic name set. Fall back to None if not found. This is the same defensive approach as Hayabusa's `_TACTIC_EXPAND` dict.

---

## Validation Architecture

nyquist_validation is enabled in `.planning/config.json`.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (auto mode, pyproject.toml) |
| Config file | `pyproject.toml` (existing) |
| Quick run command | `uv run pytest tests/unit/test_chainsaw_scanner.py -x -q` |
| Full suite command | `uv run pytest tests/unit/ -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CHA-01 | `scan_evtx()` yields zero records when `CHAINSAW_BIN=None` | unit | `uv run pytest tests/unit/test_chainsaw_scanner.py::test_no_binary -x` | ❌ Wave 0 |
| CHA-02 | `chainsaw_record_to_detection()` maps name/level/tags to DetectionRecord | unit | `uv run pytest tests/unit/test_chainsaw_scanner.py::test_record_mapping -x` | ❌ Wave 0 |
| CHA-02 | `_LEVEL_MAP` maps all level strings correctly | unit | `uv run pytest tests/unit/test_chainsaw_scanner.py::test_level_normalization -x` | ❌ Wave 0 |
| CHA-02 | MITRE technique extracted from `tags` list (attack.tXXXX format) | unit | `uv run pytest tests/unit/test_chainsaw_scanner.py::test_mitre_tag_extraction -x` | ❌ Wave 0 |
| CHA-02 | MITRE tactic extracted from `tags` list (attack.tactic_name format) | unit | `uv run pytest tests/unit/test_chainsaw_scanner.py::test_tactic_extraction -x` | ❌ Wave 0 |
| CHA-03 | `is_chainsaw_scanned()` + `mark_chainsaw_scanned()` dedup logic | unit | `uv run pytest tests/unit/test_chainsaw_scanner.py::test_dedup_skip -x` | ❌ Wave 0 |
| CHA-03 | `chainsaw_scanned_files` table migration idempotence | unit | `uv run pytest tests/unit/test_chainsaw_scanner.py::test_migration_idempotent -x` | ❌ Wave 0 |

**Integration test stub (gated on binary):**
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CHA-01 | `scan_evtx()` against real fixture EVTX produces DetectionRecord objects | integration | `uv run pytest tests/integration/test_chainsaw_e2e.py -m chainsaw -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/unit/test_chainsaw_scanner.py -x -q`
- **Per wave merge:** `uv run pytest tests/unit/ -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/unit/test_chainsaw_scanner.py` — 7 unit stubs covering CHA-01 through CHA-03
- [ ] `tests/integration/test_chainsaw_e2e.py` — 1 integration stub gated on binary (same `chainsaw` marker pattern as Phase 48 `hayabusa` marker)
- [ ] `pyproject.toml` — add `chainsaw` to markers list (mirrors `hayabusa` marker from Phase 48 key decision 48-01)
- [ ] `ingestion/chainsaw_scanner.py` — stub module so `pytest.importorskip("ingestion.chainsaw_scanner")` skips cleanly

**Module-level importorskip pattern** (from Phase 48 key decision 48-01 — entire file skips atomically):
```python
pytest.importorskip(
    "ingestion.chainsaw_scanner",
    reason="Implementation not yet present — will be created in Plan 49-02",
)
```

---

## Sources

### Primary (HIGH confidence)
- Phase 48 `ingestion/hayabusa_scanner.py` — direct template; all structural patterns copied
- Phase 48 `backend/stores/sqlite_store.py` — `_HAYABUSA_DDL`, `is_already_scanned()`, `mark_scanned()` are the exact dedup pattern
- Phase 48 `ingestion/loader.py` — `_run_hayabusa_scan()`, `IngestionResult.hayabusa_findings`, non-fatal block location
- Phase 48 STATE.md key decisions (48-01, 48-02, 48-03) — importorskip pattern, get_logger usage, SIGMA filter compat, badge CSS class naming

### Secondary (MEDIUM confidence)
- [Velociraptor Windows.EventLogs.Chainsaw artifact](https://docs.velociraptor.app/exchange/artifacts/pages/windows.eventlogs.chainsaw/) — confirmed JSON field paths: `name`, `level`, `status`, `group`, `document.data.Event.System.*`, `document.data.Event.EventData.*`
- [WithSecureLabs/chainsaw Wiki — Usage](https://github.com/WithSecureLabs/chainsaw/wiki/Usage) — confirmed `hunt` subcommand, `--json` flag, `-q` quiet flag, `-o` output flag, `-s` sigma path, `--mapping` flag
- [WithSecureLabs/chainsaw README](https://github.com/WithSecureLabs/chainsaw/blob/master/README.md) — confirmed rule types (Sigma YAML + native TOML), bundled zip structure
- [SOCFortress Wazuh+Chainsaw integration](https://socfortress.medium.com/wazuh-and-chainsaw-integration-for-near-real-time-sigma-detection-6f3e729e892) — confirmed JSON field `level`, `name`, `id`, `tags` (attack.tXXXX format), `logsource`
- [Chainsaw v2 Discussion #77](https://github.com/WithSecureLabs/chainsaw/discussions/77) — confirmed `group`, `kind`, `document.kind`, `document.data` top-level fields; confirmed MITRE tags not natively in output (require Sigma rule tag inheritance)
- [Chainsaw releases page](https://github.com/WithSecureLabs/chainsaw/releases) — confirmed v2.14.1 is latest (Feb 2025); `chainsaw_all_platforms+rules+examples.zip` bundle confirmed from v2.3.0 release notes search

### Tertiary (LOW confidence — flag for validation)
- MITRE tactic extraction from tags: inferred from `"attack.lateral_movement"` tag format seen in Wazuh integration; actual tag format per rule varies and must be validated against live output
- Chainsaw exit code behavior (0 = matches, 1 = no matches OR error): inferred from Hayabusa parallel + community articles; validate against actual binary run

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — exact mirror of Phase 48 (stdlib only, no new dependencies)
- Architecture: HIGH — direct template from `hayabusa_scanner.py` with documented differences
- Chainsaw JSON schema: MEDIUM — confirmed from 3+ integration sources (Velociraptor, Wazuh/SOCFortress, vanimpe.eu) but not validated against live binary run
- Pitfalls: HIGH — JSON array vs JSONL, exit code handling, path resolution all confirmed from sources
- MITRE tag extraction: MEDIUM — format inferred from Sigma rule conventions + integration examples

**Research date:** 2026-04-14
**Valid until:** 2026-05-14 (Chainsaw v2.x is stable; low churn risk on JSON schema)
