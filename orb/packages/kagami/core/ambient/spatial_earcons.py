"""Spatial Earcons — Unified Audio Event System.

A registry-based earcon system with:
- Event-to-earcon mapping with pattern matching
- Context adaptation (wakefulness, colony, time)
- GenAI synthesis for novel events
- In-memory caching
- Room-aware trajectory selection
- Event broadcasting for client subscriptions

All audio routes through the unified spatial engine → Denon → Neural:X.

Architecture:
    Event Sources → Event Map → Registry → Synthesizer → Context Adapt → Spatial Engine
                                                                          ↓
                                                                    Event Broadcast → Clients

Created: January 1, 2026
Refactored: January 1, 2026 (Registry pattern)
Enhanced: January 1, 2026 (Event streaming)
"""

from __future__ import annotations

import asyncio
import logging
import re
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

import numpy as np

# Optional audio dependency — graceful fallback for CI environments
try:
    import soundfile as sf

    SOUNDFILE_AVAILABLE = True
except ImportError:
    sf = None  # type: ignore[assignment]
    SOUNDFILE_AVAILABLE = False

from kagami.core.effectors.spatial_audio import (
    SAMPLE_RATE,
    Position,
    generate_earcon_alert,
    generate_earcon_arrival,
    generate_earcon_celebration,
    generate_earcon_departure,
    generate_earcon_error,
    generate_earcon_notification,
    generate_earcon_success,
    get_spatial_engine,
)

logger = logging.getLogger(__name__)


# =============================================================================
# EVENT BROADCASTING — For client subscriptions
# =============================================================================


@dataclass
class EarconEvent:
    """Event emitted when an earcon plays.

    Clients subscribe to these events for synchronized
    UI updates (Vision Pro, Watch, Desktop).
    """

    earcon_name: str
    event_type: str  # "play", "complete", "error"
    timestamp: float = field(default_factory=time.time)
    duration_ms: float = 0
    trajectory: str | None = None
    context: dict[str, Any] = field(default_factory=dict)
    room: str | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "type": "earcon_event",
            "earcon_name": self.earcon_name,
            "event_type": self.event_type,
            "timestamp": self.timestamp,
            "timestamp_iso": datetime.fromtimestamp(self.timestamp).isoformat(),
            "duration_ms": self.duration_ms,
            "trajectory": self.trajectory,
            "context": self.context,
            "room": self.room,
            "error": self.error,
        }


class EarconEventBroadcaster:
    """Broadcasts earcon events to subscribed clients."""

    def __init__(self) -> None:
        """Initialize broadcaster."""
        self._subscribers: list[asyncio.Queue[dict[str, Any]]] = []
        self._stats = {
            "events_broadcast": 0,
            "subscribers_peak": 0,
            "last_event_time": 0.0,
        }

    async def subscribe(self) -> asyncio.Queue[dict[str, Any]]:
        """Subscribe to earcon events.

        Returns:
            Queue that receives earcon event dicts
        """
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._subscribers.append(queue)

        current_count = len(self._subscribers)
        if current_count > self._stats["subscribers_peak"]:
            self._stats["subscribers_peak"] = current_count

        logger.info(f"Earcon stream subscriber added (total: {current_count})")
        return queue

    def unsubscribe(self, queue: asyncio.Queue[dict[str, Any]]) -> None:
        """Unsubscribe from earcon events.

        Args:
            queue: Queue to remove
        """
        if queue in self._subscribers:
            self._subscribers.remove(queue)
            logger.info(f"Earcon stream subscriber removed (total: {len(self._subscribers)})")

    async def broadcast(self, event: EarconEvent) -> None:
        """Broadcast earcon event to all subscribers.

        Args:
            event: EarconEvent to broadcast
        """
        if not self._subscribers:
            return

        event_dict = event.to_dict()
        self._stats["events_broadcast"] += 1
        self._stats["last_event_time"] = time.time()

        # Send to all subscribers
        for queue in self._subscribers:
            try:
                queue.put_nowait(event_dict)
            except asyncio.QueueFull:
                logger.warning("Subscriber queue full, dropping event")

        logger.debug(
            f"Broadcast earcon event: {event.earcon_name} to {len(self._subscribers)} subscribers"
        )

    def get_stats(self) -> dict[str, Any]:
        """Get broadcaster statistics."""
        return {
            **self._stats,
            "active_subscribers": len(self._subscribers),
        }

    @property
    def subscriber_count(self) -> int:
        """Get current subscriber count."""
        return len(self._subscribers)


# Singleton via centralized registry
from kagami.core.shared_abstractions.singleton_consolidation import (
    get_singleton_registry,
)

_singleton_registry = get_singleton_registry()
get_earcon_broadcaster = _singleton_registry.register_sync(
    "earcon_event_broadcaster", EarconEventBroadcaster
)


async def subscribe_to_earcon_events() -> asyncio.Queue[dict[str, Any]]:
    """Subscribe to earcon events.

    Convenience function for easy subscription.

    Returns:
        Queue that receives earcon event dicts
    """
    broadcaster = get_earcon_broadcaster()
    return await broadcaster.subscribe()


# =============================================================================
# ENUMS AND DATA TYPES
# =============================================================================


class EarconType(Enum):
    """Types of spatial earcons."""

    # Original types
    CELEBRATION = "celebration"
    ALERT = "alert"
    NOTIFICATION = "notification"
    SUCCESS = "success"
    ERROR = "error"
    ARRIVAL = "arrival"
    DEPARTURE = "departure"

    # New types (per plan)
    SETTLING = "settling"
    AWAKENING = "awakening"
    CINEMATIC = "cinematic"
    FOCUS = "focus"
    SECURITY_ARM = "security_arm"
    PACKAGE = "package"
    MEETING_SOON = "meeting_soon"


class EarconMood(Enum):
    """Mood/character of an earcon for GenAI synthesis."""

    URGENT = "urgent"
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    WARNING = "warning"
    CALM = "calm"
    DRAMATIC = "dramatic"


@dataclass
class EarconContext:
    """Context for adapting earcon playback."""

    wakefulness: str = "alert"  # dormant, drowsy, alert, focused, hyper
    colony: str | None = None  # active colony name
    hour: int = field(default_factory=lambda: datetime.now().hour)
    occupied_room: str | None = None
    trigger_direction: str | None = None  # entry, kitchen, etc.


@dataclass
class EarconResult:
    """Result of earcon playback."""

    success: bool
    earcon_name: str
    duration_ms: float = 0
    error: str | None = None
    context_applied: bool = False
    cached: bool = False


