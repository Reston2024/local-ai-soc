# Phase 34: MITRE ATT&CK + Actor Intelligence + Asset Inventory — Research

**Researched:** 2026-04-10
**Domain:** MITRE ATT&CK STIX 2.1 parsing, SQLite CRUD patterns, Svelte 5 inline expansion UX, Sigma tag extraction
**Confidence:** HIGH (all critical findings verified against codebase + official MITRE sources)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Asset table is IP-centric (primary key = IP address). Hostname is display label, may be null.
- Asset row shows exactly: hostname, risk_score (0–100), last_seen, alert_count.
- Asset detail panel: inline expansion (same pattern as HuntingView OSINT panel). Three blocks: event timeline (last 10), associated detections, OSINT enrichment (reuse GET /api/osint/{ip}).
- Internal/external tag computed at upsert time using `ipaddress` module RFC1918 + loopback check. Stored in asset record.
- Actor matching is ON-DEMAND only (not at-ingest). GET /api/attack/actor-matches. Top-3 groups by TTP overlap %, confidence: ≥60%=High, 30–59%=Medium, <30%=Low.
- ATT&CK heatmap: 14-column grid (one tactic per column), heat-scale by rule coverage count. Click tactic expands inline list of techniques. Colours: 0=#333, 1-2=#7a4400, 3-9=#c96a00, 10+=#e84a00.
- Coverage heatmap uses Sigma rule ATT&CK tags only — NOT fired detections. A rule is "covered" if it exists on disk with attack.tXXXX tags.
- STIX download is startup-time only; skip if attack_techniques table has >0 rows. No hot-reload.
- No open_ports, OS fingerprinting, or service discovery in Phase 34. Asset data from normalized events only.
- ATT&CK Coverage is a new view under Intelligence sidebar nav, between Threat Intel and Threat Map.

### Claude's Discretion
- Exact SQLite DDL for assets, attack_techniques, attack_groups, attack_group_techniques tables.
- Whether actor matching endpoint is called from AssetsView header or a dedicated sidebar widget.
- STIX JSON download strategy (prefer startup download with 24h SQLite cache).
- Asset risk score formula (combine alert_count + ioc_matched + detection severity; exact weights).
- ATT&CK Coverage view placement of expanded technique list (below column header, inline).

### Deferred Ideas (OUT OF SCOPE)
- P34-T05: Campaign clustering (Phase 35)
- P34-T06: Diamond Model view / CampaignView.svelte (Phase 35)
- P34-T10: UEBA baseline engine (Phase 35)
- P34-T11: Actor profile cards / CampaignView nav item (Phase 35)
- ATT&CK sub-technique drill-down (Phase 35)
- Coverage trend over time (Future)
- Asset timeline pagination (Phase 34 shows last 10 only)
- Open port / service inventory (Phase 36)
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| P34-T01 | Download and parse MITRE ATT&CK Enterprise STIX 2.1 JSON → SQLite (attack_techniques, attack_groups, attack_group_techniques) | STIX bundle structure verified; raw download URL confirmed; Python parse pattern documented |
| P34-T02 | Auto-tag DetectionRecords with ATT&CK technique IDs on detection fire (from Sigma rule tags) | Sigma tag format confirmed (attack.tXXXX); pySigma SigmaRule.tags access pattern documented |
| P34-T03 | Actor profile matching — score each ATT&CK group by TTP overlap %, surface top-3 with confidence label | Jaccard-style overlap formula; on-demand only; SQLite group→technique join query pattern |
| P34-T04 | ATT&CK coverage heatmap — GET /api/attack/coverage + AttackCoverageView.svelte | Sigma rule scanner pattern; existing MITRE_TACTICS list in analytics.py confirmed; heatmap colour scale defined |
| P34-T07 | Asset store upsert pipeline — on every normalized event upsert src_ip/dst_ip as assets | _apply_ioc_matching() pattern directly reusable; asyncio.to_thread threading constraint verified |
| P34-T08 | Assets API — GET /api/assets, GET /api/assets/{id}, POST /api/assets/{id}/tag | intel.py router pattern confirmed; existing AssetsView.svelte shell needs full rewrite |
| P34-T09 | AssetsView.svelte — live asset table with detail panel | ThreatIntelView.svelte expand/collapse UX confirmed as template; existing AssetsView.svelte is coverage shell — must be replaced |
</phase_requirements>

---

## Summary

Phase 34 adds three integrated capabilities to AI-SOC-Brain: (1) a real asset inventory built from network telemetry, (2) ATT&CK technique tagging on every detection with actor group scoring, and (3) a new heatmap view showing Sigma rule coverage across the ATT&CK matrix.

The codebase already has strong templates for all three capabilities. `IocStore` + `_apply_ioc_matching()` in `loader.py` is the exact pattern for asset upsert. `backend/api/intel.py` is the exact template for the two new API routers. `ThreatIntelView.svelte` is the exact UX template for `AssetsView.svelte`'s expandable rows. The existing `analytics.py` already defines `MITRE_TACTICS` in the correct 14-tactic order — the new `attack.py` router can import and reuse that constant.

A critical discovery: `AssetsView.svelte` already exists as a coverage/health shell from an earlier phase. It must be completely replaced with the IP-centric asset table. The existing `backend/api/analytics.py` has a `mitre-coverage` endpoint that cross-references fired detections and playbooks — the new `GET /api/attack/coverage` endpoint differs in that it scans Sigma rule YAML files on disk, not fired detections.

