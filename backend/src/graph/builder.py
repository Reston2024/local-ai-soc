"""Build Cytoscape-compatible graph from normalized events and alerts.

Phase 4 Plan 02: full node/edge extraction with Union-Find attack path grouping.
"""
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
# Public API
# ---------------------------------------------------------------------------

def build_graph(events: list[dict], alerts: list[dict]) -> GraphResponse:
    """Build a GraphResponse from normalized events and alert dicts."""
    nodes = _extract_nodes(events, alerts)
    edges = _extract_edges(events, alerts, nodes)
    attack_paths = _group_attack_paths(nodes, edges)
    return GraphResponse(
        nodes=list(nodes.values()),
        edges=edges,
        attack_paths=attack_paths,
        stats={
            "node_count": len(nodes),
            "edge_count": len(edges),
            "event_count": len(events),
            "alert_count": len(alerts),
        },
    )
