"""
backend.startup.routers — Router mounting.

All app.include_router() calls in one place.  No business logic here.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import Depends
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.api.detect import router as detect_router
from backend.api.events import router as events_router
from backend.api.export import router as export_router
from backend.api.graph import router as graph_router
from backend.api.health import router as health_router
from backend.api.ingest import router as ingest_router
from backend.api.perf import router as perf_router
from backend.api.query import router as query_router
from backend.core.auth import verify_token
from backend.core.logging import get_logger

if TYPE_CHECKING:
    from fastapi import FastAPI, Request

log = get_logger(__name__)


def mount_routers(app: "FastAPI") -> None:
    """Mount all API routers onto the FastAPI application.

    Core routers are mounted unconditionally; optional/deferred routers are
    wrapped in try/except so a missing module degrades gracefully.
    """
    # ------------------------------------------------------------------
    # Core routers (always present)
    # ------------------------------------------------------------------
    app.include_router(health_router)                                                              # /health
    app.include_router(events_router,  prefix="/api", dependencies=[Depends(verify_token)])        # /api/events
    app.include_router(ingest_router,  prefix="/api", dependencies=[Depends(verify_token)])        # /api/ingest
    app.include_router(query_router,   prefix="/api", dependencies=[Depends(verify_token)])        # /api/query
    app.include_router(detect_router,  prefix="/api", dependencies=[Depends(verify_token)])        # /api/detect
    app.include_router(graph_router,   prefix="/api", dependencies=[Depends(verify_token)])        # /api/graph
    app.include_router(export_router,  prefix="/api", dependencies=[Depends(verify_token)])        # /api/export
    app.include_router(perf_router,    prefix="/api", dependencies=[Depends(verify_token)])        # /api/metrics/perf

    # ------------------------------------------------------------------
    # Deferred routers (graceful degradation if modules absent)
    # ------------------------------------------------------------------
    try:
        from backend.causality.causality_routes import causality_router
        app.include_router(causality_router, prefix="/api", dependencies=[Depends(verify_token)])
        log.info("Causality router mounted at /api/causality")
    except ImportError as exc:
        log.warning("Causality module not available — skipping router mount: %s", exc)

    try:
        from backend.investigation.investigation_routes import investigation_router
        app.include_router(investigation_router, dependencies=[Depends(verify_token)])
        log.info("Investigation router mounted at /api")
    except ImportError as exc:
        log.warning("Investigation module not available — skipping router mount: %s", exc)

    try:
        from backend.api.correlate import router as correlate_router
        app.include_router(correlate_router, prefix="/api", dependencies=[Depends(verify_token)])
        log.info("Correlate router mounted at /api/correlate")
    except ImportError as exc:
        log.warning("Correlate router not available: %s", exc)

    try:
        from backend.api.investigate import router as investigate_router
        app.include_router(investigate_router, prefix="/api", dependencies=[Depends(verify_token)])
        log.info("Investigate router mounted at /api/investigate")
    except ImportError as exc:
        log.warning("Investigate router not available: %s", exc)

    try:
        from backend.api.telemetry import router as telemetry_router
        app.include_router(telemetry_router, prefix="/api", dependencies=[Depends(verify_token)])
        log.info("Telemetry router mounted at /api/telemetry")
    except ImportError as exc:
        log.warning("Telemetry module not available — skipping router mount: %s", exc)

    try:
        from backend.api.score import router as score_router
        app.include_router(score_router, prefix="/api", dependencies=[Depends(verify_token)])
        log.info("score router mounted at /api/score")
    except ImportError as exc:
        log.warning("score router not available: %s", exc)

    try:
        from backend.api.top_threats import router as top_threats_router
        app.include_router(top_threats_router, prefix="/api", dependencies=[Depends(verify_token)])
        log.info("top-threats router mounted at /api/top-threats")
    except ImportError as exc:
        log.warning("top-threats router not available: %s", exc)

    try:
        from backend.api.explain import router as explain_router
        app.include_router(explain_router, prefix="/api", dependencies=[Depends(verify_token)])
        log.info("explain router mounted at /api/explain")
    except ImportError as exc:
        log.warning("explain router not available: %s", exc)

    try:
        from backend.api.investigations import router as investigations_router
        app.include_router(investigations_router, prefix="/api", dependencies=[Depends(verify_token)])
        log.info("investigations router mounted at /api/investigations")
    except ImportError as exc:
        log.warning("investigations router not available: %s", exc)

    try:
        from backend.api.metrics import router as metrics_router
        app.include_router(metrics_router, prefix="/api", dependencies=[Depends(verify_token)])
        log.info("metrics router mounted at /api/metrics")
    except ImportError as exc:
        log.warning("metrics router not available: %s", exc)

    try:
        from backend.api.timeline import router as timeline_router
        app.include_router(timeline_router, dependencies=[Depends(verify_token)])
        log.info("timeline router mounted at /api/investigations/{id}/timeline")
    except ImportError as exc:
        log.warning("timeline router not available: %s", exc)

    try:
        from backend.api.chat import router as chat_router
        app.include_router(chat_router, dependencies=[Depends(verify_token)])
        log.info("chat router mounted at /api/investigations/{id}/chat")
    except ImportError as exc:
        log.warning("chat router not available: %s", exc)

    try:
        from backend.api.playbooks import router as playbooks_router
        from backend.api.playbooks import runs_router as playbook_runs_router
        app.include_router(playbooks_router, dependencies=[Depends(verify_token)])
        app.include_router(playbook_runs_router, dependencies=[Depends(verify_token)])
        log.info("playbooks router mounted at /api/playbooks and /api/playbook-runs")
    except ImportError as exc:
        log.warning("playbooks router not available: %s", exc)

    try:
        from backend.api.reports import router as reports_router
        app.include_router(reports_router, dependencies=[Depends(verify_token)])
        log.info("reports router mounted at /api/reports")
    except ImportError as exc:
        log.warning("reports router not available: %s", exc)

    try:
        from backend.api.report_templates import router as report_templates_router
        app.include_router(report_templates_router, dependencies=[Depends(verify_token)])
        log.info("report_templates router mounted at /api/reports (templates)")
    except ImportError as exc:
        log.warning("report_templates router not available: %s", exc)

    try:
        from backend.api.analytics import router as analytics_router
        app.include_router(analytics_router, dependencies=[Depends(verify_token)])
        log.info("analytics router mounted at /api/analytics")
    except ImportError as exc:
        log.warning("analytics router not available: %s", exc)

    try:
        from backend.api.operators import router as operators_router
        app.include_router(operators_router, prefix="/api", dependencies=[Depends(verify_token)])
        log.info("operators router mounted at /api/operators")
    except ImportError as exc:
        log.warning("operators router not available: %s", exc)

    try:
        from backend.api.settings import router as settings_router
        app.include_router(settings_router, prefix="/api", dependencies=[Depends(verify_token)])
        log.info("settings router mounted at /api/settings")
    except ImportError as exc:
        log.warning("settings router not available: %s", exc)

    try:
        from backend.api.provenance import router as provenance_router
        app.include_router(provenance_router, dependencies=[Depends(verify_token)])
        log.info("provenance router mounted at /api/provenance")
    except ImportError as exc:
        log.warning("provenance router not available: %s", exc)

    try:
        from backend.api.firewall import router as firewall_router
        app.include_router(firewall_router, prefix="/api", dependencies=[Depends(verify_token)])
        log.info("Firewall router mounted at /api/firewall")
    except ImportError as exc:
        log.warning("Firewall router not available: %s", exc)

    try:
        from backend.api.recommendations import router as recommendations_router
        app.include_router(recommendations_router, dependencies=[Depends(verify_token)])
        log.info("Recommendations router mounted at /api/recommendations")
    except ImportError as exc:
        log.warning("Recommendations router not available: %s", exc)

    try:
        from backend.api.receipts import router as receipts_router
        app.include_router(receipts_router, dependencies=[Depends(verify_token)])
        log.info("Receipts router mounted at /api/receipts")
    except ImportError as exc:
        log.warning("Receipts router not available: %s", exc)

    try:
        from backend.api.notifications import router as notifications_router
        app.include_router(notifications_router, dependencies=[Depends(verify_token)])
        log.info("Notifications router mounted at /api/notifications")
    except ImportError as exc:
        log.warning("Notifications router not available: %s", exc)

    try:
        from backend.api.hunting import router as hunting_router
        app.include_router(hunting_router, prefix="/api", dependencies=[Depends(verify_token)])
        log.info("Hunting router mounted at /api/hunts")
    except Exception as exc:
        log.warning("Hunting router not available: %s", exc)

    try:
        from backend.api.osint_api import router as osint_router
        app.include_router(osint_router, prefix="/api", dependencies=[Depends(verify_token)])
        log.info("OSINT router mounted at /api/osint")
    except Exception as exc:
        log.warning("OSINT router not available: %s", exc)

    try:
        from backend.api import intel as intel_api
        app.include_router(intel_api.router, prefix="/api/intel", tags=["intel"])
        log.info("Intel router mounted at /api/intel")
    except Exception as exc:
        log.warning("Intel router not available: %s", exc)

    try:
        from backend.api.assets import router as assets_router
        app.include_router(assets_router, prefix="/api", dependencies=[Depends(verify_token)])
        log.info("Assets router registered at /api/assets")
    except Exception as exc:
        log.warning("Assets router failed to load: %s", exc)

    try:
        from backend.api.attack import router as attack_router
        app.include_router(attack_router, prefix="/api", dependencies=[Depends(verify_token)])
        log.info("Attack router registered at /api/attack")
    except Exception as exc:
        log.warning("Attack router failed to load: %s", exc)

    try:
        from backend.api.triage import router as triage_router
        app.include_router(triage_router, prefix="/api", dependencies=[Depends(verify_token)])
        log.info("Triage router mounted at /api/triage")
    except ImportError as exc:
        log.warning("Triage router not available: %s", exc)

    try:
        from backend.api.atomics import router as atomics_router
        app.include_router(atomics_router, prefix="/api", dependencies=[Depends(verify_token)])
        log.info("Atomics router mounted at /api/atomics")
    except Exception as exc:
        log.warning("Atomics router not available: %s", exc)

    try:
        from backend.api.map import router as map_router
        app.include_router(map_router, prefix="/api/map", tags=["map"])
        log.info("Map router mounted at /api/map")
    except Exception as exc:
        log.warning("Map router not available: %s", exc)

    try:
        from backend.api.anomaly import router as anomaly_router
        app.include_router(anomaly_router)
        log.info("Anomaly router mounted at /api/anomaly")
    except Exception as exc:
        log.warning("Anomaly router not available: %s", exc)

    try:
        from backend.api.feedback import feedback_router
        app.include_router(feedback_router, prefix="/api/feedback", tags=["feedback"])
        log.info("Feedback router mounted at /api/feedback (Phase 44)")
    except Exception as exc:
        log.warning("Feedback router not available: %s", exc)

    try:
        from backend.api.coverage import router as coverage_router
        app.include_router(coverage_router, dependencies=[Depends(verify_token)])
        log.info("Coverage router mounted at /api/coverage (Phase 40)")
    except Exception as exc:
        log.warning("Coverage router not available: %s", exc)

    try:
        from backend.api.privacy import privacy_router as _privacy_router
        app.include_router(_privacy_router)
        log.info("Privacy router mounted at /api/privacy (Phase 53)")
    except Exception as exc:
        log.warning("Phase 53 privacy router failed to load: %s", exc)

    try:
        from backend.api.detection_quality import router as detection_quality_router
        app.include_router(detection_quality_router, prefix="/api", dependencies=[Depends(verify_token)])
        log.info("Detection quality router mounted at /api/detections/quality")
    except Exception as exc:
        log.warning("Detection quality router not available: %s", exc)