**Primary recommendation:** Build `AssetStore` as a direct copy of `IocStore` (same in-memory testable pattern). Use `_apply_ioc_matching()` as the exact integration point in `loader.py` for asset upsert. Reuse `MITRE_TACTICS` from `analytics.py`. Download STIX from `https://raw.githubusercontent.com/mitre-attack/attack-stix-data/master/enterprise-attack/enterprise-attack.json`.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `httpx` | already pinned | Download ATT&CK STIX JSON at startup | Already used by OllamaClient; async + connection pooling |
| `sqlite3` | stdlib | AssetStore, AttackStore SQLite CRUD | Pattern established by IocStore; no external dep needed |
| `ipaddress` | stdlib | RFC1918 / loopback classification | Already used in `backend/services/osint.py._sanitize_ip()` |
| `pySigma` | already pinned | Parse Sigma rule YAML to extract ATT&CK tags | Already used by detections/matcher.py |
| `re` | stdlib | Extract technique IDs from Sigma tag strings | Zero-dep; pattern is `^attack\\.t(\\d{4})` |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `pathlib.Path` | stdlib | Scan `detections/rules/` dir for Sigma YAML files | Coverage scan in P34-T04 |
| `json` | stdlib | Parse STIX bundle objects; serialize group technique lists | Throughout |
| `asyncio.to_thread` | stdlib | Wrap all synchronous SQLite calls from async route handlers | Established pattern |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `httpx` for STIX download | `requests` | `httpx` is already imported; async-first avoids blocking event loop on startup |
| Raw STIX JSON parse | `mitreattack-python` library | mitreattack-python is a 3rd-party dep; raw JSON parse is ~30 lines and fully controllable |
| `sqlite3` direct | `SQLiteStore` wrapper | IocStore wraps `sqlite3.Connection` directly for in-memory testability — follow same pattern |

**Installation:**
```bash
# No new dependencies required — all needed libraries are already in pyproject.toml
# Verify: httpx, pySigma, sqlite3 (stdlib), ipaddress (stdlib)
```

---

## Architecture Patterns

### Recommended Project Structure (new files only)
```
backend/
├── services/
│   └── attack/
│       ├── asset_store.py          # AssetStore — SQLite CRUD (mirrors ioc_store.py)
│       └── attack_store.py         # AttackStore — STIX download, parse, SQLite CRUD
├── api/
│   ├── assets.py                   # GET /api/assets, GET /api/assets/{id}, POST /api/assets/{id}/tag
│   └── attack.py                   # GET /api/attack/coverage, GET /api/attack/actor-matches
dashboard/src/views/
├── AssetsView.svelte               # FULL REWRITE — replace existing coverage shell
└── AttackCoverageView.svelte       # NEW — 14-col heatmap + inline technique drill-down
```

### Pattern 1: AssetStore — mirrors IocStore exactly

**What:** Synchronous SQLite CRUD class wrapping `sqlite3.Connection` directly. All methods called via `asyncio.to_thread()` from async route handlers. Constructor accepts connection for in-memory testability.

**When to use:** Any time an asset needs upserting from a normalized event, or the API needs asset list/detail queries.

```python
# Source: codebase — backend/services/intel/ioc_store.py (exact template)
class AssetStore:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def upsert_asset(
        self,
        ip: str,
        hostname: Optional[str],
        tag: str,           # "internal" | "external"
        last_seen: str,     # ISO8601
    ) -> None:
        """
        INSERT OR REPLACE into assets table.
        risk_score is recomputed in a separate pass (or at query time via alert_count JOIN).
        """
        self._conn.execute(
            """
            INSERT INTO assets (ip, hostname, tag, last_seen, first_seen)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(ip) DO UPDATE SET
                hostname = COALESCE(excluded.hostname, assets.hostname),
                tag      = excluded.tag,
                last_seen = excluded.last_seen
            """,
            (ip, hostname, tag, last_seen, last_seen),
        )
        self._conn.commit()
```

### Pattern 2: Asset classification using existing `_sanitize_ip` logic

**What:** Reuse the `ipaddress` module check from `osint.py` to classify IPs as internal/external at upsert time.

**When to use:** Inside `upsert_asset()` or the loader helper that calls it.

```python
# Source: codebase — backend/services/osint.py._sanitize_ip() (verified)
import ipaddress

def _classify_ip(ip: str) -> str:
    """Return 'internal' for RFC1918/loopback, 'external' otherwise."""
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return "external"   # malformed → treat as external
    if addr.is_loopback or addr.is_private:
        return "internal"
    return "external"
```

### Pattern 3: Asset upsert in loader.py — follows `_apply_ioc_matching` exactly

**What:** Synchronous helper called inside the existing `asyncio.to_thread()` block in `ingest_events()`. Safe to write to SQLite directly (no nested to_thread needed).

**When to use:** After IOC matching, before returning the normalized event batch to DuckDB INSERT.

