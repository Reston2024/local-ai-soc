"""
Wave 0 test stubs for Phase 33 feed workers.
P33-T01 (Feodo), P33-T02 (CISA KEV), P33-T03 (ThreatFox).

All external calls are mocked — no real network I/O.
"""

from __future__ import annotations

import asyncio
import csv
import io
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Try importing feed workers — skip if not yet implemented
# ---------------------------------------------------------------------------
try:
    from backend.services.intel.feed_sync import (
        CisaKevWorker,
        FeodoWorker,
        ThreatFoxWorker,
    )
    _FEED_SYNC_AVAILABLE = True
except ImportError:
    _FEED_SYNC_AVAILABLE = False

# ---------------------------------------------------------------------------
# Feodo CSV fixture
# ---------------------------------------------------------------------------
_FEODO_CSV = """\
# first_seen_utc,dst_ip,dst_port,c2_status,last_online,malware
2024-01-01 00:00:00,1.2.3.4,8080,online,2024-01-01,Emotet
2024-01-02 00:00:00,5.6.7.8,443,offline,2024-01-02,QakBot
"""

_CISA_KEV_JSON = json.dumps({
    "vulnerabilities": [
        {"cveID": "CVE-2024-0001", "dateAdded": "2024-01-01", "vulnerabilityName": "TestVuln1"},
        {"cveID": "CVE-2024-0002", "dateAdded": "2024-01-02", "vulnerabilityName": "TestVuln2"},
    ]
})

_THREATFOX_CSV = """\
# first_seen_utc,ioc_id,ioc_value,ioc_type,malware_printable,confidence_level,tags
2024-01-01 00:00:00,1001,1.2.3.4:4000,ip:port,Emotet,75,botnet
2024-01-02 00:00:00,1002,5.6.7.8:9000,ip:port,QakBot,80,c2
"""


# ---------------------------------------------------------------------------
# test_feodo_csv_parse — parse Feodo CSV into list of dicts
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not _FEED_SYNC_AVAILABLE, reason="Wave 0 stub — implementation in Task 2/3")
def test_feodo_csv_parse():
    """Feodo CSV parser produces list of dicts with ioc_value, ioc_type, malware_family."""
    worker = FeodoWorker.__new__(FeodoWorker)

    result = worker._parse_feodo_csv(_FEODO_CSV)

    assert len(result) == 2
    row = result[0]
    assert row["ioc_value"] == "1.2.3.4"
    assert row["ioc_type"] == "ip"
    assert row["malware_family"] == "Emotet"

    row2 = result[1]
    assert row2["ioc_value"] == "5.6.7.8"
    assert row2["malware_family"] == "QakBot"


# ---------------------------------------------------------------------------
# test_feodo_sync_success — mock httpx + IocStore, assert _sync returns True
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not _FEED_SYNC_AVAILABLE, reason="Wave 0 stub — implementation in Task 2/3")
@pytest.mark.asyncio
async def test_feodo_sync_success():
    """FeodoWorker._sync() returns True and calls upsert_ioc for each non-comment row."""
    mock_ioc_store = MagicMock()
    mock_ioc_store.upsert_ioc = MagicMock(return_value=False)
    mock_conn = MagicMock()
    mock_conn.execute = MagicMock()

    worker = FeodoWorker(mock_ioc_store, mock_conn)

    mock_response = MagicMock()
    mock_response.text = _FEODO_CSV
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.get", return_value=mock_response):
        result = await worker._sync()

    assert result is True
    # 2 non-comment rows
    assert mock_ioc_store.upsert_ioc.call_count == 2


# ---------------------------------------------------------------------------
# test_cisa_kev_parse — parse CISA KEV JSON
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not _FEED_SYNC_AVAILABLE, reason="Wave 0 stub — implementation in Task 2/3")
def test_cisa_kev_parse():
    """CISA KEV parser produces list with ioc_value=cveID, ioc_type='cve', confidence=40."""
    worker = CisaKevWorker.__new__(CisaKevWorker)

    result = worker._parse_kev_json(_CISA_KEV_JSON)

    assert len(result) == 2
    row = result[0]
    assert row["ioc_value"] == "CVE-2024-0001"
    assert row["ioc_type"] == "cve"
    assert row["confidence"] == 40


# ---------------------------------------------------------------------------
# test_threatfox_csv_parse — parse ThreatFox CSV
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not _FEED_SYNC_AVAILABLE, reason="Wave 0 stub — implementation in Task 2/3")
def test_threatfox_csv_parse():
    """ThreatFox CSV parser stores ioc_value as-is, extracts bare_ip, confidence=50."""
    worker = ThreatFoxWorker.__new__(ThreatFoxWorker)

    result = worker._parse_threatfox_csv(_THREATFOX_CSV)

    assert len(result) == 2
    row = result[0]
    assert row["ioc_value"] == "1.2.3.4:4000"
    assert row["bare_ip"] == "1.2.3.4"
    assert row["confidence"] == 50

    row2 = result[1]
    assert row2["ioc_value"] == "5.6.7.8:9000"
    assert row2["bare_ip"] == "5.6.7.8"
