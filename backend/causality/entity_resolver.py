"""Entity normalization and canonical ID resolution — Phase 6 Plan 01."""

import re

# Maps logical entity_type names to the raw field key in an event dict
# Field names match NormalizedEvent / normalized_events DuckDB columns
FIELD_MAP = {
    "host": "hostname",
    "user": "username",
    "process": "process_name",
    "ip_src": "src_ip",
    "ip_dst": "dst_ip",
    "domain": "domain",
    "file": "file_path",
}

# Maps entity_type names to canonical ID prefix (when prefix differs from entity_type)
TYPE_PREFIX = {
    "ip_src": "ip",
    "ip_dst": "ip",
}


def resolve_canonical_id(event: dict, entity_type: str) -> str | None:
    """Return a canonical entity ID string for the given entity_type from event.

    The canonical ID has the form ``<prefix>:<normalized_value>``.
    Returns ``None`` if the field is absent or empty.

    Normalization rules:
    - host:    lowercase, strip domain suffix (take first dot-segment)
    - user:    lowercase, strip domain prefix (after backslash) or email suffix (before @)
    - process: lowercase basename (last path segment, split on / and \\)
    - ip_src / ip_dst: strip port if present (keep part before first colon), lowercase
    - domain:  lowercase, strip trailing dot
    - file:    lowercase basename (last path segment, split on / and \\)
    - default: lowercase
    """
    # Look up the raw event field key
    field_key = FIELD_MAP.get(entity_type, entity_type)
    raw_value = event.get(field_key)

    if raw_value is None or raw_value == "":
        return None

    value = str(raw_value)

    if entity_type == "host":
        # lowercase, take first segment before any dot (strips domain suffix)
        normalized = value.lower().split(".")[0]

    elif entity_type == "user":
        # lowercase, strip domain prefix (CORP\jsmith -> jsmith) or email suffix (jsmith@corp.com -> jsmith)
        lower = value.lower()
        if "\\" in lower:
            normalized = lower.rsplit("\\", 1)[-1]
        elif "@" in lower:
            normalized = lower.split("@", 1)[0]
        else:
            normalized = lower

    elif entity_type == "process":
        # lowercase basename — split on both / and \
        parts = re.split(r"[/\\]", value.lower())
        normalized = parts[-1] if parts else value.lower()

    elif entity_type in ("ip_src", "ip_dst"):
        # strip port if present (e.g. 192.168.1.1:443 -> 192.168.1.1)
        normalized = value.split(":")[0].lower()

    elif entity_type == "domain":
        # lowercase, strip trailing dot
        normalized = value.lower().rstrip(".")

    elif entity_type == "file":
        # lowercase basename
        parts = re.split(r"[/\\]", value.lower())
        normalized = parts[-1] if parts else value.lower()

    else:
        normalized = value.lower()

    if not normalized:
        return None

    prefix = TYPE_PREFIX.get(entity_type, entity_type)
    return f"{prefix}:{normalized}"
