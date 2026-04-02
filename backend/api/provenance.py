"""Evidence provenance API endpoints.

Provides read-only access to provenance records stored in SQLite so analysts
can audit exactly which software versions and raw inputs produced each
detection or ingest event.
"""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException, Request

from backend.core.deps import Stores, get_stores
from backend.core.rbac import OperatorContext, require_role
from backend.models.provenance import (
    DetectionProvenanceRecord,
    IngestProvenanceRecord,
    LlmProvenanceRecord,
    PlaybookProvenanceRecord,
)

router = APIRouter(prefix="/api/provenance", tags=["provenance"])


@router.get(
    "/ingest/{event_id}",
    response_model=IngestProvenanceRecord,
    summary="Get ingest provenance",
    description=(
        "Return the provenance record for a given ingested event: the raw-file SHA-256, "
        "parser name, parser version, and operator who triggered the ingest."
    ),
)
async def get_ingest_provenance(
    event_id: str,
    request: Request,
    ctx: OperatorContext = Depends(require_role("analyst", "admin")),
    stores: Stores = Depends(get_stores),
) -> IngestProvenanceRecord:
    row = await asyncio.to_thread(
        stores.sqlite.get_ingest_provenance, event_id
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Ingest provenance not found")
    row["event_id"] = event_id
    return IngestProvenanceRecord(**row)


@router.get(
    "/detection/{detection_id}",
    response_model=DetectionProvenanceRecord,
    summary="Get detection provenance",
    description=(
        "Return the provenance record for a given detection: the Sigma rule SHA-256, "
        "pySigma library version, and field-map version active when the rule fired."
    ),
)
async def get_detection_provenance(
    detection_id: str,
    request: Request,
    ctx: OperatorContext = Depends(require_role("analyst", "admin")),
    stores: Stores = Depends(get_stores),
) -> DetectionProvenanceRecord:
    row = await asyncio.to_thread(
        stores.sqlite.get_detection_provenance, detection_id
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Detection provenance not found")
    return DetectionProvenanceRecord(**row)


@router.get(
    "/llm/{audit_id}",
    response_model=LlmProvenanceRecord,
    summary="Get LLM call provenance",
    description=(
        "Return the provenance record for a given LLM call: the model ID, "
        "prompt template name and SHA-256, response SHA-256, and grounding event IDs."
    ),
)
async def get_llm_provenance(
    audit_id: str,
    request: Request,
    ctx: OperatorContext = Depends(require_role("analyst", "admin")),
    stores: Stores = Depends(get_stores),
) -> LlmProvenanceRecord:
    row = await asyncio.to_thread(
        stores.sqlite.get_llm_provenance, audit_id
    )
    if row is None:
        raise HTTPException(status_code=404, detail="LLM provenance not found")
    return LlmProvenanceRecord(**row)


@router.get(
    "/playbook/{run_id}",
    response_model=PlaybookProvenanceRecord,
    summary="Get playbook run provenance",
    description=(
        "Return the provenance record for a given playbook run: the playbook steps SHA-256, "
        "playbook version, trigger event IDs, and approving operator."
    ),
)
async def get_playbook_provenance(
    run_id: str,
    request: Request,
    ctx: OperatorContext = Depends(require_role("analyst", "admin")),
    stores: Stores = Depends(get_stores),
) -> PlaybookProvenanceRecord:
    row = await asyncio.to_thread(
        stores.sqlite.get_playbook_provenance, run_id
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Playbook provenance not found")
    return PlaybookProvenanceRecord(**row)
