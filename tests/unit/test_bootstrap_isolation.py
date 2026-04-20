"""
Bootstrap module isolation tests.

Verifies that backend/startup/* modules import independently without
circular imports or global side effects. This is the architectural
boundary test for the composition-root decomposition.

If any of these tests fail, a circular import or mis-placed dependency
was introduced into the startup bootstrap layer.
"""
from __future__ import annotations

import importlib

import pytest

pytestmark = pytest.mark.unit

_STARTUP_MODULES = [
    "backend.startup.stores",
    "backend.startup.workers",
    "backend.startup.collectors",
    "backend.startup.routers",
]


@pytest.mark.parametrize("module_name", _STARTUP_MODULES)
def test_startup_module_imports_cleanly(module_name: str):
    """Each startup bootstrap module must import without raising ImportError.

    A failure here means a circular import, missing dependency, or
    module-level side effect was introduced into the bootstrap layer.
    """
    try:
        mod = importlib.import_module(module_name)
        assert mod is not None
    except ImportError as exc:
        pytest.fail(
            f"Startup module {module_name!r} failed to import: {exc}\n"
            "Check for circular imports or missing dependencies."
        )


def test_stores_does_not_import_from_routers():
    """stores.py must not import from routers.py (would create circular dep).

    stores initialises data layer; routers depend on stores.
    The dependency must be one-way: routers → stores, never stores → routers.
    """
    import inspect
    import backend.startup.stores as stores_mod

    source = inspect.getsource(stores_mod)
    assert "from backend.startup.routers" not in source, (
        "backend.startup.stores must not import from backend.startup.routers "
        "(circular dependency: stores → routers → stores)"
    )
    assert "import backend.startup.routers" not in source, (
        "backend.startup.stores must not import backend.startup.routers"
    )


def test_workers_does_not_import_from_routers():
    """workers.py must not import from routers.py."""
    import inspect
    import backend.startup.workers as workers_mod

    source = inspect.getsource(workers_mod)
    assert "from backend.startup.routers" not in source
    assert "import backend.startup.routers" not in source


def test_main_create_app_delegates_to_startup_modules():
    """main.create_app() must delegate to all four startup modules.

    This is the integration boundary check: if any startup module gets
    accidentally inlined back into main.py, this test catches it.
    """
    import inspect
    import backend.main as main_mod

    source = inspect.getsource(main_mod)
    assert "from backend.startup.stores import" in source, (
        "main.py must import init_stores from backend.startup.stores"
    )
    assert "from backend.startup.workers import" in source, (
        "main.py must import init_workers from backend.startup.workers"
    )
    assert "from backend.startup.collectors import" in source, (
        "main.py must import init_collectors from backend.startup.collectors"
    )
    assert "from backend.startup.routers import" in source, (
        "main.py must import mount_routers from backend.startup.routers"
    )
