"""Unit tests for backend/core/config.py Settings class."""
import pytest

pytestmark = pytest.mark.unit


def test_cybersec_model_default():
    """OLLAMA_CYBERSEC_MODEL should default to foundation-sec:8b."""
    from backend.core.config import Settings

    s = Settings()
    assert s.OLLAMA_CYBERSEC_MODEL == "foundation-sec:8b"


def test_cybersec_model_override(monkeypatch):
    """OLLAMA_CYBERSEC_MODEL can be overridden via environment variable."""
    monkeypatch.setenv("OLLAMA_CYBERSEC_MODEL", "custom:model")

    from importlib import reload
    import backend.core.config as config_module
    reload(config_module)
    s = config_module.Settings()

    assert s.OLLAMA_CYBERSEC_MODEL == "custom:model"


def test_existing_model_unchanged():
    """Regression: existing OLLAMA_MODEL default must remain qwen3:14b."""
    from backend.core.config import Settings

    s = Settings()
    assert s.OLLAMA_MODEL == "qwen3:14b"
