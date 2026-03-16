"""Attack chain severity scoring — Phase 6."""

_SEVERITY_POINTS: dict[str, int] = {
    "critical": 40,
    "high": 30,
    "medium": 20,
    "low": 10,
}


def score_chain(
    chain_events: list,
    chain_alerts: list,
    techniques: list,
) -> int:
    """Additive 0-100 score for an attack chain.

    Components:
    - Max alert severity (0-40 pts): reflects the worst threat observed
    - MITRE technique count (0-20 pts): 5 pts per unique technique, max 4 techniques
    - Chain length (0-20 pts): 2 pts per event, max 10 events
    - Recurrence (0-20 pts): +20 if any entity appears in 3+ events
    """
    score = 0

    # Component 1: Max alert severity in chain (up to 40 pts)
    max_severity_pts = 0
    for alert in chain_alerts:
        sev = ""
        if isinstance(alert, dict):
            sev = alert.get("severity", "")
        else:
            sev = getattr(alert, "severity", "")
        pts = _SEVERITY_POINTS.get(str(sev).lower(), 0)
        if pts > max_severity_pts:
            max_severity_pts = pts
    score += max_severity_pts

    # Component 2: MITRE technique count (up to 20 pts, 5 pts per technique)
    seen_techniques: set[str] = set()
    for t in techniques:
        if isinstance(t, dict):
            tid = t.get("technique", "")
        else:
            tid = str(t)
        if tid:
            seen_techniques.add(tid)
    score += min(len(seen_techniques) * 5, 20)

    # Component 3: Chain length (up to 20 pts, 2 pts per event)
    score += min(len(chain_events) * 2, 20)

    # Component 4: Recurrence — same entity in 3+ events (+20 pts)
    entity_counts: dict[str, int] = {}
    for ev in chain_events:
        if not isinstance(ev, dict):
            continue
        for field in ("host", "user", "process", "src_ip", "dst_ip"):
            val = ev.get(field)
            if val:
                entity_counts[str(val)] = entity_counts.get(str(val), 0) + 1
    if any(v >= 3 for v in entity_counts.values()):
        score += 20

    return min(score, 100)
