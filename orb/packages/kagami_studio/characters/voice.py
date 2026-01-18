"""Character Voice — Unified TTS for all characters.

Replaces:
- services/voice/bella_voice.py
- services/voice/dialogue.py
- media/production/characters.py voice handling

Features:
- Voice synthesis via ElevenLabs (Flash/V3 models)
- Mood modulation for emotional delivery
- Voice remixing for character variants
- Live playback via UnifiedVoiceEffector (home, car, glasses, desktop)

Usage:
    from kagami_studio.characters import speak, CharacterVoice

    # Quick path
    result = await speak("bella", "SNOW! SNOW SNOW SNOW!")

    # With emotion
    result = await speak_with_emotion("bella", "The vacuum approaches.", emotion="dramatic")

    # Full control
    voice = CharacterVoice("bella")
    await voice.initialize()
    result = await voice.speak("I am built for the cold.", mood="regal")

    # Create remixed voice variant
    variant = await voice.create_remix_variant(
        name="Bella Whisper",
        description="Softer, more intimate",
    )

    # Play through smart home / speakers
    result = await voice.speak("Hello", mood="warm", play=True, rooms=["Living Room"])
"""

from __future__ import annotations

import asyncio
import logging
import tempfile
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from kagami_studio.characters.protocol import Character, load_character

logger = logging.getLogger(__name__)


class Mood(str, Enum):
    """Universal mood settings for voice modulation."""

    NEUTRAL = "neutral"
    WARM = "warm"
    EXCITED = "excited"
    DRAMATIC = "dramatic"
    SLEEPY = "sleepy"
    PROTECTIVE = "protective"
    WISE = "wise"
    NERVOUS = "nervous"
    PROFESSIONAL = "professional"


# =============================================================================
# ELEVENLABS V3 AUDIO TAGS
# =============================================================================
# These tags ONLY work with eleven_v3 model. Other models will speak them literally.
#
# PAUSES (natural speech rhythm):
#   [pause]        - Standard pause (~0.5s)
#   [short pause]  - Brief pause (~0.25s)
#   [long pause]   - Extended pause (~1s)
#
# EMOTIONS (affect delivery tone):
#   [curious]      - Questioning, interested
#   [crying]       - Tearful, emotional
#   [mischievously]- Playful, teasing
#   [sad]          - Melancholy, somber
#   [angry]        - Intense, frustrated
#   [happily]      - Joyful, upbeat
#
# DELIVERY STYLES:
#   [whispers]     - Quiet, intimate
#   [shouts]       - Loud, emphatic
#
# NON-VERBAL REACTIONS:
#   [laughs]       - Laughter
#   [clears throat]- Throat clear
#   [sighs]        - Audible sigh
#
# Example: "Hold on. [pause] I've got it! [laughs] This is amazing."


class V3AudioTag:
    """ElevenLabs V3 audio tags for expressive speech."""

    # Pauses
    PAUSE = "[pause]"
    SHORT_PAUSE = "[short pause]"
    LONG_PAUSE = "[long pause]"

    # Emotions
    CURIOUS = "[curious]"
    CRYING = "[crying]"
    MISCHIEVOUS = "[mischievously]"
    SAD = "[sad]"
    ANGRY = "[angry]"
    HAPPY = "[happily]"

    # Delivery
    WHISPER = "[whispers]"
    SHOUT = "[shouts]"

    # Non-verbal
    LAUGH = "[laughs]"
    CLEAR_THROAT = "[clears throat]"
    SIGH = "[sighs]"


