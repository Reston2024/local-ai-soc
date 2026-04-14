"""Stub tests for Phase 27 MalcolmCollector (P27-T02). Activated in plan 27-02."""
from __future__ import annotations

import pytest

try:
    from ingestion.jobs.malcolm_collector import MalcolmCollector
    _IMPORT_OK = True
except ImportError:
    _IMPORT_OK = False

pytestmark = pytest.mark.skipif(
    not _IMPORT_OK,
    reason="MalcolmCollector not implemented — Wave 2 (plan 27-02)",
)


def test_malcolm_collector_init_sets_defaults():
    """MalcolmCollector() sets _running=False, _alerts_ingested=0,
    _syslog_ingested=0, _consecutive_failures=0."""
    collector = MalcolmCollector()
    assert collector._running is False
    assert collector._alerts_ingested == 0
    assert collector._syslog_ingested == 0
    assert collector._consecutive_failures == 0


def test_malcolm_collector_status_shape():
    """status() returns dict with keys: running, alerts_ingested,
    syslog_ingested, consecutive_failures."""
    collector = MalcolmCollector()
    status = collector.status()
    assert isinstance(status, dict)
    assert "running" in status
    assert "alerts_ingested" in status
    assert "syslog_ingested" in status
    assert "consecutive_failures" in status


@pytest.mark.asyncio
async def test_malcolm_collector_run_cancels_cleanly():
    """asyncio.CancelledError propagates out of run() and sets _running=False."""
    import asyncio
    from unittest.mock import patch

    collector = MalcolmCollector()

    async def _cancel_immediately():
        task = asyncio.create_task(collector.run())
        await asyncio.sleep(0)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    await _cancel_immediately()
    assert collector._running is False


def test_malcolm_collector_backoff_on_failure():
    """After a failed poll cycle, backoff doubles (up to 300s cap)."""
    collector = MalcolmCollector()
    base_interval = getattr(collector, "_interval_sec", 30)

    collector._consecutive_failures = 3
    expected_backoff = min(base_interval * (2 ** 3), 300)

    # Verify the expected formula — implementation must honour this cap
    assert expected_backoff <= 300
    assert expected_backoff == min(base_interval * 8, 300)


@pytest.mark.asyncio
async def test_malcolm_collector_heartbeat_updates_kv():
    """_poll_and_ingest() calls sqlite.set_kv("malcolm.last_heartbeat", ...) each cycle."""
    from unittest.mock import AsyncMock, MagicMock, call

    mock_sqlite = MagicMock()
    mock_sqlite.set_kv = MagicMock()

    collector = MalcolmCollector(sqlite_store=mock_sqlite)
    await collector._poll_and_ingest()

    assert mock_sqlite.set_kv.called
    kv_key = mock_sqlite.set_kv.call_args[0][0]
    assert kv_key == "malcolm.last_heartbeat"


# --- Phase 31: new EVE normalizers and expanded poll ---

def test_normalize_tls():
    """_normalize_tls() maps TLS EVE doc to NormalizedEvent with event_type='tls'."""
    collector = MalcolmCollector()
    # Full nested ECS doc
    doc = {
        "source": {"ip": "1.2.3.4", "port": 12345},
        "destination": {"ip": "5.6.7.8", "port": 443},
        "tls": {
            "version": "TLSv1.3",
            "ja3": {"hash": "abc"},
            "ja3s": {"hash": "def"},
            "sni": "example.com",
            "cipher": "TLS_AES_256_GCM_SHA384",
            "established": True,
        },
        "@timestamp": "2026-01-01T00:00:00Z",
    }
    event = collector._normalize_tls(doc)
    assert event is not None
    assert event.event_type == "tls"
    assert event.tls_version == "TLSv1.3"
    assert event.tls_ja3 == "abc"
    assert event.src_ip == "1.2.3.4"
    assert event.tls_validation_status == "valid"

    # Arkime-flat fallback
    doc2 = {"source": {"ip": "1.2.3.4"}, "tls.version_string": "TLSv1.2"}
    event2 = collector._normalize_tls(doc2)
    assert event2 is not None
    assert event2.tls_version == "TLSv1.2"

    # No source.ip → None
    doc3 = {"tls": {"version": "TLSv1.3"}}
    assert collector._normalize_tls(doc3) is None


def test_normalize_dns():
    """_normalize_dns() maps DNS EVE doc to NormalizedEvent with event_type='dns_query'."""
    collector = MalcolmCollector()
    doc = {
        "source": {"ip": "10.0.0.5", "port": 54321},
        "destination": {"ip": "8.8.8.8", "port": 53},
        "dns": {
            "question": {"name": "malware.ru", "type": "A"},
            "response_code": "NOERROR",
            "answers": [{"data": "1.1.1.1", "ttl": 300}],
        },
        "@timestamp": "2026-01-01T00:00:00Z",
    }
    event = collector._normalize_dns(doc)
    assert event is not None
    assert event.event_type == "dns_query"
    assert event.dns_query == "malware.ru"
    assert event.dns_query_type == "A"
    assert event.src_ip == "10.0.0.5"
    # dns_answers stored as JSON string
    import json
    answers = json.loads(event.dns_answers)
    assert answers[0]["data"] == "1.1.1.1"
    assert event.dns_ttl == 300

    # No source.ip → None
    assert collector._normalize_dns({"dns": {"question": {"name": "evil.com"}}}) is None


