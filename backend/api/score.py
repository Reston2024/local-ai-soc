"""POST /api/score — risk-score entities for a detection or event set."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel

from backend.intelligence.risk_scorer import score_detection, score_entity, enrich_nodes_with_risk_score
from backend.intelligence.anomaly_rules import check_event_anomalies

log = logging.getLogger(__name__)
router = APIRouter()


class ScoreRequest(BaseModel):
    detection_id: str | None = None
    event_ids: list[str] | None = None


class ScoreResponse(BaseModel):
    scored_entities: dict[str, int] = {}
    top_entity: str | None = None
    top_score: int = 0
    enriched_nodes: list[dict] = []


@router.post("/score", response_model=ScoreResponse)
async def post_score(request: Request, body: ScoreRequest = None) -> ScoreResponse:  # type: ignore[assignment]
    """Return risk scores for entities associated with a detection or event set.

    Always returns HTTP 200. Returns empty result if detection_id not found.
    Persists risk_score back to the detections row in SQLite so GET /api/top-threats
    returns real ranked data (not all zeros).
    """
    if body is None:
        body = ScoreRequest()
    try:
        return await _compute_scores(request, body)
    except Exception as exc:
        log.warning("score endpoint error (returning empty): %s", exc)
        return ScoreResponse()


async def _compute_scores(request: Request, body: ScoreRequest) -> ScoreResponse:
    scored_entities: dict[str, int] = {}
    graph_nodes: list[dict] = []

    if body.detection_id:
        try:
            stores = request.app.state.stores
            sqlite_store = stores.sqlite

            row = await asyncio.to_thread(
                lambda: sqlite_store._conn.execute(
                    "SELECT severity, attack_technique, matched_event_ids FROM detections WHERE id = ?",
                    (body.detection_id,),
                ).fetchone()
            )
            if row:
                severity, technique, matched_ids_json = row
                import json
                event_ids = json.loads(matched_ids_json or "[]")

                # Score the detection itself
                det_score = score_detection(severity or "info", technique, anomaly_count=0)
                scored_entities[body.detection_id] = det_score

                # Persist risk_score back to SQLite so GET /api/top-threats returns real scores.
                await asyncio.to_thread(
                    lambda: (
                        sqlite_store._conn.execute(
                            "UPDATE detections SET risk_score = ? WHERE id = ?",
                            (det_score, body.detection_id),
                        ),
                        sqlite_store._conn.commit(),
                    )
                )

                # Try to score matched events from DuckDB
                if event_ids:
                    try:
                        duckdb_store = stores.duckdb
                        placeholders = ",".join("?" * len(event_ids))
                        events_rows = await duckdb_store.fetch_all(
                            f"SELECT event_id, process_name, severity, attack_technique, "
                            f"parent_process_name, process_path, dest_ip, dest_port "
                            f"FROM normalized_events WHERE event_id IN ({placeholders})",
                            event_ids,
                        )
                        for evt in events_rows:
                            flags = check_event_anomalies(dict(evt))
                            entity_name = evt.get("process_name") or evt.get("event_id", "unknown")
                            entity_score = score_entity(
                                entity_id=entity_name,
                                events=[dict(evt)],
                                detections=[{"severity": severity}],
                                anomaly_flags=flags,
                            )
                            scored_entities[entity_name] = entity_score
                    except Exception as dex:
                        log.debug("DuckDB event scoring skipped: %s", dex)
        except Exception as sex:
            log.debug("SQLite detection lookup skipped: %s", sex)

    if not scored_entities:
        return ScoreResponse()

    # Enrich graph nodes with risk scores so Cytoscape selectors (node[risk_score > 80]) work.
    enriched_nodes = enrich_nodes_with_risk_score(graph_nodes, scored_entities)

    top_entity = max(scored_entities, key=scored_entities.__getitem__)
    top_score = scored_entities[top_entity]
    return ScoreResponse(
        scored_entities=scored_entities,
        top_entity=top_entity,
        top_score=top_score,
        enriched_nodes=enriched_nodes,
    )
