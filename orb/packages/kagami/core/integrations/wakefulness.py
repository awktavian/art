"""Wakefulness Manager — Unified Wakefulness State for All Subsystems.

CREATED: December 29, 2025
UPDATED: December 30, 2025 - Added visual wakefulness detection via Meta Glasses

This module provides a SINGLE source of truth for system wakefulness,
affecting polling rates, autonomy, and alert thresholds across all subsystems.

Wakefulness Levels:
- DORMANT: System sleeping (minimal polling, no autonomy)
- DROWSY: Waking up or winding down (reduced polling, limited autonomy)
- ALERT: Normal active state (standard polling, full autonomy)
- FOCUSED: Deep work mode (reduced interrupts, active autonomy)
- HYPER: High urgency (aggressive polling, immediate alerts)

Visual Wakefulness Detection (December 30, 2025):
- Meta Glasses camera can detect eyes open/closed
- Combines with Eight Sleep data for robust wakefulness inference
- Lighting conditions inform circadian state

Integration Points:
- UnifiedSensory: Adapts poll_interval multipliers
- AutonomousGoalEngine: Controls autonomy enable/pause
- AlertHierarchy: Adapts alert thresholds
- OrganismConsciousness: Sync wakefulness to consciousness tensor
- SituationAwarenessEngine: SituationPhase → WakefulnessLevel mapping
- MetaGlassesIntegration: Visual wakefulness detection

Philosophy: One wakefulness state drives all behavior.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from kagami.core.autonomous_goal_engine import AutonomousGoalEngine
    from kagami.core.integrations.unified_sensory import UnifiedSensoryIntegration

    # Visual wakefulness detection
    try:
        from kagami_smarthome.integrations.meta_glasses import MetaGlassesIntegration, VisualContext
    except ImportError:
        MetaGlassesIntegration = None
        VisualContext = None

logger = logging.getLogger(__name__)


class WakefulnessLevel(Enum):
    """System wakefulness levels.

    Each level affects:
    - poll_multiplier: How fast/slow to poll senses
    - autonomy_enabled: Whether autonomous goals run
    - alert_threshold: Minimum priority for interruptions
    - processing_budget: CPU/memory budget for background tasks
    """

    DORMANT = "dormant"  # Sleeping - minimal activity
    DROWSY = "drowsy"  # Waking/winding down - reduced activity
    ALERT = "alert"  # Normal active state
    FOCUSED = "focused"  # Deep work - minimize interrupts
    HYPER = "hyper"  # High urgency - maximum responsiveness


@dataclass
class WakefulnessConfig:
    """Configuration for a wakefulness level."""

    level: WakefulnessLevel
    poll_multiplier: float  # Multiply poll intervals (>1 = slower, <1 = faster)
    autonomy_enabled: bool  # Whether autonomous goals run
    alert_min_priority: int  # Minimum alert priority (1=critical only, 5=all)
    processing_budget: float  # 0.0-1.0 budget for background processing

    # Sense-specific overrides (sense_type -> multiplier)
    sense_overrides: dict[str, float] = field(default_factory=dict)


# Default configurations per wakefulness level
WAKEFULNESS_CONFIGS: dict[WakefulnessLevel, WakefulnessConfig] = {
    WakefulnessLevel.DORMANT: WakefulnessConfig(
        level=WakefulnessLevel.DORMANT,
        poll_multiplier=10.0,  # Poll 10x slower
        autonomy_enabled=False,  # No autonomous activity
        alert_min_priority=1,  # Only critical alerts
        processing_budget=0.1,  # 10% processing budget
        sense_overrides={
            "presence": 2.0,  # Still check presence somewhat
            "security": 1.0,  # Security always normal
            "locks": 1.0,  # Locks always normal
        },
    ),
    WakefulnessLevel.DROWSY: WakefulnessConfig(
        level=WakefulnessLevel.DROWSY,
        poll_multiplier=3.0,  # Poll 3x slower
        autonomy_enabled=False,  # No autonomous activity
        alert_min_priority=2,  # High priority and above
        processing_budget=0.3,  # 30% processing budget
        sense_overrides={
            "presence": 1.0,  # Normal presence polling
            "security": 1.0,
        },
    ),
    WakefulnessLevel.ALERT: WakefulnessConfig(
        level=WakefulnessLevel.ALERT,
        poll_multiplier=1.0,  # Normal polling
        autonomy_enabled=True,  # Full autonomy
        alert_min_priority=4,  # Normal and above
        processing_budget=0.7,  # 70% processing budget
    ),
    WakefulnessLevel.FOCUSED: WakefulnessConfig(
        level=WakefulnessLevel.FOCUSED,
        poll_multiplier=2.0,  # Slower polling (less interrupts)
        autonomy_enabled=True,  # Autonomy continues
        alert_min_priority=2,  # Only high priority interrupts
        processing_budget=0.5,  # 50% processing budget
        sense_overrides={
            "gmail": 5.0,  # Much slower email polling
            "discord": 10.0,  # Almost no Discord polling
            "calendar": 1.0,  # But watch calendar
        },
    ),
    WakefulnessLevel.HYPER: WakefulnessConfig(
        level=WakefulnessLevel.HYPER,
        poll_multiplier=0.5,  # Poll 2x faster
        autonomy_enabled=True,  # Full autonomy
        alert_min_priority=5,  # All alerts
        processing_budget=1.0,  # Full processing budget
    ),
}


# Callback type for wakefulness changes
WakefulnessCallback = Callable[[WakefulnessLevel, WakefulnessLevel], Awaitable[None]]


class WakefulnessManager:
    """Unified wakefulness state manager.

    ARCHITECTURE:
    =============
    WakefulnessManager is the SINGLE source of truth for system wakefulness.

    All subsystems subscribe to wakefulness changes and adapt:
    - UnifiedSensory: Multiplies poll intervals
    - AutonomousGoalEngine: Enables/disables autonomy
    - AlertHierarchy: Adjusts alert thresholds
    - OrganismConsciousness: Updates wakefulness tensor

    Wakefulness is derived from:
    - SituationPhase (from SituationAwareness)
    - Time of day
    - User activity signals
    - Sleep state (from Eight Sleep)
    - Visual cues (from Meta Glasses) — NEW

    Visual Wakefulness Signals:
    - Eyes open/closed detection
    - Lighting conditions (bright = alert, dark = drowsy)
    - Face detection (looking at camera = engaged)

    Usage:
        wakefulness = get_wakefulness_manager()
        wakefulness.on_change(my_callback)
        await wakefulness.set_level(WakefulnessLevel.FOCUSED)

        # With visual detection
        wakefulness.connect_meta_glasses(glasses)
        await wakefulness.update_from_visual_context()
    """

    def __init__(self):
        self._level = WakefulnessLevel.ALERT
        self._config = WAKEFULNESS_CONFIGS[WakefulnessLevel.ALERT]

        # Subscribers
        self._listeners: list[WakefulnessCallback] = []

        # Connected subsystems (for direct control)
        self._sensory: UnifiedSensoryIntegration | None = None
        self._autonomy: AutonomousGoalEngine | None = None
        self._alert_hierarchy: Any = None
        self._consciousness: Any = None
        self._meta_glasses: Any = None  # MetaGlassesIntegration

        # Visual wakefulness state
        self._last_visual_context: Any = None  # VisualContext
        self._visual_wakefulness_confidence = 0.0
        self._eyes_detected_open = True  # Assume awake by default

        # State tracking
        self._last_change = time.time()
        self._change_count = 0
        self._stats = {
            "transitions": 0,
            "time_per_level": {level.value: 0.0 for level in WakefulnessLevel},
            "visual_updates": 0,
        }

    @property
    def level(self) -> WakefulnessLevel:
        """Get current wakefulness level."""
        return self._level

    @property
    def config(self) -> WakefulnessConfig:
        """Get current wakefulness configuration."""
        return self._config

    def get_poll_multiplier(self, sense_type: str | None = None) -> float:
        """Get poll interval multiplier for current wakefulness.

        Args:
            sense_type: Optional sense type for specific override

        Returns:
            Multiplier (>1 = slower, <1 = faster)
        """
        if sense_type and sense_type in self._config.sense_overrides:
            return self._config.sense_overrides[sense_type]
        return self._config.poll_multiplier

    def is_autonomy_enabled(self) -> bool:
        """Check if autonomy should be running."""
        return self._config.autonomy_enabled

    def get_alert_threshold(self) -> int:
        """Get minimum alert priority for interruptions."""
        return self._config.alert_min_priority

    def get_processing_budget(self) -> float:
        """Get background processing budget (0.0-1.0)."""
        return self._config.processing_budget

    # =========================================================================
    # SUBSCRIBER MANAGEMENT
    # =========================================================================

    def on_change(self, callback: WakefulnessCallback) -> None:
        """Register callback for wakefulness changes.

        Callback receives (old_level, new_level).
        """
        self._listeners.append(callback)
        logger.debug(f"Registered wakefulness listener: {callback.__name__}")

    def remove_listener(self, callback: WakefulnessCallback) -> None:
        """Remove a wakefulness listener."""
        if callback in self._listeners:
            self._listeners.remove(callback)

    async def _emit_change(self, old_level: WakefulnessLevel, new_level: WakefulnessLevel) -> None:
        """Emit wakefulness change to all listeners."""
        for listener in self._listeners:
            try:
                await listener(old_level, new_level)
            except Exception as e:
                logger.warning(f"Wakefulness listener error: {e}")

    # =========================================================================
    # SUBSYSTEM CONNECTIONS
    # =========================================================================

    def connect_sensory(self, sensory: UnifiedSensoryIntegration) -> None:
        """Connect to UnifiedSensory for poll interval control."""
        self._sensory = sensory
        # Wire the poll multiplier
        if hasattr(sensory, "set_poll_multiplier"):
            sensory.set_poll_multiplier(self.get_poll_multiplier)
        logger.info("🔗 Wakefulness connected to UnifiedSensory")

    def connect_autonomy(self, autonomy: AutonomousGoalEngine) -> None:
        """Connect to AutonomousGoalEngine for autonomy control."""
        self._autonomy = autonomy
        logger.info("🔗 Wakefulness connected to AutonomousGoalEngine")

    def connect_alerts(self, alert_hierarchy: Any) -> None:
        """Connect to AlertHierarchy for threshold control."""
        self._alert_hierarchy = alert_hierarchy
        logger.info("🔗 Wakefulness connected to AlertHierarchy")

    def connect_consciousness(self, consciousness: Any) -> None:
        """Connect to OrganismConsciousness for state sync."""
        self._consciousness = consciousness
        logger.info("🔗 Wakefulness connected to OrganismConsciousness")

    def connect_meta_glasses(self, glasses: Any) -> None:
        """Connect to MetaGlassesIntegration for visual wakefulness detection.

        Args:
            glasses: MetaGlassesIntegration instance
        """
        self._meta_glasses = glasses
        logger.info("🔗 Wakefulness connected to MetaGlasses (visual detection)")

    # =========================================================================
    # VISUAL WAKEFULNESS DETECTION (December 30, 2025)
    # =========================================================================

    async def update_from_visual_context(self, context: Any = None) -> WakefulnessLevel | None:
        """Update wakefulness from visual context (Meta Glasses camera).

        Visual signals:
        - Eyes open/closed → ALERT vs DROWSY/DORMANT
        - Lighting conditions → Circadian hints
        - Face engagement → Focus level

        Args:
            context: Optional VisualContext (if None, fetches from glasses)

        Returns:
            New WakefulnessLevel if changed, None if unchanged
        """
        # Get context from glasses if not provided
        if context is None and self._meta_glasses:
            try:
                context = await self._meta_glasses.get_visual_context()
            except Exception as e:
                logger.debug(f"Failed to get visual context: {e}")
                return None

        if context is None:
            return None

        self._last_visual_context = context
        self._stats["visual_updates"] += 1

        # Infer wakefulness from visual signals
        inferred_level = self._infer_wakefulness_from_visual(context)

        if inferred_level and inferred_level != self._level:
            # Only change if confidence is high enough
            if self._visual_wakefulness_confidence >= 0.7:
                await self.set_level(inferred_level)
                return inferred_level

        return None

    def _infer_wakefulness_from_visual(self, context: Any) -> WakefulnessLevel | None:
        """Infer wakefulness level from visual context.

        Args:
            context: VisualContext from Meta Glasses

        Returns:
            Inferred WakefulnessLevel or None if uncertain
        """
        # Reset confidence
        self._visual_wakefulness_confidence = 0.0

        # Get visual features
        lighting = getattr(context, "lighting", None)
        activity_hint = getattr(context, "activity_hint", None)
        faces_detected = getattr(context, "faces_detected", 0)
        is_indoor = getattr(context, "is_indoor", None)
        confidence = getattr(context, "confidence", 0.0)

        # Low confidence context — don't change
        if confidence < 0.5:
            return None

        # Check for activity hints
        if activity_hint:
            hint_lower = activity_hint.lower()

            if hint_lower in ("sleeping", "resting", "eyes_closed"):
                self._eyes_detected_open = False
                self._visual_wakefulness_confidence = confidence
                return WakefulnessLevel.DORMANT

            if hint_lower in ("waking", "drowsy", "tired"):
                self._visual_wakefulness_confidence = confidence * 0.8
                return WakefulnessLevel.DROWSY

            if hint_lower in ("working", "reading", "focused"):
                self._eyes_detected_open = True
                self._visual_wakefulness_confidence = confidence
                return WakefulnessLevel.FOCUSED

            if hint_lower in ("exercising", "active", "urgent"):
                self._eyes_detected_open = True
                self._visual_wakefulness_confidence = confidence
                return WakefulnessLevel.HYPER

        # Check lighting conditions
        if lighting:
            if lighting == "dark":
                # Dark environment — likely drowsy or sleeping
                self._visual_wakefulness_confidence = confidence * 0.6
                if is_indoor:
                    return WakefulnessLevel.DROWSY
                return None  # Could be outside at night

            if lighting == "dim":
                # Dim lighting — could be relaxing or winding down
                self._visual_wakefulness_confidence = confidence * 0.5
                return WakefulnessLevel.ALERT  # Don't change to drowsy just from dim

            if lighting == "bright":
                # Bright lighting — definitely awake
                self._eyes_detected_open = True
                self._visual_wakefulness_confidence = confidence * 0.7
                return WakefulnessLevel.ALERT

        # Check social context
        if faces_detected > 0:
            # Other people present — probably alert/engaged
            self._eyes_detected_open = True
            self._visual_wakefulness_confidence = confidence * 0.6
            return WakefulnessLevel.ALERT

        return None

    def get_visual_wakefulness_state(self) -> dict[str, Any]:
        """Get visual wakefulness detection state.

        Returns:
            Dict with visual wakefulness info
        """
        return {
            "eyes_detected_open": self._eyes_detected_open,
            "visual_confidence": self._visual_wakefulness_confidence,
            "has_visual_context": self._last_visual_context is not None,
            "glasses_connected": self._meta_glasses is not None
            and getattr(self._meta_glasses, "is_connected", False),
            "visual_updates": self._stats.get("visual_updates", 0),
        }

    # =========================================================================
    # LEVEL MANAGEMENT
    # =========================================================================

    async def set_level(self, new_level: WakefulnessLevel) -> None:
        """Set wakefulness level and notify all subsystems.

        This is the SINGLE point of control for wakefulness.
        All connected subsystems adapt automatically.
        """
        if new_level == self._level:
            return

        old_level = self._level

        # Track time in previous level
        time_in_level = time.time() - self._last_change
        self._stats["time_per_level"][old_level.value] += time_in_level
        self._stats["transitions"] += 1

        # Update state
        self._level = new_level
        self._config = WAKEFULNESS_CONFIGS[new_level]
        self._last_change = time.time()
        self._change_count += 1

        logger.info(f"🌡️ Wakefulness: {old_level.value} → {new_level.value}")

        # Notify connected subsystems directly
        await self._apply_to_subsystems(old_level, new_level)

        # Notify event listeners
        await self._emit_change(old_level, new_level)

    async def _apply_to_subsystems(
        self, old_level: WakefulnessLevel, new_level: WakefulnessLevel
    ) -> None:
        """Apply wakefulness change to all connected subsystems."""

        # 1. Autonomy control
        if self._autonomy:
            if self._config.autonomy_enabled:
                if hasattr(self._autonomy, "resume"):
                    await self._autonomy.resume()
            else:
                if hasattr(self._autonomy, "pause"):
                    await self._autonomy.pause()

        # 2. Alert threshold
        if self._alert_hierarchy:
            if hasattr(self._alert_hierarchy, "set_min_priority"):
                self._alert_hierarchy.set_min_priority(self._config.alert_min_priority)

        # 3. Consciousness sync
        if self._consciousness:
            if hasattr(self._consciousness, "set_wakefulness"):
                await self._consciousness.set_wakefulness(new_level.value)

    # =========================================================================
    # SITUATION PHASE MAPPING (Dec 30, 2025)
    # =========================================================================

    def from_situation_phase(self, phase: Any) -> WakefulnessLevel:
        """Map SituationPhase to WakefulnessLevel.

        This is THE canonical mapping from situation → wakefulness.

        Args:
            phase: SituationPhase enum or string value

        Returns:
            Corresponding WakefulnessLevel
        """
        # Handle both enum and string
        phase_value = phase.value if hasattr(phase, "value") else str(phase)

        mapping = {
            # Sleep states
            "sleeping": WakefulnessLevel.DORMANT,
            "waking": WakefulnessLevel.DROWSY,
            "winding_down": WakefulnessLevel.DROWSY,
            # Morning states
            "morning_routine": WakefulnessLevel.DROWSY,
            # Work states
            "working": WakefulnessLevel.ALERT,
            "in_meeting": WakefulnessLevel.FOCUSED,
            "focused": WakefulnessLevel.FOCUSED,
            "break": WakefulnessLevel.ALERT,
            # Movement states
            "commuting": WakefulnessLevel.ALERT,
            "exercising": WakefulnessLevel.HYPER,
            # Leisure states
            "relaxing": WakefulnessLevel.ALERT,
            "eating": WakefulnessLevel.ALERT,
            "socializing": WakefulnessLevel.ALERT,
            # Unknown
            "unknown": WakefulnessLevel.ALERT,
        }
        return mapping.get(phase_value, WakefulnessLevel.ALERT)

    async def update_from_situation_phase(self, phase: Any) -> None:
        """Update wakefulness from a SituationPhase.

        Args:
            phase: SituationPhase enum (from situation_awareness.py)
        """
        new_level = self.from_situation_phase(phase)
        await self.set_level(new_level)

    # =========================================================================
    # STATUS & STATISTICS
    # =========================================================================

    def get_status(self) -> dict[str, Any]:
        """Get wakefulness status and statistics."""
        return {
            "level": self._level.value,
            "poll_multiplier": self._config.poll_multiplier,
            "autonomy_enabled": self._config.autonomy_enabled,
            "alert_threshold": self._config.alert_min_priority,
            "processing_budget": self._config.processing_budget,
            "time_at_level": time.time() - self._last_change,
            "transitions": self._stats["transitions"],
            "connected": {
                "sensory": self._sensory is not None,
                "autonomy": self._autonomy is not None,
                "alerts": self._alert_hierarchy is not None,
                "consciousness": self._consciousness is not None,
                "meta_glasses": self._meta_glasses is not None,
            },
            "visual": self.get_visual_wakefulness_state(),
        }


# =============================================================================
# SINGLETON
# =============================================================================

_wakefulness_manager: WakefulnessManager | None = None


def get_wakefulness_manager() -> WakefulnessManager:
    """Get global WakefulnessManager instance."""
    global _wakefulness_manager
    if _wakefulness_manager is None:
        _wakefulness_manager = WakefulnessManager()
    return _wakefulness_manager


def reset_wakefulness_manager() -> None:
    """Reset global WakefulnessManager (for testing)."""
    global _wakefulness_manager
    _wakefulness_manager = None


async def initialize_wakefulness(
    sensory: UnifiedSensoryIntegration | None = None,
    autonomy: AutonomousGoalEngine | None = None,
    alert_hierarchy: Any = None,
    consciousness: Any = None,
) -> WakefulnessManager:
    """Initialize and wire the WakefulnessManager.

    Args:
        sensory: UnifiedSensoryIntegration for poll control
        autonomy: AutonomousGoalEngine for autonomy control
        alert_hierarchy: AlertHierarchy for threshold control
        consciousness: OrganismConsciousness for state sync

    Returns:
        Configured WakefulnessManager
    """
    manager = get_wakefulness_manager()

    if sensory:
        manager.connect_sensory(sensory)
    if autonomy:
        manager.connect_autonomy(autonomy)
    if alert_hierarchy:
        manager.connect_alerts(alert_hierarchy)
    if consciousness:
        manager.connect_consciousness(consciousness)

    logger.info("✅ WakefulnessManager initialized")
    return manager


__all__ = [
    "WAKEFULNESS_CONFIGS",
    "WakefulnessCallback",
    "WakefulnessConfig",
    "WakefulnessLevel",
    "WakefulnessManager",
    "get_wakefulness_manager",
    "initialize_wakefulness",
    "reset_wakefulness_manager",
]
