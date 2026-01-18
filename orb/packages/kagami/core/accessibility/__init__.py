"""Accessibility Foundation Module.

Provides comprehensive accessibility support for Kagami apps:
- Visual alerts for deaf/hard-of-hearing users
- Simplified mode for elder users
- High contrast WCAG AAA compliance checking
- Reduced motion support
- Screen reader announcements

Usage:
    from kagami.core.accessibility import (
        AccessibilityManager,
        SimplifiedModeConfig,
        visual_alert,
        check_contrast,
        should_reduce_motion,
    )

    # Initialize accessibility manager
    a11y = AccessibilityManager(user_id="user-123")
    await a11y.initialize()

    # Check if simplified mode is enabled
    if a11y.simplified_mode_enabled:
        # Show larger buttons, simpler UI
        pass

    # Send visual alert (for deaf users)
    await visual_alert("Door is open", severity="warning")

    # Check color contrast
    is_valid = check_contrast("#ffffff", "#000000", level="AAA")

Created: January 1, 2026
Part of: Apps 100/100 Transformation - Phase 1.4
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class AlertSeverity(str, Enum):
    """Severity levels for visual alerts."""

    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AlertType(str, Enum):
    """Types of visual alerts."""

    FLASH = "flash"  # Screen border flash
    OVERLAY = "overlay"  # Full-screen overlay
    BADGE = "badge"  # Icon badge/indicator
    VIBRATION = "vibration"  # Device vibration (mobile)
    LED = "led"  # LED indicator (Hub device)


@dataclass
class VisualAlert:
    """Configuration for a visual alert."""

    message: str
    severity: AlertSeverity = AlertSeverity.INFO
    alert_types: list[AlertType] = field(default_factory=lambda: [AlertType.FLASH])
    duration_ms: int = 2000
    color: str | None = None  # Override color, or use severity default
    repeat: int = 1  # Number of times to repeat

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for transmission."""
        return {
            "message": self.message,
            "severity": self.severity.value,
            "alert_types": [t.value for t in self.alert_types],
            "duration_ms": self.duration_ms,
            "color": self.color or self._get_severity_color(),
            "repeat": self.repeat,
        }

    def _get_severity_color(self) -> str:
        """Get default color for severity level."""
        colors = {
            AlertSeverity.INFO: "#3498db",  # Blue
            AlertSeverity.SUCCESS: "#2ecc71",  # Green
            AlertSeverity.WARNING: "#f1c40f",  # Yellow
            AlertSeverity.ERROR: "#e74c3c",  # Red
            AlertSeverity.CRITICAL: "#9b59b6",  # Purple (high visibility)
        }
        return colors.get(self.severity, "#3498db")


