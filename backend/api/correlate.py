"""
Correlation API — event clustering endpoints.
"""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.core.logging import get_logger

log = get_logger(__name__)
router = APIRouter(prefix="/correlate", tags=["correlate"])


@router.post("")
async def correlate_events(
    request: Request, window_minutes: int = 10
) -> JSONResponse:
    """Run entity-based and temporal correlation on stored events."""
    stores = request.app.state.stores

    from correlation.clustering import cluster_events_by_entity, cluster_events_by_time

    # Both functions are async and accept (stores, ...) signature
    entity_clusters = await cluster_events_by_entity(stores, event_ids=[])
    time_clusters = await cluster_events_by_time(stores, window_minutes=window_minutes)

    return JSONResponse(
        content={
            "entity_clusters": [
                {
                    "cluster_id": c.cluster_id,
                    "events": c.events,
                    "shared_entities": c.shared_entities,
                    "cluster_type": c.cluster_type,
                    "relatedness_score": c.relatedness_score,
                    "time_range": (
                        [c.time_range[0].isoformat(), c.time_range[1].isoformat()]
                        if c.time_range
                        else None
                    ),
                }
                for c in entity_clusters
            ],
            "time_clusters": [
                {
                    "cluster_id": c.cluster_id,
                    "events": c.events,
                    "shared_entities": c.shared_entities,
                    "cluster_type": c.cluster_type,
                    "relatedness_score": c.relatedness_score,
                    "time_range": (
                        [c.time_range[0].isoformat(), c.time_range[1].isoformat()]
                        if c.time_range
                        else None
                    ),
                }
                for c in time_clusters
            ],
            "total_entity_clusters": len(entity_clusters),
            "total_time_clusters": len(time_clusters),
        }
    )
