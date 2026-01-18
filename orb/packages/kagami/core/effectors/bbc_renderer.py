"""BBC Symphony Orchestra Renderer — High-quality orchestral rendering.

This is the primary rendering path for orchestral audio, using BBC Symphony
Orchestra VST through REAPER.

Pipeline:
1. MIDI Analysis → Detect sections, instruments, articulations
2. Expression Engine → Add dynamics (CC1), expression (CC11), keyswitches
3. RfxChain Generation → Create full-state BBC SO FX chains per instrument
4. REAPER Project → Multi-track project with spatial panning
5. REAPER Render → WAV output via CLI
6. Spatial Audio → 5.1.4 spatialization via VBAP

Created: January 1, 2026
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
from scipy import signal

from kagami.core.effectors.bbc_instruments import (
    BBC_CATALOG,
    Section,
    find_instrument_by_gm_program,
)
from kagami.core.effectors.expression_engine import (
    ExpressionStyle,
    add_expression,
    apply_keyswitches_to_file,
)
from kagami.core.effectors.renderers import (
    BaseRenderer,
    register_renderer,
)
from kagami.core.effectors.renderers import (
    RenderConfig as BaseRenderConfig,
)
from kagami.core.effectors.renderers import (
    RenderResult as BaseRenderResult,
)
from kagami.core.effectors.rfxchain_generator import (
    generate_reaper_project,
    get_rfxchain_path,
)
from kagami.core.effectors.vbap_core import (
    CH_LFE,
    NUM_CH,
    Pos3D,
    vbap_10ch,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# ============================================================================
# Constants
# ============================================================================

SAMPLE_RATE = 48000
REAPER_APP = Path("/Applications/REAPER.app/Contents/MacOS/REAPER")
BBC_VST3 = Path("/Library/Audio/Plug-Ins/VST3/BBC Symphony Orchestra.vst3")

WORK_DIR = Path.home() / ".kagami" / "symphony"
OUTPUT_DIR = WORK_DIR / "rendered"
CACHE_DIR = WORK_DIR / "reaper" / "instruments"


# ============================================================================
# Data Classes
# ============================================================================


@dataclass
class InstrumentTrack:
    """Information about a single instrument track."""

    name: str
    key: str  # BBC_CATALOG key
    section: Section
    position: Pos3D
    note_count: int
    duration_sec: float
    channel: int = 0
    pan: float = 0.0  # -1.0 (left) to 1.0 (right)


@dataclass
class BBCRenderResult:
    """Result of a BBC render operation."""

    success: bool
    path: Path | None = None
    duration_sec: float = 0.0
    render_time_sec: float = 0.0
    tracks: int = 0
    channels: int = NUM_CH
    error: str | None = None
    track_info: list[InstrumentTrack] = field(default_factory=list)


# ============================================================================
# MIDI Analysis
# ============================================================================


async def analyze_midi(midi_path: Path) -> list[InstrumentTrack]:
    """Analyze MIDI file to determine instruments and sections.

    Priority for instrument detection:
    1. Track name matching BBC_CATALOG key (e.g., "violins_2")
    2. Filename containing instrument key (e.g., "violins_2_virtuoso.mid")
    3. GM program number lookup
    4. Default to violins_1

    Args:
        midi_path: Path to MIDI file

    Returns:
        List of InstrumentTrack for each instrument
    """
    import pretty_midi

    midi = pretty_midi.PrettyMIDI(str(midi_path))
    tracks = []

    # Try to extract instrument from filename
    filename_key = None
    for key in BBC_CATALOG:
        if key in midi_path.stem:
            filename_key = key
            break

    for i, inst in enumerate(midi.instruments):
        if not inst.notes:
            continue

        # Priority 1: Track name matches BBC_CATALOG key
        bbc_inst = None
        if inst.name:
            # Normalize track name (lowercase, replace spaces/dashes with underscores)
            normalized = inst.name.lower().replace(" ", "_").replace("-", "_")
            for key in BBC_CATALOG:
                if key in normalized or normalized in key:
                    bbc_inst = BBC_CATALOG[key]
                    break

        # Priority 2: Filename contains instrument key
        if bbc_inst is None and filename_key:
            bbc_inst = BBC_CATALOG.get(filename_key)

        # Priority 3: GM program lookup
        if bbc_inst is None:
            bbc_inst = find_instrument_by_gm_program(inst.program)

        # Priority 4: Default
        if bbc_inst is None:
            bbc_inst = BBC_CATALOG.get("violins_1")

        # Calculate duration
        note_times = [n.end for n in inst.notes]
        duration = max(note_times) if note_times else 0

        # Calculate pan from position
        pan = bbc_inst.position.az / 90.0 if bbc_inst else 0.0
        pan = max(-1.0, min(1.0, pan))

        tracks.append(
            InstrumentTrack(
                name=inst.name or bbc_inst.name if bbc_inst else f"Track {i + 1}",
                key=bbc_inst.key if bbc_inst else "violins_1",
                section=bbc_inst.section if bbc_inst else Section.STRINGS,
                position=bbc_inst.position if bbc_inst else Pos3D(0, 0, 5),
                note_count=len(inst.notes),
                duration_sec=duration,
                channel=i,
                pan=pan,
            )
        )

    return tracks


async def split_midi_by_instrument(
    midi_path: Path,
    tracks: list[InstrumentTrack],
) -> dict[str, Path]:
    """Split MIDI into per-instrument files.

    Each instrument gets its own MIDI file for independent rendering.

    Args:
        midi_path: Original MIDI file
        tracks: Analyzed tracks

    Returns:
        Dict mapping instrument key to MIDI file path
    """
    import pretty_midi

    midi = pretty_midi.PrettyMIDI(str(midi_path))
    work_dir = WORK_DIR / "work" / f"split_{uuid.uuid4().hex[:8]}"
    work_dir.mkdir(parents=True, exist_ok=True)

    split_paths: dict[str, Path] = {}

    for track, inst in zip(tracks, midi.instruments, strict=False):
        if not inst.notes:
            continue

        # Create single-instrument MIDI
        new_midi = pretty_midi.PrettyMIDI()

        # Copy tempo/time signature
        for ts in midi.time_signature_changes:
            new_midi.time_signature_changes.append(ts)

        # Create new instrument on channel 1
        new_inst = pretty_midi.Instrument(
            program=inst.program,
            is_drum=inst.is_drum,
            name=track.name,
        )

        # Copy notes
        for note in inst.notes:
            new_inst.notes.append(
                pretty_midi.Note(
                    velocity=note.velocity,
                    pitch=note.pitch,
                    start=note.start,
                    end=note.end,
                )
            )

        # Copy control changes
        for cc in inst.control_changes:
            new_inst.control_changes.append(cc)

        new_midi.instruments.append(new_inst)

        # Save
        out_path = work_dir / f"{track.key}.mid"
        new_midi.write(str(out_path))
        split_paths[track.key] = out_path

    return split_paths


# ============================================================================
# BBC Renderer
# ============================================================================


class BBCRenderer(BaseRenderer):
    """BBC Symphony Orchestra renderer.

    Renders MIDI to high-quality orchestral audio using BBC SO VST
    through REAPER. Supports:
    - 36 instruments from BBC SO catalog
    - Full-state FX chains (generated programmatically)
    - Expression automation (dynamics, keyswitches)
    - Spatial positioning (5.1.4 VBAP)

    Implements RendererProtocol for pluggable rendering.
    """

    def __init__(self) -> None:
        super().__init__()
        self._reaper_available = False
        self._vst_available = False

    @property
    def name(self) -> str:
        return "bbc"

    @property
    def available(self) -> bool:
        return self._reaper_available and self._vst_available

    async def _do_initialize(self) -> bool:
        """Initialize renderer, verify BBC SO is available."""
        self._reaper_available = REAPER_APP.exists()
        self._vst_available = BBC_VST3.exists()

        if not self._reaper_available:
            self._logger.warning("REAPER not found at %s", REAPER_APP)
        if not self._vst_available:
            self._logger.warning("BBC Symphony Orchestra VST3 not found at %s", BBC_VST3)

        if not self.available:
            return False

        # Create directories
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

        self._logger.info("✓ BBC Renderer initialized (%d instruments)", len(BBC_CATALOG))
        return True

    async def _do_render(
        self,
        midi_path: Path,
        output_path: Path,
        config: BaseRenderConfig,
    ) -> BaseRenderResult:
        """Render MIDI to orchestral audio using BBC Symphony Orchestra.

        Full pipeline:
        1. Analyze MIDI → detect instruments
        2. Apply expression → dynamics, keyswitches
        3. Generate FX chains → per-instrument BBC SO (full state)
        4. Create REAPER project → multi-track
        5. Render via REAPER CLI
        6. Spatialize → 5.1.4
        """
        t0 = time.perf_counter()

        if not midi_path.exists():
            return BaseRenderResult(
                success=False,
                renderer=self.name,
                error=f"MIDI file not found: {midi_path}",
            )

        self._logger.info("🎼 BBC Render: %s", midi_path.name)

        # Step 1: Analyze MIDI
        self._logger.info("   1/5 Analyzing MIDI...")
        tracks = await analyze_midi(midi_path)

        if not tracks:
            return BaseRenderResult(
                success=False,
                renderer=self.name,
                error="No instrument tracks found",
            )

        self._logger.info("       → %d instruments detected", len(tracks))

        # Step 2: Apply expression
        expressed_path = midi_path
        if config.apply_expression:
            self._logger.info("   2/5 Applying expression...")
            work_dir = WORK_DIR / "work"
            work_dir.mkdir(parents=True, exist_ok=True)
            expressed_path = work_dir / f"{midi_path.stem}_expressed.mid"

            # Map config style to ExpressionStyle
            style_map = {
                "romantic": ExpressionStyle.FILM_SCORE,
                "classical": ExpressionStyle.CLASSICAL,
                "baroque": ExpressionStyle.BAROQUE,
            }
            style = style_map.get(config.expression_style, ExpressionStyle.FILM_SCORE)

            await add_expression(
                midi_path,
                expressed_path,
                style=style,
            )

            if config.apply_keyswitches:
                ks_path = apply_keyswitches_to_file(expressed_path)
                expressed_path = ks_path

        # Step 3: Generate FX chains (full state)
        self._logger.info("   3/5 Generating full-state FX chains...")
        for track in tracks:
            fxchain_path = get_rfxchain_path(track.key)
            self._logger.debug(
                "       → %s: %s (%d bytes)",
                track.key,
                fxchain_path.name,
                fxchain_path.stat().st_size,
            )

        # Step 4: Create REAPER project
        self._logger.info("   4/5 Creating REAPER project...")

        # Build track list with spatial panning
        track_list = [(track.name, track.key, track.pan) for track in tracks]

        # Calculate duration
        duration = max(t.duration_sec for t in tracks) + 2  # Add buffer

        # Get tempo from config or default
        tempo = config.tempo or 120.0

        project_path = generate_reaper_project(
            midi_path=expressed_path,
            tracks=track_list,
            output_dir=output_path.parent,
            output_name=output_path.stem,
            tempo=tempo,
            duration=duration,
        )

        self._logger.info("       → %s", project_path.name)

        # Step 5: Render via REAPER CLI
        self._logger.info("   5/5 Rendering with REAPER (headless)...")

        render_timeout = config.extra.get("render_timeout", 300)

        # Use centralized headless render function
        from kagami.core.effectors.rfxchain_generator import render_project_headless

        success, error = render_project_headless(
            project_path,
            timeout=render_timeout,
            parallel_safe=True,
        )

        if not success:
            return BaseRenderResult(
                success=False,
                renderer=self.name,
                error=error or "REAPER render failed",
            )

        # Check for output file - REAPER may create a directory with WAV inside
        actual_output = output_path
        if output_path.is_dir():
            # REAPER created a directory, look for WAV inside
            wav_files = list(output_path.glob("*.wav"))
            if wav_files:
                actual_output = wav_files[0]
            else:
                return BaseRenderResult(
                    success=False,
                    renderer=self.name,
                    error="REAPER render produced directory but no WAV inside",
                )
        elif not output_path.exists():
            return BaseRenderResult(
                success=False,
                renderer=self.name,
                error="REAPER render produced no output",
            )

        # Verify audio is not silent
        import soundfile as sf

        audio, sr = sf.read(str(actual_output))
        if np.max(np.abs(audio)) < 0.001:
            return BaseRenderResult(
                success=False,
                renderer=self.name,
                error="BBC rendered silence - check FX chains and VST installation",
            )

        # Apply spatialization if requested
        final_path = actual_output
        if config.apply_spatialization:
            final_path = await self._spatialize(actual_output, tracks, config)

        render_time = time.perf_counter() - t0
        audio_duration = len(audio) / sr

        self._logger.info(
            "   ✓ Complete: %s (%.1fs, %.1fs render)",
            final_path.name,
            audio_duration,
            render_time,
        )

        return BaseRenderResult(
            success=True,
            output_path=final_path,
            duration=audio_duration,
            renderer=self.name,
            metadata={
                "render_time": render_time,
                "tracks": len(tracks),
                "channels": config.channels,
                "sample_rate": sr,
                "track_info": [
                    {"name": t.name, "key": t.key, "section": t.section.value} for t in tracks
                ],
            },
        )

    async def _spatialize(
        self,
        audio_path: Path,
        tracks: list[InstrumentTrack],
        config: BaseRenderConfig,
    ) -> Path:
        """Apply 5.1.4 spatialization based on instrument positions.

        Uses VBAP to position each instrument in 3D space.
        """
        import soundfile as sf

        audio, sr = sf.read(str(audio_path))

        # Convert to mono for processing
        if len(audio.shape) > 1:
            mono = audio.mean(axis=1)
        else:
            mono = audio

        mono = mono.astype(np.float32)
        n_samples = len(mono)

        # Create output array
        output = np.zeros((n_samples, NUM_CH), dtype=np.float32)

        # Weight contributions by note count
        total_notes = sum(t.note_count for t in tracks) or 1

        for track in tracks:
            weight = track.note_count / total_notes
            pos = track.position

            # Get VBAP gains
            gains = np.array(vbap_10ch(pos.az, pos.el, pos.dist), dtype=np.float32)

            # Apply to output
            for ch in range(NUM_CH):
                if ch != CH_LFE and gains[ch] > 0.001:
                    output[:, ch] += mono * gains[ch] * weight

        # Add LFE
        lfe_sos = signal.butter(4, 120 / (sr / 2), "low", output="sos")
        lfe = signal.sosfilt(lfe_sos, mono).astype(np.float32)
        lfe_peak = np.max(np.abs(lfe))
        if lfe_peak > 0.01:
            output[:, CH_LFE] = lfe / lfe_peak * 0.2

        # Normalize
        master_volume = config.extra.get("master_volume", 0.85)
        output = np.tanh(output * 2.0) / 2.0
        peak = np.max(np.abs(output))
        if peak > 0.01:
            output *= master_volume / peak

        # Save spatialized output
        spatial_path = audio_path.parent / f"{audio_path.stem}_spatial.wav"
        sf.write(str(spatial_path), output, sr)

        return spatial_path

    async def render_scale(
        self,
        instrument_key: str,
        output_dir: Path | None = None,
    ) -> BaseRenderResult:
        """Render a scale for a single instrument (for testing).

        Creates a simple C major scale MIDI and renders it.

        Args:
            instrument_key: Key from BBC_CATALOG
            output_dir: Output directory (default: ~/.kagami/symphony/scales/)

        Returns:
            RenderResult with audio path
        """
        import pretty_midi

        if instrument_key not in BBC_CATALOG:
            return BaseRenderResult(
                success=False,
                renderer=self.name,
                error=f"Unknown instrument: {instrument_key}",
            )

        instrument = BBC_CATALOG[instrument_key]

        # Create scale MIDI
        midi = pretty_midi.PrettyMIDI()
        inst = pretty_midi.Instrument(program=0)

        # C major scale starting at middle C
        scale = [60, 62, 64, 65, 67, 69, 71, 72]  # C4 to C5

        # Adjust for instrument range
        base = instrument.range_low + 12
        if base + 12 > instrument.range_high:
            base = instrument.range_high - 12

        for i, semitone in enumerate(scale):
            note = pretty_midi.Note(
                velocity=80,
                pitch=base + (semitone - 60),
                start=i * 0.5,
                end=(i + 1) * 0.5 - 0.05,
            )
            inst.notes.append(note)

        midi.instruments.append(inst)

        # Save MIDI
        output_dir = output_dir or WORK_DIR / "scales"
        output_dir.mkdir(parents=True, exist_ok=True)
        midi_path = output_dir / f"{instrument_key}_scale.mid"
        midi.write(str(midi_path))

        # Render
        return await self.render(
            midi_path,
            output_dir / f"{instrument_key}_scale.wav",
            BaseRenderConfig(),
        )


# ============================================================================
# Factory Functions
# ============================================================================

_renderer: BBCRenderer | None = None


async def get_bbc_renderer() -> BBCRenderer:
    """Get or create the BBC renderer singleton."""
    global _renderer
    if _renderer is None:
        _renderer = BBCRenderer()
        await _renderer.initialize()
    return _renderer


async def render(
    midi_path: Path | str,
    output_path: Path | str | None = None,
    config: BaseRenderConfig | None = None,
) -> BaseRenderResult:
    """Render MIDI to orchestral audio using BBC Symphony Orchestra.

    Convenience function that uses the global renderer.

    Args:
        midi_path: Input MIDI file
        output_path: Output audio file
        config: Rendering configuration

    Returns:
        RenderResult with audio path
    """
    renderer = await get_bbc_renderer()

    midi_path = Path(midi_path)
    if output_path is None:
        output_path = OUTPUT_DIR / f"{midi_path.stem}_bbc.wav"
    else:
        output_path = Path(output_path)

    return await renderer.render(midi_path, output_path, config)


async def render_scale(instrument_key: str) -> BaseRenderResult:
    """Render a scale for a single instrument (for testing).

    Args:
        instrument_key: Key from BBC_CATALOG (e.g., "violins_1")

    Returns:
        RenderResult with audio path
    """
    renderer = await get_bbc_renderer()
    return await renderer.render_scale(instrument_key)


# ============================================================================
# Auto-register on import
# ============================================================================


def _register_bbc_renderer() -> None:
    """Register the BBC renderer with the global registry."""
    renderer = BBCRenderer()
    register_renderer(renderer)


# Register on module load
_register_bbc_renderer()


# ============================================================================
# Exports
# ============================================================================

__all__ = [
    "BBCRenderResult",
    # Renderer
    "BBCRenderer",
    # Data classes
    "InstrumentTrack",
    # Analysis
    "analyze_midi",
    "get_bbc_renderer",
    # Convenience functions
    "render",
    "render_scale",
    "split_midi_by_instrument",
]
