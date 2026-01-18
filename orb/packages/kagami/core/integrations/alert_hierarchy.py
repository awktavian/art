"""Alert Hierarchy — Priority-Based Notification Routing.

Routes alerts from the unified sensory bus to appropriate outputs:
- CRITICAL: Immediate audio announcement + all rooms
- HIGH: Audio in occupied room if home and awake
- NORMAL: Log to console, queryable
- LOW: Batch and summarize

Integrates with:
- SmartHome audio (Denon + Triad AMS)
- Notification manager
- Console logging

Created: December 29, 2025
Philosophy: Not all signals deserve equal attention.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import IntEnum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from kagami_smarthome import SmartHomeController

logger = logging.getLogger(__name__)


# =============================================================================
# ALERT LEVELS
# =============================================================================


class AlertPriority(IntEnum):
    """Alert priority levels (lower = higher priority)."""

    CRITICAL = 1  # Security, urgent contacts, safety
    HIGH = 2  # Important emails, imminent meetings
    NORMAL = 3  # Standard notifications
    LOW = 4  # Routine updates, batched


class AlertCategory(IntEnum):
    """Categories for alert routing."""

    SECURITY = 1  # Locks, alarms, intrusion
    COMMUNICATION = 2  # Email, messages, calls
    CALENDAR = 3  # Meetings, reminders
    WORK = 4  # GitHub, Linear, tasks
    HOME = 5  # Device status, presence
    HEALTH = 6  # Sleep, activity
    SYSTEM = 7  # Internal alerts


# =============================================================================
# ALERT DATA
# =============================================================================


@dataclass
class Alert:
    """An alert to be routed through the hierarchy."""

    id: str
    title: str
    message: str
    priority: AlertPriority
    category: AlertCategory

    # Routing hints
    source: str = "unknown"
    target_rooms: list[str] = field(default_factory=list)

    # State
    timestamp: float = field(default_factory=time.time)
    delivered: bool = False
    acknowledged: bool = False

    # Additional data
    data: dict[str, Any] = field(default_factory=dict)

    def __lt__(self, other: Alert) -> bool:
        """Sort by priority (lower = higher priority)."""
        return self.priority < other.priority


@dataclass
class AlertConfig:
    """Configuration for alert routing."""

    # Audio settings
    enable_audio: bool = True
    audio_volume: int = 50  # 0-100
    quiet_hours_start: int = 22  # 10 PM
    quiet_hours_end: int = 7  # 7 AM

    # Priority overrides
    critical_override_quiet_hours: bool = True
    high_override_quiet_hours: bool = False

    # Batching for LOW priority
    batch_interval: float = 300.0  # 5 minutes
    batch_max_size: int = 10

    # Key contacts (critical priority for emails from these)
    key_contacts: list[str] = field(default_factory=list)

    # Security-related terms that escalate priority
    security_keywords: list[str] = field(
        default_factory=lambda: [
            "security",
            "urgent",
            "emergency",
            "alarm",
            "intrusion",
            "fire",
            "leak",
            "break-in",
            "911",
        ]
    )


# =============================================================================
# ALERT HIERARCHY
# =============================================================================


class AlertHierarchy:
    """Priority-based alert routing system.

    Routes alerts to appropriate outputs based on:
    - Priority level
    - Current presence state
    - Time of day (quiet hours)
    - User preferences
    - Semantic deduplication (December 30, 2025)
    """

    # Minimum similarity threshold for considering alerts as duplicates
    DEDUP_SIMILARITY_THRESHOLD = 0.85

    def __init__(self, config: AlertConfig | None = None):
        self._config = config or AlertConfig()
        self._smart_home: SmartHomeController | None = None

        # Alert queues by priority
        self._queues: dict[AlertPriority, list[Alert]] = {
            priority: [] for priority in AlertPriority
        }

        # Batch buffer for LOW priority
        self._batch_buffer: list[Alert] = []
        self._last_batch_time: float = time.time()

        # Callbacks for custom handlers
        self._handlers: dict[AlertPriority, list[Callable]] = {
            priority: [] for priority in AlertPriority
        }

        # Statistics
        self._stats = {
            "total_alerts": 0,
            "by_priority": {p.name: 0 for p in AlertPriority},
            "audio_announcements": 0,
            "batched_alerts": 0,
            "suppressed_quiet_hours": 0,
            "suppressed_duplicate": 0,  # NEW: Semantic deduplication
        }

        # Alert history (limited)
        self._history: list[Alert] = []
        self._max_history = 100

        # Embedding cache for deduplication (December 30, 2025)
        self._embedding_service = None
        self._recent_embeddings: list[tuple[float, Any]] = []  # (timestamp, embedding)
        self._dedup_window_seconds = 300  # 5 minute dedup window

        self._initialized = False

    def _ensure_embedding_service(self) -> bool:
        """Lazy-load embedding service for semantic deduplication."""
        if self._embedding_service is not None:
            return True

        try:
            from kagami.core.services.embedding_service import get_embedding_service

            self._embedding_service = get_embedding_service()
            return True
        except ImportError:
            return False

    def _is_semantic_duplicate(self, alert: Alert) -> bool:
        """Check if alert is semantically similar to recent alerts.

        Uses embedding similarity to detect duplicate/similar alerts
        that should be suppressed to avoid notification spam.

        Args:
            alert: Alert to check

        Returns:
            True if alert is a duplicate
        """
        if not self._ensure_embedding_service():
            return False

        try:
            import numpy as np

            # Build alert text for embedding
            alert_text = f"{alert.title}: {alert.message}"

            # Get embedding
            embedding = self._embedding_service.embed_text(alert_text)

            # Clean old embeddings outside window
            now = time.time()
            self._recent_embeddings = [
                (ts, emb)
                for ts, emb in self._recent_embeddings
                if now - ts < self._dedup_window_seconds
            ]

            # Check similarity against recent alerts
            for _ts, recent_emb in self._recent_embeddings:
                similarity = float(np.dot(embedding, recent_emb))
                if similarity > self.DEDUP_SIMILARITY_THRESHOLD:
                    logger.debug(
                        f"Suppressing duplicate alert (similarity={similarity:.2f}): {alert.title}"
                    )
                    return True

            # Store embedding for future comparisons
            self._recent_embeddings.append((now, embedding))

            # Limit cache size
            if len(self._recent_embeddings) > 50:
                self._recent_embeddings = self._recent_embeddings[-50:]

            return False

        except Exception as e:
            logger.debug(f"Semantic deduplication failed: {e}")
            return False

    async def initialize(self, smart_home: SmartHomeController | None = None) -> bool:
        """Initialize with SmartHome connection for audio routing."""
        self._smart_home = smart_home
        self._initialized = True
        logger.info("🔔 AlertHierarchy initialized (with semantic deduplication)")
        return True

    # =========================================================================
    # ALERT SUBMISSION
    # =========================================================================

    async def submit(self, alert: Alert) -> bool:
        """Submit an alert for routing.

        Includes semantic deduplication to prevent notification spam.

        Args:
            alert: The alert to route

        Returns:
            True if alert was delivered
        """
        # Semantic deduplication (December 30, 2025)
        # Skip for CRITICAL alerts - those always go through
        if alert.priority != AlertPriority.CRITICAL and self._is_semantic_duplicate(alert):
            self._stats["suppressed_duplicate"] += 1
            return False

        self._stats["total_alerts"] += 1
        self._stats["by_priority"][alert.priority.name] += 1

        # Add to history
        self._history.append(alert)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history :]

        # Route based on priority
        if alert.priority == AlertPriority.CRITICAL:
            return await self._handle_critical(alert)
        elif alert.priority == AlertPriority.HIGH:
            return await self._handle_high(alert)
        elif alert.priority == AlertPriority.NORMAL:
            return await self._handle_normal(alert)
        else:  # LOW
            return await self._handle_low(alert)

    async def submit_from_sense(
        self,
        title: str,
        message: str,
        source: str,
        category: AlertCategory,
        priority: AlertPriority | None = None,
        data: dict[str, Any] | None = None,
    ) -> Alert:
        """Create and submit an alert from a sensory source.

        Automatically determines priority if not provided.
        """
        import uuid

        # Auto-determine priority if not provided
        if priority is None:
            priority = self._auto_priority(title, message, source, category)

        alert = Alert(
            id=f"alert-{uuid.uuid4().hex[:8]}",
            title=title,
            message=message,
            priority=priority,
            category=category,
            source=source,
            data=data or {},
        )

        await self.submit(alert)
        return alert

    def _auto_priority(
        self,
        title: str,
        message: str,
        source: str,
        category: AlertCategory,
    ) -> AlertPriority:
        """Automatically determine priority based on content."""

        text = f"{title} {message}".lower()

        # Security always high priority
        if category == AlertCategory.SECURITY:
            return AlertPriority.CRITICAL

        # Check for security keywords
        for keyword in self._config.security_keywords:
            if keyword in text:
                return AlertPriority.CRITICAL

        # Check for key contacts
        for contact in self._config.key_contacts:
            if contact.lower() in text:
                return AlertPriority.HIGH

        # Calendar events are high priority if imminent
        if category == AlertCategory.CALENDAR:
            if "5 min" in text or "starting" in text:
                return AlertPriority.HIGH

        # Default by category
        category_defaults = {
            AlertCategory.SECURITY: AlertPriority.CRITICAL,
            AlertCategory.COMMUNICATION: AlertPriority.HIGH,
            AlertCategory.CALENDAR: AlertPriority.HIGH,
            AlertCategory.WORK: AlertPriority.NORMAL,
            AlertCategory.HOME: AlertPriority.NORMAL,
            AlertCategory.HEALTH: AlertPriority.NORMAL,
            AlertCategory.SYSTEM: AlertPriority.LOW,
        }

        return category_defaults.get(category, AlertPriority.NORMAL)

    # =========================================================================
    # PRIORITY HANDLERS
    # =========================================================================

    async def _handle_critical(self, alert: Alert) -> bool:
        """Handle CRITICAL priority alerts.

        - Immediate audio announcement
        - All rooms (or all occupied rooms)
        - Override quiet hours
        - Log to console
        """
        logger.warning(f"🚨 CRITICAL: {alert.title} - {alert.message}")

        # Call custom handlers
        for handler in self._handlers[AlertPriority.CRITICAL]:
            try:
                await handler(alert)
            except Exception as e:
                logger.error(f"Critical handler error: {e}")

        # Audio announcement
        if self._config.enable_audio and self._smart_home:
            try:
                rooms = alert.target_rooms or ["all"]
                await self._smart_home.announce(
                    f"Critical alert: {alert.title}. {alert.message}",
                    rooms=rooms,
                )
                self._stats["audio_announcements"] += 1
                alert.delivered = True
            except Exception as e:
                logger.error(f"Critical audio announcement failed: {e}")

        return alert.delivered

    async def _handle_high(self, alert: Alert) -> bool:
        """Handle HIGH priority alerts.

        - Audio announcement if home and not quiet hours
        - Occupied rooms only
        - Log to console
        """
        logger.info(f"⚠️ HIGH: {alert.title} - {alert.message}")

        # Call custom handlers
        for handler in self._handlers[AlertPriority.HIGH]:
            try:
                await handler(alert)
            except Exception as e:
                logger.error(f"High handler error: {e}")

        # Check quiet hours
        if self._is_quiet_hours() and not self._config.high_override_quiet_hours:
            self._stats["suppressed_quiet_hours"] += 1
            logger.debug(f"High alert suppressed during quiet hours: {alert.title}")
            return False

        # Audio announcement
        if self._config.enable_audio and self._smart_home:
            try:
                # Get occupied rooms or default to Living Room
                rooms = alert.target_rooms or ["Living Room"]
                await self._smart_home.announce(
                    f"{alert.title}. {alert.message}",
                    rooms=rooms,
                )
                self._stats["audio_announcements"] += 1
                alert.delivered = True
            except Exception as e:
                logger.debug(f"High audio announcement failed: {e}")

        return alert.delivered

    async def _handle_normal(self, alert: Alert) -> bool:
        """Handle NORMAL priority alerts.

        - Log to console
        - No audio (unless requested)
        - Available on query
        """
        logger.info(f"ℹ️ NORMAL: {alert.title} - {alert.message}")

        # Call custom handlers
        for handler in self._handlers[AlertPriority.NORMAL]:
            try:
                await handler(alert)
            except Exception as e:
                logger.error(f"Normal handler error: {e}")

        # Add to queue for later retrieval
        self._queues[AlertPriority.NORMAL].append(alert)
        alert.delivered = True

        return True

    async def _handle_low(self, alert: Alert) -> bool:
        """Handle LOW priority alerts.

        - Batch for summary
        - No immediate notification
        - Summarized periodically
        """
        logger.debug(f"📝 LOW: {alert.title}")

        # Add to batch buffer
        self._batch_buffer.append(alert)
        self._stats["batched_alerts"] += 1

        # Check if batch should be flushed
        if (
            len(self._batch_buffer) >= self._config.batch_max_size
            or (time.time() - self._last_batch_time) > self._config.batch_interval
        ):
            await self._flush_batch()

        alert.delivered = True
        return True

    async def _flush_batch(self) -> None:
        """Flush batched LOW priority alerts."""
        if not self._batch_buffer:
            return

        # Create summary
        count = len(self._batch_buffer)
        sources = {a.source for a in self._batch_buffer}

        summary = f"{count} updates from {', '.join(sources)}"
        logger.info(f"📋 Batch summary: {summary}")

        # Call custom handlers
        for handler in self._handlers[AlertPriority.LOW]:
            try:
                await handler(self._batch_buffer.copy())
            except Exception as e:
                logger.error(f"Low batch handler error: {e}")

        # Clear batch
        self._batch_buffer.clear()
        self._last_batch_time = time.time()

    # =========================================================================
    # UTILITY
    # =========================================================================

    def _is_quiet_hours(self) -> bool:
        """Check if currently in quiet hours."""
        current_hour = datetime.now().hour

        start = self._config.quiet_hours_start
        end = self._config.quiet_hours_end

        # Handle overnight quiet hours (e.g., 22:00 - 07:00)
        if start > end:
            return current_hour >= start or current_hour < end
        else:
            return start <= current_hour < end

    def register_handler(
        self,
        priority: AlertPriority,
        handler: Callable,
    ) -> None:
        """Register a custom handler for a priority level."""
        self._handlers[priority].append(handler)

    def get_pending(self, priority: AlertPriority | None = None) -> list[Alert]:
        """Get pending alerts, optionally filtered by priority."""
        if priority:
            return self._queues[priority].copy()

        all_alerts = []
        for queue in self._queues.values():
            all_alerts.extend(queue)
        return sorted(all_alerts)

    def get_history(self, limit: int = 20) -> list[Alert]:
        """Get recent alert history."""
        return self._history[-limit:]

    def get_stats(self) -> dict[str, Any]:
        """Get alert statistics."""
        return {
            **self._stats,
            "pending_count": sum(len(q) for q in self._queues.values()),
            "batch_buffer_size": len(self._batch_buffer),
            "quiet_hours": self._is_quiet_hours(),
        }

    def clear_pending(self, priority: AlertPriority | None = None) -> int:
        """Clear pending alerts."""
        if priority:
            count = len(self._queues[priority])
            self._queues[priority].clear()
            return count

        count = sum(len(q) for q in self._queues.values())
        for queue in self._queues.values():
            queue.clear()
        return count


# =============================================================================
# SINGLETON
# =============================================================================


_alert_hierarchy: AlertHierarchy | None = None


def get_alert_hierarchy() -> AlertHierarchy:
    """Get global AlertHierarchy instance."""
    global _alert_hierarchy
    if _alert_hierarchy is None:
        _alert_hierarchy = AlertHierarchy()
    return _alert_hierarchy


async def initialize_alert_hierarchy(
    smart_home: SmartHomeController | None = None,
    config: AlertConfig | None = None,
) -> AlertHierarchy:
    """Initialize the alert hierarchy with optional SmartHome connection."""
    global _alert_hierarchy

    if config:
        _alert_hierarchy = AlertHierarchy(config)
    else:
        _alert_hierarchy = get_alert_hierarchy()

    await _alert_hierarchy.initialize(smart_home)
    return _alert_hierarchy


__all__ = [
    "Alert",
    "AlertCategory",
    "AlertConfig",
    "AlertHierarchy",
    "AlertPriority",
    "get_alert_hierarchy",
    "initialize_alert_hierarchy",
]
