"""
Phase 50 Wave 0 stubs: MispSyncService + MispWorker tests.
Tests 1-2 (type/confidence maps) pass immediately.
Tests 3-5 fail until Plan 50-02 implements fetch_ioc_attributes + MispWorker.
"""
from __future__ import annotations

import asyncio
import sqlite3
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.unit

# importorskip at module level so entire file skips atomically
misp_sync = pytest.importorskip("backend.services.intel.misp_sync")
MispSyncService = misp_sync.MispSyncService
MISP_TYPE_MAP = misp_sync.MISP_TYPE_MAP
THREAT_LEVEL_CONFIDENCE = misp_sync.THREAT_LEVEL_CONFIDENCE

try:
    from backend.services.intel.feed_sync import MispWorker
    _WORKER_AVAILABLE = True
except ImportError:
    _WORKER_AVAILABLE = False


def test_attribute_type_mapping():
    """MISP_TYPE_MAP covers all 10 expected attribute types."""
    expected_keys = {
        "ip-src", "ip-dst", "domain", "hostname", "url",
        "md5", "sha1", "sha256", "email-src", "filename",
    }
    assert expected_keys == set(MISP_TYPE_MAP.keys())
    assert MISP_TYPE_MAP["ip-src"] == "ip"
    assert MISP_TYPE_MAP["ip-dst"] == "ip"
    assert MISP_TYPE_MAP["hostname"] == "domain"


def test_confidence_mapping():
    """THREAT_LEVEL_CONFIDENCE maps 1→90, 2→70, 3→50, 4→30."""
    assert THREAT_LEVEL_CONFIDENCE[1] == 90
    assert THREAT_LEVEL_CONFIDENCE[2] == 70
    assert THREAT_LEVEL_CONFIDENCE[3] == 50
    assert THREAT_LEVEL_CONFIDENCE[4] == 30


@pytest.mark.skipif(True, reason="Wave 0 stub — fetch_ioc_attributes raises NotImplementedError until Plan 50-02")
def test_fetch_ioc_attributes_returns_list():
    """fetch_ioc_attributes() returns a list of normalized dicts."""
    mock_attr = MagicMock()
    mock_attr.type = "ip-dst"
    mock_attr.value = "10.0.0.1"
    mock_attr.uuid = "abc-123"
    mock_attr.category = "Network activity"
    mock_attr.comment = ""
    mock_attr.first_seen = None
    mock_attr.last_seen = None
    mock_attr.Tag = []
    mock_event = MagicMock()
    mock_event.threat_level_id = 2
    mock_attr.Event = mock_event

    svc = MispSyncService("http://localhost", "fakekey")
    with patch("backend.services.intel.misp_sync.PyMISP") as mock_pymisp:
        mock_pymisp.return_value.search.return_value = [mock_attr]
        result = svc.fetch_ioc_attributes()
    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0]["ioc_type"] == "ip"
    assert result[0]["confidence"] == 70


@pytest.mark.skipif(not _WORKER_AVAILABLE, reason="Wave 0 stub — MispWorker not yet in feed_sync.py (Plan 50-02)")
def test_misp_worker_sync():
    """MispWorker._sync() calls ioc_store.upsert_ioc for each returned attribute."""
    conn = sqlite3.connect(":memory:")
    conn.execute(
        "CREATE TABLE system_kv (key TEXT PRIMARY KEY, value TEXT, updated_at TEXT)"
    )
    ioc_store = MagicMock()
    ioc_store.upsert_ioc.return_value = False

    worker = MispWorker(ioc_store, conn, misp_url="http://localhost", misp_key="fake")
    fake_attrs = [
        {
            "value": "192.168.1.1",
            "ioc_type": "ip",
            "confidence": 70,
            "first_seen": None,
            "last_seen": None,
            "malware_family": None,
            "actor_tag": None,
            "extra_json": "{}",
        }
    ]
    with patch(
        "backend.services.intel.misp_sync.MispSyncService.fetch_ioc_attributes",
        return_value=fake_attrs,
    ):
        result = asyncio.get_event_loop().run_until_complete(worker._sync())
    assert result is True
    ioc_store.upsert_ioc.assert_called_once()


@pytest.mark.skipif(not _WORKER_AVAILABLE, reason="Wave 0 stub — MispWorker not yet in feed_sync.py (Plan 50-02)")
def test_retroactive_trigger():
    """MispWorker._sync() calls _trigger_retroactive_scan for newly inserted IOCs."""
    conn = sqlite3.connect(":memory:")
    conn.execute(
        "CREATE TABLE system_kv (key TEXT PRIMARY KEY, value TEXT, updated_at TEXT)"
    )
    ioc_store = MagicMock()
    ioc_store.upsert_ioc.return_value = True  # True = new IOC

    worker = MispWorker(ioc_store, conn, misp_url="http://localhost", misp_key="fake")
    fake_attrs = [
        {
            "value": "evil.example.com",
            "ioc_type": "domain",
            "confidence": 90,
            "first_seen": None,
            "last_seen": None,
            "malware_family": None,
            "actor_tag": None,
            "extra_json": "{}",
        }
    ]
    with patch(
        "backend.services.intel.misp_sync.MispSyncService.fetch_ioc_attributes",
        return_value=fake_attrs,
    ), patch.object(worker, "_trigger_retroactive_scan", return_value=None) as mock_retro:
        asyncio.get_event_loop().run_until_complete(worker._sync())
    mock_retro.assert_called_once()
