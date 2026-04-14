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
    CopilotResponseRecord,
    DetectionProvenanceRecord,
    IngestProvenanceRecord,
    LlmProvenanceRecord,
    PlaybookProvenanceRecord,
)

router = APIRouter(prefix="/api/provenance", tags=["provenance"])


@router.get("/recent")
async def get_recent_provenance(
    request: Request,
    limit: int = 20,
    stores: Stores = Depends(get_stores),
) -> dict:
    """
    Return recent provenance records across all four tables (ingest, detection, LLM, playbook),
    sorted by created_at DESC. Used by the UI to auto-populate the recent records list.
    """
    def _query() -> dict:
        conn = stores.sqlite._conn

        def safe_query(sql: str, params: tuple = ()) -> list[dict]:
            try:
                rows = conn.execute(sql, params).fetchall()
                return [dict(r) for r in rows]
            except Exception:
                return []

        detections = safe_query(
            """
            SELECT detection_id AS record_id, rule_id, rule_title AS label,
                   detected_at AS created_at, 'detection' AS record_type
            FROM detection_provenance
            ORDER BY detected_at DESC LIMIT ?
            """,
            (limit,),
        )
        llm = safe_query(
            """
            SELECT audit_id AS record_id, model_id AS label, prompt_template_name,
                   created_at, 'llm' AS record_type
            FROM llm_audit_provenance
            ORDER BY created_at DESC LIMIT ?
            """,
            (limit,),
        )
        playbook = safe_query(
            """
            SELECT run_id AS record_id, playbook_id AS label,
                   created_at, 'playbook' AS record_type
            FROM playbook_run_provenance
            ORDER BY created_at DESC LIMIT ?
            """,
            (limit,),
        )
        ingest = safe_query(
            """
            SELECT ip.prov_id AS record_id, ip.source_file AS label,
                   ip.ingested_at AS created_at, 'ingest' AS record_type
            FROM ingest_provenance ip
            ORDER BY ip.ingested_at DESC LIMIT ?
            """,
            (limit,),
        )

        combined = detections + llm + playbook + ingest
        combined.sort(key=lambda r: r.get("created_at") or "", reverse=True)
        return {"records": combined[:limit]}

    return await asyncio.to_thread(_query)


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


@router.get(
    "/copilot/response/{audit_id}",
    response_model=CopilotResponseRecord,
    summary="Get AI Copilot response trust record",
    description=(
        "Return the trust metadata for a given AI Copilot response: model ID, "
        "grounding event IDs (cited sources), confidence score, and whether the "
        "response was grounded in retrieved evidence. Note: response text is not "
        "stored — this endpoint surfaces trust signals for audit and UI display."
    ),
)
async def get_copilot_response(
    audit_id: str,
    request: Request,
    ctx: OperatorContext = Depends(require_role("analyst", "admin")),
    stores: Stores = Depends(get_stores),
) -> CopilotResponseRecord:
    row = await asyncio.to_thread(
        stores.sqlite.get_llm_provenance, audit_id
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Copilot response not found")
    grounding_ids = row.get("grounding_event_ids") or []
    return CopilotResponseRecord(
        audit_id=row["audit_id"],
        model_id=row["model_id"],
        grounding_event_ids=grounding_ids,
        confidence_score=row.get("confidence_score"),
        is_grounded=len(grounding_ids) > 0,
        prompt_template_name=row.get("prompt_template_name"),
        operator_id=row.get("operator_id"),
        created_at=row["created_at"],
    )
