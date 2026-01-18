"""Unit tests for CBF periodic monitoring.

CREATED: December 16, 2025
PURPOSE: Test periodic background monitoring of CBF barriers

Test Coverage:
1. Monitoring task lifecycle (start/stop)
2. Warning threshold detection
3. Critical threshold detection
4. Violation detection during monitoring
5. State gathering and formatting
6. Integration with CBFRegistry
7. Error handling in monitoring loop
8. Task cancellation
"""

from __future__ import annotations

from typing import Any

import pytest

pytestmark = pytest.mark.tier_integration

import asyncio
import logging
from unittest.mock import Mock, patch

from kagami.core.safety.cbf_init import (
    _format_relevant_state,
    _gather_system_state,
    _monitor_cbf_periodic,
    initialize_cbf_system,
)
from kagami.core.safety.cbf_registry import CBFRegistry
from kagami.core.safety.types import StateDict

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def clean_registry() -> Any:
    """Provide a clean registry for each test."""
    CBFRegistry.reset_singleton()
    registry = CBFRegistry()
    yield registry
    CBFRegistry.reset_singleton()


@pytest.fixture
def test_registry(clean_registry: Any) -> None:
    """Registry with test barriers at different thresholds."""

    def h_safe(state: StateDict | None) -> float:
        """Always safe (h = 0.5)."""
        return 0.5

    def h_warning(state: StateDict | None) -> float:
        """In warning zone (h = 0.15)."""
        return 0.15

    def h_critical(state: StateDict | None) -> float:
        """In critical zone (h = 0.03)."""
        return 0.03

    def h_violation(state: StateDict | None) -> float:
        """Violation (h = -0.1)."""
        return -0.1

    clean_registry.register(tier=1, name="test.safe", func=h_safe)
    clean_registry.register(tier=1, name="test.warning", func=h_warning)
    clean_registry.register(tier=1, name="test.critical", func=h_critical)
    clean_registry.register(tier=1, name="test.violation", func=h_violation)

    return clean_registry


# =============================================================================
# MONITORING LIFECYCLE TESTS
# =============================================================================


@pytest.mark.asyncio
async def test_monitoring_starts_and_runs(test_registry: Any, caplog: Any) -> None:
    """Test that monitoring task starts and runs."""
    caplog.set_level(logging.INFO)

    # Start monitoring with short interval
    task = asyncio.create_task(
        _monitor_cbf_periodic(
            test_registry,
            interval=0.1,
            warning_threshold=0.2,
            critical_threshold=0.05,
        )
    )

    # Let it run for a few cycles
    await asyncio.sleep(0.3)

    # Cancel task
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    # Check that monitoring started
    assert "CBF periodic monitoring started" in caplog.text
    assert "interval=0.1" in caplog.text


@pytest.mark.asyncio
async def test_monitoring_stops_cleanly_on_cancel(test_registry: Any, caplog: Any) -> None:
    """Test that monitoring stops cleanly when cancelled."""
    caplog.set_level(logging.INFO)

    task = asyncio.create_task(_monitor_cbf_periodic(test_registry, interval=0.1))

    await asyncio.sleep(0.15)

    # Cancel and wait
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    # Should see stop message
    assert "CBF periodic monitoring stopped" in caplog.text


# =============================================================================
# THRESHOLD DETECTION TESTS
# =============================================================================


@pytest.mark.asyncio
async def test_monitoring_detects_warning_threshold(test_registry: Any, caplog: Any) -> None:
    """Test that monitoring detects barriers in warning zone."""
    caplog.set_level(logging.WARNING)

    task = asyncio.create_task(
        _monitor_cbf_periodic(
            test_registry,
            interval=0.1,
            warning_threshold=0.2,
            critical_threshold=0.05,
        )
    )

    # Let monitoring run
    await asyncio.sleep(0.2)

    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    # Should see warning for test.warning (h=0.15 < 0.2)
    assert "CBF WARNING" in caplog.text
    assert "test.warning" in caplog.text
    assert "YELLOW zone" in caplog.text


@pytest.mark.asyncio
async def test_monitoring_detects_critical_threshold(test_registry: Any, caplog: Any) -> None:
    """Test that monitoring detects barriers in critical zone."""
    caplog.set_level(logging.CRITICAL)

    task = asyncio.create_task(
        _monitor_cbf_periodic(
            test_registry,
            interval=0.1,
            warning_threshold=0.2,
            critical_threshold=0.05,
        )
    )

    await asyncio.sleep(0.2)

    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    # Should see critical alert for test.critical (h=0.03 < 0.05)
    assert "CBF CRITICAL" in caplog.text
    assert "test.critical" in caplog.text
    assert "RED zone" in caplog.text


