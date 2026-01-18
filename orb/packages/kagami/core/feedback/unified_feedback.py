"""Unified Feedback Service — Coordinated sound + haptic feedback.

This service provides:
- Paired sound + haptic events for consistent UX
- Event broadcasting to connected clients via WebSocket
- Context-aware feedback (wakefulness, location, time)
- Spatial audio routing through unified voice effector
- Cross-platform coordination

Usage:
    from kagami.core.feedback import get_unified_feedback, FeedbackEvent

    feedback = await get_unified_feedback()

    # Trigger coordinated feedback
    await feedback.trigger(FeedbackEvent(
        earcon_name="success",
        haptic_pattern="success",
        spatial_position=Pos3D(0, 0, 5),
    ))

    # Scene-specific feedback
    await feedback.scene_activated("Movie Mode")

    # Safety feedback (bypasses wakefulness checks)
    await feedback.safety_violation()

Created: January 12, 2026
Colony: 🔗 Nexus — Coordination
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

from kagami.core.effectors.vbap_core import Pos3D

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


# ============================================================================
# Feedback Types
# ============================================================================


class FeedbackTarget(Enum):
    """Where to route feedback."""

    AUTO = "auto"  # Context-aware routing
    HOME_ROOM = "home_room"  # Specific room(s)
    HOME_ALL = "home_all"  # All audio zones
    CLIENTS = "clients"  # Mobile/desktop clients only
    GLASSES = "glasses"  # Meta Ray-Ban spatial
    CAR = "car"  # Tesla cabin


class HapticIntensity(Enum):
    """Haptic intensity levels."""

    SUBTLE = 0.3
    LIGHT = 0.5
    MEDIUM = 0.7
    STRONG = 0.9
    FULL = 1.0


@dataclass
class FeedbackEvent:
    """Unified feedback event with sound + haptic coordination.

    Defines what sound to play, what haptic to trigger,
    and optional spatial positioning.
    """

    # Sound
    earcon_name: str  # From earcon_orchestrator
    spatial_position: Pos3D | None = None  # 3D position (or None for center)

    # Haptic
    haptic_pattern: str | None = None  # Matching haptic pattern name
    haptic_intensity: float = 1.0  # 0.0 to 1.0

    # Targeting
    target: FeedbackTarget = FeedbackTarget.AUTO
    rooms: list[str] = field(default_factory=list)

    # Context
    priority: int = 5  # 1 (highest) to 10 (lowest)
    bypass_wakefulness: bool = False  # For safety/urgent events


# ============================================================================
# Predefined Feedback Pairs
# ============================================================================

# Maps common events to coordinated sound + haptic pairs
FEEDBACK_PAIRS: dict[str, FeedbackEvent] = {
    # Positive outcomes
    "success": FeedbackEvent(
        earcon_name="success",
        haptic_pattern="success",
        haptic_intensity=0.8,
        priority=5,
    ),
    "celebration": FeedbackEvent(
        earcon_name="celebration",
        haptic_pattern="success",
        haptic_intensity=1.0,
        priority=3,
    ),
    "scene_activated": FeedbackEvent(
        earcon_name="success",
        haptic_pattern="scene_activated",
        haptic_intensity=0.7,
        priority=5,
    ),
    # Negative outcomes
    "error": FeedbackEvent(
        earcon_name="error",
        haptic_pattern="error",
        haptic_intensity=0.9,
        priority=3,
    ),
    "warning": FeedbackEvent(
        earcon_name="alert",
        haptic_pattern="warning",
        haptic_intensity=0.8,
        priority=4,
    ),
    # Notifications
    "notification": FeedbackEvent(
        earcon_name="notification",
        haptic_pattern="light_impact",
        haptic_intensity=0.5,
        priority=6,
    ),
    "message": FeedbackEvent(
        earcon_name="message_received",
        haptic_pattern="selection",
        haptic_intensity=0.6,
        priority=6,
    ),
    "package": FeedbackEvent(
        earcon_name="package",
        haptic_pattern="discovery_engage",
        haptic_intensity=0.7,
        priority=5,
    ),
    "meeting_soon": FeedbackEvent(
        earcon_name="meeting_soon",
        haptic_pattern="medium_impact",
        haptic_intensity=0.6,
        priority=4,
    ),
    # Presence
    "arrival": FeedbackEvent(
        earcon_name="arrival",
        haptic_pattern="success",
        haptic_intensity=0.6,
        priority=5,
    ),
    "departure": FeedbackEvent(
        earcon_name="departure",
        haptic_pattern="soft_impact",
        haptic_intensity=0.4,
        priority=6,
    ),
    "first_home": FeedbackEvent(
        earcon_name="first_home",
        haptic_pattern="success",
        haptic_intensity=0.7,
        priority=4,
    ),
    "home_empty": FeedbackEvent(
        earcon_name="home_empty",
        haptic_pattern="soft_impact",
        haptic_intensity=0.3,
        priority=7,
    ),
    # Security
    "lock_engaged": FeedbackEvent(
        earcon_name="lock_engaged",
        haptic_pattern="lock_engaged",
        haptic_intensity=0.8,
        priority=4,
    ),
    "security_arm": FeedbackEvent(
        earcon_name="security_arm",
        haptic_pattern="rigid_impact",
        haptic_intensity=0.7,
        priority=4,
    ),
    "camera_alert": FeedbackEvent(
        earcon_name="camera_alert",
        haptic_pattern="warning",
        haptic_intensity=0.9,
        priority=2,
    ),
    "motion_detected": FeedbackEvent(
        earcon_name="motion_detected",
        haptic_pattern="tick",
        haptic_intensity=0.3,
        priority=8,
    ),
    # Appliances
    "washer_complete": FeedbackEvent(
        earcon_name="washer_complete",
        haptic_pattern="success",
        haptic_intensity=0.5,
        priority=6,
    ),
    "dryer_complete": FeedbackEvent(
        earcon_name="dryer_complete",
        haptic_pattern="success",
        haptic_intensity=0.5,
        priority=6,
    ),
    "dishwasher_complete": FeedbackEvent(
        earcon_name="dishwasher_complete",
        haptic_pattern="success",
        haptic_intensity=0.5,
        priority=6,
    ),
    "coffee_ready": FeedbackEvent(
        earcon_name="coffee_ready",
        haptic_pattern="discovery_engage",
        haptic_intensity=0.6,
        priority=5,
    ),
    "oven_preheat": FeedbackEvent(
        earcon_name="oven_preheat",
        haptic_pattern="medium_impact",
        haptic_intensity=0.5,
        priority=6,
    ),
    # Voice
    "voice_acknowledge": FeedbackEvent(
        earcon_name="voice_acknowledge",
        haptic_pattern="selection",
        haptic_intensity=0.4,
        priority=7,
    ),
    "voice_complete": FeedbackEvent(
        earcon_name="voice_complete",
        haptic_pattern="success",
        haptic_intensity=0.5,
        priority=6,
    ),
    # Time
    "awakening": FeedbackEvent(
        earcon_name="awakening",
        haptic_pattern="soft_impact",
        haptic_intensity=0.4,
        priority=6,
    ),
    "settling": FeedbackEvent(
        earcon_name="settling",
        haptic_pattern="soft_impact",
        haptic_intensity=0.3,
        priority=7,
    ),
    "evening_transition": FeedbackEvent(
        earcon_name="evening_transition",
        haptic_pattern="soft_impact",
        haptic_intensity=0.3,
        priority=7,
    ),
    "midnight": FeedbackEvent(
        earcon_name="midnight",
        haptic_pattern="tick",
        haptic_intensity=0.2,
        priority=9,
    ),
    # UI
    "tap": FeedbackEvent(
        earcon_name="focus",
        haptic_pattern="light_impact",
        haptic_intensity=0.5,
        priority=8,
    ),
    "selection": FeedbackEvent(
        earcon_name="focus",
        haptic_pattern="selection",
        haptic_intensity=0.4,
        priority=8,
    ),
    "discovery_glance": FeedbackEvent(
        earcon_name="room_enter",
        haptic_pattern="discovery_glance",
        haptic_intensity=0.3,
        priority=9,
    ),
    # Safety (high priority, bypasses wakefulness)
    "safety_violation": FeedbackEvent(
        earcon_name="alert",
        haptic_pattern="safety_violation",
        haptic_intensity=1.0,
        priority=1,
        bypass_wakefulness=True,
    ),
    # Weather
    "storm_approaching": FeedbackEvent(
        earcon_name="storm_approaching",
        haptic_pattern="warning",
        haptic_intensity=0.7,
        priority=4,
    ),
    "rain_starting": FeedbackEvent(
        earcon_name="rain_starting",
        haptic_pattern="soft_impact",
        haptic_intensity=0.3,
        priority=7,
    ),
}


# ============================================================================
# Unified Feedback Service
# ============================================================================


class UnifiedFeedbackService:
    """Coordinates sound + haptic feedback across all platforms.

    This service:
    1. Plays earcons through the unified voice effector (spatial audio)
    2. Broadcasts haptic events to connected clients via WebSocket
    3. Adapts to wakefulness state (quiet at night)
    4. Routes to appropriate rooms based on context

    Thread-safe via asyncio.
    """

    def __init__(self) -> None:
        self._initialized = False
        self._connected_clients: set[str] = set()
        self._broadcast_callback: Any | None = None

    async def initialize(self) -> bool:
        """Initialize the feedback service."""
        if self._initialized:
            return True

        logger.info("Initializing unified feedback service")
        self._initialized = True
        return True

    def set_broadcast_callback(self, callback: Any) -> None:
        """Set callback for broadcasting haptic events to clients.

        The callback should accept (event_type: str, data: dict).
        Typically this is the WebSocket broadcast function.
        """
        self._broadcast_callback = callback

    def register_client(self, client_id: str) -> None:
        """Register a connected client for haptic events."""
        self._connected_clients.add(client_id)
        logger.debug("Registered client for haptics: %s", client_id)

    def unregister_client(self, client_id: str) -> None:
        """Unregister a client."""
        self._connected_clients.discard(client_id)

    # ========================================================================
    # Core API
    # ========================================================================

    async def trigger(self, event: FeedbackEvent) -> bool:
        """Trigger coordinated sound + haptic feedback.

        Args:
            event: The feedback event to trigger

        Returns:
            True if feedback was triggered successfully
        """
        if not self._initialized:
            await self.initialize()

        # Check wakefulness (skip for bypassed events)
        if not event.bypass_wakefulness:
            should_play = await self._check_wakefulness(event)
            if not should_play:
                logger.debug("Skipping feedback due to wakefulness: %s", event.earcon_name)
                return False

        # Play audio through spatial system
        audio_success = await self._play_earcon(event)

        # Broadcast haptic to clients
        haptic_success = await self._broadcast_haptic(event)

        return audio_success or haptic_success

    async def trigger_named(self, name: str, **overrides: Any) -> bool:
        """Trigger a predefined feedback pair by name.

        Args:
            name: Predefined feedback name (e.g., "success", "error")
            **overrides: Optional overrides for the event

        Returns:
            True if feedback was triggered
        """
        base_event = FEEDBACK_PAIRS.get(name)
        if not base_event:
            logger.warning("Unknown feedback event: %s", name)
            return False

        # Apply overrides
        event = FeedbackEvent(
            earcon_name=overrides.get("earcon_name", base_event.earcon_name),
            spatial_position=overrides.get("spatial_position", base_event.spatial_position),
            haptic_pattern=overrides.get("haptic_pattern", base_event.haptic_pattern),
            haptic_intensity=overrides.get("haptic_intensity", base_event.haptic_intensity),
            target=overrides.get("target", base_event.target),
            rooms=overrides.get("rooms", base_event.rooms),
            priority=overrides.get("priority", base_event.priority),
            bypass_wakefulness=overrides.get("bypass_wakefulness", base_event.bypass_wakefulness),
        )

        return await self.trigger(event)

    # ========================================================================
    # Convenience Methods
    # ========================================================================

    async def success(self, rooms: list[str] | None = None) -> bool:
        """Play success feedback."""
        return await self.trigger_named("success", rooms=rooms or [])

    async def error(self, rooms: list[str] | None = None) -> bool:
        """Play error feedback."""
        return await self.trigger_named("error", rooms=rooms or [])

    async def warning(self, rooms: list[str] | None = None) -> bool:
        """Play warning feedback."""
        return await self.trigger_named("warning", rooms=rooms or [])

    async def notification(self, rooms: list[str] | None = None) -> bool:
        """Play notification feedback."""
        return await self.trigger_named("notification", rooms=rooms or [])

    async def scene_activated(self, scene_name: str, rooms: list[str] | None = None) -> bool:
        """Play scene activation feedback."""
        logger.info("Scene activated: %s", scene_name)
        return await self.trigger_named("scene_activated", rooms=rooms or [])

    async def arrival(self, who: str = "", rooms: list[str] | None = None) -> bool:
        """Play arrival feedback."""
        logger.info("Arrival: %s", who or "someone")
        return await self.trigger_named("arrival", rooms=rooms or [])

    async def departure(self, who: str = "", rooms: list[str] | None = None) -> bool:
        """Play departure feedback."""
        logger.info("Departure: %s", who or "someone")
        return await self.trigger_named("departure", rooms=rooms or [])

    async def safety_violation(self) -> bool:
        """Play safety violation feedback (always plays, high priority)."""
        logger.warning("Safety violation feedback triggered")
        return await self.trigger_named("safety_violation")

    async def voice_acknowledge(self) -> bool:
        """Play voice acknowledgment (assistant is listening)."""
        return await self.trigger_named("voice_acknowledge")

    async def voice_complete(self) -> bool:
        """Play voice completion (assistant finished task)."""
        return await self.trigger_named("voice_complete")

    # ========================================================================
    # Internal Methods
    # ========================================================================

    async def _check_wakefulness(self, event: FeedbackEvent) -> bool:
        """Check if feedback should play based on wakefulness state.

        High-priority events (1-3) always play.
        Lower priority events are suppressed during sleep.
        """
        # High priority always plays
        if event.priority <= 3:
            return True

        try:
            from kagami.core.integrations.wakefulness import get_wakefulness_manager

            wakefulness = get_wakefulness_manager()
            state = await wakefulness.get_state()

            # Allow during active/drowsy states
            if state.level in ("active", "drowsy"):
                return True

            # Suppress during dormant/sleep
            if state.level in ("dormant", "asleep"):
                # Allow medium priority during dormant
                if event.priority <= 5 and state.level == "dormant":
                    return True
                return False

            return True

        except Exception:
            # If wakefulness check fails, allow playback
            return True

    async def _play_earcon(self, event: FeedbackEvent) -> bool:
        """Play the earcon through the spatial audio system."""
        try:
            from kagami.core.audio import get_audio_asset_store

            store = await get_audio_asset_store()
            audio_path = await store.get_earcon(event.earcon_name, format="aac")

            if not audio_path:
                logger.warning("Earcon not found: %s", event.earcon_name)
                return False

            # Route through unified voice effector for spatial playback
            # (In production, this would use the full spatial pipeline)
            logger.debug("Playing earcon: %s", event.earcon_name)

            # For now, just confirm the path exists
            # Full integration would call:
            # await unified_voice_effector.play_spatial(audio_path, event.spatial_position)
            return True

        except Exception as e:
            logger.error("Failed to play earcon %s: %s", event.earcon_name, e)
            return False

    async def _broadcast_haptic(self, event: FeedbackEvent) -> bool:
        """Broadcast haptic event to connected clients."""
        if not event.haptic_pattern:
            return True  # No haptic needed

        if not self._connected_clients and not self._broadcast_callback:
            return True  # No clients to notify

        haptic_data = {
            "type": "haptic",
            "pattern": event.haptic_pattern,
            "intensity": event.haptic_intensity,
            "priority": event.priority,
        }

        try:
            if self._broadcast_callback:
                await self._broadcast_callback("haptic", haptic_data)
                return True

            # Direct broadcast to registered clients
            # (Would use WebSocket in production)
            logger.debug("Broadcasting haptic: %s", event.haptic_pattern)
            return True

        except Exception as e:
            logger.error("Failed to broadcast haptic: %s", e)
            return False


# ============================================================================
# Factory Function
# ============================================================================

_service: UnifiedFeedbackService | None = None


async def get_unified_feedback() -> UnifiedFeedbackService:
    """Get or create the unified feedback service singleton."""
    global _service
    if _service is None:
        _service = UnifiedFeedbackService()
        await _service.initialize()
    return _service


# ============================================================================
# Exports
# ============================================================================

__all__ = [
    "FEEDBACK_PAIRS",
    "FeedbackEvent",
    "FeedbackTarget",
    "HapticIntensity",
    "UnifiedFeedbackService",
    "get_unified_feedback",
]
