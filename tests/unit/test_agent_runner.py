"""TDD stubs for Phase 45 agent runner. P45-T02, P45-T05.
All tests skip until backend/services/agent/runner.py exists."""
from __future__ import annotations
import pytest

pytestmark = pytest.mark.unit

try:
    from backend.services.agent.runner import build_agent, run_investigation
    _RUNNER_AVAILABLE = True
except ImportError:
    _RUNNER_AVAILABLE = False

_skip = pytest.mark.skipif(not _RUNNER_AVAILABLE, reason="agent runner not implemented yet")


@_skip
def test_build_agent():
    """build_agent(stores) returns a ToolCallingAgent with 6 tools."""
    from smolagents import ToolCallingAgent
    from types import SimpleNamespace
    import tempfile, os
    with tempfile.TemporaryDirectory() as tmp:
        import duckdb
        db_path = os.path.join(tmp, "events.duckdb")
        duckdb.connect(db_path).close()
        stores = SimpleNamespace(
            duckdb=SimpleNamespace(_db_path=db_path),
            sqlite=SimpleNamespace(_db_path=os.path.join(tmp, "soc.db")),
            chroma=SimpleNamespace(_data_dir=tmp),
        )
        agent = build_agent(stores)
        assert isinstance(agent, ToolCallingAgent)
        assert len(agent.tools) == 6  # 6 investigation tools


@_skip
def test_max_steps_limit():
    """build_agent respects max_steps=10 configuration."""
    from types import SimpleNamespace
    import tempfile, os
    with tempfile.TemporaryDirectory() as tmp:
        stores = SimpleNamespace(
            duckdb=SimpleNamespace(_db_path=os.path.join(tmp, "e.duckdb")),
            sqlite=SimpleNamespace(_db_path=os.path.join(tmp, "s.db")),
            chroma=SimpleNamespace(_data_dir=tmp),
        )
        agent = build_agent(stores)
        assert agent.max_steps == 10


@_skip
def test_timeout_fires():
    """run_investigation raises asyncio.TimeoutError when timeout < agent duration."""
    pytest.skip("requires live smolagents execution — integration test")
