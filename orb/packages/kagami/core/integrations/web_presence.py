"""Web-Based Presence Detection — Browser heartbeats for presence tracking.

Extends presence detection beyond WiFi/mDNS to include browser-based heartbeats.
Web clients (desktop, mobile browsers, PWAs) send periodic heartbeats to indicate
presence, providing presence awareness even when user is away from home network.

Architecture:
```
┌─────────────────────────────────────────────────────────────────────────┐
│                        WEB PRESENCE DETECTION                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  Browser/PWA ──────────────────────────┐                                │
│  Desktop Client ───────────────────────┤                                │
│  Mobile App ───────────────────────────┤                                │
│                                        │                                │
│                                        ▼                                │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │                    WebPresenceService                             │  │
│  │                                                                   │  │
│  │  • Heartbeat ingestion (HTTP POST)                               │  │
│  │  • Client session tracking                                       │  │
│  │  • Visibility state handling (tab active/hidden)                 │  │
│  │  • Geohash-based coarse location                                 │  │
│  │  • Activity inference (typing, scrolling, idle)                  │  │
│  │                                                                   │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│                          │                                              │
│                          ▼                                              │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │               PresenceService (unified)                          │  │
│  │     Combines: WiFi + mDNS + WebPresence + Device Location        │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

Usage:
    from kagami.core.integrations.web_presence import (
        get_web_presence_service,
        WebPresenceHeartbeat,
    )

    service = get_web_presence_service()

    # Process incoming heartbeat
    await service.process_heartbeat(WebPresenceHeartbeat(
        client_id="desktop-abc123",
        user_id="tim",
        visibility_state="visible",
        ...
    ))

    # Check web presence
    is_active = service.is_user_active("tim")

Created: January 4, 2026
Colony: Nexus (e₄) — Connection and presence
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

logger = logging.getLogger(__name__)


# =============================================================================
# CONSTANTS
# =============================================================================


# Heartbeat timing
DEFAULT_HEARTBEAT_INTERVAL = 30.0  # Expected heartbeat interval (seconds)
STALE_THRESHOLD_MULTIPLIER = 3.0  # Session stale after N * interval
IDLE_TIMEOUT = 300.0  # 5 minutes of no activity = idle


# =============================================================================
# DATA TYPES
# =============================================================================


class VisibilityState(str, Enum):
    """Browser/app visibility states."""

    VISIBLE = "visible"  # Tab/app is in foreground
    HIDDEN = "hidden"  # Tab/app is in background
    PRERENDER = "prerender"  # Page is being prerendered
    UNKNOWN = "unknown"


class ActivityType(str, Enum):
    """User activity types inferred from web events."""

    ACTIVE = "active"  # Recent mouse/keyboard activity
    TYPING = "typing"  # Currently typing
    SCROLLING = "scrolling"  # Currently scrolling
    IDLE = "idle"  # No recent activity
    AWAY = "away"  # Extended inactivity


class PresenceConfidence(str, Enum):
    """Confidence level for web-based presence."""

    HIGH = "high"  # Active with visible tab
    MEDIUM = "medium"  # Hidden tab or idle
    LOW = "low"  # Stale heartbeat
    NONE = "none"  # No recent data


@dataclass
class WebPresenceHeartbeat:
    """Heartbeat message from web client.

    Attributes:
        client_id: Unique client/device identifier
        user_id: User identifier (e.g., "tim", "jill")
        browser_info: User agent or browser identifier
        page_url: Current page URL (sanitized)
        visibility_state: Browser visibility state
        timestamp: Client-side timestamp (Unix seconds)
        activity_type: Inferred activity type
        last_input_ms: Milliseconds since last user input
        geo_hash: Optional geohash for coarse location
        metadata: Additional client-specific data
    """

    client_id: str
    user_id: str
    browser_info: str = ""
    page_url: str = ""
    visibility_state: str = "visible"
    timestamp: float = field(default_factory=time.time)
    activity_type: str = "active"
    last_input_ms: int = 0
    geo_hash: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "client_id": self.client_id,
            "user_id": self.user_id,
            "browser_info": self.browser_info,
            "page_url": self.page_url,
            "visibility_state": self.visibility_state,
            "timestamp": self.timestamp,
            "activity_type": self.activity_type,
            "last_input_ms": self.last_input_ms,
            "geo_hash": self.geo_hash,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WebPresenceHeartbeat:
        """Deserialize from dictionary."""
        return cls(
            client_id=data["client_id"],
            user_id=data["user_id"],
            browser_info=data.get("browser_info", ""),
            page_url=data.get("page_url", ""),
            visibility_state=data.get("visibility_state", "visible"),
            timestamp=data.get("timestamp", time.time()),
            activity_type=data.get("activity_type", "active"),
            last_input_ms=data.get("last_input_ms", 0),
            geo_hash=data.get("geo_hash"),
            metadata=data.get("metadata", {}),
        )


@dataclass
class WebPresenceSession:
    """Active web presence session for a client.

    Tracks the state of a single web client connection.
    """

    client_id: str
    user_id: str
    browser_info: str
    visibility_state: VisibilityState
    activity_type: ActivityType
    last_heartbeat: float
    session_start: float
    heartbeat_count: int = 0
    geo_hash: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_active(self) -> bool:
        """Check if session is actively present."""
        if self.is_stale:
            return False
        return self.visibility_state == VisibilityState.VISIBLE and self.activity_type in (
            ActivityType.ACTIVE,
            ActivityType.TYPING,
            ActivityType.SCROLLING,
        )

    @property
    def is_stale(self) -> bool:
        """Check if session heartbeat is stale."""
        threshold = DEFAULT_HEARTBEAT_INTERVAL * STALE_THRESHOLD_MULTIPLIER
        return time.time() - self.last_heartbeat > threshold

    @property
    def confidence(self) -> PresenceConfidence:
        """Get presence confidence level."""
        if self.is_stale:
            return PresenceConfidence.LOW
        if self.visibility_state == VisibilityState.VISIBLE:
            if self.activity_type in (ActivityType.ACTIVE, ActivityType.TYPING):
                return PresenceConfidence.HIGH
            return PresenceConfidence.MEDIUM
        return PresenceConfidence.LOW

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "client_id": self.client_id,
            "user_id": self.user_id,
            "browser_info": self.browser_info,
            "visibility_state": self.visibility_state.value,
            "activity_type": self.activity_type.value,
            "last_heartbeat": self.last_heartbeat,
            "session_start": self.session_start,
            "heartbeat_count": self.heartbeat_count,
            "geo_hash": self.geo_hash,
            "is_active": self.is_active,
            "is_stale": self.is_stale,
            "confidence": self.confidence.value,
        }


@dataclass
class UserWebPresence:
    """Aggregated web presence for a user across all clients."""

    user_id: str
    sessions: dict[str, WebPresenceSession] = field(default_factory=dict)
    last_activity: float = field(default_factory=time.time)

    @property
    def active_session_count(self) -> int:
        """Count of active (non-stale, visible) sessions."""
        return sum(1 for s in self.sessions.values() if s.is_active)

    @property
    def is_present(self) -> bool:
        """Check if user has any active web presence."""
        return self.active_session_count > 0

    @property
    def confidence(self) -> PresenceConfidence:
        """Get aggregated presence confidence."""
        if not self.sessions:
            return PresenceConfidence.NONE

        # Return highest confidence from any session
        confidences = [s.confidence for s in self.sessions.values()]
        if PresenceConfidence.HIGH in confidences:
            return PresenceConfidence.HIGH
        if PresenceConfidence.MEDIUM in confidences:
            return PresenceConfidence.MEDIUM
        if PresenceConfidence.LOW in confidences:
            return PresenceConfidence.LOW
        return PresenceConfidence.NONE

    @property
    def primary_geo_hash(self) -> str | None:
        """Get most recent geohash from active sessions."""
        active = [s for s in self.sessions.values() if s.is_active and s.geo_hash]
        if active:
            # Return from most recently active session
            active.sort(key=lambda s: s.last_heartbeat, reverse=True)
            return active[0].geo_hash
        return None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "user_id": self.user_id,
            "is_present": self.is_present,
            "active_session_count": self.active_session_count,
            "total_session_count": len(self.sessions),
            "confidence": self.confidence.value,
            "last_activity": self.last_activity,
            "primary_geo_hash": self.primary_geo_hash,
            "sessions": {k: v.to_dict() for k, v in self.sessions.items()},
        }


# =============================================================================
# WEB PRESENCE SERVICE
# =============================================================================


# Event callback type
WebPresenceCallback = Callable[[str, UserWebPresence], Awaitable[None]]


class WebPresenceService:
    """Service for tracking web-based presence.

    Manages heartbeats from web clients (browsers, desktop apps, PWAs)
    and aggregates presence information per user.

    Thread Safety:
    - All public methods are async-safe
    - Internal state protected by lock

    Integration:
    - Emits events on presence changes
    - Integrates with PresenceService for unified presence
    """

    def __init__(
        self,
        heartbeat_interval: float = DEFAULT_HEARTBEAT_INTERVAL,
        stale_cleanup_interval: float = 60.0,
    ):
        """Initialize web presence service.

        Args:
            heartbeat_interval: Expected heartbeat interval from clients
            stale_cleanup_interval: How often to clean up stale sessions
        """
        self._heartbeat_interval = heartbeat_interval
        self._stale_cleanup_interval = stale_cleanup_interval

        # User presence state
        self._users: dict[str, UserWebPresence] = {}
        self._lock = asyncio.Lock()

        # Event callbacks
        self._callbacks: list[WebPresenceCallback] = []

        # Background tasks
        self._cleanup_task: asyncio.Task | None = None
        self._started = False
        self._shutdown = False

        # Stats
        self._stats = {
            "heartbeats_received": 0,
            "sessions_created": 0,
            "sessions_expired": 0,
            "presence_changes": 0,
        }

        logger.info(f"WebPresenceService initialized (heartbeat={heartbeat_interval}s)")

    # =========================================================================
    # LIFECYCLE
    # =========================================================================

    async def start(self) -> None:
        """Start the web presence service."""
        if self._started:
            return

        self._started = True
        self._shutdown = False

        # Start cleanup task
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())

        logger.info("✅ WebPresenceService started")

    async def stop(self) -> None:
        """Stop the web presence service."""
        self._shutdown = True

        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        self._started = False
        logger.info("✅ WebPresenceService stopped")

    # =========================================================================
    # HEARTBEAT PROCESSING
    # =========================================================================

    async def process_heartbeat(self, heartbeat: WebPresenceHeartbeat) -> WebPresenceSession:
        """Process an incoming heartbeat from a web client.

        Args:
            heartbeat: Heartbeat data from client

        Returns:
            Updated WebPresenceSession

        Example:
            session = await service.process_heartbeat(WebPresenceHeartbeat(
                client_id="browser-xyz",
                user_id="tim",
                visibility_state="visible",
            ))
        """
        async with self._lock:
            self._stats["heartbeats_received"] += 1

            # Get or create user presence
            if heartbeat.user_id not in self._users:
                self._users[heartbeat.user_id] = UserWebPresence(user_id=heartbeat.user_id)

            user = self._users[heartbeat.user_id]
            now = time.time()

            # Parse enums
            try:
                visibility = VisibilityState(heartbeat.visibility_state)
            except ValueError:
                visibility = VisibilityState.UNKNOWN

            try:
                activity = ActivityType(heartbeat.activity_type)
            except ValueError:
                activity = ActivityType.ACTIVE

            # Determine activity from last_input_ms if not specified
            if activity == ActivityType.ACTIVE and heartbeat.last_input_ms > 0:
                if heartbeat.last_input_ms > IDLE_TIMEOUT * 1000:
                    activity = ActivityType.AWAY
                elif heartbeat.last_input_ms > 60000:  # 1 minute
                    activity = ActivityType.IDLE

            # Check if this is a new session
            is_new_session = heartbeat.client_id not in user.sessions

            # Update or create session
            if is_new_session:
                session = WebPresenceSession(
                    client_id=heartbeat.client_id,
                    user_id=heartbeat.user_id,
                    browser_info=heartbeat.browser_info,
                    visibility_state=visibility,
                    activity_type=activity,
                    last_heartbeat=now,
                    session_start=now,
                    heartbeat_count=1,
                    geo_hash=heartbeat.geo_hash,
                    metadata=heartbeat.metadata,
                )
                user.sessions[heartbeat.client_id] = session
                self._stats["sessions_created"] += 1
                logger.info(f"New web session: {heartbeat.user_id}/{heartbeat.client_id}")
            else:
                session = user.sessions[heartbeat.client_id]
                old_active = session.is_active

                session.visibility_state = visibility
                session.activity_type = activity
                session.last_heartbeat = now
                session.heartbeat_count += 1
                session.geo_hash = heartbeat.geo_hash or session.geo_hash
                session.metadata.update(heartbeat.metadata)

                # Check for presence change
                if old_active != session.is_active:
                    self._stats["presence_changes"] += 1

            # Update user last activity
            user.last_activity = now

            # Emit event
            await self._emit_presence_update(heartbeat.user_id, user)

            return session

    async def end_session(self, user_id: str, client_id: str) -> None:
        """End a web presence session.

        Args:
            user_id: User identifier
            client_id: Client identifier
        """
        async with self._lock:
            if user_id in self._users:
                user = self._users[user_id]
                if client_id in user.sessions:
                    del user.sessions[client_id]
                    logger.info(f"Web session ended: {user_id}/{client_id}")
                    await self._emit_presence_update(user_id, user)

    # =========================================================================
    # QUERIES
    # =========================================================================

    def is_user_present(self, user_id: str) -> bool:
        """Check if user has active web presence.

        Args:
            user_id: User identifier

        Returns:
            True if user has any active web sessions
        """
        if user_id not in self._users:
            return False
        return self._users[user_id].is_present

    def is_user_active(self, user_id: str) -> bool:
        """Check if user is actively using a web client.

        More strict than is_user_present - requires visible tab with activity.

        Args:
            user_id: User identifier

        Returns:
            True if user has active, visible session
        """
        if user_id not in self._users:
            return False

        user = self._users[user_id]
        return any(
            s.visibility_state == VisibilityState.VISIBLE
            and s.activity_type in (ActivityType.ACTIVE, ActivityType.TYPING)
            for s in user.sessions.values()
            if not s.is_stale
        )

    def get_user_presence(self, user_id: str) -> UserWebPresence | None:
        """Get aggregated web presence for a user.

        Args:
            user_id: User identifier

        Returns:
            UserWebPresence or None if no data
        """
        return self._users.get(user_id)

    def get_all_users(self) -> dict[str, UserWebPresence]:
        """Get web presence for all users.

        Returns:
            Dictionary of user_id -> UserWebPresence
        """
        return self._users.copy()

    def get_presence_confidence(self, user_id: str) -> PresenceConfidence:
        """Get presence confidence level for a user.

        Args:
            user_id: User identifier

        Returns:
            PresenceConfidence level
        """
        if user_id not in self._users:
            return PresenceConfidence.NONE
        return self._users[user_id].confidence

    def get_user_location_hint(self, user_id: str) -> str | None:
        """Get geohash location hint for a user.

        Args:
            user_id: User identifier

        Returns:
            Geohash string or None
        """
        if user_id not in self._users:
            return None
        return self._users[user_id].primary_geo_hash

    # =========================================================================
    # EVENTS
    # =========================================================================

    def on_presence_change(self, callback: WebPresenceCallback) -> None:
        """Register callback for presence changes.

        Args:
            callback: Async function called with (user_id, UserWebPresence)
        """
        self._callbacks.append(callback)

    async def _emit_presence_update(self, user_id: str, presence: UserWebPresence) -> None:
        """Emit presence update to all callbacks."""
        for callback in self._callbacks:
            try:
                await callback(user_id, presence)
            except Exception as e:
                logger.error(f"Presence callback error: {e}")

    # =========================================================================
    # BACKGROUND TASKS
    # =========================================================================

    async def _cleanup_loop(self) -> None:
        """Background task to clean up stale sessions."""
        while not self._shutdown:
            try:
                await self._cleanup_stale_sessions()
                await asyncio.sleep(self._stale_cleanup_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cleanup error: {e}")
                await asyncio.sleep(30)

    async def _cleanup_stale_sessions(self) -> None:
        """Remove stale sessions from all users."""
        async with self._lock:
            for user_id, user in list(self._users.items()):
                stale = [
                    client_id for client_id, session in user.sessions.items() if session.is_stale
                ]

                for client_id in stale:
                    del user.sessions[client_id]
                    self._stats["sessions_expired"] += 1
                    logger.debug(f"Expired stale session: {user_id}/{client_id}")

                if stale:
                    await self._emit_presence_update(user_id, user)

                # Remove user if no sessions left
                if not user.sessions:
                    del self._users[user_id]

    # =========================================================================
    # STATISTICS
    # =========================================================================

    def get_stats(self) -> dict[str, Any]:
        """Get service statistics.

        Returns:
            Dictionary with service statistics
        """
        return {
            "started": self._started,
            "users": len(self._users),
            "total_sessions": sum(len(u.sessions) for u in self._users.values()),
            "active_sessions": sum(u.active_session_count for u in self._users.values()),
            **self._stats,
        }


# =============================================================================
# FACTORY
# =============================================================================


_web_presence_service: WebPresenceService | None = None
_service_lock = asyncio.Lock()


async def get_web_presence_service() -> WebPresenceService:
    """Get or create the global web presence service.

    Returns:
        WebPresenceService singleton instance
    """
    global _web_presence_service

    async with _service_lock:
        if _web_presence_service is None:
            _web_presence_service = WebPresenceService()
            await _web_presence_service.start()

    return _web_presence_service


def get_web_presence_service_sync() -> WebPresenceService | None:
    """Get the web presence service synchronously (may be None).

    Returns:
        WebPresenceService or None if not initialized
    """
    return _web_presence_service


# =============================================================================
# 鏡
# η → s → μ → a → η′
# h(x) ≥ 0. Always.
# =============================================================================
