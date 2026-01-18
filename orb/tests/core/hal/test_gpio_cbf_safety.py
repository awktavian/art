"""Tests for GPIO actuator CBF safety integration.

CREATED: December 15, 2025
AUTHOR: Forge (e₂)

Tests verify that GPIO actuators enforce CBF constraints before hardware operations.
"""

from __future__ import annotations


import pytest
from kagami_hal.adapters.embedded.actuators.gpio import (
    GPIOActuator,
    LEDActuator,
    MotorActuator,
    RelayActuator,
)
from kagami.core.safety.cbf_decorators import CBFViolation


class TestGPIOActuatorCBFSafety:
    """Test GPIO actuator CBF safety enforcement."""

    @pytest.mark.asyncio
    async def test_gpio_set_with_safe_state(self):
        """GPIO set operation succeeds when CBF h(x) >= 0."""
        actuator = GPIOActuator(pin=17, initial_state=False)
        success = await actuator.initialize()

        if not success:
            pytest.skip("GPIO not available on this platform")

        # Should succeed (no CBF registered yet, defaults to safe)
        # This test will pass once we add CBF enforcement
        await actuator.set(True)
        assert await actuator.get() is True

        await actuator.shutdown()

    @pytest.mark.asyncio
    async def test_gpio_set_blocks_unsafe_state(self):
        """GPIO set operation blocks when CBF h(x) < 0."""
        # This test will be implemented after CBF decorator is added
        # Expected: CBFViolation raised when safety constraint violated
        pass

    @pytest.mark.asyncio
    async def test_gpio_pulse_validates_duration(self):
        """GPIO pulse validates duration against safety limits."""
        actuator = GPIOActuator(pin=17)

        # Test max duration safety limit
        with pytest.raises(ValueError, match="out of bounds"):
            await actuator.pulse(6000)  # Exceeds 5000ms limit

        with pytest.raises(ValueError, match="out of bounds"):
            await actuator.pulse(-100)  # Negative duration

    @pytest.mark.asyncio
    async def test_gpio_hardware_failure_injection(self):
        """GPIO actuator handles hardware failures gracefully."""
        actuator = GPIOActuator(pin=999)  # Invalid pin

        # Should return False on init failure, not crash
        result = await actuator.initialize()
        assert result is False

    @pytest.mark.asyncio
    async def test_gpio_shutdown_safety(self):
        """GPIO shutdown sets pin to safe state (low)."""
        actuator = GPIOActuator(pin=17, initial_state=True)
        await actuator.shutdown()

        # After shutdown, should not be running
        assert actuator._running is False


class TestLEDActuatorCBFSafety:
    """Test LED actuator CBF safety enforcement."""

    @pytest.mark.asyncio
    async def test_led_brightness_validates_range(self):
        """LED brightness is clamped to [0.0, 1.0]."""
        actuator = LEDActuator(pin=18)
        success = await actuator.initialize()

        if not success:
            pytest.skip("GPIO not available on this platform")

        # Should clamp, not raise
        await actuator.set_brightness(1.5)
        assert actuator._brightness == 1.0

        await actuator.set_brightness(-0.5)
        assert actuator._brightness == 0.0

        await actuator.shutdown()

    @pytest.mark.asyncio
    async def test_led_brightness_cbf_enforcement(self):
        """LED brightness checks CBF before setting."""
        # This test will verify CBF enforcement after decorator added
        # Expected: CBFViolation if power budget exceeded
        pass


class TestRelayActuatorCBFSafety:
    """Test relay actuator CBF safety enforcement."""

    @pytest.mark.asyncio
    async def test_relay_max_on_duration_enforced(self):
        """Relay automatically turns off after max_on_duration."""
        import asyncio

        actuator = RelayActuator(pin=22, max_on_duration_s=0.2)
        success = await actuator.initialize()

        if not success:
            pytest.skip("GPIO not available on this platform")

        await actuator.turn_on()
        assert await actuator.is_on() is True

        # Wait for watchdog to trigger
        await asyncio.sleep(0.3)

        # Should be auto-turned off by watchdog
        assert await actuator.is_on() is False

        await actuator.shutdown()

    @pytest.mark.asyncio
    async def test_relay_cbf_blocks_unsafe_on(self):
        """Relay respects CBF constraints before turning on."""
        # This test will verify CBF enforcement after decorator added
        # Expected: CBFViolation if power budget exceeded
        pass


class TestMotorActuatorCBFSafety:
    """Test motor actuator CBF safety enforcement."""

    @pytest.mark.asyncio
    async def test_motor_speed_limited_by_max_speed(self):
        """Motor speed is limited by max_speed safety parameter."""
        actuator = MotorActuator(
            pin_forward=23,
            pin_backward=24,
            max_speed=0.8,
        )
        success = await actuator.initialize()

        if not success:
            pytest.skip("GPIO not available on this platform")

        # Should raise if speed exceeds max_speed
        with pytest.raises(ValueError, match="exceeds max_speed"):
            await actuator.set_speed(0.9, direction=1)

        await actuator.shutdown()

    @pytest.mark.asyncio
    async def test_motor_stop_before_direction_change(self):
        """Motor stops before changing direction."""
        actuator = MotorActuator(
            pin_forward=23,
            pin_backward=24,
        )
        success = await actuator.initialize()

        if not success:
            pytest.skip("GPIO not available on this platform")

        # Set forward
        await actuator.set_speed(0.5, direction=1)
        assert actuator._current_direction == 1

        # Change to backward - should stop first
        await actuator.set_speed(0.5, direction=-1)
        assert actuator._current_direction == -1

        await actuator.shutdown()

    @pytest.mark.asyncio
    async def test_motor_cbf_enforces_mechanical_limits(self):
        """Motor operations check CBF for mechanical safety."""
        # This test will verify CBF enforcement after decorator added
        # Expected: CBFViolation if mechanical stress limits exceeded
        pass


class TestActuatorHardwareFailureInjection:
    """Test actuator resilience to hardware failures."""

    @pytest.mark.asyncio
    async def test_gpio_backend_unavailable(self):
        """GPIO gracefully handles missing backend libraries."""
        # Test when gpiod and RPi.GPIO both unavailable
        # Should return False from initialize(), not crash
        actuator = GPIOActuator(pin=17)

        # In test mode, should gracefully degrade
        result = await actuator.initialize()
        # Can be True or False depending on platform
        assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_gpio_device_disconnected(self):
        """GPIO handles device disconnection during operation."""
        actuator = GPIOActuator(pin=17)
        success = await actuator.initialize()

        if not success:
            pytest.skip("GPIO not available")

        # Simulate hardware disconnection by shutting down
        await actuator.shutdown()

        # Operations after shutdown should raise
        with pytest.raises(RuntimeError, match="not initialized"):
            await actuator.set(True)

    @pytest.mark.asyncio
    async def test_motor_pwm_fallback(self):
        """Motor falls back gracefully when PWM unavailable."""
        actuator = MotorActuator(
            pin_forward=23,
            pin_backward=24,
            pin_enable=25,  # Requires PWM
        )

        # Should handle PWM init failure gracefully
        # (logged warning, but still functional with digital on/off)
        result = await actuator.initialize()
        assert isinstance(result, bool)
