"""Comprehensive unit tests for the Orb State module.

Tests cover:
- state.py: OrbState, OrbActivity, ConnectionState, OrbPosition
- events.py: OrbInteractionEvent, OrbStateChangedEvent, InteractionAction, ClientType
- colors.py: ColonyColor, get_colony_color, get_safety_color
- constants.py: SpatialZone, LED mappings, position presets

Colony: Crystal (e7) — Verification and quality
"""

from __future__ import annotations

import math
import time
import uuid
from dataclasses import FrozenInstanceError

import pytest

pytestmark = pytest.mark.tier_unit


# =============================================================================
# state.py Tests
# =============================================================================


class TestOrbActivity:
    """Tests for OrbActivity enum."""

    @pytest.mark.unit
    def test_all_activity_values_exist(self) -> None:
        """Verify all expected activity values are defined."""
        from kagami.core.orb.state import OrbActivity

        expected_activities = [
            "idle",
            "listening",
            "processing",
            "responding",
            "error",
            "safety_alert",
            "portable",
        ]
        for activity_value in expected_activities:
            activity = OrbActivity(activity_value)
            assert activity.value == activity_value

    @pytest.mark.unit
    def test_activity_is_string_enum(self) -> None:
        """Verify OrbActivity is a string enum."""
        from kagami.core.orb.state import OrbActivity

        assert isinstance(OrbActivity.IDLE, str)
        assert OrbActivity.IDLE == "idle"

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "activity,expected_value",
        [
            ("IDLE", "idle"),
            ("LISTENING", "listening"),
            ("PROCESSING", "processing"),
            ("RESPONDING", "responding"),
            ("ERROR", "error"),
            ("SAFETY_ALERT", "safety_alert"),
            ("PORTABLE", "portable"),
        ],
    )
    def test_activity_enum_values(self, activity: str, expected_value: str) -> None:
        """Test each activity enum has correct value."""
        from kagami.core.orb.state import OrbActivity

        enum_member = getattr(OrbActivity, activity)
        assert enum_member.value == expected_value


class TestConnectionState:
    """Tests for ConnectionState enum."""

    @pytest.mark.unit
    def test_all_connection_states_exist(self) -> None:
        """Verify all expected connection states are defined."""
        from kagami.core.orb.state import ConnectionState

        expected_states = ["connected", "connecting", "disconnected", "error"]
        for state_value in expected_states:
            state = ConnectionState(state_value)
            assert state.value == state_value

    @pytest.mark.unit
    def test_connection_state_is_string_enum(self) -> None:
        """Verify ConnectionState is a string enum."""
        from kagami.core.orb.state import ConnectionState

        assert isinstance(ConnectionState.CONNECTED, str)
        assert ConnectionState.CONNECTED == "connected"


class TestOrbPosition:
    """Tests for OrbPosition dataclass."""

    @pytest.mark.unit
    def test_default_position_at_origin(self) -> None:
        """Default position should be at origin."""
        from kagami.core.orb.state import OrbPosition

        pos = OrbPosition()
        assert pos.x == 0.0
        assert pos.y == 0.0
        assert pos.z == 0.0
        assert pos.scale == 1.0

    @pytest.mark.unit
    def test_position_creation_with_values(self) -> None:
        """Position should accept custom coordinates."""
        from kagami.core.orb.state import OrbPosition

        pos = OrbPosition(x=1.5, y=2.0, z=-3.0, scale=0.5)
        assert pos.x == 1.5
        assert pos.y == 2.0
        assert pos.z == -3.0
        assert pos.scale == 0.5

    @pytest.mark.unit
    def test_position_is_immutable(self) -> None:
        """Position dataclass should be frozen (immutable)."""
        from kagami.core.orb.state import OrbPosition

        pos = OrbPosition(x=1.0, y=2.0, z=3.0)
        with pytest.raises(FrozenInstanceError):
            pos.x = 5.0  # type: ignore[misc]

    @pytest.mark.unit
    def test_as_tuple_returns_xyz(self) -> None:
        """as_tuple should return (x, y, z) tuple without scale."""
        from kagami.core.orb.state import OrbPosition

        pos = OrbPosition(x=1.0, y=2.0, z=3.0, scale=2.0)
        result = pos.as_tuple()
        assert result == (1.0, 2.0, 3.0)
        assert len(result) == 3

    @pytest.mark.unit
    def test_distance_from_origin_at_origin(self) -> None:
        """Distance from origin should be 0 at origin."""
        from kagami.core.orb.state import OrbPosition

        pos = OrbPosition()
        assert pos.distance_from_origin() == 0.0

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "x,y,z,expected_distance",
        [
            (3.0, 0.0, 0.0, 3.0),
            (0.0, 4.0, 0.0, 4.0),
            (0.0, 0.0, 5.0, 5.0),
            (3.0, 4.0, 0.0, 5.0),  # Pythagorean 3-4-5
            (1.0, 2.0, 2.0, 3.0),  # sqrt(1 + 4 + 4) = 3
        ],
    )
    def test_distance_from_origin_calculation(
        self, x: float, y: float, z: float, expected_distance: float
    ) -> None:
        """Test distance calculation for various positions."""
        from kagami.core.orb.state import OrbPosition

        pos = OrbPosition(x=x, y=y, z=z)
        assert math.isclose(pos.distance_from_origin(), expected_distance, rel_tol=1e-9)


