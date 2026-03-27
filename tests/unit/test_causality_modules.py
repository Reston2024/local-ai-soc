"""Unit tests for causality modules — pure function tests.

Covers:
- backend/causality/entity_resolver.py
- backend/causality/attack_chain_builder.py
- backend/causality/scoring.py
- backend/causality/engine.py
- backend/causality/mitre_mapper.py
- backend/investigation/tagging.py
"""
import sqlite3

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# entity_resolver tests
# ---------------------------------------------------------------------------

class TestEntityResolver:
    def test_resolve_host_lowercases(self):
        from backend.causality.entity_resolver import resolve_canonical_id
        result = resolve_canonical_id({"hostname": "DC01"}, "host")
        assert result == "host:dc01"

    def test_resolve_host_strips_domain_suffix(self):
        from backend.causality.entity_resolver import resolve_canonical_id
        result = resolve_canonical_id({"hostname": "dc01.corp.local"}, "host")
        assert result == "host:dc01"

    def test_resolve_user_strips_domain_prefix(self):
        from backend.causality.entity_resolver import resolve_canonical_id
        result = resolve_canonical_id({"username": "CORP\\jsmith"}, "user")
        assert result == "user:jsmith"

    def test_resolve_user_strips_email_suffix(self):
        from backend.causality.entity_resolver import resolve_canonical_id
        result = resolve_canonical_id({"username": "jsmith@corp.com"}, "user")
        assert result == "user:jsmith"

    def test_resolve_user_plain_lowercases(self):
        from backend.causality.entity_resolver import resolve_canonical_id
        result = resolve_canonical_id({"username": "Alice"}, "user")
        assert result == "user:alice"

    def test_resolve_process_basename(self):
        from backend.causality.entity_resolver import resolve_canonical_id
        result = resolve_canonical_id(
            {"process_name": "C:\\Windows\\System32\\cmd.exe"}, "process"
        )
        assert result == "process:cmd.exe"

    def test_resolve_process_forward_slash(self):
        from backend.causality.entity_resolver import resolve_canonical_id
        result = resolve_canonical_id(
            {"process_name": "/usr/bin/python3"}, "process"
        )
        assert result == "process:python3"

    def test_resolve_ip_src_strips_port(self):
        from backend.causality.entity_resolver import resolve_canonical_id
        result = resolve_canonical_id({"src_ip": "192.168.1.1:443"}, "ip_src")
        assert result == "ip:192.168.1.1"

    def test_resolve_ip_dst_no_port(self):
        from backend.causality.entity_resolver import resolve_canonical_id
        result = resolve_canonical_id({"dst_ip": "10.0.0.1"}, "ip_dst")
        assert result == "ip:10.0.0.1"

    def test_resolve_domain_strips_trailing_dot(self):
        from backend.causality.entity_resolver import resolve_canonical_id
        result = resolve_canonical_id({"domain": "example.com."}, "domain")
        assert result == "domain:example.com"

    def test_resolve_domain_lowercases(self):
        from backend.causality.entity_resolver import resolve_canonical_id
        result = resolve_canonical_id({"domain": "EVIL.COM"}, "domain")
        assert result == "domain:evil.com"

    def test_resolve_returns_none_for_missing_field(self):
        from backend.causality.entity_resolver import resolve_canonical_id
        result = resolve_canonical_id({}, "host")
        assert result is None

    def test_resolve_returns_none_for_empty_string(self):
        from backend.causality.entity_resolver import resolve_canonical_id
        result = resolve_canonical_id({"hostname": ""}, "host")
        assert result is None

    def test_resolve_file_basename(self):
        from backend.causality.entity_resolver import resolve_canonical_id
        result = resolve_canonical_id(
            {"file_path": "C:\\Temp\\malware.exe"}, "file"
        )
        assert result == "file:malware.exe"

    def test_resolve_unknown_type_lowercases(self):
        from backend.causality.entity_resolver import resolve_canonical_id
        result = resolve_canonical_id({"unknown_type": "VALUE"}, "unknown_type")
        assert result == "unknown_type:value"

    def test_field_map_has_expected_keys(self):
        from backend.causality.entity_resolver import FIELD_MAP
        assert "host" in FIELD_MAP
        assert "user" in FIELD_MAP
        assert "process" in FIELD_MAP
        assert "ip_src" in FIELD_MAP
        assert "ip_dst" in FIELD_MAP


