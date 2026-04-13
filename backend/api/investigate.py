"""
Investigation API — unified investigation workflow endpoint.

POST /api/investigate  — start investigation from detection or entity
POST /api/investigate/agentic  — agentic SSE investigation stream
"""
from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from backend.core.logging import get_logger

log = get_logger(__name__)
router = APIRouter(prefix="/investigate", tags=["investigate"])


def _describe_event(evt: dict) -> str:
    """Generate human-readable description for an event."""
    event_type = evt.get("event_type", "")
    proc = evt.get("process_name", "")
    parent = evt.get("parent_process_name", "")
    dst_ip = evt.get("dst_ip", "")
    file_path = evt.get("file_path", "")
    hostname = evt.get("hostname", "")

    if event_type == "process_create":
        if parent:
            return f"{parent} spawned {proc} on {hostname}"
        return f"Process created: {proc} on {hostname}"
    elif event_type == "network_connection":
        return f"{proc} connected to {dst_ip}:{evt.get('dst_port', '?')} from {hostname}"
    elif event_type == "file_create":
        return f"{proc} wrote file {file_path} on {hostname}"
    elif event_type == "registry_write":
        return f"{proc} wrote registry key {file_path} on {hostname}"
    elif event_type == "process_access":
        return f"{proc} accessed {file_path} on {hostname}"
    elif event_type == "auth_failure":
        return f"Authentication failed for {evt.get('username', '?')} on {hostname}"
    else:
        return f"{event_type}: {proc} on {hostname}"


def _safe_val(val: Any) -> Any:
    """Convert datetime objects and other non-JSON-serializable types."""
    if hasattr(val, "isoformat"):
        return val.isoformat()
    return val


def _normalize_event(row: dict) -> dict:
    """Ensure all event values are JSON-serializable."""
    return {k: _safe_val(v) for k, v in row.items()}


