"""
Report Templates API — Phase 37 Analyst Report Templates.

Endpoints:
    GET  /api/reports/template/meta                    — counts + lists for dropdowns
    POST /api/reports/template/session-log             — daily session log report
    POST /api/reports/template/incident/{case_id}      — security incident report
    POST /api/reports/template/playbook-log/{run_id}   — playbook execution log report

HTML builder functions (exported for testing):
    _session_log_html, _incident_html, _playbook_log_html,
    _pir_html, _ti_bulletin_html, _severity_ref_html
"""

from __future__ import annotations

import asyncio
import base64
import json
import subprocess
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.api.reports import _render_pdf, _strip_pdf_b64
from backend.core.logging import get_logger

log = get_logger(__name__)

router = APIRouter(prefix="/api/reports", tags=["report-templates"])

# ---------------------------------------------------------------------------
# CSS / shared style block
# ---------------------------------------------------------------------------

_CSS = """
<style>
  body { font-family: Arial, sans-serif; font-size: 12px; margin: 30px; }
  h1 { color: #1a1a2e; margin-bottom: 4px; }
  h2 { color: #16213e; border-bottom: 1px solid #ccc; padding-bottom: 4px; margin-top: 24px; }
  table { border-collapse: collapse; width: 100%; margin-bottom: 20px; }
  th { background: #16213e; color: #fff; padding: 6px; text-align: left; }
  td { padding: 5px; vertical-align: top; word-break: break-all; }
  tr:nth-child(even) { background: #f2f2f2; }
  .meta { color: #666; font-size: 11px; margin-bottom: 20px; }
  .header-bar { background: #16213e; color: #fff; padding: 16px 24px; margin-bottom: 20px; display: flex; justify-content: space-between; align-items: center; }
  .header-brand { font-size: 18px; font-weight: bold; }
  .classification-badge { background: #c0392b; color: #fff; padding: 4px 10px; font-weight: bold; font-size: 11px; border-radius: 3px; }
  .placeholder { color: #999; font-style: italic; }
  .signature-line { margin-top: 40px; border-top: 1px solid #ccc; padding-top: 16px; }
  pre { white-space: pre-wrap; word-break: break-all; background: #f8f8f8; padding: 8px; font-size: 11px; }
</style>
"""

_HEADER = """
<div class="header-bar">
  <span class="header-brand">AI-SOC-Brain</span>
  <span class="classification-badge">INTERNAL USE ONLY</span>
</div>
"""

_SIGNATURE = """
<div class="signature-line">
  <p>Analyst Signature: _________________&nbsp;&nbsp;&nbsp;&nbsp; Date: _______________</p>
  <p>Reviewer Signature: ________________&nbsp;&nbsp;&nbsp;&nbsp; Date: _______________</p>
</div>
"""


def _html_wrap(title: str, body: str) -> str:
    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8"/>
<title>{title}</title>
{_CSS}
</head>
<body>
{_HEADER}
<h1>{title}</h1>
{body}
{_SIGNATURE}
</body>
</html>"""


def _no_data() -> str:
    return '<p class="placeholder">[No data available — analyst to complete]</p>'


# ---------------------------------------------------------------------------
# HTML builder: Session Log
# ---------------------------------------------------------------------------


def _session_log_html(
    title: str,
    generated_at: str,
    event_count_24h: int,
    event_type_breakdown: list[tuple[str, int]],
    source_types: list[tuple[str, int]],
    detection_count_24h: int,
    latest_triage: dict | None,
    git_hash: str,
) -> str:
    """Build HTML for a daily session log report."""

    # Section 1 — Ingest Summary
    source_rows = "".join(
        f"<tr><td>{st}</td><td>{cnt}</td></tr>"
        for st, cnt in (source_types or [])
    ) or "<tr><td colspan='2'>No source type data</td></tr>"

    s1 = f"""
<h2>1. Ingest Summary</h2>
<table>
  <tr><th>Metric</th><th>Value</th></tr>
  <tr><td>Total Events (last 24 h)</td><td>{event_count_24h:,}</td></tr>
</table>
<h3>Source Types</h3>
<table>
  <thead><tr><th>Source Type</th><th>Count</th></tr></thead>
  <tbody>{source_rows}</tbody>
</table>
"""

    # Section 2 — Detection Summary
    s2 = f"""
<h2>2. Detection Summary</h2>
<table>
  <tr><th>Metric</th><th>Value</th></tr>
  <tr><td>Detections Triggered (last 24 h)</td><td>{detection_count_24h:,}</td></tr>
</table>
"""

    # Section 3 — Event Type Breakdown
    type_rows = "".join(
        f"<tr><td>{et}</td><td>{cnt}</td></tr>"
        for et, cnt in (event_type_breakdown or [])
    ) or "<tr><td colspan='2'>No event type data</td></tr>"

    s3 = f"""
<h2>3. Event Type Breakdown</h2>
<table>
  <thead><tr><th>Event Type</th><th>Count</th></tr></thead>
  <tbody>{type_rows}</tbody>
</table>
"""

    # Section 4 — Latest Triage Result
    if latest_triage:
        triage_body = f"""
