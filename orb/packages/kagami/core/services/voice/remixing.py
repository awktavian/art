"""ElevenLabs Voice Remixing — Transform voices with prompts.

Voice Remixing allows transforming existing voices by modifying:
- Gender (make more masculine/feminine)
- Accent (add/change regional accents)
- Speaking style (professional, casual, dramatic)
- Pacing (faster, slower, more deliberate)
- Audio quality (enhance clarity, warmth)

The original voice remains unchanged — remixing creates new variants.

Usage:
    from kagami.core.services.voice.remixing import get_voice_remixer

    remixer = await get_voice_remixer()

    # Preview a remix
    previews = await remixer.preview_remix(
        voice_id="dDK8sjusg0SxsbmE6l6z",
        description="Make the voice warmer and add a slight British accent",
        prompt_strength=0.5,
    )

    # Listen to previews, pick one, then create the voice
    voice_id = await remixer.apply_remix(
        name="Kagami British",
        generated_voice_id=previews[0].generated_voice_id,
    )

    # Or do it all at once
    voice_id = await remixer.remix_voice(
        voice_id="dDK8sjusg0SxsbmE6l6z",
        name="Kagami Whisper",
        description="Make the voice softer and more intimate, like whispering",
        prompt_strength=0.7,
    )

Prompt Strength Levels:
- 0.0-0.3 (Low): Subtle changes, mostly preserves original
- 0.3-0.5 (Medium): Balanced transformation
- 0.5-0.7 (High): Strong adherence to prompt
- 0.7-1.0 (Max): Full transformation, may lose original character

Created: January 4, 2026
"""

from __future__ import annotations

import asyncio
import base64
import logging
import tempfile
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from elevenlabs import ElevenLabs

logger = logging.getLogger(__name__)


class PromptStrength(str, Enum):
    """Remix intensity levels with recommended use cases."""

    LOW = "low"  # 0.2 — Subtle enhancement (voice brightening, slight accent)
    MEDIUM = "medium"  # 0.4 — Balanced (moderate style change)
    HIGH = "high"  # 0.6 — Strong transformation (gender shift, strong accent)
    MAX = "max"  # 0.8 — Full transformation (complete character change)

    @property
    def value_float(self) -> float:
        """Get numeric value for API."""
        return {
            PromptStrength.LOW: 0.2,
            PromptStrength.MEDIUM: 0.4,
            PromptStrength.HIGH: 0.6,
            PromptStrength.MAX: 0.8,
        }[self]


