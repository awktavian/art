"""Meta Ray-Ban Smart Glasses Integration.

First-person perspective for Kagami:
- Visual context (scene, objects, activity)
- Private audio (whispered notifications)
- Wakefulness detection (eyes open/closed)
- Presence enhancement (visual room hints)

Architecture:
    Meta Glasses (BLE) ← Companion App (WS) ← HAL Adapter ← This Integration

The HAL adapter handles protocol. This integration handles SmartHome semantics.

Created: December 31, 2025
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from kagami_smarthome import SmartHomeController

logger = logging.getLogger(__name__)


# =============================================================================
# VISUAL CONTEXT
# =============================================================================


@dataclass
class VisualContext:
    """Semantic features from glasses camera.

    Raw video stays on companion device. Only features sent to backend.
    """

    timestamp: float = 0.0

    # Scene understanding
    is_indoor: bool = True
    lighting: str = "normal"  # "bright", "dim", "dark"
    scene_type: str = "unknown"  # "kitchen", "office", "outdoor", etc.

    # Object detection
    detected_objects: list[str] = field(default_factory=list)
    detected_text: list[str] = field(default_factory=list)

    # Face detection
    faces_detected: int = 0
    known_people: list[str] = field(default_factory=list)

    # Activity inference
    activity_hint: str = "unknown"  # "working", "cooking", "relaxing"

    # Confidence
    confidence: float = 0.0


# Scene type to room mapping
SCENE_TO_ROOMS = {
    "kitchen": ["Kitchen"],
    "office": ["Office"],
    "bedroom": ["Primary Bedroom", "Bed 3", "Bed 4"],
    "bathroom": ["Primary Bath", "Bath 3", "Bath 4"],
    "living": ["Living Room"],
    "dining": ["Dining"],
    "gym": ["Gym"],
    "outdoor": ["Deck", "Patio", "Porch"],
    "garage": ["Garage"],
    "game_room": ["Game Room"],
    "entry": ["Entry", "Mudroom"],
}


# =============================================================================
# META GLASSES INTEGRATION
# =============================================================================


class MetaGlassesIntegration:
    """SmartHome integration for Meta Ray-Ban glasses.

    Wraps the HAL adapter and provides SmartHome-level features:
    - Room hints from visual context
    - Activity inference for automation
    - Private audio for notifications
    - Wakefulness signals

    Usage:
        glasses = MetaGlassesIntegration()
        await glasses.connect()

        context = await glasses.get_visual_context()
        print(f"Scene: {context.scene_type}")

        await glasses.whisper("Your meeting starts in 5 minutes")
    """

    def __init__(self):
        self._protocol = None
        self._camera = None
        self._audio = None
        self._connected = False
        self._smart_home: SmartHomeController | None = None

        # Callbacks
        self._context_callbacks: list[Callable[[VisualContext], Awaitable[None]]] = []
        self._wearing_callbacks: list[Callable[[bool], Awaitable[None]]] = []

        # State
        self._is_wearing = False
        self._last_context: VisualContext | None = None
        self._context_poll_task: asyncio.Task | None = None

        # Statistics
        self._stats = {
            "contexts_captured": 0,
            "whispers_sent": 0,
            "room_hints_provided": 0,
        }

    @property
    def is_connected(self) -> bool:
        """Check if connected to glasses."""
        return self._connected and self._protocol is not None

    @property
    def is_wearing(self) -> bool:
        """Check if user is currently wearing the glasses."""
        return self._is_wearing

    async def connect(self, companion_url: str = "ws://localhost:8001") -> bool:
        """Connect to glasses via companion app.

        Args:
            companion_url: WebSocket URL of companion app

        Returns:
            True if connected
        """
        try:
            from kagami_hal.adapters.meta_glasses import (
                MetaGlassesAudio,
                MetaGlassesCamera,
                MetaGlassesProtocol,
            )

            # Initialize protocol
            self._protocol = MetaGlassesProtocol()
            await self._protocol.initialize(companion_url)

            # Wait for connection
            for _ in range(10):  # 5 second timeout
                if self._protocol.is_connected:
                    break
                await asyncio.sleep(0.5)

            if not self._protocol.is_connected:
                logger.warning("MetaGlasses: Connection timeout")
                return False

            # Initialize camera and audio
            self._camera = MetaGlassesCamera(self._protocol)
            await self._camera.initialize()

            self._audio = MetaGlassesAudio(self._protocol)
            await self._audio.initialize()

            # Subscribe to wearing state changes
            def on_status_change(status):
                old_wearing = self._is_wearing
                self._is_wearing = status.is_wearing
                if old_wearing != self._is_wearing:
                    asyncio.create_task(self._emit_wearing_change(self._is_wearing))

            self._protocol.on_event(lambda e: self._handle_event(e))

            self._connected = True
            logger.info("✅ MetaGlasses connected")
            return True

        except ImportError:
            logger.warning("MetaGlasses HAL adapter not available")
            return False
        except Exception as e:
            logger.error(f"MetaGlasses connection failed: {e}")
            return False

    async def disconnect(self) -> None:
        """Disconnect from glasses."""
        if self._context_poll_task:
            self._context_poll_task.cancel()

        if self._audio:
            await self._audio.shutdown()
        if self._camera:
            await self._camera.shutdown()
        if self._protocol:
            await self._protocol.shutdown()

        self._connected = False
        logger.info("MetaGlasses disconnected")

    # =========================================================================
    # VISUAL CONTEXT
    # =========================================================================

    async def get_visual_context(self) -> VisualContext | None:
        """Capture current visual context from camera.

        Returns:
            VisualContext with scene understanding, or None if unavailable
        """
        if not self._camera or not self._connected:
            return None

        try:
            # Get context from camera adapter
            raw_context = await self._camera.get_visual_context()
            if not raw_context:
                return None

            # Convert to our VisualContext
            context = VisualContext(
                timestamp=raw_context.get("timestamp", datetime.now().timestamp()),
                is_indoor=raw_context.get("is_indoor", True),
                lighting=raw_context.get("lighting", "normal"),
                scene_type=raw_context.get("scene_type", "unknown"),
                detected_objects=raw_context.get("detected_objects", []),
                detected_text=raw_context.get("detected_text", []),
                faces_detected=raw_context.get("faces_detected", 0),
                known_people=raw_context.get("known_people", []),
                activity_hint=raw_context.get("activity_hint", "unknown"),
                confidence=raw_context.get("confidence", 0.5),
            )

            self._last_context = context
            self._stats["contexts_captured"] += 1

            # Emit to callbacks
            for callback in self._context_callbacks:
                try:
                    await callback(context)
                except Exception as e:
                    logger.error(f"Context callback error: {e}")

            return context

        except Exception as e:
            logger.error(f"Failed to get visual context: {e}")
            return None

    def get_room_hint(self) -> str | None:
        """Get room hint from last visual context.

        Returns:
            Most likely room name, or None
        """
        if not self._last_context:
            return None

        scene_type = self._last_context.scene_type
        rooms = SCENE_TO_ROOMS.get(scene_type)

        if rooms:
            self._stats["room_hints_provided"] += 1
            return rooms[0]  # Return first match

        return None

    def on_visual_context(self, callback: Callable[[VisualContext], Awaitable[None]]) -> None:
        """Subscribe to visual context updates."""
        self._context_callbacks.append(callback)

    # =========================================================================
    # AUDIO (WHISPER)
    # =========================================================================

    async def whisper(self, text: str, priority: str = "normal") -> bool:
        """Whisper a message to the glasses speakers.

        Only the wearer hears this - perfect for private notifications.

        Args:
            text: Message to speak
            priority: "low", "normal", "high", "urgent"

        Returns:
            True if sent successfully
        """
        if not self._audio or not self._connected:
            return False

        if not self._is_wearing:
            logger.debug("Glasses not being worn, skipping whisper")
            return False

        try:
            success = await self._audio.speak(text, priority=priority)
            if success:
                self._stats["whispers_sent"] += 1
            return success
        except Exception as e:
            logger.error(f"Whisper failed: {e}")
            return False

    async def play_notification(self, sound: str = "default") -> bool:
        """Play a notification sound.

        Args:
            sound: "default", "subtle", "alert"
        """
        if not self._audio or not self._connected:
            return False

        return await self._audio.play_notification(sound)

    # =========================================================================
    # SMART HOME INTEGRATION
    # =========================================================================

    def set_smart_home(self, controller: SmartHomeController) -> None:
        """Connect to SmartHome for enhanced integration."""
        self._smart_home = controller

    async def announce_if_wearing(self, text: str, fallback_rooms: list[str] | None = None) -> bool:
        """Announce via glasses if wearing, otherwise via speakers.

        Args:
            text: Message to announce
            fallback_rooms: Rooms to announce in if not wearing glasses

        Returns:
            True if announced
        """
        if self._is_wearing and self._audio:
            return await self.whisper(text)
        elif self._smart_home and fallback_rooms:
            await self._smart_home.announce(text, rooms=fallback_rooms)
            return True
        return False

    def on_wearing_change(self, callback: Callable[[bool], Awaitable[None]]) -> None:
        """Subscribe to wearing state changes."""
        self._wearing_callbacks.append(callback)

    async def _emit_wearing_change(self, is_wearing: bool) -> None:
        """Emit wearing state change to callbacks."""
        for callback in self._wearing_callbacks:
            try:
                await callback(is_wearing)
            except Exception as e:
                logger.error(f"Wearing callback error: {e}")

    async def _handle_event(self, event) -> None:
        """Handle events from glasses protocol."""
        if event.event_type == "wearing_state":
            old = self._is_wearing
            self._is_wearing = event.data.get("is_wearing", False)
            if old != self._is_wearing:
                await self._emit_wearing_change(self._is_wearing)

    # =========================================================================
    # STATS
    # =========================================================================

    @property
    def stats(self) -> dict[str, Any]:
        """Get integration statistics."""
        return {
            **self._stats,
            "connected": self._connected,
            "is_wearing": self._is_wearing,
            "last_context_scene": self._last_context.scene_type if self._last_context else None,
        }


# =============================================================================
# FACTORY
# =============================================================================

_glasses: MetaGlassesIntegration | None = None


async def get_meta_glasses() -> MetaGlassesIntegration:
    """Get or create the Meta Glasses integration singleton."""
    global _glasses
    if _glasses is None:
        _glasses = MetaGlassesIntegration()
    return _glasses


__all__ = [
    "SCENE_TO_ROOMS",
    "MetaGlassesIntegration",
    "VisualContext",
    "get_meta_glasses",
]
