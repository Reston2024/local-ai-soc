"""Causal chain construction via shared-entity BFS — Phase 6 Plan 01."""

from backend.causality.entity_resolver import resolve_canonical_id

# Entity types to consider when building the entity fingerprint for an event
ENTITY_FIELDS = ["host", "user", "process", "ip_src", "ip_dst", "domain"]


def _get_entity_ids(event: dict) -> set:
    """Return set of canonical entity IDs present in this event."""
    result = set()
    for etype in ENTITY_FIELDS:
        cid = resolve_canonical_id(event, etype)
        if cid:
            result.add(cid)
    return result


def find_causal_chain(
    start_event_id: str,
    all_events: list,
    max_depth: int = 5,
    max_events: int = 50,
) -> list:
    """BFS over events sharing entity IDs with start_event.

    Traverses the event graph by finding events that share at least one
    canonical entity ID with the current frontier event.  Cycle protection
    is provided by the ``visited_event_ids`` set — each event ID is enqueued
    at most once, so circular references cannot produce an infinite loop.

    Returns the collected events sorted ascending by timestamp.
    Returns [] when start_event_id is not found in all_events.
    """
    # Locate the starting event
    start_event = next(
        (e for e in all_events if e.get("id") == start_event_id), None
    )
    if not start_event:
        return []

    visited_event_ids: set = {start_event_id}
    chain_events: list = []
    queue: list = [(start_event, 0)]  # (event, current_depth)

    while queue and len(chain_events) < max_events:
        current_event, depth = queue.pop(0)
        chain_events.append(current_event)

        if depth >= max_depth:
            continue

        current_entity_ids = _get_entity_ids(current_event)
        if not current_entity_ids:
            continue

        for ev in all_events:
            ev_id = ev.get("id")
            if not ev_id or ev_id in visited_event_ids:
                continue
            ev_entity_ids = _get_entity_ids(ev)
            if current_entity_ids & ev_entity_ids:  # shared entity — link found
                visited_event_ids.add(ev_id)
                queue.append((ev, depth + 1))

    return sorted(chain_events, key=lambda e: e.get("timestamp", ""))
