"""Eval tests for P22-T01: Response grounding threading."""
from __future__ import annotations

import pytest

# Import target modules — fail-fast on removal of skip if module is missing
from backend.api import query as _query_module  # noqa: F401


@pytest.mark.skip(reason="stub — implemented in 22-01")
async def test_grounding_event_ids_in_response():
    """audit_id and grounding_event_ids appear in /ask JSON response."""
    pass


@pytest.mark.skip(reason="stub — implemented in 22-01")
async def test_ungrounded_response():
    """is_grounded=False when context_event_ids is empty."""
    pass


@pytest.mark.skip(reason="stub — implemented in 22-01")
async def test_audit_id_is_uuid():
    """audit_id in response is a valid UUID string."""
    pass