# Mood → voice_settings modifiers
MOOD_MODIFIERS: dict[Mood, dict[str, float]] = {
    Mood.NEUTRAL: {},
    Mood.WARM: {"stability": 0.52, "style": 0.38},
    Mood.EXCITED: {"stability": 0.25, "style": 0.60, "speed": 1.15},
    Mood.DRAMATIC: {"stability": 0.30, "style": 0.55, "speed": 0.90},
    Mood.SLEEPY: {"stability": 0.60, "style": 0.25, "speed": 0.80},
    Mood.PROTECTIVE: {"stability": 0.55, "style": 0.35, "speed": 0.85},
    Mood.WISE: {"stability": 0.50, "style": 0.38, "speed": 0.92},
    Mood.NERVOUS: {"stability": 0.35, "style": 0.45, "speed": 1.05},
    Mood.PROFESSIONAL: {"stability": 0.55, "style": 0.30, "speed": 0.98},
}


@dataclass
class WordTiming:
    """Timing for a single word from ElevenLabs alignment."""

    text: str
    start_ms: int
    end_ms: int


@dataclass
class SpeakResult:
    """Result of TTS generation."""

    success: bool
    audio_path: Path | None = None
    audio_bytes: bytes | None = None
    ttfa_ms: float = 0.0
    total_ms: float = 0.0
    character: str = ""
    mood: str = "neutral"
    text: str = ""
    error: str | None = None
    # Playback tracking
    played: bool = False
    play_target: str | None = None  # home, car, glasses, desktop
    # Word-level timing from ElevenLabs
    word_timings: list[WordTiming] | None = None


@dataclass
class RemixVariant:
    """A remixed voice variant for a character."""

    name: str
    voice_id: str
    description: str
    base_character: str
    prompt_strength: float = 0.5


