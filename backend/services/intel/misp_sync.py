"""
Phase 50: MispSyncService — PyMISP wrapper for MISP attribute sync.
Called via asyncio.to_thread() (PyMISP uses blocking requests library).
Implementation filled in by Plan 50-02.
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
        Raises NotImplementedError until Plan 50-02 implements this."""
        raise NotImplementedError("Wave 1 implementation pending (Plan 50-02)")