```python
# Source: codebase — ingestion/loader.py._apply_ioc_matching() (exact integration point)
def _apply_asset_upsert(event: NormalizedEvent, asset_store: AssetStore) -> None:
    """Upsert src_ip and dst_ip as assets. Called inside asyncio.to_thread() block."""
    now = datetime.now(timezone.utc).isoformat()
    for ip in filter(None, [event.src_ip, event.dst_ip]):
        tag = _classify_ip(ip)
        asset_store.upsert_asset(
            ip=ip,
            hostname=event.hostname,
            tag=tag,
            last_seen=now,
        )
```

### Pattern 4: STIX JSON download + parse

**What:** Fetch STIX bundle from GitHub at app startup (inside lifespan, after SQLite store is ready). Skip if `attack_techniques` table already has rows. Parse three STIX object types: `attack-pattern` (technique), `intrusion-set` (group), `relationship` (group→technique uses).

**When to use:** `AttackStore.bootstrap_from_stix()` called in lifespan, similar to playbook seeding.

```python
# Source: MITRE attack-stix-data USAGE.md + codebase lifespan pattern
STIX_URL = (
    "https://raw.githubusercontent.com/mitre-attack/attack-stix-data"
    "/master/enterprise-attack/enterprise-attack.json"
)

async def bootstrap_attack_data(attack_store: AttackStore, http_client: httpx.AsyncClient):
    if attack_store.technique_count() > 0:
        return   # already seeded — 24h cache implicitly satisfied
    resp = await http_client.get(STIX_URL, timeout=30.0)
    bundle = resp.json()
    objects = bundle["objects"]  # list of STIX 2.1 objects

    # Index by STIX id for relationship resolution
    by_id = {obj["id"]: obj for obj in objects}

    # Extract techniques (attack-pattern, not sub-techniques)
    techniques = [
        obj for obj in objects
        if obj.get("type") == "attack-pattern"
        and not obj.get("x_mitre_is_subtechnique", False)
        and not obj.get("revoked", False)
    ]
    for t in techniques:
        ext_refs = t.get("external_references", [])
        tech_id = next(
            (r["external_id"] for r in ext_refs if r.get("source_name") == "mitre-attack"),
            None
        )
        if not tech_id:
            continue
        # Tactic from kill_chain_phases (may be multiple — take first)
        phases = t.get("kill_chain_phases", [])
        tactic = phases[0]["phase_name"] if phases else "unknown"
        attack_store.upsert_technique(tech_id=tech_id, name=t["name"], tactic=tactic)

    # Extract groups (intrusion-set, not revoked)
    groups = [
        obj for obj in objects
        if obj.get("type") == "intrusion-set"
        and not obj.get("revoked", False)
    ]
    for g in groups:
        ext_refs = g.get("external_references", [])
        group_id = next(
            (r["external_id"] for r in ext_refs if r.get("source_name") == "mitre-attack"),
            None
        )
        aliases = g.get("aliases", [])
        attack_store.upsert_group(
            stix_id=g["id"],
            group_id=group_id or g["id"],
            name=g["name"],
            aliases=json.dumps(aliases),
        )

    # Extract relationships: intrusion-set --uses--> attack-pattern
    rels = [
        obj for obj in objects
        if obj.get("type") == "relationship"
        and obj.get("relationship_type") == "uses"
        and not obj.get("revoked", False)
    ]
    for rel in rels:
        src = by_id.get(rel["source_ref"], {})
        tgt = by_id.get(rel["target_ref"], {})
        if src.get("type") == "intrusion-set" and tgt.get("type") == "attack-pattern":
            # resolve technique ID
            ext = tgt.get("external_references", [])
            tech_id = next(
                (r["external_id"] for r in ext if r.get("source_name") == "mitre-attack"),
                None
            )
            if tech_id:
                attack_store.upsert_group_technique(
                    stix_group_id=src["id"],
                    tech_id=tech_id,
                )
```

### Pattern 5: Sigma ATT&CK tag extraction

**What:** Sigma rule YAML files use tags like `attack.t1059` and `attack.t1059.001` for techniques, and `attack.execution` for tactics. To extract technique IDs, scan `rule.tags` for items matching `^attack\.t\d{4}`. The pySigma `SigmaRule` object exposes tags as `rule.tags` (a list of `SigmaTag` objects with `.name` string attribute).

**When to use:** (a) Coverage scan — scan all `.yml` files in `detections/rules/`. (b) Detection tagging — in `detections/matcher.py` after a rule match fires.

```python
# Source: Sigma tag format verified via sigmahq.io docs + pySigma rule object
import re
from sigma.rule import SigmaRule
from pathlib import Path

_TECH_RE = re.compile(r"^attack\.(t\d{4})(?:\.\d+)?$", re.IGNORECASE)

def extract_attack_techniques_from_rule(rule: SigmaRule) -> list[str]:
    """Return list of T-IDs (e.g. ['T1059', 'T1027']) from a parsed SigmaRule."""
    techniques = []
    for tag in rule.tags:
        m = _TECH_RE.match(tag.name)
        if m:
            techniques.append(m.group(1).upper())  # normalise to "T1059"
    return techniques

def scan_rules_dir_for_coverage(rules_dir: Path) -> dict[str, list[str]]:
    """
    Returns {technique_id: [rule_title, ...]} for all rules with ATT&CK tags.
    Runs synchronously — call via asyncio.to_thread from async handler.
    """
    coverage: dict[str, list[str]] = {}
    for yml_path in rules_dir.rglob("*.yml"):
        try:
            yaml_text = yml_path.read_text(encoding="utf-8")
            rule = SigmaRule.from_yaml(yaml_text)
            for tech_id in extract_attack_techniques_from_rule(rule):
                coverage.setdefault(tech_id, []).append(rule.title)
        except Exception:
            pass  # malformed rules silently skipped
    return coverage
```