class CharacterVoice:
    """Unified voice for any character.

    Loads character from metadata.json and uses their voice settings.
    Supports mood modulation via ElevenLabs parameters.
    """

    def __init__(self, character_name: str):
        """Initialize voice for a character.

        Args:
            character_name: Character identity_id (bella, tim, kagami, etc.)
        """
        self.character_name = character_name
        self._character: Character | None = None
        self._client: Any = None
        self._initialized = False
        self._temp_dir = Path(tempfile.gettempdir()) / "kagami_voices"
        self._stats = {
            "speaks": 0,
            "total_ms": 0.0,
            "by_mood": {m.value: 0 for m in Mood},
        }

    async def initialize(self) -> bool:
        """Initialize ElevenLabs client and load character."""
        if self._initialized:
            return True

        try:
            # Load character
            self._character = load_character(self.character_name)
            if not self._character:
                logger.error(f"Character not found: {self.character_name}")
                return False

            if not self._character.has_voice:
                logger.error(f"Character has no voice_id: {self.character_name}")
                return False

            # Initialize ElevenLabs
            from elevenlabs import ElevenLabs
            from kagami.core.security import get_secret

            api_key = get_secret("elevenlabs_api_key")
            if not api_key:
                logger.error("ElevenLabs API key not found")
                return False

            self._client = ElevenLabs(api_key=api_key)
            self._temp_dir.mkdir(exist_ok=True)
            self._initialized = True

            logger.info(f"✓ CharacterVoice ready: {self._character.name}")
            return True

        except Exception as e:
            logger.error(f"CharacterVoice init failed: {e}")
            return False

    def _get_voice_settings(self, mood: Mood) -> dict[str, Any]:
        """Get voice settings modified by mood."""
        if not self._character:
            return {}

        # Start with character's base settings
        settings = self._character.voice.to_elevenlabs()

        # Apply mood modifiers
        modifiers = MOOD_MODIFIERS.get(mood, {})
        for key, value in modifiers.items():
            if key in settings:
                settings[key] = value

        return settings

    async def speak(
        self,
        text: str,
        mood: Mood | str = Mood.NEUTRAL,
        with_timestamps: bool = False,
    ) -> SpeakResult:
        """Generate TTS audio using ElevenLabs V3.

        ALWAYS uses eleven_v3 model for audio tag support.

        Args:
            text: Text to speak (can include v3 audio tags like [whispers], [excited])
            mood: Emotional state for voice modulation
            with_timestamps: Return word-level timestamps from ElevenLabs

        Returns:
            SpeakResult with audio data and optional word timings
        """
        start = time.perf_counter()

        if not self._initialized:
            await self.initialize()

        if not self._client or not self._character:
            return SpeakResult(
                success=False,
                error="Not initialized",
                character=self.character_name,
                text=text,
            )

        # Parse mood
        if isinstance(mood, str):
            try:
                mood = Mood(mood.lower())
            except ValueError:
                mood = Mood.NEUTRAL

        try:
            # ALWAYS use V3 for audio tag support
            model_id = "eleven_v3"

            # Use timestamps API if requested
            if with_timestamps:
                return await self._speak_with_timestamps(text, mood, model_id, start)

            # Stream for lower latency
            chunks: list[bytes] = []
            ttfa = 0.0
            first_chunk = True

            # Use streaming API
            audio_stream = self._client.text_to_speech.stream(
                voice_id=self._character.voice.voice_id,
                text=text,
                model_id=model_id,
            )

            for chunk in audio_stream:
                if first_chunk:
                    ttfa = (time.perf_counter() - start) * 1000
                    first_chunk = False
                if isinstance(chunk, bytes):
                    chunks.append(chunk)

            audio_bytes = b"".join(chunks)

            # Save to temp file
            timestamp = int(time.time() * 1000)
            audio_path = self._temp_dir / f"{self.character_name}_{mood.value}_{timestamp}.mp3"
            with open(audio_path, "wb") as f:
                f.write(audio_bytes)

            total_ms = (time.perf_counter() - start) * 1000

            # Update stats
            self._stats["speaks"] += 1
            self._stats["total_ms"] += total_ms
            self._stats["by_mood"][mood.value] += 1

            logger.info(
                f"🎤 {self._character.name} [{mood.value}] "
                f"TTFA:{ttfa:.0f}ms Total:{total_ms:.0f}ms "
                f'"{text[:50]}{"..." if len(text) > 50 else ""}"'
            )

            return SpeakResult(
                success=True,
                audio_path=audio_path,
                audio_bytes=audio_bytes,
                ttfa_ms=ttfa,
                total_ms=total_ms,
                character=self.character_name,
                mood=mood.value,
                text=text,
            )

        except Exception as e:
            import traceback

            logger.error(f"Speak failed: {e}")
            logger.error(traceback.format_exc())
            return SpeakResult(
                success=False,
                error=str(e) or f"{type(e).__name__}: check logs for traceback",
                character=self.character_name,
                mood=mood.value,
                text=text,
            )

    async def _speak_with_timestamps(
        self,
        text: str,
        mood: Mood,
        model_id: str,
        start: float,
    ) -> SpeakResult:
        """Generate TTS with word-level timestamps from ElevenLabs.

        Uses the /with-timestamps endpoint for alignment data.
        Note: This endpoint requires stability to be exactly 0.0, 0.5, or 1.0
        """
        import httpx
        from kagami.core.security import get_secret

        api_key = get_secret("elevenlabs_api_key")
        voice_id = self._character.voice.voice_id

        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/with-timestamps"

        # Get voice settings and snap stability to valid values
        voice_settings = self._get_voice_settings(mood)
        # /with-timestamps only accepts stability of 0.0, 0.5, or 1.0
        raw_stability = voice_settings.get("stability", 0.5)
        if raw_stability < 0.25:
            voice_settings["stability"] = 0.0
        elif raw_stability < 0.75:
            voice_settings["stability"] = 0.5
        else:
            voice_settings["stability"] = 1.0

        # Longer timeout for longer texts (unified narration can be several minutes)
        timeout_s = max(120.0, len(text) / 100)  # At least 2 min, +1s per 100 chars
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            response = await client.post(
                url,
                headers={
                    "xi-api-key": api_key,
                    "Content-Type": "application/json",
                },
                json={
                    "text": text,
                    "model_id": model_id,
                    "voice_settings": voice_settings,
                },
            )

            if response.status_code != 200:
                return SpeakResult(
                    success=False,
                    error=f"ElevenLabs API error: {response.status_code} - {response.text[:200]}",
                    character=self.character_name,
                    mood=mood.value,
                    text=text,
                )

            data = response.json()

            # Extract audio (base64 encoded)
            import base64

            audio_base64 = data.get("audio_base64", "")
            audio_bytes = base64.b64decode(audio_base64)

            # Extract word timings
            alignment = data.get("alignment", {})
            characters = alignment.get("characters", [])
            char_start_times = alignment.get("character_start_times_seconds", [])
            char_end_times = alignment.get("character_end_times_seconds", [])

            # Build word timings from character timings
            word_timings = self._build_word_timings(characters, char_start_times, char_end_times)

            # Save audio
            timestamp = int(time.time() * 1000)
            audio_path = self._temp_dir / f"{self.character_name}_{mood.value}_{timestamp}.mp3"
            with open(audio_path, "wb") as f:
                f.write(audio_bytes)

            total_ms = (time.perf_counter() - start) * 1000

            # Update stats
            self._stats["speaks"] += 1
            self._stats["total_ms"] += total_ms
            self._stats["by_mood"][mood.value] += 1

            logger.info(
                f"🎤 {self._character.name} [{mood.value}] "
                f"Total:{total_ms:.0f}ms Words:{len(word_timings)} "
                f'"{text[:50]}{"..." if len(text) > 50 else ""}"'
            )

            return SpeakResult(
                success=True,
                audio_path=audio_path,
                audio_bytes=audio_bytes,
                ttfa_ms=0,
                total_ms=total_ms,
                character=self.character_name,
                mood=mood.value,
                text=text,
                word_timings=word_timings,
            )

    def _build_word_timings(
        self,
        characters: list[str],
        start_times: list[float],
        end_times: list[float],
    ) -> list[WordTiming]:
        """Build word timings from character-level alignment."""
        if not characters or not start_times or not end_times:
            return []

        word_timings = []
        current_word = ""
        word_start = 0.0
        word_end = 0.0

        for i, char in enumerate(characters):
            if i >= len(start_times) or i >= len(end_times):
                break

            if char == " " or char in ".,!?;:":
                # End of word
                if current_word.strip():
                    word_timings.append(
                        WordTiming(
                            text=current_word.strip() + (char if char in ".,!?;:" else ""),
                            start_ms=int(word_start * 1000),
                            end_ms=int(word_end * 1000),
                        )
                    )
                current_word = ""
                word_start = end_times[i] if i < len(end_times) else 0
            else:
                if not current_word:
                    word_start = start_times[i]
                current_word += char
                word_end = end_times[i]

        # Don't forget last word
        if current_word.strip():
            word_timings.append(
                WordTiming(
                    text=current_word.strip(),
                    start_ms=int(word_start * 1000),
                    end_ms=int(word_end * 1000),
                )
            )

        return word_timings

    def get_stats(self) -> dict[str, Any]:
        """Get voice statistics."""
        return {
            **self._stats,
            "character": self.character_name,
            "initialized": self._initialized,
            "voice_id": self._character.voice.voice_id if self._character else None,
        }

    async def create_remix_variant(
        self,
        name: str,
        description: str,
        prompt_strength: float = 0.5,
    ) -> RemixVariant | None:
        """Create a remixed voice variant for this character.

        Uses ElevenLabs Voice Remixing to create a permanent new voice
        based on the character's voice with modifications.

        Args:
            name: Name for the new voice variant
            description: Natural language description of the changes
                        (e.g., "warmer British accent", "more dramatic")
            prompt_strength: How much to change (0.1 = subtle, 1.0 = dramatic)

        Returns:
            RemixVariant with new voice_id, or None if failed

        Example:
            variant = await voice.create_remix_variant(
                name="Bella Whisper",
                description="Softer, more intimate, like whispering secrets",
                prompt_strength=0.6,
            )
        """
        if not self._initialized:
            await self.initialize()

        if not self._character:
            logger.error("Character not loaded")
            return None

        try:
            from kagami.core.services.voice.remixing import get_voice_remixer

            remixer = await get_voice_remixer()
            result = await remixer.remix_voice(
                voice_id=self._character.voice.voice_id,
                name=name,
                description=description,
                prompt_strength=prompt_strength,
            )

            if result.success and result.voice_id:
                logger.info(f"✓ Created remix variant: {name} ({result.voice_id})")
                return RemixVariant(
                    name=name,
                    voice_id=result.voice_id,
                    description=description,
                    base_character=self.character_name,
                    prompt_strength=prompt_strength,
                )
            else:
                logger.error(f"Remix failed for {self.character_name}")
                return None

        except Exception as e:
            logger.error(f"Remix variant creation failed: {e}")
            return None

    async def preview_remix(
        self,
        description: str,
        prompt_strength: float = 0.5,
        num_previews: int = 3,
    ) -> list[Path]:
        """Preview voice remix options before committing.

        Args:
            description: Natural language description of changes
            prompt_strength: How much to change (0.1-1.0)
            num_previews: Number of variations to generate

        Returns:
            List of audio preview file paths
        """
        if not self._initialized:
            await self.initialize()

        if not self._character:
            return []

        try:
            from kagami.core.services.voice.remixing import get_voice_remixer

            remixer = await get_voice_remixer()
            previews = await remixer.preview_remix(
                voice_id=self._character.voice.voice_id,
                description=description,
                prompt_strength=prompt_strength,
                num_previews=num_previews,
            )

            return [p.preview_path for p in previews if p.preview_path]

        except Exception as e:
            logger.error(f"Preview remix failed: {e}")
            return []

    async def speak_and_play(
        self,
        text: str,
        mood: Mood | str = Mood.NEUTRAL,
        rooms: list[str] | None = None,
        target: str = "auto",
    ) -> SpeakResult:
        """Generate TTS and play through UnifiedVoiceEffector.

        Args:
            text: Text to speak
            mood: Emotional state
            rooms: Specific rooms (for home target)
            target: Output target - "auto", "home", "car", "glasses", "desktop"

        Returns:
            SpeakResult with playback info
        """
        # First generate the audio
        result = await self.speak(text, mood)

        if not result.success or not result.audio_path:
            return result

        # Now play through effector
        try:
            from kagami.core.effectors.voice import VoiceTarget, get_voice_effector

            # Map target string to enum
            target_map = {
                "auto": VoiceTarget.AUTO,
                "home": VoiceTarget.HOME_ROOM if rooms else VoiceTarget.HOME_ALL,
                "home_room": VoiceTarget.HOME_ROOM,
                "home_all": VoiceTarget.HOME_ALL,
                "car": VoiceTarget.CAR,
                "glasses": VoiceTarget.GLASSES,
                "desktop": VoiceTarget.DESKTOP,
            }
            voice_target = target_map.get(target.lower(), VoiceTarget.AUTO)

            effector = await get_voice_effector()
            play_result = await effector.play_audio(
                audio_path=result.audio_path,
                target=voice_target,
                rooms=rooms,
            )

            result.played = play_result.success
            result.play_target = play_result.target.value if play_result.success else None

            if play_result.success:
                logger.info(f"🔊 Played to {play_result.target.value}")
            else:
                logger.warning(f"Playback failed: {play_result.error}")

        except ImportError:
            logger.warning("UnifiedVoiceEffector not available, skipping playback")
        except Exception as e:
            logger.warning(f"Playback failed: {e}")

        return result


