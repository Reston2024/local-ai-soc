"""
Windows Event Log live collector — polls Sysmon, Security, and PowerShell channels.

Uses PowerShell Get-WinEvent via subprocess to read live Windows event log channels
without requiring WEF or file access (works even on locked .evtx files).

Channels polled:
  - Microsoft-Windows-Sysmon/Operational   (EventIDs 1-29 — process, network, file, registry)
  - Security                                (EventIDs 4624/4625/4648/4672/4688/4697/4698/4720)
  - Microsoft-Windows-PowerShell/Operational (EventIDs 4103/4104 — script block logging)
  - Microsoft-Windows-WMI-Activity/Operational (EventIDs 5857-5861 — WMI persistence)
  - Microsoft-Windows-TaskScheduler/Operational (EventIDs 106/141/200/201 — task scheduling)

Pattern:
  - asyncio poll loop with configurable interval (default 30s)
  - Timestamp cursor per channel stored in system_kv (winevent.<channel>.last_timestamp)
  - Ingest via IngestionLoader.ingest_events()
  - Exponential backoff on subprocess/parse failures
  - status() returns dict for /api/status endpoint
"""
from __future__ import annotations

import asyncio
import json
import subprocess
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from backend.core.logging import get_logger
from backend.models.event import NormalizedEvent

log = get_logger(__name__)

# Sysmon EventID → canonical event_type
_SYSMON_EVENT_TYPES: dict[int, str] = {
    1:  "process_create",
    2:  "file_creation_time_changed",
    3:  "network_connect",
    5:  "process_terminate",
    6:  "driver_load",
    7:  "image_load",
    8:  "create_remote_thread",
    9:  "raw_access_read",
    10: "process_access",
    11: "file_create",
    12: "registry_event",
    13: "registry_value_set",
    14: "registry_key_rename",
    15: "file_create_stream_hash",
    16: "sysmon_config_change",
    17: "pipe_created",
    18: "pipe_connected",
    19: "wmi_event_filter_activity",
    20: "wmi_event_consumer_activity",
    21: "wmi_event_consumer_to_filter_activity",
    22: "dns_query",
    23: "file_delete",
    25: "process_tamper",
    26: "file_delete_detected",
    29: "file_executable_detected",
}

# Security EventID → canonical event_type
_SECURITY_EVENT_TYPES: dict[int, str] = {
    4624: "logon",
    4625: "logon_failure",
    4648: "logon_explicit_cred",
    4672: "special_logon",
    4688: "process_create",
    4697: "service_installed",
    4698: "scheduled_task_created",
    4699: "scheduled_task_deleted",
    4700: "scheduled_task_enabled",
    4701: "scheduled_task_disabled",
    4702: "scheduled_task_updated",
    4720: "user_account_created",
    4722: "user_account_enabled",
    4725: "user_account_disabled",
    4726: "user_account_deleted",
    4732: "user_added_to_group",
    4756: "user_added_to_global_group",
    4768: "kerberos_ticket_requested",
    4769: "kerberos_service_ticket_requested",
    4771: "kerberos_pre_auth_failed",
}

# PowerShell / WMI / TaskScheduler
_POWERSHELL_EVENT_TYPES: dict[int, str] = {
    4103: "powershell_module_logging",
    4104: "powershell_script_block",
    4105: "powershell_command_start",
    4106: "powershell_command_stop",
    # PowerShell engine lifecycle events
    40961: "powershell_console_start",
    40962: "powershell_console_ready",
    53504: "powershell_ipc_thread",
    # PowerShell pipeline events (Operational channel)
    4100: "powershell_error",
    4101: "powershell_execute_pipeline",
    4102: "powershell_complete_pipeline",
}

_WMI_EVENT_TYPES: dict[int, str] = {
    5857: "wmi_activity",
    5858: "wmi_activity_error",
    5859: "wmi_subscription_event",
    5860: "wmi_temporary_subscription",
    5861: "wmi_permanent_subscription",
}

_TASK_EVENT_TYPES: dict[int, str] = {
    106:  "scheduled_task_registered",
    141:  "scheduled_task_deleted",
    200:  "scheduled_task_started",
    201:  "scheduled_task_completed",
    319:  "scheduled_task_failed",
}

