"""Orchestral Spectrum Integration — BBC Symphony Orchestra + Lights.

LIGHT IS MUSIC IS SPECTRUM.

This module integrates the BBC Symphony Orchestra renderer with
the spectrum-driven lighting system, providing end-to-end
orchestral playback with synchronized lights.

Pipeline:
1. MIDI → BBC Renderer → Orchestral Audio
2. Audio → Spatial Engine → Denon 5.1.4
3. Audio → MixAnalyzer → FrequencyBalance
4. FrequencyBalance → SpectrumEngine → Light Parameters
5. Light Parameters → Oelo/Govee

Created: January 3, 2026
h(x) >= 0 always.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from kagami_smarthome.spectrum.engine import (
    MusicalContext,
    MusicMood,
)
from kagami_smarthome.spectrum.spatial_sync import (
    SpatialSyncConfig,
    SpatialSyncController,
)

if TYPE_CHECKING:
    from kagami_smarthome.controller import SmartHomeController

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================


@dataclass
class OrchestralPlaybackConfig:
    """Configuration for orchestral playback with lights."""

    # Rendering
    sample_rate: int = 48000
    channels: int = 10  # 5.1.4

    # Spatial
    enable_spatial: bool = True
    trajectory: str = "orbit"  # corkscrew, orbit, voice, static

    # Spectrum/Lights
    enable_lights: bool = True
    light_update_fps: int = 15

    # BBC Renderer
    expression_style: str = "virtuoso"  # virtuoso, romantic, modern, baroque
    use_cache: bool = True


# =============================================================================
# MIDI Analysis for Musical Context
# =============================================================================


async def analyze_midi_context(midi_path: Path) -> MusicalContext:
    """Extract musical context from MIDI file.

    Analyzes the MIDI to extract:
    - Tempo (BPM)
    - Key signature
    - Mode (major/minor)
    - Average dynamics (velocity)
    - Note density
    - Inferred mood

    Args:
        midi_path: Path to MIDI file

    Returns:
        MusicalContext for spectrum engine
    """
    try:
        import pretty_midi

        midi = pretty_midi.PrettyMIDI(str(midi_path))

        # Tempo
        tempos = midi.get_tempo_changes()[1]
        tempo_bpm = float(tempos[0]) if len(tempos) > 0 else 120.0

        # Key signature
        key_sigs = midi.key_signature_changes
        if key_sigs:
            key_number = key_sigs[0].key_number
            key_names = [
                "C",
                "Db",
                "D",
                "Eb",
                "E",
                "F",
                "F#",
                "G",
                "Ab",
                "A",
                "Bb",
                "B",
                "Cm",
                "C#m",
                "Dm",
                "Ebm",
                "Em",
                "Fm",
                "F#m",
                "Gm",
                "G#m",
                "Am",
                "Bbm",
                "Bm",
            ]
            key = key_names[key_number % 24] if key_number < 24 else "C"
            mode = "minor" if key_number >= 12 else "major"
        else:
            key = "C"
            mode = "major"

        # Collect all notes for analysis
        all_notes = []
        for instrument in midi.instruments:
            if not instrument.is_drum:
                all_notes.extend(instrument.notes)

        if not all_notes:
            return MusicalContext(tempo_bpm=tempo_bpm, key=key, mode=mode)

        # Average velocity → dynamics
        velocities = [n.velocity for n in all_notes]
        avg_velocity = sum(velocities) / len(velocities)
        dynamics = avg_velocity / 127.0

        # Velocity range → dynamics range
        vel_range = max(velocities) - min(velocities)
        dynamics_range = vel_range / 127.0

        # Note density (notes per beat)
        duration = midi.get_end_time()
        beats = duration * tempo_bpm / 60
        note_density = min(1.0, len(all_notes) / beats / 4)  # Normalize to ~4 notes/beat

        # Infer articulation from note durations
        durations = [n.end - n.start for n in all_notes]
        avg_duration = sum(durations) / len(durations)
        beat_duration = 60.0 / tempo_bpm

        if avg_duration < beat_duration * 0.25:
            articulation = "staccato"
        elif avg_duration > beat_duration * 0.9:
            articulation = "legato"
        else:
            articulation = "normal"

        # Infer mood
        if mode == "minor":
            if dynamics > 0.7 and tempo_bpm > 100:
                mood = MusicMood.INTENSE
            elif dynamics > 0.5:
                mood = MusicMood.DRAMATIC
            elif tempo_bpm < 70:
                mood = MusicMood.GENTLE
            else:
                mood = MusicMood.NEUTRAL
        else:
            if dynamics > 0.7 and tempo_bpm > 120:
                mood = MusicMood.ENERGETIC
            elif tempo_bpm < 60:
                mood = MusicMood.PEACEFUL
            elif dynamics < 0.4:
                mood = MusicMood.GENTLE
            else:
                mood = MusicMood.NEUTRAL

        return MusicalContext(
            tempo_bpm=tempo_bpm,
            key=key.replace("m", ""),  # Strip minor suffix for key
            mode=mode,
            dynamics=dynamics,
            dynamics_range=dynamics_range,
            articulation=articulation,
            note_density=note_density,
            mood=mood,
        )

    except ImportError:
        logger.warning("pretty_midi not available, using default context")
        return MusicalContext()
    except Exception as e:
        logger.warning(f"MIDI analysis failed: {e}")
        return MusicalContext()


# =============================================================================
# Orchestral Playback Controller
# =============================================================================


class OrchestralPlaybackController:
    """Complete orchestral playback with BBC SO + spatial audio + lights.

    LIGHT IS MUSIC IS SPECTRUM.

    This is the unified controller for orchestral experiences:
    - Renders MIDI through BBC Symphony Orchestra
    - Plays through Denon 5.1.4 spatial audio
    - Synchronizes Oelo/Govee lights to the music
    - Maps frequency content to light parameters

    Usage:
        controller = OrchestralPlaybackController(smart_home)

        # From MIDI
        result = await controller.play_midi(
            "/path/to/score.mid",
            expression_style="virtuoso",
        )

        # From pre-rendered audio
        result = await controller.play_audio(
            "/path/to/orchestral.wav",
            tempo_bpm=72,
            key="Cm",
            mode="minor",
        )
    """

    def __init__(
        self,
        smart_home: SmartHomeController | None = None,
        config: OrchestralPlaybackConfig | None = None,
    ):
        """Initialize controller."""
        self._smart_home = smart_home
        self._config = config or OrchestralPlaybackConfig()
        self._sync_controller: SpatialSyncController | None = None

    async def play_midi(
        self,
        midi_path: str | Path,
        expression_style: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Render and play MIDI with synchronized lights.

        Args:
            midi_path: Path to MIDI file
            expression_style: Override expression style
            **kwargs: Additional arguments passed to play_audio

        Returns:
            Playback statistics
        """
        midi_path = Path(midi_path)
        if not midi_path.exists():
            raise FileNotFoundError(f"MIDI file not found: {midi_path}")

        logger.info(f"Rendering MIDI: {midi_path.name}")

        # Extract musical context from MIDI
        context = await analyze_midi_context(midi_path)
        logger.info(
            f"Musical context: {context.tempo_bpm:.0f} BPM, "
            f"{context.key} {context.mode}, mood={context.mood.value}"
        )

        # Render through BBC Symphony Orchestra
        try:
            from kagami.core.effectors.bbc_renderer import (
                BBCRenderer,
            )
            from kagami.core.effectors.expression_engine import ExpressionStyle

            # Map style string to enum
            style_map = {
                "virtuoso": ExpressionStyle.VIRTUOSO,
                "romantic": ExpressionStyle.ROMANTIC,
                "modern": ExpressionStyle.MODERN,
                "baroque": ExpressionStyle.BAROQUE,
            }
            style = style_map.get(
                expression_style or self._config.expression_style,
                ExpressionStyle.VIRTUOSO,
            )

            renderer = BBCRenderer()
            result = await renderer.render(
                midi_path,
                expression_style=style,
            )

            if not result.success or not result.path:
                raise RuntimeError(f"BBC render failed: {result.error}")

            audio_path = result.path
            logger.info(f"Rendered: {audio_path} ({result.duration_sec:.1f}s)")

        except ImportError:
            logger.warning("BBC Renderer not available, falling back to FluidSynth")
            # Fallback to FluidSynth
            audio_path = await self._render_fluidsynth(midi_path)

        # Play with lights
        return await self.play_audio(
            audio_path,
            tempo_bpm=context.tempo_bpm,
            key=context.key,
            mode=context.mode,
            mood=context.mood,
            **kwargs,
        )

    async def play_audio(
        self,
        audio_path: str | Path,
        tempo_bpm: float = 90,
        key: str = "C",
        mode: str = "major",
        mood: MusicMood = MusicMood.NEUTRAL,
        trajectory: str | None = None,
    ) -> dict[str, Any]:
        """Play orchestral audio with synchronized lights.

        Args:
            audio_path: Path to audio file
            tempo_bpm: Tempo for light timing
            key: Musical key
            mode: Mode (major/minor)
            mood: Musical mood
            trajectory: Spatial trajectory type

        Returns:
            Playback statistics
        """
        audio_path = Path(audio_path)
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        # Create sync controller
        if self._sync_controller is None:
            sync_config = SpatialSyncConfig(
                light_update_fps=self._config.light_update_fps,
                enable_oelo=self._config.enable_lights,
                enable_govee=self._config.enable_lights,
            )
            self._sync_controller = SpatialSyncController(
                self._smart_home,
                sync_config,
            )

        # Build musical context
        context = MusicalContext(
            tempo_bpm=tempo_bpm,
            key=key,
            mode=mode,
            mood=mood,
        )

        # Play with synchronized lights
        logger.info(
            f"Playing orchestral: {audio_path.name} "
            f"({tempo_bpm:.0f} BPM, {key} {mode}, {mood.value})"
        )

        return await self._sync_controller.play_with_lights(
            audio_path=audio_path,
            spatial=self._config.enable_spatial,
            trajectory=trajectory or self._config.trajectory,
            musical_context=context,
        )

    async def _render_fluidsynth(self, midi_path: Path) -> Path:
        """Fallback rendering with FluidSynth."""
        try:
            from kagami.core.effectors.renderers.fluidsynth_renderer import (
                FluidSynthRenderer,
            )

            renderer = FluidSynthRenderer()
            result = await renderer.render(midi_path)

            if result.success and result.path:
                return result.path
            raise RuntimeError(f"FluidSynth render failed: {result.error}")

        except ImportError as e:
            raise RuntimeError(
                "No MIDI renderer available. Install BBC SO VST or FluidSynth."
            ) from e

    def stop(self) -> None:
        """Stop playback."""
        if self._sync_controller:
            self._sync_controller.stop()