### Pattern 6: API router structure — follows intel.py exactly

**What:** All new API endpoints follow the `backend/api/intel.py` pattern: `APIRouter()`, async functions with `request: Request`, `asyncio.to_thread()` for SQLite calls, `dependencies=[Depends(verify_token)]` applied at `include_router()` in `main.py`.

```python
# Source: codebase — backend/api/intel.py (exact template)
# backend/api/assets.py
from fastapi import APIRouter, Depends, Request
from backend.core.auth import verify_token
import asyncio

router = APIRouter()

@router.get("/assets", dependencies=[Depends(verify_token)])
async def list_assets(request: Request, limit: int = 200):
    assets = await asyncio.to_thread(request.app.state.asset_store.list_assets, limit)
    return assets

@router.get("/assets/{ip}", dependencies=[Depends(verify_token)])
async def get_asset(ip: str, request: Request):
    asset = await asyncio.to_thread(request.app.state.asset_store.get_asset, ip)
    if asset is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Asset not found")
    return asset
```

### Pattern 7: Svelte 5 expandable row — follows ThreatIntelView.svelte exactly

**What:** `$state<string | null>(null)` for `expandedIp`, toggle function, `{#if expandedIp === asset.ip}` renders inline detail panel. API calls use typed `api.assets.list()` / `api.assets.get(ip)` methods.

**When to use:** AssetsView.svelte row expansion + AttackCoverageView.svelte tactic column expansion.

```typescript
// Source: codebase — dashboard/src/views/ThreatIntelView.svelte (exact pattern)
let expandedIp = $state<string | null>(null)

function toggleExpand(ip: string) {
  expandedIp = expandedIp === ip ? null : ip
}
// In template:
// {#if expandedIp === asset.ip}
//   <div class="detail-panel">...</div>
// {/if}
```

### Anti-Patterns to Avoid

- **Calling `asyncio.to_thread()` inside another `asyncio.to_thread()` block:** `_apply_asset_upsert()` runs inside the existing `to_thread()` from `ingest_events()`. Do NOT add another `to_thread()` wrapper around SQLite calls inside this helper — it is already in a thread.
- **Using DuckDB for asset storage:** Assets belong in SQLite (same as IOCs, cases, detections). DuckDB is for immutable normalized events only.
- **Running actor matching at ingest time:** TTP overlap scoring iterates all groups × all detected techniques. Too expensive for hot path. On-demand endpoint only.
- **Downloading STIX on every request:** Check `attack_store.technique_count() > 0` at startup. If data exists, skip download entirely.
- **Sub-technique IDs in coverage:** Phase 34 only surfaces parent technique IDs (T1059, not T1059.001). Filter `x_mitre_is_subtechnique == True` objects out of technique table.
- **Using `svelte:store` or `writable()`:** Project is Svelte 5. Use `$state()`, `$derived()`, `$effect()` only (per CLAUDE.md).

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Private IP detection | Custom regex | `ipaddress.ip_address(ip).is_private` | Handles IPv4/IPv6, CIDR edge cases, loopback; already used in osint.py |
| STIX JSON fetching | Custom HTTP retry | `httpx.AsyncClient.get()` with timeout | httpx already in project; handles redirects, SSL |
| Sigma rule YAML parsing | Custom YAML parser | `SigmaRule.from_yaml()` from pySigma | Already used in matcher.py; handles all Sigma YAML edge cases |
| SQLite connection management | New connection pool | Reuse `sqlite_store._conn` directly | IocStore pattern; same connection = same WAL journal; thread-safe with GIL |
| ATT&CK tactic ordering | Custom list | Import `MITRE_TACTICS` from `backend.api.analytics` | Already defined in correct Enterprise ATT&CK v14 order |

**Key insight:** The project already has templates for every major pattern in Phase 34. The main work is wiring new stores into the existing infrastructure, not building new patterns.

---

## Common Pitfalls

### Pitfall 1: AssetsView.svelte already exists as wrong component
**What goes wrong:** `dashboard/src/views/AssetsView.svelte` already exists — it is a coverage/health view showing entity counts and ingestion source status, NOT an IP-centric asset table.
**Why it happens:** This view was scaffolded in an earlier phase with a generic "assets" concept.
**How to avoid:** Plan must explicitly say "full rewrite" of AssetsView.svelte. Do not try to adapt the existing component.
**Warning signs:** If the plan says "update AssetsView.svelte" without "replace", the risk is inheriting stale state variables and wrong data types.

### Pitfall 2: STIX `revoked` objects in ATT&CK bundle
**What goes wrong:** The STIX bundle contains deprecated/revoked techniques and groups with `"revoked": true`. These appear as real objects but should not be seeded into the database.
**Why it happens:** MITRE marks old techniques as revoked rather than deleting them to preserve historical tracking.
**How to avoid:** Always filter `not obj.get("revoked", False)` when iterating the bundle `objects` array.
**Warning signs:** Unexpected technique IDs in the database that don't appear on the MITRE ATT&CK website.

