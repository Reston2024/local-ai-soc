"""
Reports API — Phase 18 Report Generation.

Endpoints:
    POST /api/reports/investigation/{investigation_id}  — generate investigation report
    POST /api/reports/executive                         — generate executive summary report
    GET  /api/reports                                   — list all reports (no pdf_b64)
    GET  /api/reports/{report_id}/pdf                   — download PDF binary

Reports are stored in SQLite (reports table).  PDFs are rendered via WeasyPrint
(CPU-bound, wrapped in asyncio.to_thread) and stored base64-encoded in content_json.
"""

from __future__ import annotations

import asyncio
import base64
import io
import json
import zipfile
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse

from backend.core.logging import get_logger
from backend.models.report import ExecutiveReportRequest, InvestigationReportRequest

log = get_logger(__name__)

router = APIRouter(prefix="/api/reports", tags=["reports"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _render_pdf(html_content: str) -> bytes:
    """
    Render HTML to PDF bytes using WeasyPrint.

    Imported lazily to avoid startup cost — WeasyPrint loads font/CSS
    subsystems on first import.  This function is always called inside
    asyncio.to_thread() because WeasyPrint is CPU-bound blocking I/O.
    """
    import weasyprint  # noqa: PLC0415 — intentional lazy import

    return weasyprint.HTML(string=html_content).write_pdf()


def _strip_pdf_b64(report: dict) -> dict:
    """Return a copy of a report dict with pdf_b64 removed from content_json."""
    report = dict(report)
    try:
        content = json.loads(report.get("content_json", "{}"))
        content.pop("pdf_b64", None)
        report["content_json"] = json.dumps(content)
    except (json.JSONDecodeError, TypeError):
        pass
    return report


# ---------------------------------------------------------------------------
# HTML template helpers
# ---------------------------------------------------------------------------


def _investigation_html(
    title: str,
    investigation: dict,
    detections: list[dict],
    chat_history: list[dict],
    playbook_runs: list[dict],
    generated_at: str,
) -> str:
    """Build an HTML string for an investigation report."""
    rows_detections = "".join(
        f"<tr><td>{d.get('rule_name', '')}</td>"
        f"<td>{d.get('severity', '')}</td>"
        f"<td>{d.get('created_at', '')}</td></tr>"
        for d in detections
    )
    chat_section = ""
    if chat_history:
        chat_rows = "".join(
            f"<tr><td><strong>{m.get('role', '')}</strong></td>"
            f"<td>{m.get('content', '')}</td>"
            f"<td>{m.get('created_at', '')}</td></tr>"
            for m in chat_history
        )
        chat_section = f"""
        <h2>Chat History</h2>
        <table border="1" cellpadding="4" cellspacing="0" width="100%">
            <thead><tr><th>Role</th><th>Message</th><th>Time</th></tr></thead>
            <tbody>{chat_rows}</tbody>
        </table>
        """

    pb_section = ""
    if playbook_runs:
        pb_rows = "".join(
            f"<tr><td>{r.get('run_id', '')}</td>"
            f"<td>{r.get('playbook_id', '')}</td>"
            f"<td>{r.get('status', '')}</td>"
            f"<td>{r.get('started_at', '')}</td></tr>"
            for r in playbook_runs
        )
        pb_section = f"""
        <h2>Playbook Runs</h2>
        <table border="1" cellpadding="4" cellspacing="0" width="100%">
            <thead><tr><th>Run ID</th><th>Playbook</th><th>Status</th><th>Started</th></tr></thead>
            <tbody>{pb_rows}</tbody>
        </table>
        """

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8"/>
<title>{title}</title>
<style>
  body {{ font-family: Arial, sans-serif; font-size: 12px; margin: 30px; }}
  h1 {{ color: #1a1a2e; }}
  h2 {{ color: #16213e; border-bottom: 1px solid #ccc; padding-bottom: 4px; }}
  table {{ border-collapse: collapse; width: 100%; margin-bottom: 20px; }}
  th {{ background: #16213e; color: #fff; padding: 6px; text-align: left; }}
  td {{ padding: 5px; vertical-align: top; }}
  tr:nth-child(even) {{ background: #f2f2f2; }}
  .meta {{ color: #666; font-size: 11px; margin-bottom: 20px; }}
</style>
</head>
<body>
<h1>{title}</h1>
<p class="meta">Generated: {generated_at}</p>

<h2>Investigation Summary</h2>
<table border="1" cellpadding="4" cellspacing="0" width="100%">
  <tr><th>Field</th><th>Value</th></tr>
  <tr><td>Case ID</td><td>{investigation.get('case_id', '')}</td></tr>
  <tr><td>Title</td><td>{investigation.get('title', '')}</td></tr>
  <tr><td>Status</td><td>{investigation.get('case_status', '')}</td></tr>
  <tr><td>Analyst Notes</td><td>{investigation.get('analyst_notes', '')}</td></tr>
  <tr><td>Created</td><td>{investigation.get('created_at', '')}</td></tr>
</table>

<h2>Detections Timeline</h2>
<table border="1" cellpadding="4" cellspacing="0" width="100%">
  <thead><tr><th>Rule</th><th>Severity</th><th>Created At</th></tr></thead>
  <tbody>{rows_detections if rows_detections else '<tr><td colspan="3">No detections</td></tr>'}</tbody>
</table>

{chat_section}
{pb_section}
</body>
</html>"""


def _executive_html(
    title: str,
    period_start: str,
    period_end: str,
    detection_count: int,
    investigation_count: int,
    alert_volume: int,
    mttd_avg: float,
    mttr_avg: float,
    generated_at: str,
) -> str:
    """Build an HTML string for an executive summary report."""
    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8"/>
<title>{title}</title>
<style>
  body {{ font-family: Arial, sans-serif; font-size: 12px; margin: 30px; }}
  h1 {{ color: #1a1a2e; }}
  h2 {{ color: #16213e; border-bottom: 1px solid #ccc; padding-bottom: 4px; }}
  table {{ border-collapse: collapse; width: 100%; margin-bottom: 20px; }}
  th {{ background: #16213e; color: #fff; padding: 6px; text-align: left; }}
  td {{ padding: 5px; }}
  tr:nth-child(even) {{ background: #f2f2f2; }}
  .meta {{ color: #666; font-size: 11px; margin-bottom: 20px; }}
  .kpi {{ font-size: 24px; font-weight: bold; color: #1a1a2e; }}
</style>
</head>
<body>
<h1>{title}</h1>
<p class="meta">Period: {period_start} to {period_end} | Generated: {generated_at}</p>

<h2>Key Performance Indicators</h2>
<table border="1" cellpadding="8" cellspacing="0" width="100%">
  <thead><tr><th>Metric</th><th>Value</th></tr></thead>
  <tbody>
    <tr><td>Alert Volume</td><td class="kpi">{alert_volume}</td></tr>
    <tr><td>Detections Triggered</td><td class="kpi">{detection_count}</td></tr>
    <tr><td>Investigations Created</td><td class="kpi">{investigation_count}</td></tr>
    <tr><td>Mean Time to Detect (MTTD) avg</td><td class="kpi">{mttd_avg:.1f} min</td></tr>
    <tr><td>Mean Time to Respond (MTTR) avg</td><td class="kpi">{mttr_avg:.1f} min</td></tr>
  </tbody>
</table>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post("/investigation/{investigation_id}", status_code=201)
async def generate_investigation_report(
    investigation_id: str,
    body: InvestigationReportRequest,
    request: Request,
) -> JSONResponse:
    """
    POST /api/reports/investigation/{investigation_id}

    Generate an investigation report: fetches the investigation case, related
    detections, optional chat history and playbook runs, renders a PDF via
    WeasyPrint, and stores the result in SQLite.

    Returns 201 with the report metadata (id, type, title, subject_id, created_at).
    Returns 404 if the investigation case does not exist.
    """
    stores = request.app.state.stores

    # --- Fetch investigation data from SQLite ---
    investigation: dict[str, Any] | None = await asyncio.to_thread(
        stores.sqlite.get_investigation_case, investigation_id
    )
    if investigation is None:
        raise HTTPException(status_code=404, detail="Investigation not found")

    detections: list[dict[str, Any]] = await asyncio.to_thread(
        stores.sqlite.get_detections_by_case, investigation_id
    )

    chat_history: list[dict[str, Any]] = []
    if body.include_chat:
        chat_history = await asyncio.to_thread(
            stores.sqlite.get_chat_history, investigation_id
        )

    playbook_runs: list[dict[str, Any]] = []
    if body.include_playbook_runs:
        # playbook_runs are keyed by investigation_id in the playbook_runs table
        def _get_runs_for_investigation(sqlite_store: Any, inv_id: str) -> list[dict]:
            rows = sqlite_store._conn.execute(
                "SELECT * FROM playbook_runs WHERE investigation_id = ? ORDER BY started_at DESC",
                (inv_id,),
            ).fetchall()
            return [sqlite_store._parse_playbook_run(dict(r)) for r in rows]

        playbook_runs = await asyncio.to_thread(
            _get_runs_for_investigation, stores.sqlite, investigation_id
        )

    # --- Build content dict ---
    content_dict: dict[str, Any] = {
        "investigation": investigation,
        "detections": detections,
        "chat_history": chat_history,
        "playbook_runs": playbook_runs,
    }

    # --- Generate HTML ---
    title = f"Investigation Report: {investigation.get('title', investigation_id)}"
    generated_at = _utcnow_iso()
    html_content = _investigation_html(
        title=title,
        investigation=investigation,
        detections=detections,
        chat_history=chat_history,
        playbook_runs=playbook_runs,
        generated_at=generated_at,
    )

    # --- Render PDF (CPU-bound — separate thread) ---
    pdf_bytes: bytes = await asyncio.to_thread(_render_pdf, html_content)

    # --- Store pdf_b64 in content_json ---
    content_dict["pdf_b64"] = base64.b64encode(pdf_bytes).decode("ascii")

    # --- Persist report record ---
    report_id = str(uuid4())
    report_data: dict[str, Any] = {
        "id": report_id,
        "type": "investigation",
        "title": title,
        "subject_id": investigation_id,
        "period_start": None,
        "period_end": None,
        "content_json": json.dumps(content_dict),
        "created_at": generated_at,
    }
    await asyncio.to_thread(stores.sqlite.insert_report, report_data)

    log.info(
        "Investigation report generated",
        report_id=report_id,
        investigation_id=investigation_id,
    )
    return JSONResponse(
        content={
            "id": report_id,
            "type": "investigation",
            "title": title,
            "subject_id": investigation_id,
            "created_at": generated_at,
        },
        status_code=201,
    )


@router.post("/executive", status_code=201)
async def generate_executive_report(
    body: ExecutiveReportRequest,
    request: Request,
) -> JSONResponse:
    """
    POST /api/reports/executive

    Generate an executive summary report for a time period.  Counts detections
    and investigations in the period; fetches KPIs from DuckDB daily_kpi_snapshots
    if the table exists (graceful fallback to zeros).

    Returns 201 with the report metadata.
    """
    stores = request.app.state.stores

    # --- Count detections and investigations in period from SQLite ---
    def _count_detections(sqlite_store: Any, start: str, end: str) -> int:
        row = sqlite_store._conn.execute(
            "SELECT COUNT(*) FROM detections WHERE created_at >= ? AND created_at <= ?",
            (start, end),
        ).fetchone()
        return row[0] if row else 0

    def _count_investigations(sqlite_store: Any, start: str, end: str) -> int:
        row = sqlite_store._conn.execute(
            "SELECT COUNT(*) FROM investigation_cases WHERE created_at >= ? AND created_at <= ?",
            (start, end),
        ).fetchone()
        return row[0] if row else 0

    detection_count: int = await asyncio.to_thread(
        _count_detections, stores.sqlite, body.period_start, body.period_end
    )
    investigation_count: int = await asyncio.to_thread(
        _count_investigations, stores.sqlite, body.period_start, body.period_end
    )

    # --- Fetch KPI metrics from DuckDB (graceful fallback) ---
    alert_volume: int = 0
    mttd_avg: float = 0.0
    mttr_avg: float = 0.0

    try:
        kpi_rows = await stores.duckdb.fetch_all(
            """
            SELECT
                SUM(alert_count)    AS alert_volume,
                AVG(mttd_minutes)   AS mttd_avg,
                AVG(mttr_minutes)   AS mttr_avg
            FROM daily_kpi_snapshots
            WHERE snapshot_date >= ? AND snapshot_date <= ?
            """,
            [body.period_start[:10], body.period_end[:10]],
        )
        if kpi_rows:
            row = kpi_rows[0]
            alert_volume = int(row.get("alert_volume") or 0)
            mttd_avg = float(row.get("mttd_avg") or 0.0)
            mttr_avg = float(row.get("mttr_avg") or 0.0)
    except Exception as exc:
        # daily_kpi_snapshots may not exist yet (created in plan 18-03)
        log.debug("KPI snapshot table not available — using zeros", error=str(exc))

    # --- Build content dict ---
    content_dict: dict[str, Any] = {
        "period_start": body.period_start,
        "period_end": body.period_end,
        "alert_volume": alert_volume,
        "detection_count": detection_count,
        "investigation_count": investigation_count,
        "mttd_avg": mttd_avg,
        "mttr_avg": mttr_avg,
    }

    # --- Generate HTML ---
    generated_at = _utcnow_iso()
    html_content = _executive_html(
        title=body.title,
        period_start=body.period_start,
        period_end=body.period_end,
        detection_count=detection_count,
        investigation_count=investigation_count,
        alert_volume=alert_volume,
        mttd_avg=mttd_avg,
        mttr_avg=mttr_avg,
        generated_at=generated_at,
    )

    # --- Render PDF (CPU-bound — separate thread) ---
    pdf_bytes: bytes = await asyncio.to_thread(_render_pdf, html_content)

    # --- Store pdf_b64 in content_json ---
    content_dict["pdf_b64"] = base64.b64encode(pdf_bytes).decode("ascii")

    # --- Persist report record ---
    report_id = str(uuid4())
    report_data: dict[str, Any] = {
        "id": report_id,
        "type": "executive",
        "title": body.title,
        "subject_id": None,
        "period_start": body.period_start,
        "period_end": body.period_end,
        "content_json": json.dumps(content_dict),
        "created_at": generated_at,
    }
    await asyncio.to_thread(stores.sqlite.insert_report, report_data)

    log.info(
        "Executive report generated",
        report_id=report_id,
        period_start=body.period_start,
        period_end=body.period_end,
    )
    return JSONResponse(
        content={
            "id": report_id,
            "type": "executive",
            "title": body.title,
            "subject_id": None,
            "period_start": body.period_start,
            "period_end": body.period_end,
            "created_at": generated_at,
        },
        status_code=201,
    )


@router.get("")
async def list_reports(request: Request) -> JSONResponse:
    """
    GET /api/reports — list all stored reports.

    Strips pdf_b64 from content_json before returning (metadata only).
    """
    stores = request.app.state.stores
    reports: list[dict[str, Any]] = await asyncio.to_thread(stores.sqlite.list_reports)
    # Strip large pdf_b64 field — callers use /pdf endpoint to download
    stripped = [_strip_pdf_b64(r) for r in reports]
    return JSONResponse(content={"reports": stripped})


@router.get("/compliance")
async def get_compliance_export(
    request: Request,
    framework: str = Query(..., description="nist-csf | thehive"),
) -> Response:
    """
    GET /api/reports/compliance?framework=nist-csf|thehive

    Returns a downloadable ZIP archive formatted for the specified compliance framework.

    - nist-csf: Six JSON evidence files (one per NIST CSF 2.0 function) + summary.html
    - thehive:  TheHive 5 Alert + Case JSON records for all investigations
    - Unknown framework: 400 with descriptive error
    """
    stores = request.app.state.stores

    # ------------------------------------------------------------------
    # Shared SQLite helpers (run in asyncio.to_thread)
    # ------------------------------------------------------------------

    def _fetch_detections(conn: Any) -> list[dict]:
        rows = conn.execute(
            "SELECT id, rule_id, rule_name, severity, attack_technique, attack_tactic, created_at "
            "FROM detections ORDER BY created_at DESC LIMIT 500"
        ).fetchall()
        return [dict(r) for r in rows]

    def _fetch_investigations(conn: Any) -> list[dict]:
        rows = conn.execute(
            "SELECT case_id, title, case_status, created_at, updated_at, analyst_notes "
            "FROM investigation_cases ORDER BY created_at DESC LIMIT 200"
        ).fetchall()
        return [dict(r) for r in rows]

    def _fetch_playbook_runs(conn: Any) -> list[dict]:
        rows = conn.execute(
            "SELECT run_id, playbook_id, investigation_id, status, started_at, completed_at "
            "FROM playbook_runs ORDER BY started_at DESC LIMIT 200"
        ).fetchall()
        return [dict(r) for r in rows]

    def _fetch_reports_list(conn: Any) -> list[dict]:
        rows = conn.execute(
            "SELECT id, type, title, created_at FROM reports ORDER BY created_at DESC LIMIT 100"
        ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # NIST CSF 2.0 path
    # ------------------------------------------------------------------

    if framework == "nist-csf":
        conn = stores.sqlite._conn
        detections, investigations, playbook_runs, reports_list = await asyncio.gather(
            asyncio.to_thread(_fetch_detections, conn),
            asyncio.to_thread(_fetch_investigations, conn),
            asyncio.to_thread(_fetch_playbook_runs, conn),
            asyncio.to_thread(_fetch_reports_list, conn),
        )

        # KPI evidence from DuckDB (graceful fallback if table missing)
        try:
            kpi_rows = await stores.duckdb.fetch_all(
                "SELECT * FROM daily_kpi_snapshots ORDER BY snapshot_date DESC LIMIT 90"
            )
        except Exception:
            kpi_rows = []

        evidence = {
            "GOVERN": {"kpi_snapshots": [dict(r) for r in kpi_rows]},
            "IDENTIFY": {
                "detections": detections,
                "technique_count": len(
                    {d["attack_technique"] for d in detections if d.get("attack_technique")}
                ),
            },
            "PROTECT": {
                "playbook_runs_completed": [r for r in playbook_runs if r["status"] == "completed"],
            },
            "DETECT": {
                "detections": detections,
                "rules_fired": len({d["rule_id"] for d in detections}),
            },
            "RESPOND": {
                "investigations": investigations,
                "playbook_runs": playbook_runs,
            },
            "RECOVER": {
                "investigations_resolved": [
                    i for i in investigations if i["case_status"] in ("resolved", "closed")
                ],
                "playbook_runs_completed": [r for r in playbook_runs if r["status"] == "completed"],
            },
        }

        rows_html = "".join(
            f"<tr><td>{func}</td><td>{len(data if isinstance(data, list) else list(data.values()))} items</td></tr>"
            for func, data in evidence.items()
        )
        # Build per-function summary rows using top-level item counts
        func_summary_rows = {
            "GOVERN": len(evidence["GOVERN"]["kpi_snapshots"]),
            "IDENTIFY": len(evidence["IDENTIFY"]["detections"]),
            "PROTECT": len(evidence["PROTECT"]["playbook_runs_completed"]),
            "DETECT": len(evidence["DETECT"]["detections"]),
            "RESPOND": len(evidence["RESPOND"]["investigations"]),
            "RECOVER": len(evidence["RECOVER"]["investigations_resolved"]),
        }
        rows_html = "".join(
            f"<tr><td>{func}</td><td>{count} items</td></tr>"
            for func, count in func_summary_rows.items()
        )
        summary_html = (
            "<!DOCTYPE html><html><head><meta charset=\"utf-8\">"
            "<title>NIST CSF 2.0 Evidence Package</title>"
            "<style>body{font-family:sans-serif;max-width:900px;margin:40px auto}"
            "table{border-collapse:collapse;width:100%}"
            "td,th{border:1px solid #ccc;padding:8px;text-align:left}"
            "th{background:#f0f0f0}</style>"
            "</head><body>"
            "<h1>NIST CSF 2.0 Evidence Package</h1>"
            f"<p>Generated: {datetime.now(timezone.utc).isoformat()}</p>"
            "<table><tr><th>CSF Function</th><th>Evidence Items</th></tr>"
            f"{rows_html}"
            "</table></body></html>"
        )

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for func, data in evidence.items():
                zf.writestr(f"nist-csf/{func.lower()}.json", json.dumps(data, indent=2, default=str))
            zf.writestr("summary.html", summary_html)
        buf.seek(0)
        zip_bytes = buf.read()
        filename = f"nist-csf-evidence-{datetime.now(timezone.utc).strftime('%Y%m%d')}.zip"
        return Response(
            content=zip_bytes,
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    # ------------------------------------------------------------------
    # TheHive path
    # ------------------------------------------------------------------

    if framework == "thehive":
        conn = stores.sqlite._conn
        investigations = await asyncio.to_thread(_fetch_investigations, conn)

        alerts = [
            {
                "title": inv["title"],
                "description": inv.get("analyst_notes", "") or "",
                "severity": 2,
                "tags": ["ai-soc-brain", inv["case_status"]],
                "source": "AI-SOC-Brain",
                "sourceRef": inv["case_id"],
                "type": "internal",
                "date": inv["created_at"],
            }
            for inv in investigations
        ]
        cases = [
            {
                "title": inv["title"],
                "description": inv.get("analyst_notes", "") or "",
                "severity": 2,
                "tags": ["ai-soc-brain"],
                "status": "Resolved" if inv["case_status"] in ("resolved", "closed") else "Open",
                "startDate": inv["created_at"],
                "endDate": inv.get("updated_at"),
            }
            for inv in investigations
        ]

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("thehive/alerts.json", json.dumps(alerts, indent=2, default=str))
            zf.writestr("thehive/cases.json", json.dumps(cases, indent=2, default=str))
        buf.seek(0)
        filename = f"thehive-export-{datetime.now(timezone.utc).strftime('%Y%m%d')}.zip"
        return Response(
            content=buf.read(),
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    # ------------------------------------------------------------------
    # Unknown framework
    # ------------------------------------------------------------------

    raise HTTPException(
        status_code=400,
        detail=f"Unknown framework '{framework}'. Supported: nist-csf, thehive",
    )


# ---------------------------------------------------------------------------
# Helper: severity string → TheHive integer severity
# ---------------------------------------------------------------------------


def _severity_to_int(severity: str) -> int:
    return {"low": 1, "medium": 2, "high": 3, "critical": 3}.get(
        severity.lower() if severity else "", 2
    )


@router.get("/{report_id}/pdf")
async def download_report_pdf(report_id: str, request: Request) -> Response:
    """
    GET /api/reports/{report_id}/pdf — download the rendered PDF binary.

    Returns 404 if the report does not exist.
    Returns 422 if the report has no PDF stored.
    """
    stores = request.app.state.stores
    report: dict[str, Any] | None = await asyncio.to_thread(
        stores.sqlite.get_report, report_id
    )
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")

    try:
        content = json.loads(report.get("content_json", "{}"))
        pdf_b64 = content.get("pdf_b64", "")
        if not pdf_b64:
            raise HTTPException(status_code=422, detail="Report has no PDF stored")
        pdf_bytes = base64.b64decode(pdf_b64)
    except (json.JSONDecodeError, Exception) as exc:
        log.error("Failed to decode PDF for report", report_id=report_id, error=str(exc))
        raise HTTPException(status_code=500, detail="Failed to decode PDF") from exc

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="report-{report_id}.pdf"'
        },
    )