class TestOrbState:
    """Tests for OrbState dataclass."""

    @pytest.mark.unit
    def test_default_state_creation(self) -> None:
        """Default OrbState should have sensible defaults."""
        from kagami.core.orb.state import ConnectionState, OrbActivity, OrbState

        state = OrbState()
        assert state.active_colony is None
        assert state.activity == OrbActivity.IDLE
        assert state.safety_score == 1.0
        assert state.connection == ConnectionState.CONNECTED
        assert state.active_colonies == []
        assert state.home_status == {}
        assert state.timestamp > 0

    @pytest.mark.unit
    def test_state_creation_with_values(self) -> None:
        """OrbState should accept custom values."""
        from kagami.core.orb.state import ConnectionState, OrbActivity, OrbPosition, OrbState

        pos = OrbPosition(x=1.0, y=2.0, z=3.0)
        state = OrbState(
            active_colony="forge",
            activity=OrbActivity.PROCESSING,
            safety_score=0.85,
            connection=ConnectionState.CONNECTING,
            position=pos,
            active_colonies=["forge", "spark"],
            home_status={"lights": "on"},
            timestamp=12345.0,
        )
        assert state.active_colony == "forge"
        assert state.activity == OrbActivity.PROCESSING
        assert state.safety_score == 0.85
        assert state.connection == ConnectionState.CONNECTING
        assert state.position == pos
        assert state.active_colonies == ["forge", "spark"]
        assert state.home_status == {"lights": "on"}
        assert state.timestamp == 12345.0

    @pytest.mark.unit
    def test_state_is_immutable(self) -> None:
        """OrbState dataclass should be frozen (immutable)."""
        from kagami.core.orb.state import OrbState

        state = OrbState(active_colony="spark")
        with pytest.raises(FrozenInstanceError):
            state.active_colony = "forge"  # type: ignore[misc]

    @pytest.mark.unit
    def test_is_safe_property_true_when_above_threshold(self) -> None:
        """is_safe should return True when safety_score >= 0.5."""
        from kagami.core.orb.state import OrbState

        state_high = OrbState(safety_score=0.9)
        state_mid = OrbState(safety_score=0.5)
        assert state_high.is_safe is True
        assert state_mid.is_safe is True

    @pytest.mark.unit
    def test_is_safe_property_false_when_below_threshold(self) -> None:
        """is_safe should return False when safety_score < 0.5."""
        from kagami.core.orb.state import OrbState

        state = OrbState(safety_score=0.49)
        assert state.is_safe is False

    @pytest.mark.unit
    def test_is_connected_property_true_when_connected(self) -> None:
        """is_connected should return True when connection is CONNECTED."""
        from kagami.core.orb.state import ConnectionState, OrbState

        state = OrbState(connection=ConnectionState.CONNECTED)
        assert state.is_connected is True

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "connection_state",
        ["CONNECTING", "DISCONNECTED", "ERROR"],
    )
    def test_is_connected_property_false_when_not_connected(self, connection_state: str) -> None:
        """is_connected should return False when not CONNECTED."""
        from kagami.core.orb.state import ConnectionState, OrbState

        state = OrbState(connection=getattr(ConnectionState, connection_state))
        assert state.is_connected is False

    @pytest.mark.unit
    def test_color_property_returns_colony_color(self) -> None:
        """color property should return colony color when colony is active."""
        from kagami.core.orb.colors import get_colony_color
        from kagami.core.orb.state import OrbState

        state = OrbState(active_colony="forge")
        expected = get_colony_color("forge")
        assert state.color.hex == expected.hex

    @pytest.mark.unit
    def test_color_property_returns_default_when_no_colony(self) -> None:
        """color property should return default idle color when no colony."""
        from kagami.core.orb.colors import DEFAULT_COLOR
        from kagami.core.orb.state import OrbState

        state = OrbState(active_colony=None)
        assert state.color.hex == DEFAULT_COLOR.hex

    @pytest.mark.unit
    def test_color_property_returns_error_on_connection_error(self) -> None:
        """color property should return error color on connection error."""
        from kagami.core.orb.colors import ERROR_COLOR
        from kagami.core.orb.state import ConnectionState, OrbState

        state = OrbState(active_colony="forge", connection=ConnectionState.ERROR)
        assert state.color.hex == ERROR_COLOR.hex

    @pytest.mark.unit
    def test_color_property_returns_error_on_activity_error(self) -> None:
        """color property should return error color on activity error."""
        from kagami.core.orb.colors import ERROR_COLOR
        from kagami.core.orb.state import OrbActivity, OrbState

        state = OrbState(active_colony="forge", activity=OrbActivity.ERROR)
        assert state.color.hex == ERROR_COLOR.hex

    @pytest.mark.unit
    def test_color_property_returns_safety_color_on_safety_alert(self) -> None:
        """color property should return safety color on safety alert."""
        from kagami.core.orb.colors import get_safety_color
        from kagami.core.orb.state import OrbActivity, OrbState

        state = OrbState(active_colony="forge", activity=OrbActivity.SAFETY_ALERT, safety_score=0.5)
        expected = get_safety_color(0.5)
        assert state.color.hex == expected.hex


