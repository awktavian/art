"""GPIO Output Actuators for embedded platforms.

Supports:
- Digital outputs (LEDs, relays)
- Motor control via H-bridge
- Safety-limited actuators

Uses gpiod (modern) or RPi.GPIO (legacy).

Created: December 15, 2025
"""

from __future__ import annotations

import asyncio
import logging
import time
from enum import Enum
from pathlib import Path
from typing import Any

from kagami.core.boot_mode import is_test_mode
from kagami.core.safety.cbf_decorators import CBFViolation
from kagami.core.safety.cbf_integration import check_cbf_for_operation

logger = logging.getLogger(__name__)

# Check for GPIO libraries
GPIOD_AVAILABLE = False
RPI_GPIO_AVAILABLE = False

try:
    import gpiod

    GPIOD_AVAILABLE = True
except ImportError:
    pass

try:
    import RPi.GPIO as GPIO

    RPI_GPIO_AVAILABLE = True
except ImportError:
    pass


class GPIOOutputMode(Enum):
    """GPIO output drive modes."""

    PUSH_PULL = "push_pull"  # Standard output
    OPEN_DRAIN = "open_drain"  # Open-drain output


class GPIOActuator:
    """GPIO output actuator for embedded platforms.

    Implements basic digital output control.
    """

    def __init__(
        self,
        pin: int,
        initial_state: bool = False,
        mode: GPIOOutputMode = GPIOOutputMode.PUSH_PULL,
    ):
        """Initialize GPIO actuator.

        Args:
            pin: GPIO pin number (BCM numbering)
            initial_state: Initial output state
            mode: Output drive mode
        """
        self._pin = pin
        self._initial_state = initial_state
        self._mode = mode

        self._backend: str = "none"
        self._gpio_line: Any = None
        self._gpio_chip: Any = None
        self._running = False
        self._current_state = initial_state

    async def initialize(self) -> bool:
        """Initialize GPIO actuator.

        Returns:
            True if successful
        """
        # Try modern gpiod first
        if GPIOD_AVAILABLE and self._try_gpiod():
            logger.info(f"GPIO actuator initialized: pin {self._pin} (gpiod)")
            return True

        # Fall back to RPi.GPIO
        if RPI_GPIO_AVAILABLE and self._try_rpi_gpio():
            logger.info(f"GPIO actuator initialized: pin {self._pin} (RPi.GPIO)")
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
            chip_path = Path("/dev/gpiochip0")
            if not chip_path.exists():
                return False

            self._gpio_chip = gpiod.Chip(str(chip_path))
            self._gpio_line = self._gpio_chip.get_line(self._pin)

            # Configure line as output
            flags = 0
            if self._mode == GPIOOutputMode.OPEN_DRAIN:
                flags |= gpiod.LINE_REQ_FLAG_OPEN_DRAIN

            self._gpio_line.request(
                consumer="kagami_gpio_actuator",
                type=gpiod.LINE_REQ_DIR_OUT,
                flags=flags,
                default_val=1 if self._initial_state else 0,
            )

            self._backend = "gpiod"
            self._running = True
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
            GPIO.setup(self._pin, GPIO.OUT, initial=GPIO.HIGH if self._initial_state else GPIO.LOW)

            self._backend = "rpi_gpio"
            self._running = True
            return True

        except Exception as e:
            logger.debug(f"RPi.GPIO init failed: {e}")
            return False

    async def set(self, state: bool) -> None:
        """Set GPIO output state with CBF safety enforcement.

        Args:
            state: True for high, False for low

        Raises:
            RuntimeError: If not initialized
            CBFViolation: If safety constraints violated
        """
        if not self._running:
            raise RuntimeError("GPIO actuator not initialized")

        # CBF Safety Check: Verify operation is safe before actuating
        safety_result = await check_cbf_for_operation(
            operation="hal.gpio.write",
            action="set_pin",
            target=f"pin_{self._pin}",
            params={"pin": self._pin, "state": state},
            metadata={"backend": self._backend},
        )

        if not safety_result.safe:
            raise CBFViolation(
                barrier_name="gpio_output",
                h_value=safety_result.h_x,  # type: ignore[arg-type]
                tier=3,
                detail=f"GPIO write blocked: {safety_result.reason or safety_result.detail}",
            )

        try:
            if self._backend == "gpiod" and self._gpio_line:
                self._gpio_line.set_value(1 if state else 0)
            elif self._backend == "rpi_gpio":
                GPIO.output(self._pin, GPIO.HIGH if state else GPIO.LOW)
            else:
                raise RuntimeError("No GPIO backend active")

            self._current_state = state

        except Exception as e:
            logger.error(f"GPIO set failed: {e}")
            raise

    async def get(self) -> bool:
        """Get current GPIO output state.

        Returns:
            Current state
        """
        return self._current_state

    async def toggle(self) -> None:
        """Toggle GPIO output state."""
        await self.set(not self._current_state)

    async def pulse(self, duration_ms: int) -> None:
        """Generate a pulse on the GPIO pin.

        Args:
            duration_ms: Pulse width in milliseconds (max 5000ms for safety)

        Raises:
            ValueError: If duration_ms exceeds safety limit
        """
        MAX_PULSE_DURATION_MS = 5000  # 5 seconds safety limit
        if duration_ms < 0 or duration_ms > MAX_PULSE_DURATION_MS:
            raise ValueError(
                f"Pulse duration {duration_ms}ms out of bounds [0, {MAX_PULSE_DURATION_MS}]"
            )
        await self.set(True)
        await asyncio.sleep(duration_ms / 1000.0)
        await self.set(False)

    async def shutdown(self) -> None:
        """Shutdown GPIO actuator."""
        self._running = False

        # Set to safe state (low)
        try:
            await self.set(False)
        except Exception:
            pass

        if self._backend == "gpiod" and self._gpio_line:
            try:
                self._gpio_line.release()
                self._gpio_chip.close()
            except Exception as e:
                logger.error(f"gpiod shutdown error: {e}")

        elif self._backend == "rpi_gpio":
            try:
                GPIO.cleanup(self._pin)
            except Exception as e:
                logger.error(f"RPi.GPIO shutdown error: {e}")

        self._gpio_line = None
        self._gpio_chip = None

        logger.info(f"GPIO actuator shutdown (pin {self._pin})")


