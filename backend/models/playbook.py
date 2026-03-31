"""
Pydantic models for the SOAR Playbook Engine (Phase 17).

Models:
- PlaybookStep: A single step in a playbook procedure
- Playbook: A complete incident response playbook
- PlaybookCreate: POST body for creating a new playbook
- PlaybookRun: A runtime execution record for a playbook against an investigation
- PlaybookRunAdvance: PATCH body for advancing a playbook run (Plan 02)
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict


class PlaybookStep(BaseModel):
    """A single procedural step within a playbook."""

    model_config = ConfigDict(from_attributes=True)

    step_number: int
    title: str
    description: str
    requires_approval: bool = True
    evidence_prompt: Optional[str] = None


class Playbook(BaseModel):
    """A complete incident response playbook."""

    model_config = ConfigDict(from_attributes=True)

    playbook_id: str
    name: str
    description: str
    trigger_conditions: list[str]
    steps: list[PlaybookStep]
    version: str = "1.0"
    created_at: str
    is_builtin: bool = False


class PlaybookCreate(BaseModel):
    """Request body for POST /api/playbooks."""

    model_config = ConfigDict(from_attributes=True)

    name: str
    description: str = ""
    trigger_conditions: list[str] = []
    steps: list[PlaybookStep] = []
    version: str = "1.0"


class PlaybookRun(BaseModel):
    """A runtime execution record linking a playbook to an investigation."""

    model_config = ConfigDict(from_attributes=True)

    run_id: str
    playbook_id: str
    investigation_id: str
    status: Literal["running", "completed", "cancelled"] = "running"
    started_at: str
    completed_at: Optional[str] = None
    steps_completed: list[dict] = []
    analyst_notes: str = ""


class PlaybookRunAdvance(BaseModel):
    """Request body for PATCH /api/playbook-runs/{run_id}/step/{step_n} (Plan 02).

    Every step advance is analyst-initiated — no autonomous execution.
    """

    model_config = ConfigDict(from_attributes=True)

    analyst_note: str = ""
    outcome: Literal["confirmed", "skipped"] = "confirmed"