@router.post("")
async def start_investigation(request: Request) -> JSONResponse:
    """
    Start a full investigation from a detection or entity.

    Body: { "detection_id": "..." } or { "entity_id": "...", "entity_type": "..." }

    Returns: detection, events, graph (Cytoscape format), timeline, attack_chain,
             techniques, entity_clusters, summary
    """
    body: dict = await request.json()
    stores = request.app.state.stores

    detection_id = body.get("detection_id")
    entity_id = body.get("entity_id")

    result: dict[str, Any] = {
        "detection": None,
        "events": [],
        "graph": {"elements": {"nodes": [], "edges": []}},
        "timeline": [],
        "attack_chain": [],
        "techniques": [],
        "entity_clusters": [],
        "summary": "",
        "car_analytics": [],    # Phase 39: CAR enrichment for investigation evidence
    }

    # -----------------------------------------------------------------------
    # Load detection and matched events
    # -----------------------------------------------------------------------
    events: list[dict] = []

    if detection_id:
        import asyncio
        detection = await asyncio.to_thread(stores.sqlite.get_detection, detection_id)
        if detection:
            result["detection"] = detection

            # Phase 39: CAR analytics enrichment for investigation evidence panel
            attack_tech = detection.get("attack_technique")
            if attack_tech:
                try:
                    parent_id = attack_tech.split(".")[0].upper()
                    car_rows = await asyncio.to_thread(
                        lambda: stores.sqlite._conn.execute(
                            """SELECT analytic_id, technique_id, title, description,
                                      log_sources, analyst_notes, pseudocode,
                                      coverage_level, platforms
                               FROM car_analytics
                               WHERE technique_id = ?
                               ORDER BY analytic_id ASC""",
                            (parent_id,),
                        ).fetchall()
                    )
                    result["car_analytics"] = [dict(r) for r in car_rows]
                except Exception as _exc:
                    log.debug("investigate: CAR lookup failed — %s", _exc)
                    result["car_analytics"] = []

            matched_ids: list[str] = detection.get("matched_event_ids") or []
            if matched_ids:
                placeholders = ",".join(["?" for _ in matched_ids])
                events = await stores.duckdb.fetch_df(
                    f"SELECT * FROM normalized_events WHERE event_id IN ({placeholders}) ORDER BY timestamp",
                    list(matched_ids),
                )

    # -----------------------------------------------------------------------
    # Fallback: search by entity_id string
    # -----------------------------------------------------------------------
    if not events and entity_id:
        events = await stores.duckdb.fetch_df(
            """SELECT * FROM normalized_events
               WHERE hostname = ? OR username = ? OR process_name = ?
                  OR dst_ip = ? OR domain = ?
               ORDER BY timestamp LIMIT 100""",
            [entity_id] * 5,
        )

    # -----------------------------------------------------------------------
    # Expand via entity clustering
    # -----------------------------------------------------------------------
    if events:
        try:
            import asyncio

            from correlation.clustering import cluster_events_by_entity

            matched_event_ids = {e["event_id"] for e in events}
            clusters = await cluster_events_by_entity(stores, event_ids=[])

            expanded_ids = set(matched_event_ids)
            relevant_clusters = []
            for cluster in clusters:
                cluster_set = set(cluster.events)
                if cluster_set & matched_event_ids:
                    expanded_ids.update(cluster_set)
                    relevant_clusters.append(
                        {
                            "cluster_id": cluster.cluster_id,
                            "events": cluster.events,
                            "shared_entities": cluster.shared_entities,
                            "relatedness_score": cluster.relatedness_score,
                        }
                    )
            result["entity_clusters"] = relevant_clusters

            if expanded_ids != matched_event_ids:
                placeholders = ",".join(["?" for _ in expanded_ids])
                events = await stores.duckdb.fetch_df(
                    f"SELECT * FROM normalized_events WHERE event_id IN ({placeholders}) ORDER BY timestamp",
                    list(expanded_ids),
                )
        except Exception as exc:
            log.warning("investigate: clustering failed — %s", exc)

    # -----------------------------------------------------------------------
    # Normalize event dicts for JSON serialization
    # -----------------------------------------------------------------------
    events = [_normalize_event(e) for e in events]
    result["events"] = events

    # -----------------------------------------------------------------------
    # Build timeline
    # -----------------------------------------------------------------------
    sorted_events = sorted(events, key=lambda e: e.get("timestamp") or "")
    result["timeline"] = [
        {
            "timestamp": evt.get("timestamp"),
            "event_id": evt.get("event_id"),
            "hostname": evt.get("hostname"),
            "process_name": evt.get("process_name"),
            "event_type": evt.get("event_type"),
            "severity": evt.get("severity"),
            "description": _describe_event(evt),
            "attack_technique": evt.get("attack_technique"),
            "attack_tactic": evt.get("attack_tactic"),
        }
        for evt in sorted_events
    ]

    # -----------------------------------------------------------------------
    # Build Cytoscape-format graph
    # -----------------------------------------------------------------------
    graph_nodes: dict[str, dict] = {}
    graph_edges: list[dict] = []
    edge_set: set[str] = set()

    def add_node(nid: str, data: dict) -> None:
        if nid not in graph_nodes:
            graph_nodes[nid] = {"data": {"id": nid, **data}}

    def add_edge(src: str, tgt: str, label: str, etype: str) -> None:
        if src and tgt and src in graph_nodes and tgt in graph_nodes:
            key = f"{src}->{tgt}:{etype}"
            if key not in edge_set:
                edge_set.add(key)
                graph_edges.append(
                    {"data": {"source": src, "target": tgt, "label": label, "edge_type": etype}}
                )

    for evt in events:
        hostname = evt.get("hostname")
        username = evt.get("username")
        proc = evt.get("process_name")
        proc_id = evt.get("process_id") or "?"
        parent_proc = evt.get("parent_process_name")
        dst_ip = evt.get("dst_ip")
        file_path = evt.get("file_path")
        domain = evt.get("domain")
        event_type = evt.get("event_type", "")
        technique = evt.get("attack_technique")

        host_node = f"host:{hostname}" if hostname else None
        user_node = f"user:{username}" if username else None
        proc_node = f"process:{proc}:{hostname or '?'}" if proc else None
        parent_node = f"process:{parent_proc}:{hostname or '?'}" if parent_proc else None
        dst_node = f"ip:{dst_ip}" if dst_ip else None
        skip_file = file_path and file_path.startswith("HK")
        file_node = f"file:{file_path}" if file_path and not skip_file else None
        dom_node = f"domain:{domain}" if domain else None

        if host_node:
            add_node(host_node, {"label": hostname, "type": "host", "entity_type": "host"})
        if user_node:
            add_node(user_node, {"label": username, "type": "user", "entity_type": "user"})
        if proc_node:
            add_node(
                proc_node,
                {
                    "label": proc, "type": "process", "entity_type": "process",
                    "process_id": proc_id, "hostname": hostname,
                    "command_line": evt.get("command_line"),
                    "severity": evt.get("severity"),
                    "attack_technique": technique,
                },
            )
        if parent_node:
            add_node(
                parent_node,
                {"label": parent_proc, "type": "process", "entity_type": "process", "hostname": hostname},
            )
        if dst_node:
            add_node(
                dst_node,
                {"label": dst_ip, "type": "ip", "entity_type": "ip", "dst_port": evt.get("dst_port")},
            )
        if file_node:
            label = (file_path or "").split("\\")[-1] or file_path
            add_node(file_node, {"label": label, "type": "file", "entity_type": "file", "full_path": file_path})
        if dom_node:
            add_node(dom_node, {"label": domain, "type": "domain", "entity_type": "domain"})

        # Edges
        if event_type == "process_create" and parent_node and proc_node:
            add_edge(parent_node, proc_node, "spawned", "spawned")
        if event_type == "network_connection" and proc_node and dst_node:
            add_edge(proc_node, dst_node, "connected_to", "connected_to")
        if event_type == "file_create" and proc_node and file_node:
            add_edge(proc_node, file_node, "wrote", "wrote")
        if event_type in ("process_access", "file_read") and proc_node and file_node:
            add_edge(proc_node, file_node, "accessed", "accessed")
        if proc_node and host_node:
            add_edge(proc_node, host_node, "ran_on", "ran_on")
        if dom_node and dst_node:
            add_edge(dom_node, dst_node, "resolved_to", "resolved_to")

        # Technique nodes for high/critical severity
        if technique and evt.get("severity") in ("high", "critical"):
            t_nid = f"technique:{technique}"
            add_node(t_nid, {"label": technique, "type": "detection", "entity_type": "attack_technique"})
            if proc_node:
                add_edge(proc_node, t_nid, "triggered", "triggered")

    result["graph"] = {"elements": {"nodes": list(graph_nodes.values()), "edges": graph_edges}}

    # -----------------------------------------------------------------------
    # MITRE techniques
    # -----------------------------------------------------------------------
    techniques_seen: dict[str, dict] = {}
    for evt in events:
        t = evt.get("attack_technique")
        if t:
            if t not in techniques_seen:
                techniques_seen[t] = {
                    "technique_id": t,
                    "tactic": evt.get("attack_tactic"),
                    "count": 0,
                }
            techniques_seen[t]["count"] += 1
    result["techniques"] = list(techniques_seen.values())

    # -----------------------------------------------------------------------
    # Attack chain (ordered by timestamp)
    # -----------------------------------------------------------------------
    result["attack_chain"] = [
        {
            "step": i,
            "timestamp": evt.get("timestamp"),
            "event_id": evt.get("event_id"),
            "hostname": evt.get("hostname"),
            "entity": evt.get("process_name") or evt.get("username") or evt.get("hostname"),
            "action": evt.get("event_type"),
            "description": _describe_event(evt),
            "technique": evt.get("attack_technique"),
            "severity": evt.get("severity"),
        }
        for i, evt in enumerate(sorted_events)
    ]

    # -----------------------------------------------------------------------
    # Summary text
    # -----------------------------------------------------------------------
    hosts = {e.get("hostname") for e in events if e.get("hostname")}
    techniques_set = {e.get("attack_technique") for e in events if e.get("attack_technique")}
    critical_count = sum(1 for e in events if e.get("severity") in ("critical", "high"))
    result["summary"] = (
        f"Investigation covers {len(events)} events across {len(hosts)} host(s). "
        f"{len(techniques_set)} MITRE technique(s) observed. "
        f"{critical_count} high/critical severity events."
    )

    return JSONResponse(content=result)


