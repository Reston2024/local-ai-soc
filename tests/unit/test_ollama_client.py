"""Unit tests for backend/services/ollama_client.py using mocked httpx."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


def _make_client(base_url="http://127.0.0.1:11434"):
    from backend.services.ollama_client import OllamaClient
    return OllamaClient(base_url=base_url, model="test-model", embed_model="test-embed")


class TestOllamaClientInit:
    def test_instantiation(self):
        client = _make_client()
        assert client is not None
        assert client.model == "test-model"
        assert client.embed_model == "test-embed"

    def test_base_url_strips_trailing_slash(self):
        from backend.services.ollama_client import OllamaClient
        c = OllamaClient(base_url="http://localhost:11434/")
        assert not c.base_url.endswith("/")

    async def test_context_manager(self):
        async with _make_client() as c:
            assert c is not None

    async def test_close(self):
        c = _make_client()
        await c.close()  # Should not raise


class TestOllamaClientHealthCheck:
    async def test_health_check_returns_true_on_success(self):
        client = _make_client()
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"models": [{"name": "llama2"}]}

        with patch.object(client._client, "get", new=AsyncMock(return_value=mock_response)):
            result = await client.health_check()
        assert result is True

    async def test_health_check_returns_false_on_connection_error(self):
        import httpx
        client = _make_client()

        with patch.object(client._client, "get",
                         new=AsyncMock(side_effect=httpx.ConnectError("refused"))):
            result = await client.health_check()
        assert result is False

    async def test_health_check_returns_false_on_http_error(self):
        import httpx
        client = _make_client()

        with patch.object(client._client, "get",
                         new=AsyncMock(side_effect=httpx.HTTPError("500"))):
            result = await client.health_check()
        assert result is False


class TestOllamaClientEmbed:
    async def test_embed_returns_vector(self):
        client = _make_client()
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"embedding": [0.1, 0.2, 0.3]}

        with patch.object(client._client, "post", new=AsyncMock(return_value=mock_response)):
            result = await client.embed("test text")
        assert result == [0.1, 0.2, 0.3]

    async def test_embed_raises_on_empty_embedding(self):
        from backend.services.ollama_client import OllamaError
        client = _make_client()
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"embedding": []}

        with patch.object(client._client, "post", new=AsyncMock(return_value=mock_response)):
            with pytest.raises(OllamaError):
                await client.embed("test text")

    async def test_embed_raises_on_http_status_error(self):
        import httpx

        from backend.services.ollama_client import OllamaError
        client = _make_client()

        mock_request = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 503
        mock_response.text = "Service Unavailable"
        exc = httpx.HTTPStatusError("503", request=mock_request, response=mock_response)

        with patch.object(client._client, "post", new=AsyncMock(side_effect=exc)):
            with pytest.raises(OllamaError):
                await client.embed("test text")

    async def test_embed_raises_on_generic_error(self):
        from backend.services.ollama_client import OllamaError
        client = _make_client()

        with patch.object(client._client, "post",
                         new=AsyncMock(side_effect=Exception("network error"))):
            with pytest.raises(OllamaError):
                await client.embed("test text")


class TestOllamaClientEmbedBatch:
    async def test_embed_batch_empty_list(self):
        client = _make_client()
        result = await client.embed_batch([])
        assert result == []

    async def test_embed_batch_returns_vectors(self):
        client = _make_client()
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"embedding": [0.1, 0.2]}

        with patch.object(client._client, "post", new=AsyncMock(return_value=mock_response)):
            result = await client.embed_batch(["text1", "text2"])
        assert len(result) == 2
        assert result[0] == [0.1, 0.2]

    async def test_embed_batch_handles_item_failure(self):
        from backend.services.ollama_client import OllamaError
        client = _make_client()

        call_count = [0]
        async def _mock_embed(text):
            call_count[0] += 1
            if call_count[0] == 2:
                raise OllamaError("failed")
            return [0.1, 0.2]

        with patch.object(client, "embed", side_effect=_mock_embed):
            result = await client.embed_batch(["text1", "text2", "text3"])
        # Failed item gets empty list, others succeed
        assert len(result) == 3
        assert result[0] == [0.1, 0.2]
        assert result[1] == []  # failed
        assert result[2] == [0.1, 0.2]


class TestOllamaClientGenerate:
    async def test_generate_returns_text(self):
        client = _make_client()
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "response": "This is a test response.",
            "done": True,
        }

        with patch.object(client._client, "post", new=AsyncMock(return_value=mock_response)):
            result = await client.generate("What is T1059?")
        assert result == "This is a test response."

    async def test_generate_with_system_prompt(self):
        client = _make_client()
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"response": "Answer.", "done": True}

        with patch.object(client._client, "post", new=AsyncMock(return_value=mock_response)) as mock_post:
            await client.generate("Question?", system="You are a SOC analyst.")
        # Verify post was called
        assert mock_post.called

    async def test_generate_raises_on_http_status_error(self):
        import httpx

        from backend.services.ollama_client import OllamaError
        client = _make_client()

        mock_request = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        exc = httpx.HTTPStatusError("500", request=mock_request, response=mock_response)

        with patch.object(client._client, "post", new=AsyncMock(side_effect=exc)):
            with pytest.raises(OllamaError):
                await client.generate("test")

    async def test_generate_raises_on_generic_error(self):
        from backend.services.ollama_client import OllamaError
        client = _make_client()

        with patch.object(client._client, "post",
                         new=AsyncMock(side_effect=Exception("timeout"))):
            with pytest.raises(OllamaError):
                await client.generate("test")


class TestOllamaClientListModels:
    async def test_list_models_returns_names(self):
        client = _make_client()
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "models": [{"name": "llama2"}, {"name": "qwen3:14b"}]
        }

        with patch.object(client._client, "get", new=AsyncMock(return_value=mock_response)):
            result = await client.list_models()
        assert "llama2" in result
        assert "qwen3:14b" in result

    async def test_list_models_returns_empty_on_error(self):
        client = _make_client()
        with patch.object(client._client, "get",
                         new=AsyncMock(side_effect=Exception("connection refused"))):
            result = await client.list_models()
        assert result == []


class TestCybersecModelRouting:
    """Tests for cybersec model routing — ADR-020 (Plan 13-02)."""

    def test_cybersec_model_stored_when_provided(self):
        from backend.services.ollama_client import OllamaClient

        c = OllamaClient(cybersec_model="foundation-sec:8b")
        assert c.cybersec_model == "foundation-sec:8b"

    def test_cybersec_model_falls_back_to_model_when_not_provided(self):
        from backend.services.ollama_client import OllamaClient

        c = OllamaClient(model="qwen3:14b")
        # When cybersec_model not given, should fall back to self.model
        assert c.cybersec_model == "qwen3:14b"

    async def test_generate_routes_to_cybersec_model_when_flag_set(self):
        from backend.services.ollama_client import OllamaClient
        from unittest.mock import AsyncMock, MagicMock, patch

        c = OllamaClient(model="qwen3:14b", cybersec_model="foundation-sec:8b")

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"response": "cyber answer", "done": True}

        with patch.object(c._client, "post", new=AsyncMock(return_value=mock_response)) as mock_post:
            result = await c.generate("What is CVE-2024-1234?", use_cybersec_model=True)

        assert result == "cyber answer"
        call_kwargs = mock_post.call_args
        payload = call_kwargs[1]["json"] if "json" in call_kwargs[1] else call_kwargs[0][1]
        assert payload["model"] == "foundation-sec:8b"

    async def test_generate_uses_default_model_without_flag(self):
        from backend.services.ollama_client import OllamaClient
        from unittest.mock import AsyncMock, MagicMock, patch

        c = OllamaClient(model="qwen3:14b", cybersec_model="foundation-sec:8b")

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"response": "default answer", "done": True}

        with patch.object(c._client, "post", new=AsyncMock(return_value=mock_response)) as mock_post:
            result = await c.generate("What is the weather?")

        assert result == "default answer"
        call_kwargs = mock_post.call_args
        payload = call_kwargs[1]["json"] if "json" in call_kwargs[1] else call_kwargs[0][1]
        assert payload["model"] == "qwen3:14b"

    async def test_stream_generate_routes_to_cybersec_model_when_flag_set(self):
        import json
        from backend.services.ollama_client import OllamaClient
        from unittest.mock import AsyncMock, MagicMock, patch

        c = OllamaClient(model="qwen3:14b", cybersec_model="foundation-sec:8b")

        # Build a minimal async context manager mock for stream
        chunks = [
            json.dumps({"response": "sec", "done": False}).encode(),
            json.dumps({"response": " answer", "done": True}).encode(),
        ]

        async def _aiter_lines():
            for chunk in chunks:
                yield chunk.decode()

        mock_stream_ctx = MagicMock()
        mock_stream_ctx.__aenter__ = AsyncMock(return_value=mock_stream_ctx)
        mock_stream_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_stream_ctx.raise_for_status = MagicMock()
        mock_stream_ctx.aiter_lines = _aiter_lines

        with patch.object(c._client, "stream", return_value=mock_stream_ctx) as mock_stream:
            result = await c.stream_generate("Explain MITRE T1059", use_cybersec_model=True)

        assert "sec" in result or result  # streamed tokens assembled
        call_kwargs = mock_stream.call_args
        payload = call_kwargs[1]["json"] if "json" in call_kwargs[1] else call_kwargs[0][2]
        assert payload["model"] == "foundation-sec:8b"


class TestSha256Short:
    def test_sha256_short_returns_16_chars(self):
        from backend.services.ollama_client import _sha256_short
        result = _sha256_short("hello world")
        assert len(result) == 16

    def test_sha256_short_deterministic(self):
        from backend.services.ollama_client import _sha256_short
        assert _sha256_short("test") == _sha256_short("test")

    def test_sha256_short_different_inputs(self):
        from backend.services.ollama_client import _sha256_short
        assert _sha256_short("abc") != _sha256_short("xyz")


# ---------------------------------------------------------------------------
# Plan 14-03: LLMOps telemetry — DuckDB store param + _write_telemetry
# ---------------------------------------------------------------------------

class TestOllamaClientDuckDBStore:
    def test_instantiation_without_store_still_works(self):
        """OllamaClient() with no duckdb_store arg instantiates fine (no regression)."""
        from backend.services.ollama_client import OllamaClient
        c = OllamaClient(base_url="http://127.0.0.1:11434", model="test-model", embed_model="test-embed")
        assert c is not None

    def test_instantiation_with_duckdb_store_stores_it(self):
        """OllamaClient(duckdb_store=mock_store) stores it on self._duckdb_store."""
        from backend.services.ollama_client import OllamaClient
        mock_store = MagicMock()
        c = OllamaClient(duckdb_store=mock_store)
        assert c._duckdb_store is mock_store

    def test_duckdb_store_defaults_to_none(self):
        """When no store provided, _duckdb_store is None."""
        from backend.services.ollama_client import OllamaClient
        c = OllamaClient()
        assert c._duckdb_store is None

    async def test_write_telemetry_is_noop_when_store_is_none(self):
        """_write_telemetry() does nothing when _duckdb_store is None."""
        from backend.services.ollama_client import OllamaClient
        c = OllamaClient()
        # Should not raise
        await c._write_telemetry(
            model="test-model",
            endpoint="generate",
            prompt_chars=10,
            completion_chars=20,
            latency_ms=100,
            success=True,
        )

    async def test_write_telemetry_calls_execute_write_when_store_present(self):
        """_write_telemetry() calls execute_write on the store when present."""
        from backend.services.ollama_client import OllamaClient
        mock_store = MagicMock()
        mock_store.execute_write = AsyncMock()
        c = OllamaClient(duckdb_store=mock_store)
        await c._write_telemetry(
            model="qwen3:14b",
            endpoint="generate",
            prompt_chars=42,
            completion_chars=100,
            latency_ms=250,
            success=True,
        )
        assert mock_store.execute_write.called

    async def test_generate_calls_write_telemetry_on_success(self):
        """generate() records telemetry on success."""
        from backend.services.ollama_client import OllamaClient
        mock_store = MagicMock()
        mock_store.execute_write = AsyncMock()
        c = OllamaClient(duckdb_store=mock_store)

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"response": "test answer", "done": True}

        with patch.object(c._client, "post", new=AsyncMock(return_value=mock_response)):
            result = await c.generate("test prompt")

        assert result == "test answer"
        assert mock_store.execute_write.called

    async def test_stream_generate_calls_write_telemetry_on_success(self):
        """stream_generate() records telemetry after stream completes."""
        import json as _json
        from backend.services.ollama_client import OllamaClient
        mock_store = MagicMock()
        mock_store.execute_write = AsyncMock()
        c = OllamaClient(duckdb_store=mock_store)

        chunks = [
            _json.dumps({"response": "hello", "done": False}).encode(),
            _json.dumps({"response": " world", "done": True}).encode(),
        ]

        async def _aiter_lines():
            for chunk in chunks:
                yield chunk.decode()

        mock_stream_ctx = MagicMock()
        mock_stream_ctx.__aenter__ = AsyncMock(return_value=mock_stream_ctx)
        mock_stream_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_stream_ctx.raise_for_status = MagicMock()
        mock_stream_ctx.aiter_lines = _aiter_lines

        with patch.object(c._client, "stream", return_value=mock_stream_ctx):
            result = await c.stream_generate("test prompt")

        assert mock_store.execute_write.called

    async def test_stream_generate_iter_accepts_use_cybersec_model(self):
        """stream_generate_iter() accepts use_cybersec_model kwarg without error."""
        import json as _json
        from backend.services.ollama_client import OllamaClient
        c = OllamaClient(model="qwen3:14b", cybersec_model="foundation-sec:8b")

        chunks = [
            _json.dumps({"response": "tok", "done": True}).encode(),
        ]

        async def _aiter_lines():
            for chunk in chunks:
                yield chunk.decode()

        mock_stream_ctx = MagicMock()
        mock_stream_ctx.__aenter__ = AsyncMock(return_value=mock_stream_ctx)
        mock_stream_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_stream_ctx.raise_for_status = MagicMock()
        mock_stream_ctx.aiter_lines = _aiter_lines

        with patch.object(c._client, "stream", return_value=mock_stream_ctx) as mock_stream:
            tokens = []
            async for tok in c.stream_generate_iter("test", use_cybersec_model=True):
                tokens.append(tok)

        call_kwargs = mock_stream.call_args
        payload = call_kwargs[1]["json"] if "json" in call_kwargs[1] else call_kwargs[0][2]
        assert payload["model"] == "foundation-sec:8b"
