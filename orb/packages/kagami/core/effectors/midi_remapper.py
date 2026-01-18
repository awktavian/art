"""MIDI Instrument Remapper — Intelligent orchestral instrument assignment.

Many free MIDI files have wrong instrument assignments (guitars, pianos, etc.
when they should be orchestral). This module analyzes musical context and
assigns appropriate orchestral instruments.

Heuristics:
1. Note range → instrument family (bass notes → cellos/bass, high → violins)
2. Density → texture (sparse → solo, dense → ensemble)
3. Velocity variation → expression (flat → needs humanization)
4. Track name hints → instrument suggestions

Created: January 1, 2026
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pretty_midi

logger = logging.getLogger(__name__)


# =============================================================================
# General MIDI Orchestral Programs
# =============================================================================

# GM Program numbers for orchestral instruments
GM_ORCHESTRAL = {
    # Strings (40-49)
    "violin": 40,  # Violin
    "viola": 41,  # Viola
    "cello": 42,  # Cello
    "contrabass": 43,  # Contrabass
    "tremolo_strings": 44,  # Tremolo Strings
    "pizzicato": 45,  # Pizzicato Strings
    "harp": 46,  # Orchestral Harp
    "timpani": 47,  # Timpani
    "string_ensemble_1": 48,  # String Ensemble 1
    "string_ensemble_2": 49,  # String Ensemble 2
    # Brass (56-63)
    "trumpet": 56,  # Trumpet
    "trombone": 57,  # Trombone
    "tuba": 58,  # Tuba
    "muted_trumpet": 59,  # Muted Trumpet
    "french_horn": 60,  # French Horn
    "brass_section": 61,  # Brass Section
    "synth_brass_1": 62,  # Synth Brass 1
    "synth_brass_2": 63,  # Synth Brass 2
    # Woodwinds (64-79)
    "soprano_sax": 64,  # Soprano Sax
    "alto_sax": 65,  # Alto Sax
    "tenor_sax": 66,  # Tenor Sax
    "baritone_sax": 67,  # Baritone Sax
    "oboe": 68,  # Oboe
    "english_horn": 69,  # English Horn
    "bassoon": 70,  # Bassoon
    "clarinet": 71,  # Clarinet
    "piccolo": 72,  # Piccolo
    "flute": 73,  # Flute
    "recorder": 74,  # Recorder
    "pan_flute": 75,  # Pan Flute
}

# Pitch ranges for orchestral instruments (MIDI note numbers)
INSTRUMENT_RANGES = {
    # Strings
    "violin": (55, 103),  # G3 - G7
    "viola": (48, 91),  # C3 - G6
    "cello": (36, 76),  # C2 - E5
    "contrabass": (28, 60),  # E1 - C4
    "string_ensemble_1": (36, 96),  # Wide range for ensemble
    # Brass
    "trumpet": (54, 82),  # F#3 - A#5
    "french_horn": (41, 77),  # F2 - F5
    "trombone": (34, 72),  # A#1 - C5
    "tuba": (24, 55),  # C1 - G3
    "brass_section": (36, 84),  # Wide range for section
    # Woodwinds
    "flute": (60, 96),  # C4 - C7
    "piccolo": (74, 108),  # D5 - C8
    "oboe": (58, 91),  # A#3 - G6
    "clarinet": (50, 94),  # D3 - A#6
    "bassoon": (34, 75),  # A#1 - D#5
    # Percussion
    "timpani": (36, 60),  # C2 - C4
}


@dataclass
class TrackAnalysis:
    """Analysis of a MIDI track for remapping."""

    track_idx: int
    name: str
    original_program: int
    note_count: int
    low_note: int
    high_note: int
    avg_velocity: int
    velocity_variance: float
    note_density: float  # Notes per second
    suggested_instrument: str
    suggested_program: int
    confidence: float
    reasoning: str


def analyze_track(track_idx: int, inst: pretty_midi.Instrument, duration: float) -> TrackAnalysis:
    """Analyze a track and suggest appropriate orchestral instrument."""

    notes = inst.notes
    if not notes:
        return TrackAnalysis(
            track_idx=track_idx,
            name=inst.name or f"Track {track_idx}",
            original_program=inst.program,
            note_count=0,
            low_note=0,
            high_note=0,
            avg_velocity=0,
            velocity_variance=0,
            note_density=0,
            suggested_instrument="mute",
            suggested_program=-1,
            confidence=1.0,
            reasoning="Empty track",
        )

    # Basic stats
    pitches = [n.pitch for n in notes]
    velocities = [n.velocity for n in notes]
    low = min(pitches)
    high = max(pitches)
    avg_vel = sum(velocities) // len(velocities)
    vel_var = sum((v - avg_vel) ** 2 for v in velocities) / len(velocities)
    density = len(notes) / max(duration, 1.0)

    # Determine pitch center
    center = (low + high) / 2

    # Name hints
    name_lower = (inst.name or "").lower()

    # Decision logic
    suggested = None
    confidence = 0.7
    reasoning = []

    # Check track name hints first
    name_hints = {
        "violin": "violin",
        "viola": "viola",
        "cello": "cello",
        "bass": "contrabass",
        "string": "string_ensemble_1",
        "trumpet": "trumpet",
        "horn": "french_horn",
        "trombone": "trombone",
        "tuba": "tuba",
        "brass": "brass_section",
        "flute": "flute",
        "oboe": "oboe",
        "clarinet": "clarinet",
        "bassoon": "bassoon",
        "timpani": "timpani",
        "drum": "timpani",
    }

    for hint, instrument in name_hints.items():
        if hint in name_lower:
            suggested = instrument
            confidence = 0.9
            reasoning.append(f"Name contains '{hint}'")
            break

    # If no name hint, use pitch range
    if not suggested:
        # Very low (bass range)
        if high <= 55 and center < 48:
            if density < 2:  # Sparse = timpani or contrabass
                suggested = "contrabass" if vel_var > 100 else "timpani"
            else:
                suggested = "cello"
            reasoning.append(f"Low range (center={center:.0f})")

        # Low-mid (tenor/bass)
        elif center < 55:
            suggested = "cello" if high > 65 else "trombone"
            reasoning.append(f"Low-mid range (center={center:.0f})")

        # Mid range (alto)
        elif center < 65:
            if high - low > 24:  # Wide range = strings
                suggested = "viola" if density > 3 else "french_horn"
            else:
                suggested = "french_horn"
            reasoning.append(f"Mid range (center={center:.0f})")

        # High-mid (soprano/alto)
        elif center < 75:
            if density > 4:  # Dense = strings
                suggested = "violin"
            else:
                suggested = "trumpet" if high < 82 else "oboe"
            reasoning.append(f"High-mid range (center={center:.0f})")

        # High (soprano)
        else:
            suggested = "flute" if center < 85 else "piccolo"
            reasoning.append(f"High range (center={center:.0f})")

        confidence = 0.6

    # Adjust based on density
    if density > 8:
        reasoning.append(f"High density ({density:.1f} notes/s) suggests ensemble")
        if "string" not in suggested and "brass" not in suggested:
            if center < 60:
                suggested = "string_ensemble_1"
            else:
                suggested = "string_ensemble_1"
            confidence *= 0.9

    # Get GM program number
    program = GM_ORCHESTRAL.get(suggested, 48)  # Default to string ensemble

    return TrackAnalysis(
        track_idx=track_idx,
        name=inst.name or f"Track {track_idx}",
        original_program=inst.program,
        note_count=len(notes),
        low_note=low,
        high_note=high,
        avg_velocity=avg_vel,
        velocity_variance=vel_var,
        note_density=density,
        suggested_instrument=suggested or "string_ensemble_1",
        suggested_program=program,
        confidence=confidence,
        reasoning="; ".join(reasoning),
    )


def remap_midi(midi_path: Path, output_path: Path | None = None) -> Path:
    """Remap MIDI instruments to proper orchestral assignments.

    Args:
        midi_path: Input MIDI file
        output_path: Output path (default: adds _orchestral suffix)

    Returns:
        Path to remapped MIDI file
    """
    import pretty_midi as pm

    midi = pm.PrettyMIDI(str(midi_path))
    duration = midi.get_end_time()

    logger.info(f"🎼 Remapping: {midi_path.name}")
    logger.info(f"   Duration: {duration:.1f}s")

    # Analyze and remap each track
    analyses = []
    for i, inst in enumerate(midi.instruments):
        analysis = analyze_track(i, inst, duration)
        analyses.append(analysis)

        if analysis.note_count > 0:
            original_name = pm.program_to_instrument_name(inst.program)
            logger.info(
                f"   Track {i}: {original_name} → {analysis.suggested_instrument} "
                f"({analysis.confidence:.0%} - {analysis.reasoning})"
            )

            # Apply remapping
            inst.program = analysis.suggested_program

    # Humanize velocities if too flat
    for inst in midi.instruments:
        velocities = [n.velocity for n in inst.notes]
        if velocities:
            vel_range = max(velocities) - min(velocities)
            if vel_range < 20:  # Too flat - add variation
                import random

                for note in inst.notes:
                    # Add ±15% variation
                    variation = random.gauss(0, 0.15)
                    new_vel = int(note.velocity * (1 + variation))
                    note.velocity = max(30, min(127, new_vel))
                logger.info(f"   Humanized flat velocities for {inst.name}")

    # Save remapped MIDI
    if output_path is None:
        output_path = midi_path.with_stem(midi_path.stem + "_orchestral")

    midi.write(str(output_path))
    logger.info(f"   ✓ Saved: {output_path.name}")

    return output_path


def analyze_midi(midi_path: Path) -> list[TrackAnalysis]:
    """Analyze a MIDI file without modifying it.

    Returns:
        List of TrackAnalysis for each track
    """
    import pretty_midi as pm

    midi = pm.PrettyMIDI(str(midi_path))
    duration = midi.get_end_time()

    return [analyze_track(i, inst, duration) for i, inst in enumerate(midi.instruments)]


__all__ = [
    "GM_ORCHESTRAL",
    "INSTRUMENT_RANGES",
    "TrackAnalysis",
    "analyze_midi",
    "analyze_track",
    "remap_midi",
]
