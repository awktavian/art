"""systemd sd_notify integration for Type=notify services.

Provides sd_notify functionality for the Kagami API to integrate with systemd.

Functionality:
- READY=1: Signal service is ready to accept connections
- WATCHDOG=1: Periodic watchdog pings (if WatchdogSec configured)
- STATUS=...: Human-readable status updates
- STOPPING=1: Signal graceful shutdown in progress

Usage:
    systemd service file:
        [Service]
        Type=notify
        WatchdogSec=30

    Python:
        from kagami_api.systemd_notify import notify_ready, start_watchdog_task

        notify_ready()  # Signal READY=1
        task = start_watchdog_task()  # Start watchdog ping loop

Created: January 4, 2026
Colony: Forge (A₃) — Infrastructure
h(x) ≥ 0. Always.
"""

from __future__ import annotations

import asyncio
import logging
import os
import socket
from typing import Any

logger = logging.getLogger(__name__)


def _get_notify_socket() -> socket.socket | None:
    """Get the sd_notify socket if available.

    Returns:
        Unix socket for sd_notify, or None if not running under systemd.
    """
    notify_socket = os.environ.get("NOTIFY_SOCKET")
    if not notify_socket:
        return None

    # Handle abstract sockets (prefixed with @)
    if notify_socket.startswith("@"):
        notify_socket = "\x00" + notify_socket[1:]

    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        sock.connect(notify_socket)
        return sock
    except Exception as e:
        logger.debug(f"sd_notify socket unavailable: {e}")
        return None


def _notify(message: str) -> bool:
    """Send a notification to systemd.

    Args:
        message: sd_notify message (e.g., "READY=1", "WATCHDOG=1")

    Returns:
        True if notification was sent, False otherwise.
    """
    sock = _get_notify_socket()
    if sock is None:
        return False

    try:
        sock.sendall(message.encode("utf-8"))
        sock.close()
        return True
    except Exception as e:
        logger.debug(f"sd_notify send failed: {e}")
        return False


def notify_ready() -> bool:
    """Notify systemd that the service is ready.

    Sends READY=1 to signal that the service has completed startup
    and is ready to accept connections.

    Returns:
        True if notification was sent, False if not running under systemd.

    Example:
        >>> notify_ready()
        True
    """
    result = _notify("READY=1")
    if result:
        logger.info("systemd: READY=1 sent")
    return result


def notify_stopping() -> bool:
    """Notify systemd that the service is stopping.

    Sends STOPPING=1 to signal graceful shutdown in progress.

    Returns:
        True if notification was sent.
    """
    result = _notify("STOPPING=1")
    if result:
        logger.info("systemd: STOPPING=1 sent")
    return result


def notify_watchdog() -> bool:
    """Send watchdog ping to systemd.

    Sends WATCHDOG=1 to reset the watchdog timer.
    Must be called periodically if WatchdogSec is configured.

    Returns:
        True if notification was sent.
    """
    return _notify("WATCHDOG=1")


def notify_status(status: str) -> bool:
    """Update human-readable status in systemd.

    Args:
        status: Human-readable status string.

    Returns:
        True if notification was sent.
    """
    return _notify(f"STATUS={status}")


def get_watchdog_interval() -> float | None:
    """Get the configured watchdog interval in seconds.

    Reads WATCHDOG_USEC from environment and converts to seconds.
    Recommended to ping at half the interval.

    Returns:
        Watchdog interval in seconds, or None if not configured.
    """
    watchdog_usec = os.environ.get("WATCHDOG_USEC")
    if not watchdog_usec:
        return None

    try:
        usec = int(watchdog_usec)
        # Ping at half the interval for safety
        return usec / 1_000_000 / 2
    except ValueError:
        return None


def start_watchdog_task() -> asyncio.Task[Any] | None:
    """Start a background task to ping the watchdog.

    Reads WATCHDOG_USEC to determine ping interval.
    Pings at half the configured interval.

    Returns:
        The background task, or None if watchdog not configured.

    Example:
        >>> task = start_watchdog_task()
        >>> if task:
        ...     # Watchdog is active
        ...     pass
    """
    interval = get_watchdog_interval()
    if interval is None:
        return None

    async def _watchdog_loop() -> None:
        """Background task to ping systemd watchdog."""
        logger.debug(f"Watchdog ping task started (interval={interval:.1f}s)")
        while True:
            try:
                notify_watchdog()
            except Exception as e:
                logger.debug(f"Watchdog ping failed: {e}")
            await asyncio.sleep(interval)

    task = asyncio.create_task(_watchdog_loop())
    return task


def stop_watchdog_task(task: asyncio.Task[Any] | None) -> None:
    """Stop the watchdog background task.

    Args:
        task: The task returned by start_watchdog_task().
    """
    if task and not task.done():
        task.cancel()


# Export for __all__
__all__ = [
    "get_watchdog_interval",
    "notify_ready",
    "notify_status",
    "notify_stopping",
    "notify_watchdog",
    "start_watchdog_task",
    "stop_watchdog_task",
]
