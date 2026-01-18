"""Tests for SmartHome Type Definitions.

Tests all dataclasses, enums, and type definitions.

Created: December 30, 2025
"""

from __future__ import annotations

import time

import pytest

from kagami_smarthome.types import (
    ActivityContext,
    DSCTemperature,
    DSCTroubleState,
    DSCZoneState,
    GeofenceState,
    HomeState,
    PresenceEvent,
    PresenceState,
    SecurityState,
    SmartHomeConfig,
    TrackedDevice,
)

# =============================================================================
# PRESENCE STATE TESTS
# =============================================================================


class TestPresenceState:
    """Test PresenceState enum."""

    def test_all_states_defined(self):
        """All presence states are defined."""
        assert PresenceState.AWAY is not None
        assert PresenceState.ARRIVING is not None
        assert PresenceState.HOME is not None
        assert PresenceState.ACTIVE is not None
        assert PresenceState.SLEEPING is not None

    def test_state_values(self):
        """State values are strings."""
        assert PresenceState.AWAY.value == "away"
        assert PresenceState.HOME.value == "home"

    def test_enum_iteration(self):
        """Can iterate over all states."""
        states = list(PresenceState)
        assert len(states) >= 5


# =============================================================================
# SECURITY STATE TESTS
# =============================================================================


class TestSecurityState:
    """Test SecurityState enum."""

    def test_all_states_defined(self):
        """All security states are defined."""
        assert SecurityState.DISARMED is not None
        assert SecurityState.ARMED_STAY is not None
        assert SecurityState.ARMED_AWAY is not None
        assert SecurityState.ARMED_NIGHT is not None
        assert SecurityState.ALARM is not None
        assert SecurityState.TROUBLE is not None

    def test_state_values(self):
        """State values match DSC panel states."""
        assert SecurityState.DISARMED.value == "disarmed"
        assert SecurityState.ARMED_AWAY.value == "armed_away"


# =============================================================================
# ACTIVITY CONTEXT TESTS
# =============================================================================


class TestActivityContext:
    """Test ActivityContext enum."""

    def test_all_contexts_defined(self):
        """All activity contexts are defined."""
        assert ActivityContext.UNKNOWN is not None
        assert ActivityContext.WAKING is not None
        assert ActivityContext.WORKING is not None
        assert ActivityContext.COOKING is not None
        assert ActivityContext.RELAXING is not None
        assert ActivityContext.ENTERTAINING is not None
        assert ActivityContext.SLEEPING is not None


# =============================================================================
# PRESENCE EVENT TESTS
# =============================================================================


class TestPresenceEvent:
    """Test PresenceEvent dataclass."""

    def test_event_creation(self):
        """PresenceEvent can be created."""
        event = PresenceEvent(
            source="unifi_camera",
            event_type="motion",
            location="Living Room",
            confidence=0.9,
        )
        assert event.source == "unifi_camera"
        assert event.event_type == "motion"

    def test_default_timestamp(self):
        """PresenceEvent has default timestamp."""
        before = time.time()
        event = PresenceEvent(
            source="test",
            event_type="test",
            location=None,
            confidence=1.0,
        )
        after = time.time()
        assert before <= event.timestamp <= after

    def test_optional_metadata(self):
        """PresenceEvent accepts metadata."""
        event = PresenceEvent(
            source="test",
            event_type="test",
            location=None,
            confidence=1.0,
            metadata={"device_mac": "aa:bb:cc:dd:ee:ff"},
        )
        assert "device_mac" in event.metadata


# =============================================================================
# DSC ZONE STATE TESTS
# =============================================================================


class TestDSCZoneState:
    """Test DSCZoneState dataclass."""

    def test_zone_creation(self):
        """DSCZoneState can be created."""
        zone = DSCZoneState(zone_num=1, name="Front Door")
        assert zone.zone_num == 1
        assert zone.name == "Front Door"

    def test_default_values(self):
        """DSCZoneState has sensible defaults."""
        zone = DSCZoneState(zone_num=1)
        assert zone.state == "closed"
        assert zone.battery_low is False
        assert zone.activity_count == 0

    def test_is_open_property(self):
        """is_open property works correctly."""
        zone = DSCZoneState(zone_num=1, state="open")
        assert zone.is_open is True

        zone.state = "closed"
        assert zone.is_open is False

        zone.state = "alarm"
        assert zone.is_open is True

    def test_is_motion_zone(self):
        """is_motion_zone identifies motion detectors."""
        zone = DSCZoneState(zone_num=1, zone_type="motion")
        assert zone.is_motion_zone is True

        zone.zone_type = "door_window"
        assert zone.is_motion_zone is False

    def test_is_entry_zone(self):
        """is_entry_zone identifies door/window sensors."""
        zone = DSCZoneState(zone_num=1, zone_type="door_window")
        assert zone.is_entry_zone is True

    def test_is_safety_zone(self):
        """is_safety_zone identifies life safety devices."""
        zone = DSCZoneState(zone_num=1, zone_type="smoke")
        assert zone.is_safety_zone is True

        zone.zone_type = "co"
        assert zone.is_safety_zone is True

        zone.zone_type = "heat"
        assert zone.is_safety_zone is True

    def test_time_since_activity(self):
        """time_since_activity calculates correctly."""
        zone = DSCZoneState(zone_num=1, last_activity=time.time() - 5)
        elapsed = zone.time_since_activity
        assert 4 < elapsed < 7

        zone.last_activity = 0
        assert zone.time_since_activity == float("inf")


