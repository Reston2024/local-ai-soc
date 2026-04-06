"""Pydantic models for execution receipt ingestion (Phase 25).

Implements ReceiptIngest (POST /api/receipts request body) validated against
the local JSON Schema stub at import time, plus NotificationItem and the three
ADR-032 business-logic constants: CASE_STATE_MAP, NOTIFICATION_TRIGGERS,
REQUIRED_ACTION_MAP.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal, Optional

import jsonschema
from pydantic import BaseModel, model_validator

# Load and cache the schema stub at import time (fails fast if file missing).
_SCHEMA_PATH = (
    Path(__file__).parent.parent.parent / "contracts" / "execution-receipt.schema.json"
)
_SCHEMA: dict = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))

# ---------------------------------------------------------------------------
# ADR-032: deterministic case-state transition map (5 taxonomy values)
# ---------------------------------------------------------------------------

CASE_STATE_MAP: dict[str, str] = {
    "applied": "containment_confirmed",
    "noop_already_present": "containment_confirmed",
    "validation_failed": "containment_failed",
    "expired_rejected": "containment_failed",
    "rolled_back": "containment_rolled_back",
}

# Taxonomy values that trigger an analyst notification
NOTIFICATION_TRIGGERS: set[str] = {"validation_failed", "rolled_back", "expired_rejected"}

# Required action per notification taxonomy
REQUIRED_ACTION_MAP: dict[str, str] = {
    "validation_failed": "manual_review_required",
    "rolled_back": "manual_review_required",
    "expired_rejected": "re_approve_required",
}


# ---------------------------------------------------------------------------
# Primary request-body model
# ---------------------------------------------------------------------------


class ReceiptIngest(BaseModel):
    """Request body for POST /api/receipts. Validated against local schema stub."""

    schema_version: Literal["1.0.0-stub"] = "1.0.0-stub"
    receipt_id: str
    recommendation_id: str
    case_id: str
    failure_taxonomy: Literal[
        "applied",
        "noop_already_present",
        "validation_failed",
        "expired_rejected",
        "rolled_back",
    ]
    executed_at: str
    executor_version: Optional[str] = None
    detail: Optional[str] = None

    @model_validator(mode="after")
    def validate_against_schema(self) -> "ReceiptIngest":
        """Full JSON Schema Draft 2020-12 validation against contracts/execution-receipt.schema.json.

        Uses exclude_none=True to omit optional None fields — prevents false positives
        from additionalProperties=false seeing null keys (mirrors recommendation.py pattern).
        Note: format_checker is intentionally NOT passed — uuid/date-time formats are not
        enforced at jsonschema level (Research pitfall 5).
        """
        data = self.model_dump(mode="json", exclude_none=True)
        try:
            jsonschema.validate(instance=data, schema=_SCHEMA)
        except jsonschema.ValidationError as exc:
            raise ValueError(
                f"Receipt schema validation failed: {exc.message}"
            ) from exc
        return self


# ---------------------------------------------------------------------------
# Notification output model
# ---------------------------------------------------------------------------


class NotificationItem(BaseModel):
    """Structured notification emitted when a receipt requires human review."""

    notification_id: str
    case_id: str
    receipt_id: str
    required_action: Literal["manual_review_required", "re_approve_required"]
    status: Literal["pending"] = "pending"
    created_at: str
