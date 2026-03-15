"""
Ingest API — accept and store normalized security events.

Endpoints:
  POST /ingest/event       — ingest a single NormalizedEvent
  POST /ingest/events      — ingest a batch of NormalizedEvents
  POST /ingest/upload      — upload a raw file (EVTX, JSON, CSV) for parsing
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request, UploadFile, File
from fastapi.responses import JSONResponse

from backend.core.logging import get_logger
from backend.models.event import NormalizedEvent
from backend.stores.chroma_store import DEFAULT_COLLECTION

log = get_logger(__name__)
router = APIRouter(prefix="/ingest", tags=["ingest"])

# DuckDB INSERT statement matching NormalizedEvent column order
_INSERT_EVENT_SQL = """
INSERT OR REPLACE INTO normalized_events (
    event_id, timestamp, ingested_at, source_type, source_file,
    hostname, username, process_name, process_id,
    parent_process_name, parent_process_id,
    file_path, file_hash_sha256, command_line,
    src_ip, src_port, dst_ip, dst_port, domain, url,
    event_type, severity, confidence, detection_source,
    attack_technique, attack_tactic,
    raw_event, tags, case_id
) VALUES (
    ?, ?, ?, ?, ?,
    ?, ?, ?, ?,
    ?, ?,
    ?, ?, ?,
    ?, ?, ?, ?, ?, ?,
    ?, ?, ?, ?,
    ?, ?,
    ?, ?, ?
)
"""


async def _store_event(event: NormalizedEvent, request: Request) -> None:
    """Write a single event to DuckDB and optionally embed into Chroma."""
    stores = request.app.state.stores

    # Ensure ingested_at is set
    if not event.ingested_at:
        event = event.model_copy(
            update={"ingested_at": datetime.now(tz=timezone.utc)}
        )

    row = event.to_duckdb_row()
    await stores.duckdb.execute_write(_INSERT_EVENT_SQL, list(row))

    # Generate embedding and store in Chroma (non-fatal if Ollama is offline)
    try:
        ollama = request.app.state.ollama
        text = event.to_embedding_text()
        if text.strip():
            embedding = await ollama.embed(text)
            if embedding:
                metadata: dict[str, Any] = {
                    "event_id": event.event_id,
                    "event_type": event.event_type or "",
                    "hostname": event.hostname or "",
                    "severity": event.severity or "",
                    "case_id": event.case_id or "",
                }
                await stores.chroma.add_documents_async(
                    collection_name=DEFAULT_COLLECTION,
                    ids=[event.event_id],
                    documents=[text],
                    embeddings=[embedding],
                    metadatas=[metadata],
                )
    except Exception as exc:
        log.warning(
            "Chroma embedding skipped",
            event_id=event.event_id,
            error=str(exc),
        )


@router.post("/event", status_code=201)
async def ingest_event(event: NormalizedEvent, request: Request) -> JSONResponse:
    """
    Ingest a single pre-normalized event.

    Stores the event in DuckDB and enqueues an embedding for Chroma.
    Returns 201 with the stored event_id on success.
    """
    # Assign event_id if not provided
    if not event.event_id:
        event = event.model_copy(update={"event_id": str(uuid4())})

    try:
        await _store_event(event, request)
    except Exception as exc:
        log.error("Event ingest failed", event_id=event.event_id, error=str(exc))
        raise HTTPException(status_code=500, detail=f"Ingest failed: {exc}") from exc

    log.info("Event ingested", event_id=event.event_id, source_type=event.source_type)
    return JSONResponse(
        status_code=201,
        content={"event_id": event.event_id, "status": "ingested"},
    )


@router.post("/events", status_code=201)
async def ingest_events(events: list[NormalizedEvent], request: Request) -> JSONResponse:
    """
    Ingest a batch of pre-normalized events.

    Events are stored sequentially.  Failed events are logged and skipped;
    the response reports success and failure counts.
    """
    if not events:
        raise HTTPException(status_code=400, detail="Event list is empty")
    if len(events) > 10_000:
        raise HTTPException(
            status_code=400,
            detail="Batch size exceeds limit of 10,000 events per request",
        )

    ingested_ids: list[str] = []
    failed_ids: list[str] = []

    for event in events:
        if not event.event_id:
            event = event.model_copy(update={"event_id": str(uuid4())})
        try:
            await _store_event(event, request)
            ingested_ids.append(event.event_id)
        except Exception as exc:
            log.error("Batch event ingest failed", event_id=event.event_id, error=str(exc))
            failed_ids.append(event.event_id)

    log.info(
        "Batch ingest complete",
        total=len(events),
        ingested=len(ingested_ids),
        failed=len(failed_ids),
    )
    return JSONResponse(
        status_code=201,
        content={
            "ingested": len(ingested_ids),
            "failed": len(failed_ids),
            "failed_ids": failed_ids,
        },
    )


@router.post("/upload", status_code=202)
async def upload_file(
    request: Request,
    file: UploadFile = File(...),
    case_id: str | None = None,
) -> JSONResponse:
    """
    Accept a raw file upload for asynchronous parsing and ingestion.

    Supported formats: .evtx, .json, .ndjson, .csv
    The file is saved to data/uploads/ and a background parse task is queued.

    Returns 202 Accepted immediately; poll /ingest/status/{job_id} for progress.
    """
    import hashlib
    from pathlib import Path

    settings = request.app.state.settings
    upload_dir = Path(settings.DATA_DIR) / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)

    # Basic validation
    filename = file.filename or "unknown"
    suffix = Path(filename).suffix.lower()
    allowed = {".evtx", ".json", ".ndjson", ".jsonl", ".csv"}
    if suffix not in allowed:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type {suffix!r}. Allowed: {sorted(allowed)}",
        )

    # Save to disk
    content = await file.read()
    if len(content) > 500 * 1024 * 1024:  # 500 MB hard limit
        raise HTTPException(status_code=413, detail="File exceeds 500 MB limit")

    job_id = str(uuid4())
    file_hash = hashlib.sha256(content).hexdigest()[:16]
    dest_path = upload_dir / f"{job_id}_{file_hash}{suffix}"

    await asyncio.to_thread(dest_path.write_bytes, content)

    log.info(
        "File uploaded",
        job_id=job_id,
        filename=filename,
        size_bytes=len(content),
        dest=str(dest_path),
        case_id=case_id,
    )

    # TODO (Phase 2): enqueue parse job to ingestion pipeline
    return JSONResponse(
        status_code=202,
        content={
            "job_id": job_id,
            "status": "queued",
            "filename": filename,
            "size_bytes": len(content),
            "message": "File queued for parsing. Ingestion pipeline not yet implemented.",
        },
    )
