"""Unit tests for backend/core/config.py Settings class."""
import pytest

pytestmark = pytest.mark.unit


_DUMMY_TOKEN = "a" * 32  # satisfies AUTH_TOKEN minimum-length validator


def test_cybersec_model_default(monkeypatch):
    """OLLAMA_CYBERSEC_MODEL code-default should be foundation-sec:8b (isolated from .env)."""
    monkeypatch.delenv("OLLAMA_CYBERSEC_MODEL", raising=False)
    monkeypatch.setenv("AUTH_TOKEN", _DUMMY_TOKEN)
    from backend.core.config import Settings

    s = Settings(_env_file=None)
    assert s.OLLAMA_CYBERSEC_MODEL == "foundation-sec:8b"


def test_cybersec_model_override(monkeypatch):
    """OLLAMA_CYBERSEC_MODEL can be overridden via environment variable."""
    monkeypatch.setenv("OLLAMA_CYBERSEC_MODEL", "custom:model")

    from importlib import reload
    import backend.core.config as config_module
    reload(config_module)
    s = config_module.Settings()

    assert s.OLLAMA_CYBERSEC_MODEL == "custom:model"


def test_existing_model_unchanged(monkeypatch):
    """Regression: OLLAMA_MODEL code-default must remain qwen3:14b (isolated from .env)."""
    monkeypatch.delenv("OLLAMA_MODEL", raising=False)
    monkeypatch.setenv("AUTH_TOKEN", _DUMMY_TOKEN)
    from backend.core.config import Settings

    s = Settings(_env_file=None)
    assert s.OLLAMA_MODEL == "qwen3:14b"
