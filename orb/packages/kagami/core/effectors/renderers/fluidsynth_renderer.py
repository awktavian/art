"""FluidSynth Renderer — SoundFont-based MIDI rendering.

Lightweight MIDI rendering using FluidSynth and SoundFonts.
This is the fallback renderer when BBC Symphony Orchestra is not available.

Requirements:
- FluidSynth (brew install fluid-synth)
- SoundFont file (e.g., MuseScore_General.sf3)

Created: January 1, 2026
"""

from __future__ import annotations

import logging
import os
import subprocess
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import lru_cache
from pathlib import Path

import numpy as np
from numpy.typing import NDArray
from scipy import signal

from kagami.core.effectors.renderers import (
    BaseRenderer,
    RenderConfig,
    RenderResult,
    register_renderer,
)
from kagami.core.effectors.vbap_core import (
    CH_LFE,
    NUM_CH,
    Pos3D,
    get_orchestra_position,
    vbap_10ch,
)

logger = logging.getLogger(__name__)

# =============================================================================
# Constants
# =============================================================================

SAMPLE_RATE = 48000
ASSETS_DIR = Path.home() / ".kagami" / "symphony"
SOUNDFONT = ASSETS_DIR / "soundfonts" / "MuseScore_General.sf3"
OUTPUT_DIR = ASSETS_DIR / "rendered"

CPU_COUNT = os.cpu_count() or 4
MAX_WORKERS = min(8, CPU_COUNT)


# =============================================================================
# Room Acoustics
# =============================================================================


@lru_cache(maxsize=4)
def _room_ir(sr: int) -> NDArray:
    """Concert hall impulse response."""
    rt60 = 1.8
    n = int(rt60 * sr)
    rng = np.random.RandomState(42)
    ir = rng.randn(n).astype(np.float32) * 0.018 * np.exp(-4 * np.arange(n) / sr / rt60)
    for ms, g in [(8, 0.30), (15, 0.24), (28, 0.18), (42, 0.12)]:
        idx = int(ms / 1000 * sr)
        if idx < len(ir):
            ir[idx] += g
    return signal.sosfilt(signal.butter(2, 6000 / (sr / 2), "low", output="sos"), ir).astype(
        np.float32
    )


def apply_room(audio: NDArray, pos: Pos3D, sr: int) -> NDArray:
    """Position-dependent reverb."""
    ir = _room_ir(sr)
    wet = min(0.38, 0.10 + 0.04 * pos.dist / 5 + pos.el / 90 * 0.06)
    reverb = signal.fftconvolve(audio, ir, "full")[: len(audio)]
    return (audio * (1 - wet) + reverb * wet).astype(np.float32)


def spatialize_10ch(mono: NDArray, pos: Pos3D) -> NDArray:
    """Spatialize mono to 10ch 5.1.4."""
    gains = np.array(vbap_10ch(pos.az, pos.el, pos.dist), dtype=np.float32)
    out = np.zeros((len(mono), NUM_CH), dtype=np.float32)
    for ch in range(NUM_CH):
        if ch != CH_LFE and gains[ch] > 0.001:
            out[:, ch] = mono * gains[ch]
    return out


# =============================================================================
# FluidSynth Track Rendering
# =============================================================================


def _render_track_fluidsynth(
    track_idx: int,
    track_midi_path: str,
    track_wav_path: str,
    soundfont: str,
    sr: int,
    gain: float,
    inst_name: str,
    program: int,
) -> dict:
    """Render single track via FluidSynth."""
    import soundfile as sf

    try:
        subprocess.run(
            [
                "fluidsynth",
                "-ni",
                "-F",
                track_wav_path,
                "-r",
                str(sr),
                "-g",
                str(gain),
                soundfont,
                track_midi_path,
            ],
            capture_output=True,
            timeout=180,
        )

        if not Path(track_wav_path).exists():
            return {"idx": track_idx, "error": "FluidSynth failed", "audio": None}

        audio, _ = sf.read(track_wav_path)
        mono = (audio[:, 0] + audio[:, 1]) * 0.5 if len(audio.shape) == 2 else audio
        mono = mono.astype(np.float32)

        return {
            "idx": track_idx,
            "name": inst_name,
            "pos": get_orchestra_position(inst_name, program),
            "audio": mono,
            "error": None,
        }
    except Exception as e:
        return {"idx": track_idx, "error": str(e), "audio": None}


