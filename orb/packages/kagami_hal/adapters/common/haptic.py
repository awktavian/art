"""Haptic Feedback Controller for HAL.

Provides tactile feedback through vibration motors and haptic actuators.

Patterns:
- Single tap (notification)
- Double tap (confirmation)
- Long vibration (alert)
- Custom patterns

Moved from kagami.core.ambient to HAL for proper hardware abstraction alignment.

Created: November 10, 2025
Moved to HAL: December 1, 2025
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


class HapticPattern(Enum):
    """Predefined haptic patterns."""

    TAP = "tap"  # Quick single vibration
    DOUBLE_TAP = "double_tap"  # Two quick vibrations
    ALERT = "alert"  # Long strong vibration
    SUCCESS = "success"  # Quick double with pause
    ERROR = "error"  # Three short pulses
    NOTIFICATION = "notification"  # Gentle notification
    CUSTOM = "custom"


@dataclass
class HapticPulse:
    """Single haptic pulse."""

    duration_ms: int
    intensity: float  # 0.0-1.0


class HapticController:
    """HAL Haptic feedback controller.

    Provides platform-independent haptic feedback interface.
    """

    def __init__(self, device_path: str | None = None):
        """Initialize haptic controller.

        Args:
            device_path: Vibration motor device path (platform-specific)
        """
        self.device_path = device_path or "/dev/vibrator"
        self._initialized = False
        self._mock_mode = True

        # Predefined patterns
        self.patterns: dict[HapticPattern, list[HapticPulse]] = {
            HapticPattern.TAP: [HapticPulse(50, 0.5)],
            HapticPattern.DOUBLE_TAP: [
                HapticPulse(50, 0.5),
                HapticPulse(100, 0.0),  # Pause
                HapticPulse(50, 0.5),
            ],
            HapticPattern.ALERT: [HapticPulse(500, 0.8)],
            HapticPattern.SUCCESS: [
                HapticPulse(30, 0.4),
                HapticPulse(80, 0.0),
                HapticPulse(30, 0.4),
            ],
            HapticPattern.ERROR: [
                HapticPulse(50, 0.6),
                HapticPulse(50, 0.0),
                HapticPulse(50, 0.6),
                HapticPulse(50, 0.0),
                HapticPulse(50, 0.6),
            ],
            HapticPattern.NOTIFICATION: [
                HapticPulse(30, 0.3),
                HapticPulse(100, 0.0),
                HapticPulse(30, 0.3),
            ],
        }

    async def initialize(self) -> bool:
        """Initialize haptic controller.

        Returns:
            True if hardware is available, False if in mock mode
        """
        if self._initialized:
            return not self._mock_mode

        # Check for vibrator device
        if Path(self.device_path).exists():
            self._mock_mode = False
            self._initialized = True
            logger.info(f"✅ HAL Haptic controller initialized: {self.device_path}")
            return True

        # Try platform-specific initialization
        import platform

        system = platform.system()

        if system == "Darwin":
            # macOS: Try to use CoreHaptics
            try:
                # Would use CoreHaptics framework
                logger.debug("macOS detected - CoreHaptics may be available")
            except Exception:
                pass
        elif system == "Linux":
            # Linux: Check for input event devices
            try:
                import glob

                haptic_devices = glob.glob("/dev/input/event*")
                for _device in haptic_devices:
                    # Would check for FF_RUMBLE capability
                    pass
            except Exception:
                pass

        self._initialized = True
        logger.warning(
            f"Vibrator device not found: {self.device_path}\n"
            "Haptic feedback in mock mode - no hardware response"
        )
        return False

    @property
    def available(self) -> bool:
        """Check if haptic hardware is available."""
        return self._initialized and not self._mock_mode

    async def play_pattern(self, pattern: HapticPattern) -> None:
        """Play predefined haptic pattern.

        Args:
            pattern: Pattern to play
        """
        pulses = self.patterns.get(pattern, [])
        await self.play_custom(pulses)

    async def play_custom(self, pulses: list[HapticPulse]) -> None:
        """Play custom haptic pattern.

        Args:
            pulses: List of haptic pulses
        """
        if not self._initialized:
            await self.initialize()

        if self._mock_mode:
            # Log but don't raise - allow graceful degradation
            logger.debug(f"Haptic mock: playing {len(pulses)} pulses")
            return

        for pulse in pulses:
            if pulse.intensity > 0:
                await self._vibrate(pulse.duration_ms, pulse.intensity)
            else:
                await asyncio.sleep(pulse.duration_ms / 1000.0)

    async def _vibrate(self, duration_ms: int, intensity: float) -> None:
        """Activate vibration motor.

        Args:
            duration_ms: Duration in milliseconds
            intensity: Vibration strength (0.0-1.0)
        """
        # Platform-specific vibration implementation would go here
        # Example implementations:
        # - Linux: Write to /dev/input/eventX with FF_RUMBLE
        # - macOS: CoreHaptics CHHapticEngine
        # - Android: Vibrator service via JNI
        # - iOS: UIFeedbackGenerator

        await asyncio.sleep(duration_ms / 1000.0)

    # Convenience methods
    async def tap(self) -> None:
        """Quick tap feedback."""
        await self.play_pattern(HapticPattern.TAP)

    async def double_tap(self) -> None:
        """Double tap feedback."""
        await self.play_pattern(HapticPattern.DOUBLE_TAP)

    async def alert(self) -> None:
        """Alert feedback."""
        await self.play_pattern(HapticPattern.ALERT)

    async def success(self) -> None:
        """Success feedback."""
        await self.play_pattern(HapticPattern.SUCCESS)

    async def error(self) -> None:
        """Error feedback."""
        await self.play_pattern(HapticPattern.ERROR)

    async def notification(self) -> None:
        """Notification feedback."""
        await self.play_pattern(HapticPattern.NOTIFICATION)

    async def shutdown(self) -> None:
        """Shutdown haptic controller."""
        logger.info("✅ HAL Haptic controller shutdown")


# Singleton instance
_HAPTIC_CONTROLLER: HapticController | None = None


def get_haptic_controller() -> HapticController:
    """Get global haptic controller instance."""
    global _HAPTIC_CONTROLLER
    if _HAPTIC_CONTROLLER is None:
        _HAPTIC_CONTROLLER = HapticController()
    return _HAPTIC_CONTROLLER


async def get_haptic_controller_async() -> HapticController:
    """Get and initialize global haptic controller."""
    controller = get_haptic_controller()
    await controller.initialize()
    return controller
