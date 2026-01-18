from kagami.core.async_utils import safe_create_task

"Coordinated memory pressure response system for K os WITH cleanup.\n\nProvides system-wide coordination of memory pressure responses to prevent\ncascade failures and ensure critical components maintain minimum resources.\n"
import asyncio
import gc
import logging
import os
import time
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any

import psutil

from kagami.core.infra.singleton_cleanup_mixin import SingletonCleanupMixin

logger = logging.getLogger(__name__)


class MemoryPressureLevel(IntEnum):
    """System-wide memory pressure levels."""

    NORMAL = 0
    MODERATE = 1
    HIGH = 2
    CRITICAL = 3
    EMERGENCY = 4


class ComponentPriority(IntEnum):
    """Component priority for resource allocation."""

    CRITICAL = 0
    HIGH = 1
    NORMAL = 2
    LOW = 3
    EXPENDABLE = 4


@dataclass
class MemoryConsumer:
    """Registered memory consumer component."""

    component_id: str
    name: str
    priority: ComponentPriority
    min_memory: int
    max_memory: int | None = None
    current_usage: int = 0
    can_evict: bool = True
    eviction_callback: Callable[[], int] | None = None
    pressure_callback: Callable[[MemoryPressureLevel], None] | None = None
    last_eviction: float = 0.0
    eviction_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict[str, Any])


@dataclass
class PressureSnapshot:
    """Point-in-time memory pressure state snapshot.

    Note: Distinct from kagami.core.memory.types.MemorySnapshot (experience replay).
    This type tracks system memory pressure levels.
    """

    timestamp: float
    total_memory: int
    available_memory: int
    used_memory: int
    percent_used: float
    pressure_level: MemoryPressureLevel
    component_usage: dict[str, int]
    swap_used: int = 0
    swap_percent: float = 0.0


