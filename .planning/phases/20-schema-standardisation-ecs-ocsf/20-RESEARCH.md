# Phase 20: Schema Standardisation (ECS/OCSF) - Research

**Researched:** 2026-04-01
**Domain:** Event schema normalisation — ECS 8.x field alignment, OCSF class_uid mapping, DuckDB migration, pySigma field-map update
**Confidence:** HIGH (ECS field names and OCSF class_uids verified against official sources; DuckDB ALTER TABLE syntax verified against official docs; code archaeology verified against live source files)

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| P20-T01 | Canonical NormalizedEvent model: ECS-aligned Pydantic, OCSF class_uid, backward-compatible | ECS 8.x field mapping table, OCSF class_uid reference, Pydantic alias pattern |
| P20-T02 | Parser field mapping layer: FieldMapper utility, pure function, all parsers updated | Current parser field-key frozensets catalogued; FieldMapper design documented |
| P20-T03 | DuckDB schema migration: additive ALTER TABLE, db_meta version table | DuckDB ALTER TABLE syntax verified; one-column-per-statement constraint documented |
| P20-T04 | Sigma field map update: ECS-aligned field names, existing smoke tests still pass | Current SIGMA_FIELD_MAP catalogued; ECS column name mapping documented |
| P20-T05 | Enrichment and AI Copilot alignment: entity_extractor, prompt templates, graph schema | entity_extractor field usage catalogued; prompt templates use to_embedding_text() |
</phase_requirements>

---

## Summary

Phase 20 replaces the project-local flat field schema with an industry-standard layout aligned to Elastic Common Schema (ECS) 8.x and annotated with OCSF class_uid values. The current `NormalizedEvent` model uses simple snake_case column names (`process_name`, `dst_ip`, `username`) that do not map to any published standard. After this phase, the canonical model uses ECS dotted-field names for the first-class columns while retaining the old snake_case names as Pydantic aliases so that every existing parser, test, and API consumer continues to work without modification.

The migration has five bounded tasks. T01 adds ECS-aligned field names and an `ocsf_class_uid` integer column to `NormalizedEvent`. T02 introduces a single `FieldMapper` utility that centralises the vendor→ECS translation now scattered across four parser files. T03 runs additive `ALTER TABLE` statements (one per new column — DuckDB limitation) and creates a `db_meta` version table. T04 rewrites `detections/field_map.py` to point Sigma field names at the new ECS column names and confirms all existing sigma smoke tests still pass. T05 updates `entity_extractor.py` and prompt templates to use the new ECS field names while keeping the embedding text output identical.

**Primary recommendation:** Use Pydantic `model_validator` + `Field(alias=...)` to expose both ECS field names (`process.name` stored as `process_name_ecs`) AND the legacy names in one model. The DuckDB table retains snake_case column names (they are not dotted-path identifiers); new ECS columns are added additively via `ALTER TABLE`.

---

## Current State Audit

Understanding the existing code is critical before planning any changes.

### Current NormalizedEvent fields (backend/models/event.py)

| Current Field | Type | Maps to ECS | Maps to OCSF |
|---|---|---|---|
| `event_id` | str | `event.id` | `metadata.uid` |
| `timestamp` | datetime | `@timestamp` | `time` |
| `ingested_at` | datetime | `event.ingested` | `metadata.processed_time` |
| `source_type` | str | `event.module` | `metadata.log_provider` |
| `source_file` | str | `log.file.path` | `metadata.log_name` |
| `hostname` | str | `host.hostname` | `device.hostname` |
| `username` | str | `user.name` | `user.name` |
| `process_name` | str | `process.name` | `process.name` |
| `process_id` | int | `process.pid` | `process.pid` |
| `parent_process_name` | str | `process.parent.name` | `process.parent_process.name` |
| `parent_process_id` | int | `process.parent.pid` | `process.parent_process.pid` |
| `file_path` | str | `file.path` | `file.path` |
| `file_hash_sha256` | str | `file.hash.sha256` | `file.hashes[].value` |
| `command_line` | str | `process.command_line` | `process.cmd_line` |
| `src_ip` | str | `source.ip` | `src_endpoint.ip` |
| `src_port` | int | `source.port` | `src_endpoint.port` |
| `dst_ip` | str | `destination.ip` | `dst_endpoint.ip` |
| `dst_port` | int | `destination.port` | `dst_endpoint.port` |
| `domain` | str | `dns.question.name` / `destination.domain` | `dns.query.hostname` |
| `url` | str | `url.original` | `http.request.url.path` |
| `event_type` | str | `event.action` | (drives `class_uid` + `activity_id`) |
| `severity` | str | `event.severity` / `log.level` | `severity_id` |
| `confidence` | float | `kibana.alert.risk_score` | `confidence_id` |
| `detection_source` | str | `event.provider` | `metadata.product.name` |
| `attack_technique` | str | `threat.technique.id` | `attacks[].technique.uid` |
| `attack_tactic` | str | `threat.tactic.name` | `attacks[].tactic.name` |
| `raw_event` | str | `event.original` | `unmapped` |
| `tags` | str | `tags` | `metadata.labels` |
| `case_id` | str | (custom) | `metadata.correlation_uid` |

