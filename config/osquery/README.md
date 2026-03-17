# osquery Configuration

This directory contains the osquery configuration for the AI-SOC-Brain telemetry pipeline.

## Scheduled Queries

| Query Name       | Interval | Description                                              |
|------------------|----------|----------------------------------------------------------|
| `process_events` | 30s      | Running processes snapshot for process ancestry analysis |
| `network_events` | 60s      | Open sockets snapshot for network connection analysis    |
| `user_events`    | 60s      | Logged-in users snapshot for lateral movement detection  |
| `file_events`    | 120s     | System32 EXE/DLL snapshot for DLL hijacking detection   |

## Installation

### 1. Install osquery

```powershell
winget install osquery.osquery
```

### 2. Copy configuration

```powershell
Copy-Item "config\osquery\osquery.conf" "C:\Program Files\osquery\osquery.conf"
```

### 3. Enable in .env

Add or update in your `.env` file:

```
OSQUERY_ENABLED=True
OSQUERY_LOG_PATH=C:\Program Files\osquery\log\osqueryd.results.log
```

### 4. Fix ACL for service log access

The osquery Windows service writes logs as SYSTEM. Grant read access so the
AI-SOC-Brain backend (running as your user) can tail the log file:

```powershell
icacls "C:\Program Files\osquery\log" /grant Users:R
```

### 5. Start the osquery service

```powershell
Start-Service osqueryd
# or
net start osqueryd
```

## Verification

Check the telemetry status endpoint once the backend is running:

```powershell
Invoke-RestMethod http://localhost:8000/api/telemetry/osquery/status
```

Expected response when enabled and running:

```json
{
  "enabled": true,
  "log_path": "C:\\Program Files\\osquery\\log\\osqueryd.results.log",
  "log_exists": true,
  "running": true,
  "lines_processed": 0,
  "error": null
}
```

## Log Format

osquery snapshot queries emit newline-delimited JSON (NDJSON) to the log file.
Each line is a JSON object with `name`, `hostIdentifier`, `calendarTime`, `columns`, and `action` fields.
The AI-SOC-Brain ingestion pipeline parses this format via `ingestion/parsers/osquery.py`.