class MemoryPressureCoordinator(SingletonCleanupMixin):
    """Coordinates system-wide memory pressure responses WITH automatic cleanup.

    Features:
    - Priority-based resource allocation
    - Coordinated eviction to prevent thrashing
    - Minimum memory guarantees for critical components
    - Adaptive pressure thresholds
    - OOM prevention strategies
    """

    THRESHOLDS = {
        MemoryPressureLevel.NORMAL: 0.7,
        MemoryPressureLevel.MODERATE: 0.8,
        MemoryPressureLevel.HIGH: 0.9,
        MemoryPressureLevel.CRITICAL: 0.95,
        MemoryPressureLevel.EMERGENCY: 0.98,
    }

    def __init__(
        self,
        check_interval: float = 5.0,
        eviction_cooldown: float = 30.0,
        aggressive_gc: bool = True,
    ) -> None:
        """Initialize memory pressure coordinator.

        Args:
            check_interval: Seconds between memory checks
            eviction_cooldown: Minimum seconds between evictions per component
            aggressive_gc: Whether to run aggressive GC during pressure
        """
        self.check_interval = check_interval
        self.eviction_cooldown = eviction_cooldown
        self.aggressive_gc = aggressive_gc
        self.consumers: dict[str, MemoryConsumer] = {}
        self._lock = asyncio.Lock()
        self.current_level = MemoryPressureLevel.NORMAL
        self.last_snapshot: PressureSnapshot | None = None
        self._monitor_task: asyncio.Task | None = None
        self._running = False
        self.total_evictions = 0
        self.total_bytes_freed = 0
        self.pressure_events: dict[MemoryPressureLevel, int] = defaultdict(int)
        self.oom_prevented = 0
        self._load_thresholds()
        self._cleanup_interval = 3600.0
        self._register_cleanup_on_exit()
        logger.info(f"Initialized MemoryPressureCoordinator with thresholds: {self.THRESHOLDS}")

    def _load_thresholds(self) -> None:
        """Load custom thresholds from environment variables."""
        for level in MemoryPressureLevel:
            env_key = f"KAGAMI_MEMORY_THRESHOLD_{level.name}"
            env_val = os.getenv(env_key)
            if env_val:
                try:
                    self.THRESHOLDS[level] = float(env_val)
                except ValueError:
                    logger.warning(f"Invalid threshold value for {env_key}: {env_val}")

    def register_consumer(
        self,
        component_id: str,
        name: str,
        priority: ComponentPriority,
        min_memory: int,
        max_memory: int | None = None,
        can_evict: bool = True,
        eviction_callback: Callable[[], int] | None = None,
        pressure_callback: Callable[[MemoryPressureLevel], None] | None = None,
        **metadata: Any,
    ) -> None:
        """Register a memory consumer component.

        Args:
            component_id: Unique component identifier
            name: Human-readable component name
            priority: Component priority level
            min_memory: Minimum memory required (bytes)
            max_memory: Maximum memory allowed (bytes)
            can_evict: Whether component can evict data
            eviction_callback: Function to call for eviction
            pressure_callback: Function to notify of pressure changes
            **metadata: Additional component metadata
        """
        consumer = MemoryConsumer(
            component_id=component_id,
            name=name,
            priority=priority,
            min_memory=min_memory,
            max_memory=max_memory,
            can_evict=can_evict,
            eviction_callback=eviction_callback,
            pressure_callback=pressure_callback,
            metadata=metadata,
        )
        self.consumers[component_id] = consumer
        logger.info(
            f"Registered memory consumer: {name} (priority={priority.name}, min={min_memory / 1024 / 1024:.1f}MB)"
        )

    def unregister_consumer(self, component_id: str) -> None:
        """Unregister a memory consumer.

        Args:
            component_id: Component to unregister
        """
        if component_id in self.consumers:
            del self.consumers[component_id]
            logger.info(f"Unregistered memory consumer: {component_id}")

    async def get_memory_snapshot(self) -> PressureSnapshot:
        """Get current memory snapshot.

        Returns:
            PressureSnapshot: Current memory state
        """
        mem = psutil.virtual_memory()
        swap = psutil.swap_memory()
        pressure_level = self._calculate_pressure_level(mem.percent / 100)
        component_usage = {}
        for component_id, consumer in self.consumers.items():
            if consumer.current_usage > 0:
                component_usage[component_id] = consumer.current_usage
        snapshot = PressureSnapshot(
            timestamp=time.time(),
            total_memory=mem.total,
            available_memory=mem.available,
            used_memory=mem.used,
            percent_used=mem.percent,
            pressure_level=pressure_level,
            component_usage=component_usage,
            swap_used=swap.used,
            swap_percent=swap.percent,
        )
        self.last_snapshot = snapshot
        return snapshot

    def _calculate_pressure_level(self, percent: float) -> MemoryPressureLevel:
        """Calculate pressure level from memory percentage.

        Args:
            percent: Memory usage percentage (0.0-1.0)

        Returns:
            MemoryPressureLevel: Current pressure level
        """
        for level in reversed(list(MemoryPressureLevel)):
            if percent >= self.THRESHOLDS.get(level, 1.0):
                return level
        return MemoryPressureLevel.NORMAL

    async def coordinate_eviction(self) -> int:
        """Coordinate memory eviction across components.

        Returns:
            int: Total bytes freed
        """
        async with self._lock:
            return await self._coordinate_eviction_internal()

    async def _coordinate_eviction_internal(self) -> int:
        """Internal eviction coordination (must be called with lock)."""
        snapshot = await self.get_memory_snapshot()
        if snapshot.pressure_level < MemoryPressureLevel.HIGH:
            return 0
        logger.warning(
            f"Coordinating eviction at {snapshot.pressure_level.name} pressure ({snapshot.percent_used:.1f}% memory used)"
        )
        total_freed = 0
        current_time = time.time()
        sorted_consumers = sorted(
            self.consumers.values(), key=lambda c: (c.priority, -c.current_usage), reverse=True
        )
        target_percent = self.THRESHOLDS[MemoryPressureLevel.MODERATE]
        target_bytes = int((snapshot.percent_used / 100 - target_percent) * snapshot.total_memory)
        for consumer in sorted_consumers:
            if total_freed >= target_bytes:
                break
            if not consumer.can_evict or not consumer.eviction_callback:
                continue
            if current_time - consumer.last_eviction < self.eviction_cooldown:
                continue
            if (
                consumer.priority == ComponentPriority.CRITICAL
                and snapshot.pressure_level < MemoryPressureLevel.EMERGENCY
            ):
                continue
            try:
                if asyncio.iscoroutinefunction(consumer.eviction_callback):
                    bytes_freed = await consumer.eviction_callback()
                else:
                    bytes_freed = consumer.eviction_callback()
                if bytes_freed > 0:
                    total_freed += bytes_freed
                    consumer.last_eviction = current_time
                    consumer.eviction_count += 1
                    self.total_evictions += 1
                    self.total_bytes_freed += bytes_freed
                    logger.info(f"Evicted {bytes_freed / 1024 / 1024:.1f}MB from {consumer.name}")
            except Exception as e:
                logger.error(f"Eviction failed for {consumer.name}: {e}")
        if self.aggressive_gc and snapshot.pressure_level >= MemoryPressureLevel.CRITICAL:
            gc.collect(2)
            logger.info("Ran aggressive garbage collection")
        if snapshot.pressure_level == MemoryPressureLevel.EMERGENCY:
            self.oom_prevented += 1
            logger.critical(
                f"Emergency eviction completed, freed {total_freed / 1024 / 1024:.1f}MB (OOM prevention #{self.oom_prevented})"
            )
        return total_freed

    async def notify_pressure_change(self, new_level: MemoryPressureLevel) -> None:
        """Notify components of pressure level change.

        Args:
            new_level: New pressure level
        """
        if new_level == self.current_level:
            return
        old_level = self.current_level
        self.current_level = new_level
        self.pressure_events[new_level] += 1
        logger.info(f"Memory pressure changed: {old_level.name} -> {new_level.name}")
        for consumer in self.consumers.values():
            if consumer.pressure_callback:
                try:
                    if asyncio.iscoroutinefunction(consumer.pressure_callback):
                        await consumer.pressure_callback(new_level)
                    else:
                        consumer.pressure_callback(new_level)
                except Exception as e:
                    logger.error(f"Pressure callback failed for {consumer.name}: {e}")

    async def check_memory_pressure(self) -> MemoryPressureLevel:
        """Check current memory pressure and coordinate response.

        Returns:
            MemoryPressureLevel: Current pressure level
        """
        snapshot = await self.get_memory_snapshot()
        await self.notify_pressure_change(snapshot.pressure_level)
        if snapshot.pressure_level >= MemoryPressureLevel.HIGH:
            await self.coordinate_eviction()
        return snapshot.pressure_level

    async def start_monitoring(self) -> None:
        """Start background memory monitoring."""
        if self._running:
            return
        self._running = True
        self._monitor_task = safe_create_task(self._monitor_loop(), name="_monitor_loop")
        logger.info("Started memory pressure monitoring")

    async def stop_monitoring(self) -> None:
        """Stop background monitoring."""
        self._running = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        logger.info("Stopped memory pressure monitoring")

    async def _monitor_loop(self) -> None:
        """Background monitoring loop."""
        while self._running:
            try:
                await self.check_memory_pressure()
                await asyncio.sleep(self.check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Memory monitor error: {e}")
                await asyncio.sleep(self.check_interval)

    def get_stats(self) -> dict[str, Any]:
        """Get memory coordinator statistics.

        Returns:
            Dict containing statistics
        """
        return {
            "current_level": self.current_level.name,
            "total_evictions": self.total_evictions,
            "total_bytes_freed": self.total_bytes_freed,
            "bytes_freed_mb": self.total_bytes_freed / 1024 / 1024,
            "pressure_events": dict(self.pressure_events),
            "oom_prevented": self.oom_prevented,
            "registered_consumers": len(self.consumers),
            "last_snapshot": (
                {
                    "percent_used": self.last_snapshot.percent_used,
                    "available_mb": self.last_snapshot.available_memory / 1024 / 1024,
                    "pressure": self.last_snapshot.pressure_level.name,
                }
                if self.last_snapshot
                else None
            ),
        }

    def _cleanup_internal_state(self) -> dict[str, Any]:
        """Clean up inactive components (implements SingletonCleanupMixin)."""
        current_time = time.time()
        removed = 0
        for component_id in list(self.consumers.keys()):
            consumer = self.consumers[component_id]
            if consumer.last_eviction > 0 and current_time - consumer.last_eviction > 600:
                del self.consumers[component_id]
                removed += 1
        return {
            "components_removed": removed,
            "components_active": len(self.consumers),
            "current_level": self.current_level.name,
        }


_global_coordinator: MemoryPressureCoordinator | None = None
