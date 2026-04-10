"""Unit tests for Zeek / ECS field entries in SIGMA_FIELD_MAP (Wave 0 stubs — 35-01)."""
from __future__ import annotations

import pytest

from detections.field_map import SIGMA_FIELD_MAP


@pytest.mark.parametrize("sigma_field,expected_column", [
    ("dns.query.name",   "dns_query"),
    ("http.user_agent",  "http_user_agent"),
    ("tls.client.ja3",   "tls_ja3"),
])
def test_zeek_ecs_fields_in_sigma_field_map(sigma_field: str, expected_column: str):
    """SIGMA_FIELD_MAP must map Zeek/ECS dotted field names to the correct DuckDB columns."""
    assert sigma_field in SIGMA_FIELD_MAP, (
        f"Missing entry: SIGMA_FIELD_MAP['{sigma_field}'] not found"
    )
    assert SIGMA_FIELD_MAP[sigma_field] == expected_column, (
        f"Expected SIGMA_FIELD_MAP['{sigma_field}'] == '{expected_column}', "
        f"got '{SIGMA_FIELD_MAP[sigma_field]}'"
    )
