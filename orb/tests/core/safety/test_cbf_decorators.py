"""Unit tests for CBF decorators.

Tests all decorator variants and edge cases to ensure >90% coverage.

CREATED: December 14, 2025
AUTHOR: Forge (e₂)
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tier_integration


import asyncio
import gc
import logging
import time
from typing import Any
from unittest.mock import MagicMock, patch

from kagami.core.safety.cbf_decorators import (
    CBFRequiredViolation,
    CBFViolation,
    cbf_required,
    enforce_cbf,
    enforce_cbf_timed,
    enforce_tier1,
    enforce_tier2,
    enforce_tier3,
    monitor_cbf,
)

# =============================================================================
# TEST FIXTURES
# =============================================================================


@pytest.fixture
def simple_state() -> dict[str, Any]:
    """Simple state for testing."""
    return {"memory": 100, "cpu": 50}


@pytest.fixture
def mock_registry() -> Any:
    """Mock CBF registry."""

    class MockEntry:
        def __init__(self, func, threshold=0.0):
            self.func = func
            self.threshold = threshold

    class MockRegistry:
        def __init__(self):
            self._barriers = {}

        def get_barrier(self, name):
            return self._barriers.get(name)

        def register(self, name, func, threshold=0.0):
            self._barriers[name] = MockEntry(func, threshold)

    registry = MockRegistry()

    # Register some test barriers
    registry.register("memory", lambda: 10.0 - 5.0, threshold=0.0)
    registry.register("cpu", lambda: 0.5, threshold=0.0)
    registry.register("tight", lambda: -0.1, threshold=0.0)

    return registry


# =============================================================================
# TEST BASIC ENFORCEMENT
# =============================================================================


class TestEnforceCBF:
    """Test core enforce_cbf decorator."""

    def test_safe_execution(self: Any) -> None:
        """Test that safe barrier allows execution."""
        calls = []

        @enforce_cbf(cbf_func=lambda: 1.0)  # Safe: h = 1.0 > 0
        def safe_func() -> Any:
            calls.append("executed")
            return "result"

        result = safe_func()
        assert result == "result"
        assert calls == ["executed"]

    def test_unsafe_raises_exception(self: Any) -> None:
        """Test that unsafe barrier raises CBFViolation."""

        @enforce_cbf(cbf_func=lambda: -1.0, barrier_name="test")  # Unsafe: h = -1.0 < 0
        def unsafe_func() -> Any:
            return "should not execute"

        with pytest.raises(CBFViolation) as exc_info:
            unsafe_func()

        assert exc_info.value.barrier_name == "test"
        assert exc_info.value.h_value == -1.0
        assert exc_info.value.tier == 3  # Default tier

    def test_violation_handler(self: Any) -> None:
        """Test that violation_handler is called instead of raising."""
        handler_calls = []

        def handler(*args, **kwargs) -> Any:
            handler_calls.append((args, kwargs))
            return "handled"

        @enforce_cbf(cbf_func=lambda: -1.0, violation_handler=handler)
        def func_with_handler(x, y=10) -> Any:
            return "should not execute"

        result = func_with_handler(5, y=20)
        assert result == "handled"
        assert len(handler_calls) == 1
        assert handler_calls[0] == ((5,), {"y": 20})

    def test_state_extraction(self: Any) -> None:
        """Test that state extraction works correctly."""

        def extract_state(obj, size) -> dict[str, Any]:
            return {"memory": obj.memory, "request": size}

        class MemoryManager:
            def __init__(self):
                self.memory = 100

            @enforce_cbf(
                cbf_func=lambda s: 200 - s["memory"] - s["request"], extract_state=extract_state
            )
            def allocate(self, size):
                self.memory += size
                return self.memory

        manager = MemoryManager()

        # Safe allocation (100 + 50 = 150 < 200)
        result = manager.allocate(50)
        assert result == 150

        # Unsafe allocation (150 + 100 = 250 > 200, h would be negative)
        with pytest.raises(CBFViolation):
            manager.allocate(100)

    def test_custom_threshold(self: Any) -> None:
        """Test custom safety threshold."""

        @enforce_cbf(cbf_func=lambda: 0.5, threshold=1.0)  # h=0.5 < threshold=1.0
        def needs_margin() -> Any:
            return "executed"

        with pytest.raises(CBFViolation):
            needs_margin()

        @enforce_cbf(cbf_func=lambda: 1.5, threshold=1.0)  # h=1.5 > threshold=1.0
        def has_margin() -> Any:
            return "executed"

        result = has_margin()
        assert result == "executed"

    def test_barrier_evaluation_failure(self: Any) -> None:
        """Test that barrier evaluation failures block execution (fail-closed)."""
        calls = []

        def bad_barrier():
            raise RuntimeError("Barrier computation failed")

        @enforce_cbf(cbf_func=bad_barrier, barrier_name="test_barrier")
        def func() -> Any:
            calls.append("executed")
            return "result"

        # Should raise CBFViolation on barrier evaluation failure (fail-closed)
        with pytest.raises(CBFViolation) as exc_info:
            func()

        # Should NOT have executed
        assert calls == []
        assert exc_info.value.barrier_name == "test_barrier"
        assert "Barrier evaluation crashed" in exc_info.value.detail

    def test_tier_parameter(self: Any) -> None:
        """Test that tier parameter is included in exception."""

        @enforce_cbf(cbf_func=lambda: -1.0, barrier_name="test", tier=1)
        def tier1_func():
            pass

        with pytest.raises(CBFViolation) as exc_info:
            tier1_func()

        assert exc_info.value.tier == 1
        assert "organism" in str(exc_info.value)


# =============================================================================
# TEST ASYNC SUPPORT
# =============================================================================


class TestAsyncEnforcement:
    """Test async function support."""

    @pytest.mark.asyncio
    async def test_async_safe_execution(self: Any) -> None:
        """Test async function with safe barrier."""
        calls = []

        @enforce_cbf(cbf_func=lambda: 1.0)
        async def async_func() -> Any:
            calls.append("executed")
            await asyncio.sleep(0.001)
            return "result"

        result = await async_func()
        assert result == "result"
        assert calls == ["executed"]

    @pytest.mark.asyncio
    async def test_async_violation(self: Any) -> None:
        """Test async function with violation."""

        @enforce_cbf(cbf_func=lambda: -1.0)
        async def async_unsafe() -> Any:
            return "should not execute"

        with pytest.raises(CBFViolation):
            await async_unsafe()

    @pytest.mark.asyncio
    async def test_async_violation_handler(self: Any) -> None:
        """Test async violation handler."""

        async def async_handler(*args, **kwargs) -> Any:
            await asyncio.sleep(0.001)
            return "handled async"

        @enforce_cbf(cbf_func=lambda: -1.0, violation_handler=async_handler)
        async def func() -> Any:
            return "should not execute"

        result = await func()
        assert result == "handled async"

    @pytest.mark.asyncio
    async def test_async_with_sync_handler(self: Any) -> None:
        """Test async function with sync violation handler."""

        def sync_handler(*args, **kwargs) -> Any:
            return "handled sync"

        @enforce_cbf(cbf_func=lambda: -1.0, violation_handler=sync_handler)
        async def func() -> Any:
            return "should not execute"

        result = await func()
        assert result == "handled sync"


# =============================================================================
# TEST REGISTRY INTEGRATION
# =============================================================================


class TestRegistryIntegration:
    """Test registry-based barrier lookup."""

    def test_registry_lookup_success(self: Any, mock_registry: Any) -> None:
        """Test successful registry lookup."""
        with patch("kagami.core.safety.cbf_registry.CBFRegistry", return_value=mock_registry):

            @enforce_cbf(barrier_name="memory", use_registry=True)
            def func() -> Any:
                return "executed"

            # mock_registry.memory returns 5.0 > 0, should be safe
            result = func()
            assert result == "executed"

    def test_registry_lookup_violation(self: Any, mock_registry: Any) -> None:
        """Test registry lookup with violation."""
        with patch("kagami.core.safety.cbf_registry.CBFRegistry", return_value=mock_registry):

            @enforce_cbf(barrier_name="tight", use_registry=True)
            def func() -> Any:
                return "should not execute"

            # mock_registry.tight returns -0.1 < 0, should raise
            with pytest.raises(CBFViolation):
                func()

    def test_registry_not_found(self: Any, mock_registry: Any) -> None:
        """Test error when barrier not in registry."""
        with patch("kagami.core.safety.cbf_registry.CBFRegistry", return_value=mock_registry):

            @enforce_cbf(barrier_name="nonexistent", use_registry=True)
            def func() -> Any:
                return "executed"

            with pytest.raises(ValueError, match="not found in CBFRegistry"):
                func()

    def test_registry_import_failure_with_fallback(self: Any) -> None:
        """Test fallback when registry not available."""
        # Patch the import to fail
        import sys

        with patch.dict(sys.modules, {"kagami.core.safety.cbf_registry": None}):

            @enforce_cbf(cbf_func=lambda: 1.0, barrier_name="test", use_registry=True)
            def func() -> Any:
                return "executed with fallback"

            # Should use cbf_func as fallback
            result = func()
            assert result == "executed with fallback"

    def test_registry_import_failure_no_fallback(self: Any) -> None:
        """Test error when registry unavailable and no fallback."""
        import sys

        with patch.dict(sys.modules, {"kagami.core.safety.cbf_registry": None}):

            @enforce_cbf(barrier_name="test", use_registry=True)
            def func() -> Any:
                return "should not execute"

            with pytest.raises(ValueError, match="CBFRegistry not available"):
                func()


# =============================================================================
# TEST MONITORING DECORATOR
# =============================================================================


class TestMonitorCBF:
    """Test non-blocking monitoring decorator."""

    def test_monitor_always_executes(self: Any, mock_registry: Any, caplog: Any) -> None:
        """Test that monitor never blocks execution."""
        with patch("kagami.core.safety.cbf_registry.CBFRegistry", return_value=mock_registry):

            @monitor_cbf(barrier_name="tight", alert_threshold=0.5)
            def func() -> Any:
                return "always executes"

            with caplog.at_level(logging.WARNING):
                result = func()

            assert result == "always executes"
            # Should log warning since -0.1 < 0.5
            assert "CBF alert" in caplog.text

    def test_monitor_no_alert_when_safe(self: Any, mock_registry: Any, caplog: Any) -> None:
        """Test that monitor doesn't log when safe."""
        with patch("kagami.core.safety.cbf_registry.CBFRegistry", return_value=mock_registry):

            @monitor_cbf(barrier_name="memory", alert_threshold=0.1)
            def func() -> Any:
                return "executes"

            with caplog.at_level(logging.WARNING):
                result = func()

            assert result == "executes"
            # Should not log warning since 5.0 > 0.1
            assert "CBF alert" not in caplog.text

    @pytest.mark.asyncio
    async def test_monitor_async(self: Any, mock_registry: Any) -> None:
        """Test monitoring on async function."""
        with patch("kagami.core.safety.cbf_registry.CBFRegistry", return_value=mock_registry):

            @monitor_cbf(barrier_name="memory", alert_threshold=0.1)
            async def async_func() -> Any:
                await asyncio.sleep(0.001)
                return "executes"

            result = await async_func()
            assert result == "executes"


