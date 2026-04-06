"""
Unit tests for backend/models/receipt.py — ReceiptIngest, NotificationItem,
CASE_STATE_MAP, NOTIFICATION_TRIGGERS, REQUIRED_ACTION_MAP.

TDD RED phase: all tests here fail until backend/models/receipt.py is created.
Requirements: P25-T01, P25-T02, P25-T04
"""

import uuid
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from backend.models.receipt import (
    CASE_STATE_MAP,
    NOTIFICATION_TRIGGERS,
    REQUIRED_ACTION_MAP,
    NotificationItem,
    ReceiptIngest,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NOW = datetime.now(timezone.utc).isoformat()
_UUID = str(uuid.uuid4())


def _valid_receipt(**overrides) -> dict:
    base = {
        "schema_version": "1.0.0-stub",
        "receipt_id": _UUID,
        "recommendation_id": _UUID,
        "case_id": _UUID,
        "failure_taxonomy": "applied",
        "executed_at": _NOW,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Test 1 — valid ReceiptIngest constructs without error
# ---------------------------------------------------------------------------


def test_receipt_ingest_valid_construction():
    """Test 1: ReceiptIngest with all required fields and failure_taxonomy='applied' constructs without error."""
    r = ReceiptIngest(**_valid_receipt())
    assert r.receipt_id == _UUID
    assert r.failure_taxonomy == "applied"


# ---------------------------------------------------------------------------
# Test 2 — unknown failure_taxonomy raises ValidationError
# ---------------------------------------------------------------------------


def test_receipt_ingest_invalid_taxonomy():
    """Test 2: ReceiptIngest(..., failure_taxonomy='invalid_value') raises ValidationError."""
    with pytest.raises(ValidationError):
        ReceiptIngest(**_valid_receipt(failure_taxonomy="invalid_value"))


# ---------------------------------------------------------------------------
# Test 3 — missing required field raises ValidationError
# ---------------------------------------------------------------------------


def test_receipt_ingest_missing_required_field():
    """Test 3: ReceiptIngest without required field (case_id) raises ValidationError."""
    data = _valid_receipt()
    del data["case_id"]
    with pytest.raises(ValidationError):
        ReceiptIngest(**data)


# ---------------------------------------------------------------------------
# Tests 4–8 — CASE_STATE_MAP entries
# ---------------------------------------------------------------------------


def test_case_state_map_applied():
    """Test 4: CASE_STATE_MAP['applied'] == 'containment_confirmed'."""
    assert CASE_STATE_MAP["applied"] == "containment_confirmed"


def test_case_state_map_noop_already_present():
    """Test 5: CASE_STATE_MAP['noop_already_present'] == 'containment_confirmed'."""
    assert CASE_STATE_MAP["noop_already_present"] == "containment_confirmed"


def test_case_state_map_validation_failed():
    """Test 6: CASE_STATE_MAP['validation_failed'] == 'containment_failed'."""
    assert CASE_STATE_MAP["validation_failed"] == "containment_failed"


def test_case_state_map_expired_rejected():
    """Test 7: CASE_STATE_MAP['expired_rejected'] == 'containment_failed'."""
    assert CASE_STATE_MAP["expired_rejected"] == "containment_failed"


def test_case_state_map_rolled_back():
    """Test 8: CASE_STATE_MAP['rolled_back'] == 'containment_rolled_back'."""
    assert CASE_STATE_MAP["rolled_back"] == "containment_rolled_back"


# ---------------------------------------------------------------------------
# Test 9 — NOTIFICATION_TRIGGERS
# ---------------------------------------------------------------------------


def test_notification_triggers_set():
    """Test 9: NOTIFICATION_TRIGGERS == {'validation_failed', 'rolled_back', 'expired_rejected'}."""
    assert NOTIFICATION_TRIGGERS == {"validation_failed", "rolled_back", "expired_rejected"}


# ---------------------------------------------------------------------------
# Tests 10–12 — REQUIRED_ACTION_MAP entries
# ---------------------------------------------------------------------------


def test_required_action_map_validation_failed():
    """Test 10: REQUIRED_ACTION_MAP['validation_failed'] == 'manual_review_required'."""
    assert REQUIRED_ACTION_MAP["validation_failed"] == "manual_review_required"


def test_required_action_map_rolled_back():
    """Test 11: REQUIRED_ACTION_MAP['rolled_back'] == 'manual_review_required'."""
    assert REQUIRED_ACTION_MAP["rolled_back"] == "manual_review_required"


def test_required_action_map_expired_rejected():
    """Test 12: REQUIRED_ACTION_MAP['expired_rejected'] == 're_approve_required'."""
    assert REQUIRED_ACTION_MAP["expired_rejected"] == "re_approve_required"


# ---------------------------------------------------------------------------
# Test 13 — NotificationItem fields
# ---------------------------------------------------------------------------


def test_notification_item_fields():
    """Test 13: NotificationItem has expected fields: notification_id, case_id, receipt_id,
    required_action, status, created_at."""
    item = NotificationItem(
        notification_id=_UUID,
        case_id=_UUID,
        receipt_id=_UUID,
        required_action="manual_review_required",
        status="pending",
        created_at=_NOW,
    )
    assert item.notification_id == _UUID
    assert item.case_id == _UUID
    assert item.receipt_id == _UUID
    assert item.required_action == "manual_review_required"
    assert item.status == "pending"
    assert item.created_at == _NOW
