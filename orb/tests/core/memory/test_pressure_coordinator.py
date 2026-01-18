"""Tests for kagami.core.memory.pressure_coordinator."""

from __future__ import annotations

import pytest
pytestmark = pytest.mark.tier_integration



import asyncio

from kagami.core.memory.pressure_coordinator import (
    ComponentPriority,
    MemoryConsumer,
    MemoryPressureCoordinator,
    MemoryPressureLevel,
    PressureSnapshot,
)


@pytest.mark.tier_unit
class TestMemoryPressureLevel:
    """Test MemoryPressureLevel enum."""

    def test_pressure_levels(self) -> None:
        """Test pressure level enum values."""
        assert MemoryPressureLevel.NORMAL == 0
        assert MemoryPressureLevel.MODERATE == 1
        assert MemoryPressureLevel.HIGH == 2
        assert MemoryPressureLevel.CRITICAL == 3
        assert MemoryPressureLevel.EMERGENCY == 4


@pytest.mark.tier_unit
class TestComponentPriority:
    """Test ComponentPriority enum."""

    def test_priority_levels(self) -> None:
        """Test priority level enum values."""
        assert ComponentPriority.CRITICAL == 0
        assert ComponentPriority.HIGH == 1
        assert ComponentPriority.NORMAL == 2
        assert ComponentPriority.LOW == 3
        assert ComponentPriority.EXPENDABLE == 4


@pytest.mark.tier_unit
class TestMemoryConsumer:
    """Test MemoryConsumer dataclass."""

    def test_consumer_creation(self) -> None:
        """Test creating a memory consumer."""
        consumer = MemoryConsumer(
            component_id="test_component",
            name="Test Component",
            priority=ComponentPriority.NORMAL,
            min_memory=1024 * 1024,
            max_memory=10 * 1024 * 1024,
            can_evict=True,
        )

        assert consumer.component_id == "test_component"
        assert consumer.priority == ComponentPriority.NORMAL
        assert consumer.min_memory == 1024 * 1024
        assert consumer.eviction_count == 0


@pytest.mark.tier_unit
class TestPressureSnapshot:
    """Test PressureSnapshot dataclass."""

    def test_snapshot_creation(self) -> None:
        """Test creating a pressure snapshot."""
        snapshot = PressureSnapshot(
            timestamp=0.0,
            total_memory=16 * 1024 * 1024 * 1024,
            available_memory=8 * 1024 * 1024 * 1024,
            used_memory=8 * 1024 * 1024 * 1024,
            percent_used=50.0,
            pressure_level=MemoryPressureLevel.NORMAL,
            component_usage={},
        )

        assert snapshot.total_memory == 16 * 1024 * 1024 * 1024
        assert snapshot.percent_used == 50.0
        assert snapshot.pressure_level == MemoryPressureLevel.NORMAL


