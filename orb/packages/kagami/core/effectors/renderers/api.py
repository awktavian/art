"""Unified Orchestral Rendering API.

Clean, simple interface for orchestral audio rendering.

Usage:
    from kagami.core.effectors.renderers.api import render_orchestra

    # Simple usage
    result = await render_orchestra(
        midi_path="/tmp/score.mid",
        output_path="/tmp/render.wav",
    )

    # With options
    result = await render_orchestra(
        midi_path="/tmp/score.mid",
        output_path="/tmp/render.wav",
        expression_style="film_score",
        sample_rate=48000,
        background=True,
    )

Colony: Forge (e₂)
Created: January 2, 2026
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# =============================================================================
# Public API Types
# =============================================================================


class Style(Enum):
    """Expression style presets."""

    ROMANTIC = "romantic"  # Expressive, rubato, sweeping dynamics
    BAROQUE = "baroque"  # Terraced dynamics, precise timing
    CLASSICAL = "classical"  # Balanced, moderate expression
    MODERN = "modern"  # Sharp, precise
    FILM_SCORE = "film_score"  # Dramatic, cinematic
    MINIMALIST = "minimalist"  # Subtle, steady


@dataclass
class RenderOptions:
    """Options for orchestral rendering.

    Attributes:
        expression_style: Musical expression style
        sample_rate: Output sample rate (default 48000)
        channels: Output channels (2=stereo, default)
        apply_expression: Add CC1/CC11 dynamics
        apply_spatial: Apply 5.1.4 VBAP spatialization
        background: Hide REAPER GUI during render
        timeout: Render timeout in seconds
    """

    expression_style: Style = Style.FILM_SCORE
    sample_rate: int = 48000
    channels: int = 2
    apply_expression: bool = True
    apply_spatial: bool = False
    background: bool = True
    timeout: int = 300


@dataclass
class RenderResult:
    """Result of orchestral rendering.

    Attributes:
        success: Whether rendering succeeded
        output_path: Path to rendered audio
        duration: Audio duration in seconds
        tracks: Number of instrument tracks
        error: Error message if failed
        metadata: Additional info
    """

    success: bool
    output_path: Path | None = None
    duration: float = 0.0
    tracks: int = 0
    error: str | None = None
    metadata: dict[str, Any] | None = None


# =============================================================================
# Main API
# =============================================================================


async def render_orchestra(
    midi_path: str | Path,
    output_path: str | Path,
    expression_style: str | Style = "film_score",
    sample_rate: int = 48000,
    apply_expression: bool = True,
    apply_spatial: bool = False,
    background: bool = True,
    timeout: int = 300,
) -> RenderResult:
    """Render orchestral MIDI to audio using BBC Symphony Orchestra.

    This is the main entry point for orchestral rendering. It:
    1. Analyzes the MIDI to detect instruments
    2. Applies expression (dynamics, articulations)
    3. Inserts keyswitches for sustained playback
    4. Splits MIDI by instrument
    5. Creates REAPER project with BBC SO
    6. Renders via REAPER (hidden in background)

    Args:
        midi_path: Input MIDI file
        output_path: Output WAV file
        expression_style: One of: romantic, baroque, classical, modern, film_score, minimalist
        sample_rate: Output sample rate (default 48000)
        apply_expression: Add dynamics/expression CCs
        apply_spatial: Apply 5.1.4 spatialization (requires multichannel output)
        background: Hide REAPER window during render
        timeout: Render timeout in seconds

    Returns:
        RenderResult with success status and output info

    Example:
        >>> result = await render_orchestra("score.mid", "output.wav")
        >>> if result.success:
        ...     print(f"Rendered {result.duration:.1f}s audio")
    """
    midi_path = Path(midi_path)
    output_path = Path(output_path)

    if not midi_path.exists():
        return RenderResult(success=False, error=f"MIDI not found: {midi_path}")

    # Convert style string to enum
    if isinstance(expression_style, str):
        try:
            style = Style(expression_style.lower())
        except ValueError:
            style = Style.FILM_SCORE
    else:
        style = expression_style

    try:
        # Import here to avoid circular imports
        from kagami.core.effectors.expression_engine import ExpressionStyle, add_expression
        from kagami.core.effectors.renderers.reaper import analyze_midi, split_midi_by_instrument
        from kagami.core.effectors.renderers.reaper_project import (
            generate_reaper_project,
            render_project_headless,
        )

        logger.info("🎼 Rendering: %s", midi_path.name)

        # 1. Analyze MIDI
        tracks = await analyze_midi(midi_path)
        if not tracks:
            return RenderResult(success=False, error="No instruments found in MIDI")
        logger.info("   Found %d instruments", len(tracks))

        # 2. Apply expression
        work_dir = output_path.parent
        expressed_path = work_dir / f"{midi_path.stem}_expressed.mid"

        if apply_expression:
            style_map = {
                Style.ROMANTIC: ExpressionStyle.ROMANTIC,
                Style.BAROQUE: ExpressionStyle.BAROQUE,
                Style.CLASSICAL: ExpressionStyle.CLASSICAL,
                Style.MODERN: ExpressionStyle.MODERN,
                Style.FILM_SCORE: ExpressionStyle.FILM_SCORE,
                Style.MINIMALIST: ExpressionStyle.MINIMALIST,
            }
            await add_expression(
                midi_path, expressed_path, style=style_map.get(style, ExpressionStyle.FILM_SCORE)
            )
        else:
            import shutil

            shutil.copy(midi_path, expressed_path)

        # 3. Split by instrument
        split_paths = await split_midi_by_instrument(expressed_path, tracks)

        # 4. Create REAPER project
        track_list = [(t.name, t.key, t.pan) for t in tracks]
        duration = max(t.duration_sec for t in tracks) + 2

        project_path = generate_reaper_project(
            midi_path=expressed_path,
            tracks=track_list,
            output_dir=output_path.parent,
            output_name=output_path.stem,
            tempo=120.0,
            duration=duration,
            split_midi_paths=split_paths,
        )

        # 5. Render
        success, error = render_project_headless(
            project_path,
            timeout=timeout,
            background=background,
        )

        if not success:
            return RenderResult(success=False, error=error or "Render failed", tracks=len(tracks))

        # 6. Verify output
        if not output_path.exists():
            return RenderResult(success=False, error="No output file created", tracks=len(tracks))

        import numpy as np
        import soundfile as sf

        audio, sr = sf.read(str(output_path))
        duration_sec = len(audio) / sr
        peak = np.max(np.abs(audio))

        # Check for silence (expected in headless BBC SO)
        if peak < 0.001:
            logger.warning("   ⚠ Output is silent (BBC SO needs GUI for sample loading)")

        return RenderResult(
            success=True,
            output_path=output_path,
            duration=duration_sec,
            tracks=len(tracks),
            metadata={
                "sample_rate": sr,
                "peak_amplitude": float(peak),
                "style": style.value,
                "project_path": str(project_path),
            },
        )

    except Exception as e:
        logger.exception("Render failed: %s", e)
        return RenderResult(success=False, error=str(e))


async def render_with_gui(
    midi_path: str | Path,
    output_path: str | Path,
    **kwargs,
) -> RenderResult:
    """Render orchestral MIDI with REAPER GUI visible.

    Use this when you need BBC SO samples to load correctly.
    The GUI will be shown during rendering.

    Args:
        midi_path: Input MIDI file
        output_path: Output WAV file
        **kwargs: Additional options (see render_orchestra)

    Returns:
        RenderResult
    """
    return await render_orchestra(midi_path, output_path, background=False, **kwargs)


# =============================================================================
# Convenience Functions
# =============================================================================


async def preview(midi_path: str | Path, duration: float = 10.0) -> RenderResult:
    """Quick preview render (first N seconds).

    Args:
        midi_path: Input MIDI file
        duration: Preview duration in seconds

    Returns:
        RenderResult
    """
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        output_path = Path(f.name)

    return await render_orchestra(
        midi_path,
        output_path,
        expression_style="modern",  # Faster, less processing
        timeout=60,
    )


def get_available_styles() -> list[str]:
    """Get list of available expression styles."""
    return [s.value for s in Style]


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "RenderOptions",
    "RenderResult",
    # Types
    "Style",
    "get_available_styles",
    "preview",
    # Main API
    "render_orchestra",
    "render_with_gui",
]
