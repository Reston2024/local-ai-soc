"""
Unit tests for backend/api/report_templates.py — all 6 HTML builder functions.

Wave 0 stubs: tests that require the module are gated by TEMPLATES_AVAILABLE.
Once report_templates.py exists all 7 tests should pass.
"""

from __future__ import annotations

import pytest
from backend.models.report import Report

# ---------------------------------------------------------------------------
# Conditional import — tests are skipped if module not yet created
# ---------------------------------------------------------------------------

try:
    from backend.api.report_templates import (
        _incident_html,
        _pir_html,
        _playbook_log_html,
        _session_log_html,
        _severity_ref_html,
        _ti_bulletin_html,
    )

    TEMPLATES_AVAILABLE = True
except ImportError:
    TEMPLATES_AVAILABLE = False

skip_if_missing = pytest.mark.skipif(
    not TEMPLATES_AVAILABLE, reason="report_templates not yet created"
)

# ---------------------------------------------------------------------------
# Test: Report.type widening (no import of report_templates needed)
# ---------------------------------------------------------------------------


def test_report_type_widening() -> None:
    """Report model accepts all 6 template type strings without ValidationError."""
    template_types = [
        "template_session_log",
        "template_incident",
        "template_playbook_log",
        "template_pir",
        "template_ti_bulletin",
        "template_severity_ref",
    ]
    for t in template_types:
        r = Report(
            id="test-id",
            type=t,
            title="Test",
            content_json="{}",
            created_at="2026-01-01T00:00:00Z",
        )
        assert r.type == t


# ---------------------------------------------------------------------------
# HTML builder tests
# ---------------------------------------------------------------------------


@skip_if_missing
def test_session_log_html_returns_string() -> None:
    html = _session_log_html(
        title="Session Log Test",
        generated_at="2026-01-01T00:00:00Z",
        event_count_24h=5,
        event_type_breakdown=[("alert", 3), ("dns", 2)],
        source_types=[("suricata", 5)],
        detection_count_24h=2,
        latest_triage=None,
        git_hash="abc123",
    )
    assert isinstance(html, str)
    assert "INTERNAL USE ONLY" in html
    assert "Session Log" in html
    assert "Analyst Signature" in html


@skip_if_missing
def test_incident_html_returns_string() -> None:
    html = _incident_html(
        title="Incident Report Test",
        case=None,
        detections=[],
        ioc_hits=[],
        triage=None,
        techniques=[],
    )
    assert isinstance(html, str)
    assert "Incident Report" in html
    assert "INTERNAL USE ONLY" in html


@skip_if_missing
def test_playbook_log_html_returns_string() -> None:
    html = _playbook_log_html(
        title="Playbook Log Test",
        run=None,
        playbook=None,
        case=None,
        triage=None,
    )
    assert isinstance(html, str)
    assert "Playbook" in html
    assert "INTERNAL USE ONLY" in html


@skip_if_missing
def test_pir_html_returns_string() -> None:
    html = _pir_html(
        title="Post-Incident Review Test",
        case=None,
        detections=[],
        techniques=[],
        playbook_runs=[],
        triage=None,
    )
    assert isinstance(html, str)
    assert "Post-Incident" in html
    assert "INTERNAL USE ONLY" in html


@skip_if_missing
def test_ti_bulletin_html_returns_string() -> None:
    html = _ti_bulletin_html(
        title="TI Bulletin Test",
        actor_name="APT28",
        actor_info=None,
        group_techniques=[],
        ioc_rows=[],
        asset_rows=[],
        triage=None,
    )
    assert isinstance(html, str)
    assert "Threat Intelligence" in html
    assert "INTERNAL USE ONLY" in html


@skip_if_missing
def test_severity_ref_html_returns_string() -> None:
    html = _severity_ref_html()
    assert isinstance(html, str)
    assert "Severity" in html
    assert "INTERNAL USE ONLY" in html
