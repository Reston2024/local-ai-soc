"""Unit tests for ingestion.field_mapper.FieldMapper — P20-T02."""


def test_field_mapper_importable():
    """ingestion.field_mapper.FieldMapper must be importable."""
    from ingestion.field_mapper import FieldMapper
    assert callable(FieldMapper)


def test_map_evtx_fields():
    """EVTX-style PascalCase keys are NOT in _FIELD_VARIANTS; they pass through unchanged."""
    from ingestion.field_mapper import FieldMapper
    raw = {"Image": "cmd.exe", "CommandLine": "cmd /c", "ProcessId": 1234}
    result = FieldMapper().map(raw)
    assert result == {"Image": "cmd.exe", "CommandLine": "cmd /c", "ProcessId": 1234}


def test_map_ecs_dotted_fields():
    """ECS dotted keys (process.name, user.name, host.hostname) map correctly."""
    from ingestion.field_mapper import FieldMapper
    raw = {"process.name": "cmd.exe", "user.name": "SYSTEM", "host.hostname": "WS01"}
    result = FieldMapper().map(raw)
    assert result == {"process_name": "cmd.exe", "username": "SYSTEM", "hostname": "WS01"}


def test_map_network_fields():
    """Network keys (source.ip, destination.ip, network.protocol) map to DuckDB columns."""
    from ingestion.field_mapper import FieldMapper
    raw = {"source.ip": "10.0.0.1", "destination.ip": "8.8.8.8", "network.protocol": "dns"}
    result = FieldMapper().map(raw)
    assert result == {"src_ip": "10.0.0.1", "dst_ip": "8.8.8.8", "network_protocol": "dns"}


def test_map_unknown_fields_passthrough():
    """Unknown keys are passed through unchanged (not dropped)."""
    from ingestion.field_mapper import FieldMapper
    raw = {"custom_field": "value", "another": 42}
    result = FieldMapper().map(raw)
    assert result == {"custom_field": "value", "another": 42}


def test_map_new_ecs_fields():
    """New ECS fields map correctly: process.executable, user.domain, event.outcome."""
    from ingestion.field_mapper import FieldMapper
    raw = {
        "process.executable": "/bin/sh",
        "user.domain": "CORP",
        "event.outcome": "success",
    }
    result = FieldMapper().map(raw)
    assert result == {
        "process_executable": "/bin/sh",
        "user_domain": "CORP",
        "event_outcome": "success",
    }
