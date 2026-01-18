"""Visual Alert System for Deaf/Hard-of-Hearing Users.

Provides visual feedback alternatives to audio alerts:
- Screen border flashing
- Full-screen overlays
- LED indicators (for Hub device)
- Device vibration (for mobile)

Usage:
    from kagami.core.accessibility.visual_alerts import (
        VisualAlertSystem,
        flash_alert,
        overlay_alert,
    )

    # Initialize alert system
    alerts = VisualAlertSystem()
    alerts.register_handler(my_flash_handler)

    # Send flash alert
    await flash_alert("Door opened", severity="warning")

    # Send overlay alert
    await overlay_alert("Smoke detected!", severity="critical")

Created: January 1, 2026
Part of: Apps 100/100 Transformation - Phase 1.4
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class AlertPattern(str, Enum):
    """Patterns for visual alerts."""

    SOLID = "solid"  # Solid color
    PULSE = "pulse"  # Pulsing brightness
    FLASH = "flash"  # On/off flash
    WAVE = "wave"  # Wave pattern (for LED rings)
    BREATHE = "breathe"  # Slow breathing effect


class AlertLocation(str, Enum):
    """Where to display visual alerts."""

    BORDER = "border"  # Screen border only
    FULLSCREEN = "fullscreen"  # Full screen overlay
    CORNER = "corner"  # Corner indicator
    LED = "led"  # External LED (Hub)
    ALL = "all"  # All available methods


@dataclass
class VisualAlertConfig:
    """Configuration for a visual alert."""

    message: str
    severity: str = "info"
    color: str | None = None  # Override color
    pattern: AlertPattern = AlertPattern.FLASH
    location: AlertLocation = AlertLocation.BORDER
    duration_ms: int = 2000
    repeat: int = 2
    vibrate: bool = True

    # Pattern-specific settings
    flash_interval_ms: int = 200  # For FLASH pattern
    pulse_min_opacity: float = 0.3  # For PULSE pattern
    breathe_cycle_ms: int = 2000  # For BREATHE pattern

    @property
    def color_value(self) -> str:
        """Get the actual color to use.

        Colors synchronized with packages/kagami-design/design-tokens.json
        """
        if self.color:
            return self.color

        # Semantic colors from design-tokens.json
        severity_colors = {
            "info": "#5AC8FA",  # color.semantic.info.base (Flow cyan)
            "success": "#32D74B",  # color.semantic.success.base (Grove green)
            "warning": "#FFD60A",  # color.semantic.warning.base (Beacon yellow)
            "error": "#FF3B30",  # color.semantic.error.base
            "critical": "#AF52DE",  # color.colony.nexus.base (Purple)
        }
        return severity_colors.get(self.severity, "#5AC8FA")

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for transmission."""
        return {
            "message": self.message,
            "severity": self.severity,
            "color": self.color_value,
            "pattern": self.pattern.value,
            "location": self.location.value,
            "duration_ms": self.duration_ms,
            "repeat": self.repeat,
            "vibrate": self.vibrate,
            "flash_interval_ms": self.flash_interval_ms,
            "pulse_min_opacity": self.pulse_min_opacity,
            "breathe_cycle_ms": self.breathe_cycle_ms,
        }


class VisualAlertSystem:
    """Central system for managing visual alerts.

    Coordinates visual alerts across different output methods
    (screen, LED, vibration) and handles alert queuing.
    """

    def __init__(self):
        """Initialize the visual alert system."""
        self._handlers: list[Callable[[VisualAlertConfig], None]] = []
        self._led_handlers: list[Callable[[VisualAlertConfig], None]] = []
        self._vibration_handlers: list[Callable[[int, int], None]] = []
        self._enabled = True
        self._current_alert: VisualAlertConfig | None = None
        self._alert_lock = asyncio.Lock()

    @property
    def enabled(self) -> bool:
        """Check if visual alerts are enabled."""
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        """Enable or disable visual alerts."""
        self._enabled = value

    def register_handler(
        self,
        handler: Callable[[VisualAlertConfig], None],
    ) -> None:
        """Register a handler for screen-based visual alerts.

        Args:
            handler: Function that receives VisualAlertConfig
        """
        self._handlers.append(handler)

    def register_led_handler(
        self,
        handler: Callable[[VisualAlertConfig], None],
    ) -> None:
        """Register a handler for LED alerts (Hub device).

        Args:
            handler: Function that receives VisualAlertConfig
        """
        self._led_handlers.append(handler)

    def register_vibration_handler(
        self,
        handler: Callable[[int, int], None],
    ) -> None:
        """Register a handler for vibration alerts.

        Args:
            handler: Function that receives (duration_ms, repeat)
        """
        self._vibration_handlers.append(handler)

    async def send_alert(self, config: VisualAlertConfig) -> None:
        """Send a visual alert.

        Args:
            config: Alert configuration
        """
        if not self._enabled:
            return

        async with self._alert_lock:
            self._current_alert = config

            # Send to screen handlers
            if config.location in (
                AlertLocation.BORDER,
                AlertLocation.FULLSCREEN,
                AlertLocation.CORNER,
                AlertLocation.ALL,
            ):
                for handler in self._handlers:
                    try:
                        handler(config)
                    except Exception as e:
                        logger.error(f"Visual alert handler error: {e}")

            # Send to LED handlers
            if config.location in (AlertLocation.LED, AlertLocation.ALL):
                for handler in self._led_handlers:
                    try:
                        handler(config)
                    except Exception as e:
                        logger.error(f"LED alert handler error: {e}")

            # Send vibration
            if config.vibrate:
                vibration_pattern = self._get_vibration_pattern(config)
                for handler in self._vibration_handlers:
                    try:
                        handler(*vibration_pattern)
                    except Exception as e:
                        logger.error(f"Vibration handler error: {e}")

            # Clear after duration
            await asyncio.sleep(config.duration_ms / 1000)
            self._current_alert = None

    def _get_vibration_pattern(
        self,
        config: VisualAlertConfig,
    ) -> tuple[int, int]:
        """Get vibration pattern for severity.

        Returns:
            Tuple of (duration_ms, repeat_count)
        """
        patterns = {
            "info": (100, 1),
            "success": (200, 1),
            "warning": (300, 2),
            "error": (500, 3),
            "critical": (1000, 5),
        }
        return patterns.get(config.severity, (200, 1))