<table>
  <tr><th>Field</th><th>Value</th></tr>
  <tr><td>Model</td><td>{latest_triage.get('model_name', '')}</td></tr>
  <tr><td>Severity Summary</td><td>{latest_triage.get('severity_summary', '')}</td></tr>
  <tr><td>Created At</td><td>{latest_triage.get('created_at', '')}</td></tr>
</table>
<p><strong>Result Text:</strong></p>
<pre>{latest_triage.get('result_text', '')}</pre>
"""
    else:
        triage_body = _no_data()

    s4 = f"<h2>4. Latest Triage Result</h2>\n{triage_body}"

    # Section 5 — LLM Inference Audit Trail (Rule 5.3)
    if latest_triage:
        audit_row = (
            f"<tr>"
            f"<td>{latest_triage.get('model_name', '')}</td>"
            f"<td>{latest_triage.get('prompt_version', 'N/A')}</td>"
            f"<td>{latest_triage.get('severity_summary', '')}</td>"
            f"<td style='white-space:pre-wrap;word-break:break-all;'>{latest_triage.get('result_text', '')[:500]}</td>"
            f"<td></td>"
            f"<td></td>"
            f"</tr>"
        )
    else:
        audit_row = "<tr><td colspan='6'>No triage data available</td></tr>"

    s5 = f"""
<h2>5. LLM Inference Audit Trail</h2>
<table>
  <thead>
    <tr><th>Model</th><th>Prompt Version</th><th>Severity Summary</th>
    <th>Result Text</th><th>Confidence</th><th>Disposition</th></tr>
  </thead>
  <tbody>{audit_row}</tbody>
</table>
"""

    # Section 6 — Build Reference
    s6 = f"""
<h2>6. Git Hash / Build Reference</h2>
<table>
  <tr><th>Field</th><th>Value</th></tr>
  <tr><td>Git Commit Hash</td><td>{git_hash}</td></tr>
  <tr><td>Generated At</td><td>{generated_at}</td></tr>
</table>
"""

    body = s1 + s2 + s3 + s4 + s5 + s6
    return _html_wrap(title, body)


# ---------------------------------------------------------------------------
# HTML builder: Incident Report
# ---------------------------------------------------------------------------


def _incident_html(
    title: str,
    case: dict | None,
    detections: list[dict],
    ioc_hits: list[dict],
    triage: dict | None,
    techniques: list[dict],
) -> str:
    """Build HTML for a Security Incident Report."""

    if case:
        case_id = case.get("case_id", "")
        case_title = case.get("title", "")
        case_status = case.get("case_status", "")
        case_notes = case.get("analyst_notes", "")
        case_created = case.get("created_at", "")
        case_section = f"""
<table>
  <tr><th>Field</th><th>Value</th></tr>
  <tr><td>Case ID</td><td>{case_id}</td></tr>
  <tr><td>Title</td><td>{case_title}</td></tr>
  <tr><td>Status</td><td>{case_status}</td></tr>
  <tr><td>Analyst Notes</td><td style="white-space:pre-wrap;">{case_notes}</td></tr>
  <tr><td>Created At</td><td>{case_created}</td></tr>
</table>
"""
    else:
        case_section = _no_data()

    # Section 2 — Timeline of Detections
    detection_rows = "".join(
        f"<tr><td>{d.get('rule_name', '')}</td><td>{d.get('severity', '')}</td>"
        f"<td>{d.get('attack_technique', '')}</td><td>{d.get('created_at', '')}</td></tr>"
        for d in (detections or [])
    ) or "<tr><td colspan='4'>No detections</td></tr>"

    # Section 3 — IOC Matches
    ioc_rows = "".join(
        f"<tr><td>{h.get('indicator', '')}</td><td>{h.get('ioc_type', '')}</td>"
        f"<td>{h.get('confidence', '')}</td><td>{h.get('source_feed', '')}</td>"
        f"<td>{h.get('matched_at', '')}</td></tr>"
        for h in (ioc_hits or [])
    ) or "<tr><td colspan='5'>No IOC matches</td></tr>"

    # Section 4 — ATT&CK Techniques
    tech_rows = "".join(
        f"<tr><td>{t.get('technique_id', '')}</td><td>{t.get('name', '')}</td>"
        f"<td>{t.get('tactic', '')}</td></tr>"
        for t in (techniques or [])
    ) or "<tr><td colspan='3'>No techniques observed</td></tr>"

    # Section 5 — LLM Inference Audit Trail
    if triage:
        audit_row = (
            f"<tr>"
            f"<td>{triage.get('model_name', '')}</td>"
            f"<td>{triage.get('prompt_version', 'N/A')}</td>"
            f"<td>{triage.get('severity_summary', '')}</td>"
            f"<td style='white-space:pre-wrap;word-break:break-all;'>{triage.get('result_text', '')[:500]}</td>"
            f"<td></td><td></td>"
            f"</tr>"
        )
    else:
        audit_row = "<tr><td colspan='6'>No triage data</td></tr>"

    body = f"""
<p class="meta">Generated: {datetime.now(timezone.utc).isoformat()}</p>

