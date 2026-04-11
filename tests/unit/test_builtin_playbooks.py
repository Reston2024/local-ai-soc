"""
Unit tests for built-in CISA IR playbooks and seed_builtin_playbooks().

Updated in Phase 38: NIST starters replaced with 4 CISA playbooks.
"""

import pytest

from backend.data.builtin_playbooks import BUILTIN_PLAYBOOKS
from backend.stores.sqlite_store import SQLiteStore


@pytest.fixture()
def store(tmp_path):
    return SQLiteStore(data_dir=str(tmp_path))


class TestBuiltinPlaybooksData:
    def test_exactly_four_playbooks(self):
        assert len(BUILTIN_PLAYBOOKS) == 4

    def test_all_marked_as_builtin(self):
        for pb in BUILTIN_PLAYBOOKS:
            assert pb["is_builtin"] is True, f"{pb['name']} missing is_builtin=True"

    def test_all_have_source_cisa(self):
        for pb in BUILTIN_PLAYBOOKS:
            assert pb.get("source") == "cisa", f"{pb['name']} missing source=cisa"

    def test_all_have_required_fields(self):
        required = {"name", "description", "trigger_conditions", "steps", "version"}
        for pb in BUILTIN_PLAYBOOKS:
            missing = required - set(pb.keys())
            assert not missing, f"{pb['name']} missing fields: {missing}"

    def test_all_have_steps(self):
        for pb in BUILTIN_PLAYBOOKS:
            assert len(pb["steps"]) >= 6, (
                f"{pb['name']} has only {len(pb['steps'])} steps (expected >= 6)"
            )

    def test_all_have_trigger_conditions(self):
        for pb in BUILTIN_PLAYBOOKS:
            assert len(pb["trigger_conditions"]) >= 1, (
                f"{pb['name']} has no trigger_conditions"
            )

    def test_steps_have_required_fields(self):
        required = {"step_number", "title", "description", "requires_approval"}
        for pb in BUILTIN_PLAYBOOKS:
            for step in pb["steps"]:
                missing = required - set(step.keys())
                assert not missing, (
                    f"{pb['name']} step {step.get('step_number')} missing: {missing}"
                )

    def test_step_numbers_are_sequential(self):
        for pb in BUILTIN_PLAYBOOKS:
            numbers = [s["step_number"] for s in pb["steps"]]
            assert numbers == list(range(1, len(numbers) + 1)), (
                f"{pb['name']} step numbers not sequential: {numbers}"
            )

    def test_known_playbook_names(self):
        names = {pb["name"] for pb in BUILTIN_PLAYBOOKS}
        expected = {
            "Phishing / BEC Response",
            "Ransomware Response",
            "Credential / Account Compromise Response",
            "Malware / Intrusion Response",
        }
        assert names == expected

    def test_version_is_string(self):
        for pb in BUILTIN_PLAYBOOKS:
            assert isinstance(pb["version"], str)


class TestSeedBuiltinPlaybooks:
    def test_seed_inserts_four_cisa_playbooks(self, store):
        import asyncio
        from backend.api.playbooks import seed_builtin_playbooks

        asyncio.run(seed_builtin_playbooks(store))
        playbooks = store.get_playbooks()
        builtin = [pb for pb in playbooks if pb["is_builtin"]]
        assert len(builtin) == 4

    def test_seed_is_idempotent(self, store):
        import asyncio
        from backend.api.playbooks import seed_builtin_playbooks

        # Seed twice
        asyncio.run(seed_builtin_playbooks(store))
        asyncio.run(seed_builtin_playbooks(store))

        playbooks = store.get_playbooks()
        builtin = [pb for pb in playbooks if pb["is_builtin"]]
        assert len(builtin) == 4  # not 8

    def test_seeded_playbooks_have_correct_names(self, store):
        import asyncio
        from backend.api.playbooks import seed_builtin_playbooks

        asyncio.run(seed_builtin_playbooks(store))
        playbooks = store.get_playbooks()
        names = {pb["name"] for pb in playbooks}
        assert "Phishing / BEC Response" in names
        assert "Ransomware Response" in names

    def test_seeded_playbooks_have_deserialized_steps(self, store):
        import asyncio
        from backend.api.playbooks import seed_builtin_playbooks

        asyncio.run(seed_builtin_playbooks(store))
        playbooks = store.get_playbooks()
        for pb in playbooks:
            assert isinstance(pb["steps"], list)
            assert isinstance(pb["trigger_conditions"], list)

    def test_seeded_playbooks_have_source_cisa(self, store):
        import asyncio
        from backend.api.playbooks import seed_builtin_playbooks

        asyncio.run(seed_builtin_playbooks(store))
        playbooks = store.get_playbooks()
        builtin = [pb for pb in playbooks if pb["is_builtin"]]
        for pb in builtin:
            assert pb.get("source") == "cisa", f"{pb['name']} source is not 'cisa'"