**New fields to add (not currently present):**

| New Field | Type | ECS Equivalent | OCSF Equivalent | Rationale |
|---|---|---|---|---|
| `ocsf_class_uid` | int | (OCSF-specific) | `class_uid` | Enables OCSF-aware export and filtering |
| `event_outcome` | str | `event.outcome` (success/failure/unknown) | `status_id` | Auth/process success/failure |
| `user_domain` | str | `user.domain` | `user.domain` | Windows domain for NTLM/Kerberos rules |
| `process_executable` | str | `process.executable` | `process.file.path` | Full PE path vs. name |
| `network_protocol` | str | `network.protocol` (tcp/udp/dns) | `connection_info.protocol_name` | Protocol for network detections |
| `network_direction` | str | `network.direction` (inbound/outbound/internal) | `connection_info.direction` | Firewall-style direction |

### OCSF class_uid mapping for this project's event_type values

| Current `event_type` | OCSF class_uid | OCSF Class Name |
|---|---|---|
| `process_create` | 1007 | Process Activity |
| `process_terminate` | 1007 | Process Activity |
| `process_access` | 1007 | Process Activity |
| `file_create` | 1001 | File System Activity |
| `file_delete` | 1001 | File System Activity |
| `file_create_stream_hash` | 1001 | File System Activity |
| `file_creation_time_changed` | 1001 | File System Activity |
| `file_delete_detected` | 1001 | File System Activity |
| `network_connect` | 4001 | Network Activity |
| `dns_query` | 4003 | DNS Activity |
| `logon_success` | 3002 | Authentication |
| `logon_failure` | 3002 | Authentication |
| `logoff` | 3002 | Authentication |
| `explicit_credential_logon` | 3002 | Authentication |
| `kerberos_tgs_request` | 3002 | Authentication |
| `kerberos_service_ticket` | 3002 | Authentication |
| `ntlm_auth` | 3002 | Authentication |
| `registry_event` | 1001 | File System Activity (OCSF deprecated registry classes in v1.0) |
| `registry_value_set` | 1001 | File System Activity |
| `driver_load` | 1005 | Module Activity |
| `image_load` | 1005 | Module Activity |
| `scheduled_task_created` | 1006 | Scheduled Job Activity |
| `user_account_created` | 3001 | Account Change |
| `user_account_deleted` | 3001 | Account Change |
| `wmi_event` | 1009 | Script Activity |
| `wmi_consumer` | 1009 | Script Activity |
| `wmi_subscription` | 1009 | Script Activity |
| `logon_event` (osquery) | 3002 | Authentication |

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pydantic | 2.x (already in use) | NormalizedEvent model with ECS aliases | Already used; Field(alias=) and model_validator patterns cover backward compat |
| duckdb | current (already in use) | ALTER TABLE for additive migration | Official DuckDB ALTER TABLE docs confirm syntax |
| pytest | current (already in use) | Regression suite for all five tasks | 50+ existing tests provide baseline |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pydantic `Field(alias=...)` | pydantic 2.x | Expose both ECS names and legacy names | T01 model design |
| pydantic `model_validator(mode='before')` | pydantic 2.x | Accept legacy snake_case inputs while storing ECS-aligned values | T01 backward compat |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Pydantic alias approach | Rename fields directly | Direct rename breaks all 50+ tests; alias approach maintains backward compat with zero test changes |
| In-place ALTER TABLE | CREATE TABLE ... AS SELECT | CTAS is cleaner but requires data copy; ALTER TABLE is zero-downtime and preserves existing DuckDB file |