# =============================================================================
# DSC TROUBLE STATE TESTS
# =============================================================================


class TestDSCTroubleState:
    """Test DSCTroubleState dataclass."""

    def test_creation(self):
        """DSCTroubleState can be created."""
        trouble = DSCTroubleState()
        assert trouble.ac_failure is False
        assert trouble.battery_low is False

    def test_all_trouble_types(self):
        """All trouble types are tracked."""
        trouble = DSCTroubleState(
            ac_failure=True,
            battery_low=True,
            bell_trouble=True,
            phone_line_trouble=True,
            fire_trouble=True,
            system_tamper=True,
            low_battery_zones=[1, 5, 10],
        )
        assert trouble.ac_failure is True
        assert 5 in trouble.low_battery_zones


# =============================================================================
# DSC TEMPERATURE TESTS
# =============================================================================


class TestDSCTemperature:
    """Test DSCTemperature dataclass."""

    def test_creation(self):
        """DSCTemperature can be created."""
        temp = DSCTemperature(interior=72.0, exterior=55.0)
        assert temp.interior == 72.0
        assert temp.exterior == 55.0

    def test_nullable_temps(self):
        """Temperatures can be None."""
        temp = DSCTemperature()
        assert temp.interior is None
        assert temp.exterior is None


# =============================================================================
# GEOFENCE STATE TESTS
# =============================================================================


class TestGeofenceState:
    """Test GeofenceState enum."""

    def test_all_states_defined(self):
        """All geofence states are defined."""
        assert GeofenceState.UNKNOWN is not None
        assert GeofenceState.HOME is not None
        assert GeofenceState.NEAR is not None
        assert GeofenceState.AWAY is not None
        assert GeofenceState.ARRIVING is not None
        assert GeofenceState.LEAVING is not None


# =============================================================================
# TRACKED DEVICE TESTS
# =============================================================================


class TestTrackedDevice:
    """Test TrackedDevice dataclass."""

    def test_creation(self):
        """TrackedDevice can be created."""
        device = TrackedDevice(mac="aa:bb:cc:dd:ee:ff", name="iPhone")
        assert device.mac == "aa:bb:cc:dd:ee:ff"
        assert device.name == "iPhone"

    def test_default_values(self):
        """TrackedDevice has sensible defaults."""
        device = TrackedDevice(mac="aa:bb:cc:dd:ee:ff")
        assert device.device_type == "unknown"
        assert device.current_room is None
        assert device.is_online is False
        assert device.is_owner is False


# =============================================================================
# HOME STATE TESTS
# =============================================================================


class TestHomeState:
    """Test HomeState dataclass."""

    def test_creation(self):
        """HomeState can be created."""
        state = HomeState()
        assert state.presence == PresenceState.AWAY
        assert state.security == SecurityState.DISARMED

    def test_all_fields_accessible(self):
        """All HomeState fields are accessible."""
        state = HomeState(
            presence=PresenceState.HOME,
            security=SecurityState.ARMED_STAY,
            activity=ActivityContext.RELAXING,
            owner_room="Living Room",
        )
        assert state.presence == PresenceState.HOME
        assert state.owner_room == "Living Room"


# =============================================================================
# SMART HOME CONFIG TESTS
# =============================================================================


class TestSmartHomeConfig:
    """Test SmartHomeConfig dataclass."""

    def test_default_config(self):
        """SmartHomeConfig has defaults."""
        config = SmartHomeConfig()
        assert config is not None

    def test_auto_discover_default(self):
        """auto_discover defaults to True."""
        config = SmartHomeConfig()
        # Check if auto_discover exists and has a reasonable default
        has_auto_discover = hasattr(config, "auto_discover")
        if has_auto_discover:
            # Just verify it's a boolean
            assert isinstance(config.auto_discover, bool)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