class TestOrbStateSerialization:
    """Tests for OrbState serialization methods."""

    @pytest.mark.unit
    def test_to_dict_contains_all_fields(self) -> None:
        """to_dict should contain all state fields."""
        from kagami.core.orb.state import OrbState

        state = OrbState(active_colony="spark")
        data = state.to_dict()

        assert "active_colony" in data
        assert "activity" in data
        assert "safety_score" in data
        assert "connection" in data
        assert "position" in data
        assert "active_colonies" in data
        assert "home_status" in data
        assert "timestamp" in data
        assert "color" in data

    @pytest.mark.unit
    def test_to_dict_serializes_enums_to_values(self) -> None:
        """to_dict should serialize enums to their string values."""
        from kagami.core.orb.state import OrbActivity, OrbState

        state = OrbState(activity=OrbActivity.PROCESSING)
        data = state.to_dict()

        assert data["activity"] == "processing"
        assert data["connection"] == "connected"

    @pytest.mark.unit
    def test_to_dict_serializes_position(self) -> None:
        """to_dict should serialize position correctly."""
        from kagami.core.orb.state import OrbPosition, OrbState

        pos = OrbPosition(x=1.0, y=2.0, z=3.0, scale=0.5)
        state = OrbState(position=pos)
        data = state.to_dict()

        assert data["position"]["x"] == 1.0
        assert data["position"]["y"] == 2.0
        assert data["position"]["z"] == 3.0
        assert data["position"]["scale"] == 0.5

    @pytest.mark.unit
    def test_to_dict_includes_color_info(self) -> None:
        """to_dict should include color information."""
        from kagami.core.orb.state import OrbState

        state = OrbState(active_colony="spark")
        data = state.to_dict()

        assert "color" in data
        assert "hex" in data["color"]
        assert "rgb" in data["color"]
        assert "name" in data["color"]

    @pytest.mark.unit
    def test_from_dict_creates_valid_state(self) -> None:
        """from_dict should create valid OrbState from dict."""
        from kagami.core.orb.state import OrbActivity, OrbState

        data = {
            "active_colony": "forge",
            "activity": "processing",
            "safety_score": 0.8,
            "connection": "connected",
            "position": {"x": 1.0, "y": 2.0, "z": 3.0, "scale": 1.0},
            "active_colonies": ["forge"],
            "home_status": {"test": True},
            "timestamp": 12345.0,
        }
        state = OrbState.from_dict(data)

        assert state.active_colony == "forge"
        assert state.activity == OrbActivity.PROCESSING
        assert state.safety_score == 0.8
        assert state.position.x == 1.0
        assert state.timestamp == 12345.0

    @pytest.mark.unit
    def test_from_dict_handles_missing_fields(self) -> None:
        """from_dict should use defaults for missing fields."""
        from kagami.core.orb.state import OrbState

        data: dict = {}
        state = OrbState.from_dict(data)

        assert state.active_colony is None
        assert state.safety_score == 1.0

    @pytest.mark.unit
    def test_roundtrip_serialization(self) -> None:
        """State should survive roundtrip through serialization."""
        from kagami.core.orb.state import OrbActivity, OrbPosition, OrbState

        original = OrbState(
            active_colony="flow",
            activity=OrbActivity.LISTENING,
            safety_score=0.75,
            position=OrbPosition(x=1.0, y=2.0, z=3.0),
            active_colonies=["flow", "nexus"],
        )
        data = original.to_dict()
        restored = OrbState.from_dict(data)

        assert restored.active_colony == original.active_colony
        assert restored.activity == original.activity
        assert restored.safety_score == original.safety_score
        assert restored.position.x == original.position.x


class TestOrbStateFactoryFunctions:
    """Tests for orb state factory functions."""

    @pytest.mark.unit
    def test_create_orb_state_basic(self) -> None:
        """create_orb_state should create state with defaults."""
        from kagami.core.orb.state import create_orb_state

        state = create_orb_state()
        assert state.active_colony is None
        assert state.safety_score == 1.0

    @pytest.mark.unit
    def test_create_orb_state_with_colony(self) -> None:
        """create_orb_state should accept colony parameter."""
        from kagami.core.orb.state import create_orb_state

        state = create_orb_state(active_colony="beacon")
        assert state.active_colony == "beacon"

    @pytest.mark.unit
    def test_create_orb_state_updates_global(self) -> None:
        """create_orb_state should update global state."""
        from kagami.core.orb.state import create_orb_state, get_orb_state

        create_orb_state(active_colony="crystal")
        global_state = get_orb_state()
        assert global_state.active_colony == "crystal"

    @pytest.mark.unit
    def test_get_orb_state_returns_singleton(self) -> None:
        """get_orb_state should return same state on multiple calls."""
        from kagami.core.orb.state import get_orb_state

        state1 = get_orb_state()
        state2 = get_orb_state()
        assert state1 is state2

    @pytest.mark.unit
    def test_update_orb_state_updates_fields(self) -> None:
        """update_orb_state should update specific fields."""
        from kagami.core.orb.state import create_orb_state, update_orb_state

        create_orb_state(active_colony="spark", safety_score=1.0)
        updated = update_orb_state(active_colony="forge")

        assert updated.active_colony == "forge"
        # Other fields should be preserved (though timestamp changes)

    @pytest.mark.unit
    def test_update_orb_state_handles_position_dict(self) -> None:
        """update_orb_state should handle position as dict."""
        from kagami.core.orb.state import create_orb_state, update_orb_state

        create_orb_state()
        updated = update_orb_state(position={"x": 5.0, "y": 6.0, "z": 7.0, "scale": 2.0})

        assert updated.position.x == 5.0
        assert updated.position.y == 6.0


# =============================================================================
# events.py Tests
# =============================================================================


class TestInteractionAction:
    """Tests for InteractionAction enum."""

    @pytest.mark.unit
    def test_all_actions_exist(self) -> None:
        """Verify all expected interaction actions are defined."""
        from kagami.core.orb.events import InteractionAction

        expected_actions = [
            "tap",
            "long_press",
            "gaze_dwell",
            "voice_wake",
            "gesture",
            "double_tap",
        ]
        for action_value in expected_actions:
            action = InteractionAction(action_value)
            assert action.value == action_value

    @pytest.mark.unit
    def test_action_is_string_enum(self) -> None:
        """Verify InteractionAction is a string enum."""
        from kagami.core.orb.events import InteractionAction

        assert isinstance(InteractionAction.TAP, str)
        assert InteractionAction.TAP == "tap"


