"""Stubs for P20-T01: ECS-aligned NormalizedEvent model."""
import pytest
from backend.models.event import NormalizedEvent


def test_ecs_new_fields_present():
    """NormalizedEvent must accept ocsf_class_uid, event_outcome, user_domain,
    process_executable, network_protocol, network_direction."""
    pytest.fail("NOT IMPLEMENTED")


def test_ecs_new_fields_optional_default_none():
    """All six new ECS fields must default to None — existing callers not broken."""
    pytest.fail("NOT IMPLEMENTED")


def test_ocsf_class_uid_process_create():
    """event_type='process_create' must map to ocsf_class_uid=1007 via OCSF_CLASS_UID_MAP."""
    pytest.fail("NOT IMPLEMENTED")


def test_ocsf_class_uid_network_connect():
    """event_type='network_connect' must map to ocsf_class_uid=4001."""
    pytest.fail("NOT IMPLEMENTED")


def test_ocsf_class_uid_logon():
    """event_type='logon_success' must map to ocsf_class_uid=3002."""
    pytest.fail("NOT IMPLEMENTED")


def test_ocsf_class_uid_dns_query():
    """event_type='dns_query' must map to ocsf_class_uid=4003."""
    pytest.fail("NOT IMPLEMENTED")


def test_backward_compat_existing_fields():
    """Legacy fields (hostname, username, process_name, etc.) must still work unchanged."""
    pytest.fail("NOT IMPLEMENTED")


def test_to_duckdb_row_includes_new_fields():
    """to_duckdb_row() must return a tuple that includes the 6 new ECS columns at the end."""
    pytest.fail("NOT IMPLEMENTED")
