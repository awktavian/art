"""BBC Symphony Orchestra — Virtuoso Sample Generator.

This module generates demonstration MIDI files for each BBC SO instrument,
showcasing all articulations and expression capabilities in a structured
60-second format:

    0:00-0:10  — Legato phrase (CC1 dynamics + CC21 vibrato)
    0:10-0:20  — Staccato/short passage (attack precision)
    0:20-0:30  — Dynamic swell pp→ff→pp (expression range)
    0:30-0:40  — Extended technique showcase (tremolo/trill/sul pont/muted)
    0:40-0:50  — Virtuosic passage (fast runs, ornaments)
    0:50-1:00  — Musical excerpt (real repertoire phrase)

Each sample is tuned according to virtuoso references and conductor philosophies.
"""

from __future__ import annotations

import math
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from .bbc_database import BBC_INSTRUMENTS_DATABASE, get_articulations
from .bbc_virtuoso import (
    TuningPreset,
    get_default_tuning,
)

if TYPE_CHECKING:
    pass


# =============================================================================
# MIDI CONSTANTS
# =============================================================================

TICKS_PER_BEAT = 480
TEMPO_BPM = 90  # Moderate tempo for demonstration
BEATS_PER_SECTION = 36  # ~10 seconds per section at 90 BPM


# =============================================================================
# PITCH RANGES BY INSTRUMENT FAMILY
# =============================================================================

# MIDI note ranges for each instrument (lowest, highest, comfortable_low, comfortable_high)
PITCH_RANGES: dict[str, tuple[int, int, int, int]] = {
    # Strings
    "violin_1_leader": (55, 96, 60, 88),  # G3-C7, comfortable D4-E6
    "violins_1": (55, 96, 60, 84),
    "violin_2_leader": (55, 96, 60, 84),
    "violins_2": (55, 96, 60, 84),
    "viola_leader": (48, 88, 53, 79),  # C3-E6, comfortable F3-G5
    "violas": (48, 88, 53, 79),
    "celli_leader": (36, 76, 41, 69),  # C2-E5, comfortable F2-A4
    "celli": (36, 76, 41, 69),
    "bass_leader": (28, 60, 33, 55),  # E1-C4, comfortable A1-G3
    "basses": (28, 60, 33, 55),
    # Woodwinds
    "flute": (60, 96, 65, 91),  # C4-C7, comfortable F4-G6
    "flutes_a3": (60, 96, 65, 88),
    "piccolo": (74, 108, 79, 103),  # D5-C8, comfortable G5-G7
    "oboe": (58, 91, 63, 86),  # Bb3-G6, comfortable Eb4-D6
    "oboes_a3": (58, 88, 63, 84),
    "clarinet": (50, 94, 55, 89),  # D3-Bb6, comfortable G3-F6
    "clarinets_a3": (50, 91, 55, 86),
    "bassoon": (34, 75, 39, 70),  # Bb1-Eb5, comfortable Eb2-Bb4
    "bassoons_a3": (34, 72, 39, 67),
    "bass_clarinet": (38, 82, 43, 77),  # D2-Bb5
    "contrabass_clarinet": (26, 70, 31, 65),  # D1-Bb4
    "contrabassoon": (22, 58, 27, 53),  # Bb0-Bb3
    "cor_anglais": (52, 84, 57, 79),  # E3-C6
    "bass_flute": (48, 84, 53, 79),  # C3-C6
    # Brass
    "horn": (41, 77, 46, 72),  # F2-F5, comfortable Bb2-C5
    "horns_a4": (41, 77, 46, 70),
    "trumpet": (55, 84, 60, 79),  # G3-C6, comfortable C4-G5
    "trumpets_a2": (55, 82, 60, 77),
    "tenor_trombone": (40, 72, 45, 67),  # E2-C5, comfortable A2-G4
    "tenor_trombones_a3": (40, 70, 45, 65),
    "bass_trombones_a2": (34, 65, 39, 60),  # Bb1-F4
    "tuba": (28, 58, 33, 53),  # E1-Bb3
    "contrabass_tuba": (24, 53, 29, 48),  # C1-F3
    "contrabass_trombone": (28, 58, 33, 53),  # E1-Bb3
    "cimbasso": (24, 53, 29, 48),  # C1-F3
    # Percussion (pitched)
    "timpani": (40, 57, 43, 55),  # E2-A3
    "harp": (24, 103, 36, 96),  # C1-G7
    "celeste": (60, 108, 65, 103),  # C4-C8
    "marimba": (45, 96, 53, 89),  # A2-C7
    "xylophone": (65, 108, 72, 103),  # F4-C8
    "glockenspiel": (79, 108, 84, 103),  # G5-C8
    "tubular_bells": (60, 77, 62, 75),  # C4-F5
    "vibraphone": (53, 89, 58, 84),  # F3-F6
    "crotales": (84, 108, 89, 103),  # C6-C8
}


