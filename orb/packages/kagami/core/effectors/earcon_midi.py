"""Earcon MIDI Generator — Creates MIDI scores from earcon orchestrations.

Converts the high-level EarconDefinition orchestrations into actual MIDI files
that can be rendered through the BBC Symphony Orchestra pipeline.

Each MIDI file includes:
- Notes with proper timing, pitch, duration, velocity
- CC1 (dynamics) automation curves
- CC11 (expression) automation curves
- Keyswitch messages for articulation selection
- Tempo and time signature information

Colony: Forge (e₂)
Created: January 4, 2026
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

try:
    import pretty_midi
except ImportError:
    pretty_midi = None  # type: ignore[assignment]

from kagami.core.effectors.bbc_instruments import (
    BBC_CATALOG,
    CC_DYNAMICS,
    CC_EXPRESSION,
)
from kagami.core.effectors.earcon_orchestrator import (
    EarconDefinition,
    get_earcon_registry,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


# =============================================================================
# MIDI Generation Configuration
# =============================================================================

TICKS_PER_BEAT = 480  # Standard MIDI resolution
DEFAULT_VELOCITY = 80


@dataclass
class MIDIGeneratorConfig:
    """Configuration for MIDI generation."""

    output_dir: Path = Path.home() / ".kagami" / "earcons" / "midi"
    ticks_per_beat: int = TICKS_PER_BEAT
    add_expression_curves: bool = True
    add_keyswitches: bool = True
    keyswitch_lead_time: float = 0.05  # Seconds before note
    humanize_timing: float = 0.0  # Random timing variance (seconds)
    humanize_velocity: float = 0.0  # Random velocity variance (0-1)


# =============================================================================
# MIDI Generator
# =============================================================================


class EarconMIDIGenerator:
    """Generates MIDI files from earcon orchestrations.

    Takes EarconDefinition objects and produces MIDI files with:
    - Multi-track structure (one track per instrument)
    - Proper BBC SO keyswitch selection
    - CC1/CC11 automation curves
    - Humanization options
    """

    def __init__(self, config: MIDIGeneratorConfig | None = None):
        """Initialize the MIDI generator.

        Args:
            config: Configuration options. Uses defaults if None.
        """
        if pretty_midi is None:
            raise ImportError(
                "pretty_midi is required for MIDI generation. Install with: pip install pretty_midi"
            )

        self.config = config or MIDIGeneratorConfig()
        self.config.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_midi(self, earcon: EarconDefinition) -> pretty_midi.PrettyMIDI:
        """Generate a PrettyMIDI object from an earcon definition.

        Args:
            earcon: The earcon definition to convert

        Returns:
            PrettyMIDI object with all tracks
        """
        # Create MIDI object with correct tempo
        midi = pretty_midi.PrettyMIDI(initial_tempo=earcon.orchestration.tempo_bpm)

        # Add each voice as a separate track
        for i, voice in enumerate(earcon.orchestration.voices):
            instrument_info = BBC_CATALOG.get(voice.instrument_key)
            if not instrument_info:
                logger.warning(f"Unknown instrument: {voice.instrument_key}")
                continue

            # Create MIDI instrument track
            # Use program 0 (piano) as placeholder - BBC SO ignores this
            track = pretty_midi.Instrument(
                program=0,
                is_drum=False,
                name=f"{voice.instrument_key}_{i}",
            )

            # Add keyswitch if configured
            if self.config.add_keyswitches and voice.articulation:
                keyswitch = instrument_info.articulations.get(voice.articulation)
                if keyswitch is not None:
                    # Keyswitch before first note
                    first_note_time = min(n[0] for n in voice.notes) if voice.notes else 0
                    ks_time = max(0, first_note_time - self.config.keyswitch_lead_time)
                    track.notes.append(
                        pretty_midi.Note(
                            velocity=100,
                            pitch=keyswitch,
                            start=ks_time,
                            end=ks_time + 0.01,
                        )
                    )

            # Add notes
            for time, pitch, duration, velocity in voice.notes:
                # Optional humanization
                if self.config.humanize_timing > 0:
                    time += np.random.uniform(
                        -self.config.humanize_timing, self.config.humanize_timing
                    )
                    time = max(0, time)

                if self.config.humanize_velocity > 0:
                    vel_var = int(velocity * self.config.humanize_velocity)
                    velocity += np.random.randint(-vel_var, vel_var + 1)
                    velocity = max(1, min(127, velocity))

                track.notes.append(
                    pretty_midi.Note(
                        velocity=velocity,
                        pitch=pitch,
                        start=time,
                        end=time + duration,
                    )
                )

            # Add CC1 (dynamics) automation
            if self.config.add_expression_curves and voice.cc1_dynamics:
                self._add_cc_curve(track, CC_DYNAMICS, voice.cc1_dynamics)
            else:
                # Default dynamics if no curve specified
                default_cc1 = instrument_info.default_cc1
                track.control_changes.append(
                    pretty_midi.ControlChange(number=CC_DYNAMICS, value=default_cc1, time=0)
                )

            # Add CC11 (expression) automation
            if self.config.add_expression_curves and voice.cc11_expression:
                self._add_cc_curve(track, CC_EXPRESSION, voice.cc11_expression)
            else:
                # Default expression if no curve specified
                default_cc11 = instrument_info.default_cc11
                track.control_changes.append(
                    pretty_midi.ControlChange(number=CC_EXPRESSION, value=default_cc11, time=0)
                )

            midi.instruments.append(track)

        return midi

    def _add_cc_curve(
        self,
        track: pretty_midi.Instrument,
        cc_number: int,
        keyframes: list[tuple[float, int]],
    ) -> None:
        """Add CC automation curve to a track.

        Interpolates between keyframes for smooth curves.

        Args:
            track: MIDI instrument track
            cc_number: CC number (1=dynamics, 11=expression)
            keyframes: List of (time, value) tuples
        """
        if len(keyframes) < 2:
            # Single point - just add it
            for time, value in keyframes:
                track.control_changes.append(
                    pretty_midi.ControlChange(number=cc_number, value=value, time=time)
                )
            return

        # Interpolate between keyframes
        resolution = 0.05  # 50ms between CC messages

        for i in range(len(keyframes) - 1):
            t1, v1 = keyframes[i]
            t2, v2 = keyframes[i + 1]

            # Number of steps between keyframes
            steps = max(1, int((t2 - t1) / resolution))

            for step in range(steps):
                t = t1 + (t2 - t1) * step / steps
                # Linear interpolation
                alpha = step / steps
                v = int(v1 + (v2 - v1) * alpha)
                v = max(0, min(127, v))

                track.control_changes.append(
                    pretty_midi.ControlChange(number=cc_number, value=v, time=t)
                )

        # Add final keyframe
        track.control_changes.append(
            pretty_midi.ControlChange(
                number=cc_number, value=keyframes[-1][1], time=keyframes[-1][0]
            )
        )

    def save_midi(self, earcon: EarconDefinition, filename: str | None = None) -> Path:
        """Generate and save MIDI file for an earcon.

        Args:
            earcon: The earcon definition
            filename: Optional custom filename. Defaults to earcon name.

        Returns:
            Path to the saved MIDI file
        """
        midi = self.generate_midi(earcon)
        filename = filename or f"{earcon.name}.mid"
        output_path = self.config.output_dir / filename
        midi.write(str(output_path))
        logger.info(f"Saved MIDI: {output_path}")
        return output_path

    def generate_all_earcons(self) -> dict[str, Path]:
        """Generate MIDI files for all registered earcons.

        Returns:
            Dict mapping earcon names to their MIDI file paths
        """
        registry = get_earcon_registry()
        results = {}

        for name, earcon in registry.items():
            try:
                path = self.save_midi(earcon)
                results[name] = path
                logger.info(f"Generated MIDI for {name}")
            except Exception as e:
                logger.error(f"Failed to generate MIDI for {name}: {e}")

        logger.info(f"Generated {len(results)}/{len(registry)} MIDI files")
        return results


# =============================================================================
# Trajectory to MIDI Pan
# =============================================================================


def trajectory_to_pan_automation(
    earcon: EarconDefinition,
    sample_rate: float = 20.0,  # Pan changes per second
) -> list[tuple[float, float]]:
    """Convert spatial trajectory to pan automation.

    Note: This is a simplified stereo pan. Full spatialization
    happens in the VBAP rendering stage.

    Args:
        earcon: Earcon with spatial trajectory
        sample_rate: Pan automation resolution

    Returns:
        List of (time, pan) tuples where pan is -1 to 1
    """
    trajectory = earcon.get_trajectory()
    duration = earcon.duration
    num_samples = int(duration * sample_rate)

    automation = []
    for i in range(num_samples + 1):
        t_ratio = i / num_samples
        t = t_ratio * duration

        # Find surrounding keyframes
        pos = None
        for j, (kf_ratio, kf_pos) in enumerate(trajectory.keyframes):
            if kf_ratio >= t_ratio:
                if j == 0:
                    pos = kf_pos
                else:
                    # Interpolate
                    prev_ratio, prev_pos = trajectory.keyframes[j - 1]
                    alpha = (t_ratio - prev_ratio) / (kf_ratio - prev_ratio)
                    pos_az = prev_pos.az + (kf_pos.az - prev_pos.az) * alpha
                    # Convert azimuth to pan (-1 to 1)
                    pan = np.clip(pos_az / 90.0, -1.0, 1.0)
                    automation.append((t, float(pan)))
                break
        else:
            # Past last keyframe
            pos = trajectory.keyframes[-1][1]
            pan = np.clip(pos.az / 90.0, -1.0, 1.0)
            automation.append((t, float(pan)))

    return automation


# =============================================================================
# Convenience Functions
# =============================================================================


def generate_earcon_midi(earcon_name: str, output_dir: Path | None = None) -> Path | None:
    """Generate MIDI file for a single earcon by name.

    Args:
        earcon_name: Name of the earcon
        output_dir: Optional output directory

    Returns:
        Path to generated MIDI file, or None if earcon not found
    """
    from kagami.core.effectors.earcon_orchestrator import get_earcon

    earcon = get_earcon(earcon_name)
    if not earcon:
        logger.error(f"Earcon not found: {earcon_name}")
        return None

    config = MIDIGeneratorConfig()
    if output_dir:
        config.output_dir = output_dir

    generator = EarconMIDIGenerator(config)
    return generator.save_midi(earcon)


def generate_all_earcon_midis(output_dir: Path | None = None) -> dict[str, Path]:
    """Generate MIDI files for all registered earcons.

    Args:
        output_dir: Optional output directory

    Returns:
        Dict mapping earcon names to MIDI file paths
    """
    config = MIDIGeneratorConfig()
    if output_dir:
        config.output_dir = output_dir

    generator = EarconMIDIGenerator(config)
    return generator.generate_all_earcons()


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "EarconMIDIGenerator",
    "MIDIGeneratorConfig",
    "generate_all_earcon_midis",
    "generate_earcon_midi",
    "trajectory_to_pan_automation",
]
