"""ATT&CK-style static tag mapper — Phase 5.

map_attack_tags: static lookup returning list of {tactic, technique} dicts.
Returns [] (empty list) for unmapped events. No guessing.

This is a simplified mapping table (5 entries) — not full ATT&CK coverage.
Full coverage is explicitly deferred to a future phase.
"""


def map_attack_tags(alert, event) -> list[dict]:
    """Map alert + event to ATT&CK tactic/technique labels.

    Not yet implemented — raises NotImplementedError until Plan 02.
    """
    raise NotImplementedError("map_attack_tags not implemented — see Plan 02")
