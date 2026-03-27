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
