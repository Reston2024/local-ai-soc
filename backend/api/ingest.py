"""
Ingest API — accept and store normalized security events.

Endpoints:
  POST /ingest/event       — ingest a single NormalizedEvent
  POST /ingest/events      — ingest a batch of NormalizedEvents (uses full pipeline)
  POST /ingest/file        — upload a raw file (EVTX, JSON, CSV) for full pipeline
  GET  /ingest/jobs/{id}   — poll ingestion job status

The /ingest/file and /ingest/events endpoints use IngestionLoader which
handles parsing, normalisation, deduplication, DuckDB inserts, Chroma
embedding, and SQLite graph extraction in one pipeline call.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse

from backend.core.logging import get_logger
from backend.core.rate_limit import limiter
from backend.models.event import NormalizedEvent
from backend.stores.chroma_store import DEFAULT_COLLECTION
from ingestion.loader import IngestionLoader, get_job_status

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


def _get_loader(request: Request) -> IngestionLoader:
    """Construct an IngestionLoader from app.state stores and ollama client."""
    return IngestionLoader(
        stores=request.app.state.stores,
        ollama_client=request.app.state.ollama,
    )


async def _store_event_direct(event: NormalizedEvent, request: Request) -> None:
    """
    Write a single event directly to DuckDB and optionally embed into Chroma.
    Used by the /event single-event endpoint for low-latency ingestion.
    """
    stores = request.app.state.stores

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


# ---------------------------------------------------------------------------
# Single event endpoint (fast path — no full pipeline overhead)
# ---------------------------------------------------------------------------


@router.post("/event", status_code=201)
async def ingest_event(event: NormalizedEvent, request: Request) -> JSONResponse:
    """
    Ingest a single pre-normalized event.

    Stores the event in DuckDB and enqueues an embedding for Chroma.
    Returns 201 with the stored event_id on success.
    """
    if not event.event_id:
        event = event.model_copy(update={"event_id": str(uuid4())})

    try:
        await _store_event_direct(event, request)
    except Exception as exc:
        log.error("Event ingest failed", event_id=event.event_id, error=str(exc))
        raise HTTPException(status_code=500, detail=f"Ingest failed: {exc}") from exc

    log.info("Event ingested", event_id=event.event_id, source_type=event.source_type)
    return JSONResponse(
        status_code=201,
        content={"event_id": event.event_id, "status": "ingested"},
    )


# ---------------------------------------------------------------------------
# Batch event endpoint (full pipeline)
# ---------------------------------------------------------------------------


@router.post("/events", status_code=201)
async def ingest_events(
    events: list[NormalizedEvent],
    request: Request,
    case_id: str | None = None,
) -> JSONResponse:
    """
    Ingest a batch of pre-normalized events using the full ingestion pipeline.

    Runs: normalisation → deduplication → DuckDB batch INSERT →
          Chroma embeddings → entity/edge extraction → SQLite graph.

    Returns 201 with parsed/loaded/embedded/edges_created counts.
    """
    if not events:
        raise HTTPException(status_code=400, detail="Event list is empty")
    if len(events) > 10_000:
        raise HTTPException(
            status_code=400,
            detail="Batch size exceeds limit of 10,000 events per request",
        )

    # Apply case_id override if provided
    if case_id:
        events = [
            e.model_copy(update={"case_id": case_id}) if not e.case_id else e
            for e in events
        ]

    loader = _get_loader(request)
    try:
        result = await loader.ingest_events(events)
    except Exception as exc:
        log.error("Batch ingest failed", count=len(events), error=str(exc))
        raise HTTPException(status_code=500, detail=f"Batch ingest failed: {exc}") from exc

    log.info(
        "Batch ingest complete",
        total=len(events),
        loaded=result.loaded,
        embedded=result.embedded,
        edges_created=result.edges_created,
        errors=len(result.errors),
    )
    return JSONResponse(
        status_code=201,
        content={
            "parsed": len(events),
            "loaded": result.loaded,
            "embedded": result.embedded,
            "edges_created": result.edges_created,
            "errors": result.errors[:20],  # cap error list in response
        },
    )


# ---------------------------------------------------------------------------
# File upload endpoint (async, background job)
# ---------------------------------------------------------------------------


async def _run_ingestion_job(
    file_path: str,
    case_id: str | None,
    job_id: str,
    stores: Any,
    ollama: Any,
) -> None:
    """Background task that runs the full ingestion pipeline for an uploaded file."""
    from ingestion.loader import IngestionLoader, _set_job

    loader = IngestionLoader(stores=stores, ollama_client=ollama)
    try:
        result = await loader.ingest_file(file_path, case_id=case_id, job_id=job_id)
        log.info(
            "Background ingestion job complete",
            job_id=job_id,
            result=str(result),
        )
    except Exception as exc:
        log.error(
            "Background ingestion job failed",
            job_id=job_id,
            error=str(exc),
        )
        _set_job(job_id, "error", error=str(exc))


@limiter.limit("10/minute")
@router.post("/file", status_code=202)
async def upload_file(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    case_id: str | None = None,
) -> JSONResponse:
    """
    Accept a raw file upload for asynchronous parsing and ingestion.

    Supported formats: .evtx, .json, .ndjson, .jsonl, .csv

    The file is saved to data/uploads/ and a background parse + ingest task
    is queued immediately.

    Returns 202 Accepted with a job_id.  Poll GET /ingest/jobs/{job_id}
    for progress.
    """
    import hashlib

    settings = request.app.state.settings
    upload_dir = Path(settings.DATA_DIR) / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)

    filename = file.filename or "unknown"
    suffix = Path(filename).suffix.lower()
    allowed = {".evtx", ".json", ".ndjson", ".jsonl", ".csv"}
    if suffix not in allowed:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type {suffix!r}. Allowed: {sorted(allowed)}",
        )

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
        upload_filename=filename,
        size_bytes=len(content),
        dest=str(dest_path),
        case_id=case_id,
    )

    # Mark job as queued in the in-memory tracker
    from ingestion.loader import _set_job
    _set_job(job_id, "queued")

    # Schedule background ingestion
    background_tasks.add_task(
        _run_ingestion_job,
        file_path=str(dest_path),
        case_id=case_id,
        job_id=job_id,
        stores=request.app.state.stores,
        ollama=request.app.state.ollama,
    )

    return JSONResponse(
        status_code=202,
        content={
            "job_id": job_id,
            "status": "queued",
            "filename": filename,
            "size_bytes": len(content),
            "message": "File queued for ingestion. Poll /ingest/jobs/{job_id} for progress.",
        },
    )


# ---------------------------------------------------------------------------
# Legacy upload endpoint (preserved for backwards compatibility)
# ---------------------------------------------------------------------------


@router.post("/upload", status_code=202)
async def upload_file_legacy(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    case_id: str | None = None,
) -> JSONResponse:
    """
    Legacy upload endpoint — delegates to /ingest/file behaviour.

    Preserved for backwards compatibility with clients that target /ingest/upload.
    """
    return await upload_file(request, background_tasks, file, case_id)


# ---------------------------------------------------------------------------
# Job status endpoint
# ---------------------------------------------------------------------------


@router.get("/jobs/{job_id}")
async def get_job(job_id: str) -> JSONResponse:
    """
    Return the current status and result of an ingestion job.

    Status values:
    - "queued"   — job is waiting to start
    - "running"  — job is actively processing
    - "complete" — job finished successfully
    - "error"    — job encountered a fatal error

    Returns 404 if the job_id is not known.
    """
    status = get_job_status(job_id)
    if status is None:
        raise HTTPException(
            status_code=404,
            detail=f"Job {job_id!r} not found. Jobs are lost on server restart.",
        )
    return JSONResponse(content=status)