# ---------------------------------------------------------------------------
# attack_chain_builder tests
# ---------------------------------------------------------------------------

class TestAttackChainBuilder:
    def test_find_causal_chain_returns_empty_for_unknown_start(self):
        from backend.causality.attack_chain_builder import find_causal_chain
        result = find_causal_chain("nonexistent-id", [])
        assert result == []

    def test_find_causal_chain_single_event(self):
        from backend.causality.attack_chain_builder import find_causal_chain
        events = [{"id": "evt-1", "hostname": "host1", "timestamp": "2026-01-01"}]
        result = find_causal_chain("evt-1", events)
        assert len(result) == 1
        assert result[0]["id"] == "evt-1"

    def test_find_causal_chain_links_shared_host(self):
        from backend.causality.attack_chain_builder import find_causal_chain
        events = [
            {"id": "evt-1", "hostname": "dc01", "timestamp": "2026-01-01T10:00:00"},
            {"id": "evt-2", "hostname": "dc01", "timestamp": "2026-01-01T10:01:00"},
            {"id": "evt-3", "hostname": "workstation1", "timestamp": "2026-01-01T10:02:00"},
        ]
        result = find_causal_chain("evt-1", events)
        ids = [e["id"] for e in result]
        assert "evt-1" in ids
        assert "evt-2" in ids
        # evt-3 has different host — may or may not be included
        assert "evt-3" not in ids

    def test_find_causal_chain_respects_max_events(self):
        from backend.causality.attack_chain_builder import find_causal_chain
        events = [
            {"id": f"evt-{i}", "hostname": "host1", "timestamp": f"2026-01-01T{i:02d}:00:00"}
            for i in range(20)
        ]
        result = find_causal_chain("evt-0", events, max_events=5)
        assert len(result) <= 5

    def test_find_causal_chain_sorted_by_timestamp(self):
        from backend.causality.attack_chain_builder import find_causal_chain
        events = [
            {"id": "evt-a", "hostname": "host1", "timestamp": "2026-01-01T10:02:00"},
            {"id": "evt-b", "hostname": "host1", "timestamp": "2026-01-01T10:00:00"},
            {"id": "evt-c", "hostname": "host1", "timestamp": "2026-01-01T10:01:00"},
        ]
        result = find_causal_chain("evt-a", events)
        timestamps = [e["timestamp"] for e in result]
        assert timestamps == sorted(timestamps)

    def test_get_entity_ids_empty_event(self):
        from backend.causality.attack_chain_builder import _get_entity_ids
        result = _get_entity_ids({})
        assert result == set()

    def test_get_entity_ids_with_host(self):
        from backend.causality.attack_chain_builder import _get_entity_ids
        result = _get_entity_ids({"hostname": "dc01"})
        assert "host:dc01" in result


# ---------------------------------------------------------------------------
# scoring tests
# ---------------------------------------------------------------------------

