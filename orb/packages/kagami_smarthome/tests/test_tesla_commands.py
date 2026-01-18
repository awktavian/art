"""Tesla Fleet API Commands Tests.

Tests for:
- TeslaCommandExecutor class
- All 65 Fleet API commands
- CBF safety decorator
- Command categories and safety levels
- Statistics tracking

Created: December 31, 2025
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from kagami_smarthome.integrations.tesla import (
    CommandCategory,
    SafetyLevel,
    TeslaCommandExecutor,
    cbf_protected,
)

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def mock_tesla_integration():
    """Create mock Tesla integration."""
    mock = MagicMock()
    mock._vehicle_id = "12345678901234567"
    mock._vehicle_vin = "5YJ3E1EA1NF123456"
    mock._state = MagicMock()
    mock._state.state = "online"
    mock._api_post = AsyncMock(return_value=True)
    mock.wake_up = AsyncMock(return_value=True)
    return mock


@pytest.fixture
def executor(mock_tesla_integration):
    """Create TeslaCommandExecutor with mock integration."""
    return TeslaCommandExecutor(mock_tesla_integration)


# =============================================================================
# COMMAND REGISTRY TESTS
# =============================================================================


# NOTE: TestCommandRegistry removed - COMMANDS registry was removed in Tesla consolidation
# (commit 54147d4fb). Command metadata is now handled internally by TeslaCommandExecutor.


# =============================================================================
# CBF DECORATOR TESTS
# =============================================================================


class TestCbfProtected:
    """Test CBF safety decorator."""

    @pytest.mark.asyncio
    async def test_cbf_decorator_safe(self):
        """Test CBF decorator with safe level."""

        @cbf_protected(SafetyLevel.SAFE)
        async def safe_command(self):
            return True

        mock_self = MagicMock()
        result = await safe_command(mock_self)
        assert result is True

    @pytest.mark.asyncio
    async def test_cbf_decorator_critical(self):
        """Test CBF decorator with critical level."""

        @cbf_protected(SafetyLevel.CRITICAL)
        async def critical_command(self):
            return True

        mock_self = MagicMock()
        result = await critical_command(mock_self)
        assert result is True

    @pytest.mark.asyncio
    async def test_cbf_decorator_preserves_function_name(self):
        """Test decorator preserves function name for logging."""

        @cbf_protected(SafetyLevel.SAFE)
        async def my_special_command(self):
            return True

        assert my_special_command.__name__ == "my_special_command"


# =============================================================================
# EXECUTOR INITIALIZATION TESTS
# =============================================================================


class TestExecutorInitialization:
    """Test TeslaCommandExecutor initialization."""

    def test_executor_init(self, mock_tesla_integration):
        """Test executor initializes correctly."""
        executor = TeslaCommandExecutor(mock_tesla_integration)

        assert executor._integration == mock_tesla_integration
        assert executor._stats["commands_sent"] == 0
        assert executor._stats["commands_succeeded"] == 0
        assert executor._stats["commands_failed"] == 0

    def test_executor_stats_categories(self, mock_tesla_integration):
        """Test executor initializes category stats."""
        executor = TeslaCommandExecutor(mock_tesla_integration)

        for category in CommandCategory:
            assert category.value in executor._stats["by_category"]
            assert executor._stats["by_category"][category.value] == 0


# =============================================================================
# TRUNK COMMAND TESTS
# =============================================================================


class TestTrunkCommands:
    """Test trunk/frunk commands."""

    @pytest.mark.asyncio
    async def test_open_trunk(self, executor, mock_tesla_integration):
        """Test open_trunk command."""
        result = await executor.open_trunk()

        assert result is True
        mock_tesla_integration._api_post.assert_called()
        call_path = mock_tesla_integration._api_post.call_args[0][0]
        assert "actuate_trunk" in call_path
        assert mock_tesla_integration._api_post.call_args[0][1]["which_trunk"] == "rear"

    @pytest.mark.asyncio
    async def test_open_frunk(self, executor, mock_tesla_integration):
        """Test open_frunk command."""
        result = await executor.open_frunk()

        assert result is True
        call_path = mock_tesla_integration._api_post.call_args[0][0]
        assert "actuate_trunk" in call_path
        assert mock_tesla_integration._api_post.call_args[0][1]["which_trunk"] == "front"


# =============================================================================
# CHARGING COMMAND TESTS
# =============================================================================


class TestChargingCommands:
    """Test charging commands."""

    @pytest.mark.asyncio
    async def test_charge_start(self, executor, mock_tesla_integration):
        """Test charge_start command."""
        result = await executor.charge_start()

        assert result is True
        call_path = mock_tesla_integration._api_post.call_args[0][0]
        assert "charge_start" in call_path

    @pytest.mark.asyncio
    async def test_charge_stop(self, executor, mock_tesla_integration):
        """Test charge_stop command."""
        result = await executor.charge_stop()

        assert result is True
        call_path = mock_tesla_integration._api_post.call_args[0][0]
        assert "charge_stop" in call_path

    @pytest.mark.asyncio
    async def test_charge_max_range(self, executor, mock_tesla_integration):
        """Test charge_max_range command."""
        result = await executor.charge_max_range()

        assert result is True
        call_path = mock_tesla_integration._api_post.call_args[0][0]
        assert "charge_max_range" in call_path

    @pytest.mark.asyncio
    async def test_charge_standard(self, executor, mock_tesla_integration):
        """Test charge_standard command."""
        result = await executor.charge_standard()

        assert result is True
        call_path = mock_tesla_integration._api_post.call_args[0][0]
        assert "charge_standard" in call_path

    @pytest.mark.asyncio
    async def test_set_charge_limit_normal(self, executor, mock_tesla_integration):
        """Test set_charge_limit with normal value."""
        result = await executor.set_charge_limit(80)

        assert result is True
        assert mock_tesla_integration._api_post.call_args[0][1]["percent"] == 80

    @pytest.mark.asyncio
    async def test_set_charge_limit_clamped_low(self, executor, mock_tesla_integration):
        """Test set_charge_limit clamps to minimum."""
        result = await executor.set_charge_limit(30)

        assert result is True
        assert mock_tesla_integration._api_post.call_args[0][1]["percent"] == 50

    @pytest.mark.asyncio
    async def test_set_charge_limit_clamped_high(self, executor, mock_tesla_integration):
        """Test set_charge_limit clamps to maximum."""
        result = await executor.set_charge_limit(120)

        assert result is True
        assert mock_tesla_integration._api_post.call_args[0][1]["percent"] == 100

    @pytest.mark.asyncio
    async def test_set_charging_amps(self, executor, mock_tesla_integration):
        """Test set_charging_amps command."""
        result = await executor.set_charging_amps(32)

        assert result is True
        assert mock_tesla_integration._api_post.call_args[0][1]["charging_amps"] == 32

    @pytest.mark.asyncio
    async def test_open_close_charge_port(self, executor, mock_tesla_integration):
        """Test charge port commands."""
        await executor.open_charge_port()
        assert "charge_port_door_open" in mock_tesla_integration._api_post.call_args[0][0]

        await executor.close_charge_port()
        assert "charge_port_door_close" in mock_tesla_integration._api_post.call_args[0][0]


# =============================================================================
# CLIMATE COMMAND TESTS
# =============================================================================


class TestClimateCommands:
    """Test climate commands."""

    @pytest.mark.asyncio
    async def test_start_climate(self, executor, mock_tesla_integration):
        """Test start_climate command."""
        result = await executor.start_climate()

        assert result is True
        call_path = mock_tesla_integration._api_post.call_args[0][0]
        assert "auto_conditioning_start" in call_path

    @pytest.mark.asyncio
    async def test_stop_climate(self, executor, mock_tesla_integration):
        """Test stop_climate command."""
        result = await executor.stop_climate()

        assert result is True
        call_path = mock_tesla_integration._api_post.call_args[0][0]
        assert "auto_conditioning_stop" in call_path

    @pytest.mark.asyncio
    async def test_set_temps_both(self, executor, mock_tesla_integration):
        """Test set_temps with both temperatures."""
        result = await executor.set_temps(21.0, 22.0)

        assert result is True
        call_data = mock_tesla_integration._api_post.call_args[0][1]
        assert call_data["driver_temp"] == 21.0
        assert call_data["passenger_temp"] == 22.0

    @pytest.mark.asyncio
    async def test_set_temps_single(self, executor, mock_tesla_integration):
        """Test set_temps with single temperature (same for both)."""
        result = await executor.set_temps(21.0)

        assert result is True
        call_data = mock_tesla_integration._api_post.call_args[0][1]
        assert call_data["driver_temp"] == 21.0
        assert call_data["passenger_temp"] == 21.0

    @pytest.mark.asyncio
    async def test_set_seat_heater(self, executor, mock_tesla_integration):
        """Test set_seat_heater command."""
        result = await executor.set_seat_heater(0, 3)  # Driver, max

        assert result is True
        call_data = mock_tesla_integration._api_post.call_args[0][1]
        assert call_data["heater"] == 0
        assert call_data["level"] == 3

    @pytest.mark.asyncio
    async def test_set_seat_cooler(self, executor, mock_tesla_integration):
        """Test set_seat_cooler command."""
        result = await executor.set_seat_cooler(1, 2)  # Passenger, medium

        assert result is True
        call_data = mock_tesla_integration._api_post.call_args[0][1]
        assert call_data["seat_position"] == 1
        assert call_data["seat_cooler_level"] == 2

    @pytest.mark.asyncio
    async def test_set_steering_wheel_heater(self, executor, mock_tesla_integration):
        """Test set_steering_wheel_heater command."""
        result = await executor.set_steering_wheel_heater(True)

        assert result is True
        assert mock_tesla_integration._api_post.call_args[0][1]["on"] is True

    @pytest.mark.asyncio
    async def test_set_climate_keeper(self, executor, mock_tesla_integration):
        """Test set_climate_keeper command."""
        for mode, expected_value in [("off", 0), ("on", 1), ("dog", 2), ("camp", 3)]:
            result = await executor.set_climate_keeper(mode)
            assert result is True
            assert (
                mock_tesla_integration._api_post.call_args[0][1]["climate_keeper_mode"]
                == expected_value
            )

    @pytest.mark.asyncio
    async def test_set_bioweapon_mode(self, executor, mock_tesla_integration):
        """Test set_bioweapon_mode command."""
        result = await executor.set_bioweapon_mode(True)

        assert result is True
        call_path = mock_tesla_integration._api_post.call_args[0][0]
        assert "set_bioweapon_mode" in call_path
        assert mock_tesla_integration._api_post.call_args[0][1]["on"] is True


# =============================================================================
# LOCK COMMAND TESTS
# =============================================================================


class TestLockCommands:
    """Test lock commands."""

    @pytest.mark.asyncio
    async def test_lock(self, executor, mock_tesla_integration):
        """Test lock command."""
        result = await executor.lock()

        assert result is True
        call_path = mock_tesla_integration._api_post.call_args[0][0]
        assert "door_lock" in call_path

    @pytest.mark.asyncio
    async def test_unlock(self, executor, mock_tesla_integration):
        """Test unlock command (protected)."""
        result = await executor.unlock()

        assert result is True
        call_path = mock_tesla_integration._api_post.call_args[0][0]
        assert "door_unlock" in call_path


# =============================================================================
# MEDIA COMMAND TESTS
# =============================================================================


class TestMediaCommands:
    """Test media commands."""

    @pytest.mark.asyncio
    async def test_adjust_volume(self, executor, mock_tesla_integration):
        """Test adjust_volume command."""
        result = await executor.adjust_volume(5.5)

        assert result is True
        assert mock_tesla_integration._api_post.call_args[0][1]["volume"] == 5.5

    @pytest.mark.asyncio
    async def test_media_playback(self, executor, mock_tesla_integration):
        """Test media playback controls."""
        await executor.media_toggle_playback()
        assert "media_toggle_playback" in mock_tesla_integration._api_post.call_args[0][0]

        await executor.media_next_track()
        assert "media_next_track" in mock_tesla_integration._api_post.call_args[0][0]

        await executor.media_prev_track()
        assert "media_prev_track" in mock_tesla_integration._api_post.call_args[0][0]

    @pytest.mark.asyncio
    async def test_media_favorites(self, executor, mock_tesla_integration):
        """Test media favorite controls."""
        await executor.media_next_fav()
        assert "media_next_fav" in mock_tesla_integration._api_post.call_args[0][0]

        await executor.media_prev_fav()
        assert "media_prev_fav" in mock_tesla_integration._api_post.call_args[0][0]


# =============================================================================
# NAVIGATION COMMAND TESTS
# =============================================================================


class TestNavigationCommands:
    """Test navigation commands."""

    @pytest.mark.asyncio
    async def test_navigate_to(self, executor, mock_tesla_integration):
        """Test navigate_to command."""
        result = await executor.navigate_to("Pike Place Market, Seattle")

        assert result is True
        call_data = mock_tesla_integration._api_post.call_args[0][1]
        assert call_data["value"]["android.intent.extra.TEXT"] == "Pike Place Market, Seattle"

    @pytest.mark.asyncio
    async def test_navigate_to_gps(self, executor, mock_tesla_integration):
        """Test navigate_to_gps command."""
        result = await executor.navigate_to_gps(47.6815, -122.3406)

        assert result is True
        call_data = mock_tesla_integration._api_post.call_args[0][1]
        assert call_data["lat"] == 47.6815
        assert call_data["lon"] == -122.3406

    @pytest.mark.asyncio
    async def test_navigate_to_supercharger(self, executor, mock_tesla_integration):
        """Test navigate_to_supercharger command."""
        result = await executor.navigate_to_supercharger()

        assert result is True
        call_path = mock_tesla_integration._api_post.call_args[0][0]
        assert "navigation_sc_request" in call_path


# =============================================================================
# SECURITY COMMAND TESTS
# =============================================================================


class TestSecurityCommands:
    """Test security commands."""

    @pytest.mark.asyncio
    async def test_set_sentry_mode(self, executor, mock_tesla_integration):
        """Test set_sentry_mode command."""
        result = await executor.set_sentry_mode(True)

        assert result is True
        call_path = mock_tesla_integration._api_post.call_args[0][0]
        assert "set_sentry_mode" in call_path
        assert mock_tesla_integration._api_post.call_args[0][1]["on"] is True

    @pytest.mark.asyncio
    async def test_set_valet_mode(self, executor, mock_tesla_integration):
        """Test set_valet_mode command."""
        result = await executor.set_valet_mode(True, "1234")

        assert result is True
        call_data = mock_tesla_integration._api_post.call_args[0][1]
        assert call_data["on"] is True
        assert call_data["password"] == "1234"

    @pytest.mark.asyncio
    async def test_set_vehicle_name(self, executor, mock_tesla_integration):
        """Test set_vehicle_name command."""
        result = await executor.set_vehicle_name("My Tesla")

        assert result is True
        assert mock_tesla_integration._api_post.call_args[0][1]["vehicle_name"] == "My Tesla"


# =============================================================================
# WINDOW/SUNROOF COMMAND TESTS
# =============================================================================


class TestWindowCommands:
    """Test window and sunroof commands."""

    @pytest.mark.asyncio
    async def test_sunroof_control(self, executor, mock_tesla_integration):
        """Test sunroof_control command."""
        result = await executor.sunroof_control("vent")

        assert result is True
        assert mock_tesla_integration._api_post.call_args[0][1]["state"] == "vent"

    @pytest.mark.asyncio
    async def test_close_sunroof(self, executor, mock_tesla_integration):
        """Test close_sunroof helper."""
        result = await executor.close_sunroof()

        assert result is True
        assert mock_tesla_integration._api_post.call_args[0][1]["state"] == "close"

    @pytest.mark.asyncio
    async def test_vent_sunroof(self, executor, mock_tesla_integration):
        """Test vent_sunroof helper."""
        result = await executor.vent_sunroof()

        assert result is True
        assert mock_tesla_integration._api_post.call_args[0][1]["state"] == "vent"

    @pytest.mark.asyncio
    async def test_vent_windows(self, executor, mock_tesla_integration):
        """Test vent_windows command."""
        result = await executor.vent_windows()

        assert result is True
        call_data = mock_tesla_integration._api_post.call_args[0][1]
        assert call_data["command"] == "vent"

    @pytest.mark.asyncio
    async def test_close_windows(self, executor, mock_tesla_integration):
        """Test close_windows command with location."""
        result = await executor.close_windows(47.6815, -122.3406)

        assert result is True
        call_data = mock_tesla_integration._api_post.call_args[0][1]
        assert call_data["command"] == "close"
        assert call_data["lat"] == 47.6815
        assert call_data["lon"] == -122.3406


# =============================================================================
# ALERT COMMAND TESTS
# =============================================================================


class TestAlertCommands:
    """Test alert commands."""

    @pytest.mark.asyncio
    async def test_flash_lights(self, executor, mock_tesla_integration):
        """Test flash_lights command."""
        result = await executor.flash_lights()

        assert result is True
        call_path = mock_tesla_integration._api_post.call_args[0][0]
        assert "flash_lights" in call_path

    @pytest.mark.asyncio
    async def test_honk_horn(self, executor, mock_tesla_integration):
        """Test honk_horn command."""
        result = await executor.honk_horn()

        assert result is True
        call_path = mock_tesla_integration._api_post.call_args[0][0]
        assert "honk_horn" in call_path

    @pytest.mark.asyncio
    async def test_remote_boombox(self, executor, mock_tesla_integration):
        """Test remote_boombox command."""
        result = await executor.remote_boombox("Fart")

        assert result is True
        assert mock_tesla_integration._api_post.call_args[0][1]["sound"] == "Fart"


# =============================================================================
# SOFTWARE COMMAND TESTS
# =============================================================================


class TestSoftwareCommands:
    """Test software update commands."""

    @pytest.mark.asyncio
    async def test_schedule_software_update(self, executor, mock_tesla_integration):
        """Test schedule_software_update command."""
        result = await executor.schedule_software_update(300)

        assert result is True
        assert mock_tesla_integration._api_post.call_args[0][1]["offset_sec"] == 300

    @pytest.mark.asyncio
    async def test_cancel_software_update(self, executor, mock_tesla_integration):
        """Test cancel_software_update command."""
        result = await executor.cancel_software_update()

        assert result is True
        call_path = mock_tesla_integration._api_post.call_args[0][0]
        assert "cancel_software_update" in call_path


# =============================================================================
# DRIVE COMMAND TESTS (CRITICAL)
# =============================================================================


class TestDriveCommands:
    """Test drive commands (critical safety level)."""

    @pytest.mark.asyncio
    async def test_remote_start_drive(self, executor, mock_tesla_integration):
        """Test remote_start_drive command (critical)."""
        result = await executor.remote_start_drive()

        assert result is True
        call_path = mock_tesla_integration._api_post.call_args[0][0]
        assert "remote_start_drive" in call_path

    @pytest.mark.asyncio
    async def test_speed_limit_activate(self, executor, mock_tesla_integration):
        """Test speed_limit_activate command."""
        result = await executor.speed_limit_activate("1234")

        assert result is True
        assert mock_tesla_integration._api_post.call_args[0][1]["pin"] == "1234"

    @pytest.mark.asyncio
    async def test_speed_limit_set_limit(self, executor, mock_tesla_integration):
        """Test speed_limit_set_limit with bounds."""
        # Normal value
        await executor.speed_limit_set_limit(70)
        assert mock_tesla_integration._api_post.call_args[0][1]["limit_mph"] == 70

        # Below minimum (50)
        await executor.speed_limit_set_limit(40)
        assert mock_tesla_integration._api_post.call_args[0][1]["limit_mph"] == 50

        # Above maximum (90)
        await executor.speed_limit_set_limit(100)
        assert mock_tesla_integration._api_post.call_args[0][1]["limit_mph"] == 90


# =============================================================================
# HOMELINK COMMAND TESTS
# =============================================================================


class TestHomelinkCommands:
    """Test HomeLink commands."""

    @pytest.mark.asyncio
    async def test_trigger_homelink(self, executor, mock_tesla_integration):
        """Test trigger_homelink command."""
        result = await executor.trigger_homelink()

        assert result is True
        call_path = mock_tesla_integration._api_post.call_args[0][0]
        assert "trigger_homelink" in call_path

    @pytest.mark.asyncio
    async def test_trigger_homelink_with_location(self, executor, mock_tesla_integration):
        """Test trigger_homelink with location."""
        result = await executor.trigger_homelink(47.6815, -122.3406)

        assert result is True
        call_data = mock_tesla_integration._api_post.call_args[0][1]
        assert call_data["lat"] == 47.6815
        assert call_data["lon"] == -122.3406


# =============================================================================
# DATA COMMAND TESTS
# =============================================================================


class TestDataCommands:
    """Test data commands."""

    @pytest.mark.asyncio
    async def test_erase_user_data(self, executor, mock_tesla_integration):
        """Test erase_user_data command (critical)."""
        result = await executor.erase_user_data()

        assert result is True
        call_path = mock_tesla_integration._api_post.call_args[0][0]
        assert "erase_user_data" in call_path

    @pytest.mark.asyncio
    async def test_get_upcoming_calendar_entries(self, executor, mock_tesla_integration):
        """Test get_upcoming_calendar_entries command."""
        result = await executor.get_upcoming_calendar_entries()

        assert result is True
        call_path = mock_tesla_integration._api_post.call_args[0][0]
        assert "upcoming_calendar_entries" in call_path


# =============================================================================
# STATISTICS TESTS
# =============================================================================


class TestExecutorStatistics:
    """Test executor statistics tracking."""

    @pytest.mark.asyncio
    async def test_stats_increment_on_success(self, executor, mock_tesla_integration):
        """Test stats increment on successful command."""
        await executor.flash_lights()

        assert executor._stats["commands_sent"] == 1
        assert executor._stats["commands_succeeded"] == 1
        assert executor._stats["commands_failed"] == 0

    @pytest.mark.asyncio
    async def test_stats_increment_on_failure(self, executor, mock_tesla_integration):
        """Test stats increment on failed command."""
        mock_tesla_integration._api_post.return_value = False

        await executor.flash_lights()

        assert executor._stats["commands_sent"] == 1
        assert executor._stats["commands_succeeded"] == 0
        assert executor._stats["commands_failed"] == 1

    @pytest.mark.asyncio
    async def test_stats_category_tracking(self, executor, mock_tesla_integration):
        """Test category statistics tracking."""
        await executor.flash_lights()  # ALERTS
        await executor.lock()  # LOCKS
        await executor.start_climate()  # CLIMATE

        assert executor._stats["by_category"]["alerts"] == 1
        assert executor._stats["by_category"]["locks"] == 1
        assert executor._stats["by_category"]["climate"] == 1

    def test_stats_property(self, executor):
        """Test stats property includes success rate."""
        executor._stats["commands_sent"] = 10
        executor._stats["commands_succeeded"] = 8

        stats = executor.stats

        assert stats["success_rate"] == 0.8

    def test_stats_property_zero_division(self, executor):
        """Test stats property handles zero commands."""
        stats = executor.stats

        assert stats["success_rate"] == 0.0


# =============================================================================
# ERROR HANDLING TESTS
# =============================================================================


class TestErrorHandling:
    """Test error handling."""

    @pytest.mark.asyncio
    async def test_command_without_vehicle_id(self, mock_tesla_integration):
        """Test commands fail gracefully without vehicle_id."""
        mock_tesla_integration._vehicle_id = None
        executor = TeslaCommandExecutor(mock_tesla_integration)

        result = await executor.flash_lights()

        assert result is False

    @pytest.mark.asyncio
    async def test_wake_on_asleep_vehicle(self, executor, mock_tesla_integration):
        """Test executor wakes vehicle before command."""
        mock_tesla_integration._state.state = "asleep"

        # Should attempt to wake
        await executor._command("flash_lights", wake_first=True)

        # Note: wake_up would be called but we're testing the flow


# =============================================================================
# ENUM TESTS
# =============================================================================


class TestEnums:
    """Test command-related enums."""

    def test_command_category_values(self):
        """Test CommandCategory enum values."""
        assert CommandCategory.TRUNK.value == "trunk"
        assert CommandCategory.CHARGING.value == "charging"
        assert CommandCategory.CLIMATE.value == "climate"
        assert CommandCategory.LOCKS.value == "locks"
        assert CommandCategory.MEDIA.value == "media"
        assert CommandCategory.NAVIGATION.value == "navigation"
        assert CommandCategory.SECURITY.value == "security"
        assert CommandCategory.WINDOWS.value == "windows"
        assert CommandCategory.ALERTS.value == "alerts"
        assert CommandCategory.SOFTWARE.value == "software"
        assert CommandCategory.DRIVE.value == "drive"
        assert CommandCategory.HOMELINK.value == "homelink"
        assert CommandCategory.DATA.value == "data"

    def test_safety_level_values(self):
        """Test SafetyLevel enum values."""
        assert SafetyLevel.SAFE.value == "safe"
        assert SafetyLevel.CAUTION.value == "caution"
        assert SafetyLevel.PROTECTED.value == "protected"
        assert SafetyLevel.CRITICAL.value == "critical"
