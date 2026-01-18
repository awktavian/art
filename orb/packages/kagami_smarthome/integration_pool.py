"""Integration Connection Pool & Management.

Optimizes integration connectivity with:
- Connection pooling and reuse
- Parallel initialization with smart batching
- Adaptive retry strategies

DELEGATES health monitoring to SystemHealthMonitor (Phase 1 refactor).

Targets sub-2s initialization and 99.9% uptime through intelligent
connection management.

Created: December 29, 2025
Updated: December 30, 2025 - Delegate health to SystemHealthMonitor
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any, TypeVar

from kagami_smarthome.performance_monitor import (
    MetricType,
    PerformanceMonitor,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")


class ConnectionState(str, Enum):
    """Connection states for integrations."""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    FAILED = "failed"
    CIRCUIT_OPEN = "circuit_open"


class IntegrationPriority(int, Enum):
    """Priority levels for integration initialization.

    Maps to IntegrationTier in SystemHealthMonitor.
    """

    CRITICAL = 1  # Control4, UniFi (core infrastructure)
    HIGH = 2  # Security, HVAC, Lighting (safety/comfort)
    MEDIUM = 3  # Audio/Video, Smart devices
    LOW = 4  # Appliances, Secondary features


@dataclass
class IntegrationConfig:
    """Configuration for an integration in the pool."""

    name: str
    integration: Any
    priority: IntegrationPriority
    timeout: float = 30.0
    max_retries: int = 3
    retry_delay: float = 2.0
    health_check_interval: float = 300.0  # 5 minutes
    circuit_breaker_threshold: int = 5
    circuit_breaker_timeout: float = 300.0  # 5 minutes
    dependencies: list[str] | None = None
    post_connect_callback: Callable[[], None] | None = None


@dataclass
class ConnectionMetrics:
    """Metrics for an integration connection.

    NOTE: Health metrics are delegated to SystemHealthMonitor.
    This class tracks connection-specific metrics only.
    """

    connection_count: int = 0
    failure_count: int = 0
    last_connection_time: float = 0.0
    last_failure_time: float = 0.0
    total_downtime: float = 0.0
    avg_connection_time: float = 0.0
    # circuit_breaker_trips now tracked by SystemHealthMonitor


def _get_health_monitor():
    """Lazy import to avoid circular dependency."""
    try:
        from kagami.core.integrations.system_health import get_system_health_monitor

        return get_system_health_monitor()
    except ImportError:
        return None


class IntegrationPool:
    """Manages smart home integration connections with optimization.

    DELEGATES health monitoring to SystemHealthMonitor (unified health source).

    Features:
    - Parallel initialization with dependency resolution
    - Circuit breaker delegated to SystemHealthMonitor
    - Automatic retry with exponential backoff
    - Connection pooling and reuse

    Connection Strategy:
    1. Initialize critical integrations first (Control4, UniFi)
    2. Start high-priority integrations in parallel
    3. Continue with medium/low priority as resources allow
    4. Health monitoring delegated to SystemHealthMonitor
    """

    def __init__(self, performance_monitor: PerformanceMonitor | None = None):
        self._integrations: dict[str, IntegrationConfig] = {}
        self._states: dict[str, ConnectionState] = {}
        self._metrics: dict[str, ConnectionMetrics] = {}

        # Circuit breaker state delegated to SystemHealthMonitor
        self._health_monitor = _get_health_monitor()

        self._performance_monitor = performance_monitor
        self._initialization_start_time: float | None = None

        # Concurrency control
        self._max_concurrent_connections = 8
        self._connection_semaphore = asyncio.Semaphore(self._max_concurrent_connections)

        # Background tasks - health monitoring delegated to SystemHealthMonitor
        self._recovery_task: asyncio.Task | None = None
        self._running = False

        # Callbacks
        self._state_callbacks: list[Callable[[str, ConnectionState], None]] = []

    def register_integration(self, config: IntegrationConfig) -> None:
        """Register an integration with the pool."""
        self._integrations[config.name] = config
        self._states[config.name] = ConnectionState.DISCONNECTED
        self._metrics[config.name] = ConnectionMetrics()

        logger.debug(f"Registered integration: {config.name} (priority: {config.priority.name})")

    async def initialize_all(self) -> dict[str, bool]:
        """Initialize all integrations with optimized parallel strategy.

        Returns:
            Dict mapping integration name to success status
        """
        start_time = time.monotonic()
        self._initialization_start_time = start_time

        logger.info("🏠 Starting optimized integration initialization...")

        # Group by priority and resolve dependencies
        priority_groups = self._group_by_priority()
        self._resolve_dependencies()

        results: dict[str, bool] = {}

        # Initialize in priority order with smart batching
        for priority in [
            IntegrationPriority.CRITICAL,
            IntegrationPriority.HIGH,
            IntegrationPriority.MEDIUM,
            IntegrationPriority.LOW,
        ]:
            group_integrations = priority_groups.get(priority, [])
            if not group_integrations:
                continue

            # Filter by dependency resolution
            available_integrations = [
                name for name in group_integrations if self._dependencies_satisfied(name, results)
            ]

            if not available_integrations:
                continue

            logger.info(
                f"🔧 Initializing {priority.name} priority integrations: {available_integrations}"
            )

            # Initialize this priority group in parallel
            group_results = await self._initialize_group(available_integrations)
            results.update(group_results)

            # Record group timing
            group_time = time.monotonic() - start_time
            logger.debug(f"Priority {priority.name} completed in {group_time:.1f}s")

        # Start monitoring
        if not self._running:
            await self.start_monitoring()

        total_time = time.monotonic() - start_time
        success_count = sum(1 for success in results.values() if success)
        total_count = len(results)

        # Record initialization performance
        if self._performance_monitor:
            self._performance_monitor.record_metric(
                MetricType.SCENE_ACTIVATION_TIME,
                total_time * 1000,  # Convert to milliseconds
                "initialization",
                {"success_count": success_count, "total_count": total_count},
            )

        logger.info(
            f"✅ Integration initialization complete: {success_count}/{total_count} "
            f"succeeded in {total_time:.1f}s"
        )

        return results

    def _group_by_priority(self) -> dict[IntegrationPriority, list[str]]:
        """Group integrations by priority level."""
        groups: dict[IntegrationPriority, list[str]] = {}

        for name, config in self._integrations.items():
            if config.priority not in groups:
                groups[config.priority] = []
            groups[config.priority].append(name)

        return groups

    def _resolve_dependencies(self) -> list[str]:
        """Resolve integration dependencies using topological sort."""
        # Build dependency graph
        graph: dict[str, list[str]] = {}
        in_degree: dict[str, int] = {}

        for name, config in self._integrations.items():
            graph[name] = config.dependencies or []
            in_degree[name] = 0

        # Calculate in-degrees
        for name, deps in graph.items():
            for dep in deps:
                if dep in in_degree:
                    in_degree[name] += 1

        # Topological sort
        queue = [name for name, degree in in_degree.items() if degree == 0]
        result = []

        while queue:
            current = queue.pop(0)
            result.append(current)

            for name, deps in graph.items():
                if current in deps:
                    in_degree[name] -= 1
                    if in_degree[name] == 0:
                        queue.append(name)

        return result

    def _dependencies_satisfied(
        self, integration_name: str, completed_results: dict[str, bool]
    ) -> bool:
        """Check if integration dependencies are satisfied."""
        config = self._integrations[integration_name]
        if not config.dependencies:
            return True

        for dep in config.dependencies:
            if dep not in completed_results or not completed_results[dep]:
                return False

        return True

    async def _initialize_group(self, integration_names: list[str]) -> dict[str, bool]:
        """Initialize a group of integrations in parallel."""
        tasks = []

        for name in integration_names:
            task = asyncio.create_task(self._initialize_integration(name), name=f"init_{name}")
            tasks.append((name, task))

        # Wait for all tasks with timeout
        results = {}

        try:
            done, pending = await asyncio.wait(
                [task for _, task in tasks],
                timeout=60.0,  # 1 minute timeout for the group
                return_when=asyncio.ALL_COMPLETED,
            )

            # Process completed tasks
            for name, task in tasks:
                if task in done:
                    try:
                        results[name] = await task
                    except Exception as e:
                        logger.error(f"Integration {name} failed: {e}")
                        results[name] = False
                else:
                    # Task didn't complete, cancel it
                    task.cancel()
                    results[name] = False
                    logger.warning(f"Integration {name} timed out")

            # Cancel any pending tasks
            for task in pending:
                task.cancel()

        except Exception as e:
            logger.error(f"Group initialization error: {e}")
            for name in integration_names:
                results[name] = False

        return results

    async def _initialize_integration(self, name: str) -> bool:
        """Initialize a single integration with monitoring."""
        async with self._connection_semaphore:
            config = self._integrations[name]
            metrics = self._metrics[name]

            # Check circuit breaker
            if self._is_circuit_open(name):
                logger.debug(f"Circuit breaker open for {name}, skipping")
                return False

            start_time = time.monotonic()

            try:
                self._set_state(name, ConnectionState.CONNECTING)

                # Attempt connection with timeout
                success = await asyncio.wait_for(
                    self._connect_integration(config), timeout=config.timeout
                )

                connection_time = time.monotonic() - start_time

                if success:
                    # Update metrics
                    metrics.connection_count += 1
                    metrics.last_connection_time = time.time()

                    # Update average connection time
                    if metrics.avg_connection_time == 0:
                        metrics.avg_connection_time = connection_time
                    else:
                        # Exponential moving average
                        alpha = 0.1
                        metrics.avg_connection_time = (
                            alpha * connection_time + (1 - alpha) * metrics.avg_connection_time
                        )

                    self._set_state(name, ConnectionState.CONNECTED)

                    # Record performance
                    if self._performance_monitor:
                        self._performance_monitor.record_metric(
                            MetricType.CONNECTION_LATENCY,
                            connection_time * 1000,  # Convert to ms
                            name,
                        )

                    # Execute post-connect callback
                    if config.post_connect_callback:
                        try:
                            config.post_connect_callback()
                        except Exception as e:
                            logger.warning(f"{name} post-connect callback failed: {e}")

                    logger.debug(f"✅ {name} connected in {connection_time:.1f}s")
                    return True
                else:
                    raise Exception("Integration returned False")

            except TimeoutError:
                logger.warning(f"⏰ {name} connection timeout ({config.timeout}s)")
                self._handle_connection_failure(name)
                return False

            except Exception as e:
                logger.debug(f"❌ {name} connection failed: {e}")
                self._handle_connection_failure(name)
                return False

    async def _connect_integration(self, config: IntegrationConfig) -> bool:
        """Connect to an integration."""
        try:
            integration = config.integration

            # Call the integration's connect method
            if hasattr(integration, "connect"):
                if asyncio.iscoroutinefunction(integration.connect):
                    return await integration.connect()
                else:
                    return integration.connect()
            else:
                # If no connect method, assume it's always available
                return True

        except Exception as e:
            logger.debug(f"Integration connection error: {e}")
            return False

    def _handle_connection_failure(self, name: str) -> None:
        """Handle integration connection failure.

        Circuit breaker logic delegated to SystemHealthMonitor.
        """
        metrics = self._metrics[name]

        metrics.failure_count += 1
        metrics.last_failure_time = time.time()

        self._set_state(name, ConnectionState.FAILED)

        # Record performance
        if self._performance_monitor:
            total_operations = metrics.connection_count + metrics.failure_count
            error_rate = metrics.failure_count / max(total_operations, 1)

            self._performance_monitor.record_metric(MetricType.ERROR_RATE, error_rate, name)

        # Notify SystemHealthMonitor of failure (it handles circuit breaker)
        if self._health_monitor:
            health = self._health_monitor.get_health(name)
            if health:
                health.record_failure(f"Connection failed (attempt {metrics.failure_count})")

    def _is_circuit_open(self, name: str) -> bool:
        """Check if circuit breaker is open for integration.

        DELEGATES to SystemHealthMonitor.
        """
        if self._health_monitor:
            return self._health_monitor.is_circuit_open(name)
        return False

    def get_circuit_status(self, name: str) -> dict[str, Any] | None:
        """Get circuit breaker status from SystemHealthMonitor."""
        if self._health_monitor:
            return self._health_monitor.get_circuit_status(name)
        return None

    def _set_state(self, name: str, state: ConnectionState) -> None:
        """Set integration state and notify callbacks."""
        old_state = self._states.get(name, ConnectionState.DISCONNECTED)
        self._states[name] = state

        if old_state != state:
            logger.debug(f"{name}: {old_state.value} → {state.value}")

            for callback in self._state_callbacks:
                try:
                    callback(name, state)
                except Exception as e:
                    logger.error(f"State callback error: {e}")

    async def start_monitoring(self) -> None:
        """Start background recovery loop.

        Health monitoring delegated to SystemHealthMonitor.
        """
        if self._running:
            return

        self._running = True

        # Health monitoring delegated to SystemHealthMonitor
        # We only run recovery loop here
        self._recovery_task = asyncio.create_task(self._recovery_loop())

        logger.info(
            "📊 Integration pool recovery started (health delegated to SystemHealthMonitor)"
        )

    async def stop_monitoring(self) -> None:
        """Stop background monitoring."""
        self._running = False

        if self._recovery_task:
            self._recovery_task.cancel()
            try:
                await self._recovery_task
            except asyncio.CancelledError:
                pass

    async def _recovery_loop(self) -> None:
        """Attempt recovery of failed integrations."""
        while self._running:
            try:
                await self._attempt_recovery()
                await asyncio.sleep(120)  # Recovery attempt every 2 minutes
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Recovery loop error: {e}")
                await asyncio.sleep(60)

    async def _attempt_recovery(self) -> None:
        """Attempt to recover failed integrations."""
        failed_integrations = [
            name
            for name, state in self._states.items()
            if state in (ConnectionState.FAILED, ConnectionState.DISCONNECTED)
        ]

        for name in failed_integrations:
            if self._is_circuit_open(name):
                continue

            config = self._integrations[name]
            metrics = self._metrics[name]

            # Exponential backoff based on failure count
            delay = min(
                config.retry_delay * (2 ** min(metrics.failure_count, 6)),
                300,  # Max 5 minute delay
            )

            if time.time() - metrics.last_failure_time < delay:
                continue

            logger.info(f"🔄 Attempting recovery for {name}")

            success = await self._initialize_integration(name)
            if success:
                logger.info(f"✅ Successfully recovered {name}")
                # Notify SystemHealthMonitor of success
                if self._health_monitor:
                    health = self._health_monitor.get_health(name)
                    if health:
                        health.record_success()

    def get_state(self, name: str) -> ConnectionState:
        """Get current state of an integration."""
        return self._states.get(name, ConnectionState.DISCONNECTED)

    def get_metrics(self, name: str) -> ConnectionMetrics:
        """Get metrics for an integration."""
        return self._metrics.get(name, ConnectionMetrics())

    def get_all_states(self) -> dict[str, ConnectionState]:
        """Get states of all integrations."""
        return self._states.copy()

    def get_connected_integrations(self) -> list[str]:
        """Get list of currently connected integrations."""
        return [name for name, state in self._states.items() if state == ConnectionState.CONNECTED]

    def get_failed_integrations(self) -> list[str]:
        """Get list of failed integrations."""
        return [name for name, state in self._states.items() if state == ConnectionState.FAILED]

    def on_state_change(self, callback: Callable[[str, ConnectionState], None]) -> None:
        """Register callback for state changes."""
        self._state_callbacks.append(callback)

    def get_initialization_time(self) -> float | None:
        """Get total initialization time in seconds."""
        if self._initialization_start_time is None:
            return None

        return time.monotonic() - self._initialization_start_time

    async def stop(self) -> None:
        """Stop the integration pool and monitoring."""
        await self.stop_monitoring()
