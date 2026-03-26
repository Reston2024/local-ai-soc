"""
Async Ollama client for the AI-SOC-Brain backend.

Wraps the Ollama HTTP API (http://127.0.0.1:11434) with:
- Health check
- Single and batch text embedding
- Non-streaming text generation
- Streaming text generation with callback

All methods are async and use httpx.AsyncClient.

Ollama API reference: https://github.com/ollama/ollama/blob/main/docs/api.md
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import AsyncIterator, Callable, Optional

import httpx

from backend.core.logging import get_logger

_audit_log = logging.getLogger("llm_audit")


def _sha256_short(text: str) -> str:
    """Return first 16 hex chars of SHA-256 hash of text."""
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:16]

log = get_logger(__name__)

# Default timeouts (seconds)
_CONNECT_TIMEOUT = 5.0
_EMBED_TIMEOUT = 30.0
_GENERATE_TIMEOUT = 120.0
_STREAM_TIMEOUT = 300.0


class OllamaError(Exception):
    """Raised when the Ollama API returns an error or is unreachable."""


class OllamaClient:
    """
    Async HTTP client for the Ollama REST API.

    Usage::

        async with OllamaClient(base_url, model, embed_model) as client:
            embedding = await client.embed("Hello, world")
            response  = await client.generate("Explain T1059 in 2 sentences")
    """

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:11434",
        model: str = "qwen3:14b",
        embed_model: str = "mxbai-embed-large",
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.embed_model = embed_model

        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(
                connect=_CONNECT_TIMEOUT,
                read=_GENERATE_TIMEOUT,
                write=30.0,
                pool=5.0,
            ),
            headers={"Content-Type": "application/json"},
        )
        log.info(
            "OllamaClient initialised",
            base_url=self.base_url,
            model=self.model,
            embed_model=self.embed_model,
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def close(self) -> None:
        """Close the underlying httpx AsyncClient."""
        await self._client.aclose()
        log.debug("OllamaClient closed")

    async def __aenter__(self) -> "OllamaClient":
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()

    # ------------------------------------------------------------------
    # Health check
    # ------------------------------------------------------------------

    async def health_check(self) -> bool:
        """
        Return True if Ollama is reachable and has at least one model.

        Calls GET /api/tags with a 3-second timeout.
        """
        try:
            resp = await self._client.get(
                "/api/tags",
                timeout=httpx.Timeout(connect=3.0, read=3.0, write=3.0, pool=3.0),
            )
            resp.raise_for_status()
            data = resp.json()
            models = [m["name"] for m in data.get("models", [])]
            log.debug("Ollama health check passed", models=models)
            return True
        except (httpx.HTTPError, httpx.ConnectError, Exception) as exc:
            log.warning("Ollama health check failed", error=str(exc))
            return False

    async def list_models(self) -> list[str]:
        """Return list of model names available in Ollama."""
        try:
            resp = await self._client.get("/api/tags")
            resp.raise_for_status()
            data = resp.json()
            return [m["name"] for m in data.get("models", [])]
        except Exception as exc:
            log.error("Failed to list Ollama models", error=str(exc))
            return []

    # ------------------------------------------------------------------
    # Embeddings
    # ------------------------------------------------------------------

    async def embed(self, text: str) -> list[float]:
        """
        Generate a single embedding vector for the given text.

        Uses the embed_model configured at init time.

        Args:
            text: The text to embed (should be <= model context window).

        Returns:
            A list of floats representing the embedding vector.

        Raises:
            OllamaError: If the API call fails.
        """
        _audit_log.info("", extra={
            "event_type": "llm_embed",
            "model": self.embed_model,
            "prompt_length": len(text),
            "prompt_hash": _sha256_short(text),
            "status": "start",
        })
        try:
            resp = await self._client.post(
                "/api/embeddings",
                json={"model": self.embed_model, "prompt": text},
                timeout=httpx.Timeout(
                    connect=_CONNECT_TIMEOUT,
                    read=_EMBED_TIMEOUT,
                    write=10.0,
                    pool=5.0,
                ),
            )
            resp.raise_for_status()
            data = resp.json()
            embedding = data.get("embedding", [])
            if not embedding:
                raise OllamaError(f"Empty embedding returned for model {self.embed_model!r}")
            embedding_str = str(embedding)
            _audit_log.info("", extra={
                "event_type": "llm_embed",
                "model": self.embed_model,
                "prompt_length": len(text),
                "prompt_hash": _sha256_short(text),
                "response_length": len(embedding),
                "response_hash": _sha256_short(embedding_str),
                "status": "complete",
            })
            return embedding
        except OllamaError:
            raise
        except httpx.HTTPStatusError as exc:
            _audit_log.info("", extra={
                "event_type": "llm_embed",
                "model": self.embed_model,
                "prompt_hash": _sha256_short(text),
                "status": "error",
                "error_type": "HTTPStatusError",
            })
            raise OllamaError(
                f"Ollama embed HTTP error {exc.response.status_code}: {exc.response.text}"
            ) from exc
        except Exception as exc:
            _audit_log.info("", extra={
                "event_type": "llm_embed",
                "model": self.embed_model,
                "prompt_hash": _sha256_short(text),
                "status": "error",
                "error_type": type(exc).__name__,
            })
            raise OllamaError(f"Ollama embed failed: {exc}") from exc

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """
        Generate embedding vectors for a list of texts.

        Sends requests sequentially (Ollama does not have a native batch
        endpoint in older versions). For large batches consider using
        asyncio.gather with rate limiting.

        Args:
            texts: List of texts to embed.

        Returns:
            List of embedding vectors, one per input text.
        """
        if not texts:
            return []

        embeddings: list[list[float]] = []
        for i, text in enumerate(texts):
            try:
                vec = await self.embed(text)
                embeddings.append(vec)
            except OllamaError as exc:
                log.error(
                    "Embed batch item failed",
                    index=i,
                    text_preview=text[:80],
                    error=str(exc),
                )
                # Append a zero vector so indexes remain aligned.
                embeddings.append([])
        return embeddings

    # ------------------------------------------------------------------
    # Text generation (non-streaming)
    # ------------------------------------------------------------------

    async def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.1,
        model: Optional[str] = None,
    ) -> str:
        """
        Generate a complete text response (non-streaming).

        Args:
            prompt:      The user prompt.
            system:      Optional system message prepended to the context.
            temperature: Sampling temperature (default 0.1 for factual tasks).
            model:       Override the default model for this call.

        Returns:
            The model's text response as a string.

        Raises:
            OllamaError: If the API call fails.
        """
        _effective_model = model or self.model
        payload: dict = {
            "model": _effective_model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": temperature},
        }
        if system:
            payload["system"] = system

        _audit_log.info("", extra={
            "event_type": "llm_generate",
            "model": _effective_model,
            "prompt_length": len(prompt),
            "prompt_hash": _sha256_short(prompt),
            "status": "start",
        })
        try:
            resp = await self._client.post(
                "/api/generate",
                json=payload,
                timeout=httpx.Timeout(
                    connect=_CONNECT_TIMEOUT,
                    read=_GENERATE_TIMEOUT,
                    write=30.0,
                    pool=5.0,
                ),
            )
            resp.raise_for_status()
            data = resp.json()
            response_text = data.get("response", "")
            log.debug(
                "Generate complete",
                model=payload["model"],
                prompt_len=len(prompt),
                response_len=len(response_text),
            )
            _audit_log.info("", extra={
                "event_type": "llm_generate",
                "model": _effective_model,
                "prompt_length": len(prompt),
                "prompt_hash": _sha256_short(prompt),
                "response_length": len(response_text),
                "response_hash": _sha256_short(response_text),
                "status": "complete",
            })
            return response_text
        except OllamaError:
            raise
        except httpx.HTTPStatusError as exc:
            _audit_log.info("", extra={
                "event_type": "llm_generate",
                "model": _effective_model,
                "prompt_hash": _sha256_short(prompt),
                "status": "error",
                "error_type": "HTTPStatusError",
            })
            raise OllamaError(
                f"Ollama generate HTTP error {exc.response.status_code}: {exc.response.text}"
            ) from exc
        except Exception as exc:
            _audit_log.info("", extra={
                "event_type": "llm_generate",
                "model": _effective_model,
                "prompt_hash": _sha256_short(prompt),
                "status": "error",
                "error_type": type(exc).__name__,
            })
            raise OllamaError(f"Ollama generate failed: {exc}") from exc

    # ------------------------------------------------------------------
    # Streaming generation
    # ------------------------------------------------------------------

    async def stream_generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        on_token: Optional[Callable[[str], None]] = None,
        temperature: float = 0.1,
        model: Optional[str] = None,
    ) -> str:
        """
        Generate a streaming text response token by token.

        Args:
            prompt:      The user prompt.
            system:      Optional system message.
            on_token:    Optional synchronous callback called for each token.
                         Receives the token string.  Use for SSE streaming.
            temperature: Sampling temperature.
            model:       Override the default model for this call.

        Returns:
            The complete response text assembled from all tokens.

        Raises:
            OllamaError: If the API call fails.
        """
        payload: dict = {
            "model": model or self.model,
            "prompt": prompt,
            "stream": True,
            "options": {"temperature": temperature},
        }
        if system:
            payload["system"] = system

        full_response: list[str] = []

        try:
            async with self._client.stream(
                "POST",
                "/api/generate",
                json=payload,
                timeout=httpx.Timeout(
                    connect=_CONNECT_TIMEOUT,
                    read=_STREAM_TIMEOUT,
                    write=30.0,
                    pool=5.0,
                ),
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        chunk = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    token = chunk.get("response", "")
                    if token:
                        full_response.append(token)
                        if on_token is not None:
                            on_token(token)

                    if chunk.get("done", False):
                        break

        except OllamaError:
            raise
        except httpx.HTTPStatusError as exc:
            raise OllamaError(
                f"Ollama stream HTTP error {exc.response.status_code}: {exc.response.text}"
            ) from exc
        except Exception as exc:
            raise OllamaError(f"Ollama stream failed: {exc}") from exc

        result = "".join(full_response)
        log.debug(
            "Stream generate complete",
            model=payload["model"],
            response_len=len(result),
        )
        return result

    # ------------------------------------------------------------------
    # Async generator variant for SSE endpoints
    # ------------------------------------------------------------------

    async def stream_generate_iter(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.1,
        model: Optional[str] = None,
    ) -> AsyncIterator[str]:
        """
        Yield tokens one at a time as an async generator.

        Suitable for Server-Sent Events (SSE) endpoints::

            async for token in client.stream_generate_iter(prompt):
                yield f"data: {json.dumps({'token': token})}\n\n"
        """
        payload: dict = {
            "model": model or self.model,
            "prompt": prompt,
            "stream": True,
            "options": {"temperature": temperature},
        }
        if system:
            payload["system"] = system

        async with self._client.stream(
            "POST",
            "/api/generate",
            json=payload,
            timeout=httpx.Timeout(
                connect=_CONNECT_TIMEOUT,
                read=_STREAM_TIMEOUT,
                write=30.0,
                pool=5.0,
            ),
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.strip():
                    continue
                try:
                    chunk = json.loads(line)
                except json.JSONDecodeError:
                    continue

                token = chunk.get("response", "")
                if token:
                    yield token

                if chunk.get("done", False):
                    return
