"""Tests for Apple Health Integration.

Created: December 30, 2025
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from kagami_smarthome.integrations.apple_health import (
    ActivityData,
    AppleHealthIntegration,
    HealthMetricType,
    HealthState,
    HeartData,
    RespiratoryData,
    SleepData,
    WorkoutData,
    WorkoutType,
    get_apple_health,
)


class TestHeartData:
    """Tests for HeartData dataclass."""

    def test_default_values(self):
        """Test default HeartData values."""
        heart = HeartData()
        assert heart.heart_rate is None
        assert heart.resting_heart_rate is None
        assert heart.hrv is None

    def test_is_elevated_normal(self):
        """Test elevated check with normal heart rate."""
        heart = HeartData(heart_rate=72, resting_heart_rate=70)
        assert not heart.is_elevated

    def test_is_elevated_high(self):
        """Test elevated check with high heart rate."""
        heart = HeartData(heart_rate=130, resting_heart_rate=70)
        assert heart.is_elevated

    def test_hrv_status_good(self):
        """Test HRV status interpretation - good."""
        heart = HeartData(hrv=60)
        assert heart.hrv_status == "good"

    def test_hrv_status_moderate(self):
        """Test HRV status interpretation - moderate."""
        heart = HeartData(hrv=40)
        assert heart.hrv_status == "moderate"

    def test_hrv_status_low(self):
        """Test HRV status interpretation - low."""
        heart = HeartData(hrv=20)
        assert heart.hrv_status == "low"


class TestSleepData:
    """Tests for SleepData dataclass."""

    def test_default_values(self):
        """Test default SleepData values."""
        sleep = SleepData()
        assert sleep.total_duration_hours == 0.0
        assert sleep.quality_score == 0

    def test_sleep_quality_excellent(self):
        """Test sleep quality assessment - excellent."""
        sleep = SleepData(quality_score=85)
        assert sleep.sleep_quality == "excellent"

    def test_sleep_quality_good(self):
        """Test sleep quality assessment - good."""
        sleep = SleepData(quality_score=65)
        assert sleep.sleep_quality == "good"

    def test_sleep_quality_fair(self):
        """Test sleep quality assessment - fair."""
        sleep = SleepData(quality_score=45)
        assert sleep.sleep_quality == "fair"

    def test_sleep_quality_poor(self):
        """Test sleep quality assessment - poor."""
        sleep = SleepData(quality_score=30)
        assert sleep.sleep_quality == "poor"

    def test_deep_sleep_percentage(self):
        """Test deep sleep percentage calculation."""
        sleep = SleepData(total_duration_hours=8.0, deep_hours=1.6)
        assert sleep.deep_sleep_percentage == 20.0


class TestActivityData:
    """Tests for ActivityData dataclass."""

    def test_default_values(self):
        """Test default ActivityData values."""
        activity = ActivityData()
        assert activity.steps == 0
        assert activity.active_calories == 0

    def test_move_ring_progress(self):
        """Test move ring progress calculation."""
        activity = ActivityData(active_calories=250, move_goal=500)
        assert activity.move_ring_progress == 0.5

    def test_exercise_ring_progress(self):
        """Test exercise ring progress calculation."""
        activity = ActivityData(exercise_minutes=15, exercise_goal=30)
        assert activity.exercise_ring_progress == 0.5

    def test_stand_ring_progress(self):
        """Test stand ring progress calculation."""
        activity = ActivityData(stand_hours=6, stand_goal=12)
        assert activity.stand_ring_progress == 0.5

    def test_all_rings_closed(self):
        """Test all rings closed check."""
        activity = ActivityData(
            active_calories=600,
            move_goal=500,
            exercise_minutes=45,
            exercise_goal=30,
            stand_hours=14,
            stand_goal=12,
        )
        assert activity.all_rings_closed

    def test_rings_not_closed(self):
        """Test all rings not closed."""
        activity = ActivityData(
            active_calories=200,
            move_goal=500,
            exercise_minutes=10,
            exercise_goal=30,
            stand_hours=5,
            stand_goal=12,
        )
        assert not activity.all_rings_closed


class TestRespiratoryData:
    """Tests for RespiratoryData dataclass."""

    def test_oxygen_status_normal(self):
        """Test oxygen status - normal."""
        resp = RespiratoryData(blood_oxygen=98)
        assert resp.oxygen_status == "normal"

    def test_oxygen_status_low(self):
        """Test oxygen status - low."""
        resp = RespiratoryData(blood_oxygen=92)
        assert resp.oxygen_status == "low"

    def test_oxygen_status_critical(self):
        """Test oxygen status - critical."""
        resp = RespiratoryData(blood_oxygen=85)
        assert resp.oxygen_status == "critical"


class TestHealthState:
    """Tests for HealthState dataclass."""

    def test_to_dict(self):
        """Test conversion to dictionary."""
        state = HealthState()
        state.heart.heart_rate = 72
        state.activity.steps = 5000

        result = state.to_dict()

        assert result["heart"]["heart_rate"] == 72
        assert result["activity"]["steps"] == 5000
        assert "sleep" in result
        assert "respiratory" in result


class TestAppleHealthIntegration:
    """Tests for AppleHealthIntegration class."""

    def test_initialization(self):
        """Test integration initialization."""
        health = AppleHealthIntegration()
        assert not health.is_connected
        assert health._state is not None

    def test_get_state(self):
        """Test getting health state."""
        health = AppleHealthIntegration()
        state = health.get_state()
        assert isinstance(state, HealthState)

    def test_get_heart_data(self):
        """Test getting heart data."""
        health = AppleHealthIntegration()
        heart = health.get_heart_data()
        assert isinstance(heart, HeartData)

    def test_get_sleep_data(self):
        """Test getting sleep data."""
        health = AppleHealthIntegration()
        sleep = health.get_sleep_data()
        assert isinstance(sleep, SleepData)

    def test_get_activity_data(self):
        """Test getting activity data."""
        health = AppleHealthIntegration()
        activity = health.get_activity_data()
        assert isinstance(activity, ActivityData)

    def test_get_stats(self):
        """Test getting integration stats."""
        health = AppleHealthIntegration()
        stats = health.get_stats()

        assert "connected" in stats
        assert "has_terra" in stats
        assert "samples_received" in stats

    @pytest.mark.asyncio
    async def test_connect_without_terra(self):
        """Test connection without Terra API."""
        health = AppleHealthIntegration()

        with patch.object(health, "_session", MagicMock()):
            result = await health.connect()
            # Should succeed in webhook-only mode
            assert result is True

    @pytest.mark.asyncio
    async def test_process_webhook(self):
        """Test processing webhook data."""
        health = AppleHealthIntegration()
        health._initialized = True

        payload = {
            "data": {
                "metrics": [
                    {
                        "name": "heart_rate",
                        "units": "bpm",
                        "data": [{"qty": 72, "date": "2025-12-30T10:00:00"}],
                    },
                    {
                        "name": "steps",
                        "units": "count",
                        "data": [{"qty": 5000, "date": "2025-12-30T10:00:00"}],
                    },
                ]
            }
        }

        await health.process_webhook(payload)

        assert health._state.heart.heart_rate == 72.0
        assert health._state.activity.steps == 5000

    def test_map_metric_name(self):
        """Test metric name mapping."""
        health = AppleHealthIntegration()

        # Test HealthKit identifiers
        assert (
            health._map_metric_name("HKQuantityTypeIdentifierHeartRate")
            == HealthMetricType.HEART_RATE
        )

        # Test common names
        assert health._map_metric_name("heart_rate") == HealthMetricType.HEART_RATE
        assert health._map_metric_name("steps") == HealthMetricType.STEPS
        assert health._map_metric_name("hrv") == HealthMetricType.HEART_RATE_VARIABILITY

    def test_event_callback_registration(self):
        """Test event callback registration."""
        health = AppleHealthIntegration()

        callback = AsyncMock()
        health.on_event(callback)

        assert callback in health._callbacks

        health.remove_callback(callback)
        assert callback not in health._callbacks

    def test_calculate_sleep_quality(self):
        """Test sleep quality score calculation."""
        health = AppleHealthIntegration()

        # Good sleep
        health._state.sleep.total_duration_hours = 8.0
        health._state.sleep.deep_hours = 1.6  # 20%
        health._state.sleep.sleep_efficiency = 0.9

        score = health._calculate_sleep_quality()
        assert score >= 80  # Should be excellent


class TestFactoryFunction:
    """Tests for factory functions."""

    def test_get_apple_health_singleton(self):
        """Test that get_apple_health returns singleton."""
        import kagami_smarthome.integrations.apple_health as module

        # Reset singleton
        module._apple_health = None

        health1 = get_apple_health()
        health2 = get_apple_health()

        assert health1 is health2


class TestHealthMetricType:
    """Tests for HealthMetricType enum."""

    def test_all_types_exist(self):
        """Test that all expected metric types exist."""
        expected = [
            "HEART_RATE",
            "RESTING_HEART_RATE",
            "HEART_RATE_VARIABILITY",
            "SLEEP_ANALYSIS",
            "STEPS",
            "ACTIVE_CALORIES",
            "BLOOD_OXYGEN",
            "WEIGHT",
        ]

        for name in expected:
            assert hasattr(HealthMetricType, name)


class TestWorkoutData:
    """Tests for WorkoutData dataclass."""

    def test_workout_creation(self):
        """Test workout data creation."""
        workout = WorkoutData(
            workout_type=WorkoutType.RUNNING,
            duration_minutes=30.0,
            calories_burned=300,
            distance_miles=3.1,
            avg_heart_rate=145,
        )

        assert workout.workout_type == WorkoutType.RUNNING
        assert workout.duration_minutes == 30.0
        assert workout.calories_burned == 300