# ---------------------------------------------------------------------------
# Phase 45: Agentic investigation SSE endpoint
# ---------------------------------------------------------------------------

class AgenticInvestigateRequest(BaseModel):
    detection_id: str


@router.post("/agentic")
async def run_agentic_investigation(
    body: AgenticInvestigateRequest,
    request: Request,
) -> EventSourceResponse:
    """
    Run an agentic investigation for a detection.

    Streams SSE events:
      - tool_call: each tool the agent invokes
      - reasoning: LLM chain-of-thought text between calls
      - verdict: final TP/FP verdict with confidence + narrative
      - limit: hit max_calls (10) or timeout (90s)
      - done: stream complete
      - error: agent error (Ollama unavailable, etc.)
    """
    detection_id = body.detection_id

    async def _event_generator():
        try:
            stores = request.app.state.stores
        except AttributeError:
            yield {"event": "error", "data": json.dumps({"message": "Stores not initialised"})}
            return

        try:
            from backend.services.agent.runner import build_agent, run_investigation
            agent = build_agent(stores)
        except Exception as exc:
            log.error("Failed to build agent: %s", exc)
            yield {"event": "error", "data": json.dumps({"message": f"Agent build failed: {exc}"})}
            return

        # Enrich task prompt with detection context so tools have concrete values to query.
        # query_events and get_entity_profile need hostname, not detection_id — supply it here.
        import asyncio as _asyncio
        detection_ctx = ""
        try:
            det = await _asyncio.to_thread(stores.sqlite.get_detection, detection_id)
            if det:
                rule_id = det.get("rule_id") or ""
                technique = det.get("attack_technique") or ""
                severity = det.get("severity") or ""
                entity_key = det.get("entity_key") or ""
                # Hostname may be in entity_key ("hostname:FQDN" or bare value)
                hostname = ""
                if entity_key:
                    hostname = entity_key.split(":", 1)[-1] if ":" in entity_key else entity_key
                # If no entity_key, try to get hostname from matched events
                if not hostname:
                    matched_ids: list[str] = det.get("matched_event_ids") or []
                    if matched_ids:
                        sample_events = await stores.duckdb.fetch_df(
                            f"SELECT hostname FROM normalized_events WHERE event_id IN ({','.join(['?' for _ in matched_ids[:3]])}) AND hostname IS NOT NULL LIMIT 1",
                            matched_ids[:3],
                        )
                        if sample_events:
                            hostname = sample_events[0].get("hostname") or ""
                ctx_parts = []
                if hostname:
                    ctx_parts.append(f"hostname={hostname}")
                if rule_id:
                    ctx_parts.append(f"rule_id={rule_id}")
                if technique:
                    ctx_parts.append(f"technique={technique}")
                if severity:
                    ctx_parts.append(f"severity={severity}")
                if ctx_parts:
                    detection_ctx = " Context: " + ", ".join(ctx_parts) + "."
        except Exception as _exc:
            log.debug("Could not enrich task with detection context: %s", _exc)

        task = (
            f"Investigate security detection ID: {detection_id}.{detection_ctx} "
            "IMPORTANT: query_events and get_entity_profile require a hostname parameter — "
            "use the hostname from the context above, NOT the detection_id. "
            "Query relevant events for the host, enrich suspicious destination IPs, "
            "check graph connections for lateral movement, and search for similar confirmed incidents. "
            "Produce a final TP or FP verdict with confidence and narrative."
        )

        log.info("Starting agentic investigation for detection_id=%s", detection_id)
        async for event in run_investigation(agent, task, timeout=300.0):
            yield event
        log.info("Agentic investigation complete for detection_id=%s", detection_id)

    return EventSourceResponse(_event_generator())
