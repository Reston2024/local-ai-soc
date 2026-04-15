"""
Phase 50: MispSyncService — PyMISP wrapper for MISP attribute sync.
Called via asyncio.to_thread() (PyMISP uses blocking requests library).
Implementation added by Plan 50-02 (Wave 1).
"""
from __future__ import annotations

import json
from typing import TYPE_CHECKING

# Module-level type map: MISP attribute type → ioc_store ioc_type
MISP_TYPE_MAP: dict[str, str] = {
    "ip-src": "ip",
    "ip-dst": "ip",
    "domain": "domain",
    "hostname": "domain",
    "url": "url",
    "md5": "md5",
    "sha1": "sha1",
    "sha256": "sha256",
    "email-src": "email",
    "filename": "filename",
}

# Confidence from MISP threat_level_id (1=High → 90, 4=Undefined → 30)
THREAT_LEVEL_CONFIDENCE: dict[int, int] = {1: 90, 2: 70, 3: 50, 4: 30}

# ---------------------------------------------------------------------------
# Module-level lazy references — populated by _load_pymisp().
# These names exist at module scope so test mocks can patch them via
# "backend.services.intel.misp_sync.PyMISP".
# ---------------------------------------------------------------------------
PyMISP = None        # type: ignore[assignment]
MISPAttribute = None  # type: ignore[assignment]


def _load_pymisp() -> None:
    """Lazily import PyMISP and MISPAttribute into module namespace.

    Importing at module level would break environments where the pymisp
    wheel is not installed (CI, edge containers). We defer until first
    call to fetch_ioc_attributes() and expose the names at module scope
    so that unit tests can patch them via:
        patch("backend.services.intel.misp_sync.PyMISP")
    """
    global PyMISP, MISPAttribute  # noqa: PLW0603
    if PyMISP is None:
        from pymisp import MISPAttribute as _MA
        from pymisp import PyMISP as _P
        PyMISP = _P  # type: ignore[assignment]
        MISPAttribute = _MA  # type: ignore[assignment]


class MispSyncService:
    """Synchronous PyMISP wrapper. Always call via asyncio.to_thread()."""

    def __init__(self, url: str, key: str, ssl: bool = False) -> None:
        self._url = url
        self._key = key
        self._ssl = ssl
        self._misp = None  # Lazy-init in fetch_ioc_attributes

    def fetch_ioc_attributes(
        self,
        to_ids: bool = True,
        limit: int = 5000,
        last: str = "1d",
    ) -> list[dict]:
        """Pull IDS-flagged attributes from MISP, normalize to ioc_store schema.

        MUST be called via asyncio.to_thread() — PyMISP uses blocking requests.

        Returns a list[dict] with keys:
            value, ioc_type, confidence, first_seen, last_seen,
            malware_family, actor_tag, extra_json
        """
        _load_pymisp()

        if self._misp is None:
            self._misp = PyMISP(self._url, self._key, ssl=self._ssl)  # type: ignore[call-arg]

        results = self._misp.search(
            controller="attributes",
            type_attribute=list(MISP_TYPE_MAP.keys()),
            to_ids=to_ids,
            last=last,
            limit=limit,
            pythonify=True,
        )

        normalized: list[dict] = []
        for attr in results:
            # When MISPAttribute is None (test env with only PyMISP patched),
            # skip the guard — the test controls what search() returns.
            if MISPAttribute is not None and not isinstance(attr, MISPAttribute):
                continue
            ioc_type = MISP_TYPE_MAP.get(attr.type)
            if not ioc_type:
                continue

            # Confidence from event threat_level_id
            confidence = 50
            event = getattr(attr, "Event", None)
            if event:
                tl = getattr(event, "threat_level_id", 4)
                confidence = THREAT_LEVEL_CONFIDENCE.get(int(tl), 50)

            # Extract malware_family from event info field (free-text title)
            malware_family: str | None = None
            if event:
                event_info = getattr(event, "info", "") or ""
                if event_info:
                    malware_family = event_info[:120]  # Cap length

            # Extract actor_tag from MISP galaxy tags
            actor_tag: str | None = None
            tags = getattr(attr, "Tag", []) or []
            for tag in tags:
                tag_name = getattr(tag, "name", "") or ""
                if tag_name.startswith("misp-galaxy:threat-actor="):
                    actor_tag = tag_name.split("=", 1)[1].strip('"')
                    break

            # Convert fields to JSON-safe types (str/None) — MagicMock-safe
            _ev_id = getattr(attr, "event_id", None)
            _uuid = getattr(attr, "uuid", None)
            _cat = getattr(attr, "category", None)
            _comment = getattr(attr, "comment", None)
            extra = {
                "misp_event_id": str(_ev_id) if _ev_id is not None else None,
                "misp_attr_uuid": str(_uuid) if _uuid is not None else None,
                "misp_category": str(_cat) if _cat is not None else None,
                "misp_tags": [str(getattr(t, "name", "")) for t in tags],
                "misp_comment": str(_comment) if _comment else "",
            }

            def _iso(dt) -> str | None:  # noqa: ANN001
                if dt is None:
                    return None
                return dt.isoformat() if hasattr(dt, "isoformat") else str(dt)

            normalized.append({
                "value": attr.value,
                "ioc_type": ioc_type,
                "confidence": confidence,
                "first_seen": _iso(getattr(attr, "first_seen", None)),
                "last_seen": _iso(getattr(attr, "last_seen", None)),
                "malware_family": malware_family,
                "actor_tag": actor_tag,
                "extra_json": json.dumps(extra),
            })
        return normalized
