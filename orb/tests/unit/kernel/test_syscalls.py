"""Comprehensive tests for K os syscall interface.

Tests cover:
- Syscall registration and dispatch
- Performance (latency <0.1ms)
- Error handling
- Statistics tracking
- Core syscall implementations

Created: November 10, 2025
"""

from __future__ import annotations
from typing import Any

import pytest

pytestmark = pytest.mark.tier_unit


import asyncio
import time
from unittest.mock import AsyncMock, Mock, patch

from kagami.core.kernel.syscalls import (
    _SYSCALL_HANDLERS,
    KagamiOSSyscall,
    SyscallResult,
    get_syscall_stats,
    register_syscall,
    syscall_handler,
)


class TestSyscallInfrastructure:
    """Test syscall infrastructure."""

    def test_syscall_enum_values(self) -> None:
        """Test syscall numbers are unique and valid."""
        syscall_nums = [s.value for s in KagamiOSSyscall]

        # Check uniqueness
        assert len(syscall_nums) == len(set(syscall_nums))

        # Check range (0x00-0xFF)
        for num in syscall_nums:
            assert 0x00 <= num <= 0xFF

    def test_syscall_registration(self) -> None:
        """Test syscall handler registration."""

        async def test_handler(*args: Any, **kwargs) -> Any:
            return SyscallResult(success=True, data="test")

        # Register custom syscall
        test_num = 0xFF  # Use high number to avoid conflicts
        register_syscall(test_num, test_handler)  # type: ignore[arg-type]

        # Verify registered
        assert test_num in _SYSCALL_HANDLERS
        assert _SYSCALL_HANDLERS[test_num] == test_handler

    @pytest.mark.asyncio
    async def test_syscall_dispatch_success(self) -> Any:
        """Test successful syscall dispatch."""

        async def test_handler(*args: Any, **kwargs) -> Any:
            return SyscallResult(success=True, data={"result": "ok"})

        test_num = 0xFE
        register_syscall(test_num, test_handler)  # type: ignore[arg-type]

        result = await syscall_handler(test_num)

        assert result.success
        assert result.data == {"result": "ok"}
        assert result.duration_us > 0

    @pytest.mark.asyncio
    async def test_syscall_dispatch_error(self) -> Any:
        """Test syscall error handling."""

        async def error_handler(*args: Any, **kwargs) -> None:
            raise ValueError("Test error")

        test_num = 0xFD
        register_syscall(test_num, error_handler)  # type: ignore[arg-type]

        result = await syscall_handler(test_num)

        assert not result.success
        assert "Test error" in result.error  # type: ignore[operator]
        assert result.duration_us > 0

    @pytest.mark.asyncio
    async def test_syscall_unknown(self) -> None:
        """Test unknown syscall handling."""
        result = await syscall_handler(0x00)  # Unlikely to be registered

        # Should return error for unknown syscall
        # (unless 0x00 is actually registered)
        if not result.success:
            assert "Unknown syscall" in result.error  # type: ignore[operator]


class TestSyscallPerformance:
    """Test syscall performance targets."""

    @pytest.mark.asyncio
    async def test_syscall_latency(self) -> None:
        """Test syscall latency <0.1ms target."""

        async def fast_handler(*args: Any, **kwargs) -> Any:
            return SyscallResult(success=True)

        test_num = 0xFC
        register_syscall(test_num, fast_handler)  # type: ignore[arg-type]

        # Warm up
        for _ in range(10):
            await syscall_handler(test_num)

        # Measure latency
        latencies = []
        for _ in range(100):
            start = time.perf_counter()
            result = await syscall_handler(test_num)
            latency_us = (time.perf_counter() - start) * 1_000_000
            latencies.append(latency_us)

        avg_latency = sum(latencies) / len(latencies)
        p95_latency = sorted(latencies)[94]  # 95th percentile

        print(f"\nSyscall latency - avg: {avg_latency:.2f}μs, p95: {p95_latency:.2f}μs")

        # Target: <100μs (0.1ms)
        assert avg_latency < 100, f"Average latency {avg_latency:.2f}μs exceeds 100μs target"
        assert p95_latency < 200, f"P95 latency {p95_latency:.2f}μs exceeds 200μs target"

    @pytest.mark.asyncio
    async def test_syscall_throughput(self) -> None:
        """Test syscall throughput."""

        async def fast_handler(*args: Any, **kwargs) -> Any:
            return SyscallResult(success=True)

        test_num = 0xFB
        register_syscall(test_num, fast_handler)  # type: ignore[arg-type]

        # Measure throughput
        count = 1000
        start = time.perf_counter()

        for _ in range(count):
            await syscall_handler(test_num)

        duration = time.perf_counter() - start
        throughput = count / duration

        print(f"\nSyscall throughput: {throughput:.0f} calls/sec")

        # Should handle >10,000 syscalls/sec
        assert throughput > 10_000


