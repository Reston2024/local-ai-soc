"""Tests for Phase 31: EVE protocol telemetry fields on NormalizedEvent.

Adds 20 new fields (dns_*, tls_*, file_*, http_*) to NormalizedEvent at
positions 35-54 in to_duckdb_row(). Plan 31-01.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from backend.models.event import OCSF_CLASS_UID_MAP, NormalizedEvent


# --- Phase 31: new EVE protocol fields ---

def test_new_fields_in_duckdb_row():
    """to_duckdb_row() returns 80-element tuple; EVE fields at 35-54, IOC at 55-57, Zeek at 58-74, anomaly_score at 75, privacy HTTP at 76-79."""
    event = NormalizedEvent(
        event_id="test-31",
        timestamp=datetime.now(timezone.utc),
        ingested_at=datetime.now(timezone.utc),
        dns_query="evil.com",
    )
    row = event.to_duckdb_row()
    assert len(row) == 80  # Phase 53: expanded from 76 to 80 (4 new HTTP privacy fields)
    assert row[35] == "evil.com"   # dns_query
    assert row[47] is None          # file_md5
    assert row[55] is False         # ioc_matched (defaults False)
    assert row[56] is None          # ioc_confidence
    assert row[57] is None          # ioc_actor_tag
    # Phase 36: Zeek fields at positions 58-74
    assert row[58] is None          # conn_state
    # Phase 53: extended HTTP fields at positions 76-79
    assert row[76] is None          # http_referrer
    assert row[77] is None          # http_request_body_len
    assert row[78] is None          # http_response_body_len
    assert row[79] is None          # http_resp_mime_type


def test_ocsf_new_types():
    """OCSF_CLASS_UID_MAP contains tls, file_transfer, anomaly entries."""
    assert OCSF_CLASS_UID_MAP["tls"] == 4001
    assert OCSF_CLASS_UID_MAP["file_transfer"] == 1001
    assert OCSF_CLASS_UID_MAP["anomaly"] == 4001
    assert OCSF_CLASS_UID_MAP["dns_query"] == 4003   # must not change
