"""
FastAPI dependency injection helpers.

Usage in route functions::

    from backend.core.deps import get_settings, get_stores, get_ollama

    @router.get("/example")
    async def example(
        settings: Settings = Depends(get_settings),
        stores: Stores = Depends(get_stores),
    ):
        ...
"""

from typing import TYPE_CHECKING, Annotated

from fastapi import Depends, Request

from backend.core.config import Settings

if TYPE_CHECKING:
    from backend.stores.chroma_store import ChromaStore
    from backend.stores.duckdb_store import DuckDBStore
    from backend.stores.sqlite_store import SQLiteStore
    from backend.services.ollama_client import OllamaClient


class Stores:
    """
    Container for all data-store handles that live on app.state.

    Populated during the lifespan context manager in main.py.
    """

    def __init__(
        self,
        duckdb: "DuckDBStore",
        chroma: "ChromaStore",
        sqlite: "SQLiteStore",
    ) -> None:
        self.duckdb = duckdb
        self.chroma = chroma
        self.sqlite = sqlite


# ---------------------------------------------------------------------------
# Dependency providers
# ---------------------------------------------------------------------------


def get_settings(request: Request) -> Settings:
    """Return the application Settings instance stored on app.state."""
    return request.app.state.settings  # type: ignore[no-any-return]


def get_stores(request: Request) -> Stores:
    """Return the Stores container stored on app.state."""
    return request.app.state.stores  # type: ignore[no-any-return]


def get_ollama(request: Request) -> "OllamaClient":
    """Return the OllamaClient instance stored on app.state."""
    return request.app.state.ollama  # type: ignore[no-any-return]


# Annotated type aliases for concise route signatures
SettingsDep = Annotated[Settings, Depends(get_settings)]
StoresDep = Annotated[Stores, Depends(get_stores)]
OllamaDep = Annotated["OllamaClient", Depends(get_ollama)]
