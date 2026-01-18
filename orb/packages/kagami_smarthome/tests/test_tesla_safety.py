"""Tests for Tesla Safety Barrier — CBF Hardware-in-the-Loop.

Tests cover:
- Speed-tiered protection (parked/stopped/15mph/45mph thresholds)
- Key card confirmation window (30s timeout)
- Command categorization (BLOCKED, KEY_CARD, SOFT, NONE)
- safe_execute() wrapper flow
- Statistics tracking

Created: January 1, 2026
"""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock

import pytest
from kagami_smarthome.integrations.tesla import (
    DRIVING_PROTECTION,
    DrivingState,
    TeslaSafetyBarrier,
)
from kagami_smarthome.integrations.tesla.tesla import (
    SPEED_THRESHOLD_HIGH,
    SPEED_THRESHOLD_LOW,
)


@pytest.fixture
def mock_integration():
    """Create mock Tesla integration."""
    integration = MagicMock()
    integration._vehicle_id = "123456"
    integration._api_post = AsyncMock(return_value=True)
    return integration


@pytest.fixture
def barrier(mock_integration):
    """Create safety barrier with mock integration."""
    return TeslaSafetyBarrier(mock_integration)


class TestDrivingStateDetection:
    """Test driving state detection from telemetry."""

    @pytest.mark.asyncio
    async def test_parked_state(self, barrier):
        """Test detection of parked state (P gear, 0 speed)."""
        await barrier.on_telemetry_event("ShiftState", "P", time.time())
        await barrier.on_telemetry_event("Speed", 0, time.time())

        assert barrier.driving_state == DrivingState.PARKED
        assert not barrier.is_moving
        assert barrier.speed_mph == 0

    @pytest.mark.asyncio
    async def test_stopped_in_gear(self, barrier):
        """Test detection of stopped in gear (D gear, 0 speed)."""
        await barrier.on_telemetry_event("ShiftState", "D", time.time())
        await barrier.on_telemetry_event("Speed", 0, time.time())

        assert barrier.driving_state == DrivingState.STOPPED
        assert not barrier.is_moving

    @pytest.mark.asyncio
    async def test_moving_state(self, barrier):
        """Test detection of moving state."""
        await barrier.on_telemetry_event("ShiftState", "D", time.time())
        await barrier.on_telemetry_event("Speed", 30, time.time())

        assert barrier.driving_state == DrivingState.MOVING
        assert barrier.is_moving
        assert barrier.speed_mph == 30


class TestParkedAllowsAllCommands:
    """Test that parked state allows all commands."""

    @pytest.mark.asyncio
    async def test_blocked_commands_allowed_when_parked(self, barrier):
        """Even 'blocked' commands should work when parked."""
        await barrier.on_telemetry_event("ShiftState", "P", time.time())
        await barrier.on_telemetry_event("Speed", 0, time.time())

        # erase_user_data is BLOCKED while driving
        allowed, reason = barrier.check_command("erase_user_data")
        assert allowed is True
        assert reason == "parked"

    @pytest.mark.asyncio
    async def test_key_card_commands_allowed_when_parked(self, barrier):
        """KEY_CARD commands should not need confirmation when parked."""
        await barrier.on_telemetry_event("ShiftState", "P", time.time())
        await barrier.on_telemetry_event("Speed", 0, time.time())

        allowed, reason = barrier.check_command("speed_limit_deactivate")
        assert allowed is True
        assert reason == "parked"

    @pytest.mark.asyncio
    async def test_all_commands_allowed_when_parked(self, barrier):
        """All commands from the protection dict should be allowed when parked."""
        await barrier.on_telemetry_event("ShiftState", "P", time.time())
        await barrier.on_telemetry_event("Speed", 0, time.time())

        for command in DRIVING_PROTECTION.keys():
            allowed, reason = barrier.check_command(command)
            assert allowed is True, f"Command {command} should be allowed when parked"
            assert reason == "parked"


class TestStoppedInGear:
    """Test commands when stopped in gear (D/R/N at 0 mph)."""

    @pytest.mark.asyncio
    async def test_blocked_commands_not_allowed_stopped(self, barrier):
        """BLOCKED commands should not be allowed even when stopped in gear."""
        await barrier.on_telemetry_event("ShiftState", "D", time.time())
        await barrier.on_telemetry_event("Speed", 0, time.time())

        allowed, reason = barrier.check_command("erase_user_data")
        assert allowed is False
        assert "blocked" in reason

    @pytest.mark.asyncio
    async def test_key_card_commands_allowed_stopped(self, barrier):
        """KEY_CARD commands should be allowed when stopped."""
        await barrier.on_telemetry_event("ShiftState", "D", time.time())
        await barrier.on_telemetry_event("Speed", 0, time.time())

        allowed, reason = barrier.check_command("speed_limit_deactivate")
        assert allowed is True
        assert reason == "stopped"