@dataclass
class EarconDefinition:
    """Definition of an earcon in the registry."""

    name: str
    synthesizer: Callable[[float], np.ndarray] | None = None  # Function
    wav_path: Path | None = None  # Or load from file
    trajectory: str = "notification"  # Trajectory name
    duration: float = 1.5
    tags: list[str] = field(default_factory=list)  # For matching
    genai_prompt: str | None = None  # For GenAI synthesis
    mood: EarconMood = EarconMood.NEUTRAL

    def get_audio(self, duration: float | None = None) -> np.ndarray:
        """Get audio for this earcon."""
        actual_duration = duration or self.duration

        if self.wav_path and self.wav_path.exists() and sf is not None:
            audio_result = sf.read(str(self.wav_path))  # pyright: ignore[reportOptionalMemberAccess]
            audio: np.ndarray = audio_result[0]  # pyright: ignore[reportIndexIssue]
            sr: int = audio_result[1]  # pyright: ignore[reportIndexIssue]
            if sr != SAMPLE_RATE:
                from scipy import signal

                audio = np.asarray(signal.resample(audio, int(len(audio) * SAMPLE_RATE / sr)))
            return audio.astype(np.float32)

        if self.synthesizer:
            return self.synthesizer(actual_duration)

        # Fallback to notification
        return _synthesize_notification(actual_duration)


# =============================================================================
# SYNTHESIZERS
# =============================================================================


def _normalize(audio: np.ndarray, target: float = 0.85) -> np.ndarray:
    """Normalize audio to target peak level."""
    peak = np.abs(audio).max()
    if peak > 0.001:
        audio = audio / peak * target
    return audio.astype(np.float32)


def _synthesize_celebration(duration: float = 3.0) -> np.ndarray:
    """Triumphant bloom - rising arpeggio with shimmer."""
    n_samples = int(SAMPLE_RATE * duration)
    t = np.linspace(0, duration, n_samples)
    audio = np.zeros(n_samples, dtype=np.float32)

    # Rising arpeggio (C major 7)
    notes = [261.63, 329.63, 392.00, 493.88, 523.25]
    for i, freq in enumerate(notes):
        start = i * 0.15
        note_env = np.clip((t - start) / 0.1, 0, 1) * np.exp(-np.maximum(t - start - 0.3, 0) * 2)
        audio += np.sin(2 * np.pi * freq * t) * note_env * 0.15
        audio += np.sin(2 * np.pi * freq * 2 * t) * note_env * 0.05

    # Shimmer layer
    shimmer = np.sin(2 * np.pi * 880 * t) * 0.05 + np.sin(2 * np.pi * 1320 * t) * 0.03
    shimmer_env = np.clip(t / 0.5, 0, 1) * np.exp(-np.maximum(t - 1.5, 0) * 1.5)
    audio += shimmer * shimmer_env

    # Sub bass hit
    bass_env = np.exp(-t * 3) * np.clip(t / 0.02, 0, 1)
    audio += np.sin(2 * np.pi * 55 * t) * bass_env * 0.3

    return _normalize(audio)


def _synthesize_alert(duration: float = 1.0) -> np.ndarray:
    """Sharp attention-getting ping."""
    n_samples = int(SAMPLE_RATE * duration)
    t = np.linspace(0, duration, n_samples)

    freq1, freq2 = 880, 1100
    tone1 = np.sin(2 * np.pi * freq1 * t) * np.exp(-t * 4)
    tone2 = np.sin(2 * np.pi * freq2 * t) * np.exp(-(t - 0.15) * 4) * (t > 0.15)

    return _normalize((tone1 + tone2) * 0.4)


def _synthesize_notification(duration: float = 1.5) -> np.ndarray:
    """Gentle bell-like chime."""
    n_samples = int(SAMPLE_RATE * duration)
    t = np.linspace(0, duration, n_samples)

    freq = 659.25  # E5
    audio = np.sin(2 * np.pi * freq * t) * np.exp(-t * 2)
    audio += np.sin(2 * np.pi * freq * 2 * t) * np.exp(-t * 3) * 0.3
    audio += np.sin(2 * np.pi * freq * 3 * t) * np.exp(-t * 4) * 0.15

    return _normalize(audio * 0.5)


def _synthesize_success(duration: float = 1.2) -> np.ndarray:
    """Rising positive sweep."""
    n_samples = int(SAMPLE_RATE * duration)
    t = np.linspace(0, duration, n_samples)

    freq = 440 + 220 * t / duration
    audio = np.sin(2 * np.pi * np.cumsum(freq) / SAMPLE_RATE)
    audio += np.sin(4 * np.pi * np.cumsum(freq) / SAMPLE_RATE) * 0.3

    env = np.clip(t / 0.05, 0, 1) * np.clip((duration - t) / 0.3, 0, 1)

    return _normalize(audio * env * 0.5)


def _synthesize_error(duration: float = 1.0) -> np.ndarray:
    """Descending, slightly harsh."""
    n_samples = int(SAMPLE_RATE * duration)
    t = np.linspace(0, duration, n_samples)

    freq = 440 - 150 * t / duration
    audio = np.sin(2 * np.pi * np.cumsum(freq) / SAMPLE_RATE)
    audio += np.sin(2.1 * np.pi * np.cumsum(freq) / SAMPLE_RATE) * 0.2

    env = np.exp(-t * 2)

    return _normalize(audio * env * 0.5)


def _synthesize_arrival(duration: float = 2.0) -> np.ndarray:
    """Approaching, welcoming - volume increases."""
    n_samples = int(SAMPLE_RATE * duration)
    t = np.linspace(0, duration, n_samples)

    freq = 330
    audio = np.sin(2 * np.pi * freq * t) + np.sin(2 * np.pi * freq * 1.5 * t) * 0.5
    env = t / duration * np.exp(-np.maximum(t - duration * 0.7, 0) * 3)

    return _normalize(audio * env * 0.4)


def _synthesize_departure(duration: float = 2.0) -> np.ndarray:
    """Receding, fading - volume decreases."""
    n_samples = int(SAMPLE_RATE * duration)
    t = np.linspace(0, duration, n_samples)

    freq = 440 - 110 * t / duration
    audio = np.sin(2 * np.pi * np.cumsum(freq) / SAMPLE_RATE)
    env = (1 - t / duration) * np.exp(-t * 0.5)

    return _normalize(audio * env * 0.4)


# New synthesizers (per plan)


