"""
Structured JSON logging for the AI-SOC-Brain backend.

Sets up a root logger that emits JSON lines to:
  - stderr (console)
  - logs/backend.jsonl (rotating file, 10 MB × 5 backups)

Usage:
    from backend.core.logging import get_logger
    log = get_logger(__name__)
    log.info("event ingested", event_id="abc123", source="evtx")
"""

import json
import logging
import logging.handlers
import os
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_INITIALIZED = False


class _JsonFormatter(logging.Formatter):
    """
    Serialise every log record as a single JSON line.

    The ``extra`` dict passed to log calls is merged into the top-level
    JSON object so callers can do:
        log.info("msg", extra={"event_id": "x"})
    or, with the LoggerAdapter wrapper below:
        log.info("msg", event_id="x")
    """

    # Keys that belong to the LogRecord itself — not forwarded as context.
    _RESERVED = frozenset(
        {
            "name", "msg", "args", "levelname", "levelno", "pathname",
            "filename", "module", "exc_info", "exc_text", "stack_info",
            "lineno", "funcName", "created", "msecs", "relativeCreated",
            "thread", "threadName", "processName", "process", "message",
            "taskName",
        }
    )

    def format(self, record: logging.LogRecord) -> str:  # noqa: A003
        record.message = record.getMessage()

        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "component": record.name,
            "message": record.message,
        }

        # Merge any extra fields injected by the caller.
        for key, value in record.__dict__.items():
            if key not in self._RESERVED and not key.startswith("_"):
                payload[key] = value

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        if record.stack_info:
            payload["stack"] = self.formatStack(record.stack_info)

        try:
            return json.dumps(payload, default=str)
        except Exception:
            # Fallback: at least emit something
            payload = {
                "timestamp": payload["timestamp"],
                "level": "ERROR",
                "component": "logging",
                "message": "Failed to serialise log record",
                "original_message": str(record.message),
            }
            return json.dumps(payload)


class _KwargsAdapter(logging.LoggerAdapter):
    """
    Allows callers to pass keyword arguments directly:
        log.info("started", port=8000, host="127.0.0.1")

    The kwargs are merged into ``extra`` so they appear in the JSON output.
    """

    def process(
        self, msg: str, kwargs: dict[str, Any]
    ) -> tuple[str, dict[str, Any]]:
        extra = dict(self.extra or {})
        # Pull out any keys that are not standard logging kwargs
        _log_kwargs = {"exc_info", "stack_info", "stacklevel", "extra"}
        for key in list(kwargs.keys()):
            if key not in _log_kwargs:
                value = kwargs.pop(key)
                # Rename keys that collide with LogRecord reserved attributes
                # to avoid KeyError in logging.makeRecord.
                safe_key = f"ctx_{key}" if key in _JsonFormatter._RESERVED else key
                extra[safe_key] = value
        kwargs["extra"] = extra
        return msg, kwargs


def setup_logging(log_level: str = "INFO", log_dir: str = "logs") -> None:
    """
    Configure root logger once at application startup.

    Calling this function multiple times is safe (idempotent).
    """
    global _INITIALIZED
    if _INITIALIZED:
        return

    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    root = logging.getLogger()
    root.setLevel(numeric_level)

    # Remove any handlers that might have been set by imported libraries
    # before we had a chance to configure logging.
    root.handlers.clear()

    formatter = _JsonFormatter()

    # --- Console handler ---
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(formatter)
    root.addHandler(console_handler)

    # --- File handler (JSONL, rotating) ---
    try:
        log_path = Path(log_dir)
        log_path.mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            log_path / "backend.jsonl",
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setLevel(numeric_level)
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)
    except OSError as exc:
        # If we cannot write to the log directory, continue with console only.
        root.warning("Could not open log file: %s", exc)

    _INITIALIZED = True


def get_logger(name: str) -> _KwargsAdapter:
    """
    Return a structured logger for the given component name.

    Example::

        log = get_logger(__name__)
        log.info("connection opened", host="127.0.0.1", port=8000)
    """
    return _KwargsAdapter(logging.getLogger(name), {})
