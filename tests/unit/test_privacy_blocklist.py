"""
Phase 53 Wave 0 stubs: Privacy blocklist tests (Plan 53-01).
Stubs for PRIV-01 through PRIV-04 (blocklist parsing + store) and PRIV-11 (normalizer).

The importorskip at module level causes the entire file to skip atomically
when backend.services.intel.privacy_blocklist is absent.
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit

# Skip the entire file if the implementation module does not yet exist.
privacy_blocklist = pytest.importorskip(
    "backend.services.intel.privacy_blocklist",
    reason="Wave 0 — implement in Plan 53-02",
)


# ---------------------------------------------------------------------------
# PRIV-01: EasyPrivacy parsing
# ---------------------------------------------------------------------------
def test_parse_easyprivacy_extracts_domains():
    """_parse_easyprivacy(text) returns only valid domain entries.

    PRIV-01: Given "||tracker.example.com^\n||ads.test.org^\n! comment\n"
    the function returns ["tracker.example.com", "ads.test.org"].
    Comment lines starting with '!' and blank lines are excluded.
    """
    from backend.services.intel.privacy_blocklist import _parse_easyprivacy

    text = "||tracker.example.com^\n||ads.test.org^\n! comment\n\n"
    result = _parse_easyprivacy(text)
    assert result == ["tracker.example.com", "ads.test.org"]


# ---------------------------------------------------------------------------
# PRIV-02: Disconnect.me parsing
# ---------------------------------------------------------------------------
def test_parse_disconnect_extracts_all_categories():
    """_parse_disconnect(json_text) returns (domain, category) tuples for all entries.

    PRIV-02: Given minimal services.json with Email and Advertising categories,
    the function returns a list of (domain, category) tuples covering both categories.
    """
    import json
    from backend.services.intel.privacy_blocklist import _parse_disconnect

    json_text = json.dumps({
        "categories": {
            "Email": [
                {"Example Email": {"example-email.com": ["tracker.example-email.com"]}}
            ],
            "Advertising": [
                {"Example Ads": {"example-ads.com": ["tracker.example-ads.com"]}}
            ],
        }
    })
    result = _parse_disconnect(json_text)
    assert isinstance(result, list)
    domains = [d for d, _ in result]
    categories = [c for _, c in result]
    assert "tracker.example-email.com" in domains
    assert "tracker.example-ads.com" in domains
    assert "Email" in categories
    assert "Advertising" in categories


# ---------------------------------------------------------------------------
# PRIV-03: Store upsert and lookup
# ---------------------------------------------------------------------------
def test_store_upsert_and_lookup():
    """PrivacyBlocklistStore upserts domains and answers is_tracker() correctly.

    PRIV-03: store.upsert_domain("tracker.test", "easyprivacy", None);
    store.is_tracker("tracker.test") returns True;
    store.is_tracker("legit.example.com") returns False.
    """
    import sqlite3
    from backend.services.intel.privacy_blocklist import PrivacyBlocklistStore

    conn = sqlite3.connect(":memory:")
    store = PrivacyBlocklistStore(conn)
    store.upsert_domain("tracker.test", "easyprivacy", None)
    assert store.is_tracker("tracker.test") is True
    assert store.is_tracker("legit.example.com") is False


# ---------------------------------------------------------------------------
# PRIV-04: Worker populates store
# ---------------------------------------------------------------------------
def test_worker_populates_store():
    """PrivacyWorker._sync() calls parsers and upserts results into the store.

    PRIV-04: PrivacyWorker with mocked httpx responses calls _parse_easyprivacy
    and _parse_disconnect, then upserts parsed domains into the store.
    """
    from unittest.mock import MagicMock, patch
    from backend.services.intel.privacy_blocklist import PrivacyWorker

    mock_store = MagicMock()
    with patch("backend.services.intel.privacy_blocklist._parse_easyprivacy") as mock_ep, \
         patch("backend.services.intel.privacy_blocklist._parse_disconnect") as mock_dc, \
         patch("backend.services.intel.privacy_blocklist.httpx") as mock_httpx:
        mock_ep.return_value = ["tracker.example.com"]
        mock_dc.return_value = [("ad.example.com", "Advertising")]
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.text = ""
        mock_httpx.get.return_value = mock_resp
        worker = PrivacyWorker(store=mock_store)
        worker._sync()
    mock_store.upsert_domain.assert_called()


# ---------------------------------------------------------------------------
# PRIV-04b: Feed metadata updated after sync
# ---------------------------------------------------------------------------
def test_feed_meta_updated_after_sync():
    """store.get_feed_status() returns dicts with feed, last_sync, domain_count keys.

    PRIV-04b: After PrivacyWorker._sync() with mocked HTTP, store.get_feed_status()
    returns a list where each entry contains 'feed', 'last_sync', and 'domain_count' keys.
    """
    from unittest.mock import MagicMock, patch
    from backend.services.intel.privacy_blocklist import PrivacyBlocklistStore, PrivacyWorker
    import sqlite3

    conn = sqlite3.connect(":memory:")
    store = PrivacyBlocklistStore(conn)

    with patch("backend.services.intel.privacy_blocklist.httpx") as mock_httpx, \
         patch("backend.services.intel.privacy_blocklist._parse_easyprivacy") as mock_ep, \
         patch("backend.services.intel.privacy_blocklist._parse_disconnect") as mock_dc:
        mock_ep.return_value = ["tracker.test"]
        mock_dc.return_value = [("ad.test", "Advertising")]
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.text = ""
        mock_httpx.get.return_value = mock_resp
        worker = PrivacyWorker(store=store)
        worker._sync()

    statuses = store.get_feed_status()
    assert isinstance(statuses, list)
    assert len(statuses) >= 1
    for entry in statuses:
        assert "feed" in entry
        assert "last_sync" in entry
        assert "domain_count" in entry


# ---------------------------------------------------------------------------
# PRIV-11: HTTP normalizer extended fields
# Note: Tests ingestion/jobs/malcolm_collector._normalize_http extension.
# ---------------------------------------------------------------------------
def test_normalize_http_extended_fields():
    """_normalize_http(doc) maps zeek HTTP extended fields to NormalizedEvent.

    PRIV-11: doc with zeek.http.referrer, zeek.http.request_body_len,
    zeek.http.response_body_len, zeek.http.resp_mime_types returns NormalizedEvent
    with http_referrer, http_request_body_len, http_response_body_len,
    http_resp_mime_type populated correctly.
    """
    from ingestion.jobs.malcolm_collector import _normalize_http

    doc = {
        "source": {"ip": "10.0.0.1"},  # required by _normalize_http (returns None without src_ip)
        "zeek": {
            "http": {
                "referrer": "https://mail.example.com",
                "request_body_len": 8192,
                "response_body_len": 45,
                "resp_mime_types": ["image/gif"],
            }
        }
    }
    event = _normalize_http(doc)
    assert event is not None
    assert event.http_referrer == "https://mail.example.com"
    assert event.http_request_body_len == 8192
    assert event.http_response_body_len == 45
    assert event.http_resp_mime_type == "image/gif"