def get_pitch_range(instrument_key: str) -> tuple[int, int, int, int]:
    """Get the pitch range for an instrument."""
    return PITCH_RANGES.get(instrument_key, (48, 84, 53, 79))


# =============================================================================
# KEYSWITCH MAPPINGS
# =============================================================================


def get_keyswitch_for_articulation(instrument_key: str, articulation: str) -> int:
    """Get the MIDI note number for a keyswitch.

    BBC SO uses low keyswitches starting at C0 (MIDI 12) or C-1 (MIDI 0).
    The order matches the articulation list order.
    """
    arts = get_articulations(instrument_key)
    try:
        idx = arts.index(articulation)
        # Start at C0 (MIDI 12) for keyswitches
        return 12 + idx
    except ValueError:
        return 12  # Default to first articulation


# =============================================================================
# CC CURVE GENERATORS
# =============================================================================


def generate_cc_curve(
    curve_type: str,
    start_val: int,
    end_val: int,
    num_points: int,
) -> list[int]:
    """Generate CC values for a curve shape.

    Args:
        curve_type: "linear", "exponential", "s_curve"
        start_val: Starting CC value
        end_val: Ending CC value
        num_points: Number of points to generate

    Returns:
        List of CC values
    """
    if num_points <= 1:
        return [start_val]

    values = []
    for i in range(num_points):
        t = i / (num_points - 1)  # 0 to 1

        if curve_type == "linear":
            factor = t
        elif curve_type == "exponential":
            factor = t * t
        elif curve_type == "s_curve":
            # Smooth S-curve using sine
            factor = (1 - math.cos(t * math.pi)) / 2
        else:
            factor = t

        val = int(start_val + (end_val - start_val) * factor)
        values.append(max(0, min(127, val)))

    return values


def generate_crescendo_diminuendo(
    min_val: int = 30,
    max_val: int = 110,
    num_points: int = 32,
) -> list[int]:
    """Generate a crescendo-diminuendo CC curve (hairpin dynamics)."""
    half = num_points // 2
    up = generate_cc_curve("s_curve", min_val, max_val, half)
    down = generate_cc_curve("s_curve", max_val, min_val, num_points - half)
    return up + down


