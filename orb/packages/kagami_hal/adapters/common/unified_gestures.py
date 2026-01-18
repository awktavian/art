"""Unified Cross-Device Gesture Vocabulary.

Provides a consistent gesture language across all Kagami devices:
- Apple Watch (Crown, tap)
- Vision Pro (Pinch, gaze, hand tracking)
- Meta Glasses (Temple tap, head movements)
- iOS/Android (Touch, shake)
- Desktop (Keyboard, mouse)

Design Principles:
1. Same action, any device: "Primary action" works everywhere
2. Progressive disclosure: Basic gestures are universal, advanced are optional
3. Modality-appropriate: Each device uses its natural interaction
4. Learnable: Consistent mental model

Gesture Categories:
- Primary Action: Confirm, select, execute
- Secondary Action: Cancel, back, menu
- Voice Input: Activate voice assistant
- Brightness: Adjust ambient light
- Volume: Adjust audio
- Navigation: Next/previous, scroll
- Quick Actions: Shortcuts to common operations

Created: December 30, 2025
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class DeviceType(Enum):
    """Device types supporting gestures."""

    WATCH = "watch"  # Apple Watch
    VISION = "vision"  # Vision Pro
    GLASSES = "glasses"  # Meta Ray-Ban
    NEURAL_BAND = "neural_band"  # Meta Neural Band (sEMG wristband)
    PHONE = "phone"  # iOS/Android
    DESKTOP = "desktop"  # macOS/Windows
    HUB = "hub"  # Kagami Hub (voice only)
    ANDROID_XR = "android_xr"  # Android XR headsets


class GestureSource(Enum):
    """Gesture input source."""

    # Watch
    CROWN_TAP = "crown_tap"
    CROWN_DOUBLE_TAP = "crown_double_tap"
    CROWN_HOLD = "crown_hold"
    CROWN_SCROLL = "crown_scroll"
    WATCH_TAP = "watch_tap"
    WATCH_DOUBLE_TAP = "watch_double_tap"
    RAISE_WRIST = "raise_wrist"

    # Vision Pro
    PINCH = "pinch"
    PINCH_HOLD = "pinch_hold"
    DOUBLE_PINCH = "double_pinch"
    GAZE_DWELL = "gaze_dwell"
    HAND_SWIPE_UP = "hand_swipe_up"
    HAND_SWIPE_DOWN = "hand_swipe_down"
    HAND_SWIPE_LEFT = "hand_swipe_left"
    HAND_SWIPE_RIGHT = "hand_swipe_right"

    # Meta Glasses
    TEMPLE_TAP = "temple_tap"
    TEMPLE_DOUBLE_TAP = "temple_double_tap"
    TEMPLE_HOLD = "temple_hold"
    HEAD_TILT_UP = "head_tilt_up"
    HEAD_TILT_DOWN = "head_tilt_down"
    HEAD_NOD = "head_nod"
    HEAD_SHAKE = "head_shake"

    # Phone/Tablet
    SCREEN_TAP = "screen_tap"
    SCREEN_DOUBLE_TAP = "screen_double_tap"
    SCREEN_HOLD = "screen_hold"
    SCREEN_SWIPE_UP = "screen_swipe_up"
    SCREEN_SWIPE_DOWN = "screen_swipe_down"
    PHONE_SHAKE = "phone_shake"

    # Desktop
    KEYBOARD_SHORTCUT = "keyboard_shortcut"
    HOTKEY = "hotkey"
    MOUSE_CLICK = "mouse_click"
    MOUSE_DOUBLE_CLICK = "mouse_double_click"

    # Voice (all devices)
    VOICE_WAKE = "voice_wake"
    VOICE_COMMAND = "voice_command"

    # Meta Neural Band (EMG wristband)
    EMG_THUMB_TAP = "emg_thumb_tap"
    EMG_THUMB_DOUBLE_TAP = "emg_thumb_double_tap"
    EMG_THUMB_SWIPE_LEFT = "emg_thumb_swipe_left"
    EMG_THUMB_SWIPE_RIGHT = "emg_thumb_swipe_right"
    EMG_THUMB_SWIPE_FORWARD = "emg_thumb_swipe_forward"
    EMG_THUMB_SWIPE_BACKWARD = "emg_thumb_swipe_backward"
    EMG_PINCH_INDEX = "emg_pinch_index"
    EMG_PINCH_HOLD = "emg_pinch_hold"
    EMG_PINCH_RELEASE = "emg_pinch_release"
    EMG_WRIST_ROTATE_CW = "emg_wrist_rotate_cw"
    EMG_WRIST_ROTATE_CCW = "emg_wrist_rotate_ccw"

    # Android XR (hand tracking)
    XR_PINCH = "xr_pinch"
    XR_POINT = "xr_point"
    XR_FIST = "xr_fist"
    XR_OPEN_PALM = "xr_open_palm"
    XR_THUMBS_UP = "xr_thumbs_up"
    XR_EMERGENCY_STOP = "xr_emergency_stop"


class GestureAction(Enum):
    """Semantic actions that gestures map to."""

    # Primary
    PRIMARY_ACTION = "primary_action"  # Confirm, select, execute
    SECONDARY_ACTION = "secondary_action"  # Cancel, back, menu

    # Voice
    VOICE_INPUT = "voice_input"  # Activate voice assistant
    VOICE_CANCEL = "voice_cancel"  # Cancel voice input

    # Adjustments
    BRIGHTNESS_UP = "brightness_up"
    BRIGHTNESS_DOWN = "brightness_down"
    VOLUME_UP = "volume_up"
    VOLUME_DOWN = "volume_down"

    # Navigation
    NEXT = "next"
    PREVIOUS = "previous"
    SCROLL_UP = "scroll_up"
    SCROLL_DOWN = "scroll_down"
    GO_BACK = "go_back"
    GO_HOME = "go_home"

    # Quick Actions
    QUICK_ACTION_1 = "quick_action_1"  # First quick action slot
    QUICK_ACTION_2 = "quick_action_2"
    QUICK_ACTION_3 = "quick_action_3"

    # System
    DISMISS = "dismiss"
    SHOW_MENU = "show_menu"
    TOGGLE_MODE = "toggle_mode"


@dataclass
class Gesture:
    """A detected gesture from a device."""

    source: GestureSource
    device_type: DeviceType
    timestamp: float
    confidence: float = 1.0

    # Optional modifiers
    modifiers: list[str] = field(default_factory=list)

    # For scrolls/swipes
    magnitude: float = 0.0
    direction: str | None = None

    # For holds
    duration_ms: int = 0

    # Raw data from device
    raw_data: dict[str, Any] = field(default_factory=dict)


@dataclass
class GestureBinding:
    """Maps a gesture source to an action for a device type."""

    source: GestureSource
    action: GestureAction
    device_type: DeviceType

    # Optional constraints
    modifiers: list[str] = field(default_factory=list)
    min_duration_ms: int = 0
    max_duration_ms: int = 0
    min_magnitude: float = 0.0

    # Description for users
    description: str = ""


# Default gesture bindings across devices
DEFAULT_BINDINGS: list[GestureBinding] = [
    # =========================================================================
    # PRIMARY ACTION (Double tap = confirm)
    # =========================================================================
    GestureBinding(
        source=GestureSource.CROWN_DOUBLE_TAP,
        action=GestureAction.PRIMARY_ACTION,
        device_type=DeviceType.WATCH,
        description="Double tap crown to confirm",
    ),
    GestureBinding(
        source=GestureSource.DOUBLE_PINCH,
        action=GestureAction.PRIMARY_ACTION,
        device_type=DeviceType.VISION,
        description="Double pinch to confirm",
    ),
    GestureBinding(
        source=GestureSource.TEMPLE_DOUBLE_TAP,
        action=GestureAction.PRIMARY_ACTION,
        device_type=DeviceType.GLASSES,
        description="Double tap temple to confirm",
    ),
    GestureBinding(
        source=GestureSource.SCREEN_DOUBLE_TAP,
        action=GestureAction.PRIMARY_ACTION,
        device_type=DeviceType.PHONE,
        description="Double tap to confirm",
    ),
    # =========================================================================
    # VOICE INPUT (Hold = voice)
    # =========================================================================
    GestureBinding(
        source=GestureSource.CROWN_HOLD,
        action=GestureAction.VOICE_INPUT,
        device_type=DeviceType.WATCH,
        min_duration_ms=500,
        description="Hold crown for voice input",
    ),
    GestureBinding(
        source=GestureSource.PINCH_HOLD,
        action=GestureAction.VOICE_INPUT,
        device_type=DeviceType.VISION,
        min_duration_ms=500,
        description="Hold pinch for voice input",
    ),
    GestureBinding(
        source=GestureSource.TEMPLE_HOLD,
        action=GestureAction.VOICE_INPUT,
        device_type=DeviceType.GLASSES,
        min_duration_ms=500,
        description="Hold temple for voice input",
    ),
    GestureBinding(
        source=GestureSource.SCREEN_HOLD,
        action=GestureAction.VOICE_INPUT,
        device_type=DeviceType.PHONE,
        min_duration_ms=500,
        description="Long press for voice input",
    ),
    # =========================================================================
    # BRIGHTNESS (Swipe/tilt up/down)
    # =========================================================================
    GestureBinding(
        source=GestureSource.CROWN_SCROLL,
        action=GestureAction.BRIGHTNESS_UP,
        device_type=DeviceType.WATCH,
        modifiers=["up"],
        description="Scroll crown up for brightness+",
    ),
    GestureBinding(
        source=GestureSource.CROWN_SCROLL,
        action=GestureAction.BRIGHTNESS_DOWN,
        device_type=DeviceType.WATCH,
        modifiers=["down"],
        description="Scroll crown down for brightness-",
    ),
    GestureBinding(
        source=GestureSource.HAND_SWIPE_UP,
        action=GestureAction.BRIGHTNESS_UP,
        device_type=DeviceType.VISION,
        description="Swipe hand up for brightness+",
    ),
    GestureBinding(
        source=GestureSource.HAND_SWIPE_DOWN,
        action=GestureAction.BRIGHTNESS_DOWN,
        device_type=DeviceType.VISION,
        description="Swipe hand down for brightness-",
    ),
    GestureBinding(
        source=GestureSource.HEAD_TILT_UP,
        action=GestureAction.BRIGHTNESS_UP,
        device_type=DeviceType.GLASSES,
        description="Tilt head up for brightness+",
    ),
    GestureBinding(
        source=GestureSource.HEAD_TILT_DOWN,
        action=GestureAction.BRIGHTNESS_DOWN,
        device_type=DeviceType.GLASSES,
        description="Tilt head down for brightness-",
    ),
    GestureBinding(
        source=GestureSource.SCREEN_SWIPE_UP,
        action=GestureAction.BRIGHTNESS_UP,
        device_type=DeviceType.PHONE,
        description="Swipe up for brightness+",
    ),
    GestureBinding(
        source=GestureSource.SCREEN_SWIPE_DOWN,
        action=GestureAction.BRIGHTNESS_DOWN,
        device_type=DeviceType.PHONE,
        description="Swipe down for brightness-",
    ),
    # =========================================================================
    # NAVIGATION (Single tap = next, back gestures)
    # =========================================================================
    GestureBinding(
        source=GestureSource.CROWN_TAP,
        action=GestureAction.NEXT,
        device_type=DeviceType.WATCH,
        description="Tap crown for next",
    ),
    GestureBinding(
        source=GestureSource.PINCH,
        action=GestureAction.PRIMARY_ACTION,
        device_type=DeviceType.VISION,
        description="Pinch to select",
    ),
    GestureBinding(
        source=GestureSource.TEMPLE_TAP,
        action=GestureAction.NEXT,
        device_type=DeviceType.GLASSES,
        description="Tap temple for next",
    ),
    GestureBinding(
        source=GestureSource.SCREEN_TAP,
        action=GestureAction.PRIMARY_ACTION,
        device_type=DeviceType.PHONE,
        description="Tap to select",
    ),
    # =========================================================================
    # GO BACK (Shake/nod = dismiss)
    # =========================================================================
    GestureBinding(
        source=GestureSource.PHONE_SHAKE,
        action=GestureAction.GO_BACK,
        device_type=DeviceType.PHONE,
        description="Shake to go back",
    ),
    GestureBinding(
        source=GestureSource.HEAD_SHAKE,
        action=GestureAction.DISMISS,
        device_type=DeviceType.GLASSES,
        description="Shake head to dismiss",
    ),
    GestureBinding(
        source=GestureSource.HEAD_NOD,
        action=GestureAction.PRIMARY_ACTION,
        device_type=DeviceType.GLASSES,
        description="Nod to confirm",
    ),
    # =========================================================================
    # VOICE WAKE (Wake word)
    # =========================================================================
    GestureBinding(
        source=GestureSource.VOICE_WAKE,
        action=GestureAction.VOICE_INPUT,
        device_type=DeviceType.WATCH,
        description='Say "Hey Kagami"',
    ),
    GestureBinding(
        source=GestureSource.VOICE_WAKE,
        action=GestureAction.VOICE_INPUT,
        device_type=DeviceType.VISION,
        description='Say "Hey Kagami"',
    ),
    GestureBinding(
        source=GestureSource.VOICE_WAKE,
        action=GestureAction.VOICE_INPUT,
        device_type=DeviceType.GLASSES,
        description='Say "Hey Kagami"',
    ),
    GestureBinding(
        source=GestureSource.VOICE_WAKE,
        action=GestureAction.VOICE_INPUT,
        device_type=DeviceType.PHONE,
        description='Say "Hey Kagami"',
    ),
    GestureBinding(
        source=GestureSource.VOICE_WAKE,
        action=GestureAction.VOICE_INPUT,
        device_type=DeviceType.HUB,
        description='Say "Hey Kagami"',
    ),
    # =========================================================================
    # META NEURAL BAND (EMG wristband)
    # =========================================================================
    GestureBinding(
        source=GestureSource.EMG_THUMB_TAP,
        action=GestureAction.PRIMARY_ACTION,
        device_type=DeviceType.NEURAL_BAND,
        description="Thumb tap to select",
    ),
    GestureBinding(
        source=GestureSource.EMG_THUMB_DOUBLE_TAP,
        action=GestureAction.TOGGLE_MODE,
        device_type=DeviceType.NEURAL_BAND,
        description="Double tap to toggle",
    ),
    GestureBinding(
        source=GestureSource.EMG_THUMB_SWIPE_LEFT,
        action=GestureAction.PREVIOUS,
        device_type=DeviceType.NEURAL_BAND,
        description="Swipe left for previous",
    ),
    GestureBinding(
        source=GestureSource.EMG_THUMB_SWIPE_RIGHT,
        action=GestureAction.NEXT,
        device_type=DeviceType.NEURAL_BAND,
        description="Swipe right for next",
    ),
    GestureBinding(
        source=GestureSource.EMG_THUMB_SWIPE_FORWARD,
        action=GestureAction.SCROLL_UP,
        device_type=DeviceType.NEURAL_BAND,
        description="Swipe forward to scroll up",
    ),
    GestureBinding(
        source=GestureSource.EMG_THUMB_SWIPE_BACKWARD,
        action=GestureAction.SCROLL_DOWN,
        device_type=DeviceType.NEURAL_BAND,
        description="Swipe backward to scroll down",
    ),
    GestureBinding(
        source=GestureSource.EMG_PINCH_INDEX,
        action=GestureAction.PRIMARY_ACTION,
        device_type=DeviceType.NEURAL_BAND,
        description="Pinch to select",
    ),
    GestureBinding(
        source=GestureSource.EMG_PINCH_HOLD,
        action=GestureAction.VOICE_INPUT,
        device_type=DeviceType.NEURAL_BAND,
        min_duration_ms=500,
        description="Hold pinch for voice input",
    ),
    GestureBinding(
        source=GestureSource.EMG_WRIST_ROTATE_CW,
        action=GestureAction.VOLUME_UP,
        device_type=DeviceType.NEURAL_BAND,
        description="Rotate wrist clockwise for volume up",
    ),
    GestureBinding(
        source=GestureSource.EMG_WRIST_ROTATE_CCW,
        action=GestureAction.VOLUME_DOWN,
        device_type=DeviceType.NEURAL_BAND,
        description="Rotate wrist counter-clockwise for volume down",
    ),
    GestureBinding(
        source=GestureSource.VOICE_WAKE,
        action=GestureAction.VOICE_INPUT,
        device_type=DeviceType.NEURAL_BAND,
        description='Say "Hey Kagami"',
    ),
    # =========================================================================
    # ANDROID XR (Hand tracking)
    # =========================================================================
    GestureBinding(
        source=GestureSource.XR_PINCH,
        action=GestureAction.PRIMARY_ACTION,
        device_type=DeviceType.ANDROID_XR,
        description="Pinch to select",
    ),
    GestureBinding(
        source=GestureSource.XR_POINT,
        action=GestureAction.NEXT,
        device_type=DeviceType.ANDROID_XR,
        description="Point to focus",
    ),
    GestureBinding(
        source=GestureSource.XR_FIST,
        action=GestureAction.DISMISS,
        device_type=DeviceType.ANDROID_XR,
        description="Fist to dismiss",
    ),
    GestureBinding(
        source=GestureSource.XR_OPEN_PALM,
        action=GestureAction.SHOW_MENU,
        device_type=DeviceType.ANDROID_XR,
        description="Open palm to show menu",
    ),
    GestureBinding(
        source=GestureSource.XR_THUMBS_UP,
        action=GestureAction.PRIMARY_ACTION,
        device_type=DeviceType.ANDROID_XR,
        description="Thumbs up to confirm",
    ),
    GestureBinding(
        source=GestureSource.XR_EMERGENCY_STOP,
        action=GestureAction.DISMISS,
        device_type=DeviceType.ANDROID_XR,
        description="Two-hand stop for emergency",
    ),
    GestureBinding(
        source=GestureSource.VOICE_WAKE,
        action=GestureAction.VOICE_INPUT,
        device_type=DeviceType.ANDROID_XR,
        description='Say "Hey Kagami"',
    ),
]


GestureCallback = Callable[[Gesture, GestureAction], Awaitable[None]]


class GestureRegistry:
    """Registry for cross-device gesture bindings.

    Manages gesture-to-action mappings and provides unified gesture handling.

    Usage:
        registry = GestureRegistry()

        # Register callback for actions
        registry.on_action(GestureAction.PRIMARY_ACTION, handle_primary)

        # Process a gesture
        await registry.process_gesture(gesture)

        # Get bindings for a device
        bindings = registry.get_bindings_for_device(DeviceType.WATCH)
    """

    def __init__(self) -> None:
        self._bindings: list[GestureBinding] = list(DEFAULT_BINDINGS)
        self._callbacks: dict[GestureAction, list[GestureCallback]] = {}
        self._device_callbacks: dict[DeviceType, list[GestureCallback]] = {}

    def add_binding(self, binding: GestureBinding) -> None:
        """Add a custom gesture binding.

        Args:
            binding: GestureBinding to add
        """
        self._bindings.append(binding)
        logger.debug(f"Added gesture binding: {binding.source.value} -> {binding.action.value}")

    def remove_binding(self, source: GestureSource, device_type: DeviceType) -> bool:
        """Remove a gesture binding.

        Args:
            source: Gesture source to remove
            device_type: Device type

        Returns:
            True if removed
        """
        for i, binding in enumerate(self._bindings):
            if binding.source == source and binding.device_type == device_type:
                self._bindings.pop(i)
                return True
        return False

    def get_bindings_for_device(self, device_type: DeviceType) -> list[GestureBinding]:
        """Get all gesture bindings for a device type.

        Args:
            device_type: Device type to get bindings for

        Returns:
            List of GestureBinding
        """
        return [b for b in self._bindings if b.device_type == device_type]

    def get_bindings_for_action(self, action: GestureAction) -> list[GestureBinding]:
        """Get all bindings that produce an action.

        Args:
            action: Action to find bindings for

        Returns:
            List of GestureBinding
        """
        return [b for b in self._bindings if b.action == action]

    def lookup_action(self, gesture: Gesture) -> GestureAction | None:
        """Look up the action for a gesture.

        Args:
            gesture: Gesture to look up

        Returns:
            GestureAction if found, None otherwise
        """
        for binding in self._bindings:
            if binding.source != gesture.source:
                continue
            if binding.device_type != gesture.device_type:
                continue

            # Check modifiers
            if binding.modifiers:
                if not all(m in gesture.modifiers for m in binding.modifiers):
                    continue

            # Check duration constraints
            if binding.min_duration_ms > 0:
                if gesture.duration_ms < binding.min_duration_ms:
                    continue
            if binding.max_duration_ms > 0:
                if gesture.duration_ms > binding.max_duration_ms:
                    continue

            # Check magnitude
            if binding.min_magnitude > 0:
                if gesture.magnitude < binding.min_magnitude:
                    continue

            return binding.action

        return None

    async def process_gesture(self, gesture: Gesture) -> GestureAction | None:
        """Process a gesture and dispatch to callbacks.

        Args:
            gesture: Gesture to process

        Returns:
            GestureAction if matched and dispatched
        """
        action = self.lookup_action(gesture)

        if action:
            logger.debug(
                f"Gesture {gesture.source.value} ({gesture.device_type.value}) -> {action.value}"
            )

            # Dispatch to action callbacks
            for callback in self._callbacks.get(action, []):
                try:
                    await callback(gesture, action)
                except Exception as e:
                    logger.error(f"Gesture callback error: {e}")

            # Dispatch to device callbacks
            for callback in self._device_callbacks.get(gesture.device_type, []):
                try:
                    await callback(gesture, action)
                except Exception as e:
                    logger.error(f"Device gesture callback error: {e}")

        return action

    def on_action(self, action: GestureAction, callback: GestureCallback) -> None:
        """Register callback for an action.

        Args:
            action: Action to listen for
            callback: Async function to call
        """
        if action not in self._callbacks:
            self._callbacks[action] = []
        self._callbacks[action].append(callback)

    def on_device_gesture(self, device_type: DeviceType, callback: GestureCallback) -> None:
        """Register callback for all gestures from a device.

        Args:
            device_type: Device to listen for
            callback: Async function to call
        """
        if device_type not in self._device_callbacks:
            self._device_callbacks[device_type] = []
        self._device_callbacks[device_type].append(callback)

    def get_gesture_help(self, device_type: DeviceType) -> list[dict[str, str]]:
        """Get help text for all gestures on a device.

        Args:
            device_type: Device to get help for

        Returns:
            List of dicts with 'gesture', 'action', 'description'
        """
        bindings = self.get_bindings_for_device(device_type)
        return [
            {
                "gesture": b.source.value,
                "action": b.action.value,
                "description": b.description,
            }
            for b in bindings
        ]


# =============================================================================
# Factory
# =============================================================================

_registry: GestureRegistry | None = None


def get_gesture_registry() -> GestureRegistry:
    """Get or create gesture registry singleton."""
    global _registry
    if _registry is None:
        _registry = GestureRegistry()
    return _registry


__all__ = [
    "DEFAULT_BINDINGS",
    "DeviceType",
    "Gesture",
    "GestureAction",
    "GestureBinding",
    "GestureRegistry",
    "GestureSource",
    "get_gesture_registry",
]


"""
Mirror
h(x) >= 0. Always.

The gesture is the intent.
Same meaning, any device.
Consistent, learnable, natural.
"""
