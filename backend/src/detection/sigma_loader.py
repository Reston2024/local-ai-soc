"""Sigma rule loader — Phase 3.

Loads YAML Sigma rules from backend/src/detection/sigma/ and compiles
each to a Python callable: (NormalizedEvent) -> Alert | None.

This uses direct Python attribute matching against NormalizedEvent fields.
Full pySigma DuckDB backend (SQL compilation) is deferred to Phase 4.

Integration:
    from backend.src.detection.sigma_loader import load_sigma_rules
    _SIGMA_RULES = load_sigma_rules()
    # Then in _store_event: call each fn, collect non-None results
"""
import uuid
import logging
import yaml
from pathlib import Path

logger = logging.getLogger(__name__)

_SIGMA_DIR = Path(__file__).parent / "sigma"

# Sigma level -> severity string mapping
_LEVEL_MAP = {
    "critical": "critical",
    "high": "high",
    "medium": "medium",
    "low": "low",
    "informational": "info",
}

# Sigma field name -> NormalizedEvent attribute name
# Handles both our custom field names and Sigma canonical Windows names.
_FIELD_TO_ATTR = {
    "query": "query",
    "QueryName": "query",        # Sigma DNS canonical (Windows Sysmon)
    "host": "host",
    "src_ip": "src_ip",
    "dst_ip": "dst_ip",
    "event_type": "event_type",
    "user": "user",
    "port": "port",
    "protocol": "protocol",
    "severity": "severity",
}


def _get_event_field(event, field_name: str):
    """Resolve a Sigma field name to a NormalizedEvent attribute value."""
    attr = _FIELD_TO_ATTR.get(field_name, field_name.lower())
    return getattr(event, attr, None)


def _make_rule_fn(rule_id: str, rule_title: str, level: str, detection: dict):
    """Compile a parsed Sigma detection block into a callable.

    Supports:
      selection.<field>: <value>           — exact match (case-insensitive)
      selection.<field>|contains: <value>  — substring match
      selection.<field>|contains: [<v1>, <v2>]  — any substring match
    condition must be 'selection' (only supported condition in Phase 3).
    """
    selection = detection.get("selection", {})
    severity = _LEVEL_MAP.get(level, "medium")

    def rule_fn(event):
        from backend.src.api.models import Alert as _Alert
        for raw_field, value in selection.items():
            # Parse field modifier (e.g. "query|contains" -> field="query", op="contains")
            if "|" in raw_field:
                field, modifier = raw_field.split("|", 1)
            else:
                field, modifier = raw_field, "exact"

            ev_val = _get_event_field(event, field)
            if ev_val is None:
                return None  # field not present on event — rule does not match

            ev_str = str(ev_val).lower()

            if modifier == "contains":
                values = value if isinstance(value, list) else [value]
                if not any(str(v).lower() in ev_str for v in values):
                    return None
            else:
                # exact match (case-insensitive)
                values = value if isinstance(value, list) else [value]
                if not any(str(v).lower() == ev_str for v in values):
                    return None

        # All selection conditions matched
        return _Alert(
            id=str(uuid.uuid4()),
            timestamp=event.timestamp,
            rule=rule_id,
            severity=severity,
            event_id=event.id,
            description=f"Sigma rule '{rule_title}' matched",
        )

    rule_fn.__name__ = f"sigma_{rule_id}"
    return rule_fn


def load_sigma_rules() -> list:
    """Scan sigma/ directory, load YAML rules, return compiled callables.

    Returns empty list if sigma/ is missing or all rules fail to parse.
    Never raises — logs warnings for individual failures.
    """
    if not _SIGMA_DIR.exists():
        logger.warning("Sigma rules directory not found: %s", _SIGMA_DIR)
        return []

    rules = []
    for yml_path in sorted(_SIGMA_DIR.glob("*.yml")):
        try:
            with open(yml_path, encoding="utf-8") as f:
                rule_data = yaml.safe_load(f)

            rule_id = rule_data.get("id", "")
            rule_title = rule_data.get("title", yml_path.stem)
            level = rule_data.get("level", "medium")
            detection = rule_data.get("detection", {})

            if not rule_id:
                logger.warning("Sigma rule %s missing 'id' field — skipping", yml_path.name)
                continue
            if not detection:
                logger.warning("Sigma rule %s missing 'detection' block — skipping", yml_path.name)
                continue

            condition = detection.get("condition", "")
            if condition != "selection":
                logger.warning(
                    "Sigma rule %s uses unsupported condition '%s' — skipping (only 'selection' supported in Phase 3)",
                    yml_path.name, condition,
                )
                continue

            rule_fn = _make_rule_fn(rule_id, rule_title, level, detection)
            rules.append(rule_fn)
            logger.info("Loaded Sigma rule: %s (%s)", rule_title, rule_id)

        except Exception as exc:
            logger.warning("Failed to load Sigma rule %s: %s", yml_path.name, exc)

    return rules