### Pitfall 3: Sigma technique tag case sensitivity
**What goes wrong:** Sigma tags may be `attack.T1059` (uppercase) or `attack.t1059` (lowercase). The regex needs case-insensitive matching and normalisation to uppercase for storage.
**Why it happens:** The Sigma specification allows either case. Community rules are inconsistent.
**How to avoid:** Use `re.IGNORECASE` on the regex, then call `.upper()` on the captured group.
**Warning signs:** Technique ID not found in coverage even though a rule exists with the tag.

### Pitfall 4: STIX external_references index is not always [0]
**What goes wrong:** Some STIX objects have multiple external references (CAPEC, NVD, etc.). Assuming `external_references[0]` is the MITRE ATT&CK ID will fail for some objects.
**Why it happens:** STIX objects can reference multiple external databases.
**How to avoid:** Use `next((r["external_id"] for r in refs if r.get("source_name") == "mitre-attack"), None)` — filter by `source_name`.
**Warning signs:** Technique IDs like "CAPEC-123" appearing in the technique table.

### Pitfall 5: Actor matching uses un-indexed JOIN across large technique sets
**What goes wrong:** If `attack_group_techniques` has no index on `tech_id`, the overlap query scans the full table for each detected technique ID.
**Why it happens:** SQLite creates indexes explicitly — no auto-index on foreign keys.
**How to avoid:** Create `CREATE INDEX idx_agt_tech ON attack_group_techniques(tech_id)` and `CREATE INDEX idx_agt_group ON attack_group_techniques(stix_group_id)`.
**Warning signs:** Actor matching endpoint takes >5 seconds.

### Pitfall 6: `ON CONFLICT(ip)` asset upsert won't work without UNIQUE constraint
**What goes wrong:** SQLite `ON CONFLICT` clause in INSERT requires the column to have a `UNIQUE` or `PRIMARY KEY` constraint defined in the DDL.
**Why it happens:** SQLite's upsert syntax `ON CONFLICT(ip) DO UPDATE SET` requires a conflict target.
**How to avoid:** Define `ip TEXT PRIMARY KEY` (or `UNIQUE`) in the `assets` table DDL.
**Warning signs:** `OperationalError: no such conflict target` at runtime.

---

## Code Examples

### SQLite DDL (Claude's discretion — recommended)

```sql
-- Source: pattern from sqlite_store.py existing DDL
CREATE TABLE IF NOT EXISTS assets (
    ip          TEXT PRIMARY KEY,
    hostname    TEXT,                   -- most recent hostname seen; may be NULL
    tag         TEXT NOT NULL DEFAULT 'external',  -- 'internal' | 'external'
    risk_score  INTEGER NOT NULL DEFAULT 0,        -- 0-100; recomputed on upsert
    alert_count INTEGER NOT NULL DEFAULT 0,        -- updated by detection tagging or query
    last_seen   TEXT NOT NULL,          -- ISO8601 UTC
    first_seen  TEXT NOT NULL,          -- ISO8601 UTC
    ioc_matched INTEGER NOT NULL DEFAULT 0,        -- 1 if any IOC hit in last 30d
    updated_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_assets_tag ON assets (tag);
CREATE INDEX IF NOT EXISTS idx_assets_last_seen ON assets (last_seen);

CREATE TABLE IF NOT EXISTS attack_techniques (
    tech_id     TEXT PRIMARY KEY,       -- e.g. "T1059"
    name        TEXT NOT NULL,
    tactic      TEXT NOT NULL,          -- e.g. "execution"
    created_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_attack_tech_tactic ON attack_techniques (tactic);

CREATE TABLE IF NOT EXISTS attack_groups (
    stix_id     TEXT PRIMARY KEY,       -- STIX UUID e.g. "intrusion-set--..."
    group_id    TEXT,                   -- ATT&CK ID e.g. "G0007" (may be null for non-catalogued)
    name        TEXT NOT NULL,
    aliases     TEXT NOT NULL DEFAULT '[]',  -- JSON array of strings
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS attack_group_techniques (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    stix_group_id TEXT NOT NULL,
    tech_id     TEXT NOT NULL,
    UNIQUE(stix_group_id, tech_id),
    FOREIGN KEY (stix_group_id) REFERENCES attack_groups (stix_id),
    FOREIGN KEY (tech_id)       REFERENCES attack_techniques (tech_id)
);
CREATE INDEX IF NOT EXISTS idx_agt_group ON attack_group_techniques (stix_group_id);
CREATE INDEX IF NOT EXISTS idx_agt_tech  ON attack_group_techniques (tech_id);

CREATE TABLE IF NOT EXISTS detection_techniques (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    detection_id    TEXT NOT NULL,
    tech_id         TEXT NOT NULL,
    created_at      TEXT NOT NULL,
    UNIQUE(detection_id, tech_id)
);
CREATE INDEX IF NOT EXISTS idx_det_tech_detection ON detection_techniques (detection_id);
CREATE INDEX IF NOT EXISTS idx_det_tech_tech ON detection_techniques (tech_id);
```

### Asset risk score formula (Claude's discretion — recommended weights)

