"""Unit tests for OrbState model.

Colony: Crystal (e₇) — Verification

Tests:
    - OrbState creation and defaults
    - Color computation based on colony
    - Safety color thresholds
    - State serialization/deserialization
"""

import time
from kagami.core.orb import (
    OrbState,
    OrbActivity,
    OrbPosition,
    create_orb_state,
    get_orb_state,
)
from kagami.core.orb.state import ConnectionState


class TestOrbState:
    """Tests for OrbState dataclass."""

    def test_default_state(self) -> None:
        """Test default OrbState values."""
        state = OrbState()
        assert state.active_colony is None
        assert state.activity == OrbActivity.IDLE
        assert state.safety_score == 1.0
        assert state.connection == ConnectionState.CONNECTED
        assert state.active_colonies == []
        assert state.home_status == {}

    def test_state_with_colony(self) -> None:
        """Test OrbState with active colony."""
        state = OrbState(active_colony="forge")
        assert state.active_colony == "forge"
        assert state.color.hex == "#FFB347"
        assert state.color.description == "Forge Amber"

    def test_color_for_each_colony(self) -> None:
        """Test that each colony has correct color."""
        expected_colors = {
            "spark": "#FF6B35",
            "forge": "#FFB347",
            "flow": "#4ECDC4",
            "nexus": "#9B59B6",
            "beacon": "#D4AF37",
            "grove": "#27AE60",
            "crystal": "#E0E0E0",
        }

        for colony, expected_hex in expected_colors.items():
            state = OrbState(active_colony=colony)
            assert state.color.hex == expected_hex, f"Color mismatch for {colony}"

    def test_default_color_when_idle(self) -> None:
        """Test that idle state uses default blue color."""
        state = OrbState(active_colony=None)
        assert state.color.hex == "#4A90D9"  # Idle Blue

    def test_is_safe_property(self) -> None:
        """Test is_safe property threshold."""
        safe_state = OrbState(safety_score=0.7)
        assert safe_state.is_safe is True

        caution_state = OrbState(safety_score=0.4)
        assert caution_state.is_safe is False

        unsafe_state = OrbState(safety_score=0.2)
        assert unsafe_state.is_safe is False

    def test_is_connected_property(self) -> None:
        """Test is_connected property."""
        connected = OrbState(connection=ConnectionState.CONNECTED)
        assert connected.is_connected is True

        disconnected = OrbState(connection=ConnectionState.DISCONNECTED)
        assert disconnected.is_connected is False

    def test_to_dict_serialization(self) -> None:
        """Test OrbState serialization to dict."""
        state = OrbState(active_colony="forge", safety_score=0.85)
        data = state.to_dict()

        assert data["active_colony"] == "forge"
        assert data["safety_score"] == 0.85
        assert data["activity"] == "idle"
        assert "color" in data
        assert data["color"]["hex"] == "#FFB347"

    def test_from_dict_deserialization(self) -> None:
        """Test OrbState deserialization from dict."""
        data = {
            "active_colony": "flow",
            "activity": "processing",
            "safety_score": 0.9,
            "connection": "connected",
            "timestamp": time.time(),
        }
        state = OrbState.from_dict(data)

        assert state.active_colony == "flow"
        assert state.activity == OrbActivity.PROCESSING
        assert state.safety_score == 0.9


class TestOrbPosition:
    """Tests for OrbPosition dataclass."""

    def test_default_position(self) -> None:
        """Test default position at origin."""
        pos = OrbPosition()
        assert pos.x == 0.0
        assert pos.y == 0.0
        assert pos.z == 0.0
        assert pos.scale == 1.0

    def test_as_tuple(self) -> None:
        """Test as_tuple method."""
        pos = OrbPosition(x=0.3, y=1.2, z=-0.8)
        assert pos.as_tuple() == (0.3, 1.2, -0.8)

    def test_distance_from_origin(self) -> None:
        """Test distance calculation."""
        pos = OrbPosition(x=3.0, y=4.0, z=0.0)
        assert pos.distance_from_origin() == 5.0  # 3-4-5 triangle


class TestFactoryFunctions:
    """Tests for orb factory functions."""

    def test_create_orb_state(self) -> None:
        """Test create_orb_state factory."""
        state = create_orb_state(active_colony="beacon", safety_score=0.75)

        assert state.active_colony == "beacon"
        assert state.safety_score == 0.75
        assert state.color.hex == "#D4AF37"

    def test_get_orb_state_singleton(self) -> None:
        """Test that get_orb_state returns consistent state."""
        # Reset global state
        create_orb_state(active_colony="spark")

        state1 = get_orb_state()
        state2 = get_orb_state()

        # Should return same state (singleton)
        assert state1.active_colony == state2.active_colony