# =============================================================================
# Convenience Functions
# =============================================================================

# Global controller
_orchestral_controller: OrchestralPlaybackController | None = None


async def play_orchestral(
    source: str | Path,
    smart_home: SmartHomeController | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """High-level API for orchestral playback with lights.

    LIGHT IS MUSIC IS SPECTRUM.

    Automatically detects MIDI vs audio and routes appropriately.

    Args:
        source: Path to MIDI (.mid) or audio (.wav/.mp3/.flac) file
        smart_home: SmartHomeController for light control
        **kwargs: Additional playback options

    Returns:
        Playback statistics

    Example:
        # From MIDI
        await play_orchestral("/path/to/beethoven.mid")

        # From audio
        await play_orchestral(
            "/path/to/symphony.wav",
            tempo_bpm=72,
            key="Cm",
            mode="minor",
            mood=MusicMood.DRAMATIC,
        )
    """
    global _orchestral_controller

    if _orchestral_controller is None or _orchestral_controller._smart_home != smart_home:
        _orchestral_controller = OrchestralPlaybackController(smart_home)

    source = Path(source)

    if source.suffix.lower() in (".mid", ".midi"):
        return await _orchestral_controller.play_midi(source, **kwargs)
    else:
        return await _orchestral_controller.play_audio(source, **kwargs)


def stop_orchestral() -> None:
    """Stop orchestral playback."""
    global _orchestral_controller
    if _orchestral_controller:
        _orchestral_controller.stop()


__all__ = [
    "OrchestralPlaybackConfig",
    "OrchestralPlaybackController",
    "analyze_midi_context",
    "play_orchestral",
    "stop_orchestral",
]