class TestLowSpeedProtection:
    """Test protection at low speed (<15 mph)."""

    @pytest.mark.asyncio
    async def test_key_card_downgraded_at_low_speed(self, barrier):
        """KEY_CARD commands should be downgraded to allowed at low speed."""
        await barrier.on_telemetry_event("ShiftState", "D", time.time())
        await barrier.on_telemetry_event("Speed", 10, time.time())

        allowed, reason = barrier.check_command("speed_limit_deactivate")
        assert allowed is True
        assert "low_speed" in reason

    @pytest.mark.asyncio
    async def test_soft_allowed_at_low_speed(self, barrier):
        """SOFT commands should be allowed at low speed."""
        await barrier.on_telemetry_event("ShiftState", "D", time.time())
        await barrier.on_telemetry_event("Speed", 10, time.time())

        allowed, reason = barrier.check_command("door_unlock")
        assert allowed is True

    @pytest.mark.asyncio
    async def test_blocked_still_blocked_at_low_speed(self, barrier):
        """BLOCKED commands should remain blocked at low speed."""
        await barrier.on_telemetry_event("ShiftState", "D", time.time())
        await barrier.on_telemetry_event("Speed", 10, time.time())

        allowed, reason = barrier.check_command("erase_user_data")
        assert allowed is False


class TestHighwaySpeedProtection:
    """Test protection at highway speed (>45 mph)."""

    @pytest.mark.asyncio
    async def test_key_card_required_at_highway(self, barrier):
        """KEY_CARD commands should require confirmation at highway speed."""
        await barrier.on_telemetry_event("ShiftState", "D", time.time())
        await barrier.on_telemetry_event("Speed", 65, time.time())

        allowed, reason = barrier.check_command("speed_limit_deactivate")
        assert allowed is False
        assert "key_card_required" in reason

    @pytest.mark.asyncio
    async def test_soft_allowed_at_highway_with_warning(self, barrier):
        """SOFT commands should be allowed at highway speed (passenger may need)."""
        await barrier.on_telemetry_event("ShiftState", "D", time.time())
        await barrier.on_telemetry_event("Speed", 65, time.time())

        allowed, reason = barrier.check_command("door_unlock")
        assert allowed is True
        assert "soft" in reason or "soft_confirm" in reason

    @pytest.mark.asyncio
    async def test_climate_commands_always_allowed(self, barrier):
        """Climate commands should always be allowed even at highway speed."""
        await barrier.on_telemetry_event("ShiftState", "D", time.time())
        await barrier.on_telemetry_event("Speed", 75, time.time())

        # auto_conditioning_start is not in DRIVING_PROTECTION, so default NONE
        allowed, reason = barrier.check_command("auto_conditioning_start")
        assert allowed is True


class TestKeyCardConfirmation:
    """Test key card confirmation flow."""

    @pytest.mark.asyncio
    async def test_key_card_tap_confirms_pending_request(self, barrier):
        """Key card tap should confirm pending requests."""
        await barrier.on_telemetry_event("ShiftState", "D", time.time())
        await barrier.on_telemetry_event("Speed", 65, time.time())

        # Request confirmation
        request = await barrier.request_confirmation("speed_limit_deactivate", {})
        assert request.confirmed is False

        # Simulate key card tap
        await barrier.on_telemetry_event("KeyCardPresent", True, time.time())

        # Should be confirmed now
        assert request.confirmed is True

    @pytest.mark.asyncio
    async def test_key_card_validity_window(self, barrier):
        """Key card should be valid for a short window after tap."""
        await barrier.on_telemetry_event("ShiftState", "D", time.time())
        await barrier.on_telemetry_event("Speed", 65, time.time())

        # No key card tap yet
        assert barrier._is_key_card_valid() is False

        # Simulate key card tap
        await barrier.on_telemetry_event("KeyCardPresent", True, time.time())

        # Should be valid now
        assert barrier._is_key_card_valid() is True

        # After validity window, should expire
        barrier._state.last_key_card_tap = time.time() - 10  # 10s ago
        assert barrier._is_key_card_valid() is False

    @pytest.mark.asyncio
    async def test_confirmation_request_expiry(self, barrier):
        """Confirmation requests should expire after window."""
        request = await barrier.request_confirmation("speed_limit_deactivate", {})

        # Set expired time
        request.expires_at = time.time() - 1

        assert request.is_expired is True

    @pytest.mark.asyncio
    async def test_wait_for_confirmation_timeout(self, barrier):
        """wait_for_confirmation should timeout properly."""
        request = await barrier.request_confirmation("speed_limit_deactivate", {})

        # Wait with very short timeout
        confirmed = await barrier.wait_for_confirmation(request, timeout=0.1)

        assert confirmed is False
        assert barrier._stats["confirmations_expired"] >= 1