<h2>1. Case Summary</h2>
{case_section}

<h2>2. Timeline of Detections</h2>
<table>
  <thead><tr><th>Rule Name</th><th>Severity</th><th>ATT&CK Technique</th><th>Detected At</th></tr></thead>
  <tbody>{detection_rows}</tbody>
</table>

<h2>3. IOC Matches</h2>
<table>
  <thead><tr><th>Indicator</th><th>Type</th><th>Confidence</th><th>Feed</th><th>Matched At</th></tr></thead>
  <tbody>{ioc_rows}</tbody>
</table>

<h2>4. ATT&amp;CK Techniques Observed</h2>
<table>
  <thead><tr><th>Technique ID</th><th>Name</th><th>Tactic</th></tr></thead>
  <tbody>{tech_rows}</tbody>
</table>

<h2>5. LLM Inference Audit Trail</h2>
<table>
  <thead>
    <tr><th>Model</th><th>Prompt Version</th><th>Severity Summary</th>
    <th>Result Text</th><th>Confidence</th><th>Disposition</th></tr>
  </thead>
  <tbody>{audit_row}</tbody>
</table>

<h2>6. Analyst Assessment</h2>
{_no_data()}
"""
    return _html_wrap(title, body)


# ---------------------------------------------------------------------------
# HTML builder: Playbook Execution Log
# ---------------------------------------------------------------------------


def _playbook_log_html(
    title: str,
    run: dict | None,
    playbook: dict | None,
    case: dict | None,
    triage: dict | None,
) -> str:
    """Build HTML for a Playbook Execution Log report."""

    # Section 1 — Run Metadata
    if run:
        run_body = f"""
<table>
  <tr><th>Field</th><th>Value</th></tr>
  <tr><td>Run ID</td><td>{run.get('run_id', '')}</td></tr>
  <tr><td>Playbook ID</td><td>{run.get('playbook_id', '')}</td></tr>
  <tr><td>Status</td><td>{run.get('status', '')}</td></tr>
  <tr><td>Investigation ID</td><td>{run.get('investigation_id', '')}</td></tr>
  <tr><td>Started At</td><td>{run.get('started_at', '')}</td></tr>
  <tr><td>Completed At</td><td>{run.get('completed_at', '')}</td></tr>
</table>
"""
    else:
        run_body = _no_data()

    # Section 2 — Playbook Definition
    if playbook:
        pb_body = f"""
<table>
  <tr><th>Field</th><th>Value</th></tr>
  <tr><td>Name</td><td>{playbook.get('name', '')}</td></tr>
  <tr><td>Description</td><td>{playbook.get('description', '')}</td></tr>
  <tr><td>Trigger</td><td>{playbook.get('trigger', '')}</td></tr>
</table>
"""
    else:
        pb_body = _no_data()

    # Section 3 — Step-by-Step Execution Log
    steps_raw = run.get("steps_completed") if run else None
    steps: list[dict] = []
    if steps_raw:
        try:
            steps = json.loads(steps_raw) if isinstance(steps_raw, str) else steps_raw
        except (json.JSONDecodeError, TypeError):
            steps = []

    if steps:
        step_rows = "".join(
            f"<tr><td>{i + 1}</td>"
            f"<td>{s.get('step_name', s.get('name', ''))}</td>"
            f"<td>{s.get('status', '')}</td>"
            f"<td style='white-space:pre-wrap;word-break:break-all;'>{json.dumps(s.get('output', s.get('result', '')))[:500]}</td>"
            f"<td>{s.get('timestamp', s.get('completed_at', ''))}</td></tr>"
            for i, s in enumerate(steps)
        )
    else:
        step_rows = "<tr><td colspan='5'>No step data recorded</td></tr>"

    # Section 4 — LLM Inference Audit Trail
    if triage:
        audit_row = (
            f"<tr>"
            f"<td>{triage.get('model_name', '')}</td>"
            f"<td>{triage.get('prompt_version', 'N/A')}</td>"
            f"<td>{triage.get('severity_summary', '')}</td>"
            f"<td style='white-space:pre-wrap;word-break:break-all;'>{triage.get('result_text', '')[:500]}</td>"
            f"<td></td><td></td>"
            f"</tr>"
        )
    else:
        audit_row = "<tr><td colspan='6'>No triage data</td></tr>"

    body = f"""
<p class="meta">Generated: {datetime.now(timezone.utc).isoformat()}</p>

<h2>1. Run Metadata</h2>
{run_body}

<h2>2. Playbook Definition</h2>
{pb_body}

<h2>3. Step-by-Step Execution Log</h2>
<table>
  <thead><tr><th>#</th><th>Step</th><th>Status</th><th>Output</th><th>Timestamp</th></tr></thead>
  <tbody>{step_rows}</tbody>
</table>

<h2>4. LLM Inference Audit Trail</h2>
<table>
  <thead>
    <tr><th>Model</th><th>Prompt Version</th><th>Severity Summary</th>
    <th>Result Text</th><th>Confidence</th><th>Disposition</th></tr>
  </thead>
  <tbody>{audit_row}</tbody>
