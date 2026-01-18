from kagami.core.async_utils import safe_create_task

"Graceful shutdown coordinator for K os.\n\nEnsures clean shutdown of all components with proper resource cleanup,\nconnection draining, and state persistence.\n"
import asyncio
import logging
import signal
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class ShutdownPhase(Enum):
    """Phases of graceful shutdown."""

    RUNNING = "running"
    DRAINING = "draining"
    FINISHING = "finishing"
    CLEANUP = "cleanup"
    TERMINATED = "terminated"


class ComponentType(Enum):
    """Types of components for shutdown ordering."""

    API = "api"
    WEBSOCKET = "websocket"
    WORKER = "worker"
    DATABASE = "database"
    CACHE = "cache"
    MESSAGING = "messaging"
    MONITORING = "monitoring"


@dataclass
class ShutdownComponent:
    """Component registration for shutdown."""

    component_id: str
    name: str
    component_type: ComponentType
    shutdown_callback: Callable[[], Any]
    cleanup_callback: Callable[[], Any] | None = None
    drain_callback: Callable[[], Any] | None = None
    timeout: float = 30.0
    priority: int = 0
    dependencies: set[str] = field(default_factory=set[Any])
    metadata: dict[str, Any] = field(default_factory=dict[str, Any])


class GracefulShutdownCoordinator:
    """Coordinates graceful shutdown across all components.

    Features:
    - Phased shutdown (drain -> finish -> cleanup)
    - Component dependency ordering
    - Timeout enforcement
    - Signal handling (SIGTERM, SIGINT)
    - Resource cleanup tracking
    """

    DEFAULT_PRIORITIES = {
        ComponentType.API: 0,
        ComponentType.WEBSOCKET: 1,
        ComponentType.WORKER: 2,
        ComponentType.MESSAGING: 3,
        ComponentType.CACHE: 4,
        ComponentType.DATABASE: 5,
        ComponentType.MONITORING: 6,
    }

    def __init__(
        self,
        drain_timeout: float = 10.0,
        finish_timeout: float = 30.0,
        cleanup_timeout: float = 10.0,
    ) -> None:
        """Initialize shutdown coordinator.

        Args:
            drain_timeout: Timeout for draining phase
            finish_timeout: Timeout for finishing in-flight work
            cleanup_timeout: Timeout for cleanup phase
        """
        self.drain_timeout = drain_timeout
        self.finish_timeout = finish_timeout
        self.cleanup_timeout = cleanup_timeout
        self.components: dict[str, ShutdownComponent] = {}
        self._lock = asyncio.Lock()
        self.phase = ShutdownPhase.RUNNING
        self.shutdown_started: float | None = None
        self.shutdown_completed: float | None = None
        self.on_phase_change: list[Callable[[ShutdownPhase], None]] = []
        self._signal_received = False
        self._shutdown_task: asyncio.Task | None = None
        self._loop: asyncio.AbstractEventLoop | None = None  # Set when signal handlers installed
        self.components_drained = 0
        self.components_finished = 0
        self.components_cleaned = 0
        self.components_failed: list[str] = []
        logger.info("Initialized GracefulShutdownCoordinator")

    def register_component(
        self,
        component_id: str,
        name: str,
        component_type: ComponentType,
        shutdown_callback: Callable[[], Any],
        cleanup_callback: Callable[[], Any] | None = None,
        drain_callback: Callable[[], Any] | None = None,
        timeout: float | None = None,
        priority: int | None = None,
        dependencies: set[str] | None = None,
        **metadata: Any,
    ) -> None:
        """Register a component for graceful shutdown.

        Args:
            component_id: Unique component identifier
            name: Human-readable component name
            component_type: Type of component
            shutdown_callback: Function to call for shutdown
            cleanup_callback: Optional cleanup function
            drain_callback: Optional drain function
            timeout: Component-specific timeout
            priority: Shutdown priority (lower = earlier)
            dependencies: Component IDs that must shutdown first
            **metadata: Additional metadata
        """
        if priority is None:
            priority = self.DEFAULT_PRIORITIES.get(component_type, 99)
        component = ShutdownComponent(
            component_id=component_id,
            name=name,
            component_type=component_type,
            shutdown_callback=shutdown_callback,
            cleanup_callback=cleanup_callback,
            drain_callback=drain_callback,
            timeout=timeout or 30.0,
            priority=priority,
            dependencies=dependencies or set(),
            metadata=metadata,
        )
        self.components[component_id] = component
        logger.info(
            f"Registered shutdown component: {name} (type={component_type.value}, priority={priority})"
        )

    def install_signal_handlers(self) -> None:
        """Install signal handlers for graceful shutdown.

        Must be called from within an async context (running event loop).
        """
        # Capture the running loop when signal handlers are installed
        try:
            self._loop = asyncio.get_running_loop()
        except RuntimeError:
            logger.warning("No running event loop - signal handlers may not work correctly")
            self._loop = None

        def signal_handler(signum: int, frame: Any) -> None:
            logger.info(f"Received signal {signum}, initiating graceful shutdown")
            self._signal_received = True
            if self._loop and not self._loop.is_closed():
                if not self._shutdown_task or self._shutdown_task.done():
                    self._shutdown_task = self._loop.create_task(self.shutdown())
            else:
                logger.warning("Event loop not available - shutdown must be called manually")

        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)
        logger.info("Installed signal handlers for graceful shutdown")

    async def shutdown(self) -> None:
        """Execute graceful shutdown sequence."""
        if self.phase != ShutdownPhase.RUNNING:
            logger.warning(f"Shutdown already in progress (phase: {self.phase.value})")
            return
        logger.info("Starting graceful shutdown sequence")
        self.shutdown_started = time.time()
        try:
            await self._execute_phase(
                ShutdownPhase.DRAINING, self._drain_components, self.drain_timeout
            )
            await self._execute_phase(
                ShutdownPhase.FINISHING, self._finish_components, self.finish_timeout
            )
            await self._execute_phase(
                ShutdownPhase.CLEANUP, self._cleanup_components, self.cleanup_timeout
            )
            self.phase = ShutdownPhase.TERMINATED
            self.shutdown_completed = time.time()
            await self._notify_phase_change(ShutdownPhase.TERMINATED)
            duration = self.shutdown_completed - self.shutdown_started
            logger.info(
                f"Graceful shutdown completed in {duration:.2f}s (drained={self.components_drained}, finished={self.components_finished}, cleaned={self.components_cleaned}, failed={len(self.components_failed)})"
            )
        except Exception as e:
            logger.error(f"Error during graceful shutdown: {e}")
            self.phase = ShutdownPhase.TERMINATED
            raise

    async def _execute_phase(
        self, phase: ShutdownPhase, executor: Callable, timeout: float
    ) -> None:
        """Execute a shutdown phase.

        Args:
            phase: Phase to execute
            executor: Function to execute the phase
            timeout: Phase timeout
        """
        logger.info(f"Entering shutdown phase: {phase.value}")
        self.phase = phase
        await self._notify_phase_change(phase)
        try:
            await asyncio.wait_for(executor(), timeout=timeout)
        except TimeoutError:
            logger.warning(f"Phase {phase.value} timed out after {timeout}s")

    async def _drain_components(self) -> None:
        """Execute drain phase - stop accepting new work."""
        ordered = self._get_ordered_components()
        for component in ordered:
            if component.drain_callback:
                try:
                    logger.debug(f"Draining component: {component.name}")
                    if asyncio.iscoroutinefunction(component.drain_callback):
                        await component.drain_callback()
                    else:
                        component.drain_callback()
                    self.components_drained += 1
                except Exception as e:
                    logger.error(f"Failed to drain {component.name}: {e}")
                    self.components_failed.append(component.component_id)

    async def _finish_components(self) -> None:
        """Execute finish phase - complete in-flight work."""
        ordered = self._get_ordered_components()
        shutdown_tasks = []
        for component in ordered:
            task = safe_create_task(self._shutdown_component(component, name="_shutdown_component"))  # type: ignore[call-arg]
            shutdown_tasks.append((component, task))
        for component, task in shutdown_tasks:
            try:
                await asyncio.wait_for(task, timeout=component.timeout)
                self.components_finished += 1
            except TimeoutError:
                logger.error(f"Component {component.name} shutdown timed out")
                self.components_failed.append(component.component_id)
                task.cancel()
            except Exception as e:
                logger.error(f"Component {component.name} shutdown failed: {e}")
                self.components_failed.append(component.component_id)

    async def _shutdown_component(self, component: ShutdownComponent) -> None:
        """Shutdown a single component.

        Args:
            component: Component to shutdown
        """
        try:
            logger.debug(f"Shutting down component: {component.name}")
            if asyncio.iscoroutinefunction(component.shutdown_callback):
                await component.shutdown_callback()
            else:
                component.shutdown_callback()
        except Exception as e:
            logger.error(f"Error shutting down {component.name}: {e}")
            raise

    async def _cleanup_components(self) -> None:
        """Execute cleanup phase - release resources."""
        ordered = list(reversed(self._get_ordered_components()))
        for component in ordered:
            if component.cleanup_callback:
                try:
                    logger.debug(f"Cleaning up component: {component.name}")
                    if asyncio.iscoroutinefunction(component.cleanup_callback):
                        await component.cleanup_callback()
                    else:
                        component.cleanup_callback()
                    self.components_cleaned += 1
                except Exception as e:
                    logger.error(f"Failed to cleanup {component.name}: {e}")
                    self.components_failed.append(component.component_id)

    def _get_ordered_components(self) -> list[ShutdownComponent]:
        """Get components ordered by priority and dependencies.

        Returns:
            List of components in shutdown order
        """
        ordered = []
        visited = set()

        def visit(component_id: str) -> None:
            if component_id in visited:
                return
            component = self.components.get(component_id)
            if not component:
                return
            for dep_id in component.dependencies:
                visit(dep_id)
            visited.add(component_id)
            ordered.append(component)

        for component_id in self.components:
            visit(component_id)
        ordered.sort(key=lambda c: c.priority)
        return ordered

    async def _notify_phase_change(self, phase: ShutdownPhase) -> None:
        """Notify callbacks of phase change.

        Args:
            phase: New phase
        """
        for callback in self.on_phase_change:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(phase)
                else:
                    callback(phase)
            except Exception as e:
                logger.error(f"Phase change callback failed: {e}")

    def is_shutting_down(self) -> bool:
        """Check if shutdown is in progress.

        Returns:
            bool: True if shutting down
        """
        return self.phase != ShutdownPhase.RUNNING

    def get_stats(self) -> dict[str, Any]:
        """Get shutdown statistics.

        Returns:
            Dict containing statistics
        """
        stats = {
            "phase": self.phase.value,
            "registered_components": len(self.components),
            "components_drained": self.components_drained,
            "components_finished": self.components_finished,
            "components_cleaned": self.components_cleaned,
            "components_failed": len(self.components_failed),
            "failed_components": self.components_failed,
        }
        if self.shutdown_started:
            stats["shutdown_started"] = self.shutdown_started  # type: ignore[assignment]
            if self.shutdown_completed:
                stats["shutdown_duration"] = self.shutdown_completed - self.shutdown_started  # type: ignore[assignment]
        return stats


_global_coordinator: GracefulShutdownCoordinator | None = None