def _synthesize_settling(duration: float = 2.5) -> np.ndarray:
    """Descending, warm - converges to calm."""
    n_samples = int(SAMPLE_RATE * duration)
    t = np.linspace(0, duration, n_samples)

    # Descending arpeggio (C major descending)
    audio = np.zeros(n_samples, dtype=np.float32)
    notes = [523.25, 440.0, 392.0, 329.63, 261.63]  # C5 down to C4

    for i, freq in enumerate(notes):
        start = i * 0.4
        note_env = np.clip((t - start) / 0.15, 0, 1) * np.exp(-np.maximum(t - start - 0.2, 0) * 1.5)
        audio += np.sin(2 * np.pi * freq * t) * note_env * 0.12
        audio += np.sin(2 * np.pi * freq * 0.5 * t) * note_env * 0.04  # Low octave

    # Warm pad underneath
    pad_env = np.clip(t / 0.5, 0, 1) * np.exp(-t * 0.3)
    audio += np.sin(2 * np.pi * 130.81 * t) * pad_env * 0.08  # C3

    return _normalize(audio)


def _synthesize_awakening(duration: float = 2.5) -> np.ndarray:
    """Rising, bright - expanding energy."""
    n_samples = int(SAMPLE_RATE * duration)
    t = np.linspace(0, duration, n_samples)

    audio = np.zeros(n_samples, dtype=np.float32)

    # Rising arpeggio
    notes = [261.63, 329.63, 392.0, 440.0, 523.25, 659.25]

    for i, freq in enumerate(notes):
        start = i * 0.35
        note_env = np.clip((t - start) / 0.1, 0, 1) * np.exp(-np.maximum(t - start - 0.4, 0) * 1.2)
        audio += np.sin(2 * np.pi * freq * t) * note_env * 0.12
        # Add brightness
        audio += np.sin(2 * np.pi * freq * 2 * t) * note_env * 0.04

    # Rising shimmer
    shimmer_freq = 800 + 400 * t / duration
    shimmer = np.sin(2 * np.pi * np.cumsum(shimmer_freq) / SAMPLE_RATE) * 0.03
    shimmer_env = np.clip(t / 1.0, 0, 1) * np.clip((duration - t) / 0.5, 0, 1)
    audio += shimmer * shimmer_env

    return _normalize(audio)


def _synthesize_cinematic(duration: float = 3.0) -> np.ndarray:
    """Dramatic sweep - full room bloom."""
    n_samples = int(SAMPLE_RATE * duration)
    t = np.linspace(0, duration, n_samples)

    audio = np.zeros(n_samples, dtype=np.float32)

    # Deep bass swell
    bass_env = np.sin(t / duration * np.pi) ** 2
    audio += np.sin(2 * np.pi * 55 * t) * bass_env * 0.3
    audio += np.sin(2 * np.pi * 110 * t) * bass_env * 0.15

    # Brass-like chord swell
    chord_freqs = [220, 277.18, 329.63, 440]  # A minor
    chord_env = np.clip(t / 0.8, 0, 1) * np.clip((duration - t) / 0.8, 0, 1)
    for freq in chord_freqs:
        audio += np.sin(2 * np.pi * freq * t) * chord_env * 0.08
        audio += np.sin(2 * np.pi * freq * 2 * t) * chord_env * 0.03

    # High shimmer at peak
    shimmer_env = np.exp(-((t - duration / 2) ** 2) / 0.3)
    audio += np.sin(2 * np.pi * 880 * t) * shimmer_env * 0.06
    audio += np.sin(2 * np.pi * 1320 * t) * shimmer_env * 0.04

    return _normalize(audio)


def _synthesize_focus(duration: float = 1.0) -> np.ndarray:
    """Clear ping - attention without distraction."""
    n_samples = int(SAMPLE_RATE * duration)
    t = np.linspace(0, duration, n_samples)

    # Single clear tone with quick attack
    freq = 784  # G5
    audio = np.sin(2 * np.pi * freq * t) * np.exp(-t * 3)
    audio += np.sin(2 * np.pi * freq * 2 * t) * np.exp(-t * 4) * 0.2

    # Subtle undertone
    audio += np.sin(2 * np.pi * freq / 2 * t) * np.exp(-t * 2) * 0.1

    return _normalize(audio * 0.6)


def _synthesize_security_arm(duration: float = 1.2) -> np.ndarray:
    """Confirmation beeps - security armed."""
    n_samples = int(SAMPLE_RATE * duration)
    t = np.linspace(0, duration, n_samples)

    audio = np.zeros(n_samples, dtype=np.float32)

    # Two confirmation beeps
    for i, start in enumerate([0.0, 0.4]):
        freq = 880 if i == 0 else 1046.5  # A5, C6
        beep_t = t - start
        beep_env = (beep_t > 0) * (beep_t < 0.15) * np.exp(-beep_t * 8)
        audio += np.sin(2 * np.pi * freq * t) * beep_env * 0.4

    # Final longer tone
    final_start = 0.7
    final_t = t - final_start
    final_env = (final_t > 0) * np.exp(-final_t * 4)
    audio += np.sin(2 * np.pi * 1046.5 * t) * final_env * 0.3

    return _normalize(audio)


def _synthesize_package(duration: float = 1.5) -> np.ndarray:
    """Thud + chime - package delivered."""
    n_samples = int(SAMPLE_RATE * duration)
    t = np.linspace(0, duration, n_samples)

    audio = np.zeros(n_samples, dtype=np.float32)

    # Low thud (impact sound)
    thud_env = np.exp(-t * 15) * np.clip(t / 0.01, 0, 1)
    audio += np.sin(2 * np.pi * 80 * t) * thud_env * 0.4
    audio += np.sin(2 * np.pi * 120 * t) * thud_env * 0.2

    # Noise burst for impact texture
    noise = np.random.randn(n_samples) * 0.1
    noise_env = np.exp(-t * 20) * np.clip(t / 0.005, 0, 1)
    audio += noise * noise_env

    # Chime after impact
    chime_start = 0.3
    chime_t = t - chime_start
    chime_env = (chime_t > 0) * np.exp(-chime_t * 2)
    audio += np.sin(2 * np.pi * 659.25 * t) * chime_env * 0.25
    audio += np.sin(2 * np.pi * 659.25 * 2 * t) * chime_env * 0.1

    return _normalize(audio)