class TestClientType:
    """Tests for ClientType enum."""

    @pytest.mark.unit
    def test_all_client_types_exist(self) -> None:
        """Verify all expected client types are defined."""
        from kagami.core.orb.events import ClientType

        expected_clients = [
            "vision_pro",
            "hub",
            "desktop",
            "watch",
            "ios",
            "android",
            "hardware_orb",
            "web",
        ]
        for client_value in expected_clients:
            client = ClientType(client_value)
            assert client.value == client_value

    @pytest.mark.unit
    def test_client_type_is_string_enum(self) -> None:
        """Verify ClientType is a string enum."""
        from kagami.core.orb.events import ClientType

        assert isinstance(ClientType.VISION_PRO, str)
        assert ClientType.VISION_PRO == "vision_pro"


class TestOrbInteractionEvent:
    """Tests for OrbInteractionEvent dataclass."""

    @pytest.mark.unit
    def test_default_event_creation(self) -> None:
        """Default event should have sensible defaults."""
        from kagami.core.orb.events import ClientType, InteractionAction, OrbInteractionEvent

        event = OrbInteractionEvent()
        assert event.event_id is not None
        assert event.client == ClientType.DESKTOP
        assert event.action == InteractionAction.TAP
        assert event.context == {}
        assert event.timestamp > 0

    @pytest.mark.unit
    def test_event_creation_with_values(self) -> None:
        """Event should accept custom values."""
        from kagami.core.orb.events import ClientType, InteractionAction, OrbInteractionEvent

        event = OrbInteractionEvent(
            event_id="test-123",
            client=ClientType.VISION_PRO,
            action=InteractionAction.GAZE_DWELL,
            context={"room": "living"},
            timestamp=12345.0,
        )
        assert event.event_id == "test-123"
        assert event.client == ClientType.VISION_PRO
        assert event.action == InteractionAction.GAZE_DWELL
        assert event.context == {"room": "living"}
        assert event.timestamp == 12345.0

    @pytest.mark.unit
    def test_event_is_immutable(self) -> None:
        """Event dataclass should be frozen (immutable)."""
        from kagami.core.orb.events import OrbInteractionEvent

        event = OrbInteractionEvent()
        with pytest.raises(FrozenInstanceError):
            event.event_id = "new-id"  # type: ignore[misc]

    @pytest.mark.unit
    def test_event_id_is_uuid_by_default(self) -> None:
        """Event ID should be valid UUID by default."""
        from kagami.core.orb.events import OrbInteractionEvent

        event = OrbInteractionEvent()
        # Should not raise ValueError
        uuid.UUID(event.event_id)

    @pytest.mark.unit
    def test_to_websocket_message_format(self) -> None:
        """to_websocket_message should return correct format."""
        from kagami.core.orb.events import ClientType, InteractionAction, OrbInteractionEvent

        event = OrbInteractionEvent(
            event_id="test-id",
            client=ClientType.HUB,
            action=InteractionAction.LONG_PRESS,
            context={"test": True},
            timestamp=12345.0,
        )
        msg = event.to_websocket_message()

        assert msg["type"] == "orb_interaction"
        assert msg["event_id"] == "test-id"
        assert msg["client"] == "hub"
        assert msg["action"] == "long_press"
        assert msg["context"] == {"test": True}
        assert msg["timestamp"] == 12345.0

    @pytest.mark.unit
    def test_from_websocket_message(self) -> None:
        """from_websocket_message should create event from dict."""
        from kagami.core.orb.events import ClientType, InteractionAction, OrbInteractionEvent

        data = {
            "event_id": "msg-id",
            "client": "ios",
            "action": "double_tap",
            "context": {"zone": "bedroom"},
            "timestamp": 99999.0,
        }
        event = OrbInteractionEvent.from_websocket_message(data)

        assert event.event_id == "msg-id"
        assert event.client == ClientType.IOS
        assert event.action == InteractionAction.DOUBLE_TAP
        assert event.context == {"zone": "bedroom"}
        assert event.timestamp == 99999.0

    @pytest.mark.unit
    def test_from_websocket_message_uses_defaults(self) -> None:
        """from_websocket_message should use defaults for missing fields."""
        from kagami.core.orb.events import ClientType, InteractionAction, OrbInteractionEvent

        data: dict = {}
        event = OrbInteractionEvent.from_websocket_message(data)

        assert event.client == ClientType.DESKTOP
        assert event.action == InteractionAction.TAP
        assert event.context == {}

    @pytest.mark.unit
    def test_roundtrip_websocket_serialization(self) -> None:
        """Event should survive roundtrip through WebSocket serialization."""
        from kagami.core.orb.events import ClientType, InteractionAction, OrbInteractionEvent

        original = OrbInteractionEvent(
            event_id="round-trip",
            client=ClientType.WATCH,
            action=InteractionAction.GESTURE,
            context={"gesture_type": "wave"},
        )
        msg = original.to_websocket_message()
        restored = OrbInteractionEvent.from_websocket_message(msg)

        assert restored.event_id == original.event_id
        assert restored.client == original.client
        assert restored.action == original.action
        assert restored.context == original.context


