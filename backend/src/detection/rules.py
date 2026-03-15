"""Simple alert rule engine — Phase 1 only (not production coverage)."""
import uuid
from backend.src.api.models import NormalizedEvent, Alert

SUSPICIOUS_DOMAINS = {"suspicious-domain.test", "malware.example", "c2.evil.test"}
SUSPICIOUS_IPS = {"9.9.9.9", "198.51.100.1", "203.0.113.1"}

def evaluate(event: NormalizedEvent) -> list[Alert]:
    alerts = []

    if event.event_type == "dns_query" and event.query in SUSPICIOUS_DOMAINS:
        alerts.append(Alert(
            id=str(uuid.uuid4()),
            timestamp=event.timestamp,
            rule="suspicious_dns_query",
            severity="high",
            event_id=event.id,
            description=f"DNS query to suspicious domain: {event.query}",
        ))

    if event.dst_ip in SUSPICIOUS_IPS:
        alerts.append(Alert(
            id=str(uuid.uuid4()),
            timestamp=event.timestamp,
            rule="suspicious_outbound_connection",
            severity="high",
            event_id=event.id,
            description=f"Outbound connection to suspicious IP: {event.dst_ip}",
        ))

    return alerts