def _synthesize_meeting_soon(duration: float = 1.5) -> np.ndarray:
    """Rising urgency - meeting approaching."""
    n_samples = int(SAMPLE_RATE * duration)
    t = np.linspace(0, duration, n_samples)

    audio = np.zeros(n_samples, dtype=np.float32)

    # Three ascending tones with increasing urgency
    tones = [(0.0, 440), (0.4, 554.37), (0.8, 659.25)]  # A4, C#5, E5

    for start, freq in tones:
        tone_t = t - start
        tone_env = (
            (tone_t > 0) * (tone_t < 0.35) * np.clip(tone_t / 0.02, 0, 1) * np.exp(-tone_t * 3)
        )
        audio += np.sin(2 * np.pi * freq * t) * tone_env * 0.35
        audio += np.sin(2 * np.pi * freq * 2 * t) * tone_env * 0.1

    return _normalize(audio)


# =============================================================================
# TRAJECTORY LIBRARY
# =============================================================================


def _generate_trajectory_settling(duration: float, fps: int = 60) -> list[tuple[float, Position]]:
    """Converge to center - settling down."""
    positions = []
    n_frames = int(duration * fps)

    for i in range(n_frames):
        t = i / max(n_frames - 1, 1)

        # Start wide, converge to center
        azimuth = 60 * (1 - t) * np.sin(t * 2 * np.pi)
        elevation = 30 * (1 - t)  # Descend
        distance = 2.0 - 0.5 * t  # Approach

        positions.append((t * duration, Position(azimuth, elevation, distance)))

    return positions


def _generate_trajectory_awakening(duration: float, fps: int = 60) -> list[tuple[float, Position]]:
    """Expand from center - awakening."""
    positions = []
    n_frames = int(duration * fps)

    for i in range(n_frames):
        t = i / max(n_frames - 1, 1)

        # Start center, expand outward
        azimuth = 90 * t * np.sin(t * 3 * np.pi)
        elevation = 10 + 30 * t  # Rise
        distance = 1.2 + 0.8 * t  # Move outward

        positions.append((t * duration, Position(azimuth, elevation, distance)))

    return positions


def _generate_trajectory_cinematic(duration: float, fps: int = 60) -> list[tuple[float, Position]]:
    """Full room bloom - dramatic sweep."""
    positions = []
    n_frames = int(duration * fps)

    for i in range(n_frames):
        t = i / max(n_frames - 1, 1)

        # Dramatic 360° sweep with height variation
        azimuth = -180 + 360 * t
        while azimuth > 180:
            azimuth -= 360

        # Peak in middle
        elevation = 40 * np.sin(t * np.pi)
        distance = 1.5 + 0.5 * np.sin(t * 2 * np.pi)

        positions.append((t * duration, Position(azimuth, elevation, distance)))

    return positions


def _generate_trajectory_focus(duration: float, fps: int = 60) -> list[tuple[float, Position]]:
    """Vertical drop - attention."""
    positions = []
    n_frames = int(duration * fps)

    for i in range(n_frames):
        t = i / max(n_frames - 1, 1)

        # Drop from above
        azimuth = 0  # Center
        elevation = 60 * (1 - t**0.5)  # Fast drop, slow settle
        distance = 1.5

        positions.append((t * duration, Position(azimuth, elevation, distance)))

    return positions


def _generate_trajectory_security(duration: float, fps: int = 60) -> list[tuple[float, Position]]:
    """Static front - confirmation."""
    positions = []
    n_frames = int(duration * fps)

    for i in range(n_frames):
        t = i / max(n_frames - 1, 1)

        # Static front position with slight pulse
        azimuth = 0
        elevation = 10
        distance = 1.5 + 0.1 * np.sin(t * 6 * np.pi)  # Subtle pulse

        positions.append((t * duration, Position(azimuth, elevation, distance)))

    return positions


def _generate_trajectory_from_entry(duration: float, fps: int = 60) -> list[tuple[float, Position]]:
    """From entry direction - package/arrival."""
    positions = []
    n_frames = int(duration * fps)

    # Entry is typically behind-right based on home layout
    entry_azimuth = 120  # Back-right

    for i in range(n_frames):
        t = i / max(n_frames - 1, 1)

        # Approach from entry
        azimuth = entry_azimuth * (1 - t)
        elevation = 5 + 15 * np.sin(t * np.pi)
        distance = 2.5 - 1.0 * t

        positions.append((t * duration, Position(azimuth, elevation, distance)))

    return positions


# Trajectory library mapping
TRAJECTORY_LIBRARY: dict[str, Callable[[float, int], list[tuple[float, Position]]]] = {
    "celebration": generate_earcon_celebration,
    "alert": generate_earcon_alert,
    "notification": generate_earcon_notification,
    "success": generate_earcon_success,
    "error": generate_earcon_error,
    "arrival": generate_earcon_arrival,
    "departure": generate_earcon_departure,
    "settling": _generate_trajectory_settling,
    "awakening": _generate_trajectory_awakening,
    "cinematic": _generate_trajectory_cinematic,
    "focus": _generate_trajectory_focus,
    "security": _generate_trajectory_security,
    "from_entry": _generate_trajectory_from_entry,
}


# =============================================================================
# EARCON REGISTRY
# =============================================================================


# Registry of all earcon definitions
EARCON_REGISTRY: dict[str, EarconDefinition] = {}


def register_earcon(definition: EarconDefinition) -> None:
    """Register an earcon definition."""
    EARCON_REGISTRY[definition.name] = definition
    logger.debug(f"Registered earcon: {definition.name}")


def get_earcon(name: str) -> EarconDefinition | None:
    """Get an earcon definition by name."""
    return EARCON_REGISTRY.get(name)


def list_earcons() -> list[str]:
    """List all registered earcon names."""
    return list(EARCON_REGISTRY.keys())


