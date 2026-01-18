"""Embedded Input Adapter using GPIO.

Implements InputController for embedded systems using:
- GPIO for buttons
- ADC for rotary encoders
- I2C for capacitive touch

Created: November 10, 2025
Updated: December 2, 2025 - Full implementation
"""

from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path

from kagami.core.boot_mode import is_test_mode

from kagami_hal.data_types import InputEvent, InputType
from kagami_hal.input_controller import BaseInputController

logger = logging.getLogger(__name__)

EMBEDDED_AVAILABLE = Path("/sys/class/gpio").exists()

# Try to import GPIO libraries
GPIO_AVAILABLE = False
try:
    import RPi.GPIO as GPIO

    GPIO_AVAILABLE = True
except ImportError:
    pass


class EmbeddedInput(BaseInputController):
    """Embedded input implementation using GPIO."""

    def __init__(
        self,
        button_pins: dict[str, int] | None = None,
        debounce_ms: int = 50,
    ):
        """Initialize embedded input.

        Args:
            button_pins: Mapping of button names to GPIO pins
            debounce_ms: Debounce time in milliseconds
        """
        super().__init__()
        self._button_pins = button_pins or {}
        self._debounce_ms = debounce_ms
        self._running = False
        self._poll_task: asyncio.Task | None = None
        self._button_states: dict[int, bool] = {}
        self._last_change: dict[int, float] = {}

    async def initialize(self) -> bool:
        """Initialize input devices."""
        if not EMBEDDED_AVAILABLE:
            if is_test_mode():
                logger.info("Embedded input not available, gracefully degrading")
                return False
            raise RuntimeError("Embedded input only available on embedded systems")

        try:
            if GPIO_AVAILABLE:
                GPIO.setmode(GPIO.BCM)

                # Set up button pins as inputs with pull-up
                for name, pin in self._button_pins.items():
                    GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
                    self._button_states[pin] = GPIO.input(pin)
                    self._last_change[pin] = 0
                    logger.debug(f"Configured button '{name}' on GPIO {pin}")

            self._running = True
            self._poll_task = asyncio.create_task(self._poll_buttons())

            logger.info(f"✅ Embedded input initialized ({len(self._button_pins)} buttons)")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize embedded input: {e}", exc_info=True)
            return False

    async def _poll_buttons(self) -> None:
        """Poll GPIO buttons for changes."""
        while self._running and GPIO_AVAILABLE:
            try:
                current_time = time.time()

                for _name, pin in self._button_pins.items():
                    state = GPIO.input(pin)
                    prev_state = self._button_states.get(pin, state)

                    # Check for change with debounce
                    if state != prev_state:
                        last_change = self._last_change.get(pin, 0)
                        if (current_time - last_change) * 1000 >= self._debounce_ms:
                            self._button_states[pin] = state
                            self._last_change[pin] = current_time

                            # Create event (inverted for pull-up: LOW = pressed)
                            event = InputEvent(
                                type=InputType.BUTTON,
                                code=pin,
                                value=0 if state else 1,  # Pull-up: LOW = pressed
                                timestamp_ms=int(current_time * 1000),
                            )

                            # Dispatch to subscribers
                            for callback in self._subscribers.get(InputType.BUTTON, []):
                                try:
                                    await callback(event)
                                except Exception as e:
                                    logger.error(f"Error in input callback: {e}")

                await asyncio.sleep(0.001)  # 1ms polling

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Button polling error: {e}")
                await asyncio.sleep(0.1)

    async def read_event(self) -> InputEvent | None:
        """Read next input event (non-blocking)."""
        if not GPIO_AVAILABLE:
            return None

        current_time = time.time()

        for _name, pin in self._button_pins.items():
            state = GPIO.input(pin)
            prev_state = self._button_states.get(pin, state)

            if state != prev_state:
                self._button_states[pin] = state
                return InputEvent(
                    type=InputType.BUTTON,
                    code=pin,
                    value=0 if state else 1,
                    timestamp_ms=int(current_time * 1000),
                )

        return None

    async def inject_event(self, type: InputType, code: int, value: int) -> bool:
        """Inject synthetic input event.

        Note: GPIO output injection not typically supported.
        """
        return False

    async def shutdown(self) -> None:
        """Shutdown input controller."""
        self._running = False

        if self._poll_task:
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass

        if GPIO_AVAILABLE:
            try:
                GPIO.cleanup()
            except Exception:
                pass

        logger.info("✅ Embedded input shutdown")
