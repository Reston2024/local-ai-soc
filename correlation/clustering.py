"""
Event clustering for the AI-SOC-Brain correlation engine.

Two clustering strategies are provided:

1. cluster_events_by_entity()
   Groups events that share one or more graph entities (host, user, process).
   Useful for finding all activity related to a compromised account or host.

2. cluster_events_by_time()
   Groups events within fixed time windows on the same host.
   Useful for identifying attack chains that unfold over minutes.

Both functions return lists of EventCluster objects.  They operate
entirely in-process using data fetched from DuckDB and SQLite.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from backend.core.deps import Stores
from backend.core.logging import get_logger

log = get_logger(__name__)


@dataclass
class EventCluster:
    """
    A group of related security events.

    Attributes:
        cluster_id:       Unique identifier for this cluster.
        events:           Ordered list of event_id strings.
        shared_entities:  Entity IDs shared across events in this cluster.
        cluster_type:     "process_tree" | "temporal" | "shared_entity"
        relatedness_score: 0.0 (unrelated) → 1.0 (strongly related).
        time_range:       (earliest_timestamp, latest_timestamp) or None.
    """

    cluster_id: str
    events: list[str]  # event_id values
    shared_entities: list[str]  # entity IDs
    cluster_type: str
    relatedness_score: float
    time_range: tuple[datetime, datetime] | None = None


# ---------------------------------------------------------------------------
# Shared entity clustering
# ---------------------------------------------------------------------------


async def cluster_events_by_entity(
    stores: Stores,
    event_ids: list[str],
    case_id: str | None = None,
) -> list[EventCluster]:
    """
    Group events by shared graph entities (process, user, host, ip).

    Algorithm:
    1. For each event, derive a set of entity IDs using the same logic as
       entity_extractor (host:{hostname}, user:{username}, etc.).
    2. Build a reverse map: entity_id → [event_ids].
    3. Union-Find to merge events that share at least one entity.
    4. Return one EventCluster per connected component.

    Args:
        stores:    Data store container.
        event_ids: Which events to cluster (empty = all events for case_id).
        case_id:   Scope to a specific investigation case.

    Returns:
        List of EventCluster objects sorted by descending cluster size.
    """
    events = await _fetch_events(stores, event_ids, case_id)
    if not events:
        return []

    # Build entity → events reverse index
    entity_to_events: dict[str, list[str]] = defaultdict(list)
    event_to_entities: dict[str, set[str]] = defaultdict(set)
    event_timestamps: dict[str, datetime] = {}

    for ev in events:
        eid = ev["event_id"]
        ts = ev.get("timestamp")
        if isinstance(ts, str):
            try:
                ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            except ValueError:
                ts = None
        if ts and ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        if ts:
            event_timestamps[eid] = ts

        # Derive entity IDs from event fields (mirrors entity_extractor logic)
        if ev.get("hostname"):
            ent = f"host:{ev['hostname'].lower()}"
            entity_to_events[ent].append(eid)
            event_to_entities[eid].add(ent)
        if ev.get("username"):
            ent = f"user:{ev['username'].lower()}"
            entity_to_events[ent].append(eid)
            event_to_entities[eid].add(ent)
        if ev.get("process_name") and ev.get("process_id") is not None:
            hostname_key = ev["hostname"].lower() if ev.get("hostname") else "unknown"
            ent = f"proc:{hostname_key}:{ev['process_id']}"
            entity_to_events[ent].append(eid)
            event_to_entities[eid].add(ent)
        if ev.get("dst_ip"):
            ent = f"ip:{ev['dst_ip']}"
            entity_to_events[ent].append(eid)
            event_to_entities[eid].add(ent)
        if ev.get("domain"):
            ent = f"domain:{ev['domain'].lower()}"
            entity_to_events[ent].append(eid)
            event_to_entities[eid].add(ent)

    # Union-Find clustering
    parent = {ev["event_id"]: ev["event_id"] for ev in events}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]  # path compression
            x = parent[x]
        return x

    def union(x: str, y: str) -> None:
        px, py = find(x), find(y)
        if px != py:
            parent[px] = py

    for ent, eids in entity_to_events.items():
        if len(eids) < 2:
            continue
        first = eids[0]
        for other in eids[1:]:
            union(first, other)

    # Collect clusters
    groups: dict[str, list[str]] = defaultdict(list)
    for ev in events:
        eid = ev["event_id"]
        root = find(eid)
        groups[root].append(eid)

    clusters: list[EventCluster] = []
    for group_id, group_eids in groups.items():
        if len(group_eids) < 2:
            continue  # Skip singletons

        # Compute shared entities
        sets = [event_to_entities[eid] for eid in group_eids]
        shared = sets[0].copy()
        for s in sets[1:]:
            shared &= s
        shared_list = sorted(shared)

        # Compute time range
        timestamps = [event_timestamps[eid] for eid in group_eids if eid in event_timestamps]
        time_range = (min(timestamps), max(timestamps)) if timestamps else None

        # Relatedness score based on entity overlap ratio
        all_entities: set[str] = set()
        for s in sets:
            all_entities |= s
        score = len(shared) / len(all_entities) if all_entities else 0.0

        clusters.append(
            EventCluster(
                cluster_id=str(uuid.uuid4()),
                events=sorted(group_eids),
                shared_entities=shared_list,
                cluster_type="shared_entity",
                relatedness_score=round(score, 3),
                time_range=time_range,
            )
        )

    clusters.sort(key=lambda c: len(c.events), reverse=True)
    log.info(
        "Entity clustering complete",
        total_events=len(events),
        clusters=len(clusters),
        case_id=case_id,
    )
    return clusters


# ---------------------------------------------------------------------------
# Temporal clustering
# ---------------------------------------------------------------------------


async def cluster_events_by_time(
    stores: Stores,
    window_minutes: int = 5,
    hostname: str | None = None,
    case_id: str | None = None,
) -> list[EventCluster]:
    """
    Group events that fall within overlapping time windows on the same host.

    A sliding window approach:
    - Sort events by (hostname, timestamp).
    - Open a new cluster when the time gap from the window start exceeds
      *window_minutes*.
    - Report clusters with >= 2 events.

    Args:
        stores:          Data store container.
        window_minutes:  Maximum minutes between first and last event in cluster.
        hostname:        Optional host filter.
        case_id:         Optional case filter.

    Returns:
        List of EventCluster objects sorted by time_range start.
    """
    sql = """
        SELECT event_id, timestamp, hostname
        FROM normalized_events
        WHERE timestamp IS NOT NULL
    """
    params: list[Any] = []

    if hostname:
        sql += " AND hostname = ?"
        params.append(hostname)
    if case_id:
        sql += " AND case_id = ?"
        params.append(case_id)

    sql += " ORDER BY hostname, timestamp"

    try:
        rows = await stores.duckdb.fetch_all(sql, params if params else None)
    except Exception as exc:
        log.error("Temporal clustering query failed", error=str(exc))
        return []

    if not rows:
        return []

    # Group by hostname then apply sliding window
    host_events: dict[str, list[tuple[str, datetime]]] = defaultdict(list)
    for row in rows:
        eid, ts, host = row[0], row[1], row[2] or "unknown"
        if isinstance(ts, str):
            try:
                ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            except ValueError:
                continue
        if ts and ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        if ts:
            host_events[host].append((eid, ts))

    window = timedelta(minutes=window_minutes)
    clusters: list[EventCluster] = []

    for host, ev_list in host_events.items():
        # ev_list is already sorted by timestamp
        current_window: list[tuple[str, datetime]] = []

        for eid, ts in ev_list:
            if not current_window:
                current_window.append((eid, ts))
                continue

            window_start_ts = current_window[0][1]
            if ts - window_start_ts <= window:
                current_window.append((eid, ts))
            else:
                # Emit current window if >= 2 events
                if len(current_window) >= 2:
                    _emit_temporal_cluster(clusters, current_window, host)
                # Start new window
                current_window = [(eid, ts)]

        # Flush last window
        if len(current_window) >= 2:
            _emit_temporal_cluster(clusters, current_window, host)

    clusters.sort(key=lambda c: c.time_range[0] if c.time_range else datetime.min.replace(tzinfo=timezone.utc))
    log.info(
        "Temporal clustering complete",
        window_minutes=window_minutes,
        hostname=hostname,
        clusters=len(clusters),
        case_id=case_id,
    )
    return clusters


def _emit_temporal_cluster(
    clusters: list[EventCluster],
    window: list[tuple[str, datetime]],
    host: str,
) -> None:
    """Construct an EventCluster from a completed time window and append it."""
    eids = [e for e, _ in window]
    timestamps = [t for _, t in window]
    duration_secs = (max(timestamps) - min(timestamps)).total_seconds()
    # Score based on event density: more events in a shorter window = higher score
    window_secs = max(1.0, duration_secs)
    score = min(1.0, len(eids) / (window_secs / 60.0 + 1.0))

    clusters.append(
        EventCluster(
            cluster_id=str(uuid.uuid4()),
            events=eids,
            shared_entities=[f"host:{host.lower()}"],
            cluster_type="temporal",
            relatedness_score=round(score, 3),
            time_range=(min(timestamps), max(timestamps)),
        )
    )


# ---------------------------------------------------------------------------
# Data fetch helper
# ---------------------------------------------------------------------------


async def _fetch_events(
    stores: Stores,
    event_ids: list[str],
    case_id: str | None,
) -> list[dict[str, Any]]:
    """
    Fetch event records from DuckDB.

    If *event_ids* is non-empty, fetch only those events.
    Otherwise fetch all events (optionally filtered by case_id).
    """
    if event_ids:
        placeholders = ",".join("?" * len(event_ids))
        sql = f"""
            SELECT event_id, timestamp, hostname, username, process_name,
                   process_id, dst_ip, domain
            FROM normalized_events
            WHERE event_id IN ({placeholders})
        """
        params: list[Any] = event_ids
        if case_id:
            sql += " AND case_id = ?"
            params.append(case_id)
    else:
        sql = """
            SELECT event_id, timestamp, hostname, username, process_name,
                   process_id, dst_ip, domain
            FROM normalized_events
        """
        params = []
        if case_id:
            sql += " WHERE case_id = ?"
            params.append(case_id)

    sql += " ORDER BY timestamp"

    try:
        rows = await stores.duckdb.fetch_all(sql, params if params else None)
    except Exception as exc:
        log.error("Event fetch for clustering failed", error=str(exc))
        return []

    columns = ["event_id", "timestamp", "hostname", "username",
               "process_name", "process_id", "dst_ip", "domain"]
    return [dict(zip(columns, row)) for row in rows]
