"""Unified Voice Pipeline — THE SINGLE ENTRY POINT.

Consolidates ALL voice, STT, speaker ID, and presence into ONE pipeline:

Input (Sensing):
    Audio → STT → Speaker ID → Intent Parse → Execute

Output (Acting):
    Text → TTS → Spatial Routing → Playback

This is THE canonical path. All apps route through here.

Architecture:
    UnifiedVoicePipeline
    ├── STT: FasterWhisperProvider (Python) / Whisper (Rust Hub)
    ├── Speaker ID: Voice profile matching
    ├── Identity: User resolution from voice
    ├── Presence: Context-aware routing
    └── TTS: KagamiVoice → UnifiedVoiceEffector

Created: January 1, 2026
"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from kagami.core.effectors.voice import UnifiedVoiceEffector

logger = logging.getLogger(__name__)


# =============================================================================
# Data Types
# =============================================================================


class VoiceInputState(str, Enum):
    """Voice input pipeline state."""

    IDLE = "idle"
    LISTENING = "listening"
    TRANSCRIBING = "transcribing"
    IDENTIFYING = "identifying"
    PROCESSING = "processing"
    RESPONDING = "responding"


@dataclass
class SpeakerProfile:
    """Speaker voice profile for identification."""

    user_id: str
    name: str
    embedding: list[float] = field(default_factory=list)
    confidence_threshold: float = 0.7
    is_owner: bool = False
    role: str = "member"  # owner, admin, member, guest


@dataclass
class SpeakerMatch:
    """Result of speaker identification."""

    is_identified: bool = False
    speaker: SpeakerProfile | None = None
    confidence: float = 0.0
    all_scores: dict[str, float] = field(default_factory=dict)


@dataclass
class VoiceInputResult:
    """Result of voice input processing."""

    success: bool
    transcript: str = ""
    speaker: SpeakerMatch = field(default_factory=SpeakerMatch)
    intent: str | None = None
    entities: dict[str, Any] = field(default_factory=dict)
    audio_duration_ms: float = 0.0
    processing_time_ms: float = 0.0
    error: str | None = None


@dataclass
class VoiceContext:
    """Context for voice interaction."""

    # Location context
    at_home: bool = True
    current_room: str | None = None
    in_vehicle: bool = False

    # User context
    current_user_id: str | None = None
    current_user_name: str | None = None

    # State context
    wakefulness: str = "alert"  # dormant, drowsy, alert, focused, hyper
    movie_mode: bool = False
    is_sleeping: bool = False

    # Time context
    hour: int = 12
    is_night: bool = False


# =============================================================================
# STT Provider Interface
# =============================================================================


class STTProvider(ABC):
    """Base class for speech-to-text providers."""

    @abstractmethod
    async def transcribe(
        self,
        audio_data: bytes | Path,
        language: str = "en",
    ) -> tuple[str, float]:
        """Transcribe audio to text.

        Args:
            audio_data: Audio bytes or path to audio file
            language: Language code

        Returns:
            Tuple of (transcript, confidence)
        """
        ...


class FasterWhisperSTT(STTProvider):
    """Faster Whisper STT provider (Python)."""

    def __init__(self, model_size: str = "base"):
        self._model_size = model_size
        self._model = None
        self._initialized = False

    async def initialize(self) -> bool:
        """Initialize the Whisper model."""
        if self._initialized:
            return True

        try:
            from faster_whisper import WhisperModel

            # Use CPU for now, CUDA if available
            self._model = WhisperModel(
                self._model_size,
                device="auto",
                compute_type="auto",
            )
            self._initialized = True
            logger.info(f"✓ FasterWhisper STT initialized ({self._model_size})")
            return True

        except ImportError:
            logger.warning("faster-whisper not installed, STT unavailable")
            return False
        except Exception as e:
            logger.error(f"FasterWhisper init failed: {e}")
            return False

    async def transcribe(
        self,
        audio_data: bytes | Path,
        language: str = "en",
    ) -> tuple[str, float]:
        """Transcribe audio using Faster Whisper."""
        if not self._initialized:
            await self.initialize()

        if not self._model:
            return "", 0.0

        try:
            # Handle path or bytes
            if isinstance(audio_data, Path):
                audio_path = str(audio_data)
            else:
                # Write bytes to temp file
                import tempfile

                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                    f.write(audio_data)
                    audio_path = f.name

            # Transcribe
            segments, info = self._model.transcribe(
                audio_path,
                language=language,
                beam_size=5,
                vad_filter=True,
            )

            # Collect transcript
            transcript = " ".join(segment.text.strip() for segment in segments)
            confidence = info.language_probability if info else 0.8

            return transcript, confidence

        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            return "", 0.0


# =============================================================================
# Speaker Identification
# =============================================================================


class SpeakerIdentifier:
    """Speaker identification from voice embeddings."""

    def __init__(self):
        self._profiles: dict[str, SpeakerProfile] = {}
        self._api_url: str | None = None
        self._initialized = False

    async def initialize(self, api_url: str | None = None) -> bool:
        """Initialize and load profiles from API."""
        self._api_url = api_url

        if api_url:
            await self.load_profiles_from_api()

        self._initialized = True
        return True

    async def load_profiles_from_api(self) -> None:
        """Load voice profiles from Kagami API."""
        if not self._api_url:
            return

        try:
            import httpx

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self._api_url}/api/users/voice-profiles",
                    timeout=10.0,
                )

                if response.status_code == 200:
                    data = response.json()
                    profiles = data.get("profiles", [])

                    for p in profiles:
                        profile = SpeakerProfile(
                            user_id=p["user_id"],
                            name=p["display_name"],
                            embedding=p.get("embedding", []),
                            is_owner=p.get("is_owner", False),
                            role=p.get("role", "member"),
                        )
                        self._profiles[p["user_id"]] = profile

                    logger.info(f"Loaded {len(profiles)} voice profiles")

        except Exception as e:
            logger.warning(f"Could not load voice profiles: {e}")

    def register_profile(self, profile: SpeakerProfile) -> None:
        """Register a speaker profile."""
        self._profiles[profile.user_id] = profile

    async def identify(
        self,
        audio_embedding: list[float],
    ) -> SpeakerMatch:
        """Identify speaker from audio embedding.

        Args:
            audio_embedding: Voice embedding vector

        Returns:
            SpeakerMatch with identification result
        """
        if not self._profiles or not audio_embedding:
            return SpeakerMatch()

        # Compare against all profiles
        scores: dict[str, float] = {}
        best_match: SpeakerProfile | None = None
        best_score = 0.0

        for user_id, profile in self._profiles.items():
            if not profile.embedding:
                continue

            # Cosine similarity
            score = self._cosine_similarity(audio_embedding, profile.embedding)
            scores[user_id] = score

            if score > best_score and score >= profile.confidence_threshold:
                best_score = score
                best_match = profile

        return SpeakerMatch(
            is_identified=best_match is not None,
            speaker=best_match,
            confidence=best_score,
            all_scores=scores,
        )

    def _cosine_similarity(self, a: list[float], b: list[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        if len(a) != len(b) or not a:
            return 0.0

        dot_product = sum(x * y for x, y in zip(a, b, strict=True))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return dot_product / (norm_a * norm_b)

    async def extract_embedding(self, audio_data: bytes | Path) -> list[float]:
        """Extract voice embedding from audio.

        Returns placeholder embeddings. Production implementation would use:
        - SpeechBrain (speaker-recognition)
        - Resemblyzer (d-vector embeddings)
        - Pyannote (speaker diarization)
        """
        _ = audio_data  # Reserved for speaker embedding model
        return [0.0] * 192  # Placeholder: standard embedding dimension


# =============================================================================
# Unified Voice Pipeline
# =============================================================================


class UnifiedVoicePipeline:
    """THE unified voice pipeline.

    Single entry point for all voice operations:
    - Input: Audio → STT → Speaker ID → Intent
    - Output: Text → TTS → Spatial Routing → Playback

    Usage:
        pipeline = await get_voice_pipeline()

        # Process voice input
        result = await pipeline.process_input(audio_bytes)
        print(f"{result.speaker.speaker.name}: {result.transcript}")

        # Generate voice output (personalized)
        await pipeline.speak("Hello", user_id=result.speaker.speaker.user_id)
    """

    def __init__(self):
        # Components
        self._stt: STTProvider | None = None
        self._speaker_id: SpeakerIdentifier | None = None
        self._voice_effector: UnifiedVoiceEffector | None = None

        # Context
        self._context = VoiceContext()

        # State
        self._state = VoiceInputState.IDLE
        self._initialized = False

        # Current speaker for personalization
        self._current_speaker: SpeakerMatch | None = None

        # Statistics
        self._stats = {
            "total_inputs": 0,
            "total_outputs": 0,
            "speakers_identified": 0,
            "total_input_latency_ms": 0,
            "total_output_latency_ms": 0,
        }

    # =========================================================================
    # Initialization
    # =========================================================================

    async def initialize(
        self,
        api_url: str | None = None,
        stt_model: str = "base",
    ) -> bool:
        """Initialize the voice pipeline.

        Args:
            api_url: Kagami API URL for voice profiles
            stt_model: Whisper model size

        Returns:
            True if initialization successful
        """
        if self._initialized:
            return True

        start = time.perf_counter()

        # Initialize STT
        self._stt = FasterWhisperSTT(model_size=stt_model)
        await self._stt.initialize()

        # Initialize Speaker ID
        self._speaker_id = SpeakerIdentifier()
        await self._speaker_id.initialize(api_url)

        # Initialize Voice Effector (output)
        try:
            from kagami.core.effectors.voice import get_voice_effector

            self._voice_effector = await get_voice_effector()
            logger.info("✓ Voice effector connected")
        except Exception as e:
            logger.warning(f"Voice effector not available: {e}")

        # Update context from presence service
        await self._update_context()

        self._initialized = True
        init_time = (time.perf_counter() - start) * 1000

        logger.info(f"✅ UnifiedVoicePipeline initialized in {init_time:.0f}ms")
        return True

    async def _update_context(self) -> None:
        """Update voice context from presence service."""
        try:
            from kagami.core.integrations.presence_service import get_presence_service

            presence = get_presence_service()
            snapshot = await presence.get_snapshot()

            self._context.at_home = snapshot.is_home
            self._context.current_room = snapshot.current_room
            self._context.in_vehicle = snapshot.travel_mode.value == "driving"

        except ImportError:
            pass
        except Exception as e:
            logger.debug(f"Context update failed: {e}")

    # =========================================================================
    # Voice Input Processing
    # =========================================================================

    async def process_input(
        self,
        audio_data: bytes | Path,
        language: str = "en",
        identify_speaker: bool = True,
    ) -> VoiceInputResult:
        """Process voice input through the full pipeline.

        Pipeline:
        1. STT: Transcribe audio to text
        2. Speaker ID: Identify who is speaking (optional)
        3. Intent: Parse command intent (if applicable)

        Args:
            audio_data: Audio bytes or path
            language: Language code
            identify_speaker: Whether to identify speaker

        Returns:
            VoiceInputResult with transcript, speaker, and intent
        """
        start = time.perf_counter()
        self._state = VoiceInputState.LISTENING
        self._stats["total_inputs"] += 1

        result = VoiceInputResult(success=False)

        try:
            # 1. STT - Transcribe
            self._state = VoiceInputState.TRANSCRIBING
            if not self._stt:
                result.error = "STT not initialized"
                return result

            transcript, _confidence = await self._stt.transcribe(audio_data, language)

            if not transcript:
                result.error = "No speech detected"
                return result

            result.transcript = transcript

            # 2. Speaker ID - Identify (parallel-capable)
            speaker_match = SpeakerMatch()
            if identify_speaker and self._speaker_id:
                self._state = VoiceInputState.IDENTIFYING

                # Extract embedding and identify
                embedding = await self._speaker_id.extract_embedding(audio_data)
                speaker_match = await self._speaker_id.identify(embedding)

                if speaker_match.is_identified:
                    self._stats["speakers_identified"] += 1
                    self._current_speaker = speaker_match

            result.speaker = speaker_match

            # 3. Parse intent (simple keyword matching for now)
            self._state = VoiceInputState.PROCESSING
            intent, entities = self._parse_intent(transcript)
            result.intent = intent
            result.entities = entities

            result.success = True

        except Exception as e:
            logger.error(f"Voice input processing failed: {e}")
            result.error = str(e)

        finally:
            self._state = VoiceInputState.IDLE
            result.processing_time_ms = (time.perf_counter() - start) * 1000
            self._stats["total_input_latency_ms"] += result.processing_time_ms

        return result

    def _parse_intent(self, transcript: str) -> tuple[str | None, dict[str, Any]]:
        """Parse intent from transcript using semantic parser.

        Uses the SemanticIntentParser for flexible natural language understanding
        that handles any phrasing from ElevenLabs agent or human speech.
        """
        try:
            from kagami.core.services.voice.intent_parser import (
                IntentCategory,
                parse_intent,
            )

            parsed = parse_intent(transcript)

            # Convert ParsedIntent to (intent_name, entities) format
            if parsed.category == IntentCategory.UNKNOWN:
                # Fall back to generic command
                return "command", {"text": transcript}

            # Build intent name from category and action
            category = parsed.category.name.lower()
            action = parsed.action.name.lower()
            intent_name = f"{category}_{action}"

            # Map to legacy intent names for backwards compatibility
            intent_map = {
                "lighting_turn_on": "lights_on",
                "lighting_turn_off": "lights_off",
                "lighting_set_brightness": "lights_dim",
                "shades_open": "shades_open",
                "shades_close": "shades_close",
                "scene_movie_mode": "scene_movie",
                "scene_goodnight": "scene_goodnight",
                "scene_welcome_home": "scene_welcome",
                "climate_fireplace_on": "fireplace_on",
                "climate_fireplace_off": "fireplace_off",
                "info_get_time": "query",
                "info_get_status": "query",
                "info_get_presence": "query",
            }

            final_intent = intent_map.get(intent_name, intent_name)

            # Build entities from parsed parameters
            entities = dict(parsed.parameters)
            entities["confidence"] = parsed.confidence
            entities["raw_command"] = transcript

            return final_intent, entities

        except ImportError:
            logger.warning("Semantic intent parser not available, using simple parsing")
            return self._parse_intent_simple(transcript)
        except Exception as e:
            logger.warning(f"Semantic parsing failed: {e}, using simple parsing")
            return self._parse_intent_simple(transcript)

    def _parse_intent_simple(self, transcript: str) -> tuple[str | None, dict[str, Any]]:
        """Simple keyword-based parsing fallback."""
        text = transcript.lower()
        entities: dict[str, Any] = {}

        # Light control
        if any(w in text for w in ["light", "lights", "lamp"]):
            if any(w in text for w in ["on", "turn on", "brighten"]):
                return "lights_on", entities
            if any(w in text for w in ["off", "turn off", "darken"]):
                return "lights_off", entities
            if any(w in text for w in ["dim", "lower"]):
                return "lights_dim", entities

        # Shade control
        if any(w in text for w in ["shade", "shades", "blind", "blinds"]):
            if any(w in text for w in ["open", "up", "raise"]):
                return "shades_open", entities
            if any(w in text for w in ["close", "down", "lower"]):
                return "shades_close", entities

        # Scene control
        if "movie" in text:
            return "scene_movie", entities
        if "goodnight" in text or "good night" in text:
            return "scene_goodnight", entities
        if "welcome" in text:
            return "scene_welcome", entities

        # General query
        if text.startswith(("what", "who", "where", "when", "how")):
            return "query", {"question": transcript}

        # Command
        return "command", {"text": transcript}

    # =========================================================================
    # Voice Output
    # =========================================================================

    async def speak(
        self,
        text: str,
        user_id: str | None = None,
        personalize: bool = True,
        **kwargs: Any,
    ) -> bool:
        """Speak text through the voice effector.

        Personalizes response based on identified speaker if available.

        Args:
            text: Text to speak
            user_id: Optional user ID for personalization
            personalize: Whether to personalize greeting
            **kwargs: Additional args for voice effector

        Returns:
            True if speech successful
        """
        self._state = VoiceInputState.RESPONDING
        start = time.perf_counter()

        try:
            if not self._voice_effector:
                logger.warning("Voice effector not available")
                return False

            # Personalize greeting if speaker identified
            final_text = text
            if personalize and self._current_speaker and self._current_speaker.is_identified:
                speaker = self._current_speaker.speaker
                if speaker and speaker.name and text.startswith(("Hello", "Hi", "Hey")):
                    final_text = (
                        f"Hello {speaker.name.split()[0]}, " + text[text.find(",") + 1 :].strip()
                        if "," in text
                        else text
                    )

            # Speak through effector
            result = await self._voice_effector.speak(final_text, **kwargs)

            self._stats["total_outputs"] += 1
            self._stats["total_output_latency_ms"] += (time.perf_counter() - start) * 1000

            return result.success

        except Exception as e:
            logger.error(f"Speech failed: {e}")
            return False

        finally:
            self._state = VoiceInputState.IDLE

    async def speak_to_user(
        self,
        text: str,
        user_id: str,
        **kwargs: Any,
    ) -> bool:
        """Speak to a specific user with personalization."""
        # Look up user's preferred settings if available
        return await self.speak(text, user_id=user_id, personalize=True, **kwargs)

    # =========================================================================
    # Speaker Management
    # =========================================================================

    def get_current_speaker(self) -> SpeakerMatch | None:
        """Get the currently identified speaker."""
        return self._current_speaker

    def clear_current_speaker(self) -> None:
        """Clear current speaker identification."""
        self._current_speaker = None

    async def register_speaker(
        self,
        user_id: str,
        name: str,
        audio_samples: list[bytes | Path],
        is_owner: bool = False,
    ) -> bool:
        """Register a new speaker profile from audio samples.

        Args:
            user_id: User ID
            name: Display name
            audio_samples: List of audio samples for embedding
            is_owner: Whether this is the owner

        Returns:
            True if registration successful
        """
        if not self._speaker_id:
            return False

        try:
            # Extract embeddings from all samples
            embeddings = []
            for sample in audio_samples:
                emb = await self._speaker_id.extract_embedding(sample)
                if emb:
                    embeddings.append(emb)

            if not embeddings:
                return False

            # Average embeddings
            avg_embedding = [
                sum(e[i] for e in embeddings) / len(embeddings) for i in range(len(embeddings[0]))
            ]

            # Create and register profile
            profile = SpeakerProfile(
                user_id=user_id,
                name=name,
                embedding=avg_embedding,
                is_owner=is_owner,
            )
            self._speaker_id.register_profile(profile)

            logger.info(f"Registered speaker: {name} ({user_id})")
            return True

        except Exception as e:
            logger.error(f"Speaker registration failed: {e}")
            return False

    # =========================================================================
    # Context & State
    # =========================================================================

    @property
    def state(self) -> VoiceInputState:
        """Get current pipeline state."""
        return self._state

    @property
    def context(self) -> VoiceContext:
        """Get current voice context."""
        return self._context

    def get_stats(self) -> dict[str, Any]:
        """Get pipeline statistics."""
        total_inputs = self._stats["total_inputs"] or 1
        total_outputs = self._stats["total_outputs"] or 1

        return {
            **self._stats,
            "avg_input_latency_ms": self._stats["total_input_latency_ms"] / total_inputs,
            "avg_output_latency_ms": self._stats["total_output_latency_ms"] / total_outputs,
            "speaker_id_rate": self._stats["speakers_identified"] / total_inputs,
            "state": self._state.value,
            "initialized": self._initialized,
        }


# =============================================================================
# Singleton & Factory
# =============================================================================


_voice_pipeline: UnifiedVoicePipeline | None = None


async def get_voice_pipeline() -> UnifiedVoicePipeline:
    """Get the unified voice pipeline singleton.

    Returns:
        Initialized UnifiedVoicePipeline
    """
    global _voice_pipeline
    if _voice_pipeline is None:
        _voice_pipeline = UnifiedVoicePipeline()
        await _voice_pipeline.initialize()
    return _voice_pipeline


def reset_voice_pipeline() -> None:
    """Reset the singleton (for testing)."""
    global _voice_pipeline
    _voice_pipeline = None


# =============================================================================
# Convenience Functions
# =============================================================================


async def process_voice(
    audio_data: bytes | Path,
    language: str = "en",
) -> VoiceInputResult:
    """Process voice input through the unified pipeline.

    Convenience function for quick voice processing.

    Args:
        audio_data: Audio bytes or path
        language: Language code

    Returns:
        VoiceInputResult with transcript and speaker
    """
    pipeline = await get_voice_pipeline()
    return await pipeline.process_input(audio_data, language)


async def speak(text: str, **kwargs: Any) -> bool:
    """Speak text through the unified pipeline.

    Args:
        text: Text to speak
        **kwargs: Additional args

    Returns:
        True if successful
    """
    pipeline = await get_voice_pipeline()
    return await pipeline.speak(text, **kwargs)


__all__ = [
    "FasterWhisperSTT",
    "STTProvider",
    "SpeakerIdentifier",
    "SpeakerMatch",
    "SpeakerProfile",
    "UnifiedVoicePipeline",
    "VoiceContext",
    "VoiceInputResult",
    "VoiceInputState",
    "get_voice_pipeline",
    "process_voice",
    "reset_voice_pipeline",
    "speak",
]
