"""
Unit tests for built-in CISA IR playbooks and seed_builtin_playbooks().

Updated in Phase 38: NIST starters replaced with CISA playbooks.
Updated in Phase 39: Expanded from 4 to 19 CISA playbooks.
Updated in Phase 46: Expanded to 30 playbooks (added SOC reference library).
"""

import pytest

from backend.data.builtin_playbooks import BUILTIN_PLAYBOOKS
from backend.stores.sqlite_store import SQLiteStore

# Total CISA playbooks in the library (update when adding new ones)
_EXPECTED_PLAYBOOK_COUNT = 30

@pytest.fixture()
def store(tmp_path):
    return SQLiteStore(data_dir=str(tmp_path))


class TestBuiltinPlaybooksData:
    def test_exactly_four_playbooks(self):
        assert len(BUILTIN_PLAYBOOKS) == _EXPECTED_PLAYBOOK_COUNT

    def test_all_marked_as_builtin(self):
        for pb in BUILTIN_PLAYBOOKS:
            assert pb["is_builtin"] is True, f"{pb['name']} missing is_builtin=True"

    def test_all_have_source(self):
        """All playbooks must have a non-empty source field. Sources expanded in
        Phase 46 beyond 'cisa' to include aws, cert_sg, community, guardsight, microsoft.
        """
        _VALID_SOURCES = {"cisa", "aws", "cert_sg", "community", "guardsight", "microsoft"}
        for pb in BUILTIN_PLAYBOOKS:
            src = pb.get("source")
            assert src in _VALID_SOURCES, (
                f"{pb['name']} has invalid source={src!r} (expected one of {_VALID_SOURCES})"
            )

    def test_all_have_required_fields(self):
        required = {"name", "description", "trigger_conditions", "steps", "version"}
        for pb in BUILTIN_PLAYBOOKS:
            missing = required - set(pb.keys())
            assert not missing, f"{pb['name']} missing fields: {missing}"

    def test_all_have_steps(self):
        """All playbooks must have at least 4 steps. CISA playbooks have >= 6;
        community/cert_sg/aws/guardsight/microsoft playbooks may have 4-5.
        """
        for pb in BUILTIN_PLAYBOOKS:
            assert len(pb["steps"]) >= 4, (
                f"{pb['name']} has only {len(pb['steps'])} steps (expected >= 4)"
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
        # Core original 4 (Phase 38) — always present
        core_expected = {
            "Phishing / BEC Response",
            "Ransomware Response",
            "Credential / Account Compromise Response",
            "Malware / Intrusion Response",
        }
        assert core_expected.issubset(names), (
            f"Core playbooks missing: {core_expected - names}"
        )
        # Phase 39 expanded set — 19 total
        assert len(names) == _EXPECTED_PLAYBOOK_COUNT

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
        assert len(builtin) == _EXPECTED_PLAYBOOK_COUNT

    def test_seed_is_idempotent(self, store):
        import asyncio
        from backend.api.playbooks import seed_builtin_playbooks

        # Seed twice — should not create duplicates
        asyncio.run(seed_builtin_playbooks(store))
        asyncio.run(seed_builtin_playbooks(store))

        playbooks = store.get_playbooks()
        builtin = [pb for pb in playbooks if pb["is_builtin"]]
        assert len(builtin) == _EXPECTED_PLAYBOOK_COUNT  # not doubled

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

    def test_seeded_playbooks_have_valid_source(self, store):
        """Seeded playbooks must have a valid source. Phase 46 expanded sources
        beyond 'cisa' to include aws, cert_sg, community, guardsight, microsoft.
        """
        import asyncio
        from backend.api.playbooks import seed_builtin_playbooks

        _VALID_SOURCES = {"cisa", "aws", "cert_sg", "community", "guardsight", "microsoft"}
        asyncio.run(seed_builtin_playbooks(store))
        playbooks = store.get_playbooks()
        builtin = [pb for pb in playbooks if pb["is_builtin"]]
        for pb in builtin:
            src = pb.get("source")
            assert src in _VALID_SOURCES, (
                f"{pb['name']} has invalid source={src!r}"
            )
