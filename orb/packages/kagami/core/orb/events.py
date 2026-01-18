"""Orb Events — Cross-Client Interaction Events.

This module defines events for orb interactions that are broadcast
to all connected clients. When a user taps the orb on VisionOS,
the Hub LED ring should respond. This enables cross-client sync.

Event Types:
    - OrbInteractionEvent: User interacted with orb
    - OrbStateChangedEvent: Server state changed

Colony: Nexus (e₄) — Event-driven synchronization

Example:
    >>> from kagami.core.orb import create_orb_interaction
    >>> event = create_orb_interaction(
    ...     client="vision_pro",
    ...     action="tap",
    ...     context="evening_scene"
    ... )
    >>> event.to_websocket_message()
    {'type': 'orb_interaction', 'client': 'vision_pro', ...}
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class InteractionAction(str, Enum):
    """Types of orb interactions.

    Actions map to specific responses:
        - TAP: Quick press, activates quick action
        - LONG_PRESS: Hold, opens menu
        - GAZE_DWELL: Look + wait, activates context action
        - VOICE_WAKE: Wake word detected
        - GESTURE: Hand gesture recognized
    """

    TAP = "tap"
    LONG_PRESS = "long_press"
    GAZE_DWELL = "gaze_dwell"
    VOICE_WAKE = "voice_wake"
    GESTURE = "gesture"
    DOUBLE_TAP = "double_tap"


class ClientType(str, Enum):
    """Client platform identifiers."""

    VISION_PRO = "vision_pro"
    HUB = "hub"
    DESKTOP = "desktop"
    WATCH = "watch"
    IOS = "ios"
    ANDROID = "android"
    HARDWARE_ORB = "hardware_orb"
    WEB = "web"


@dataclass(frozen=True)
class OrbInteractionEvent:
    """Event emitted when user interacts with the orb.

    This event is broadcast to all clients so they can respond
    appropriately (e.g., Hub LED flash when VisionOS orb is tapped).

    Attributes:
        event_id: Unique event identifier
        client: Client that generated the interaction
        action: Type of interaction
        context: Additional context (time of day, room, etc.)
        timestamp: Unix timestamp

    Example:
        >>> event = OrbInteractionEvent(
        ...     client=ClientType.VISION_PRO,
        ...     action=InteractionAction.TAP,
        ...     context={"time_of_day": "evening", "room": "living_room"}
        ... )
    """

    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    client: ClientType = ClientType.DESKTOP
    action: InteractionAction = InteractionAction.TAP
    context: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_websocket_message(self) -> dict[str, Any]:
        """Convert to WebSocket message format.

        Returns:
            Dict for JSON serialization and broadcast
        """
        return {
            "type": "orb_interaction",
            "event_id": self.event_id,
            "client": self.client.value,
            "action": self.action.value,
            "context": self.context,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_websocket_message(cls, data: dict[str, Any]) -> OrbInteractionEvent:
        """Create from WebSocket message.

        Args:
            data: Dict from WebSocket

        Returns:
            OrbInteractionEvent instance
        """
        return cls(
            event_id=data.get("event_id", str(uuid.uuid4())),
            client=ClientType(data.get("client", "desktop")),
            action=InteractionAction(data.get("action", "tap")),
            context=data.get("context", {}),
            timestamp=data.get("timestamp", time.time()),
        )


@dataclass(frozen=True)
class OrbStateChangedEvent:
    """Event emitted when orb state changes on server.

    This event is broadcast to all clients when the canonical
    orb state is updated. Clients should update their display.

    Attributes:
        event_id: Unique event identifier
        previous_colony: Colony before change
        new_colony: Colony after change
        trigger: What caused the change
        timestamp: Unix timestamp
    """

    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    previous_colony: str | None = None
    new_colony: str | None = None
    trigger: str = "api"
    timestamp: float = field(default_factory=time.time)

    def to_websocket_message(self) -> dict[str, Any]:
        """Convert to WebSocket message format.

        Returns:
            Dict for JSON serialization and broadcast
        """
        return {
            "type": "orb_state_changed",
            "event_id": self.event_id,
            "previous_colony": self.previous_colony,
            "new_colony": self.new_colony,
            "trigger": self.trigger,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_websocket_message(cls, data: dict[str, Any]) -> OrbStateChangedEvent:
        """Create from WebSocket message.

        Args:
            data: Dict from WebSocket

        Returns:
            OrbStateChangedEvent instance
        """
        return cls(
            event_id=data.get("event_id", str(uuid.uuid4())),
            previous_colony=data.get("previous_colony"),
            new_colony=data.get("new_colony"),
            trigger=data.get("trigger", "api"),
            timestamp=data.get("timestamp", time.time()),
        )


# =============================================================================
# Factory Functions
# =============================================================================


def create_orb_interaction(
    client: str | ClientType,
    action: str | InteractionAction,
    context: dict[str, Any] | None = None,
) -> OrbInteractionEvent:
    """Create an orb interaction event.

    This is the preferred way to create interaction events
    for broadcasting to other clients.

    Args:
        client: Client platform (or ClientType enum)
        action: Interaction type (or InteractionAction enum)
        context: Additional context data

    Returns:
        OrbInteractionEvent for broadcasting

    Example:
        >>> event = create_orb_interaction(
        ...     client="vision_pro",
        ...     action="tap",
        ...     context={"scene": "movie_mode"}
        ... )
    """
    # Convert strings to enums
    if isinstance(client, str):
        client = ClientType(client)
    if isinstance(action, str):
        action = InteractionAction(action)

    return OrbInteractionEvent(
        client=client,
        action=action,
        context=context or {},
    )


def create_state_changed_event(
    previous_colony: str | None,
    new_colony: str | None,
    trigger: str = "api",
) -> OrbStateChangedEvent:
    """Create an orb state changed event.

    Args:
        previous_colony: Colony before change
        new_colony: Colony after change
        trigger: What caused the change

    Returns:
        OrbStateChangedEvent for broadcasting
    """
    return OrbStateChangedEvent(
        previous_colony=previous_colony,
        new_colony=new_colony,
        trigger=trigger,
    )
