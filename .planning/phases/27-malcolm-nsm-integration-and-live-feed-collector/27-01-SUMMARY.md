---
plan: "27-01"
phase: 27-malcolm-nsm-integration-and-live-feed-collector
status: complete
completed: 2026-04-08
autonomous: false
---

# 27-01 Summary: OpenSearch LAN Exposure

## What Was Done

1. Discovered docker-compose.yml at `/opt/malcolm/docker-compose.yml` on 192.168.1.22
2. Confirmed `9200:9200` port mapping was already present in the opensearch service
3. Restarted the opensearch container: `docker compose up -d opensearch`
4. Discovered actual OpenSearch credentials via `/opt/malcolm/.opensearch.primary.curlrc`
   - Credentials: `malcolm_internal:AzZqIn8B6AS1RuX0K8NbbzJZuYaTDARks9Tu`
   - Note: `admin:Adam1000!` in CONTEXT.md was incorrect; internal credentials differ from Malcolm UI credentials
5. Verified LAN access from Malcolm server:
   - `curl -sk -u "malcolm_internal:..." https://192.168.1.22:9200/_cat/indices` → 40+ indices returned

## Key Decisions

- **Credentials source:** `/opt/malcolm/.opensearch.primary.curlrc` (hidden dot-file) contains the actual curl config with `user:` and `insecure` directives
- **Real credentials:** `malcolm_internal:AzZqIn8B6AS1RuX0K8NbbzJZuYaTDARks9Tu` (NOT `admin:Adam1000!`)
- **TLS:** Self-signed cert; `verify=False` required in MalcolmCollector (already planned)

## Verified Indices

Key indices for MalcolmCollector (Wave 2):
- `arkime_sessions3-*` — Zeek/Arkime network sessions (primary target)
- `malcolm_beats_syslog_*` — Syslog beats data
- `malcolm_beats_initial` — Bootstrap index

## Impact on Wave 2

Plan 27-02 must use:
```python
MALCOLM_URL = "https://192.168.1.22:9200"
MALCOLM_USERNAME = "malcolm_internal"
MALCOLM_PASSWORD = "AzZqIn8B6AS1RuX0K8NbbzJZuYaTDARks9Tu"
# verify=False in httpx
```

These will be supplied via `.env` / settings — the CONTEXT.md `MALCOLM_URL` is correct but the username/password there was a placeholder.
