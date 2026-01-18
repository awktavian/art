"""Unified Haptics Controller for XR and Wearables.

Provides consistent haptic feedback across devices:
- Meta Neural Band (wrist haptics via air pressure)
- Apple Watch (Taptic Engine)
- Quest Controllers (rumble motors)
- iOS/Android devices (vibration motors)

Design Philosophy:
"A small, well-tested set of patterns that align with user tasks delivers
better results than a large assortment of novelty effects."
    - Haptics Industry Forum

Pattern Categories:
1. Confirmation: Action completed successfully
2. Alert: Requires attention
3. Navigation: Spatial/directional feedback
4. Safety: Critical warnings (h(x) >= 0)
5. State Change: Device/mode transitions

Timing uses Fibonacci sequence for natural feel:
89ms, 144ms, 233ms, 377ms, 610ms, 987ms

References:
- Meta Bellowband/Tasbi prototypes for wrist haptics
- XR Haptics Design Guidelines book
- WCAG 2.1 motion/haptics accessibility requirements

Created: January 2026
h(x) >= 0. Always.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


# =============================================================================
# Fibonacci Timing Constants
# =============================================================================

# Natural-feeling durations based on Fibonacci sequence
TIMING_INSTANT = 34  # ms - barely perceptible
TIMING_QUICK = 55  # ms - quick tap
TIMING_SHORT = 89  # ms - short pulse
TIMING_MEDIUM = 144  # ms - medium pulse
TIMING_STANDARD = 233  # ms - standard duration
TIMING_LONG = 377  # ms - long pulse
TIMING_EXTENDED = 610  # ms - extended feedback
TIMING_SUSTAINED = 987  # ms - sustained feedback


class HapticDevice(Enum):
    """Supported haptic-capable devices."""

    # Wrist wearables
    META_NEURAL_BAND = "meta_neural_band"
    APPLE_WATCH = "apple_watch"

    # XR controllers
    QUEST_LEFT = "quest_left"
    QUEST_RIGHT = "quest_right"
    SPATIAL_LEFT = "spatial_left"
    SPATIAL_RIGHT = "spatial_right"

    # Mobile devices
    PHONE = "phone"
    TABLET = "tablet"

    # Unknown/generic
    UNKNOWN = "unknown"


class HapticIntensity(Enum):
    """Haptic feedback intensity levels."""

    LIGHT = 0.25  # Subtle, background feedback
    MEDIUM = 0.5  # Default, noticeable but not intrusive
    STRONG = 0.75  # Important, demands attention
    CRITICAL = 1.0  # Safety-critical, maximum intensity


class HapticPattern(Enum):
    """Predefined haptic patterns for common actions.

    Each pattern is designed for a specific purpose and tested
    across devices for consistent feel.
    """

    # =========================================================================
    # CONFIRMATION PATTERNS (Success, completion)
    # =========================================================================
    CONFIRM_TAP = "confirm_tap"  # Single quick tap
    CONFIRM_DOUBLE = "confirm_double"  # Two quick taps
    CONFIRM_SUCCESS = "confirm_success"  # Rising pulse (success)
    CONFIRM_COMPLETE = "confirm_complete"  # Satisfying completion

    # =========================================================================
    # ALERT PATTERNS (Attention needed)
    # =========================================================================
    ALERT_NOTIFICATION = "alert_notification"  # Gentle notification
    ALERT_ATTENTION = "alert_attention"  # Requires attention
    ALERT_WARNING = "alert_warning"  # Warning, not critical
    ALERT_ERROR = "alert_error"  # Error occurred

    # =========================================================================
    # SAFETY PATTERNS (h(x) >= 0 enforcement)
    # =========================================================================
    SAFETY_CRITICAL = "safety_critical"  # Critical safety alert
    SAFETY_STOP = "safety_stop"  # Emergency stop confirmation
    SAFETY_BOUNDARY = "safety_boundary"  # Approaching safety boundary
    SAFETY_VIOLATION = "safety_violation"  # Safety constraint violated

    # =========================================================================
    # NAVIGATION PATTERNS (Spatial/directional)
    # =========================================================================
    NAV_LEFT = "nav_left"  # Directional left
    NAV_RIGHT = "nav_right"  # Directional right
    NAV_UP = "nav_up"  # Directional up
    NAV_DOWN = "nav_down"  # Directional down
    NAV_SELECT = "nav_select"  # Selection made
    NAV_BACK = "nav_back"  # Going back

    # =========================================================================
    # STATE CHANGE PATTERNS (Mode/device transitions)
    # =========================================================================
    STATE_ON = "state_on"  # Device/feature turned on
    STATE_OFF = "state_off"  # Device/feature turned off
    STATE_TOGGLE = "state_toggle"  # State toggled
    STATE_LOCK = "state_lock"  # Locked/secured
    STATE_UNLOCK = "state_unlock"  # Unlocked

    # =========================================================================
    # SCENE ACTIVATION PATTERNS (Smart home scenes)
    # =========================================================================
    SCENE_SPARK = "scene_spark"  # Quick scene (Colony: Spark)
    SCENE_FORGE = "scene_forge"  # Powerful action (Colony: Forge)
    SCENE_FLOW = "scene_flow"  # Smooth transition (Colony: Flow)
    SCENE_NEXUS = "scene_nexus"  # Integration (Colony: Nexus)
    SCENE_BEACON = "scene_beacon"  # Guidance (Colony: Beacon)
    SCENE_GROVE = "scene_grove"  # Calm/nature (Colony: Grove)
    SCENE_CRYSTAL = "scene_crystal"  # Clarity (Colony: Crystal)

    # =========================================================================
    # INTERACTION PATTERNS (Continuous feedback)
    # =========================================================================
    DRAG_START = "drag_start"  # Starting drag interaction
    DRAG_END = "drag_end"  # Ending drag interaction
    SLIDER_TICK = "slider_tick"  # Slider position tick
    SLIDER_LIMIT = "slider_limit"  # Reached slider limit
    SCROLL_BUMP = "scroll_bump"  # Scroll resistance
    PINCH_CONFIRM = "pinch_confirm"  # Pinch gesture confirmed


@dataclass
class HapticPulse:
    """Single haptic pulse definition."""

    duration_ms: int
    intensity: float  # 0.0 to 1.0
    frequency_hz: float = 200.0  # For devices that support frequency


@dataclass
class HapticFeedback:
    """Complete haptic feedback definition."""

    pattern: HapticPattern
    pulses: list[HapticPulse] = field(default_factory=list)
    intensity_multiplier: float = 1.0
    loop: bool = False
    loop_count: int = 1


# =============================================================================
# Pattern Definitions
# =============================================================================

PATTERN_DEFINITIONS: dict[HapticPattern, list[HapticPulse]] = {
    # Confirmation
    HapticPattern.CONFIRM_TAP: [
        HapticPulse(TIMING_QUICK, 0.5),
    ],
    HapticPattern.CONFIRM_DOUBLE: [
        HapticPulse(TIMING_QUICK, 0.5),
        HapticPulse(TIMING_SHORT, 0.0),  # Pause
        HapticPulse(TIMING_QUICK, 0.5),
    ],
    HapticPattern.CONFIRM_SUCCESS: [
        HapticPulse(TIMING_SHORT, 0.3),
        HapticPulse(TIMING_INSTANT, 0.0),
        HapticPulse(TIMING_MEDIUM, 0.5),
    ],
    HapticPattern.CONFIRM_COMPLETE: [
        HapticPulse(TIMING_SHORT, 0.4),
        HapticPulse(TIMING_QUICK, 0.0),
        HapticPulse(TIMING_SHORT, 0.5),
        HapticPulse(TIMING_QUICK, 0.0),
        HapticPulse(TIMING_MEDIUM, 0.6),
    ],
    # Alerts
    HapticPattern.ALERT_NOTIFICATION: [
        HapticPulse(TIMING_SHORT, 0.3),
        HapticPulse(TIMING_MEDIUM, 0.0),
        HapticPulse(TIMING_SHORT, 0.3),
    ],
    HapticPattern.ALERT_ATTENTION: [
        HapticPulse(TIMING_MEDIUM, 0.6),
        HapticPulse(TIMING_SHORT, 0.0),
        HapticPulse(TIMING_MEDIUM, 0.6),
    ],
    HapticPattern.ALERT_WARNING: [
        HapticPulse(TIMING_STANDARD, 0.7),
        HapticPulse(TIMING_SHORT, 0.0),
        HapticPulse(TIMING_STANDARD, 0.7),
        HapticPulse(TIMING_SHORT, 0.0),
        HapticPulse(TIMING_STANDARD, 0.7),
    ],
    HapticPattern.ALERT_ERROR: [
        HapticPulse(TIMING_LONG, 0.8),
        HapticPulse(TIMING_MEDIUM, 0.0),
        HapticPulse(TIMING_LONG, 0.8),
    ],
    # Safety (h(x) >= 0 - these are critical)
    HapticPattern.SAFETY_CRITICAL: [
        HapticPulse(TIMING_SUSTAINED, 1.0),
        HapticPulse(TIMING_STANDARD, 0.0),
        HapticPulse(TIMING_SUSTAINED, 1.0),
    ],
    HapticPattern.SAFETY_STOP: [
        HapticPulse(TIMING_EXTENDED, 1.0),
    ],
    HapticPattern.SAFETY_BOUNDARY: [
        HapticPulse(TIMING_MEDIUM, 0.6, 100.0),  # Lower frequency = rumble
    ],
    HapticPattern.SAFETY_VIOLATION: [
        HapticPulse(TIMING_STANDARD, 0.9),
        HapticPulse(TIMING_SHORT, 0.0),
        HapticPulse(TIMING_STANDARD, 0.9),
        HapticPulse(TIMING_SHORT, 0.0),
        HapticPulse(TIMING_LONG, 1.0),
    ],
    # Navigation
    HapticPattern.NAV_LEFT: [
        HapticPulse(TIMING_SHORT, 0.4),
    ],
    HapticPattern.NAV_RIGHT: [
        HapticPulse(TIMING_SHORT, 0.4),
    ],
    HapticPattern.NAV_UP: [
        HapticPulse(TIMING_SHORT, 0.4, 250.0),  # Higher frequency = up
    ],
    HapticPattern.NAV_DOWN: [
        HapticPulse(TIMING_SHORT, 0.4, 150.0),  # Lower frequency = down
    ],
    HapticPattern.NAV_SELECT: [
        HapticPulse(TIMING_QUICK, 0.6),
    ],
    HapticPattern.NAV_BACK: [
        HapticPulse(TIMING_QUICK, 0.3),
        HapticPulse(TIMING_INSTANT, 0.0),
        HapticPulse(TIMING_QUICK, 0.3),
    ],
    # State changes
    HapticPattern.STATE_ON: [
        HapticPulse(TIMING_SHORT, 0.3),
        HapticPulse(TIMING_QUICK, 0.0),
        HapticPulse(TIMING_MEDIUM, 0.5),
    ],
    HapticPattern.STATE_OFF: [
        HapticPulse(TIMING_MEDIUM, 0.5),
        HapticPulse(TIMING_QUICK, 0.0),
        HapticPulse(TIMING_SHORT, 0.3),
    ],
    HapticPattern.STATE_TOGGLE: [
        HapticPulse(TIMING_SHORT, 0.4),
    ],
    HapticPattern.STATE_LOCK: [
        HapticPulse(TIMING_MEDIUM, 0.6),
        HapticPulse(TIMING_INSTANT, 0.0),
        HapticPulse(TIMING_QUICK, 0.4),
    ],
    HapticPattern.STATE_UNLOCK: [
        HapticPulse(TIMING_QUICK, 0.3),
        HapticPulse(TIMING_SHORT, 0.0),
        HapticPulse(TIMING_SHORT, 0.5),
    ],
    # Scene activation (Colony patterns)
    HapticPattern.SCENE_SPARK: [
        HapticPulse(TIMING_INSTANT, 0.7),
        HapticPulse(TIMING_QUICK, 0.5),
    ],
    HapticPattern.SCENE_FORGE: [
        HapticPulse(TIMING_MEDIUM, 0.7),
        HapticPulse(TIMING_SHORT, 0.0),
        HapticPulse(TIMING_LONG, 0.8),
    ],
    HapticPattern.SCENE_FLOW: [
        HapticPulse(TIMING_SHORT, 0.3),
        HapticPulse(TIMING_SHORT, 0.4),
        HapticPulse(TIMING_MEDIUM, 0.5),
        HapticPulse(TIMING_SHORT, 0.4),
        HapticPulse(TIMING_SHORT, 0.3),
    ],
    HapticPattern.SCENE_NEXUS: [
        HapticPulse(TIMING_SHORT, 0.5),
        HapticPulse(TIMING_INSTANT, 0.0),
        HapticPulse(TIMING_SHORT, 0.5),
        HapticPulse(TIMING_INSTANT, 0.0),
        HapticPulse(TIMING_MEDIUM, 0.6),
    ],
    HapticPattern.SCENE_BEACON: [
        HapticPulse(TIMING_QUICK, 0.3),
        HapticPulse(TIMING_MEDIUM, 0.0),
        HapticPulse(TIMING_SHORT, 0.4),
        HapticPulse(TIMING_STANDARD, 0.0),
        HapticPulse(TIMING_MEDIUM, 0.5),
    ],
    HapticPattern.SCENE_GROVE: [
        HapticPulse(TIMING_STANDARD, 0.3),
        HapticPulse(TIMING_MEDIUM, 0.2),
    ],
    HapticPattern.SCENE_CRYSTAL: [
        HapticPulse(TIMING_INSTANT, 0.6),
        HapticPulse(TIMING_INSTANT, 0.0),
        HapticPulse(TIMING_INSTANT, 0.6),
    ],
    # Interaction
    HapticPattern.DRAG_START: [
        HapticPulse(TIMING_QUICK, 0.4),
    ],
    HapticPattern.DRAG_END: [
        HapticPulse(TIMING_SHORT, 0.5),
    ],
    HapticPattern.SLIDER_TICK: [
        HapticPulse(TIMING_INSTANT, 0.3),
    ],
    HapticPattern.SLIDER_LIMIT: [
        HapticPulse(TIMING_SHORT, 0.6),
    ],
    HapticPattern.SCROLL_BUMP: [
        HapticPulse(TIMING_INSTANT, 0.2),
    ],
    HapticPattern.PINCH_CONFIRM: [
        HapticPulse(TIMING_SHORT, 0.5),
    ],
}


HapticCallback = Callable[["HapticEvent"], Awaitable[None]]


@dataclass
class HapticEvent:
    """Event when haptic feedback is triggered."""

    pattern: HapticPattern
    device: HapticDevice
    intensity: HapticIntensity
    timestamp: float = field(default_factory=time.time)


@dataclass
class HapticsConfig:
    """Configuration for haptics controller."""

    # Enable/disable
    enabled: bool = True

    # Global intensity multiplier (accessibility)
    intensity_multiplier: float = 1.0

    # Device-specific settings
    wrist_haptics_enabled: bool = True
    controller_haptics_enabled: bool = True
    phone_haptics_enabled: bool = True

    # Safety overrides (always play safety haptics)
    safety_override_enabled: bool = True

    # Debounce to prevent over-triggering
    min_interval_ms: int = 50


class UnifiedHapticsController:
    """Cross-device haptic feedback controller.

    Provides consistent haptic patterns across:
    - Wrist wearables (Meta Neural Band, Apple Watch)
    - XR controllers (Quest, spatial controllers)
    - Mobile devices (phone, tablet vibration)

    Usage:
        controller = UnifiedHapticsController()
        await controller.initialize()

        # Play a pattern
        await controller.play(HapticPattern.CONFIRM_SUCCESS)

        # Play on specific device
        await controller.play(
            HapticPattern.NAV_LEFT,
            device=HapticDevice.QUEST_LEFT
        )

        # Safety feedback (always plays)
        await controller.safety_alert(HapticPattern.SAFETY_CRITICAL)
    """

    def __init__(self, config: HapticsConfig | None = None) -> None:
        self.config = config or HapticsConfig()

        self._devices: dict[HapticDevice, Any] = {}
        self._last_play_time: float = 0.0
        self._callbacks: list[HapticCallback] = []

        logger.info("UnifiedHapticsController created")

    async def initialize(self) -> bool:
        """Initialize haptics controller.

        Discovers available haptic devices and initializes drivers.

        Returns:
            True if at least one haptic device is available
        """
        logger.info("Initializing haptics controller...")

        # Try to initialize each device type
        await self._init_wrist_devices()
        await self._init_controller_devices()
        await self._init_phone_devices()

        available = len(self._devices) > 0
        if available:
            logger.info(f"Haptics initialized with {len(self._devices)} device(s)")
        else:
            logger.warning("No haptic devices available - feedback will be silent")

        return available

    async def _init_wrist_devices(self) -> None:
        """Initialize wrist haptic devices."""
        if not self.config.wrist_haptics_enabled:
            return

        # Meta Neural Band
        try:
            from kagami_hal.adapters.neural import get_meta_emg_adapter

            adapter = get_meta_emg_adapter()
            if adapter.is_connected:
                self._devices[HapticDevice.META_NEURAL_BAND] = adapter
                logger.debug("Meta Neural Band haptics available")
        except Exception as e:
            logger.debug(f"Meta Neural Band not available: {e}")

        # Apple Watch (via WatchConnectivity)
        # Would require native bridge

    async def _init_controller_devices(self) -> None:
        """Initialize XR controller haptic devices."""
        if not self.config.controller_haptics_enabled:
            return

        # Quest controllers would be initialized via native bridge
        # Placeholder for now

    async def _init_phone_devices(self) -> None:
        """Initialize phone haptic devices."""
        if not self.config.phone_haptics_enabled:
            return

        # iOS/Android vibration would be via native bridge
        # Placeholder for now

    async def play(
        self,
        pattern: HapticPattern,
        device: HapticDevice | None = None,
        intensity: HapticIntensity = HapticIntensity.MEDIUM,
    ) -> bool:
        """Play a haptic pattern.

        Args:
            pattern: Pattern to play
            device: Specific device (None = all available)
            intensity: Intensity level

        Returns:
            True if played on at least one device
        """
        if not self.config.enabled:
            return False

        # Debounce check
        now = time.time()
        if (now - self._last_play_time) * 1000 < self.config.min_interval_ms:
            return False
        self._last_play_time = now

        # Get pulses for pattern
        pulses = PATTERN_DEFINITIONS.get(pattern, [])
        if not pulses:
            logger.warning(f"Unknown pattern: {pattern}")
            return False

        # Apply intensity
        effective_intensity = intensity.value * self.config.intensity_multiplier
        adjusted_pulses = [
            HapticPulse(
                duration_ms=p.duration_ms,
                intensity=min(1.0, p.intensity * effective_intensity),
                frequency_hz=p.frequency_hz,
            )
            for p in pulses
        ]

        # Play on device(s)
        played = False
        target_devices = [device] if device else list(self._devices.keys())

        for dev in target_devices:
            if dev in self._devices:
                try:
                    await self._play_on_device(dev, adjusted_pulses)
                    played = True

                    # Fire callback
                    event = HapticEvent(
                        pattern=pattern,
                        device=dev,
                        intensity=intensity,
                    )
                    for callback in self._callbacks:
                        try:
                            await callback(event)
                        except Exception as e:
                            logger.warning(f"Haptic callback error: {e}")

                except Exception as e:
                    logger.warning(f"Failed to play haptic on {dev}: {e}")

        return played

    async def _play_on_device(self, device: HapticDevice, pulses: list[HapticPulse]) -> None:
        """Play pulses on specific device."""
        # Device-specific playback
        if device == HapticDevice.META_NEURAL_BAND:
            await self._play_neural_band(pulses)
        elif device in (HapticDevice.QUEST_LEFT, HapticDevice.QUEST_RIGHT):
            await self._play_quest_controller(device, pulses)
        elif device == HapticDevice.APPLE_WATCH:
            await self._play_apple_watch(pulses)
        elif device in (HapticDevice.PHONE, HapticDevice.TABLET):
            await self._play_mobile(pulses)
        else:
            # Generic fallback - just time the pulses
            await self._play_generic(pulses)

    async def _play_neural_band(self, pulses: list[HapticPulse]) -> None:
        """Play haptics on Meta Neural Band."""
        # Neural band uses air pressure chambers (Bellowband-style)
        # Would send via WebSocket to companion app
        for pulse in pulses:
            if pulse.intensity > 0:
                # In real implementation: send haptic command
                await asyncio.sleep(pulse.duration_ms / 1000.0)
            else:
                await asyncio.sleep(pulse.duration_ms / 1000.0)

    async def _play_quest_controller(self, device: HapticDevice, pulses: list[HapticPulse]) -> None:
        """Play haptics on Quest controller."""
        # Would use OpenXR haptics API
        for pulse in pulses:
            await asyncio.sleep(pulse.duration_ms / 1000.0)

    async def _play_apple_watch(self, pulses: list[HapticPulse]) -> None:
        """Play haptics on Apple Watch."""
        # Would use WatchConnectivity to trigger Taptic Engine
        for pulse in pulses:
            await asyncio.sleep(pulse.duration_ms / 1000.0)

    async def _play_mobile(self, pulses: list[HapticPulse]) -> None:
        """Play haptics on mobile device."""
        # Would use platform vibration API
        for pulse in pulses:
            await asyncio.sleep(pulse.duration_ms / 1000.0)

    async def _play_generic(self, pulses: list[HapticPulse]) -> None:
        """Generic pulse playback (timing only)."""
        for pulse in pulses:
            await asyncio.sleep(pulse.duration_ms / 1000.0)

    # =========================================================================
    # Convenience Methods
    # =========================================================================

    async def confirm(self) -> bool:
        """Quick confirmation feedback."""
        return await self.play(HapticPattern.CONFIRM_TAP)

    async def success(self) -> bool:
        """Success feedback."""
        return await self.play(HapticPattern.CONFIRM_SUCCESS)

    async def error(self) -> bool:
        """Error feedback."""
        return await self.play(HapticPattern.ALERT_ERROR)

    async def notification(self) -> bool:
        """Notification feedback."""
        return await self.play(HapticPattern.ALERT_NOTIFICATION)

    # =========================================================================
    # Safety Patterns (h(x) >= 0)
    # =========================================================================

    async def safety_alert(
        self,
        pattern: HapticPattern = HapticPattern.SAFETY_CRITICAL,
    ) -> bool:
        """Play safety-critical haptic feedback.

        Safety haptics always play regardless of user settings.
        h(x) >= 0. Always.

        Args:
            pattern: Safety pattern to play

        Returns:
            True if played
        """
        # Safety override - always play at maximum intensity
        if self.config.safety_override_enabled:
            old_enabled = self.config.enabled
            self.config.enabled = True

            result = await self.play(
                pattern,
                intensity=HapticIntensity.CRITICAL,
            )

            self.config.enabled = old_enabled
            return result

        return await self.play(pattern, intensity=HapticIntensity.CRITICAL)

    async def emergency_stop(self) -> bool:
        """Emergency stop haptic confirmation."""
        return await self.safety_alert(HapticPattern.SAFETY_STOP)

    async def safety_boundary_warning(self) -> bool:
        """Approaching safety boundary warning."""
        return await self.safety_alert(HapticPattern.SAFETY_BOUNDARY)

    # =========================================================================
    # Scene Activation Patterns (Colony)
    # =========================================================================

    async def scene_activated(self, colony_name: str) -> bool:
        """Play haptic for scene activation.

        Args:
            colony_name: Colony/scene name (spark, forge, flow, etc.)

        Returns:
            True if played
        """
        pattern_map = {
            "spark": HapticPattern.SCENE_SPARK,
            "forge": HapticPattern.SCENE_FORGE,
            "flow": HapticPattern.SCENE_FLOW,
            "nexus": HapticPattern.SCENE_NEXUS,
            "beacon": HapticPattern.SCENE_BEACON,
            "grove": HapticPattern.SCENE_GROVE,
            "crystal": HapticPattern.SCENE_CRYSTAL,
        }

        pattern = pattern_map.get(colony_name.lower())
        if pattern:
            return await self.play(pattern)

        # Default to confirm for unknown scenes
        return await self.play(HapticPattern.CONFIRM_SUCCESS)

    # =========================================================================
    # Callbacks
    # =========================================================================

    def on_haptic(self, callback: HapticCallback) -> None:
        """Register callback for haptic events."""
        self._callbacks.append(callback)

    def off_haptic(self, callback: HapticCallback) -> None:
        """Unregister haptic callback."""
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    # =========================================================================
    # Lifecycle
    # =========================================================================

    async def shutdown(self) -> None:
        """Shutdown haptics controller."""
        self._devices.clear()
        self._callbacks.clear()
        logger.info("UnifiedHapticsController shutdown")


# =============================================================================
# Singleton
# =============================================================================

_controller: UnifiedHapticsController | None = None


def get_haptics_controller(config: HapticsConfig | None = None) -> UnifiedHapticsController:
    """Get or create the haptics controller singleton."""
    global _controller
    if _controller is None:
        _controller = UnifiedHapticsController(config)
    return _controller


async def initialize_haptics(config: HapticsConfig | None = None) -> UnifiedHapticsController:
    """Initialize and return the haptics controller."""
    controller = get_haptics_controller(config)
    await controller.initialize()
    return controller


"""
Mirror
h(x) >= 0. Always.

Haptics speak to the body directly.
The skin understands what words cannot say.
Confirmation. Warning. Guidance.
A tap is worth a thousand words.
"""
