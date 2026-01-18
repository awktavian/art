"""
Orchestrator — MIDI composition and orchestral mixing.

Creates MIDI files and mixes rendered stems with proper orchestral staging.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

import numpy as np
import soundfile as sf
from midiutil import MIDIFile


class Instrument(str, Enum):
    """Available BBC Symphony Orchestra instruments."""

    # Strings
    VIOLINS_1 = "violins_1"
    VIOLINS_2 = "violins_2"
    VIOLAS = "violas"
    CELLI = "celli"
    BASSES = "basses"

    # Woodwinds
    FLUTES = "flutes"
    OBOES = "oboes"
    CLARINETS = "clarinets"
    BASSOONS = "bassoons"

    # Brass
    HORNS = "horns"
    TRUMPETS = "trumpets"
    TROMBONES = "trombones"
    TUBA = "tuba"

    # Percussion
    TIMPANI = "timpani"
    HARP = "harp"


@dataclass
class Note:
    """A single note in a composition."""

    pitch: int  # MIDI pitch (60 = C4)
    time: float  # Start time in beats
    duration: float  # Duration in beats
    velocity: int = 100  # 0-127


@dataclass
class InstrumentPart:
    """A single instrument's part in a composition."""

    instrument: Instrument
    notes: list[Note] = field(default_factory=list)
    channel: int = 0


# Orchestral staging - standard concert hall positions
ORCHESTRAL_STAGING = {
    # Strings - left to right arc
    Instrument.VIOLINS_1: {"gain": 0.0, "pan": -0.35},
    Instrument.VIOLINS_2: {"gain": -2.0, "pan": -0.15},
    Instrument.VIOLAS: {"gain": -1.0, "pan": 0.1},
    Instrument.CELLI: {"gain": 0.0, "pan": 0.25},
    Instrument.BASSES: {"gain": -1.0, "pan": 0.35},
    # Woodwinds - center-left
    Instrument.FLUTES: {"gain": -2.0, "pan": -0.15},
    Instrument.OBOES: {"gain": -2.0, "pan": -0.05},
    Instrument.CLARINETS: {"gain": -3.0, "pan": 0.05},
    Instrument.BASSOONS: {"gain": -2.0, "pan": 0.15},
    # Brass - center-right, powerful
    Instrument.HORNS: {"gain": 1.0, "pan": -0.1},
    Instrument.TRUMPETS: {"gain": 0.0, "pan": 0.1},
    Instrument.TROMBONES: {"gain": 0.0, "pan": 0.2},
    Instrument.TUBA: {"gain": -1.0, "pan": 0.25},
    # Percussion - center-back
    Instrument.TIMPANI: {"gain": 2.0, "pan": 0.0},
    Instrument.HARP: {"gain": -1.0, "pan": -0.3},
}


class Composer:
    """Compose orchestral music with BBC Symphony Orchestra.

    Example:
        composer = Composer(tempo=108)

        # Beethoven's 5th opening
        composer.add_notes(Instrument.VIOLINS_1, [
            Note(67, 0.0, 0.4, 100),  # G
            Note(67, 0.5, 0.4, 100),  # G
            Note(67, 1.0, 0.4, 100),  # G
            Note(63, 1.5, 2.5, 110),  # Eb (fermata)
        ])

        # Render
        await composer.render("/tmp/beethoven.wav")
    """

    def __init__(self, tempo: int = 120, time_signature: tuple[int, int] = (4, 4)):
        self.tempo = tempo
        self.time_signature = time_signature
        self.parts: dict[Instrument, InstrumentPart] = {}

    def add_notes(self, instrument: Instrument, notes: list[Note]) -> None:
        """Add notes to an instrument part."""
        if instrument not in self.parts:
            self.parts[instrument] = InstrumentPart(instrument=instrument)
        self.parts[instrument].notes.extend(notes)

    def add_instrument(self, instrument: Instrument, notes: list[Note]) -> None:
        """Alias for add_notes."""
        self.add_notes(instrument, notes)

    def to_midi(self, output_dir: Path) -> dict[Instrument, Path]:
        """Export each instrument part to a separate MIDI file.

        Returns:
            Dict mapping instrument to MIDI file path
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        midi_files = {}

        for instrument, part in self.parts.items():
            if not part.notes:
                continue

            midi = MIDIFile(1)
            midi.addTempo(0, 0, self.tempo)
            midi.addTrackName(0, 0, instrument.value)

            for note in part.notes:
                midi.addNote(
                    track=0,
                    channel=part.channel,
                    pitch=note.pitch,
                    time=note.time,
                    duration=note.duration,
                    volume=note.velocity,
                )

            midi_path = output_dir / f"{instrument.value}.mid"
            with open(midi_path, "wb") as f:
                midi.writeFile(f)

            midi_files[instrument] = midi_path

        return midi_files

    def get_duration_beats(self) -> float:
        """Get the total duration in beats."""
        max_time = 0.0
        for part in self.parts.values():
            for note in part.notes:
                end_time = note.time + note.duration
                if end_time > max_time:
                    max_time = end_time
        return max_time

    def get_duration_seconds(self) -> float:
        """Get the total duration in seconds."""
        beats = self.get_duration_beats()
        return beats * 60.0 / self.tempo


class OrchestraMixer:
    """Mix rendered orchestral stems with proper staging."""

    def __init__(self, sample_rate: int = 48000):
        self.sr = sample_rate

    def mix(
        self,
        stems: dict[Instrument, Path],
        output_path: Path,
        staging: dict[Instrument, dict] | None = None,
    ) -> dict:
        """Mix stems with orchestral staging.

        Args:
            stems: Dict mapping instrument to WAV file path
            output_path: Output WAV file path
            staging: Optional custom staging (default: ORCHESTRAL_STAGING)

        Returns:
            Mix statistics
        """
        staging = staging or ORCHESTRAL_STAGING

        # Load all stems
        audio_data = {}
        min_length = float("inf")

        for instrument, wav_path in stems.items():
            audio, sr = sf.read(wav_path)
            if sr != self.sr:
                # Resample would go here - for now assume matching SR
                pass

            # Get staging for this instrument
            config = staging.get(instrument, {"gain": 0.0, "pan": 0.0})

            # Apply gain
            gain_linear = 10 ** (config["gain"] / 20)
            audio = audio * gain_linear

            # Ensure stereo
            if len(audio.shape) == 1:
                audio = np.column_stack([audio, audio])

            # Apply pan
            pan = config["pan"]
            left_gain = np.sqrt(0.5 - 0.5 * pan)
            right_gain = np.sqrt(0.5 + 0.5 * pan)
            audio[:, 0] *= left_gain
            audio[:, 1] *= right_gain

            audio_data[instrument] = audio
            min_length = min(min_length, len(audio))

        # Trim to same length
        for instrument in audio_data:
            audio_data[instrument] = audio_data[instrument][: int(min_length)]

        # Sum all stems
        mix = np.zeros((int(min_length), 2))
        for audio in audio_data.values():
            mix += audio

        # Normalize to -6 dBFS headroom
        peak = np.max(np.abs(mix))
        target_peak = 10 ** (-6 / 20)
        if peak > 0:
            mix = mix * (target_peak / peak)

        # Write output
        sf.write(output_path, mix, self.sr)

        # Return stats
        final_peak = np.max(np.abs(mix))
        rms = np.sqrt(np.mean(mix**2))

        return {
            "duration_seconds": len(mix) / self.sr,
            "peak_db": 20 * np.log10(final_peak + 1e-10),
            "rms_db": 20 * np.log10(rms + 1e-10),
            "instruments": len(audio_data),
        }
