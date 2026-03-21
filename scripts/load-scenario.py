#!/usr/bin/env python3
"""
Load the APT scenario fixture and run detection.

Usage:
    uv run python scripts/load-scenario.py

Requires the backend to be running on http://localhost:8000
"""
import json
import sys
from pathlib import Path

import httpx


BASE_URL = "http://localhost:8000"
FIXTURE_PATH = Path(__file__).parent.parent / "fixtures" / "ndjson" / "apt_scenario.ndjson"


def main():
    print("[*] Loading APT scenario fixture...")

    if not FIXTURE_PATH.exists():
        print(f"[!] Fixture not found: {FIXTURE_PATH}")
        sys.exit(1)

    events = []
    with FIXTURE_PATH.open() as f:
        for line in f:
            line = line.strip()
            if line:
                events.append(json.loads(line))

    print(f"[*] Loaded {len(events)} events from fixture")

    with httpx.Client(timeout=30) as client:
        # Bulk ingest — endpoint accepts a JSON array of NormalizedEvent objects
        resp = client.post(f"{BASE_URL}/api/ingest/events", json=events)
        if resp.status_code == 201:
            result = resp.json()
            print(
                f"[+] Ingested: parsed={result.get('parsed', 0)}, "
                f"loaded={result.get('loaded', 0)}, "
                f"embedded={result.get('embedded', 0)}, "
                f"edges={result.get('edges_created', 0)}"
            )
        else:
            print(f"[!] Ingest failed: {resp.status_code} {resp.text}")
            sys.exit(1)

        # Fetch detections created by the ingestion pipeline's Sigma matching
        print("[*] Fetching Sigma detections...")
        resp = client.get(f"{BASE_URL}/api/detect?limit=50")
        if resp.status_code == 200:
            result = resp.json()
            detections = result.get("detections", [])
            print(f"[+] Detections in DB: {len(detections)}")
            for d in detections:
                print(
                    f"    [{d.get('severity', '?').upper()}] "
                    f"{d.get('rule_name')} — {d.get('attack_technique')}"
                )
        else:
            print(f"[!] Detection fetch failed: {resp.status_code} {resp.text}")

        # Show events
        resp = client.get(f"{BASE_URL}/api/events?page_size=20")
        if resp.status_code == 200:
            result = resp.json()
            print(f"[+] Total events in DB: {result.get('total', 0)}")

    print("[+] Done. Visit https://localhost/app/ to investigate.")


if __name__ == "__main__":
    main()