def generate_vibrato_swell(
    base: int = 40,
    peak: int = 80,
    num_points: int = 32,
) -> list[int]:
    """Generate vibrato that swells on sustained notes."""
    # Start low, swell up, hold, then relax
    quarter = num_points // 4
    start = generate_cc_curve("exponential", base, peak, quarter)
    hold = [peak] * (num_points // 2)
    end = generate_cc_curve("linear", peak, base + 10, quarter)
    return (start + hold + end)[:num_points]


# =============================================================================
# MIDI EVENT BUILDER
# =============================================================================


@dataclass
class MIDIEvent:
    """A MIDI event with tick position."""

    tick: int
    event_type: str  # "note_on", "note_off", "cc", "program"
    channel: int
    data1: int
    data2: int

    def to_bytes(self, running_tick: int) -> tuple[bytes, int]:
        """Convert to MIDI bytes with delta time.

        Returns:
            (bytes, new_running_tick)
        """
        delta = self.tick - running_tick

        # Variable-length delta time
        delta_bytes = []
        if delta == 0:
            delta_bytes = [0]
        else:
            while delta > 0:
                byte = delta & 0x7F
                delta >>= 7
                if delta_bytes:
                    byte |= 0x80
                delta_bytes.insert(0, byte)

        # Event bytes
        if self.event_type == "note_on":
            status = 0x90 | (self.channel & 0x0F)
            event_bytes = bytes([status, self.data1 & 0x7F, self.data2 & 0x7F])
        elif self.event_type == "note_off":
            status = 0x80 | (self.channel & 0x0F)
            event_bytes = bytes([status, self.data1 & 0x7F, self.data2 & 0x7F])
        elif self.event_type == "cc":
            status = 0xB0 | (self.channel & 0x0F)
            event_bytes = bytes([status, self.data1 & 0x7F, self.data2 & 0x7F])
        else:
            event_bytes = b""

        return bytes(delta_bytes) + event_bytes, self.tick


class MIDIBuilder:
    """Builder for creating MIDI files with BBC SO articulations."""

    def __init__(self, ticks_per_beat: int = TICKS_PER_BEAT):
        self.ticks_per_beat = ticks_per_beat
        self.events: list[MIDIEvent] = []
        self.channel = 0

    def add_note(
        self,
        tick: int,
        pitch: int,
        velocity: int,
        duration_ticks: int,
    ) -> None:
        """Add a note on and note off event."""
        self.events.append(MIDIEvent(tick, "note_on", self.channel, pitch, velocity))
        self.events.append(MIDIEvent(tick + duration_ticks, "note_off", self.channel, pitch, 0))

    def add_keyswitch(self, tick: int, keyswitch_note: int) -> None:
        """Add a keyswitch to change articulation."""
        # Short keyswitch note
        self.events.append(MIDIEvent(tick, "note_on", self.channel, keyswitch_note, 100))
        self.events.append(MIDIEvent(tick + 10, "note_off", self.channel, keyswitch_note, 0))

    def add_cc(self, tick: int, cc_number: int, value: int) -> None:
        """Add a CC event."""
        self.events.append(MIDIEvent(tick, "cc", self.channel, cc_number, value))

    def add_cc_curve(
        self,
        start_tick: int,
        cc_number: int,
        values: list[int],
        interval_ticks: int = 20,
    ) -> None:
        """Add a series of CC events to create a curve."""
        for i, val in enumerate(values):
            self.add_cc(start_tick + i * interval_ticks, cc_number, val)

    def build(self) -> bytes:
        """Build the complete MIDI file."""
        # Sort events by tick
        self.events.sort(key=lambda e: (e.tick, e.event_type != "note_off"))

        # Build track data
        track_data = b""
        running_tick = 0

        for event in self.events:
            event_bytes, running_tick = event.to_bytes(running_tick)
            track_data += event_bytes

        # End of track
        track_data += b"\x00\xff\x2f\x00"

        # Track chunk
        track_chunk = b"MTrk" + struct.pack(">I", len(track_data)) + track_data

        # Header chunk (format 0, 1 track)
        header = b"MThd\x00\x00\x00\x06\x00\x00\x00\x01" + struct.pack(">H", self.ticks_per_beat)

        return header + track_chunk


# =============================================================================
# SECTION GENERATORS
# =============================================================================


def generate_legato_section(
    builder: MIDIBuilder,
    start_tick: int,
    instrument_key: str,
    tuning: TuningPreset,
) -> int:
    """Generate the legato phrase section (0:00-0:10).

    Returns:
        End tick
    """
    # Get pitch range
    _, _, low, high = get_pitch_range(instrument_key)
    mid = (low + high) // 2

    # Add keyswitch for legato if available
    arts = get_articulations(instrument_key)
    if "Legato" in arts:
        ks = get_keyswitch_for_articulation(instrument_key, "Legato")
        builder.add_keyswitch(start_tick, ks)
    elif "Long" in arts:
        ks = get_keyswitch_for_articulation(instrument_key, "Long")
        builder.add_keyswitch(start_tick, ks)

    # Generate CC1 crescendo-diminuendo curve
    cc1_curve = generate_crescendo_diminuendo(tuning.cc1_min, tuning.cc1_max, 32)
    builder.add_cc_curve(start_tick + TICKS_PER_BEAT, 1, cc1_curve, TICKS_PER_BEAT // 2)

    # Add vibrato swell if enabled
    if tuning.cc21_vibrato_swell:
        vib_curve = generate_vibrato_swell(
            tuning.cc21_vibrato_base, tuning.cc21_vibrato_base + 30, 32
        )
        builder.add_cc_curve(start_tick + TICKS_PER_BEAT, 21, vib_curve, TICKS_PER_BEAT // 2)

    # Melodic phrase (ascending then descending)
    notes = [mid, mid + 2, mid + 4, mid + 5, mid + 7, mid + 5, mid + 4, mid + 2]
    tick = start_tick + TICKS_PER_BEAT * 2

    overlap = tuning.legato_overlap_ticks
    for i, pitch in enumerate(notes):
        duration = TICKS_PER_BEAT * 4
        velocity = 80 + (i % 3) * 5
        builder.add_note(tick, pitch, velocity, duration + overlap)
        tick += duration

    return tick


def generate_staccato_section(
    builder: MIDIBuilder,
    start_tick: int,
    instrument_key: str,
    tuning: TuningPreset,
) -> int:
    """Generate the staccato/short passage section (0:10-0:20).

    Returns:
        End tick
    """
    _, _, low, high = get_pitch_range(instrument_key)
    mid = (low + high) // 2

    # Find best short articulation
    arts = get_articulations(instrument_key)
    short_arts = [a for a in arts if "Short" in a or "Spicc" in a or "Stac" in a]
    if short_arts:
        ks = get_keyswitch_for_articulation(instrument_key, short_arts[0])
        builder.add_keyswitch(start_tick, ks)
    elif "Short Hits" in arts:
        ks = get_keyswitch_for_articulation(instrument_key, "Short Hits")
        builder.add_keyswitch(start_tick, ks)

    # Set moderate dynamics
    builder.add_cc(start_tick, 1, 80)

    # Rhythmic pattern with velocity variation
    pattern = [mid, mid + 4, mid + 2, mid + 5, mid, mid + 4, mid + 7, mid + 2]
    tick = start_tick + TICKS_PER_BEAT

    for i, pitch in enumerate(pattern * 4):  # Repeat pattern 4 times
        duration = TICKS_PER_BEAT // 2  # Eighth notes
        velocity = 70 + (i % 4) * 10  # Accent pattern
        builder.add_note(tick, pitch, velocity, duration - 20)
        tick += duration

    return tick


def generate_dynamic_swell_section(
    builder: MIDIBuilder,
    start_tick: int,
    instrument_key: str,
    tuning: TuningPreset,
) -> int:
    """Generate the dynamic swell section pp→ff→pp (0:20-0:30).

    Returns:
        End tick
    """
    _, _, low, high = get_pitch_range(instrument_key)
    mid = (low + high) // 2

    # Use Long articulation
    arts = get_articulations(instrument_key)
    if "Long" in arts:
        ks = get_keyswitch_for_articulation(instrument_key, "Long")
        builder.add_keyswitch(start_tick, ks)

    # Full pp to ff to pp swell
    swell = generate_crescendo_diminuendo(20, 125, 64)
    builder.add_cc_curve(start_tick, 1, swell, TICKS_PER_BEAT // 4)

    # Add expression (CC11) layer
    expr_swell = generate_crescendo_diminuendo(40, 127, 64)
    builder.add_cc_curve(start_tick, 11, expr_swell, TICKS_PER_BEAT // 4)

    # Single sustained note with full swell
    tick = start_tick + TICKS_PER_BEAT
    duration = TICKS_PER_BEAT * 32  # Long sustained note
    builder.add_note(tick, mid + 2, 80, duration)

    return tick + duration + TICKS_PER_BEAT


def generate_extended_section(
    builder: MIDIBuilder,
    start_tick: int,
    instrument_key: str,
    tuning: TuningPreset,
) -> int:
    """Generate the extended technique showcase section (0:30-0:40).

    Returns:
        End tick
    """
    _, _, low, high = get_pitch_range(instrument_key)
    mid = (low + high) // 2

    arts = get_articulations(instrument_key)
    tick = start_tick + TICKS_PER_BEAT

    # Set moderate dynamics
    builder.add_cc(start_tick, 1, 85)

    # Try different extended techniques
    techniques_to_try = [
        "Tremolo",
        "Trill (Major 2nd)",
        "Long Flutter",
        "Long Sul Pont",
        "Long Harmonics",
        "Long (Muted)",
        "Long Cuivre",
        "Long Bisbigliando Trem",
    ]

    techniques_found = []
    for tech in techniques_to_try:
        if tech in arts:
            techniques_found.append(tech)
            if len(techniques_found) >= 3:
                break

    # Fallback to any available articulations
    if len(techniques_found) < 2:
        techniques_found = arts[:3]

    # Play each technique
    for tech in techniques_found:
        ks = get_keyswitch_for_articulation(instrument_key, tech)
        builder.add_keyswitch(tick, ks)
        tick += 20

        # Note for this technique
        duration = TICKS_PER_BEAT * 10
        builder.add_note(tick, mid, 80, duration)
        tick += duration + TICKS_PER_BEAT

    return tick


def generate_virtuosic_section(
    builder: MIDIBuilder,
    start_tick: int,
    instrument_key: str,
    tuning: TuningPreset,
) -> int:
    """Generate the virtuosic passage section (0:40-0:50).

    Returns:
        End tick
    """
    _, _, low, high = get_pitch_range(instrument_key)
    mid = (low + high) // 2

    arts = get_articulations(instrument_key)

    # Use spiccato or staccato for runs
    if "Short Spiccato" in arts:
        ks = get_keyswitch_for_articulation(instrument_key, "Short Spiccato")
    elif "Short Staccatissimo" in arts:
        ks = get_keyswitch_for_articulation(instrument_key, "Short Staccatissimo")
    else:
        ks = get_keyswitch_for_articulation(instrument_key, arts[0])
    builder.add_keyswitch(start_tick, ks)

    # Set dynamics
    builder.add_cc(start_tick, 1, 90)

    # Fast chromatic run up and down
    tick = start_tick + TICKS_PER_BEAT

    # Ascending chromatic
    for i in range(12):
        pitch = mid - 6 + i
        duration = TICKS_PER_BEAT // 4  # Sixteenth notes
        velocity = 75 + (i % 3) * 8
        builder.add_note(tick, pitch, velocity, duration - 10)
        tick += duration

    # Descending chromatic
    for i in range(12):
        pitch = mid + 6 - i
        duration = TICKS_PER_BEAT // 4
        velocity = 80 + (i % 3) * 8
        builder.add_note(tick, pitch, velocity, duration - 10)
        tick += duration

    # Arpeggio pattern
    arpeggio = [mid - 5, mid - 2, mid, mid + 3, mid + 7, mid + 3, mid, mid - 2]
    for _ in range(4):
        for pitch in arpeggio:
            duration = TICKS_PER_BEAT // 3  # Triplets
            builder.add_note(tick, pitch, 85, duration - 10)
            tick += duration

    return tick


def generate_musical_excerpt_section(
    builder: MIDIBuilder,
    start_tick: int,
    instrument_key: str,
    tuning: TuningPreset,
) -> int:
    """Generate a musical excerpt section (0:50-1:00).

    Uses a recognizable melodic pattern appropriate for the instrument.

    Returns:
        End tick
    """
    _, _, low, high = get_pitch_range(instrument_key)
    mid = (low + high) // 2

    arts = get_articulations(instrument_key)

    # Use legato for melodic excerpt
    if "Legato" in arts:
        ks = get_keyswitch_for_articulation(instrument_key, "Legato")
        builder.add_keyswitch(start_tick, ks)

    # Expressive dynamics
    expr_curve = generate_cc_curve("s_curve", 60, 100, 24)
    builder.add_cc_curve(start_tick, 1, expr_curve, TICKS_PER_BEAT // 2)

    # Vibrato swell
    if tuning.cc21_vibrato_swell:
        vib_curve = generate_vibrato_swell(40, 70, 24)
        builder.add_cc_curve(start_tick, 21, vib_curve, TICKS_PER_BEAT // 2)

    # A lyrical melody (inspired by Romantic era phrasing)
    # This is a generic beautiful phrase that works for most instruments
    melody = [
        (mid, TICKS_PER_BEAT * 2, 75),
        (mid + 2, TICKS_PER_BEAT * 2, 80),
        (mid + 4, TICKS_PER_BEAT * 3, 85),
        (mid + 2, TICKS_PER_BEAT, 78),
        (mid + 5, TICKS_PER_BEAT * 4, 90),
        (mid + 4, TICKS_PER_BEAT * 2, 82),
        (mid + 2, TICKS_PER_BEAT * 2, 75),
        (mid, TICKS_PER_BEAT * 4, 70),
    ]

    tick = start_tick + TICKS_PER_BEAT
    overlap = tuning.legato_overlap_ticks

    for pitch, duration, velocity in melody:
        builder.add_note(tick, pitch, velocity, duration + overlap)
        tick += duration

    return tick


# =============================================================================
# MAIN SAMPLE GENERATOR
# =============================================================================


def generate_virtuoso_sample(instrument_key: str) -> bytes:
    """Generate a complete 60-second virtuoso demonstration sample.

    Args:
        instrument_key: Key from BBC_INSTRUMENTS_DATABASE

    Returns:
        MIDI file bytes
    """
    if instrument_key not in BBC_INSTRUMENTS_DATABASE:
        raise ValueError(f"Unknown instrument: {instrument_key}")

    tuning = get_default_tuning(instrument_key)
    builder = MIDIBuilder()

    # Initialize CC values
    builder.add_cc(0, 1, tuning.cc1_min)  # CC1 Dynamics
    builder.add_cc(0, 7, 100)  # CC7 Volume
    builder.add_cc(0, 11, 100)  # CC11 Expression
    builder.add_cc(0, 17, tuning.cc17_release)  # CC17 Release
    builder.add_cc(0, 18, tuning.cc18_tightness)  # CC18 Tightness
    builder.add_cc(0, 21, tuning.cc21_vibrato_base)  # CC21 Vibrato

    tick = TICKS_PER_BEAT  # Start after 1 beat

    # Section 1: Legato phrase (0:00-0:10)
    tick = generate_legato_section(builder, tick, instrument_key, tuning)

    # Section 2: Staccato/short passage (0:10-0:20)
    tick = max(tick, TICKS_PER_BEAT * BEATS_PER_SECTION)
    tick = generate_staccato_section(builder, tick, instrument_key, tuning)

    # Section 3: Dynamic swell (0:20-0:30)
    tick = max(tick, TICKS_PER_BEAT * BEATS_PER_SECTION * 2)
    tick = generate_dynamic_swell_section(builder, tick, instrument_key, tuning)

    # Section 4: Extended technique showcase (0:30-0:40)
    tick = max(tick, TICKS_PER_BEAT * BEATS_PER_SECTION * 3)
    tick = generate_extended_section(builder, tick, instrument_key, tuning)

    # Section 5: Virtuosic passage (0:40-0:50)
    tick = max(tick, TICKS_PER_BEAT * BEATS_PER_SECTION * 4)
    tick = generate_virtuosic_section(builder, tick, instrument_key, tuning)

    # Section 6: Musical excerpt (0:50-1:00)
    tick = max(tick, TICKS_PER_BEAT * BEATS_PER_SECTION * 5)
    tick = generate_musical_excerpt_section(builder, tick, instrument_key, tuning)

    # All notes off at the end
    builder.add_cc(tick + TICKS_PER_BEAT * 2, 123, 0)

    return builder.build()


def generate_and_save_sample(
    instrument_key: str,
    output_dir: Path,
) -> Path:
    """Generate and save a virtuoso sample MIDI file.

    Args:
        instrument_key: Key from BBC_INSTRUMENTS_DATABASE
        output_dir: Directory to save the MIDI file

    Returns:
        Path to saved MIDI file
    """
    midi_bytes = generate_virtuoso_sample(instrument_key)

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{instrument_key}_virtuoso.mid"
    output_path.write_bytes(midi_bytes)

    return output_path


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "PITCH_RANGES",
    "MIDIBuilder",
    "MIDIEvent",
    "generate_and_save_sample",
    "generate_cc_curve",
    "generate_crescendo_diminuendo",
    "generate_vibrato_swell",
    "generate_virtuoso_sample",
    "get_keyswitch_for_articulation",
    "get_pitch_range",
]
