import json
from pathlib import Path

import jsonschema
import pytest

from backend.models.receipt import CASE_STATE_MAP

_SCHEMA_PATH = Path(__file__).parent.parent.parent / "contracts" / "execution-receipt.schema.json"


def test_schema_file_valid():
    """P25-T04: contracts/execution-receipt.schema.json is valid JSON Schema; version is '1.0.0-stub'."""
    assert _SCHEMA_PATH.exists(), f"Schema file not found: {_SCHEMA_PATH}"
    schema = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator.check_schema(schema)
    assert schema["version"] == "1.0.0-stub"
    assert schema["properties"]["failure_taxonomy"]["enum"] == [
        "applied",
        "noop_already_present",
        "validation_failed",
        "expired_rejected",
        "rolled_back",
    ]


def test_applied_transition():
    """P25-T02: failure_taxonomy='applied' maps to case_status='containment_confirmed'."""
    assert CASE_STATE_MAP["applied"] == "containment_confirmed"


def test_noop_transition():
    """P25-T02: failure_taxonomy='noop_already_present' maps to case_status='containment_confirmed'."""
    assert CASE_STATE_MAP["noop_already_present"] == "containment_confirmed"


def test_validation_failed_transition():
    """P25-T02: failure_taxonomy='validation_failed' maps to case_status='containment_failed'."""
    assert CASE_STATE_MAP["validation_failed"] == "containment_failed"


def test_expired_rejected_transition():
    """P25-T02: failure_taxonomy='expired_rejected' maps to case_status='containment_failed'."""
    assert CASE_STATE_MAP["expired_rejected"] == "containment_failed"


def test_rolled_back_transition():
    """P25-T02: failure_taxonomy='rolled_back' maps to case_status='containment_rolled_back'."""
    assert CASE_STATE_MAP["rolled_back"] == "containment_rolled_back"
