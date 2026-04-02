"""Evidence provenance API endpoints.

Provides read-only access to provenance records stored in SQLite so analysts
can audit exactly which software versions and raw inputs produced each
detection or ingest event.
"""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException

from backend.core.deps import Stores, get_stores
from backend.models.provenance import DetectionProvenanceRecord, IngestProvenanceRecord

router = APIRouter(prefix="/api/provenance", tags=["provenance"])


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
    stores: Stores = Depends(get_stores),
) -> DetectionProvenanceRecord:
    row = await asyncio.to_thread(
        stores.sqlite.get_detection_provenance, detection_id
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Provenance record not found")
    return DetectionProvenanceRecord(**row)


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
    stores: Stores = Depends(get_stores),
) -> IngestProvenanceRecord:
    row = await asyncio.to_thread(
        stores.sqlite.get_ingest_provenance, event_id
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Provenance record not found")
    # get_ingest_provenance returns keys from ingest_provenance; we need event_id too
    row["event_id"] = event_id
    return IngestProvenanceRecord(**row)
