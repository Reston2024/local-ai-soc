"""Alert rule engine — Phase 2.

Detection rules fire alerts based on enrichment tags added by the enrichment
pipeline (backend.src.ingestion.enricher) and raw event fields.

Rules in this module:
  - suspicious_dns_query       — enrichment tag 'suspicious_dns' present
  - suspicious_outbound_conn   — enrichment tag 'suspicious_dst_ip' present
  - suspicious_port            — enrichment tag 'suspicious_port:NNNN' present
  - high_severity_syslog       — syslog event with severity critical/high

Adding a new rule: implement a function(event) -> Alert | None, add to _RULES.
"""
import uuid
from backend.src.api.models import NormalizedEvent, Alert


def _alert(event: NormalizedEvent, rule: str, severity: str, description: str) -> Alert:
    return Alert(
        id=str(uuid.uuid4()),
        timestamp=event.timestamp,
        rule=rule,
        severity=severity,
        event_id=event.id,
        description=description,
    )


def rule_suspicious_dns(event: NormalizedEvent) -> Alert | None:
    if "suspicious_dns" in event.enrichments:
        return _alert(event, "suspicious_dns_query", "high",
                      f"DNS query to suspicious domain: {event.query}")
    return None


def rule_suspicious_outbound(event: NormalizedEvent) -> Alert | None:
    if "suspicious_dst_ip" in event.enrichments:
        return _alert(event, "suspicious_outbound_connection", "high",
                      f"Outbound connection to suspicious IP: {event.dst_ip}")
    return None


def rule_suspicious_port(event: NormalizedEvent) -> Alert | None:
    for tag in event.enrichments:
        if tag.startswith("suspicious_port:"):
            port = tag.split(":", 1)[1]
            return _alert(event, "suspicious_port", "high",
                          f"Connection on known-malicious port {port}")
    return None


def rule_high_syslog(event: NormalizedEvent) -> Alert | None:
    if event.source.value == "syslog" and event.severity in ("critical", "high"):
        return _alert(event, "high_severity_syslog", event.severity,
                      f"High-severity syslog from {event.host}: {event.event_type}")
    return None


# Ordered evaluation — first match wins per rule (all run, de-duped by event_id + rule)
_RULES = [
    rule_suspicious_dns,
    rule_suspicious_outbound,
    rule_suspicious_port,
    rule_high_syslog,
]


def evaluate(event: NormalizedEvent) -> list[Alert]:
    """Run all detection rules against event. Returns list of triggered alerts."""
    alerts: list[Alert] = []
    for rule_fn in _RULES:
        result = rule_fn(event)
        if result is not None:
            alerts.append(result)
    return alerts