class TestOrbStateChangedEvent:
    """Tests for OrbStateChangedEvent dataclass."""

    @pytest.mark.unit
    def test_default_event_creation(self) -> None:
        """Default event should have sensible defaults."""
        from kagami.core.orb.events import OrbStateChangedEvent

        event = OrbStateChangedEvent()
        assert event.event_id is not None
        assert event.previous_colony is None
        assert event.new_colony is None
        assert event.trigger == "api"
        assert event.timestamp > 0

    @pytest.mark.unit
    def test_event_creation_with_values(self) -> None:
        """Event should accept custom values."""
        from kagami.core.orb.events import OrbStateChangedEvent

        event = OrbStateChangedEvent(
            event_id="change-123",
            previous_colony="spark",
            new_colony="forge",
            trigger="user_action",
            timestamp=54321.0,
        )
        assert event.event_id == "change-123"
        assert event.previous_colony == "spark"
        assert event.new_colony == "forge"
        assert event.trigger == "user_action"
        assert event.timestamp == 54321.0

    @pytest.mark.unit
    def test_to_websocket_message_format(self) -> None:
        """to_websocket_message should return correct format."""
        from kagami.core.orb.events import OrbStateChangedEvent

        event = OrbStateChangedEvent(
            event_id="ws-id",
            previous_colony="flow",
            new_colony="nexus",
            trigger="schedule",
            timestamp=11111.0,
        )
        msg = event.to_websocket_message()

        assert msg["type"] == "orb_state_changed"
        assert msg["event_id"] == "ws-id"
        assert msg["previous_colony"] == "flow"
        assert msg["new_colony"] == "nexus"
        assert msg["trigger"] == "schedule"
        assert msg["timestamp"] == 11111.0

    @pytest.mark.unit
    def test_from_websocket_message(self) -> None:
        """from_websocket_message should create event from dict."""
        from kagami.core.orb.events import OrbStateChangedEvent

        data = {
            "event_id": "recv-id",
            "previous_colony": "beacon",
            "new_colony": "grove",
            "trigger": "voice",
            "timestamp": 22222.0,
        }
        event = OrbStateChangedEvent.from_websocket_message(data)

        assert event.event_id == "recv-id"
        assert event.previous_colony == "beacon"
        assert event.new_colony == "grove"
        assert event.trigger == "voice"
        assert event.timestamp == 22222.0


class TestEventFactoryFunctions:
    """Tests for event factory functions."""

    @pytest.mark.unit
    def test_create_orb_interaction_basic(self) -> None:
        """create_orb_interaction should create event with enums."""
        from kagami.core.orb.events import ClientType, InteractionAction, create_orb_interaction

        event = create_orb_interaction(
            client=ClientType.VISION_PRO,
            action=InteractionAction.TAP,
        )
        assert event.client == ClientType.VISION_PRO
        assert event.action == InteractionAction.TAP

    @pytest.mark.unit
    def test_create_orb_interaction_with_strings(self) -> None:
        """create_orb_interaction should accept string values."""
        from kagami.core.orb.events import ClientType, InteractionAction, create_orb_interaction

        event = create_orb_interaction(
            client="ios",
            action="double_tap",
            context={"key": "value"},
        )
        assert event.client == ClientType.IOS
        assert event.action == InteractionAction.DOUBLE_TAP
        assert event.context == {"key": "value"}

    @pytest.mark.unit
    def test_create_state_changed_event(self) -> None:
        """create_state_changed_event should create event."""
        from kagami.core.orb.events import create_state_changed_event

        event = create_state_changed_event(
            previous_colony="spark",
            new_colony="forge",
            trigger="test",
        )
        assert event.previous_colony == "spark"
        assert event.new_colony == "forge"
        assert event.trigger == "test"


# =============================================================================
# colors.py Tests
# =============================================================================


class TestColonyColor:
    """Tests for ColonyColor dataclass."""

    @pytest.mark.unit
    def test_colony_color_creation(self) -> None:
        """ColonyColor should store all attributes."""
        from kagami.core.orb.colors import ColonyColor

        color = ColonyColor(
            name="test",
            hex="#FF0000",
            rgb=(255, 0, 0),
            description="Test Red",
        )
        assert color.name == "test"
        assert color.hex == "#FF0000"
        assert color.rgb == (255, 0, 0)
        assert color.description == "Test Red"

    @pytest.mark.unit
    def test_colony_color_is_immutable(self) -> None:
        """ColonyColor should be frozen (immutable)."""
        from kagami.core.orb.colors import ColonyColor

        color = ColonyColor("test", "#FF0000", (255, 0, 0), "Test")
        with pytest.raises(FrozenInstanceError):
            color.name = "new"  # type: ignore[misc]

    @pytest.mark.unit
    def test_css_rgba_default_alpha(self) -> None:
        """css_rgba with default alpha should be 1.0."""
        from kagami.core.orb.colors import ColonyColor

        color = ColonyColor("test", "#FF0000", (255, 128, 64), "Test")
        assert color.css_rgba() == "rgba(255, 128, 64, 1.0)"

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "alpha,expected",
        [
            (0.0, "rgba(255, 128, 64, 0.0)"),
            (0.5, "rgba(255, 128, 64, 0.5)"),
            (1.0, "rgba(255, 128, 64, 1.0)"),
        ],
    )
    def test_css_rgba_custom_alpha(self, alpha: float, expected: str) -> None:
        """css_rgba should use custom alpha value."""
        from kagami.core.orb.colors import ColonyColor

        color = ColonyColor("test", "#FF8040", (255, 128, 64), "Test")
        assert color.css_rgba(alpha) == expected

    @pytest.mark.unit
    def test_swift_color_format(self) -> None:
        """swift_color should return correct Swift Color initializer."""
        from kagami.core.orb.colors import ColonyColor

        color = ColonyColor("test", "#FF8040", (255, 128, 64), "Test")
        result = color.swift_color()
        assert "Color(red:" in result
        assert "green:" in result
        assert "blue:" in result
        # 255/255 = 1.0, 128/255 ≈ 0.50, 64/255 ≈ 0.25
        assert "1.00" in result

    @pytest.mark.unit
    def test_led_rgbw_pure_red(self) -> None:
        """led_rgbw for pure red should have no white component."""
        from kagami.core.orb.colors import ColonyColor

        color = ColonyColor("red", "#FF0000", (255, 0, 0), "Red")
        r, g, b, w = color.led_rgbw()
        assert r == 255
        assert g == 0
        assert b == 0
        assert w == 0

    @pytest.mark.unit
    def test_led_rgbw_white(self) -> None:
        """led_rgbw for white should extract white component."""
        from kagami.core.orb.colors import ColonyColor

        color = ColonyColor("white", "#FFFFFF", (255, 255, 255), "White")
        r, g, b, w = color.led_rgbw()
        assert r == 0
        assert g == 0
        assert b == 0
        assert w == 255

    @pytest.mark.unit
    def test_led_rgbw_mixed_color(self) -> None:
        """led_rgbw for mixed color should extract white component."""
        from kagami.core.orb.colors import ColonyColor

        color = ColonyColor("test", "#C8C864", (200, 200, 100), "Test")
        r, g, b, w = color.led_rgbw()
        # min(200, 200, 100) = 100 for white
        assert w == 100
        assert r == 100  # 200 - 100
        assert g == 100  # 200 - 100
        assert b == 0  # 100 - 100


