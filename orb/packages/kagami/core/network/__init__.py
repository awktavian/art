"""Network primitives for K os.

Includes:
- message_bus: Redis-backed pub/sub for inter-instance coordination
- load_balancer: Request distribution
"""

from .message_bus import MeshMessageBus, get_message_bus

__all__ = [
    # Message bus
    "MeshMessageBus",
    "get_message_bus",
]
