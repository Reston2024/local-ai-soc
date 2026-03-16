"""Threat scoring model — Phase 5.

score_alert: additive 0-100 model combining:
  + suricata_severity_points (critical=40, high=30, medium=20, low=10)
  + sigma_hit: +20 if alert.rule matches UUID pattern (sigma-sourced alert)
  + recurrence: +10 if same host/IP seen >= 3 times in events list
  + graph_connectivity: +10 if graph_data provided and host/IP has >= 3 edges

Score is capped at 100.

PERFORMANCE NOTE: Do NOT call build_graph() inside score_alert — that is O(n²)
for batch ingestion. Accept graph_data: dict | None = None. When None (default),
skip the graph_connectivity component entirely (contributes +0).
"""
import re

_SEVERITY_POINTS: dict[str, int] = {
    "critical": 40,
    "high": 30,
    "medium": 20,
    "low": 10,
}

# UUID v4 pattern (hex groups: 8-4-4-4-12)
_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def score_alert(alert, events: list[dict], graph_data: dict | None = None) -> int:
    """Compute threat score 0-100 using an additive four-component model.

    Parameters
    ----------
    alert:
        Alert instance with .severity, .rule, and .event_id attributes.
    events:
        List of raw event dicts used to compute recurrence. Each dict should
        contain 'id', 'host', and optionally 'src_ip' keys.
    graph_data:
        Optional pre-built graph dict. When None the graph_connectivity
        component contributes +0 (avoids O(n²) build_graph() call during
        batch ingestion).

    Returns
    -------
    int
        Threat score in range [0, 100].
    """
    score = 0

    # Component 1 — severity points
    severity = getattr(alert, "severity", "info")
    score += _SEVERITY_POINTS.get(severity.lower(), 0)

    # Component 2 — sigma hit (+20 if rule field is a UUID)
    rule = getattr(alert, "rule", "")
    if rule and _UUID_RE.match(rule):
        score += 20

    # Component 3 — recurrence (+10 if same host/IP seen >= 3 times)
    event_id = getattr(alert, "event_id", "")
    alert_event = next(
        (e for e in events if e.get("id") == event_id),
        None,
    )
    if alert_event is not None:
        alert_host = alert_event.get("host")
        alert_src_ip = alert_event.get("src_ip")
        count = sum(
            1
            for e in events
            if (alert_host and e.get("host") == alert_host)
            or (alert_src_ip and e.get("src_ip") == alert_src_ip)
        )
        if count >= 3:
            score += 10

    # Component 4 — graph connectivity (+10 if >= 3 edges for host/IP)
    # Only computed when graph_data is explicitly provided.
    if graph_data is not None:
        alert_host = alert_host if alert_event is not None else None
        alert_src_ip = alert_src_ip if alert_event is not None else None
        edges = graph_data.get("edges", [])
        edge_count = sum(
            1
            for e in edges
            if (alert_host and (e.get("src") == alert_host or e.get("dst") == alert_host))
            or (alert_src_ip and (e.get("src") == alert_src_ip or e.get("dst") == alert_src_ip))
        )
        if edge_count >= 3:
            score += 10

    return min(score, 100)
