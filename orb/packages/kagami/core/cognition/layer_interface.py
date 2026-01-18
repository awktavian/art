from __future__ import annotations

"""Communication protocol between cognitive layers."""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class LayerMessage:
    """Message passed between cognitive layers."""

    from_layer: str  # "technological"|"scientific"|"philosophical"
    to_layer: str
    message_type: str  # "feedback"|"question"|"proposal"|"instruction"
    content: dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.utcnow)
    correlation_id: str | None = None


class LayerInterface:
    """Interface for layer-to-layer communication."""

    def __init__(self) -> None:
        self._message_queue: list[LayerMessage] = []

    def send_message(self, message: LayerMessage) -> None:
        """Send message to another layer."""
        self._message_queue.append(message)

    def get_messages_for(self, layer: str) -> list[LayerMessage]:
        """Get pending messages for a specific layer."""
        messages = [m for m in self._message_queue if m.to_layer == layer]
        # Remove retrieved messages
        self._message_queue = [m for m in self._message_queue if m.to_layer != layer]
        return messages

    def has_messages_for(self, layer: str) -> bool:
        """Check if there are pending messages."""
        return any(m.to_layer == layer for m in self._message_queue)