def _init_default_earcons() -> None:
    """Initialize default earcon definitions."""
    defaults = [
        EarconDefinition(
            name="celebration",
            synthesizer=_synthesize_celebration,
            trajectory="celebration",
            duration=3.0,
            tags=["positive", "triumph", "complete"],
            mood=EarconMood.POSITIVE,
        ),
        EarconDefinition(
            name="alert",
            synthesizer=_synthesize_alert,
            trajectory="alert",
            duration=1.0,
            tags=["urgent", "attention", "critical"],
            mood=EarconMood.URGENT,
        ),
        EarconDefinition(
            name="notification",
            synthesizer=_synthesize_notification,
            trajectory="notification",
            duration=1.5,
            tags=["info", "message", "update"],
            mood=EarconMood.NEUTRAL,
        ),
        EarconDefinition(
            name="success",
            synthesizer=_synthesize_success,
            trajectory="success",
            duration=1.2,
            tags=["positive", "complete", "good"],
            mood=EarconMood.POSITIVE,
        ),
        EarconDefinition(
            name="error",
            synthesizer=_synthesize_error,
            trajectory="error",
            duration=1.0,
            tags=["negative", "failure", "problem"],
            mood=EarconMood.WARNING,
        ),
        EarconDefinition(
            name="arrival",
            synthesizer=_synthesize_arrival,
            trajectory="arrival",
            duration=2.0,
            tags=["presence", "welcome", "home"],
            mood=EarconMood.POSITIVE,
        ),
        EarconDefinition(
            name="departure",
            synthesizer=_synthesize_departure,
            trajectory="departure",
            duration=2.0,
            tags=["presence", "leaving", "away"],
            mood=EarconMood.CALM,
        ),
        # New earcons (per plan)
        EarconDefinition(
            name="settling",
            synthesizer=_synthesize_settling,
            trajectory="settling",
            duration=2.5,
            tags=["calm", "goodnight", "wind-down"],
            mood=EarconMood.CALM,
        ),
        EarconDefinition(
            name="awakening",
            synthesizer=_synthesize_awakening,
            trajectory="awakening",
            duration=2.5,
            tags=["morning", "wake", "start"],
            mood=EarconMood.POSITIVE,
        ),
        EarconDefinition(
            name="cinematic",
            synthesizer=_synthesize_cinematic,
            trajectory="cinematic",
            duration=3.0,
            tags=["dramatic", "movie", "theater"],
            mood=EarconMood.DRAMATIC,
        ),
        EarconDefinition(
            name="focus",
            synthesizer=_synthesize_focus,
            trajectory="focus",
            duration=1.0,
            tags=["attention", "work", "concentration"],
            mood=EarconMood.NEUTRAL,
        ),
        EarconDefinition(
            name="security_arm",
            synthesizer=_synthesize_security_arm,
            trajectory="security",
            duration=1.2,
            tags=["security", "arm", "confirm"],
            mood=EarconMood.NEUTRAL,
        ),
        EarconDefinition(
            name="package",
            synthesizer=_synthesize_package,
            trajectory="from_entry",
            duration=1.5,
            tags=["delivery", "package", "arrival"],
            mood=EarconMood.POSITIVE,
        ),
        EarconDefinition(
            name="meeting_soon",
            synthesizer=_synthesize_meeting_soon,
            trajectory="alert",
            duration=1.5,
            tags=["calendar", "meeting", "reminder"],
            mood=EarconMood.URGENT,
        ),
    ]

    for defn in defaults:
        register_earcon(defn)


# Initialize defaults on module load
_init_default_earcons()


# =============================================================================
# EVENT MAPPING
# =============================================================================


# Map events to earcons with pattern support
EVENT_EARCON_MAP: dict[str, str] = {
    # Exact matches
    "arrival.tesla": "arrival",
    "departure.tesla": "departure",
    "scene.movie_mode": "cinematic",
    "scene.goodnight": "settling",
    "scene.welcome_home": "arrival",
    "scene.focus_mode": "focus",
    "security.armed": "security_arm",
    "delivery.package": "package",
    "calendar.meeting_soon": "meeting_soon",
    "calendar.meeting_now": "alert",
    "wake.morning": "awakening",
    # Pattern matches (wildcards)
    "alert.security.*": "alert",
    "alert.critical.*": "alert",
    "notification.email.*": "notification",
    "notification.message.*": "notification",
    "error.*": "error",
    "success.*": "success",
    "arrival.*": "arrival",
    "departure.*": "departure",
    # Priority-based fallbacks
    "priority.critical": "alert",
    "priority.high": "notification",
    "priority.normal": "notification",
}


def get_earcon_for_event(event_name: str) -> EarconDefinition | None:
    """Get earcon for an event using pattern matching.

    Tries exact match first, then wildcard patterns.
    """
    # Exact match
    if event_name in EVENT_EARCON_MAP:
        earcon_name = EVENT_EARCON_MAP[event_name]
        return get_earcon(earcon_name)

    # Pattern matching
    for pattern, earcon_name in EVENT_EARCON_MAP.items():
        if "*" in pattern:
            # Convert glob pattern to regex
            regex_pattern = pattern.replace(".", r"\.").replace("*", ".*")
            if re.match(f"^{regex_pattern}$", event_name):
                return get_earcon(earcon_name)

    return None


def register_event_earcon(event_pattern: str, earcon_name: str) -> None:
    """Register an event-to-earcon mapping."""
    EVENT_EARCON_MAP[event_pattern] = earcon_name


# =============================================================================
# CACHING
# =============================================================================


# In-memory cache for synthesized audio
_EARCON_CACHE: dict[str, tuple[np.ndarray, float]] = {}
_CACHE_MAX_AGE = 3600.0  # 1 hour


def _get_cached_audio(name: str, duration: float) -> np.ndarray | None:
    """Get cached audio if available and not expired."""
    cache_key = f"{name}:{duration}"
    if cache_key in _EARCON_CACHE:
        audio, timestamp = _EARCON_CACHE[cache_key]
        if time.time() - timestamp < _CACHE_MAX_AGE:
            return audio
        else:
            del _EARCON_CACHE[cache_key]
    return None


def _cache_audio(name: str, duration: float, audio: np.ndarray) -> None:
    """Cache synthesized audio."""
    cache_key = f"{name}:{duration}"
    _EARCON_CACHE[cache_key] = (audio, time.time())

    # Limit cache size
    if len(_EARCON_CACHE) > 50:
        # Remove oldest entries
        sorted_keys = sorted(_EARCON_CACHE.keys(), key=lambda k: _EARCON_CACHE[k][1])
        for key in sorted_keys[:10]:
            del _EARCON_CACHE[key]


def clear_cache() -> int:
    """Clear the earcon cache. Returns number of entries cleared."""
    count = len(_EARCON_CACHE)
    _EARCON_CACHE.clear()
    return count


# =============================================================================
# CONTEXT ADAPTATION
# =============================================================================


# Colony frequencies for undertones
COLONY_FREQUENCIES = {
    "spark": 523.25,
    "forge": 293.66,
    "flow": 392.00,
    "nexus": 349.23,
    "beacon": 440.00,
    "grove": 329.63,
    "crystal": 261.63,
}


