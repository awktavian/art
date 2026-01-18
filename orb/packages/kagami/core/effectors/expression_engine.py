"""Expression Engine — MIDI CC Automation and Articulation Detection.

Transforms raw MIDI into expressive performances by:
- Generating CC1 (dynamics) and CC11 (expression) automation curves
- Detecting and applying appropriate articulations
- Inserting keyswitches for BBC Symphony Orchestra
- Humanizing velocity with natural variance
- Adding rubato and tempo variation

Colony: Forge (e₂)
Created: January 1, 2026
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    import pretty_midi

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================


class ExpressionStyle(Enum):
    """Musical expression style presets."""

    ROMANTIC = "romantic"  # Large dynamics, rubato, expressive
    BAROQUE = "baroque"  # Terraced dynamics, precise timing
    CLASSICAL = "classical"  # Balanced dynamics, moderate rubato
    MODERN = "modern"  # Sharp dynamics, precise
    FILM_SCORE = "film_score"  # Dramatic dynamics, sweeping gestures
    MINIMALIST = "minimalist"  # Subtle dynamics, steady tempo


@dataclass
class ExpressionConfig:
    """Expression engine configuration."""

    style: ExpressionStyle = ExpressionStyle.ROMANTIC

    # CC1 Dynamics
    dynamics_min: int = 40  # Minimum CC1 value (pianissimo)
    dynamics_max: int = 127  # Maximum CC1 value (fortissimo)
    dynamics_curve: float = 0.7  # Curve shape (0=linear, 1=exponential)

    # CC11 Expression
    expression_min: int = 60  # Minimum CC11 value
    expression_max: int = 127  # Maximum CC11 value
    phrase_swell: float = 0.15  # Swell amount at phrase peaks

    # Velocity
    velocity_humanize: float = 0.1  # Random variance (0-0.3)
    velocity_accent_boost: int = 15  # Accent velocity boost

    # Timing
    rubato_amount: float = 0.02  # Timing variance in seconds
    anticipate_downbeats: bool = True  # Slight anticipation on downbeats

    # Articulation thresholds
    staccato_threshold: float = 0.15  # Notes shorter than this = staccato
    legato_threshold: float = 0.05  # Gap smaller than this = legato


# =============================================================================
# Style Presets
# =============================================================================

STYLE_PRESETS: dict[ExpressionStyle, ExpressionConfig] = {
    ExpressionStyle.ROMANTIC: ExpressionConfig(
        style=ExpressionStyle.ROMANTIC,
        dynamics_min=30,
        dynamics_max=127,
        dynamics_curve=0.8,
        expression_min=50,
        phrase_swell=0.2,
        velocity_humanize=0.12,
        rubato_amount=0.03,
    ),
    ExpressionStyle.BAROQUE: ExpressionConfig(
        style=ExpressionStyle.BAROQUE,
        dynamics_min=60,
        dynamics_max=100,
        dynamics_curve=0.3,
        expression_min=70,
        phrase_swell=0.05,
        velocity_humanize=0.05,
        rubato_amount=0.005,
        anticipate_downbeats=False,
    ),
    ExpressionStyle.CLASSICAL: ExpressionConfig(
        style=ExpressionStyle.CLASSICAL,
        dynamics_min=45,
        dynamics_max=115,
        dynamics_curve=0.5,
        expression_min=60,
        phrase_swell=0.12,
        velocity_humanize=0.08,
        rubato_amount=0.015,
    ),
    ExpressionStyle.MODERN: ExpressionConfig(
        style=ExpressionStyle.MODERN,
        dynamics_min=40,
        dynamics_max=127,
        dynamics_curve=0.4,
        expression_min=65,
        phrase_swell=0.08,
        velocity_humanize=0.05,
        rubato_amount=0.005,
    ),
    ExpressionStyle.FILM_SCORE: ExpressionConfig(
        style=ExpressionStyle.FILM_SCORE,
        dynamics_min=20,
        dynamics_max=127,
        dynamics_curve=0.9,
        expression_min=40,
        phrase_swell=0.25,
        velocity_humanize=0.1,
        rubato_amount=0.02,
    ),
    ExpressionStyle.MINIMALIST: ExpressionConfig(
        style=ExpressionStyle.MINIMALIST,
        dynamics_min=60,
        dynamics_max=90,
        dynamics_curve=0.2,
        expression_min=75,
        phrase_swell=0.03,
        velocity_humanize=0.03,
        rubato_amount=0.0,
        anticipate_downbeats=False,
    ),
}


# =============================================================================
# BBC Symphony Orchestra Keyswitches
# =============================================================================

# BBC SO Core/Pro keyswitches - extracted from BBC SO v1.5.0 patch files
# Source: bbc_instruments.py (authoritative mapping from .zmulti files)
# Keyswitches start at C-1 (MIDI 12) for most instruments
BBC_KEYSWITCHES: dict[str, int] = {
    # Sustained articulations (strings)
    "legato": 12,  # C-1 - smooth connected notes
    "long": 13,  # C#-1 - sustained
    "long cs": 14,  # D-1 - con sordino (muted)
    "long flautando": 15,  # D#-1 - light/airy
    "long sul tasto": 16,  # E-1 - over fingerboard
    "long sul pont": 17,  # F-1 - on bridge (glassy)
    "long harmonics": 18,  # F#-1 - harmonic overtones
    "long marcato attack": 19,  # G-1 - accented start
    # Short articulations (strings)
    "short spiccato": 20,  # G#-1 - bounced bow
    "spiccato": 20,  # alias
    "short spiccato cs": 21,  # A-1 - spiccato con sordino
    "short staccato": 22,  # A#-1 - detached
    "staccato": 22,  # alias
    "staccatissimo": 22,  # alias
    "short": 22,  # alias
    "short pizzicato": 23,  # B-1 - plucked
    "pizzicato": 23,  # alias
    "pizz": 23,  # alias
    "short pizzicato bartok": 24,  # C0 - snap pizz
    "short col legno": 25,  # C#0 - wood of bow
    "col_legno": 25,  # alias
    "short harmonics": 26,  # D0 - harmonic pluck
    # Tremolo/Trills (strings)
    "tremolo": 27,  # D#0 - rapid repetition
    "tremolo cs": 28,  # E0 - tremolo con sordino
    "tremolo sul pont": 29,  # F0 - tremolo on bridge
    "trill": 30,  # F#0 - alternating notes (major 2nd)
    "trill major": 30,  # alias
    "trill minor": 31,  # G0 - trill minor 2nd
    # Brass/Wind sustained
    "long cuivre": 14,  # brassy/forced
    "long sfz": 15,  # sforzando attack
    "long flutter": 13,  # flutter tongue (winds)
    # Brass/Wind short
    "short marcato": 16,  # accented short
    "marcato": 16,  # alias
    # Percussion
    "short hits": 12,  # basic hit
    "short damped": 12,  # damped hit
    "long rolls": 13,  # sustained roll
    "long trills": 12,  # trill/roll
}

# Articulation name aliases (normalize different names to keyswitch lookup)
ARTICULATION_ALIASES: dict[str, str] = {
    "leg": "legato",
    "marc": "marcato",
    "ten": "tenuto",
    "stacc": "staccato",
    "pizz": "pizzicato",
    "trem": "tremolo",
    "spicc": "spiccato",
    "sfz": "sforzando",
}


def get_keyswitch_for_articulation(articulation: str) -> int | None:
    """Get the BBC SO keyswitch MIDI note for an articulation.

    Args:
        articulation: Articulation name (e.g., "legato", "spiccato")

    Returns:
        MIDI note number for keyswitch, or None if not found
    """
    # Normalize articulation name
    art_lower = articulation.lower().strip()

    # Check aliases first
    if art_lower in ARTICULATION_ALIASES:
        art_lower = ARTICULATION_ALIASES[art_lower]

    return BBC_KEYSWITCHES.get(art_lower)


# =============================================================================
# Articulation Detection
# =============================================================================


@dataclass
class ArticulationEvent:
    """Articulation change event."""

    time: float  # Time in seconds
    articulation: str  # Articulation name
    keyswitch: int | None = None  # MIDI note for keyswitch

    def __post_init__(self):
        """Auto-populate keyswitch if not provided."""
        if self.keyswitch is None:
            self.keyswitch = get_keyswitch_for_articulation(self.articulation)


@dataclass
class CCEvent:
    """MIDI CC event."""

    time: float
    cc_number: int
    value: int


@dataclass
class NoteAnalysis:
    """Analysis of a single note."""

    start: float
    end: float
    pitch: int
    velocity: int
    duration: float
    gap_to_next: float | None
    is_legato: bool
    is_staccato: bool
    is_accent: bool
    suggested_articulation: str


def detect_articulations(
    notes: list,
    config: ExpressionConfig,
) -> tuple[list[NoteAnalysis], list[ArticulationEvent]]:
    """Analyze notes and detect appropriate articulations.

    Args:
        notes: List of pretty_midi.Note objects
        config: Expression configuration

    Returns:
        Tuple of (note analyses, articulation events)
    """
    if not notes:
        return [], []

    # Sort notes by start time
    sorted_notes = sorted(notes, key=lambda n: n.start)

    analyses = []
    articulation_events = []
    current_articulation = "long"

    for i, note in enumerate(sorted_notes):
        duration = note.end - note.start

        # Calculate gap to next note
        gap_to_next = None
        if i < len(sorted_notes) - 1:
            gap_to_next = sorted_notes[i + 1].start - note.end

        # Detect articulation characteristics
        is_staccato = duration < config.staccato_threshold
        is_legato = gap_to_next is not None and gap_to_next < config.legato_threshold

        # Detect accents (high velocity relative to surrounding)
        is_accent = False
        if i > 0 and i < len(sorted_notes) - 1:
            prev_vel = sorted_notes[i - 1].velocity
            next_vel = sorted_notes[i + 1].velocity
            avg_vel = (prev_vel + next_vel) / 2
            is_accent = note.velocity > avg_vel + 15

        # Determine suggested articulation
        if is_staccato:
            if duration < 0.08:
                suggested = "staccatissimo"
            else:
                suggested = "spiccato"
        elif is_legato:
            suggested = "legato"
        else:
            suggested = "long"

        analyses.append(
            NoteAnalysis(
                start=note.start,
                end=note.end,
                pitch=note.pitch,
                velocity=note.velocity,
                duration=duration,
                gap_to_next=gap_to_next,
                is_legato=is_legato,
                is_staccato=is_staccato,
                is_accent=is_accent,
                suggested_articulation=suggested,
            )
        )

        # Generate articulation change events
        if suggested != current_articulation:
            articulation_events.append(
                ArticulationEvent(
                    time=note.start - 0.01,  # Slightly before note
                    articulation=suggested,
                )
            )
            current_articulation = suggested

    return analyses, articulation_events


# =============================================================================
# Phrase Detection
# =============================================================================


@dataclass
class Phrase:
    """Musical phrase."""

    start: float
    end: float
    peak_time: float  # Time of dynamic peak
    intensity: float  # 0-1 overall intensity


def detect_phrases(notes: list, min_gap: float = 0.5) -> list[Phrase]:
    """Detect musical phrases based on gaps between notes.

    Args:
        notes: List of pretty_midi.Note objects
        min_gap: Minimum gap to consider phrase break

    Returns:
        List of detected phrases
    """
    if not notes:
        return []

    sorted_notes = sorted(notes, key=lambda n: n.start)

    phrases = []
    phrase_start = sorted_notes[0].start
    phrase_notes = [sorted_notes[0]]

    for i in range(1, len(sorted_notes)):
        note = sorted_notes[i]
        prev_note = sorted_notes[i - 1]
        gap = note.start - prev_note.end

        if gap >= min_gap:
            # End current phrase
            phrases.append(_analyze_phrase(phrase_start, prev_note.end, phrase_notes))
            phrase_start = note.start
            phrase_notes = [note]
        else:
            phrase_notes.append(note)

    # Final phrase
    if phrase_notes:
        phrases.append(_analyze_phrase(phrase_start, sorted_notes[-1].end, phrase_notes))

    return phrases


def _analyze_phrase(start: float, end: float, notes: list) -> Phrase:
    """Analyze a phrase to find peak and intensity."""
    # Find velocity peak
    max_vel = 0
    peak_time = start
    total_vel = 0

    for note in notes:
        if note.velocity > max_vel:
            max_vel = note.velocity
            peak_time = (note.start + note.end) / 2
        total_vel += note.velocity

    avg_vel = total_vel / len(notes) if notes else 64
    intensity = avg_vel / 127.0

    return Phrase(
        start=start,
        end=end,
        peak_time=peak_time,
        intensity=intensity,
    )


# =============================================================================
# CC Curve Generation
# =============================================================================


def generate_dynamics_curve(
    phrases: list[Phrase],
    duration: float,
    resolution: float = 0.05,
    config: ExpressionConfig | None = None,
) -> list[CCEvent]:
    """Generate CC1 dynamics curve based on phrases.

    Args:
        phrases: Detected phrases
        duration: Total duration in seconds
        resolution: Time resolution for CC events
        config: Expression configuration

    Returns:
        List of CC events for dynamics (CC1)
    """
    cfg = config or ExpressionConfig()
    events = []

    if not phrases:
        # Flat dynamics if no phrases
        events.append(CCEvent(time=0, cc_number=1, value=cfg.dynamics_min))
        return events

    # Generate curve points
    num_points = int(duration / resolution) + 1

    for i in range(num_points):
        t = i * resolution

        # Find containing phrase
        containing_phrase = None
        for phrase in phrases:
            if phrase.start <= t <= phrase.end:
                containing_phrase = phrase
                break

        if containing_phrase is None:
            # Between phrases - use minimum
            value = cfg.dynamics_min
        else:
            # Within phrase - create arc towards peak
            phrase_duration = containing_phrase.end - containing_phrase.start

            # Guard against zero/tiny duration (instant phrase)
            if phrase_duration < 0.001:
                # Instant phrase - use intensity-scaled value
                range_val = cfg.dynamics_max - cfg.dynamics_min
                value = int(cfg.dynamics_min + range_val * containing_phrase.intensity)
                value = max(cfg.dynamics_min, min(cfg.dynamics_max, value))
            else:
                phrase_pos = (t - containing_phrase.start) / phrase_duration

                # Distance to peak (0-1), clamped to valid range
                peak_pos = (containing_phrase.peak_time - containing_phrase.start) / phrase_duration
                # Clamp peak_pos to [0, 1] in case peak_time is outside phrase bounds
                peak_pos = max(0.0, min(1.0, peak_pos))
                dist_to_peak = abs(phrase_pos - peak_pos)
                # Clamp dist_to_peak to [0, 1] to prevent negative swell
                dist_to_peak = min(1.0, dist_to_peak)

                # Inverse distance for swell (now guaranteed [0, 1])
                swell = 1.0 - dist_to_peak

                # Apply curve shape (swell is now guaranteed non-negative)
                swell = swell**cfg.dynamics_curve

                # Calculate value
                range_val = cfg.dynamics_max - cfg.dynamics_min
                value = int(cfg.dynamics_min + swell * range_val * containing_phrase.intensity)
                value = max(cfg.dynamics_min, min(cfg.dynamics_max, value))

        events.append(CCEvent(time=t, cc_number=1, value=value))

    return _simplify_cc_events(events, threshold=3)


def generate_expression_curve(
    phrases: list[Phrase],
    duration: float,
    resolution: float = 0.05,
    config: ExpressionConfig | None = None,
) -> list[CCEvent]:
    """Generate CC11 expression curve for phrase shaping.

    Args:
        phrases: Detected phrases
        duration: Total duration in seconds
        resolution: Time resolution
        config: Expression configuration

    Returns:
        List of CC events for expression (CC11)
    """
    cfg = config or ExpressionConfig()
    events = []

    if not phrases:
        events.append(CCEvent(time=0, cc_number=11, value=cfg.expression_max))
        return events

    num_points = int(duration / resolution) + 1

    for i in range(num_points):
        t = i * resolution

        # Find containing phrase
        containing_phrase = None
        for phrase in phrases:
            if phrase.start <= t <= phrase.end:
                containing_phrase = phrase
                break

        if containing_phrase is None:
            value = cfg.expression_min
        else:
            phrase_duration = containing_phrase.end - containing_phrase.start

            # Guard against zero/tiny duration (instant phrase)
            if phrase_duration < 0.001:
                # Instant phrase - use base expression
                range_val = cfg.expression_max - cfg.expression_min
                value = int(cfg.expression_min + range_val * 0.7)
                value = max(cfg.expression_min, min(cfg.expression_max, value))
            else:
                phrase_pos = (t - containing_phrase.start) / phrase_duration
                # Clamp phrase_pos to [0, 1] for safety
                phrase_pos = max(0.0, min(1.0, phrase_pos))

                # Gentle arc - rise in first half, fall in second
                if phrase_pos < 0.5:
                    arc = phrase_pos * 2  # 0 to 1
                else:
                    arc = (1 - phrase_pos) * 2  # 1 to 0

                arc = arc**0.7  # Softer curve

                range_val = cfg.expression_max - cfg.expression_min
                base = cfg.expression_min + range_val * 0.7
                swell_amount = range_val * cfg.phrase_swell * arc

                value = int(base + swell_amount)
                value = max(cfg.expression_min, min(cfg.expression_max, value))

        events.append(CCEvent(time=t, cc_number=11, value=value))

    return _simplify_cc_events(events, threshold=2)


def _simplify_cc_events(events: list[CCEvent], threshold: int = 3) -> list[CCEvent]:
    """Remove redundant CC events where value changes are minimal."""
    if len(events) <= 2:
        return events

    simplified = [events[0]]

    for i in range(1, len(events) - 1):
        prev_val = simplified[-1].value
        curr_val = events[i].value

        if abs(curr_val - prev_val) >= threshold:
            simplified.append(events[i])

    simplified.append(events[-1])
    return simplified


# =============================================================================
# Keyswitch Insertion
# =============================================================================


def insert_keyswitches(
    midi: pretty_midi.PrettyMIDI,
    articulation_events: list[ArticulationEvent],
    instrument_index: int = 0,
    keyswitch_duration: float = 0.05,
    keyswitch_velocity: int = 100,
) -> int:
    """Insert BBC Symphony Orchestra keyswitch notes into MIDI.

    Keyswitches are short MIDI notes that trigger articulation changes
    in the BBC SO VST. They're placed at very low pitches (C0 area)
    just before the notes that should use that articulation.

    Args:
        midi: PrettyMIDI object to modify
        articulation_events: List of articulation events with keyswitches
        instrument_index: Index of instrument to add keyswitches to
        keyswitch_duration: Duration of keyswitch notes in seconds
        keyswitch_velocity: Velocity of keyswitch notes

    Returns:
        Number of keyswitch notes inserted
    """
    import pretty_midi

    if not articulation_events:
        return 0

    if instrument_index >= len(midi.instruments):
        logger.warning(f"Instrument index {instrument_index} out of range")
        return 0

    inst = midi.instruments[instrument_index]
    inserted = 0

    for event in articulation_events:
        if event.keyswitch is None:
            continue

        # Create keyswitch note
        # Place it slightly before the articulation change time
        ks_start = max(0, event.time - keyswitch_duration)
        ks_end = event.time

        # Ensure end > start (pretty_midi requirement)
        if ks_end <= ks_start:
            ks_end = ks_start + keyswitch_duration

        keyswitch_note = pretty_midi.Note(
            velocity=keyswitch_velocity,
            pitch=event.keyswitch,
            start=ks_start,
            end=ks_end,
        )

        inst.notes.append(keyswitch_note)
        inserted += 1

        logger.debug(
            f"   Keyswitch: {event.articulation} -> MIDI {event.keyswitch} at {event.time:.2f}s"
        )

    # Sort notes by start time to maintain order
    inst.notes.sort(key=lambda n: n.start)

    return inserted


def apply_keyswitches_to_file(
    midi_path: Path | str,
    output_path: Path | str | None = None,
    articulation_events: list[ArticulationEvent] | None = None,
) -> Path:
    """Apply keyswitch insertions to a MIDI file.

    If no articulation events provided, detects articulations first.
    If the MIDI already contains keyswitches (notes with pitch <= 31),
    returns the original file unchanged to avoid overwriting.

    Args:
        midi_path: Input MIDI file
        output_path: Output MIDI file (None = modify original filename)
        articulation_events: Pre-detected events (None = detect automatically)

    Returns:
        Path to output file
    """
    import pretty_midi

    midi = pretty_midi.PrettyMIDI(str(midi_path))

    # Check if MIDI already has keyswitches (pitch <= 31)
    has_keyswitches = False
    for inst in midi.instruments:
        for note in inst.notes:
            if note.pitch <= 31:
                has_keyswitches = True
                break
        if has_keyswitches:
            break

    if has_keyswitches:
        logger.info("MIDI already has keyswitches, skipping keyswitch insertion")
        return Path(midi_path)

    # Detect articulations if not provided
    if articulation_events is None:
        all_notes = []
        for inst in midi.instruments:
            all_notes.extend(inst.notes)

        config = ExpressionConfig()
        _, articulation_events = detect_articulations(all_notes, config)

    # Insert keyswitches for each instrument
    total_inserted = 0
    for i in range(len(midi.instruments)):
        count = insert_keyswitches(midi, articulation_events, instrument_index=i)
        total_inserted += count

    # Determine output path
    if output_path is None:
        in_path = Path(midi_path)
        output_path = in_path.parent / f"{in_path.stem}_keyswitched{in_path.suffix}"

    midi.write(str(output_path))
    logger.info(f"✓ Inserted {total_inserted} keyswitches: {output_path}")

    return Path(output_path)


# =============================================================================
# Velocity Humanization
# =============================================================================


def humanize_velocities(
    notes: list,
    config: ExpressionConfig | None = None,
    seed: int = 42,
) -> list[tuple[int, int]]:
    """Apply humanization to note velocities.

    Args:
        notes: List of pretty_midi.Note objects
        config: Expression configuration
        seed: Random seed for reproducibility

    Returns:
        List of (original_velocity, humanized_velocity) tuples
    """
    cfg = config or ExpressionConfig()
    rng = np.random.RandomState(seed)

    results = []

    for i, note in enumerate(notes):
        original = note.velocity

        # Random variance
        variance = int(rng.normal(0, cfg.velocity_humanize * 20))

        # Accent detection and boost
        accent_boost = 0
        if i > 0 and i < len(notes) - 1:
            prev_vel = notes[i - 1].velocity
            next_vel = notes[i + 1].velocity
            if original > (prev_vel + next_vel) / 2 + 10:
                accent_boost = cfg.velocity_accent_boost

        humanized = original + variance + accent_boost
        humanized = max(1, min(127, humanized))

        results.append((original, humanized))

    return results


# =============================================================================
# Timing Humanization (Rubato)
# =============================================================================


def apply_rubato(
    notes: list,
    tempo: float,
    config: ExpressionConfig | None = None,
    seed: int = 42,
) -> list[tuple[float, float, float, float]]:
    """Apply rubato (tempo variation) to note timing.

    Args:
        notes: List of pretty_midi.Note objects
        tempo: Tempo in BPM
        config: Expression configuration
        seed: Random seed

    Returns:
        List of (original_start, original_end, new_start, new_end) tuples
    """
    cfg = config or ExpressionConfig()
    rng = np.random.RandomState(seed)

    if cfg.rubato_amount == 0:
        return [(n.start, n.end, n.start, n.end) for n in notes]

    results = []
    beat_duration = 60.0 / tempo

    for note in notes:
        # Random timing offset
        offset = rng.normal(0, cfg.rubato_amount)

        # Slight anticipation on downbeats
        if cfg.anticipate_downbeats:
            beat_pos = (note.start / beat_duration) % 1.0
            if beat_pos < 0.1:  # Near downbeat
                offset -= cfg.rubato_amount * 0.5

        new_start = max(0, note.start + offset)
        new_end = note.end + offset

        results.append((note.start, note.end, new_start, new_end))

    return results


# =============================================================================
# Expression Engine
# =============================================================================


@dataclass
class ExpressionResult:
    """Result of expression processing."""

    dynamics_curve: list[CCEvent]
    expression_curve: list[CCEvent]
    articulations: list[ArticulationEvent]
    note_analyses: list[NoteAnalysis]
    phrases: list[Phrase]
    velocity_changes: list[tuple[int, int]]
    timing_changes: list[tuple[float, float, float, float]]


class ExpressionEngine:
    """Engine for adding musical expression to MIDI.

    Analyzes MIDI content and generates:
    - CC1 dynamics automation
    - CC11 expression automation
    - Articulation keyswitches
    - Humanized velocities
    - Rubato timing
    """

    def __init__(self, config: ExpressionConfig | None = None):
        self.config = config or ExpressionConfig()
        self._bbc_catalog = None

    def set_style(self, style: ExpressionStyle) -> None:
        """Set expression style from preset."""
        self.config = STYLE_PRESETS.get(style, ExpressionConfig())

    async def process_midi(
        self,
        midi_path: Path | str,
        output_path: Path | str | None = None,
    ) -> ExpressionResult:
        """Process MIDI file and add expression.

        Args:
            midi_path: Input MIDI file path
            output_path: Output MIDI file path (None = modify in place)

        Returns:
            ExpressionResult with all generated data
        """
        import pretty_midi

        midi = pretty_midi.PrettyMIDI(str(midi_path))
        duration = midi.get_end_time()
        tempo = midi.get_tempo_changes()[1][0] if midi.get_tempo_changes()[1].size > 0 else 120

        all_notes = []
        for inst in midi.instruments:
            all_notes.extend(inst.notes)

        # Analyze and generate expression data
        note_analyses, articulations = detect_articulations(all_notes, self.config)
        phrases = detect_phrases(all_notes)

        dynamics_curve = generate_dynamics_curve(phrases, duration, config=self.config)
        expression_curve = generate_expression_curve(phrases, duration, config=self.config)

        velocity_changes = humanize_velocities(all_notes, self.config)
        timing_changes = apply_rubato(all_notes, tempo, self.config)

        # Apply changes to MIDI if output path provided
        if output_path:
            await self._apply_to_midi(
                midi,
                dynamics_curve,
                expression_curve,
                articulations,
                velocity_changes,
                timing_changes,
                output_path,
            )

        return ExpressionResult(
            dynamics_curve=dynamics_curve,
            expression_curve=expression_curve,
            articulations=articulations,
            note_analyses=note_analyses,
            phrases=phrases,
            velocity_changes=velocity_changes,
            timing_changes=timing_changes,
        )

    async def _apply_to_midi(
        self,
        midi: pretty_midi.PrettyMIDI,
        dynamics: list[CCEvent],
        expression: list[CCEvent],
        articulations: list[ArticulationEvent],
        velocity_changes: list[tuple[int, int]],
        timing_changes: list[tuple[float, float, float, float]],
        output_path: Path | str,
        insert_bbc_keyswitches: bool = True,
    ) -> None:
        """Apply expression data to MIDI file.

        Args:
            midi: PrettyMIDI object to modify
            dynamics: CC1 dynamics curve events
            expression: CC11 expression curve events
            articulations: Articulation change events
            velocity_changes: (original, new) velocity pairs
            timing_changes: (orig_start, orig_end, new_start, new_end) tuples
            output_path: Output file path
            insert_bbc_keyswitches: Whether to insert BBC SO keyswitches
        """
        import pretty_midi

        # Add CC events to first instrument
        if midi.instruments:
            inst = midi.instruments[0]

            # Add dynamics (CC1)
            for cc in dynamics:
                inst.control_changes.append(
                    pretty_midi.ControlChange(
                        number=cc.cc_number,
                        value=cc.value,
                        time=cc.time,
                    )
                )

            # Add expression (CC11)
            for cc in expression:
                inst.control_changes.append(
                    pretty_midi.ControlChange(
                        number=cc.cc_number,
                        value=cc.value,
                        time=cc.time,
                    )
                )

        # Apply velocity changes
        all_notes = []
        for inst in midi.instruments:
            all_notes.extend(inst.notes)

        all_notes.sort(key=lambda n: n.start)

        for i, (_orig, new_vel) in enumerate(velocity_changes):
            if i < len(all_notes):
                all_notes[i].velocity = new_vel

        # Apply timing changes
        for i, (_orig_start, _orig_end, new_start, new_end) in enumerate(timing_changes):
            if i < len(all_notes):
                all_notes[i].start = new_start
                all_notes[i].end = new_end

        # Insert BBC SO keyswitches for articulation changes
        # Skip if MIDI already has keyswitches (pitch <= 31)
        has_keyswitches = any(note.pitch <= 31 for inst in midi.instruments for note in inst.notes)

        if insert_bbc_keyswitches and articulations and not has_keyswitches:
            total_ks = 0
            for i in range(len(midi.instruments)):
                count = insert_keyswitches(midi, articulations, instrument_index=i)
                total_ks += count
            if total_ks > 0:
                logger.debug(f"   Inserted {total_ks} BBC SO keyswitches")
        elif has_keyswitches:
            logger.debug("   Skipping keyswitch insertion - MIDI already has keyswitches")

        # Save modified MIDI
        midi.write(str(output_path))
        logger.info(f"✓ Expression applied: {output_path}")


# =============================================================================
# Factory Functions
# =============================================================================

_engine: ExpressionEngine | None = None


def get_expression_engine(config: ExpressionConfig | None = None) -> ExpressionEngine:
    """Get or create expression engine singleton."""
    global _engine
    if _engine is None or config is not None:
        _engine = ExpressionEngine(config)
    return _engine


async def add_expression(
    midi_path: Path | str,
    output_path: Path | str | None = None,
    style: ExpressionStyle = ExpressionStyle.ROMANTIC,
) -> ExpressionResult:
    """Add expression to MIDI file.

    Args:
        midi_path: Input MIDI file
        output_path: Output path (None = return data only)
        style: Expression style preset

    Returns:
        ExpressionResult with generated data
    """
    engine = get_expression_engine()
    engine.set_style(style)
    return await engine.process_midi(midi_path, output_path)


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "ARTICULATION_ALIASES",
    # Keyswitch constants
    "BBC_KEYSWITCHES",
    "STYLE_PRESETS",
    # Data classes
    "ArticulationEvent",
    "CCEvent",
    # Config
    "ExpressionConfig",
    # Engine
    "ExpressionEngine",
    "ExpressionResult",
    # Enums
    "ExpressionStyle",
    "NoteAnalysis",
    "Phrase",
    "add_expression",
    "apply_keyswitches_to_file",
    "apply_rubato",
    # Functions
    "detect_articulations",
    "detect_phrases",
    "generate_dynamics_curve",
    "generate_expression_curve",
    "get_expression_engine",
    # Keyswitch functions
    "get_keyswitch_for_articulation",
    "humanize_velocities",
    "insert_keyswitches",
]