```python
# Recommended formula — produces 0-100 score
def compute_risk_score(
    alert_count: int,
    ioc_matched: bool,
    has_critical: bool,   # any detection severity == "critical" in last 30d
    has_high: bool,
) -> int:
    score = 0
    # Alert contribution: cap at 50 points (log-scaled)
    if alert_count > 0:
        import math
        score += min(50, int(math.log2(alert_count + 1) * 10))
    # IOC hit: +30 points
    if ioc_matched:
        score += 30
    # Severity contribution: +20 for critical, +10 for high
    if has_critical:
        score += 20
    elif has_high:
        score += 10
    return min(100, score)
```

### Actor matching query (SQLite)

```sql
-- Source: CONTEXT.md actor matching spec + standard SQL JOIN pattern
-- Step 1: get all detected technique IDs from last 30 days
SELECT DISTINCT tech_id FROM detection_techniques
WHERE created_at >= datetime('now', '-30 days');

-- Step 2: for each group, compute overlap
-- (Run as single query with subquery for detected set)
WITH detected AS (
    SELECT DISTINCT tech_id FROM detection_techniques
    WHERE created_at >= datetime('now', '-30 days')
),
group_totals AS (
    SELECT stix_group_id, COUNT(*) as total_techs
    FROM attack_group_techniques GROUP BY stix_group_id
),
overlaps AS (
    SELECT agt.stix_group_id,
           COUNT(DISTINCT agt.tech_id) as overlap_count
    FROM attack_group_techniques agt
    INNER JOIN detected d ON agt.tech_id = d.tech_id
    GROUP BY agt.stix_group_id
)
SELECT
    ag.name,
    ag.aliases,
    ag.group_id,
    o.overlap_count,
    gt.total_techs,
    CAST(o.overlap_count AS REAL) / gt.total_techs AS overlap_pct
FROM overlaps o
JOIN attack_groups ag ON o.stix_group_id = ag.stix_id
JOIN group_totals gt ON o.stix_group_id = gt.stix_group_id
ORDER BY overlap_pct DESC
LIMIT 3;
```

### Coverage heatmap query (SQLite JOIN + Sigma scan)

```python
# Source: CONTEXT.md coverage spec
# Coverage = rules on disk with attack.tXXXX tags (NOT fired detections)
# The API handler:
# 1. Scan rules dir → dict[tech_id, rule_count]
# 2. Query attack_techniques to get all known techniques per tactic
# 3. Join: for each tactic, for each technique, coverage_count = rule_count.get(tech_id, 0)

# GET /api/attack/coverage response shape:
{
  "tactics": ["reconnaissance", "resource-development", ...],   # 14 items
  "heatmap": [
    {
      "tactic": "execution",
      "short_name": "Exec",
      "covered_rules": 5,
      "total_techniques": 67,
      "techniques": [
        {"tech_id": "T1059", "name": "Command and Scripting Interpreter", "rule_count": 3},
        {"tech_id": "T1106", "name": "Native API", "rule_count": 0},
        ...
      ]
    },
    ...
  ]
}
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `mitre/cti` GitHub repo for STIX data | `mitre-attack/attack-stix-data` repo | 2021 (MITRE migration) | New repo has cleaner versioned releases; raw URL still works from old repo but `attack-stix-data` is the canonical source |
| STIX 2.0 (mitre/cti era) | STIX 2.1 in attack-stix-data | ATT&CK v9+ | Object IDs and schema are compatible; `x_mitre_is_subtechnique` flag added in 2.1 |
| `mitreattack-python` library | Raw JSON parse | — | Library adds ~10MB dependency for functionality achievable in ~50 lines; raw parse preferred for this project |

**Deprecated/outdated:**
- `mitre/cti` blob URL (`https://raw.githubusercontent.com/mitre/cti/master/enterprise-attack/enterprise-attack.json`): Still works but `mitre-attack/attack-stix-data` is the canonical maintained source.
- ATT&CK v13 had 14 tactics — this count is unchanged in v15+ (Enterprise). The 14-column heatmap decision is stable.

---

## Key Integration Points

### loader.py change (P34-T07)

The only change to `loader.py` is adding a call to `_apply_asset_upsert()` immediately after the existing `_apply_ioc_matching()` call in the `ingest_events()` synchronous inner function. Both run inside the same `asyncio.to_thread()` block.

```python
# In the batch processing loop inside ingest_events() (sync function called via to_thread):
for event in batch:
    event = normalize_event(event)
    event = _apply_ioc_matching(event, ioc_store)   # existing
    _apply_asset_upsert(event, asset_store)          # NEW — Phase 34
    rows.append(event.to_duckdb_row())
```

### detections/matcher.py change (P34-T02)

After creating a `DetectionRecord`, extract ATT&CK technique IDs from the Sigma rule's tags and write them to `detection_techniques` join table. The `SigmaRule` object is already available in `match_rule()`.

```python
# In SigmaMatcher.match_rule() after creating detection_record:
tech_ids = extract_attack_techniques_from_rule(rule)
for tech_id in tech_ids:
    attack_store.upsert_detection_technique(
        detection_id=detection_record.id,
        tech_id=tech_id,
    )
```

### main.py changes (P34-T01, T07, T08)

