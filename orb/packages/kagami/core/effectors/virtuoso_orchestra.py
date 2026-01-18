"""Virtuoso Orchestra Engine — True Orchestral Mastery.

This module unifies all instrument positioning, dynamics, and expression into
a single source of truth for virtuoso-level orchestral rendering.

Key Improvements over Previous Implementation:
1. UNIFIED POSITIONS: All 45 BBC instruments mapped to Carnegie Hall positions
2. PROPER ELEVATION: Height tiers based on actual orchestral risers
3. EMOTION-DRIVEN DYNAMICS: CC1/CC11 curves that breathe, not just compute
4. INSTRUMENT FAMILIES: Blend rules for proper section cohesion
5. VIRTUOSO ARTICULATION: Context-aware articulation selection

Reference:
- Carnegie Hall main stage: 58 feet wide × 24 feet deep
- Vienna Musikverein: 60 feet wide × 26 feet deep
- Standard elevation: 0=stage floor, 5°=first riser, 10°=second, 15°=third

Colony: Full Fano Collaboration (all 7)
Created: January 4, 2026 — True Virtuoso Level
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


# =============================================================================
# Position Types — Enhanced for Virtuoso Rendering
# =============================================================================


@dataclass(frozen=True)
class VirtuosoPosition:
    """3D orchestral position with full spatial context.

    Coordinates follow conductor's perspective:
    - azimuth: -90 (far left) to +90 (far right), 0 = center
    - elevation: 0 (stage floor) to 25° (highest riser)
    - distance: 3-12 meters from conductor

    Additional parameters:
    - width: Stereo spread for ensemble sections (0 = point, 1 = full spread)
    - depth_blend: Room reverb mix (0 = dry close, 1 = wet ambient)
    """

    azimuth: float = 0.0  # Degrees: negative=left, positive=right
    elevation: float = 0.0  # Degrees: stage floor to riser height
    distance: float = 6.0  # Meters from conductor
    width: float = 0.0  # Stereo spread for sections (0-1)
    depth_blend: float = 0.3  # Room reverb amount (0-1)

    def to_vbap_tuple(self) -> tuple[float, float, float]:
        """Convert to VBAP-compatible (az, el, dist) tuple."""
        return (self.azimuth, self.elevation, self.distance)


class OrchestraRow(Enum):
    """Physical row in orchestra seating."""

    FRONT = 1  # Stage floor level
    SECOND = 2  # First riser (woodwinds)
    THIRD = 3  # Second riser (brass)
    BACK = 4  # Highest riser (percussion)


class InstrumentFamily(Enum):
    """Instrument families for blend rules."""

    STRINGS = "strings"
    WOODWINDS = "woodwinds"
    BRASS = "brass"
    PERCUSSION_TUNED = "percussion_tuned"
    PERCUSSION_UNTUNED = "percussion_untuned"


# =============================================================================
# VIRTUOSO ORCHESTRA POSITIONS — Complete 45-Instrument Mapping
# =============================================================================
#
# Based on:
# - Carnegie Hall standard orchestral seating
# - Vienna Philharmonic arrangement
# - BBC Proms configuration
#
# American seating: Violins I left, Violins II inside-left, Violas center-right,
# Celli right, Basses far right (German seating swaps violins II to right)

VIRTUOSO_POSITIONS: dict[str, VirtuosoPosition] = {
    # =========================================================================
    # STRINGS — Front row, stage floor (elevation 0-2°)
    # =========================================================================
    # First Violins: Far left front, 14-16 players spread
    "violins_1": VirtuosoPosition(
        azimuth=-45, elevation=1, distance=4.5, width=0.25, depth_blend=0.2
    ),
    "violin_1_leader": VirtuosoPosition(
        azimuth=-42, elevation=1, distance=4.0, width=0.0, depth_blend=0.15
    ),
    # Second Violins: Inside left, 12-14 players
    "violins_2": VirtuosoPosition(
        azimuth=-20, elevation=1, distance=5.0, width=0.2, depth_blend=0.22
    ),
    "violin_2_leader": VirtuosoPosition(
        azimuth=-18, elevation=1, distance=4.5, width=0.0, depth_blend=0.18
    ),
    # Violas: Center-right, 10-12 players
    "violas": VirtuosoPosition(azimuth=15, elevation=1, distance=5.0, width=0.2, depth_blend=0.22),
    "viola_leader": VirtuosoPosition(
        azimuth=12, elevation=1, distance=4.5, width=0.0, depth_blend=0.18
    ),
    # Celli: Right front, 8-10 players
    "celli": VirtuosoPosition(azimuth=40, elevation=1, distance=5.5, width=0.18, depth_blend=0.25),
    "celli_leader": VirtuosoPosition(
        azimuth=38, elevation=1, distance=5.0, width=0.0, depth_blend=0.2
    ),
    # Basses: Far right, elevated slightly, 6-8 players
    "basses": VirtuosoPosition(azimuth=55, elevation=3, distance=6.0, width=0.15, depth_blend=0.28),
    "bass_leader": VirtuosoPosition(
        azimuth=52, elevation=3, distance=5.5, width=0.0, depth_blend=0.22
    ),
    # =========================================================================
    # WOODWINDS — Second row, first riser (elevation 8-12°)
    # =========================================================================
    # Flutes: Left of center, typically 2-3 players
    "flute": VirtuosoPosition(azimuth=-22, elevation=10, distance=7.0, width=0.0, depth_blend=0.35),
    "flutes_a3": VirtuosoPosition(
        azimuth=-22, elevation=10, distance=7.0, width=0.1, depth_blend=0.35
    ),
    "piccolo": VirtuosoPosition(
        azimuth=-28, elevation=12, distance=7.5, width=0.0, depth_blend=0.38
    ),
    "bass_flute": VirtuosoPosition(
        azimuth=-18, elevation=9, distance=7.5, width=0.0, depth_blend=0.36
    ),
    # Oboes: Center-left
    "oboe": VirtuosoPosition(azimuth=-8, elevation=10, distance=7.0, width=0.0, depth_blend=0.35),
    "oboes_a3": VirtuosoPosition(
        azimuth=-8, elevation=10, distance=7.0, width=0.08, depth_blend=0.35
    ),
    "cor_anglais": VirtuosoPosition(
        azimuth=-5, elevation=11, distance=7.5, width=0.0, depth_blend=0.37
    ),
    # Clarinets: Center
    "clarinet": VirtuosoPosition(
        azimuth=8, elevation=10, distance=7.0, width=0.0, depth_blend=0.35
    ),
    "clarinets_a3": VirtuosoPosition(
        azimuth=8, elevation=10, distance=7.0, width=0.08, depth_blend=0.35
    ),
    "bass_clarinet": VirtuosoPosition(
        azimuth=12, elevation=9, distance=7.5, width=0.0, depth_blend=0.36
    ),
    "contrabass_clarinet": VirtuosoPosition(
        azimuth=15, elevation=8, distance=8.0, width=0.0, depth_blend=0.38
    ),
    # Bassoons: Center-right
    "bassoon": VirtuosoPosition(azimuth=22, elevation=9, distance=7.5, width=0.0, depth_blend=0.36),
    "bassoons_a3": VirtuosoPosition(
        azimuth=22, elevation=9, distance=7.5, width=0.08, depth_blend=0.36
    ),
    "contrabassoon": VirtuosoPosition(
        azimuth=25, elevation=8, distance=8.0, width=0.0, depth_blend=0.38
    ),
    # =========================================================================
    # BRASS — Third row, second riser (elevation 15-20°)
    # =========================================================================
    # Horns: Far left of brass, 4-8 players (bells face away)
    "horn": VirtuosoPosition(azimuth=-35, elevation=16, distance=9.0, width=0.0, depth_blend=0.45),
    "horns_a4": VirtuosoPosition(
        azimuth=-35, elevation=16, distance=9.0, width=0.15, depth_blend=0.45
    ),
    # Trumpets: Center-left
    "trumpet": VirtuosoPosition(
        azimuth=-5, elevation=18, distance=9.5, width=0.0, depth_blend=0.42
    ),
    "trumpets_a2": VirtuosoPosition(
        azimuth=-5, elevation=18, distance=9.5, width=0.08, depth_blend=0.42
    ),
    # Trombones: Center to right
    "tenor_trombone": VirtuosoPosition(
        azimuth=15, elevation=17, distance=9.5, width=0.0, depth_blend=0.43
    ),
    "tenor_trombones_a3": VirtuosoPosition(
        azimuth=15, elevation=17, distance=9.5, width=0.12, depth_blend=0.43
    ),
    "bass_trombones_a2": VirtuosoPosition(
        azimuth=22, elevation=16, distance=10.0, width=0.08, depth_blend=0.45
    ),
    "contrabass_trombone": VirtuosoPosition(
        azimuth=28, elevation=15, distance=10.5, width=0.0, depth_blend=0.48
    ),
    # Tubas: Right side
    "tuba": VirtuosoPosition(azimuth=35, elevation=15, distance=10.0, width=0.0, depth_blend=0.46),
    "cimbasso": VirtuosoPosition(
        azimuth=38, elevation=14, distance=10.5, width=0.0, depth_blend=0.48
    ),
    "contrabass_tuba": VirtuosoPosition(
        azimuth=42, elevation=13, distance=11.0, width=0.0, depth_blend=0.5
    ),
    # =========================================================================
    # PERCUSSION — Back row, highest riser (elevation 18-25°)
    # =========================================================================
    # Timpani: Left side of percussion
    "timpani": VirtuosoPosition(
        azimuth=-50, elevation=18, distance=11.0, width=0.12, depth_blend=0.55
    ),
    # Pitched Percussion: Center-back area
    "celeste": VirtuosoPosition(azimuth=-55, elevation=8, distance=6.5, width=0.0, depth_blend=0.3),
    "glockenspiel": VirtuosoPosition(
        azimuth=0, elevation=22, distance=11.5, width=0.0, depth_blend=0.6
    ),
    "xylophone": VirtuosoPosition(
        azimuth=8, elevation=22, distance=11.5, width=0.0, depth_blend=0.6
    ),
    "marimba": VirtuosoPosition(
        azimuth=-8, elevation=22, distance=11.5, width=0.1, depth_blend=0.6
    ),
    "vibraphone": VirtuosoPosition(
        azimuth=15, elevation=22, distance=11.5, width=0.0, depth_blend=0.6
    ),
    "crotales": VirtuosoPosition(
        azimuth=22, elevation=24, distance=12.0, width=0.0, depth_blend=0.65
    ),
    "tubular_bells": VirtuosoPosition(
        azimuth=-15, elevation=23, distance=12.0, width=0.0, depth_blend=0.62
    ),
    # Untuned Percussion: Spread across back
    "untuned_percussion": VirtuosoPosition(
        azimuth=0, elevation=22, distance=11.5, width=0.3, depth_blend=0.6
    ),
    # Harp: Far left, front of woodwinds (special position)
    "harp": VirtuosoPosition(azimuth=-60, elevation=3, distance=5.5, width=0.0, depth_blend=0.25),
}


# =============================================================================
# Instrument Family Classification
# =============================================================================

INSTRUMENT_FAMILIES: dict[str, InstrumentFamily] = {
    # Strings
    "violins_1": InstrumentFamily.STRINGS,
    "violins_2": InstrumentFamily.STRINGS,
    "violin_1_leader": InstrumentFamily.STRINGS,
    "violin_2_leader": InstrumentFamily.STRINGS,
    "violas": InstrumentFamily.STRINGS,
    "viola_leader": InstrumentFamily.STRINGS,
    "celli": InstrumentFamily.STRINGS,
    "celli_leader": InstrumentFamily.STRINGS,
    "basses": InstrumentFamily.STRINGS,
    "bass_leader": InstrumentFamily.STRINGS,
    # Woodwinds
    "flute": InstrumentFamily.WOODWINDS,
    "flutes_a3": InstrumentFamily.WOODWINDS,
    "piccolo": InstrumentFamily.WOODWINDS,
    "bass_flute": InstrumentFamily.WOODWINDS,
    "oboe": InstrumentFamily.WOODWINDS,
    "oboes_a3": InstrumentFamily.WOODWINDS,
    "cor_anglais": InstrumentFamily.WOODWINDS,
    "clarinet": InstrumentFamily.WOODWINDS,
    "clarinets_a3": InstrumentFamily.WOODWINDS,
    "bass_clarinet": InstrumentFamily.WOODWINDS,
    "contrabass_clarinet": InstrumentFamily.WOODWINDS,
    "bassoon": InstrumentFamily.WOODWINDS,
    "bassoons_a3": InstrumentFamily.WOODWINDS,
    "contrabassoon": InstrumentFamily.WOODWINDS,
    # Brass
    "horn": InstrumentFamily.BRASS,
    "horns_a4": InstrumentFamily.BRASS,
    "trumpet": InstrumentFamily.BRASS,
    "trumpets_a2": InstrumentFamily.BRASS,
    "tenor_trombone": InstrumentFamily.BRASS,
    "tenor_trombones_a3": InstrumentFamily.BRASS,
    "bass_trombones_a2": InstrumentFamily.BRASS,
    "contrabass_trombone": InstrumentFamily.BRASS,
    "tuba": InstrumentFamily.BRASS,
    "cimbasso": InstrumentFamily.BRASS,
    "contrabass_tuba": InstrumentFamily.BRASS,
    # Tuned Percussion
    "timpani": InstrumentFamily.PERCUSSION_TUNED,
    "celeste": InstrumentFamily.PERCUSSION_TUNED,
    "glockenspiel": InstrumentFamily.PERCUSSION_TUNED,
    "xylophone": InstrumentFamily.PERCUSSION_TUNED,
    "marimba": InstrumentFamily.PERCUSSION_TUNED,
    "vibraphone": InstrumentFamily.PERCUSSION_TUNED,
    "crotales": InstrumentFamily.PERCUSSION_TUNED,
    "tubular_bells": InstrumentFamily.PERCUSSION_TUNED,
    "harp": InstrumentFamily.PERCUSSION_TUNED,
    # Untuned Percussion
    "untuned_percussion": InstrumentFamily.PERCUSSION_UNTUNED,
}


# =============================================================================
# Emotion-Driven Expression — True Virtuoso Dynamics
# =============================================================================


class EmotionProfile(Enum):
    """Emotional character for expression shaping."""

    TENDER = "tender"  # Soft, gentle, intimate — pp to mp
    PASSIONATE = "passionate"  # Full, expressive — mf to ff
    TRIUMPHANT = "triumphant"  # Bold, victorious — f to fff
    MELANCHOLIC = "melancholic"  # Sad, yearning — pp to mf, lots of decay
    AGITATED = "agitated"  # Anxious, urgent — rapid dynamics
    SERENE = "serene"  # Calm, peaceful — p to mf, stable
    HEROIC = "heroic"  # Noble, grand — mf to fff with brass prominence
    MYSTERIOUS = "mysterious"  # Ethereal, uncertain — ppp to mp


@dataclass
class EmotionConfig:
    """Configuration for emotion-driven expression.

    Dynamics:
    - base_dynamics: CC1 starting value (20-127)
    - dynamics_range: How much CC1 can vary
    - dynamics_curve: Shape of crescendo/decrescendo (0=linear, 1=exponential)

    Expression (CC11):
    - base_expression: CC11 starting value
    - expression_swell: How much CC11 swells at phrase peaks
    - breath_rate: Natural breathing cycle for wind instruments (Hz)

    Timing:
    - rubato_amount: Timing flexibility (0-0.05 seconds)
    - attack_variance: Note attack variation
    - anticipate_peaks: Push slightly ahead at climaxes
    """

    base_dynamics: int = 70
    dynamics_range: int = 50
    dynamics_curve: float = 0.7
    base_expression: int = 90
    expression_swell: float = 0.15
    breath_rate: float = 0.25  # ~4 second breath cycle
    rubato_amount: float = 0.015
    attack_variance: float = 0.005
    anticipate_peaks: bool = True


# Emotion presets
EMOTION_PRESETS: dict[EmotionProfile, EmotionConfig] = {
    EmotionProfile.TENDER: EmotionConfig(
        base_dynamics=45,
        dynamics_range=30,
        dynamics_curve=0.5,
        base_expression=95,
        expression_swell=0.2,
        breath_rate=0.2,
        rubato_amount=0.025,
        attack_variance=0.008,
    ),
    EmotionProfile.PASSIONATE: EmotionConfig(
        base_dynamics=80,
        dynamics_range=45,
        dynamics_curve=0.8,
        base_expression=100,
        expression_swell=0.25,
        breath_rate=0.3,
        rubato_amount=0.02,
        attack_variance=0.006,
    ),
    EmotionProfile.TRIUMPHANT: EmotionConfig(
        base_dynamics=100,
        dynamics_range=27,
        dynamics_curve=0.9,
        base_expression=110,
        expression_swell=0.3,
        breath_rate=0.35,
        rubato_amount=0.01,
        attack_variance=0.003,
        anticipate_peaks=True,
    ),
    EmotionProfile.MELANCHOLIC: EmotionConfig(
        base_dynamics=55,
        dynamics_range=40,
        dynamics_curve=0.4,
        base_expression=85,
        expression_swell=0.18,
        breath_rate=0.18,
        rubato_amount=0.03,
        attack_variance=0.01,
    ),
    EmotionProfile.AGITATED: EmotionConfig(
        base_dynamics=75,
        dynamics_range=50,
        dynamics_curve=0.6,
        base_expression=95,
        expression_swell=0.12,
        breath_rate=0.5,
        rubato_amount=0.008,
        attack_variance=0.004,
    ),
    EmotionProfile.SERENE: EmotionConfig(
        base_dynamics=60,
        dynamics_range=25,
        dynamics_curve=0.3,
        base_expression=100,
        expression_swell=0.1,
        breath_rate=0.15,
        rubato_amount=0.012,
        attack_variance=0.005,
    ),
    EmotionProfile.HEROIC: EmotionConfig(
        base_dynamics=90,
        dynamics_range=35,
        dynamics_curve=0.85,
        base_expression=105,
        expression_swell=0.22,
        breath_rate=0.32,
        rubato_amount=0.01,
        attack_variance=0.003,
    ),
    EmotionProfile.MYSTERIOUS: EmotionConfig(
        base_dynamics=35,
        dynamics_range=45,
        dynamics_curve=0.4,
        base_expression=80,
        expression_swell=0.2,
        breath_rate=0.12,
        rubato_amount=0.035,
        attack_variance=0.012,
    ),
}


# =============================================================================
# Virtuoso Articulation Selection
# =============================================================================


@dataclass
class ArticulationContext:
    """Context for intelligent articulation selection.

    A virtuoso player considers:
    - Tempo and note duration
    - Phrase position (beginning, middle, end)
    - Harmonic function (tonic, dominant, etc.)
    - Musical character (lyrical, rhythmic, dramatic)
    - Previous and following notes
    """

    tempo_bpm: float = 120.0
    note_duration_beats: float = 1.0
    phrase_position: float = 0.5  # 0=start, 0.5=middle, 1=end
    is_phrase_start: bool = False
    is_phrase_end: bool = False
    is_downbeat: bool = False
    previous_pitch: int | None = None
    next_pitch: int | None = None
    velocity: int = 80
    emotion: EmotionProfile = EmotionProfile.PASSIONATE


def select_virtuoso_articulation(
    instrument_key: str,
    context: ArticulationContext,
    available_articulations: list[str],
) -> str:
    """Select the most appropriate articulation like a virtuoso player.

    This goes beyond simple duration-based selection to consider:
    - Musical context and emotion
    - Phrase structure
    - Instrument idiom
    - Technical feasibility

    Args:
        instrument_key: BBC instrument key
        context: Musical context
        available_articulations: Available articulations for this instrument

    Returns:
        Selected articulation name
    """
    # Convert beat duration to seconds
    beat_duration_sec = 60.0 / context.tempo_bpm
    note_duration_sec = context.note_duration_beats * beat_duration_sec

    # Get instrument family
    family = INSTRUMENT_FAMILIES.get(instrument_key, InstrumentFamily.STRINGS)

    # Priority ranking based on context
    priorities: list[str] = []

    # === VERY SHORT NOTES (<0.15s) ===
    if note_duration_sec < 0.15:
        if context.is_downbeat and context.velocity > 90:
            priorities.extend(["Short Marcato", "Short Staccatissimo"])
        else:
            priorities.extend(["Short Staccatissimo", "Short Spiccato", "Short Staccato"])

    # === SHORT NOTES (0.15-0.4s) ===
    elif note_duration_sec < 0.4:
        if family == InstrumentFamily.STRINGS:
            if context.velocity > 100:
                priorities.extend(["Short Marcato", "Short Spiccato"])
            else:
                priorities.extend(["Short Spiccato", "Short Staccato"])
        elif family == InstrumentFamily.BRASS:
            priorities.extend(["Short Marcato", "Short Staccatissimo"])
        else:
            priorities.extend(["Short Marcato", "Short Staccatissimo", "Short Tenuto"])

    # === MEDIUM NOTES (0.4-1.0s) ===
    elif note_duration_sec < 1.0:
        if context.phrase_position < 0.2 or context.phrase_position > 0.8:
            # Phrase boundaries: more articulate
            priorities.extend(["Short Tenuto", "Legato", "Long"])
        else:
            # Mid-phrase: connected
            priorities.extend(["Legato", "Long", "Short Tenuto"])

    # === LONG NOTES (>1.0s) ===
    else:
        # Check for special articulations based on emotion
        if context.emotion == EmotionProfile.MYSTERIOUS:
            if family == InstrumentFamily.STRINGS:
                priorities.extend(["Long Sul Tasto", "Long Flautando", "Legato"])
            else:
                priorities.extend(["Legato", "Long", "Long Flutter"])
        elif context.emotion == EmotionProfile.TRIUMPHANT:
            if family == InstrumentFamily.BRASS:
                priorities.extend(["Long Cuivre", "Long Sfz", "Legato"])
            else:
                priorities.extend(["Legato", "Long", "Long Marcato Attack"])
        elif context.emotion == EmotionProfile.AGITATED:
            if family == InstrumentFamily.STRINGS:
                priorities.extend(["Tremolo", "Tremolo Sul Pont", "Legato"])
            else:
                priorities.extend(["Long Flutter", "Legato", "Long"])
        else:
            priorities.extend(["Legato", "Legato (Extended)", "Long"])

    # === SPECIAL CASES ===

    # Legato between notes less than minor 3rd apart
    if (
        context.previous_pitch is not None
        and context.next_pitch is not None
        and abs(context.previous_pitch - context.next_pitch) <= 3
    ):
        if "Legato" not in priorities[:2]:
            priorities.insert(0, "Legato")
            priorities.insert(1, "Legato (Extended)")

    # Pizzicato for very specific string contexts (leave to user)
    # Tremolo for agitated passages
    if context.emotion == EmotionProfile.AGITATED and note_duration_sec > 0.5:
        if family == InstrumentFamily.STRINGS:
            priorities.insert(0, "Tremolo")

    # Find first available articulation from priorities
    for art in priorities:
        if art in available_articulations:
            return art

    # Fallback: return first available
    return available_articulations[0] if available_articulations else "Long"


# =============================================================================
# Unified Position Lookup
# =============================================================================


def get_virtuoso_position(instrument_key: str) -> VirtuosoPosition:
    """Get the virtuoso-level position for any BBC instrument.

    Falls back to intelligent defaults based on instrument name matching.

    Args:
        instrument_key: BBC instrument key (e.g., "violins_1", "horn")

    Returns:
        VirtuosoPosition for this instrument
    """
    # Direct lookup
    if instrument_key in VIRTUOSO_POSITIONS:
        return VIRTUOSO_POSITIONS[instrument_key]

    # Try to match by partial name
    key_lower = instrument_key.lower()

    # String matching
    if "violin" in key_lower or "vln" in key_lower:
        if "2" in key_lower or "ii" in key_lower:
            return VIRTUOSO_POSITIONS["violins_2"]
        return VIRTUOSO_POSITIONS["violins_1"]

    if "viola" in key_lower or "vla" in key_lower:
        return VIRTUOSO_POSITIONS["violas"]

    if "cello" in key_lower or "celli" in key_lower or "vcl" in key_lower:
        return VIRTUOSO_POSITIONS["celli"]

    if "bass" in key_lower or "contrabass" in key_lower or "cb" in key_lower:
        if "clarinet" in key_lower:
            return VIRTUOSO_POSITIONS["bass_clarinet"]
        if "trombone" in key_lower:
            return VIRTUOSO_POSITIONS["bass_trombones_a2"]
        if "tuba" in key_lower:
            return VIRTUOSO_POSITIONS["contrabass_tuba"]
        return VIRTUOSO_POSITIONS["basses"]

    # Woodwind matching
    if "flute" in key_lower or "fl" in key_lower:
        if "piccolo" in key_lower:
            return VIRTUOSO_POSITIONS["piccolo"]
        return VIRTUOSO_POSITIONS["flute"]

    if "oboe" in key_lower or "ob" in key_lower:
        return VIRTUOSO_POSITIONS["oboe"]

    if "cor anglais" in key_lower or "english horn" in key_lower:
        return VIRTUOSO_POSITIONS["cor_anglais"]

    if "clarinet" in key_lower or "cl" in key_lower:
        return VIRTUOSO_POSITIONS["clarinet"]

    if "bassoon" in key_lower or "bsn" in key_lower:
        return VIRTUOSO_POSITIONS["bassoon"]

    # Brass matching
    if "horn" in key_lower or "hn" in key_lower:
        return VIRTUOSO_POSITIONS["horn"]

    if "trumpet" in key_lower or "tpt" in key_lower or "trp" in key_lower:
        return VIRTUOSO_POSITIONS["trumpet"]

    if "trombone" in key_lower or "tbn" in key_lower:
        if "bass" in key_lower:
            return VIRTUOSO_POSITIONS["bass_trombones_a2"]
        return VIRTUOSO_POSITIONS["tenor_trombone"]

    if "tuba" in key_lower:
        return VIRTUOSO_POSITIONS["tuba"]

    if "cimbasso" in key_lower:
        return VIRTUOSO_POSITIONS["cimbasso"]

    # Percussion matching
    if "timpani" in key_lower or "timp" in key_lower:
        return VIRTUOSO_POSITIONS["timpani"]

    if "harp" in key_lower:
        return VIRTUOSO_POSITIONS["harp"]

    if "celeste" in key_lower or "celesta" in key_lower:
        return VIRTUOSO_POSITIONS["celeste"]

    if "glock" in key_lower:
        return VIRTUOSO_POSITIONS["glockenspiel"]

    if "xylophone" in key_lower or "xylo" in key_lower:
        return VIRTUOSO_POSITIONS["xylophone"]

    if "marimba" in key_lower:
        return VIRTUOSO_POSITIONS["marimba"]

    if "vibraphone" in key_lower or "vibes" in key_lower:
        return VIRTUOSO_POSITIONS["vibraphone"]

    # Default: center of orchestra
    return VirtuosoPosition(azimuth=0, elevation=10, distance=7, width=0, depth_blend=0.4)


# =============================================================================
# Expression Curve Generation — Breathing, Not Mechanical
# =============================================================================


def generate_emotion_dynamics(
    duration_sec: float,
    phrase_peaks: list[float],  # Times of emotional peaks (0-1 normalized)
    emotion: EmotionProfile = EmotionProfile.PASSIONATE,
    resolution: float = 0.05,  # CC event resolution in seconds
) -> list[tuple[float, int]]:
    """Generate CC1 dynamics curve driven by emotion and phrase structure.

    Unlike mechanical curves, this creates:
    - Natural crescendo/decrescendo arcs to phrase peaks
    - Micro-variations that simulate human breath/bow control
    - Emotion-appropriate dynamic range
    - Subtle anticipation of peaks (like a real musician leaning in)

    Args:
        duration_sec: Total duration in seconds
        phrase_peaks: List of peak positions (0.0-1.0 normalized time)
        emotion: Emotional character
        resolution: CC event time resolution

    Returns:
        List of (time, cc1_value) tuples
    """
    config = EMOTION_PRESETS.get(emotion, EMOTION_PRESETS[EmotionProfile.PASSIONATE])

    events: list[tuple[float, int]] = []
    num_points = int(duration_sec / resolution) + 1

    # Sort peaks
    peaks = sorted(phrase_peaks) if phrase_peaks else [0.5]

    for i in range(num_points):
        t = i * resolution
        t_norm = t / duration_sec if duration_sec > 0 else 0

        # Find nearest peak and distance
        min_peak_dist = 1.0
        nearest_peak = 0.5
        for peak in peaks:
            dist = abs(t_norm - peak)
            if dist < min_peak_dist:
                min_peak_dist = dist
                nearest_peak = peak

        # Anticipation: push peak slightly earlier for buildup
        if config.anticipate_peaks and t_norm < nearest_peak:
            anticipated_dist = max(0, min_peak_dist - 0.05)
        else:
            anticipated_dist = min_peak_dist

        # Base curve: inverse distance to peak
        peak_factor = 1.0 - min(1.0, anticipated_dist * 2)

        # Apply curve shape
        peak_factor = peak_factor**config.dynamics_curve

        # Add micro-breath variation (subtle, humanizing)
        breath_phase = math.sin(2 * math.pi * config.breath_rate * t)
        breath_variation = breath_phase * 3  # ±3 CC units

        # Calculate final value
        base = config.base_dynamics
        swell = peak_factor * config.dynamics_range
        value = int(base + swell + breath_variation)
        value = max(20, min(127, value))

        events.append((t, value))

    return _simplify_cc_curve(events, threshold=2)


def generate_emotion_expression(
    duration_sec: float,
    phrase_peaks: list[float],
    emotion: EmotionProfile = EmotionProfile.PASSIONATE,
    resolution: float = 0.05,
) -> list[tuple[float, int]]:
    """Generate CC11 expression curve for phrase shaping.

    Expression (CC11) controls volume without changing timbre (unlike CC1).
    Used for:
    - Phrase breathing (subtle swells)
    - Note-to-note legato shaping
    - Final decays and releases

    Args:
        duration_sec: Total duration
        phrase_peaks: Emotional peak positions
        emotion: Emotional character
        resolution: Event resolution

    Returns:
        List of (time, cc11_value) tuples
    """
    config = EMOTION_PRESETS.get(emotion, EMOTION_PRESETS[EmotionProfile.PASSIONATE])

    events: list[tuple[float, int]] = []
    num_points = int(duration_sec / resolution) + 1

    peaks = sorted(phrase_peaks) if phrase_peaks else [0.5]

    for i in range(num_points):
        t = i * resolution
        t_norm = t / duration_sec if duration_sec > 0 else 0

        # Find position within phrase (between peaks)
        prev_peak = 0.0
        next_peak = 1.0
        for j, peak in enumerate(peaks):
            if t_norm <= peak:
                prev_peak = peaks[j - 1] if j > 0 else 0.0
                next_peak = peak
                break
            prev_peak = peak
            next_peak = peaks[j + 1] if j + 1 < len(peaks) else 1.0

        # Position within current phrase (0-1)
        phrase_span = max(0.001, next_peak - prev_peak)
        phrase_pos = (t_norm - prev_peak) / phrase_span

        # Arc shape: rise to middle, fall at end
        if phrase_pos < 0.5:
            arc = phrase_pos * 2  # Rising
        else:
            arc = (1 - phrase_pos) * 2  # Falling

        # Soften the arc
        arc = arc**0.7

        # Calculate value
        base = config.base_expression
        swell = arc * config.expression_swell * 25  # Scale to CC range

        # Add very subtle breath (even smaller than dynamics)
        breath = math.sin(2 * math.pi * config.breath_rate * t * 1.5) * 1.5

        value = int(base + swell + breath)
        value = max(60, min(127, value))

        events.append((t, value))

    return _simplify_cc_curve(events, threshold=1)


def _simplify_cc_curve(
    events: list[tuple[float, int]], threshold: int = 2
) -> list[tuple[float, int]]:
    """Remove redundant CC events where value change is below threshold."""
    if len(events) <= 2:
        return events

    simplified = [events[0]]
    for i in range(1, len(events) - 1):
        if abs(events[i][1] - simplified[-1][1]) >= threshold:
            simplified.append(events[i])

    simplified.append(events[-1])
    return simplified


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "EMOTION_PRESETS",
    "INSTRUMENT_FAMILIES",
    # Position data
    "VIRTUOSO_POSITIONS",
    # Articulation
    "ArticulationContext",
    "EmotionConfig",
    # Emotion system
    "EmotionProfile",
    "InstrumentFamily",
    "OrchestraRow",
    # Position types
    "VirtuosoPosition",
    "generate_emotion_dynamics",
    "generate_emotion_expression",
    # Functions
    "get_virtuoso_position",
    "select_virtuoso_articulation",
]
