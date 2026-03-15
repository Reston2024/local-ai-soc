"""
Parser registry.

Maps file extensions to parser instances.  Parsers are singletons —
one instance is created at import time and shared across all calls.

Usage::

    from ingestion.registry import get_parser, register_parser

    parser = get_parser("security.evtx")
    if parser:
        for event in parser.parse("/data/security.evtx"):
            ...

    # Register a custom parser at runtime:
    register_parser(MyCustomParser())
"""

from __future__ import annotations

from ingestion.parsers.base import BaseParser
from ingestion.parsers.csv_parser import CsvParser
from ingestion.parsers.evtx_parser import EvtxParser
from ingestion.parsers.json_parser import JsonParser

# Default parser instances — order matters: first match wins.
_PARSERS: list[BaseParser] = [
    EvtxParser(),
    JsonParser(),
    CsvParser(),
]


def get_parser(filename: str) -> BaseParser | None:
    """
    Return the first registered parser that claims to handle *filename*.

    Matching is based on file extension (case-insensitive).

    Args:
        filename: Bare filename or full path — only the suffix is used.

    Returns:
        A BaseParser instance, or None if no parser supports the extension.
    """
    for parser in _PARSERS:
        if parser.can_handle(filename):
            return parser
    return None


def register_parser(parser: BaseParser) -> None:
    """
    Add *parser* to the registry.

    The new parser is appended at the end of the list, so default parsers
    take priority.  To override a built-in, insert at position 0::

        _PARSERS.insert(0, MyHighPriorityParser())

    Args:
        parser: A fully-initialised BaseParser subclass instance.
    """
    _PARSERS.append(parser)


def list_parsers() -> list[BaseParser]:
    """Return a shallow copy of the current parser list (read-only view)."""
    return list(_PARSERS)
