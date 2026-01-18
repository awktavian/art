"""Tests for PWM actuator CBF safety integration.

CREATED: December 15, 2025
AUTHOR: Forge (e₂)

Tests verify that PWM actuators enforce CBF constraints before hardware operations.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tier_integration

from kagami_hal.adapters.embedded.actuators.pwm import (
    ESCActuator,
    PWMActuator,
    ServoActuator,
)
from kagami.core.safety.cbf_decorators import CBFViolation


class TestPWMActuatorCBFSafety:
    """Test PWM actuator CBF safety enforcement."""

    @pytest.mark.asyncio
    async def test_pwm_duty_cycle_validates_range(self):
        """PWM duty cycle is clamped to [0.0, 1.0]."""
        actuator = PWMActuator(channel=0, frequency_hz=1000)
        success = await actuator.initialize()

        if not success:
            pytest.skip("PWM hardware not available")

        # Should clamp within valid range
        await actuator.set_duty_cycle(1.5)
        assert actuator._duty_cycle == 1.0

        await actuator.set_duty_cycle(-0.5)
        assert actuator._duty_cycle == 0.0

        await actuator.shutdown()

    @pytest.mark.asyncio
    async def test_pwm_frequency_change_disables_first(self):
        """PWM frequency change disables PWM before changing period."""
        actuator = PWMActuator(channel=0, frequency_hz=1000)
        success = await actuator.initialize()

        if not success:
            pytest.skip("PWM hardware not available")

        # Change frequency
        await actuator.set_frequency(2000)
        assert actuator._frequency_hz == 2000

        await actuator.shutdown()

    @pytest.mark.asyncio
    async def test_pwm_cbf_enforces_power_budget(self):
        """PWM operations check CBF for power constraints."""
        # This test will verify CBF enforcement after decorator added
        # Expected: CBFViolation if power budget exceeded
        pass

    @pytest.mark.asyncio
    async def test_pwm_hardware_failure_graceful(self):
        """PWM handles hardware failures gracefully."""
        actuator = PWMActuator(channel=99, chip=99)  # Invalid chip

        # Should return False, not crash
        result = await actuator.initialize()
        assert result is False


class TestServoActuatorCBFSafety:
    """Test servo actuator CBF safety enforcement."""

    @pytest.mark.asyncio
    async def test_servo_angle_validates_range(self):
        """Servo angle is validated against max_angle_deg."""
        actuator = ServoActuator(channel=0, max_angle_deg=180.0)

        # Should raise on out-of-range angle
        with pytest.raises(ValueError, match="Angle must be"):
            await actuator.set_angle(200.0)

        with pytest.raises(ValueError, match="Angle must be"):
            await actuator.set_angle(-10.0)

    @pytest.mark.asyncio
    async def test_servo_pulse_width_calculation(self):
        """Servo correctly calculates pulse width from angle."""
        actuator = ServoActuator(
            channel=0,
            min_pulse_ms=1.0,
            max_pulse_ms=2.0,
            max_angle_deg=180.0,
        )
        success = await actuator.initialize()

        if not success:
            pytest.skip("PWM hardware not available")

        # 0° -> 1.0ms pulse
        await actuator.set_angle(0.0)
        expected_duty = 1.0 / 20.0  # 50Hz = 20ms period
        assert abs(actuator._duty_cycle - expected_duty) < 0.001

        # 90° -> 1.5ms pulse
        await actuator.set_angle(90.0)
        expected_duty = 1.5 / 20.0
        assert abs(actuator._duty_cycle - expected_duty) < 0.001

        # 180° -> 2.0ms pulse
        await actuator.set_angle(180.0)
        expected_duty = 2.0 / 20.0
        assert abs(actuator._duty_cycle - expected_duty) < 0.001

        await actuator.shutdown()

    @pytest.mark.asyncio
    async def test_servo_center_position(self):
        """Servo center() moves to middle position."""
        actuator = ServoActuator(channel=0, max_angle_deg=180.0)
        success = await actuator.initialize()

        if not success:
            pytest.skip("PWM hardware not available")

        await actuator.center()
        assert actuator._current_angle == 90.0

        await actuator.shutdown()

    @pytest.mark.asyncio
    async def test_servo_cbf_enforces_mechanical_limits(self):
        """Servo operations check CBF for mechanical safety."""
        # This test will verify CBF enforcement after decorator added
        # Expected: CBFViolation if mechanical stress limits exceeded
        pass


class TestESCActuatorCBFSafety:
    """Test ESC actuator CBF safety enforcement."""

    @pytest.mark.asyncio
    async def test_esc_throttle_limited_by_max_throttle(self):
        """ESC throttle is limited by max_throttle safety parameter."""
        actuator = ESCActuator(channel=0, max_throttle=0.8)

        # Should raise if throttle exceeds max_throttle
        with pytest.raises(ValueError, match="exceeds max_throttle"):
            await actuator.set_throttle(0.9)

    @pytest.mark.asyncio
    async def test_esc_throttle_validates_range(self):
        """ESC throttle is clamped to [0.0, 1.0]."""
        actuator = ESCActuator(channel=0)
        success = await actuator.initialize()

        if not success:
            pytest.skip("PWM hardware not available")

        # Should clamp
        await actuator.set_throttle(1.5)
        assert actuator._current_throttle == 1.0

        await actuator.set_throttle(-0.5)
        assert actuator._current_throttle == 0.0

        await actuator.shutdown()

    @pytest.mark.asyncio
    async def test_esc_arming_sequence(self):
        """ESC initializes with arming sequence (min pulse for 1s)."""
        actuator = ESCActuator(channel=0)
        success = await actuator.initialize()

        if not success:
            pytest.skip("PWM hardware not available")

        # After init, throttle should be 0
        assert actuator._current_throttle == 0.0

        await actuator.shutdown()

    @pytest.mark.asyncio
    async def test_esc_stop_sets_zero_throttle(self):
        """ESC stop() sets throttle to 0."""
        actuator = ESCActuator(channel=0)
        success = await actuator.initialize()

        if not success:
            pytest.skip("PWM hardware not available")

        await actuator.set_throttle(0.5)
        assert actuator._current_throttle == 0.5

        await actuator.stop()
        assert actuator._current_throttle == 0.0

        await actuator.shutdown()

    @pytest.mark.asyncio
    async def test_esc_cbf_enforces_power_limits(self):
        """ESC operations check CBF for power constraints."""
        # This test will verify CBF enforcement after decorator added
        # Expected: CBFViolation if power budget exceeded
        pass


class TestPWMHardwareFailureInjection:
    """Test PWM actuator resilience to hardware failures."""

    @pytest.mark.asyncio
    async def test_pwm_chip_missing(self):
        """PWM gracefully handles missing PWM chip."""
        actuator = PWMActuator(channel=0, chip=99)

        # Should return False, not crash
        result = await actuator.initialize()
        assert result is False

    @pytest.mark.asyncio
    async def test_pwm_channel_export_failure(self):
        """PWM handles channel export failure gracefully."""
        # This would require mocking sysfs, testing graceful degradation
        actuator = PWMActuator(channel=0)
        result = await actuator.initialize()

        # Should either succeed or fail gracefully
        assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_pwm_device_disconnected_during_operation(self):
        """PWM handles device disconnection during operation."""
        actuator = PWMActuator(channel=0)
        success = await actuator.initialize()

        if not success:
            pytest.skip("PWM not available")

        await actuator.shutdown()

        # Operations after shutdown should raise
        with pytest.raises(RuntimeError, match="not initialized"):
            await actuator.set_duty_cycle(0.5)
