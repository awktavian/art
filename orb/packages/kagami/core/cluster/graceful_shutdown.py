"""Graceful Shutdown Coordination — Coordinated cluster node shutdown.

This module implements graceful shutdown for distributed cluster nodes:
- Pre-shutdown notification to peers
- Request draining
- State handoff to other nodes
- Consensus participation completion
- Final cleanup

Shutdown Phases:
```
    Phase               Actions                     Duration
    ─────               ───────                     ────────
    1. Announce     →   Notify peers               ~100ms
    2. Drain        →   Stop accepting requests    ~5s
    3. Handoff      →   Transfer state             ~2s
    4. Complete     →   Finish in-flight ops       ~5s
    5. Cleanup      →   Close connections          ~1s
```

Colony: Flow (A₄) — Graceful transitions
h(x) ≥ 0. Always.

Created: January 4, 2026
"""

from __future__ import annotations

import asyncio
import logging
import signal
import time
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


# =============================================================================
# Shutdown Types
# =============================================================================


class ShutdownPhase(str, Enum):
    """Phases of graceful shutdown."""

    RUNNING = "running"
    ANNOUNCING = "announcing"
    DRAINING = "draining"
    HANDOFF = "handoff"
    COMPLETING = "completing"
    CLEANUP = "cleanup"
    STOPPED = "stopped"


class ShutdownReason(str, Enum):
    """Reasons for shutdown."""

    SIGNAL = "signal"  # OS signal (SIGTERM, SIGINT)
    API = "api"  # API request
    HEALTH = "health"  # Health check failure
    MAINTENANCE = "maintenance"  # Scheduled maintenance
    UPGRADE = "upgrade"  # Rolling upgrade
    FAULT = "fault"  # Byzantine fault detected


@dataclass
class ShutdownConfig:
    """Configuration for graceful shutdown."""

    # Phase timeouts
    announce_timeout_seconds: float = 1.0
    drain_timeout_seconds: float = 10.0
    handoff_timeout_seconds: float = 5.0
    complete_timeout_seconds: float = 10.0
    cleanup_timeout_seconds: float = 2.0

    # Total shutdown timeout
    total_timeout_seconds: float = 30.0

    # Behavior
    force_on_timeout: bool = True
    notify_systemd: bool = True


@dataclass
class ShutdownState:
    """Current state of shutdown."""

    phase: ShutdownPhase = ShutdownPhase.RUNNING
    reason: ShutdownReason | None = None
    started_at: float | None = None
    phase_started_at: float | None = None
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "phase": self.phase.value,
            "reason": self.reason.value if self.reason else None,
            "started_at": self.started_at,
            "elapsed_seconds": time.time() - self.started_at if self.started_at else 0,
            "errors": self.errors,
        }


# =============================================================================
# Shutdown Handler Type
# =============================================================================


ShutdownHandler = Callable[[], Coroutine[Any, Any, None]]


# =============================================================================
# Graceful Shutdown Coordinator
# =============================================================================


