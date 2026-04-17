"""
Detection Quality API — TP/FP metrics per Sigma rule.

Endpoint:
  GET /api/detections/quality  — aggregate detection quality metrics with MITRE coverage
"""
from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.core.logging import get_logger

log = get_logger(__name__)

router = APIRouter(prefix="/detections", tags=["detections"])


# ---------------------------------------------------------------------------
# Helper — pure sync, called via asyncio.to_thread
# ---------------------------------------------------------------------------


def _compute_quality_metrics(sqlite_conn) -> dict[str, Any]:
    """Query SQLite to compute per-rule and summary quality metrics.

    Never raises — returns zeroed structure on any error.
    """
    try:
        # Per-rule metrics: join detections with feedback
        rows = sqlite_conn.execute(
            """
            SELECT
                d.rule_id,
                d.rule_name,
                COUNT(d.id)                                         AS total_hits,
                MAX(d.created_at)                                   AS last_hit,
                COUNT(f.verdict)                                    AS analyst_reviewed,
                SUM(CASE WHEN f.verdict = 'TP' THEN 1 ELSE 0 END)  AS confirmed_tp,
                SUM(CASE WHEN f.verdict = 'FP' THEN 1 ELSE 0 END)  AS confirmed_fp
            FROM detections d
            LEFT JOIN feedback f ON d.id = f.detection_id
            WHERE d.rule_id IS NOT NULL
            GROUP BY d.rule_id, d.rule_name
            ORDER BY total_hits DESC
            """
        ).fetchall()

        rule_metrics: list[dict[str, Any]] = []
        for row in rows:
            reviewed = row[4] or 0
            tp = row[5] or 0
            fp = row[6] or 0
            tp_rate = round(tp / reviewed, 4) if reviewed else 0.0
            fp_rate = round(fp / reviewed, 4) if reviewed else 0.0
            rule_metrics.append(
                {
                    "rule_id": row[0],
                    "rule_name": row[1],
                    "total_hits": row[2] or 0,
                    "analyst_reviewed": reviewed,
                    "confirmed_tp": tp,
                    "confirmed_fp": fp,
                    "tp_rate": tp_rate,
                    "fp_rate": fp_rate,
                    "last_hit": row[3],
                }
            )

        # Summary aggregates
        total_detections_row = sqlite_conn.execute(
            "SELECT COUNT(*) FROM detections"
        ).fetchone()
        total_detections = total_detections_row[0] if total_detections_row else 0

        total_rules_fired_row = sqlite_conn.execute(
            "SELECT COUNT(DISTINCT rule_id) FROM detections WHERE rule_id IS NOT NULL"
        ).fetchone()
        total_rules_fired = total_rules_fired_row[0] if total_rules_fired_row else 0

        feedback_agg_row = sqlite_conn.execute(
            """
            SELECT
                COUNT(*)                                            AS total_reviewed,
                SUM(CASE WHEN verdict = 'TP' THEN 1 ELSE 0 END)    AS total_tp,
                SUM(CASE WHEN verdict = 'FP' THEN 1 ELSE 0 END)    AS total_fp,
                COUNT(DISTINCT detection_id)                        AS distinct_reviewed
            FROM feedback
            """
        ).fetchone()

        rules_with_feedback_row = sqlite_conn.execute(
            """
            SELECT COUNT(DISTINCT d.rule_id)
            FROM feedback f
            JOIN detections d ON d.id = f.detection_id
            WHERE d.rule_id IS NOT NULL
            """
        ).fetchone()
        rules_with_feedback = rules_with_feedback_row[0] if rules_with_feedback_row else 0

        total_reviewed = feedback_agg_row[0] or 0
        total_tp = feedback_agg_row[1] or 0
        total_fp = feedback_agg_row[2] or 0
        analyst_reviewed = feedback_agg_row[3] or 0

        overall_tp_rate = round(total_tp / total_reviewed, 4) if total_reviewed else 0.0
        overall_fp_rate = round(total_fp / total_reviewed, 4) if total_reviewed else 0.0

        summary = {
            "total_rules_fired": total_rules_fired,
            "rules_with_feedback": rules_with_feedback,
            "overall_tp_rate": overall_tp_rate,
            "overall_fp_rate": overall_fp_rate,
            "total_detections": total_detections,
            "analyst_reviewed": analyst_reviewed,
        }

        # MITRE coverage: distinct non-null tactics and technique count
        mitre_rows = sqlite_conn.execute(
            """
            SELECT DISTINCT attack_tactic, attack_technique
            FROM detections
            WHERE attack_tactic IS NOT NULL OR attack_technique IS NOT NULL
            """
        ).fetchall()

        tactics_covered: list[str] = []
        technique_count = 0
        seen_tactics: set[str] = set()
        seen_techniques: set[str] = set()

        for row in mitre_rows:
            tactic = row[0]
            technique = row[1]
            if tactic and tactic not in seen_tactics:
                seen_tactics.add(tactic)
                tactics_covered.append(tactic)
            if technique and technique not in seen_techniques:
                seen_techniques.add(technique)
                technique_count += 1

        mitre_coverage = {
            "tactics_covered": sorted(tactics_covered),
            "technique_count": technique_count,
        }

        return {
            "rule_metrics": rule_metrics,
            "summary": summary,
            "mitre_coverage": mitre_coverage,
        }

    except Exception as exc:
        log.warning("detection_quality: query failed (returning zeros): %s", exc)
        return {
            "rule_metrics": [],
            "summary": {
                "total_rules_fired": 0,
                "rules_with_feedback": 0,
                "overall_tp_rate": 0.0,
                "overall_fp_rate": 0.0,
                "total_detections": 0,
                "analyst_reviewed": 0,
            },
            "mitre_coverage": {
                "tactics_covered": [],
                "technique_count": 0,
            },
        }


# ---------------------------------------------------------------------------
# GET /api/detections/quality
# ---------------------------------------------------------------------------


@router.get("/quality")
async def get_detection_quality(request: Request) -> JSONResponse:
    """Return detection quality metrics: per-rule TP/FP rates and MITRE coverage.

    Joins the detections table with the feedback (Phase 44) table.
    Never returns 500 — gracefully returns zeroed structure on empty data.
    """
    stores = request.app.state.stores
    result = await asyncio.to_thread(
        _compute_quality_metrics, stores.sqlite._conn
    )
    return JSONResponse(content=result)
