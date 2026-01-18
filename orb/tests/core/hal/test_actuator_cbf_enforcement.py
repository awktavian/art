"""Tests for HAL actuator CBF enforcement.

CREATED: December 18, 2025
AUTHOR: Forge (e₂)

Tests verify that all HAL actuators properly enforce CBF constraints
before performing hardware operations. This ensures safety invariants
h(x) >= 0 are maintained across all actuator paths.

Test Coverage:
1. GPIO actuators (digital output, LED, relay, motor)
2. PWM actuators (PWM, servo, ESC)
3. Virtual compute resource allocation
4. CBF violation handling (fail-closed behavior)
5. Integration with check_cbf_for_operation()
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tier_integration

from unittest.mock import AsyncMock, MagicMock, patch

from kagami_hal.adapters.embedded.actuators.gpio import (
    GPIOActuator,
    LEDActuator,
    MotorActuator,
    RelayActuator,
)
from kagami_hal.adapters.embedded.actuators.pwm import (
    ESCActuator,
    PWMActuator,
    ServoActuator,
)
from kagami_hal.adapters.virtual.compute import (
    allocate_compute_resource,
    allocate_worker_pool,
    set_batch_size,
)
from kagami.core.safety.cbf_decorators import CBFViolation
from kagami.core.safety.types import SafetyCheckResult


class TestGPIOActuatorCBFEnforcement:
    """Test GPIO actuator CBF enforcement."""

    @pytest.mark.asyncio
    async def test_gpio_set_calls_cbf_check(self):
        """GPIO set() calls check_cbf_for_operation before actuation."""
        actuator = GPIOActuator(pin=17, initial_state=False)
        actuator._running = True
        actuator._backend = "mock"

        # Mock CBF check to return safe
        mock_result = SafetyCheckResult(safe=True, h_x=0.8)
        with patch(
            "kagami.core.hal.adapters.embedded.actuators.gpio.check_cbf_for_operation",
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_cbf:
            try:
                await actuator.set(True)
            except RuntimeError:
                # Expected - no actual GPIO backend
                pass

            # Verify CBF was called with correct parameters
            mock_cbf.assert_called_once()
            call_kwargs = mock_cbf.call_args.kwargs
            assert call_kwargs["operation"] == "hal.gpio.write"
            assert call_kwargs["action"] == "set_pin"
            assert call_kwargs["params"]["pin"] == 17
            assert call_kwargs["params"]["state"] is True

    @pytest.mark.asyncio
    async def test_gpio_set_blocks_when_cbf_unsafe(self):
        """GPIO set() raises CBFViolation when CBF check fails."""
        actuator = GPIOActuator(pin=17)
        actuator._running = True

        # Mock CBF check to return unsafe
        mock_result = SafetyCheckResult(
            safe=False,
            h_x=-0.5,
            reason="power_budget_exceeded",
            detail="GPIO write would exceed power budget",
        )
        with patch(
            "kagami.core.hal.adapters.embedded.actuators.gpio.check_cbf_for_operation",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            with pytest.raises(CBFViolation) as exc_info:
                await actuator.set(True)

            # Verify exception details
            exc = exc_info.value
            assert exc.barrier_name == "gpio_output"
            assert exc.h_value == -0.5
            assert exc.tier == 3
            assert "blocked" in str(exc).lower()

    @pytest.mark.asyncio
    async def test_led_brightness_calls_cbf_check(self):
        """LED set_brightness() calls check_cbf_for_operation."""
        actuator = LEDActuator(pin=18)
        actuator._running = True
        actuator._backend = "mock"

        mock_result = SafetyCheckResult(safe=True, h_x=0.9)
        with patch(
            "kagami.core.hal.adapters.embedded.actuators.gpio.check_cbf_for_operation",
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_cbf:
            try:
                await actuator.set_brightness(0.8)
            except RuntimeError:
                # Expected - no actual GPIO backend for final set() call
                pass

            # Verify CBF was called (may be called twice: once for brightness, once for set)
            assert mock_cbf.call_count >= 1
            # Check first call was for LED brightness
            first_call_kwargs = mock_cbf.call_args_list[0].kwargs
            assert first_call_kwargs["operation"] == "hal.led.set_brightness"
            assert first_call_kwargs["params"]["brightness"] == 0.8

    @pytest.mark.asyncio
    async def test_relay_turn_on_calls_cbf_check(self):
        """Relay turn_on() calls check_cbf_for_operation."""
        actuator = RelayActuator(pin=22)
        actuator._running = True
        actuator._backend = "mock"

        mock_result = SafetyCheckResult(safe=True, h_x=0.7)
        with patch(
            "kagami.core.hal.adapters.embedded.actuators.gpio.check_cbf_for_operation",
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_cbf:
            try:
                await actuator.turn_on()
            except RuntimeError:
                # Expected - no actual GPIO backend
                pass

            # Verify CBF was called (may be called twice: once for relay, once for set)
            assert mock_cbf.call_count >= 1
            # Check first call was for relay.turn_on
            first_call_kwargs = mock_cbf.call_args_list[0].kwargs
            assert first_call_kwargs["operation"] == "hal.relay.turn_on"

    @pytest.mark.asyncio
    async def test_motor_set_speed_calls_cbf_check(self):
        """Motor set_speed() calls check_cbf_for_operation."""
        actuator = MotorActuator(pin_forward=23, pin_backward=24)
        actuator._running = True
        actuator._backend = "mock"

        mock_result = SafetyCheckResult(safe=True, h_x=0.6)
        with patch(
            "kagami.core.hal.adapters.embedded.actuators.gpio.check_cbf_for_operation",
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_cbf:
            try:
                await actuator.set_speed(0.5, direction=1)
            except RuntimeError:
                # Expected - no actual GPIO backend
                pass

            # Verify CBF was called (may be called multiple times: motor + stop + set)
            assert mock_cbf.call_count >= 1
            # Check first call was for motor.set_speed
            first_call_kwargs = mock_cbf.call_args_list[0].kwargs
            assert first_call_kwargs["operation"] == "hal.motor.set_speed"
            assert first_call_kwargs["params"]["speed"] == 0.5


class TestPWMActuatorCBFEnforcement:
    """Test PWM actuator CBF enforcement."""

    @pytest.mark.asyncio
    async def test_pwm_set_duty_cycle_calls_cbf_check(self):
        """PWM set_duty_cycle() calls check_cbf_for_operation."""
        actuator = PWMActuator(channel=0, frequency_hz=1000)
        actuator._running = True
        actuator._pwm_path = MagicMock()

        mock_result = SafetyCheckResult(safe=True, h_x=0.8)
        with patch(
            "kagami.core.hal.adapters.embedded.actuators.pwm.check_cbf_for_operation",
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_cbf:
            # Mock Path write_text to avoid filesystem operations
            with patch.object(actuator._pwm_path.__truediv__.return_value, "write_text"):
                await actuator.set_duty_cycle(0.75)

            # Verify CBF was called
            mock_cbf.assert_called_once()
            call_kwargs = mock_cbf.call_args.kwargs
            assert call_kwargs["operation"] == "hal.pwm.set_duty_cycle"
            assert call_kwargs["params"]["duty_cycle"] == 0.75

    @pytest.mark.asyncio
    async def test_pwm_set_duty_cycle_blocks_when_unsafe(self):
        """PWM set_duty_cycle() raises CBFViolation when unsafe."""
        actuator = PWMActuator(channel=0)
        actuator._running = True
        actuator._pwm_path = MagicMock()

        mock_result = SafetyCheckResult(
            safe=False,
            h_x=-0.3,
            reason="power_exceeded",
        )
        with patch(
            "kagami.core.hal.adapters.embedded.actuators.pwm.check_cbf_for_operation",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            with pytest.raises(CBFViolation) as exc_info:
                await actuator.set_duty_cycle(0.9)

            exc = exc_info.value
            assert exc.barrier_name == "pwm_duty_cycle"
            assert exc.h_value == -0.3

    @pytest.mark.asyncio
    async def test_servo_set_angle_calls_cbf_check(self):
        """Servo set_angle() calls check_cbf_for_operation."""
        actuator = ServoActuator(channel=0)
        actuator._running = True
        actuator._pwm_path = MagicMock()

        # Mock both CBF checks (servo and underlying PWM)
        mock_result = SafetyCheckResult(safe=True, h_x=0.9)
        with patch(
            "kagami.core.hal.adapters.embedded.actuators.pwm.check_cbf_for_operation",
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_cbf:
            with patch.object(actuator._pwm_path.__truediv__.return_value, "write_text"):
                await actuator.set_angle(90.0)

            # Should have at least one CBF call for servo.set_angle
            assert mock_cbf.call_count >= 1
            # Check first call was for servo
            first_call_kwargs = mock_cbf.call_args_list[0].kwargs
            assert first_call_kwargs["operation"] == "hal.servo.set_angle"

    @pytest.mark.asyncio
    async def test_esc_set_throttle_calls_cbf_check(self):
        """ESC set_throttle() calls check_cbf_for_operation."""
        actuator = ESCActuator(channel=0)
        actuator._running = True
        actuator._pwm_path = MagicMock()

        mock_result = SafetyCheckResult(safe=True, h_x=0.7)
        with patch(
            "kagami.core.hal.adapters.embedded.actuators.pwm.check_cbf_for_operation",
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_cbf:
            with patch.object(actuator._pwm_path.__truediv__.return_value, "write_text"):
                await actuator.set_throttle(0.6)

            # Should have at least one CBF call for esc.set_throttle
            assert mock_cbf.call_count >= 1
            first_call_kwargs = mock_cbf.call_args_list[0].kwargs
            assert first_call_kwargs["operation"] == "hal.esc.set_throttle"


class TestVirtualComputeCBFEnforcement:
    """Test virtual compute resource CBF enforcement."""

    @pytest.mark.asyncio
    async def test_allocate_compute_resource_calls_cbf(self):
        """allocate_compute_resource() calls check_cbf_for_operation."""
        mock_result = SafetyCheckResult(safe=True, h_x=0.8)
        with patch(
            "kagami.core.hal.adapters.virtual.compute.check_cbf_for_operation",
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_cbf:
            result = await allocate_compute_resource("cpu", 4)

            assert result is True
            mock_cbf.assert_called_once()
            call_kwargs = mock_cbf.call_args.kwargs
            assert call_kwargs["operation"] == "hal.compute.allocate"
            assert call_kwargs["params"]["resource_type"] == "cpu"
            assert call_kwargs["params"]["amount"] == 4

    @pytest.mark.asyncio
    async def test_allocate_compute_resource_blocks_when_unsafe(self):
        """allocate_compute_resource() raises CBFViolation when unsafe."""
        mock_result = SafetyCheckResult(
            safe=False,
            h_x=-0.4,
            reason="resource_exhaustion",
        )
        with patch(
            "kagami.core.hal.adapters.virtual.compute.check_cbf_for_operation",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            with pytest.raises(CBFViolation) as exc_info:
                await allocate_compute_resource("memory", 16384)

            exc = exc_info.value
            assert exc.barrier_name == "compute_allocation"
            assert exc.h_value == -0.4

    @pytest.mark.asyncio
    async def test_set_batch_size_calls_cbf(self):
        """set_batch_size() calls check_cbf_for_operation."""
        mock_result = SafetyCheckResult(safe=True, h_x=0.9)
        with patch(
            "kagami.core.hal.adapters.virtual.compute.check_cbf_for_operation",
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_cbf:
            batch_size = await set_batch_size(32, model_size_mb=500)

            assert batch_size == 32
            mock_cbf.assert_called_once()
            call_kwargs = mock_cbf.call_args.kwargs
            assert call_kwargs["operation"] == "hal.compute.set_batch_size"
            assert call_kwargs["params"]["batch_size"] == 32

    @pytest.mark.asyncio
    async def test_set_batch_size_reduces_on_violation(self):
        """set_batch_size() reduces batch size when initial check fails."""
        # First check fails, second check succeeds
        mock_results = [
            SafetyCheckResult(safe=False, h_x=-0.1, reason="memory_exceeded"),
            SafetyCheckResult(safe=True, h_x=0.3),  # Reduced batch size passes
        ]

        with patch(
            "kagami.core.hal.adapters.virtual.compute.check_cbf_for_operation",
            new_callable=AsyncMock,
            side_effect=mock_results,
        ) as mock_cbf:
            batch_size = await set_batch_size(128, model_size_mb=1000)

            # Should have reduced batch size to recommended value
            # (detected from system capabilities)
            assert batch_size < 128
            assert mock_cbf.call_count == 2

    @pytest.mark.asyncio
    async def test_allocate_worker_pool_calls_cbf(self):
        """allocate_worker_pool() calls check_cbf_for_operation."""
        mock_result = SafetyCheckResult(safe=True, h_x=0.7)
        with patch(
            "kagami.core.hal.adapters.virtual.compute.check_cbf_for_operation",
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_cbf:
            worker_count = await allocate_worker_pool(8)

            assert worker_count == 8
            mock_cbf.assert_called_once()
            call_kwargs = mock_cbf.call_args.kwargs
            assert call_kwargs["operation"] == "hal.compute.allocate_workers"
            assert call_kwargs["params"]["worker_count"] == 8

    @pytest.mark.asyncio
    async def test_allocate_worker_pool_reduces_on_violation(self):
        """allocate_worker_pool() reduces worker count when check fails."""
        mock_results = [
            SafetyCheckResult(safe=False, h_x=-0.2, reason="cpu_overload"),
            SafetyCheckResult(safe=True, h_x=0.4),  # Reduced worker count passes
        ]

        with patch(
            "kagami.core.hal.adapters.virtual.compute.check_cbf_for_operation",
            new_callable=AsyncMock,
            side_effect=mock_results,
        ) as mock_cbf:
            worker_count = await allocate_worker_pool(32)

            # Should have reduced to optimal worker count
            assert worker_count < 32
            assert mock_cbf.call_count == 2


class TestCBFIntegrationPatterns:
    """Test CBF integration patterns across actuators."""

    @pytest.mark.asyncio
    async def test_cbf_check_includes_metadata(self):
        """CBF checks include contextual metadata for better decisions."""
        actuator = GPIOActuator(pin=17)
        actuator._running = True
        actuator._backend = "gpiod"

        mock_result = SafetyCheckResult(safe=True, h_x=0.8)
        with patch(
            "kagami.core.hal.adapters.embedded.actuators.gpio.check_cbf_for_operation",
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_cbf:
            try:
                await actuator.set(True)
            except RuntimeError:
                pass

            # Verify metadata was passed
            call_kwargs = mock_cbf.call_args.kwargs
            assert "metadata" in call_kwargs
            assert call_kwargs["metadata"]["backend"] == "gpiod"

    @pytest.mark.asyncio
    async def test_cbf_violations_include_h_value(self):
        """CBF violations include h(x) value for debugging."""
        actuator = GPIOActuator(pin=17)
        actuator._running = True

        mock_result = SafetyCheckResult(safe=False, h_x=-0.75)
        with patch(
            "kagami.core.hal.adapters.embedded.actuators.gpio.check_cbf_for_operation",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            with pytest.raises(CBFViolation) as exc_info:
                await actuator.set(True)

            # Verify h_value is accessible
            assert exc_info.value.h_value == -0.75

    @pytest.mark.asyncio
    async def test_multiple_actuators_independent_cbf_checks(self):
        """Multiple actuators perform independent CBF checks."""
        actuator1 = GPIOActuator(pin=17)
        actuator1._running = True

        actuator2 = GPIOActuator(pin=18)
        actuator2._running = True

        # First actuator passes, second fails
        mock_results = [
            SafetyCheckResult(safe=True, h_x=0.5),  # actuator1
            SafetyCheckResult(safe=False, h_x=-0.1),  # actuator2
        ]

        with patch(
            "kagami.core.hal.adapters.embedded.actuators.gpio.check_cbf_for_operation",
            new_callable=AsyncMock,
            side_effect=mock_results,
        ):
            # First should succeed
            try:
                await actuator1.set(True)
            except RuntimeError:
                pass  # Expected - no backend

            # Second should fail with CBF violation
            with pytest.raises(CBFViolation):
                await actuator2.set(True)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
