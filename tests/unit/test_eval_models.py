"""
Tests for scripts/eval_models.py — EvalResult schema, score_response(),
and dry-run row generation behaviour.
"""

import asyncio
import pytest

try:
    from scripts.eval_models import EvalResult, score_response, _eval_one_row
except ImportError:
    EvalResult = None  # type: ignore
    score_response = None  # type: ignore
    _eval_one_row = None  # type: ignore


# ---------------------------------------------------------------------------
# EvalResult schema
# ---------------------------------------------------------------------------


def test_eval_result_fields():
    """EvalResult has all required fields with correct types."""
    assert EvalResult is not None, "scripts.eval_models not implemented yet"
    r = EvalResult(
        model="qwen3:14b",
        prompt_id="row-1-triage",
        prompt_type="triage",
        latency_ms=100,
        eval_count=50,
        keyword_recall=0.8,
        timestamp="2026-01-01T00:00:00Z",
    )
    assert r.model == "qwen3:14b"
    assert r.prompt_id == "row-1-triage"
    assert r.prompt_type == "triage"
    assert isinstance(r.latency_ms, int)
    assert isinstance(r.eval_count, int)
    assert isinstance(r.keyword_recall, float)
    assert 0.0 <= r.keyword_recall <= 1.0
    assert isinstance(r.timestamp, str)
    # Verify ISO-8601 shape (contains 'T' and 'Z')
    assert "T" in r.timestamp and r.timestamp.endswith("Z")


# ---------------------------------------------------------------------------
# score_response — return type and range
# ---------------------------------------------------------------------------


def test_score_response_returns_float_in_range():
    """score_response returns a float between 0.0 and 1.0."""
    assert score_response is not None, "scripts.eval_models not implemented yet"
    result = score_response("The host was compromised via RDP brute force.", ["RDP", "brute force"])
    assert isinstance(result, float)
    assert 0.0 <= result <= 1.0


def test_score_response_empty_keywords_returns_one():
    """Empty keyword list yields 1.0 — no penalty for no ground truth."""
    assert score_response is not None, "scripts.eval_models not implemented yet"
    result = score_response("Any response text here.", [])
    assert result == 1.0


def test_score_response_all_keywords_present_returns_one():
    """When all keywords appear in response, recall is 1.0."""
    assert score_response is not None, "scripts.eval_models not implemented yet"
    result = score_response("lateral movement via pass-the-hash credential theft", ["lateral movement", "pass-the-hash"])
    assert result == 1.0


def test_score_response_no_keywords_present_returns_zero():
    """When no keywords appear in response, recall is 0.0."""
    assert score_response is not None, "scripts.eval_models not implemented yet"
    result = score_response("The weather is sunny today.", ["ransomware", "exfiltration", "C2"])
    assert result == 0.0


def test_score_response_case_insensitive():
    """score_response matching is case-insensitive."""
    assert score_response is not None, "scripts.eval_models not implemented yet"
    # Keyword in uppercase, response in lowercase — should still match
    result = score_response("ransomware detected on workstation.", ["RANSOMWARE"])
    assert result == 1.0


# ---------------------------------------------------------------------------
# EvalResult prompt_type values
# ---------------------------------------------------------------------------


def test_eval_result_prompt_type_triage():
    """EvalResult accepts prompt_type='triage'."""
    assert EvalResult is not None, "scripts.eval_models not implemented yet"
    r = EvalResult(
        model="x",
        prompt_id="row-0-triage",
        prompt_type="triage",
        latency_ms=50,
        eval_count=10,
        keyword_recall=1.0,
        timestamp="2026-01-01T00:00:00Z",
    )
    assert r.prompt_type == "triage"


def test_eval_result_prompt_type_summarise():
    """EvalResult accepts prompt_type='summarise'."""
    assert EvalResult is not None, "scripts.eval_models not implemented yet"
    r = EvalResult(
        model="x",
        prompt_id="row-0-summarise",
        prompt_type="summarise",
        latency_ms=40,
        eval_count=8,
        keyword_recall=0.9,
        timestamp="2026-01-01T00:00:00Z",
    )
    assert r.prompt_type == "summarise"


# ---------------------------------------------------------------------------
# _eval_one_row dry-run mode (no DuckDB, no HTTP)
# ---------------------------------------------------------------------------


def test_eval_one_row_dry_run_returns_eval_result():
    """_eval_one_row in dry-run mode returns EvalResult without making HTTP calls."""
    assert _eval_one_row is not None, "scripts.eval_models not implemented yet"
    assert EvalResult is not None, "scripts.eval_models not implemented yet"

    dry_run_row = (
        "dry-run-id",
        "process_create",
        "WORKSTATION-01",
        "cmd.exe",
        "cmd.exe /c whoami",
        "high",
        "T1059",
    )

    result = asyncio.run(
        _eval_one_row(
            row=dry_run_row,
            model="qwen3:14b",
            prompt_type="triage",
            row_idx=0,
            ollama_base_url="http://localhost:11434",
            dry_run=True,
        )
    )

    assert isinstance(result, EvalResult)
    assert result.model == "qwen3:14b"
    assert result.prompt_type == "triage"
    assert result.latency_ms == 0
    assert result.eval_count == 0
    assert result.keyword_recall == 1.0
    assert "T" in result.timestamp and result.timestamp.endswith("Z")


def test_eval_one_row_dry_run_summarise():
    """_eval_one_row in dry-run mode works for summarise prompt_type."""
    assert _eval_one_row is not None, "scripts.eval_models not implemented yet"
    assert EvalResult is not None, "scripts.eval_models not implemented yet"

    dry_run_row = (
        "dry-run-id",
        "process_create",
        "WORKSTATION-01",
        "cmd.exe",
        "cmd.exe /c whoami",
        "high",
        "T1059",
    )

    result = asyncio.run(
        _eval_one_row(
            row=dry_run_row,
            model="foundation-sec:8b",
            prompt_type="summarise",
            row_idx=2,
            ollama_base_url="http://localhost:11434",
            dry_run=True,
        )
    )

    assert isinstance(result, EvalResult)
    assert result.prompt_id == "row-2-summarise"
    assert result.latency_ms == 0
    assert result.keyword_recall == 1.0
