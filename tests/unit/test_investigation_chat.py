"""
Wave-0 test stub: output contract for backend/api/chat.py.

These tests are intentionally RED until plan 14-04 implements
CHAT_MESSAGES_DDL and ChatMessage pydantic model.
"""

import pytest

try:
    from backend.api.chat import CHAT_MESSAGES_DDL, ChatMessage
except ImportError:
    CHAT_MESSAGES_DDL = None  # type: ignore
    ChatMessage = None  # type: ignore


# ---------------------------------------------------------------------------
# CHAT_MESSAGES_DDL — SQLite DDL contract
# ---------------------------------------------------------------------------


def test_chat_messages_ddl_create_table():
    """CHAT_MESSAGES_DDL contains CREATE TABLE IF NOT EXISTS chat_messages."""
    assert CHAT_MESSAGES_DDL is not None, "backend.api.chat not implemented yet"
    assert "CREATE TABLE IF NOT EXISTS chat_messages" in CHAT_MESSAGES_DDL


def test_chat_messages_ddl_columns():
    """CHAT_MESSAGES_DDL defines all required columns."""
    assert CHAT_MESSAGES_DDL is not None, "backend.api.chat not implemented yet"
    required_columns = [
        "id",
        "investigation_id",
        "role",
        "content",
        "created_at",
    ]
    ddl_lower = CHAT_MESSAGES_DDL.lower()
    for col in required_columns:
        assert col in ddl_lower, f"Column '{col}' missing from CHAT_MESSAGES_DDL"


# ---------------------------------------------------------------------------
# ChatMessage pydantic model
# ---------------------------------------------------------------------------


def test_chat_message_model_fields():
    """ChatMessage pydantic model has investigation_id, role, content fields."""
    assert ChatMessage is not None, "backend.api.chat not implemented yet"
    msg = ChatMessage(
        investigation_id="inv-001",
        role="user",
        content="What processes ran on this host?",
    )
    assert msg.investigation_id == "inv-001"
    assert msg.role == "user"
    assert msg.content == "What processes ran on this host?"


# ---------------------------------------------------------------------------
# P16-SEC-03c: LLM audit logger smoke test
# ---------------------------------------------------------------------------


def test_llm_audit_logger_has_handler(tmp_path):
    """When setup_logging() is called, the llm_audit logger must have at least one configured file handler."""
    import logging
    import backend.core.logging as _logging_mod

    # Reset the initialization flag so setup_logging() runs fully
    original_initialized = _logging_mod._INITIALIZED
    _logging_mod._INITIALIZED = False

    try:
        from backend.core.logging import setup_logging
        setup_logging(log_level="INFO", log_dir=str(tmp_path / "test_logs_audit"))
        audit_logger = logging.getLogger("llm_audit")
        assert len(audit_logger.handlers) >= 1, "llm_audit logger must have file handler configured"
        assert not audit_logger.propagate, "llm_audit must not propagate to root logger"
    finally:
        # Restore state so subsequent tests are unaffected
        _logging_mod._INITIALIZED = original_initialized