class LEDActuator(GPIOActuator):
    """LED actuator with brightness control (via software PWM).

    Note: For true hardware PWM, use PWMActuator.
    """

    def __init__(self, pin: int, frequency_hz: int = 1000):
        """Initialize LED actuator.

        Args:
            pin: GPIO pin number
            frequency_hz: PWM frequency for brightness control
        """
        super().__init__(pin, initial_state=False)
        self._frequency_hz = frequency_hz
        self._pwm: Any = None
        self._brightness = 0.0

    async def initialize(self) -> bool:
        """Initialize LED with PWM."""
        if not await super().initialize():
            return False

        # Set up PWM (only supported on RPi.GPIO backend)
        if self._backend == "rpi_gpio":
            try:
                self._pwm = GPIO.PWM(self._pin, self._frequency_hz)
                self._pwm.start(0)
                logger.info(f"LED PWM initialized at {self._frequency_hz} Hz")
            except Exception as e:
                logger.warning(f"PWM init failed, using digital output: {e}")

        return True

    async def set_brightness(self, level: float) -> None:
        """Set LED brightness with CBF safety enforcement.

        Args:
            level: Brightness 0.0-1.0

        Raises:
            CBFViolation: If power budget exceeded
        """
        level = max(0.0, min(1.0, level))

        # CBF Safety Check: Verify power budget before changing brightness
        safety_result = await check_cbf_for_operation(
            operation="hal.led.set_brightness",
            action="adjust_brightness",
            target=f"pin_{self._pin}",
            params={"pin": self._pin, "brightness": level},
            metadata={"current_brightness": self._brightness},
        )

        if not safety_result.safe:
            raise CBFViolation(
                barrier_name="led_brightness",
                h_value=safety_result.h_x,  # type: ignore[arg-type]
                tier=3,
                detail=f"LED brightness change blocked: {safety_result.reason or safety_result.detail}",
            )

        self._brightness = level

        if self._pwm:
            # Use PWM for smooth brightness
            self._pwm.ChangeDutyCycle(level * 100)
        else:
            # Fall back to binary on/off
            await self.set(level > 0.5)

    async def shutdown(self) -> None:
        """Shutdown LED."""
        if self._pwm:
            try:
                self._pwm.stop()
            except Exception:
                pass
            self._pwm = None

        await super().shutdown()


