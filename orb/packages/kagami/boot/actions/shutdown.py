"""Shutdown actions for boot process.

Graceful shutdown handlers for all subsystems.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from fastapi import FastAPI

logger = logging.getLogger(__name__)


async def _shutdown_service(name: str, shutdown_fn: Any) -> None:
    """Helper to shutdown a single service with error handling."""
    try:
        await shutdown_fn()
        logger.info(f"✓ {name} shut down")
    except Exception as e:
        # OK to catch all exceptions during shutdown - must attempt all cleanup
        logger.error(f"{name} shutdown error: {e}")


async def shutdown_all(app: FastAPI) -> None:
    """Shutdown all services gracefully."""
    logger.info("Shutting down K os...")

    # Shutdown services in reverse startup order

    # Stop receipt stream processor first (depends on learning systems)
    if hasattr(app.state, "receipt_processor") and app.state.receipt_processor:
        await _shutdown_service("Receipt stream processor", app.state.receipt_processor.stop)

    # Stop unified event bus (best-effort; may already be stopped by BootGraph)
    if hasattr(app.state, "e8_bus") and app.state.e8_bus:
        await _shutdown_service("UnifiedE8Bus", app.state.e8_bus.stop)

    # Shutdown world model registry
    if hasattr(app.state, "production_systems") and app.state.production_systems:
        # World model registry shutdown (if it has shutdown method)
        if (
            hasattr(app.state.production_systems, "world_model_registry")
            and app.state.production_systems.world_model_registry
        ):
            if hasattr(app.state.production_systems.world_model_registry, "shutdown"):
                try:
                    await app.state.production_systems.world_model_registry.shutdown()
                    logger.info("✓ World model registry shut down")
                except Exception as e:
                    # OK to catch all exceptions during shutdown - must attempt all cleanup
                    logger.error(f"World model registry shutdown error: {e}")

    # Shutdown learning loop first (depends on production systems)
    if hasattr(app.state, "learning_loop") and app.state.learning_loop:
        await _shutdown_service("Learning loop", app.state.learning_loop.stop)

    # Shutdown production systems (contains stateful components)
    if hasattr(app.state, "production_systems") and app.state.production_systems:
        await _shutdown_service("Production systems", app.state.production_systems.shutdown)

    if hasattr(app.state, "orchestrator"):
        await _shutdown_service("Orchestrator", app.state.orchestrator.shutdown)

    if hasattr(app.state, "unified_organism") and app.state.unified_organism:
        await _shutdown_service("Unified organism", app.state.unified_organism.stop)

    if hasattr(app.state, "brain_api"):
        await _shutdown_service("Brain", app.state.brain_api.stop)

    if hasattr(app.state, "background_task_manager"):
        await _shutdown_service("Background tasks", app.state.background_task_manager.stop)

    # Stop job storage cleanup tasks
    if hasattr(app.state, "job_storage_image") and app.state.job_storage_image:
        await _shutdown_service("Image job cleanup", app.state.job_storage_image.stop_cleanup_task)

    if hasattr(app.state, "job_storage_animation") and app.state.job_storage_animation:
        await _shutdown_service(
            "Animation job cleanup", app.state.job_storage_animation.stop_cleanup_task
        )

    # Shutdown Ambient Controller (uses HAL, must shutdown before HAL)
    if hasattr(app.state, "ambient_controller") and app.state.ambient_controller:
        try:
            await app.state.ambient_controller.shutdown()
            logger.info("✓ Ambient Controller shutdown")
        except Exception as e:
            # OK to catch all exceptions during shutdown - must attempt all cleanup
            logger.error(f"Ambient Controller shutdown error: {e}")

    # Shutdown HAL (hardware adapters)
    if hasattr(app.state, "hal_manager") and app.state.hal_manager:
        try:
            from kagami_hal.manager import shutdown_hal_manager

            await shutdown_hal_manager()
            logger.info("✓ HAL shutdown")
        except Exception as e:
            # OK to catch all exceptions during shutdown - must attempt all cleanup
            logger.error(f"HAL shutdown error: {e}")

    # Shutdown Ambient OS (Multi-Device Coordinator)
    if hasattr(app.state, "device_coordinator") and app.state.device_coordinator:
        try:
            await app.state.device_coordinator.stop()
            logger.info("✓ Ambient OS coordinator stopped")
        except Exception as e:
            # OK to catch all exceptions during shutdown - must attempt all cleanup
            logger.error(f"Ambient OS shutdown error: {e}")

    # Close connections
    try:
        from kagami.core.database.async_connection import close_async_engine

        await close_async_engine()
        logger.info("✓ Database closed")
    except Exception as e:
        # OK to catch all exceptions during shutdown - best-effort cleanup
        logger.debug(f"Database shutdown (best-effort): {e}")

    try:
        from kagami.core.caching.redis import RedisClientFactory

        await RedisClientFactory.aclose_all()
        logger.info("✓ Redis closed")
    except Exception as e:
        # OK to catch all exceptions during shutdown - must attempt all cleanup
        logger.error(f"Redis shutdown error: {e}")

    # Clear Socket.IO global to avoid stale refs in test environments
    try:
        from kagami_api.socketio_server import set_socketio_server

        set_socketio_server(None)
    except Exception:
        pass  # OK to continue on cleanup failure

    logger.info("✅ K os shut down complete")


__all__ = ["shutdown_all"]
