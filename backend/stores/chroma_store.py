"""
Chroma vector store wrapper.

Supports two client modes (selected at construction time):
- Remote HttpClient: when chroma_url is set (e.g. "http://192.168.1.22:8200")
- Local PersistentClient: fallback when chroma_url is empty

Collections are keyed by name; the default collection for SOC evidence
embeddings is "soc_evidence".

All Chroma calls are blocking (Chroma's Python client is synchronous) so
they must be wrapped in asyncio.to_thread() when called from async code.
"""

import asyncio
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

import chromadb
from chromadb import Collection
from chromadb.config import Settings as ChromaSettings

from backend.core.logging import get_logger

log = get_logger(__name__)

DEFAULT_COLLECTION = "soc_evidence"


class ChromaStore:
    """
    Thin wrapper around a Chroma client (HttpClient or PersistentClient).

    Pass chroma_url to connect to a remote Chroma server; leave it empty
    to use a local PersistentClient at {data_dir}/chroma.
    """

    def __init__(self, data_dir: str, chroma_url: str = "", chroma_token: str = "") -> None:
        remote_ok = False
        if chroma_url:
            parsed = urlparse(chroma_url)
            host = parsed.hostname or "localhost"
            port = parsed.port or 8000
            ssl = parsed.scheme == "https"
            headers = {"X-Chroma-Token": chroma_token} if chroma_token else {}
            try:
                self._client = chromadb.HttpClient(
                    host=host,
                    port=port,
                    ssl=ssl,
                    headers=headers,
                    settings=ChromaSettings(anonymized_telemetry=False),
                )
                log.info("Chroma store initialised (remote)", url=chroma_url)
                remote_ok = True
            except Exception as exc:
                log.warning(
                    "Chroma remote unavailable — falling back to local PersistentClient",
                    url=chroma_url,
                    error=str(exc),
                )
        if not remote_ok:
            chroma_dir = str(Path(data_dir) / "chroma")
            Path(chroma_dir).mkdir(parents=True, exist_ok=True)
            self._client = chromadb.PersistentClient(
                path=chroma_dir,
                settings=ChromaSettings(anonymized_telemetry=False),
            )
            log.info("Chroma store initialised (local)", chroma_dir=chroma_dir)
        # D-20: expose mode for /health observability
        self._mode = "remote" if remote_ok else "local_fallback"

    @property
    def mode(self) -> str:
        """Return 'remote' or 'local_fallback' — surfaced in /health."""
        return self._mode

    # ------------------------------------------------------------------
    # Collection management
    # ------------------------------------------------------------------

    def get_or_create_collection(
        self,
        name: str = DEFAULT_COLLECTION,
        metadata: Optional[dict[str, Any]] = None,
    ) -> Collection:
        """
        Return an existing collection or create it if absent.

        Args:
            name:     Collection name.
            metadata: Optional metadata stored with the collection
                      (e.g. embedding model name, dimension count).

        Returns:
            A Chroma Collection handle.
        """
        collection = self._client.get_or_create_collection(
            name=name,
            **({"metadata": metadata} if metadata else {}),
        )
        log.debug("Collection ready", collection=name)
        return collection

    async def get_or_create_collection_async(
        self,
        name: str = DEFAULT_COLLECTION,
        metadata: Optional[dict[str, Any]] = None,
    ) -> Collection:
        """Async wrapper around get_or_create_collection."""
        return await asyncio.to_thread(self.get_or_create_collection, name, metadata)

    # ------------------------------------------------------------------
    # Document ingestion
    # ------------------------------------------------------------------

    def add_documents(
        self,
        collection_name: str,
        ids: list[str],
        documents: list[str],
        embeddings: list[list[float]],
        metadatas: Optional[list[dict[str, Any]]] = None,
    ) -> None:
        """
        Add documents with pre-computed embeddings to a collection.

        Args:
            collection_name: Target collection.
            ids:             Unique document IDs (must not already exist,
                             or use upsert if overwriting is intended).
            documents:       The raw text strings that were embedded.
            embeddings:      Pre-computed embedding vectors (one per document).
            metadatas:       Optional per-document metadata dicts.
        """
        collection = self.get_or_create_collection(collection_name)
        # Chroma 1.5+ rejects empty metadata dicts — only pass metadatas when provided
        upsert_kwargs: dict = {
            "ids": ids,
            "documents": documents,
            "embeddings": embeddings,
        }
        if metadatas:
            upsert_kwargs["metadatas"] = metadatas
        collection.upsert(**upsert_kwargs)
        log.debug(
            "Documents added to Chroma",
            collection=collection_name,
            count=len(ids),
        )

    async def add_documents_async(
        self,
        collection_name: str,
        ids: list[str],
        documents: list[str],
        embeddings: list[list[float]],
        metadatas: Optional[list[dict[str, Any]]] = None,
    ) -> None:
        """Async wrapper around add_documents."""
        await asyncio.to_thread(
            self.add_documents,
            collection_name,
            ids,
            documents,
            embeddings,
            metadatas,
        )

    # ------------------------------------------------------------------
    # Similarity search
    # ------------------------------------------------------------------

    def query(
        self,
        collection_name: str,
        query_embeddings: list[list[float]],
        n_results: int = 10,
        where: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """
        Perform a nearest-neighbour search against a collection.

        Args:
            collection_name:  Collection to search.
            query_embeddings: One or more query vectors (outer list = batch).
            n_results:        Maximum number of results per query.
            where:            Optional metadata filter dict (Chroma $eq/$in syntax).

        Returns:
            Chroma query result dict with keys:
            ids, distances, documents, metadatas, embeddings.
        """
        collection = self.get_or_create_collection(collection_name)
        kwargs: dict[str, Any] = {
            "query_embeddings": query_embeddings,
            "n_results": n_results,
            "include": ["documents", "metadatas", "distances"],
        }
        if where:
            kwargs["where"] = where

        results = collection.query(**kwargs)
        log.debug(
            "Chroma query complete",
            collection=collection_name,
            n_results=n_results,
        )
        return results

    async def query_async(
        self,
        collection_name: str,
        query_embeddings: list[list[float]],
        n_results: int = 10,
        where: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Async wrapper around query."""
        return await asyncio.to_thread(
            self.query,
            collection_name,
            query_embeddings,
            n_results,
            where,
        )

    # ------------------------------------------------------------------
    # Admin / introspection
    # ------------------------------------------------------------------

    def list_collections(self) -> list[str]:
        """Return a list of collection names in this Chroma instance."""
        return [c.name for c in self._client.list_collections()]

    async def list_collections_async(self) -> list[str]:
        """Async wrapper around list_collections."""
        return await asyncio.to_thread(self.list_collections)

    def count(self, collection_name: str) -> int:
        """Return the number of documents in a collection."""
        collection = self.get_or_create_collection(collection_name)
        return collection.count()

    async def count_async(self, collection_name: str) -> int:
        """Async wrapper around count."""
        return await asyncio.to_thread(self.count, collection_name)

    # ------------------------------------------------------------------
    # Destructive operations (admin-gated)
    # ------------------------------------------------------------------

    def delete_collection(self, name: str, *, _admin_override: bool = False) -> None:
        """Delete a ChromaDB collection. Only callable with explicit admin_override=True.

        This guard prevents accidental or unauthorized deletion of collections from
        any non-admin code path.  At the API layer, gate all callers behind
        ``require_role('admin')`` before passing ``_admin_override=True``.

        Production use: gate this behind require_role('admin') at the API layer.

        Args:
            name:            The collection name to delete.
            _admin_override: Must be True to proceed.  Pass True only from
                             API endpoints that are already protected by
                             ``require_role('admin')``.

        Raises:
            PermissionError: If called without ``_admin_override=True``.
        """
        if not _admin_override:
            raise PermissionError(
                "Collection deletion requires explicit admin authorization. "
                "Pass _admin_override=True only from admin-gated API endpoints."
            )
        self._client.delete_collection(name)
        log.info("Collection deleted (admin action)", collection=name)

    async def delete_collection_async(
        self, name: str, *, _admin_override: bool = False
    ) -> None:
        """Async wrapper around delete_collection."""
        await asyncio.to_thread(self.delete_collection, name, _admin_override=_admin_override)

    # ------------------------------------------------------------------
    # Initialisation helper
    # ------------------------------------------------------------------

    async def initialise_default_collections(self, embed_model: str) -> None:
        """
        Ensure the default SOC evidence collection exists with correct metadata.

        Called once during application startup.
        """
        await self.get_or_create_collection_async(
            DEFAULT_COLLECTION,
            metadata={"embed_model": embed_model, "hnsw:space": "cosine"},
        )
        log.info(
            "Default Chroma collection ready",
            collection=DEFAULT_COLLECTION,
            embed_model=embed_model,
        )