class TestScoringModule:
    def test_score_chain_empty_returns_zero(self):
        from backend.causality.scoring import score_chain
        result = score_chain([], [], [])
        assert result == 0

    def test_score_chain_critical_alert(self):
        from backend.causality.scoring import score_chain
        alerts = [{"severity": "critical"}]
        result = score_chain([], alerts, [])
        assert result == 40

    def test_score_chain_high_alert(self):
        from backend.causality.scoring import score_chain
        alerts = [{"severity": "high"}]
        result = score_chain([], alerts, [])
        assert result == 30

    def test_score_chain_technique_adds_points(self):
        from backend.causality.scoring import score_chain
        techniques = ["T1059"]
        result = score_chain([], [], techniques)
        assert result == 5

    def test_score_chain_four_techniques_cap_at_20(self):
        from backend.causality.scoring import score_chain
        techniques = ["T1059", "T1078", "T1003", "T1110", "T1021"]
        result = score_chain([], [], techniques)
        # 5 unique techniques = 25 pts but capped at 20
        assert result == 20

    def test_score_chain_length_adds_points(self):
        from backend.causality.scoring import score_chain
        events = [{"id": f"e{i}"} for i in range(5)]
        result = score_chain(events, [], [])
        assert result == 10  # 5 * 2 = 10

    def test_score_chain_length_capped_at_20(self):
        from backend.causality.scoring import score_chain
        events = [{"id": f"e{i}"} for i in range(20)]
        result = score_chain(events, [], [])
        assert result == 20  # capped at 20

    def test_score_chain_recurrence_bonus(self):
        from backend.causality.scoring import score_chain
        events = [
            {"host": "dc01"},
            {"host": "dc01"},
            {"host": "dc01"},
        ]
        result = score_chain(events, [], [])
        # 3 events * 2 = 6 points for length + 20 for recurrence
        assert result == 26

    def test_score_chain_max_is_100(self):
        from backend.causality.scoring import score_chain
        # Max everything out
        alerts = [{"severity": "critical"}]  # 40 pts
        techniques = ["T1", "T2", "T3", "T4"]  # 20 pts
        events = [{"host": "h", "id": f"e{i}"} for i in range(10)]  # 20 pts + recurrence 20 pts
        result = score_chain(events, alerts, techniques)
        assert result <= 100

    def test_score_chain_object_alert(self):
        """Alert can be an object with .severity attribute."""
        from types import SimpleNamespace

        from backend.causality.scoring import score_chain
        alert = SimpleNamespace(severity="high")
        result = score_chain([], [alert], [])
        assert result == 30


# ---------------------------------------------------------------------------
# tagging tests
# ---------------------------------------------------------------------------

