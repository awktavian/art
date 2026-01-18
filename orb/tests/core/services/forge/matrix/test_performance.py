"""Tests for forge matrix performance module."""

from __future__ import annotations

from typing import Any

import pytest

pytestmark = pytest.mark.tier_integration


import asyncio
import time

from kagami.forge.matrix.performance import (
    PerformanceViolationError,
    monitor_performance,
)


class TestMonitorPerformance:
    """Tests for monitor_performance decorator."""

    @pytest.mark.asyncio
    async def test_decorator_basic(self) -> None:
        """Test basic decorator functionality."""

        @monitor_performance("test_operation")
        async def fast_operation():
            return "result"

        result = await fast_operation()

        assert result == "result"

    @pytest.mark.asyncio
    async def test_decorator_with_latency_limit(self) -> None:
        """Test decorator with custom latency limit."""

        @monitor_performance("test_operation", max_latency_ms=1000)
        async def fast_operation():
            return "result"

        result = await fast_operation()

        assert result == "result"

    @pytest.mark.asyncio
    async def test_decorator_preserves_function_metadata(self) -> None:
        """Test decorator preserves function name and docstring."""

        @monitor_performance("test_operation")
        async def documented_function():
            """This is documentation."""
            return "result"

        assert documented_function.__name__ == "documented_function"
        assert "documentation" in documented_function.__doc__

    @pytest.mark.asyncio
    async def test_decorator_with_args_kwargs(self) -> None:
        """Test decorator with function arguments."""

        @monitor_performance("test_operation")
        async def operation_with_args(a, b, c=10):
            return a + b + c

        result = await operation_with_args(1, 2, c=3)

        assert result == 6

    @pytest.mark.asyncio
    async def test_decorator_passes_through_exceptions(self) -> None:
        """Test decorator passes through exceptions."""

        @monitor_performance("test_operation")
        async def failing_operation():
            raise ValueError("Test error")

        with pytest.raises(ValueError, match="Test error"):
            await failing_operation()

    @pytest.mark.asyncio
    async def test_decorator_attaches_metadata_to_dict_result(self) -> None:
        """Test decorator may attach performance metadata to dict results."""

        @monitor_performance("test_operation")
        async def operation_returning_dict():
            return {"key": "value"}

        result = await operation_returning_dict()

        # Result should still have original data
        assert result["key"] == "value"

    @pytest.mark.asyncio
    async def test_decorator_logs_warning_near_limit(self) -> None:
        """Test warning is logged when approaching limit."""

        @monitor_performance("test_operation", max_latency_ms=100)
        async def slow_operation():
            await asyncio.sleep(0.09)  # 90ms - near warning threshold (80%)
            return "result"

        # Should complete without error
        result = await slow_operation()
        assert result == "result"


class TestPerformanceViolationError:
    """Tests for PerformanceViolationError exception."""

    def test_creation(self) -> None:
        """Test exception creation."""
        error = PerformanceViolationError("Operation too slow")

        assert "Operation too slow" in str(error)
        assert isinstance(error, Exception)
