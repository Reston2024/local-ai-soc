"""ATT&CK-style static tag mapper — Phase 5.

map_attack_tags: static lookup returning list of {tactic, technique} dicts.
Returns [] (empty list) for unmapped events. No guessing.

This is a simplified mapping table (5 entries) — not full ATT&CK coverage.
Full coverage is explicitly deferred to a future phase.

Lookup order:
  1. alert.raw.get("category") → _CATEGORY_MAP
  2. event.event_type           → _EVENT_TYPE_MAP
  3. alert.rule                 → _RULE_MAP
  4. event.source + alert.severity → _SOURCE_SEVERITY_MAP

First match wins. Returns [] if none match.
"""

# Category-based mapping (alert.raw["category"] normalised to lowercase+strip)
_CATEGORY_MAP: dict[str, dict] = {
    "dns request": {"tactic": "Command and Control", "technique": "T1071.004"},
    "potentially bad traffic": {"tactic": "Exfiltration", "technique": "T1048"},
    "network trojan": {"tactic": "Command and Control", "technique": "T1095"},
    "malware command and control activity detected": {
        "tactic": "Command and Control",
        "technique": "T1095",
    },
}

# Event-type-based mapping (event.event_type)
_EVENT_TYPE_MAP: dict[str, dict] = {
    "dns_query": {"tactic": "Command and Control", "technique": "T1071.004"},
}

# Rule-based mapping (alert.rule)
_RULE_MAP: dict[str, dict] = {
    "suspicious_dns_query": {"tactic": "Command and Control", "technique": "T1071.004"},
}

# Source+severity-based mapping
# Key: (source_value, severity)
_SOURCE_SEVERITY_MAP: dict[tuple, dict] = {
    ("syslog", "critical"): {"tactic": "Impact", "technique": "T1499"},
    ("syslog", "high"): {"tactic": "Impact", "technique": "T1499"},
}


def map_attack_tags(alert, event) -> list[dict]:
    """Map alert + event to a list of ATT&CK tactic/technique tags.

    Returns a list with at most one entry (first match wins). Returns []
    when no static mapping matches.

    Parameters
    ----------
    alert:
        Alert instance with .rule, .severity, and .raw attributes.
    event:
        NormalizedEvent instance with .event_type and .source attributes.
    """
    # 1. Category lookup (from alert raw data)
    raw = getattr(alert, "raw", {}) or {}
    category = str(raw.get("category", "")).lower().strip()
    if category and category in _CATEGORY_MAP:
        return [_CATEGORY_MAP[category]]

    # 2. Event-type lookup
    event_type = getattr(event, "event_type", "") or ""
    if event_type in _EVENT_TYPE_MAP:
        return [_EVENT_TYPE_MAP[event_type]]

    # 3. Rule lookup
    rule = getattr(alert, "rule", "") or ""
    if rule in _RULE_MAP:
        return [_RULE_MAP[rule]]

    # 4. Source + severity lookup
    source = getattr(event, "source", None)
    source_val = source.value if hasattr(source, "value") else str(source)
    severity = (getattr(alert, "severity", "") or "").lower()
    key = (source_val, severity)
    if key in _SOURCE_SEVERITY_MAP:
        return [_SOURCE_SEVERITY_MAP[key]]

    return []