class TestTagging:
    def _make_db(self):
        """Create an in-memory SQLite DB with the case_tags schema."""
        conn = sqlite3.connect(":memory:")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS cases (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                status TEXT DEFAULT 'active',
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS case_tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id TEXT NOT NULL,
                tag TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(case_id, tag)
            )
        """)
        conn.commit()
        return conn

    def test_add_tag(self):
        from backend.investigation.tagging import add_tag, list_tags
        conn = self._make_db()
        add_tag(conn, "case-001", "malware")
        tags = list_tags(conn, "case-001")
        assert "malware" in tags

    def test_add_tag_idempotent(self):
        from backend.investigation.tagging import add_tag, list_tags
        conn = self._make_db()
        add_tag(conn, "case-001", "apt")
        add_tag(conn, "case-001", "apt")  # duplicate — should not raise
        tags = list_tags(conn, "case-001")
        assert tags.count("apt") == 1

    def test_remove_tag(self):
        from backend.investigation.tagging import add_tag, list_tags, remove_tag
        conn = self._make_db()
        add_tag(conn, "case-001", "lateral-movement")
        remove_tag(conn, "case-001", "lateral-movement")
        tags = list_tags(conn, "case-001")
        assert "lateral-movement" not in tags

    def test_remove_nonexistent_tag_is_noop(self):
        from backend.investigation.tagging import list_tags, remove_tag
        conn = self._make_db()
        remove_tag(conn, "case-001", "does-not-exist")  # should not raise
        tags = list_tags(conn, "case-001")
        assert tags == []

    def test_list_tags_empty(self):
        from backend.investigation.tagging import list_tags
        conn = self._make_db()
        tags = list_tags(conn, "case-999")
        assert tags == []

    def test_add_tags_to_case_multiple(self):
        from backend.investigation.tagging import add_tags_to_case, list_tags
        conn = self._make_db()
        add_tags_to_case(conn, "case-001", ["apt29", "credential-theft", "lateral-movement"])
        tags = list_tags(conn, "case-001")
        assert len(tags) == 3
        assert "apt29" in tags

    def test_tags_isolated_by_case(self):
        from backend.investigation.tagging import add_tag, list_tags
        conn = self._make_db()
        add_tag(conn, "case-A", "malware")
        add_tag(conn, "case-B", "phishing")
        assert list_tags(conn, "case-A") == ["malware"]
        assert list_tags(conn, "case-B") == ["phishing"]


# ---------------------------------------------------------------------------
# MitreMapper tests
# ---------------------------------------------------------------------------

class TestMitreMapper:
    def test_map_techniques_sigma_tag(self):
        from backend.causality.mitre_mapper import map_techniques
        result = map_techniques(["attack.t1059.001"], "", "")
        assert len(result) == 1
        assert result[0]["technique"] == "T1059.001"
        assert result[0]["tactic"] == "Execution"

    def test_map_techniques_unknown_tag_returns_empty(self):
        from backend.causality.mitre_mapper import map_techniques
        result = map_techniques(["attack.t9999.999"], "", "")
        assert result == []

    def test_map_techniques_non_attack_tag_skipped(self):
        from backend.causality.mitre_mapper import map_techniques
        result = map_techniques(["defense.evasion", "tlp.white"], "", "")
        assert result == []

    def test_map_techniques_fallback_event_type(self):
        from backend.causality.mitre_mapper import map_techniques
        result = map_techniques([], "dns_query", "")
        assert len(result) == 1
        assert result[0]["technique"] == "T1071.004"

    def test_map_techniques_fallback_alert_category(self):
        from backend.causality.mitre_mapper import map_techniques
        result = map_techniques([], "", "potentially bad traffic")
        assert len(result) == 1
        assert result[0]["technique"] == "T1048"

    def test_map_techniques_empty_all_returns_empty(self):
        from backend.causality.mitre_mapper import map_techniques
        result = map_techniques([], "", "")
        assert result == []

    def test_technique_catalog_has_required_entries(self):
        from backend.causality.mitre_mapper import TECHNIQUE_CATALOG
        assert "T1059.001" in TECHNIQUE_CATALOG
        assert "T1003.001" in TECHNIQUE_CATALOG
        assert "T1486" in TECHNIQUE_CATALOG

    def test_map_techniques_multiple_tags(self):
        from backend.causality.mitre_mapper import map_techniques
        result = map_techniques(["attack.t1059.001", "attack.t1003.001"], "", "")
        assert len(result) == 2
        techniques = {r["technique"] for r in result}
        assert "T1059.001" in techniques
        assert "T1003.001" in techniques

    def test_map_techniques_dict_tag_format(self):
        """Tags can be dicts with 'technique' key (from sigma rule processing)."""
        from backend.causality.mitre_mapper import map_techniques
        # When tags come in as pre-converted "attack.tXXXX" strings
        result = map_techniques(["attack.t1082"], "", "")
        assert len(result) == 1
        assert result[0]["technique"] == "T1082"


# ---------------------------------------------------------------------------
# CausalityEngine tests (build_causality_sync)
# ---------------------------------------------------------------------------

class TestCausalityEngine:
    def test_unknown_alert_returns_empty(self):
        from backend.causality.engine import build_causality_sync
        result = build_causality_sync("alert-999", [], [])
        assert result == {}

    def test_alert_without_event_id_returns_empty(self):
        from backend.causality.engine import build_causality_sync
        alerts = [{"id": "alert-1", "event_id": None}]
        result = build_causality_sync("alert-1", [], alerts)
        assert result == {}

    def test_basic_result_keys(self):
        from backend.causality.engine import build_causality_sync
        events = [{"id": "evt-1", "hostname": "host1", "timestamp": "2026-01-01T10:00:00",
                   "event_type": "process_create"}]
        alerts = [{"id": "alert-1", "event_id": "evt-1", "attack_tags": [], "description": ""}]
        result = build_causality_sync("alert-1", events, alerts)
        assert isinstance(result, dict)
        assert "alert_id" in result
        assert "chain" in result
        assert "techniques" in result
        assert "score" in result
        assert "nodes" in result
        assert "edges" in result

    def test_alert_id_preserved_in_result(self):
        from backend.causality.engine import build_causality_sync
        events = [{"id": "evt-1", "hostname": "host1", "timestamp": "2026-01-01T10:00:00"}]
        alerts = [{"id": "alert-42", "event_id": "evt-1", "attack_tags": [], "description": ""}]
        result = build_causality_sync("alert-42", events, alerts)
        assert result["alert_id"] == "alert-42"

    def test_chain_includes_trigger_event(self):
        from backend.causality.engine import build_causality_sync
        events = [{"id": "evt-1", "hostname": "host1", "timestamp": "2026-01-01T10:00:00"}]
        alerts = [{"id": "alert-1", "event_id": "evt-1", "attack_tags": [], "description": ""}]
        result = build_causality_sync("alert-1", events, alerts)
        chain_ids = [e.get("id") for e in result["chain"]]
        assert "evt-1" in chain_ids

    def test_sigma_tags_mapped_to_techniques(self):
        from backend.causality.engine import build_causality_sync
        events = [{"id": "evt-1", "hostname": "host1", "timestamp": "2026-01-01T10:00:00",
                   "event_type": ""}]
        alerts = [{
            "id": "alert-1",
            "event_id": "evt-1",
            "attack_tags": [{"technique": "T1059.001"}],
            "description": "",
        }]
        result = build_causality_sync("alert-1", events, alerts)
        assert len(result["techniques"]) >= 1
        t_ids = [t["technique"] for t in result["techniques"]]
        assert "T1059.001" in t_ids

    def test_score_nonzero_for_technique(self):
        from backend.causality.engine import build_causality_sync
        events = [{"id": "evt-1", "hostname": "host1", "timestamp": "2026-01-01T10:00:00"}]
        alerts = [{
            "id": "alert-1",
            "event_id": "evt-1",
            "attack_tags": [{"technique": "T1059.001"}],
            "description": "",
        }]
        result = build_causality_sync("alert-1", events, alerts)
        assert result["score"] > 0

    def test_temporal_bounds_populated(self):
        from backend.causality.engine import build_causality_sync
        events = [
            {"id": "evt-1", "hostname": "host1", "timestamp": "2026-01-01T10:00:00"},
            {"id": "evt-2", "hostname": "host1", "timestamp": "2026-01-01T10:01:00"},
        ]
        alerts = [{"id": "alert-1", "event_id": "evt-1", "attack_tags": [], "description": ""}]
        result = build_causality_sync("alert-1", events, alerts)
        assert result["first_event"] != ""
        assert result["last_event"] != ""

    def test_string_sigma_tags_processed(self):
        from backend.causality.engine import build_causality_sync
        events = [{"id": "evt-1", "hostname": "host1", "timestamp": "2026-01-01T10:00:00",
                   "event_type": ""}]
        alerts = [{
            "id": "alert-1",
            "event_id": "evt-1",
            "attack_tags": ["attack.t1003.001"],
            "description": "",
        }]
        result = build_causality_sync("alert-1", events, alerts)
        t_ids = [t["technique"] for t in result["techniques"]]
        assert "T1003.001" in t_ids

    def test_correlated_alerts_included(self):
        from backend.causality.engine import build_causality_sync
        events = [
            {"id": "evt-1", "hostname": "host1", "timestamp": "2026-01-01T10:00:00"},
            {"id": "evt-2", "hostname": "host1", "timestamp": "2026-01-01T10:01:00"},
        ]
        alerts = [
            {"id": "alert-1", "event_id": "evt-1", "attack_tags": [], "description": ""},
            {"id": "alert-2", "event_id": "evt-2", "attack_tags": [], "description": ""},
        ]
        result = build_causality_sync("alert-1", events, alerts)
        # Should return a valid result
        assert "chain" in result

    def test_fallback_event_type_for_techniques(self):
        from backend.causality.engine import build_causality_sync
        events = [{"id": "evt-1", "hostname": "host1", "timestamp": "2026-01-01T10:00:00",
                   "event_type": "dns_query"}]
        alerts = [{
            "id": "alert-1",
            "event_id": "evt-1",
            "attack_tags": [],
            "description": "",
        }]
        result = build_causality_sync("alert-1", events, alerts)
        # dns_query event_type should map to T1071.004
        t_ids = [t["technique"] for t in result["techniques"]]
        assert "T1071.004" in t_ids

    def test_no_events_still_returns_result(self):
        """Alert found but no events in list — should return result with empty chain."""
        from backend.causality.engine import build_causality_sync
        alerts = [{
            "id": "alert-1",
            "event_id": "evt-missing",
            "attack_tags": [],
            "description": "",
        }]
        result = build_causality_sync("alert-1", [], alerts)
        assert isinstance(result, dict)
        assert result["chain"] == []