@dataclass
class SimplifiedModeConfig:
    """Configuration for simplified mode (elder-friendly UI).

    Simplified mode reduces cognitive load by:
    - Showing larger tap targets
    - Reducing the number of visible options
    - Using clearer, simpler language
    - Removing animations
    - Providing audio feedback
    """

    enabled: bool = False

    # Visual adjustments
    larger_buttons: bool = True  # Minimum 48dp tap targets → 64dp
    larger_text: bool = True  # Base text size increase
    text_scale_factor: float = 1.3  # 130% of normal text size
    high_contrast: bool = True
    reduce_motion: bool = True

    # Content simplification
    hide_advanced_options: bool = True
    max_visible_devices_per_room: int = 6
    max_visible_scenes: int = 4
    show_only_favorites: bool = True

    # Feedback
    audio_feedback: bool = True  # Speak confirmations
    haptic_feedback: bool = True  # Vibrate on actions
    confirmation_prompts: bool = True  # "Are you sure?" prompts

    # Safety
    emergency_button_visible: bool = True
    check_in_reminders: bool = False  # Daily check-in with family

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "enabled": self.enabled,
            "larger_buttons": self.larger_buttons,
            "larger_text": self.larger_text,
            "text_scale_factor": self.text_scale_factor,
            "high_contrast": self.high_contrast,
            "reduce_motion": self.reduce_motion,
            "hide_advanced_options": self.hide_advanced_options,
            "max_visible_devices_per_room": self.max_visible_devices_per_room,
            "max_visible_scenes": self.max_visible_scenes,
            "show_only_favorites": self.show_only_favorites,
            "audio_feedback": self.audio_feedback,
            "haptic_feedback": self.haptic_feedback,
            "confirmation_prompts": self.confirmation_prompts,
            "emergency_button_visible": self.emergency_button_visible,
            "check_in_reminders": self.check_in_reminders,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SimplifiedModeConfig:
        """Create from dictionary."""
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class AccessibilityPreferences:
    """User's accessibility preferences."""

    # Visual
    reduce_motion: bool = False
    high_contrast: bool = False
    increase_contrast: float = 0.0  # Additional contrast boost (0-1)
    color_blind_mode: str | None = None  # "protanopia", "deuteranopia", "tritanopia"
    dark_mode: bool | None = None  # None = system default

    # Text
    text_scale_factor: float = 1.0  # 1.0 = normal, 1.5 = 150%
    bold_text: bool = False

    # Audio
    screen_reader_enabled: bool = False
    speak_notifications: bool = False
    speak_confirmations: bool = False

    # Interaction
    touch_accommodations: bool = False  # Ignore accidental touches
    hold_duration_ms: int = 500  # Long-press threshold
    dwell_control: bool = False  # Trigger on hover/dwell
    dwell_time_ms: int = 1000

    # Visual alerts (for deaf/hard-of-hearing)
    visual_alerts_enabled: bool = False
    flash_screen: bool = True
    vibration_alerts: bool = True

    # Simplified mode
    simplified_mode: SimplifiedModeConfig = field(default_factory=SimplifiedModeConfig)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "reduce_motion": self.reduce_motion,
            "high_contrast": self.high_contrast,
            "increase_contrast": self.increase_contrast,
            "color_blind_mode": self.color_blind_mode,
            "dark_mode": self.dark_mode,
            "text_scale_factor": self.text_scale_factor,
            "bold_text": self.bold_text,
            "screen_reader_enabled": self.screen_reader_enabled,
            "speak_notifications": self.speak_notifications,
            "speak_confirmations": self.speak_confirmations,
            "touch_accommodations": self.touch_accommodations,
            "hold_duration_ms": self.hold_duration_ms,
            "dwell_control": self.dwell_control,
            "dwell_time_ms": self.dwell_time_ms,
            "visual_alerts_enabled": self.visual_alerts_enabled,
            "flash_screen": self.flash_screen,
            "vibration_alerts": self.vibration_alerts,
            "simplified_mode": self.simplified_mode.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AccessibilityPreferences:
        """Create from dictionary."""
        # Handle nested SimplifiedModeConfig
        simplified_data = data.pop("simplified_mode", None)
        prefs = cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
        if simplified_data:
            prefs.simplified_mode = SimplifiedModeConfig.from_dict(simplified_data)
        return prefs


