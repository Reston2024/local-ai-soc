"""
Entity and edge extraction from normalized security events.

extract_entities_and_edges() is a pure function (no I/O) that derives
graph nodes and directed relationships from a single NormalizedEvent.

The returned structures use plain dicts to avoid coupling to the SQLite
store's internal API — callers pass them to SQLiteStore.upsert_entity()
and SQLiteStore.insert_edge().

Entity ID format:
    host:{hostname}
    user:{username}
    proc:{hostname}:{process_id}
    file:{file_path}
    ip:{ip_address}
    domain:{domain_name}

These IDs are stable across events and enable deduplication — two events
from the same host will reference the same "host:..." entity node.
"""

from __future__ import annotations

from typing import Any

from backend.models.event import NormalizedEvent


def extract_entities_and_edges(
    event: NormalizedEvent,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Derive graph entities and edges from a single normalised event.

    Args:
        event: A fully normalised NormalizedEvent.

    Returns:
        A two-tuple (entities, edges) where:

        entities — list of dicts, each with keys:
            id, type, name, attributes (dict), case_id

        edges — list of dicts, each with keys:
            source_type, source_id, edge_type,
            target_type, target_id, properties (dict)
    """
    entities: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Build entity nodes
    # ------------------------------------------------------------------

    host_id: str | None = None
    user_id: str | None = None
    proc_id: str | None = None
    file_id: str | None = None
    ip_id: str | None = None
    domain_id: str | None = None

    if event.hostname:
        host_id = f"host:{event.hostname.lower()}"
        entities.append({
            "id": host_id,
            "type": "host",
            "name": event.hostname,
            "attributes": {
                "hostname": event.hostname,
                "source_type": event.source_type,
            },
            "case_id": event.case_id,
        })

    if event.username:
        user_id = f"user:{event.username.lower()}"
        entities.append({
            "id": user_id,
            "type": "user",
            "name": event.username,
            "attributes": {
                "username": event.username,
                "source_type": event.source_type,
                **({"user_domain": event.user_domain} if event.user_domain else {}),
            },
            "case_id": event.case_id,
        })

    if event.process_name and event.process_id is not None:
        # Include hostname in the process ID to scope it to the originating host
        hostname_key = event.hostname.lower() if event.hostname else "unknown"
        proc_id = f"proc:{hostname_key}:{event.process_id}"
        proc_attrs: dict[str, Any] = {
            "process_name": event.process_name,
            "process_id": event.process_id,
            "hostname": event.hostname,
            "source_type": event.source_type,
        }
        if event.command_line:
            proc_attrs["command_line"] = event.command_line[:256]
        if event.process_executable:
            proc_attrs["process_executable"] = event.process_executable
        if event.parent_process_id is not None:
            proc_attrs["parent_process_id"] = event.parent_process_id
        if event.parent_process_name:
            proc_attrs["parent_process_name"] = event.parent_process_name
        entities.append({
            "id": proc_id,
            "type": "process",
            "name": event.process_name,
            "attributes": proc_attrs,
            "case_id": event.case_id,
        })

    if event.file_path:
        file_id = f"file:{event.file_path}"
        file_attrs: dict[str, Any] = {"file_path": event.file_path}
        if event.file_hash_sha256:
            file_attrs["sha256"] = event.file_hash_sha256
        entities.append({
            "id": file_id,
            "type": "file",
            "name": event.file_path.split("\\")[-1].split("/")[-1] or event.file_path,
            "attributes": file_attrs,
            "case_id": event.case_id,
        })

    if event.dst_ip:
        ip_id = f"ip:{event.dst_ip}"
        ip_attrs: dict[str, Any] = {"ip_address": event.dst_ip}
        if event.dst_port:
            ip_attrs["dst_port"] = event.dst_port
        if event.network_protocol:
            ip_attrs["network_protocol"] = event.network_protocol
        if event.network_direction:
            ip_attrs["network_direction"] = event.network_direction
        entities.append({
            "id": ip_id,
            "type": "ip",
            "name": event.dst_ip,
            "attributes": ip_attrs,
            "case_id": event.case_id,
        })

    if event.domain:
        domain_id = f"domain:{event.domain.lower()}"
        entities.append({
            "id": domain_id,
            "type": "domain",
            "name": event.domain,
            "attributes": {"domain": event.domain},
            "case_id": event.case_id,
        })

    # ------------------------------------------------------------------
    # Build edges
    # ------------------------------------------------------------------

    edge_props_base: dict[str, Any] = {
        "event_id": event.event_id,
        "timestamp": event.timestamp.isoformat() if event.timestamp else None,
    }

    # process → user: "executed_by"
    if proc_id and user_id:
        edges.append({
            "source_type": "process",
            "source_id": proc_id,
            "edge_type": "executed_by",
            "target_type": "user",
            "target_id": user_id,
            "properties": {**edge_props_base},
        })

    # process → host: "ran_on"
    if proc_id and host_id:
        edges.append({
            "source_type": "process",
            "source_id": proc_id,
            "edge_type": "ran_on",
            "target_type": "host",
            "target_id": host_id,
            "properties": {**edge_props_base},
        })

    # process → file: "accessed"
    # Only emit if it looks like a file-related event (not just process name)
    if proc_id and file_id and event.file_path:
        edges.append({
            "source_type": "process",
            "source_id": proc_id,
            "edge_type": "accessed",
            "target_type": "file",
            "target_id": file_id,
            "properties": {**edge_props_base},
        })

    # process → ip: "connected_to"
    if proc_id and ip_id:
        props = {
            **edge_props_base,
            "dst_port": event.dst_port,
            "src_ip": event.src_ip,
            "src_port": event.src_port,
            **({"network_protocol": event.network_protocol} if event.network_protocol else {}),
            **({"event_outcome": event.event_outcome} if event.event_outcome else {}),
        }
        edges.append({
            "source_type": "process",
            "source_id": proc_id,
            "edge_type": "connected_to",
            "target_type": "ip",
            "target_id": ip_id,
            "properties": props,
        })

    # domain → ip: "resolved_to"
    if domain_id and ip_id:
        edges.append({
            "source_type": "domain",
            "source_id": domain_id,
            "edge_type": "resolved_to",
            "target_type": "ip",
            "target_id": ip_id,
            "properties": {**edge_props_base},
        })

    # user → host: "logged_into" (for authentication events)
    if user_id and host_id and not proc_id:
        # Only create direct user→host edge when there's no process to mediate
        if event.event_type in (
            "logon_success", "logon_failure", "logoff",
            "explicit_credential_logon",
        ):
            edges.append({
                "source_type": "user",
                "source_id": user_id,
                "edge_type": "logged_into",
                "target_type": "host",
                "target_id": host_id,
                "properties": {
                    **edge_props_base,
                    "event_type": event.event_type,
                },
            })

    return entities, edges
