import pytest
from unittest.mock import MagicMock


class TestRequireRole:
    @pytest.mark.asyncio
    async def test_require_role_pass(self):
        """require_role('admin') dep returns ctx when role == 'admin'."""
        pytest.fail("NOT IMPLEMENTED")

    @pytest.mark.asyncio
    async def test_require_role_403(self):
        """require_role('admin') dep raises HTTPException(403) when role == 'analyst'."""
        pytest.fail("NOT IMPLEMENTED")

    @pytest.mark.asyncio
    async def test_require_role_multiple_allowed(self):
        """require_role('admin', 'analyst') passes for analyst."""
        pytest.fail("NOT IMPLEMENTED")
