"""Route handlers for Wave 1 AI SOC API."""
from fastapi import APIRouter, HTTPException
from pathlib import Path
from backend.src.api.models import HealthResponse, GraphResponse, NormalizedEvent, Alert
from backend.src.parsers.normalizer import normalize
from backend.src.graph.builder import build_graph
from backend.src.detection.rules import evaluate
from backend.src.fixtures.loader import load_ndjson

router = APIRouter()

# In-memory store (Phase 1 — not production)
_events: list[dict] = []
_alerts: list[dict] = []

FIXTURE_PATH = Path(__file__).parents[3] / "fixtures" / "ndjson" / "sample_events.ndjson"


@router.get("/health", response_model=HealthResponse)
def health():
    return HealthResponse(status="ok")


@router.get("/events")
def get_events():
    return _events


@router.post("/events", status_code=201)
def post_event(raw: dict):
    event = normalize(raw)
    _events.append(event.model_dump())
    new_alerts = evaluate(event)
    _alerts.extend(a.model_dump() for a in new_alerts)
    return event.model_dump()


@router.get("/timeline")
def get_timeline():
    return sorted(_events, key=lambda e: e.get("timestamp", ""))


@router.get("/graph", response_model=GraphResponse)
def get_graph():
    return build_graph(_events)


@router.get("/alerts")
def get_alerts():
    return _alerts


@router.post("/fixtures/load")
def load_fixtures():
    result = load_ndjson(FIXTURE_PATH, _events, normalize, evaluate)
    _alerts.extend(result.get("alert_list", []))
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return {"loaded": result["loaded"], "alerts": result["alerts"]}
