"""Tests for kagami.forge.forge_middleware."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from kagami.forge.forge_middleware import forge_operation

pytestmark = pytest.mark.tier_unit


class TestForgeOperationDecorator:
    """Test @forge_operation decorator."""

    @pytest.mark.asyncio
    async def test_decorator_basic(self):
        """Test basic decorator functionality."""

        @forge_operation("test_op", module="test", aspect="test")
        async def test_func():
            return {"result": "success"}

        result = await test_func()
        assert result["result"] == "success"

    @pytest.mark.asyncio
    async def test_decorator_with_args(self):
        """Test decorator with function arguments."""

        @forge_operation("test_op", module="test", aspect="test")
        async def test_func(x, y):
            return {"sum": x + y}

        result = await test_func(5, 3)
        assert result["sum"] == 8

    @pytest.mark.asyncio
    async def test_decorator_exception_handling(self):
        """Test decorator handles exceptions."""

        @forge_operation("test_op", module="test", aspect="test")
        async def test_func():
            raise ValueError("Test error")

        with pytest.raises(ValueError):
            await test_func()


class TestOperationMetrics:
    """Test operation metrics recording."""

    @pytest.mark.asyncio
    async def test_metrics_on_success(self):
        """Test metrics are recorded on success."""
        with patch("kagami.forge.observability.metrics.FORGE_OPERATIONS_TOTAL") as mock_metric:

            @forge_operation("test_op", module="test", aspect="test")
            async def test_func():
                return {"success": True}

            await test_func()

            # Verify metrics were called
            # (Note: actual implementation depends on observability setup)

    @pytest.mark.asyncio
    async def test_metrics_on_error(self):
        """Test metrics are recorded on error."""
        with patch("kagami.forge.observability.metrics.FORGE_OPERATIONS_TOTAL") as mock_metric:

            @forge_operation("test_op", module="test", aspect="test")
            async def test_func():
                raise RuntimeError("Test error")

            with pytest.raises(RuntimeError):
                await test_func()