# =============================================================================
# TEST TIER-SPECIFIC DECORATORS
# =============================================================================


class TestTierDecorators:
    """Test convenience tier decorators."""

    def test_enforce_tier1(self: Any, mock_registry: Any) -> None:
        """Test Tier 1 convenience decorator."""
        with patch("kagami.core.safety.cbf_registry.CBFRegistry", return_value=mock_registry):

            @enforce_tier1("memory")
            def func() -> Any:
                return "tier1"

            result = func()
            assert result == "tier1"

    def test_enforce_tier2(self: Any, mock_registry: Any) -> None:
        """Test Tier 2 convenience decorator."""
        # Register colony-specific barrier
        mock_registry.register("cpu_colony0", lambda: 1.0, threshold=0.0)

        with patch("kagami.core.safety.cbf_registry.CBFRegistry", return_value=mock_registry):

            @enforce_tier2("cpu", colony=0)
            def func() -> Any:
                return "tier2"

            result = func()
            assert result == "tier2"

    def test_enforce_tier3(self: Any) -> None:
        """Test Tier 3 convenience decorator."""

        @enforce_tier3(cbf_func=lambda: 1.0)
        def func() -> Any:
            return "tier3"

        result = func()
        assert result == "tier3"

        @enforce_tier3(cbf_func=lambda: -1.0)
        def unsafe() -> Any:
            return "should not execute"

        with pytest.raises(CBFViolation):
            unsafe()


