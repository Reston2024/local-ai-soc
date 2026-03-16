"""Enrichment pipeline — Phase 2.

Adds analyst-readable tags to NormalizedEvent.enrichments.
Runs BEFORE the detection/rules engine so detection can use enrichment tags.

Enrichments are non-alerting labels that describe what an event IS.
Detection rules decide whether to alert based on enrichments + raw fields.

Enrichers in this module:
  - enrich_suspicious_dns     — known-bad domain list
  - enrich_suspicious_ip      — known-bad IP list
  - enrich_suspicious_port    — common C2/malware ports
  - enrich_private_src        — marks RFC1918 source IPs
  - enrich_external_dst       — marks non-RFC1918 destination IPs

Run all via:  enrich(event) → NormalizedEvent  (mutates enrichments in place)
"""
import re
from backend.src.api.models import NormalizedEvent

# --- Threat Intelligence Lists (Phase 2 — local, no external feed yet) -----
# Phase 3 will wire to an actual TI feed via Ollama tool-use or static CSV.

SUSPICIOUS_DOMAINS: frozenset[str] = frozenset({
    "suspicious-domain.test",
    "malware.example",
    "c2.evil.test",
    # Add Phase 3 TI feed entries here
})

SUSPICIOUS_IPS: frozenset[str] = frozenset({
    "9.9.9.9",
    "198.51.100.1",
    "203.0.113.1",
    # Add Phase 3 TI feed entries here
})

# Common C2 / reverse-shell / malware ports
SUSPICIOUS_PORTS: frozenset[int] = frozenset({
    4444,    # Metasploit default
    1337,    # common backdoor
    8888,    # alt HTTP C2
    9001,    # Tor relay
    6667,    # IRC C2
    6660, 6661, 6662, 6663, 6664, 6665, 6666, 6668, 6669,  # IRC range
    31337,   # "elite" port
})

# RFC1918 private address ranges
_PRIVATE = re.compile(
    r"^(10\.|172\.(1[6-9]|2[0-9]|3[01])\.|192\.168\.)"
)


def _is_private(ip: str | None) -> bool:
    return bool(ip and _PRIVATE.match(ip))


def enrich_suspicious_dns(event: NormalizedEvent) -> None:
    if event.event_type == "dns_query" and event.query in SUSPICIOUS_DOMAINS:
        event.enrichments.append("suspicious_dns")


def enrich_suspicious_ip(event: NormalizedEvent) -> None:
    if event.src_ip in SUSPICIOUS_IPS:
        event.enrichments.append("suspicious_src_ip")
    if event.dst_ip in SUSPICIOUS_IPS:
        event.enrichments.append("suspicious_dst_ip")


def enrich_suspicious_port(event: NormalizedEvent) -> None:
    if event.port and event.port in SUSPICIOUS_PORTS:
        event.enrichments.append(f"suspicious_port:{event.port}")


def enrich_private_src(event: NormalizedEvent) -> None:
    if _is_private(event.src_ip):
        event.enrichments.append("src_private")


def enrich_external_dst(event: NormalizedEvent) -> None:
    if event.dst_ip and not _is_private(event.dst_ip):
        event.enrichments.append("dst_external")


# Pipeline — ordered by specificity
_PIPELINE = [
    enrich_suspicious_dns,
    enrich_suspicious_ip,
    enrich_suspicious_port,
    enrich_private_src,
    enrich_external_dst,
]


def enrich(event: NormalizedEvent) -> NormalizedEvent:
    """Run all enrichers against event. Mutates event.enrichments. Returns event."""
    for fn in _PIPELINE:
        fn(event)
    return event
