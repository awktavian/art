"""Instrument mapping for OMR results.

Maps OMR-detected staves to BBC Symphony Orchestra instruments using:
1. Standard orchestral score order (Woodwinds → Brass → Percussion → Strings)
2. Pitch range analysis
3. Note density patterns
4. Clef detection (via music21)

The Beethoven 5th Symphony uses this instrumentation:
- Movement 1-3: Flutes (2), Oboes (2), Clarinets (2), Bassoons (2),
                Horns (2), Trumpets (2), Timpani, Strings
- Movement 4 adds: Piccolo, Contrabassoon, Trombones (3)

References:
    - BBC SO Instrument Catalog: packages/kagami/core/effectors/bbc_instruments.py
    - MIDI Remapper: packages/kagami/core/effectors/midi_remapper.py
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .omr_engine import Note, OMRResult

logger = logging.getLogger(__name__)


# =============================================================================
# Instrument Definitions
# =============================================================================


@dataclass
class InstrumentMapping:
    """Mapping from OMR staff to orchestral instrument.

    Attributes:
        name: Full instrument name (e.g., "Flute 1")
        abbreviation: Score abbreviation (e.g., "Fl.1")
        staff_indices: Which OMR staff indices belong to this instrument
        bbc_key: Key in BBC_CATALOG for rendering
        gm_program: General MIDI program number
        transposition: Semitones to transpose (e.g., Bb clarinet = -2)
        section: Orchestra section (woodwinds, brass, percussion, strings)
        confidence: Confidence in this mapping (0-1)
        reasoning: Why this mapping was chosen
    """

    name: str
    abbreviation: str
    staff_indices: list[int]
    bbc_key: str
    gm_program: int
    transposition: int = 0
    section: str = ""
    confidence: float = 0.0
    reasoning: str = ""


# Standard orchestral score order (top to bottom)
# This is the typical layout for a Beethoven symphony score
BEETHOVEN_5_INSTRUMENTATION = [
    # Woodwinds
    {"name": "Flute 1", "abbr": "Fl.1", "bbc": "flute", "gm": 73, "section": "woodwinds"},
    {"name": "Flute 2", "abbr": "Fl.2", "bbc": "flute", "gm": 73, "section": "woodwinds"},
    {"name": "Oboe 1", "abbr": "Ob.1", "bbc": "oboe", "gm": 68, "section": "woodwinds"},
    {"name": "Oboe 2", "abbr": "Ob.2", "bbc": "oboe", "gm": 68, "section": "woodwinds"},
    {
        "name": "Clarinet 1",
        "abbr": "Cl.1",
        "bbc": "clarinet",
        "gm": 71,
        "section": "woodwinds",
        "trans": -2,
    },
    {
        "name": "Clarinet 2",
        "abbr": "Cl.2",
        "bbc": "clarinet",
        "gm": 71,
        "section": "woodwinds",
        "trans": -2,
    },
    {"name": "Bassoon 1", "abbr": "Bsn.1", "bbc": "bassoon", "gm": 70, "section": "woodwinds"},
    {"name": "Bassoon 2", "abbr": "Bsn.2", "bbc": "bassoon", "gm": 70, "section": "woodwinds"},
    # Brass
    {"name": "Horn 1", "abbr": "Hn.1", "bbc": "horn", "gm": 60, "section": "brass"},
    {"name": "Horn 2", "abbr": "Hn.2", "bbc": "horn", "gm": 60, "section": "brass"},
    {"name": "Trumpet 1", "abbr": "Tpt.1", "bbc": "trumpet", "gm": 56, "section": "brass"},
    {"name": "Trumpet 2", "abbr": "Tpt.2", "bbc": "trumpet", "gm": 56, "section": "brass"},
    # Percussion
    {"name": "Timpani", "abbr": "Timp.", "bbc": "timpani", "gm": 47, "section": "percussion"},
    # Strings
    {"name": "Violin I", "abbr": "Vln.I", "bbc": "violins_1", "gm": 40, "section": "strings"},
    {"name": "Violin II", "abbr": "Vln.II", "bbc": "violins_2", "gm": 40, "section": "strings"},
    {"name": "Viola", "abbr": "Vla.", "bbc": "violas", "gm": 41, "section": "strings"},
    {"name": "Cello", "abbr": "Vc.", "bbc": "celli", "gm": 42, "section": "strings"},
    {"name": "Bass", "abbr": "Cb.", "bbc": "basses", "gm": 43, "section": "strings"},
]

# Extended instrumentation for Movement 4
BEETHOVEN_5_MVT4_ADDITIONS = [
    {
        "name": "Piccolo",
        "abbr": "Picc.",
        "bbc": "piccolo",
        "gm": 72,
        "section": "woodwinds",
        "position": 0,
    },
    {
        "name": "Contrabassoon",
        "abbr": "Cbsn.",
        "bbc": "contrabassoon",
        "gm": 70,
        "section": "woodwinds",
        "position": 8,
    },
    {
        "name": "Trombone 1",
        "abbr": "Tbn.1",
        "bbc": "tenor_trombone",
        "gm": 57,
        "section": "brass",
        "position": 12,
    },
    {
        "name": "Trombone 2",
        "abbr": "Tbn.2",
        "bbc": "tenor_trombone",
        "gm": 57,
        "section": "brass",
        "position": 13,
    },
    {
        "name": "Trombone 3",
        "abbr": "Tbn.3",
        "bbc": "bass_trombones_a2",
        "gm": 57,
        "section": "brass",
        "position": 14,
    },
]

# Pitch ranges for instrument identification (MIDI note numbers)
INSTRUMENT_PITCH_RANGES = {
    "piccolo": (74, 108),  # D5 - C8
    "flute": (60, 96),  # C4 - C7
    "oboe": (58, 91),  # A#3 - G6
    "clarinet": (50, 94),  # D3 - A#6 (written)
    "bassoon": (34, 75),  # A#1 - D#5
    "contrabassoon": (22, 58),  # A#0 - A#3
    "horn": (41, 77),  # F2 - F5
    "trumpet": (54, 82),  # F#3 - A#5
    "trombone": (34, 72),  # A#1 - C5
    "timpani": (36, 60),  # C2 - C4
    "violin": (55, 103),  # G3 - G7
    "viola": (48, 91),  # C3 - G6
    "cello": (36, 76),  # C2 - E5
    "bass": (28, 60),  # E1 - C4
}


# =============================================================================
# Staff Analysis
# =============================================================================


@dataclass
class StaffAnalysis:
    """Analysis of notes on a single OMR staff."""

    staff_idx: int
    note_count: int
    low_pitch: int
    high_pitch: int
    pitch_center: float
    density: float  # Notes per beat
    avg_velocity: float
    unique_pitches: int

    @classmethod
    def from_notes(cls, staff_idx: int, notes: list[Note], duration: float = 1.0) -> StaffAnalysis:
        """Create analysis from a list of notes."""
        if not notes:
            return cls(
                staff_idx=staff_idx,
                note_count=0,
                low_pitch=0,
                high_pitch=0,
                pitch_center=0,
                density=0,
                avg_velocity=0,
                unique_pitches=0,
            )

        pitches = [n.pitch for n in notes]
        velocities = [n.velocity for n in notes]

        return cls(
            staff_idx=staff_idx,
            note_count=len(notes),
            low_pitch=min(pitches),
            high_pitch=max(pitches),
            pitch_center=sum(pitches) / len(pitches),
            density=len(notes) / max(duration, 1.0),
            avg_velocity=sum(velocities) / len(velocities),
            unique_pitches=len(set(pitches)),
        )


def analyze_staves(omr_result: OMRResult) -> dict[int, StaffAnalysis]:
    """Analyze each staff in the OMR result.

    Args:
        omr_result: The OMR recognition result.

    Returns:
        Dict mapping staff index to StaffAnalysis.
    """
    # Group notes by staff
    staff_notes: dict[int, list[Note]] = defaultdict(list)
    for note in omr_result.notes:
        staff_notes[note.staff].append(note)

    # Calculate total duration (approximate from last note)
    if omr_result.notes:
        duration = max(n.start_beat + n.duration for n in omr_result.notes)
    else:
        duration = 1.0

    # Analyze each staff
    analyses = {}
    for staff_idx, notes in staff_notes.items():
        analyses[staff_idx] = StaffAnalysis.from_notes(staff_idx, notes, duration)

    return analyses


# =============================================================================
# Instrument Mapper
# =============================================================================


class InstrumentMapper:
    """Maps OMR-detected staves to orchestral instruments.

    Uses multiple strategies:
    1. Standard orchestral score order (positional)
    2. Pitch range analysis
    3. Note density patterns
    """

    def __init__(
        self,
        instrumentation: list[dict] | None = None,
        use_bbc: bool = True,
    ) -> None:
        """Initialize the instrument mapper.

        Args:
            instrumentation: Custom instrumentation list (defaults to Beethoven 5)
            use_bbc: Whether to map to BBC Symphony Orchestra instruments
        """
        self.instrumentation = instrumentation or BEETHOVEN_5_INSTRUMENTATION
        self.use_bbc = use_bbc

    def map_instruments(self, omr_result: OMRResult) -> list[InstrumentMapping]:
        """Map OMR staves to orchestral instruments.

        Args:
            omr_result: The OMR recognition result.

        Returns:
            List of InstrumentMapping objects.
        """
        # Analyze each staff
        staff_analyses = analyze_staves(omr_result)
        sorted_staff_indices = sorted(staff_analyses.keys())

        logger.info(f"Mapping {len(sorted_staff_indices)} staves to instruments")

        mappings: list[InstrumentMapping] = []

        # Strategy 1: Positional mapping (assume standard score order)
        if len(sorted_staff_indices) <= len(self.instrumentation):
            logger.info("Using positional mapping (standard score order)")
            mappings = self._map_positional(sorted_staff_indices, staff_analyses)
        else:
            # More staves than expected - use range analysis
            logger.info("Using pitch range analysis (too many staves for positional)")
            mappings = self._map_by_range(sorted_staff_indices, staff_analyses)

        # Log mappings
        for m in mappings:
            logger.info(
                f"  Staff {m.staff_indices} → {m.name} "
                f"(BBC: {m.bbc_key}, GM: {m.gm_program}, conf: {m.confidence:.0%})"
            )

        return mappings

    def _map_positional(
        self,
        staff_indices: list[int],
        analyses: dict[int, StaffAnalysis],
    ) -> list[InstrumentMapping]:
        """Map staves to instruments based on score position."""
        mappings = []

        for i, staff_idx in enumerate(staff_indices):
            if i < len(self.instrumentation):
                inst = self.instrumentation[i]
                analysis = analyses.get(staff_idx)

                # Check if pitch range matches expected instrument
                confidence = 0.8
                reasoning = "Positional mapping"

                if analysis and analysis.note_count > 0:
                    expected_range = INSTRUMENT_PITCH_RANGES.get(inst["bbc"].split("_")[0].lower())
                    if expected_range:
                        in_range = (
                            expected_range[0] <= analysis.low_pitch
                            and analysis.high_pitch <= expected_range[1]
                        )
                        if in_range:
                            confidence = 0.95
                            reasoning += "; pitch range confirmed"
                        else:
                            confidence = 0.6
                            reasoning += f"; pitch range mismatch ({analysis.low_pitch}-{analysis.high_pitch})"

                mappings.append(
                    InstrumentMapping(
                        name=inst["name"],
                        abbreviation=inst["abbr"],
                        staff_indices=[staff_idx],
                        bbc_key=inst["bbc"],
                        gm_program=inst["gm"],
                        transposition=inst.get("trans", 0),
                        section=inst.get("section", ""),
                        confidence=confidence,
                        reasoning=reasoning,
                    )
                )
            else:
                # Extra staff - assign generically
                mappings.append(
                    InstrumentMapping(
                        name=f"Unknown {staff_idx}",
                        abbreviation=f"Unk.{staff_idx}",
                        staff_indices=[staff_idx],
                        bbc_key="violins_1",  # Default to strings
                        gm_program=48,
                        confidence=0.3,
                        reasoning="Extra staff beyond instrumentation",
                    )
                )

        return mappings

    def _map_by_range(
        self,
        staff_indices: list[int],
        analyses: dict[int, StaffAnalysis],
    ) -> list[InstrumentMapping]:
        """Map staves to instruments based on pitch range analysis."""
        mappings = []

        for staff_idx in staff_indices:
            analysis = analyses.get(staff_idx)

            if not analysis or analysis.note_count == 0:
                mappings.append(
                    InstrumentMapping(
                        name=f"Empty Staff {staff_idx}",
                        abbreviation="Empty",
                        staff_indices=[staff_idx],
                        bbc_key="violins_1",
                        gm_program=48,
                        confidence=0.1,
                        reasoning="Empty staff",
                    )
                )
                continue

            # Find best matching instrument by pitch range
            best_match = None
            best_score = 0

            for inst_name, (low, high) in INSTRUMENT_PITCH_RANGES.items():
                # Calculate overlap with staff range
                overlap_low = max(analysis.low_pitch, low)
                overlap_high = min(analysis.high_pitch, high)

                if overlap_high >= overlap_low:
                    # Some overlap exists
                    overlap = overlap_high - overlap_low
                    inst_range = high - low
                    staff_range = analysis.high_pitch - analysis.low_pitch

                    # Score based on how well the ranges match
                    score = overlap / max(inst_range, staff_range, 1)

                    # Bonus for center pitch being in range
                    if low <= analysis.pitch_center <= high:
                        score += 0.2

                    if score > best_score:
                        best_score = score
                        best_match = inst_name

            # Convert to BBC instrument
            if best_match:
                bbc_mapping = self._get_bbc_for_instrument(best_match)
                mappings.append(
                    InstrumentMapping(
                        name=best_match.title(),
                        abbreviation=best_match[:3].title() + ".",
                        staff_indices=[staff_idx],
                        bbc_key=bbc_mapping["bbc"],
                        gm_program=bbc_mapping["gm"],
                        confidence=min(0.9, best_score),
                        reasoning=f"Pitch range analysis (score={best_score:.2f})",
                    )
                )
            else:
                # No match - use generic
                mappings.append(
                    InstrumentMapping(
                        name=f"Unknown {staff_idx}",
                        abbreviation="Unk.",
                        staff_indices=[staff_idx],
                        bbc_key="violins_1",
                        gm_program=48,
                        confidence=0.2,
                        reasoning="No pitch range match",
                    )
                )

        return mappings

    def _get_bbc_for_instrument(self, instrument: str) -> dict:
        """Get BBC instrument key and GM program for a generic instrument name."""
        mapping = {
            "piccolo": {"bbc": "piccolo", "gm": 72},
            "flute": {"bbc": "flute", "gm": 73},
            "oboe": {"bbc": "oboe", "gm": 68},
            "clarinet": {"bbc": "clarinet", "gm": 71},
            "bassoon": {"bbc": "bassoon", "gm": 70},
            "contrabassoon": {"bbc": "contrabassoon", "gm": 70},
            "horn": {"bbc": "horn", "gm": 60},
            "trumpet": {"bbc": "trumpet", "gm": 56},
            "trombone": {"bbc": "tenor_trombone", "gm": 57},
            "timpani": {"bbc": "timpani", "gm": 47},
            "violin": {"bbc": "violins_1", "gm": 40},
            "viola": {"bbc": "violas", "gm": 41},
            "cello": {"bbc": "celli", "gm": 42},
            "bass": {"bbc": "basses", "gm": 43},
        }
        return mapping.get(instrument, {"bbc": "violins_1", "gm": 48})


# =============================================================================
# Convenience Functions
# =============================================================================


def map_beethoven_5(omr_result: OMRResult, movement: int = 1) -> list[InstrumentMapping]:
    """Map OMR result using Beethoven 5th instrumentation.

    Args:
        omr_result: The OMR recognition result.
        movement: Movement number (1-4). Movement 4 has expanded instrumentation.

    Returns:
        List of InstrumentMapping objects.
    """
    if movement == 4:
        # Build extended instrumentation for Mvt 4
        instrumentation = list(BEETHOVEN_5_INSTRUMENTATION)
        for addition in BEETHOVEN_5_MVT4_ADDITIONS:
            pos = addition.get("position", len(instrumentation))
            instrumentation.insert(
                pos,
                {
                    "name": addition["name"],
                    "abbr": addition["abbr"],
                    "bbc": addition["bbc"],
                    "gm": addition["gm"],
                    "section": addition["section"],
                },
            )
        mapper = InstrumentMapper(instrumentation=instrumentation)
    else:
        mapper = InstrumentMapper()

    return mapper.map_instruments(omr_result)


def get_bbc_catalog_mapping() -> dict[str, str]:
    """Get mapping from generic instrument names to BBC catalog keys.

    Returns:
        Dict mapping instrument names to BBC keys.
    """
    try:
        from kagami.core.effectors.bbc_instruments import BBC_CATALOG

        return {inst.name.lower(): key for key, inst in BBC_CATALOG.items()}
    except ImportError:
        logger.warning("BBC catalog not available, using default mappings")
        return {}


__all__ = [
    "BEETHOVEN_5_INSTRUMENTATION",
    "BEETHOVEN_5_MVT4_ADDITIONS",
    "INSTRUMENT_PITCH_RANGES",
    "InstrumentMapper",
    "InstrumentMapping",
    "StaffAnalysis",
    "analyze_staves",
    "map_beethoven_5",
]
