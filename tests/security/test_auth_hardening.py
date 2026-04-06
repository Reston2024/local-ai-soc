"""
Wave 0 stub tests for authentication hardening requirements.

All tests are pre-skipped. They are activated in subsequent implementation plans:
- 23.5-02: T01, T02
- 23.5-03: T09, T11, T12

Requirements covered: P23.5-T01, P23.5-T02, P23.5-T09, P23.5-T11, P23.5-T12
"""
import pytest


def test_default_token_rejected():
    """
    T01: Settings must raise ValueError/ValidationError when AUTH_TOKEN == 'changeme' or len < 32.
    Verifies the model_validator(mode='after') added in plan 23.5-02.
    """
    from pydantic import ValidationError

    from backend.core.config import Settings

    # Default value "changeme" must be rejected
    with pytest.raises((ValueError, ValidationError)):
        Settings(AUTH_TOKEN="changeme")

    # Weak token (too short, < 32 chars) must be rejected
    with pytest.raises((ValueError, ValidationError)):
        Settings(AUTH_TOKEN="tooshort")

    # Strong token (>= 32 chars) must succeed
    strong = Settings(AUTH_TOKEN="a" * 32)
    assert strong.AUTH_TOKEN == "a" * 32

    # Explicit dev bypass value is accepted (allows intentional weak tokens for local dev)
    dev = Settings(AUTH_TOKEN="dev-only-bypass")
    assert dev.AUTH_TOKEN == "dev-only-bypass"


@pytest.mark.asyncio
async def test_legacy_path_requires_totp(monkeypatch):
    """
    T02: The legacy-admin path in auth.py must return 401 when TOTP code is absent.
    Verifies TOTP enforcement on the legacy hmac path (line ~130 in auth.py).
    Tests verify_token() directly as a unit test — no full app needed.
    """
    from unittest.mock import MagicMock

    from fastapi import HTTPException
    from fastapi.security import HTTPAuthorizationCredentials

    from backend.core.auth import verify_token

    strong_token = "a" * 32
    mock_settings = MagicMock()
    mock_settings.AUTH_TOKEN = strong_token
    mock_settings.LEGACY_TOTP_SECRET = ""  # empty = legacy path disabled → 401 always

    monkeypatch.setattr("backend.core.auth.settings", mock_settings)

    # Build a mock request: no operator in sqlite (falls through to legacy path)
    mock_request = MagicMock()
    mock_request.app.state.stores.sqlite.get_operator_by_prefix.return_value = None
    mock_request.app.state.stores.sqlite.update_last_seen = MagicMock()
    mock_request.state = MagicMock()
    mock_request.headers.get.return_value = None  # no X-TOTP-Code header

    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=strong_token)

    # With LEGACY_TOTP_SECRET="" and no TOTP header — must raise 401
    with pytest.raises(HTTPException) as exc_info:
        await verify_token(request=mock_request, credentials=creds)
    assert exc_info.value.status_code == 401
    # Detail must mention legacy path or TOTP
    detail = exc_info.value.detail.lower()
    assert "legacy" in detail or "totp" in detail


@pytest.mark.asyncio
async def test_health_no_path_leak():
    """
    T09/E3-04: /health component error detail must not expose filesystem paths or tracebacks.
    Verifies that health check error responses are sanitised before returning to clients.
    """
    from unittest.mock import AsyncMock, MagicMock, patch

    from fastapi.testclient import TestClient

    from backend.api.health import router

    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(router)

    # Build a fake stores state where duckdb raises with a file path in the message
    fake_path = "/data/secret/backend.duckdb"
    fake_duckdb = MagicMock()
    fake_duckdb.fetch_all = AsyncMock(
        side_effect=RuntimeError(f"Cannot open database: {fake_path}")
    )

    fake_chroma = MagicMock()
    fake_chroma.list_collections_async = AsyncMock(
        side_effect=RuntimeError(f"Chroma directory not found: {fake_path}")
    )

    fake_sqlite = MagicMock()
    fake_sqlite.health_check = MagicMock(
        side_effect=RuntimeError(f"SQLite file missing: {fake_path}")
    )

    fake_ollama = MagicMock()
    fake_ollama.health_check = AsyncMock(return_value=True)

    fake_stores = MagicMock()
    fake_stores.duckdb = fake_duckdb
    fake_stores.chroma = fake_chroma
    fake_stores.sqlite = fake_sqlite

    app.state.stores = fake_stores
    app.state.ollama = fake_ollama

    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/health")

    body = response.text
    # The fake_path must NOT appear anywhere in the response body
    assert fake_path not in body, (
        f"Health endpoint leaked file path in response: {body!r}"
    )
    # No Python traceback keywords should appear
    assert "Traceback" not in body, (
        f"Health endpoint leaked traceback in response: {body!r}"
    )
    assert "RuntimeError" not in body, (
        f"Health endpoint leaked exception class name in response: {body!r}"
    )


