"""Tests for slowapi rate limiting integration."""
import os
import pytest
from unittest.mock import patch


def test_limiter_disabled_in_testing_mode():
    """Limiter must be disabled when TESTING=1."""
    with patch.dict(os.environ, {"TESTING": "1"}):
        # Re-import to pick up new env
        import importlib
        import backend.core.rate_limit as rl_module
        importlib.reload(rl_module)
        assert rl_module.limiter.enabled is False


def test_limiter_enabled_in_production_mode():
    """Limiter must be enabled when TESTING is not set."""
    env_without_testing = {k: v for k, v in os.environ.items() if k != "TESTING"}
    with patch.dict(os.environ, env_without_testing, clear=True):
        import importlib
        import backend.core.rate_limit as rl_module
        importlib.reload(rl_module)
        assert rl_module.limiter.enabled is True


def test_slowapi_middleware_registered():
    """SlowAPIMiddleware must be registered in the app's middleware stack."""
    from backend.main import create_app
    from slowapi.middleware import SlowAPIMiddleware

    with patch.dict(os.environ, {"TESTING": "1"}):
        app = create_app()
    middleware_types = [type(m) for m in app.user_middleware]
    middleware_class_names = [m.__class__.__name__ for m in app.user_middleware]
    # SlowAPIMiddleware is registered as a starlette middleware
    assert any("SlowAPI" in name for name in middleware_class_names) or \
           SlowAPIMiddleware in middleware_types or \
           any(hasattr(m, 'cls') and m.cls is SlowAPIMiddleware for m in app.user_middleware)


def test_rate_limit_exceeded_handler_registered():
    """RateLimitExceeded handler must be registered."""
    from backend.main import create_app
    from slowapi.errors import RateLimitExceeded

    with patch.dict(os.environ, {"TESTING": "1"}):
        app = create_app()
    assert RateLimitExceeded in app.exception_handlers