class RelayActuator(GPIOActuator):
    """Relay actuator with safety timeout.

    Relays control high-power loads and should have fail-safe timeouts.
    """

    def __init__(
        self,
        pin: int,
        active_high: bool = True,
        max_on_duration_s: float | None = None,
    ):
        """Initialize relay actuator.

        Args:
            pin: GPIO pin number
            active_high: True if relay is active-high
            max_on_duration_s: Maximum on-time before auto-shutoff (safety)
        """
        super().__init__(pin, initial_state=False)
        self._active_high = active_high
        self._max_on_duration_s = max_on_duration_s
        self._on_since: float | None = None
        self._watchdog_task: asyncio.Task | None = None

    async def initialize(self) -> bool:
        """Initialize relay with watchdog."""
        if not await super().initialize():
            return False

        if self._max_on_duration_s is not None:
            self._watchdog_task = asyncio.create_task(self._watchdog())

        return True

    async def _watchdog(self) -> None:
        """Safety watchdog to enforce max on-time."""
        while self._running:
            try:
                if self._on_since is not None and self._max_on_duration_s is not None:
                    elapsed = time.time() - self._on_since
                    if elapsed >= self._max_on_duration_s:
                        logger.warning(
                            f"Relay on pin {self._pin} exceeded max on-time "
                            f"({self._max_on_duration_s}s), forcing off"
                        )
                        await self.turn_off()

                await asyncio.sleep(0.1)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Relay watchdog error: {e}")
                await asyncio.sleep(1.0)

    async def turn_on(self) -> None:
        """Turn relay on with CBF safety enforcement.

        Raises:
            CBFViolation: If power budget exceeded
        """
        # CBF Safety Check: Verify power budget before turning on relay
        safety_result = await check_cbf_for_operation(
            operation="hal.relay.turn_on",
            action="activate_relay",
            target=f"pin_{self._pin}",
            params={"pin": self._pin, "active_high": self._active_high},
            metadata={"max_on_duration_s": self._max_on_duration_s},
        )

        if not safety_result.safe:
            raise CBFViolation(
                barrier_name="relay_power",
                h_value=safety_result.h_x,  # type: ignore[arg-type]
                tier=3,
                detail=f"Relay activation blocked: {safety_result.reason or safety_result.detail}",
            )

        await self.set(self._active_high)
        self._on_since = time.time()
        logger.debug(f"Relay on pin {self._pin} turned ON")

    async def turn_off(self) -> None:
        """Turn relay off."""
        await self.set(not self._active_high)
        self._on_since = None
        logger.debug(f"Relay on pin {self._pin} turned OFF")

    async def is_on(self) -> bool:
        """Check if relay is on.

        Returns:
            True if on
        """
        state = await self.get()
        return state == self._active_high

    async def shutdown(self) -> None:
        """Shutdown relay (turn off first)."""
        if self._watchdog_task:
            self._watchdog_task.cancel()
            try:
                await self._watchdog_task
            except asyncio.CancelledError:
                pass

        await self.turn_off()
        await super().shutdown()


