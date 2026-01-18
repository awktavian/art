"""Symphony Generator — LLM-Powered Orchestral Composition.

Generate orchestral music from text prompts using:
- MusicGen for melody/harmony generation
- Audio-to-MIDI conversion
- BBC Symphony Orchestra rendering
- Expression engine for humanization
- VBAP spatialization for Dolby Atmos

Example:
    from kagami.forge.modules.audio import generate_symphony

    result = await generate_symphony(
        "A triumphant fanfare with brass and timpani",
        duration=30,
        style="film_score"
    )

Colony: Forge (e₂)
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

import numpy as np

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================


class CompositionStyle(Enum):
    """Orchestral composition style."""

    ROMANTIC = "romantic"  # Brahms, Tchaikovsky, sweeping melodies
    BAROQUE = "baroque"  # Bach, Handel, counterpoint
    CLASSICAL = "classical"  # Mozart, Haydn, balanced form
    IMPRESSIONIST = "impressionist"  # Debussy, Ravel, colorful
    FILM_SCORE = "film_score"  # Williams, Zimmer, dramatic
    MINIMALIST = "minimalist"  # Reich, Glass, repetitive patterns
    CONTEMPORARY = "contemporary"  # Modern orchestral
    EPIC = "epic"  # Trailer music, powerful


# Style-specific prompt templates for MusicGen
STYLE_PROMPTS: dict[CompositionStyle, str] = {
    CompositionStyle.ROMANTIC: (
        "romantic orchestral music with sweeping strings, "
        "expressive melodies, rich harmonies, emotional"
    ),
    CompositionStyle.BAROQUE: (
        "baroque orchestral music with harpsichord, strings, "
        "counterpoint, ornamental, precise rhythm"
    ),
    CompositionStyle.CLASSICAL: (
        "classical orchestral music with balanced phrases, "
        "elegant melodies, clear structure, Mozart style"
    ),
    CompositionStyle.IMPRESSIONIST: (
        "impressionist orchestral music with colorful harmonies, "
        "flowing textures, harp, woodwinds, ethereal"
    ),
    CompositionStyle.FILM_SCORE: (
        "cinematic orchestral music with dramatic brass, epic strings, timpani, powerful, emotional"
    ),
    CompositionStyle.MINIMALIST: (
        "minimalist orchestral music with repeating patterns, gradual changes, hypnotic, meditative"
    ),
    CompositionStyle.CONTEMPORARY: (
        "modern orchestral music with complex harmonies, varied textures, innovative"
    ),
    CompositionStyle.EPIC: (
        "epic trailer music with massive orchestra, "
        "thunderous percussion, heroic brass, soaring strings"
    ),
}


@dataclass
class SymphonyConfig:
    """Symphony generation configuration.

    Strong defaults for high-quality orchestral output:
    - MusicGen medium model (balance of quality and speed)
    - Expression always enabled with romantic style
    - Full instrumentation
    - BBC Symphony Orchestra rendering (primary)
    - 5.1.4 Atmos spatialization
    """

    # Duration and style
    duration_sec: float = 30.0  # Target duration (30s = ~1-2min generation)
    style: CompositionStyle = CompositionStyle.FILM_SCORE  # Cinematic default
    tempo_bpm: int = 100  # Moderate tempo for flexibility
    key: str = "C major"  # Default key

    # Instrumentation - full orchestra by default
    use_strings: bool = True
    use_brass: bool = True
    use_woodwinds: bool = True
    use_percussion: bool = True

    # MusicGen settings - optimized for quality
    musicgen_model: str = "facebook/musicgen-medium"  # Medium = good quality + reasonable speed
    cfg_coef: float = 3.5  # Higher = more prompt adherence (3.0-4.0 optimal)
    top_k: int = 250  # Diversity in sampling
    top_p: float = 0.0  # Disabled when using top_k
    temperature: float = 1.0  # Standard temperature

    # Expression - ALWAYS enabled for musical quality
    apply_expression: bool = True  # Never disable - critical for realism
    expression_style: str = "film_score"  # Match default composition style

    # Output - high quality defaults
    render_spatial: bool = True  # Always render to 5.1.4 Atmos
    output_format: str = "wav"  # Lossless output
    prefer_bbc: bool = True  # Always prefer BBC Symphony Orchestra


@dataclass
class SymphonyResult:
    """Result of symphony generation."""

    success: bool
    audio_path: Path | None = None
    midi_path: Path | None = None
    duration_sec: float = 0.0
    generation_time_sec: float = 0.0
    render_time_sec: float = 0.0
    style: CompositionStyle = CompositionStyle.FILM_SCORE
    prompt_used: str = ""
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


# =============================================================================
# MusicGen Integration
# =============================================================================


class MusicGenWrapper:
    """Wrapper for Meta's MusicGen model.

    Handles model loading, generation, and audio output.
    Falls back to placeholder if audiocraft not installed.
    """

    def __init__(self, model_name: str = "facebook/musicgen-medium"):
        self.model_name = model_name
        self._model = None
        self._available = False

    async def initialize(self) -> bool:
        """Initialize MusicGen model."""
        try:
            from audiocraft.models import MusicGen

            logger.info(f"Loading MusicGen: {self.model_name}")
            self._model = MusicGen.get_pretrained(self.model_name)
            self._available = True
            logger.info("✓ MusicGen loaded")
            return True
        except ImportError:
            logger.warning("audiocraft not installed. Install with: pip install audiocraft")
            self._available = False
            return False
        except Exception as e:
            logger.error(f"MusicGen init failed: {e}")
            self._available = False
            return False

    @property
    def is_available(self) -> bool:
        """Check if MusicGen is available."""
        return self._available

    async def generate(
        self,
        prompt: str,
        duration_sec: float = 30.0,
        cfg_coef: float = 3.0,
        top_k: int = 250,
        temperature: float = 1.0,
    ) -> np.ndarray | None:
        """Generate audio from text prompt.

        Args:
            prompt: Text description of music to generate
            duration_sec: Target duration in seconds
            cfg_coef: Classifier-free guidance coefficient
            top_k: Top-k sampling
            temperature: Sampling temperature

        Returns:
            Audio array (sample_rate=32000) or None if failed
        """
        if not self._available:
            logger.error("MusicGen not available")
            return None

        try:
            self._model.set_generation_params(
                duration=duration_sec,
                use_sampling=True,
                top_k=top_k,
                cfg_coef=cfg_coef,
                temperature=temperature,
            )

            logger.info(f"🎵 Generating {duration_sec}s: {prompt[:50]}...")
            wav = self._model.generate([prompt], progress=True)

            # Convert to numpy
            audio = wav[0].cpu().numpy()
            if len(audio.shape) > 1:
                audio = audio.squeeze()

            return audio

        except Exception as e:
            logger.error(f"MusicGen generation failed: {e}")
            return None

    @property
    def sample_rate(self) -> int:
        """MusicGen output sample rate."""
        return 32000


# =============================================================================
# Audio to MIDI Conversion
# =============================================================================


async def audio_to_midi(
    audio: np.ndarray,
    sample_rate: int = 32000,
    output_path: Path | None = None,
) -> Path | None:
    """Convert audio to MIDI using basic-pitch.

    Args:
        audio: Audio array
        sample_rate: Sample rate
        output_path: Output MIDI path

    Returns:
        Path to generated MIDI file
    """
    try:
        from basic_pitch.inference import predict

        logger.info("Converting audio to MIDI...")

        # basic-pitch expects a file path, so save temporarily
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            import soundfile as sf

            temp_wav = Path(f.name)
            sf.write(str(temp_wav), audio, sample_rate)

        # Run pitch detection
        _model_output, midi_data, _note_events = predict(str(temp_wav))

        # Save MIDI
        if output_path is None:
            output_path = Path(tempfile.mkdtemp()) / "output.mid"

        midi_data.write(str(output_path))

        # Cleanup
        temp_wav.unlink()

        logger.info(f"✓ MIDI generated: {output_path}")
        return output_path

    except ImportError:
        logger.warning("basic-pitch not installed. Install with: pip install basic-pitch")
        return None
    except Exception as e:
        logger.error(f"Audio to MIDI conversion failed: {e}")
        return None


# =============================================================================
# Prompt Building
# =============================================================================


def build_prompt(
    user_prompt: str,
    style: CompositionStyle,
    config: SymphonyConfig,
) -> str:
    """Build MusicGen prompt from user input and style.

    Args:
        user_prompt: User's description
        style: Composition style
        config: Symphony configuration

    Returns:
        Full prompt for MusicGen
    """
    # Base style prompt
    style_prompt = STYLE_PROMPTS.get(style, STYLE_PROMPTS[CompositionStyle.FILM_SCORE])

    # Instrumentation
    instruments = []
    if config.use_strings:
        instruments.append("strings")
    if config.use_brass:
        instruments.append("brass")
    if config.use_woodwinds:
        instruments.append("woodwinds")
    if config.use_percussion:
        instruments.append("percussion")

    instruments_str = ", ".join(instruments) if instruments else "full orchestra"

    # Combine
    prompt_parts = [
        style_prompt,
        f"with {instruments_str}",
        user_prompt,
        f"tempo around {config.tempo_bpm} BPM",
    ]

    return ", ".join(prompt_parts)


# =============================================================================
# Symphony Generator
# =============================================================================


class SymphonyGenerator:
    """LLM-powered orchestral music generator.

    Generates symphonic music from text prompts by:
    1. Using MusicGen to generate raw audio
    2. Converting to MIDI for orchestration
    3. Rendering through BBC Symphony Orchestra
    4. Applying expression and humanization
    5. Spatializing to 5.1.4 Atmos
    """

    def __init__(self, config: SymphonyConfig | None = None):
        self.config = config or SymphonyConfig()
        self._musicgen: MusicGenWrapper | None = None
        self._orchestra = None
        self._expression_engine = None

    async def initialize(self) -> bool:
        """Initialize all components."""
        # Initialize MusicGen
        self._musicgen = MusicGenWrapper(self.config.musicgen_model)
        musicgen_ok = await self._musicgen.initialize()

        # Initialize Orchestra
        try:
            from kagami.core.effectors.orchestra import Config, Orchestra, RenderMode

            # Use AUTO mode which prefers BBC if available
            self._orchestra = Orchestra(Config(render_mode=RenderMode.AUTO))
            await self._orchestra.init()
        except ImportError:
            logger.warning("Orchestra not available")
            self._orchestra = None

        # Initialize Expression Engine
        try:
            from kagami.core.effectors.expression_engine import ExpressionEngine

            self._expression_engine = ExpressionEngine()
        except ImportError:
            logger.warning("Expression engine not available")
            self._expression_engine = None

        return musicgen_ok

    async def generate(
        self,
        prompt: str,
        output_dir: Path | None = None,
    ) -> SymphonyResult:
        """Generate symphonic music from text prompt.

        Args:
            prompt: Text description of desired music
            output_dir: Output directory (auto-generated if None)

        Returns:
            SymphonyResult with paths to generated files
        """
        t0 = time.perf_counter()

        # Setup output directory
        if output_dir is None:
            output_dir = Path.home() / ".kagami" / "symphony" / "generated"
        output_dir.mkdir(parents=True, exist_ok=True)

        # Generate timestamp-based filename
        timestamp = int(time.time())
        base_name = f"symphony_{timestamp}"

        try:
            # Build full prompt
            full_prompt = build_prompt(prompt, self.config.style, self.config)
            logger.info(f"🎼 Generating symphony: {prompt}")
            logger.debug(f"Full prompt: {full_prompt}")

            # Step 1: Generate with MusicGen
            if not self._musicgen or not self._musicgen.is_available:
                return SymphonyResult(
                    success=False,
                    error="MusicGen not available. Install audiocraft.",
                    prompt_used=full_prompt,
                )

            audio = await self._musicgen.generate(
                full_prompt,
                duration_sec=self.config.duration_sec,
                cfg_coef=self.config.cfg_coef,
                top_k=self.config.top_k,
                temperature=self.config.temperature,
            )

            if audio is None:
                return SymphonyResult(
                    success=False,
                    error="MusicGen generation failed",
                    prompt_used=full_prompt,
                )

            generation_time = time.perf_counter() - t0
            logger.info(f"✓ Generated {len(audio) / 32000:.1f}s audio in {generation_time:.1f}s")

            # Step 2: Convert to MIDI
            midi_path = output_dir / f"{base_name}.mid"
            midi_result = await audio_to_midi(audio, self._musicgen.sample_rate, midi_path)

            # Step 3: Apply expression (if MIDI conversion succeeded)
            if midi_result and self._expression_engine and self.config.apply_expression:
                try:
                    from kagami.core.effectors.expression_engine import ExpressionStyle

                    style_map = {
                        "romantic": ExpressionStyle.ROMANTIC,
                        "baroque": ExpressionStyle.BAROQUE,
                        "classical": ExpressionStyle.CLASSICAL,
                        "modern": ExpressionStyle.MODERN,
                        "film_score": ExpressionStyle.FILM_SCORE,
                        "minimalist": ExpressionStyle.MINIMALIST,
                    }
                    expr_style = style_map.get(
                        self.config.expression_style, ExpressionStyle.ROMANTIC
                    )
                    self._expression_engine.set_style(expr_style)

                    expressed_midi = output_dir / f"{base_name}_expr.mid"
                    await self._expression_engine.process_midi(midi_path, expressed_midi)
                    midi_path = expressed_midi
                except Exception as e:
                    logger.warning(f"Expression engine failed: {e}")

            # Step 4: Render through Orchestra (if available and MIDI exists)
            audio_path = output_dir / f"{base_name}.wav"
            render_time = 0.0

            if midi_result and self._orchestra:
                try:
                    render_t0 = time.perf_counter()
                    result = await self._orchestra.render(midi_path, audio_path)
                    render_time = time.perf_counter() - render_t0

                    if result.success:
                        audio_path = result.path
                        logger.info(f"✓ Rendered through Orchestra in {render_time:.1f}s")
                    else:
                        # Fallback: save MusicGen audio directly
                        logger.warning(f"Orchestra render failed: {result.error}")
                        await self._save_musicgen_audio(audio, audio_path)
                except Exception as e:
                    logger.warning(f"Orchestra failed: {e}")
                    await self._save_musicgen_audio(audio, audio_path)
            else:
                # No Orchestra - save MusicGen audio directly
                await self._save_musicgen_audio(audio, audio_path)

            total_time = time.perf_counter() - t0

            return SymphonyResult(
                success=True,
                audio_path=audio_path,
                midi_path=midi_path,
                duration_sec=len(audio) / 32000,
                generation_time_sec=generation_time,
                render_time_sec=render_time,
                style=self.config.style,
                prompt_used=full_prompt,
                metadata={
                    "model": self.config.musicgen_model,
                    "cfg_coef": self.config.cfg_coef,
                    "total_time": total_time,
                },
            )

        except Exception as e:
            logger.error(f"Symphony generation failed: {e}", exc_info=True)
            return SymphonyResult(
                success=False,
                error=str(e),
                prompt_used=prompt,
            )

    async def _save_musicgen_audio(self, audio: np.ndarray, path: Path) -> None:
        """Save MusicGen audio directly to file."""
        import soundfile as sf

        # Resample to 48kHz for consistency
        from scipy import signal

        resampled = signal.resample(audio, int(len(audio) * 48000 / 32000))
        sf.write(str(path), resampled, 48000)
        logger.info(f"✓ Saved MusicGen audio: {path}")


# =============================================================================
# Singleton and API
# =============================================================================

_generator: SymphonyGenerator | None = None


async def get_symphony_generator(
    config: SymphonyConfig | None = None,
) -> SymphonyGenerator:
    """Get or create symphony generator singleton."""
    global _generator
    if _generator is None or config is not None:
        _generator = SymphonyGenerator(config)
        await _generator.initialize()
    return _generator


async def generate_symphony(
    prompt: str,
    duration: float = 30.0,
    style: str | CompositionStyle = "film_score",
    instruments: list[str] | None = None,
    output_dir: Path | str | None = None,
    **kwargs,
) -> SymphonyResult:
    """Generate orchestral music from text prompt.

    This is the main API for symphony generation.

    Args:
        prompt: Description of desired music
        duration: Target duration in seconds
        style: Composition style (romantic, baroque, classical, etc.)
        instruments: List of instrument families to use
        output_dir: Output directory
        **kwargs: Additional config options

    Returns:
        SymphonyResult with generated files

    Examples:
        # Simple generation
        result = await generate_symphony("A triumphant fanfare")

        # With specific style
        result = await generate_symphony(
            "Melancholic cello solo with string accompaniment",
            style="romantic",
            duration=60
        )

        # With instrument selection
        result = await generate_symphony(
            "Peaceful morning",
            instruments=["strings", "woodwinds"],
            style="impressionist"
        )
    """
    # Parse style
    if isinstance(style, str):
        style_map = {
            "romantic": CompositionStyle.ROMANTIC,
            "baroque": CompositionStyle.BAROQUE,
            "classical": CompositionStyle.CLASSICAL,
            "impressionist": CompositionStyle.IMPRESSIONIST,
            "film_score": CompositionStyle.FILM_SCORE,
            "minimalist": CompositionStyle.MINIMALIST,
            "contemporary": CompositionStyle.CONTEMPORARY,
            "epic": CompositionStyle.EPIC,
        }
        comp_style = style_map.get(style.lower(), CompositionStyle.FILM_SCORE)
    else:
        comp_style = style

    # Build config
    config = SymphonyConfig(
        duration_sec=duration,
        style=comp_style,
        **kwargs,
    )

    # Handle instruments
    if instruments:
        config.use_strings = "strings" in instruments
        config.use_brass = "brass" in instruments
        config.use_woodwinds = "woodwinds" in instruments
        config.use_percussion = "percussion" in instruments

    # Get generator and generate
    generator = await get_symphony_generator(config)

    out_dir = Path(output_dir) if output_dir else None
    return await generator.generate(prompt, out_dir)


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "STYLE_PROMPTS",
    # Enums
    "CompositionStyle",
    "MusicGenWrapper",
    # Config
    "SymphonyConfig",
    # Classes
    "SymphonyGenerator",
    # Result
    "SymphonyResult",
    "audio_to_midi",
    "build_prompt",
    # Functions
    "generate_symphony",
    "get_symphony_generator",
]