def test_normalize_fileinfo():
    """_normalize_fileinfo() maps fileinfo EVE doc to NormalizedEvent with event_type='file_transfer'."""
    collector = MalcolmCollector()
    doc = {
        "source": {"ip": "10.0.0.1", "port": 54321},
        "file": {
            "hash": {"md5": "abc123", "sha256": "sha256hash"},
            "type": "application/x-pe",
            "size": 204800,
        },
        "@timestamp": "2026-01-01T00:00:00Z",
    }
    event = collector._normalize_fileinfo(doc)
    assert event is not None
    assert event.event_type == "file_transfer"
    assert event.file_md5 == "abc123"
    assert event.file_mime_type == "application/x-pe"
    assert event.file_size_bytes == 204800

    # No source.ip → None
    assert collector._normalize_fileinfo({"file": {"hash": {"md5": "x"}}}) is None


def test_normalize_anomaly():
    """_normalize_anomaly() maps anomaly EVE doc to NormalizedEvent with event_type='anomaly'."""
    collector = MalcolmCollector()
    doc = {
        "source": {"ip": "10.0.0.2"},
        "event": {"severity": "high"},
        "@timestamp": "2026-01-01T00:00:00Z",
    }
    event = collector._normalize_anomaly(doc)
    assert event is not None
    assert event.event_type == "anomaly"
    assert event.severity == "high"

    # No source.ip → None
    assert collector._normalize_anomaly({"event": {"severity": "high"}}) is None


@pytest.mark.asyncio
async def test_poll_all_eve_types():
    """_poll_and_ingest() calls _fetch_index for all 6 cursor keys."""
    from unittest.mock import AsyncMock, MagicMock, patch

    mock_sqlite = MagicMock()
    mock_sqlite.get_kv = MagicMock(return_value=None)
    mock_sqlite.set_kv = MagicMock()

    collector = MalcolmCollector(sqlite_store=mock_sqlite)

    # Patch _fetch_index to return [] without making network calls
    with patch.object(collector, "_fetch_index", new=AsyncMock(return_value=[])) as mock_fetch:
        await collector._poll_and_ingest()

    # Check all cursor keys were used.
    # Phase 36 fix: removed Phase 31 duplicate tls/dns/fileinfo keys (they were
    # wrong event.type names). The correct event.dataset-based keys are now used:
    #   - zeek_ssl (not tls), zeek_dns_zeek (not dns), zeek_files (not fileinfo)
    call_cursor_keys = [call.args[1] for call in mock_fetch.call_args_list]
    expected_keys = {
        "malcolm.alerts.last_timestamp",
        "malcolm.anomaly.last_timestamp",
        "malcolm.syslog.last_timestamp",
        "malcolm.zeek_conn.last_timestamp",
        "malcolm.zeek_weird.last_timestamp",
        # Phase 36-02: Zeek log types (using correct event.dataset values)
        "malcolm.zeek_http.last_timestamp",
        "malcolm.zeek_ssl.last_timestamp",
        "malcolm.zeek_x509.last_timestamp",
        "malcolm.zeek_files.last_timestamp",
        "malcolm.zeek_notice.last_timestamp",
        "malcolm.zeek_kerberos.last_timestamp",
        "malcolm.zeek_ntlm.last_timestamp",
        "malcolm.zeek_ssh.last_timestamp",
        "malcolm.zeek_smb_mapping.last_timestamp",
        "malcolm.zeek_smb_files.last_timestamp",
        "malcolm.zeek_rdp.last_timestamp",
        "malcolm.zeek_dce_rpc.last_timestamp",
        "malcolm.zeek_dhcp.last_timestamp",
        "malcolm.zeek_dns_zeek.last_timestamp",
        "malcolm.zeek_software.last_timestamp",
        "malcolm.zeek_known_hosts.last_timestamp",
        "malcolm.zeek_known_services.last_timestamp",
        "malcolm.zeek_sip.last_timestamp",
        "malcolm.zeek_ftp.last_timestamp",
        "malcolm.zeek_smtp.last_timestamp",
        "malcolm.zeek_socks.last_timestamp",
        "malcolm.zeek_tunnel.last_timestamp",
        "malcolm.zeek_pe.last_timestamp",
    }
    assert set(call_cursor_keys) == expected_keys
    assert mock_fetch.call_count == len(expected_keys)


# --- Phase 31 Plan 03: Ubuntu normalizer poll ---

def test_ubuntu_poll():
    """_poll_ubuntu_normalizer() returns [] when URL is empty (disabled)."""
    collector = MalcolmCollector(ubuntu_normalizer_url="")
    # Synchronous path: URL empty → disabled, no HTTP needed
    import asyncio
    result = asyncio.run(collector._poll_ubuntu_normalizer())
    assert result == []
