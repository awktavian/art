"""Orchestra Composer — Unified End-to-End Music Pipeline.

Complete automated pipeline from text prompt to rendered orchestral audio:
    Prompt → LLM Generation → MIDI → Arrangement → Expression → BBC SO Render → Spatial Audio

Also supports:
    PDF Score → OMR → MIDI → [same pipeline]
    MIDI → Arrangement → Expression → BBC SO Render → Spatial Audio

This is the FULLY AUTOMATED RALPH system for orchestral music.

Usage:
    from kagami.forge.modules.audio.orchestra_composer import compose

    # From text prompt
    result = await compose(
        "A triumphant fanfare with brass and timpani",
        style="film_score",
        duration=30
    )

    # From existing MIDI
    result = await compose(
        midi_path="theme.mid",
        style="romantic"
    )

    # From PDF score
    result = await compose(
        score_path="beethoven_5.pdf",
        style="classical"
    )

Colony: Forge (e₂)
Created: January 2, 2026
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================


class ComposerStyle(Enum):
    """Overall composition/orchestration style."""

    ROMANTIC = "romantic"
    BAROQUE = "baroque"
    CLASSICAL = "classical"
    IMPRESSIONIST = "impressionist"
    FILM_SCORE = "film_score"
    MINIMALIST = "minimalist"
    EPIC = "epic"
    CONTEMPORARY = "contemporary"


class OutputType(Enum):
    """Primary output type."""

    AUDIO = "audio"  # Rendered audio (default)
    MIDI = "midi"  # Arranged MIDI only
    SCORE = "score"  # Sheet music PDF
    ALL = "all"  # All outputs


@dataclass
class ComposerConfig:
    """Orchestra Composer configuration."""

    # Style
    style: ComposerStyle = ComposerStyle.FILM_SCORE

    # Generation (if from prompt)
    duration_sec: float = 30.0
    tempo_bpm: int = 100
    key: str = "C major"

    # Score parsing (OMR)
    use_orchestral_parser: bool = True  # Use enhanced orchestral parser
    layout_hint: str | None = None  # romantic_orchestra, classical, etc.

    # Arrangement
    use_arranger: bool = True
    target_ensemble: str = "full"  # full, strings, chamber, quartet
    use_llm_arrangement: bool = True

    # Expression
    apply_expression: bool = True
    humanize: bool = True

    # Rendering
    render_audio: bool = True
    prefer_bbc: bool = True  # Use BBC Symphony Orchestra
    spatial_audio: bool = True  # 5.1.4 Atmos

    # Sheet music
    generate_score: bool = False
    score_title: str | None = None
    score_composer: str = "Kagami"

    # Output
    output_type: OutputType = OutputType.AUDIO
    output_dir: Path | None = None


@dataclass
class ComposerResult:
    """Result of composition pipeline."""

    success: bool

    # Outputs
    audio_path: Path | None = None
    midi_path: Path | None = None
    arranged_midi_path: Path | None = None
    score_path: Path | None = None

    # Metadata
    duration_sec: float = 0.0
    instruments: list[str] = field(default_factory=list)
    style: ComposerStyle = ComposerStyle.FILM_SCORE

    # Timing
    generation_time_sec: float = 0.0
    arrangement_time_sec: float = 0.0
    expression_time_sec: float = 0.0
    render_time_sec: float = 0.0
    total_time_sec: float = 0.0

    # Pipeline steps completed
    steps_completed: list[str] = field(default_factory=list)

    # Error info
    error: str | None = None
    failed_step: str | None = None

    # Extra metadata
    metadata: dict[str, Any] = field(default_factory=dict)


# =============================================================================
# Pipeline Steps
# =============================================================================


async def step_generate_from_prompt(
    prompt: str,
    config: ComposerConfig,
    output_dir: Path,
) -> tuple[Path | None, float]:
    """Generate MIDI from text prompt using MusicGen.

    Returns:
        Tuple of (midi_path, generation_time)
    """
    from kagami.forge.modules.audio.symphony_generator import (
        generate_symphony,
    )

    t0 = time.perf_counter()

    # Map composer style to symphony style
    style_map = {
        ComposerStyle.ROMANTIC: "romantic",
        ComposerStyle.BAROQUE: "baroque",
        ComposerStyle.CLASSICAL: "classical",
        ComposerStyle.IMPRESSIONIST: "impressionist",
        ComposerStyle.FILM_SCORE: "film_score",
        ComposerStyle.MINIMALIST: "minimalist",
        ComposerStyle.EPIC: "epic",
        ComposerStyle.CONTEMPORARY: "contemporary",
    }
    style = style_map.get(config.style, "film_score")

    result = await generate_symphony(
        prompt,
        duration=config.duration_sec,
        style=style,
        output_dir=output_dir,
    )

    elapsed = time.perf_counter() - t0

    if result.success and result.midi_path:
        return result.midi_path, elapsed
    else:
        logger.error(f"Symphony generation failed: {result.error}")
        return None, elapsed


async def step_parse_score(
    score_path: Path,
    output_dir: Path,
    use_orchestral_parser: bool = True,
    layout_hint: str | None = None,
) -> tuple[Path | None, float, dict[str, Any]]:
    """Parse PDF/image score to MIDI using enhanced OMR.

    Uses the new orchestral parser for complex scores with automatic
    system detection and group-level processing.

    Supports:
        - PDF files (multi-page)
        - Image files (PNG, JPG, TIFF - single page)

    Args:
        score_path: Path to score file
        output_dir: Output directory for MIDI
        use_orchestral_parser: Use enhanced orchestral parser (default True)
        layout_hint: Optional layout hint (romantic_orchestra, classical, etc.)

    Returns:
        Tuple of (midi_path, parse_time, metadata)
    """
    t0 = time.perf_counter()
    metadata: dict[str, Any] = {}

    try:
        suffix = score_path.suffix.lower()
        midi_path = output_dir / f"{score_path.stem}_parsed.mid"

        # Try orchestral parser first for complex scores
        if use_orchestral_parser:
            try:
                from kagami_virtuoso.score_parser.orchestral import (
                    LayoutHint,
                    parse_orchestral_score,
                )

                # Determine layout hint
                hint = LayoutHint.AUTO
                if layout_hint:
                    try:
                        hint = LayoutHint(layout_hint.lower())
                    except ValueError:
                        pass

                logger.info(f"🎼 Parsing with orchestral parser: {score_path.name}")
                logger.info(f"   Layout hint: {hint.value}")

                result = await parse_orchestral_score(
                    score_path,
                    layout_hint=hint,
                    use_ensemble=False,  # Start simple
                )

                elapsed = time.perf_counter() - t0

                if result.success and result.note_count > 0:
                    # Export merged result to MIDI
                    from kagami_virtuoso.score_parser.postprocessor import MIDIExporter

                    exporter = MIDIExporter()
                    exporter.export(result.merged_result, midi_path)

                    metadata = {
                        "parser": "orchestral",
                        "strategy": result.strategy_used,
                        "systems": len(result.page_results),
                        "notes": result.note_count,
                    }

                    logger.info(
                        f"✓ Orchestral parse: {result.note_count} notes, "
                        f"strategy={result.strategy_used} in {elapsed:.1f}s"
                    )

                    return midi_path, elapsed, metadata

                else:
                    logger.warning("Orchestral parser found no notes, falling back to standard")

            except ImportError as e:
                logger.warning(f"Orchestral parser not available: {e}")
            except Exception as e:
                logger.warning(f"Orchestral parser failed, falling back: {e}")

        # Fallback to standard parser
        if suffix in (".png", ".jpg", ".jpeg", ".tiff", ".tif"):
            from kagami_virtuoso.score_parser import ScoreParser
            from kagami_virtuoso.score_parser.postprocessor import MIDIExporter
            from PIL import Image

            logger.info(f"🎼 Parsing score image (standard): {score_path.name}")

            parser = ScoreParser(skip_on_error=True)
            image = Image.open(score_path)

            omr_result = parser.parse_image(image)

            elapsed = time.perf_counter() - t0

            if omr_result and omr_result.note_count > 0:
                exporter = MIDIExporter()
                exporter.export(omr_result, midi_path)

                metadata = {
                    "parser": "standard",
                    "notes": omr_result.note_count,
                    "staves": omr_result.num_staves,
                }

                logger.info(
                    f"✓ Image parsed: {omr_result.note_count} notes, "
                    f"{omr_result.num_staves} staves in {elapsed:.1f}s"
                )

                return midi_path, elapsed, metadata
            else:
                logger.error("Image parsing returned no notes")
                return None, elapsed, {"error": "no_notes"}

        elif suffix == ".pdf":
            from kagami_virtuoso.score_parser import parse_score

            logger.info(f"🎼 Parsing PDF score (standard): {score_path.name}")

            parsed = await parse_score(
                str(score_path),
                cache_dir=output_dir / "omr_cache",
                skip_on_error=True,
            )

            elapsed = time.perf_counter() - t0

            if parsed and parsed.note_count > 0:
                parsed.to_midi(midi_path, use_instrument_mapping=True)

                metadata = {
                    "parser": "standard",
                    "notes": parsed.note_count,
                    "pages": parsed.page_count,
                }

                logger.info(
                    f"✓ PDF parsed: {parsed.note_count} notes from "
                    f"{parsed.page_count} pages in {elapsed:.1f}s"
                )

                return midi_path, elapsed, metadata
            else:
                logger.error("PDF parsing returned no notes")
                return None, elapsed, {"error": "no_notes"}

        else:
            elapsed = time.perf_counter() - t0
            logger.error(f"Unsupported score format: {suffix}")
            return None, elapsed, {"error": f"unsupported_format:{suffix}"}

    except Exception as e:
        elapsed = time.perf_counter() - t0
        logger.error(f"Score parsing failed: {e}")
        return None, elapsed, {"error": str(e)}


async def step_arrange(
    midi_path: Path,
    config: ComposerConfig,
    output_dir: Path,
) -> tuple[Path | None, float, list[str]]:
    """Arrange MIDI for target ensemble.

    Returns:
        Tuple of (arranged_midi_path, arrangement_time, instruments_used)
    """
    from kagami.forge.modules.audio.arranger import (
        ArrangementStyle,
        TargetEnsemble,
        arrange,
    )

    t0 = time.perf_counter()

    # Map styles
    style_map = {
        ComposerStyle.ROMANTIC: ArrangementStyle.ROMANTIC,
        ComposerStyle.BAROQUE: ArrangementStyle.BAROQUE,
        ComposerStyle.CLASSICAL: ArrangementStyle.CLASSICAL,
        ComposerStyle.IMPRESSIONIST: ArrangementStyle.IMPRESSIONIST,
        ComposerStyle.FILM_SCORE: ArrangementStyle.FILM_SCORE,
        ComposerStyle.MINIMALIST: ArrangementStyle.MINIMALIST,
        ComposerStyle.EPIC: ArrangementStyle.FILM_SCORE,  # Epic uses film_score arrangement
        ComposerStyle.CONTEMPORARY: ArrangementStyle.FILM_SCORE,  # Contemporary uses film_score arrangement
    }
    arr_style = style_map.get(config.style, ArrangementStyle.FILM_SCORE)

    # Map ensemble
    ensemble_map = {
        "full": TargetEnsemble.FULL_ORCHESTRA,
        "strings": TargetEnsemble.STRINGS_ONLY,
        "chamber": TargetEnsemble.CHAMBER,
        "quartet": TargetEnsemble.STRING_QUARTET,
        "brass": TargetEnsemble.BRASS_BAND,
        "winds": TargetEnsemble.WIND_ENSEMBLE,
    }
    ensemble = ensemble_map.get(config.target_ensemble, TargetEnsemble.FULL_ORCHESTRA)

    output_path = output_dir / f"{midi_path.stem}_arranged.mid"

    result = await arrange(
        midi_path,
        output_path=output_path,
        style=arr_style,
        target_ensemble=ensemble,
        use_llm=config.use_llm_arrangement,
    )

    elapsed = time.perf_counter() - t0

    if result.success and result.output_path:
        return result.output_path, elapsed, result.instruments_used
    else:
        logger.error(f"Arrangement failed: {result.error}")
        return None, elapsed, []


async def step_apply_expression(
    midi_path: Path,
    config: ComposerConfig,
    output_dir: Path,
) -> tuple[Path | None, float]:
    """Apply expression and humanization to MIDI.

    Returns:
        Tuple of (expressed_midi_path, expression_time)
    """
    from kagami.core.effectors.expression_engine import (
        ExpressionStyle,
        add_expression,
    )

    t0 = time.perf_counter()

    # Map styles
    style_map = {
        ComposerStyle.ROMANTIC: ExpressionStyle.ROMANTIC,
        ComposerStyle.BAROQUE: ExpressionStyle.BAROQUE,
        ComposerStyle.CLASSICAL: ExpressionStyle.CLASSICAL,
        ComposerStyle.IMPRESSIONIST: ExpressionStyle.ROMANTIC,  # Similar
        ComposerStyle.FILM_SCORE: ExpressionStyle.FILM_SCORE,
        ComposerStyle.MINIMALIST: ExpressionStyle.MINIMALIST,
        ComposerStyle.EPIC: ExpressionStyle.FILM_SCORE,
        ComposerStyle.CONTEMPORARY: ExpressionStyle.MODERN,
    }
    expr_style = style_map.get(config.style, ExpressionStyle.ROMANTIC)

    output_path = output_dir / f"{midi_path.stem}_expressed.mid"

    await add_expression(
        midi_path,
        output_path=output_path,
        style=expr_style,
    )

    elapsed = time.perf_counter() - t0

    if output_path.exists():
        return output_path, elapsed
    else:
        # Expression might not modify file if no changes needed
        return midi_path, elapsed


async def step_render_audio(
    midi_path: Path,
    config: ComposerConfig,
    output_dir: Path,
) -> tuple[Path | None, float]:
    """Render MIDI to audio through BBC Symphony Orchestra.

    Returns:
        Tuple of (audio_path, render_time)
    """
    from kagami.core.effectors.orchestra import get_orchestra

    t0 = time.perf_counter()

    orchestra = await get_orchestra()
    output_path = output_dir / f"{midi_path.stem}_rendered.wav"

    result = await orchestra.render(midi_path, output_path)

    elapsed = time.perf_counter() - t0

    if result.success and result.path:
        return result.path, elapsed
    else:
        logger.error(f"Rendering failed: {result.error}")
        return None, elapsed


async def step_generate_score(
    midi_path: Path,
    config: ComposerConfig,
    output_dir: Path,
) -> tuple[Path | None, float]:
    """Generate sheet music PDF from MIDI.

    Returns:
        Tuple of (score_path, generation_time)
    """
    from kagami.forge.modules.audio.sheet_music import generate_sheet_music

    t0 = time.perf_counter()

    title = config.score_title or "Orchestral Score"

    result = await generate_sheet_music(
        midi_path,
        output_path=output_dir / f"{midi_path.stem}_score.pdf",
        title=title,
        composer=config.score_composer,
        output_format="pdf",
    )

    elapsed = time.perf_counter() - t0

    if result.success and result.output_path:
        return result.output_path, elapsed
    else:
        logger.warning(f"Score generation failed: {result.error}")
        return None, elapsed


# =============================================================================
# Main Pipeline
# =============================================================================


class OrchestraComposer:
    """Unified orchestra composition pipeline.

    Full automation from:
    - Text prompt → MIDI → Arrangement → Expression → BBC SO → Audio
    - PDF score → OMR → MIDI → Arrangement → Expression → BBC SO → Audio
    - Existing MIDI → Arrangement → Expression → BBC SO → Audio

    Optionally generates sheet music PDF at any stage.
    """

    def __init__(self, config: ComposerConfig | None = None):
        self.config = config or ComposerConfig()

    async def compose(
        self,
        prompt: str | None = None,
        midi_path: Path | str | None = None,
        score_path: Path | str | None = None,
    ) -> ComposerResult:
        """Run full composition pipeline.

        Exactly one of prompt, midi_path, or score_path must be provided.

        Args:
            prompt: Text description to generate music from
            midi_path: Existing MIDI file to orchestrate
            score_path: PDF/image score to parse and orchestrate

        Returns:
            ComposerResult with all generated outputs
        """
        t_total_start = time.perf_counter()

        # Validate inputs
        inputs = [prompt, midi_path, score_path]
        provided = sum(1 for x in inputs if x is not None)

        if provided == 0:
            return ComposerResult(
                success=False,
                error="Must provide prompt, midi_path, or score_path",
            )
        if provided > 1:
            return ComposerResult(
                success=False,
                error="Provide only one of: prompt, midi_path, or score_path",
            )

        # Setup output directory
        output_dir = self.config.output_dir
        if output_dir is None:
            output_dir = Path.home() / ".kagami" / "symphony" / "composed"
        output_dir.mkdir(parents=True, exist_ok=True)

        result = ComposerResult(
            success=False,
            style=self.config.style,
        )

        current_midi: Path | None = None
        instruments: list[str] = []

        try:
            # Step 1: Get initial MIDI
            if prompt:
                logger.info(f"🎼 Composing from prompt: {prompt[:50]}...")
                midi, gen_time = await step_generate_from_prompt(prompt, self.config, output_dir)
                result.generation_time_sec = gen_time

                if not midi:
                    result.error = "Music generation from prompt failed"
                    result.failed_step = "generate"
                    return result

                current_midi = midi
                result.midi_path = midi
                result.steps_completed.append("generate")

            elif score_path:
                score_path = Path(score_path)
                logger.info(f"📄 Parsing score: {score_path}")
                midi, parse_time, parse_metadata = await step_parse_score(
                    score_path,
                    output_dir,
                    use_orchestral_parser=self.config.use_orchestral_parser,
                    layout_hint=self.config.layout_hint,
                )
                result.generation_time_sec = parse_time
                result.metadata["parse"] = parse_metadata

                if not midi:
                    result.error = f"Score parsing failed: {parse_metadata.get('error', 'unknown')}"
                    result.failed_step = "parse_score"
                    return result

                current_midi = midi
                result.midi_path = midi
                result.steps_completed.append("parse_score")

            elif midi_path:
                current_midi = Path(midi_path)
                result.midi_path = current_midi
                result.steps_completed.append("load_midi")

            # Step 2: Arrangement
            if self.config.use_arranger and current_midi:
                logger.info("🎻 Arranging for orchestra...")
                arranged, arr_time, instruments = await step_arrange(
                    current_midi, self.config, output_dir
                )
                result.arrangement_time_sec = arr_time

                if arranged:
                    current_midi = arranged
                    result.arranged_midi_path = arranged
                    result.instruments = instruments
                    result.steps_completed.append("arrange")
                else:
                    logger.warning("Arrangement failed, continuing with original MIDI")

            # Step 3: Expression
            if self.config.apply_expression and current_midi:
                logger.info("🎭 Applying expression and humanization...")
                expressed, expr_time = await step_apply_expression(
                    current_midi, self.config, output_dir
                )
                result.expression_time_sec = expr_time

                if expressed:
                    current_midi = expressed
                    result.steps_completed.append("expression")

            # Step 4: Render audio
            if self.config.render_audio and current_midi:
                logger.info("🎵 Rendering through BBC Symphony Orchestra...")
                audio, render_time = await step_render_audio(current_midi, self.config, output_dir)
                result.render_time_sec = render_time

                if audio:
                    result.audio_path = audio
                    result.steps_completed.append("render")

                    # Get duration from audio
                    try:
                        import soundfile as sf

                        info = sf.info(str(audio))
                        result.duration_sec = info.duration
                    except Exception:
                        pass

            # Step 5: Generate score (optional)
            if self.config.generate_score and current_midi:
                logger.info("📜 Generating sheet music...")
                score, _score_time = await step_generate_score(
                    current_midi, self.config, output_dir
                )

                if score:
                    result.score_path = score
                    result.steps_completed.append("score")

            # Calculate total time
            result.total_time_sec = time.perf_counter() - t_total_start

            # Success if we completed at least generation and have an output
            has_output = result.audio_path or result.midi_path or result.score_path
            result.success = has_output

            if result.success:
                logger.info(f"✓ Composition complete in {result.total_time_sec:.1f}s")
                logger.info(f"   Steps: {' → '.join(result.steps_completed)}")
                if result.audio_path:
                    logger.info(f"   Audio: {result.audio_path}")
                if result.score_path:
                    logger.info(f"   Score: {result.score_path}")

            return result

        except Exception as e:
            logger.error(f"Composition failed: {e}", exc_info=True)
            result.error = str(e)
            result.total_time_sec = time.perf_counter() - t_total_start
            return result


# =============================================================================
# API Functions
# =============================================================================

_composer: OrchestraComposer | None = None


def get_composer(config: ComposerConfig | None = None) -> OrchestraComposer:
    """Get or create composer singleton."""
    global _composer
    if _composer is None or config is not None:
        _composer = OrchestraComposer(config)
    return _composer


async def compose(
    prompt: str | None = None,
    midi_path: Path | str | None = None,
    score_path: Path | str | None = None,
    style: str | ComposerStyle = "film_score",
    duration: float = 30.0,
    target_ensemble: str = "full",
    generate_score: bool = False,
    output_dir: Path | str | None = None,
    layout_hint: str | None = None,
    use_orchestral_parser: bool = True,
    **kwargs,
) -> ComposerResult:
    """Compose orchestral music — the main RALPH API.

    Full automated pipeline from text/MIDI/score to rendered orchestral audio.

    Args:
        prompt: Text description to generate music from
        midi_path: Existing MIDI file to orchestrate
        score_path: PDF/image score to parse and orchestrate
        style: Composition/orchestration style
        duration: Target duration (for generation)
        target_ensemble: Target ensemble (full, strings, chamber, quartet)
        generate_score: Also generate sheet music PDF
        output_dir: Output directory
        layout_hint: Layout hint for orchestral parser (romantic_orchestra, classical, etc.)
        use_orchestral_parser: Use enhanced orchestral parser for complex scores
        **kwargs: Additional ComposerConfig options

    Returns:
        ComposerResult with all outputs

    Examples:
        # Generate from prompt
        result = await compose(
            "A triumphant fanfare with brass and timpani",
            style="film_score",
            duration=30
        )

        # Orchestrate existing MIDI
        result = await compose(
            midi_path="theme.mid",
            style="romantic",
            target_ensemble="strings"
        )

        # Parse orchestral score with layout hint
        result = await compose(
            score_path="beethoven_5.pdf",
            style="classical",
            layout_hint="romantic_orchestra"
        )

        # Full output (audio + score)
        result = await compose(
            "Peaceful morning with strings",
            style="impressionist",
            generate_score=True
        )
    """
    # Parse style
    if isinstance(style, str):
        style = ComposerStyle(style.lower())

    # Build config
    config = ComposerConfig(
        style=style,
        duration_sec=duration,
        target_ensemble=target_ensemble,
        generate_score=generate_score,
        output_dir=Path(output_dir) if output_dir else None,
        layout_hint=layout_hint,
        use_orchestral_parser=use_orchestral_parser,
        **kwargs,
    )

    composer = get_composer(config)
    return await composer.compose(
        prompt=prompt,
        midi_path=midi_path,
        score_path=score_path,
    )


# =============================================================================
# Convenience Functions
# =============================================================================


async def compose_from_prompt(
    prompt: str,
    style: str = "film_score",
    duration: float = 30.0,
    **kwargs,
) -> ComposerResult:
    """Shorthand for composing from text prompt."""
    return await compose(prompt=prompt, style=style, duration=duration, **kwargs)


async def orchestrate_midi(
    midi_path: Path | str,
    style: str = "romantic",
    target_ensemble: str = "full",
    **kwargs,
) -> ComposerResult:
    """Shorthand for orchestrating existing MIDI."""
    return await compose(
        midi_path=midi_path,
        style=style,
        target_ensemble=target_ensemble,
        **kwargs,
    )


async def render_score(
    score_path: Path | str,
    style: str = "classical",
    **kwargs,
) -> ComposerResult:
    """Shorthand for rendering PDF score to audio."""
    return await compose(score_path=score_path, style=style, **kwargs)


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Config
    "ComposerConfig",
    # Result
    "ComposerResult",
    # Enums
    "ComposerStyle",
    # Main class
    "OrchestraComposer",
    "OutputType",
    # Main API
    "compose",
    # Convenience
    "compose_from_prompt",
    "get_composer",
    "orchestrate_midi",
    "render_score",
    "step_apply_expression",
    "step_arrange",
    # Pipeline steps (for advanced use)
    "step_generate_from_prompt",
    "step_generate_score",
    "step_parse_score",
    "step_render_audio",
]
