"""Unit test stubs for Phase 9 explain engine.

Tests P9-T07 (build_evidence_context, generate_explanation).
Wave 0: all stubs are xfail.
Plan 05 will implement backend/intelligence/explain_engine.py.
"""
from unittest.mock import AsyncMock

import pytest

pytestmark = pytest.mark.unit


class TestBuildEvidenceContext:
    @pytest.mark.xfail(reason="P9-T07: backend/intelligence/explain_engine.py not yet implemented")
    def test_build_evidence_context_includes_detection_info(self):
        from backend.intelligence.explain_engine import build_evidence_context
        investigation = {
            "detection": {"rule_name": "Mimikatz", "severity": "critical", "attack_technique": "T1003.001"},
            "events": [],
            "techniques": [],
            "graph": {"elements": {"nodes": []}},
            "timeline": [],
        }
        ctx = build_evidence_context(investigation)
        assert "Mimikatz" in ctx
        assert "T1003.001" in ctx

    @pytest.mark.xfail(reason="P9-T07: build_evidence_context includes top N events")
    def test_build_evidence_context_limits_events(self):
        from backend.intelligence.explain_engine import build_evidence_context
        investigation = {
            "detection": None,
            "events": [{"timestamp": f"2024-01-01T00:{i:02d}:00Z", "event_type": "process_create",
                         "process_name": f"proc{i}.exe", "hostname": "host1",
                         "severity": "low", "attack_technique": None} for i in range(20)],
            "techniques": [],
            "graph": {"elements": {"nodes": []}},
            "timeline": [],
        }
        ctx = build_evidence_context(investigation, max_events=5)
        # at most 5 EVENT: lines
        assert ctx.count("EVENT:") <= 5


class TestGenerateExplanation:
    @pytest.mark.xfail(reason="P9-T07: generate_explanation async not yet implemented")
    async def test_generate_explanation_returns_three_sections(self):
        from backend.intelligence.explain_engine import generate_explanation
        mock_client = AsyncMock()
        mock_client.generate = AsyncMock(return_value=(
            "## What Happened\nFoo\n## Why It Matters\nBar\n## Recommended Next Steps\nBaz"
        ))
        investigation = {
            "detection": {"rule_name": "Test", "severity": "high", "attack_technique": "T1059.001"},
            "events": [], "techniques": [], "graph": {"elements": {"nodes": []}}, "timeline": [],
        }
        result = await generate_explanation(investigation, mock_client)
        assert "what_happened" in result
        assert "why_it_matters" in result
        assert "recommended_next_steps" in result
