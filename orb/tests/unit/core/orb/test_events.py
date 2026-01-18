"""Unit tests for orb events.

Colony: Crystal (e₇) — Verification

Tests:
    - OrbInteractionEvent creation
    - OrbStateChangedEvent creation
    - WebSocket message serialization
"""

import time
from kagami.core.orb.events import (
    OrbInteractionEvent,
    OrbStateChangedEvent,
    InteractionAction,
    ClientType,
    create_orb_interaction,
    create_state_changed_event,
)


class TestOrbInteractionEvent:
    """Tests for OrbInteractionEvent."""

    def test_default_event(self) -> None:
        """Test default event values."""
        event = OrbInteractionEvent()

        assert event.client == ClientType.DESKTOP
        assert event.action == InteractionAction.TAP
        assert event.context == {}
        assert event.event_id is not None

    def test_event_with_values(self) -> None:
        """Test event with specific values."""
        event = OrbInteractionEvent(
            client=ClientType.VISION_PRO,
            action=InteractionAction.LONG_PRESS,
            context={"scene": "movie_mode"},
        )

        assert event.client == ClientType.VISION_PRO
        assert event.action == InteractionAction.LONG_PRESS
        assert event.context["scene"] == "movie_mode"

    def test_to_websocket_message(self) -> None:
        """Test WebSocket message serialization."""
        event = OrbInteractionEvent(
            client=ClientType.HUB,
            action=InteractionAction.VOICE_WAKE,
        )

        msg = event.to_websocket_message()

        assert msg["type"] == "orb_interaction"
        assert msg["client"] == "hub"
        assert msg["action"] == "voice_wake"
        assert "event_id" in msg
        assert "timestamp" in msg

    def test_from_websocket_message(self) -> None:
        """Test WebSocket message deserialization."""
        data = {
            "type": "orb_interaction",
            "event_id": "test-id",
            "client": "vision_pro",
            "action": "tap",
            "context": {"room": "living_room"},
            "timestamp": time.time(),
        }

        event = OrbInteractionEvent.from_websocket_message(data)

        assert event.event_id == "test-id"
        assert event.client == ClientType.VISION_PRO
        assert event.action == InteractionAction.TAP
        assert event.context["room"] == "living_room"


class TestOrbStateChangedEvent:
    """Tests for OrbStateChangedEvent."""

    def test_default_event(self) -> None:
        """Test default event values."""
        event = OrbStateChangedEvent()

        assert event.previous_colony is None
        assert event.new_colony is None
        assert event.trigger == "api"

    def test_event_with_colonies(self) -> None:
        """Test event with colony change."""
        event = OrbStateChangedEvent(
            previous_colony="spark",
            new_colony="forge",
            trigger="user_action",
        )

        assert event.previous_colony == "spark"
        assert event.new_colony == "forge"
        assert event.trigger == "user_action"

    def test_to_websocket_message(self) -> None:
        """Test WebSocket message serialization."""
        event = OrbStateChangedEvent(
            previous_colony="idle",
            new_colony="flow",
        )

        msg = event.to_websocket_message()

        assert msg["type"] == "orb_state_changed"
        assert msg["previous_colony"] == "idle"
        assert msg["new_colony"] == "flow"


class TestFactoryFunctions:
    """Tests for event factory functions."""

    def test_create_orb_interaction_with_strings(self) -> None:
        """Test create_orb_interaction with string arguments."""
        event = create_orb_interaction(
            client="vision_pro",
            action="tap",
            context={"test": "value"},
        )

        assert event.client == ClientType.VISION_PRO
        assert event.action == InteractionAction.TAP
        assert event.context["test"] == "value"

    def test_create_orb_interaction_with_enums(self) -> None:
        """Test create_orb_interaction with enum arguments."""
        event = create_orb_interaction(
            client=ClientType.HUB,
            action=InteractionAction.GAZE_DWELL,
        )

        assert event.client == ClientType.HUB
        assert event.action == InteractionAction.GAZE_DWELL

    def test_create_state_changed_event(self) -> None:
        """Test create_state_changed_event factory."""
        event = create_state_changed_event(
            previous_colony="beacon",
            new_colony="grove",
            trigger="scheduled",
        )

        assert event.previous_colony == "beacon"
        assert event.new_colony == "grove"
        assert event.trigger == "scheduled"


class TestClientType:
    """Tests for ClientType enum."""

    def test_all_client_types(self) -> None:
        """Test that all expected client types exist."""
        expected = [
            "vision_pro", "hub", "desktop", "watch",
            "ios", "android", "hardware_orb", "web"
        ]

        for client in expected:
            assert ClientType(client).value == client


class TestInteractionAction:
    """Tests for InteractionAction enum."""

    def test_all_action_types(self) -> None:
        """Test that all expected action types exist."""
        expected = [
            "tap", "long_press", "gaze_dwell",
            "voice_wake", "gesture", "double_tap"
        ]

        for action in expected:
            assert InteractionAction(action).value == action