class TestCoreSyscalls:
    """Test core syscall implementations."""

    @pytest.mark.asyncio
    async def test_sys_power_get_battery(self) -> None:
        """Test SYS_POWER_GET_BATTERY syscall."""
        # Mock HAL to avoid real system calls
        mock_hal = Mock()
        mock_hal.power = Mock()

        # Mock battery status
        mock_status = Mock()
        mock_status.level = 75.0
        mock_status.charging = True
        mock_status.plugged = True
        mock_status.voltage = 12.6
        mock_status.temperature_c = 25.0
        mock_status.time_remaining_minutes = 120.0

        mock_hal.power.get_battery_status = AsyncMock(return_value=mock_status)

        # Mock _get_hal to return our mock
        with patch("kagami.core.kernel.syscalls._get_hal", return_value=mock_hal):
            result = await syscall_handler(KagamiOSSyscall.SYS_POWER_GET_BATTERY)

        assert result.success
        assert "level" in result.data
        assert "charging" in result.data

        # Level should be 0-100 percentage (HAL standard)
        assert 0.0 <= result.data["level"] <= 100.0
        assert result.data["level"] == 75.0
        assert result.data["charging"] is True

    @pytest.mark.asyncio
    async def test_sys_agent_list(self) -> None:
        """Test SYS_AGENT_LIST syscall."""
        # Mock organism to avoid real system state
        mock_organism = Mock()
        mock_organism.colonies = {}

        # Create mock colony with workers
        mock_colony = Mock()
        mock_colony.domain = Mock()
        mock_colony.domain.value = "test_colony"
        mock_colony.workers = []

        # Add mock worker
        mock_worker = Mock()
        mock_worker.worker_id = "test_worker_1"
        mock_worker.fitness = 0.85
        mock_worker.state = Mock()
        mock_worker.state.created_at = time.time() - 10.0
        mock_colony.workers.append(mock_worker)

        mock_organism.colonies = {"test": mock_colony}

        # Patch where it's imported, not where it's defined
        with patch("kagami.core.unified_agents.get_unified_organism", return_value=mock_organism):
            result = await syscall_handler(KagamiOSSyscall.SYS_AGENT_LIST)

        assert result.success
        assert "agents" in result.data
        assert "total" in result.data
        assert isinstance(result.data["agents"], list)
        assert result.data["total"] == 1
        assert result.data["agents"][0]["id"] == "test_worker_1"


class TestSyscallStatistics:
    """Test syscall statistics tracking."""

    @pytest.mark.asyncio
    async def test_stats_tracking(self) -> None:
        """Test syscall statistics are tracked."""

        async def test_handler(*args: Any, **kwargs) -> Any:
            return SyscallResult(success=True)

        test_num = 0xFA
        register_syscall(test_num, test_handler)  # type: ignore[arg-type]

        # Get initial stats
        stats_before = get_syscall_stats()
        calls_before = stats_before["total_calls"]

        # Make some calls
        for _ in range(10):
            await syscall_handler(test_num)

        # Get updated stats
        stats_after = get_syscall_stats()

        assert stats_after["total_calls"] == calls_before + 10
        assert stats_after["avg_latency_us"] > 0

    @pytest.mark.asyncio
    async def test_error_rate_tracking(self) -> None:
        """Test error rate is tracked."""

        async def error_handler(*args: Any, **kwargs) -> None:
            raise ValueError("Test error")

        test_num = 0xF9
        register_syscall(test_num, error_handler)  # type: ignore[arg-type]

        # Get initial stats
        stats_before = get_syscall_stats()

        # Make failing calls
        for _ in range(5):
            await syscall_handler(test_num)

        # Get updated stats
        stats_after = get_syscall_stats()

        assert stats_after["failed_calls"] > stats_before["failed_calls"]
        assert stats_after["error_rate"] > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
