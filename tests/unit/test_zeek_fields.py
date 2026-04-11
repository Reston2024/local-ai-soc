"""Phase 36: Tests for NormalizedEvent schema expansion and DuckDB sync."""
import re
import pytest
from backend.models.event import NormalizedEvent


def test_normalized_event_has_conn_state():
    """NormalizedEvent must have conn_state field."""
    e = NormalizedEvent(event_id="x", timestamp="2026-01-01T00:00:00Z", ingested_at="2026-01-01T00:00:00Z")
    assert hasattr(e, "conn_state")
    assert e.conn_state is None


def test_normalized_event_has_conn_duration():
    e = NormalizedEvent(event_id="x", timestamp="2026-01-01T00:00:00Z", ingested_at="2026-01-01T00:00:00Z")
    assert hasattr(e, "conn_duration")


def test_normalized_event_has_conn_bytes():
    e = NormalizedEvent(event_id="x", timestamp="2026-01-01T00:00:00Z", ingested_at="2026-01-01T00:00:00Z")
    assert hasattr(e, "conn_orig_bytes")
    assert hasattr(e, "conn_resp_bytes")


def test_normalized_event_has_zeek_weird_name():
    e = NormalizedEvent(event_id="x", timestamp="2026-01-01T00:00:00Z", ingested_at="2026-01-01T00:00:00Z")
    assert hasattr(e, "zeek_weird_name")


def test_normalized_event_has_ssh_fields():
    e = NormalizedEvent(event_id="x", timestamp="2026-01-01T00:00:00Z", ingested_at="2026-01-01T00:00:00Z")
    assert hasattr(e, "ssh_auth_success")
    assert hasattr(e, "ssh_version")


def test_normalized_event_has_auth_fields():
    e = NormalizedEvent(event_id="x", timestamp="2026-01-01T00:00:00Z", ingested_at="2026-01-01T00:00:00Z")
    assert hasattr(e, "kerberos_client")
    assert hasattr(e, "kerberos_service")
    assert hasattr(e, "ntlm_domain")
    assert hasattr(e, "ntlm_username")


def test_normalized_event_has_lateral_fields():
    e = NormalizedEvent(event_id="x", timestamp="2026-01-01T00:00:00Z", ingested_at="2026-01-01T00:00:00Z")
    assert hasattr(e, "smb_path")
    assert hasattr(e, "smb_action")
    assert hasattr(e, "rdp_cookie")
    assert hasattr(e, "rdp_security_protocol")


def test_to_duckdb_row_matches_insert_sql_placeholder_count():
    """CRITICAL: to_duckdb_row() tuple length must equal ? count in _INSERT_SQL."""
    from ingestion.loader import _INSERT_SQL
    placeholder_count = _INSERT_SQL.count("?")
    e = NormalizedEvent(event_id="x", timestamp="2026-01-01T00:00:00Z", ingested_at="2026-01-01T00:00:00Z")
    row = e.to_duckdb_row()
    assert len(row) == placeholder_count, (
        f"to_duckdb_row() returns {len(row)} values but _INSERT_SQL has {placeholder_count} placeholders. "
        "Update both in the same commit to keep them in sync."
    )