class TestGetColonyColor:
    """Tests for get_colony_color function."""

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "colony,expected_hex",
        [
            ("spark", "#FF6B35"),
            ("forge", "#FFB347"),
            ("flow", "#4ECDC4"),
            ("nexus", "#9B59B6"),
            ("beacon", "#D4AF37"),
            ("grove", "#27AE60"),
            ("crystal", "#E0E0E0"),
        ],
    )
    def test_get_color_for_all_colonies(self, colony: str, expected_hex: str) -> None:
        """get_colony_color should return correct color for each colony."""
        from kagami.core.orb.colors import get_colony_color

        color = get_colony_color(colony)
        assert color.hex == expected_hex

    @pytest.mark.unit
    def test_get_color_case_insensitive(self) -> None:
        """get_colony_color should be case insensitive."""
        from kagami.core.orb.colors import get_colony_color

        lower = get_colony_color("spark")
        upper = get_colony_color("SPARK")
        mixed = get_colony_color("SpArK")
        assert lower.hex == upper.hex == mixed.hex

    @pytest.mark.unit
    def test_get_color_none_returns_default(self) -> None:
        """get_colony_color(None) should return default idle color."""
        from kagami.core.orb.colors import DEFAULT_COLOR, get_colony_color

        color = get_colony_color(None)
        assert color.hex == DEFAULT_COLOR.hex
        assert color.name == "idle"

    @pytest.mark.unit
    def test_get_color_unknown_returns_default(self) -> None:
        """get_colony_color for unknown colony should return default."""
        from kagami.core.orb.colors import DEFAULT_COLOR, get_colony_color

        color = get_colony_color("nonexistent")
        assert color.hex == DEFAULT_COLOR.hex


class TestGetSafetyColor:
    """Tests for get_safety_color function."""

    @pytest.mark.unit
    def test_high_safety_returns_crystal(self) -> None:
        """High safety (>= 0.7) should return crystal color."""
        from kagami.core.orb.colors import COLONY_COLORS, get_safety_color

        for h_x in [0.7, 0.8, 0.9, 1.0]:
            color = get_safety_color(h_x)
            assert color.hex == COLONY_COLORS["crystal"].hex

    @pytest.mark.unit
    def test_medium_safety_returns_amber(self) -> None:
        """Medium safety (0.3-0.7) should return safety amber."""
        from kagami.core.orb.colors import SAFETY_COLOR, get_safety_color

        for h_x in [0.3, 0.4, 0.5, 0.6, 0.69]:
            color = get_safety_color(h_x)
            assert color.hex == SAFETY_COLOR.hex

    @pytest.mark.unit
    def test_low_safety_returns_error(self) -> None:
        """Low safety (< 0.3) should return error red."""
        from kagami.core.orb.colors import ERROR_COLOR, get_safety_color

        for h_x in [0.0, 0.1, 0.2, 0.29]:
            color = get_safety_color(h_x)
            assert color.hex == ERROR_COLOR.hex

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "h_x,expected_description",
        [
            (0.0, "Error Red"),
            (0.29, "Error Red"),
            (0.3, "Safety Amber"),
            (0.5, "Safety Amber"),
            (0.69, "Safety Amber"),
            (0.7, "Diamond White"),
            (1.0, "Diamond White"),
        ],
    )
    def test_safety_color_thresholds(self, h_x: float, expected_description: str) -> None:
        """Test safety color at boundary values."""
        from kagami.core.orb.colors import get_safety_color

        color = get_safety_color(h_x)
        assert color.description == expected_description


