import pytest

pytestmark = pytest.mark.skip(reason="Wave 0 stub — activated in plan 25-05")


def test_validation_failed_emits_notification():
    """P25-T03: failure_taxonomy='validation_failed' emits notification with required_action='manual_review_required'."""


def test_rolled_back_emits_notification():
    """P25-T03: failure_taxonomy='rolled_back' emits notification with required_action='manual_review_required'."""


def test_expired_rejected_emits_notification():
    """P25-T03: failure_taxonomy='expired_rejected' emits notification with required_action='re_approve_required'."""


def test_applied_no_notification():
    """P25-T03: failure_taxonomy='applied' does NOT emit a notification."""


def test_noop_no_notification():
    """P25-T03: failure_taxonomy='noop_already_present' does NOT emit a notification."""


def test_get_notifications_returns_pending():
    """P25-T03: GET /api/notifications returns list of pending notifications."""
