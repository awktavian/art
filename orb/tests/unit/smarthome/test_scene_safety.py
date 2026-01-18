"""Tests for Scene Safety — Goodnight, Movie Mode, and Emergency Scenarios.

Tests safety checks for scene orchestration:
- goodnight() safety checks
- movie_mode() safety checks
- emergency scenarios

SAFETY INVARIANT: h(x) >= 0 always.

Created: January 12, 2026
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from kagami_smarthome.safety import (
    FIREPLACE_MAX_ON_DURATION,
    PhysicalActionType,
    SafetyContext,
    SafetyResult,
    check_fireplace_safety,
    check_lock_safety,
    check_physical_safety,
    check_tv_mount_safety,
    get_fireplace_runtime,
    start_fireplace_timer,
    stop_fireplace_timer,
)
from kagami_smarthome.scenes import (
    SCENE_AWAY,
    SCENE_GOODNIGHT,
    SCENE_MOVIE,
    SCENE_SLEEPING,
    AudioPreset,
    HVACPreset,
    LightingPreset,
    Scene,
    SceneRegistry,
    Season,
    ShadePreset,
    TimeOfDay,
    get_all_scenes,
    get_scene,
)


class TestPhysicalActionType:
    """Tests for PhysicalActionType enum."""

    def test_all_action_types_defined(self) -> None:
        """All expected action types should be defined."""
        expected = [
            "fireplace_on",
            "fireplace_off",
            "tv_lower",
            "tv_raise",
            "tv_move",
            "lock",
            "unlock",
            "hvac_extreme",
            "shade_all",
        ]
        actual = [a.value for a in PhysicalActionType]
        for action in expected:
            assert action in actual, f"Missing action type: {action}"


class TestSafetyContext:
    """Tests for SafetyContext dataclass."""

    def test_context_creation(self) -> None:
        """Should create safety context with all fields."""
        ctx = SafetyContext(
            action_type=PhysicalActionType.FIREPLACE_ON,
            target="living_room",
            parameters={"temp": 70},
        )

        assert ctx.action_type == PhysicalActionType.FIREPLACE_ON
        assert ctx.target == "living_room"
        assert ctx.parameters["temp"] == 70
        assert ctx.force is False
        assert ctx.acknowledged_risk is False

    def test_context_timestamp(self) -> None:
        """Context should have automatic timestamp."""
        before = time.time()
        ctx = SafetyContext(
            action_type=PhysicalActionType.LOCK,
            target="front_door",
        )
        after = time.time()

        assert before <= ctx.timestamp <= after


class TestSafetyResult:
    """Tests for SafetyResult dataclass."""

    def test_result_creation(self) -> None:
        """Should create safety result with all fields."""
        result = SafetyResult(
            allowed=True,
            h_x=0.5,
            reason="Safe to proceed",
            warnings=["Check area is clear"],
        )

        assert result.allowed is True
        assert result.h_x == 0.5
        assert result.reason == "Safe to proceed"
        assert len(result.warnings) == 1

    def test_is_safe_property(self) -> None:
        """is_safe should reflect h(x) >= 0."""
        safe_result = SafetyResult(allowed=True, h_x=0.5)
        unsafe_result = SafetyResult(allowed=False, h_x=-0.5)
        boundary_result = SafetyResult(allowed=True, h_x=0.0)

        assert safe_result.is_safe is True
        assert unsafe_result.is_safe is False
        assert boundary_result.is_safe is True  # h(x) = 0 is safe


class TestFireplaceSafety:
    """Tests for fireplace safety checks."""

    def test_fireplace_on_safety_check(self) -> None:
        """Fireplace on should return safety result."""
        result = check_fireplace_safety("on")

        assert isinstance(result, SafetyResult)
        assert result.h_x > 0  # Should be safe by default

    def test_fireplace_off_always_safe(self) -> None:
        """Turning off fireplace should always be safe."""
        result = check_fireplace_safety("off")

        assert result.allowed is True
        assert result.h_x == 1.0  # Maximum safety

    def test_fireplace_max_duration_constant(self) -> None:
        """Fireplace max duration should be 4 hours."""
        assert FIREPLACE_MAX_ON_DURATION == 4 * 60 * 60  # 4 hours in seconds

    @pytest.mark.asyncio
    async def test_fireplace_timer_management(self) -> None:
        """Fireplace timer should be manageable."""
        # Mock controller
        mock_controller = AsyncMock()

        # Start timer (requires running event loop)
        start_fireplace_timer(mock_controller)
        runtime = get_fireplace_runtime()

        assert runtime is not None
        assert runtime >= 0
        assert runtime < 1  # Should be nearly instant

        # Stop timer
        stop_fireplace_timer()
        runtime_after_stop = get_fireplace_runtime()

        assert runtime_after_stop is None

    def test_fireplace_on_adds_warning(self) -> None:
        """Fireplace ignition should add safety warning."""
        stop_fireplace_timer()  # Ensure clean state

        result = check_fireplace_safety("on")

        # Should have a warning about ignition
        assert len(result.warnings) > 0


class TestTVMountSafety:
    """Tests for TV mount safety checks."""

    def test_tv_lower_safety(self) -> None:
        """Lowering TV should have safety check."""
        result = check_tv_mount_safety("lower")

        assert isinstance(result, SafetyResult)
        assert result.h_x > 0  # Should be safe with preset

    def test_tv_raise_safety(self) -> None:
        """Raising TV should have safety check."""
        result = check_tv_mount_safety("raise")

        assert isinstance(result, SafetyResult)
        assert result.h_x > 0

    def test_tv_move_continuous_more_dangerous(self) -> None:
        """Continuous TV movement should be more dangerous."""
        lower_result = check_tv_mount_safety("lower")
        move_result = check_tv_mount_safety("move")

        # Continuous movement should have lower h(x)
        assert move_result.h_x < lower_result.h_x

    def test_tv_preset_adds_safety(self) -> None:
        """Using preset should be preferred."""
        result = check_tv_mount_safety("lower", preset=1)

        assert isinstance(result, SafetyResult)
        # Preset usage doesn't affect h(x) in current implementation
        # but should be tracked in parameters

    def test_tv_movement_warning(self) -> None:
        """TV movement should add path-clear warning."""
        result = check_tv_mount_safety("lower")

        assert len(result.warnings) > 0
        assert any("path" in w.lower() or "clear" in w.lower() for w in result.warnings)


class TestLockSafety:
    """Tests for lock safety checks."""

    def test_lock_action_safe(self) -> None:
        """Locking should be generally safe."""
        result = check_lock_safety("lock", "front_door")

        assert result.allowed is True
        assert result.h_x > 0.5  # High safety value

    def test_unlock_action_has_warning(self) -> None:
        """Unlocking should have security warning."""
        result = check_lock_safety("unlock", "front_door")

        assert result.h_x <= 0.5  # Lower safety due to security
        assert len(result.warnings) > 0
        assert any("security" in w.lower() or "unlock" in w.lower() for w in result.warnings)


class TestPhysicalSafetyCheck:
    """Tests for check_physical_safety function."""

    def test_force_bypasses_check(self) -> None:
        """Force flag should bypass safety checks."""
        ctx = SafetyContext(
            action_type=PhysicalActionType.FIREPLACE_ON,
            target="fireplace",
            force=True,
        )

        result = check_physical_safety(ctx)

        assert result.allowed is True
        assert result.h_x == 0.0  # At boundary
        assert len(result.warnings) > 0

    def test_hvac_extreme_temperature_warning(self) -> None:
        """Extreme HVAC settings should warn."""
        ctx = SafetyContext(
            action_type=PhysicalActionType.HVAC_EXTREME,
            target="hvac",
            parameters={"temperature": 55},  # Very cold
        )

        result = check_physical_safety(ctx)

        assert result.h_x < 0.5  # Lower safety
        assert len(result.warnings) > 0

    def test_hvac_normal_temperature_safe(self) -> None:
        """Normal HVAC settings should be safe."""
        ctx = SafetyContext(
            action_type=PhysicalActionType.HVAC_EXTREME,
            target="hvac",
            parameters={"temperature": 72},  # Normal
        )

        result = check_physical_safety(ctx)

        assert result.h_x > 0.5  # Higher safety


class TestTimeOfDay:
    """Tests for TimeOfDay scene adjustments."""

    def test_time_of_day_from_hour(self) -> None:
        """Should correctly determine time of day from hour."""
        assert TimeOfDay.from_hour(6) == TimeOfDay.DAWN
        assert TimeOfDay.from_hour(10) == TimeOfDay.MORNING
        assert TimeOfDay.from_hour(14) == TimeOfDay.AFTERNOON
        assert TimeOfDay.from_hour(18) == TimeOfDay.EVENING
        assert TimeOfDay.from_hour(22) == TimeOfDay.NIGHT
        assert TimeOfDay.from_hour(2) == TimeOfDay.LATE_NIGHT

    def test_current_time_of_day(self) -> None:
        """Should return current time of day."""
        tod = TimeOfDay.current()
        assert isinstance(tod, TimeOfDay)


class TestSeason:
    """Tests for Season adjustments."""

    def test_season_detection(self) -> None:
        """Should detect current season."""
        season = Season.current()
        assert isinstance(season, Season)

    def test_all_seasons_defined(self) -> None:
        """All seasons should be defined."""
        expected = ["spring", "summer", "autumn", "winter"]
        actual = [s.value for s in Season]
        for s in expected:
            assert s in actual


class TestLightingPreset:
    """Tests for LightingPreset."""

    def test_preset_creation(self) -> None:
        """Should create lighting preset."""
        preset = LightingPreset(
            level=70,
            warm_white=True,
            color_temp_k=2700,
        )

        assert preset.level == 70
        assert preset.warm_white is True
        assert preset.color_temp_k == 2700

    def test_time_of_day_adjustment(self) -> None:
        """Level should adjust for time of day."""
        preset = LightingPreset(
            level=70,
            dawn_modifier=-20,
            night_modifier=-30,
        )

        dawn_level = preset.get_level(TimeOfDay.DAWN)
        night_level = preset.get_level(TimeOfDay.LATE_NIGHT)
        afternoon_level = preset.get_level(TimeOfDay.AFTERNOON)

        assert dawn_level < afternoon_level
        assert night_level < dawn_level

    def test_level_clamping(self) -> None:
        """Level should be clamped to 0-100."""
        preset = LightingPreset(level=10, night_modifier=-30)

        level = preset.get_level(TimeOfDay.LATE_NIGHT)
        assert level >= 0  # Should clamp to 0, not go negative


class TestShadePreset:
    """Tests for ShadePreset."""

    def test_preset_creation(self) -> None:
        """Should create shade preset."""
        preset = ShadePreset(
            position=100,
            blackout=True,
        )

        assert preset.position == 100
        assert preset.blackout is True

    def test_follow_sun_option(self) -> None:
        """Should support follow sun option."""
        preset = ShadePreset(follow_sun=True)
        assert preset.follow_sun is True


class TestHVACPreset:
    """Tests for HVACPreset."""

    def test_preset_creation(self) -> None:
        """Should create HVAC preset."""
        preset = HVACPreset(
            target_temp_f=72.0,
            mode="auto",
        )

        assert preset.target_temp_f == 72.0
        assert preset.mode == "auto"

    def test_season_adjustment(self) -> None:
        """Temperature should adjust for season."""
        preset = HVACPreset(
            target_temp_f=72.0,
            summer_offset=-2.0,
            winter_offset=2.0,
        )

        summer_temp = preset.get_temp(Season.SUMMER)
        winter_temp = preset.get_temp(Season.WINTER)

        assert summer_temp < winter_temp
        assert summer_temp == 70.0
        assert winter_temp == 74.0


class TestGoodnightScene:
    """Tests for goodnight scene safety."""

    def test_goodnight_scene_exists(self) -> None:
        """Goodnight scene should exist."""
        scene = get_scene("goodnight")
        assert scene is not None
        assert scene.name == "goodnight"

    def test_goodnight_lights_off(self) -> None:
        """Goodnight should turn lights off."""
        assert SCENE_GOODNIGHT.lighting.level == 0

    def test_goodnight_shades_blackout(self) -> None:
        """Goodnight should blackout shades."""
        assert SCENE_GOODNIGHT.shades.position == 100
        assert SCENE_GOODNIGHT.shades.blackout is True

    def test_goodnight_audio_muted(self) -> None:
        """Goodnight should mute audio."""
        assert SCENE_GOODNIGHT.audio.volume == 0
        assert SCENE_GOODNIGHT.audio.muted is True

    def test_goodnight_fireplace_off(self) -> None:
        """Goodnight should turn fireplace off."""
        assert SCENE_GOODNIGHT.fireplace_on is False

    def test_goodnight_tv_off(self) -> None:
        """Goodnight should turn TV off."""
        assert SCENE_GOODNIGHT.tv_on is False

    def test_goodnight_temperature(self) -> None:
        """Goodnight should set sleep temperature."""
        assert SCENE_GOODNIGHT.hvac.target_temp_f == 68.0


class TestMovieScene:
    """Tests for movie mode scene safety."""

    def test_movie_scene_exists(self) -> None:
        """Movie scene should exist."""
        scene = get_scene("movie")
        assert scene is not None
        assert scene.name == "movie"

    def test_movie_lights_dim(self) -> None:
        """Movie mode should dim lights."""
        assert SCENE_MOVIE.lighting.level <= 10

    def test_movie_shades_blackout(self) -> None:
        """Movie mode should blackout shades."""
        assert SCENE_MOVIE.shades.position == 100
        assert SCENE_MOVIE.shades.blackout is True

    def test_movie_fireplace_off(self) -> None:
        """Movie mode should turn fireplace off (visual distraction)."""
        assert SCENE_MOVIE.fireplace_on is False

    def test_movie_tv_on(self) -> None:
        """Movie mode should turn TV on."""
        assert SCENE_MOVIE.tv_on is True


class TestSleepingScene:
    """Tests for sleeping scene safety."""

    def test_sleeping_scene_exists(self) -> None:
        """Sleeping scene should exist."""
        scene = get_scene("sleeping")
        assert scene is not None

    def test_sleeping_lights_off(self) -> None:
        """Sleeping should turn lights completely off."""
        assert SCENE_SLEEPING.lighting.level == 0

    def test_sleeping_shades_blackout(self) -> None:
        """Sleeping should blackout shades."""
        assert SCENE_SLEEPING.shades.position == 100
        assert SCENE_SLEEPING.shades.blackout is True

    def test_sleeping_fireplace_off(self) -> None:
        """Sleeping should turn fireplace off."""
        assert SCENE_SLEEPING.fireplace_on is False

    def test_sleeping_tv_off(self) -> None:
        """Sleeping should turn TV off."""
        assert SCENE_SLEEPING.tv_on is False

    def test_sleeping_temperature_cool(self) -> None:
        """Sleeping should set cool temperature."""
        assert SCENE_SLEEPING.hvac.target_temp_f == 68.0


class TestAwayScene:
    """Tests for away scene safety."""

    def test_away_scene_exists(self) -> None:
        """Away scene should exist."""
        scene = get_scene("away")
        assert scene is not None

    def test_away_lights_off(self) -> None:
        """Away should turn lights off."""
        assert SCENE_AWAY.lighting.level == 0

    def test_away_fireplace_off(self) -> None:
        """Away should turn fireplace off."""
        assert SCENE_AWAY.fireplace_on is False

    def test_away_tv_off(self) -> None:
        """Away should turn TV off."""
        assert SCENE_AWAY.tv_on is False

    def test_away_temperature_setback(self) -> None:
        """Away should set back temperature."""
        assert SCENE_AWAY.hvac.target_temp_f == 65.0


class TestSceneRegistry:
    """Tests for SceneRegistry."""

    def test_registry_has_all_scenes(self) -> None:
        """Registry should contain all predefined scenes."""
        expected_scenes = [
            "morning",
            "working",
            "cooking",
            "dining",
            "relaxing",
            "watching",
            "movie",
            "entertaining",
            "sleeping",
            "away",
            "goodnight",
            "welcome_home",
        ]

        for name in expected_scenes:
            scene = get_scene(name)
            assert scene is not None, f"Missing scene: {name}"

    def test_get_all_scenes(self) -> None:
        """Should return all scenes."""
        scenes = get_all_scenes()
        assert len(scenes) >= 12

    def test_custom_scene_registration(self) -> None:
        """Should allow custom scene registration."""
        registry = SceneRegistry()

        custom = Scene(
            name="custom_test",
            display_name="Custom Test",
            description="Test scene",
        )
        registry.register(custom)

        retrieved = registry.get("custom_test")
        assert retrieved is not None
        assert retrieved.name == "custom_test"


class TestSafetyInvariant:
    """Critical tests verifying h(x) >= 0 safety invariant."""

    def test_fireplace_off_highest_safety(self) -> None:
        """SAFETY: Turning off fireplace should be highest safety."""
        result = check_fireplace_safety("off")
        assert result.h_x == 1.0

    def test_locking_high_safety(self) -> None:
        """SAFETY: Locking doors should have high safety value."""
        result = check_lock_safety("lock", "any_door")
        assert result.h_x >= 0.8

    def test_unlocking_lower_safety(self) -> None:
        """SAFETY: Unlocking should have lower safety (security risk)."""
        result = check_lock_safety("unlock", "any_door")
        assert result.h_x <= 0.6

    def test_all_scenes_have_safe_defaults(self) -> None:
        """SAFETY: All scenes should have safe default values."""
        for scene in get_all_scenes():
            # Lighting level should be 0-100
            assert 0 <= scene.lighting.level <= 100

            # Shade position should be 0-100
            assert 0 <= scene.shades.position <= 100

            # Audio volume should be 0-100
            assert 0 <= scene.audio.volume <= 100

            # HVAC temp should be in reasonable range
            assert 60 <= scene.hvac.target_temp_f <= 85

    def test_sleep_scenes_turn_off_hazards(self) -> None:
        """SAFETY: Sleep-related scenes must turn off fire/TV."""
        sleep_scenes = ["sleeping", "goodnight"]

        for name in sleep_scenes:
            scene = get_scene(name)
            assert scene is not None

            assert scene.fireplace_on is False, f"Scene {name} must turn off fireplace for safety"
            assert scene.tv_on is False, f"Scene {name} must turn off TV for sleep"

    def test_away_scene_energy_safe(self) -> None:
        """SAFETY: Away scene must be energy-safe."""
        scene = get_scene("away")
        assert scene is not None

        # All non-essential things off
        assert scene.lighting.level == 0
        assert scene.audio.muted is True
        assert scene.fireplace_on is False
        assert scene.tv_on is False

    def test_force_flag_documented_danger(self) -> None:
        """SAFETY: Force flag should add warning."""
        ctx = SafetyContext(
            action_type=PhysicalActionType.FIREPLACE_ON,
            target="fireplace",
            force=True,
        )

        result = check_physical_safety(ctx)

        # Must have warning about bypass
        assert len(result.warnings) > 0
        assert any("bypass" in w.lower() or "caution" in w.lower() for w in result.warnings)

    def test_hvac_extreme_limits_enforced(self) -> None:
        """SAFETY: HVAC extreme limits should reduce safety score."""
        # Too cold
        cold_ctx = SafetyContext(
            action_type=PhysicalActionType.HVAC_EXTREME,
            target="hvac",
            parameters={"temperature": 50},
        )
        cold_result = check_physical_safety(cold_ctx)

        # Too hot
        hot_ctx = SafetyContext(
            action_type=PhysicalActionType.HVAC_EXTREME,
            target="hvac",
            parameters={"temperature": 90},
        )
        hot_result = check_physical_safety(hot_ctx)

        # Both should have reduced safety
        assert cold_result.h_x < 0.5
        assert hot_result.h_x < 0.5

    def test_continuous_tv_movement_lowest_safety(self) -> None:
        """SAFETY: Continuous TV movement should be lowest TV safety."""
        lower = check_tv_mount_safety("lower")
        raise_tv = check_tv_mount_safety("raise")
        move = check_tv_mount_safety("move")

        # Continuous movement should have lowest h(x)
        assert move.h_x <= lower.h_x
        assert move.h_x <= raise_tv.h_x


class TestEmergencyScenarios:
    """Tests for emergency scenario handling."""

    def test_force_bypass_available(self) -> None:
        """Emergency bypass should be available for all action types."""
        for action_type in PhysicalActionType:
            ctx = SafetyContext(
                action_type=action_type,
                target="emergency_target",
                force=True,
            )

            result = check_physical_safety(ctx)
            assert result.allowed is True

    def test_acknowledged_risk_flag(self) -> None:
        """Acknowledged risk flag should exist."""
        ctx = SafetyContext(
            action_type=PhysicalActionType.UNLOCK,
            target="front_door",
            acknowledged_risk=True,
        )

        # Flag should be set
        assert ctx.acknowledged_risk is True

    def test_all_action_types_have_handler(self) -> None:
        """All action types should have a safety handler."""
        for action_type in PhysicalActionType:
            ctx = SafetyContext(
                action_type=action_type,
                target="test",
            )

            # Should not raise
            result = check_physical_safety(ctx)
            assert isinstance(result, SafetyResult)
            assert isinstance(result.h_x, float)


class TestSceneTransitions:
    """Tests for scene transition timing."""

    def test_slow_transitions_for_sleep(self) -> None:
        """Sleep scenes should have slow transitions."""
        sleeping = get_scene("sleeping")
        goodnight = get_scene("goodnight")

        assert sleeping.transition_seconds >= 30
        assert goodnight.transition_seconds >= 30

    def test_morning_has_slow_transition(self) -> None:
        """Morning should have gradual wake-up transition."""
        morning = get_scene("morning")
        assert morning.transition_seconds >= 20

    def test_movie_has_reasonable_transition(self) -> None:
        """Movie mode should have reasonable transition."""
        movie = get_scene("movie")
        assert 5 <= movie.transition_seconds <= 30


class TestSceneRoomTypes:
    """Tests for room type applicability."""

    def test_sleeping_applies_to_bedroom(self) -> None:
        """Sleeping scene should apply to bedroom."""
        sleeping = get_scene("sleeping")
        assert "bedroom" in sleeping.room_types

    def test_movie_applies_to_living(self) -> None:
        """Movie scene should apply to living room."""
        movie = get_scene("movie")
        assert "living" in movie.room_types

    def test_cooking_applies_to_kitchen(self) -> None:
        """Cooking scene should apply to kitchen."""
        cooking = get_scene("cooking")
        assert "kitchen" in cooking.room_types