**No new package installation required.** All dependencies already present.

---

## Architecture Patterns

### Pattern 1: ECS Field Aliases in Pydantic (for P20-T01)

The correct approach is to add new ECS-named properties as `@property` accessors on the model or as computed fields, while keeping the DuckDB column names as snake_case. The DuckDB schema column names do NOT need to use dotted ECS paths — they are SQL column identifiers and cannot contain dots without quoting. The ECS alignment happens at the model/API layer.

**Design decision:** Add new ECS-oriented columns as additional Optional fields with their own DuckDB columns. Expose ECS dotted-name aliases via Pydantic `Field(alias=...)` for serialisation purposes.

```python
# Source: backend/models/event.py (new design)
from pydantic import BaseModel, Field

class NormalizedEvent(BaseModel):
    model_config = {"populate_by_name": True}  # allow both alias and field name

    # --- Legacy snake_case names remain primary (DuckDB column names) ---
    hostname: Optional[str] = None
    username: Optional[str] = None
    process_name: Optional[str] = None
    process_id: Optional[int] = None

    # --- New ECS-enrichment fields (new DuckDB columns) ---
    ocsf_class_uid: Optional[int] = None          # OCSF class_uid (1007, 4001, etc.)
    event_outcome: Optional[str] = None            # ECS event.outcome: success/failure/unknown
    user_domain: Optional[str] = None              # ECS user.domain
    process_executable: Optional[str] = None       # ECS process.executable (full path)
    network_protocol: Optional[str] = None         # ECS network.protocol
    network_direction: Optional[str] = None        # ECS network.direction

    # --- ECS name aliases for API serialisation (not stored separately) ---
    # These are read-only computed properties, not stored columns
    @property
    def ecs_process_name(self) -> Optional[str]:
        return self.process_name  # maps to ECS process.name

    @property
    def ecs_host_hostname(self) -> Optional[str]:
        return self.hostname  # maps to ECS host.hostname
```

**Key insight:** DuckDB column names stay as `process_name`, `dst_ip`, etc. The ECS mapping is documented in a lookup table and used in the FieldMapper and the Sigma field map — not encoded as literal dotted column names in SQL.

### Pattern 2: FieldMapper Utility (for P20-T02)

A `FieldMapper` is a pure function / class that takes a raw dict from a parser and returns a `NormalizedEvent`-compatible dict with standardised field names. The four parsers (EVTX, JSON, CSV, osquery) currently each maintain their own `frozenset` of key variants. The FieldMapper centralises this.

```python
# Source: ingestion/field_mapper.py (new file)
from __future__ import annotations
from typing import Any

# Canonical mapping: raw field name variants → NormalizedEvent field name
_FIELD_VARIANTS: dict[str, str] = {
    # ECS process fields
    "process.name": "process_name",
    "process.pid": "process_id",
    "process.command_line": "command_line",
    "process.executable": "process_executable",
    "process.parent.name": "parent_process_name",
    "process.parent.pid": "parent_process_id",
    # ECS user fields
    "user.name": "username",
    "user.domain": "user_domain",
    # ECS host fields
    "host.hostname": "hostname",
    "host.name": "hostname",
    # ECS source/destination fields
    "source.ip": "src_ip",
    "source.port": "src_port",
    "destination.ip": "dst_ip",
    "destination.port": "dst_port",
    "destination.domain": "domain",
    # ECS file fields
    "file.path": "file_path",
    "file.hash.sha256": "file_hash_sha256",
    # ECS network fields
    "network.protocol": "network_protocol",
    "network.direction": "network_direction",
    # ECS event fields
    "event.action": "event_type",
    "event.outcome": "event_outcome",
    "event.original": "raw_event",
    # ECS threat fields
    "threat.technique.id": "attack_technique",
    "threat.tactic.name": "attack_tactic",
    # ECS URL/DNS
    "url.original": "url",
    "dns.question.name": "domain",
}

class FieldMapper:
    """Translate vendor/ECS field names to NormalizedEvent column names."""

    def map(self, raw: dict[str, Any]) -> dict[str, Any]:
        """Return a new dict with field names translated to NormalizedEvent keys."""
        result: dict[str, Any] = {}
        for k, v in raw.items():
            canonical = _FIELD_VARIANTS.get(k) or _FIELD_VARIANTS.get(k.lower())
            result[canonical if canonical else k] = v
        return result
```

