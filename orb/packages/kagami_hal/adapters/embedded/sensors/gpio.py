"""GPIO Input Sensors for embedded platforms.

Supports:
- Digital inputs (buttons, switches)
- PIR motion sensors
- Reed switches (door/window sensors)
- Hall effect sensors

Uses modern gpiod library (preferred) or RPi.GPIO (legacy).

Created: December 15, 2025
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable
from enum import Enum
from pathlib import Path
from typing import Any

from kagami.core.boot_mode import is_test_mode

from kagami_hal.data_types import SensorReading, SensorType

logger = logging.getLogger(__name__)

# Check for GPIO libraries
GPIOD_AVAILABLE = False
RPI_GPIO_AVAILABLE = False

try:
    import gpiod  # Modern Linux GPIO interface

    GPIOD_AVAILABLE = True
except ImportError:
    pass

try:
    import RPi.GPIO as GPIO  # Legacy Raspberry Pi GPIO

    RPI_GPIO_AVAILABLE = True
except ImportError:
    pass


class GPIOMode(Enum):
    """GPIO input modes."""

    PULL_UP = "pull_up"  # Internal pull-up resistor
    PULL_DOWN = "pull_down"  # Internal pull-down resistor
    FLOATING = "floating"  # No pull resistor


class GPIOEdge(Enum):
    """GPIO edge detection."""

    RISING = "rising"  # Low to high
    FALLING = "falling"  # High to low
    BOTH = "both"  # Any change


class GPIOSensor:
    """GPIO input sensor for embedded platforms.

    Implements interrupt-driven GPIO input with debouncing.
    """

    def __init__(
        self,
        pin: int,
        mode: GPIOMode = GPIOMode.PULL_UP,
        edge: GPIOEdge = GPIOEdge.BOTH,
        debounce_ms: int = 50,
        active_low: bool = True,
    ):
        """Initialize GPIO sensor.

        Args:
            pin: GPIO pin number (BCM numbering)
            mode: Pull resistor mode
            edge: Edge detection mode
            debounce_ms: Debounce time in milliseconds
            active_low: True if active state is low (for pull-up)
        """
        self._pin = pin
        self._mode = mode
        self._edge = edge
        self._debounce_ms = debounce_ms
        self._active_low = active_low

        self._backend: str = "none"
        self._gpio_line: Any = None
        self._gpio_chip: Any = None
        self._running = False
        self._last_state: bool | None = None
        self._last_event_time: float = 0.0

        self._callbacks: list[Callable[[bool], None]] = []
        self._callbacks_lock = asyncio.Lock()

    async def initialize(self) -> bool:
        """Initialize GPIO sensor.

        Returns:
            True if successful
        """
        # Try modern gpiod first
        if GPIOD_AVAILABLE and self._try_gpiod():
            logger.info(f"GPIO sensor initialized: pin {self._pin} (gpiod)")
            return True

        # Fall back to RPi.GPIO
        if RPI_GPIO_AVAILABLE and self._try_rpi_gpio():
            logger.info(f"GPIO sensor initialized: pin {self._pin} (RPi.GPIO)")
            return True

        if is_test_mode():
            logger.info("GPIO not available, gracefully degrading")
            return False

        logger.error("No GPIO backend available")
        return False

    def _try_gpiod(self) -> bool:
        """Try to initialize using gpiod (modern).

        Returns:
            True if successful
        """
        try:
            # Find GPIO chip (usually gpiochip0)
            chip_path = Path("/dev/gpiochip0")
            if not chip_path.exists():
                return False

            self._gpio_chip = gpiod.Chip(str(chip_path))

            # Get line
            self._gpio_line = self._gpio_chip.get_line(self._pin)

            # Configure line
            if self._mode == GPIOMode.PULL_UP:
                flags = gpiod.LINE_REQ_FLAG_BIAS_PULL_UP
            elif self._mode == GPIOMode.PULL_DOWN:
                flags = gpiod.LINE_REQ_FLAG_BIAS_PULL_DOWN
            else:
                flags = 0

            if self._edge == GPIOEdge.RISING:
                flags |= gpiod.LINE_REQ_EV_RISING_EDGE
            elif self._edge == GPIOEdge.FALLING:
                flags |= gpiod.LINE_REQ_EV_FALLING_EDGE
            elif self._edge == GPIOEdge.BOTH:
                flags |= gpiod.LINE_REQ_EV_BOTH_EDGES

            self._gpio_line.request(
                consumer="kagami_gpio_sensor",
                type=gpiod.LINE_REQ_EV_BOTH_EDGES,
                flags=flags,
            )

            self._backend = "gpiod"
            self._running = True

            # Start event loop
            asyncio.create_task(self._poll_gpiod())

            return True

        except Exception as e:
            logger.debug(f"gpiod init failed: {e}")
            return False

    def _try_rpi_gpio(self) -> bool:
        """Try to initialize using RPi.GPIO (legacy).

        Returns:
            True if successful
        """
        try:
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)

            # Configure pull mode
            if self._mode == GPIOMode.PULL_UP:
                pull = GPIO.PUD_UP
            elif self._mode == GPIOMode.PULL_DOWN:
                pull = GPIO.PUD_DOWN
            else:
                pull = GPIO.PUD_OFF

            GPIO.setup(self._pin, GPIO.IN, pull_up_down=pull)

            # Configure edge detection
            if self._edge == GPIOEdge.RISING:
                edge = GPIO.RISING
            elif self._edge == GPIOEdge.FALLING:
                edge = GPIO.FALLING
            else:
                edge = GPIO.BOTH

            GPIO.add_event_detect(
                self._pin,
                edge,
                callback=self._rpi_gpio_callback,
                bouncetime=self._debounce_ms,
            )

            self._backend = "rpi_gpio"
            self._running = True

            return True

        except Exception as e:
            logger.debug(f"RPi.GPIO init failed: {e}")
            return False

    async def _poll_gpiod(self) -> None:
        """Poll gpiod events (async)."""
        while self._running and self._gpio_line:
            try:
                # Wait for event (blocking, so run in executor)
                loop = asyncio.get_event_loop()
                event = await loop.run_in_executor(None, self._gpio_line.event_wait, 0.1)

                if event:
                    # Read event
                    ev = self._gpio_line.event_read()
                    state = ev.type == gpiod.LineEvent.RISING_EDGE

                    # Apply active_low logic
                    if self._active_low:
                        state = not state

                    # Debounce
                    current_time = time.time()
                    if (current_time - self._last_event_time) * 1000 >= self._debounce_ms:
                        self._last_state = state
                        self._last_event_time = current_time

                        # Fire callbacks (thread-safe copy)
                        async with self._callbacks_lock:
                            callbacks = self._callbacks.copy()
                        for callback in callbacks:
                            try:
                                callback(state)
                            except Exception as e:
                                logger.error(f"GPIO callback error: {e}")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"gpiod poll error: {e}")
                await asyncio.sleep(0.1)

    def _rpi_gpio_callback(self, channel: int) -> None:
        """RPi.GPIO callback (runs in GPIO thread)."""
        try:
            state = GPIO.input(self._pin)

            # Apply active_low logic
            if self._active_low:
                state = not state

            # Debounce (RPi.GPIO has built-in bouncetime, but double-check)
            current_time = time.time()
            if (current_time - self._last_event_time) * 1000 >= self._debounce_ms:
                self._last_state = state
                self._last_event_time = current_time

                # Fire callbacks (thread-safe copy, RPi.GPIO runs in separate thread)
                # Use synchronous approach since this runs in GPIO thread, not async context
                callbacks = self._callbacks.copy()
                for callback in callbacks:
                    try:
                        callback(state)
                    except Exception as e:
                        logger.error(f"GPIO callback error: {e}")

        except Exception as e:
            logger.error(f"RPi.GPIO callback error: {e}")

    async def read(self) -> SensorReading:
        """Read current GPIO state.

        Returns:
            SensorReading with boolean state
        """
        if not self._running:
            raise RuntimeError("GPIO sensor not initialized")

        try:
            if self._backend == "gpiod" and self._gpio_line:
                state = self._gpio_line.get_value() == 1
            elif self._backend == "rpi_gpio":
                state = GPIO.input(self._pin) == 1
            else:
                raise RuntimeError("No GPIO backend active")

            # Apply active_low logic
            if self._active_low:
                state = not state

            self._last_state = state

            return SensorReading(
                sensor=SensorType.LIGHT,  # Generic sensor type
                value=state,
                timestamp_ms=int(time.time() * 1000),
                accuracy=1.0,
            )

        except Exception as e:
            logger.error(f"GPIO read failed: {e}")
            raise

    async def subscribe(self, callback: Callable[[bool], None]) -> None:
        """Subscribe to GPIO state changes.

        Args:
            callback: Function to call on state change (receives bool)
        """
        async with self._callbacks_lock:
            self._callbacks.append(callback)

    async def unsubscribe(self, callback: Callable[[bool], None]) -> None:
        """Unsubscribe from GPIO state changes.

        Args:
            callback: Function to remove
        """
        async with self._callbacks_lock:
            if callback in self._callbacks:
                self._callbacks.remove(callback)

    async def shutdown(self) -> None:
        """Shutdown GPIO sensor."""
        self._running = False

        if self._backend == "gpiod" and self._gpio_line:
            try:
                self._gpio_line.release()
                self._gpio_chip.close()
            except Exception as e:
                logger.error(f"gpiod shutdown error: {e}")

        elif self._backend == "rpi_gpio":
            try:
                GPIO.remove_event_detect(self._pin)
                GPIO.cleanup(self._pin)
            except Exception as e:
                logger.error(f"RPi.GPIO shutdown error: {e}")

        self._gpio_line = None
        self._gpio_chip = None

        logger.info(f"GPIO sensor shutdown (pin {self._pin})")


class PIRSensor(GPIOSensor):
    """PIR (Passive Infrared) motion sensor.

    Typically active-high, triggers on motion detected.
    """

    def __init__(self, pin: int, debounce_ms: int = 100):
        """Initialize PIR sensor.

        Args:
            pin: GPIO pin number
            debounce_ms: Debounce time (PIR sensors can be noisy)
        """
        super().__init__(
            pin=pin,
            mode=GPIOMode.PULL_DOWN,  # PIR usually needs pull-down
            edge=GPIOEdge.BOTH,
            debounce_ms=debounce_ms,
            active_low=False,  # Active-high
        )


class ReedSwitchSensor(GPIOSensor):
    """Reed switch sensor (door/window sensor).

    Typically active-low with pull-up, closed = low, open = high.
    """

    def __init__(self, pin: int, debounce_ms: int = 50):
        """Initialize reed switch sensor.

        Args:
            pin: GPIO pin number
            debounce_ms: Debounce time
        """
        super().__init__(
            pin=pin,
            mode=GPIOMode.PULL_UP,
            edge=GPIOEdge.BOTH,
            debounce_ms=debounce_ms,
            active_low=True,  # Active-low (closed = low)
        )


__all__ = [
    "GPIOEdge",
    "GPIOMode",
    "GPIOSensor",
    "PIRSensor",
    "ReedSwitchSensor",
]
