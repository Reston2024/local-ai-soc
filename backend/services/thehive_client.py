"""
TheHive 5 case management client — Phase 52.

Wraps thehive4py 2.x (synchronous/blocking) with asyncio.to_thread() for
async-safe use in the FastAPI event loop.

Lazy import pattern: _CLIENT_AVAILABLE = False when thehive4py is absent.
The module is always importable; functions degrade gracefully.
"""
from __future__ import annotations

import asyncio
import json
import sqlite3
from datetime import datetime, timezone
from typing import Any

from backend.core.config import settings
from backend.core.logging import get_logger

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# Lazy import — thehive4py may not be installed in all environments
# ---------------------------------------------------------------------------

_CLIENT_AVAILABLE = False
TheHiveApi = None  # type: ignore[assignment]

try:
    from thehive4py import TheHiveApi  # type: ignore[assignment]
    from thehive4py.query.filters import Eq  # noqa: F401
    _CLIENT_AVAILABLE = True
except ImportError:
    pass


# ---------------------------------------------------------------------------
# TheHiveClient — async-safe wrapper around thehive4py.TheHiveApi
# ---------------------------------------------------------------------------

class TheHiveClient:
    """Async-safe wrapper around the synchronous thehive4py.TheHiveApi.

    All blocking thehive4py calls are wrapped in asyncio.to_thread().
    ping() is the only synchronous method (used for health checks from
    sync contexts and unit tests).
    """

    def __init__(self, url: str, api_key: str) -> None:
        if TheHiveApi is None:
            raise ImportError(
                "thehive4py is not installed. Run: uv add thehive4py==2.0.3"
            )
        self._api = TheHiveApi(url=url, apikey=api_key)

    def ping(self) -> bool:
        """Return True if TheHive is reachable (synchronous).

        Uses self._api.case.find() with an empty filter as a liveness probe.
        Returns False (never raises) when TheHive is unreachable.
        """
        try:
            self._api.case.find(filters=None)
            return True
        except Exception:
            return False

    async def create_case(self, case_dict: dict) -> dict:
        """Create a TheHive case and return the created case dict (includes _id)."""
        return await asyncio.to_thread(self._api.case.create, case=case_dict)

    async def create_observable(self, case_id: str, obs_dict: dict) -> dict:
        """Add an observable to an existing case."""
        return await asyncio.to_thread(
            self._api.case.create_observable,
            case_id=case_id,
            observable=obs_dict,
        )

    async def find_resolved_cases(self) -> list[dict]:
        """Return all Resolved cases from TheHive."""
        try:
            from thehive4py.query.filters import Eq as _Eq
            filters = _Eq("status", "Resolved")
        except ImportError:
            filters = None  # type: ignore[assignment]
        return await asyncio.to_thread(self._api.case.find, filters=filters)


# ---------------------------------------------------------------------------
# Case payload builder
# ---------------------------------------------------------------------------

_SEVERITY_MAP: dict[str, int] = {
    "low": 1,
    "medium": 2,
    "high": 3,
    "critical": 4,
}


def build_case_payload(detection: dict) -> dict:
    """Map a SOC Brain detection dict to a TheHive 5 case payload (dict).

    Severity mapping:
      high     -> 3 (TheHive High)
      critical -> 4 (TheHive Critical)
      medium   -> 2
      low      -> 1

    TLP=2 (AMBER), PAP=2 (AMBER) per organisational policy.
    """
    sev = detection.get("severity", "medium").lower()
    thehive_severity = _SEVERITY_MAP.get(sev, 2)

    rule_name = detection.get("rule_name", "Unknown Rule")
    src_ip = detection.get("src_ip") or "N/A"
    detection_id = detection.get("id", "")
    attack_technique = detection.get("attack_technique") or "N/A"
    attack_tactic = detection.get("attack_tactic") or "N/A"

    title = f"[{sev.upper()}] {rule_name} — {src_ip}"
    description = (
        f"**Rule:** {rule_name}\n"
        f"**Detection ID:** {detection_id}\n"
        f"**ATT&CK:** {attack_technique} — {attack_tactic}\n"
        f"**Source:** SOC Brain auto-case"
    )

    tags = [
        "soc-brain",
        detection.get("attack_technique", ""),
        detection.get("attack_tactic", ""),
    ]
    # Filter out empty/None tags
    tags = [t for t in tags if t]

    return {
        "title": title,
        "description": description,
        "severity": thehive_severity,
        "tags": tags,
        "tlp": 2,   # TLP:AMBER
        "pap": 2,   # PAP:AMBER
        "status": "New",
    }


# ---------------------------------------------------------------------------
# Observable builder
# ---------------------------------------------------------------------------

