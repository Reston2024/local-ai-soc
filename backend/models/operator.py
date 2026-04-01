"""
Pydantic models for operator identity management (Phase 19).
"""
from typing import Optional

from pydantic import BaseModel, Field


class OperatorCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=64)
    role: str = Field(default="analyst", pattern="^(admin|analyst)$")


class OperatorRead(BaseModel):
    operator_id: str
    username: str
    role: str
    is_active: bool
    created_at: str
    last_seen_at: Optional[str] = None


class OperatorCreateResponse(BaseModel):
    operator_id: str
    username: str
    role: str
    api_key: str        # returned ONCE; not stored server-side
    created_at: str


class OperatorRotateResponse(BaseModel):
    operator_id: str
    api_key: str        # new key, shown once
