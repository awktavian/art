"""Hardware PWM Actuators for embedded platforms.

Supports:
- Servo motors (50Hz PWM, 1-2ms pulse width)
- Brushless motor ESCs (similar to servos)
- LED dimming (high-frequency PWM)
- Precise timing control

Uses hardware PWM (/sys/class/pwm) for real-time performance.

Created: December 15, 2025
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from kagami.core.boot_mode import is_test_mode
from kagami.core.safety.cbf_decorators import CBFViolation
from kagami.core.safety.cbf_integration import check_cbf_for_operation

logger = logging.getLogger(__name__)

# Hardware PWM chip paths
PWM_CHIP_PATHS = [
    "/sys/class/pwm/pwmchip0",
    "/sys/class/pwm/pwmchip1",
]


class PWMActuator:
    """Hardware PWM actuator for embedded platforms.

    Uses Linux sysfs PWM interface for precise, real-time control.
    """

    def __init__(
        self,
        channel: int,
        frequency_hz: int = 50,
        duty_cycle: float = 0.0,
        chip: int = 0,
    ):
        """Initialize PWM actuator.

        Args:
            channel: PWM channel number (0-3 typical)
            frequency_hz: PWM frequency in Hz
            duty_cycle: Initial duty cycle (0.0-1.0)
            chip: PWM chip number (0 or 1)
        """
        self._channel = channel
        self._frequency_hz = frequency_hz
        self._duty_cycle = max(0.0, min(1.0, duty_cycle))
        self._chip = chip

        self._pwm_path: Path | None = None
        self._running = False

    async def initialize(self) -> bool:
        """Initialize hardware PWM.

        Returns:
            True if successful
        """
        chip_path = Path(f"/sys/class/pwm/pwmchip{self._chip}")

        if not chip_path.exists():
            if is_test_mode():
                logger.info(f"PWM chip {self._chip} not available, gracefully degrading")
                return False
            raise RuntimeError(f"PWM chip {self._chip} not available")

        try:
            self._pwm_path = chip_path / f"pwm{self._channel}"

            # Export PWM channel if not already exported
            if not self._pwm_path.exists():
                export_path = chip_path / "export"
                export_path.write_text(str(self._channel))
                await asyncio.sleep(0.1)  # Wait for export (non-blocking)

            # Configure PWM
            period_ns = int(1e9 / self._frequency_hz)
            duty_ns = int(period_ns * self._duty_cycle)

            (self._pwm_path / "period").write_text(str(period_ns))
            (self._pwm_path / "duty_cycle").write_text(str(duty_ns))
            (self._pwm_path / "enable").write_text("1")

            self._running = True
            logger.info(
                f"Hardware PWM initialized: chip{self._chip}/pwm{self._channel}, "
                f"{self._frequency_hz} Hz, duty={self._duty_cycle:.1%}"
            )
            return True

        except Exception as e:
            logger.error(f"PWM init failed: {e}", exc_info=True)
            return False

    async def set_duty_cycle(self, duty_cycle: float) -> None:
        """Set PWM duty cycle with CBF safety enforcement.

        Args:
            duty_cycle: Duty cycle 0.0-1.0

        Raises:
            RuntimeError: If PWM not initialized
            CBFViolation: If power budget exceeded
        """
        if not self._running or not self._pwm_path:
            raise RuntimeError("PWM not initialized")

        duty_cycle = max(0.0, min(1.0, duty_cycle))

        # CBF Safety Check: Verify power budget before changing duty cycle
        safety_result = await check_cbf_for_operation(
            operation="hal.pwm.set_duty_cycle",
            action="adjust_pwm",
            target=f"chip{self._chip}_channel{self._channel}",
            params={
                "duty_cycle": duty_cycle,
                "frequency_hz": self._frequency_hz,
                "chip": self._chip,
                "channel": self._channel,
            },
            metadata={"current_duty_cycle": self._duty_cycle},
        )

        if not safety_result.safe:
            raise CBFViolation(
                barrier_name="pwm_duty_cycle",
                h_value=safety_result.h_x,  # type: ignore[arg-type]
                tier=3,
                detail=f"PWM duty cycle change blocked: {safety_result.reason or safety_result.detail}",
            )

        self._duty_cycle = duty_cycle

        # Calculate duty cycle in nanoseconds
        period_ns = int(1e9 / self._frequency_hz)
        duty_ns = int(period_ns * duty_cycle)

        try:
            (self._pwm_path / "duty_cycle").write_text(str(duty_ns))
        except Exception as e:
            logger.error(f"Failed to set duty cycle: {e}")
            raise

    async def set_frequency(self, frequency_hz: int) -> None:
        """Set PWM frequency.

        Args:
            frequency_hz: Frequency in Hz

        Note: Changing frequency requires disabling PWM first.
        """
        if not self._running or not self._pwm_path:
            raise RuntimeError("PWM not initialized")

        try:
            # Disable PWM
            (self._pwm_path / "enable").write_text("0")

            # Set new period
            period_ns = int(1e9 / frequency_hz)
            (self._pwm_path / "period").write_text(str(period_ns))

            # Update duty cycle to match new period
            duty_ns = int(period_ns * self._duty_cycle)
            (self._pwm_path / "duty_cycle").write_text(str(duty_ns))

            # Re-enable PWM
            (self._pwm_path / "enable").write_text("1")

            self._frequency_hz = frequency_hz

        except Exception as e:
            logger.error(f"Failed to set frequency: {e}")
            raise

    async def get_duty_cycle(self) -> float:
        """Get current duty cycle.

        Returns:
            Duty cycle 0.0-1.0
        """
        return self._duty_cycle

    async def get_frequency(self) -> int:
        """Get current frequency.

        Returns:
            Frequency in Hz
        """
        return self._frequency_hz

    async def shutdown(self) -> None:
        """Shutdown PWM (disable and unexport)."""
        self._running = False

        if self._pwm_path and self._pwm_path.exists():
            try:
                # Disable PWM
                (self._pwm_path / "enable").write_text("0")

                # Unexport channel
                chip_path = Path(f"/sys/class/pwm/pwmchip{self._chip}")
                unexport_path = chip_path / "unexport"
                unexport_path.write_text(str(self._channel))

            except Exception as e:
                logger.error(f"PWM shutdown error: {e}")

        logger.info(f"Hardware PWM shutdown: chip{self._chip}/pwm{self._channel}")


class ServoActuator(PWMActuator):
    """Servo motor actuator (50Hz PWM, 1-2ms pulse width).

    Standard hobby servos use:
    - 50Hz PWM (20ms period)
    - 1.0ms pulse = 0 degrees (0%)
    - 1.5ms pulse = 90 degrees (50%)
    - 2.0ms pulse = 180 degrees (100%)
    """

    def __init__(
        self,
        channel: int,
        chip: int = 0,
        min_pulse_ms: float = 1.0,
        max_pulse_ms: float = 2.0,
        max_angle_deg: float = 180.0,
    ):
        """Initialize servo actuator.

        Args:
            channel: PWM channel number
            chip: PWM chip number
            min_pulse_ms: Minimum pulse width in ms (0 degrees)
            max_pulse_ms: Maximum pulse width in ms (max degrees)
            max_angle_deg: Maximum servo angle (typically 180)
        """
        super().__init__(channel, frequency_hz=50, duty_cycle=0.075, chip=chip)
        self._min_pulse_ms = min_pulse_ms
        self._max_pulse_ms = max_pulse_ms
        self._max_angle_deg = max_angle_deg
        self._current_angle = 90.0  # Center position

    async def set_angle(self, angle_deg: float) -> None:
        """Set servo angle with CBF safety enforcement.

        Args:
            angle_deg: Target angle in degrees (0 to max_angle_deg)

        Raises:
            ValueError: If angle out of range
            CBFViolation: If mechanical stress limits exceeded
        """
        if not 0 <= angle_deg <= self._max_angle_deg:
            raise ValueError(f"Angle must be 0-{self._max_angle_deg}, got {angle_deg}")

        # CBF Safety Check: Verify mechanical safety before changing angle
        safety_result = await check_cbf_for_operation(
            operation="hal.servo.set_angle",
            action="move_servo",
            target=f"chip{self._chip}_channel{self._channel}",
            params={
                "angle_deg": angle_deg,
                "max_angle_deg": self._max_angle_deg,
                "channel": self._channel,
            },
            metadata={"current_angle": self._current_angle},
        )

        if not safety_result.safe:
            raise CBFViolation(
                barrier_name="servo_angle",
                h_value=safety_result.h_x,  # type: ignore[arg-type]
                tier=3,
                detail=f"Servo angle change blocked: {safety_result.reason or safety_result.detail}",
            )

        # Calculate pulse width
        pulse_range_ms = self._max_pulse_ms - self._min_pulse_ms
        pulse_ms = self._min_pulse_ms + (angle_deg / self._max_angle_deg) * pulse_range_ms

        # Convert to duty cycle (50Hz = 20ms period)
        duty_cycle = pulse_ms / 20.0

        await self.set_duty_cycle(duty_cycle)
        self._current_angle = angle_deg

        logger.debug(f"Servo angle set: {angle_deg:.1f}° (pulse {pulse_ms:.2f}ms)")

    async def center(self) -> None:
        """Move servo to center position."""
        await self.set_angle(self._max_angle_deg / 2.0)

    async def get_angle(self) -> float:
        """Get current servo angle.

        Returns:
            Current angle in degrees
        """
        return self._current_angle


class ESCActuator(PWMActuator):
    """Electronic Speed Controller (ESC) for brushless motors.

    ESCs use servo-style PWM control:
    - 50Hz or higher
    - 1.0ms = stopped
    - 2.0ms = full speed
    """

    def __init__(
        self,
        channel: int,
        chip: int = 0,
        min_pulse_ms: float = 1.0,
        max_pulse_ms: float = 2.0,
        max_throttle: float = 1.0,
    ):
        """Initialize ESC actuator.

        Args:
            channel: PWM channel number
            chip: PWM chip number
            min_pulse_ms: Minimum pulse width (stopped)
            max_pulse_ms: Maximum pulse width (full speed)
            max_throttle: Maximum allowed throttle (0.0-1.0) for safety
        """
        super().__init__(channel, frequency_hz=50, duty_cycle=0.05, chip=chip)
        self._min_pulse_ms = min_pulse_ms
        self._max_pulse_ms = max_pulse_ms
        self._max_throttle = max(0.0, min(1.0, max_throttle))
        self._current_throttle = 0.0

    async def initialize(self) -> bool:
        """Initialize ESC with arming sequence."""
        if not await super().initialize():
            return False

        # Arm ESC: send minimum pulse for 1 second
        await self.set_throttle(0.0)
        logger.info("ESC arming (1s)...")
        import asyncio

        await asyncio.sleep(1.0)
        logger.info("ESC armed")

        return True

    async def set_throttle(self, throttle: float) -> None:
        """Set ESC throttle with CBF safety enforcement.

        Args:
            throttle: Throttle 0.0-1.0

        Raises:
            ValueError: If throttle exceeds max_throttle
            CBFViolation: If power budget exceeded
        """
        if throttle > self._max_throttle:
            raise ValueError(
                f"Throttle {throttle:.2f} exceeds max_throttle {self._max_throttle:.2f} (safety limit)"
            )

        throttle = max(0.0, min(1.0, throttle))

        # CBF Safety Check: Verify power budget before changing throttle
        safety_result = await check_cbf_for_operation(
            operation="hal.esc.set_throttle",
            action="control_motor",
            target=f"chip{self._chip}_channel{self._channel}",
            params={
                "throttle": throttle,
                "max_throttle": self._max_throttle,
                "channel": self._channel,
            },
            metadata={"current_throttle": self._current_throttle},
        )

        if not safety_result.safe:
            raise CBFViolation(
                barrier_name="esc_throttle",
                h_value=safety_result.h_x,  # type: ignore[arg-type]
                tier=3,
                detail=f"ESC throttle change blocked: {safety_result.reason or safety_result.detail}",
            )

        # Calculate pulse width
        pulse_range_ms = self._max_pulse_ms - self._min_pulse_ms
        pulse_ms = self._min_pulse_ms + throttle * pulse_range_ms

        # Convert to duty cycle (50Hz = 20ms period)
        duty_cycle = pulse_ms / 20.0

        await self.set_duty_cycle(duty_cycle)
        self._current_throttle = throttle

        logger.debug(f"ESC throttle set: {throttle:.1%} (pulse {pulse_ms:.2f}ms)")

    async def stop(self) -> None:
        """Stop motor (throttle = 0)."""
        await self.set_throttle(0.0)

    async def get_throttle(self) -> float:
        """Get current throttle.

        Returns:
            Current throttle 0.0-1.0
        """
        return self._current_throttle

    async def shutdown(self) -> None:
        """Shutdown ESC (stop motor first)."""
        await self.stop()
        await super().shutdown()


__all__ = [
    "ESCActuator",
    "PWMActuator",
    "ServoActuator",
]
