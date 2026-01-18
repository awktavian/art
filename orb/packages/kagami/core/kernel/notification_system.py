"""Notification System for K os Kernel.

Provides cross-platform notifications with priority levels:
- Desktop: Native OS notifications (macOS/Windows/Linux)
- Web: WebSocket push to connected clients
- Mobile: Future support for push notifications

Created: November 15, 2025
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)


class NotificationPriority(str, Enum):
    """Notification priority levels."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


@dataclass
class Notification:
    """Notification data."""

    notification_id: str
    title: str
    message: str
    priority: NotificationPriority = NotificationPriority.NORMAL
    created_at: float = field(default_factory=time.time)
    read: bool = False
    dismissed: bool = False
    metadata: dict[str, Any] = field(default_factory=dict[str, Any])


class NotificationSystem:
    """Cross-platform notification system.

    Routes notifications to appropriate channels based on platform and priority.
    """

    def __init__(self) -> None:
        self._notifications: dict[str, Notification] = {}
        self._lock = asyncio.Lock()

        # Cleanup interval
        self._cleanup_interval = 1800  # 30 minutes
        self._last_cleanup = time.time()

        # Desktop notification backend
        self._desktop_backend: Any = None
        self._desktop_available = False

        self._initialize_backend()

    def _initialize_backend(self) -> None:
        """Initialize desktop notification backend."""
        try:
            # Try plyer for cross-platform notifications
            from plyer import notification as plyer_notification

            self._desktop_backend = plyer_notification
            self._desktop_available = True
            logger.info("Desktop notifications available via plyer")

        except ImportError:
            logger.debug("plyer not available, desktop notifications disabled")
            self._desktop_available = False

    async def send(
        self,
        title: str,
        message: str,
        priority: NotificationPriority = NotificationPriority.NORMAL,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Send notification.

        Args:
            title: Notification title
            message: Notification message
            priority: Priority level
            metadata: Optional metadata

        Returns:
            Notification ID
        """
        notification_id = f"notif_{uuid4().hex[:12]}"

        async with self._lock:
            notification = Notification(
                notification_id=notification_id,
                title=title,
                message=message,
                priority=priority,
                metadata=metadata or {},
            )

            self._notifications[notification_id] = notification

            # Route to appropriate channel
            await self._route_notification(notification)

            # Periodic cleanup
            await self._maybe_cleanup()

            return notification_id

    async def _route_notification(self, notification: Notification) -> None:
        """Route notification to appropriate channels.

        Args:
            notification: Notification to route
        """
        # 1. Desktop notification (for urgent/high priority)
        if notification.priority in (NotificationPriority.HIGH, NotificationPriority.URGENT):
            await self._send_desktop(notification)

        # 2. WebSocket broadcast (all notifications)
        await self._send_websocket(notification)

        # 3. Emit receipt
        await self._emit_receipt(notification)

    async def _send_desktop(self, notification: Notification) -> None:
        """Send desktop OS notification.

        Args:
            notification: Notification to send
        """
        if not self._desktop_available or not self._desktop_backend:
            return

        try:
            # Send via plyer (blocking call, run in executor)
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(
                None,
                lambda: self._desktop_backend.notify(
                    title=notification.title,
                    message=notification.message,
                    timeout=10,  # seconds
                ),
            )

            logger.debug(f"Desktop notification sent: {notification.title}")

        except Exception as e:
            logger.debug(f"Desktop notification failed: {e}")

    async def _send_websocket(self, notification: Notification) -> None:
        """Broadcast notification via WebSocket.

        Args:
            notification: Notification to broadcast
        """
        try:
            from kagami.core.di.container import try_resolve
            from kagami.core.interfaces import EventBroadcaster

            broadcaster = try_resolve(EventBroadcaster)
            if broadcaster:
                await broadcaster.broadcast(
                    "notification",
                    {
                        "notification_id": notification.notification_id,
                        "title": notification.title,
                        "message": notification.message,
                        "priority": notification.priority.value,
                        "created_at": notification.created_at,
                    },
                )
                logger.debug(f"WebSocket notification broadcast: {notification.title}")

        except Exception as e:
            logger.debug(f"WebSocket notification failed: {e}")

    async def _emit_receipt(self, notification: Notification) -> None:
        """Emit receipt for notification.

        Args:
            notification: Notification sent
        """
        try:
            from kagami.core.receipts import UnifiedReceiptFacade as URF

            await URF.emit(  # type: ignore[misc]
                correlation_id=notification.notification_id,
                action="notification.send",
                event_name="NOTIFICATION_SENT",
                data={
                    "notification_id": notification.notification_id,
                    "title": notification.title,
                    "priority": notification.priority.value,
                },
            )

        except Exception as e:
            logger.debug(f"Failed to emit notification receipt: {e}")

    async def clear(self, notification_id: str) -> bool:
        """Clear/dismiss notification.

        Args:
            notification_id: Notification ID

        Returns:
            True if cleared, False if not found
        """
        async with self._lock:
            if notification_id not in self._notifications:
                return False

            notification = self._notifications[notification_id]
            notification.dismissed = True

            logger.debug(f"Notification {notification_id} cleared")
            return True

    async def mark_read(self, notification_id: str) -> bool:
        """Mark notification as read.

        Args:
            notification_id: Notification ID

        Returns:
            True if marked, False if not found
        """
        async with self._lock:
            if notification_id not in self._notifications:
                return False

            notification = self._notifications[notification_id]
            notification.read = True

            return True

    async def list_notifications(
        self,
        include_dismissed: bool = False,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """List active notifications.

        Args:
            include_dismissed: Include dismissed notifications
            limit: Maximum notifications to return

        Returns:
            List of notification dicts
        """
        async with self._lock:
            notifications = []

            for notification in self._notifications.values():
                if not include_dismissed and notification.dismissed:
                    continue

                notifications.append(
                    {
                        "notification_id": notification.notification_id,
                        "title": notification.title,
                        "message": notification.message,
                        "priority": notification.priority.value,
                        "created_at": notification.created_at,
                        "read": notification.read,
                        "dismissed": notification.dismissed,
                    }
                )

            # Sort by created_at (newest first)
            notifications.sort(key=lambda x: x["created_at"], reverse=True)

            return notifications[:limit]

    async def _maybe_cleanup(self) -> None:
        """Cleanup old dismissed notifications."""
        now = time.time()

        if now - self._last_cleanup < self._cleanup_interval:
            return

        self._last_cleanup = now

        # Remove dismissed notifications older than 1 hour
        cutoff = now - 3600
        to_remove = []

        for notification_id, notification in self._notifications.items():
            if notification.dismissed and notification.created_at < cutoff:
                to_remove.append(notification_id)

        for notification_id in to_remove:
            del self._notifications[notification_id]

        if to_remove:
            logger.debug(f"Cleaned up {len(to_remove)} old notifications")

    def get_stats(self) -> dict[str, Any]:
        """Get notification statistics.

        Returns:
            Stats dict[str, Any]
        """
        total = len(self._notifications)
        unread = sum(1 for n in self._notifications.values() if not n.read)
        dismissed = sum(1 for n in self._notifications.values() if n.dismissed)

        by_priority: dict[str, Any] = {}
        for notification in self._notifications.values():
            priority = notification.priority.value
            by_priority[priority] = by_priority.get(priority, 0) + 1

        return {
            "total": total,
            "unread": unread,
            "dismissed": dismissed,
            "by_priority": by_priority,
            "desktop_available": self._desktop_available,
        }


# Global singleton
_notification_system: NotificationSystem | None = None


def get_notification_system() -> NotificationSystem:
    """Get global notification system.

    Returns:
        NotificationSystem singleton
    """
    global _notification_system

    if _notification_system is None:
        _notification_system = NotificationSystem()

    return _notification_system


__all__ = [
    "Notification",
    "NotificationPriority",
    "NotificationSystem",
    "get_notification_system",
]