class AccessibilityManager:
    """Central manager for accessibility features.

    Coordinates all accessibility features for a user, including:
    - Loading/saving preferences
    - Dispatching visual alerts
    - Managing simplified mode
    - Screen reader announcements
    """

    def __init__(self, user_id: str):
        """Initialize accessibility manager.

        Args:
            user_id: User identifier
        """
        self.user_id = user_id
        self.preferences = AccessibilityPreferences()
        self._alert_handlers: list[Callable[[VisualAlert], None]] = []
        self._announcement_handlers: list[Callable[[str, str], None]] = []
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize and load user preferences."""
        if self._initialized:
            return

        # Load preferences from cache/database
        try:
            from kagami.core.caching.offline import get_offline_cache

            cache = get_offline_cache(self.user_id)
            await cache.initialize()

            saved_prefs = await cache.get_preference("accessibility")
            if saved_prefs:
                self.preferences = AccessibilityPreferences.from_dict(saved_prefs)
                logger.debug(f"Loaded accessibility preferences for user {self.user_id}")
        except Exception as e:
            logger.warning(f"Failed to load accessibility preferences: {e}")

        self._initialized = True

    async def save_preferences(self) -> None:
        """Save current preferences."""
        try:
            from kagami.core.caching.offline import get_offline_cache

            cache = get_offline_cache(self.user_id)
            await cache.initialize()
            await cache.store_preference("accessibility", self.preferences.to_dict())
            logger.debug(f"Saved accessibility preferences for user {self.user_id}")
        except Exception as e:
            logger.error(f"Failed to save accessibility preferences: {e}")

    @property
    def simplified_mode_enabled(self) -> bool:
        """Check if simplified mode is enabled."""
        return self.preferences.simplified_mode.enabled

    @property
    def should_reduce_motion(self) -> bool:
        """Check if motion should be reduced."""
        return self.preferences.reduce_motion or self.preferences.simplified_mode.reduce_motion

    @property
    def visual_alerts_enabled(self) -> bool:
        """Check if visual alerts are enabled."""
        return self.preferences.visual_alerts_enabled

    def register_alert_handler(self, handler: Callable[[VisualAlert], None]) -> None:
        """Register a handler for visual alerts.

        Client apps register handlers to display visual alerts in their UI.

        Args:
            handler: Function that receives VisualAlert objects
        """
        self._alert_handlers.append(handler)

    def register_announcement_handler(
        self,
        handler: Callable[[str, str], None],
    ) -> None:
        """Register a handler for screen reader announcements.

        Args:
            handler: Function that receives (message, priority)
        """
        self._announcement_handlers.append(handler)

    async def send_visual_alert(self, alert: VisualAlert) -> None:
        """Send a visual alert to all registered handlers.

        Args:
            alert: Visual alert configuration
        """
        if not self.visual_alerts_enabled:
            return

        for handler in self._alert_handlers:
            try:
                handler(alert)
            except Exception as e:
                logger.error(f"Alert handler error: {e}")

    async def announce(
        self,
        message: str,
        priority: str = "polite",
    ) -> None:
        """Announce a message to screen readers.

        Args:
            message: Message to announce
            priority: "polite" (wait for idle) or "assertive" (interrupt)
        """
        if not self.preferences.screen_reader_enabled:
            return

        for handler in self._announcement_handlers:
            try:
                handler(message, priority)
            except Exception as e:
                logger.error(f"Announcement handler error: {e}")

    def get_text_scale(self) -> float:
        """Get the effective text scale factor."""
        base_scale = self.preferences.text_scale_factor
        if self.preferences.simplified_mode.enabled:
            base_scale = max(base_scale, self.preferences.simplified_mode.text_scale_factor)
        return base_scale

    def get_minimum_tap_target(self) -> int:
        """Get the minimum tap target size in dp."""
        if (
            self.preferences.simplified_mode.enabled
            and self.preferences.simplified_mode.larger_buttons
        ):
            return 64  # WCAG AAA: larger targets for motor impairments
        return 48  # WCAG AA minimum

    def should_show_confirmation(self, action: str) -> bool:
        """Check if a confirmation prompt should be shown for an action.

        Args:
            action: Action identifier (e.g., "lock_door", "turn_off_lights")

        Returns:
            True if confirmation should be shown
        """
        if not self.preferences.simplified_mode.confirmation_prompts:
            return False

        # Always confirm destructive or security actions
        confirmation_actions = [
            "lock_door",
            "unlock_door",
            "arm_security",
            "disarm_security",
            "delete",
            "remove",
            "emergency",
            "call",
        ]
        return any(action.startswith(a) for a in confirmation_actions)


# Module-level convenience functions

_managers: dict[str, AccessibilityManager] = {}


def get_accessibility_manager(user_id: str) -> AccessibilityManager:
    """Get or create an accessibility manager for a user.

    Args:
        user_id: User identifier

    Returns:
        AccessibilityManager instance
    """
    if user_id not in _managers:
        _managers[user_id] = AccessibilityManager(user_id)
    return _managers[user_id]


async def visual_alert(
    message: str,
    severity: str = "info",
    user_id: str | None = None,
) -> None:
    """Send a visual alert.

    Convenience function for sending visual alerts. If no user_id is provided,
    sends to all registered managers.

    Args:
        message: Alert message
        severity: Severity level ("info", "success", "warning", "error", "critical")
        user_id: Optional specific user
    """
    alert = VisualAlert(
        message=message,
        severity=AlertSeverity(severity),
    )

    if user_id:
        manager = get_accessibility_manager(user_id)
        await manager.send_visual_alert(alert)
    else:
        # Send to all managers in parallel
        await asyncio.gather(
            *[manager.send_visual_alert(alert) for manager in _managers.values()],
            return_exceptions=True,
        )


def check_contrast(
    foreground: str,
    background: str,
    level: str = "AA",
) -> bool:
    """Check if two colors meet WCAG contrast requirements.

    Args:
        foreground: Foreground color (hex string, e.g., "#ffffff")
        background: Background color (hex string)
        level: WCAG level - "AA" (4.5:1) or "AAA" (7:1)

    Returns:
        True if contrast meets the specified level
    """
    from kagami.core.accessibility.contrast import calculate_contrast_ratio

    ratio = calculate_contrast_ratio(foreground, background)

    required_ratio = 7.0 if level == "AAA" else 4.5
    return ratio >= required_ratio


def should_reduce_motion(user_id: str | None = None) -> bool:
    """Check if motion should be reduced.

    Args:
        user_id: Optional user identifier

    Returns:
        True if motion should be reduced
    """
    if user_id and user_id in _managers:
        return _managers[user_id].should_reduce_motion

    # Default: check any manager or return False
    for manager in _managers.values():
        if manager.should_reduce_motion:
            return True
    return False


__all__ = [
    "AccessibilityManager",
    "AccessibilityPreferences",
    "AlertSeverity",
    "AlertType",
    "SimplifiedModeConfig",
    "VisualAlert",
    "check_contrast",
    "get_accessibility_manager",
    "should_reduce_motion",
    "visual_alert",
]
