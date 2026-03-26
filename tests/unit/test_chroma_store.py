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
        from backend.stores.chroma_store import ChromaStore, DEFAULT_COLLECTION
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
        from backend.stores.chroma_store import ChromaStore, DEFAULT_COLLECTION
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