# =============================================================================
# SINGLETON CACHE AND FAST PATH
# =============================================================================

_voice_cache: dict[str, CharacterVoice] = {}
_init_lock = asyncio.Lock()


async def get_voice(character_name: str) -> CharacterVoice:
    """Get or create a CharacterVoice instance."""
    if character_name not in _voice_cache:
        async with _init_lock:
            if character_name not in _voice_cache:
                voice = CharacterVoice(character_name)
                await voice.initialize()
                _voice_cache[character_name] = voice

    return _voice_cache[character_name]


async def speak(
    character_name: str,
    text: str,
    mood: Mood | str = Mood.NEUTRAL,
) -> SpeakResult:
    """Quick speak for any character.

    Args:
        character_name: Character identity (bella, tim, kagami, etc.)
        text: Text to speak
        mood: Emotional state

    Returns:
        SpeakResult
    """
    voice = await get_voice(character_name)
    return await voice.speak(text, mood)


async def speak_with_emotion(
    character_name: str,
    text: str,
    emotion: str,
) -> SpeakResult:
    """Speak with specified emotion (alias for mood).

    Maps common emotion words to Mood enum.
    """
    # Map emotion strings to moods
    emotion_map = {
        "happy": Mood.EXCITED,
        "sad": Mood.SLEEPY,
        "angry": Mood.DRAMATIC,
        "scared": Mood.NERVOUS,
        "calm": Mood.NEUTRAL,
        "excited": Mood.EXCITED,
        "dramatic": Mood.DRAMATIC,
        "sleepy": Mood.SLEEPY,
        "protective": Mood.PROTECTIVE,
        "wise": Mood.WISE,
        "warm": Mood.WARM,
        "professional": Mood.PROFESSIONAL,
        "regal": Mood.WARM,  # Map Bella's "regal" to warm
        "nervous": Mood.NERVOUS,
    }

    mood = emotion_map.get(emotion.lower(), Mood.NEUTRAL)
    return await speak(character_name, text, mood)


