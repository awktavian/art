"""Notification Manager for K os Ambient OS.

Manages notifications across devices with:
- Priority-based delivery
- Cross-device synchronization
- Delivery policies (immediate, scheduled, quiet hours)
- Notification history

Created: November 10, 2025
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime
from datetime import time as dt_time
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class NotificationPriority(Enum):
    """Notification priority levels."""

    CRITICAL = "critical"  # Always deliver immediately
    HIGH = "high"  # Deliver unless quiet hours
    NORMAL = "normal"  # Standard delivery
    LOW = "low"  # Best-effort, can defer


@dataclass
class Notification:
    """Notification data."""

    id: str
    title: str
    body: str
    priority: NotificationPriority
    category: str | None = None
    actions: list[dict[str, str]] = field(default_factory=list[Any])
    data: dict[str, Any] = field(default_factory=dict[str, Any])
    timestamp: float = field(default_factory=time.time)
    delivered: bool = False
    read: bool = False
    dismissed: bool = False


@dataclass
class DeliveryPolicy:
    """Notification delivery policy."""

    quiet_hours_start: dt_time | None = None
    quiet_hours_end: dt_time | None = None
    priority_override: bool = True  # High/Critical override quiet hours
    device_preference: list[str] = field(default_factory=list[Any])  # Device IDs


class NotificationManager:
    """Manages notifications across devices."""

    def __init__(self) -> None:
        # Notification queue
        self.queue: deque[Notification] = deque(maxlen=1000)

        # Notification history
        self.history: list[Notification] = []

        # Delivery policy
        self.policy = DeliveryPolicy()

        # Delivery callbacks
        self.delivery_callbacks: dict[NotificationPriority, list[Callable]] = {
            priority: [] for priority in NotificationPriority
        }

        # Statistics
        self.stats = {
            "sent": 0,
            "delivered": 0,
            "read": 0,
            "dismissed": 0,
        }

        # Background task
        self._running = False
        self._delivery_task: asyncio.Task | None = None

    async def send(
        self,
        title: str,
        body: str,
        priority: NotificationPriority = NotificationPriority.NORMAL,
        **kwargs: Any,
    ) -> Notification:
        """Send notification.

        Args:
            title: Notification title
            body: Notification body
            priority: Priority level
            **kwargs: Additional notification fields

        Returns:
            Notification object
        """
        import uuid

        notification = Notification(
            id=str(uuid.uuid4()), title=title, body=body, priority=priority, **kwargs
        )

        # Add to queue
        self.queue.append(notification)
        self.stats["sent"] += 1

        logger.info(f"📬 Notification: {title} (priority={priority.value})")

        # Deliver immediately if critical
        if priority == NotificationPriority.CRITICAL:
            await self._deliver(notification)

        return notification

    async def _deliver(self, notification: Notification) -> bool:
        """Deliver notification.

        Args:
            notification: Notification to deliver

        Returns:
            True if delivered
        """
        # Check delivery policy
        if not await self._should_deliver(notification):
            logger.debug(f"Notification deferred: {notification.id}")
            return False

        # Call delivery callbacks
        callbacks = self.delivery_callbacks.get(notification.priority, [])
        for callback in callbacks:
            try:
                await callback(notification)
            except Exception as e:
                logger.error(f"Delivery callback failed: {e}")

        # Mark as delivered
        notification.delivered = True
        self.stats["delivered"] += 1
        self.history.append(notification)

        logger.debug(f"Notification delivered: {notification.id}")

        return True

    async def _should_deliver(self, notification: Notification) -> bool:
        """Check if notification should be delivered now.

        Args:
            notification: Notification to check

        Returns:
            True if should deliver
        """
        # Critical always delivers
        if notification.priority == NotificationPriority.CRITICAL:
            return True

        # Check quiet hours
        if self.policy.quiet_hours_start and self.policy.quiet_hours_end:
            now = datetime.now().time()
            in_quiet_hours = self.policy.quiet_hours_start <= now <= self.policy.quiet_hours_end

            if in_quiet_hours:
                # High priority overrides quiet hours if enabled
                if notification.priority == NotificationPriority.HIGH:
                    return self.policy.priority_override
                return False

        return True

    async def mark_read(self, notification_id: str) -> None:
        """Mark notification as read.

        Args:
            notification_id: Notification ID
        """
        for notif in self.history:
            if notif.id == notification_id and not notif.read:
                notif.read = True
                self.stats["read"] += 1
                break

    async def mark_dismissed(self, notification_id: str) -> None:
        """Mark notification as dismissed.

        Args:
            notification_id: Notification ID
        """
        for notif in self.history:
            if notif.id == notification_id and not notif.dismissed:
                notif.dismissed = True
                self.stats["dismissed"] += 1
                break

    def subscribe_delivery(
        self, priority: NotificationPriority, callback: Callable[[Notification], Awaitable[None]]
    ) -> None:
        """Subscribe to notification delivery.

        Args:
            priority: Priority to subscribe to
            callback: Async callback for notifications
        """
        self.delivery_callbacks[priority].append(callback)

    async def _delivery_loop(self) -> None:
        """Background delivery loop."""
        logger.info("📬 Notification manager started")

        while self._running:
            try:
                # Process queue every second
                await asyncio.sleep(1)

                # Deliver pending notifications
                while self.queue:
                    notification = self.queue.popleft()
                    if not notification.delivered:
                        await self._deliver(notification)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Delivery loop error: {e}", exc_info=True)

        logger.info("📬 Notification manager stopped")

    async def start(self) -> None:
        """Start notification manager."""
        if self._running:
            return

        self._running = True

        from kagami.core.async_utils import safe_create_task

        self._delivery_task = safe_create_task(
            self._delivery_loop(),
            name="notification_delivery",
            error_callback=lambda e: logger.error(f"Notification manager crashed: {e}"),
        )

    async def stop(self) -> None:
        """Stop notification manager."""
        self._running = False
        if self._delivery_task:
            self._delivery_task.cancel()

    def get_stats(self) -> dict[str, Any]:
        """Get notification statistics."""
        return {
            **self.stats,
            "pending": len(self.queue),
            "history": len(self.history),
        }


# Global notification manager
_NOTIFICATION_MANAGER: NotificationManager | None = None


async def get_notification_manager() -> NotificationManager:
    """Get global notification manager."""
    global _NOTIFICATION_MANAGER
    if _NOTIFICATION_MANAGER is None:
        _NOTIFICATION_MANAGER = NotificationManager()
        await _NOTIFICATION_MANAGER.start()
    return _NOTIFICATION_MANAGER
