"""Build Cytoscape-compatible graph from normalized events and alerts.

Phase 4 Plan 02: full node/edge extraction with Union-Find attack path grouping.
Phase 4 Plan 03: _correlate() with 4 correlation patterns.
"""
from collections import defaultdict
from datetime import datetime, timezone
from backend.src.api.models import GraphNode, GraphEdge, AttackPath, GraphResponse

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DNS_CHAIN_WINDOW_SEC = 60
PROXIMITY_WINDOW_SEC = 30
MAX_PROXIMITY_EDGES_PER_EVENT = 10

SEVERITY_RANK: dict[str, int] = {
    "critical": 4,
    "high": 3,
    "medium": 2,
    "low": 1,
    "info": 0,
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_or_create_node(
    nodes: dict[str, GraphNode],
    nid: str,
    type_: str,
    label: str,
    ev_id: str | None = None,
    timestamp: str | None = None,
    attributes: dict | None = None,
) -> GraphNode:
    """Return existing node or create it; update evidence + timestamps in place."""
    if nid not in nodes:
        nodes[nid] = GraphNode(
            id=nid,
            type=type_,
            label=label,
            attributes=attributes or {},
            first_seen=timestamp or "",
            last_seen=timestamp or "",
            evidence=[ev_id] if ev_id else [],
        )
    else:
        node = nodes[nid]
        # Update evidence list
        if ev_id and ev_id not in node.evidence:
            node.evidence.append(ev_id)
        # Update first_seen / last_seen (ISO string min/max comparison)
        if timestamp:
            if not node.first_seen or timestamp < node.first_seen:
                node.first_seen = timestamp
            if not node.last_seen or timestamp > node.last_seen:
                node.last_seen = timestamp
        # Merge attributes
        if attributes:
            node.attributes.update(attributes)
    return nodes[nid]


def _extract_nodes(events: list[dict], alerts: list[dict]) -> dict[str, GraphNode]:
    """Create/update nodes for all entities seen in events and alerts."""
    nodes: dict[str, GraphNode] = {}

    for ev in events:
        ev_id = ev.get("id")
        ts = ev.get("timestamp")
        host = ev.get("host")
        src_ip = ev.get("src_ip")
        dst_ip = ev.get("dst_ip")
        query = ev.get("query")
        user = ev.get("user")
        process = ev.get("process")
        event_type = ev.get("event_type") or ev.get("event", "")

        if host:
            _get_or_create_node(nodes, f"host:{host}", "host", host, ev_id, ts)

        if src_ip:
            _get_or_create_node(nodes, f"ip:{src_ip}", "ip", src_ip, ev_id, ts)

        if dst_ip:
            _get_or_create_node(nodes, f"ip:{dst_ip}", "ip", dst_ip, ev_id, ts)

        if query and event_type in ("dns", "dns_query"):
            _get_or_create_node(nodes, f"domain:{query}", "domain", query, ev_id, ts)

        if user:
            _get_or_create_node(nodes, f"user:{user}", "user", user, ev_id, ts)

        if process:
            _get_or_create_node(nodes, f"process:{process}", "process", process, ev_id, ts)

    for alert in alerts:
        aid = alert.get("id", "")
        if not aid:
            continue
        label = alert.get("rule", "alert")
        attrs = {
            "severity": alert.get("severity", "info"),
            "description": alert.get("description", ""),
        }
        _get_or_create_node(
            nodes,
            f"alert:{aid}",
            "alert",
            label,
            ev_id=alert.get("event_id"),
            timestamp=alert.get("timestamp"),
            attributes=attrs,
        )

    return nodes


def _extract_edges(
    events: list[dict],
    alerts: list[dict],
    nodes: dict[str, GraphNode],
) -> list[GraphEdge]:
    """Create directed edges for connections, DNS queries, and alert triggers."""
    edges: list[GraphEdge] = []
    edge_count = 0

    # Build event lookup for alert_trigger resolution
    event_lookup: dict[str, dict] = {}
    for ev in events:
        ev_id = ev.get("id")
        if ev_id:
            event_lookup[ev_id] = ev

    for ev in events:
        ev_id = ev.get("id", "")
        ts = ev.get("timestamp", "")
        host = ev.get("host")
        src_ip = ev.get("src_ip")
        dst_ip = ev.get("dst_ip")
        query = ev.get("query")
        event_type = ev.get("event_type") or ev.get("event", "")

        if src_ip and dst_ip:
            edge_count += 1
            edges.append(GraphEdge(
                id=f"e{edge_count}",
                type="connection",
                src=f"ip:{src_ip}",
                dst=f"ip:{dst_ip}",
                timestamp=ts,
                evidence_event_ids=[ev_id] if ev_id else [],
            ))
        elif host and dst_ip and not src_ip:
            edge_count += 1
            edges.append(GraphEdge(
                id=f"e{edge_count}",
                type="connection",
                src=f"host:{host}",
                dst=f"ip:{dst_ip}",
                timestamp=ts,
                evidence_event_ids=[ev_id] if ev_id else [],
            ))

        if event_type in ("dns", "dns_query") and host and query:
            edge_count += 1
            edges.append(GraphEdge(
                id=f"e{edge_count}",
                type="dns_query",
                src=f"host:{host}",
                dst=f"domain:{query}",
                timestamp=ts,
                evidence_event_ids=[ev_id] if ev_id else [],
            ))

    for alert in alerts:
        aid = alert.get("id", "")
        if not aid:
            continue
        alert_nid = f"alert:{aid}"
        if alert_nid not in nodes:
            continue

        # Resolve target node from triggering event
        triggering_event_id = alert.get("event_id")
        target_nid: str | None = None
        if triggering_event_id and triggering_event_id in event_lookup:
            tev = event_lookup[triggering_event_id]
            thost = tev.get("host")
            tdst_ip = tev.get("dst_ip")
            if thost and f"host:{thost}" in nodes:
                target_nid = f"host:{thost}"
            elif tdst_ip and f"ip:{tdst_ip}" in nodes:
                target_nid = f"ip:{tdst_ip}"

        if target_nid:
            edge_count += 1
            edges.append(GraphEdge(
                id=f"e{edge_count}",
                type="alert_trigger",
                src=alert_nid,
                dst=target_nid,
                timestamp=alert.get("timestamp", ""),
                evidence_event_ids=[triggering_event_id] if triggering_event_id else [],
            ))

    return edges


# ---------------------------------------------------------------------------
# Union-Find helpers
# ---------------------------------------------------------------------------

def _find(parent: dict[str, str], x: str) -> str:
    while parent[x] != x:
        parent[x] = parent[parent[x]]  # path compression
        x = parent[x]
    return x


def _union(parent: dict[str, str], a: str, b: str) -> None:
    ra, rb = _find(parent, a), _find(parent, b)
    if ra != rb:
        parent[rb] = ra


# ---------------------------------------------------------------------------
# Attack path grouping
# ---------------------------------------------------------------------------

def _path_severity(path_node_ids: list[str], nodes: dict[str, GraphNode]) -> str:
    """Return max severity among alert nodes in the path; default 'info'."""
    best = "info"
    best_rank = SEVERITY_RANK["info"]
    for nid in path_node_ids:
        node = nodes.get(nid)
        if node and node.type == "alert":
            sev = node.attributes.get("severity", "info")
            rank = SEVERITY_RANK.get(sev, 0)
            if rank > best_rank:
                best_rank = rank
                best = sev
    return best


def _group_attack_paths(
    nodes: dict[str, GraphNode],
    edges: list[GraphEdge],
) -> list[AttackPath]:
    """Union-Find over node graph; return one AttackPath per connected component."""
    if not nodes:
        return []

    parent: dict[str, str] = {nid: nid for nid in nodes}

    for edge in edges:
        if edge.src in parent and edge.dst in parent:
            _union(parent, edge.src, edge.dst)

    # Group node IDs by root
    components: dict[str, list[str]] = {}
    for nid in nodes:
        root = _find(parent, nid)
        components.setdefault(root, []).append(nid)

    attack_paths: list[AttackPath] = []
    for i, (root, node_ids) in enumerate(components.items()):
        # Collect edges whose both endpoints belong to this component
        node_set = set(node_ids)
        path_edge_ids = [
            e.id for e in edges
            if e.src in node_set and e.dst in node_set
        ]

        severity = _path_severity(node_ids, nodes)

        # Compute first_event / last_event from node timestamps
        timestamps = [
            nodes[nid].first_seen
            for nid in node_ids
            if nodes[nid].first_seen
        ]
        first_event = min(timestamps) if timestamps else ""
        last_event = max(timestamps) if timestamps else ""

        attack_paths.append(AttackPath(
            id=f"path-{i + 1}",
            node_ids=node_ids,
            edge_ids=path_edge_ids,
            severity=severity,
            first_event=first_event,
            last_event=last_event,
        ))

    return attack_paths


# ---------------------------------------------------------------------------
# Correlation engine
# ---------------------------------------------------------------------------

def _correlate(
    events: list[dict],
    nodes: dict[str, GraphNode],
    edges: list[GraphEdge],
) -> list[GraphEdge]:
    """Emit related_event edges using 4 correlation patterns.

    Pattern 1: Repeated DNS queries to the same domain (>=2 events).
    Pattern 2: DNS query followed by connection on same host within DNS_CHAIN_WINDOW_SEC.
    Pattern 3: Alerts sharing the same entity (host, src_ip, or dst_ip).
    Pattern 4: Events from the same host within PROXIMITY_WINDOW_SEC (capped at MAX_PROXIMITY_EDGES_PER_EVENT).
    """
    corr_edges: list[GraphEdge] = []
    ec = 10000  # Start high to avoid ID collision with _extract_edges counters

    # --- Pattern 1: Repeated DNS to same domain ---
    dns_by_query: dict[str, list[dict]] = defaultdict(list)
    for ev in events:
        et = ev.get("event_type") or ev.get("event", "")
        if et in ("dns", "dns_query") and ev.get("query"):
            dns_by_query[ev["query"]].append(ev)
    for domain, dns_evs in dns_by_query.items():
        if len(dns_evs) < 2:
            continue
        domain_nid = f"domain:{domain}"
        if domain_nid not in nodes:
            continue
        host_nids = []
        for ev in dns_evs:
            h = ev.get("host")
            if h:
                host_nids.append((f"host:{h}", ev.get("id", "")))
        for i in range(len(host_nids)):
            for j in range(i + 1, min(i + 1 + MAX_PROXIMITY_EDGES_PER_EVENT, len(host_nids))):
                src_nid, src_eid = host_nids[i]
                dst_nid, dst_eid = host_nids[j]
                if src_nid in nodes and dst_nid in nodes and src_nid != dst_nid:
                    ec += 1
                    corr_edges.append(GraphEdge(
                        id=f"related_event:{src_nid}:{dst_nid}:{ec}",
                        type="related_event",
                        src=src_nid,
                        dst=dst_nid,
                        evidence_event_ids=[src_eid, dst_eid],
                    ))

    # --- Pattern 2: DNS → connection chain within DNS_CHAIN_WINDOW_SEC ---
    timed_events: list[tuple] = []
    for ev in events:
        ts_str = ev.get("timestamp", "")
        try:
            ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00")) if ts_str else None
        except ValueError:
            ts = None
        timed_events.append((ts, ev))
    timed_events.sort(key=lambda x: (x[0] or datetime.min.replace(tzinfo=timezone.utc)))

    for i, (ts_i, ev_i) in enumerate(timed_events):
        et_i = ev_i.get("event_type") or ev_i.get("event", "")
        if et_i not in ("dns", "dns_query") or not ev_i.get("query") or ts_i is None:
            continue
        host_i = ev_i.get("host")
        domain_nid = f"domain:{ev_i['query']}"
        for j in range(i + 1, len(timed_events)):
            ts_j, ev_j = timed_events[j]
            if ts_j is None:
                continue
            delta = (ts_j - ts_i).total_seconds()
            if delta > DNS_CHAIN_WINDOW_SEC:
                break
            et_j = ev_j.get("event_type") or ev_j.get("event", "")
            if et_j == "connection" and ev_j.get("host") == host_i and ev_j.get("dst_ip"):
                dst_nid = f"ip:{ev_j['dst_ip']}"
                if domain_nid in nodes and dst_nid in nodes:
                    ec += 1
                    corr_edges.append(GraphEdge(
                        id=f"related_event:{domain_nid}:{dst_nid}:{ec}",
                        type="related_event",
                        src=domain_nid,
                        dst=dst_nid,
                        timestamp=ts_j.isoformat(),
                        evidence_event_ids=[ev_i.get("id", ""), ev_j.get("id", "")],
                    ))

    # --- Pattern 3: Shared entity alerts ---
    alert_trigger_edges = [e for e in edges if e.type == "alert_trigger"]
    entity_to_alert_srcs: dict[str, list[str]] = defaultdict(list)
    for edge in alert_trigger_edges:
        entity_to_alert_srcs[edge.dst].append(edge.src)
    for entity_nid, alert_nids in entity_to_alert_srcs.items():
        if len(alert_nids) < 2:
            continue
        for i in range(len(alert_nids)):
            for j in range(i + 1, min(i + 2, len(alert_nids))):
                src_nid, dst_nid = alert_nids[i], alert_nids[j]
                ec += 1
                corr_edges.append(GraphEdge(
                    id=f"related_event:{src_nid}:{dst_nid}:{ec}",
                    type="related_event",
                    src=src_nid,
                    dst=dst_nid,
                ))

    # --- Pattern 4: Temporal proximity (same host, within PROXIMITY_WINDOW_SEC) ---
    host_events: dict[str, list[tuple]] = defaultdict(list)
    for ts, ev in timed_events:
        h = ev.get("host")
        if h and ts is not None:
            host_events[h].append((ts, ev))

    for host, hev_list in host_events.items():
        host_nid = f"host:{host}"
        if host_nid not in nodes:
            continue
        edge_count_per_event: dict[str, int] = defaultdict(int)
        for i, (ts_i, ev_i) in enumerate(hev_list):
            ev_i_id = ev_i.get("id", "")
            for j in range(i + 1, len(hev_list)):
                ts_j, ev_j = hev_list[j]
                if (ts_j - ts_i).total_seconds() > PROXIMITY_WINDOW_SEC:
                    break
                if edge_count_per_event[ev_i_id] >= MAX_PROXIMITY_EDGES_PER_EVENT:
                    break
                ev_j_id = ev_j.get("id", "")
                src_nid = (
                    f"ip:{ev_i.get('src_ip')}"
                    if ev_i.get("src_ip") and f"ip:{ev_i.get('src_ip')}" in nodes
                    else host_nid
                )
                dst_nid = (
                    f"ip:{ev_j.get('dst_ip')}"
                    if ev_j.get("dst_ip") and f"ip:{ev_j.get('dst_ip')}" in nodes
                    else host_nid
                )
                if src_nid != dst_nid:
                    ec += 1
                    edge_count_per_event[ev_i_id] += 1
                    corr_edges.append(GraphEdge(
                        id=f"related_event:{src_nid}:{dst_nid}:{ec}",
                        type="related_event",
                        src=src_nid,
                        dst=dst_nid,
                        timestamp=ts_j.isoformat(),
                        evidence_event_ids=[ev_i_id, ev_j_id],
                    ))

    return corr_edges


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_graph(events: list[dict], alerts: list[dict]) -> GraphResponse:
    """Build a GraphResponse from normalized events and alert dicts."""
    nodes = _extract_nodes(events, alerts)
    edges = _extract_edges(events, alerts, nodes)
    corr_edges = _correlate(events, nodes, edges)
    all_edges = edges + corr_edges
    attack_paths = _group_attack_paths(nodes, all_edges)
    return GraphResponse(
        nodes=list(nodes.values()),
        edges=all_edges,
        attack_paths=attack_paths,
        stats={
            "node_count": len(nodes),
            "edge_count": len(all_edges),
            "event_count": len(events),
            "alert_count": len(alerts),
        },
    )
