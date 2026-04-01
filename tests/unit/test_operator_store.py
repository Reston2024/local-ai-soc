import pytest


class TestOperatorDDL:
    def test_operators_table_exists(self):
        """Opens in-memory SQLiteStore; asserts 'operators' in table list."""
        pytest.fail("NOT IMPLEMENTED")

    def test_key_prefix_index_exists(self):
        pytest.fail("NOT IMPLEMENTED")


class TestBcrypt:
    def test_hash_produces_bcrypt(self):
        """hash_api_key returns string starting with '$2b$'."""
        pytest.fail("NOT IMPLEMENTED")

    def test_verify_correct_key(self):
        pytest.fail("NOT IMPLEMENTED")

    def test_verify_wrong_key_returns_false(self):
        pytest.fail("NOT IMPLEMENTED")


class TestBootstrap:
    def test_inserts_admin_when_empty(self):
        pytest.fail("NOT IMPLEMENTED")

    def test_noop_when_operators_exist(self):
        pytest.fail("NOT IMPLEMENTED")
