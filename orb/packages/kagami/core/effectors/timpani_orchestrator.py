"""Timpani Orchestration Module.

Intelligent timpani orchestration with proper musical patterns,
rolls, tuning changes, and dynamics based on BBC Symphony Orchestra
capabilities.

BBC SO Timpani Articulations:
- Long Rolls: Sustained rolls for crescendos/decrescendos
- Long Rolls Soft: Gentle rolls for subtle tension
- Long Rolls Hotrods: Aggressive rolls with hotrods
- Short Hits: Standard single hits
- Short Hits Damped: Hits with dampening
- Short Hits Soft: Gentle hits
- Short Hits Super Damped: Very short, dry hits
- Hotrods Hits Damped: Aggressive damped hits

Timpani Range: E2 (40) to A3 (57) - approximately 17 semitones
Standard tuning: Can play 4 pitches at once (4 drums)

Common Orchestral Patterns:
1. Pedal point: Sustained low note supporting harmony
2. Rolls: Building tension with crescendo
3. Accents: Marking downbeats and phrase endings
4. Dialogue: Call-response with other percussion
5. Thunder rolls: Dramatic long rolls with dynamics

Colony: Forge (e₂)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

import pretty_midi

if TYPE_CHECKING:
    from collections.abc import Sequence


# =============================================================================
# Constants
# =============================================================================

# Timpani range in BBC SO
TIMPANI_LOW = 40  # E2
TIMPANI_HIGH = 57  # A3

# Standard orchestral timpani tuning (4 drums)
# Can be retuned but these are common starting points
STANDARD_TUNING = [40, 45, 47, 52]  # E2, A2, B2, E3

# Velocity ranges for BBC SO dynamics
VELOCITY_PP = (1, 32)
VELOCITY_P = (33, 58)
VELOCITY_MP = (59, 80)
VELOCITY_MF = (81, 98)
VELOCITY_F = (99, 120)
VELOCITY_FF = (121, 127)

# CC for dynamics control
CC_DYNAMICS = 1
CC_EXPRESSION = 11


class TimpaniArticulation(Enum):
    """Available timpani articulations in BBC SO."""

    LONG_ROLL = "Long Rolls"
    LONG_ROLL_SOFT = "Long Rolls Soft"
    LONG_ROLL_HOTRODS = "Long Rolls Hotrods"
    SHORT_HIT = "Short Hits"
    SHORT_HIT_DAMPED = "Short Hits Damped"
    SHORT_HIT_SOFT = "Short Hits Soft"
    SHORT_HIT_SUPER_DAMPED = "Short Hits Super Damped"
    HOTRODS_DAMPED = "Hotrods Hits Damped"


class TimpaniPattern(Enum):
    """Common timpani orchestration patterns."""

    PEDAL_POINT = "pedal_point"  # Sustained low note
    OSTINATO = "ostinato"  # Repeating rhythmic pattern
    ACCENT = "accent"  # Single accent hits
    ROLL_CRESCENDO = "roll_crescendo"  # Roll building to climax
    ROLL_DECRESCENDO = "roll_decrescendo"  # Roll fading away
    THUNDER = "thunder"  # Dramatic long roll
    DIALOGUE = "dialogue"  # Call-response pattern
    MARCH = "march"  # Military-style pattern


@dataclass
class TimpaniNote:
    """A single timpani note with full expression."""

    pitch: int  # MIDI pitch (40-57)
    start: float  # Start time in seconds
    duration: float  # Duration in seconds
    velocity: int  # MIDI velocity (1-127)
    articulation: TimpaniArticulation = TimpaniArticulation.SHORT_HIT
    is_roll: bool = False  # If True, render as roll


@dataclass
class TimpaniPhrase:
    """A musical phrase for timpani."""

    notes: list[TimpaniNote] = field(default_factory=list)
    tuning: list[int] = field(default_factory=lambda: STANDARD_TUNING.copy())
    tempo: float = 120.0


@dataclass
class TimpaniConfig:
    """Configuration for timpani orchestration."""

    # Tuning
    root_pitch: int = 40  # Root note (usually tonic)
    fifth_pitch: int = 47  # Fifth (usually dominant)
    extra_pitches: list[int] = field(default_factory=lambda: [45, 52])

    # Dynamics
    base_velocity: int = 90
    accent_velocity: int = 120
    soft_velocity: int = 60

    # Timing
    humanize_timing: float = 0.02  # Max timing variation in seconds
    humanize_velocity: int = 8  # Max velocity variation

    # Roll parameters
    roll_note_density: float = 12.0  # Notes per second in simulated roll
    roll_velocity_variation: int = 15  # Velocity variation in rolls


class TimpaniOrchestrator:
    """Orchestrate timpani parts with musical intelligence.

    This class generates musically appropriate timpani parts based on
    the musical context (tempo, key, section type) and desired patterns.

    Example:
        >>> orchestrator = TimpaniOrchestrator(tempo=212, key_root=52)
        >>> phrase = orchestrator.create_roll_crescendo(
        ...     start=0, duration=4.0, start_vel=40, end_vel=120
        ... )
        >>> midi = orchestrator.to_midi(phrase)
    """

    def __init__(
        self,
        tempo: float = 120.0,
        key_root: int = 40,
        config: TimpaniConfig | None = None,
    ) -> None:
        """Initialize timpani orchestrator.

        Args:
            tempo: Tempo in BPM
            key_root: Root note of the key (MIDI pitch)
            config: Optional configuration overrides
        """
        self.tempo = tempo
        self.key_root = max(TIMPANI_LOW, min(key_root, TIMPANI_HIGH))
        self.config = config or TimpaniConfig()

        # Calculate tuning based on key
        self._calculate_tuning()

    def _calculate_tuning(self) -> None:
        """Calculate optimal timpani tuning for the key."""
        root = self.key_root

        # Find fifth above root (within range)
        fifth = root + 7
        if fifth > TIMPANI_HIGH:
            fifth = root - 5  # Fifth below

        # Find fourth (for dominant pedal)
        fourth = root + 5
        if fourth > TIMPANI_HIGH:
            fourth = root - 7

        # Find octave if possible
        octave = root + 12
        if octave > TIMPANI_HIGH:
            octave = root - 12 if root - 12 >= TIMPANI_LOW else root

        self.tuning = sorted({root, fourth, fifth, octave})[:4]
        self.config.root_pitch = root
        self.config.fifth_pitch = fifth

    def _humanize_timing(self, time: float) -> float:
        """Add subtle timing variation."""
        import random

        variation = random.uniform(-self.config.humanize_timing, self.config.humanize_timing)
        return max(0, time + variation)

    def _humanize_velocity(self, velocity: int) -> int:
        """Add subtle velocity variation."""
        import random

        variation = random.randint(-self.config.humanize_velocity, self.config.humanize_velocity)
        return max(1, min(127, velocity + variation))

    def create_roll(
        self,
        start: float,
        duration: float,
        pitch: int | None = None,
        velocity: int = 90,
        crescendo: bool = False,
        decrescendo: bool = False,
        start_velocity: int | None = None,
        end_velocity: int | None = None,
    ) -> TimpaniPhrase:
        """Create a timpani roll with optional dynamics.

        BBC SO has dedicated roll articulations, but for MIDI control
        we can also simulate rolls with rapid notes + CC automation.

        Args:
            start: Start time in seconds
            duration: Duration in seconds
            pitch: MIDI pitch (default: root)
            velocity: Base velocity (if no crescendo/decrescendo)
            crescendo: Build from soft to loud
            decrescendo: Fade from loud to soft
            start_velocity: Starting velocity for dynamic change
            end_velocity: Ending velocity for dynamic change

        Returns:
            TimpaniPhrase with roll notes and CC data
        """
        pitch = pitch or self.config.root_pitch
        phrase = TimpaniPhrase(tempo=self.tempo)

        # Determine velocities
        if crescendo:
            start_vel = start_velocity or VELOCITY_P[0]
            end_vel = end_velocity or VELOCITY_FF[1]
        elif decrescendo:
            start_vel = start_velocity or VELOCITY_FF[1]
            end_vel = end_velocity or VELOCITY_P[0]
        else:
            start_vel = end_vel = velocity

        # For BBC SO, we use a single long note with dynamics CC
        # The roll articulation handles the actual roll sound
        roll_note = TimpaniNote(
            pitch=pitch,
            start=start,
            duration=duration,
            velocity=start_vel,
            articulation=TimpaniArticulation.LONG_ROLL,
            is_roll=True,
        )
        phrase.notes.append(roll_note)

        # Store dynamics curve for CC generation
        roll_note._start_vel = start_vel  # type: ignore[attr-defined]
        roll_note._end_vel = end_vel  # type: ignore[attr-defined]

        return phrase

    def create_accent_pattern(
        self,
        start: float,
        beats: Sequence[float],
        pitch: int | None = None,
        velocity: int = 110,
        damped: bool = False,
    ) -> TimpaniPhrase:
        """Create accent hits on specific beats.

        Args:
            start: Start time in seconds
            beats: Beat positions relative to start (in beats, not seconds)
            pitch: MIDI pitch (default: root)
            velocity: Hit velocity
            damped: Use damped articulation

        Returns:
            TimpaniPhrase with accent hits
        """
        pitch = pitch or self.config.root_pitch
        phrase = TimpaniPhrase(tempo=self.tempo)

        beat_duration = 60.0 / self.tempo

        articulation = (
            TimpaniArticulation.SHORT_HIT_DAMPED if damped else TimpaniArticulation.SHORT_HIT
        )

        for beat in beats:
            time = start + beat * beat_duration
            note = TimpaniNote(
                pitch=pitch,
                start=self._humanize_timing(time),
                duration=0.3,  # Short hit
                velocity=self._humanize_velocity(velocity),
                articulation=articulation,
            )
            phrase.notes.append(note)

        return phrase

    def create_ostinato(
        self,
        start: float,
        duration: float,
        pattern: Sequence[tuple[float, int]] | None = None,
        pitches: Sequence[int] | None = None,
        velocity: int = 90,
    ) -> TimpaniPhrase:
        """Create a repeating rhythmic pattern.

        Args:
            start: Start time in seconds
            duration: Total duration
            pattern: List of (beat_offset, pitch_index) tuples
            pitches: Pitches to use (default: tuning)
            velocity: Base velocity

        Returns:
            TimpaniPhrase with ostinato pattern
        """
        pitches = pitches or self.tuning
        phrase = TimpaniPhrase(tempo=self.tempo)

        # Default pattern: quarter notes alternating root and fifth
        if pattern is None:
            pattern = [(0, 0), (1, 1), (2, 0), (3, 1)]

        beat_duration = 60.0 / self.tempo
        pattern_duration = max(p[0] for p in pattern) * beat_duration + beat_duration

        current_time = start
        while current_time < start + duration:
            for beat_offset, pitch_idx in pattern:
                time = current_time + beat_offset * beat_duration
                if time >= start + duration:
                    break

                pitch = pitches[pitch_idx % len(pitches)]
                note = TimpaniNote(
                    pitch=pitch,
                    start=self._humanize_timing(time),
                    duration=beat_duration * 0.8,
                    velocity=self._humanize_velocity(velocity),
                    articulation=TimpaniArticulation.SHORT_HIT,
                )
                phrase.notes.append(note)

            current_time += pattern_duration

        return phrase

    def create_thunder_roll(
        self,
        start: float,
        duration: float,
        pitch: int | None = None,
        peak_time: float = 0.7,  # Where the peak occurs (0-1)
    ) -> TimpaniPhrase:
        """Create a dramatic thunder roll with swell.

        The roll builds to a peak and then fades, creating a
        dramatic thunderous effect.

        Args:
            start: Start time
            duration: Total duration
            pitch: MIDI pitch (default: lowest available)
            peak_time: Relative position of peak (0-1)

        Returns:
            TimpaniPhrase with thunder roll
        """
        pitch = pitch or min(self.tuning)
        phrase = TimpaniPhrase(tempo=self.tempo)

        # Create swell effect with two rolls
        peak_position = duration * peak_time

        # Crescendo to peak
        roll1 = TimpaniNote(
            pitch=pitch,
            start=start,
            duration=peak_position,
            velocity=VELOCITY_P[0],
            articulation=TimpaniArticulation.LONG_ROLL,
            is_roll=True,
        )
        roll1._start_vel = VELOCITY_P[0]  # type: ignore[attr-defined]
        roll1._end_vel = VELOCITY_FF[1]  # type: ignore[attr-defined]
        phrase.notes.append(roll1)

        # Decrescendo from peak
        roll2 = TimpaniNote(
            pitch=pitch,
            start=start + peak_position,
            duration=duration - peak_position,
            velocity=VELOCITY_FF[1],
            articulation=TimpaniArticulation.LONG_ROLL,
            is_roll=True,
        )
        roll2._start_vel = VELOCITY_FF[1]  # type: ignore[attr-defined]
        roll2._end_vel = VELOCITY_P[0]  # type: ignore[attr-defined]
        phrase.notes.append(roll2)

        return phrase

    def create_march_pattern(
        self,
        start: float,
        measures: int = 4,
        time_signature: tuple[int, int] = (4, 4),
    ) -> TimpaniPhrase:
        """Create a military-style march pattern.

        Standard march pattern: strong on 1 and 3, with fills.

        Args:
            start: Start time
            measures: Number of measures
            time_signature: Time signature (beats, beat_value)

        Returns:
            TimpaniPhrase with march pattern
        """
        phrase = TimpaniPhrase(tempo=self.tempo)
        beats_per_measure, _ = time_signature
        beat_duration = 60.0 / self.tempo
        measure_duration = beats_per_measure * beat_duration

        root = self.config.root_pitch
        fifth = self.config.fifth_pitch

        for m in range(measures):
            measure_start = start + m * measure_duration

            # Beat 1: Strong root hit
            phrase.notes.append(
                TimpaniNote(
                    pitch=root,
                    start=self._humanize_timing(measure_start),
                    duration=beat_duration * 0.5,
                    velocity=self._humanize_velocity(115),
                    articulation=TimpaniArticulation.SHORT_HIT,
                )
            )

            # Beat 3: Fifth hit (slightly softer)
            phrase.notes.append(
                TimpaniNote(
                    pitch=fifth,
                    start=self._humanize_timing(measure_start + 2 * beat_duration),
                    duration=beat_duration * 0.5,
                    velocity=self._humanize_velocity(100),
                    articulation=TimpaniArticulation.SHORT_HIT,
                )
            )

            # Every 4th measure: fill
            if (m + 1) % 4 == 0:
                # Add fill on beat 4
                for i, offset in enumerate([3.0, 3.25, 3.5, 3.75]):
                    phrase.notes.append(
                        TimpaniNote(
                            pitch=root if i % 2 == 0 else fifth,
                            start=self._humanize_timing(measure_start + offset * beat_duration),
                            duration=beat_duration * 0.2,
                            velocity=self._humanize_velocity(90 + i * 8),
                            articulation=TimpaniArticulation.SHORT_HIT,
                        )
                    )

        return phrase

    def to_midi(
        self,
        phrase: TimpaniPhrase,
        instrument_name: str = "timpani",
    ) -> pretty_midi.PrettyMIDI:
        """Convert timpani phrase to MIDI.

        Args:
            phrase: TimpaniPhrase to convert
            instrument_name: Name for the instrument track

        Returns:
            PrettyMIDI object with timpani track
        """
        midi = pretty_midi.PrettyMIDI(initial_tempo=phrase.tempo)

        # Create timpani instrument (program 47 = orchestral timpani)
        instrument = pretty_midi.Instrument(
            program=47,
            is_drum=False,
            name=instrument_name,
        )

        # Add notes
        for note in phrase.notes:
            midi_note = pretty_midi.Note(
                velocity=note.velocity,
                pitch=note.pitch,
                start=note.start,
                end=note.start + note.duration,
            )
            instrument.notes.append(midi_note)

            # Add dynamics CC for rolls
            if note.is_roll and hasattr(note, "_start_vel"):
                start_vel = note._start_vel  # type: ignore[attr-defined]
                end_vel = note._end_vel  # type: ignore[attr-defined]

                # Generate CC1 curve
                num_points = max(10, int(note.duration * 20))
                for i in range(num_points):
                    t = note.start + (note.duration * i / num_points)
                    progress = i / num_points
                    # Exponential curve for more natural dynamics
                    cc_value = int(start_vel + (end_vel - start_vel) * (progress**1.5))
                    cc_value = max(0, min(127, cc_value))

                    instrument.control_changes.append(
                        pretty_midi.ControlChange(
                            number=CC_DYNAMICS,
                            value=cc_value,
                            time=t,
                        )
                    )

        midi.instruments.append(instrument)
        return midi

    def merge_phrases(self, *phrases: TimpaniPhrase) -> TimpaniPhrase:
        """Merge multiple phrases into one.

        Args:
            *phrases: Phrases to merge

        Returns:
            Combined TimpaniPhrase
        """
        combined = TimpaniPhrase(tempo=self.tempo)
        for phrase in phrases:
            combined.notes.extend(phrase.notes)

        # Sort by start time
        combined.notes.sort(key=lambda n: n.start)
        return combined


def create_mop_timpani(tempo: float = 212.0) -> pretty_midi.PrettyMIDI:
    """Create proper timpani part for Master of Puppets.

    This creates a musically appropriate timpani arrangement that:
    - Uses proper tuning (E key, so E2, A2, B2, E3)
    - Includes rolls for dramatic sections
    - Has varied dynamics and articulations
    - Follows the song structure

    Args:
        tempo: Tempo in BPM (default: 212 for MoP)

    Returns:
        PrettyMIDI with timpani track
    """
    # E minor key - tune timpani to E, A, B, E octave
    orch = TimpaniOrchestrator(tempo=tempo, key_root=40)  # E2

    phrases = []

    # ==========================================================================
    # INTRO (0-35s): Building tension with rolls
    # ==========================================================================
    # Soft roll building
    phrases.append(
        orch.create_roll(
            start=0,
            duration=8,
            pitch=40,  # Low E
            crescendo=True,
            start_velocity=30,
            end_velocity=80,
        )
    )

    # Accent hits on downbeats
    phrases.append(
        orch.create_accent_pattern(
            start=8,
            beats=[0, 4, 8, 12, 14, 15, 16],  # Building intensity
            pitch=40,
            velocity=100,
        )
    )

    # Thunder roll before main riff
    phrases.append(orch.create_thunder_roll(start=25, duration=10, pitch=40))

    # ==========================================================================
    # VERSE 1 (35-75s): Driving rhythm
    # ==========================================================================
    # Steady quarter note pulse
    phrases.append(
        orch.create_ostinato(
            start=35,
            duration=40,
            pattern=[(0, 0), (2, 1)],  # Root on 1, fifth on 3
            velocity=85,
        )
    )

    # ==========================================================================
    # CHORUS 1 (75-115s): Power hits
    # ==========================================================================
    # Strong accents
    for i in range(10):
        measure_start = 75 + i * 4 * (60 / tempo)
        phrases.append(
            orch.create_accent_pattern(
                start=measure_start,
                beats=[0, 0.5] if i % 2 == 0 else [0],
                pitch=40,
                velocity=115,
            )
        )

    # ==========================================================================
    # INTERLUDE (115-175s): Dramatic rolls
    # ==========================================================================
    # Long building roll
    phrases.append(
        orch.create_roll(
            start=115,
            duration=20,
            pitch=40,
            crescendo=True,
            start_velocity=40,
            end_velocity=120,
        )
    )

    # Thunder for transition
    phrases.append(orch.create_thunder_roll(start=145, duration=15, pitch=40))

    # Quiet section with soft rolls
    phrases.append(
        orch.create_roll(
            start=160,
            duration=15,
            pitch=45,  # A2
            velocity=50,
        )
    )

    # ==========================================================================
    # CLEAN SECTION (175-235s): Minimal, tasteful
    # ==========================================================================
    # Sparse accents only
    phrases.append(
        orch.create_accent_pattern(
            start=175,
            beats=[0],
            pitch=40,
            velocity=70,
        )
    )
    phrases.append(
        orch.create_roll(
            start=200,
            duration=8,
            pitch=40,
            velocity=60,
        )
    )

    # Build back
    phrases.append(
        orch.create_roll(
            start=220,
            duration=15,
            pitch=40,
            crescendo=True,
            start_velocity=50,
            end_velocity=110,
        )
    )

    # ==========================================================================
    # SOLO SECTION (235-315s): Supporting the melody
    # ==========================================================================
    # Steady pulse under solo
    phrases.append(
        orch.create_ostinato(
            start=235,
            duration=40,
            pattern=[(0, 0), (1, 0), (2, 1), (3, 1)],
            velocity=75,
        )
    )

    # Dramatic rolls at solo climax
    phrases.append(orch.create_thunder_roll(start=275, duration=10, pitch=40, peak_time=0.6))

    # Build to final section
    phrases.append(
        orch.create_roll(
            start=295,
            duration=20,
            pitch=40,
            crescendo=True,
            start_velocity=60,
            end_velocity=127,
        )
    )

    # ==========================================================================
    # FINAL CHORUS (315-365s): Full power
    # ==========================================================================
    # March-style pattern
    phrases.append(
        orch.create_march_pattern(
            start=315,
            measures=16,
        )
    )

    # Final thunder
    phrases.append(orch.create_thunder_roll(start=345, duration=10, pitch=40))

    # ==========================================================================
    # OUTRO (365-400s): Fading
    # ==========================================================================
    phrases.append(
        orch.create_roll(
            start=365,
            duration=20,
            pitch=40,
            decrescendo=True,
            start_velocity=100,
            end_velocity=30,
        )
    )

    # Final hit
    phrases.append(
        orch.create_accent_pattern(
            start=395,
            beats=[0],
            pitch=40,
            velocity=127,
            damped=True,
        )
    )

    # Merge all phrases
    combined = orch.merge_phrases(*phrases)

    return orch.to_midi(combined)
