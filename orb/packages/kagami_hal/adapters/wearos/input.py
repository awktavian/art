"""WearOS Input Adapter.

Implements input handling for Wear OS using Android APIs.

Features:
- Rotary input (crown/bezel)
- Touch gestures
- Physical buttons
- Haptic feedback (vibration)

Created: December 13, 2025
"""

from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import Awaitable, Callable
from typing import Any

from kagami.core.boot_mode import is_test_mode

from kagami_hal.data_types import InputEvent, InputType

logger = logging.getLogger(__name__)

WEAROS_AVAILABLE = "ANDROID_ARGUMENT" in os.environ or os.environ.get("KAGAMI_PLATFORM") == "wearos"


class WearOSInput:
    """Wear OS input adapter.

    Provides:
    - Rotary input (crown/rotating bezel)
    - Touch gestures
    - Button events
    - Vibration haptic feedback
    """

    def __init__(self):
        """Initialize WearOS input adapter."""
        self._vibrator: Any = None
        self._initialized = False
        self._subscribers: dict[InputType, list[Callable[[InputEvent], Awaitable[None]]]] = {}
        self._rotary_value: float = 0.0

    async def initialize(self, config: Any | None = None) -> bool:
        """Initialize input adapter."""
        if not WEAROS_AVAILABLE:
            if is_test_mode():
                logger.info("WearOS input not available, gracefully degrading")
                return False
            raise RuntimeError("WearOS input only available on Wear OS")

        try:
            from jnius import autoclass

            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            Context = autoclass("android.content.Context")

            activity = PythonActivity.mActivity
            self._vibrator = activity.getSystemService(Context.VIBRATOR_SERVICE)

            self._initialized = True
            logger.info("✅ WearOS input adapter initialized")
            return True

        except ImportError as e:
            logger.error(f"Pyjnius not available: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to initialize WearOS input: {e}", exc_info=True)
            return False

    async def shutdown(self) -> None:
        """Shutdown input adapter."""
        self._subscribers.clear()
        self._initialized = False
        logger.info("✅ WearOS input adapter shutdown")

    async def subscribe(
        self,
        input_type: InputType,
        callback: Callable[[InputEvent], Awaitable[None]],
    ) -> None:
        """Subscribe to input events."""
        if input_type not in self._subscribers:
            self._subscribers[input_type] = []
        self._subscribers[input_type].append(callback)

    async def unsubscribe(self, input_type: InputType) -> None:
        """Unsubscribe from input events."""
        self._subscribers.pop(input_type, None)

    async def read_event(self) -> InputEvent | None:
        """Read next input event (non-blocking)."""
        return None

    async def inject_event(self, type: InputType, code: int, value: int) -> bool:
        """Inject synthetic input event."""
        logger.debug(f"Input injection not available on WearOS: {type}, {code}")
        return False

    # =========================================================================
    # Rotary Input (Crown/Bezel)
    # =========================================================================

    async def on_rotary_scroll(self, delta: float) -> None:
        """Handle rotary input (crown or rotating bezel).

        Called when the user rotates the crown or bezel.

        Args:
            delta: Rotation delta (negative = counterclockwise)
        """
        self._rotary_value += delta

        event = InputEvent(
            type=InputType.GESTURE,
            code=2000,  # Custom code for rotary
            value=int(delta * 100),
            timestamp_ms=int(asyncio.get_event_loop().time() * 1000),
        )

        for callback in self._subscribers.get(InputType.GESTURE, []):
            try:
                await callback(event)
            except Exception as e:
                logger.error(f"Error in rotary callback: {e}")

    @property
    def rotary_value(self) -> float:
        """Get accumulated rotary value."""
        return self._rotary_value

    def reset_rotary(self) -> None:
        """Reset rotary value to zero."""
        self._rotary_value = 0.0

    # =========================================================================
    # Physical Buttons
    # =========================================================================

    async def on_button_press(self, key_code: int) -> None:
        """Handle physical button press.

        Common key codes:
        - KEYCODE_STEM_1 (265): Main button
        - KEYCODE_STEM_2 (266): Secondary button (if present)
        - KEYCODE_STEM_3 (267): Third button (if present)
        """
        event = InputEvent(
            type=InputType.BUTTON,
            code=key_code,
            value=1,
            timestamp_ms=int(asyncio.get_event_loop().time() * 1000),
        )

        for callback in self._subscribers.get(InputType.BUTTON, []):
            try:
                await callback(event)
            except Exception as e:
                logger.error(f"Error in button callback: {e}")

    # =========================================================================
    # Haptic Feedback (Vibration)
    # =========================================================================

    async def vibrate(self, duration_ms: int = 50, amplitude: int = 255) -> None:
        """Vibrate for a duration.

        Args:
            duration_ms: Vibration duration in milliseconds
            amplitude: Vibration strength (1-255)
        """
        if not self._vibrator:
            return

        try:
            from jnius import autoclass

            VibrationEffect = autoclass("android.os.VibrationEffect")

            amplitude = max(1, min(255, amplitude))
            effect = VibrationEffect.createOneShot(duration_ms, amplitude)
            self._vibrator.vibrate(effect)

            logger.debug(f"Vibration: {duration_ms}ms, amplitude={amplitude}")

        except Exception as e:
            logger.error(f"Failed to vibrate: {e}")

    async def vibrate_pattern(
        self,
        pattern: list[int],
        amplitudes: list[int] | None = None,
        repeat: int = -1,
    ) -> None:
        """Vibrate with a pattern.

        Args:
            pattern: List of durations [wait, vibrate, wait, vibrate, ...]
            amplitudes: Optional amplitude for each vibration segment
            repeat: Index to repeat from (-1 = no repeat)
        """
        if not self._vibrator:
            return

        try:
            from jnius import autoclass

            VibrationEffect = autoclass("android.os.VibrationEffect")

            if amplitudes:
                effect = VibrationEffect.createWaveform(pattern, amplitudes, repeat)
            else:
                effect = VibrationEffect.createWaveform(pattern, repeat)

            self._vibrator.vibrate(effect)

        except Exception as e:
            logger.error(f"Failed to vibrate pattern: {e}")

    async def cancel_vibration(self) -> None:
        """Cancel ongoing vibration."""
        if self._vibrator:
            self._vibrator.cancel()

    # Convenience haptic methods
    async def haptic_click(self) -> None:
        """Light click feedback."""
        await self.vibrate(20, 128)

    async def haptic_confirm(self) -> None:
        """Confirmation feedback."""
        await self.vibrate_pattern([0, 30, 50, 30], [0, 200, 0, 200])

    async def haptic_reject(self) -> None:
        """Rejection feedback."""
        await self.vibrate_pattern([0, 50, 30, 50, 30, 50], [0, 255, 0, 255, 0, 255])

    async def haptic_notification(self) -> None:
        """Notification feedback."""
        await self.vibrate(100, 180)

    # =========================================================================
    # Gesture Support
    # =========================================================================

    @property
    def supports_rotary(self) -> bool:
        """Check if device has rotary input (crown or bezel)."""
        # Most Wear OS 3.0+ devices have rotary input
        return True

    @property
    def has_rotating_bezel(self) -> bool:
        """Check if device has physical rotating bezel (Galaxy Watch)."""
        try:
            from jnius import autoclass

            Build = autoclass("android.os.Build")
            manufacturer = Build.MANUFACTURER.lower()
            return "samsung" in manufacturer
        except Exception:
            return False