async def generate_presentation_audio(
    slides: list[dict],
    character_name: str = "tim",
    mood: Mood | str = Mood.PROFESSIONAL,
    add_pauses: bool = True,
) -> SpeakResult:
    """Generate unified audio for a presentation with natural timing.

    Uses ElevenLabs v3 audio tags for natural pauses between slides.
    IMPORTANT: Must use eleven_v3 model for tags to work.

    Args:
        slides: List of slide dicts with 'spoken_text' or 'spoken' keys
        character_name: Speaker character
        mood: Delivery mood
        add_pauses: Add natural pauses between slides (v3 tags)

    Returns:
        SpeakResult with word_timings for sync

    Example:
        slides = [
            {"spoken_text": "Welcome to our presentation."},
            {"spoken_text": "First, let's explore the basics."},
        ]
        result = await generate_presentation_audio(slides, "tim")
    """
    # Extract spoken text from slides
    texts = []
    for slide in slides:
        text = slide.get("spoken_text") or slide.get("spoken", "")
        if text and text.strip():
            texts.append(text.strip())

    if not texts:
        return SpeakResult(
            success=False,
            error="No spoken text in slides",
            character=character_name,
        )

    # Join with natural pauses (v3 tags only work with eleven_v3!)
    if add_pauses:
        # Use [long pause] between slides for natural pacing
        full_text = f" {V3AudioTag.LONG_PAUSE} ".join(texts)
    else:
        # Just double space for natural sentence break
        full_text = "  ".join(texts)

    # Generate with timestamps for sync
    voice = await get_voice(character_name)
    return await voice.speak(
        text=full_text,
        mood=mood,
        use_v3=True,  # MUST be v3 for audio tags
        with_timestamps=True,
    )


__all__ = [
    "MOOD_MODIFIERS",
    "CharacterVoice",
    "Mood",
    "RemixVariant",
    "SpeakResult",
    "V3AudioTag",
    "WordTiming",
    "generate_presentation_audio",
    "get_voice",
    "speak",
    "speak_with_emotion",
]