@dataclass
class RemixPreview:
    """A preview of a remixed voice.

    Contains audio sample and generated_voice_id for creating the final voice.
    """

    generated_voice_id: str
    audio_base64: str
    audio_data: bytes = field(default_factory=bytes, repr=False)
    duration_ms: float = 0.0
    preview_path: Path | None = None

    def __post_init__(self) -> None:
        """Decode audio if not already done."""
        if self.audio_base64 and not self.audio_data:
            self.audio_data = base64.b64decode(self.audio_base64)

    async def save(self, path: Path | str) -> Path:
        """Save preview audio to file.

        Args:
            path: Output file path

        Returns:
            Path to saved file
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            f.write(self.audio_data)
        self.preview_path = path
        return path


@dataclass
class RemixResult:
    """Result of a voice remix operation."""

    success: bool
    voice_id: str | None = None
    voice_name: str | None = None
    original_voice_id: str | None = None
    description: str = ""
    prompt_strength: float = 0.0
    previews: list[RemixPreview] = field(default_factory=list)
    selected_preview_index: int = 0
    processing_ms: float = 0.0
    error: str | None = None


@dataclass
class RemixableVoice:
    """A voice that can be remixed."""

    voice_id: str
    name: str
    description: str = ""
    category: str = ""  # premade, cloned, generated
    labels: dict[str, str] = field(default_factory=dict)
    is_kagami: bool = False


class VoiceRemixer:
    """ElevenLabs Voice Remixing service.

    Transforms existing voices using natural language prompts.

    Key capabilities:
    - Preview remixes before applying
    - Control transformation intensity
    - Create permanent voice variants
    - Iterate on remixes (remix a remix)

    Architecture:
        remix_voice(voice_id, description)
        → text_to_voice.remix() API
        → Multiple previews returned
        → Select best preview
        → text_to_voice.create() API
        → New voice_id

    Limitations:
    - Can only remix voices you own
    - Each remix consumes API credits
    - Some voices respond better to remixing
    """

    def __init__(self) -> None:
        """Initialize the remixer."""
        self._client: ElevenLabs | None = None
        self._api_key: str | None = None
        self._kagami_voice_id: str | None = None
        self._initialized = False
        self._temp_dir = Path(tempfile.gettempdir()) / "kagami_remix"

        # Cache of remixable voices
        self._voices_cache: dict[str, RemixableVoice] = {}

        # Stats
        self._stats = {
            "remixes_created": 0,
            "previews_generated": 0,
            "voices_created": 0,
            "total_processing_ms": 0.0,
        }

    async def initialize(self) -> bool:
        """Initialize ElevenLabs client.

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
                logger.error("ElevenLabs API key not found in keychain")
                return False

            self._client = ElevenLabs(api_key=self._api_key)
            self._temp_dir.mkdir(exist_ok=True)

            # Cache remixable voices
            await self._cache_voices()

            self._initialized = True
            logger.info(f"✓ VoiceRemixer initialized ({len(self._voices_cache)} remixable voices)")
            return True

        except Exception as e:
            logger.error(f"VoiceRemixer initialization failed: {e}")
            return False

    async def _cache_voices(self) -> None:
        """Cache list of remixable voices."""
        if not self._client:
            return

        try:
            voices = self._client.voices.get_all()

            for v in voices.voices:
                # Only include voices we can remix (owned or cloned)
                category = getattr(v, "category", "unknown")
                if category in ("cloned", "generated", "professional", "premade"):
                    self._voices_cache[v.voice_id] = RemixableVoice(
                        voice_id=v.voice_id,
                        name=v.name or "Unnamed",
                        description=v.description or "",
                        category=category,
                        labels=dict(v.labels) if v.labels else {},
                        is_kagami=v.voice_id == self._kagami_voice_id,
                    )

            logger.debug(f"Cached {len(self._voices_cache)} remixable voices")

        except Exception as e:
            logger.warning(f"Failed to cache voices: {e}")

    # =========================================================================
    # Core Remixing API
    # =========================================================================

    async def preview_remix(
        self,
        voice_id: str,
        description: str,
        prompt_strength: float | PromptStrength = 0.5,
        script: str | None = None,
        num_previews: int = 3,
        output_format: str = "mp3_44100_128",
    ) -> list[RemixPreview]:
        """Generate remix previews without creating the final voice.

        Use this to audition different remix options before committing.

        Args:
            voice_id: ID of voice to remix
            description: Natural language description of desired changes
                Examples:
                - "Make the voice deeper and more authoritative"
                - "Add a warm British accent"
                - "Make it sound younger and more energetic"
            prompt_strength: How strongly to apply the remix (0.0-1.0)
            script: Optional custom script for preview (100-1000 chars)
            num_previews: Number of preview variants to generate (1-5)
            output_format: Audio format for previews

        Returns:
            List of RemixPreview objects with audio samples
        """
        if not self._initialized:
            await self.initialize()

        if not self._client:
            raise RuntimeError("VoiceRemixer not initialized")

        start = time.perf_counter()

        # Convert enum to float if needed
        if isinstance(prompt_strength, PromptStrength):
            prompt_strength = prompt_strength.value_float

        # Clamp to valid range
        prompt_strength = max(0.0, min(1.0, prompt_strength))

        try:
            # Call remix API
            response = self._client.text_to_voice.remix(
                voice_id=voice_id,
                voice_description=description,
                prompt_strength=prompt_strength,
                text=script,
                auto_generate_text=script is None,
                output_format=output_format,
            )

            # Parse response - VoiceDesignPreviewResponse with previews list
            previews: list[RemixPreview] = []

            # Response has .previews which is a list of VoicePreviewResponseModel
            if hasattr(response, "previews") and response.previews:
                for item in response.previews[:num_previews]:
                    preview = RemixPreview(
                        generated_voice_id=getattr(item, "generated_voice_id", ""),
                        audio_base64=getattr(item, "audio_base_64", ""),
                        duration_ms=getattr(item, "duration_secs", 0) * 1000,
                    )
                    previews.append(preview)
            elif hasattr(response, "voice_id"):
                # Fallback: Single preview response
                preview = RemixPreview(
                    generated_voice_id=response.voice_id,
                    audio_base64=getattr(response, "audio", "")
                    or getattr(response, "audio_base_64", ""),
                )
                previews.append(preview)

            # Save previews to temp files
            for i, preview in enumerate(previews):
                if preview.audio_data:
                    preview_path = self._temp_dir / f"preview_{voice_id}_{i}_{int(time.time())}.mp3"
                    await preview.save(preview_path)

            processing_ms = (time.perf_counter() - start) * 1000
            self._stats["previews_generated"] += len(previews)
            self._stats["total_processing_ms"] += processing_ms

            logger.info(
                f"🎨 Generated {len(previews)} remix previews "
                f"(strength={prompt_strength:.1f}, {processing_ms:.0f}ms)"
            )

            return previews

        except Exception as e:
            logger.error(f"Remix preview failed: {e}")
            raise

    async def apply_remix(
        self,
        name: str,
        generated_voice_id: str,
        description: str = "",
    ) -> str:
        """Create a permanent voice from a remix preview.

        Args:
            name: Name for the new voice
            generated_voice_id: ID from RemixPreview
            description: Optional description

        Returns:
            Voice ID of the newly created voice
        """
        if not self._initialized:
            await self.initialize()

        if not self._client:
            raise RuntimeError("VoiceRemixer not initialized")

        try:
            # Create voice from preview
            voice = self._client.text_to_voice.create_voice(
                voice_name=name,
                voice_description=description,
                generated_voice_id=generated_voice_id,
            )

            voice_id = voice.voice_id

            # Update cache
            self._voices_cache[voice_id] = RemixableVoice(
                voice_id=voice_id,
                name=name,
                description=description,
                category="generated",
            )

            self._stats["voices_created"] += 1

            logger.info(f"✓ Created remix voice: {name} ({voice_id})")
            return voice_id

        except Exception as e:
            logger.error(f"Apply remix failed: {e}")
            raise

    async def remix_voice(
        self,
        voice_id: str,
        name: str,
        description: str,
        prompt_strength: float | PromptStrength = 0.5,
        script: str | None = None,
        auto_select: bool = True,
    ) -> RemixResult:
        """Remix a voice in one operation.

        Generates previews and automatically selects the best one (or first).

        Args:
            voice_id: ID of voice to remix
            name: Name for the new voice
            description: Natural language description of changes
            prompt_strength: Transformation intensity (0.0-1.0)
            script: Optional preview script
            auto_select: If True, automatically select first preview

        Returns:
            RemixResult with new voice_id

        Example:
            result = await remixer.remix_voice(
                voice_id="dDK8sjusg0SxsbmE6l6z",
                name="Kagami Dramatic",
                description="Make the voice more dramatic and theatrical",
                prompt_strength=PromptStrength.HIGH,
            )
            print(f"New voice: {result.voice_id}")
        """
        start = time.perf_counter()

        # Convert enum to float if needed
        strength_value = (
            prompt_strength.value_float
            if isinstance(prompt_strength, PromptStrength)
            else prompt_strength
        )

        try:
            # Generate previews
            previews = await self.preview_remix(
                voice_id=voice_id,
                description=description,
                prompt_strength=strength_value,
                script=script,
            )

            if not previews:
                return RemixResult(
                    success=False,
                    original_voice_id=voice_id,
                    description=description,
                    prompt_strength=strength_value,
                    error="No previews generated",
                )

            # Auto-select first preview (or could implement scoring)
            selected = previews[0]

            # Apply the remix
            new_voice_id = await self.apply_remix(
                name=name,
                generated_voice_id=selected.generated_voice_id,
                description=f"Remixed from {voice_id}: {description}",
            )

            processing_ms = (time.perf_counter() - start) * 1000
            self._stats["remixes_created"] += 1

            return RemixResult(
                success=True,
                voice_id=new_voice_id,
                voice_name=name,
                original_voice_id=voice_id,
                description=description,
                prompt_strength=strength_value,
                previews=previews,
                selected_preview_index=0,
                processing_ms=processing_ms,
            )

        except Exception as e:
            logger.error(f"Remix voice failed: {e}")
            return RemixResult(
                success=False,
                original_voice_id=voice_id,
                description=description,
                prompt_strength=strength_value,
                error=str(e),
            )

    # =========================================================================
    # Convenience Methods
    # =========================================================================

    async def remix_kagami(
        self,
        name: str,
        description: str,
        prompt_strength: float | PromptStrength = 0.5,
    ) -> RemixResult:
        """Remix Kagami's voice.

        Convenience method using Kagami's stored voice ID.

        Args:
            name: Name for the variant (e.g., "Kagami Whisper")
            description: Description of desired changes
            prompt_strength: Transformation intensity

        Returns:
            RemixResult
        """
        if not self._kagami_voice_id:
            return RemixResult(
                success=False,
                error="Kagami voice ID not configured",
            )

        return await self.remix_voice(
            voice_id=self._kagami_voice_id,
            name=name,
            description=description,
            prompt_strength=prompt_strength,
        )

    async def list_remixable_voices(self) -> list[RemixableVoice]:
        """List all voices that can be remixed.

        Returns:
            List of RemixableVoice objects
        """
        if not self._initialized:
            await self.initialize()

        return list(self._voices_cache.values())

    async def get_kagami_variants(self) -> list[RemixableVoice]:
        """Get all Kagami voice variants (original + remixes).

        Returns:
            List of voices related to Kagami
        """
        if not self._kagami_voice_id:
            return []

        return [v for v in self._voices_cache.values() if v.is_kagami or "kagami" in v.name.lower()]

    def get_stats(self) -> dict[str, Any]:
        """Get remixing statistics."""
        return {
            **self._stats,
            "cached_voices": len(self._voices_cache),
            "kagami_voice_id": self._kagami_voice_id,
            "initialized": self._initialized,
        }


