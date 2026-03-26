"""Risk scoring engine for entities and detections.

Additive 0-100 integer scoring pattern mirroring backend/causality/scoring.py.
Pure functions — no I/O, no database access.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# MITRE ATT&CK technique weights
# ---------------------------------------------------------------------------

MITRE_WEIGHTS: dict[str, int] = {
    # Critical techniques — 40 pts
    "T1003.001": 40,  # OS Credential Dumping: LSASS Memory
    "T1071.001": 40,  # Application Layer Protocol: Web Protocols (C2)
    # High techniques — 30 pts
    "T1547.001": 30,  # Boot or Logon Autostart: Registry Run Keys
    "T1059.001": 30,  # Command and Scripting Interpreter: PowerShell
    "T1055": 30,       # Process Injection
    # Medium techniques — 20 pts
    "T1033": 20,       # System Owner/User Discovery
    "T1087.002": 20,  # Account Discovery: Domain Account
    "T1083": 20,       # File and Directory Discovery
    # Low techniques — 10 pts
    "T1057": 10,       # Process Discovery
    "T1012": 10,       # Query Registry
}

# ---------------------------------------------------------------------------
# Severity base points
# ---------------------------------------------------------------------------

SEVERITY_BASE: dict[str, int] = {
    "critical": 40,
    "high": 30,
    "medium": 20,
    "low": 10,
    "info": 5,
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def score_detection(
    severity: str,
    technique_id: str | None,
    anomaly_count: int,
) -> int:
    """Score a single detection alert.

    Components:
      - SEVERITY_BASE[severity]       (0-40)
      - MITRE_WEIGHTS[technique_id]   (0-40)
      - min(anomaly_count * 10, 20)   (0-20)

    Returns an integer capped at 100.
    """
    base = SEVERITY_BASE.get(severity, 0)
    mitre = MITRE_WEIGHTS.get(technique_id or "", 0)
    anomaly = min(anomaly_count * 10, 20)
    return min(base + mitre + anomaly, 100)


def score_entity(
    entity_id: str,
    events: list[dict],
    detections: list[dict],
    anomaly_flags: list[str],
) -> int:
    """Score an entity (process, IP, user, etc.) based on associated data.

    Components:
      - Component 1 (0-40): max MITRE weight across all events' attack_technique
      - Component 2 (0-30): max severity base across all events
      - Component 3 (0-20): min(len(anomaly_flags) * 10, 20)
      - Component 4 (0-10): min(len(detections) * 5, 10)

    Returns an integer capped at 100.
    """
    # Component 1: highest MITRE technique weight seen across events
    mitre_score = 0
    for evt in events:
        tech = evt.get("attack_technique") or ""
        mitre_score = max(mitre_score, MITRE_WEIGHTS.get(tech, 0))

    # Component 2: highest severity base seen across events
    sev_score = 0
    for evt in events:
        sev = (evt.get("severity") or "").lower()
        sev_score = max(sev_score, SEVERITY_BASE.get(sev, 0))
    sev_score = min(sev_score, 30)  # cap component at 30

    # Component 3: anomaly flags
    anomaly_score = min(len(anomaly_flags) * 10, 20)

    # Component 4: detection count
    detection_score = min(len(detections) * 5, 10)

    return min(mitre_score + sev_score + anomaly_score + detection_score, 100)


def enrich_nodes_with_risk_score(
    nodes: list[dict],
    scored_entities: dict[str, int],
) -> list[dict]:
    """Add risk_score field to Cytoscape node data dicts.

    Mutates nodes in place and returns the same list.
    Nodes whose id is not in scored_entities receive risk_score=0.
    """
    for node in nodes:
        node_id = node["data"]["id"]
        node["data"]["risk_score"] = scored_entities.get(node_id, 0)
    return nodes