### Pattern 3: DuckDB Additive Migration (for P20-T03)

DuckDB supports `ALTER TABLE ... ADD COLUMN` with optional DEFAULT. One statement per column is required (DuckDB limitation as of current version). Each new column must be nullable (no NOT NULL without default).

```sql
-- Source: DuckDB official docs (duckdb.org/docs/current/sql/statements/alter_table)
-- Run each statement separately via store.execute_write()

-- Version tracking table (create first)
CREATE TABLE IF NOT EXISTS db_meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
INSERT INTO db_meta (key, value)
VALUES ('schema_version', '1')
ON CONFLICT (key) DO NOTHING;

-- New ECS-aligned columns (additive only, all nullable)
ALTER TABLE normalized_events ADD COLUMN IF NOT EXISTS ocsf_class_uid     INTEGER;
ALTER TABLE normalized_events ADD COLUMN IF NOT EXISTS event_outcome       TEXT;
ALTER TABLE normalized_events ADD COLUMN IF NOT EXISTS user_domain         TEXT;
ALTER TABLE normalized_events ADD COLUMN IF NOT EXISTS process_executable  TEXT;
ALTER TABLE normalized_events ADD COLUMN IF NOT EXISTS network_protocol    TEXT;
ALTER TABLE normalized_events ADD COLUMN IF NOT EXISTS network_direction   TEXT;

-- Update schema version
INSERT INTO db_meta (key, value) VALUES ('schema_version', '20')
ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value;
```

**Important:** DuckDB does NOT support `IF NOT EXISTS` on `ALTER TABLE ADD COLUMN` in older versions. Wrap in a try/except in Python to handle re-run idempotency:

```python
async def migrate_to_v20(store: DuckDBStore) -> None:
    """Additive migration: add ECS-aligned columns to normalized_events."""
    new_columns = [
        ("ocsf_class_uid",    "INTEGER"),
        ("event_outcome",     "TEXT"),
        ("user_domain",       "TEXT"),
        ("process_executable","TEXT"),
        ("network_protocol",  "TEXT"),
        ("network_direction", "TEXT"),
    ]
    for col_name, col_type in new_columns:
        try:
            await store.execute_write(
                f"ALTER TABLE normalized_events ADD COLUMN {col_name} {col_type}"
            )
        except Exception:
            # Column already exists — safe to skip
            pass
```

### Pattern 4: Sigma Field Map Update (for P20-T04)

The update to `detections/field_map.py` maps Sigma Windows field names to the SAME DuckDB column names as before (snake_case), plus adds mappings for ECS field names that Sigma-ECS pipelines might use. The new columns (`network_protocol`, `event_outcome`, `user_domain`) must be added to the mapping.

```python
# detections/field_map.py additions
SIGMA_FIELD_MAP: dict[str, str] = {
    # ... all existing entries preserved unchanged ...

    # New ECS-named fields that pySigma ECS pipelines may emit
    "process.name":           "process_name",
    "process.pid":            "process_id",
    "process.command_line":   "command_line",
    "process.executable":     "process_executable",
    "process.parent.name":    "parent_process_name",
    "process.parent.pid":     "parent_process_id",
    "user.name":              "username",
    "user.domain":            "user_domain",
    "host.hostname":          "hostname",
    "source.ip":              "src_ip",
    "source.port":            "src_port",
    "destination.ip":         "dst_ip",
    "destination.port":       "dst_port",
    "destination.domain":     "domain",
    "file.path":              "file_path",
    "file.hash.sha256":       "file_hash_sha256",
    "network.protocol":       "network_protocol",
    "dns.question.name":      "domain",

    # New column mappings
    "EventOutcome":           "event_outcome",
    "SubjectDomainName":      "user_domain",
    "TargetDomainName":       "user_domain",
    "DomainName":             "user_domain",
}
```

**Smoke test impact:** All existing smoke tests that check `SIGMA_FIELD_MAP["Image"] == "process_name"` etc. continue to pass because no existing entries are changed — only additions.

