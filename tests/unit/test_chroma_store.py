"""Unit tests for backend/stores/chroma_store.py."""
import pytest

pytestmark = pytest.mark.unit


class TestChromaStore:
    def test_chroma_store_init(self, tmp_path):
        """ChromaStore can be instantiated with a temp data dir."""
        from backend.stores.chroma_store import ChromaStore
        store = ChromaStore(str(tmp_path))
        assert store is not None

    def test_default_collection_constant(self):
        from backend.stores.chroma_store import DEFAULT_COLLECTION
        assert DEFAULT_COLLECTION == "soc_evidence"

    def test_get_or_create_collection(self, tmp_path):
        from backend.stores.chroma_store import ChromaStore
        store = ChromaStore(str(tmp_path))
        collection = store.get_or_create_collection("test_collection")
        assert collection is not None
        assert collection.name == "test_collection"

    def test_get_or_create_default_collection(self, tmp_path):
        from backend.stores.chroma_store import DEFAULT_COLLECTION, ChromaStore
        store = ChromaStore(str(tmp_path))
        collection = store.get_or_create_collection()
        assert collection.name == DEFAULT_COLLECTION

    def test_list_collections_empty(self, tmp_path):
        from backend.stores.chroma_store import ChromaStore
        store = ChromaStore(str(tmp_path))
        names = store.list_collections()
        assert isinstance(names, list)

    def test_list_collections_after_create(self, tmp_path):
        from backend.stores.chroma_store import ChromaStore
        store = ChromaStore(str(tmp_path))
        store.get_or_create_collection("my_collection")
        names = store.list_collections()
        assert "my_collection" in names

    def test_count_empty_collection(self, tmp_path):
        from backend.stores.chroma_store import ChromaStore
        store = ChromaStore(str(tmp_path))
        count = store.count("empty_test_collection")
        assert count == 0

    def test_add_documents_and_count(self, tmp_path):
        from backend.stores.chroma_store import ChromaStore
        store = ChromaStore(str(tmp_path))
        store.add_documents(
            collection_name="test_docs",
            ids=["doc-1", "doc-2"],
            documents=["hello world", "foo bar"],
            embeddings=[[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]],
        )
        count = store.count("test_docs")
        assert count == 2

    def test_add_documents_with_metadata(self, tmp_path):
        from backend.stores.chroma_store import ChromaStore
        store = ChromaStore(str(tmp_path))
        store.add_documents(
            collection_name="test_meta",
            ids=["doc-a"],
            documents=["test document"],
            embeddings=[[0.1, 0.2]],
            metadatas=[{"source": "test", "case_id": "case-001"}],
        )
        count = store.count("test_meta")
        assert count == 1

    def test_upsert_deduplicates(self, tmp_path):
        """add_documents uses upsert — inserting same ID twice keeps one doc."""
        from backend.stores.chroma_store import ChromaStore
        store = ChromaStore(str(tmp_path))
        store.add_documents(
            collection_name="upsert_test",
            ids=["dup-id"],
            documents=["first version"],
            embeddings=[[0.1, 0.2]],
        )
        store.add_documents(
            collection_name="upsert_test",
            ids=["dup-id"],
            documents=["second version"],
            embeddings=[[0.3, 0.4]],
        )
        count = store.count("upsert_test")
        assert count == 1

    def test_query_returns_results(self, tmp_path):
        from backend.stores.chroma_store import ChromaStore
        store = ChromaStore(str(tmp_path))
        store.add_documents(
            collection_name="query_test",
            ids=["q-doc-1"],
            documents=["security event powershell"],
            embeddings=[[0.1, 0.2, 0.3]],
        )
        results = store.query(
            collection_name="query_test",
            query_embeddings=[[0.1, 0.2, 0.3]],
            n_results=1,
        )
        assert isinstance(results, dict)
        assert "ids" in results

    async def test_get_or_create_collection_async(self, tmp_path):
        from backend.stores.chroma_store import ChromaStore
        store = ChromaStore(str(tmp_path))
        collection = await store.get_or_create_collection_async("async_test")
        assert collection.name == "async_test"

    async def test_add_documents_async(self, tmp_path):
        from backend.stores.chroma_store import ChromaStore
        store = ChromaStore(str(tmp_path))
        await store.add_documents_async(
            collection_name="async_add_test",
            ids=["async-doc-1"],
            documents=["async document"],
            embeddings=[[0.1, 0.2]],
        )
        count = store.count("async_add_test")
        assert count == 1

    async def test_query_async(self, tmp_path):
        from backend.stores.chroma_store import ChromaStore
        store = ChromaStore(str(tmp_path))
        store.add_documents(
            collection_name="async_query_test",
            ids=["aq-1"],
            documents=["async query test"],
            embeddings=[[0.5, 0.6]],
        )
        results = await store.query_async(
            collection_name="async_query_test",
            query_embeddings=[[0.5, 0.6]],
            n_results=1,
        )
        assert isinstance(results, dict)

    async def test_list_collections_async(self, tmp_path):
        from backend.stores.chroma_store import ChromaStore
        store = ChromaStore(str(tmp_path))
        store.get_or_create_collection("async_list_test")
        names = await store.list_collections_async()
        assert "async_list_test" in names

    async def test_count_async(self, tmp_path):
        from backend.stores.chroma_store import ChromaStore
        store = ChromaStore(str(tmp_path))
        store.add_documents(
            collection_name="async_count_test",
            ids=["ac-1", "ac-2"],
            documents=["doc1", "doc2"],
            embeddings=[[0.1], [0.2]],
        )
        count = await store.count_async("async_count_test")
        assert count == 2

    async def test_initialise_default_collections(self, tmp_path):
        from backend.stores.chroma_store import DEFAULT_COLLECTION, ChromaStore
        store = ChromaStore(str(tmp_path))
        await store.initialise_default_collections(embed_model="test-model")
        names = store.list_collections()
        assert DEFAULT_COLLECTION in names

    def test_health_check(self, tmp_path):
        from backend.stores.chroma_store import ChromaStore
        store = ChromaStore(str(tmp_path))
        # Health check accesses collection list
        names = store.list_collections()
        assert isinstance(names, list)


