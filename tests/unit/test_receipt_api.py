import pytest

pytestmark = pytest.mark.skip(reason="Wave 0 stub — activated in plan 25-05")


def test_post_receipt_valid_returns_202():
    """P25-T01: POST /api/receipts with valid body returns 202 Accepted."""


def test_post_receipt_invalid_body_returns_422():
    """P25-T01: POST /api/receipts with invalid body returns 422."""


def test_post_receipt_stores_in_duckdb():
    """P25-T01: execute_write called with INSERT INTO execution_receipts."""


def test_case_state_propagated():
    """P25-T02: update_investigation_case called with correct status after receipt ingest."""


def test_duplicate_receipt_returns_409():
    """P25-T05: Same receipt_id posted twice returns 409 Conflict."""