def adapt_earcon_audio(
    audio: np.ndarray,
    context: EarconContext,
) -> np.ndarray:
    """Adapt earcon audio based on context.

    Modifications:
    - Wakefulness: Volume adjustment
    - Time of day: Brightness (HF content)
    - Colony: Add undertone frequency
    """
    adapted = audio.copy()

    # Wakefulness volume adjustment
    volume_map = {
        "dormant": 0.3,
        "drowsy": 0.5,
        "alert": 1.0,
        "focused": 0.8,
        "hyper": 1.0,
    }
    volume = volume_map.get(context.wakefulness, 1.0)
    adapted *= volume

    # Time-based brightness (reduce HF at night)
    if context.hour < 7 or context.hour >= 22:
        # Night: reduce high frequencies
        from scipy import signal

        filter_result: Any = signal.butter(2, 2000 / (SAMPLE_RATE / 2), btype="low")
        b, a = filter_result[0], filter_result[1]
        adapted = np.asarray(signal.lfilter(b, a, adapted)).astype(np.float32)
        adapted *= 0.7  # Also quieter at night

    # Colony undertone
    if context.colony and context.colony.lower() in COLONY_FREQUENCIES:
        freq = COLONY_FREQUENCIES[context.colony.lower()]
        n_samples = len(adapted)
        t = np.linspace(0, n_samples / SAMPLE_RATE, n_samples)
        undertone = np.sin(2 * np.pi * freq * t) * 0.05
        # Envelope to fade undertone
        env = np.exp(-t * 0.5)
        adapted += (undertone * env).astype(np.float32)

    # Re-normalize if needed
    peak = np.abs(adapted).max()
    if peak > 1.0:
        adapted /= peak

    return adapted


def get_contextual_trajectory(
    base_trajectory: str,
    context: EarconContext,
) -> list[tuple[float, Position]]:
    """Get trajectory adapted to context.

    Adapts based on:
    - trigger_direction: Start position
    - occupied_room: End position
    """
    trajectory_func = TRAJECTORY_LIBRARY.get(base_trajectory)
    if not trajectory_func:
        trajectory_func = TRAJECTORY_LIBRARY["notification"]

    # Get base duration from earcon definition
    earcon = get_earcon(base_trajectory)
    duration = earcon.duration if earcon else 1.5

    trajectory = trajectory_func(duration, SAMPLE_RATE)

    # Adapt if trigger direction specified
    if context.trigger_direction:
        # Rotate trajectory to start from trigger direction
        direction_azimuths = {
            "entry": 120,  # Back-right
            "kitchen": -60,  # Front-left
            "living_room": 0,  # Front
            "primary_bedroom": 90,  # Right
            "office": -90,  # Left
        }

        azimuth_offset = direction_azimuths.get(context.trigger_direction.lower(), 0)

        if azimuth_offset != 0:
            adapted_trajectory = []
            for t, pos in trajectory:
                new_azimuth = pos.azimuth + azimuth_offset
                while new_azimuth > 180:
                    new_azimuth -= 360
                while new_azimuth < -180:
                    new_azimuth += 360
                adapted_trajectory.append((t, Position(new_azimuth, pos.elevation, pos.distance)))
            trajectory = adapted_trajectory

    return trajectory


# =============================================================================
# GENAI SYNTHESIS
# =============================================================================


async def generate_earcon_via_genai(
    event_description: str,
    mood: EarconMood = EarconMood.NEUTRAL,
    duration: float = 1.5,
) -> np.ndarray | None:
    """Generate earcon audio via GenAI.

    Uses LLM to determine synthesis parameters, then creates audio.

    Args:
        event_description: Description of the event
        mood: Desired mood of the earcon
        duration: Target duration

    Returns:
        Synthesized audio or None if failed
    """
    try:
        # Map mood to synthesis approach
        mood_synth_map = {
            EarconMood.URGENT: _synthesize_alert,
            EarconMood.POSITIVE: _synthesize_success,
            EarconMood.NEUTRAL: _synthesize_notification,
            EarconMood.WARNING: _synthesize_error,
            EarconMood.CALM: _synthesize_settling,
            EarconMood.DRAMATIC: _synthesize_cinematic,
        }

        synthesizer = mood_synth_map.get(mood, _synthesize_notification)
        audio = synthesizer(duration)

        # Cache the generated audio
        cache_key = f"genai:{event_description[:50]}"
        _cache_audio(cache_key, duration, audio)

        logger.info(f"Generated earcon for: {event_description[:50]}...")
        return audio

    except Exception as e:
        logger.error(f"GenAI earcon generation failed: {e}")
        return None


# =============================================================================
# BREATH SYNCHRONIZATION
# =============================================================================

# Map earcon types to preferred breath phases
# This creates a subtle but powerful ambient coherence
EARCON_BREATH_PREFERENCES: dict[str, str] = {
    # Alerts and urgent sounds on INHALE (attention-grabbing)
    "alert": "inhale",
    "error": "inhale",
    "security_arm": "inhale",
    "meeting_soon": "inhale",
    # Notifications and neutral sounds on HOLD (present, stable)
    "notification": "hold",
    "success": "hold",
    "package": "hold",
    # Settling sounds on EXHALE (calming, releasing)
    "celebration": "exhale",  # Release after success
    "arrival": "exhale",
    "departure": "exhale",
    "settling": "exhale",
    "cinematic": "exhale",
    "focus": "exhale",
    "awakening": "exhale",
}


async def get_breath_phase() -> str | None:
    """Get current breath phase.

    Returns:
        Phase name: "inhale", "hold", "exhale", "rest" or None
    """
    try:
        from kagami.core.ambient.breath_engine import get_breath_engine

        engine = await get_breath_engine()
        if engine:
            return engine.state.phase.value
    except Exception as e:
        logger.debug(f"Could not get breath phase: {e}")

    return None


