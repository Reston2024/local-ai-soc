"""MITRE ATT&CK technique/tactic mapping — Phase 6."""

TECHNIQUE_CATALOG: dict[str, dict] = {
    # Initial Access (TA0001)
    "T1566.001": {"tactic": "Initial Access", "name": "Spearphishing Attachment"},
    "T1566.002": {"tactic": "Initial Access", "name": "Spearphishing Link"},
    "T1190": {"tactic": "Initial Access", "name": "Exploit Public-Facing Application"},
    # Execution (TA0002)
    "T1059.001": {"tactic": "Execution", "name": "PowerShell"},
    "T1059.003": {"tactic": "Execution", "name": "Windows Command Shell"},
    "T1204.002": {"tactic": "Execution", "name": "Malicious File"},
    # Persistence (TA0003)
    "T1547.001": {"tactic": "Persistence", "name": "Registry Run Keys"},
    "T1053.005": {"tactic": "Persistence", "name": "Scheduled Task"},
    # Privilege Escalation (TA0004)
    "T1055": {"tactic": "Privilege Escalation", "name": "Process Injection"},
    "T1068": {"tactic": "Privilege Escalation", "name": "Exploitation for Privilege Escalation"},
    # Defense Evasion (TA0005)
    "T1078": {"tactic": "Defense Evasion", "name": "Valid Accounts"},
    "T1562.001": {"tactic": "Defense Evasion", "name": "Disable or Modify Tools"},
    "T1070.004": {"tactic": "Defense Evasion", "name": "File Deletion"},
    # Credential Access (TA0006)
    "T1003.001": {"tactic": "Credential Access", "name": "LSASS Memory"},
    "T1110.001": {"tactic": "Credential Access", "name": "Password Guessing"},
    # Discovery (TA0007)
    "T1082": {"tactic": "Discovery", "name": "System Information Discovery"},
    "T1046": {"tactic": "Discovery", "name": "Network Service Discovery"},
    # Lateral Movement (TA0008)
    "T1021.001": {"tactic": "Lateral Movement", "name": "Remote Desktop Protocol"},
    "T1021.002": {"tactic": "Lateral Movement", "name": "SMB/Windows Admin Shares"},
    # Collection (TA0009)
    "T1005": {"tactic": "Collection", "name": "Data from Local System"},
    "T1074.001": {"tactic": "Collection", "name": "Local Data Staging"},
    # Command and Control (TA0011)
    "T1071.001": {"tactic": "Command and Control", "name": "Web Protocols"},
    "T1071.004": {"tactic": "Command and Control", "name": "DNS"},
    "T1095": {"tactic": "Command and Control", "name": "Non-Application Layer Protocol"},
    # Exfiltration (TA0010)
    "T1048": {"tactic": "Exfiltration", "name": "Exfiltration Over Alternative Protocol"},
    # Impact (TA0040)
    "T1486": {"tactic": "Impact", "name": "Data Encrypted for Impact"},
}

_FALLBACK_MAP: dict[str, str] = {
    "dns_query": "T1071.004",
    "dns request": "T1071.004",
    "potentially bad traffic": "T1048",
    "network trojan": "T1095",
    "malware command and control activity detected": "T1095",
}


def map_techniques(sigma_tags: list, event_type: str, alert_category: str) -> list[dict]:
    """Parse Sigma attack.tXXXX tags and return list of {technique, tactic, name} dicts.

    Falls back to event_type/category lookup if no Sigma tags match.
    Returns [] if no match — never raises.
    """
    results = []
    for tag in sigma_tags:
        tag_lower = str(tag).lower().strip()
        if tag_lower.startswith("attack.t"):
            # "attack.t1059.001" -> "T1059.001"
            tid = "T" + tag_lower[8:].upper()
            entry = TECHNIQUE_CATALOG.get(tid)
            if entry:
                results.append({"technique": tid, **entry})
    if results:
        return results
    # Fallback: check event_type and category
    for key in [str(event_type).lower(), str(alert_category).lower()]:
        tid = _FALLBACK_MAP.get(key)
        if tid and tid in TECHNIQUE_CATALOG:
            return [{"technique": tid, **TECHNIQUE_CATALOG[tid]}]
    return []