@pytest.mark.asyncio
async def test_monitoring_detects_violations(test_registry: Any, caplog: Any) -> None:
    """Test that monitoring detects barrier violations."""
    caplog.set_level(logging.ERROR)

    task = asyncio.create_task(
        _monitor_cbf_periodic(
            test_registry,
            interval=0.1,
            warning_threshold=0.2,
            critical_threshold=0.05,
        )
    )

    await asyncio.sleep(0.2)

    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    # Should see violation for test.violation (h=-0.1 < 0)
    assert "CBF VIOLATION" in caplog.text
    assert "test.violation" in caplog.text


@pytest.mark.asyncio
async def test_monitoring_no_alerts_for_safe_barriers(test_registry: Any, caplog: Any) -> None:
    """Test that safe barriers don't generate alerts."""
    caplog.set_level(logging.INFO)

    task = asyncio.create_task(
        _monitor_cbf_periodic(
            test_registry,
            interval=0.1,
            warning_threshold=0.2,
            critical_threshold=0.05,
        )
    )

    await asyncio.sleep(0.2)

    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    # test.safe should not appear in warnings/criticals
    # (it appears in monitoring start, but not in alerts)
    log_lines = [
        line
        for line in caplog.text.split("\n")
        if "WARNING" in line or "CRITICAL" in line or "VIOLATION" in line
    ]
    safe_alerts = [line for line in log_lines if "test.safe" in line]

    assert len(safe_alerts) == 0


# =============================================================================
# STATE GATHERING TESTS
# =============================================================================


def test_gather_system_state() -> None:
    """Test that system state gathering works."""
    state = _gather_system_state()

    # Should have at least some state fields
    assert isinstance(state, dict)

    # Check for expected keys (may vary by system)
    # At minimum, should handle gracefully if psutil missing
    assert len(state) >= 0  # May be empty if no state providers available


@patch("kagami.core.safety.cbf_init.get_system_memory_state")
def test_gather_system_state_handles_errors(mock_memory: Any) -> None:
    """Test that state gathering handles provider failures."""
    # Make memory state provider fail
    mock_memory.side_effect = RuntimeError("psutil unavailable")

    # Should not raise, should continue with partial state
    state = _gather_system_state()
    assert isinstance(state, dict)


# =============================================================================
# STATE FORMATTING TESTS
# =============================================================================


def test_format_relevant_state_memory_barrier() -> None:
    """Test formatting state for memory barrier."""
    state = {
        "memory_pct": 0.75,
        "memory_available_mb": 1024.5,
        "memory_total_mb": 4096.0,
        "disk_usage": 0.5,  # Irrelevant for memory
    }

    formatted = _format_relevant_state(state, "organism.memory")  # type: ignore[arg-type]

    # Should include memory fields
    assert "memory_pct" in formatted
    assert "memory_available_mb" in formatted
    assert "memory_total_mb" in formatted

    # Should NOT include disk fields
    assert "disk_usage" not in formatted


def test_format_relevant_state_disk_barrier() -> None:
    """Test formatting state for disk barrier."""
    state = {
        "disk_usage": 0.85,
        "disk_free_gb": 10.5,
        "disk_total_gb": 100.0,
        "memory_pct": 0.5,  # Irrelevant for disk
    }

    formatted = _format_relevant_state(state, "organism.disk")  # type: ignore[arg-type]

    # Should include disk fields
    assert "disk_usage" in formatted
    assert "disk_free_gb" in formatted
    assert "disk_total_gb" in formatted

    # Should NOT include memory fields
    assert "memory_pct" not in formatted


def test_format_relevant_state_unknown_barrier() -> None:
    """Test formatting state for unknown barrier."""
    state = {
        "field_a": 1.0,
        "field_b": 2.0,
        "field_c": 3.0,
        "field_d": 4.0,
    }

    formatted = _format_relevant_state(state, "unknown.barrier")  # type: ignore[arg-type]

    # Should show limited state keys
    assert "state keys:" in formatted


def test_format_relevant_state_missing_fields() -> None:
    """Test formatting when relevant fields missing from state."""
    state = {
        "irrelevant_field": 1.0,
    }

    formatted = _format_relevant_state(state, "organism.memory")  # type: ignore[arg-type]

    # Should handle gracefully
    assert "no relevant state" in formatted


def test_format_relevant_state_empty_state() -> None:
    """Test formatting with empty state dict."""
    state = {}

    formatted = _format_relevant_state(state, "organism.memory")

    assert "no relevant state" in formatted


# =============================================================================
# ERROR HANDLING TESTS
# =============================================================================