### Anti-Patterns to Avoid
- **Renaming existing DuckDB columns:** DuckDB does not support `RENAME COLUMN` changing data type, and doing so would require a full CTAS migration. Additive-only is the safe path.
- **Using dotted column names in SQL:** DuckDB column names with dots require quoting (`"process.name"`) and break the existing parameterised query patterns in the matcher.
- **Storing OCSF class_uid as a string:** It is a numeric identifier; store as INTEGER so it can be filtered with `= 1007` efficiently.
- **Removing the legacy field names from NormalizedEvent:** Every existing parser, test, API endpoint, and embedding function uses the current names. Removal would cascade across 50+ files.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| OCSF class_uid lookup | Custom string-to-uid map | Static dict in model based on official schema.ocsf.io | OCSF class_uid values are stable; a lookup dict is the right tool |
| Schema versioning | Complex migration framework | `db_meta` table + additive ALTER TABLE | DuckDB's transactional ALTER TABLE is sufficient for this project's scale |
| ECS field name validation | Runtime ECS validator | Document the mapping in FieldMapper + test coverage | ECS compliance is a mapping correctness problem, not a runtime validation problem |
| Parser field deduplication | Generate parsers from schema | Refactor existing frozenset sets to import from FieldMapper | The parsers already work; FieldMapper centralises the mapping without full rewrite |

**Key insight:** ECS/OCSF compliance at this scale means adding a semantic layer on top of the existing data model, not rebuilding the storage layer. The DuckDB column names can remain snake_case; the ECS alignment is a documentation and API contract concern.

---

## Common Pitfalls

### Pitfall 1: DuckDB ALTER TABLE — No Multi-Column Support
**What goes wrong:** Writing `ALTER TABLE t ADD COLUMN a TEXT, ADD COLUMN b TEXT` raises `Parser Error: Only one ALTER command per statement is supported`.
**Why it happens:** DuckDB's ALTER TABLE is more limited than PostgreSQL. Each column addition requires its own statement.
**How to avoid:** Issue one `execute_write` call per new column.
**Warning signs:** Migration script uses commas after ADD COLUMN in a single statement.

### Pitfall 2: ALTER TABLE Fails on Re-Run (No IF NOT EXISTS)
**What goes wrong:** Running the migration twice raises an error because the column already exists.
**Why it happens:** DuckDB's `ALTER TABLE ADD COLUMN` does not accept `IF NOT EXISTS` in all versions.
**How to avoid:** Wrap each ALTER in a try/except in the Python migration function; log the skip.
**Warning signs:** CI fails on second run of migration script.

### Pitfall 3: Pydantic alias vs field name confusion
**What goes wrong:** `model.model_dump()` returns ECS alias names, breaking `to_duckdb_row()` which expects specific positional order.
**Why it happens:** When `model_config = {"populate_by_name": True}` is set and aliases are defined, `model_dump(by_alias=True)` returns alias names.
**How to avoid:** Keep `to_duckdb_row()` referencing field names (not aliases) directly. Only use `by_alias=True` in API serialisation.
**Warning signs:** `to_duckdb_row()` inserts None values for fields that should have data.

### Pitfall 4: Sigma Field Map — Case Sensitivity
**What goes wrong:** Sigma rules use `CommandLine` but new ECS mapping adds `process.command_line`; matcher fails to resolve `commandline` (lowercase from rule normalisation).
**Why it happens:** The current `SigmaMatcher` does a direct dict lookup; if the normalised field name doesn't match a key, it falls back to raw_event LIKE search.
**How to avoid:** Add both capitalised and lowercase variants to `SIGMA_FIELD_MAP`, or normalise lookup keys at matcher time.
**Warning signs:** Sigma smoke tests that previously matched on `CommandLine` now return 0 results.

### Pitfall 5: entity_extractor reads NormalizedEvent field names directly
**What goes wrong:** `entity_extractor.py` accesses `event.hostname`, `event.username`, etc. by attribute name. If the model is changed so these attributes disappear or are renamed, entity extraction silently produces empty results.
**Why it happens:** The extractor is not a test-driven component — its correctness is proven by integration tests.
**How to avoid:** Keep all existing field names as primary attributes. New ECS names are additive only.
**Warning signs:** SQLite edge count drops to zero after model changes.

### Pitfall 6: to_embedding_text() references field names
**What goes wrong:** `to_embedding_text()` accesses `self.hostname`, `self.username`, etc. directly. If names change, embedding quality degrades silently.
**Why it happens:** No test validates embedding text content.
**How to avoid:** Preserve all current field names; add new ECS fields as additional attributes. Update `to_embedding_text()` to include new useful fields (`network_protocol`, `user_domain`).
**Warning signs:** Semantic search quality degrades after model changes.

