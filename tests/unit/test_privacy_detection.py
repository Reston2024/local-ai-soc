"""
Phase 53 Plan 03: Privacy detection scanner tests.
Tests for PRIV-05 through PRIV-08 (scanner logic).

Uses module-level patching of _query_http_events and _is_tracker so tests
run without live DuckDB or SQLite connections.
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

pytestmark = pytest.mark.unit

# Skip the entire file if the implementation module does not yet exist.
privacy_api = pytest.importorskip(
    "backend.api.privacy",
    reason="Wave 0 — implement in Plan 53-03",
)

from backend.api.privacy import run_privacy_scan  # noqa: E402


def _make_app(privacy_store_is_tracker=None):
    """Build a minimal mock app with the state attributes the scanner needs."""
    app = MagicMock()
    app.state.duckdb_store = MagicMock()
    app.state.sqlite_store = MagicMock()
    # privacy_store.is_tracker is called via _is_tracker helper
    if privacy_store_is_tracker is not None:
        app.state.privacy_store = MagicMock()
        app.state.privacy_store.is_tracker.side_effect = privacy_store_is_tracker
    else:
        app.state.privacy_store = MagicMock()
        app.state.privacy_store.is_tracker.return_value = False
    return app


# ---------------------------------------------------------------------------
# PRIV-05: Cookie exfil detection
# ---------------------------------------------------------------------------

def test_cookie_exfil_detection_fires_on_large_body_to_tracker():
    """run_privacy_scan() fires cookie_exfil detection for large POST to known tracker.

    PRIV-05: run_privacy_scan(app) with mock DuckDB returning one row with
    http_request_body_len=8192, domain="tracker.example.com" (in blocklist)
    returns at least one detection with hit_type="cookie_exfil".
    """
    mock_app = _make_app()

    with patch("backend.api.privacy._query_http_events") as mock_query, \
         patch("backend.api.privacy._is_tracker") as mock_tracker:
        mock_query.return_value = [
            {
                "event_id": "evt-001",
                "http_request_body_len": 8192,
                "domain": "tracker.example.com",
                "http_uri": "/collect",
                "src_ip": "10.0.0.5",
            }
        ]
        mock_tracker.side_effect = lambda ps, domain: domain == "tracker.example.com"
        detections = run_privacy_scan(mock_app)

    cookie_exfil = [d for d in detections if d.get("hit_type") == "cookie_exfil"]
    assert len(cookie_exfil) >= 1


# ---------------------------------------------------------------------------
# PRIV-06: Tracking pixel detection
# ---------------------------------------------------------------------------

def test_tracking_pixel_detection_fires_on_tiny_image_from_tracker():
    """run_privacy_scan() fires tracking_pixel detection for tiny GIF from known tracker.

    PRIV-06: run_privacy_scan(app) with mock DuckDB returning one row with
    http_response_body_len=43, http_resp_mime_type="image/gif",
    domain="pixel.example.com" (in blocklist) returns at least one detection
    with hit_type="tracking_pixel".
    """
    mock_app = _make_app()

    with patch("backend.api.privacy._query_http_events") as mock_query, \
         patch("backend.api.privacy._is_tracker") as mock_tracker:
        # First call (cookie exfil) returns empty; second call (pixel) returns one row
        mock_query.side_effect = [
            [],  # cookie exfil query — no rows
            [
                {
                    "event_id": "evt-002",
                    "http_response_body_len": 43,
                    "http_resp_mime_type": "image/gif",
                    "domain": "pixel.example.com",
                    "src_ip": "10.0.0.5",
                }
            ],
        ]
        mock_tracker.side_effect = lambda ps, domain: domain == "pixel.example.com"
        detections = run_privacy_scan(mock_app)

    pixel_detections = [d for d in detections if d.get("hit_type") == "tracking_pixel"]
    assert len(pixel_detections) >= 1


# ---------------------------------------------------------------------------
# PRIV-07: No false positive for non-tracker domain
# ---------------------------------------------------------------------------

def test_no_false_positive_for_non_tracker_domain():
    """run_privacy_scan() returns 0 detections when domain is not in the blocklist.

    PRIV-07: run_privacy_scan(app) with large body POST to "github.com"
    (NOT in blocklist) returns 0 detections regardless of body size.
    """
    mock_app = _make_app()

    with patch("backend.api.privacy._query_http_events") as mock_query, \
         patch("backend.api.privacy._is_tracker") as mock_tracker:
        mock_query.return_value = [
            {
                "event_id": "evt-003",
                "http_request_body_len": 8192,
                "domain": "github.com",
                "src_ip": "10.0.0.5",
            }
        ]
        mock_tracker.return_value = False  # github.com is not a tracker
        detections = run_privacy_scan(mock_app)

    assert len(detections) == 0


# ---------------------------------------------------------------------------
# PRIV-08: Detection record source tagging
# ---------------------------------------------------------------------------

def test_detection_record_uses_privacy_source_tag():
    """Detections from the privacy scanner use detection_source='privacy' and rule_id prefix 'privacy-'.

    PRIV-08: Detections created by run_privacy_scan() have
    detection_source="privacy" and rule_id starting with "privacy-".
    """
    mock_app = _make_app()

    with patch("backend.api.privacy._query_http_events") as mock_query, \
         patch("backend.api.privacy._is_tracker") as mock_tracker:
        mock_query.return_value = [
            {
                "event_id": "evt-004",
                "http_request_body_len": 8192,
                "domain": "tracker.example.com",
                "src_ip": "10.0.0.5",
            }
        ]
        mock_tracker.return_value = True
        detections = run_privacy_scan(mock_app)

    assert len(detections) >= 1
    for det in detections:
        assert det.get("detection_source") == "privacy"
        assert det.get("rule_id", "").startswith("privacy-")