# =============================================================================
# Singleton and Factory
# =============================================================================

_voice_remixer: VoiceRemixer | None = None
_init_lock = asyncio.Lock()


async def get_voice_remixer() -> VoiceRemixer:
    """Get the singleton VoiceRemixer instance.

    Returns:
        Initialized VoiceRemixer
    """
    global _voice_remixer

    if _voice_remixer is None:
        async with _init_lock:
            if _voice_remixer is None:
                _voice_remixer = VoiceRemixer()
                await _voice_remixer.initialize()

    return _voice_remixer


# =============================================================================
# Preset Remix Descriptions (for common transformations)
# =============================================================================

REMIX_PRESETS: dict[str, dict[str, Any]] = {
    # Gender/age modifications
    "younger": {
        "description": "Make the voice sound younger and more youthful",
        "prompt_strength": 0.5,
    },
    "older": {
        "description": "Make the voice sound more mature and experienced",
        "prompt_strength": 0.5,
    },
    "more_masculine": {
        "description": "Make the voice deeper and more masculine",
        "prompt_strength": 0.6,
    },
    "more_feminine": {
        "description": "Make the voice softer and more feminine",
        "prompt_strength": 0.6,
    },
    # Style modifications
    "whisper": {
        "description": "Make the voice softer and more intimate, like whispering",
        "prompt_strength": 0.7,
    },
    "dramatic": {
        "description": "Make the voice more theatrical and dramatic",
        "prompt_strength": 0.6,
    },
    "professional": {
        "description": "Make the voice more authoritative and professional",
        "prompt_strength": 0.4,
    },
    "casual": {
        "description": "Make the voice more relaxed and conversational",
        "prompt_strength": 0.4,
    },
    "energetic": {
        "description": "Make the voice more upbeat and energetic",
        "prompt_strength": 0.5,
    },
    "calm": {
        "description": "Make the voice calmer and more soothing",
        "prompt_strength": 0.5,
    },
    # Accent modifications
    "british": {
        "description": "Add a warm British accent",
        "prompt_strength": 0.6,
    },
    "american": {
        "description": "Add a neutral American accent",
        "prompt_strength": 0.5,
    },
    "australian": {
        "description": "Add an Australian accent",
        "prompt_strength": 0.6,
    },
    # Quality improvements
    "warmer": {
        "description": "Make the voice warmer and more resonant",
        "prompt_strength": 0.3,
    },
    "clearer": {
        "description": "Make the voice clearer and more articulate",
        "prompt_strength": 0.3,
    },
    "richer": {
        "description": "Add more depth and richness to the voice",
        "prompt_strength": 0.4,
    },
}


async def quick_remix(
    voice_id: str,
    preset: str,
    name: str | None = None,
) -> RemixResult:
    """Quick remix using a preset.

    Args:
        voice_id: Voice to remix
        preset: Preset name from REMIX_PRESETS
        name: Optional name (defaults to "Voice - Preset")

    Returns:
        RemixResult
    """
    if preset not in REMIX_PRESETS:
        raise ValueError(f"Unknown preset: {preset}. Available: {list(REMIX_PRESETS.keys())}")

    settings = REMIX_PRESETS[preset]
    remixer = await get_voice_remixer()

    return await remixer.remix_voice(
        voice_id=voice_id,
        name=name or f"Voice - {preset.title()}",
        description=settings["description"],
        prompt_strength=settings["prompt_strength"],
    )


__all__ = [
    "REMIX_PRESETS",
    "PromptStrength",
    "RemixPreview",
    "RemixResult",
    "RemixableVoice",
    "VoiceRemixer",
    "get_voice_remixer",
    "quick_remix",
]