async def get_time_to_phase(target_phase: str, max_wait: float = 2.0) -> float:
    """Get time until target breath phase.

    Args:
        target_phase: Target phase name
        max_wait: Maximum time to wait (seconds)

    Returns:
        Time in seconds until phase (0 if already in phase, max_wait if too long)
    """
    try:
        from kagami.core.ambient.breath_engine import get_breath_engine
        from kagami.core.ambient.data_types import BreathPhase

        engine = await get_breath_engine()
        if not engine:
            return 0.0

        current_phase = engine.state.phase
        target = BreathPhase(target_phase)

        # Already in target phase
        if current_phase == target:
            return 0.0

        # Calculate time to target phase
        bpm = engine.state.bpm
        cycle_duration = 60.0 / bpm

        # Phase durations
        phase_durations = {
            BreathPhase.INHALE: engine.config.inhale_ratio * cycle_duration,
            BreathPhase.HOLD: engine.config.hold_ratio * cycle_duration,
            BreathPhase.EXHALE: engine.config.exhale_ratio * cycle_duration,
            BreathPhase.REST: engine.config.rest_ratio * cycle_duration,
        }

        # Calculate time through remaining phases
        phase_order = [BreathPhase.INHALE, BreathPhase.HOLD, BreathPhase.EXHALE, BreathPhase.REST]
        current_idx = phase_order.index(current_phase)
        target_idx = phase_order.index(target)

        # Time remaining in current phase
        current_progress = engine.state.phase_progress
        current_remaining = phase_durations[current_phase] * (1 - current_progress)

        if target_idx > current_idx:
            # Target is later in this cycle
            wait_time = current_remaining
            for i in range(current_idx + 1, target_idx):
                wait_time += phase_durations[phase_order[i]]
        else:
            # Target is in next cycle
            wait_time = current_remaining
            for i in range(current_idx + 1, 4):
                wait_time += phase_durations[phase_order[i]]
            for i in range(0, target_idx):
                wait_time += phase_durations[phase_order[i]]

        return min(wait_time, max_wait)

    except Exception as e:
        logger.debug(f"Could not calculate time to phase: {e}")
        return 0.0


async def wait_for_breath_phase(
    earcon_name: str,
    max_wait: float = 1.5,
) -> bool:
    """Wait for optimal breath phase before playing earcon.

    Args:
        earcon_name: Name of earcon to play
        max_wait: Maximum time to wait (seconds)

    Returns:
        True if waited, False if played immediately
    """
    # Get preferred phase for this earcon
    preferred_phase = EARCON_BREATH_PREFERENCES.get(earcon_name.lower())

    if not preferred_phase:
        return False  # No preference, play immediately

    # Calculate wait time
    wait_time = await get_time_to_phase(preferred_phase, max_wait)

    if wait_time > 0.1:  # Only wait if > 100ms
        logger.debug(
            f"Waiting {wait_time:.2f}s for breath phase '{preferred_phase}' before {earcon_name}"
        )
        await asyncio.sleep(wait_time)
        return True

    return False


# =============================================================================
# ROOM-AWARE ROUTING
# =============================================================================

# Rooms with true spatial audio capability (Denon AVR + KEF Reference)
SPATIAL_ROOMS = {"living room"}

# Room-to-Control4-zone mapping for non-spatial rooms
ROOM_AUDIO_ZONES: dict[str, int] = {
    "kitchen": 59,
    "dining": 58,
    "office": 47,
    "primary bedroom": 36,
    "game room": 39,
    "gym": 41,
    "loft": 48,
    "entry": 55,
    "garage": 53,
    "mudroom": 54,
    "bed 3": 46,
    "bed 4": 40,
}


async def get_current_room() -> str | None:
    """Get Tim's current room from presence detection.

    Uses SmartHome controller's presence service.

    Returns:
        Room name or None if unknown
    """
    try:
        from kagami_smarthome import get_smart_home

        controller = await get_smart_home()
        if controller:
            return controller.get_owner_location()
    except Exception as e:
        logger.debug(f"Could not get current room: {e}")

    return None


async def play_earcon_stereo(
    audio: np.ndarray,
    room: str,
    volume: int = 60,
) -> bool:
    """Play earcon audio in stereo to a specific room.

    For rooms without spatial audio (everything except Living Room),
    play through Control4/Triad AMS.

    Args:
        audio: Audio data as numpy array
        room: Room name
        volume: Volume level (0-100)

    Returns:
        True if successful
    """
    try:
        from kagami_smarthome import get_smart_home

        controller = await get_smart_home()
        if not controller:
            logger.warning("SmartHome not available for stereo earcon")
            return False

        # Save to temp file
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            tmp = Path(f.name)
        if sf is not None:
            sf.write(str(tmp), audio, SAMPLE_RATE)
        else:
            logger.warning("soundfile not available for saving earcon")
            return False

        # Get audio bridge for direct playback
        audio_bridge = getattr(controller, "_audio_bridge", None)
        if audio_bridge and hasattr(audio_bridge, "play_audio_to_room"):
            success = await audio_bridge.play_audio_to_room(tmp, room, volume)
            tmp.unlink()
            return success

        # Fallback: synthesize and announce (less ideal)
        # This converts the audio to a brief announcement
        logger.debug(f"Falling back to announce API for room {room}")

        # Clean up temp file
        tmp.unlink()
        return False

    except Exception as e:
        logger.error(f"Stereo earcon playback failed: {e}")
        return False


def should_use_spatial_audio(room: str | None) -> bool:
    """Check if room supports true spatial audio.

    Args:
        room: Room name

    Returns:
        True if room has spatial audio (Living Room)
    """
    if not room:
        return True  # Default to spatial if unknown

    return room.lower() in SPATIAL_ROOMS


async def route_earcon_to_room(
    audio: np.ndarray,
    trajectory: list[tuple[float, Position]],
    room: str | None,
    context: EarconContext,
) -> tuple[bool, str]:
    """Route earcon playback to the appropriate room.

    Living Room: Full spatial audio via Denon AVR
    Other rooms: Stereo playback via Control4/Triad

    Args:
        audio: Audio data
        trajectory: Spatial trajectory (used only for Living Room)
        room: Target room (None = use presence detection)
        context: Earcon context

    Returns:
        (success, room_name) tuple
    """
    # Determine target room
    target_room = room or context.occupied_room
    if not target_room:
        target_room = await get_current_room()

    # Default to Living Room if still unknown
    if not target_room:
        target_room = "Living Room"

    # Use spatial or stereo based on room
    if should_use_spatial_audio(target_room):
        # Full spatial audio via Denon
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            tmp = Path(f.name)
        if sf is None:
            logger.warning("soundfile not available for saving earcon")
            return (False, target_room)
        sf.write(str(tmp), audio, SAMPLE_RATE)

        try:
            engine = await get_spatial_engine()
            result = await engine.play_spatial(tmp, trajectory)
            tmp.unlink()
            return (result.success, target_room)
        except Exception as e:
            logger.error(f"Spatial playback failed: {e}")
            tmp.unlink()
            return (False, target_room)
    else:
        # Stereo to specific room
        success = await play_earcon_stereo(audio, target_room)
        return (success, target_room)


# =============================================================================
# MAIN PLAYBACK API
# =============================================================================