# =============================================================================
# TEST CBF_REQUIRED DECORATOR
# =============================================================================


class TestCBFRequired:
    """Test cbf_required decorator."""

    def test_cbf_required_violation(self: Any) -> None:
        """Test that missing CBF check raises error."""

        @cbf_required(tier=1)
        def needs_cbf() -> Any:
            return "executed without cbf"

        with pytest.raises(CBFRequiredViolation):
            needs_cbf()

    @pytest.mark.asyncio
    async def test_cbf_required_async_violation(self: Any) -> None:
        """Test async version raises error."""

        @cbf_required(tier=1)
        async def needs_cbf() -> Any:
            await asyncio.sleep(0.001)
            return "executed without cbf"

        with pytest.raises(CBFRequiredViolation):
            await needs_cbf()


# =============================================================================
# TEST PERFORMANCE
# =============================================================================


class TestPerformance:
    """Test decorator performance characteristics."""

    def test_overhead_minimal(self: Any) -> None:
        """Test that decorator overhead is <0.1ms."""

        @enforce_cbf(cbf_func=lambda: 1.0)
        def fast_func() -> Any:
            return "result"

        # Warm up
        for _ in range(10):
            fast_func()

        # Measure
        t0 = time.perf_counter()
        iterations = 1000
        for _ in range(iterations):
            fast_func()
        total_time = (time.perf_counter() - t0) * 1000  # ms

        avg_overhead = total_time / iterations
        assert avg_overhead < 0.1, f"Average overhead {avg_overhead:.3f}ms exceeds 0.1ms"

    def test_timed_decorator_logs_overhead(self: Any, caplog: Any) -> None:
        """Test that timed decorator logs excessive overhead."""

        @enforce_cbf_timed(
            cbf_func=lambda: 1.0,
            barrier_name="test",
            max_overhead_ms=0.0001,  # Impossibly low threshold
        )
        def func() -> Any:
            return "result"

        with caplog.at_level(logging.WARNING):
            func()

        # Should log warning about overhead
        assert "CBF overhead" in caplog.text
        assert "exceeds" in caplog.text


