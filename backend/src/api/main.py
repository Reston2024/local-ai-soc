"""Wave 1 AI SOC Brain — FastAPI application entry point."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.src.api.routes import router


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
    return app


app = create_app()