# Channel configs: (cursor_key, log_name, event_type_map, max_events_per_poll)
_CHANNELS = [
    (
        "winevent.sysmon.last_timestamp",
        "Microsoft-Windows-Sysmon/Operational",
        _SYSMON_EVENT_TYPES,
        500,
    ),
    (
        "winevent.security.last_timestamp",
        "Security",
        _SECURITY_EVENT_TYPES,
        500,
    ),
    (
        "winevent.powershell.last_timestamp",
        "Microsoft-Windows-PowerShell/Operational",
        _POWERSHELL_EVENT_TYPES,
        200,
    ),
    (
        "winevent.wmi.last_timestamp",
        "Microsoft-Windows-WMI-Activity/Operational",
        _WMI_EVENT_TYPES,
        100,
    ),
    (
        "winevent.taskscheduler.last_timestamp",
        "Microsoft-Windows-TaskScheduler/Operational",
        _TASK_EVENT_TYPES,
        100,
    ),
]

_POWERSHELL_EXE = "powershell.exe"


def _get_events_ps(log_name: str, after_ts: str | None, max_count: int) -> list[dict]:
    """
    Call Get-WinEvent via subprocess and return parsed JSON list of events.

    Each event dict has keys: TimeCreated, Id, LevelDisplayName, Message,
    MachineName, UserId, ProviderName, plus a Properties array.
    """
    if after_ts:
        # XPath filter for events after a timestamp.
        # Use double-quotes inside XPath value to avoid clashing with PS outer single-quotes.
        # XPath datetime format: 2026-04-13T00:00:00 (no ms, no Z)
        dt_str = after_ts.rstrip("Z").split(".")[0]
        xpath_filter = f'*[System[TimeCreated[@SystemTime > "{dt_str}"]]]'
        # -FilterXPath is the filter parameter; also add -MaxEvents to cap results
        ps_script = (
            f"Get-WinEvent -LogName '{log_name}' -FilterXPath '{xpath_filter}' "
            f"-MaxEvents {max_count} "
            f"-ErrorAction SilentlyContinue 2>$null | "
            f"Select-Object TimeCreated, Id, LevelDisplayName, MachineName, UserId, Message, "
            f"@{{n='ProviderName';e={{$_.ProviderName}}}} | "
            f"ConvertTo-Json -Depth 3 -Compress 2>$null"
        )
    else:
        # No cursor yet — just get the most recent N events
        ps_script = (
            f"Get-WinEvent -LogName '{log_name}' -MaxEvents {max_count} "
            f"-ErrorAction SilentlyContinue 2>$null | "
            f"Select-Object TimeCreated, Id, LevelDisplayName, MachineName, UserId, Message, "
            f"@{{n='ProviderName';e={{$_.ProviderName}}}} | "
            f"ConvertTo-Json -Depth 3 -Compress 2>$null"
        )

    try:
        result = subprocess.run(
            [_POWERSHELL_EXE, "-NonInteractive", "-NoProfile", "-Command", ps_script],
            capture_output=True,
            text=True,
            timeout=60,
        )
        stdout = result.stdout.strip()
        if not stdout:
            return []

        # ConvertTo-Json returns a single object if only 1 result (not array)
        if stdout.startswith("{"):
            return [json.loads(stdout)]
        return json.loads(stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError) as exc:
        log.warning("winevent_collector: Get-WinEvent failed for %s: %s", log_name, exc)
        return []


