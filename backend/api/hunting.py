"""
Hunting API — NL→SQL threat hunting engine.

POST /api/hunts/query       — Run a hunt query (NL→SQL via Ollama)
GET  /api/hunts/presets     — List preset hunt definitions
GET  /api/hunts/{hunt_id}/results — Retrieve stored hunt results
"""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, field_validator

from backend.core.logging import get_logger
from backend.services.hunt_engine import PRESET_HUNTS, HuntEngine

log = get_logger(__name__)
router = APIRouter(prefix="/hunts", tags=["hunting"])


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class HuntQueryRequest(BaseModel):
    query: str
    analyst_id: str = "unknown"

    @field_validator("query")
    @classmethod
    def query_must_be_non_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("query must not be blank")
        return v


# ---------------------------------------------------------------------------
# POST /api/hunts/query
# ---------------------------------------------------------------------------


@router.post("/query")
async def run_hunt_query(body: HuntQueryRequest, request: Request) -> JSONResponse:
    """
    Run a natural-language threat hunt query.

    Translates the query to DuckDB SQL via Ollama, validates and executes it,
    ranks results by severity/recency, and persists the hunt record.
    """
    stores = request.app.state.stores
    ollama_client = request.app.state.ollama

    engine = HuntEngine(
        duckdb_store=stores.duckdb,
        sqlite_store=stores.sqlite,
        ollama_client=ollama_client,
    )

    try:
        result = await engine.run(body.query, analyst_id=body.analyst_id)
    except ValueError as exc:
        return JSONResponse(
            status_code=422,
            content={"error": str(exc), "sql_rejected": True},
        )
    except Exception as exc:
        log.error("Hunt query failed", query=body.query, error=str(exc))
        return JSONResponse(
            status_code=500,
            content={"error": f"Hunt failed: {exc}", "sql_rejected": False},
        )

    return JSONResponse(
        status_code=200,
        content=json.loads(
            json.dumps(
                {
                    "hunt_id": result.hunt_id,
                    "query": result.query,
                    "sql": result.sql,
                    "rows": result.rows,
                    "row_count": result.row_count,
                    "created_at": result.created_at,
                },
                default=str,
            )
        ),
    )


# ---------------------------------------------------------------------------
# GET /api/hunts/presets
# NOTE: This route must be defined BEFORE /{hunt_id}/results to avoid
# FastAPI routing /presets as a hunt_id path parameter.
# ---------------------------------------------------------------------------


@router.get("/presets")
async def get_hunt_presets() -> JSONResponse:
    """Return the 6 preset hunt definitions with MITRE tags."""
    return JSONResponse(content={"presets": PRESET_HUNTS})


# ---------------------------------------------------------------------------
# GET /api/hunts/history — must be before /{hunt_id} catch-all
# ---------------------------------------------------------------------------


@router.get("/history")
async def get_hunt_history(
    request: Request,
    analyst_id: str | None = None,
    limit: int = 20,
) -> JSONResponse:
    """Return recent hunt records ordered by created_at DESC."""
    stores = request.app.state.stores
    hunts = await asyncio.to_thread(stores.sqlite.list_hunts, analyst_id, limit)
    # Omit results_json (large) — return metadata only
    records = [
        {
            "hunt_id": h["hunt_id"],
            "query": h["query"],
            "sql_text": h.get("sql_text", ""),
            "row_count": h.get("row_count", 0),
            "analyst_id": h.get("analyst_id", ""),
            "created_at": h.get("created_at", ""),
        }
        for h in hunts
    ]
    return JSONResponse(content={"hunts": records})


# ---------------------------------------------------------------------------
# GET /api/hunts/{hunt_id}/results
# ---------------------------------------------------------------------------


@router.get("/{hunt_id}/results")
async def get_hunt_results(hunt_id: str, request: Request) -> JSONResponse:
    """Retrieve stored hunt results by hunt_id."""
    stores = request.app.state.stores

    hunt = await asyncio.to_thread(stores.sqlite.get_hunt, hunt_id)
    if hunt is None:
        raise HTTPException(status_code=404, detail=f"Hunt '{hunt_id}' not found")

    # Parse results_json back to list
    try:
        rows = json.loads(hunt.get("results_json", "[]"))
    except (json.JSONDecodeError, TypeError):
        rows = []

    return JSONResponse(
        content={
            "hunt_id": hunt["hunt_id"],
            "query": hunt["query"],
            "sql": hunt["sql_text"],
            "rows": rows,
            "row_count": hunt["row_count"],
            "analyst_id": hunt["analyst_id"],
            "created_at": hunt["created_at"],
        }
    )
