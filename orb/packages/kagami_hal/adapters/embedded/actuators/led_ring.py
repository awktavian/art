"""鏡 LED Ring Actuator with RTE Backend.

WS2812/NeoPixel LED ring actuator that uses the RTE subsystem for
deterministic timing. Falls back gracefully when no RTE is available.

Usage:
    from kagami_hal.adapters.embedded.actuators import LEDRingActuator
    from kagami_hal.rte import PicoRTE

    # With Pico coprocessor
    rte = PicoRTE("/dev/ttyACM0")
    led_ring = LEDRingActuator(rte=rte)

    # Or auto-select best backend
    led_ring = LEDRingActuator()

    await led_ring.initialize()
    await led_ring.set_pattern(LEDPattern.BREATHING)
    await led_ring.set_brightness(200)

Created: January 2, 2026
Colony: Nexus (e₄) — Bridge between digital and physical
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from kagami_hal.interface.actuators import ActuatorConstraints, ActuatorType, IActuator
from kagami_hal.rte.protocol import RTEBackend, RTECommand
from kagami_hal.rte.types import LEDPattern, RTEEvent, RTEStatus

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class LEDRingActuator(IActuator):
    """LED ring actuator using RTE backend.

    Provides high-level control of WS2812/NeoPixel LED rings with
    deterministic timing through the Real-Time Executor subsystem.

    Features:
    - 16 built-in animation patterns
    - Brightness control (0-255)
    - Color override (RGB)
    - Safety status display (h(x) visualization)
    - 60fps animation (with Pico RTE)

    Attributes:
        led_count: Number of LEDs in the ring
        rte: RTE backend for timing-critical operations
    """

    def __init__(
        self,
        led_count: int = 12,
        rte: RTEBackend | None = None,
    ):
        """Initialize LED ring actuator.

        Args:
            led_count: Number of LEDs in the ring
            rte: RTE backend to use, or None to auto-select
        """
        self._led_count = led_count
        self._rte = rte
        self._initialized = False

        # State
        self._pattern = LEDPattern.IDLE
        self._brightness = 128
        self._color: tuple[int, int, int] | None = None

        # Constraints
        self._constraints = ActuatorConstraints(
            actuator_type=ActuatorType.LED,
            min_value=0.0,
            max_value=255.0,
            rate_limit=100.0,  # Max 100 updates per second
        )

    @property
    def led_count(self) -> int:
        """Get number of LEDs in the ring."""
        return self._led_count

    @property
    def pattern(self) -> LEDPattern:
        """Get current pattern."""
        return self._pattern

    @property
    def brightness(self) -> int:
        """Get current brightness (0-255)."""
        return self._brightness

    async def initialize(self, config: dict | None = None) -> bool:
        """Initialize LED ring with RTE backend.

        Args:
            config: Optional configuration dict

        Returns:
            True if initialization succeeded
        """
        # If no RTE provided, auto-select
        if self._rte is None:
            from kagami_hal.rte import get_rte_backend

            self._rte = await get_rte_backend()

        # Initialize RTE if not already initialized
        if not self._rte.is_connected():
            if not await self._rte.initialize():
                logger.warning("RTE initialization failed, LED ring may not work")
                return False

        # Set initial state
        await self._rte.send_command(RTECommand.LED_PATTERN, self._pattern)
        await self._rte.send_command(RTECommand.LED_BRIGHTNESS, self._brightness)

        self._initialized = True
        logger.info(f"✓ LED ring initialized ({self._led_count} LEDs)")
        return True

    async def shutdown(self) -> None:
        """Shutdown LED ring."""
        if self._rte and self._initialized:
            try:
                # Turn off LEDs
                await self._rte.send_command(RTECommand.LED_PATTERN, LEDPattern.IDLE)
                await self._rte.send_command(RTECommand.LED_BRIGHTNESS, 0)
            except Exception as e:
                logger.warning(f"Error shutting down LED ring: {e}")

        self._initialized = False
        logger.info("LED ring shutdown complete")

    async def get_constraints(self) -> ActuatorConstraints:
        """Get actuator constraints.

        Returns:
            ActuatorConstraints for LED ring
        """
        return self._constraints

    async def write(self, value: float) -> None:
        """Write brightness value.

        Args:
            value: Brightness (0.0-255.0)
        """
        await self.set_brightness(int(value))

    async def emergency_stop(self) -> None:
        """Emergency stop - turn off all LEDs."""
        if self._rte:
            try:
                await self._rte.send_command(RTECommand.LED_BRIGHTNESS, 0)
                await self._rte.send_command(RTECommand.LED_PATTERN, LEDPattern.ERROR_FLASH)
            except Exception:
                pass

    async def reset(self) -> None:
        """Reset to default state."""
        self._pattern = LEDPattern.IDLE
        self._brightness = 128
        self._color = None

        if self._rte:
            await self._rte.send_command(RTECommand.RESET)

    # =========================================================================
    # LED Ring Specific Methods
    # =========================================================================

    async def set_pattern(self, pattern: LEDPattern | int) -> None:
        """Set LED animation pattern.

        Args:
            pattern: Pattern to display
        """
        if isinstance(pattern, int):
            pattern = LEDPattern(pattern)

        self._pattern = pattern

        if self._rte:
            await self._rte.send_command(RTECommand.LED_PATTERN, pattern)

    async def set_brightness(self, level: int) -> None:
        """Set LED brightness.

        Args:
            level: Brightness (0-255)
        """
        level = min(255, max(0, level))
        self._brightness = level

        if self._rte:
            await self._rte.send_command(RTECommand.LED_BRIGHTNESS, level)

    async def set_color(self, r: int, g: int, b: int) -> None:
        """Set color override.

        Args:
            r: Red component (0-255)
            g: Green component (0-255)
            b: Blue component (0-255)
        """
        self._color = (r, g, b)

        if self._rte:
            await self._rte.send_command(RTECommand.LED_COLOR, r, g, b)

    async def clear_color(self) -> None:
        """Clear color override, return to pattern colors."""
        self._color = None
        # Reset by setting pattern again
        if self._rte:
            await self._rte.send_command(RTECommand.LED_PATTERN, self._pattern)

    async def get_status(self) -> RTEStatus:
        """Get current LED ring status from RTE.

        Returns:
            RTEStatus with current state
        """
        if self._rte:
            return await self._rte.get_status()

        return RTEStatus(
            pattern=self._pattern,
            brightness=self._brightness,
            connected=False,
        )

    async def poll_events(self) -> list[RTEEvent]:
        """Poll for events from LED ring (e.g., button press).

        Returns:
            List of events
        """
        if self._rte:
            return await self._rte.poll_events()
        return []

    # =========================================================================
    # Convenience Methods
    # =========================================================================

    async def show_idle(self) -> None:
        """Show idle pattern (static colony colors)."""
        await self.set_pattern(LEDPattern.IDLE)

    async def show_listening(self) -> None:
        """Show listening pattern (pulsing)."""
        await self.set_pattern(LEDPattern.PULSE)

    async def show_processing(self) -> None:
        """Show processing pattern (spinning)."""
        await self.set_pattern(LEDPattern.SPIN)

    async def show_success(self) -> None:
        """Show success pattern (green flash)."""
        await self.set_pattern(LEDPattern.FLASH)

    async def show_error(self) -> None:
        """Show error pattern (red flash)."""
        await self.set_pattern(LEDPattern.ERROR_FLASH)

    async def show_safety(self, h_x: float) -> None:
        """Show safety status based on CBF barrier value.

        Visualizes h(x):
        - h(x) > 0.5: Green (safe)
        - 0 < h(x) <= 0.5: Yellow (caution)
        - h(x) <= 0: Red (violation)

        Args:
            h_x: Current CBF barrier value
        """
        if h_x >= 0.5:
            await self.set_pattern(LEDPattern.SAFETY_SAFE)
        elif h_x >= 0.0:
            await self.set_pattern(LEDPattern.SAFETY_CAUTION)
        else:
            await self.set_pattern(LEDPattern.SAFETY_VIOLATION)

    async def breathing(self) -> None:
        """Show breathing pattern (ambient)."""
        await self.set_pattern(LEDPattern.BREATHING)

    async def rainbow(self) -> None:
        """Show rainbow pattern."""
        await self.set_pattern(LEDPattern.RAINBOW)

    async def spectral(self) -> None:
        """Show spectral sweep pattern (prismorphism)."""
        await self.set_pattern(LEDPattern.SPECTRAL_SWEEP)


__all__ = [
    "LEDRingActuator",
]