---

## Code Examples

### OCSF class_uid derivation from event_type

```python
# Source: domain knowledge from schema.ocsf.io/1.7.0/categories
_EVENT_TYPE_TO_OCSF_CLASS_UID: dict[str, int] = {
    # Process Activity (1007)
    "process_create":        1007,
    "process_terminate":     1007,
    "process_access":        1007,
    "process_tampering":     1007,
    "create_remote_thread":  1007,
    # File System Activity (1001)
    "file_create":           1001,
    "file_delete":           1001,
    "file_create_stream_hash": 1001,
    "file_creation_time_changed": 1001,
    "file_delete_detected":  1001,
    "registry_event":        1001,  # OCSF registry classes deprecated; use File System Activity
    "registry_value_set":    1001,
    "registry_key_rename":   1001,
    # Module Activity (1005)
    "driver_load":           1005,
    "image_load":            1005,
    # Scheduled Job Activity (1006)
    "scheduled_task_created": 1006,
    # Script Activity (1009)
    "wmi_event":             1009,
    "wmi_consumer":          1009,
    "wmi_subscription":      1009,
    # Network Activity (4001)
    "network_connect":       4001,
    "raw_disk_access":       4001,  # approximate
    # DNS Activity (4003)
    "dns_query":             4003,
    # Authentication (3002)
    "logon_success":         3002,
    "logon_failure":         3002,
    "logoff":                3002,
    "explicit_credential_logon": 3002,
    "kerberos_tgs_request":  3002,
    "kerberos_service_ticket": 3002,
    "ntlm_auth":             3002,
    "logon_event":           3002,
    # Account Change (3001)
    "user_account_created":  3001,
    "user_account_deleted":  3001,
    "user_group_membership_enumerated": 3001,
    "security_group_enumerated": 3001,
}

def derive_ocsf_class_uid(event_type: str | None) -> int | None:
    if not event_type:
        return None
    return _EVENT_TYPE_TO_OCSF_CLASS_UID.get(event_type)
```

### DuckDB migration function

```python
# Source: DuckDB official docs — duckdb.org/docs/current/sql/statements/alter_table
_V20_NEW_COLUMNS = [
    ("ocsf_class_uid",     "INTEGER"),
    ("event_outcome",      "TEXT"),
    ("user_domain",        "TEXT"),
    ("process_executable", "TEXT"),
    ("network_protocol",   "TEXT"),
    ("network_direction",  "TEXT"),
]

_DB_META_TABLE = """
CREATE TABLE IF NOT EXISTS db_meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
)
"""

async def run_v20_migration(store: "DuckDBStore") -> None:
    """Additive ECS migration — safe to run multiple times."""
    await store.execute_write(_DB_META_TABLE)
    await store.execute_write(
        "INSERT INTO db_meta (key, value) VALUES ('schema_version', '0') "
        "ON CONFLICT (key) DO NOTHING"
    )
    for col_name, col_type in _V20_NEW_COLUMNS:
        try:
            await store.execute_write(
                f"ALTER TABLE normalized_events ADD COLUMN {col_name} {col_type}"
            )
        except Exception:
            pass  # column already exists
    await store.execute_write(
        "INSERT INTO db_meta (key, value) VALUES ('schema_version', '20') "
        "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value"
    )
```

### FieldMapper integration into normalizer

