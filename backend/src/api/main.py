"""Wave 1 AI SOC Brain — FastAPI application entry point."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.src.api.routes import router

# Phase 6 causality endpoints (deferred — graceful if causality_routes has an import error)
try:
    from backend.causality.causality_routes import causality_router as _causality_router
except ImportError:
    _causality_router = None


def create_app() -> FastAPI:
    app = FastAPI(
        title="AI SOC Brain — Wave 1",
        description="Phase 1 foundation. In-memory store, simple rules. Not production.",
        version="0.1.0",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)
    if _causality_router is not None:
        app.include_router(_causality_router)
    return app


app = create_app()
