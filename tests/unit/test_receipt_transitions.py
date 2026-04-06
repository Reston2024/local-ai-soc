import pytest

pytestmark = pytest.mark.skip(reason="Wave 0 stub — activated in plan 25-05")


def test_schema_file_valid():
    """P25-T04: contracts/execution-receipt.schema.json is valid JSON Schema; version is '1.0.0-stub'."""


def test_applied_transition():
    """P25-T02: failure_taxonomy='applied' maps to case_status='containment_confirmed'."""


def test_noop_transition():
    """P25-T02: failure_taxonomy='noop_already_present' maps to case_status='containment_confirmed'."""


def test_validation_failed_transition():
    """P25-T02: failure_taxonomy='validation_failed' maps to case_status='containment_failed'."""


def test_expired_rejected_transition():
    """P25-T02: failure_taxonomy='expired_rejected' maps to case_status='containment_failed'."""


def test_rolled_back_transition():
    """P25-T02: failure_taxonomy='rolled_back' maps to case_status='containment_rolled_back'."""