# Global alert system instance
_alert_system = VisualAlertSystem()


def get_alert_system() -> VisualAlertSystem:
    """Get the global visual alert system.

    Returns:
        The global VisualAlertSystem instance
    """
    return _alert_system


async def flash_alert(
    message: str,
    severity: str = "info",
    duration_ms: int = 2000,
    repeat: int = 2,
) -> None:
    """Send a flash alert (screen border).

    Args:
        message: Alert message
        severity: Severity level
        duration_ms: Total duration
        repeat: Number of flashes
    """
    config = VisualAlertConfig(
        message=message,
        severity=severity,
        pattern=AlertPattern.FLASH,
        location=AlertLocation.BORDER,
        duration_ms=duration_ms,
        repeat=repeat,
    )
    await _alert_system.send_alert(config)


async def overlay_alert(
    message: str,
    severity: str = "warning",
    duration_ms: int = 3000,
) -> None:
    """Send a full-screen overlay alert.

    Args:
        message: Alert message
        severity: Severity level
        duration_ms: Duration to show
    """
    config = VisualAlertConfig(
        message=message,
        severity=severity,
        pattern=AlertPattern.PULSE,
        location=AlertLocation.FULLSCREEN,
        duration_ms=duration_ms,
        repeat=1,
    )
    await _alert_system.send_alert(config)


async def corner_indicator(
    message: str,
    severity: str = "info",
    duration_ms: int = 5000,
) -> None:
    """Show a corner indicator.

    Args:
        message: Alert message
        severity: Severity level
        duration_ms: Duration to show
    """
    config = VisualAlertConfig(
        message=message,
        severity=severity,
        pattern=AlertPattern.SOLID,
        location=AlertLocation.CORNER,
        duration_ms=duration_ms,
        repeat=1,
        vibrate=False,
    )
    await _alert_system.send_alert(config)


async def led_alert(
    message: str,
    severity: str = "info",
    pattern: str = "wave",
    duration_ms: int = 3000,
) -> None:
    """Send an LED alert (for Hub device).

    Args:
        message: Alert message
        severity: Severity level
        pattern: LED pattern ("solid", "pulse", "wave", "breathe")
        duration_ms: Duration
    """
    config = VisualAlertConfig(
        message=message,
        severity=severity,
        pattern=AlertPattern(pattern),
        location=AlertLocation.LED,
        duration_ms=duration_ms,
        repeat=1,
    )
    await _alert_system.send_alert(config)


# Pre-built alert templates for common scenarios


async def alert_door_open(door_name: str = "Door") -> None:
    """Alert that a door is open."""
    await flash_alert(f"{door_name} is open", severity="warning")


async def alert_door_unlocked(door_name: str = "Door") -> None:
    """Alert that a door was unlocked."""
    await flash_alert(f"{door_name} unlocked", severity="info")


async def alert_motion_detected(location: str = "Home") -> None:
    """Alert that motion was detected."""
    await corner_indicator(f"Motion detected: {location}", severity="info")


async def alert_smoke_detected() -> None:
    """Critical alert for smoke detection."""
    await overlay_alert("SMOKE DETECTED!", severity="critical", duration_ms=10000)


async def alert_co_detected() -> None:
    """Critical alert for carbon monoxide."""
    await overlay_alert("CARBON MONOXIDE DETECTED!", severity="critical", duration_ms=10000)


async def alert_water_leak(location: str = "Home") -> None:
    """Alert for water leak."""
    await overlay_alert(f"Water leak detected: {location}", severity="error", duration_ms=5000)


async def alert_security_breach() -> None:
    """Alert for security breach."""
    await overlay_alert("SECURITY BREACH!", severity="critical", duration_ms=10000)


__all__ = [
    "AlertLocation",
    "AlertPattern",
    "VisualAlertConfig",
    "VisualAlertSystem",
    "alert_co_detected",
    "alert_door_open",
    "alert_door_unlocked",
    "alert_motion_detected",
    "alert_security_breach",
    "alert_smoke_detected",
    "alert_water_leak",
    "corner_indicator",
    "flash_alert",
    "get_alert_system",
    "led_alert",
    "overlay_alert",
]
