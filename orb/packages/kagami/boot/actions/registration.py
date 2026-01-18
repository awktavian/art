"""Registration actions for boot process.

Actions that register components and subsystems:
- HAL adapters
- Device coordinators
- Socket.IO servers
- Production systems
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import FastAPI

logger = logging.getLogger(__name__)


async def startup_hal(app: FastAPI) -> None:
    """Initialize Hardware Abstraction Layer."""
    from kagami_hal.manager import get_hal_manager

    try:
        logger.info("🔧 Initializing HAL...")

        # Initialize HAL manager (auto-detects platform and loads adapters)
        # Protect boot from hardware stalls
        hal_manager = await asyncio.wait_for(get_hal_manager(), timeout=15.0)

        # Store in app state for access by other components
        app.state.hal_manager = hal_manager

        # Log status
        status = hal_manager.get_status()
        logger.info(
            f"✅ HAL initialized: {status.platform.value} platform, "
            f"{status.adapters_initialized} adapters available, "
            f"mock={status.mock_mode}"
        )

    except (TimeoutError, ImportError, RuntimeError, AttributeError) as e:
        logger.error(f"❌ HAL initialization failed: {e}", exc_info=True)
        # HAL is optional - continue without it
        app.state.hal_manager = None


async def startup_ambient_os(app: FastAPI) -> None:
    """Initialize Ambient OS (Multi-Device Coordinator).

    OPTIMIZED (Dec 28, 2025): Reduced logging, cached hostname.
    """
    from kagami.core.ambient.multi_device_coordinator import (
        DeviceType,
        get_multi_device_coordinator,
    )

    try:
        coordinator = await get_multi_device_coordinator()
        app.state.device_coordinator = coordinator

        import platform
        import socket

        hostname = socket.gethostname()
        system = platform.system().lower()

        device_type = DeviceType.LAPTOP if system == "darwin" else DeviceType.DESKTOP

        coordinator.register_device(
            device_id=hostname,
            name=hostname,
            device_type=device_type,
            capabilities=["core", "api", "web"],
        )
        coordinator.set_active_device(hostname)
        app.state.ambient_os_ready = True

        logger.debug(f"Ambient OS active ({hostname})")

    except (ImportError, RuntimeError, AttributeError) as e:
        logger.debug(f"Ambient OS unavailable: {e}")
        app.state.device_coordinator = None
        app.state.ambient_os_ready = False


async def startup_socketio(app: FastAPI) -> None:
    """Initialize Socket.IO server and mount at /socket.io."""
    try:
        import socketio as _socketio
        from kagami_api.socketio_server import (
            create_socketio_app,
            set_socketio_server,
        )

        sio = create_socketio_app(async_mode="asgi")
        asgi_app = _socketio.ASGIApp(sio, other_asgi_app=app)
        app.mount("/socket.io", asgi_app)
        set_socketio_server(sio)
        app.state.socketio_ready = True
        logger.info("✅ Socket.IO ready at /socket.io")
    except (ImportError, RuntimeError, AttributeError) as e:
        logger.warning(f"⚠️  Socket.IO initialization failed: {e}")


__all__ = [
    "startup_ambient_os",
    "startup_hal",
    "startup_socketio",
]
