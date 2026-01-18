"""Forge Multi-Colony Conversation System.

Real-time multi-party conversations between the seven colonies,
with room-aware audio routing and catastrophe-driven dialogue patterns.

Created: December 29, 2025
Purpose: Implement optimal multi-party conversation logic through Forge
"""

from .conversation_manager import ForgeConversationManager
from .notifications import KagamiNotificationSystem, get_notification_system
from .room_mapping import ColonyRoomAffinity, RoomProfile, SmartHomeRoomMapper
from .room_streamer import ConversationAudioRouter, RealtimeRoomStreamer
from .state import (
    ColonyPersonality,
    ConversationState,
    ConversationTurn,
    EmotionType,
    get_colony_personality,
    get_colony_response_pattern,
)

__all__ = [
    "ColonyPersonality",
    "ColonyRoomAffinity",
    "ConversationAudioRouter",
    # Character and state management
    "ConversationState",
    "ConversationTurn",
    "EmotionType",
    # Core conversation management
    "ForgeConversationManager",
    # Brief notification system
    "KagamiNotificationSystem",
    "RealtimeRoomStreamer",
    "RoomProfile",
    # Smart home integration
    "SmartHomeRoomMapper",
    "get_colony_personality",
    "get_colony_response_pattern",
    "get_notification_system",
]
