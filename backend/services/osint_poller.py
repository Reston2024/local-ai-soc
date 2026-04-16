"""
osint_poller.py — Background task for SpiderFoot scan lifecycle management (Phase 51).

poll_to_completion() is started via asyncio.create_task() after /startscan.
Uses deadline-based polling (Phase 45 pattern) — never asyncio.wait_for().
On FINISHED: harvests findings from SpiderFoot REST API, cross-references MISP,
triggers DNSTwist for every DOMAIN_NAME finding, persists all results.
On timeout: stops scan, marks TIMEOUT in SQLite.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from backend.core.logging import get_logger
from backend.services.spiderfoot_client import SpiderFootClient
from backend.services.dnstwist_service import run_dnstwist

log = get_logger(__name__)

TERMINAL_STATES = {"FINISHED", "ERROR-FAILED", "ABORTED"}


def _now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


async def poll_to_completion(
    scan_id: str,
    client: SpiderFootClient,
    osint_store,
    timeout_seconds: int = 1800,
    poll_interval: int = 15,
) -> None:
    """
    Poll SpiderFoot scan status until terminal state or timeout.
    Runs as an asyncio background task.
    """
    loop = asyncio.get_event_loop()
    deadline = loop.time() + timeout_seconds

    while loop.time() < deadline:
        await asyncio.sleep(poll_interval)
        try:
            status = await client.get_status(scan_id)
        except Exception as exc:
            log.warning("poll_status failed", scan_id=scan_id, error=str(exc))
            continue

        if status in TERMINAL_STATES:
            completed_at = _now()
            if status == "FINISHED":
                try:
                    await _harvest_and_store(scan_id, client, osint_store)
                except Exception as exc:
                    log.error("harvest_and_store failed", scan_id=scan_id, error=str(exc))
            await asyncio.to_thread(
                osint_store.update_investigation_status,
                scan_id, status, completed_at,
            )
            return

    # Deadline exceeded — stop scan
    log.warning("scan timeout reached", scan_id=scan_id)
    await client.stop_scan(scan_id)
    await asyncio.to_thread(
        osint_store.update_investigation_status,
        scan_id, "TIMEOUT", _now(),
    )


async def _harvest_and_store(
    scan_id: str,
    client: SpiderFootClient,
    osint_store,
) -> None:
    """Fetch all SpiderFoot findings, MISP cross-ref, DNSTwist for domains."""
    # Get summary: list of [eventtype, count, ...] arrays
    summary = await client.get_summary(scan_id)
    event_types = [row[0] for row in summary if row and len(row) > 1 and int(row[1] or 0) > 0]

    findings = []
    for etype in event_types:
        try:
            rows = await client.get_events(scan_id, etype)
            for row in rows:
                if not row:
                    continue
                findings.append({
                    "investigation_id": scan_id,
                    "event_type": etype,
                    "source_module": row[0] if len(row) > 0 else None,
                    "data": row[2] if len(row) > 2 else "",
                    "confidence": float(row[4]) if len(row) > 4 else 1.0,
                    "misp_hit": 0,
                    "misp_event_ids": [],
                })
        except Exception as exc:
            log.warning("get_events failed", scan_id=scan_id, etype=etype, error=str(exc))

    # MISP cross-reference bulk query
    if findings:
        ioc_values = list({f["data"] for f in findings if f["data"]})
        try:
            misp_hits = await asyncio.to_thread(osint_store.bulk_query_ioc_cache, ioc_values)
            misp_map = {h["value"]: h for h in misp_hits}
            for f in findings:
                if f["data"] in misp_map:
                    f["misp_hit"] = 1
                    f["misp_event_ids"] = [misp_map[f["data"]].get("feed_source", "misp")]
        except Exception as exc:
            log.warning("misp_crossref failed", scan_id=scan_id, error=str(exc))

    # Persist findings
    if findings:
        await asyncio.to_thread(osint_store.bulk_insert_osint_findings, findings)

    # DNSTwist: auto-run for every unique DOMAIN_NAME finding
    domains = list({f["data"] for f in findings if f["event_type"] == "DOMAIN_NAME" and f["data"]})
    for domain in domains[:20]:  # cap at 20 domains to bound scan time
        try:
            lookalikes = await run_dnstwist(domain)
            if lookalikes:
                rows = [
                    {
                        "investigation_id": scan_id,
                        "seed_domain": domain,
                        "fuzzer": lk.get("fuzzer"),
                        "lookalike_domain": lk.get("domain", ""),
                        "dns_a": str(lk.get("dns_a", "")) or None,
                        "dns_mx": str(lk.get("dns_mx", "")) or None,
                        "whois_registrar": lk.get("whois_registrar"),
                        "whois_created": lk.get("whois_created"),
                    }
                    for lk in lookalikes
                    if lk.get("domain")
                ]
                if rows:
                    await asyncio.to_thread(osint_store.bulk_insert_dnstwist_findings, rows)
        except Exception as exc:
            log.warning("dnstwist failed", scan_id=scan_id, domain=domain, error=str(exc))

    # Update result_summary counts
    type_counts = {}
    for f in findings:
        type_counts[f["event_type"]] = type_counts.get(f["event_type"], 0) + 1
    await asyncio.to_thread(
        osint_store.update_investigation_status,
        scan_id, "FINISHED", _now(), None, type_counts,
    )
