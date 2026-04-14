"""
Hayabusa EVTX threat hunting scanner integration.

Runs Hayabusa (https://github.com/Yamato-Security/hayabusa) against EVTX files
and maps its JSONL output to DetectionRecord objects for insertion into SQLite.

Phase 48: HAY-01..HAY-04 behaviour.
"""
from __future__ import annotations

import json
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

HAYABUSA_BIN: str | None = (
    shutil.which("hayabusa")
    or shutil.which("hayabusa.exe")
    or (r"C:\Tools\hayabusa\hayabusa.exe" if Path(r"C:\Tools\hayabusa\hayabusa.exe").exists() else None)
)

_LEVEL_MAP: dict[str, str] = {
    "crit": "critical",
    "high": "high",
    "med": "medium",
    "medium": "medium",
    "low": "low",
    "info": "informational",
}

if not HAYABUSA_BIN:
    log.warning("hayabusa binary not found on PATH — Hayabusa EVTX scanning disabled")


# ---------------------------------------------------------------------------
# Core generator
# ---------------------------------------------------------------------------

def scan_evtx(evtx_path: str) -> Iterator[dict]:
    """
    Run Hayabusa against a single EVTX file and yield parsed JSONL records.

    When HAYABUSA_BIN is None the generator yields nothing (no exception).
    Accepts Hayabusa exit codes 0 and 1 as success; all others → silent skip.
    Cleans up the temporary output file in a finally block.

    Args:
        evtx_path: Absolute path to the .evtx file to scan.

    Yields:
        dict: Parsed Hayabusa JSONL record.
    """
    if not HAYABUSA_BIN:
        return

    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".jsonl")
    import os
    os.close(tmp_fd)  # close file descriptor; Hayabusa will write the file

    try:
        cmd = [
            HAYABUSA_BIN,
            "json-timeline",
            "-f", evtx_path,
            "-L",
            "-o", tmp_path,
            "-w",
            "-q",
            "-C",
            "--min-level", "medium",
            "--profile", "verbose",   # includes MitreTactics, MitreTags, RuleFile, EvtxFile
        ]
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
        )

        if proc.returncode not in (0, 1):
            log.warning(
                "Hayabusa returned unexpected exit code — skipping",
                evtx_path=evtx_path,
                returncode=proc.returncode,
            )
            return

        tmp = Path(tmp_path)
        if not tmp.exists() or tmp.stat().st_size == 0:
            return

        with tmp.open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue

    finally:
        Path(tmp_path).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Record mapper
# ---------------------------------------------------------------------------

def hayabusa_record_to_detection(
    rec: dict,
    evtx_path: str,
    case_id: str | None = None,
) -> DetectionRecord:
    """
    Map a single Hayabusa JSONL record to a DetectionRecord.

    Field mapping:
    - rule_id     = "hayabusa-{RuleFile}"
    - rule_name   = RuleTitle
    - severity    = _LEVEL_MAP[Level] (default "medium")
    - attack_technique = first MitreTags entry starting with "T" and len >= 5
    - attack_tactic    = first MitreTactics entry
    - explanation      = "[Hayabusa] {RuleTitle}: {Details k=v ...}" or "[Hayabusa] {RuleTitle}"
    - matched_event_ids = [] (Hayabusa does not emit event IDs in the same format)

    Args:
        rec:       Parsed Hayabusa JSONL dict.
        evtx_path: Source EVTX file path (unused in mapping, available for callers).
        case_id:   Optional case to attach this detection to.

    Returns:
        DetectionRecord ready for SQLiteStore.insert_detection().
    """
    level_raw = (rec.get("Level") or "med").lower()
    severity = _LEVEL_MAP.get(level_raw, "medium")

    mitre_tags: list[str] = rec.get("MitreTags") or []
    attack_technique: str | None = next(
        (t for t in mitre_tags if t.upper().startswith("T") and len(t) >= 5),
        None,
    )

    mitre_tactics: list[str] = rec.get("MitreTactics") or []
    attack_tactic: str | None = mitre_tactics[0] if mitre_tactics else None

    details: dict = rec.get("Details") or {}
    detail_str = " | ".join(f"{k}={v}" for k, v in details.items() if v)

    rule_title: str = rec.get("RuleTitle") or "Hayabusa Detection"
    explanation = (
        f"[Hayabusa] {rule_title}: {detail_str}"
        if detail_str
        else f"[Hayabusa] {rule_title}"
    )

    # RuleID is the stable sigma UUID; RuleFile is the .yml filename — prefer RuleID
    rule_id_raw: str = rec.get("RuleID") or rec.get("RuleFile") or "unknown"
    rule_id = f"hayabusa-{rule_id_raw}"

    return DetectionRecord(
        id=str(uuid4()),
        rule_id=rule_id,
        rule_name=rule_title,
        severity=severity,
        matched_event_ids=[],
        attack_technique=attack_technique,
        attack_tactic=attack_tactic,
        explanation=explanation,
        case_id=case_id,
    )
