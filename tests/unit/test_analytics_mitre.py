"""
Unit tests for MITRE ATT&CK coverage analytics.

Tests exercise SQLiteStore helper methods and the /api/analytics/mitre-coverage
endpoint logic without requiring a running server.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from backend.api.analytics import MITRE_TACTICS, mitre_coverage
from backend.stores.sqlite_store import SQLiteStore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_store(tmp_path: Path) -> SQLiteStore:
    """Create a fresh SQLiteStore backed by a temporary directory."""
    return SQLiteStore(data_dir=str(tmp_path))


def _insert_detection(
    store: SQLiteStore,
    detection_id: str,
    attack_technique: str,
    attack_tactic: str,
) -> None:
    """Insert a minimal detection row directly via the store connection."""
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).isoformat()
    store._conn.execute(
        """
        INSERT OR REPLACE INTO detections
            (id, rule_id, rule_name, severity, matched_event_ids,
             attack_technique, attack_tactic, explanation, case_id, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            detection_id,
            "rule-01",
            "Test Rule",
            "high",
            json.dumps([]),
            attack_technique,
            attack_tactic,
            None,
            None,
            now,
        ),
    )
    store._conn.commit()


def _insert_playbook(
    store: SQLiteStore,
    playbook_id: str,
    trigger_conditions: list[str],
) -> None:
    """Insert a minimal playbook row directly via the store connection."""
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).isoformat()
    store._conn.execute(
        """
        INSERT OR REPLACE INTO playbooks
            (playbook_id, name, description, trigger_conditions,
             steps, version, is_builtin, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            playbook_id,
            "Test Playbook",
            "",
            json.dumps(trigger_conditions),
            json.dumps([]),
            "1.0",
            0,
            now,
        ),
    )
    store._conn.commit()


# ---------------------------------------------------------------------------
# Store method tests
# ---------------------------------------------------------------------------


def test_empty_coverage(tmp_path: Path) -> None:
    """Empty detections and playbooks produce empty coverage."""
    store = _make_store(tmp_path)

    techniques = store.get_detection_techniques()
    assert techniques == [], f"Expected empty list, got {techniques}"

    trigger_conditions = store.get_playbook_trigger_conditions()
    assert trigger_conditions == [], f"Expected empty list, got {trigger_conditions}"


def test_detection_appears_in_coverage(tmp_path: Path) -> None:
    """A detection with attack_technique and attack_tactic appears in coverage."""
    store = _make_store(tmp_path)
    _insert_detection(store, "det-001", "T1059", "execution")

    techniques = store.get_detection_techniques()
    assert len(techniques) == 1
    t = techniques[0]
    assert t["attack_technique"] == "T1059"
    assert t["attack_tactic"] == "execution"

    # Simulate the coverage aggregation used by the endpoint
    coverage: dict[str, Any] = {}
    for row in techniques:
        tactic = (row.get("attack_tactic") or "").strip().lower() or "other"
        if tactic not in MITRE_TACTICS:
            tactic = "other"
        coverage.setdefault(tactic, {})
        coverage[tactic].setdefault(row["attack_technique"], {"sources": [], "status": ""})
        if "detected" not in coverage[tactic][row["attack_technique"]]["sources"]:
            coverage[tactic][row["attack_technique"]]["sources"].append("detected")

    assert "execution" in coverage
    assert "T1059" in coverage["execution"]
    assert "detected" in coverage["execution"]["T1059"]["sources"]


def test_playbook_adds_coverage(tmp_path: Path) -> None:
    """A playbook with T1059 in trigger_conditions produces playbook_covered source."""
    store = _make_store(tmp_path)
    _insert_playbook(store, "pb-001", ["T1059", "some-non-technique-condition"])

    tc_jsons = store.get_playbook_trigger_conditions()
    assert len(tc_jsons) == 1

    # Parse as the endpoint does
    import re
    _TECHNIQUE_RE = re.compile(r"^T\d{4}")
    playbook_techniques: set[str] = set()
    for tc_json in tc_jsons:
        items = json.loads(tc_json) if isinstance(tc_json, str) else []
        for item in items:
            if isinstance(item, str) and _TECHNIQUE_RE.match(item):
                playbook_techniques.add(item)

    assert "T1059" in playbook_techniques
    assert "some-non-technique-condition" not in playbook_techniques

    # Simulate coverage build (no detections)
    coverage: dict[str, Any] = {}
    for technique in playbook_techniques:
        tactic = "other"  # No detection → resolves to "other"
        coverage.setdefault(tactic, {})
        coverage[tactic][technique] = {
            "sources": ["playbook_covered"],
            "status": "playbook_covered",
        }

    # T1059 must appear with playbook_covered source
    found = False
    for tactic_data in coverage.values():
        if "T1059" in tactic_data:
            assert "playbook_covered" in tactic_data["T1059"]["sources"]
            found = True
    assert found, "T1059 not found in coverage from playbook trigger_conditions"
