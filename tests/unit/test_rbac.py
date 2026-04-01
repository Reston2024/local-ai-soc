import pytest
from unittest.mock import MagicMock

from fastapi import HTTPException

from backend.core.rbac import OperatorContext, require_role


class TestRequireRole:
    @pytest.mark.asyncio
    async def test_require_role_pass(self):
        """require_role('admin') dep returns ctx when role == 'admin'."""
        ctx = OperatorContext(operator_id="op-1", username="alice", role="admin")
        dep = require_role("admin")
        mock_request = MagicMock()
        result = await dep(request=mock_request, ctx=ctx)
        assert result.role == "admin"
        assert result is ctx

    @pytest.mark.asyncio
    async def test_require_role_403(self):
        """require_role('admin') dep raises HTTPException(403) when role == 'analyst'."""
        ctx = OperatorContext(operator_id="op-2", username="bob", role="analyst")
        dep = require_role("admin")
        mock_request = MagicMock()
        with pytest.raises(HTTPException) as exc_info:
            await dep(request=mock_request, ctx=ctx)
        assert exc_info.value.status_code == 403
        assert "analyst" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_require_role_multiple_allowed(self):
        """require_role('admin', 'analyst') passes for analyst."""
        ctx = OperatorContext(operator_id="op-3", username="carol", role="analyst")
        dep = require_role("admin", "analyst")
        mock_request = MagicMock()
        result = await dep(request=mock_request, ctx=ctx)
        assert result.role == "analyst"
        assert result is ctx
