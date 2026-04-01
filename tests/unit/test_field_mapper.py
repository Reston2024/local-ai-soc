"""Stubs for P20-T02: FieldMapper pure function."""
import pytest


def test_field_mapper_importable():
    """ingestion.field_mapper.FieldMapper must be importable."""
    pytest.fail("NOT IMPLEMENTED")


def test_map_evtx_fields():
    """EVTX-style keys (Image, CommandLine, ProcessId) map to NormalizedEvent field names."""
    pytest.fail("NOT IMPLEMENTED")


def test_map_ecs_dotted_fields():
    """ECS dotted keys (process.name, user.name, host.hostname) map correctly."""
    pytest.fail("NOT IMPLEMENTED")


def test_map_network_fields():
    """Network keys (source.ip, destination.ip, network.protocol) map to DuckDB columns."""
    pytest.fail("NOT IMPLEMENTED")


def test_map_unknown_fields_passthrough():
    """Unknown keys are passed through unchanged (not dropped)."""
    pytest.fail("NOT IMPLEMENTED")


def test_map_new_ecs_fields():
    """New ECS fields (process.executable -> process_executable, user.domain -> user_domain,
    event.outcome -> event_outcome) are mapped."""
    pytest.fail("NOT IMPLEMENTED")