```python
# ingestion/normalizer.py — extend normalize_event to derive ocsf_class_uid
from ingestion.field_mapper import derive_ocsf_class_uid

# Inside normalize_event(), after event_type is established:
if event.event_type and not event.ocsf_class_uid:
    uid = derive_ocsf_class_uid(event.event_type)
    if uid is not None:
        updates["ocsf_class_uid"] = uid
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Project-local snake_case schema | ECS-aligned naming + OCSF class_uid | Phase 20 | Tools like Elastic SIEM, Splunk CIM, and AWS Security Lake can ingest events without custom mapping |
| Field variants in each parser | Centralised FieldMapper | Phase 20 | Adding a new parser requires writing one mapping once, not duplicating frozensets |
| No schema versioning | db_meta version table | Phase 20 | Enables safe incremental migrations in future phases |
| Sigma field map covers Windows only | ECS field aliases added | Phase 20 | Sigma rules authored against ECS pipelines work without modification |

**Deprecated/outdated:**
- OCSF registry-specific classes (`registry_key_activity`, `registry_value_activity`) were deprecated in OCSF v1.0.0. Use File System Activity (1001) instead. The current `registry_event`/`registry_value_set` event_type strings should map to class_uid 1001.
- ECS field `event.severity` is not a standard ECS field (ECS uses `log.level` and `event.risk_score`). The project's internal `severity` vocabulary (critical/high/medium/low/info) is project-specific and should remain as-is; it does not need to change for ECS alignment.

---

## Open Questions

1. **Should `process_executable` be populated by the EVTX parser?**
   - What we know: The current EVTX parser maps `Image` → `process_name`. In Sysmon EID 1, `Image` is the full executable path, not just the name. `process_name` currently receives the full path.
   - What's unclear: Should `process_name` be changed to store only the basename, with `process_executable` storing the full path?
   - Recommendation: In Phase 20, populate both `process_executable = Image` (full path) and `process_name = basename(Image)`. This is additive and ECS-compliant (`process.name` = basename, `process.executable` = full path).

2. **Should the DuckDB INSERT SQL in loader.py be updated to include new columns?**
   - What we know: `loader.py` contains `_INSERT_SQL` with a fixed column list. New columns will be NULL for existing events unless the INSERT is updated.
   - What's unclear: Which parsers can actually populate `network_protocol`, `user_domain`, etc.?
   - Recommendation: Update the INSERT SQL in loader.py to include the 6 new columns. Default to None if not populated. This is P20-T02 scope.

3. **OCSF class_uid for osquery process_create vs network_connect events?**
   - What we know: osquery's `_columns_to_event` derives `event_type` from the query name. This is already handled.
   - What's unclear: No issues; the `derive_ocsf_class_uid` lookup handles it.
   - Recommendation: Apply `derive_ocsf_class_uid(event.event_type)` in `normalize_event()` after `event_type` is set.

---

## Validation Architecture

Nyquist validation is enabled (`workflow.nyquist_validation: true` in `.planning/config.json`).

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest with pytest-asyncio (auto mode) |
| Config file | pyproject.toml |
| Quick run command | `uv run pytest tests/unit/test_normalizer.py tests/unit/test_entity_extractor.py tests/sigma_smoke/test_sigma_matcher.py -x -q` |
| Full suite command | `uv run pytest tests/ -q --tb=short` |

### Phase Requirements to Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| P20-T01 | NormalizedEvent has `ocsf_class_uid`, `event_outcome`, `user_domain`, `process_executable`, `network_protocol`, `network_direction` fields | unit | `uv run pytest tests/unit/test_normalized_event_ecs.py -x` | Wave 0 |
| P20-T01 | `to_duckdb_row()` tuple includes 6 new columns in correct order | unit | `uv run pytest tests/unit/test_normalized_event_ecs.py::TestDuckDBRow -x` | Wave 0 |
| P20-T01 | `ocsf_class_uid` is populated by `normalize_event()` when `event_type` is known | unit | `uv run pytest tests/unit/test_normalized_event_ecs.py::TestOcsfClassUid -x` | Wave 0 |
| P20-T01 | Existing NormalizedEvent construction from legacy kwargs still works | unit | `uv run pytest tests/unit/test_normalizer.py -x` | ✅ |
| P20-T02 | FieldMapper translates ECS dotted names to snake_case column names | unit | `uv run pytest tests/unit/test_field_mapper.py -x` | Wave 0 |
| P20-T02 | FieldMapper translates Windows variant names (SubjectUserName, Image, etc.) | unit | `uv run pytest tests/unit/test_field_mapper.py::TestWindowsVariants -x` | Wave 0 |
| P20-T02 | EVTX parser populates `process_executable` (full path) and `process_name` (basename) | unit | `uv run pytest tests/unit/test_evtx_parser.py -x` | ✅ (needs new assertion) |
| P20-T03 | `run_v20_migration()` adds 6 new columns to `normalized_events` | unit | `uv run pytest tests/unit/test_duckdb_migration.py -x` | Wave 0 |
| P20-T03 | `db_meta` table exists with `schema_version = '20'` after migration | unit | `uv run pytest tests/unit/test_duckdb_migration.py::TestDbMeta -x` | Wave 0 |
| P20-T03 | Migration is idempotent — running twice does not raise | unit | `uv run pytest tests/unit/test_duckdb_migration.py::TestIdempotent -x` | Wave 0 |
| P20-T04 | `SIGMA_FIELD_MAP` includes ECS dotted names (`process.name`, `user.name`, etc.) | unit | `uv run pytest tests/sigma_smoke/test_sigma_matcher.py::TestSigmaFieldMap -x` | ✅ (needs new assertions) |
| P20-T04 | `SIGMA_FIELD_MAP` includes new column names (`user_domain`, `process_executable`, `network_protocol`) | unit | `uv run pytest tests/sigma_smoke/test_sigma_matcher.py -x` | ✅ (needs new assertions) |
| P20-T04 | All existing Sigma smoke tests still pass unchanged | unit | `uv run pytest tests/sigma_smoke/ -x` | ✅ |
| P20-T05 | `entity_extractor` still produces correct entities/edges after model changes | unit | `uv run pytest tests/unit/test_entity_extractor.py -x` | ✅ |
| P20-T05 | `normalizer.derive_ocsf_class_uid` returns correct uid for each known event_type | unit | `uv run pytest tests/unit/test_normalized_event_ecs.py::TestOcsfLookup -x` | Wave 0 |

### Sampling Rate

- **Per task commit:** `uv run pytest tests/unit/test_normalizer.py tests/sigma_smoke/test_sigma_matcher.py -x -q`
- **Per wave merge:** `uv run pytest tests/unit/ tests/sigma_smoke/ -q --tb=short`
- **Phase gate:** Full suite `uv run pytest tests/ -q --tb=short` green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/unit/test_normalized_event_ecs.py` — covers P20-T01: new ECS fields present on model, `to_duckdb_row()` order, `ocsf_class_uid` derivation, OCSF lookup table
- [ ] `tests/unit/test_field_mapper.py` — covers P20-T02: FieldMapper translates ECS names, Windows variants, unknown fields pass through
- [ ] `tests/unit/test_duckdb_migration.py` — covers P20-T03: migration adds columns, creates db_meta, is idempotent; uses in-memory DuckDB (`:memory:`) for speed

