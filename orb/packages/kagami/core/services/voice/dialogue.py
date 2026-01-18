"""Multi-character dialogue and podcast generator.

Full integration with ElevenLabs Text to Dialogue API, exposing
all available knobs and dials for fine-grained control.

Features:
- Unlimited speakers per dialogue
- Per-speaker voice settings
- Audio tags for emotion/singing
- Multiple output formats
- Streaming support

Created: January 1, 2026
"""

from __future__ import annotations

import logging
import tempfile
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class OutputFormat(Enum):
    """Available audio output formats.

    Format string: {codec}_{sample_rate}_{bitrate}
    """

    # MP3 formats
    MP3_22050_32 = "mp3_22050_32"  # Low quality, smallest file
    MP3_44100_64 = "mp3_44100_64"  # Medium quality
    MP3_44100_96 = "mp3_44100_96"  # Good quality
    MP3_44100_128 = "mp3_44100_128"  # High quality (default)
    MP3_44100_192 = "mp3_44100_192"  # Studio quality (Creator+)

    # PCM formats (uncompressed)
    PCM_16000 = "pcm_16000"  # 16kHz mono
    PCM_22050 = "pcm_22050"  # 22.05kHz mono
    PCM_24000 = "pcm_24000"  # 24kHz mono
    PCM_44100 = "pcm_44100"  # 44.1kHz mono (Pro+)

    # Opus formats (efficient compression)
    OPUS_48000_32 = "opus_48000_32"  # 48kHz, 32kbps
    OPUS_48000_64 = "opus_48000_64"  # 48kHz, 64kbps
    OPUS_48000_128 = "opus_48000_128"  # 48kHz, 128kbps

    # Telephony formats
    ULAW_8000 = "ulaw_8000"  # µ-law 8kHz (Twilio)
    ALAW_8000 = "alaw_8000"  # A-law 8kHz


class StabilityMode(Enum):
    """Voice stability presets.

    Based on ElevenLabs v3 documentation.
    """

    CREATIVE = 0.2  # Most emotional, expressive, may hallucinate
    NATURAL = 0.5  # Balanced, closest to original
    ROBUST = 0.8  # Highly stable, less responsive to tags


@dataclass
class VoiceSettings:
    """Voice generation settings.

    All the knobs and dials for controlling voice output.

    Attributes:
        stability: Voice consistency (0-1).
            - 0.0: Maximum variability, emotional range
            - 0.5: Balanced (default)
            - 1.0: Maximum consistency, monotone

        similarity_boost: Adherence to original voice (0-1).
            - 0.0: Creative interpretation
            - 0.75: Good similarity (default)
            - 1.0: Maximum similarity

        style: Style exaggeration (0-1).
            - 0.0: No style enhancement (default)
            - 0.5: Moderate emphasis
            - 1.0: Maximum style (higher latency)

        use_speaker_boost: Enhance clarity and presence.
            Increases computational cost but improves quality.

        speed: Speech rate (0.7-1.2).
            - 0.7: 30% slower
            - 1.0: Normal speed (default)
            - 1.2: 20% faster
            Extreme values may degrade quality.
    """

    stability: float = 0.5
    similarity_boost: float = 0.75
    style: float = 0.0
    use_speaker_boost: bool = True
    speed: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to API format."""
        return {
            "stability": self.stability,
            "similarity_boost": self.similarity_boost,
            "style": self.style,
            "use_speaker_boost": self.use_speaker_boost,
            "speed": self.speed,
        }

    @classmethod
    def creative(cls) -> VoiceSettings:
        """Preset for maximum expressiveness."""
        return cls(
            stability=0.2,
            similarity_boost=0.6,
            style=0.5,
            use_speaker_boost=True,
            speed=1.0,
        )

    @classmethod
    def natural(cls) -> VoiceSettings:
        """Preset for balanced, natural speech."""
        return cls(
            stability=0.5,
            similarity_boost=0.75,
            style=0.2,
            use_speaker_boost=True,
            speed=1.0,
        )

    @classmethod
    def robust(cls) -> VoiceSettings:
        """Preset for maximum consistency."""
        return cls(
            stability=0.8,
            similarity_boost=0.9,
            style=0.0,
            use_speaker_boost=True,
            speed=1.0,
        )

    @classmethod
    def singing(cls) -> VoiceSettings:
        """Preset optimized for [sings] tag."""
        return cls(
            stability=0.3,  # Allow pitch variation
            similarity_boost=0.7,
            style=0.4,  # Emphasize style
            use_speaker_boost=True,
            speed=1.0,
        )

    @classmethod
    def whisper(cls) -> VoiceSettings:
        """Preset optimized for [whispers] tag."""
        return cls(
            stability=0.6,
            similarity_boost=0.8,
            style=0.2,
            use_speaker_boost=False,  # Less boost for intimacy
            speed=0.9,  # Slightly slower
        )

    @classmethod
    def podcast(cls) -> VoiceSettings:
        """Preset for podcast/conversation clarity."""
        return cls(
            stability=0.6,
            similarity_boost=0.8,
            style=0.3,
            use_speaker_boost=True,
            speed=1.0,
        )


@dataclass
class Speaker:
    """A speaker/character in dialogue.

    Attributes:
        name: Display name for the speaker
        voice_id: ElevenLabs voice ID
        settings: Optional per-speaker voice settings
        description: Optional description for logging
    """

    name: str
    voice_id: str
    settings: VoiceSettings | None = None
    description: str = ""


@dataclass
class DialogueLine:
    """A single line of dialogue.

    Attributes:
        speaker: The speaker delivering this line
        text: The text to speak (can include audio tags)
    """

    speaker: Speaker
    text: str


@dataclass
class DialogueResult:
    """Result of dialogue generation."""

    success: bool
    audio_path: Path | None = None
    audio_data: bytes | None = None
    duration_ms: float = 0
    synthesis_ms: float = 0
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


# Audio tags reference
AUDIO_TAGS = """
## Audio Tags (v3 only)