def test_totp_replay_after_restart():
    """
    T11: A seen TOTP code must be rejected even after the in-memory seen-codes dict is reset,
    simulating an application restart.

    Uses a mock SQLiteStore where get_kv returns a future expiry timestamp (simulating a
    code that was accepted before a restart and is still within its TTL window).
    """
    import time
    from unittest.mock import MagicMock

    from backend.core.totp_utils import _totp_cache_key, _totp_already_seen, _seen_totp, verify_totp

    operator_id = "test-operator"
    test_code = "123456"
    cache_key = _totp_cache_key(operator_id, test_code)

    # Clear L1 cache to simulate a fresh process start
    _seen_totp.clear()

    # Mock SQLiteStore: get_kv returns a future expiry (code was seen before restart)
    mock_sqlite = MagicMock()
    mock_sqlite.get_kv.return_value = str(time.time() + 60.0)  # still valid, 60s left
    mock_sqlite.set_kv = MagicMock()

    # _totp_already_seen must return True — code was seen before restart
    already_seen = _totp_already_seen(operator_id, test_code, mock_sqlite)
    assert already_seen is True, (
        "Expected TOTP code to be rejected after restart when SQLite reports it was already used"
    )
    mock_sqlite.get_kv.assert_called_once_with(cache_key)

    # The in-process L1 cache should now be warmed from SQLite
    assert cache_key in _seen_totp, "Expected L1 cache to be warmed from SQLite authoritative store"

    # Second check: L1 cache should serve it directly (no second SQLite hit)
    mock_sqlite.get_kv.reset_mock()
    already_seen_again = _totp_already_seen(operator_id, test_code, mock_sqlite)
    assert already_seen_again is True
    mock_sqlite.get_kv.assert_not_called()

    # Fresh code not in SQLite (get_kv returns None) should be accepted
    fresh_code = "654321"
    fresh_cache_key = _totp_cache_key(operator_id, fresh_code)
    mock_sqlite.get_kv.return_value = None

    already_seen_fresh = _totp_already_seen(operator_id, fresh_code, mock_sqlite)
    assert already_seen_fresh is False, "Expected fresh code (not in SQLite) to be accepted"
    # After acceptance, code should be stored in SQLite and L1 cache
    mock_sqlite.set_kv.assert_called_once()
    set_kv_args = mock_sqlite.set_kv.call_args[0]
    assert set_kv_args[0] == fresh_cache_key, "set_kv must be called with the correct cache key"
    stored_expire = float(set_kv_args[1])
    expected_expire = time.time() + 90.0
    assert abs(stored_expire - expected_expire) < 5.0, (
        f"set_kv expire timestamp off by more than 5s: stored={stored_expire}, expected~{expected_expire}"
    )
    assert fresh_cache_key in _seen_totp


@pytest.mark.asyncio
async def test_full_prompt_logged():
    """
    T12: _write_telemetry must store the full prompt_text (not just prompt_chars count)
    and its SHA-256 hash in the llm_calls table so that prompt injection can be audited.
    """
    import hashlib
    from unittest.mock import AsyncMock, MagicMock, call

    from backend.services.ollama_client import OllamaClient

    known_prompt = "Explain lateral movement technique T1021 in detail for triage purposes."

    # Mock DuckDB store
    mock_duckdb = MagicMock()
    execute_write_calls = []

    async def fake_execute_write(sql, params=None):
        execute_write_calls.append((sql, params))

    mock_duckdb.execute_write = fake_execute_write

    client = OllamaClient(duckdb_store=mock_duckdb)

    await client._write_telemetry(
        model="qwen3:14b",
        endpoint="generate",
        prompt_chars=len(known_prompt),
        completion_chars=100,
        latency_ms=500,
        success=True,
        full_prompt=known_prompt,
    )

    assert len(execute_write_calls) == 1, "Expected exactly one INSERT into llm_calls"
    sql, params = execute_write_calls[0]

    assert "prompt_text" in sql, "INSERT SQL must include prompt_text column"
    assert "prompt_hash" in sql, "INSERT SQL must include prompt_hash column"
    assert params is not None

    # Locate prompt_text and prompt_hash in params list
    # params order: call_id, called_at, model, endpoint, prompt_chars,
    #               completion_chars, latency_ms, success, error_type, prompt_text, prompt_hash
    prompt_text_val = params[9]
    prompt_hash_val = params[10]

    assert prompt_text_val == known_prompt, (
        f"prompt_text must equal the full prompt. Got: {prompt_text_val!r}"
    )

    expected_hash = hashlib.sha256(known_prompt.encode("utf-8", errors="replace")).hexdigest()
    assert prompt_hash_val == expected_hash, (
        f"prompt_hash must be SHA-256 of the prompt. Got: {prompt_hash_val!r}"
    )
    assert len(prompt_hash_val) == 64, (
        f"SHA-256 hex digest must be 64 chars. Got length: {len(prompt_hash_val)}"
    )

    # Test that long prompts are truncated at 64 KB
    long_prompt = "A" * 70000
    execute_write_calls.clear()
    await client._write_telemetry(
        model="qwen3:14b",
        endpoint="generate",
        prompt_chars=len(long_prompt),
        completion_chars=0,
        latency_ms=100,
        success=False,
        full_prompt=long_prompt,
    )
    _, long_params = execute_write_calls[0]
    stored_text = long_params[9]
    stored_hash = long_params[10]
    assert len(stored_text) == 65536, f"prompt_text must be truncated to 65536 chars, got {len(stored_text)}"
    # Hash is computed from FULL prompt (not truncated)
    full_hash = hashlib.sha256(long_prompt.encode("utf-8", errors="replace")).hexdigest()
    assert stored_hash == full_hash, "prompt_hash must be of the full (un-truncated) prompt"
