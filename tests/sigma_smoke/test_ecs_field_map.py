"""Smoke tests for ECS field name additions to SIGMA_FIELD_MAP (Phase 20)."""
from detections.field_map import SIGMA_FIELD_MAP, INTEGER_COLUMNS


def test_ecs_process_fields():
    assert SIGMA_FIELD_MAP["process.name"] == "process_name"
    assert SIGMA_FIELD_MAP["process.pid"] == "process_id"
    assert SIGMA_FIELD_MAP["process.command_line"] == "command_line"
    assert SIGMA_FIELD_MAP["process.executable"] == "process_executable"
    assert SIGMA_FIELD_MAP["process.parent.name"] == "parent_process_name"
    assert SIGMA_FIELD_MAP["process.parent.pid"] == "parent_process_id"


def test_ecs_user_fields():
    assert SIGMA_FIELD_MAP["user.name"] == "username"
    assert SIGMA_FIELD_MAP["user.domain"] == "user_domain"


def test_ecs_network_fields():
    assert SIGMA_FIELD_MAP["source.ip"] == "src_ip"
    assert SIGMA_FIELD_MAP["destination.ip"] == "dst_ip"
    assert SIGMA_FIELD_MAP["network.protocol"] == "network_protocol"
    assert SIGMA_FIELD_MAP["dns.question.name"] == "domain"


def test_ecs_file_fields():
    assert SIGMA_FIELD_MAP["file.path"] == "file_path"
    assert SIGMA_FIELD_MAP["file.hash.sha256"] == "file_hash_sha256"


def test_windows_domain_fields():
    assert SIGMA_FIELD_MAP["SubjectDomainName"] == "user_domain"
    assert SIGMA_FIELD_MAP["TargetDomainName"] == "user_domain"
    assert SIGMA_FIELD_MAP["DomainName"] == "user_domain"
    assert SIGMA_FIELD_MAP["EventOutcome"] == "event_outcome"


def test_original_entries_unchanged():
    """Regression: no existing entry must be altered."""
    assert SIGMA_FIELD_MAP["Image"] == "process_name"
    assert SIGMA_FIELD_MAP["CommandLine"] == "command_line"
    assert SIGMA_FIELD_MAP["User"] == "username"
    assert SIGMA_FIELD_MAP["Computer"] == "hostname"
    assert SIGMA_FIELD_MAP["DestinationIp"] == "dst_ip"


def test_new_text_columns_not_in_integer_columns():
    """New ECS columns are TEXT — must not appear in INTEGER_COLUMNS."""
    for col in ("network_protocol", "event_outcome", "user_domain",
                "process_executable", "network_direction"):
        assert col not in INTEGER_COLUMNS, f"{col} must not be in INTEGER_COLUMNS"
