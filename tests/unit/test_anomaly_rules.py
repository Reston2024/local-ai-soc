"""Unit tests for Phase 9 anomaly detection rules.

Tests P9-T03 (check_event_anomalies, ANOMALY_RULES).
"""
import pytest

pytestmark = pytest.mark.unit


class TestAnomalyRules:
    def test_office_spawns_shell_fires(self):
        from backend.intelligence.anomaly_rules import check_event_anomalies
        event = {"parent_process_name": "winword.exe", "process_name": "powershell.exe"}
        flags = check_event_anomalies(event)
        assert "ANO-001" in flags

    def test_normal_process_pair_no_flag(self):
        from backend.intelligence.anomaly_rules import check_event_anomalies
        event = {"parent_process_name": "explorer.exe", "process_name": "notepad.exe"}
        flags = check_event_anomalies(event)
        assert "ANO-001" not in flags

    def test_process_masquerading_flags(self):
        from backend.intelligence.anomaly_rules import check_event_anomalies
        event = {
            "parent_process_name": "explorer.exe",
            "process_name": "svchost.exe",
            "process_path": "C:\\Users\\user\\AppData\\Local\\Temp\\svchost.exe",
        }
        flags = check_event_anomalies(event)
        assert "ANO-003" in flags

    def test_unusual_external_port_flags(self):
        from backend.intelligence.anomaly_rules import check_event_anomalies
        event = {
            "dest_ip": "185.220.101.45",
            "dest_port": 4444,
        }
        flags = check_event_anomalies(event)
        assert "ANO-004" in flags

    def test_anomaly_rules_list_non_empty(self):
        from backend.intelligence.anomaly_rules import ANOMALY_RULES
        assert len(ANOMALY_RULES) >= 4
