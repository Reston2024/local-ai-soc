"""Unit tests for backend/api/triage.py — POST /api/triage/run and GET /api/triage/latest.

Tests call _run_triage() and get_triage_latest() directly (not via HTTP) to avoid
FastAPI test client complexity and keep tests fast.
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers — build a minimal fake app.state
# ---------------------------------------------------------------------------

def _make_app(detections: list[dict], latest_triage: dict | None = None):
    """Return a fake ``app`` object that mirrors app.state structure."""
    conn = MagicMock()
    conn.execute.return_value.fetchall.return_value = [
        {
            "id": d["id"],
            "rule_name": d.get("rule_name", "TestRule"),
            "severity": d.get("severity", "high"),
            "attack_technique": d.get("attack_technique", "T1059"),
            "attack_tactic": d.get("attack_tactic", "execution"),
        }
        for d in detections
    ]

    sqlite_mock = MagicMock()
    sqlite_mock._conn = conn
    sqlite_mock.get_latest_triage.return_value = latest_triage

    stores = SimpleNamespace(sqlite=sqlite_mock)

    ollama_mock = AsyncMock()
    ollama_mock.generate = AsyncMock(return_value="CRITICAL: Possible lateral movement detected.\nSee full result.")
    ollama_mock.model = "llama3"

    app = SimpleNamespace(
        state=SimpleNamespace(stores=stores, ollama=ollama_mock),
    )
    return app


# ---------------------------------------------------------------------------
# Test 1: POST /api/triage/run with 2 untriaged detections → 200 with summary
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_triage_run_with_detections():
    """_run_triage returns run_id, detection_count=2, severity_summary, model_name."""
    from backend.api.triage import _run_triage

    detections = [
        {"id": "det-1", "rule_name": "PowerShell Encoded", "severity": "high",
         "attack_technique": "T1059.001", "attack_tactic": "execution"},
        {"id": "det-2", "rule_name": "Suspicious WMI", "severity": "medium",
         "attack_technique": "T1047", "attack_tactic": "execution"},
    ]
    app = _make_app(detections)

    result = await _run_triage(app)

    assert result["run_id"], "run_id must be non-empty"
    assert result["detection_count"] == 2
    assert result["severity_summary"], "severity_summary must be non-empty"
    assert result["model_name"], "model_name must be non-empty"
    assert "created_at" in result


# ---------------------------------------------------------------------------
# Test 2: POST /api/triage/run with no untriaged detections → 200 with message
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_triage_run_no_detections():
    """_run_triage returns detection_count=0 and message when no untriaged."""
    from backend.api.triage import _run_triage

    app = _make_app([])

    result = await _run_triage(app)

    assert result["detection_count"] == 0
    assert result.get("message") == "No untriaged detections"


# ---------------------------------------------------------------------------
# Test 3: GET /api/triage/latest with a result in store → 200, has severity_summary
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_triage_latest_with_result():
    """get_triage_latest returns result row with severity_summary key."""
    from backend.api.triage import get_triage_latest

    stored_result = {
        "run_id": "abc-123",
        "severity_summary": "High priority lateral movement.",
        "result_text": "Full text here.",
        "detection_count": 3,
        "model_name": "llama3",
        "created_at": "2026-04-10T12:00:00+00:00",
    }
    app = _make_app([], latest_triage=stored_result)

    # Build a fake Request object
    request = SimpleNamespace(app=app)

    response = await get_triage_latest(request)
    data = response.body
    import json
    parsed = json.loads(data)

    assert parsed["result"] is not None
    assert "severity_summary" in parsed["result"]


# ---------------------------------------------------------------------------
# Test 4: GET /api/triage/latest with empty store → 200, {"result": null}
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_triage_latest_empty():
    """get_triage_latest returns {result: null} when no triage results exist."""
    from backend.api.triage import get_triage_latest

    app = _make_app([], latest_triage=None)
    request = SimpleNamespace(app=app)

    response = await get_triage_latest(request)
    import json
    parsed = json.loads(response.body)

    assert parsed == {"result": None}
