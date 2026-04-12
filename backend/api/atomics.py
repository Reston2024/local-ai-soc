"""
Atomics API router — Phase 40.
GET /api/atomics — returns full ART catalog grouped by technique with coverage.
POST /api/atomics/validate — added in Plan 03.
"""
from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/atomics")
async def get_atomics(request: Request):
    atomics_store = request.app.state.atomics_store
    # Use sqlite_store._conn for detections coverage query; fall back to
    # atomics_store._conn (same DB in tests / allows graceful degradation)
    try:
        sqlite_conn = request.app.state.sqlite_store._conn
    except AttributeError:
        sqlite_conn = atomics_store._conn

    # Fetch all data in parallel threads
    techniques, all_tests, validation_results = await asyncio.gather(
        asyncio.to_thread(atomics_store.list_techniques),
        asyncio.to_thread(_get_all_tests, atomics_store),
        asyncio.to_thread(atomics_store.get_validation_results),
    )

    # Coverage computation (three-tier: validated > detected > none)
    # Validated set: any test for this technique has passed
    validated_techs = {
        tid for (tid, _), r in validation_results.items() if r["verdict"] == "pass"
    }
    # Detected set: any detection with matching attack_technique exists (all time)
    detected_techs = await asyncio.to_thread(_get_detected_techniques, sqlite_conn)

    # Group tests by technique_id
    tests_by_technique: dict[str, list] = {}
    for test in all_tests:
        tid = test["technique_id"]
        tests_by_technique.setdefault(tid, []).append(test)

    result_techniques = []
    for tech in techniques:
        tid = tech["technique_id"]
        if tid in validated_techs:
            coverage = "validated"
        elif tid in detected_techs:
            coverage = "detected"
        else:
            coverage = "none"

        tests_out = []
        for t in tests_by_technique.get(tid, []):
            test_num = t["test_number"]
            vkey = (tid, test_num)
            vr = validation_results.get(vkey)
            tests_out.append({
                "test_number": test_num,
                "test_name": t["test_name"],
                "supported_platforms": json.loads(t["supported_platforms"] or "[]"),
                "executor_name": t["executor_name"],
                "elevation_required": bool(t["elevation_required"]),
                "command": t["command"],
                "cleanup_command": t["cleanup_command"],
                "prereq_command": t["prereq_command"],
                "invoke_command": f"Invoke-AtomicTest {tid} -TestNumbers {test_num}",
                "invoke_prereq": f"Invoke-AtomicTest {tid} -TestNumbers {test_num} -CheckPrereqs",
                "invoke_cleanup": f"Invoke-AtomicTest {tid} -TestNumbers {test_num} -Cleanup",
                "validation": {"verdict": vr["verdict"], "validated_at": vr["validated_at"]} if vr else None,
            })
        result_techniques.append({
            "technique_id": tid,
            "display_name": tech["display_name"],
            "coverage": coverage,
            "tests": tests_out,
        })

    total_tests = sum(len(v) for v in tests_by_technique.values())
    return {
        "techniques": result_techniques,
        "total_techniques": len(result_techniques),
        "total_tests": total_tests,
    }


def _get_all_tests(atomics_store) -> list[dict]:
    rows = atomics_store._conn.execute(
        "SELECT * FROM atomics ORDER BY technique_id, test_number"
    ).fetchall()
    return [dict(r) for r in rows]


def _get_detected_techniques(conn) -> set[str]:
    """Return set of technique_ids that have any matching detection (all time)."""
    try:
        rows = conn.execute(
            "SELECT DISTINCT attack_technique FROM detections WHERE attack_technique IS NOT NULL AND attack_technique != ''"
        ).fetchall()
        result = set()
        for row in rows:
            tid = row[0] if not hasattr(row, 'keys') else row["attack_technique"]
            if tid:
                result.add(tid)
                # Also add parent technique for sub-techniques
                parent = tid.split(".")[0]
                result.add(parent)
        return result
    except Exception:
        return set()