# =============================================================================
# FluidSynth Renderer
# =============================================================================


class FluidSynthRenderer(BaseRenderer):
    """FluidSynth-based MIDI renderer.

    Renders MIDI files using FluidSynth and SoundFonts.
    Features:
    - Parallel track rendering for faster processing
    - VBAP spatialization for 5.1.4 output
    - Room acoustics simulation

    This is the fallback renderer when BBC Symphony Orchestra is unavailable.
    """

    def __init__(
        self,
        soundfont: Path | None = None,
        sample_rate: int = SAMPLE_RATE,
        gain: float = 0.55,
        track_norm: float = 0.42,
        master_norm: float = 0.82,
        lfe_level: float = 0.20,
        lfe_cutoff: int = 80,
        max_workers: int = MAX_WORKERS,
    ):
        super().__init__()
        self.soundfont = soundfont or SOUNDFONT
        self.sample_rate = sample_rate
        self.gain = gain
        self.track_norm = track_norm
        self.master_norm = master_norm
        self.lfe_level = lfe_level
        self.lfe_cutoff = lfe_cutoff
        self.max_workers = max_workers
        self._fluidsynth_available = False
        self._soundfont_available = False

    @property
    def name(self) -> str:
        return "fluidsynth"

    @property
    def available(self) -> bool:
        return self._fluidsynth_available and self._soundfont_available

    async def _do_initialize(self) -> bool:
        """Initialize renderer, check FluidSynth availability."""
        # Check FluidSynth
        try:
            result = subprocess.run(
                ["fluidsynth", "--version"],
                capture_output=True,
                timeout=5,
            )
            self._fluidsynth_available = result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            self._fluidsynth_available = False

        if not self._fluidsynth_available:
            self._logger.warning("FluidSynth not installed")

        # Check SoundFont
        self._soundfont_available = self.soundfont.exists()
        if not self._soundfont_available:
            self._logger.warning(f"SoundFont not found: {self.soundfont}")

        if not self.available:
            return False

        # Create output directory
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        self._logger.info(
            "✓ FluidSynth Renderer initialized (SF: %s, workers: %d)",
            self.soundfont.name,
            self.max_workers,
        )
        return True

    async def _do_render(
        self,
        midi_path: Path,
        output_path: Path,
        config: RenderConfig,
    ) -> RenderResult:
        """Render MIDI using FluidSynth with parallel track processing."""
        import pretty_midi
        import soundfile as sf

        t0 = time.perf_counter()

        if not midi_path.exists():
            return RenderResult(
                success=False,
                renderer=self.name,
                error=f"MIDI file not found: {midi_path}",
            )

        self._logger.info("🎼 FluidSynth Render: %s", midi_path.name)

        try:
            midi = pretty_midi.PrettyMIDI(str(midi_path))
            duration = midi.get_end_time()

            tracks_to_render = []
            with tempfile.TemporaryDirectory() as tmpdir:
                tmp = Path(tmpdir)

                for i, inst in enumerate(midi.instruments):
                    if not inst.notes:
                        continue

                    # Create single-track MIDI
                    track_midi = pretty_midi.PrettyMIDI()
                    track_inst = pretty_midi.Instrument(
                        program=inst.program, is_drum=inst.is_drum, name=inst.name
                    )
                    track_inst.notes = inst.notes
                    track_midi.instruments.append(track_inst)

                    track_mid = tmp / f"t{i}.mid"
                    track_wav = tmp / f"t{i}.wav"
                    track_midi.write(str(track_mid))

                    tracks_to_render.append(
                        (
                            i,
                            str(track_mid),
                            str(track_wav),
                            str(self.soundfont),
                            self.sample_rate,
                            self.gain,
                            inst.name,
                            inst.program,
                        )
                    )

                if not tracks_to_render:
                    return RenderResult(
                        success=False,
                        renderer=self.name,
                        error="No tracks to render",
                    )

                workers = self._optimal_workers(len(tracks_to_render))
                self._logger.info("   → %d tracks, %d workers", len(tracks_to_render), workers)

                # Parallel render
                results = []
                with ThreadPoolExecutor(max_workers=workers) as ex:
                    futures = {
                        ex.submit(_render_track_fluidsynth, *a): a[0] for a in tracks_to_render
                    }
                    for f in as_completed(futures):
                        r = f.result()
                        if r["audio"] is not None:
                            results.append(r)

                if not results:
                    return RenderResult(
                        success=False,
                        renderer=self.name,
                        error="No tracks rendered successfully",
                    )

                # Mix with spatialization
                max_len = max(len(r["audio"]) for r in results)
                output = np.zeros((max_len, NUM_CH), dtype=np.float32)
                lfe_sum = np.zeros(max_len, dtype=np.float32)
                lfe_sos = signal.butter(
                    4, self.lfe_cutoff, "low", fs=self.sample_rate, output="sos"
                )

                for r in results:
                    mono = r["audio"]
                    pos = r["pos"]

                    if len(mono) < max_len:
                        mono = np.pad(mono, (0, max_len - len(mono)))

                    mono = apply_room(mono, pos, self.sample_rate)
                    peak = np.max(np.abs(mono))
                    if peak > 0.01:
                        mono = mono / peak * self.track_norm

                    output += spatialize_10ch(mono, pos)
                    lfe_sum += signal.sosfilt(lfe_sos, mono).astype(np.float32) * 0.3

                # LFE
                lfe_peak = np.max(np.abs(lfe_sum))
                if lfe_peak > 0.01:
                    output[:, CH_LFE] = lfe_sum / lfe_peak * self.lfe_level

                # Limit + normalize
                output = np.tanh(output * 2.0) / 2.0
                peak = np.max(np.abs(output))
                if peak > 0.01:
                    output *= self.master_norm / peak

                # Write output
                sf.write(str(output_path), output, self.sample_rate)

            render_time = time.perf_counter() - t0
            self._logger.info(
                "   ✓ Complete: %s (%.1fs, %d tracks)", output_path.name, render_time, len(results)
            )

            return RenderResult(
                success=True,
                output_path=output_path,
                duration=duration,
                renderer=self.name,
                metadata={
                    "render_time": render_time,
                    "tracks": len(results),
                    "workers": workers,
                    "channels": NUM_CH,
                    "sample_rate": self.sample_rate,
                },
            )

        except Exception as e:
            self._logger.exception("FluidSynth render failed: %s", e)
            return RenderResult(
                success=False,
                renderer=self.name,
                error=str(e),
            )

    def _optimal_workers(self, n: int) -> int:
        """Optimal workers for track count."""
        if n <= 4:
            return min(n, 4)
        if n <= 12:
            return min(n, 8)
        return min(n, self.max_workers)