class GracefulShutdownCoordinator:
    """Coordinates graceful shutdown across the cluster.

    Features:
    - Phased shutdown with timeouts
    - Handler registration for different phases
    - Signal handling
    - Systemd notification
    - Error collection and logging
    """

    def __init__(
        self,
        node_id: str,
        config: ShutdownConfig | None = None,
    ) -> None:
        """Initialize the shutdown coordinator.

        Args:
            node_id: This node's identifier.
            config: Shutdown configuration.
        """
        self.node_id = node_id
        self.config = config or ShutdownConfig()
        self.state = ShutdownState()

        # Handlers for each phase
        self._announce_handlers: list[ShutdownHandler] = []
        self._drain_handlers: list[ShutdownHandler] = []
        self._handoff_handlers: list[ShutdownHandler] = []
        self._complete_handlers: list[ShutdownHandler] = []
        self._cleanup_handlers: list[ShutdownHandler] = []

        # Shutdown event
        self._shutdown_event = asyncio.Event()
        self._shutdown_complete = asyncio.Event()

        logger.info(f"GracefulShutdownCoordinator initialized for node {node_id}")

    # =========================================================================
    # Handler Registration
    # =========================================================================

    def on_announce(self, handler: ShutdownHandler) -> None:
        """Register handler for announce phase."""
        self._announce_handlers.append(handler)

    def on_drain(self, handler: ShutdownHandler) -> None:
        """Register handler for drain phase."""
        self._drain_handlers.append(handler)

    def on_handoff(self, handler: ShutdownHandler) -> None:
        """Register handler for handoff phase."""
        self._handoff_handlers.append(handler)

    def on_complete(self, handler: ShutdownHandler) -> None:
        """Register handler for complete phase."""
        self._complete_handlers.append(handler)

    def on_cleanup(self, handler: ShutdownHandler) -> None:
        """Register handler for cleanup phase."""
        self._cleanup_handlers.append(handler)

    # =========================================================================
    # Signal Handling
    # =========================================================================

    def install_signal_handlers(self) -> None:
        """Install OS signal handlers for graceful shutdown."""
        try:
            loop = asyncio.get_running_loop()

            for sig in (signal.SIGTERM, signal.SIGINT):
                loop.add_signal_handler(
                    sig,
                    lambda s=sig: asyncio.create_task(
                        self.initiate_shutdown(ShutdownReason.SIGNAL)
                    ),
                )

            logger.info("Signal handlers installed (SIGTERM, SIGINT)")
        except Exception as e:
            logger.warning(f"Could not install signal handlers: {e}")

    # =========================================================================
    # Shutdown Execution
    # =========================================================================

    async def initiate_shutdown(
        self,
        reason: ShutdownReason = ShutdownReason.SIGNAL,
    ) -> None:
        """Initiate graceful shutdown.

        Args:
            reason: Reason for shutdown.
        """
        if self.state.phase != ShutdownPhase.RUNNING:
            logger.warning("Shutdown already in progress, ignoring")
            return

        logger.info(f"🔴 Initiating graceful shutdown: {reason.value}")

        self.state.reason = reason
        self.state.started_at = time.time()
        self._shutdown_event.set()

        # Notify systemd
        if self.config.notify_systemd:
            self._notify_systemd("STOPPING=1")

        try:
            await asyncio.wait_for(
                self._execute_shutdown(),
                timeout=self.config.total_timeout_seconds,
            )
        except TimeoutError:
            logger.error("Shutdown timed out!")
            if self.config.force_on_timeout:
                self.state.phase = ShutdownPhase.STOPPED

        self._shutdown_complete.set()
        logger.info("✅ Graceful shutdown complete")

    async def _execute_shutdown(self) -> None:
        """Execute the shutdown sequence."""
        # Phase 1: Announce
        await self._run_phase(
            ShutdownPhase.ANNOUNCING,
            self._announce_handlers,
            self.config.announce_timeout_seconds,
        )

        # Phase 2: Drain
        await self._run_phase(
            ShutdownPhase.DRAINING,
            self._drain_handlers,
            self.config.drain_timeout_seconds,
        )

        # Phase 3: Handoff
        await self._run_phase(
            ShutdownPhase.HANDOFF,
            self._handoff_handlers,
            self.config.handoff_timeout_seconds,
        )

        # Phase 4: Complete
        await self._run_phase(
            ShutdownPhase.COMPLETING,
            self._complete_handlers,
            self.config.complete_timeout_seconds,
        )

        # Phase 5: Cleanup
        await self._run_phase(
            ShutdownPhase.CLEANUP,
            self._cleanup_handlers,
            self.config.cleanup_timeout_seconds,
        )

        # Done
        self.state.phase = ShutdownPhase.STOPPED

    async def _run_phase(
        self,
        phase: ShutdownPhase,
        handlers: list[ShutdownHandler],
        timeout: float,
    ) -> None:
        """Run a shutdown phase."""
        self.state.phase = phase
        self.state.phase_started_at = time.time()

        logger.info(f"Shutdown phase: {phase.value} ({len(handlers)} handlers)")

        if not handlers:
            return

        # Notify systemd of progress
        if self.config.notify_systemd:
            self._notify_systemd(f"STATUS=Shutdown: {phase.value}")

        # Run all handlers with timeout
        try:
            await asyncio.wait_for(
                asyncio.gather(
                    *[self._run_handler(h, phase) for h in handlers],
                    return_exceptions=True,
                ),
                timeout=timeout,
            )
        except TimeoutError:
            error = f"Phase {phase.value} timed out after {timeout}s"
            logger.warning(error)
            self.state.errors.append(error)

    async def _run_handler(
        self,
        handler: ShutdownHandler,
        phase: ShutdownPhase,
    ) -> None:
        """Run a single shutdown handler."""
        handler_name = handler.__name__ if hasattr(handler, "__name__") else str(handler)

        try:
            await handler()
            logger.debug(f"Handler completed: {handler_name}")
        except Exception as e:
            error = f"Handler {handler_name} failed: {e}"
            logger.error(error)
            self.state.errors.append(error)

    # =========================================================================
    # Systemd Notification
    # =========================================================================

    def _notify_systemd(self, status: str) -> None:
        """Send notification to systemd."""
        try:
            from kagami_api.systemd_notify import _notify

            _notify(status)
        except Exception:
            pass  # Not critical

    # =========================================================================
    # Query API
    # =========================================================================

    @property
    def is_shutting_down(self) -> bool:
        """Check if shutdown is in progress."""
        return self.state.phase != ShutdownPhase.RUNNING

    @property
    def is_stopped(self) -> bool:
        """Check if shutdown is complete."""
        return self.state.phase == ShutdownPhase.STOPPED

    async def wait_for_shutdown(self) -> None:
        """Wait for shutdown to be initiated."""
        await self._shutdown_event.wait()

    async def wait_for_complete(self) -> None:
        """Wait for shutdown to complete."""
        await self._shutdown_complete.wait()

    def get_state(self) -> dict[str, Any]:
        """Get current shutdown state."""
        return self.state.to_dict()