class MotorActuator(GPIOActuator):
    """Motor actuator via H-bridge (direction + speed control).

    Requires 2 GPIO pins for direction (or 1 if using enable pin).
    Speed control via PWM.

    SAFETY: Motors have strict limits to prevent mechanical damage.
    """

    def __init__(
        self,
        pin_forward: int,
        pin_backward: int,
        pin_enable: int | None = None,
        max_speed: float = 1.0,
        pwm_frequency_hz: int = 20000,
    ):
        """Initialize motor actuator.

        Args:
            pin_forward: GPIO pin for forward direction
            pin_backward: GPIO pin for backward direction
            pin_enable: GPIO pin for enable/PWM (optional)
            max_speed: Maximum allowed speed (0.0-1.0) for safety
            pwm_frequency_hz: PWM frequency
        """
        super().__init__(pin_forward, initial_state=False)
        self._pin_backward = pin_backward
        self._pin_enable = pin_enable
        self._max_speed = max(0.0, min(1.0, max_speed))
        self._pwm_frequency_hz = pwm_frequency_hz

        self._gpio_backward: Any = None
        self._gpio_enable: Any = None
        self._pwm: Any = None
        self._current_speed = 0.0
        self._current_direction = 0  # -1=backward, 0=stop, 1=forward

    async def initialize(self) -> bool:
        """Initialize motor controller."""
        if not await super().initialize():
            return False

        # Initialize backward pin
        if self._backend == "rpi_gpio":
            GPIO.setup(self._pin_backward, GPIO.OUT, initial=GPIO.LOW)

            # Initialize enable pin with PWM
            if self._pin_enable is not None:
                GPIO.setup(self._pin_enable, GPIO.OUT, initial=GPIO.LOW)
                self._pwm = GPIO.PWM(self._pin_enable, self._pwm_frequency_hz)
                self._pwm.start(0)

        logger.info(
            f"Motor actuator initialized: forward={self._pin}, "
            f"backward={self._pin_backward}, max_speed={self._max_speed:.1%}"
        )
        return True

    async def set_speed(self, speed: float, direction: int = 1) -> None:
        """Set motor speed and direction with CBF safety enforcement.

        Args:
            speed: Speed 0.0-1.0
            direction: -1 for backward, 0 for stop, 1 for forward

        Raises:
            ValueError: If speed exceeds max_speed
            CBFViolation: If mechanical stress limits exceeded
            RuntimeError: If not initialized
        """
        if not self._running:
            raise RuntimeError("Motor actuator not initialized")

        speed = abs(speed)
        if speed > self._max_speed:
            raise ValueError(
                f"Speed {speed:.2f} exceeds max_speed {self._max_speed:.2f} (safety limit)"
            )

        # CBF Safety Check: Verify mechanical safety before setting motor speed
        safety_result = await check_cbf_for_operation(
            operation="hal.motor.set_speed",
            action="control_motor",
            target=f"motor_pins_{self._pin}_{self._pin_backward}",
            params={
                "speed": speed,
                "direction": direction,
                "max_speed": self._max_speed,
            },
            metadata={
                "current_speed": self._current_speed,
                "current_direction": self._current_direction,
            },
        )

        if not safety_result.safe:
            raise CBFViolation(
                barrier_name="motor_speed",
                h_value=safety_result.h_x,  # type: ignore[arg-type]
                tier=3,
                detail=f"Motor speed change blocked: {safety_result.reason or safety_result.detail}",
            )

        # Stop motor first
        await self.stop()

        # Set direction
        if direction > 0:
            # Forward
            await self.set(True)  # Forward pin HIGH
            if self._backend == "rpi_gpio":
                GPIO.output(self._pin_backward, GPIO.LOW)
            self._current_direction = 1

        elif direction < 0:
            # Backward
            await self.set(False)  # Forward pin LOW
            if self._backend == "rpi_gpio":
                GPIO.output(self._pin_backward, GPIO.HIGH)
            self._current_direction = -1

        else:
            # Stop
            await self.stop()
            return

        # Set speed via PWM
        if self._pwm:
            self._pwm.ChangeDutyCycle(speed * 100)
        elif speed > 0:
            # No PWM available, just full speed
            logger.warning("Motor PWM not available, running at full speed")

        self._current_speed = speed

        logger.debug(f"Motor set: direction={'FWD' if direction > 0 else 'BWD'}, speed={speed:.1%}")

    async def stop(self) -> None:
        """Stop motor."""
        await self.set(False)
        if self._backend == "rpi_gpio":
            GPIO.output(self._pin_backward, GPIO.LOW)
        if self._pwm:
            self._pwm.ChangeDutyCycle(0)

        self._current_speed = 0.0
        self._current_direction = 0

    async def brake(self) -> None:
        """Brake motor (short both pins)."""
        await self.set(True)
        if self._backend == "rpi_gpio":
            GPIO.output(self._pin_backward, GPIO.HIGH)
        if self._pwm:
            self._pwm.ChangeDutyCycle(100)

        self._current_speed = 0.0
        self._current_direction = 0

    async def shutdown(self) -> None:
        """Shutdown motor (stop and release)."""
        await self.stop()

        if self._pwm:
            try:
                self._pwm.stop()
            except Exception:
                pass
            self._pwm = None

        if self._backend == "rpi_gpio":
            try:
                GPIO.cleanup([self._pin, self._pin_backward])
                if self._pin_enable is not None:
                    GPIO.cleanup(self._pin_enable)
            except Exception:
                pass

        await super().shutdown()


__all__ = [
    "GPIOActuator",
    "GPIOOutputMode",
    "LEDActuator",
    "MotorActuator",
    "RelayActuator",
]
