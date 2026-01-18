"""Voice Interface — Routes to Unified Voice Systems.

This module provides a minimal interface for the AmbientController.
All actual voice operations route through:
- kagami.core.effectors.voice.UnifiedVoiceEffector (TTS + spatial routing)
- kagami.core.voice.UnifiedVoicePipeline (STT)

ALWAYS uses ElevenLabs V3 for TTS.

Created: January 2026
Simplified: January 2026 (removed legacy model options)
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class VoiceState(str, Enum):
    """Voice interface state."""

    IDLE = "idle"
    LISTENING = "listening"
    SPEAKING = "speaking"


@dataclass
class SpeechRequest:
    """Request to synthesize and speak text."""

    text: str
    voice_id: str | None = None
    speed: float = 1.0
    priority: int = 0
    interruptible: bool = True


@dataclass
class UtteranceResult:
    """Result of a speech synthesis request."""

    success: bool
    duration_ms: float = 0.0
    audio_bytes: bytes | None = None
    error: str | None = None


@dataclass
class VoiceConfig:
    """Voice interface configuration."""

    enabled: bool = True
    wake_word: str = "kagami"
    wake_word_enabled: bool = True
    continuous_mode: bool = False
    enable_vision: bool = False
    voice_id: str | None = None
    language: str = "en"
    sample_rate: int = 16000


class VoiceInterface:
    """Voice interface adapter for ambient control.

    Routes all TTS operations to UnifiedVoiceEffector.
    Routes all STT operations to UnifiedVoicePipeline.
    """

    def __init__(self, config: VoiceConfig | None = None):
        self.config = config or VoiceConfig()
        self.state = VoiceState.IDLE
        self._callbacks: dict[str, list[Callable]] = {}
        self._effector = None
        self._initialized = False

    async def initialize(self) -> bool:
        """Initialize the voice interface."""
        if self._initialized:
            return True

        try:
            from kagami.core.effectors.voice import get_voice_effector

            self._effector = await get_voice_effector()
            self._initialized = True
            logger.info("✓ VoiceInterface initialized (routes to UnifiedVoiceEffector)")
            return True
        except Exception as e:
            logger.error(f"VoiceInterface init failed: {e}")
            return False

    async def speak(self, text: str, **kwargs: Any) -> UtteranceResult:
        """Speak text using V3 TTS.

        Args:
            text: Text to speak (can include V3 audio tags)
            **kwargs: Additional args passed to effector

        Returns:
            UtteranceResult
        """
        if not self._effector:
            return UtteranceResult(success=False, error="Not initialized")

        try:
            self.state = VoiceState.SPEAKING
            result = await self._effector.speak(text, **kwargs)
            self.state = VoiceState.IDLE

            return UtteranceResult(
                success=result.success,
                duration_ms=result.latency_ms,
                error=result.error,
            )
        except Exception as e:
            self.state = VoiceState.IDLE
            return UtteranceResult(success=False, error=str(e))

    def on_utterance(self, callback: Callable) -> None:
        """Register callback for voice input (STT)."""
        if "utterance" not in self._callbacks:
            self._callbacks["utterance"] = []
        self._callbacks["utterance"].append(callback)

    def on_wake_word(self, callback: Callable) -> None:
        """Register callback for wake word detection."""
        if "wake_word" not in self._callbacks:
            self._callbacks["wake_word"] = []
        self._callbacks["wake_word"].append(callback)

    async def start_listening(self) -> None:
        """Start listening for voice input."""
        self.state = VoiceState.LISTENING
        # STT handled by UnifiedVoicePipeline elsewhere

    async def stop_listening(self) -> None:
        """Stop listening for voice input."""
        self.state = VoiceState.IDLE

    async def start(self) -> None:
        """Start the voice interface."""
        await self.initialize()

    async def stop(self) -> None:
        """Stop the voice interface."""
        self.state = VoiceState.IDLE

    def set_breath_state(self, breath_state: Any) -> None:
        """Set breath state for voice modulation (stub)."""
        pass  # Voice rhythm modulation not implemented

    async def listen(self, timeout: float = 5.0) -> str | None:
        """Listen for voice input.

        Args:
            timeout: Listen timeout in seconds

        Returns:
            Transcribed text or None
        """
        # STT handled by UnifiedVoicePipeline
        return None

    async def capture_vision(self) -> dict[str, Any] | None:
        """Capture vision input (stub).

        Returns:
            Vision capture result or None
        """
        # Vision capture not implemented in VoiceInterface
        return None

    def get_stats(self) -> dict[str, Any]:
        """Get voice interface statistics."""
        return {
            "state": self.state.value,
            "initialized": self._initialized,
            "callbacks": {k: len(v) for k, v in self._callbacks.items()},
        }

    @property
    def is_speaking(self) -> bool:
        """Check if currently speaking."""
        return self.state == VoiceState.SPEAKING

    @property
    def is_listening(self) -> bool:
        """Check if currently listening."""
        return self.state == VoiceState.LISTENING

    async def process_voice_command(
        self,
        text: str,
        source: str = "unknown",
        room: str | None = None,
    ) -> dict[str, Any]:
        """Process a voice command through Kagami.

        Args:
            text: The command text
            source: Source of the command (e.g., "home_theater")
            room: Optional room context

        Returns:
            Response dict with "response" key
        """
        # Route to Kagami for actual processing
        try:
            from kagami.core.chat import chat  # pyright: ignore[reportMissingImports]

            response = await chat(text, context={"source": source, "room": room})
            return {"response": response, "success": True}
        except ImportError:
            logger.warning("Kagami chat not available, using echo")
            return {"response": f"I heard: {text}", "success": True}
        except Exception as e:
            logger.error(f"Command processing failed: {e}")
            return {"response": f"I heard: {text}", "success": True}


# Singleton
_voice_interface: VoiceInterface | None = None


async def get_voice_interface() -> VoiceInterface:
    """Get the singleton VoiceInterface."""
    global _voice_interface
    if _voice_interface is None:
        _voice_interface = VoiceInterface()
        await _voice_interface.initialize()
    return _voice_interface


__all__ = [
    "SpeechRequest",
    "UtteranceResult",
    "VoiceConfig",
    "VoiceInterface",
    "VoiceState",
    "get_voice_interface",
]
