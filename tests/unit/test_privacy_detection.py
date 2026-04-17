"""
Phase 53 Wave 0 stubs: Privacy detection scanner tests (Plan 53-01).
Stubs for PRIV-05 through PRIV-08 (scanner logic).

The importorskip at module level causes the entire file to skip atomically
when backend.api.privacy is absent.
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit

# Skip the entire file if the implementation module does not yet exist.
privacy_api = pytest.importorskip(
    "backend.api.privacy",
    reason="Wave 0 — implement in Plan 53-03",
)


# ---------------------------------------------------------------------------
# PRIV-05: Cookie exfil detection
# ---------------------------------------------------------------------------
@pytest.mark.skip(reason="Wave 0 stub — implement in Plan 53-03")
def test_cookie_exfil_detection_fires_on_large_body_to_tracker():
    """run_privacy_scan() fires cookie_exfil detection for large POST to known tracker.

    PRIV-05: run_privacy_scan(app) with mock DuckDB returning one row with
    http_request_body_len=8192, domain="tracker.example.com" (in blocklist)
    returns at least one detection with hit_type="cookie_exfil".
    """
    pytest.skip("Wave 0 stub — implement in Plan 53-03")
    from unittest.mock import MagicMock, patch
    from backend.api.privacy import run_privacy_scan

    mock_app = MagicMock()
    with patch("backend.api.privacy._query_http_events") as mock_query, \
         patch("backend.api.privacy._is_tracker") as mock_tracker:
        mock_query.return_value = [
            {"http_request_body_len": 8192, "domain": "tracker.example.com"}
        ]
        mock_tracker.side_effect = lambda domain: domain == "tracker.example.com"
        detections = run_privacy_scan(mock_app)
    cookie_exfil = [d for d in detections if d.get("hit_type") == "cookie_exfil"]
    assert len(cookie_exfil) >= 1
    assert False


# ---------------------------------------------------------------------------
# PRIV-06: Tracking pixel detection
# ---------------------------------------------------------------------------
@pytest.mark.skip(reason="Wave 0 stub — implement in Plan 53-03")
def test_tracking_pixel_detection_fires_on_tiny_image_from_tracker():
    """run_privacy_scan() fires tracking_pixel detection for tiny GIF from known tracker.

    PRIV-06: run_privacy_scan(app) with mock DuckDB returning one row with
    http_response_body_len=43, http_resp_mime_type="image/gif",
    domain="pixel.example.com" (in blocklist) returns at least one detection
    with hit_type="tracking_pixel".
    """
    pytest.skip("Wave 0 stub — implement in Plan 53-03")
    from unittest.mock import MagicMock, patch
    from backend.api.privacy import run_privacy_scan

    mock_app = MagicMock()
    with patch("backend.api.privacy._query_http_events") as mock_query, \
         patch("backend.api.privacy._is_tracker") as mock_tracker:
        mock_query.return_value = [
            {
                "http_response_body_len": 43,
                "http_resp_mime_type": "image/gif",
                "domain": "pixel.example.com",
            }
        ]
        mock_tracker.side_effect = lambda domain: domain == "pixel.example.com"
        detections = run_privacy_scan(mock_app)
    pixel_detections = [d for d in detections if d.get("hit_type") == "tracking_pixel"]
    assert len(pixel_detections) >= 1
    assert False


# ---------------------------------------------------------------------------
# PRIV-07: No false positive for non-tracker domain
# ---------------------------------------------------------------------------
@pytest.mark.skip(reason="Wave 0 stub — implement in Plan 53-03")
def test_no_false_positive_for_non_tracker_domain():
    """run_privacy_scan() returns 0 detections when domain is not in the blocklist.

    PRIV-07: run_privacy_scan(app) with large body POST to "github.com"
    (NOT in blocklist) returns 0 detections regardless of body size.
    """
    pytest.skip("Wave 0 stub — implement in Plan 53-03")
    from unittest.mock import MagicMock, patch
    from backend.api.privacy import run_privacy_scan

    mock_app = MagicMock()
    with patch("backend.api.privacy._query_http_events") as mock_query, \
         patch("backend.api.privacy._is_tracker") as mock_tracker:
        mock_query.return_value = [
            {"http_request_body_len": 8192, "domain": "github.com"}
        ]
        mock_tracker.return_value = False  # github.com is not a tracker
        detections = run_privacy_scan(mock_app)
    assert len(detections) == 0
    assert False


# ---------------------------------------------------------------------------
# PRIV-08: Detection record source tagging
# ---------------------------------------------------------------------------
@pytest.mark.skip(reason="Wave 0 stub — implement in Plan 53-03")
def test_detection_record_uses_privacy_source_tag():
    """Detections from the privacy scanner use detection_source='privacy' and rule_id prefix 'privacy-'.

    PRIV-08: Detections created by run_privacy_scan() have
    detection_source="privacy" and rule_id starting with "privacy-".
    """
    pytest.skip("Wave 0 stub — implement in Plan 53-03")
    from unittest.mock import MagicMock, patch
    from backend.api.privacy import run_privacy_scan

    mock_app = MagicMock()
    with patch("backend.api.privacy._query_http_events") as mock_query, \
         patch("backend.api.privacy._is_tracker") as mock_tracker:
        mock_query.return_value = [
            {"http_request_body_len": 8192, "domain": "tracker.example.com"}
        ]
        mock_tracker.return_value = True
        detections = run_privacy_scan(mock_app)
    assert len(detections) >= 1
    for det in detections:
        assert det.get("detection_source") == "privacy"
        assert det.get("rule_id", "").startswith("privacy-")
    assert False