```python
# In lifespan, after sqlite_store init:
from backend.services.attack.asset_store import AssetStore
from backend.services.attack.attack_store import AttackStore
from backend.api.assets import router as assets_router
from backend.api.attack import router as attack_router

asset_store = AssetStore(sqlite_store._conn)
attack_store = AttackStore(sqlite_store._conn)

# Bootstrap ATT&CK data (skip if already seeded)
async with httpx.AsyncClient() as client:
    await bootstrap_attack_data(attack_store, client)

app.state.asset_store = asset_store
app.state.attack_store = attack_store

# In create_app():
app.include_router(assets_router, prefix="/api", dependencies=[Depends(verify_token)])
app.include_router(attack_router, prefix="/api", dependencies=[Depends(verify_token)])
```

### App.svelte sidebar (P34-T09)

```svelte
<!-- Add between Threat Intel and Threat Map in Intelligence nav group -->
<button onclick={() => view = 'attack-coverage'}>ATT&CK Coverage</button>
<!-- Route: -->
{#if view === 'attack-coverage'}<AttackCoverageView />{/if}
<!-- AssetsView already routed — just replace the component implementation -->
```

---

## Open Questions

1. **Asset alert_count staleness**
   - What we know: `alert_count` is derived from DetectionRecords referencing src_ip/dst_ip. Computing it at query time requires a JOIN across DuckDB (normalized_events) and SQLite (detections). Computing at upsert time requires the detection engine to update the asset record on each match.
   - What's unclear: Whether to compute alert_count at query time (JOIN, slower but always fresh) or at detection time (write on each match, fast reads).
   - Recommendation: Compute at query time in `list_assets()` — do a DuckDB read for alert counts keyed by IP, then merge into asset rows before returning. This avoids cross-store write coupling.

2. **STIX download failure handling**
   - What we know: The STIX download is network-dependent. If GitHub is unreachable at startup, `bootstrap_attack_data()` will raise.
   - What's unclear: Whether to hard-fail startup or log warning and continue with empty tables.
   - Recommendation: Wrap in try/except, log warning, continue. ATT&CK data is informational — backend should start even without it. Match the `seed_builtin_playbooks` pattern in main.py (graceful degradation).

