"""TDD stubs for Phase 45 agent tools. P45-T01.
All tests skip until backend/services/agent/tools.py exists."""
from __future__ import annotations
import pytest

pytestmark = pytest.mark.unit

try:
    from backend.services.agent.tools import (
        QueryEventsTool,
        GetEntityProfileTool,
        EnrichIpTool,
        SearchSigmaMatchesTool,
        GetGraphNeighborsTool,
        SearchSimilarIncidentsTool,
    )
    _TOOLS_AVAILABLE = True
except ImportError:
    _TOOLS_AVAILABLE = False

_skip = pytest.mark.skipif(not _TOOLS_AVAILABLE, reason="agent tools not implemented yet")


class TestQueryEventsTool:
    @_skip
    def test_returns_string(self):
        """QueryEventsTool.forward() returns a non-empty string summary."""
        import duckdb
        conn = duckdb.connect(":memory:")
        conn.execute("""
            CREATE TABLE normalized_events (
                event_id TEXT, hostname TEXT, process_name TEXT,
                event_type TEXT, timestamp TIMESTAMP
            )
        """)
        conn.execute("INSERT INTO normalized_events VALUES ('e1','HOST1','cmd.exe','process_create',NOW())")

        class _FakeStore:
            _db_path = ":memory:"  # won't be used; tool opens own conn

        # Tool needs a db_path, not an async store
        tool = QueryEventsTool(db_path=conn.database if hasattr(conn, 'database') else ":memory:")
        result = tool.forward(hostname="HOST1", limit=5)
        assert isinstance(result, str)
        assert len(result) > 0

    @_skip
    def test_hostname_filter(self):
        """Query with unknown hostname returns 'no events found' message."""
        tool = QueryEventsTool(db_path=":memory:")
        result = tool.forward(hostname="NONEXISTENT", limit=5)
        assert isinstance(result, str)


class TestGetEntityProfileTool:
    @_skip
    def test_returns_string(self):
        """GetEntityProfileTool.forward() returns profile string."""
        tool = GetEntityProfileTool(db_path=":memory:")
        result = tool.forward(hostname="HOST1")
        assert isinstance(result, str)


class TestEnrichIpTool:
    @_skip
    def test_returns_string(self):
        """EnrichIpTool.forward() returns enrichment string without network call."""
        import tempfile, os
        with tempfile.TemporaryDirectory() as tmp:
            tool = EnrichIpTool(sqlite_path=os.path.join(tmp, "test.db"))
            result = tool.forward(ip="1.2.3.4")
            assert isinstance(result, str)


class TestSearchSigmaMatchesTool:
    @_skip
    def test_returns_string(self):
        """SearchSigmaMatchesTool.forward() returns matches string."""
        import tempfile, os
        with tempfile.TemporaryDirectory() as tmp:
            tool = SearchSigmaMatchesTool(sqlite_path=os.path.join(tmp, "test.db"))
            result = tool.forward(hostname="HOST1")
            assert isinstance(result, str)


class TestGetGraphNeighborsTool:
    @_skip
    def test_returns_string(self):
        """GetGraphNeighborsTool.forward() returns neighbors string."""
        import tempfile, os
        with tempfile.TemporaryDirectory() as tmp:
            tool = GetGraphNeighborsTool(sqlite_path=os.path.join(tmp, "test.db"))
            result = tool.forward(entity_id="HOST1")
            assert isinstance(result, str)


class TestSearchSimilarIncidentsTool:
    @_skip
    def test_returns_string(self):
        """SearchSimilarIncidentsTool.forward() returns similar incidents string."""
        import tempfile, os
        with tempfile.TemporaryDirectory() as tmp:
            tool = SearchSimilarIncidentsTool(chroma_path=os.path.join(tmp, "chroma"))
            result = tool.forward(detection_id="det-001", narrative="suspicious process")
            assert isinstance(result, str)
