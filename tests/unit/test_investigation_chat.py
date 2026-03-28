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
