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
    # Phase 38 — CISA enrichment fields
    attack_techniques: list[str] = []
    escalation_threshold: Optional[Literal["critical", "high"]] = None
    escalation_role: Optional[str] = None
    time_sla_minutes: Optional[int] = None
    containment_actions: list[str] = []


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
    source: str = "custom"  # Phase 38+46: 'cisa'|'cert_sg'|'aws'|'microsoft'|'guardsight'|'community'|'custom'
    category: str = ""  # Phase 46: malware|ransomware|phishing|identity|network|cloud|insider|supply_chain|web|endpoint|data_breach|ics_ot|vulnerability


class PlaybookCreate(BaseModel):
    """Request body for POST /api/playbooks."""

    model_config = ConfigDict(from_attributes=True)

    name: str
    description: str = ""
    trigger_conditions: list[str] = []
    steps: list[PlaybookStep] = []
    version: str = "1.0"
    category: str = ""  # Phase 46


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
    active_case_id: Optional[str] = None  # Phase 38: set on escalation acknowledge


class PlaybookRunAdvance(BaseModel):
    """Request body for PATCH /api/playbook-runs/{run_id}/step/{step_n} (Plan 02).

    Every step advance is analyst-initiated — no autonomous execution.
    """

    model_config = ConfigDict(from_attributes=True)

    analyst_note: str = ""
    outcome: Literal["confirmed", "skipped"] = "confirmed"
    containment_action: Optional[str] = None
    confidence: Optional[float] = None  # 0.0–1.0 analyst/detection confidence; used by policy gate
