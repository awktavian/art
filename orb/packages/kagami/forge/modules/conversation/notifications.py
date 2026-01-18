"""Brief & Elegant Notification System for Kagami.

Smart, concise notifications that respect user attention.
Maximum 5-7 words for TV, context-aware routing.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class NotificationConfig:
    """Configuration for brief, elegant notifications."""

    tv_max_words: int = 7
    tv_max_chars: int = 40
    voice_max_words: int = 10
    priority_levels: dict[str, str] = None

    def __post_init__(self):
        if self.priority_levels is None:
            self.priority_levels = {
                "critical": "🚨",
                "info": "ℹ️",
                "success": "✅",
                "conversation": "🎭",
                "system": "⚡",
            }


class KagamiNotificationSystem:
    """Brief, elegant notification system for all Kagami communications."""

    def __init__(self, smart_home_controller=None):
        self.controller = smart_home_controller
        self.config = NotificationConfig()

    def craft_brief_message(self, content: str, priority: str = "info") -> str:
        """Craft brief, elegant message from longer content."""

        # Pre-crafted brief templates
        brief_patterns = {
            "conversation_start": "🎭 Colony conversation started",
            "conversation_complete": "✅ Conversation complete",
            "system_ready": "⚡ Kagami systems ready",
            "colony_active": "🎭 Seven colonies active",
            "home_optimized": "🏠 Smart home optimized",
            "bottle_episode": "🎭 Bottle episode mode",
            "parallel_mode": "⚡ Parallel conversations",
            "character_depth": "🎭 Character personalities active",
            "room_configured": "🏠 Room configured",
            "fireplace_on": "🔥 Fireplace activated",
        }

        # Check for pattern matches
        content_lower = content.lower()
        for pattern, brief in brief_patterns.items():
            if any(word in content_lower for word in pattern.split("_")):
                return brief

        # Extract key words for custom brief message
        key_words = self._extract_key_words(content)
        emoji = self.config.priority_levels.get(priority, "ℹ️")

        # Construct brief message
        brief = f"{emoji} {' '.join(key_words[:5])}"

        # Ensure within limits
        if len(brief) > self.config.tv_max_chars:
            brief = f"{emoji} {key_words[0]} {key_words[1]}"

        return brief

    def _extract_key_words(self, content: str) -> list[str]:
        """Extract key words from longer content."""

        # Important words to prioritize
        priority_words = {
            "kagami",
            "colony",
            "colonies",
            "conversation",
            "ready",
            "complete",
            "active",
            "online",
            "system",
            "home",
            "smart",
            "optimized",
            "character",
            "firefly",
            "inside",
            "personality",
            "bottle",
            "parallel",
            "room",
            "audio",
            "voice",
            "notification",
        }

        # Skip common words
        skip_words = {
            "the",
            "and",
            "or",
            "but",
            "in",
            "on",
            "at",
            "to",
            "for",
            "of",
            "with",
            "by",
            "from",
            "up",
            "about",
            "into",
            "through",
            "during",
            "before",
            "after",
            "above",
            "below",
            "between",
            "among",
            "is",
            "are",
            "was",
            "were",
            "be",
            "been",
            "being",
            "have",
            "has",
            "had",
            "do",
            "does",
            "did",
            "will",
            "would",
            "could",
            "should",
            "may",
            "might",
            "must",
            "can",
            "this",
            "that",
            "these",
            "those",
            "a",
            "an",
        }

        words = content.lower().split()

        # First pass: collect priority words
        key_words = []
        for word in words:
            clean_word = word.strip(".,!?;:")
            if clean_word in priority_words:
                key_words.append(clean_word.title())

        # Second pass: add other important words if needed
        if len(key_words) < 3:
            for word in words:
                clean_word = word.strip(".,!?;:")
                if (
                    clean_word not in skip_words
                    and clean_word not in [w.lower() for w in key_words]
                    and len(clean_word) > 2
                ):
                    key_words.append(clean_word.title())
                    if len(key_words) >= 5:
                        break

        return key_words[:5]

    async def notify_tv(self, content: str, priority: str = "info") -> bool:
        """Send brief notification to TV."""
        if not self.controller:
            return False

        brief_message = self.craft_brief_message(content, priority)

        try:
            success = await self.controller.tv_notification(brief_message)
            if success:
                logger.info(f"📺 Brief TV: {brief_message}")
            return success
        except Exception as e:
            logger.debug(f"TV notification error: {e}")
            return False

    async def notify_voice(self, content: str, rooms: list[str] | None = None) -> bool:
        """Send brief voice notification to rooms."""
        if not self.controller or not hasattr(self.controller, "_audio_bridge"):
            return False

        # Craft slightly longer but still brief voice message
        brief_voice = self.craft_brief_message(content, "info")

        # Default to living room if no rooms specified
        if not rooms:
            rooms = ["Living Room"]

        try:
            audio_bridge = self.controller._audio_bridge
            success, _ = await audio_bridge.announce(text=brief_voice, rooms=rooms, colony="kagami")
            if success:
                logger.info(f"🔊 Brief Voice: {brief_voice} → {rooms}")
            return success
        except Exception as e:
            logger.debug(f"Voice notification error: {e}")
            return False

    async def notify_both(
        self, content: str, priority: str = "info", rooms: list[str] | None = None
    ) -> tuple[bool, bool]:
        """Send brief notification to both TV and voice simultaneously."""

        # Parallel execution for maximum efficiency
        tv_task = self.notify_tv(content, priority)
        voice_task = self.notify_voice(content, rooms)

        tv_success = await tv_task
        voice_success = await voice_task

        return tv_success, voice_success

    async def conversation_notification(
        self, event: str, details: str = "", rooms: list[str] | None = None
    ) -> None:
        """Brief notification for conversation events."""

        notifications = {
            "start": "🎭 Colony conversation started",
            "complete": "✅ Conversation complete",
            "bottle": "🎭 Bottle episode mode",
            "parallel": "⚡ Parallel conversations",
        }

        message = notifications.get(event, f"🎭 {event.title()}")
        await self.notify_tv(message, "conversation")

    async def system_notification(self, event: str, priority: str = "system") -> None:
        """Brief system status notification."""

        system_messages = {
            "ready": "⚡ Kagami systems ready",
            "optimized": "🏠 Smart home optimized",
            "active": "🎭 Seven colonies active",
            "configured": "🏠 Room configured",
        }

        message = system_messages.get(event, f"⚡ {event.title()}")
        await self.notify_tv(message, priority)

    def get_brief_config(self) -> NotificationConfig:
        """Get current notification configuration."""
        return self.config

    def update_brief_config(self, **kwargs) -> None:
        """Update notification configuration."""
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)


# Global instance for easy access
_notification_system: KagamiNotificationSystem | None = None


def get_notification_system(smart_home_controller=None) -> KagamiNotificationSystem:
    """Get global notification system instance."""
    global _notification_system

    if _notification_system is None:
        _notification_system = KagamiNotificationSystem(smart_home_controller)
    elif smart_home_controller and not _notification_system.controller:
        _notification_system.controller = smart_home_controller

    return _notification_system