class TestChromaStoreDeleteCollection:
    """E5-01: Collection deletion must require explicit admin authorization."""

    def test_delete_collection_without_admin_override_raises_permission_error(self):
        """Calling delete_collection without _admin_override=True raises PermissionError."""
        from unittest.mock import MagicMock

        from backend.stores.chroma_store import ChromaStore

        store = ChromaStore.__new__(ChromaStore)
        store._client = MagicMock()

        with pytest.raises(PermissionError, match="admin authorization"):
            store.delete_collection("some_collection")

        # The underlying client method must NOT have been called.
        store._client.delete_collection.assert_not_called()

    def test_delete_collection_with_admin_override_succeeds(self):
        """Calling delete_collection(_admin_override=True) calls through to the client."""
        from unittest.mock import MagicMock

        from backend.stores.chroma_store import ChromaStore

        store = ChromaStore.__new__(ChromaStore)
        store._client = MagicMock()
        # Provide a minimal logger so log.info doesn't fail on the bare object.
        import logging
        store._logger = logging.getLogger("test")

        # Patch the module-level log so it doesn't need a real structlog setup.
        import backend.stores.chroma_store as cs_module
        original_log = cs_module.log
        cs_module.log = MagicMock()

        try:
            store.delete_collection("target_collection", _admin_override=True)
        finally:
            cs_module.log = original_log

        store._client.delete_collection.assert_called_once_with("target_collection")


@pytest.mark.skip(reason="stub — implement in 54-05 after bge-m3 is pulled")
def test_bge_m3_embed_dimension():
    """Embedding a short string via Ollama with model=bge-m3 returns a 1024-dim vector.

    Phase 54 switches the embedding model from mxbai-embed-large (1024-dim,
    pulled from Ollama) to bge-m3 (1024-dim, served from the HuggingFace
    inference microservice).  This test will assert:

        embedding = ollama_embed(text="hello world", model="bge-m3")
        assert isinstance(embedding, list)
        assert len(embedding) == 1024

    Implement in plan 54-05 once the bge-m3 microservice is confirmed running
    and the OLLAMA_EMBED_MODEL setting has been updated.
    """
    pytest.skip("stub — implement in 54-05")
