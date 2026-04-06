"""
Wave 0 stub tests for authentication hardening requirements.

All tests are pre-skipped. They are activated in subsequent implementation plans:
- 23.5-02: T01, T02
- 23.5-03: T09, T11, T12

Requirements covered: P23.5-T01, P23.5-T02, P23.5-T09, P23.5-T11, P23.5-T12
"""
import pytest


@pytest.mark.skip(reason="stub — activated in 23.5-02")
def test_default_token_rejected():
    """
    T01: Settings must raise ValueError when AUTH_TOKEN == 'changeme' or len < 32.
    Verifies the model_validator(mode='after') added in plan 23.5-02.
    """
    from backend.core.config import Settings

    with pytest.raises(ValueError, match="AUTH_TOKEN"):
        Settings(AUTH_TOKEN="changeme")

    with pytest.raises(ValueError):
        Settings(AUTH_TOKEN="tooshort")

    assert False, "stub — not yet implemented"


@pytest.mark.skip(reason="stub — activated in 23.5-02")
def test_legacy_path_requires_totp():
    """
    T02: The legacy-admin path in auth.py must return 401 when TOTP code is absent.
    Verifies TOTP enforcement on the legacy hmac path (line ~130 in auth.py).
    """
    from fastapi.testclient import TestClient

    from backend.main import create_app

    client = TestClient(create_app())
    # Legacy-admin path without TOTP code should return 401
    response = client.get("/api/admin/legacy", headers={"Authorization": "Bearer valid-token"})
    assert response.status_code == 401, "Legacy admin path must require TOTP"

    assert False, "stub — not yet implemented"


@pytest.mark.skip(reason="stub — activated in 23.5-03")
def test_health_no_path_leak():
    """
    T09: /health component error detail must not expose filesystem paths or tracebacks.
    Verifies that health check error responses are sanitised before returning to clients.
    """
    from fastapi.testclient import TestClient

    from backend.main import create_app

    client = TestClient(create_app())
    response = client.get("/health")
    body = response.text
    # Must not contain filesystem path separators or traceback keywords
    assert "/" not in body or "Traceback" not in body, "Health endpoint must not leak paths"

    assert False, "stub — not yet implemented"


@pytest.mark.skip(reason="stub — activated in 23.5-03")
def test_totp_replay_after_restart():
    """
    T11: A seen TOTP code must be rejected even after the in-memory seen-codes dict is reset,
    simulating an application restart.
    """
    from backend.core import auth as auth_module

    # Simulate used TOTP code
    test_code = "123456"
    # After resetting the replay-prevention store, the code should still be rejected
    # (requires persistent or time-window-based replay prevention)
    assert False, "stub — not yet implemented"


@pytest.mark.skip(reason="stub — activated in 23.5-03")
def test_full_prompt_logged():
    """
    T12: _write_telemetry must store the full prompt_text (not just prompt_chars count)
    in the llm_calls table so that prompt injection can be audited.
    """
    from backend.services import ollama as ollama_module

    # Verify _write_telemetry persists prompt_text column
    assert False, "stub — not yet implemented"
