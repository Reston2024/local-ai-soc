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
import time
from typing import TYPE_CHECKING, AsyncIterator, Callable, Optional
from uuid import uuid4

import httpx

if TYPE_CHECKING:
    from backend.stores.duckdb_store import DuckDBStore
    from backend.stores.sqlite_store import SQLiteStore

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
        cybersec_model: str = "",  # empty = fall back to self.model
        duckdb_store: "Optional[DuckDBStore]" = None,
        sqlite_store: "Optional[SQLiteStore]" = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.embed_model = embed_model
        self.cybersec_model = cybersec_model or model  # fallback to default
        self._duckdb_store = duckdb_store
        self._sqlite = sqlite_store

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
            cybersec_model=self.cybersec_model,
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
    # LLMOps telemetry
    # ------------------------------------------------------------------

    async def _write_telemetry(
        self,
        *,
        model: str,
        endpoint: str,
        prompt_chars: int,
        completion_chars: int,
        latency_ms: int,
        success: bool,
        error_type: Optional[str] = None,
        full_prompt: Optional[str] = None,
    ) -> None:
        """Write one telemetry row to llm_calls in DuckDB.

        Stores the full prompt text (truncated to 64 KB) and its SHA-256 hash
        for audit and prompt-injection forensics (E7-02).

        No-ops silently when no store was provided at init time.
        """
        if self._duckdb_store is None:
            return
        import uuid
        from datetime import datetime, timezone
        # Truncate to 64 KB max to avoid bloating the telemetry table
        prompt_text = full_prompt[:65536] if full_prompt else None
        prompt_hash = (
            hashlib.sha256(full_prompt.encode("utf-8", errors="replace")).hexdigest()
            if full_prompt
            else None
        )
        await self._duckdb_store.execute_write(
            """INSERT OR IGNORE INTO llm_calls
               (call_id, called_at, model, endpoint, prompt_chars,
                completion_chars, latency_ms, success, error_type,
                prompt_text, prompt_hash)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                str(uuid.uuid4()),
                datetime.now(timezone.utc).isoformat(),
                model,
                endpoint,
                prompt_chars,
                completion_chars,
                latency_ms,
                success,
                error_type,
                prompt_text,
                prompt_hash,
            ],
        )

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

    async def embed(self, text: str, operator_id: str = "system") -> list[float]:
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
            "operator_id": operator_id,
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
    # Model drift detection (P22-T04 hot-path check)
    # ------------------------------------------------------------------

    async def _check_model_drift(self, effective_model: str) -> None:
        """Check for model drift on each LLM call (P22-T04 hot-path check).

        Reads last_known_model from SQLite and compares to effective_model.
        Logs a WARNING if they differ. Writes the new model as last_known when
        no prior record exists. Always non-fatal — exceptions are swallowed.

        Args:
            effective_model: The model name being used for this call (after
                             model/use_cybersec_model resolution).
        """
        if self._sqlite is None:
            return
        try:
            import asyncio as _asyncio
            last_known: str | None = await _asyncio.to_thread(
                self._sqlite.get_kv, "last_known_model"
            )
            if last_known is None:
                # First call — seed last_known_model (non-fatal)
                await _asyncio.to_thread(
                    self._sqlite.set_kv, "last_known_model", effective_model
                )
                log.debug(
                    "Model drift: seeding last_known_model",
                    model=effective_model,
                )
            elif last_known != effective_model:
                log.warning(
                    "Model drift detected on LLM call",
                    last_known_model=last_known,
                    active_model=effective_model,
                )
        except Exception as exc:
            log.debug("Model drift check failed (non-fatal)", error=str(exc))

    # ------------------------------------------------------------------
    # Text generation (non-streaming)
    # ------------------------------------------------------------------

    async def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.1,
        model: Optional[str] = None,
        use_cybersec_model: bool = False,
        operator_id: str = "system",
        prompt_template_name: Optional[str] = None,
        prompt_template_sha256: Optional[str] = None,
        grounding_event_ids: Optional[list[str]] = None,
        out_context: Optional[dict] = None,
    ) -> str:
        """
        Generate a complete text response (non-streaming).

        Args:
            prompt:              The user prompt.
            system:              Optional system message prepended to the context.
            temperature:         Sampling temperature (default 0.1 for factual tasks).
            model:               Override the default model for this call.
            use_cybersec_model:  If True, route to self.cybersec_model instead of
                                 self.model (ADR-020).
            out_context:         Optional dict; if provided, populated with
                                 ``audit_id`` and ``grounding_event_ids`` after the
                                 provenance write.

        Returns:
            The model's text response as a string.

        Raises:
            OllamaError: If the API call fails.
        """
        audit_id = str(uuid4())
        _effective_model = model or (self.cybersec_model if use_cybersec_model else self.model)
        await self._check_model_drift(_effective_model)
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
            "operator_id": operator_id,
            "status": "start",
        })
        t0 = time.monotonic_ns()
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
            await self._write_telemetry(
                model=_effective_model,
                endpoint="generate",
                prompt_chars=len(prompt),
                completion_chars=len(response_text),
                latency_ms=(time.monotonic_ns() - t0) // 1_000_000,
                success=True,
                full_prompt=prompt,
            )
            try:
                import asyncio as _asyncio
                response_sha256 = hashlib.sha256(response_text.encode()).hexdigest()
                if self._sqlite is not None:
                    await _asyncio.to_thread(
                        self._sqlite.record_llm_provenance,
                        audit_id,
                        _effective_model,
                        prompt_template_name,
                        prompt_template_sha256,
                        response_sha256,
                        grounding_event_ids or [],
                        operator_id,
                    )
            except Exception as exc:
                log.warning("LLM provenance write failed (non-fatal)", error=str(exc))
            if out_context is not None:
                out_context["audit_id"] = audit_id
                out_context["grounding_event_ids"] = grounding_event_ids or []
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
            await self._write_telemetry(
                model=_effective_model,
                endpoint="generate",
                prompt_chars=len(prompt),
                completion_chars=0,
                latency_ms=(time.monotonic_ns() - t0) // 1_000_000,
                success=False,
                error_type="HTTPStatusError",
                full_prompt=prompt,
            )
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
            await self._write_telemetry(
                model=_effective_model,
                endpoint="generate",
                prompt_chars=len(prompt),
                completion_chars=0,
                latency_ms=(time.monotonic_ns() - t0) // 1_000_000,
                success=False,
                error_type=type(exc).__name__,
                full_prompt=prompt,
            )
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
        use_cybersec_model: bool = False,
        operator_id: str = "system",
        prompt_template_name: Optional[str] = None,
        prompt_template_sha256: Optional[str] = None,
        grounding_event_ids: Optional[list[str]] = None,
        out_context: Optional[dict] = None,
    ) -> str:
        """
        Generate a streaming text response token by token.

        Args:
            prompt:              The user prompt.
            system:              Optional system message.
            on_token:            Optional synchronous callback called for each token.
                                 Receives the token string.  Use for SSE streaming.
            temperature:         Sampling temperature.
            model:               Override the default model for this call.
            use_cybersec_model:  If True, route to self.cybersec_model instead of
                                 self.model (ADR-020).
            out_context:         Optional dict; if provided, populated with
                                 ``audit_id`` and ``grounding_event_ids`` after the
                                 provenance write.

        Returns:
            The complete response text assembled from all tokens.

        Raises:
            OllamaError: If the API call fails.
        """
        stream_audit_id = str(uuid4())
        _stream_model = model or (self.cybersec_model if use_cybersec_model else self.model)
        await self._check_model_drift(_stream_model)
        payload: dict = {
            "model": _stream_model,
            "prompt": prompt,
            "stream": True,
            "options": {"temperature": temperature},
        }
        if system:
            payload["system"] = system

        full_response: list[str] = []
        t0 = time.monotonic_ns()
        _stream_error: Optional[Exception] = None

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
            _stream_error = exc
            await self._write_telemetry(
                model=_stream_model,
                endpoint="stream_generate",
                prompt_chars=len(prompt),
                completion_chars=len("".join(full_response)),
                latency_ms=(time.monotonic_ns() - t0) // 1_000_000,
                success=False,
                error_type="HTTPStatusError",
                full_prompt=prompt,
            )
            raise OllamaError(
                f"Ollama stream HTTP error {exc.response.status_code}: {exc.response.text}"
            ) from exc
        except Exception as exc:
            _stream_error = exc
            await self._write_telemetry(
                model=_stream_model,
                endpoint="stream_generate",
                prompt_chars=len(prompt),
                completion_chars=len("".join(full_response)),
                latency_ms=(time.monotonic_ns() - t0) // 1_000_000,
                success=False,
                error_type=type(exc).__name__,
                full_prompt=prompt,
            )
            raise OllamaError(f"Ollama stream failed: {exc}") from exc

        result = "".join(full_response)
        log.debug(
            "Stream generate complete",
            model=payload["model"],
            response_len=len(result),
        )
        if _stream_error is None:
            await self._write_telemetry(
                model=_stream_model,
                endpoint="stream_generate",
                prompt_chars=len(prompt),
                completion_chars=len(result),
                latency_ms=(time.monotonic_ns() - t0) // 1_000_000,
                success=True,
                full_prompt=prompt,
            )
            try:
                import asyncio as _asyncio
                stream_response_sha256 = hashlib.sha256(result.encode()).hexdigest()
                if self._sqlite is not None:
                    await _asyncio.to_thread(
                        self._sqlite.record_llm_provenance,
                        stream_audit_id,
                        _stream_model,
                        prompt_template_name,
                        prompt_template_sha256,
                        stream_response_sha256,
                        grounding_event_ids or [],
                        operator_id,
                    )
            except Exception as exc:
                log.warning("LLM provenance write failed (non-fatal)", error=str(exc))
            if out_context is not None:
                out_context["audit_id"] = stream_audit_id
                out_context["grounding_event_ids"] = grounding_event_ids or []
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
        use_cybersec_model: bool = False,
    ) -> AsyncIterator[str]:
        """
        Yield tokens one at a time as an async generator.

        Suitable for Server-Sent Events (SSE) endpoints::

            async for token in client.stream_generate_iter(prompt):
                yield f"data: {json.dumps({'token': token})}\n\n"
        """
        _effective_model = model or (self.cybersec_model if use_cybersec_model else self.model)
        payload: dict = {
            "model": _effective_model,
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
