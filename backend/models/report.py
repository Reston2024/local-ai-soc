"""
Pydantic models for the report generation API (Phase 18).

Report types:
- investigation: tied to a saved investigation, contains events + chat + playbook runs
- executive: period-based summary with KPI metrics
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel


class Report(BaseModel):
    """Persisted report record stored in SQLite."""

    id: str
    type: Literal["investigation", "executive"]
    title: str
    subject_id: Optional[str] = None
    period_start: Optional[str] = None
    period_end: Optional[str] = None
    content_json: str
    created_at: str


class InvestigationReportRequest(BaseModel):
    """Request body for POST /api/reports/investigation/{investigation_id}."""

    investigation_id: str
    include_chat: bool = True
    include_playbook_runs: bool = True


class ExecutiveReportRequest(BaseModel):
    """Request body for POST /api/reports/executive."""

    period_start: str
    period_end: str
    title: str = "Executive Security Summary"
