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

from backend.services.hunt_engine import PRESET_HUNTS, HuntEngine

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
