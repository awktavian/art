"""REAPER Renderer — BBC Symphony Orchestra via REAPER CLI.

High-quality orchestral rendering using BBC Symphony Orchestra VST3
through REAPER's headless rendering.

Pipeline:
1. Analyze MIDI → detect instruments
2. Apply expression → CC1, CC11, keyswitches
3. Split MIDI → per-instrument files
4. Create REAPER project → with RFX chains
5. Render → REAPER CLI headless

Colony: Forge (e₂)
Created: January 2, 2026
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from kagami.core.effectors.bbc_instruments import (
    BBC_CATALOG,
    Section,
    find_instrument_by_gm_program,
)
from kagami.core.effectors.expression_engine import (
    ExpressionStyle,
    add_expression,
)
from kagami.core.effectors.renderers import (
    BaseRenderer,
    RenderConfig,
    RenderResult,
    register_renderer,
)
from kagami.core.effectors.vbap_core import Pos3D

logger = logging.getLogger(__name__)

# =============================================================================
# Constants
# =============================================================================

SAMPLE_RATE = 48000
REAPER_APP = Path("/Applications/REAPER.app/Contents/MacOS/REAPER")
BBC_VST3 = Path("/Library/Audio/Plug-Ins/VST3/BBC Symphony Orchestra.vst3")
WORK_DIR = Path.home() / ".kagami" / "symphony"
RFXCHAIN_DIR = WORK_DIR / "reaper" / "instruments"


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class InstrumentTrack:
    """Information about a single instrument track."""

    name: str
    key: str  # BBC_CATALOG key
    section: Section
    position: Pos3D
    note_count: int
    duration_sec: float
    pan: float = 0.0


# =============================================================================
# MIDI Analysis
# =============================================================================


async def analyze_midi(midi_path: Path) -> list[InstrumentTrack]:
    """Analyze MIDI file to determine instruments."""
    import pretty_midi

    midi = pretty_midi.PrettyMIDI(str(midi_path))
    tracks = []

    for i, inst in enumerate(midi.instruments):
        if not inst.notes:
            continue

        # Match by track name or GM program
        bbc_inst = None
        if inst.name:
            normalized = inst.name.lower().replace(" ", "_").replace("-", "_")
            for key in BBC_CATALOG:
                if key in normalized or normalized in key:
                    bbc_inst = BBC_CATALOG[key]
                    break

        if bbc_inst is None:
            bbc_inst = find_instrument_by_gm_program(inst.program)

        if bbc_inst is None:
            bbc_inst = BBC_CATALOG.get("violins_1")

        duration = max(n.end for n in inst.notes) if inst.notes else 0
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
                pan=pan,
            )
        )

    return tracks


async def split_midi_by_instrument(
    midi_path: Path,
    tracks: list[InstrumentTrack],
) -> dict[str, Path]:
    """Split MIDI into per-instrument files."""
    import pretty_midi

    midi = pretty_midi.PrettyMIDI(str(midi_path))
    work_dir = WORK_DIR / "work" / f"split_{uuid.uuid4().hex[:8]}"
    work_dir.mkdir(parents=True, exist_ok=True)

    split_paths: dict[str, Path] = {}

    for track, inst in zip(tracks, midi.instruments, strict=False):
        if not inst.notes:
            continue

        new_midi = pretty_midi.PrettyMIDI()
        for ts in midi.time_signature_changes:
            new_midi.time_signature_changes.append(ts)

        new_inst = pretty_midi.Instrument(
            program=inst.program,
            is_drum=inst.is_drum,
            name=track.name,
        )

        for note in inst.notes:
            new_inst.notes.append(
                pretty_midi.Note(
                    velocity=note.velocity,
                    pitch=note.pitch,
                    start=note.start,
                    end=note.end,
                )
            )

        for cc in inst.control_changes:
            new_inst.control_changes.append(cc)

        new_midi.instruments.append(new_inst)
        out_path = work_dir / f"{track.key}.mid"
        new_midi.write(str(out_path))
        split_paths[track.key] = out_path

    return split_paths


# =============================================================================
# REAPER Renderer
# =============================================================================


class ReaperRenderer(BaseRenderer):
    """BBC Symphony Orchestra renderer via REAPER CLI.

    Uses pre-exported RFX chains containing full BBC SO state.
    Requires REAPER and BBC SO VST3 to be installed.
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
        if not self._initialized:
            return REAPER_APP.exists() and BBC_VST3.exists()
        return self._reaper_available and self._vst_available

    async def _do_initialize(self) -> bool:
        self._reaper_available = REAPER_APP.exists()
        self._vst_available = BBC_VST3.exists()

        if not self._reaper_available:
            self._logger.warning("REAPER not found at %s", REAPER_APP)
        if not self._vst_available:
            self._logger.warning("BBC SO VST3 not found at %s", BBC_VST3)

        if self.available:
            WORK_DIR.mkdir(parents=True, exist_ok=True)
            self._logger.info("✓ REAPER Renderer initialized (%d instruments)", len(BBC_CATALOG))

        return self.available

    async def _do_render(
        self,
        midi_path: Path,
        output_path: Path,
        config: RenderConfig,
    ) -> RenderResult:
        """Render MIDI to orchestral audio."""
        t0 = time.perf_counter()

        if not midi_path.exists():
            return RenderResult(
                success=False,
                renderer=self.name,
                error=f"MIDI file not found: {midi_path}",
            )

        self._logger.info("🎼 REAPER Render: %s", midi_path.name)

        # Step 1: Analyze MIDI
        self._logger.info("   1/5 Analyzing MIDI...")
        tracks = await analyze_midi(midi_path)
        if not tracks:
            return RenderResult(
                success=False, renderer=self.name, error="No instrument tracks found"
            )
        self._logger.info("       → %d instruments", len(tracks))

        # Step 2: Apply expression
        expressed_path = midi_path
        if config.apply_expression:
            self._logger.info("   2/5 Applying expression...")
            work_dir = WORK_DIR / "work"
            work_dir.mkdir(parents=True, exist_ok=True)
            expressed_path = work_dir / f"{midi_path.stem}_expressed.mid"

            style_map = {
                "romantic": ExpressionStyle.FILM_SCORE,
                "classical": ExpressionStyle.CLASSICAL,
                "baroque": ExpressionStyle.BAROQUE,
            }
            style = style_map.get(config.expression_style, ExpressionStyle.FILM_SCORE)
            # add_expression already inserts keyswitches internally
            # Do NOT call apply_keyswitches_to_file - it would double-insert!
            await add_expression(midi_path, expressed_path, style=style)

        # Step 3: Split MIDI by instrument
        self._logger.info("   3/5 Splitting MIDI by instrument...")
        split_paths = await split_midi_by_instrument(expressed_path, tracks)
        self._logger.info("       → %d files", len(split_paths))

        # Step 4: Create REAPER project
        self._logger.info("   4/5 Creating REAPER project...")
        from kagami.core.effectors.renderers.reaper_project import generate_reaper_project

        track_list = [(t.name, t.key, t.pan) for t in tracks]
        duration = max(t.duration_sec for t in tracks) + 2
        tempo = config.tempo or 120.0

        project_path = generate_reaper_project(
            midi_path=expressed_path,
            tracks=track_list,
            output_dir=output_path.parent,
            output_name=output_path.stem,
            tempo=tempo,
            duration=duration,
            split_midi_paths=split_paths,
        )
        self._logger.info("       → %s", project_path.name)

        # Step 5: Render via REAPER CLI
        self._logger.info("   5/5 Rendering with REAPER...")
        from kagami.core.effectors.renderers.reaper_project import render_project_headless

        success, error = render_project_headless(
            project_path,
            timeout=config.extra.get("render_timeout", 300),
            parallel_safe=True,
        )

        if not success:
            return RenderResult(
                success=False, renderer=self.name, error=error or "REAPER render failed"
            )

        # Verify output
        actual_output = output_path
        if output_path.is_dir():
            wav_files = list(output_path.glob("*.wav"))
            if wav_files:
                actual_output = wav_files[0]
            else:
                return RenderResult(success=False, renderer=self.name, error="No WAV output")
        elif not output_path.exists():
            return RenderResult(success=False, renderer=self.name, error="No output file")

        # Check for silence
        import soundfile as sf

        audio, sr = sf.read(str(actual_output))
        if np.max(np.abs(audio)) < 0.001:
            return RenderResult(success=False, renderer=self.name, error="Output is silent")

        render_time = time.perf_counter() - t0
        duration_sec = len(audio) / sr

        self._logger.info("   ✓ Complete: %s (%.1fs)", actual_output.name, duration_sec)

        return RenderResult(
            success=True,
            output_path=actual_output,
            duration=duration_sec,
            renderer=self.name,
            metadata={
                "render_time": render_time,
                "tracks": len(tracks),
                "sample_rate": sr,
            },
        )


# =============================================================================
# Factory and Registration
# =============================================================================


_renderer: ReaperRenderer | None = None


async def get_reaper_renderer() -> ReaperRenderer:
    """Get or create the REAPER renderer singleton."""
    global _renderer
    if _renderer is None:
        _renderer = ReaperRenderer()
        await _renderer.initialize()
    return _renderer


def _register() -> None:
    """Register the REAPER renderer."""
    register_renderer(ReaperRenderer())


_register()


__all__ = [
    "InstrumentTrack",
    "ReaperRenderer",
    "analyze_midi",
    "get_reaper_renderer",
    "split_midi_by_instrument",
]