class TestColorConstants:
    """Tests for color module constants."""

    @pytest.mark.unit
    def test_default_color_exists(self) -> None:
        """DEFAULT_COLOR should be defined."""
        from kagami.core.orb.colors import DEFAULT_COLOR

        assert DEFAULT_COLOR.name == "idle"
        assert DEFAULT_COLOR.hex == "#4A90D9"

    @pytest.mark.unit
    def test_error_color_exists(self) -> None:
        """ERROR_COLOR should be defined."""
        from kagami.core.orb.colors import ERROR_COLOR

        assert ERROR_COLOR.name == "error"
        assert ERROR_COLOR.hex == "#E74C3C"

    @pytest.mark.unit
    def test_safety_color_exists(self) -> None:
        """SAFETY_COLOR should be defined."""
        from kagami.core.orb.colors import SAFETY_COLOR

        assert SAFETY_COLOR.name == "safety"
        assert SAFETY_COLOR.hex == "#F39C12"

    @pytest.mark.unit
    def test_colony_enum_matches_colors(self) -> None:
        """Colony enum values should match COLONY_COLORS keys."""
        from kagami.core.orb.colors import COLONY_COLORS, Colony

        for colony in Colony:
            assert colony.value in COLONY_COLORS


# =============================================================================
# constants.py Tests
# =============================================================================


class TestSpatialZoneType:
    """Tests for SpatialZoneType enum."""

    @pytest.mark.unit
    def test_all_zone_types_exist(self) -> None:
        """All expected zone types should be defined."""
        from kagami.core.orb.constants import SpatialZoneType

        expected = ["intimate", "personal", "social", "ambient"]
        for zone_value in expected:
            zone = SpatialZoneType(zone_value)
            assert zone.value == zone_value


class TestSpatialZone:
    """Tests for SpatialZone dataclass."""

    @pytest.mark.unit
    def test_spatial_zone_creation(self) -> None:
        """SpatialZone should store all attributes."""
        from kagami.core.orb.constants import SpatialZone, SpatialZoneType

        zone = SpatialZone(
            zone_type=SpatialZoneType.INTIMATE,
            min_distance=0.0,
            max_distance=0.5,
            description="Test zone",
            typical_content=["alerts"],
        )
        assert zone.zone_type == SpatialZoneType.INTIMATE
        assert zone.min_distance == 0.0
        assert zone.max_distance == 0.5
        assert zone.description == "Test zone"
        assert zone.typical_content == ["alerts"]

    @pytest.mark.unit
    def test_contains_within_bounds(self) -> None:
        """contains should return True for distance within bounds."""
        from kagami.core.orb.constants import SpatialZone, SpatialZoneType

        zone = SpatialZone(SpatialZoneType.PERSONAL, 0.5, 1.5, "Test", [])
        assert zone.contains(0.5) is True
        assert zone.contains(1.0) is True
        assert zone.contains(1.49) is True

    @pytest.mark.unit
    def test_contains_at_boundaries(self) -> None:
        """contains should handle boundaries correctly (min inclusive, max exclusive)."""
        from kagami.core.orb.constants import SpatialZone, SpatialZoneType

        zone = SpatialZone(SpatialZoneType.PERSONAL, 0.5, 1.5, "Test", [])
        assert zone.contains(0.5) is True  # min is inclusive
        assert zone.contains(1.5) is False  # max is exclusive

    @pytest.mark.unit
    def test_contains_outside_bounds(self) -> None:
        """contains should return False for distance outside bounds."""
        from kagami.core.orb.constants import SpatialZone, SpatialZoneType

        zone = SpatialZone(SpatialZoneType.PERSONAL, 0.5, 1.5, "Test", [])
        assert zone.contains(0.4) is False
        assert zone.contains(1.6) is False


class TestSpatialZonesConstant:
    """Tests for SPATIAL_ZONES constant."""

    @pytest.mark.unit
    def test_all_zones_defined(self) -> None:
        """All four spatial zones should be defined."""
        from kagami.core.orb.constants import SPATIAL_ZONES

        assert "intimate" in SPATIAL_ZONES
        assert "personal" in SPATIAL_ZONES
        assert "social" in SPATIAL_ZONES
        assert "ambient" in SPATIAL_ZONES

    @pytest.mark.unit
    def test_zones_are_contiguous(self) -> None:
        """Zones should be contiguous (no gaps)."""
        from kagami.core.orb.constants import SPATIAL_ZONES

        zones = list(SPATIAL_ZONES.values())
        zones.sort(key=lambda z: z.min_distance)

        for i in range(len(zones) - 1):
            assert zones[i].max_distance == zones[i + 1].min_distance

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "zone_name,min_dist,max_dist",
        [
            ("intimate", 0.0, 0.45),
            ("personal", 0.45, 1.2),
            ("social", 1.2, 3.6),
            ("ambient", 3.6, 10.0),
        ],
    )
    def test_zone_distances(self, zone_name: str, min_dist: float, max_dist: float) -> None:
        """Verify zone distance boundaries from visionOS spec."""
        from kagami.core.orb.constants import SPATIAL_ZONES

        zone = SPATIAL_ZONES[zone_name]
        assert zone.min_distance == min_dist
        assert zone.max_distance == max_dist


class TestGetZoneForDistance:
    """Tests for get_zone_for_distance function."""

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "distance,expected_zone",
        [
            (0.0, "intimate"),
            (0.2, "intimate"),
            (0.44, "intimate"),
            (0.45, "personal"),
            (0.8, "personal"),
            (1.19, "personal"),
            (1.2, "social"),
            (2.5, "social"),
            (3.59, "social"),
            (3.6, "ambient"),
            (5.0, "ambient"),
            (9.9, "ambient"),
        ],
    )
    def test_zone_for_various_distances(self, distance: float, expected_zone: str) -> None:
        """get_zone_for_distance should return correct zone."""
        from kagami.core.orb.constants import get_zone_for_distance

        zone = get_zone_for_distance(distance)
        assert zone.zone_type.value == expected_zone

    @pytest.mark.unit
    def test_very_far_distance_returns_ambient(self) -> None:
        """Very far distances should default to ambient."""
        from kagami.core.orb.constants import SpatialZoneType, get_zone_for_distance

        zone = get_zone_for_distance(100.0)
        assert zone.zone_type == SpatialZoneType.AMBIENT