# =============================================================================
# TEST EDGE CASES
# =============================================================================


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_missing_cbf_func_raises(self: Any) -> None:
        """Test that missing cbf_func raises ValueError."""
        with pytest.raises(ValueError, match="cbf_func required"):

            @enforce_cbf()
            def func():
                pass

    def test_missing_barrier_name_for_registry(self: Any) -> None:
        """Test that missing barrier_name with use_registry raises."""
        with pytest.raises(ValueError, match="barrier_name required"):

            @enforce_cbf(use_registry=True)
            def func():
                pass

    def test_nan_barrier_value(self: Any, caplog: Any) -> None:
        """Test handling of NaN barrier values."""

        @enforce_cbf(cbf_func=lambda: float("nan"))
        def func() -> Any:
            return "executed"

        # NaN < threshold is False, so should execute
        with caplog.at_level(logging.WARNING):
            result = func()

        assert result == "executed"

    def test_inf_barrier_value(self: Any) -> None:
        """Test handling of infinite barrier values."""

        @enforce_cbf(cbf_func=lambda: float("inf"))
        def safe_inf() -> Any:
            return "executed"

        result = safe_inf()
        assert result == "executed"

        @enforce_cbf(cbf_func=lambda: float("-inf"))
        def unsafe_inf() -> Any:
            return "should not execute"

        with pytest.raises(CBFViolation):
            unsafe_inf()

    def test_state_extraction_failure(self: Any, caplog: Any) -> None:
        """Test graceful handling of state extraction errors."""

        def bad_extractor(*args, **kwargs):
            raise RuntimeError("Extraction failed")

        @enforce_cbf(cbf_func=lambda s: 1.0, extract_state=bad_extractor)
        def func() -> Any:
            return "executed"

        with caplog.at_level(logging.WARNING):
            result = func()

        # Should execute despite extraction failure
        assert result == "executed"
        assert "State extraction failed" in caplog.text

    def test_violation_detail_in_exception(self: Any) -> None:
        """Test that exception includes helpful detail."""

        @enforce_cbf(cbf_func=lambda: -1.0, barrier_name="memory")
        def alloc():
            pass

        with pytest.raises(CBFViolation) as exc_info:
            alloc()

        assert "Violated in alloc" in exc_info.value.detail

    def test_function_signature_preserved(self: Any) -> None:
        """Test that decorator preserves function metadata."""

        @enforce_cbf(cbf_func=lambda: 1.0)
        def documented_func(x: int, y: str = "default") -> str:
            """This is a docstring."""
            return f"{x}:{y}"

        assert documented_func.__name__ == "documented_func"
        assert documented_func.__doc__ == "This is a docstring."
        # Test it still works
        assert documented_func(5, y="test") == "5:test"


# =============================================================================
# TEST REAL-WORLD SCENARIOS
# =============================================================================