### Emotional Delivery
- [excited] - Enthusiastic tone
- [sad] - Melancholic delivery
- [happy] - Joyful expression
- [angry] - Intense, forceful
- [curious] - Questioning tone
- [sarcastic] - Dry, ironic
- [mischievously] - Playful, teasing
- [warmly] - Affectionate
- [cheerfully] - Upbeat
- [cautiously] - Careful, hesitant

### Vocal Effects
- [sings] - Singing voice
- [whispers] - Whispering
- [hums] - Humming
- [laughs] - Laughter
- [giggles] - Light laughter
- [sighs] - Sighing
- [exhales] - Breathing out
- [gasps] - Sharp intake
- [snorts] - Nasal exhale
- [woo] - Exclamation

### Speech Patterns
- [stuttering] - Hesitant speech
- [yelling] - Loud delivery
- [shouting] - Very loud
- [mumbling] - Unclear speech
- [stammering] - Broken speech

### Special Effects
- [strong X accent] - Apply accent (e.g., [strong French accent])
- [dramatic pause] - Timing control
- [clears throat] - Throat clearing

### Sound Effects
- [applause] - Clapping sounds
- [gunshot] - Sharp crack
- [explosion] - Boom
- [leaves rustling] - Nature sounds

### Usage Tips
- Place tag before the text it affects
- Tags work best with v3 model
- Effectiveness varies by voice
- Creative/Natural stability works best with tags
"""


class DialogueGenerator:
    """Multi-character dialogue and podcast generator.

    Generates seamless multi-speaker audio with full control
    over voice settings, emotions, and output format.

    Usage:
        gen = DialogueGenerator()
        await gen.initialize()

        # Define speakers
        kagami = gen.get_kagami_speaker()
        tim = Speaker("Tim", "voice_id_here")

        # Create dialogue
        result = await gen.generate([
            DialogueLine(kagami, "[cheerfully] Hey Tim!"),
            DialogueLine(tim, "[curiously] What's up?"),
            DialogueLine(kagami, "[sings] La la la!"),
        ])
    """

    def __init__(
        self,
        output_format: OutputFormat = OutputFormat.MP3_44100_128,
        default_settings: VoiceSettings | None = None,
    ):
        """Initialize the generator.

        Args:
            output_format: Audio output format
            default_settings: Default voice settings for all speakers
        """
        self._client: Any = None
        self._initialized = False
        self._api_key: str | None = None
        self._kagami_voice_id: str | None = None
        self.output_format = output_format
        self.default_settings = default_settings or VoiceSettings.natural()

        # Cache of available voices
        self._voices: dict[str, dict] = {}

    async def initialize(self) -> bool:
        """Initialize the ElevenLabs client.

        Returns:
            True if successful
        """
        if self._initialized:
            return True

        try:
            from elevenlabs import ElevenLabs

            from kagami.core.security import get_secret

            self._api_key = get_secret("elevenlabs_api_key")
            self._kagami_voice_id = get_secret("elevenlabs_kagami_voice_id")

            if not self._api_key:
                logger.error("ElevenLabs API key not found")
                return False

            self._client = ElevenLabs(api_key=self._api_key)

            # Cache voices
            voices = self._client.voices.get_all()
            for v in voices.voices:
                self._voices[v.voice_id] = {
                    "name": v.name,
                    "description": v.description,
                    "labels": v.labels,
                }

            logger.info(f"✓ DialogueGenerator initialized ({len(self._voices)} voices)")
            self._initialized = True
            return True

        except Exception as e:
            logger.error(f"DialogueGenerator initialization failed: {e}")
            return False

    def get_kagami_speaker(
        self,
        settings: VoiceSettings | None = None,
    ) -> Speaker:
        """Get a Speaker object for Kagami.

        Args:
            settings: Optional custom settings

        Returns:
            Speaker configured for Kagami's voice
        """
        return Speaker(
            name="Kagami",
            voice_id=self._kagami_voice_id or "",
            settings=settings,
            description="Kagami AI assistant voice",
        )

    def list_voices(self) -> list[dict[str, Any]]:
        """List all available voices.

        Returns:
            List of voice info dicts
        """
        return [
            {
                "voice_id": vid,
                "name": info["name"],
                "description": info.get("description", ""),
                "labels": info.get("labels", {}),
                "is_kagami": vid == self._kagami_voice_id,
            }
            for vid, info in self._voices.items()
        ]

    def find_voice(
        self,
        query: str,
        gender: str | None = None,
    ) -> str | None:
        """Find a voice by name or description.

        Args:
            query: Search query (name or keywords)
            gender: Optional filter ("male", "female")

        Returns:
            Voice ID if found, None otherwise
        """
        query_lower = query.lower()

        for vid, info in self._voices.items():
            name = info.get("name", "").lower()
            desc = str(info.get("description", "")).lower()
            labels = str(info.get("labels", {})).lower()

            # Check gender filter
            if gender:
                if gender.lower() not in labels:
                    continue

            # Check query match
            if query_lower in name or query_lower in desc:
                return vid

        return None

    async def generate(
        self,
        lines: list[DialogueLine],
        output_path: Path | str | None = None,
        model_id: str = "eleven_v3",
    ) -> DialogueResult:
        """Generate multi-speaker dialogue audio.

        Args:
            lines: List of dialogue lines
            output_path: Optional path to save audio
            model_id: Model to use (eleven_v3 for audio tags)

        Returns:
            DialogueResult with audio data
        """
        if not self._initialized:
            await self.initialize()

        if not self._client:
            return DialogueResult(success=False, error="Client not initialized")

        start = time.perf_counter()

        try:
            # Build inputs array
            inputs = []
            for line in lines:
                input_data = {
                    "text": line.text,
                    "voice_id": line.speaker.voice_id,
                }

                # Add voice settings if specified
                settings = line.speaker.settings or self.default_settings
                if settings:
                    input_data["voice_settings"] = settings.to_dict()

                inputs.append(input_data)

            # Generate dialogue
            audio = self._client.text_to_dialogue.convert(
                inputs=inputs,
                model_id=model_id,
                output_format=self.output_format.value,
            )

            # Collect audio data
            audio_data = b"".join(chunk for chunk in audio)
            synthesis_ms = (time.perf_counter() - start) * 1000

            # Save to file if path provided
            if output_path:
                output_path = Path(output_path)
                with open(output_path, "wb") as f:
                    f.write(audio_data)
            else:
                # Save to temp file
                temp_dir = Path(tempfile.gettempdir()) / "kagami_dialogue"
                temp_dir.mkdir(exist_ok=True)
                output_path = temp_dir / f"dialogue_{int(time.time() * 1000)}.mp3"
                with open(output_path, "wb") as f:
                    f.write(audio_data)

            # Build metadata
            speakers = list({line.speaker.name for line in lines})

            return DialogueResult(
                success=True,
                audio_path=output_path,
                audio_data=audio_data,
                synthesis_ms=synthesis_ms,
                metadata={
                    "speakers": speakers,
                    "line_count": len(lines),
                    "model_id": model_id,
                    "output_format": self.output_format.value,
                },
            )

        except Exception as e:
            logger.error(f"Dialogue generation failed: {e}")
            return DialogueResult(success=False, error=str(e))

    async def generate_podcast(
        self,
        script: list[tuple[str, str]],
        speakers: dict[str, Speaker],
        output_path: Path | str | None = None,
    ) -> DialogueResult:
        """Generate podcast-style audio from script.

        Convenience method for podcast generation.

        Args:
            script: List of (speaker_name, text) tuples
            speakers: Dict mapping names to Speaker objects
            output_path: Optional output path

        Returns:
            DialogueResult with audio
        """
        lines = []
        for speaker_name, text in script:
            if speaker_name not in speakers:
                raise ValueError(f"Unknown speaker: {speaker_name}")
            lines.append(DialogueLine(speakers[speaker_name], text))

        return await self.generate(lines, output_path)


# Voice cloning helpers


async def clone_voice_instant(
    name: str,
    audio_files: list[str | Path],
    description: str = "",
    remove_background_noise: bool = True,
) -> str:
    """Clone a voice instantly from audio samples.

    Requirements:
    - 1-2 minutes of clear speech
    - MP3 192kbps+ or WAV recommended
    - No background noise, single speaker
    - Consistent volume and tone

    Args:
        name: Name for the cloned voice
        audio_files: List of audio file paths (1-25 files)
        description: Optional description
        remove_background_noise: Apply noise removal

    Returns:
        Voice ID of the cloned voice
    """
    from elevenlabs import ElevenLabs

    from kagami.core.security import get_secret

    api_key = get_secret("elevenlabs_api_key")
    client = ElevenLabs(api_key=api_key)

    # Convert paths to strings
    files = [str(f) for f in audio_files]

    voice = client.voices.ivc.create(
        name=name,
        description=description,
        files=files,
        remove_background_noise=remove_background_noise,
    )

    logger.info(f"✓ Created instant voice clone: {name} ({voice.voice_id})")
    return voice.voice_id


async def list_my_voices() -> list[dict[str, Any]]:
    """List all voices in your account.

    Returns:
        List of voice info dicts
    """
    from elevenlabs import ElevenLabs

    from kagami.core.security import get_secret

    api_key = get_secret("elevenlabs_api_key")
    client = ElevenLabs(api_key=api_key)

    voices = client.voices.get_all()

    return [
        {
            "voice_id": v.voice_id,
            "name": v.name,
            "description": v.description,
            "labels": v.labels,
            "category": v.category,
            "samples": len(v.samples) if v.samples else 0,
        }
        for v in voices.voices
    ]


# =============================================================================
# Voice Remixing Integration
# =============================================================================


async def remix_speaker_voice(
    speaker: Speaker,
    description: str,
    new_name: str | None = None,
    prompt_strength: float = 0.5,
) -> Speaker:
    """Create a remixed variant of a speaker's voice.

    Useful for creating character variations (younger/older, accents, etc.)
    without needing new audio samples.

    Args:
        speaker: Original speaker to remix
        description: Natural language description of changes
        new_name: Name for remixed speaker (default: "Speaker - Remixed")
        prompt_strength: Remix intensity (0.0-1.0)

    Returns:
        New Speaker with remixed voice_id

    Example:
        kagami = gen.get_kagami_speaker()
        kagami_british = await remix_speaker_voice(
            kagami,
            "Add a warm British accent",
            new_name="Kagami (British)",
        )
    """
    from kagami.core.services.voice.remixing import get_voice_remixer

    remixer = await get_voice_remixer()

    result = await remixer.remix_voice(
        voice_id=speaker.voice_id,
        name=new_name or f"{speaker.name} - Remixed",
        description=description,
        prompt_strength=prompt_strength,
    )

    if not result.success or not result.voice_id:
        raise RuntimeError(f"Voice remix failed: {result.error}")

    return Speaker(
        name=new_name or f"{speaker.name} (Remixed)",
        voice_id=result.voice_id,
        settings=speaker.settings,
        description=f"Remixed: {description}",
    )


async def create_voice_variant(
    voice_id: str,
    variant_name: str,
    preset: str,
) -> str:
    """Create a voice variant using a preset.

    Presets: younger, older, more_masculine, more_feminine, whisper,
    dramatic, professional, casual, energetic, calm, british, american,
    australian, warmer, clearer, richer

    Args:
        voice_id: Voice to remix
        variant_name: Name for the variant
        preset: Preset name

    Returns:
        New voice_id
    """
    from kagami.core.services.voice.remixing import quick_remix

    result = await quick_remix(voice_id, preset, variant_name)

    if not result.success or not result.voice_id:
        raise RuntimeError(f"Voice variant failed: {result.error}")

    return result.voice_id


# Module-level singleton
_dialogue_generator: DialogueGenerator | None = None


async def get_dialogue_generator(
    output_format: OutputFormat = OutputFormat.MP3_44100_128,
) -> DialogueGenerator:
    """Get the singleton DialogueGenerator.

    Args:
        output_format: Audio output format

    Returns:
        Initialized DialogueGenerator
    """
    global _dialogue_generator
    if _dialogue_generator is None:
        _dialogue_generator = DialogueGenerator(output_format)
        await _dialogue_generator.initialize()
    return _dialogue_generator


# Convenience exports
__all__ = [
    "AUDIO_TAGS",
    "DialogueGenerator",
    "DialogueLine",
    "DialogueResult",
    "OutputFormat",
    "Speaker",
    "StabilityMode",
    "VoiceSettings",
    "clone_voice_instant",
    "create_voice_variant",
    "get_dialogue_generator",
    "list_my_voices",
    "remix_speaker_voice",
]