# =============================================================================
# Factory Functions
# =============================================================================

_renderer: FluidSynthRenderer | None = None


async def get_fluidsynth_renderer() -> FluidSynthRenderer:
    """Get or create the FluidSynth renderer singleton."""
    global _renderer
    if _renderer is None:
        _renderer = FluidSynthRenderer()
        await _renderer.initialize()
    return _renderer


async def render(
    midi_path: Path | str,
    output_path: Path | str | None = None,
    config: RenderConfig | None = None,
) -> RenderResult:
    """Render MIDI to audio using FluidSynth.

    Convenience function that uses the global renderer.

    Args:
        midi_path: Input MIDI file
        output_path: Output audio file
        config: Rendering configuration

    Returns:
        RenderResult with audio path
    """
    renderer = await get_fluidsynth_renderer()

    midi_path = Path(midi_path)
    if output_path is None:
        output_path = OUTPUT_DIR / f"{midi_path.stem}_fluidsynth.wav"
    else:
        output_path = Path(output_path)

    return await renderer.render(midi_path, output_path, config)


# =============================================================================
# Auto-register on import
# =============================================================================


def _register_fluidsynth_renderer() -> None:
    """Register the FluidSynth renderer with the global registry."""
    renderer = FluidSynthRenderer()
    register_renderer(renderer)


# Register on module load
_register_fluidsynth_renderer()


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "FluidSynthRenderer",
    "apply_room",
    "get_fluidsynth_renderer",
    "render",
    "spatialize_10ch",
]
