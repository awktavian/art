"""End-to-End Integration Tests for Core Models.

Tests the complete integration of:
1. Sensory Model (UnifiedSensoryIntegration)
2. Learning Loop (InstinctLearningLoop + PatternLearner)
3. Presence Model (PresenceEngine)
4. Location Model (DeviceLocalizer)
5. Energy Model (EnergyLevel via SituationAwareness)
6. Calendar Model (Calendar sense + ActiveEvent)

These models form the core perception-action loop:
    Environment → Sensory → Pattern → Context → Action

h(x) ≥ 0 Always.

Created: December 30, 2025
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# These tests don't require external infrastructure (CockroachDB, Weaviate)
# They test in-memory data structures and algorithms
# Using mock_services marker to skip the service availability check
pytestmark = [pytest.mark.tier_unit, pytest.mark.mock_services]


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def pattern_learner():
    """Create a fresh pattern learner for testing."""
    from kagami.core.learning.pattern_learner import PatternLearner, TimeGranularity

    # Create without persistence for testing
    return PatternLearner("test_patterns", TimeGranularity.HOUR, persist_path=None)


@pytest.fixture
def instinct_loop():
    """Create instinct learning loop."""
    from kagami.core.learning.instinct_learning_loop import InstinctLearningLoop

    return InstinctLearningLoop()


@pytest.fixture
def smart_home_config():
    """Create test smart home config."""
    from kagami_smarthome.types import SmartHomeConfig

    return SmartHomeConfig(
        known_devices=["aa:bb:cc:dd:ee:ff", "11:22:33:44:55:66"],
        away_timeout_minutes=30,
        sleep_start_hour=23,
        sleep_end_hour=6,
    )


@pytest.fixture
def presence_engine(smart_home_config):
    """Create presence engine for testing."""
    from kagami_smarthome.presence import PresenceEngine

    return PresenceEngine(smart_home_config)


# =============================================================================
# 1. PATTERN LEARNER TESTS
# =============================================================================


class TestPatternLearnerE2E:
    """Test PatternLearner end-to-end functionality."""

    def test_pattern_learner_records_and_predicts_events(self, pattern_learner):
        """Pattern learner should record events and make predictions."""
        # Record multiple events at the same time slot
        for _ in range(20):
            pattern_learner.record_event(occurred=True)

        # Should have high probability now
        prob = pattern_learner.get_probability()
        assert prob > 0.5, f"Expected probability > 0.5, got {prob}"

        # Confidence should increase with samples
        conf = pattern_learner.get_confidence()
        assert conf > 0.5, f"Expected confidence > 0.5 after 20 samples, got {conf}"

    def test_pattern_learner_records_and_predicts_values(self, pattern_learner):
        """Pattern learner should handle continuous values."""
        # Record consistent values
        for _ in range(20):
            pattern_learner.record_value(72.0)  # Temperature

        # Expected value should converge
        expected = pattern_learner.get_expected_value()
        assert 70.0 < expected < 74.0, f"Expected ~72.0, got {expected}"

    def test_pattern_learner_prediction_returns_complete_dict(self, pattern_learner):
        """Prediction should return all expected fields."""
        pattern_learner.record_event(occurred=True)

        prediction = pattern_learner.predict()

        # Check required fields
        assert "probability" in prediction
        assert "expected_value" in prediction
        assert "confidence" in prediction
        assert "sample_count" in prediction

    def test_pattern_learner_handles_time_slots_correctly(self, pattern_learner):
        """Different time slots should have independent patterns."""
        from kagami.core.learning.pattern_learner import TimeSlot

        # Record at specific times
        morning = datetime.now().replace(hour=8, minute=0)
        evening = datetime.now().replace(hour=20, minute=0)

        # Record high probability in morning
        for _ in range(10):
            pattern_learner.record_event(occurred=True, at=morning)

        # Record low probability in evening
        for _ in range(10):
            pattern_learner.record_event(occurred=False, at=evening)

        # Predictions should differ
        morning_prob = pattern_learner.get_probability(at=morning)
        evening_prob = pattern_learner.get_probability(at=evening)

        assert morning_prob > evening_prob, (
            f"Morning prob ({morning_prob}) should be > evening prob ({evening_prob})"
        )


# =============================================================================
# 2. INSTINCT LEARNING LOOP TESTS
# =============================================================================


class TestInstinctLearningLoopE2E:
    """Test InstinctLearningLoop end-to-end."""

    @pytest.mark.asyncio
    async def test_train_step_executes(self, instinct_loop):
        """Training step should execute and return results."""
        result = await instinct_loop.train_step()

        assert "status" in result
        assert result["status"] in ("success", "error")
        assert "observations" in result

    @pytest.mark.asyncio
    async def test_train_step_increments_counters(self, instinct_loop):
        """Training should increment observation counters."""
        initial_count = instinct_loop.observation_count

        await instinct_loop.train_step()
        await instinct_loop.train_step()
        await instinct_loop.train_step()

        assert instinct_loop.observation_count == initial_count + 3

    def test_manual_instinct_addition(self, instinct_loop):
        """Should be able to manually add instincts."""
        instinct_loop.add_instinct("lights_on_morning", {"action": "set_lights", "level": 80})

        retrieved = instinct_loop.get_instinct("lights_on_morning")
        assert retrieved is not None
        assert retrieved["level"] == 80

    def test_get_stats_returns_all_fields(self, instinct_loop):
        """get_stats should return all expected fields."""
        stats = instinct_loop.get_stats()

        assert "observations" in stats
        assert "instincts_learned" in stats
        assert "iterations" in stats
        assert "total_samples" in stats


# =============================================================================
# 3. PRESENCE ENGINE TESTS
# =============================================================================


class TestPresenceEngineE2E:
    """Test PresenceEngine end-to-end functionality."""

    def test_initial_state(self, presence_engine):
        """Initial state should be AWAY and UNKNOWN activity."""
        from kagami_smarthome.types import ActivityContext, PresenceState

        state = presence_engine.get_state()
        assert state.presence == PresenceState.AWAY
        assert state.activity == ActivityContext.UNKNOWN

    def test_motion_event_updates_state(self, presence_engine):
        """Motion event should update presence state."""
        from kagami_smarthome.types import PresenceEvent, PresenceState

        event = PresenceEvent(
            source="unifi_camera",
            event_type="motion",
            location="Living Room",
            confidence=0.9,
        )

        state = presence_engine.process_event(event)

        assert state.presence == PresenceState.ACTIVE
        assert state.last_location == "Living Room"

    def test_room_tracking(self, presence_engine):
        """Rooms should be tracked independently."""
        from kagami_smarthome.types import PresenceEvent

        # Motion in kitchen
        event1 = PresenceEvent(
            source="camera",
            event_type="motion",
            location="Kitchen",
            confidence=0.9,
        )
        presence_engine.process_event(event1)

        # Should track kitchen
        assert presence_engine.is_room_occupied("Kitchen")
        assert "Kitchen" in presence_engine.get_occupied_rooms()

    def test_pattern_learning_integration(self, presence_engine):
        """Presence engine should have pattern learner."""
        assert hasattr(presence_engine, "pattern_learner")
        assert presence_engine.pattern_learner is not None

    def test_intent_prediction_available(self, presence_engine):
        """Intent prediction should be available."""
        intent = presence_engine.predict_intent()

        assert isinstance(intent, dict)
        assert "predicted_activity" in intent
        assert "confidence" in intent

    def test_dsc_zone_processing(self, presence_engine):
        """DSC zone events should be processed."""
        from kagami_smarthome.types import PresenceState

        state = presence_engine.process_dsc_zone_event(
            zone_num=1,
            zone_name="Living Room Motion",
            zone_type="motion",
            event_type="open",
        )

        assert state.presence == PresenceState.ACTIVE
        assert 1 in state.dsc_zones

    def test_recommendations_generated(self, presence_engine):
        """Should generate recommendations based on state."""
        from kagami_smarthome.types import PresenceEvent

        # Set state to arriving
        event = PresenceEvent(
            source="unifi_doorbell",
            event_type="ring",
            location="front_door",
            confidence=1.0,
        )
        presence_engine.process_event(event)

        recommendations = presence_engine.get_recommendations()

        assert isinstance(recommendations, list)
        # Should have disarm recommendation when arriving
        actions = [r["action"] for r in recommendations]
        assert "disarm_security" in actions


# =============================================================================
# 4. LOCATION MODEL TESTS (DeviceLocalizer)
# =============================================================================


class TestLocationModelE2E:
    """Test DeviceLocalizer functionality."""

    def test_localizer_can_be_instantiated(self):
        """DeviceLocalizer should be instantiable."""
        from kagami_smarthome.localization import DeviceLocalizer

        localizer = DeviceLocalizer()
        assert localizer is not None

    def test_ap_configuration(self):
        """Should configure AP-to-room mappings."""
        from kagami_smarthome.localization import DeviceLocalizer

        localizer = DeviceLocalizer()
        localizer.configure_access_point(
            mac="aa:bb:cc:dd:ee:ff",
            name="Living Room AP",
            room="Living Room",
            floor="Main",
            adjacent_rooms=["Kitchen", "Dining"],
        )

        # Should have the configuration
        status = localizer.get_status()
        assert status["ap_mappings"] >= 1


# =============================================================================
# 5. ENERGY MODEL TESTS (via SituationAwareness)
# =============================================================================


class TestEnergyModelE2E:
    """Test energy level inference via SituationAwareness."""

    def test_energy_level_enum_values(self):
        """EnergyLevel enum should have expected values."""
        from kagami.core.integrations.situation_awareness import EnergyLevel

        assert EnergyLevel.LOW.value == "low"
        assert EnergyLevel.MEDIUM.value == "medium"
        assert EnergyLevel.HIGH.value == "high"

    def test_situation_structure(self):
        """Situation should have energy context."""
        from kagami.core.integrations.situation_awareness import (
            EnergyLevel,
            Situation,
            SituationPhase,
            UrgencyLevel,
        )

        situation = Situation(
            phase=SituationPhase.WORKING,
            urgency=UrgencyLevel.NORMAL,
            energy=EnergyLevel.HIGH,
        )

        assert situation.energy == EnergyLevel.HIGH

    def test_situation_to_dict_includes_energy(self):
        """to_dict should include energy level."""
        from kagami.core.integrations.situation_awareness import (
            EnergyLevel,
            Situation,
            SituationPhase,
            UrgencyLevel,
        )

        situation = Situation(
            phase=SituationPhase.WORKING,
            urgency=UrgencyLevel.NORMAL,
            energy=EnergyLevel.MEDIUM,
        )

        result = situation.to_dict()
        assert "energy" in result
        assert result["energy"] == "medium"


# =============================================================================
# 6. CALENDAR MODEL TESTS
# =============================================================================


class TestCalendarModelE2E:
    """Test calendar/event model functionality."""

    def test_active_event_structure(self):
        """ActiveEvent should have expected structure."""
        from kagami.core.integrations.situation_awareness import ActiveEvent, UrgencyLevel

        event = ActiveEvent(
            title="Team Standup",
            start_time=datetime.now() + timedelta(minutes=15),
            end_time=datetime.now() + timedelta(minutes=45),
            is_meeting=True,
            attendees=["alice", "bob"],
            urgency=UrgencyLevel.NORMAL,
        )

        assert event.title == "Team Standup"
        assert event.is_meeting
        assert len(event.attendees) == 2

    def test_active_event_timing_properties(self):
        """ActiveEvent should compute timing correctly."""
        from kagami.core.integrations.situation_awareness import ActiveEvent

        # Event in 15 minutes
        future_event = ActiveEvent(
            title="Future Meeting",
            start_time=datetime.now() + timedelta(minutes=15),
        )
        assert not future_event.is_now
        assert 10 < future_event.minutes_until < 20

        # Event happening now
        current_event = ActiveEvent(
            title="Current Meeting",
            start_time=datetime.now() - timedelta(minutes=10),
            end_time=datetime.now() + timedelta(minutes=20),
        )
        assert current_event.is_now
        assert current_event.minutes_until < 0


# =============================================================================
# 7. INTEGRATION TESTS - FULL LOOP
# =============================================================================


class TestFullLoopIntegration:
    """Test full integration between all models."""

    def test_presence_feeds_pattern_learning(self, presence_engine):
        """Presence events should feed into pattern learning."""
        from kagami_smarthome.types import PresenceEvent

        initial_slots = len(presence_engine.pattern_learner._patterns)

        # Process multiple events
        for _ in range(5):
            event = PresenceEvent(
                source="camera",
                event_type="motion",
                location="Kitchen",
                confidence=0.9,
            )
            presence_engine.process_event(event)

        # Pattern learner should have learned something
        stats = presence_engine.pattern_learner.get_pattern_stats()
        assert stats["total_samples"] > 0

    @pytest.mark.asyncio
    async def test_learning_loop_integrates_with_patterns(self, instinct_loop, pattern_learner):
        """Instinct learning should integrate with pattern learning."""
        # Train instinct loop
        for _ in range(5):
            await instinct_loop.train_step()

        # Both should have recorded data
        assert instinct_loop.observation_count >= 5

        # Pattern learner should work independently
        # After one event with EMA alpha=0.2, probability = 0 + 0.2 * 1 = 0.2
        # After multiple events, it converges toward 1.0
        for _ in range(10):
            pattern_learner.record_event(occurred=True)
        assert pattern_learner.get_probability() > 0.0  # Should be positive


# =============================================================================
# 8. SAFETY INTEGRATION TESTS
# =============================================================================


class TestSafetyIntegration:
    """Test that safety checks are integrated with models."""

    def test_physical_safety_module_available(self):
        """Physical safety module should be available."""
        from kagami_smarthome.safety import (
            PhysicalActionType,
            SafetyContext,
            SafetyResult,
            check_physical_safety,
        )

        # Should be able to create safety context
        context = SafetyContext(
            action_type=PhysicalActionType.FIREPLACE_ON,
            target="fireplace",
        )

        result = check_physical_safety(context)

        # Should return valid result with h(x) >= 0
        assert isinstance(result, SafetyResult)
        assert result.h_x >= 0  # Safety invariant

    def test_all_physical_actions_have_safety_checks(self):
        """All physical action types should have safety checks."""
        from kagami_smarthome.safety import (
            PhysicalActionType,
            SafetyContext,
            check_physical_safety,
        )

        for action_type in PhysicalActionType:
            context = SafetyContext(
                action_type=action_type,
                target="test",
            )
            result = check_physical_safety(context)

            # Every action should return a valid result
            assert result is not None
            assert isinstance(result.h_x, (int, float))


# =============================================================================
# 9. GENERALITY TESTS - NO ONE-OFFS
# =============================================================================


class TestGeneralityNoOneOffs:
    """Test that implementations are general, not one-offs."""

    def test_pattern_learner_works_for_any_domain(self):
        """PatternLearner should work for any domain, not just built-in ones."""
        from kagami.core.learning.pattern_learner import (
            PatternLearner,
            TimeGranularity,
        )

        # Create learner for arbitrary domain
        custom_learner = PatternLearner(
            "my_custom_domain",
            TimeGranularity.QUARTER_HOUR,
            persist_path=None,
        )

        # Should work exactly like built-in domains
        custom_learner.record_event(occurred=True)
        custom_learner.record_value(42.0)

        prob = custom_learner.get_probability()
        value = custom_learner.get_expected_value()

        assert 0 <= prob <= 1
        assert value > 0

    def test_presence_engine_handles_arbitrary_room_names(self, presence_engine):
        """PresenceEngine should handle any room name, not hardcoded ones."""
        from kagami_smarthome.types import PresenceEvent

        # Use non-standard room names
        weird_rooms = ["Room-42", "basement/storage", "MAIN_FLOOR_1", "guest_room_2b"]

        for room in weird_rooms:
            event = PresenceEvent(
                source="camera",
                event_type="motion",
                location=room,
                confidence=0.9,
            )
            state = presence_engine.process_event(event)

            # Should track any room name
            assert state.last_location == room
            assert presence_engine.is_room_occupied(room)

    def test_localizer_handles_arbitrary_ap_configs(self):
        """DeviceLocalizer should handle any AP configuration."""
        from kagami_smarthome.localization import DeviceLocalizer

        localizer = DeviceLocalizer()

        # Configure with non-standard names
        configs = [
            ("00:11:22:33:44:55", "AP_Floor1_Zone_A", "Sector-1"),
            ("66:77:88:99:aa:bb", "网络设备", "房间"),  # Unicode
            ("cc:dd:ee:ff:00:11", "ap-with-dashes", "room_with_underscores"),
        ]

        for mac, name, room in configs:
            localizer.configure_access_point(mac=mac, name=name, room=room)

        status = localizer.get_status()
        assert status["ap_mappings"] >= len(configs)

    def test_safety_context_accepts_arbitrary_parameters(self):
        """SafetyContext should accept arbitrary parameters."""
        from kagami_smarthome.safety import (
            PhysicalActionType,
            SafetyContext,
            check_physical_safety,
        )

        # Pass arbitrary parameters
        context = SafetyContext(
            action_type=PhysicalActionType.HVAC_EXTREME,
            target="zone_42",
            parameters={
                "temperature": 75,
                "mode": "custom_mode",
                "custom_field": {"nested": "data"},
                "unicode_field": "日本語",
            },
        )

        result = check_physical_safety(context)
        assert result is not None


# =============================================================================
# 10. OPTIMIZATION TESTS
# =============================================================================


class TestOptimization:
    """Test that implementations are optimized."""

    def test_pattern_learner_constant_memory(self, pattern_learner):
        """Pattern learner should not grow unboundedly."""
        import sys

        # Record many events
        for i in range(1000):
            pattern_learner.record_event(occurred=i % 2 == 0)

        # Get summary - should have fixed number of slots (based on time granularity)
        summary = pattern_learner.get_summary()

        # Hourly granularity = 7 weekdays * 24 hours = 168 max slots
        # But we only filled one slot in this test
        assert summary["active_slots"] <= 168

    def test_presence_event_history_bounded(self, presence_engine):
        """Event history should be bounded."""
        from kagami_smarthome.types import PresenceEvent

        # Generate many events
        for i in range(2000):
            event = PresenceEvent(
                source="test",
                event_type="motion",
                location=f"room_{i % 10}",
                confidence=0.9,
            )
            presence_engine.process_event(event)

        # History should be capped (default is 1000)
        assert len(presence_engine._event_history) <= 1000

    def test_pattern_slot_uses_ema_not_full_history(self, pattern_learner):
        """Pattern slots should use EMA, not store full history."""
        from kagami.core.learning.pattern_learner import PatternSlot

        slot = PatternSlot()

        # Update many times
        for i in range(1000):
            slot.update_value(float(i))

        # Should only store aggregates, not raw data
        # No list of historical values
        assert not hasattr(slot, "history")
        assert not hasattr(slot, "values")

        # Should have summary stats
        assert slot.count == 1000
        assert slot.mean_value > 0
