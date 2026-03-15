"""Build Cytoscape-compatible graph from normalized events."""
from backend.src.api.models import GraphNode, GraphEdge, GraphResponse

def build_graph(events: list[dict]) -> GraphResponse:
    nodes: dict[str, GraphNode] = {}
    edges: list[GraphEdge] = []
    edge_count = 0

    for ev in events:
        host = ev.get("host")
        src_ip = ev.get("src_ip")
        dst_ip = ev.get("dst_ip")
        severity = ev.get("severity", "info")

        if host:
            nid = f"host:{host}"
            nodes[nid] = GraphNode(id=nid, type="host", label=host)

        if src_ip:
            nid = f"ip:{src_ip}"
            nodes[nid] = GraphNode(id=nid, type="ip", label=src_ip)

        if dst_ip:
            nid = f"ip:{dst_ip}"
            nodes[nid] = GraphNode(id=nid, type="ip", label=dst_ip)

        if src_ip and dst_ip:
            edge_count += 1
            edges.append(GraphEdge(
                id=f"e{edge_count}",
                source=f"ip:{src_ip}",
                target=f"ip:{dst_ip}",
                type=ev.get("event", "connection"),
            ))
        elif host and dst_ip:
            edge_count += 1
            edges.append(GraphEdge(
                id=f"e{edge_count}",
                source=f"host:{host}",
                target=f"ip:{dst_ip}",
                type=ev.get("event", "connection"),
            ))

        if severity in ("high", "critical"):
            aid = f"alert:{ev.get('id', edge_count)}"
            nodes[aid] = GraphNode(id=aid, type="alert", label=ev.get("event", "alert"))
            if dst_ip:
                edge_count += 1
                edges.append(GraphEdge(
                    id=f"e{edge_count}",
                    source=aid,
                    target=f"ip:{dst_ip}",
                    type="flagged",
                ))

    return GraphResponse(nodes=list(nodes.values()), edges=edges)
