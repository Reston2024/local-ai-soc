"""Causality engine orchestrator — Phase 6."""
import re
from backend.causality.attack_chain_builder import find_causal_chain
from backend.causality.mitre_mapper import map_techniques
from backend.causality.scoring import score_chain

# UUID regex to detect Sigma-sourced rule IDs (used in attack_mapper.py pattern)
_UUID_RE = re.compile(
    r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
    re.IGNORECASE,
)


def build_causality_sync(alert_id: str, events: list, alerts: list) -> dict:
    """Build a causality result for a given alert.

    Arguments:
        alert_id: ID of the alert to investigate
        events: list of event dicts (from routes._events at call time)
        alerts: list of alert dicts (from routes._alerts at call time)

    Returns empty dict if alert_id not found.
    Returns CausalityResult dict with keys:
        alert_id, nodes, edges, attack_paths, chain,
        techniques, score, first_event, last_event
    """
    # Step 1: Find alert
    alert = None
    for a in alerts:
        a_id = a.get("id") if isinstance(a, dict) else getattr(a, "id", None)
        if a_id == alert_id:
            alert = a
            break
    if alert is None:
        return {}

    # Step 2: Find triggering event
    event_id = alert.get("event_id") if isinstance(alert, dict) else getattr(alert, "event_id", None)
    if not event_id:
        return {}

    # Step 3: BFS causal chain from triggering event
    chain_events = find_causal_chain(event_id, events, max_depth=5, max_events=50)
    if not chain_events:
        # Include just the triggering event if BFS finds nothing
        trigger_event = next((e for e in events if e.get("id") == event_id), None)
        if trigger_event:
            chain_events = [trigger_event]

    chain_event_ids = {e.get("id") for e in chain_events}

    # Step 4: Find correlated alerts (alerts whose event_id is in chain)
    chain_alerts = []
    for a in alerts:
        a_event_id = a.get("event_id") if isinstance(a, dict) else getattr(a, "event_id", None)
        if a_event_id in chain_event_ids:
            chain_alerts.append(a if isinstance(a, dict) else a.model_dump())

    # Step 5: Extract MITRE tags from alert
    sigma_tags = []
    attack_tags = alert.get("attack_tags") if isinstance(alert, dict) else getattr(alert, "attack_tags", [])
    for tag in (attack_tags or []):
        if isinstance(tag, dict):
            t = tag.get("technique", "")
            if t:
                # Convert "T1059.001" back to "attack.t1059.001" format for map_techniques
                sigma_tags.append(f"attack.{t.lower()}")
        elif isinstance(tag, str):
            sigma_tags.append(tag)

    # Derive event_type and category from triggering event for fallback
    trigger_ev = next((e for e in chain_events if e.get("id") == event_id), chain_events[0] if chain_events else {})
    event_type = trigger_ev.get("event_type", "") if trigger_ev else ""
    alert_description = alert.get("description", "") if isinstance(alert, dict) else getattr(alert, "description", "")

    # Step 6: Map MITRE techniques
    techniques = map_techniques(sigma_tags, event_type, alert_description.lower())

    # Step 7: Score chain
    score = score_chain(chain_events, chain_alerts, techniques)

    # Step 8: Build graph (import deferred to avoid startup failure if builder absent)
    try:
        from backend.src.graph.builder import build_graph
        alert_dicts = [a if isinstance(a, dict) else a.model_dump() for a in chain_alerts]
        graph = build_graph(chain_events, alert_dicts)
        nodes = [n.model_dump() for n in graph.nodes]
        edges = [e.model_dump() for e in graph.edges]
        attack_paths = [p.model_dump() for p in graph.attack_paths]
    except Exception:
        nodes, edges, attack_paths = [], [], []

    # Step 9: Temporal bounds
    timestamps = [e.get("timestamp", "") for e in chain_events if e.get("timestamp")]
    first_event = min(timestamps) if timestamps else ""
    last_event = max(timestamps) if timestamps else ""

    return {
        "alert_id": alert_id,
        "nodes": nodes,
        "edges": edges,
        "attack_paths": attack_paths,
        "chain": chain_events,
        "techniques": techniques,
        "score": score,
        "first_event": first_event,
        "last_event": last_event,
    }
