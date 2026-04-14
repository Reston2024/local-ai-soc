"""
Chainsaw EVTX threat hunting scanner integration.

Runs Chainsaw (https://github.com/WithSecureLabs/chainsaw) against EVTX files
and maps its JSON output to DetectionRecord objects for insertion into SQLite.

Phase 49: CHA-01..CHA-03 behaviour.
"""
from __future__ import annotations

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

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

CHAINSAW_BIN: str | None = (
    shutil.which("chainsaw")
    or shutil.which("chainsaw.exe")
    or (r"C:\Tools\chainsaw\chainsaw.exe" if Path(r"C:\Tools\chainsaw\chainsaw.exe").exists() else None)
)

# Resolve paths relative to the binary's parent directory
_CHAINSAW_DIR: Path | None = Path(CHAINSAW_BIN).parent if CHAINSAW_BIN else None

_SIGMA_DIR: str | None = (
    str(_CHAINSAW_DIR / "sigma")
    if _CHAINSAW_DIR and (_CHAINSAW_DIR / "sigma").is_dir()
    else None
)

_RULES_DIR: str | None = (
    str(_CHAINSAW_DIR / "rules")
    if _CHAINSAW_DIR and (_CHAINSAW_DIR / "rules").is_dir()
    else None
)

_MAPPING_FILE: str | None = (
    str(_CHAINSAW_DIR / "mappings" / "sigma-event-logs-all.yml")
    if _CHAINSAW_DIR and (_CHAINSAW_DIR / "mappings" / "sigma-event-logs-all.yml").is_file()
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

# Known MITRE ATT&CK tactic slugs (underscore-separated, from Chainsaw tags)
_KNOWN_TACTICS: set[str] = {
    "initial_access",
    "execution",
    "persistence",
    "privilege_escalation",
    "defense_evasion",
    "credential_access",
    "discovery",
    "lateral_movement",
    "collection",
    "command_and_control",
    "exfiltration",
    "impact",
    "reconnaissance",
    "resource_development",
}

if not CHAINSAW_BIN:
    log.warning("chainsaw binary not found on PATH — Chainsaw EVTX scanning disabled")


# ---------------------------------------------------------------------------
# Core generator
# ---------------------------------------------------------------------------

def scan_evtx(evtx_path: str) -> Iterator[dict]:
    """
    Run Chainsaw against a single EVTX file and yield parsed JSON records.

    When CHAINSAW_BIN is None the generator yields nothing (no exception).
    Accepts Chainsaw exit codes 0 and 1 as success; all others → silent skip.
    Cleans up the temporary output file in a finally block.

    Args:
        evtx_path: Absolute path to the .evtx file to scan.

    Yields:
        dict: Parsed Chainsaw JSON record.
    """
    if not CHAINSAW_BIN:
        return

    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".json")
    os.close(tmp_fd)  # close file descriptor; Chainsaw will write the file

    try:
        # Build command: chainsaw hunt [RULES] [PATH] [options]
        # [RULES] is the first positional arg (the rules directory), then the EVTX path.
        # -s adds sigma rules; --mapping wires sigma field names to Windows event fields.
        cmd: list[str] = [CHAINSAW_BIN, "hunt"]

        if _RULES_DIR:
            cmd.append(_RULES_DIR)   # positional RULES directory (built-in chainsaw rules)

        cmd.append(evtx_path)        # positional PATH (the EVTX file)

        if _SIGMA_DIR:
            cmd += ["-s", _SIGMA_DIR]
        if _MAPPING_FILE:
            cmd += ["--mapping", _MAPPING_FILE]

        cmd += ["--json", "-o", tmp_path, "-q"]

        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
        )

        # Exit code 0 = success with findings; 1 = no matches found — both are normal
        if proc.returncode not in (0, 1):
            log.warning(
                "Chainsaw returned unexpected exit code — skipping",
                evtx_path=evtx_path,
                returncode=proc.returncode,
            )
            return

        tmp = Path(tmp_path)
        if not tmp.exists() or tmp.stat().st_size == 0:
            return

        with tmp.open("r", encoding="utf-8", errors="replace") as fh:
            try:
                records = json.load(fh)  # JSON array, NOT JSONL
            except json.JSONDecodeError:
                log.warning("Chainsaw output JSON parse error", evtx_path=evtx_path)
                return

        if isinstance(records, list):
            yield from records

    finally:
        Path(tmp_path).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Record mapper
# ---------------------------------------------------------------------------

def chainsaw_record_to_detection(
    rec: dict,
    evtx_path: str,
    case_id: str | None = None,
) -> DetectionRecord:
    """
    Map a single Chainsaw JSON record to a DetectionRecord.

    Field mapping:
    - rule_id     = "chainsaw-{id}" (falls back to name or "unknown")
    - rule_name   = name field
    - severity    = _LEVEL_MAP[level] (default "medium")
    - attack_technique = from tags list e.g. "attack.t1003.001" -> "T1003.001"
    - attack_tactic    = from tags list e.g. "attack.credential_access" -> "Credential Access"
    - explanation      = "[Chainsaw] {name} (level={level}, status={status})"
    - matched_event_ids = EventRecordID from document.data.Event.System (if available)

    Args:
        rec:       Parsed Chainsaw JSON dict.
        evtx_path: Source EVTX file path (unused in mapping, available for callers).
        case_id:   Optional case to attach this detection to.

    Returns:
        DetectionRecord ready for SQLiteStore.insert_detection().
    """
    level_raw = (rec.get("level") or "medium").lower()
    severity = _LEVEL_MAP.get(level_raw, "medium")

    tags: list[str] = rec.get("tags") or []

    # Technique: "attack.t1003.001" -> "T1003.001", "attack.t1003" -> "T1003"
    # Find tag starting with "attack.t" where the part after "attack." begins with t####
    def _extract_technique(tag: str) -> str | None:
        lower = tag.lower()
        if not lower.startswith("attack.t"):
            return None
        # Everything after "attack."
        rest = tag[len("attack."):]  # e.g. "t1003" or "t1003.001"
        parts = rest.split(".")
        # First part must be t#### (t + 4 digits)
        if len(parts[0]) >= 5 and parts[0][0].lower() == "t" and parts[0][1:5].isdigit():
            return rest.upper()  # "T1003" or "T1003.001"
        return None

    attack_technique: str | None = next(
        (tech for t in tags for tech in [_extract_technique(t)] if tech is not None),
        None,
    )

    # Tactic: "attack.credential_access" -> "Credential Access"
    attack_tactic: str | None = next(
        (
            t.split("attack.")[-1].replace("_", " ").title()
            for t in tags
            if t.lower().startswith("attack.") and t.lower().split("attack.")[-1] in _KNOWN_TACTICS
        ),
        None,
    )

    # Extract EventRecordID from nested document structure
    matched_ids: list[str] = []
    try:
        event_record_id = rec["document"]["data"]["Event"]["System"]["EventRecordID"]
        matched_ids = [str(event_record_id)]
    except (KeyError, TypeError):
        pass

    rule_id_raw: str = rec.get("id") or rec.get("name") or "unknown"
    rule_id = f"chainsaw-{rule_id_raw}"
    rule_name: str = rec.get("name") or "Chainsaw Detection"

    explanation = (
        f"[Chainsaw] {rule_name} (level={level_raw}, status={rec.get('status', 'unknown')})"
    )

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
