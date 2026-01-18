"""Screen Reader Announcement Utilities.

Provides utilities for generating accessible announcements for screen readers,
including live region management and announcement queue.

Usage:
    from kagami.core.accessibility.announcements import (
        announce,
        AnnouncementQueue,
        live_region,
    )

    # Simple announcement
    announce("Lights turned on in Living Room")

    # With priority
    announce("Door unlocked!", priority="assertive")

    # Queue management
    queue = AnnouncementQueue()
    queue.add("Action completed")
    queue.add("Warning: Door open", priority="assertive")

Created: January 1, 2026
Part of: Apps 100/100 Transformation - Phase 1.4
"""

from __future__ import annotations

import asyncio
import logging
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class AnnouncementPriority(str, Enum):
    """Priority levels for screen reader announcements.

    Maps to ARIA live region politeness settings.
    """

    POLITE = "polite"  # Wait for idle to announce
    ASSERTIVE = "assertive"  # Interrupt current speech
    OFF = "off"  # Do not announce


@dataclass
class Announcement:
    """A screen reader announcement."""

    message: str
    priority: AnnouncementPriority = AnnouncementPriority.POLITE
    timestamp: datetime = None  # type: ignore[assignment]
    context: str | None = None  # Additional context (e.g., "Living Room")

    def __post_init__(self) -> None:
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()

    @property
    def full_message(self) -> str:
        """Get the full message including context."""
        if self.context:
            return f"{self.context}: {self.message}"
        return self.message

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "message": self.message,
            "priority": self.priority.value,
            "timestamp": self.timestamp.isoformat(),
            "context": self.context,
            "full_message": self.full_message,
        }


class AnnouncementQueue:
    """Queue for managing screen reader announcements.

    Handles announcement debouncing, priority ordering, and delivery.
    """

    def __init__(
        self,
        max_size: int = 50,
        debounce_ms: int = 500,
    ):
        """Initialize announcement queue.

        Args:
            max_size: Maximum queue size
            debounce_ms: Minimum time between announcements
        """
        self._queue: deque[Announcement] = deque(maxlen=max_size)
        self._debounce_ms = debounce_ms
        self._last_announcement: datetime | None = None
        self._handlers: list[Callable[[Announcement], None]] = []
        self._processing = False

    def add(
        self,
        message: str,
        priority: str = "polite",
        context: str | None = None,
    ) -> None:
        """Add an announcement to the queue.

        Args:
            message: Message to announce
            priority: Priority level ("polite", "assertive", "off")
            context: Optional context prefix
        """
        if priority == "off":
            return

        announcement = Announcement(
            message=message,
            priority=AnnouncementPriority(priority),
            context=context,
        )

        # Assertive announcements go to the front
        if announcement.priority == AnnouncementPriority.ASSERTIVE:
            self._queue.appendleft(announcement)
        else:
            self._queue.append(announcement)

        # Trigger processing
        asyncio.create_task(self._process_queue())

    def register_handler(self, handler: Callable[[Announcement], None]) -> None:
        """Register a handler for announcements.

        Args:
            handler: Function that receives Announcement objects
        """
        self._handlers.append(handler)

    async def _process_queue(self) -> None:
        """Process the announcement queue."""
        if self._processing:
            return

        self._processing = True

        try:
            while self._queue:
                # Check debounce
                if self._last_announcement:
                    elapsed = (datetime.utcnow() - self._last_announcement).total_seconds() * 1000
                    if elapsed < self._debounce_ms:
                        await asyncio.sleep((self._debounce_ms - elapsed) / 1000)

                announcement = self._queue.popleft()

                # Deliver to handlers
                for handler in self._handlers:
                    try:
                        handler(announcement)
                    except Exception as e:
                        logger.error(f"Announcement handler error: {e}")

                self._last_announcement = datetime.utcnow()

        finally:
            self._processing = False

    def clear(self) -> None:
        """Clear the announcement queue."""
        self._queue.clear()

    @property
    def pending_count(self) -> int:
        """Get the number of pending announcements."""
        return len(self._queue)


# Global announcement queue
_global_queue = AnnouncementQueue()


def announce(
    message: str,
    priority: str = "polite",
    context: str | None = None,
) -> None:
    """Add an announcement to the global queue.

    This is the primary way to announce messages to screen readers.

    Args:
        message: Message to announce
        priority: "polite" (wait) or "assertive" (interrupt)
        context: Optional context prefix (e.g., room name)

    Example:
        >>> announce("Lights turned on")
        >>> announce("Door unlocked!", priority="assertive")
        >>> announce("Temperature set to 72°", context="Living Room")
    """
    _global_queue.add(message, priority, context)


def get_announcement_queue() -> AnnouncementQueue:
    """Get the global announcement queue.

    Use this to register handlers or configure the queue.

    Returns:
        The global AnnouncementQueue instance
    """
    return _global_queue


# Announcement templates for common actions


def announce_device_change(
    device_name: str,
    action: str,
    room: str | None = None,
) -> None:
    """Announce a device state change.

    Args:
        device_name: Name of the device
        action: What happened (e.g., "turned on", "set to 50%")
        room: Optional room context
    """
    message = f"{device_name} {action}"
    announce(message, context=room)


def announce_scene_activated(scene_name: str) -> None:
    """Announce that a scene was activated.

    Args:
        scene_name: Name of the scene
    """
    announce(f"Scene activated: {scene_name}")


def announce_error(error_message: str) -> None:
    """Announce an error (assertive).

    Args:
        error_message: Error description
    """
    announce(f"Error: {error_message}", priority="assertive")


def announce_safety_alert(alert_message: str) -> None:
    """Announce a safety alert (assertive).

    Args:
        alert_message: Alert description
    """
    announce(f"Safety alert: {alert_message}", priority="assertive")


def announce_navigation(screen_name: str) -> None:
    """Announce navigation to a new screen.

    Args:
        screen_name: Name of the screen navigated to
    """
    announce(f"Now viewing {screen_name}")


def announce_loading(is_loading: bool = True) -> None:
    """Announce loading state.

    Args:
        is_loading: True if starting to load, False if done
    """
    if is_loading:
        announce("Loading")
    else:
        announce("Loading complete")


# Live region helpers (for web/HTML contexts)


def live_region(
    message: str,
    atomic: bool = True,
    relevant: str = "additions text",
    politeness: str = "polite",
) -> dict[str, Any]:
    """Generate ARIA live region attributes.

    Returns attributes that can be applied to an HTML element
    to make it a live region for screen readers.

    Args:
        message: Content for the live region
        atomic: Whether to announce entire region on change
        relevant: What types of changes to announce
        politeness: "polite", "assertive", or "off"

    Returns:
        Dictionary of ARIA attributes

    Example:
        >>> attrs = live_region("Status: Connected")
        >>> # In HTML/JSX: <div {...attrs}>Status: Connected</div>
    """
    return {
        "role": "status",
        "aria-live": politeness,
        "aria-atomic": str(atomic).lower(),
        "aria-relevant": relevant,
        "children": message,
    }


__all__ = [
    "Announcement",
    "AnnouncementPriority",
    "AnnouncementQueue",
    "announce",
    "announce_device_change",
    "announce_error",
    "announce_loading",
    "announce_navigation",
    "announce_safety_alert",
    "announce_scene_activated",
    "get_announcement_queue",
    "live_region",
]