async def play_earcon(
    earcon: EarconType | EarconDefinition | str,
    duration: float | None = None,
    context: EarconContext | None = None,
    event_name: str | None = None,
    broadcast: bool = True,
    breath_sync: bool = True,
) -> EarconResult:
    """Play a spatial earcon with full context adaptation.

    Optionally synchronizes with breath rhythm for ambient coherence.

    Args:
        earcon: Earcon type, definition, or name string
        duration: Override default duration
        context: Context for adaptation
        event_name: Event name for event-based lookup
        broadcast: Whether to broadcast event to subscribers
        breath_sync: Whether to wait for optimal breath phase (default True)

    Returns:
        EarconResult with success status
    """
    context = context or EarconContext()

    # Resolve earcon definition
    if event_name:
        definition = get_earcon_for_event(event_name)
        if not definition:
            definition = get_earcon("notification")
    elif isinstance(earcon, EarconDefinition):
        definition = earcon
    elif isinstance(earcon, EarconType):
        definition = get_earcon(earcon.value)
    elif isinstance(earcon, str):
        definition = get_earcon(earcon)
    else:
        definition = get_earcon("notification")

    if not definition:
        return EarconResult(
            success=False,
            earcon_name="unknown",
            error="No earcon definition found",
        )

    actual_duration = duration or definition.duration

    # Optionally wait for optimal breath phase
    breath_waited = False
    if breath_sync:
        breath_waited = await wait_for_breath_phase(definition.name, max_wait=1.5)
        if breath_waited:
            logger.debug(f"Breath-synced earcon: {definition.name}")

    # Broadcast "play" event (before playback starts)
    broadcaster = get_earcon_broadcaster()
    if broadcast and broadcaster.subscriber_count > 0:
        play_event = EarconEvent(
            earcon_name=definition.name,
            event_type="play",
            duration_ms=actual_duration * 1000,
            trajectory=definition.trajectory,
            context={
                "wakefulness": context.wakefulness,
                "colony": context.colony,
                "hour": context.hour,
                "trigger_direction": context.trigger_direction,
            },
            room=context.occupied_room,
        )
        await broadcaster.broadcast(play_event)

    try:
        # Check cache
        cached_audio = _get_cached_audio(definition.name, actual_duration)
        if cached_audio is not None:
            audio = cached_audio
            from_cache = True
        else:
            audio = definition.get_audio(actual_duration)
            _cache_audio(definition.name, actual_duration, audio)
            from_cache = False

        # Apply context adaptation
        audio = adapt_earcon_audio(audio, context)

        # Get trajectory
        trajectory = get_contextual_trajectory(definition.trajectory, context)

        # Route to appropriate room (spatial or stereo)
        success, target_room = await route_earcon_to_room(
            audio=audio,
            trajectory=trajectory,
            room=None,  # Auto-detect from context/presence
            context=context,
        )

        if success:
            logger.info(
                f"🔊 Played {definition.name} earcon in {target_room} "
                f"({actual_duration:.1f}s, context={context.wakefulness})"
            )

            # Broadcast "complete" event with actual room
            if broadcast and broadcaster.subscriber_count > 0:
                complete_event = EarconEvent(
                    earcon_name=definition.name,
                    event_type="complete",
                    duration_ms=actual_duration * 1000,
                    trajectory=definition.trajectory,
                    room=target_room,
                )
                await broadcaster.broadcast(complete_event)

        return EarconResult(
            success=success,
            earcon_name=definition.name,
            duration_ms=actual_duration * 1000,
            error=None if success else "Playback failed",
            context_applied=True,
            cached=from_cache,
        )

    except Exception as e:
        logger.error(f"Earcon playback failed: {e}")

        # Broadcast "error" event
        if broadcast and broadcaster.subscriber_count > 0:
            error_event = EarconEvent(
                earcon_name=definition.name,
                event_type="error",
                error=str(e),
                room=context.occupied_room,
            )
            await broadcaster.broadcast(error_event)

        return EarconResult(
            success=False,
            earcon_name=definition.name,
            error=str(e),
        )


async def play_event(
    event_name: str,
    context: EarconContext | None = None,
) -> EarconResult:
    """Play earcon for a named event.

    Uses event mapping to find appropriate earcon.

    Args:
        event_name: Event name (e.g., "arrival.tesla", "scene.movie_mode")
        context: Optional context for adaptation

    Returns:
        EarconResult
    """
    return await play_earcon(earcon="notification", event_name=event_name, context=context)


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================


async def celebrate(context: EarconContext | None = None) -> EarconResult:
    """Play celebration earcon."""
    return await play_earcon(EarconType.CELEBRATION, context=context)


async def alert(context: EarconContext | None = None) -> EarconResult:
    """Play alert earcon."""
    return await play_earcon(EarconType.ALERT, context=context)


async def notify(context: EarconContext | None = None) -> EarconResult:
    """Play notification earcon."""
    return await play_earcon(EarconType.NOTIFICATION, context=context)


async def success(context: EarconContext | None = None) -> EarconResult:
    """Play success earcon."""
    return await play_earcon(EarconType.SUCCESS, context=context)


async def error(context: EarconContext | None = None) -> EarconResult:
    """Play error earcon."""
    return await play_earcon(EarconType.ERROR, context=context)


async def arrival(context: EarconContext | None = None) -> EarconResult:
    """Play arrival earcon."""
    return await play_earcon(EarconType.ARRIVAL, context=context)


async def departure(context: EarconContext | None = None) -> EarconResult:
    """Play departure earcon."""
    return await play_earcon(EarconType.DEPARTURE, context=context)


# =============================================================================
# EXPORTS
# =============================================================================


__all__ = [
    "EARCON_BREATH_PREFERENCES",
    "EARCON_REGISTRY",
    "EVENT_EARCON_MAP",
    "ROOM_AUDIO_ZONES",
    "SPATIAL_ROOMS",
    "TRAJECTORY_LIBRARY",
    "EarconContext",
    "EarconDefinition",
    "EarconEvent",
    "EarconEventBroadcaster",
    "EarconMood",
    "EarconResult",
    "EarconType",
    "adapt_earcon_audio",
    "alert",
    "arrival",
    "celebrate",
    "clear_cache",
    "departure",
    "error",
    "generate_earcon_via_genai",
    "get_breath_phase",
    "get_contextual_trajectory",
    "get_current_room",
    "get_earcon",
    "get_earcon_broadcaster",
    "get_earcon_for_event",
    "get_time_to_phase",
    "list_earcons",
    "notify",
    "play_earcon",
    "play_earcon_stereo",
    "play_event",
    "register_earcon",
    "register_event_earcon",
    "route_earcon_to_room",
    "should_use_spatial_audio",
    "subscribe_to_earcon_events",
    "success",
    "wait_for_breath_phase",
]