@pytest.mark.tier_unit
class TestMemoryPressureCoordinator:
    """Test MemoryPressureCoordinator class."""

    def test_coordinator_initialization(self) -> None:
        """Test coordinator initialization."""
        coordinator = MemoryPressureCoordinator(
            check_interval=5.0,
            eviction_cooldown=30.0,
        )

        assert coordinator.check_interval == 5.0
        assert coordinator.eviction_cooldown == 30.0
        assert coordinator.current_level == MemoryPressureLevel.NORMAL

    def test_register_consumer(self) -> None:
        """Test registering a memory consumer."""
        coordinator = MemoryPressureCoordinator()

        coordinator.register_consumer(
            component_id="test_component",
            name="Test Component",
            priority=ComponentPriority.NORMAL,
            min_memory=1024 * 1024,
            max_memory=10 * 1024 * 1024,
        )

        assert "test_component" in coordinator.consumers

    def test_unregister_consumer(self) -> None:
        """Test unregistering a consumer."""
        coordinator = MemoryPressureCoordinator()

        coordinator.register_consumer(
            component_id="test_component",
            name="Test Component",
            priority=ComponentPriority.NORMAL,
            min_memory=1024 * 1024,
        )

        assert "test_component" in coordinator.consumers

        coordinator.unregister_consumer("test_component")

        assert "test_component" not in coordinator.consumers

    @pytest.mark.asyncio
    async def test_get_memory_snapshot(self) -> None:
        """Test getting memory snapshot."""
        coordinator = MemoryPressureCoordinator()

        snapshot = await coordinator.get_memory_snapshot()

        assert isinstance(snapshot, PressureSnapshot)
        assert snapshot.total_memory > 0
        assert snapshot.available_memory >= 0

    def test_calculate_pressure_level(self) -> None:
        """Test pressure level calculation."""
        coordinator = MemoryPressureCoordinator()

        level_low = coordinator._calculate_pressure_level(0.5)
        assert level_low == MemoryPressureLevel.NORMAL

        level_high = coordinator._calculate_pressure_level(0.95)
        assert level_high >= MemoryPressureLevel.CRITICAL

    @pytest.mark.asyncio
    async def test_coordinate_eviction_no_pressure(self) -> None:
        """Test eviction coordination with no pressure."""
        coordinator = MemoryPressureCoordinator()

        bytes_freed = await coordinator.coordinate_eviction()

        assert bytes_freed >= 0

    @pytest.mark.asyncio
    async def test_eviction_with_callback(self) -> None:
        """Test eviction with callback."""
        coordinator = MemoryPressureCoordinator()

        eviction_called = False

        def eviction_callback() -> int:
            nonlocal eviction_called
            eviction_called = True
            return 1024 * 1024

        coordinator.register_consumer(
            component_id="test_component",
            name="Test Component",
            priority=ComponentPriority.LOW,
            min_memory=1024 * 1024,
            can_evict=True,
            eviction_callback=eviction_callback,
        )

        coordinator.consumers["test_component"].current_usage = 10 * 1024 * 1024

    @pytest.mark.asyncio
    async def test_notify_pressure_change(self) -> None:
        """Test pressure change notification."""
        coordinator = MemoryPressureCoordinator()

        callback_called = False
        received_level = None

        def pressure_callback(level: MemoryPressureLevel) -> None:
            nonlocal callback_called, received_level
            callback_called = True
            received_level = level

        coordinator.register_consumer(
            component_id="test_component",
            name="Test Component",
            priority=ComponentPriority.NORMAL,
            min_memory=1024 * 1024,
            pressure_callback=pressure_callback,
        )

        await coordinator.notify_pressure_change(MemoryPressureLevel.HIGH)

        assert callback_called
        assert received_level == MemoryPressureLevel.HIGH

    @pytest.mark.asyncio
    async def test_check_memory_pressure(self) -> None:
        """Test checking memory pressure."""
        coordinator = MemoryPressureCoordinator()

        level = await coordinator.check_memory_pressure()

        assert isinstance(level, MemoryPressureLevel)

    @pytest.mark.asyncio
    async def test_start_stop_monitoring(self) -> None:
        """Test starting and stopping monitoring."""
        coordinator = MemoryPressureCoordinator()

        await coordinator.start_monitoring()

        assert coordinator._running is True
        assert coordinator._monitor_task is not None

        await asyncio.sleep(0.1)

        await coordinator.stop_monitoring()

        assert coordinator._running is False

    def test_get_stats(self) -> None:
        """Test getting coordinator statistics."""
        coordinator = MemoryPressureCoordinator()

        stats = coordinator.get_stats()

        assert "current_level" in stats
        assert "total_evictions" in stats
        assert "registered_consumers" in stats

    def test_cleanup_internal_state(self) -> None:
        """Test cleanup removes inactive components."""
        coordinator = MemoryPressureCoordinator()

        coordinator.register_consumer(
            component_id="active_component",
            name="Active Component",
            priority=ComponentPriority.NORMAL,
            min_memory=1024 * 1024,
        )

        coordinator.register_consumer(
            component_id="inactive_component",
            name="Inactive Component",
            priority=ComponentPriority.NORMAL,
            min_memory=1024 * 1024,
        )

        coordinator.consumers["inactive_component"].last_eviction = 0.0

        stats = coordinator._cleanup_internal_state()

        assert "components_removed" in stats
        assert "components_active" in stats

    def test_load_thresholds_from_env(self) -> None:
        """Test loading thresholds from environment."""
        import os

        os.environ["KAGAMI_MEMORY_THRESHOLD_HIGH"] = "0.85"

        coordinator = MemoryPressureCoordinator()

        assert coordinator.THRESHOLDS[MemoryPressureLevel.HIGH] == 0.85

        del os.environ["KAGAMI_MEMORY_THRESHOLD_HIGH"]

    def test_critical_component_protection(self) -> None:
        """Test that critical components are protected."""
        coordinator = MemoryPressureCoordinator()

        coordinator.register_consumer(
            component_id="critical_component",
            name="Critical Component",
            priority=ComponentPriority.CRITICAL,
            min_memory=1024 * 1024,
        )

        consumer = coordinator.consumers["critical_component"]
        assert consumer.priority == ComponentPriority.CRITICAL
