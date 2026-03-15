"""
Abstract base class for all ingestion parsers.

Every concrete parser must implement parse() and declare its
supported_extensions class variable.  The registry uses can_handle()
to route files to the right parser without instantiating every one.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterator

from backend.models.event import NormalizedEvent


class BaseParser(ABC):
    """
    Minimal interface every file-format parser must implement.

    Subclasses set ``supported_extensions`` to a list of lower-case
    extensions including the leading dot, e.g. ``[".evtx"]``.
    """

    supported_extensions: list[str] = []

    @abstractmethod
    def parse(
        self,
        file_path: str,
        case_id: str | None = None,
    ) -> Iterator[NormalizedEvent]:
        """
        Parse *file_path* and yield fully-populated NormalizedEvent objects.

        Implementations must stream events — do **not** read the entire file
        into memory before yielding.

        Args:
            file_path: Absolute path to the file on disk.
            case_id:   Optional investigation case to associate events with.

        Yields:
            NormalizedEvent instances with at minimum ``event_id``,
            ``timestamp``, ``ingested_at``, and ``source_type`` populated.
        """
        ...

    def can_handle(self, filename: str) -> bool:
        """
        Return True if this parser supports the given filename's extension.

        The check is case-insensitive and handles filenames with or without
        path components.

        Args:
            filename: Bare filename or full path (only the extension matters).
        """
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        return f".{ext}" in [e.lower() for e in self.supported_extensions]
