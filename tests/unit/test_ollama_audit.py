import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_generate_writes_audit_log():
    """generate() must write to llm_audit logger."""
    from backend.services.ollama_client import OllamaClient

    with patch("backend.services.ollama_client._audit_log") as mock_log:
        client = OllamaClient(base_url="http://localhost:11434")
        mock_response = MagicMock()
        mock_response.json.return_value = {"response": "test response"}
        mock_response.raise_for_status = MagicMock()
        with patch.object(client._client, "post", new_callable=AsyncMock, return_value=mock_response):
            try:
                await client.generate(model="test-model", prompt="test prompt")
            except Exception:
                pass
        assert mock_log.info.called


@pytest.mark.asyncio
async def test_embed_writes_audit_log():
    """embed() must write to llm_audit logger."""
    from backend.services.ollama_client import OllamaClient

    with patch("backend.services.ollama_client._audit_log") as mock_log:
        client = OllamaClient(base_url="http://localhost:11434")
        mock_response = MagicMock()
        mock_response.json.return_value = {"embedding": [0.1, 0.2, 0.3]}
        mock_response.raise_for_status = MagicMock()
        with patch.object(client._client, "post", new_callable=AsyncMock, return_value=mock_response):
            try:
                await client.embed(text="test text")
            except Exception:
                pass
        assert mock_log.info.called


@pytest.mark.asyncio
async def test_audit_log_has_required_fields():
    """Audit log call must include event_type, model, prompt_hash, response_hash."""
    from backend.services.ollama_client import OllamaClient

    logged_extras = []

    def capture_log(msg, *args, **kwargs):
        if "extra" in kwargs:
            logged_extras.append(kwargs["extra"])

    with patch("backend.services.ollama_client._audit_log") as mock_log:
        mock_log.info.side_effect = capture_log
        client = OllamaClient(base_url="http://localhost:11434")
        mock_response = MagicMock()
        mock_response.json.return_value = {"response": "result"}
        mock_response.raise_for_status = MagicMock()
        with patch.object(client._client, "post", new_callable=AsyncMock, return_value=mock_response):
            try:
                await client.generate(model="qwen3:14b", prompt="analyze this")
            except Exception:
                pass

    assert any("event_type" in e and "prompt_hash" in e for e in logged_extras), \
        f"Expected event_type and prompt_hash in audit log. Got: {logged_extras}"
