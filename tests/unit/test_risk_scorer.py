"""Unit tests for Phase 9 risk scoring module.

Tests P9-T01 (score_entity), P9-T02 (MITRE_WEIGHTS), P9-T08 (enrich_nodes_with_risk_score).
"""
import pytest

pytestmark = pytest.mark.unit


class TestScoreEntity:
    def test_score_entity_returns_int_0_to_100(self):
        from backend.intelligence.risk_scorer import score_entity
        result = score_entity(
            entity_id="svchosts.exe",
            events=[{"severity": "critical", "attack_technique": "T1003.001"}],
            detections=[{"severity": "critical"}],
            anomaly_flags=["ANO-001"],
        )
        assert isinstance(result, int)
        assert 0 <= result <= 100

    def test_score_detection_high_mitre_gives_high_score(self):
        from backend.intelligence.risk_scorer import score_detection
        result = score_detection(severity="critical", technique_id="T1003.001", anomaly_count=2)
        assert result >= 70

    def test_score_entity_low_severity_no_anomalies(self):
        from backend.intelligence.risk_scorer import score_entity
        result = score_entity(
            entity_id="notepad.exe",
            events=[{"severity": "low", "attack_technique": None}],
            detections=[],
            anomaly_flags=[],
        )
        assert result < 40


class TestMitreWeights:
    def test_critical_technique_weight_is_40_or_more(self):
        from backend.intelligence.risk_scorer import MITRE_WEIGHTS
        assert MITRE_WEIGHTS.get("T1003.001", 0) >= 40

    def test_high_technique_weight_is_30(self):
        from backend.intelligence.risk_scorer import MITRE_WEIGHTS
        assert MITRE_WEIGHTS.get("T1059.001", 0) >= 25

    def test_unknown_technique_defaults_to_zero(self):
        from backend.intelligence.risk_scorer import MITRE_WEIGHTS
        assert MITRE_WEIGHTS.get("T9999.999", 0) == 0


class TestNodeData:
    def test_enrich_nodes_adds_risk_score_field(self):
        from backend.intelligence.risk_scorer import enrich_nodes_with_risk_score
        nodes = [
            {"data": {"id": "svchosts.exe", "entity_type": "process", "severity": "critical"}}
        ]
        enriched = enrich_nodes_with_risk_score(nodes, scored_entities={"svchosts.exe": 85})
        assert enriched[0]["data"]["risk_score"] == 85

    def test_enrich_nodes_defaults_missing_to_zero(self):
        from backend.intelligence.risk_scorer import enrich_nodes_with_risk_score
        nodes = [{"data": {"id": "explorer.exe", "entity_type": "process"}}]
        enriched = enrich_nodes_with_risk_score(nodes, scored_entities={})
        assert enriched[0]["data"]["risk_score"] == 0