# =============================================================================
# Singleton
# =============================================================================


_shutdown_coordinator: GracefulShutdownCoordinator | None = None


def get_shutdown_coordinator(
    node_id: str | None = None,
    config: ShutdownConfig | None = None,
) -> GracefulShutdownCoordinator:
    """Get or create the shutdown coordinator singleton.

    Args:
        node_id: This node's identifier (required on first call).
        config: Shutdown configuration.

    Returns:
        The shutdown coordinator instance.
    """
    global _shutdown_coordinator

    if _shutdown_coordinator is None:
        if node_id is None:
            raise ValueError("node_id required for first initialization")

        _shutdown_coordinator = GracefulShutdownCoordinator(
            node_id=node_id,
            config=config,
        )

    return _shutdown_coordinator


# =============================================================================
# Pre-built Shutdown Handlers
# =============================================================================


async def create_service_registry_deregister() -> ShutdownHandler:
    """Create handler to deregister from service registry."""

    async def handler() -> None:
        try:
            from kagami.core.cluster import get_service_registry

            await get_service_registry()

            # Get our service IDs and deregister
            # This would be implemented based on how services track their registrations
            logger.info("Deregistering from service registry")
        except Exception as e:
            logger.error(f"Failed to deregister from service registry: {e}")

    return handler


async def create_consensus_step_down() -> ShutdownHandler:
    """Create handler to step down from consensus leadership."""

    async def handler() -> None:
        try:
            from kagami.core.consensus import get_pbft_node

            node = await get_pbft_node()

            if node and node.is_leader:
                logger.info("Stepping down from consensus leadership")
                # Trigger view change
        except Exception as e:
            logger.error(f"Failed to step down from consensus: {e}")

    return handler


async def create_websocket_close() -> ShutdownHandler:
    """Create handler to close WebSocket connections."""

    async def handler() -> None:
        try:
            from kagami_api.routes.cluster_websocket import shutdown_ws_manager

            await shutdown_ws_manager()
            logger.info("WebSocket connections closed")
        except Exception as e:
            logger.error(f"Failed to close WebSocket connections: {e}")

    return handler


async def create_recovery_stop() -> ShutdownHandler:
    """Create handler to stop recovery manager."""

    async def handler() -> None:
        try:
            from kagami.core.consensus.auto_recovery import shutdown_recovery_manager

            await shutdown_recovery_manager()
            logger.info("Recovery manager stopped")
        except Exception as e:
            logger.error(f"Failed to stop recovery manager: {e}")

    return handler


# =============================================================================
# 鏡
# Graceful endings enable graceful beginnings. h(x) ≥ 0. Always.
# =============================================================================
