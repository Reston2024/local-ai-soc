# Sigma Rules Directory

Place your Sigma detection rule files (`.yml`) in this directory. Rules are loaded automatically when `POST /api/detect/run` is called.

## How It Works

1. The detection engine scans `rules/sigma/` (this directory) and `fixtures/sigma/` (development fixtures) for `.yml` files.
2. Each file is parsed as a [Sigma rule](https://sigmahq.io/sigma-specification/) and compiled to a DuckDB SQL query.
3. Rules are matched against the `normalized_events` table. Matches produce `DetectionRecord` entries stored in SQLite.

**Important:** If both directories are empty or missing, `POST /api/detect/run` returns HTTP 422 with the message "No Sigma rules loaded". This prevents silent false-negative results where 0 detections could mean either a clean environment or a misconfigured rules path.

## Example Rule Skeleton

```yaml
title: Suspicious Process Execution
id: 12345678-1234-1234-1234-123456789abc
status: experimental
description: Detects execution of a suspicious process
references:
  - https://example.com
author: Your Name
date: 2026/01/01
tags:
  - attack.execution
  - attack.t1059
logsource:
  product: windows
  category: process_creation
detection:
  selection:
    EventID: 4688
    NewProcessName|contains: 'powershell.exe'
  condition: selection
fields:
  - EventID
  - NewProcessName
  - SubjectUserName
falsepositives:
  - Legitimate administrative use
level: medium
```

## Supported Sigma Modifiers

The AI-SOC-Brain custom DuckDB Sigma backend supports these modifiers:

| Modifier         | SQL Translation                    |
|------------------|------------------------------------|
| (none)           | `= 'value'` or `IN ('a', 'b')`    |
| `\|contains`     | `LIKE '%value%'`                   |
| `\|startswith`   | `LIKE 'value%'`                    |
| `\|endswith`     | `LIKE '%value'`                    |
| `\|contains\|all`| Multiple `LIKE` joined with `AND`  |
| `\|re`           | `SIMILAR TO` (limited support)     |

## Development vs Production Rules

- `fixtures/sigma/` — Development and test fixtures only. Do not use in production.
- `rules/sigma/` (this directory) — Operator-managed production rules. Add your `.yml` rule files here.

Subdirectories are scanned recursively, so you can organise rules into sub-folders (e.g. `rules/sigma/windows/`, `rules/sigma/linux/`).