</table>

<h2>5. Analyst Sign-off</h2>
{_no_data()}
"""
    return _html_wrap(title, body)


# ---------------------------------------------------------------------------
# HTML builder: Post-Incident Review (PIR)
# ---------------------------------------------------------------------------


def _pir_html(
    title: str,
    case: dict | None,
    detections: list[dict],
    techniques: list[dict],
    playbook_runs: list[dict],
    triage: dict | None,
) -> str:
    """Build HTML for a Post-Incident Review report."""

    if case:
        case_body = f"""
<table>
  <tr><th>Field</th><th>Value</th></tr>
  <tr><td>Case ID</td><td>{case.get('case_id', '')}</td></tr>
  <tr><td>Title</td><td>{case.get('title', '')}</td></tr>
  <tr><td>Status</td><td>{case.get('case_status', '')}</td></tr>
  <tr><td>Created At</td><td>{case.get('created_at', '')}</td></tr>
  <tr><td>Updated At</td><td>{case.get('updated_at', '')}</td></tr>
  <tr><td>Analyst Notes</td><td style="white-space:pre-wrap;">{case.get('analyst_notes', '')}</td></tr>
</table>
"""
    else:
        case_body = _no_data()

    detection_rows = "".join(
        f"<tr><td>{d.get('rule_name', '')}</td><td>{d.get('severity', '')}</td>"
        f"<td>{d.get('attack_technique', '')}</td><td>{d.get('created_at', '')}</td></tr>"
        for d in (detections or [])
    ) or "<tr><td colspan='4'>No detections</td></tr>"

    tech_rows = "".join(
        f"<tr><td>{t.get('technique_id', '')}</td><td>{t.get('name', '')}</td>"
        f"<td>{t.get('tactic', '')}</td></tr>"
        for t in (techniques or [])
    ) or "<tr><td colspan='3'>No techniques observed</td></tr>"

    pb_rows = "".join(
        f"<tr><td>{r.get('run_id', '')}</td><td>{r.get('playbook_id', '')}</td>"
        f"<td>{r.get('status', '')}</td><td>{r.get('started_at', '')}</td></tr>"
        for r in (playbook_runs or [])
    ) or "<tr><td colspan='4'>No playbook runs</td></tr>"

    if triage:
        audit_row = (
            f"<tr>"
            f"<td>{triage.get('model_name', '')}</td>"
            f"<td>{triage.get('prompt_version', 'N/A')}</td>"
            f"<td>{triage.get('severity_summary', '')}</td>"
            f"<td style='white-space:pre-wrap;word-break:break-all;'>{triage.get('result_text', '')[:500]}</td>"
            f"<td></td><td></td>"
            f"</tr>"
        )
    else:
        audit_row = "<tr><td colspan='6'>No triage data</td></tr>"

    body = f"""
<p class="meta">Generated: {datetime.now(timezone.utc).isoformat()}</p>

<h2>1. Incident Overview</h2>
{case_body}

<h2>2. Detection Timeline</h2>
<table>
  <thead><tr><th>Rule</th><th>Severity</th><th>Technique</th><th>Detected At</th></tr></thead>
  <tbody>{detection_rows}</tbody>
</table>

<h2>3. ATT&amp;CK Techniques Observed</h2>
<table>
  <thead><tr><th>Technique ID</th><th>Name</th><th>Tactic</th></tr></thead>
  <tbody>{tech_rows}</tbody>
</table>

<h2>4. Playbook Runs</h2>
<table>
  <thead><tr><th>Run ID</th><th>Playbook</th><th>Status</th><th>Started At</th></tr></thead>
  <tbody>{pb_rows}</tbody>
</table>

<h2>5. LLM Inference Audit Trail</h2>
<table>
  <thead>
    <tr><th>Model</th><th>Prompt Version</th><th>Severity Summary</th>
    <th>Result Text</th><th>Confidence</th><th>Disposition</th></tr>
  </thead>
  <tbody>{audit_row}</tbody>
</table>

<h2>6. Root Cause Analysis</h2>
{_no_data()}

<h2>7. Lessons Learned</h2>
{_no_data()}

<h2>8. Remediation Actions</h2>
{_no_data()}
"""
    return _html_wrap(title, body)


# ---------------------------------------------------------------------------
# HTML builder: Threat Intelligence Bulletin
# ---------------------------------------------------------------------------


def _ti_bulletin_html(
    title: str,
    actor_name: str,
    actor_info: dict | None,
    group_techniques: list[dict],
    ioc_rows: list[dict],
    asset_rows: list[dict],
    triage: dict | None,
) -> str:
    """Build HTML for a Threat Intelligence Bulletin."""

    if actor_info:
        actor_body = f"""
<table>
  <tr><th>Field</th><th>Value</th></tr>
  <tr><td>Name</td><td>{actor_info.get('name', actor_name)}</td></tr>
  <tr><td>Group ID</td><td>{actor_info.get('group_id', '')}</td></tr>
  <tr><td>Description</td><td>{actor_info.get('description', '')}</td></tr>
  <tr><td>Country</td><td>{actor_info.get('country', '')}</td></tr>
