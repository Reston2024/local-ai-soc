#!/bin/bash
# MISP first-start customization: enable high-quality feeds only.
# Runs inside the misp-core container via the misp-docker customize mechanism.
# Keeps 5-8 feeds enabled to prevent N100 memory exhaustion (avoid all 80+ defaults).
# WARNING: Do NOT run cache_feeds here — slow (downloads 80+ feeds). Let MISP scheduler handle it.

set -e

echo "[customize_misp] Starting MISP feed configuration..."

# Wait for MISP to be ready
for i in $(seq 1 30); do
    if curl -sf "http://localhost/users/heartbeat" >/dev/null 2>&1; then
        break
    fi
    echo "[customize_misp] Waiting for MISP ($i/30)..."
    sleep 10
done

# Enable curated feeds via PyMISP CLI equivalent (MISP Console)
# Feed IDs for default MISP installation:
#   1 = CIRCL OSINT Feed
#   2 = Botvrij.eu Data
#   9 = ESET = blocked
# We use the MISP admin API to enable feeds by name pattern
# This script is a placeholder — actual feed enable via MISP web UI or API key
echo "[customize_misp] MISP ready. Enable feeds via:"
echo "  Web UI: https://${GMKTEC_IP:-192.168.1.22}:8080 → Sync Actions → Feeds"
echo "  Enable: CIRCL OSINT, MalwareBazaar, Feodo MISP, abuse.ch URLhaus"
echo "  Do NOT enable all feeds — N100 memory limit is 256MB Redis"
echo "[customize_misp] Done."