*(None — existing test infrastructure covers T04 and T05 with new assertions added to existing files)*

---

## Sources

### Primary (HIGH confidence)
- `schema.ocsf.io/1.7.0/categories` — OCSF class_uid values verified: 1001 File System, 1007 Process, 3002 Authentication, 4001 Network, 4003 DNS
- `duckdb.org/docs/current/sql/statements/alter_table` — ALTER TABLE ADD COLUMN syntax, one-column-per-statement limitation, DEFAULT value support
- Live source files: `backend/models/event.py`, `ingestion/normalizer.py`, `detections/field_map.py`, `ingestion/entity_extractor.py`, `graph/schema.py`, all four parsers — field names verified by direct read

### Secondary (MEDIUM confidence)
- ECS 8.x field reference (elastic.co/docs/reference/ecs) — field group names confirmed: `process.*`, `user.*`, `host.*`, `source.*`, `destination.*`, `file.*`, `network.*`, `event.*`, `dns.*`, `url.*`, `threat.*`
- pySigma processing pipelines docs (sigmahq-pysigma.readthedocs.io) — ECS pipeline maps `CommandLine` → `process.command_line`, `Image` → `process.name`

### Tertiary (LOW confidence)
- None — all critical claims verified from primary sources

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new dependencies; existing pydantic/duckdb/pytest stack covers all tasks
- Architecture: HIGH — both ECS field names and OCSF class_uid values verified from official sources; DuckDB ALTER TABLE syntax verified
- Pitfalls: HIGH — DuckDB one-column limitation is documented in official GitHub issues; Pydantic alias behaviour verified from pydantic 2.x docs pattern
- OCSF class_uid mapping: HIGH — verified from schema.ocsf.io/1.7.0/categories
- ECS field names: MEDIUM — field group structure confirmed; specific field-by-field mapping is from well-established ECS docs but not line-by-line verified for every entry

**Research date:** 2026-04-01
**Valid until:** 2026-07-01 (ECS and OCSF schemas are stable; DuckDB ALTER TABLE syntax stable in current release series)