class TestRealWorldScenarios:
    """Test realistic usage patterns."""

    def test_memory_allocation_guard(self: Any) -> None:
        """Test memory allocation with CBF guard."""

        class MemoryManager:
            def __init__(self, limit=1000):
                self.used = 0
                self.limit = limit

            def _check_barrier(self, size):
                # Barrier: available memory after allocation must be >= 100
                available_after = self.limit - self.used - size
                return available_after - 100

            @enforce_cbf(
                cbf_func=lambda state: state["h_value"],
                extract_state=lambda self, size: {"h_value": self._check_barrier(size)},
            )
            def allocate(self, size):
                self.used += size
                return self.used

        manager = MemoryManager(limit=500)

        # Should work (available after = 400, h = 300 > 0)
        manager.allocate(100)
        assert manager.used == 100

        # Should work (available after = 200, h = 100 > 0)
        manager.allocate(200)
        assert manager.used == 300

        # Should work (available after = 150, h = 50 > 0)
        manager.allocate(50)
        assert manager.used == 350

        # Should fail (available after = 50, h = -50 < 0)
        with pytest.raises(CBFViolation):
            manager.allocate(100)

    def test_gc_on_violation_handler(self: Any) -> None:
        """Test triggering GC on memory violation."""
        gc_calls = []

        def gc_handler(*args, **kwargs):
            gc_calls.append("gc_triggered")
            gc.collect()
            return None

        @enforce_cbf(
            cbf_func=lambda: -1.0,  # Always violate
            violation_handler=gc_handler,
        )
        def allocate_large() -> Any:
            return "allocated"

        result = allocate_large()
        assert result is None
        assert gc_calls == ["gc_triggered"]

    @pytest.mark.asyncio
    async def test_rate_limiting(self: Any) -> None:
        """Test rate limiting with CBF."""

        class RateLimiter:
            def __init__(self, max_per_second=10):
                self.max_per_second = max_per_second
                self.last_reset = time.time()
                self.count = 0

            def _get_budget(self):
                now = time.time()
                if now - self.last_reset > 1.0:
                    self.count = 0
                    self.last_reset = now
                return self.max_per_second - self.count

            @enforce_cbf(
                cbf_func=lambda self: self._get_budget() - 1, extract_state=lambda self: self
            )
            async def call_api(self) -> Any:
                self.count += 1
                await asyncio.sleep(0.001)
                return "api_result"

        limiter = RateLimiter(max_per_second=5)

        # Should work for first 5 calls
        for _i in range(5):
            result = await limiter.call_api()
            assert result == "api_result"

        # 6th call should fail (budget = 0, h = -1 < 0)
        with pytest.raises(CBFViolation):
            await limiter.call_api()


# =============================================================================
# TEST COVERAGE EDGE CASES
# =============================================================================


class TestCoverageEdgeCases:
    """Additional tests to reach >90% coverage."""

    def test_tier_names_in_exception_message(self: Any) -> None:
        """Test that tier names appear correctly in exception."""

        @enforce_cbf(cbf_func=lambda: -1.0, tier=2)
        def colony_func():
            pass

        with pytest.raises(CBFViolation) as exc_info:
            colony_func()

        # Tier 2 should show "colony" in message
        assert "colony" in str(exc_info.value)

    def test_unknown_tier_in_exception(self: Any) -> None:
        """Test handling of unknown tier numbers."""

        @enforce_cbf(cbf_func=lambda: -1.0, tier=99)
        def weird_tier():
            pass

        with pytest.raises(CBFViolation) as exc_info:
            weird_tier()

        # Should show "tier-99" for unknown tier
        assert "tier-99" in str(exc_info.value)

    def test_monitor_with_exception(self: Any, mock_registry: Any) -> None:
        """Test monitor handles exceptions gracefully."""

        # Make barrier raise exception
        def bad_barrier():
            raise RuntimeError("Barrier failed")

        mock_registry.register("bad", bad_barrier)

        with patch("kagami.core.safety.cbf_registry.CBFRegistry", return_value=mock_registry):

            @monitor_cbf(barrier_name="bad")
            def func() -> Any:
                return "still executes"

            # Should not raise, just execute
            result = func()
            assert result == "still executes"

    @pytest.mark.asyncio
    async def test_async_monitor_with_exception(self: Any, mock_registry: Any) -> None:
        """Test async monitor handles exceptions."""

        def bad_barrier():
            raise RuntimeError("Barrier failed")

        mock_registry.register("bad", bad_barrier)

        with patch("kagami.core.safety.cbf_registry.CBFRegistry", return_value=mock_registry):

            @monitor_cbf(barrier_name="bad")
            async def func() -> Any:
                await asyncio.sleep(0.001)
                return "still executes"

            result = await func()
            assert result == "still executes"

    def test_enforce_tier2_without_colony(self: Any, mock_registry: Any) -> None:
        """Test tier2 decorator without colony parameter."""
        mock_registry.register("cpu", lambda: 1.0)

        with patch("kagami.core.safety.cbf_registry.CBFRegistry", return_value=mock_registry):

            @enforce_tier2("cpu")  # No colony specified
            def func() -> Any:
                return "executed"

            result = func()
            assert result == "executed"