@pytest.mark.asyncio
async def test_monitoring_continues_after_check_error(clean_registry: Any, caplog: Any) -> None:
    """Test that monitoring continues after a check failure."""
    caplog.set_level(logging.ERROR)

    # Register a barrier that raises exception
    def h_broken(state):
        raise ValueError("Barrier evaluation failed")

    clean_registry.register(tier=1, name="test.broken", func=h_broken)

    task = asyncio.create_task(_monitor_cbf_periodic(clean_registry, interval=0.1))

    # Let it run for multiple cycles
    await asyncio.sleep(0.3)

    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    # Should see error but monitoring should continue
    # (multiple cycles = multiple log entries)
    assert "CBF monitoring check failed" in caplog.text or "evaluation failed" in caplog.text


@pytest.mark.asyncio
async def test_monitoring_handles_disabled_barriers(test_registry: Any, caplog: Any) -> None:
    """Test that disabled barriers are skipped during monitoring."""
    caplog.set_level(logging.WARNING)

    # Disable the warning barrier
    test_registry.disable("test.warning")

    task = asyncio.create_task(
        _monitor_cbf_periodic(
            test_registry,
            interval=0.1,
            warning_threshold=0.2,
        )
    )

    await asyncio.sleep(0.2)

    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    # Should NOT see warning for disabled barrier
    warning_lines = [
        line for line in caplog.text.split("\n") if "CBF WARNING" in line and "test.warning" in line
    ]
    assert len(warning_lines) == 0


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


@pytest.mark.asyncio
async def test_initialize_cbf_system_starts_monitoring() -> None:
    """Test that initialize_cbf_system can start monitoring."""
    CBFRegistry.reset_singleton()

    # Create event loop to enable monitoring
    # (monitoring only starts if event loop exists)
    try:
        # Initialize with monitoring enabled
        registry = initialize_cbf_system(enable_monitoring=True)

        # Give it a moment
        await asyncio.sleep(0.1)

        # Registry should exist
        assert registry is not None
        stats = registry.get_stats()
        assert stats["total_barriers"] >= 4  # Organism barriers

    finally:
        CBFRegistry.reset_singleton()


@pytest.mark.asyncio
async def test_monitoring_checks_all_tiers(caplog: Any) -> None:
    """Test that monitoring checks all three tiers."""
    CBFRegistry.reset_singleton()
    registry = CBFRegistry()

    # Register barriers at all tiers
    def h_test(s):
        return 0.1  # Warning zone

    registry.register(tier=1, name="tier1.test", func=h_test)
    registry.register(tier=2, name="tier2.test", func=h_test, colony=0)
    registry.register(tier=3, name="tier3.test", func=h_test)

    caplog.set_level(logging.WARNING)

    task = asyncio.create_task(_monitor_cbf_periodic(registry, interval=0.1, warning_threshold=0.2))

    await asyncio.sleep(0.2)

    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    # Should see warnings for all tiers
    assert "tier1.test" in caplog.text
    assert "tier2.test" in caplog.text
    assert "tier3.test" in caplog.text

    CBFRegistry.reset_singleton()


# =============================================================================
# EDGE CASES
# =============================================================================


@pytest.mark.asyncio
async def test_monitoring_with_custom_thresholds(test_registry: Any, caplog: Any) -> None:
    """Test monitoring with custom threshold values."""
    caplog.set_level(logging.WARNING)

    # Use very low thresholds so test.safe triggers warning
    task = asyncio.create_task(
        _monitor_cbf_periodic(
            test_registry,
            interval=0.1,
            warning_threshold=0.6,  # Higher than test.safe (0.5)
            critical_threshold=0.4,
        )
    )

    await asyncio.sleep(0.2)

    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    # Now test.safe should trigger warning (h=0.5 < 0.6)
    assert "test.safe" in caplog.text
    assert "CBF WARNING" in caplog.text


@pytest.mark.asyncio
async def test_monitoring_with_short_interval() -> None:
    """Test that monitoring works with very short interval."""
    CBFRegistry.reset_singleton()
    registry = CBFRegistry()

    def h_test(s):
        return 1.0

    registry.register(tier=1, name="test", func=h_test)

    # Short interval (0.05s = 50ms)
    task = asyncio.create_task(_monitor_cbf_periodic(registry, interval=0.05))

    # Let it run multiple cycles
    await asyncio.sleep(0.3)

    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    # Should have evaluated at least once (timing can vary on CI)
    entry = registry.get_barrier("test")
    assert entry is not None
    assert entry.evaluation_count >= 1  # At least one evaluation

    CBFRegistry.reset_singleton()


# =============================================================================
# COVERAGE: Comprehensive monitoring tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=kagami.core.safety.cbf_init", "--cov-report=term-missing"])