def build_observables(detection: dict) -> list[dict]:
    """Build TheHive observable dicts from a detection record.

    Only includes observables where the source field is non-empty/non-None.

    Returns list of dicts with keys: dataType, data, [message], ioc.
    """
    observables: list[dict] = []

    src_ip = detection.get("src_ip")
    if src_ip:
        observables.append({
            "dataType": "ip",
            "data": src_ip,
            "ioc": False,
            "message": "Source IP from detection",
        })

    rule_name = detection.get("rule_name")
    if rule_name:
        observables.append({
            "dataType": "other",
            "data": rule_name,
            "ioc": False,
            "message": "Sigma rule name",
        })

    attack_technique = detection.get("attack_technique")
    if attack_technique:
        observables.append({
            "dataType": "other",
            "data": attack_technique,
            "ioc": False,
            "message": "ATT&CK technique",
        })

    ioc_actor_tag = detection.get("ioc_actor_tag")
    if ioc_actor_tag:
        observables.append({
            "dataType": "other",
            "data": ioc_actor_tag,
            "ioc": True,
            "message": "MISP actor tag",
        })

    return observables


# ---------------------------------------------------------------------------
# Synchronous SQLite helpers (called via asyncio.to_thread in production,
# called directly in unit tests for simplicity)
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _save_thehive_case_id(
    conn: sqlite3.Connection,
    detection_id: str,
    case_id: str,
    case_num: int | None,
    status: str,
) -> None:
    """Write thehive_case_id, thehive_case_num, thehive_status back to detections row."""
    conn.execute(
        """
        UPDATE detections
           SET thehive_case_id  = ?,
               thehive_case_num = ?,
               thehive_status   = ?
         WHERE id = ?
        """,
        (case_id, case_num, status, detection_id),
    )
    conn.commit()


def _enqueue_pending_case(
    conn: sqlite3.Connection,
    detection_id: str,
    payload_json: str,
) -> None:
    """Insert a row into thehive_pending_cases for retry on next cycle.

    The detection_json column stores a JSON blob combining detection_id and
    the full case+observables payload for retry processing.
    """
    detection_json = json.dumps({
        "detection_id": detection_id,
        "payload": json.loads(payload_json) if isinstance(payload_json, str) else payload_json,
    })
    conn.execute(
        "INSERT INTO thehive_pending_cases (detection_json, created_at) VALUES (?, ?)",
        (detection_json, _now_iso()),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# _maybe_create_thehive_case — synchronous fire-and-forget helper
#
# Synchronous so unit tests can call it directly without an event loop.
# Production callers should wrap in asyncio.to_thread() or call from
# a non-async context.
# ---------------------------------------------------------------------------

def _maybe_create_thehive_case(
    thehive_client: "TheHiveClient",
    detection: dict,
    *,
    suppress_rules: list[str] | None = None,
    db_conn: sqlite3.Connection | None = None,
) -> None:
    """Attempt to create a TheHive case for a High/Critical detection.

    Non-fatal: on any failure, enqueues the detection in thehive_pending_cases
    for retry on the next cycle.

    Args:
        thehive_client:  Initialised TheHiveClient instance.
        detection:       SOC Brain detection dict (must have 'severity', 'rule_id').
        suppress_rules:  Optional list of rule_id values that skip case creation.
                         Defaults to settings.THEHIVE_SUPPRESS_RULES if omitted.
        db_conn:         Optional sqlite3.Connection for enqueuing failed cases.
                         Pass None to skip retry-queue behaviour (testing only).
    """
    severity = detection.get("severity", "").lower()
    if severity not in ("high", "critical"):
        return

    rule_id = detection.get("rule_id", "")
    effective_suppress = suppress_rules if suppress_rules is not None else settings.THEHIVE_SUPPRESS_RULES
    if rule_id in effective_suppress:
        return

    try:
        case_payload = build_case_payload(detection)
        created: dict[str, Any] = thehive_client._api.case.create(case=case_payload)
        case_id = created["_id"]
        case_num = created.get("number") or created.get("caseId")

        # Add observables — non-fatal per observable
        for obs in build_observables(detection):
            try:
                thehive_client._api.case.create_observable(
                    case_id=case_id, observable=obs
                )
            except Exception as exc:
                log.warning("Failed to add observable", observable=obs, error=str(exc))

        if db_conn is not None:
            _save_thehive_case_id(db_conn, detection.get("id", ""), case_id, case_num, "New")

    except Exception as exc:
        log.warning(
            "TheHive case creation failed, queuing for retry",
            detection_id=detection.get("id"),
            error=str(exc),
        )
        if db_conn is not None:
            payload_json = json.dumps({
                "case": build_case_payload(detection),
                "observables": build_observables(detection),
            })
            # Pass the already-serialized JSON string; _enqueue_pending_case
            # will decode it and re-encode into the detection_json column blob
            _enqueue_pending_case(db_conn, detection.get("id", ""), payload_json)