class TestSafeExecuteWrapper:
    """Test the safe_execute() wrapper."""

    @pytest.mark.asyncio
    async def test_safe_execute_allowed_command(self, barrier):
        """safe_execute should execute allowed commands directly."""
        await barrier.on_telemetry_event("ShiftState", "P", time.time())
        await barrier.on_telemetry_event("Speed", 0, time.time())

        mock_executor = MagicMock()
        mock_executor.honk_horn = AsyncMock(return_value=True)

        success, reason = await barrier.safe_execute(mock_executor, "honk_horn")

        assert success is True
        mock_executor.honk_horn.assert_called_once()

    @pytest.mark.asyncio
    async def test_safe_execute_blocked_command(self, barrier):
        """safe_execute should block blocked commands."""
        await barrier.on_telemetry_event("ShiftState", "D", time.time())
        await barrier.on_telemetry_event("Speed", 30, time.time())

        mock_executor = MagicMock()
        mock_executor.erase_user_data = AsyncMock(return_value=True)

        success, reason = await barrier.safe_execute(mock_executor, "erase_user_data")

        assert success is False
        mock_executor.erase_user_data.assert_not_called()


class TestStatisticsTracking:
    """Test statistics tracking."""

    @pytest.mark.asyncio
    async def test_commands_checked_increments(self, barrier):
        """Stats should track commands checked."""
        initial = barrier._stats["commands_checked"]

        barrier.check_command("honk_horn")
        barrier.check_command("flash_lights")

        assert barrier._stats["commands_checked"] == initial + 2

    @pytest.mark.asyncio
    async def test_commands_allowed_increments(self, barrier):
        """Stats should track commands allowed."""
        await barrier.on_telemetry_event("ShiftState", "P", time.time())

        initial = barrier._stats["commands_allowed"]

        barrier.check_command("honk_horn")

        assert barrier._stats["commands_allowed"] == initial + 1

    @pytest.mark.asyncio
    async def test_commands_blocked_increments(self, barrier):
        """Stats should track commands blocked."""
        await barrier.on_telemetry_event("ShiftState", "D", time.time())
        await barrier.on_telemetry_event("Speed", 65, time.time())

        initial = barrier._stats["commands_blocked"]

        barrier.check_command("erase_user_data")

        assert barrier._stats["commands_blocked"] == initial + 1

    def test_stats_property(self, barrier):
        """Stats property should return full stats dict."""
        stats = barrier.stats

        assert "commands_checked" in stats
        assert "commands_allowed" in stats
        assert "commands_blocked" in stats
        assert "confirmations_requested" in stats
        assert "driving_state" in stats
        assert "speed_mph" in stats


# NOTE: TestUtilityFunctions removed - get_protection_level and list_protected_commands
# were removed in Tesla consolidation (commit 54147d4fb)


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_speed_at_exact_threshold(self, barrier):
        """Test behavior at exact speed thresholds."""
        await barrier.on_telemetry_event("ShiftState", "D", time.time())

        # At exactly 15 mph (low threshold)
        await barrier.on_telemetry_event("Speed", SPEED_THRESHOLD_LOW, time.time())
        allowed, reason = barrier.check_command("speed_limit_deactivate")
        # At threshold should use the lower tier (< comparison)
        # 15 mph is NOT < 15, so it goes to medium speed logic
        assert allowed is False or "key_card" in reason

        # At exactly 45 mph (high threshold)
        await barrier.on_telemetry_event("Speed", SPEED_THRESHOLD_HIGH, time.time())
        allowed, reason = barrier.check_command("speed_limit_deactivate")
        # 45 is NOT < 45, so it's highway speed
        assert allowed is False

    @pytest.mark.asyncio
    async def test_unknown_shift_state(self, barrier):
        """Test behavior with unknown shift state."""
        await barrier.on_telemetry_event("ShiftState", "X", time.time())
        await barrier.on_telemetry_event("Speed", 0, time.time())

        assert barrier.driving_state == DrivingState.UNKNOWN

    @pytest.mark.asyncio
    async def test_null_values_in_telemetry(self, barrier):
        """Test handling of null values in telemetry."""
        await barrier.on_telemetry_event("Speed", None, time.time())
        assert barrier.speed_mph == 0.0

        await barrier.on_telemetry_event("ShiftState", None, time.time())
        assert barrier._state.shift_state == "P"  # Defaults to P


class TestConfirmationCallbacks:
    """Test confirmation callback system."""

    @pytest.mark.asyncio
    async def test_callback_called_on_confirmation(self, barrier):
        """Callbacks should be called when confirmation received."""
        callback_results = []

        async def test_callback(token: str, confirmed: bool):
            callback_results.append((token, confirmed))

        barrier.on_confirmation(test_callback)

        await barrier.on_telemetry_event("ShiftState", "D", time.time())
        await barrier.on_telemetry_event("Speed", 65, time.time())

        # Request confirmation
        await barrier.request_confirmation("speed_limit_deactivate", {})

        # Simulate key card tap
        await barrier.on_telemetry_event("KeyCardPresent", True, time.time())

        # Callback should have been called
        assert len(callback_results) == 1
        assert callback_results[0][1] is True  # confirmed=True