def _normalize_event(
    raw: dict[str, Any],
    log_name: str,
    event_type_map: dict[int, str],
) -> NormalizedEvent | None:
    """Convert a raw Get-WinEvent dict to NormalizedEvent."""
    try:
        event_id_raw = raw.get("Id")
        event_id_int = int(event_id_raw) if event_id_raw is not None else None

        # Parse timestamp — PowerShell ConvertTo-Json emits /Date(ms)/ or ISO string
        ts_raw = raw.get("TimeCreated") or ""
        timestamp = _parse_ps_timestamp(ts_raw)

        # Map event type
        event_type = None
        if event_id_int is not None:
            event_type = event_type_map.get(event_id_int)

        message = str(raw.get("Message") or "")[:8192]
        machine = raw.get("MachineName") or ""
        # UserId can be a SecurityIdentifier dict from ConvertTo-Json — extract SID string
        user_sid_raw = raw.get("UserId")
        if isinstance(user_sid_raw, dict):
            # SID dict: {'Value': 'S-1-5-21-...', 'BinaryLength': ..., ...}
            user_sid = user_sid_raw.get("Value") or str(user_sid_raw)
        else:
            user_sid = str(user_sid_raw) if user_sid_raw else ""

        # Extract common fields from Message text (Sysmon structured output)
        fields = _extract_message_fields(message)

        return NormalizedEvent(
            event_id=str(uuid4()),
            timestamp=timestamp,
            ingested_at=datetime.now(tz=timezone.utc),
            source_type="winevent",
            source_file=log_name,
            hostname=machine or None,
            username=fields.get("User") or fields.get("SubjectUserName") or (user_sid or None),
            process_name=fields.get("Image") or fields.get("NewProcessName") or fields.get("ProcessName"),
            process_id=_safe_int(fields.get("ProcessId") or fields.get("NewProcessId")),
            parent_process_name=fields.get("ParentImage") or fields.get("ParentProcessName"),
            parent_process_id=_safe_int(fields.get("ParentProcessId")),
            command_line=fields.get("CommandLine"),
            file_path=fields.get("TargetFilename") or fields.get("TargetObject"),
            file_hash_sha256=_extract_sha256(fields.get("Hashes", "")),
            src_ip=fields.get("SourceIp"),
            src_port=_safe_int(fields.get("SourcePort")),
            dst_ip=fields.get("DestinationIp"),
            dst_port=_safe_int(fields.get("DestinationPort")),
            domain=fields.get("QueryName") or fields.get("DestinationHostname"),
            event_type=event_type,
            raw_event=json.dumps({"EventID": event_id_int, "Channel": log_name, "Message": message[:2048]}),
        )
    except Exception as exc:
        log.debug("winevent_collector: normalize error: %s", exc)
        return None


def _parse_ps_timestamp(ts_raw: Any) -> datetime:
    """Parse PowerShell ConvertTo-Json timestamp formats to datetime."""
    if not ts_raw:
        return datetime.now(tz=timezone.utc)

    # /Date(1713024000000)/ format
    ts_str = str(ts_raw)
    if ts_str.startswith("/Date("):
        try:
            ms = int(ts_str[6:ts_str.index(")")])
            return datetime.fromtimestamp(ms / 1000, tz=timezone.utc)
        except (ValueError, IndexError):
            pass

    # ISO 8601 format
    try:
        return datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
    except ValueError:
        pass

    return datetime.now(tz=timezone.utc)


def _extract_message_fields(message: str) -> dict[str, str]:
    """
    Parse Sysmon/Security event Message text into a flat field dict.

    Sysmon messages are line-oriented: "FieldName: value"
    """
    fields: dict[str, str] = {}
    for line in message.splitlines():
        if ":" in line:
            key, _, val = line.partition(":")
            key = key.strip()
            val = val.strip()
            if key and val:
                fields[key] = val
    return fields


def _extract_sha256(hashes_str: str) -> str | None:
    """Extract SHA256 from 'MD5=abc,SHA256=def,SHA1=ghi' format."""
    if not hashes_str:
        return None
    for part in hashes_str.split(","):
        if part.upper().startswith("SHA256="):
            return part.split("=", 1)[1].strip()
    return None