</table>
"""
    else:
        actor_body = f"<p>Actor: <strong>{actor_name}</strong></p>"

    tech_rows_html = "".join(
        f"<tr><td>{t.get('technique_id', '')}</td><td>{t.get('name', '')}</td>"
        f"<td>{t.get('tactic', '')}</td></tr>"
        for t in (group_techniques or [])
    ) or "<tr><td colspan='3'>No techniques recorded for this actor</td></tr>"

    ioc_html = "".join(
        f"<tr><td>{r.get('indicator', '')}</td><td>{r.get('ioc_type', '')}</td>"
        f"<td>{r.get('confidence', '')}</td><td>{r.get('source_feed', '')}</td></tr>"
        for r in (ioc_rows or [])
    ) or "<tr><td colspan='4'>No IOC hits for this actor</td></tr>"

    asset_html = "".join(
        f"<tr><td>{a.get('ip_address', '')}</td><td>{a.get('hostname', '')}</td>"
        f"<td>{a.get('asset_type', '')}</td><td>{a.get('risk_score', '')}</td></tr>"
        for a in (asset_rows or [])
    ) or "<tr><td colspan='4'>No assets at risk identified</td></tr>"

    if triage:
        audit_row = (
            f"<tr>"
            f"<td>{triage.get('model_name', '')}</td>"
            f"<td>{triage.get('prompt_version', 'N/A')}</td>"
            f"<td>{triage.get('severity_summary', '')}</td>"
            f"<td style='white-space:pre-wrap;word-break:break-all;'>{triage.get('result_text', '')[:500]}</td>"
            f"<td></td><td></td>"
            f"</tr>"
        )
    else:
        audit_row = "<tr><td colspan='6'>No triage data</td></tr>"

    body = f"""
<p class="meta">Threat Intelligence Bulletin | Generated: {datetime.now(timezone.utc).isoformat()}</p>

<h2>1. Threat Actor Profile</h2>
{actor_body}

<h2>2. Known TTPs (ATT&amp;CK Techniques)</h2>
<table>
  <thead><tr><th>Technique ID</th><th>Name</th><th>Tactic</th></tr></thead>
  <tbody>{tech_rows_html}</tbody>
</table>

<h2>3. IOC Matches (Last 30 Days)</h2>
<table>
  <thead><tr><th>Indicator</th><th>Type</th><th>Confidence</th><th>Feed</th></tr></thead>
  <tbody>{ioc_html}</tbody>
</table>

<h2>4. Assets at Risk</h2>
<table>
  <thead><tr><th>IP Address</th><th>Hostname</th><th>Asset Type</th><th>Risk Score</th></tr></thead>
  <tbody>{asset_html}</tbody>
</table>

<h2>5. LLM Inference Audit Trail</h2>
<table>
  <thead>
    <tr><th>Model</th><th>Prompt Version</th><th>Severity Summary</th>
    <th>Result Text</th><th>Confidence</th><th>Disposition</th></tr>
  </thead>
  <tbody>{audit_row}</tbody>
</table>

<h2>6. Analyst Assessment</h2>
{_no_data()}
"""
    return _html_wrap(title, body)


# ---------------------------------------------------------------------------
# HTML builder: Severity Reference Card
# ---------------------------------------------------------------------------

_SEVERITY_LEVELS = [
    ("critical", "#7b0000", "#fff", "Active compromise or imminent system-wide threat. Immediate response required (< 15 min)."),
    ("high", "#c0392b", "#fff", "Significant threat with potential for data exfiltration or lateral movement. Respond within 1 hour."),
    ("medium", "#e67e22", "#fff", "Suspicious activity requiring investigation. Respond within 4 hours."),
    ("low", "#27ae60", "#fff", "Informational alert or minor anomaly. Review within 24 hours."),
    ("informational", "#2980b9", "#fff", "Baseline telemetry and health events. No action required."),
]


def _severity_ref_html() -> str:
    """Build HTML for the Severity Reference Card (no parameters — static content)."""

    rows = "".join(
        f"<tr style='background:{bg};color:{fg};'>"
        f"<td style='font-weight:bold;padding:8px;'>{level.upper()}</td>"
        f"<td style='padding:8px;'>{desc}</td>"
        f"</tr>"
        for level, bg, fg, desc in _SEVERITY_LEVELS
    )

    sigma_rows = """
<tr><td>critical</td><td>Sigma level: critical — direct attack sequence confirmed</td></tr>
<tr><td>high</td><td>Sigma level: high — high-confidence detection firing</td></tr>
<tr><td>medium</td><td>Sigma level: medium — moderate-confidence or multi-step indicator</td></tr>
<tr><td>low</td><td>Sigma level: low — noisy / informational rule</td></tr>
"""

    body = f"""
<p class="meta">Generated: {datetime.now(timezone.utc).isoformat()} | AI-SOC-Brain Severity Reference</p>

<h2>1. Severity Levels</h2>
<table>
  <thead><tr><th>Level</th><th>Description &amp; Response SLA</th></tr></thead>
  <tbody>{rows}</tbody>