3. **existing analytics.py MITRE coverage endpoint overlap**
   - What we know: `GET /api/analytics/mitre-coverage` already exists and cross-references fired detections + playbooks. Phase 34's `GET /api/attack/coverage` cross-references Sigma rules on disk.
   - What's unclear: Whether the existing endpoint should be deprecated or kept.
   - Recommendation: Keep both. They serve different purposes. Update frontend: AttackCoverageView uses the new `/api/attack/coverage` (Sigma rule scan). The existing ReportsView can continue using `/api/analytics/mitre-coverage` (detection-based).

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest + pytest-asyncio (already configured) |
| Config file | `pyproject.toml` (mode = auto) |
| Quick run command | `uv run pytest tests/unit/test_asset_store.py tests/unit/test_attack_store.py tests/unit/test_assets_api.py tests/unit/test_attack_api.py -x -q` |
| Full suite command | `uv run pytest tests/unit/ -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| P34-T01 | `attack_store.upsert_technique()` stores technique with tactic | unit | `uv run pytest tests/unit/test_attack_store.py::test_upsert_technique -x` | ❌ Wave 0 |
| P34-T01 | `attack_store.upsert_group()` stores group with aliases | unit | `uv run pytest tests/unit/test_attack_store.py::test_upsert_group -x` | ❌ Wave 0 |
| P34-T01 | `attack_store.upsert_group_technique()` deduplicates on (group, tech) | unit | `uv run pytest tests/unit/test_attack_store.py::test_group_technique_dedup -x` | ❌ Wave 0 |
| P34-T01 | revoked STIX objects are filtered during parse | unit | `uv run pytest tests/unit/test_attack_store.py::test_revoked_filtered -x` | ❌ Wave 0 |
| P34-T01 | `external_references` lookup uses `source_name == "mitre-attack"` filter | unit | `uv run pytest tests/unit/test_attack_store.py::test_external_ref_filter -x` | ❌ Wave 0 |
| P34-T02 | `extract_attack_techniques_from_rule()` returns T-IDs from Sigma tags | unit | `uv run pytest tests/unit/test_attack_tagging.py::test_extract_techniques -x` | ❌ Wave 0 |
| P34-T02 | tag extraction is case-insensitive (attack.T1059 == attack.t1059) | unit | `uv run pytest tests/unit/test_attack_tagging.py::test_tag_case_insensitive -x` | ❌ Wave 0 |
| P34-T02 | sub-technique tags (attack.t1059.001) extract parent T1059 | unit | `uv run pytest tests/unit/test_attack_tagging.py::test_subtechnique_tag -x` | ❌ Wave 0 |
| P34-T03 | actor matching returns top-3 groups sorted by overlap_pct DESC | unit | `uv run pytest tests/unit/test_attack_store.py::test_actor_matching_top3 -x` | ❌ Wave 0 |
| P34-T03 | confidence label: >=60%=High, 30-59%=Medium, <30%=Low | unit | `uv run pytest tests/unit/test_attack_store.py::test_confidence_labels -x` | ❌ Wave 0 |
| P34-T04 | `scan_rules_dir_for_coverage()` returns tech_id→rule_count dict | unit | `uv run pytest tests/unit/test_attack_tagging.py::test_coverage_scan -x` | ❌ Wave 0 |
| P34-T04 | GET /api/attack/coverage returns 14-tactic list with technique breakdown | unit | `uv run pytest tests/unit/test_attack_api.py::test_coverage_endpoint -x` | ❌ Wave 0 |
| P34-T07 | `_apply_asset_upsert()` upserts src_ip and dst_ip from NormalizedEvent | unit | `uv run pytest tests/unit/test_asset_store.py::test_upsert_from_event -x` | ❌ Wave 0 |
| P34-T07 | RFC1918 IPs tagged "internal"; public IPs tagged "external" | unit | `uv run pytest tests/unit/test_asset_store.py::test_internal_external_tag -x` | ❌ Wave 0 |
| P34-T07 | duplicate upsert updates last_seen, keeps first_seen | unit | `uv run pytest tests/unit/test_asset_store.py::test_upsert_dedup -x` | ❌ Wave 0 |
| P34-T07 | None src_ip / dst_ip are skipped (no error) | unit | `uv run pytest tests/unit/test_asset_store.py::test_null_ip_skip -x` | ❌ Wave 0 |
| P34-T08 | GET /api/assets returns list of asset dicts | unit | `uv run pytest tests/unit/test_assets_api.py::test_list_assets -x` | ❌ Wave 0 |
| P34-T08 | GET /api/assets/{ip} returns single asset or 404 | unit | `uv run pytest tests/unit/test_assets_api.py::test_get_asset -x` | ❌ Wave 0 |
| P34-T08 | POST /api/assets/{ip}/tag updates tag field | unit | `uv run pytest tests/unit/test_assets_api.py::test_tag_asset -x` | ❌ Wave 0 |
| P34-T09 | TypeScript compilation clean with new api.ts interfaces | smoke | `cd dashboard && npm run check` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/unit/test_asset_store.py tests/unit/test_attack_store.py tests/unit/test_attack_tagging.py tests/unit/test_assets_api.py tests/unit/test_attack_api.py -x -q`
- **Per wave merge:** `uv run pytest tests/unit/ -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

All test files listed below must be created as Wave 0 stubs before implementation begins. Follow the IocStore test pattern: in-memory SQLite via `sqlite3.connect(":memory:")` + `_DDL` import.

- [ ] `tests/unit/test_asset_store.py` — covers P34-T07 (AssetStore CRUD, internal/external tag, null IP handling)
- [ ] `tests/unit/test_attack_store.py` — covers P34-T01 (technique/group/relationship upsert, revoked filter, external_ref filter), P34-T03 (actor matching query, confidence labels)
- [ ] `tests/unit/test_attack_tagging.py` — covers P34-T02 (Sigma tag extraction, case insensitivity, sub-technique handling), P34-T04 (coverage scan with fixture YAML files)
- [ ] `tests/unit/test_assets_api.py` — covers P34-T08 (list/get/tag endpoints using FastAPI TestClient with mocked app.state)
- [ ] `tests/unit/test_attack_api.py` — covers P34-T04 (GET /api/attack/coverage structure), P34-T03 (GET /api/attack/actor-matches response shape)

---

## Sources

### Primary (HIGH confidence)
- Codebase: `backend/services/intel/ioc_store.py` — AssetStore template verified
- Codebase: `ingestion/loader.py._apply_ioc_matching()` — integration point confirmed
- Codebase: `backend/api/intel.py` — API router pattern confirmed
- Codebase: `backend/api/analytics.py` — `MITRE_TACTICS` list confirmed (14 tactics, Enterprise v14 order)
- Codebase: `backend/services/osint.py._sanitize_ip()` — RFC1918 classification pattern confirmed
- Codebase: `dashboard/src/views/ThreatIntelView.svelte` — Svelte 5 expand/collapse UX template confirmed
- Codebase: `dashboard/src/views/AssetsView.svelte` — confirmed existing component is wrong shell (full rewrite needed)
- Codebase: `tests/unit/test_ioc_store.py` — in-memory SQLite test pattern confirmed

### Secondary (MEDIUM confidence)
- [MITRE attack-stix-data GitHub](https://github.com/mitre-attack/attack-stix-data) — Raw download URL confirmed: `https://raw.githubusercontent.com/mitre-attack/attack-stix-data/master/enterprise-attack/enterprise-attack.json`
- [STIX USAGE.md](https://github.com/mitre-attack/attack-stix-data/blob/master/USAGE.md) — attack-pattern, intrusion-set, relationship object structure confirmed; `external_references[source_name=="mitre-attack"]` filter pattern confirmed
- [sigmahq.io Sigma Rules docs](https://sigmahq.io/docs/basics/rules.html) — ATT&CK tag format `attack.t1059`, `attack.t1059.001`, `attack.execution` confirmed

### Tertiary (LOW confidence)
- None — all critical claims verified from codebase or official sources.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries are already in the project
- Architecture: HIGH — patterns directly verified from existing codebase (IocStore, loader.py, intel.py, ThreatIntelView)
- STIX parsing: MEDIUM — structure verified from official USAGE.md; not tested against live download
- Sigma tag extraction: HIGH — pySigma already used in project; tag format verified from official Sigma docs
- Pitfalls: HIGH — discovered from direct code inspection of existing patterns

**Research date:** 2026-04-10
**Valid until:** 2026-07-10 (STIX URL stable; ATT&CK tactic count unchanged since v9; Svelte 5 runes stable)