def _safe_int(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (ValueError, TypeError):
        return None


class WinEventCollector:
    """Background asyncio task: poll Windows Event Log channels and ingest events."""

    def __init__(
        self,
        loader=None,
        sqlite_store=None,
        interval_sec: int = 30,
    ) -> None:
        self._loader = loader
        self._sqlite = sqlite_store
        self._interval = interval_sec
        self._running = False
        self._consecutive_failures = 0
        self._total_ingested = 0
        self._last_poll: datetime | None = None
        self._available_channels: list[str] = []

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start the polling loop."""
        log.info("WinEventCollector: starting (interval=%ds)", self._interval)
        self._running = True
        await self._detect_available_channels()
        while self._running:
            try:
                await self._poll_all_channels()
                self._consecutive_failures = 0
            except Exception as exc:
                self._consecutive_failures += 1
                backoff = min(300, 30 * self._consecutive_failures)
                log.warning(
                    "WinEventCollector: poll error (failure #%d), backing off %ds: %s",
                    self._consecutive_failures,
                    backoff,
                    exc,
                )
                await asyncio.sleep(backoff)
                continue
            await asyncio.sleep(self._interval)

    async def stop(self) -> None:
        self._running = False

    def status(self) -> dict:
        return {
            "running": self._running,
            "total_ingested": self._total_ingested,
            "last_poll": self._last_poll.isoformat() if self._last_poll else None,
            "consecutive_failures": self._consecutive_failures,
            "available_channels": self._available_channels,
            "interval_sec": self._interval,
        }

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _detect_available_channels(self) -> None:
        """Quick check which channels actually exist on this machine."""
        available = []
        for cursor_key, log_name, _, _ in _CHANNELS:
            ps_check = f"Get-WinEvent -ListLog '{log_name}' -ErrorAction SilentlyContinue | Select-Object -ExpandProperty LogName"
            result = await asyncio.to_thread(
                subprocess.run,
                [_POWERSHELL_EXE, "-NonInteractive", "-NoProfile", "-Command", ps_check],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0 and log_name.lower() in result.stdout.lower():
                available.append(log_name)
                log.info("WinEventCollector: channel available: %s", log_name)
            else:
                log.info("WinEventCollector: channel NOT available (will retry): %s", log_name)

        self._available_channels = available

    async def _get_cursor(self, key: str) -> str | None:
        """Retrieve last ingested timestamp for a channel."""
        if self._sqlite is None:
            return None
        try:
            return await asyncio.to_thread(self._sqlite.get_kv, key)
        except Exception:
            return None

    async def _set_cursor(self, key: str, value: str) -> None:
        """Store last ingested timestamp for a channel."""
        if self._sqlite is None:
            return
        try:
            await asyncio.to_thread(self._sqlite.set_kv, key, value)
        except Exception as exc:
            log.warning("WinEventCollector: set_kv failed for %s: %s", key, exc)

    async def _poll_all_channels(self) -> None:
        """Poll each configured channel and ingest new events."""
        self._last_poll = datetime.now(tz=timezone.utc)

        for cursor_key, log_name, event_type_map, max_count in _CHANNELS:
            # Only poll channels we've confirmed exist (re-detect periodically via start loop)
            if self._available_channels and log_name not in self._available_channels:
                continue

            await self._poll_channel(cursor_key, log_name, event_type_map, max_count)

    async def _poll_channel(
        self,
        cursor_key: str,
        log_name: str,
        event_type_map: dict[int, str],
        max_count: int,
    ) -> None:
        """Poll a single event log channel and ingest new events."""
        last_ts = await self._get_cursor(cursor_key)

        # Get events from PowerShell in a thread (subprocess is blocking)
        raw_events = await asyncio.to_thread(
            _get_events_ps, log_name, last_ts, max_count
        )

        if not raw_events:
            return

        # Normalize
        normalized: list[NormalizedEvent] = []
        newest_ts: str | None = None

        for raw in raw_events:
            evt = _normalize_event(raw, log_name, event_type_map)
            if evt is None:
                continue
            normalized.append(evt)
            # Track newest timestamp for cursor
            ts_str = evt.timestamp.isoformat().replace("+00:00", "Z")
            if newest_ts is None or ts_str > newest_ts:
                newest_ts = ts_str

        if not normalized:
            return

        # Ingest
        if self._loader is not None:
            try:
                await self._loader.ingest_events(normalized)
                self._total_ingested += len(normalized)
                log.info(
                    "WinEventCollector: ingested %d events from %s",
                    len(normalized),
                    log_name,
                )
            except Exception as exc:
                log.warning("WinEventCollector: ingest failed for %s: %s", log_name, exc)
                return

        # Advance cursor
        if newest_ts:
            await self._set_cursor(cursor_key, newest_ts)
