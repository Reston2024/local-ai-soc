"""Stubs for P20-T03: DuckDB additive schema migration."""
import pytest


def test_db_meta_table_created():
    """initialise_schema() must create db_meta table with schema_version key."""
    pytest.fail("NOT IMPLEMENTED")


def test_new_ecs_columns_added():
    """After migration, normalized_events must have columns:
    ocsf_class_uid, event_outcome, user_domain, process_executable,
    network_protocol, network_direction."""
    pytest.fail("NOT IMPLEMENTED")


def test_migration_idempotent():
    """Running initialise_schema() twice must not raise (ALTER TABLE re-run safe)."""
    pytest.fail("NOT IMPLEMENTED")


def test_existing_rows_not_broken():
    """Existing rows retain their values; new columns default to NULL."""
    pytest.fail("NOT IMPLEMENTED")


def test_schema_version_value():
    """db_meta table must contain key='schema_version' with value='20'."""
    pytest.fail("NOT IMPLEMENTED")