</table>

<h2>2. Sigma Rule Level Mapping</h2>
<table>
  <thead><tr><th>Severity Level</th><th>Mapping Rationale</th></tr></thead>
  <tbody>{sigma_rows}</tbody>
</table>

<h2>3. Escalation Matrix</h2>
<table>
  <thead><tr><th>Severity</th><th>Notify</th><th>SLA</th><th>Auto-Triage</th></tr></thead>
  <tbody>
    <tr><td>Critical</td><td>SOC Lead + CISO</td><td>&lt; 15 min</td><td>Yes</td></tr>
    <tr><td>High</td><td>SOC Lead</td><td>&lt; 1 hr</td><td>Yes</td></tr>
    <tr><td>Medium</td><td>Analyst on duty</td><td>&lt; 4 hr</td><td>Optional</td></tr>
    <tr><td>Low</td><td>Analyst on duty</td><td>&lt; 24 hr</td><td>No</td></tr>
    <tr><td>Informational</td><td>None required</td><td>Review weekly</td><td>No</td></tr>
  </tbody>
</table>
"""
    return _html_wrap("AI-SOC-Brain Severity Reference Card", body)


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _git_hash() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True, timeout=5
        ).strip()[:12]
    except Exception:
        return "unknown"


# ---------------------------------------------------------------------------
# GET /api/reports/template/meta
# (defined FIRST to avoid path-param capture by /{report_id}/pdf in reports.py)
# ---------------------------------------------------------------------------


@router.get("/template/meta")
async def get_template_meta(request: Request) -> JSONResponse:
    """
    GET /api/reports/template/meta

    Returns dropdown-populating counts and lists in a single response.
    Includes: investigations, closed_cases, playbook_runs, actors (count),
    actor_list, case_list, run_list.
    """
    stores = request.app.state.stores

    def _fetch_meta(sqlite_store: Any) -> dict:
        conn = sqlite_store._conn

        # Investigation counts
        try:
            row = conn.execute("SELECT COUNT(*) FROM investigation_cases").fetchone()
            investigations = row[0] if row else 0
        except Exception:
            investigations = 0

        try:
            row = conn.execute(
                "SELECT COUNT(*) FROM investigation_cases WHERE case_status = 'closed'"
            ).fetchone()
            closed_cases = row[0] if row else 0
        except Exception:
            closed_cases = 0

        # Playbook run count
        try:
            row = conn.execute("SELECT COUNT(*) FROM playbook_runs").fetchone()
            playbook_runs = row[0] if row else 0
        except Exception:
            playbook_runs = 0

        # Actor list
        try:
            rows = conn.execute(
                "SELECT name, group_id FROM attack_groups ORDER BY name"
            ).fetchall()
            actor_list = [{"name": r[0], "group_id": r[1]} for r in rows]
        except Exception:
            actor_list = []

        # Case list (for dropdowns)
        try:
            rows = conn.execute(
                "SELECT case_id, title, case_status FROM investigation_cases ORDER BY created_at DESC LIMIT 200"
            ).fetchall()
            case_list = [{"case_id": r[0], "title": r[1], "case_status": r[2]} for r in rows]
        except Exception:
            case_list = []

        # Run list (for dropdowns)
        try:
            rows = conn.execute(
                "SELECT run_id, playbook_id, status, started_at FROM playbook_runs ORDER BY started_at DESC LIMIT 200"
            ).fetchall()
            run_list = [
                {"run_id": r[0], "playbook_id": r[1], "status": r[2], "started_at": r[3]}
                for r in rows
            ]
        except Exception:
            run_list = []

        return {
            "investigations": investigations,
            "closed_cases": closed_cases,
            "playbook_runs": playbook_runs,
            "actors": len(actor_list),
            "actor_list": actor_list,
            "case_list": case_list,
            "run_list": run_list,
        }

    meta = await asyncio.to_thread(_fetch_meta, stores.sqlite)
    return JSONResponse(content=meta)


# ---------------------------------------------------------------------------
# POST /api/reports/template/session-log
# ---------------------------------------------------------------------------


@router.post("/template/session-log", status_code=201)
async def generate_session_log_report(request: Request) -> JSONResponse:
    """POST /api/reports/template/session-log — generate a daily session log report."""
    stores = request.app.state.stores

    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()
    cutoff_iso = (now - timedelta(hours=24)).isoformat()

    # --- DuckDB queries (async, read-only) ---
    event_count_24h = 0
    event_type_breakdown: list[tuple[str, int]] = []
    source_types: list[tuple[str, int]] = []
    try:
        rows = await stores.duckdb.fetch_all(
            "SELECT COUNT(*) FROM normalized_events WHERE timestamp >= ? AND timestamp <= ?",
            [cutoff_iso, now_iso],
        )
        if rows:
            val = rows[0][0] if isinstance(rows[0], tuple) else rows[0].get("count_star()", 0)
            event_count_24h = int(val or 0)
    except Exception as exc:
        log.warning("session-log DuckDB event count failed", error=str(exc))

    try:
        rows = await stores.duckdb.fetch_all(
            """SELECT event_type, COUNT(*) AS cnt FROM normalized_events
               WHERE timestamp >= ? AND timestamp <= ? AND event_type IS NOT NULL
               GROUP BY event_type ORDER BY cnt DESC LIMIT 20""",
            [cutoff_iso, now_iso],
        )
        for r in rows:
            if isinstance(r, tuple):
                event_type_breakdown.append((str(r[0]), int(r[1])))
            else:
                event_type_breakdown.append((str(r.get("event_type")), int(r.get("cnt", 0))))
    except Exception as exc:
        log.warning("session-log DuckDB event_type breakdown failed", error=str(exc))

    try:
        rows = await stores.duckdb.fetch_all(
            """SELECT source_type, COUNT(*) AS cnt FROM normalized_events
               WHERE timestamp >= ? AND timestamp <= ? AND source_type IS NOT NULL
               GROUP BY source_type ORDER BY cnt DESC""",
            [cutoff_iso, now_iso],
        )
        for r in rows:
            if isinstance(r, tuple):
                source_types.append((str(r[0]), int(r[1])))
            else:
                source_types.append((str(r.get("source_type")), int(r.get("cnt", 0))))
    except Exception as exc:
        log.warning("session-log DuckDB source_type breakdown failed", error=str(exc))

    # --- SQLite queries ---
    detection_count_24h = 0
    try:
        def _count_detections(conn: Any) -> int:
            row = conn.execute(
                "SELECT COUNT(*) FROM detections WHERE created_at >= ?", (cutoff_iso,)
            ).fetchone()
            return row[0] if row else 0

        detection_count_24h = await asyncio.to_thread(
            _count_detections, stores.sqlite._conn
        )
    except Exception as exc:
        log.warning("session-log SQLite detection count failed", error=str(exc))

    latest_triage = None
    try:
        latest_triage = await asyncio.to_thread(stores.sqlite.get_latest_triage)
    except Exception as exc:
        log.warning("session-log get_latest_triage failed", error=str(exc))

    git = _git_hash()

    title = f"AI-SOC-Brain Daily Session Log — {now.strftime('%Y-%m-%d')}"
    html = _session_log_html(
        title=title,
        generated_at=now_iso,
        event_count_24h=event_count_24h,
        event_type_breakdown=event_type_breakdown,
        source_types=source_types,
        detection_count_24h=detection_count_24h,
        latest_triage=latest_triage,
        git_hash=git,
    )

    pdf_bytes: bytes = await asyncio.to_thread(_render_pdf, html)
    content_json = json.dumps({"pdf_b64": base64.b64encode(pdf_bytes).decode("ascii")})

    report_id = str(uuid4())
    await asyncio.to_thread(
        stores.sqlite.insert_report,
        {
            "id": report_id,
            "type": "template_session_log",
            "title": title,
            "subject_id": None,
            "period_start": cutoff_iso,
            "period_end": now_iso,
            "content_json": content_json,
            "created_at": now_iso,
        },
    )

    log.info("Session log report generated", report_id=report_id)
    return JSONResponse(
        content={"id": report_id, "type": "template_session_log", "title": title, "created_at": now_iso},
        status_code=201,
    )


# ---------------------------------------------------------------------------
# POST /api/reports/template/incident/{case_id}
# ---------------------------------------------------------------------------


@router.post("/template/incident/{case_id}", status_code=201)
async def generate_incident_report(case_id: str, request: Request) -> JSONResponse:
    """POST /api/reports/template/incident/{case_id} — generate a security incident report."""
    stores = request.app.state.stores
    now_iso = _utcnow_iso()

    # Fetch case (blank template if missing — never block)
    case: dict | None = None
    try:
        case = await asyncio.to_thread(stores.sqlite.get_investigation_case, case_id)
    except Exception as exc:
        log.warning("incident report: case fetch failed", case_id=case_id, error=str(exc))

    # Fetch detections
    detections: list[dict] = []
    try:
        def _fetch_detections(conn: Any) -> list[dict]:
            try:
                rows = conn.execute(
                    "SELECT * FROM detections WHERE case_id = ? LIMIT 50",
                    (case_id,),
                ).fetchall()
                return [dict(r) for r in rows]
            except Exception:
                return []

        detections = await asyncio.to_thread(_fetch_detections, stores.sqlite._conn)
    except Exception as exc:
        log.warning("incident report: detections fetch failed", error=str(exc))

    # Fetch IOC hits
    ioc_hits: list[dict] = []
    try:
        def _fetch_ioc_hits(conn: Any) -> list[dict]:
            try:
                rows = conn.execute(
                    "SELECT * FROM ioc_hits ORDER BY matched_at DESC LIMIT 30"
                ).fetchall()
                return [dict(r) for r in rows]
            except Exception:
                return []

        ioc_hits = await asyncio.to_thread(_fetch_ioc_hits, stores.sqlite._conn)
    except Exception as exc:
        log.warning("incident report: ioc_hits fetch failed", error=str(exc))

    # Fetch latest triage
    triage: dict | None = None
    try:
        triage = await asyncio.to_thread(stores.sqlite.get_latest_triage)
    except Exception as exc:
        log.warning("incident report: triage fetch failed", error=str(exc))

    # Fetch ATT&CK techniques
    techniques: list[dict] = []
    try:
        def _fetch_techniques(conn: Any) -> list[dict]:
            try:
                rows = conn.execute(
                    """SELECT DISTINCT at.technique_id, at.name, at.tactic
                       FROM detection_techniques dt
                       JOIN attack_techniques at ON dt.technique_id = at.technique_id
                       LIMIT 50"""
                ).fetchall()
                return [{"technique_id": r[0], "name": r[1], "tactic": r[2]} for r in rows]
            except Exception:
                return []

        techniques = await asyncio.to_thread(_fetch_techniques, stores.sqlite._conn)
    except Exception as exc:
        log.warning("incident report: techniques fetch failed", error=str(exc))

    case_title = case.get("title", case_id) if case else case_id
    title = f"Security Incident Report — INC-{case_id[:8].upper()}: {case_title}"
    html = _incident_html(
        title=title,
        case=case,
        detections=detections,
        ioc_hits=ioc_hits,
        triage=triage,
        techniques=techniques,
    )

    pdf_bytes: bytes = await asyncio.to_thread(_render_pdf, html)
    content_json = json.dumps({"pdf_b64": base64.b64encode(pdf_bytes).decode("ascii")})

    report_id = str(uuid4())
    await asyncio.to_thread(
        stores.sqlite.insert_report,
        {
            "id": report_id,
            "type": "template_incident",
            "title": title,
            "subject_id": case_id,
            "period_start": None,
            "period_end": None,
            "content_json": content_json,
            "created_at": now_iso,
        },
    )

    log.info("Incident report generated", report_id=report_id, case_id=case_id)
    return JSONResponse(
        content={"id": report_id, "type": "template_incident", "title": title, "created_at": now_iso},
        status_code=201,
    )


# ---------------------------------------------------------------------------
# POST /api/reports/template/playbook-log/{run_id}
# ---------------------------------------------------------------------------


@router.post("/template/playbook-log/{run_id}", status_code=201)
async def generate_playbook_log_report(run_id: str, request: Request) -> JSONResponse:
    """POST /api/reports/template/playbook-log/{run_id} — generate a playbook execution log."""
    stores = request.app.state.stores
    now_iso = _utcnow_iso()

    # Fetch playbook run (blank if missing)
    run: dict | None = None
    try:
        def _fetch_run(conn: Any) -> dict | None:
            try:
                row = conn.execute(
                    "SELECT * FROM playbook_runs WHERE run_id = ?", (run_id,)
                ).fetchone()
                return dict(row) if row else None
            except Exception:
                return None

        run = await asyncio.to_thread(_fetch_run, stores.sqlite._conn)
    except Exception as exc:
        log.warning("playbook-log report: run fetch failed", run_id=run_id, error=str(exc))

    # Fetch playbook definition if run found
    playbook: dict | None = None
    if run and run.get("playbook_id"):
        try:
            def _fetch_playbook(conn: Any, pb_id: str) -> dict | None:
                try:
                    row = conn.execute(
                        "SELECT * FROM playbooks WHERE playbook_id = ?", (pb_id,)
                    ).fetchone()
                    return dict(row) if row else None
                except Exception:
                    return None

            playbook = await asyncio.to_thread(
                _fetch_playbook, stores.sqlite._conn, run["playbook_id"]
            )
        except Exception as exc:
            log.warning("playbook-log report: playbook fetch failed", error=str(exc))

    # Fetch case if linked
    case: dict | None = None
    if run and run.get("investigation_id"):
        try:
            case = await asyncio.to_thread(
                stores.sqlite.get_investigation_case, run["investigation_id"]
            )
        except Exception as exc:
            log.warning("playbook-log report: case fetch failed", error=str(exc))

    # Fetch latest triage
    triage: dict | None = None
    try:
        triage = await asyncio.to_thread(stores.sqlite.get_latest_triage)
    except Exception as exc:
        log.warning("playbook-log report: triage fetch failed", error=str(exc))

    pb_id = run.get("playbook_id", run_id) if run else run_id
    title = f"Playbook Execution Log — {pb_id}"
    html = _playbook_log_html(
        title=title,
        run=run,
        playbook=playbook,
        case=case,
        triage=triage,
    )

    pdf_bytes: bytes = await asyncio.to_thread(_render_pdf, html)
    content_json = json.dumps({"pdf_b64": base64.b64encode(pdf_bytes).decode("ascii")})

    report_id = str(uuid4())
    await asyncio.to_thread(
        stores.sqlite.insert_report,
        {
            "id": report_id,
            "type": "template_playbook_log",
            "title": title,
            "subject_id": run_id,
            "period_start": None,
            "period_end": None,
            "content_json": content_json,
            "created_at": now_iso,
        },
    )

    log.info("Playbook log report generated", report_id=report_id, run_id=run_id)
    return JSONResponse(
        content={"id": report_id, "type": "template_playbook_log", "title": title, "created_at": now_iso},
        status_code=201,
    )