class TestLEDZone:
    """Tests for LEDZone dataclass."""

    @pytest.mark.unit
    def test_led_zone_creation(self) -> None:
        """LEDZone should store all attributes."""
        from kagami.core.orb.constants import LEDZone

        zone = LEDZone(colony="test", led_start=0, led_end=2)
        assert zone.colony == "test"
        assert zone.led_start == 0
        assert zone.led_end == 2

    @pytest.mark.unit
    def test_led_count_property(self) -> None:
        """led_count should return correct count."""
        from kagami.core.orb.constants import LEDZone

        zone = LEDZone("test", 0, 2)  # LEDs 0, 1, 2
        assert zone.led_count == 3

    @pytest.mark.unit
    def test_led_indices_property(self) -> None:
        """led_indices should return list of indices."""
        from kagami.core.orb.constants import LEDZone

        zone = LEDZone("test", 3, 5)  # LEDs 3, 4, 5
        assert zone.led_indices == [3, 4, 5]


class TestLEDZoneMapping:
    """Tests for LED_ZONE_MAPPING constant."""

    @pytest.mark.unit
    def test_all_colonies_have_led_zones(self) -> None:
        """All colonies should have LED zones defined."""
        from kagami.core.orb.constants import LED_ZONE_MAPPING

        colonies = ["spark", "forge", "flow", "nexus", "beacon", "grove", "crystal"]
        for colony in colonies:
            assert colony in LED_ZONE_MAPPING

    @pytest.mark.unit
    def test_led_zones_cover_24_leds(self) -> None:
        """All LED zones together should cover 24 LEDs."""
        from kagami.core.orb.constants import LED_ZONE_MAPPING

        all_indices = set()
        for zone in LED_ZONE_MAPPING.values():
            all_indices.update(zone.led_indices)

        assert len(all_indices) == 24
        assert min(all_indices) == 0
        assert max(all_indices) == 23

    @pytest.mark.unit
    def test_led_zones_no_overlap(self) -> None:
        """LED zones should not overlap."""
        from kagami.core.orb.constants import LED_ZONE_MAPPING

        all_indices = []
        for zone in LED_ZONE_MAPPING.values():
            all_indices.extend(zone.led_indices)

        # If no overlap, length of list equals length of set
        assert len(all_indices) == len(set(all_indices))


class TestGetColonyLedIndices:
    """Tests for get_colony_led_indices function."""

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "colony,expected_indices",
        [
            ("spark", [0, 1, 2]),
            ("forge", [3, 4, 5]),
            ("flow", [6, 7, 8, 9]),
            ("nexus", [10, 11, 12, 13]),
            ("beacon", [14, 15, 16, 17]),
            ("grove", [18, 19, 20]),
            ("crystal", [21, 22, 23]),
        ],
    )
    def test_led_indices_for_all_colonies(self, colony: str, expected_indices: list) -> None:
        """get_colony_led_indices should return correct indices for each colony."""
        from kagami.core.orb.constants import get_colony_led_indices

        indices = get_colony_led_indices(colony)
        assert indices == expected_indices

    @pytest.mark.unit
    def test_led_indices_case_insensitive(self) -> None:
        """get_colony_led_indices should be case insensitive."""
        from kagami.core.orb.constants import get_colony_led_indices

        lower = get_colony_led_indices("spark")
        upper = get_colony_led_indices("SPARK")
        mixed = get_colony_led_indices("SpArK")
        assert lower == upper == mixed

    @pytest.mark.unit
    def test_unknown_colony_returns_empty(self) -> None:
        """Unknown colony should return empty list."""
        from kagami.core.orb.constants import get_colony_led_indices

        indices = get_colony_led_indices("nonexistent")
        assert indices == []


class TestOrbPositionPreset:
    """Tests for OrbPositionPreset dataclass."""

    @pytest.mark.unit
    def test_preset_creation(self) -> None:
        """OrbPositionPreset should store all attributes."""
        from kagami.core.orb.constants import OrbPositionPreset, SpatialZoneType

        preset = OrbPositionPreset(
            name="test",
            position=(1.0, 2.0, 3.0),
            zone=SpatialZoneType.AMBIENT,
        )
        assert preset.name == "test"
        assert preset.position == (1.0, 2.0, 3.0)
        assert preset.zone == SpatialZoneType.AMBIENT

    @pytest.mark.unit
    def test_all_presets_defined(self) -> None:
        """All expected presets should be defined."""
        from kagami.core.orb.constants import ORB_POSITION_PRESETS

        expected = ["visionos_default", "visionos_presence", "desktop_ambient", "hardware_docked"]
        for preset_name in expected:
            assert preset_name in ORB_POSITION_PRESETS

    @pytest.mark.unit
    def test_visionos_default_in_ambient_zone(self) -> None:
        """VisionOS default position should be in ambient zone."""
        from kagami.core.orb.constants import ORB_POSITION_PRESETS, SpatialZoneType

        preset = ORB_POSITION_PRESETS["visionos_default"]
        assert preset.zone == SpatialZoneType.AMBIENT

    @pytest.mark.unit
    def test_visionos_presence_in_personal_zone(self) -> None:
        """VisionOS presence position should be in personal zone."""
        from kagami.core.orb.constants import ORB_POSITION_PRESETS, SpatialZoneType

        preset = ORB_POSITION_PRESETS["visionos_presence"]
        assert preset.zone == SpatialZoneType.PERSONAL
