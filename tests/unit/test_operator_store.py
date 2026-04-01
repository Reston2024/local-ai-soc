"""
Tests for Phase 19-01: operators DDL, bcrypt utils, OperatorContext, and Pydantic models.

TestOperatorDDL  — SQLiteStore schema has operators table + indexes
TestBcrypt       — hash_api_key / verify_api_key correctness
TestBootstrap    — bootstrap_admin_if_empty idempotency
TestOperatorContext — OperatorContext dataclass defaults
"""
import pytest

from backend.stores.sqlite_store import SQLiteStore
from backend.core.operator_utils import hash_api_key, verify_api_key, generate_api_key, key_prefix
from backend.core.rbac import OperatorContext


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _memory_store() -> SQLiteStore:
    """Return an in-memory SQLiteStore for isolated tests."""
    return SQLiteStore(":memory:")


# ---------------------------------------------------------------------------
# TestOperatorDDL
# ---------------------------------------------------------------------------

class TestOperatorDDL:
    def test_operators_table_exists(self):
        """Opens in-memory SQLiteStore; asserts 'operators' in table list."""
        store = _memory_store()
        row = store._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='operators'"
        ).fetchone()
        assert row is not None, "operators table should exist"

    def test_key_prefix_index_exists(self):
        store = _memory_store()
        row = store._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_operators_key_prefix'"
        ).fetchone()
        assert row is not None, "idx_operators_key_prefix index should exist"


# ---------------------------------------------------------------------------
# TestBcrypt
# ---------------------------------------------------------------------------

class TestBcrypt:
    def test_hash_produces_bcrypt(self):
        """hash_api_key returns string starting with '$2b$'."""
        hashed = hash_api_key("abc")
        assert hashed.startswith("$2b$"), "bcrypt hashes must start with $2b$"

    def test_verify_correct_key(self):
        raw = "correct-key-12345"
        hashed = hash_api_key(raw)
        assert verify_api_key(raw, hashed) is True

    def test_verify_wrong_key_returns_false(self):
        hashed = hash_api_key("right")
        assert verify_api_key("wrong", hashed) is False


# ---------------------------------------------------------------------------
# TestBootstrap
# ---------------------------------------------------------------------------

class TestBootstrap:
    def test_inserts_admin_when_empty(self):
        store = _memory_store()
        store.bootstrap_admin_if_empty("mytoken")
        count = store._conn.execute("SELECT COUNT(*) FROM operators").fetchone()[0]
        assert count == 1, "should have inserted exactly one admin operator"

    def test_noop_when_operators_exist(self):
        store = _memory_store()
        store.bootstrap_admin_if_empty("mytoken")
        store.bootstrap_admin_if_empty("mytoken")  # call twice
        count = store._conn.execute("SELECT COUNT(*) FROM operators").fetchone()[0]
        assert count == 1, "second call should be a no-op — still exactly one operator"


# ---------------------------------------------------------------------------
# TestOperatorContext (basic dataclass sanity)
# ---------------------------------------------------------------------------

class TestOperatorContext:
    def test_defaults(self):
        ctx = OperatorContext(operator_id="x", username="alice", role="analyst")
        assert ctx.totp_verified is True
        assert ctx.totp_enabled is False

    def test_fields(self):
        ctx = OperatorContext(operator_id="op-1", username="bob", role="admin")
        assert ctx.operator_id == "op-1"
        assert ctx.username == "bob"
        assert ctx.role == "admin"
