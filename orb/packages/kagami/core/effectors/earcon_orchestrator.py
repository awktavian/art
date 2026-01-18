"""Earcon Orchestrator — Virtuoso Sound Design with BBC Symphony Orchestra.

Every sound is a musical phrase performed by a real orchestra.
The home doesn't beep - it BREATHES.

Quality Standards (every earcon must pass):
    1. Fletcher Test: Is the tempo intentional and precise?
    2. Williams Test: Does it have a memorable leitmotif?
    3. Elfman Test: Does it have personality and character?
    4. Spatial Test: Does it move meaningfully in 3D space?
    5. Context Test: Does it fit the emotional moment?
    6. Duration Test: Is it exactly as long as it needs to be?
    7. Mix Test: Does it sit well in the home's acoustic space?

Colony: Spark (creative vision) + Forge (implementation)
Created: January 4, 2026
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

from kagami.core.effectors.vbap_core import Pos3D

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)


# =============================================================================
# Emotional Intent — What the sound should make you FEEL
# =============================================================================


class EmotionalIntent(Enum):
    """The emotional purpose of an earcon.

    Each earcon exists to communicate a specific feeling.
    The orchestration and spatial trajectory serve this intent.
    """

    # Positive
    GENTLE_ATTENTION = "gentle_attention"  # Soft notification
    TRIUMPH = "triumph"  # Victory without arrogance
    WARM_WELCOME = "warm_welcome"  # Homecoming feeling
    PURE_JOY = "pure_joy"  # Celebration
    PEACEFUL_DESCENT = "peaceful_descent"  # Winding down
    GENTLE_RISING = "gentle_rising"  # Morning awakening
    DELIGHTFUL_SURPRISE = "delightful_surprise"  # Package arrival

    # Neutral
    CLEAR_ATTENTION = "clear_attention"  # Focus ping
    CONFIDENT_CONFIRMATION = "confident_confirmation"  # Security armed
    RESPECTFUL_URGENCY = "respectful_urgency"  # Meeting reminder
    SUBTLE_AWARENESS = "subtle_awareness"  # Room presence

    # Cautionary
    CONCERN_NOT_PANIC = "concern_not_panic"  # Error state
    URGENT_IMPORTANCE = "urgent_importance"  # Alert
    FOND_FAREWELL = "fond_farewell"  # Departure

    # Dramatic
    EPIC_ANTICIPATION = "epic_anticipation"  # Cinematic moment

    # Ambient
    MORNING_EMERGENCE = "morning_emergence"  # Time of day
    EVENING_WARMTH = "evening_warmth"  # Settling
    NIGHT_REST = "night_rest"  # Deep rest


class SpatialMotion(Enum):
    """How the sound moves through 3D space.

    Every earcon has a trajectory - sound doesn't just exist,
    it MOVES through the room with intent.
    """

    DESCEND_FROM_ABOVE = "descend"  # Notification from the heavens
    BLOOM_FROM_CENTER = "bloom"  # Expands outward
    RISE_FROM_FLOOR = "rise"  # Emerges upward
    PULSE_FRONT_CENTER = "pulse"  # Urgent front attention
    SWEEP_FROM_DOOR = "sweep_door"  # Arrival from entry
    RECEDE_TO_DOOR = "recede_door"  # Departure toward door
    SURROUND_ROOM = "surround"  # Full room envelopment
    SETTLE_DOWNWARD = "settle"  # Gently descends
    POINT_SOURCE = "point"  # Static, focused
    THREE_CORNERS = "corners"  # Sequential corners
    APPROACH_FROM_DISTANCE = "approach"  # Gradually approaches
    CIRCLE_PERIMETER = "circle"  # Around the room
    DIAGONAL_CROSS = "diagonal"  # Front to back diagonal
    BREATHE = "breathe"  # Subtle in-out pulsing


# =============================================================================
# Orchestration Templates — The SOUND of each intent
# =============================================================================


@dataclass
class InstrumentVoice:
    """A single instrument voice in the orchestration.

    Each voice has specific notes, dynamics, and articulation
    that together create the earcon's character.
    """

    instrument_key: str  # BBC_CATALOG key
    notes: list[tuple[float, int, float, int]]  # (time, pitch, duration, velocity)
    articulation: str = "Long"  # BBC SO articulation
    cc1_dynamics: list[tuple[float, int]] = field(default_factory=list)  # (time, value)
    cc11_expression: list[tuple[float, int]] = field(default_factory=list)
    pan: float = 0.0  # -1 to 1
    reverb_send: float = 0.3  # 0 to 1


@dataclass
class Orchestration:
    """Complete orchestration for an earcon.

    This defines WHAT instruments play WHAT notes WHEN.
    The Expression Engine adds dynamics, and the renderer
    uses BBC Symphony Orchestra to bring it to life.
    """

    voices: list[InstrumentVoice]
    tempo_bpm: float = 120.0
    total_duration: float = 1.5  # seconds
    master_volume: float = 0.8
    room_reverb: float = 0.3  # Overall room presence


# =============================================================================
# Spatial Trajectory Definitions
# =============================================================================


@dataclass
class SpatialTrajectory:
    """3D path through space for an earcon.

    Defines how the sound moves from start to end,
    creating spatial narrative.
    """

    motion: SpatialMotion
    keyframes: list[tuple[float, Pos3D]]  # (time_ratio, position)
    ease_type: str = "ease_out"  # linear, ease_in, ease_out, ease_in_out


def _make_descend_trajectory(duration: float) -> SpatialTrajectory:
    """Sound descends from above, settling to ear level."""
    return SpatialTrajectory(
        motion=SpatialMotion.DESCEND_FROM_ABOVE,
        keyframes=[
            (0.0, Pos3D(az=0, el=60, dist=4)),  # Start above
            (0.3, Pos3D(az=0, el=30, dist=4.5)),  # Descending
            (0.7, Pos3D(az=0, el=10, dist=5)),  # Nearly level
            (1.0, Pos3D(az=0, el=0, dist=5)),  # At ear level
        ],
        ease_type="ease_out",
    )


def _make_bloom_trajectory(duration: float) -> SpatialTrajectory:
    """Sound blooms outward from center, filling the room."""
    return SpatialTrajectory(
        motion=SpatialMotion.BLOOM_FROM_CENTER,
        keyframes=[
            (0.0, Pos3D(az=0, el=0, dist=2)),  # Close center
            (0.2, Pos3D(az=0, el=10, dist=3)),  # Expanding
            (0.5, Pos3D(az=0, el=15, dist=4)),  # Blooming
            (0.8, Pos3D(az=0, el=20, dist=5)),  # Full expansion
            (1.0, Pos3D(az=0, el=10, dist=4.5)),  # Gentle settle
        ],
        ease_type="ease_in_out",
    )


def _make_rise_trajectory(duration: float) -> SpatialTrajectory:
    """Sound rises from below, emerging upward."""
    return SpatialTrajectory(
        motion=SpatialMotion.RISE_FROM_FLOOR,
        keyframes=[
            (0.0, Pos3D(az=0, el=-20, dist=4)),  # From below
            (0.3, Pos3D(az=0, el=0, dist=4)),  # At level
            (0.7, Pos3D(az=0, el=20, dist=4.5)),  # Rising
            (1.0, Pos3D(az=0, el=30, dist=5)),  # Above
        ],
        ease_type="ease_out",
    )


def _make_pulse_trajectory(duration: float) -> SpatialTrajectory:
    """Sound pulses urgently from front center."""
    return SpatialTrajectory(
        motion=SpatialMotion.PULSE_FRONT_CENTER,
        keyframes=[
            (0.0, Pos3D(az=0, el=5, dist=3)),  # Close
            (0.15, Pos3D(az=0, el=5, dist=4)),  # Push
            (0.3, Pos3D(az=0, el=5, dist=3)),  # Pull
            (0.45, Pos3D(az=0, el=5, dist=4)),  # Push
            (0.6, Pos3D(az=0, el=5, dist=3)),  # Pull
            (1.0, Pos3D(az=0, el=5, dist=4.5)),  # Settle
        ],
        ease_type="linear",
    )


def _make_sweep_door_trajectory(duration: float) -> SpatialTrajectory:
    """Sound sweeps from entry door into room."""
    # Entry is typically front-left at ~45 degrees
    return SpatialTrajectory(
        motion=SpatialMotion.SWEEP_FROM_DOOR,
        keyframes=[
            (0.0, Pos3D(az=-60, el=0, dist=7)),  # At door
            (0.3, Pos3D(az=-30, el=5, dist=5)),  # Entering
            (0.6, Pos3D(az=-10, el=5, dist=4)),  # Sweeping in
            (1.0, Pos3D(az=0, el=5, dist=4)),  # Center
        ],
        ease_type="ease_out",
    )


def _make_recede_door_trajectory(duration: float) -> SpatialTrajectory:
    """Sound recedes toward door, fading."""
    return SpatialTrajectory(
        motion=SpatialMotion.RECEDE_TO_DOOR,
        keyframes=[
            (0.0, Pos3D(az=0, el=5, dist=4)),  # Center
            (0.3, Pos3D(az=-15, el=5, dist=5)),  # Moving
            (0.6, Pos3D(az=-40, el=0, dist=6)),  # Receding
            (1.0, Pos3D(az=-60, el=0, dist=8)),  # At door
        ],
        ease_type="ease_in",
    )


def _make_surround_trajectory(duration: float) -> SpatialTrajectory:
    """Sound surrounds entire room, immersive."""
    return SpatialTrajectory(
        motion=SpatialMotion.SURROUND_ROOM,
        keyframes=[
            (0.0, Pos3D(az=0, el=0, dist=3)),  # Center start
            (0.2, Pos3D(az=-90, el=15, dist=5)),  # Expand left
            (0.4, Pos3D(az=0, el=30, dist=5)),  # Above
            (0.6, Pos3D(az=90, el=15, dist=5)),  # Right
            (0.8, Pos3D(az=180, el=0, dist=5)),  # Behind
            (1.0, Pos3D(az=0, el=10, dist=4)),  # Return center
        ],
        ease_type="ease_in_out",
    )


def _make_settle_trajectory(duration: float) -> SpatialTrajectory:
    """Sound gently settles downward, calming."""
    return SpatialTrajectory(
        motion=SpatialMotion.SETTLE_DOWNWARD,
        keyframes=[
            (0.0, Pos3D(az=0, el=20, dist=4)),  # Start elevated
            (0.3, Pos3D(az=-5, el=15, dist=4.5)),  # Drifting
            (0.6, Pos3D(az=5, el=8, dist=4.5)),  # Settling
            (1.0, Pos3D(az=0, el=0, dist=5)),  # Resting
        ],
        ease_type="ease_out",
    )


def _make_point_trajectory(duration: float) -> SpatialTrajectory:
    """Static point source, focused attention."""
    return SpatialTrajectory(
        motion=SpatialMotion.POINT_SOURCE,
        keyframes=[
            (0.0, Pos3D(az=0, el=5, dist=4)),
            (1.0, Pos3D(az=0, el=5, dist=4)),
        ],
        ease_type="linear",
    )


def _make_corners_trajectory(duration: float) -> SpatialTrajectory:
    """Sound moves through three corners sequentially."""
    return SpatialTrajectory(
        motion=SpatialMotion.THREE_CORNERS,
        keyframes=[
            (0.0, Pos3D(az=-45, el=15, dist=5)),  # Front-left
            (0.35, Pos3D(az=45, el=15, dist=5)),  # Front-right
            (0.7, Pos3D(az=0, el=30, dist=5)),  # Above-center
            (1.0, Pos3D(az=0, el=10, dist=4)),  # Settle center
        ],
        ease_type="ease_in_out",
    )


def _make_approach_trajectory(duration: float) -> SpatialTrajectory:
    """Sound approaches from distance."""
    return SpatialTrajectory(
        motion=SpatialMotion.APPROACH_FROM_DISTANCE,
        keyframes=[
            (0.0, Pos3D(az=0, el=5, dist=10)),  # Far
            (0.3, Pos3D(az=0, el=5, dist=7)),  # Approaching
            (0.6, Pos3D(az=0, el=5, dist=5)),  # Getting closer
            (1.0, Pos3D(az=0, el=5, dist=3.5)),  # Near
        ],
        ease_type="ease_out",
    )


TRAJECTORY_GENERATORS: dict[SpatialMotion, Callable[[float], SpatialTrajectory]] = {
    SpatialMotion.DESCEND_FROM_ABOVE: _make_descend_trajectory,
    SpatialMotion.BLOOM_FROM_CENTER: _make_bloom_trajectory,
    SpatialMotion.RISE_FROM_FLOOR: _make_rise_trajectory,
    SpatialMotion.PULSE_FRONT_CENTER: _make_pulse_trajectory,
    SpatialMotion.SWEEP_FROM_DOOR: _make_sweep_door_trajectory,
    SpatialMotion.RECEDE_TO_DOOR: _make_recede_door_trajectory,
    SpatialMotion.SURROUND_ROOM: _make_surround_trajectory,
    SpatialMotion.SETTLE_DOWNWARD: _make_settle_trajectory,
    SpatialMotion.POINT_SOURCE: _make_point_trajectory,
    SpatialMotion.THREE_CORNERS: _make_corners_trajectory,
    SpatialMotion.APPROACH_FROM_DISTANCE: _make_approach_trajectory,
}


# =============================================================================
# Earcon Definition — The Complete Specification
# =============================================================================


@dataclass
class EarconDefinition:
    """Complete definition of a virtuoso earcon.

    This is the full specification for a single earcon,
    including emotional intent, orchestration, and spatial behavior.
    """

    name: str
    intent: EmotionalIntent
    description: str  # Human-readable description
    duration: float  # Total duration in seconds
    orchestration: Orchestration
    spatial_motion: SpatialMotion
    tags: list[str] = field(default_factory=list)

    # Quality markers
    leitmotif: str = ""  # Musical signature description
    character: str = ""  # Personality description

    def get_trajectory(self) -> SpatialTrajectory:
        """Get the spatial trajectory for this earcon."""
        generator = TRAJECTORY_GENERATORS.get(self.spatial_motion, _make_point_trajectory)
        return generator(self.duration)


# =============================================================================
# TIER 1: Core Earcons (14 Redesigned)
# =============================================================================
# Each earcon is a complete musical phrase with orchestral instruments,
# emotional intent, and spatial trajectory.


def _create_notification_earcon() -> EarconDefinition:
    """Gentle attention - descending harp glissando with celeste shimmer.

    Like a gentle tap on the shoulder from heaven.
    Williams influence: The shimmering celeste from E.T.
    """
    return EarconDefinition(
        name="notification",
        intent=EmotionalIntent.GENTLE_ATTENTION,
        description="Gentle attention-getting chime that descends from above",
        duration=1.5,
        leitmotif="Descending major 6th with shimmer",
        character="Ethereal, non-intrusive, like starlight",
        orchestration=Orchestration(
            voices=[
                # Harp glissando (primary voice)
                InstrumentVoice(
                    instrument_key="harp",
                    articulation="Short Gliss",
                    notes=[
                        # Descending C major arpeggio
                        (0.0, 84, 0.3, 80),  # C6
                        (0.05, 79, 0.3, 75),  # G5
                        (0.1, 76, 0.3, 70),  # E5
                        (0.15, 72, 0.4, 65),  # C5
                        (0.2, 67, 0.5, 60),  # G4
                    ],
                    pan=-0.1,
                    reverb_send=0.4,
                ),
                # Celeste shimmer (color)
                InstrumentVoice(
                    instrument_key="celeste",
                    articulation="Short Sustained",
                    notes=[
                        (0.1, 84, 0.6, 50),  # C6 - shimmer
                        (0.2, 88, 0.5, 45),  # E6
                    ],
                    pan=0.1,
                    reverb_send=0.5,
                ),
            ],
            tempo_bpm=100,
            total_duration=1.5,
            master_volume=0.7,
            room_reverb=0.35,
        ),
        spatial_motion=SpatialMotion.DESCEND_FROM_ABOVE,
        tags=["info", "message", "update", "gentle"],
    )


def _create_success_earcon() -> EarconDefinition:
    """Triumph without arrogance - French horn call with strings swell.

    The feeling of accomplishment, earned through effort.
    Williams influence: The heroic French horn from Superman.
    """
    return EarconDefinition(
        name="success",
        intent=EmotionalIntent.TRIUMPH,
        description="Triumphant affirmation that blooms from center",
        duration=1.2,
        leitmotif="Rising perfect 5th, resolving to major",
        character="Noble, warm, earned - not boastful",
        orchestration=Orchestration(
            voices=[
                # French horn - the hero call
                InstrumentVoice(
                    instrument_key="horn",
                    articulation="Long",
                    notes=[
                        (0.0, 55, 0.4, 85),  # G3 - foundation
                        (0.3, 62, 0.6, 95),  # D4 - rising 5th
                    ],
                    cc1_dynamics=[(0.0, 70), (0.3, 100), (0.8, 85)],
                    pan=0.0,
                    reverb_send=0.3,
                ),
                # Violins - warmth and swell
                InstrumentVoice(
                    instrument_key="violins_1",
                    articulation="Long",
                    notes=[
                        (0.1, 67, 0.8, 70),  # G4
                        (0.1, 71, 0.8, 65),  # B4
                        (0.1, 74, 0.8, 60),  # D5
                    ],
                    cc1_dynamics=[(0.1, 50), (0.5, 85), (1.0, 60)],
                    pan=0.0,
                    reverb_send=0.35,
                ),
                # Subtle timpani punctuation
                InstrumentVoice(
                    instrument_key="timpani",
                    articulation="Short Hits",
                    notes=[(0.0, 43, 0.2, 75)],  # G2
                    pan=0.0,
                    reverb_send=0.25,
                ),
            ],
            tempo_bpm=108,
            total_duration=1.2,
            master_volume=0.75,
            room_reverb=0.3,
        ),
        spatial_motion=SpatialMotion.BLOOM_FROM_CENTER,
        tags=["positive", "complete", "achievement"],
    )


def _create_error_earcon() -> EarconDefinition:
    """Concern, not panic - Low brass minor 2nd with timpani.

    Something went wrong, but it's manageable.
    Elfman influence: The tension without terror from Batman.
    """
    return EarconDefinition(
        name="error",
        intent=EmotionalIntent.CONCERN_NOT_PANIC,
        description="Concerning notification that rises from below",
        duration=1.0,
        leitmotif="Minor 2nd interval, unresolved",
        character="Serious but not alarming, prompting attention",
        orchestration=Orchestration(
            voices=[
                # Bass trombone - weight and gravity
                InstrumentVoice(
                    instrument_key="bass_trombones_a2",
                    articulation="Long",
                    notes=[
                        (0.0, 41, 0.5, 85),  # F2
                        (0.1, 42, 0.5, 80),  # F#2 - minor 2nd tension
                    ],
                    cc1_dynamics=[(0.0, 80), (0.4, 95), (0.8, 60)],
                    pan=0.0,
                    reverb_send=0.25,
                ),
                # Timpani rumble
                InstrumentVoice(
                    instrument_key="timpani",
                    articulation="Long Rolls",
                    notes=[(0.0, 41, 0.6, 70)],  # F2 roll
                    pan=0.0,
                    reverb_send=0.2,
                ),
                # Violas - dark color
                InstrumentVoice(
                    instrument_key="violas",
                    articulation="Tremolo",
                    notes=[
                        (0.1, 53, 0.5, 60),  # F3
                        (0.1, 54, 0.5, 55),  # F#3
                    ],
                    pan=0.0,
                    reverb_send=0.3,
                ),
            ],
            tempo_bpm=80,
            total_duration=1.0,
            master_volume=0.7,
            room_reverb=0.25,
        ),
        spatial_motion=SpatialMotion.RISE_FROM_FLOOR,
        tags=["negative", "failure", "problem"],
    )


def _create_alert_earcon() -> EarconDefinition:
    """Urgent importance - Trumpet stab with snare rim.

    Demands immediate attention without causing fear.
    Williams influence: The urgent brass from Jaws (but shorter).
    """
    return EarconDefinition(
        name="alert",
        intent=EmotionalIntent.URGENT_IMPORTANCE,
        description="Urgent attention-demanding pulse from front",
        duration=0.8,
        leitmotif="Staccato tritone resolved up",
        character="Urgent, direct, commanding",
        orchestration=Orchestration(
            voices=[
                # Trumpet stab - cutting through
                InstrumentVoice(
                    instrument_key="trumpet",
                    articulation="Short Staccatissimo",
                    notes=[
                        (0.0, 77, 0.15, 100),  # F5
                        (0.2, 77, 0.15, 95),  # F5 repeat
                        (0.4, 79, 0.2, 105),  # G5 - resolution up
                    ],
                    pan=0.0,
                    reverb_send=0.2,
                ),
                # Snare rim shot
                InstrumentVoice(
                    instrument_key="untuned_percussion",
                    articulation="Snare 1",
                    notes=[
                        (0.0, 38, 0.1, 90),
                        (0.2, 38, 0.1, 85),
                    ],
                    pan=0.0,
                    reverb_send=0.15,
                ),
            ],
            tempo_bpm=140,
            total_duration=0.8,
            master_volume=0.8,
            room_reverb=0.2,
        ),
        spatial_motion=SpatialMotion.PULSE_FRONT_CENTER,
        tags=["urgent", "attention", "critical"],
    )


def _create_arrival_earcon() -> EarconDefinition:
    """Warm welcome - Warm strings with oboe theme.

    The feeling of coming home to someone who cares.
    Williams influence: The warmth of Hedwig's Theme.
    """
    return EarconDefinition(
        name="arrival",
        intent=EmotionalIntent.WARM_WELCOME,
        description="Welcoming sound that sweeps from entry door",
        duration=2.0,
        leitmotif="Rising major 3rd with suspensions",
        character="Welcoming, warm, like an embrace",
        orchestration=Orchestration(
            voices=[
                # Oboe - personal, singing
                InstrumentVoice(
                    instrument_key="oboe",
                    articulation="Legato",
                    notes=[
                        (0.2, 64, 0.5, 75),  # E4
                        (0.6, 67, 0.5, 80),  # G4
                        (1.0, 72, 0.6, 85),  # C5
                    ],
                    cc1_dynamics=[(0.2, 65), (0.8, 90), (1.5, 70)],
                    pan=0.0,
                    reverb_send=0.35,
                ),
                # Warm strings - foundation
                InstrumentVoice(
                    instrument_key="violins_1",
                    articulation="Long",
                    notes=[
                        (0.0, 60, 1.5, 65),  # C4
                        (0.0, 64, 1.5, 60),  # E4
                        (0.0, 67, 1.5, 55),  # G4
                    ],
                    cc1_dynamics=[(0.0, 50), (0.8, 80), (1.8, 55)],
                    pan=-0.15,
                    reverb_send=0.4,
                ),
                # Celli - warmth below
                InstrumentVoice(
                    instrument_key="celli",
                    articulation="Long",
                    notes=[(0.0, 48, 1.5, 60)],  # C3
                    cc1_dynamics=[(0.0, 55), (0.8, 75), (1.8, 50)],
                    pan=0.15,
                    reverb_send=0.35,
                ),
            ],
            tempo_bpm=72,
            total_duration=2.0,
            master_volume=0.72,
            room_reverb=0.4,
        ),
        spatial_motion=SpatialMotion.SWEEP_FROM_DOOR,
        tags=["presence", "welcome", "home"],
    )


def _create_departure_earcon() -> EarconDefinition:
    """Fond farewell - Fading strings with solo cello.

    A gentle goodbye, not sad but tender.
    Williams influence: The bittersweet ending of Schindler's List.
    """
    return EarconDefinition(
        name="departure",
        intent=EmotionalIntent.FOND_FAREWELL,
        description="Gentle farewell that recedes toward door",
        duration=2.0,
        leitmotif="Descending major 2nd with suspension",
        character="Tender, not sad - 'see you soon'",
        orchestration=Orchestration(
            voices=[
                # Solo cello - personal, intimate
                InstrumentVoice(
                    instrument_key="celli_leader",
                    articulation="Legato",
                    notes=[
                        (0.0, 60, 0.8, 70),  # C4
                        (0.7, 59, 0.8, 65),  # B3 - step down
                        (1.4, 57, 0.5, 55),  # A3 - settling
                    ],
                    cc1_dynamics=[(0.0, 75), (0.7, 65), (1.4, 45)],
                    pan=0.0,
                    reverb_send=0.4,
                ),
                # Strings - fading bed
                InstrumentVoice(
                    instrument_key="violins_2",
                    articulation="Long Sul Tasto",  # Soft, distant
                    notes=[
                        (0.0, 64, 1.8, 55),  # E4
                        (0.0, 67, 1.8, 50),  # G4
                    ],
                    cc1_dynamics=[(0.0, 60), (1.5, 30)],
                    pan=0.0,
                    reverb_send=0.5,
                ),
            ],
            tempo_bpm=66,
            total_duration=2.0,
            master_volume=0.65,
            room_reverb=0.45,
        ),
        spatial_motion=SpatialMotion.RECEDE_TO_DOOR,
        tags=["presence", "leaving", "away"],
    )


def _create_celebration_earcon() -> EarconDefinition:
    """Pure joy - Full orchestra tutti.

    The triumphant moment, complete victory.
    Williams influence: The finale of Star Wars.
    """
    return EarconDefinition(
        name="celebration",
        intent=EmotionalIntent.PURE_JOY,
        description="Triumphant celebration surrounding the room",
        duration=3.0,
        leitmotif="Ascending fanfare to major resolution",
        character="Triumphant, joyful, full of life",
        orchestration=Orchestration(
            voices=[
                # Brass fanfare
                InstrumentVoice(
                    instrument_key="trumpets_a2",
                    articulation="Long Cuivre",
                    notes=[
                        (0.0, 72, 0.3, 95),  # C5
                        (0.3, 76, 0.3, 100),  # E5
                        (0.6, 79, 0.4, 105),  # G5
                        (1.0, 84, 0.8, 110),  # C6 - triumph!
                    ],
                    cc1_dynamics=[(0.0, 85), (1.0, 115), (2.0, 90)],
                    pan=0.0,
                    reverb_send=0.35,
                ),
                # French horns - nobility
                InstrumentVoice(
                    instrument_key="horns_a4",
                    articulation="Long",
                    notes=[
                        (0.0, 60, 0.8, 85),  # C4
                        (0.6, 67, 0.8, 90),  # G4
                        (1.0, 72, 1.5, 95),  # C5
                    ],
                    cc1_dynamics=[(0.0, 80), (1.0, 105), (2.5, 75)],
                    pan=0.0,
                    reverb_send=0.35,
                ),
                # Strings - soaring
                InstrumentVoice(
                    instrument_key="violins_1",
                    articulation="Long",
                    notes=[
                        (0.5, 72, 2.0, 80),  # C5
                        (0.5, 76, 2.0, 75),  # E5
                        (0.5, 79, 2.0, 70),  # G5
                    ],
                    cc1_dynamics=[(0.5, 70), (1.5, 100), (2.8, 60)],
                    pan=0.0,
                    reverb_send=0.4,
                ),
                # Timpani - grandeur
                InstrumentVoice(
                    instrument_key="timpani",
                    articulation="Long Rolls",
                    notes=[(0.8, 48, 1.5, 85)],  # C3 roll
                    pan=0.0,
                    reverb_send=0.3,
                ),
                # Cymbal crash
                InstrumentVoice(
                    instrument_key="untuned_percussion",
                    articulation="Cymbal",
                    notes=[(1.0, 49, 0.5, 95)],
                    pan=0.0,
                    reverb_send=0.5,
                ),
            ],
            tempo_bpm=132,
            total_duration=3.0,
            master_volume=0.85,
            room_reverb=0.35,
        ),
        spatial_motion=SpatialMotion.SURROUND_ROOM,
        tags=["positive", "triumph", "complete", "major"],
    )


def _create_settling_earcon() -> EarconDefinition:
    """Peaceful descent - Descending harp with muted strings.

    The day is done, time to rest.
    Williams influence: The lullaby quality of Hook.
    """
    return EarconDefinition(
        name="settling",
        intent=EmotionalIntent.PEACEFUL_DESCENT,
        description="Calming sound that settles downward",
        duration=2.5,
        leitmotif="Descending pentatonic over sustained 5th",
        character="Peaceful, calming, like a sigh of contentment",
        orchestration=Orchestration(
            voices=[
                # Harp - descending arpeggios
                InstrumentVoice(
                    instrument_key="harp",
                    articulation="Short Sustained",
                    notes=[
                        (0.0, 79, 0.4, 60),  # G5
                        (0.2, 76, 0.4, 55),  # E5
                        (0.4, 72, 0.4, 50),  # C5
                        (0.6, 67, 0.5, 45),  # G4
                        (0.9, 64, 0.5, 40),  # E4
                        (1.2, 60, 0.6, 35),  # C4
                    ],
                    pan=0.0,
                    reverb_send=0.45,
                ),
                # Muted strings - pillowy bed
                InstrumentVoice(
                    instrument_key="violins_1",
                    articulation="Long CS",  # Con sordino (muted)
                    notes=[
                        (0.0, 60, 2.2, 45),  # C4
                        (0.0, 67, 2.2, 40),  # G4 - open 5th
                    ],
                    cc1_dynamics=[(0.0, 50), (1.5, 35), (2.3, 20)],
                    pan=-0.1,
                    reverb_send=0.5,
                ),
                # Celli - warmth
                InstrumentVoice(
                    instrument_key="celli",
                    articulation="Long CS",
                    notes=[(0.0, 48, 2.2, 40)],  # C3
                    cc1_dynamics=[(0.0, 45), (1.5, 30), (2.3, 15)],
                    pan=0.1,
                    reverb_send=0.45,
                ),
            ],
            tempo_bpm=60,
            total_duration=2.5,
            master_volume=0.6,
            room_reverb=0.5,
        ),
        spatial_motion=SpatialMotion.SETTLE_DOWNWARD,
        tags=["calm", "goodnight", "wind-down"],
    )


def _create_awakening_earcon() -> EarconDefinition:
    """Gentle rising - Solo flute with pizzicato strings.

    A new day begins, full of possibility.
    Williams influence: The wonder of Jurassic Park's first dinosaur reveal.
    """
    return EarconDefinition(
        name="awakening",
        intent=EmotionalIntent.GENTLE_RISING,
        description="Gentle morning sound that rises from below",
        duration=2.5,
        leitmotif="Rising major scale fragment with grace notes",
        character="Fresh, hopeful, like morning light",
        orchestration=Orchestration(
            voices=[
                # Solo flute - clear, bright
                InstrumentVoice(
                    instrument_key="flute",
                    articulation="Legato",
                    notes=[
                        (0.3, 72, 0.4, 65),  # C5
                        (0.6, 74, 0.4, 70),  # D5
                        (0.9, 76, 0.4, 75),  # E5
                        (1.3, 79, 0.6, 80),  # G5
                        (1.8, 84, 0.5, 75),  # C6
                    ],
                    cc1_dynamics=[(0.3, 55), (1.0, 80), (2.0, 65)],
                    pan=0.0,
                    reverb_send=0.35,
                ),
                # Pizzicato strings - sparkling
                InstrumentVoice(
                    instrument_key="violins_1",
                    articulation="Short Pizzicato",
                    notes=[
                        (0.0, 60, 0.15, 50),  # C4
                        (0.4, 64, 0.15, 55),  # E4
                        (0.8, 67, 0.15, 60),  # G4
                        (1.2, 72, 0.15, 55),  # C5
                    ],
                    pan=-0.2,
                    reverb_send=0.3,
                ),
                # Celeste - magic dust
                InstrumentVoice(
                    instrument_key="celeste",
                    articulation="Short Sustained",
                    notes=[
                        (1.5, 84, 0.4, 45),  # C6
                        (1.7, 88, 0.4, 40),  # E6
                    ],
                    pan=0.2,
                    reverb_send=0.45,
                ),
            ],
            tempo_bpm=72,
            total_duration=2.5,
            master_volume=0.65,
            room_reverb=0.4,
        ),
        spatial_motion=SpatialMotion.RISE_FROM_FLOOR,
        tags=["morning", "wake", "start", "fresh"],
    )


def _create_cinematic_earcon() -> EarconDefinition:
    """Epic anticipation - Brass fanfare with timpani roll.

    The moment before something amazing.
    Williams influence: The 20th Century Fox fanfare.
    """
    return EarconDefinition(
        name="cinematic",
        intent=EmotionalIntent.EPIC_ANTICIPATION,
        description="Dramatic sound that blooms through entire room",
        duration=3.0,
        leitmotif="Ascending fanfare with timpani crescendo",
        character="Cinematic, epic, full of promise",
        orchestration=Orchestration(
            voices=[
                # Trumpets - the announcement
                InstrumentVoice(
                    instrument_key="trumpets_a2",
                    articulation="Long Sfz",  # Strong attack
                    notes=[
                        (0.5, 67, 0.4, 90),  # G4
                        (0.9, 72, 0.4, 95),  # C5
                        (1.3, 76, 0.5, 100),  # E5
                        (1.8, 79, 0.8, 105),  # G5
                    ],
                    cc1_dynamics=[(0.5, 80), (1.5, 110), (2.5, 85)],
                    pan=0.0,
                    reverb_send=0.35,
                ),
                # Horns - depth
                InstrumentVoice(
                    instrument_key="horns_a4",
                    articulation="Long Cuivre",
                    notes=[
                        (0.3, 55, 2.0, 85),  # G3
                        (0.3, 60, 2.0, 80),  # C4
                    ],
                    cc1_dynamics=[(0.3, 75), (1.5, 100), (2.5, 70)],
                    pan=0.0,
                    reverb_send=0.35,
                ),
                # Timpani - building tension
                InstrumentVoice(
                    instrument_key="timpani",
                    articulation="Long Rolls",
                    notes=[(0.0, 48, 2.5, 80)],  # C3 crescendo roll
                    cc1_dynamics=[(0.0, 50), (1.5, 100), (2.5, 60)],
                    pan=0.0,
                    reverb_send=0.3,
                ),
                # Strings - sweeping
                InstrumentVoice(
                    instrument_key="violins_1",
                    articulation="Long Marcato Attack",
                    notes=[
                        (1.0, 72, 1.5, 75),  # C5
                        (1.0, 76, 1.5, 70),  # E5
                        (1.0, 79, 1.5, 65),  # G5
                    ],
                    cc1_dynamics=[(1.0, 65), (2.0, 95), (2.8, 60)],
                    pan=0.0,
                    reverb_send=0.4,
                ),
                # Cymbal swell
                InstrumentVoice(
                    instrument_key="untuned_percussion",
                    articulation="Cymbal",
                    notes=[(1.8, 49, 0.8, 90)],
                    pan=0.0,
                    reverb_send=0.5,
                ),
            ],
            tempo_bpm=100,
            total_duration=3.0,
            master_volume=0.85,
            room_reverb=0.4,
        ),
        spatial_motion=SpatialMotion.SURROUND_ROOM,
        tags=["dramatic", "movie", "theater", "epic"],
    )


def _create_focus_earcon() -> EarconDefinition:
    """Clear attention - Crystalline bell tone with harmonic shimmer.

    A moment of clarity, bringing attention to now.
    Like a meditation bell in a quiet temple.
    """
    return EarconDefinition(
        name="focus",
        intent=EmotionalIntent.CLEAR_ATTENTION,
        description="Clear focus ping from center - crystalline clarity",
        duration=1.0,
        leitmotif="Pure tone with crystalline resonance",
        character="Clear, centered, meditative, deliberate",
        orchestration=Orchestration(
            voices=[
                # Vibraphone - clear, resonant primary
                InstrumentVoice(
                    instrument_key="vibraphone",
                    articulation="Short Hits",
                    notes=[
                        (0.0, 79, 0.8, 80),  # G5 - pure tone
                        (0.3, 79, 0.5, 50),  # G5 - echo (softer)
                    ],
                    pan=0.0,
                    reverb_send=0.45,
                ),
                # Celeste - ethereal shimmer
                InstrumentVoice(
                    instrument_key="celeste",
                    articulation="Short Sustained",
                    notes=[
                        (0.05, 91, 0.5, 35),  # G6 - octave above
                        (0.35, 86, 0.4, 25),  # D6 - harmonic
                    ],
                    pan=0.0,
                    reverb_send=0.5,
                ),
                # Subtle harp pluck - grounding
                InstrumentVoice(
                    instrument_key="harp",
                    articulation="Close Plucked",
                    notes=[
                        (0.0, 67, 0.4, 40),  # G4 - root
                    ],
                    pan=0.0,
                    reverb_send=0.4,
                ),
            ],
            tempo_bpm=72,
            total_duration=1.0,
            master_volume=0.65,
            room_reverb=0.5,
        ),
        spatial_motion=SpatialMotion.POINT_SOURCE,
        tags=["attention", "work", "concentration", "meditation"],
    )


def _create_security_arm_earcon() -> EarconDefinition:
    """Confident confirmation - Woodwind chord with chime.

    The house is secure, you can relax.
    Elfman influence: The quirky precision of his confirmation sounds.
    """
    return EarconDefinition(
        name="security_arm",
        intent=EmotionalIntent.CONFIDENT_CONFIRMATION,
        description="Security confirmation moving through corners",
        duration=1.2,
        leitmotif="Three ascending notes in sequence",
        character="Confident, precise, reassuring",
        orchestration=Orchestration(
            voices=[
                # Clarinets - three confirmations
                InstrumentVoice(
                    instrument_key="clarinets_a3",
                    articulation="Short Staccatissimo",
                    notes=[
                        (0.0, 60, 0.15, 75),  # C4
                        (0.3, 64, 0.15, 80),  # E4
                        (0.6, 67, 0.2, 85),  # G4
                    ],
                    pan=0.0,
                    reverb_send=0.25,
                ),
                # Tubular bells - final confirmation
                InstrumentVoice(
                    instrument_key="tubular_bells",
                    articulation="Short Hits",
                    notes=[(0.8, 72, 0.35, 75)],  # C5
                    pan=0.0,
                    reverb_send=0.4,
                ),
            ],
            tempo_bpm=120,
            total_duration=1.2,
            master_volume=0.7,
            room_reverb=0.3,
        ),
        spatial_motion=SpatialMotion.THREE_CORNERS,
        tags=["security", "arm", "confirm", "safe"],
    )


def _create_package_earcon() -> EarconDefinition:
    """Delightful surprise - Pizzicato with triangle.

    Something arrived! A small joy.
    Elfman influence: The playful surprise of Edward Scissorhands.
    """
    return EarconDefinition(
        name="package",
        intent=EmotionalIntent.DELIGHTFUL_SURPRISE,
        description="Playful notification sweeping from entry",
        duration=1.5,
        leitmotif="Playful pizzicato with bell accent",
        character="Playful, surprising, delightful",
        orchestration=Orchestration(
            voices=[
                # Pizzicato strings - bouncy
                InstrumentVoice(
                    instrument_key="violins_1",
                    articulation="Short Pizzicato",
                    notes=[
                        (0.0, 67, 0.12, 75),  # G4
                        (0.15, 72, 0.12, 80),  # C5
                        (0.3, 76, 0.12, 85),  # E5
                        (0.5, 79, 0.15, 80),  # G5
                    ],
                    pan=-0.1,
                    reverb_send=0.3,
                ),
                # Celli pizz - foundation
                InstrumentVoice(
                    instrument_key="celli",
                    articulation="Short Pizzicato",
                    notes=[(0.0, 48, 0.2, 70)],  # C3
                    pan=0.1,
                    reverb_send=0.3,
                ),
                # Triangle - sparkle
                InstrumentVoice(
                    instrument_key="untuned_percussion",
                    articulation="Triangle",
                    notes=[
                        (0.5, 84, 0.3, 70),
                        (0.8, 84, 0.3, 65),
                    ],
                    pan=0.0,
                    reverb_send=0.45,
                ),
                # Celeste - magic
                InstrumentVoice(
                    instrument_key="celeste",
                    articulation="Short Sustained",
                    notes=[(0.7, 91, 0.4, 55)],  # G6
                    pan=0.0,
                    reverb_send=0.5,
                ),
            ],
            tempo_bpm=132,
            total_duration=1.5,
            master_volume=0.7,
            room_reverb=0.35,
        ),
        spatial_motion=SpatialMotion.SWEEP_FROM_DOOR,
        tags=["delivery", "package", "arrival", "surprise"],
    )


def _create_meeting_soon_earcon() -> EarconDefinition:
    """Respectful urgency - Ascending woodwind scale.

    Time to prepare, but no panic.
    Williams influence: The gentle urgency of Catch Me If You Can.
    """
    return EarconDefinition(
        name="meeting_soon",
        intent=EmotionalIntent.RESPECTFUL_URGENCY,
        description="Approaching reminder from distance",
        duration=1.5,
        leitmotif="Ascending scale with slight acceleration",
        character="Respectful, urging, professional",
        orchestration=Orchestration(
            voices=[
                # Flute - ascending
                InstrumentVoice(
                    instrument_key="flute",
                    articulation="Short Staccatissimo",
                    notes=[
                        (0.0, 72, 0.15, 70),  # C5
                        (0.2, 74, 0.15, 75),  # D5
                        (0.38, 76, 0.15, 80),  # E5
                        (0.54, 77, 0.15, 85),  # F5
                        (0.68, 79, 0.2, 90),  # G5
                    ],
                    pan=0.0,
                    reverb_send=0.3,
                ),
                # Oboe - support
                InstrumentVoice(
                    instrument_key="oboe",
                    articulation="Short Staccatissimo",
                    notes=[
                        (0.1, 60, 0.15, 60),  # C4 - octave below
                        (0.3, 62, 0.15, 65),  # D4
                        (0.48, 64, 0.15, 70),  # E4
                    ],
                    pan=0.0,
                    reverb_send=0.3,
                ),
                # Subtle chime punctuation
                InstrumentVoice(
                    instrument_key="glockenspiel",
                    articulation="Short Hits",
                    notes=[(0.9, 91, 0.3, 65)],  # G6
                    pan=0.0,
                    reverb_send=0.4,
                ),
            ],
            tempo_bpm=120,
            total_duration=1.5,
            master_volume=0.7,
            room_reverb=0.3,
        ),
        spatial_motion=SpatialMotion.APPROACH_FROM_DISTANCE,
        tags=["calendar", "meeting", "reminder", "schedule"],
    )


# =============================================================================
# TIER 2: Extended Soundscape (30+ New Earcons)
# =============================================================================


def _create_room_enter_earcon() -> EarconDefinition:
    """Subtle warmth as you enter a room."""
    return EarconDefinition(
        name="room_enter",
        intent=EmotionalIntent.SUBTLE_AWARENESS,
        description="Subtle warmth when entering a room",
        duration=0.8,
        leitmotif="Soft string breath",
        character="Barely there, acknowledging presence",
        orchestration=Orchestration(
            voices=[
                InstrumentVoice(
                    instrument_key="violins_1",
                    articulation="Long Flautando",
                    notes=[(0.0, 67, 0.7, 35)],  # G4 - gentle
                    cc1_dynamics=[(0.0, 30), (0.3, 45), (0.7, 25)],
                    pan=0.0,
                    reverb_send=0.5,
                ),
            ],
            tempo_bpm=60,
            total_duration=0.8,
            master_volume=0.4,
            room_reverb=0.5,
        ),
        spatial_motion=SpatialMotion.BLOOM_FROM_CENTER,
        tags=["presence", "room", "enter", "subtle"],
    )


def _create_door_open_earcon() -> EarconDefinition:
    """Neutral awareness - door opened."""
    return EarconDefinition(
        name="door_open",
        intent=EmotionalIntent.SUBTLE_AWARENESS,
        description="Door opening notification",
        duration=0.6,
        leitmotif="Hollow wood resonance",
        character="Neutral, informative",
        orchestration=Orchestration(
            voices=[
                InstrumentVoice(
                    instrument_key="marimba",
                    articulation="Short Hits",
                    notes=[
                        (0.0, 60, 0.25, 65),  # C4
                        (0.15, 67, 0.25, 60),  # G4
                    ],
                    pan=0.0,
                    reverb_send=0.35,
                ),
            ],
            tempo_bpm=90,
            total_duration=0.6,
            master_volume=0.55,
            room_reverb=0.35,
        ),
        spatial_motion=SpatialMotion.SWEEP_FROM_DOOR,
        tags=["door", "open", "security"],
    )


def _create_door_close_earcon() -> EarconDefinition:
    """Reassuring seal - door closed."""
    return EarconDefinition(
        name="door_close",
        intent=EmotionalIntent.CONFIDENT_CONFIRMATION,
        description="Door closing confirmation",
        duration=0.5,
        leitmotif="Resonant thud with warmth",
        character="Secure, complete",
        orchestration=Orchestration(
            voices=[
                InstrumentVoice(
                    instrument_key="timpani",
                    articulation="Short Hits Damped",
                    notes=[(0.0, 48, 0.2, 70)],  # C3
                    pan=0.0,
                    reverb_send=0.25,
                ),
                InstrumentVoice(
                    instrument_key="basses",
                    articulation="Short Pizzicato",
                    notes=[(0.05, 36, 0.2, 55)],  # C2
                    pan=0.0,
                    reverb_send=0.3,
                ),
            ],
            tempo_bpm=80,
            total_duration=0.5,
            master_volume=0.6,
            room_reverb=0.3,
        ),
        spatial_motion=SpatialMotion.POINT_SOURCE,
        tags=["door", "close", "security", "seal"],
    )


def _create_lock_engaged_earcon() -> EarconDefinition:
    """Confident security - lock engaged."""
    return EarconDefinition(
        name="lock_engaged",
        intent=EmotionalIntent.CONFIDENT_CONFIRMATION,
        description="Lock engaged confirmation",
        duration=0.7,
        leitmotif="Mechanical click with resonance",
        character="Secure, mechanical, reliable",
        orchestration=Orchestration(
            voices=[
                InstrumentVoice(
                    instrument_key="xylophone",
                    articulation="Short Hits",
                    notes=[
                        (0.0, 84, 0.15, 80),  # C6
                        (0.15, 88, 0.2, 75),  # E6
                    ],
                    pan=0.0,
                    reverb_send=0.3,
                ),
                InstrumentVoice(
                    instrument_key="celli",
                    articulation="Short Pizzicato",
                    notes=[(0.2, 48, 0.2, 60)],  # C3 - confirmation
                    pan=0.0,
                    reverb_send=0.25,
                ),
            ],
            tempo_bpm=100,
            total_duration=0.7,
            master_volume=0.65,
            room_reverb=0.3,
        ),
        spatial_motion=SpatialMotion.POINT_SOURCE,
        tags=["lock", "security", "engaged", "safe"],
    )


def _create_voice_acknowledge_earcon() -> EarconDefinition:
    """I'm listening - voice assistant acknowledgment."""
    return EarconDefinition(
        name="voice_acknowledge",
        intent=EmotionalIntent.SUBTLE_AWARENESS,
        description="Voice assistant is listening",
        duration=0.4,
        leitmotif="Soft rising dyad",
        character="Attentive, present, ready",
        orchestration=Orchestration(
            voices=[
                InstrumentVoice(
                    instrument_key="celeste",
                    articulation="Short Sustained",
                    notes=[
                        (0.0, 72, 0.3, 55),  # C5
                        (0.05, 76, 0.3, 50),  # E5
                    ],
                    pan=0.0,
                    reverb_send=0.4,
                ),
            ],
            tempo_bpm=100,
            total_duration=0.4,
            master_volume=0.55,
            room_reverb=0.4,
        ),
        spatial_motion=SpatialMotion.BLOOM_FROM_CENTER,
        tags=["voice", "acknowledge", "listening", "assistant"],
    )


def _create_voice_complete_earcon() -> EarconDefinition:
    """Done - voice assistant task complete."""
    return EarconDefinition(
        name="voice_complete",
        intent=EmotionalIntent.TRIUMPH,
        description="Voice assistant task completed",
        duration=0.5,
        leitmotif="Resolved chord",
        character="Complete, satisfied, done",
        orchestration=Orchestration(
            voices=[
                InstrumentVoice(
                    instrument_key="harp",
                    articulation="Short Sustained",
                    notes=[
                        (0.0, 60, 0.4, 65),  # C4
                        (0.0, 64, 0.4, 60),  # E4
                        (0.0, 67, 0.4, 55),  # G4
                    ],
                    pan=0.0,
                    reverb_send=0.4,
                ),
            ],
            tempo_bpm=100,
            total_duration=0.5,
            master_volume=0.6,
            room_reverb=0.4,
        ),
        spatial_motion=SpatialMotion.POINT_SOURCE,
        tags=["voice", "complete", "done", "assistant"],
    )


def _create_washer_complete_earcon() -> EarconDefinition:
    """Gentle cycle-done notification."""
    return EarconDefinition(
        name="washer_complete",
        intent=EmotionalIntent.GENTLE_ATTENTION,
        description="Washing machine cycle complete",
        duration=1.2,
        leitmotif="Gentle wave resolution",
        character="Clean, fresh, complete",
        orchestration=Orchestration(
            voices=[
                InstrumentVoice(
                    instrument_key="flute",
                    articulation="Legato",
                    notes=[
                        (0.0, 72, 0.4, 60),  # C5
                        (0.3, 76, 0.4, 65),  # E5
                        (0.6, 79, 0.5, 60),  # G5
                    ],
                    cc1_dynamics=[(0.0, 55), (0.5, 70), (1.0, 50)],
                    pan=0.0,
                    reverb_send=0.35,
                ),
                InstrumentVoice(
                    instrument_key="vibraphone",
                    articulation="Short Hits",
                    notes=[(0.8, 79, 0.3, 55)],  # G5
                    pan=0.0,
                    reverb_send=0.45,
                ),
            ],
            tempo_bpm=80,
            total_duration=1.2,
            master_volume=0.6,
            room_reverb=0.4,
        ),
        spatial_motion=SpatialMotion.APPROACH_FROM_DISTANCE,
        tags=["appliance", "washer", "laundry", "complete"],
    )


def _create_coffee_ready_earcon() -> EarconDefinition:
    """Morning ritual complete."""
    return EarconDefinition(
        name="coffee_ready",
        intent=EmotionalIntent.DELIGHTFUL_SURPRISE,
        description="Coffee is ready",
        duration=1.0,
        leitmotif="Warm percolating rise",
        character="Warm, inviting, aromatic",
        orchestration=Orchestration(
            voices=[
                InstrumentVoice(
                    instrument_key="clarinet",
                    articulation="Legato",
                    notes=[
                        (0.0, 60, 0.3, 60),  # C4
                        (0.25, 64, 0.3, 65),  # E4
                        (0.5, 67, 0.4, 70),  # G4
                    ],
                    cc1_dynamics=[(0.0, 55), (0.5, 75), (0.9, 60)],
                    pan=0.0,
                    reverb_send=0.35,
                ),
                InstrumentVoice(
                    instrument_key="marimba",
                    articulation="Short Hits",
                    notes=[
                        (0.0, 48, 0.2, 50),  # C3
                        (0.2, 48, 0.2, 45),  # bubbling
                        (0.4, 48, 0.2, 40),
                    ],
                    pan=0.0,
                    reverb_send=0.3,
                ),
            ],
            tempo_bpm=100,
            total_duration=1.0,
            master_volume=0.6,
            room_reverb=0.35,
        ),
        spatial_motion=SpatialMotion.APPROACH_FROM_DISTANCE,
        tags=["coffee", "kitchen", "morning", "ready"],
    )


def _create_morning_sequence_earcon() -> EarconDefinition:
    """30-second wake-up progression."""
    return EarconDefinition(
        name="morning_sequence",
        intent=EmotionalIntent.MORNING_EMERGENCE,
        description="Extended morning wake-up sequence",
        duration=30.0,
        leitmotif="Gradual orchestral awakening",
        character="Gentle, building, hopeful",
        orchestration=Orchestration(
            voices=[
                # Flute - bird-like awakening
                InstrumentVoice(
                    instrument_key="flute",
                    articulation="Legato",
                    notes=[
                        (5.0, 76, 1.0, 50),  # E5
                        (8.0, 79, 1.0, 55),  # G5
                        (12.0, 84, 1.5, 60),  # C6
                        (16.0, 88, 1.5, 65),  # E6
                        (22.0, 91, 2.0, 70),  # G6
                    ],
                    cc1_dynamics=[(0, 40), (15, 65), (28, 75)],
                    pan=0.1,
                    reverb_send=0.4,
                ),
                # Strings - gradual swell
                InstrumentVoice(
                    instrument_key="violins_1",
                    articulation="Long",
                    notes=[
                        (8.0, 60, 8.0, 40),  # C4
                        (8.0, 64, 8.0, 35),  # E4
                        (8.0, 67, 8.0, 30),  # G4
                        (18.0, 67, 10.0, 50),  # G4
                        (18.0, 72, 10.0, 45),  # C5
                        (18.0, 76, 10.0, 40),  # E5
                    ],
                    cc1_dynamics=[(8, 30), (20, 60), (28, 70)],
                    pan=-0.1,
                    reverb_send=0.45,
                ),
                # Harp - gentle arpeggios
                InstrumentVoice(
                    instrument_key="harp",
                    articulation="Short Sustained",
                    notes=[
                        (10.0, 48, 0.5, 45),  # C3
                        (11.0, 55, 0.5, 50),  # G3
                        (12.0, 60, 0.5, 55),  # C4
                        (15.0, 48, 0.5, 50),
                        (16.0, 55, 0.5, 55),
                        (17.0, 60, 0.5, 60),
                        (20.0, 60, 0.5, 55),
                        (21.0, 67, 0.5, 60),
                        (22.0, 72, 0.5, 65),
                    ],
                    pan=0.0,
                    reverb_send=0.4,
                ),
                # Celeste - sparkle at end
                InstrumentVoice(
                    instrument_key="celeste",
                    articulation="Short Sustained",
                    notes=[
                        (24.0, 84, 0.8, 50),  # C6
                        (25.5, 88, 0.8, 55),  # E6
                        (27.0, 91, 1.0, 60),  # G6
                    ],
                    pan=0.0,
                    reverb_send=0.5,
                ),
            ],
            tempo_bpm=60,
            total_duration=30.0,
            master_volume=0.55,
            room_reverb=0.5,
        ),
        spatial_motion=SpatialMotion.RISE_FROM_FLOOR,
        tags=["morning", "wake", "sequence", "ambient"],
    )


def _create_evening_transition_earcon() -> EarconDefinition:
    """Day-to-night shift."""
    return EarconDefinition(
        name="evening_transition",
        intent=EmotionalIntent.EVENING_WARMTH,
        description="Transition from day to evening mode",
        duration=3.0,
        leitmotif="Warm descending colors",
        character="Warm, settling, comfortable",
        orchestration=Orchestration(
            voices=[
                # Warm strings
                InstrumentVoice(
                    instrument_key="violins_1",
                    articulation="Long Sul Tasto",
                    notes=[
                        (0.0, 67, 2.5, 55),  # G4
                        (0.0, 64, 2.5, 50),  # E4
                        (0.0, 60, 2.5, 45),  # C4
                    ],
                    cc1_dynamics=[(0, 55), (1.5, 45), (2.8, 30)],
                    pan=0.0,
                    reverb_send=0.5,
                ),
                # Solo horn - warmth
                InstrumentVoice(
                    instrument_key="horn",
                    articulation="Long (Muted)",
                    notes=[(0.5, 55, 2.0, 50)],  # G3
                    cc1_dynamics=[(0.5, 50), (1.5, 40), (2.5, 25)],
                    pan=0.0,
                    reverb_send=0.45,
                ),
                # Harp settling
                InstrumentVoice(
                    instrument_key="harp",
                    articulation="Short Sustained",
                    notes=[
                        (0.0, 67, 0.4, 50),  # G4
                        (0.4, 64, 0.4, 45),  # E4
                        (0.8, 60, 0.5, 40),  # C4
                        (1.3, 55, 0.6, 35),  # G3
                    ],
                    pan=0.0,
                    reverb_send=0.5,
                ),
            ],
            tempo_bpm=54,
            total_duration=3.0,
            master_volume=0.55,
            room_reverb=0.55,
        ),
        spatial_motion=SpatialMotion.SETTLE_DOWNWARD,
        tags=["evening", "transition", "ambient", "warmth"],
    )


def _create_midnight_earcon() -> EarconDefinition:
    """Deep, magical acknowledgment of the witching hour."""
    return EarconDefinition(
        name="midnight",
        intent=EmotionalIntent.NIGHT_REST,
        description="Midnight chime - magical and mysterious",
        duration=2.5,
        leitmotif="Single resonant bell with ethereal aftermath",
        character="Deep, mysterious, enchanted",
        orchestration=Orchestration(
            voices=[
                # Tubular bells - the midnight chime
                InstrumentVoice(
                    instrument_key="tubular_bells",
                    articulation="Short Hits",
                    notes=[(0.0, 48, 2.0, 60)],  # C3 - deeper, more resonant
                    pan=0.0,
                    reverb_send=0.65,
                ),
                # Ethereal celeste shimmer - magic response
                InstrumentVoice(
                    instrument_key="celeste",
                    articulation="Short Sustained",
                    notes=[
                        (0.4, 84, 0.6, 30),  # C6 - sparkle
                        (0.8, 79, 0.5, 25),  # G5
                        (1.2, 72, 0.4, 20),  # C5 - fading
                    ],
                    pan=0.0,
                    reverb_send=0.7,
                ),
                # Violin harmonics - night sky
                InstrumentVoice(
                    instrument_key="violins_1",
                    articulation="Long Harmonics",
                    notes=[
                        (0.5, 91, 1.8, 25),  # G6 harmonic - stars
                    ],
                    cc1_dynamics=[(0.5, 30), (1.5, 15), (2.3, 5)],
                    pan=0.0,
                    reverb_send=0.6,
                ),
                # Basses - deep foundation
                InstrumentVoice(
                    instrument_key="basses",
                    articulation="Long",
                    notes=[(0.2, 36, 2.0, 35)],  # C2
                    cc1_dynamics=[(0.2, 35), (1.0, 20), (2.2, 8)],
                    pan=0.0,
                    reverb_send=0.5,
                ),
                # Distant horn - mystery
                InstrumentVoice(
                    instrument_key="horn",
                    articulation="Legato",
                    notes=[
                        (0.6, 48, 1.2, 25),  # C3 - distant echo
                    ],
                    cc1_dynamics=[(0.6, 25), (1.2, 15), (1.8, 5)],
                    pan=-0.1,
                    reverb_send=0.6,
                ),
            ],
            tempo_bpm=40,
            total_duration=2.5,
            master_volume=0.45,
            room_reverb=0.65,
        ),
        spatial_motion=SpatialMotion.BLOOM_FROM_CENTER,
        tags=["midnight", "night", "time", "ambient", "magical"],
    )


def _create_storm_approaching_earcon() -> EarconDefinition:
    """Atmospheric shift - storm approaching."""
    return EarconDefinition(
        name="storm_approaching",
        intent=EmotionalIntent.CONCERN_NOT_PANIC,
        description="Weather alert - storm approaching",
        duration=2.0,
        leitmotif="Low rumble with tension",
        character="Dramatic, foreboding, atmospheric",
        orchestration=Orchestration(
            voices=[
                # Timpani rumble
                InstrumentVoice(
                    instrument_key="timpani",
                    articulation="Long Rolls",
                    notes=[(0.0, 41, 1.8, 65)],  # F2
                    cc1_dynamics=[(0, 50), (0.8, 75), (1.6, 55)],
                    pan=0.0,
                    reverb_send=0.4,
                ),
                # Low brass - ominous
                InstrumentVoice(
                    instrument_key="bass_trombones_a2",
                    articulation="Long",
                    notes=[
                        (0.3, 41, 1.2, 60),  # F2
                        (0.3, 48, 1.2, 55),  # C3
                    ],
                    cc1_dynamics=[(0.3, 55), (1.0, 70), (1.5, 50)],
                    pan=0.0,
                    reverb_send=0.35,
                ),
                # Strings tremolo - tension
                InstrumentVoice(
                    instrument_key="violas",
                    articulation="Tremolo",
                    notes=[
                        (0.5, 53, 1.3, 50),  # F3
                        (0.5, 57, 1.3, 45),  # A3 - minor feel
                    ],
                    pan=0.0,
                    reverb_send=0.4,
                ),
            ],
            tempo_bpm=60,
            total_duration=2.0,
            master_volume=0.65,
            room_reverb=0.45,
        ),
        spatial_motion=SpatialMotion.APPROACH_FROM_DISTANCE,
        tags=["weather", "storm", "alert", "atmospheric"],
    )


def _create_rain_starting_earcon() -> EarconDefinition:
    """Gentle awareness - rain starting."""
    return EarconDefinition(
        name="rain_starting",
        intent=EmotionalIntent.SUBTLE_AWARENESS,
        description="Rain is starting",
        duration=1.5,
        leitmotif="Light pattering texture",
        character="Gentle, cozy, natural",
        orchestration=Orchestration(
            voices=[
                # Pizzicato - rain drops
                InstrumentVoice(
                    instrument_key="violins_1",
                    articulation="Short Pizzicato",
                    notes=[
                        (0.0, 79, 0.1, 45),
                        (0.12, 84, 0.1, 40),
                        (0.23, 76, 0.1, 50),
                        (0.35, 81, 0.1, 45),
                        (0.48, 77, 0.1, 42),
                        (0.6, 83, 0.1, 48),
                        (0.73, 78, 0.1, 44),
                        (0.85, 80, 0.1, 46),
                    ],
                    pan=0.0,
                    reverb_send=0.5,
                ),
                # Harp - gentle pattern
                InstrumentVoice(
                    instrument_key="harp",
                    articulation="Short Damped",
                    notes=[
                        (0.2, 60, 0.3, 40),  # C4
                        (0.5, 64, 0.3, 38),  # E4
                        (0.8, 67, 0.3, 42),  # G4
                    ],
                    pan=0.0,
                    reverb_send=0.5,
                ),
            ],
            tempo_bpm=100,
            total_duration=1.5,
            master_volume=0.5,
            room_reverb=0.5,
        ),
        spatial_motion=SpatialMotion.DESCEND_FROM_ABOVE,
        tags=["weather", "rain", "ambient", "cozy"],
    )


def _create_motion_detected_earcon() -> EarconDefinition:
    """Subtle awareness - motion detected."""
    return EarconDefinition(
        name="motion_detected",
        intent=EmotionalIntent.SUBTLE_AWARENESS,
        description="Motion detected in home",
        duration=0.5,
        leitmotif="Quick awareness pulse",
        character="Alert but subtle, noticing",
        orchestration=Orchestration(
            voices=[
                InstrumentVoice(
                    instrument_key="marimba",
                    articulation="Short Hits",
                    notes=[
                        (0.0, 72, 0.15, 55),  # C5
                        (0.1, 76, 0.2, 50),  # E5
                    ],
                    pan=0.0,
                    reverb_send=0.35,
                ),
            ],
            tempo_bpm=120,
            total_duration=0.5,
            master_volume=0.45,
            room_reverb=0.35,
        ),
        spatial_motion=SpatialMotion.PULSE_FRONT_CENTER,
        tags=["motion", "security", "presence", "subtle"],
    )


def _create_camera_alert_earcon() -> EarconDefinition:
    """Attention needed - camera alert."""
    return EarconDefinition(
        name="camera_alert",
        intent=EmotionalIntent.URGENT_IMPORTANCE,
        description="Camera alert - attention needed",
        duration=1.0,
        leitmotif="Sharp attention grab",
        character="Alert, focused, important",
        orchestration=Orchestration(
            voices=[
                InstrumentVoice(
                    instrument_key="trumpet",
                    articulation="Short Marcato",
                    notes=[
                        (0.0, 77, 0.2, 85),  # F5
                        (0.3, 79, 0.25, 90),  # G5
                    ],
                    pan=0.0,
                    reverb_send=0.25,
                ),
                InstrumentVoice(
                    instrument_key="untuned_percussion",
                    articulation="Snare 1",
                    notes=[(0.0, 38, 0.1, 75)],
                    pan=0.0,
                    reverb_send=0.2,
                ),
            ],
            tempo_bpm=120,
            total_duration=1.0,
            master_volume=0.7,
            room_reverb=0.25,
        ),
        spatial_motion=SpatialMotion.PULSE_FRONT_CENTER,
        tags=["camera", "security", "alert", "urgent"],
    )


def _create_message_received_earcon() -> EarconDefinition:
    """New communication received."""
    return EarconDefinition(
        name="message_received",
        intent=EmotionalIntent.GENTLE_ATTENTION,
        description="New message notification",
        duration=0.8,
        leitmotif="Quick ascending dyad",
        character="Friendly, quick, informative",
        orchestration=Orchestration(
            voices=[
                InstrumentVoice(
                    instrument_key="celeste",
                    articulation="Short Sustained",
                    notes=[
                        (0.0, 76, 0.3, 65),  # E5
                        (0.15, 84, 0.4, 60),  # C6
                    ],
                    pan=0.0,
                    reverb_send=0.4,
                ),
                InstrumentVoice(
                    instrument_key="vibraphone",
                    articulation="Short Hits",
                    notes=[(0.25, 79, 0.4, 50)],  # G5
                    pan=0.0,
                    reverb_send=0.45,
                ),
            ],
            tempo_bpm=120,
            total_duration=0.8,
            master_volume=0.6,
            room_reverb=0.4,
        ),
        spatial_motion=SpatialMotion.BLOOM_FROM_CENTER,
        tags=["message", "communication", "notification"],
    )


def _create_home_empty_earcon() -> EarconDefinition:
    """House settling into quiet - no one home."""
    return EarconDefinition(
        name="home_empty",
        intent=EmotionalIntent.PEACEFUL_DESCENT,
        description="Home is now empty - settling into quiet",
        duration=3.0,
        leitmotif="Fading breath with gentle resolution",
        character="Peaceful, settling, quiet but not lonely",
        orchestration=Orchestration(
            voices=[
                # Descending harp arpeggio - like closing a chapter
                InstrumentVoice(
                    instrument_key="harp",
                    articulation="Close Arpeggios",
                    notes=[
                        (0.0, 72, 0.3, 45),  # C5
                        (0.2, 67, 0.3, 40),  # G4
                        (0.4, 64, 0.3, 35),  # E4
                        (0.6, 60, 0.5, 30),  # C4 - rest
                    ],
                    pan=-0.2,
                    reverb_send=0.5,
                ),
                # Violin harmonics - ethereal shimmer
                InstrumentVoice(
                    instrument_key="violins_1",
                    articulation="Long Harmonics",
                    notes=[
                        (0.3, 79, 2.5, 35),  # G5 harmonic
                    ],
                    cc1_dynamics=[(0.3, 40), (1.5, 25), (2.8, 10)],
                    pan=0.0,
                    reverb_send=0.6,
                ),
                # Gentle horn - warmth remains
                InstrumentVoice(
                    instrument_key="horn",
                    articulation="Legato",
                    notes=[
                        (0.5, 55, 1.8, 30),  # G3 - gentle warmth
                    ],
                    cc1_dynamics=[(0.5, 35), (1.5, 20), (2.3, 10)],
                    pan=0.1,
                    reverb_send=0.55,
                ),
                # Celli foundation - settling
                InstrumentVoice(
                    instrument_key="celli",
                    articulation="Long Sul Tasto",
                    notes=[
                        (0.2, 48, 2.3, 30),  # C3
                    ],
                    cc1_dynamics=[(0.2, 35), (1.5, 20), (2.5, 8)],
                    pan=0.0,
                    reverb_send=0.55,
                ),
                # Subtle celeste sparkle at end
                InstrumentVoice(
                    instrument_key="celeste",
                    articulation="Short Sustained",
                    notes=[
                        (1.5, 84, 0.3, 25),  # C6 - distant twinkle
                    ],
                    pan=0.0,
                    reverb_send=0.6,
                ),
            ],
            tempo_bpm=50,
            total_duration=3.0,
            master_volume=0.45,
            room_reverb=0.6,
        ),
        spatial_motion=SpatialMotion.SETTLE_DOWNWARD,
        tags=["presence", "empty", "quiet", "settling"],
    )


def _create_first_home_earcon() -> EarconDefinition:
    """First person home after being empty."""
    return EarconDefinition(
        name="first_home",
        intent=EmotionalIntent.WARM_WELCOME,
        description="First person arriving to empty home",
        duration=2.0,
        leitmotif="Warmth awakening",
        character="Welcoming, awakening, warm",
        orchestration=Orchestration(
            voices=[
                InstrumentVoice(
                    instrument_key="oboe",
                    articulation="Legato",
                    notes=[
                        (0.2, 60, 0.5, 65),  # C4
                        (0.6, 64, 0.5, 70),  # E4
                        (1.0, 67, 0.6, 75),  # G4
                    ],
                    cc1_dynamics=[(0.2, 55), (0.8, 75), (1.5, 65)],
                    pan=0.0,
                    reverb_send=0.4,
                ),
                InstrumentVoice(
                    instrument_key="violins_1",
                    articulation="Long",
                    notes=[
                        (0.3, 60, 1.4, 55),  # C4
                        (0.3, 64, 1.4, 50),  # E4
                    ],
                    cc1_dynamics=[(0.3, 45), (1.0, 70), (1.7, 55)],
                    pan=0.0,
                    reverb_send=0.45,
                ),
            ],
            tempo_bpm=72,
            total_duration=2.0,
            master_volume=0.65,
            room_reverb=0.45,
        ),
        spatial_motion=SpatialMotion.SWEEP_FROM_DOOR,
        tags=["presence", "first", "welcome", "arrival"],
    )


def _create_oven_preheat_earcon() -> EarconDefinition:
    """Ready-to-cook signal - oven preheated."""
    return EarconDefinition(
        name="oven_preheat",
        intent=EmotionalIntent.GENTLE_ATTENTION,
        description="Oven has finished preheating",
        duration=1.0,
        leitmotif="Warm ready signal",
        character="Warm, ready, inviting",
        orchestration=Orchestration(
            voices=[
                InstrumentVoice(
                    instrument_key="clarinet",
                    articulation="Short Tenuto",
                    notes=[
                        (0.0, 60, 0.25, 65),  # C4
                        (0.25, 64, 0.25, 70),  # E4
                        (0.5, 67, 0.35, 75),  # G4
                    ],
                    pan=0.0,
                    reverb_send=0.3,
                ),
                InstrumentVoice(
                    instrument_key="glockenspiel",
                    articulation="Short Hits",
                    notes=[(0.7, 79, 0.25, 60)],  # G5
                    pan=0.0,
                    reverb_send=0.4,
                ),
            ],
            tempo_bpm=100,
            total_duration=1.0,
            master_volume=0.6,
            room_reverb=0.35,
        ),
        spatial_motion=SpatialMotion.APPROACH_FROM_DISTANCE,
        tags=["appliance", "oven", "kitchen", "ready"],
    )


def _create_dishwasher_complete_earcon() -> EarconDefinition:
    """Clean, fresh resolution - dishwasher done."""
    return EarconDefinition(
        name="dishwasher_complete",
        intent=EmotionalIntent.GENTLE_ATTENTION,
        description="Dishwasher cycle complete",
        duration=1.2,
        leitmotif="Clean resolution",
        character="Fresh, clean, complete",
        orchestration=Orchestration(
            voices=[
                InstrumentVoice(
                    instrument_key="flute",
                    articulation="Legato",
                    notes=[
                        (0.0, 76, 0.4, 60),  # E5
                        (0.35, 79, 0.5, 65),  # G5
                    ],
                    cc1_dynamics=[(0.0, 55), (0.5, 70), (1.0, 55)],
                    pan=0.0,
                    reverb_send=0.35,
                ),
                InstrumentVoice(
                    instrument_key="celeste",
                    articulation="Short Sustained",
                    notes=[(0.6, 84, 0.4, 50)],  # C6
                    pan=0.0,
                    reverb_send=0.45,
                ),
            ],
            tempo_bpm=90,
            total_duration=1.2,
            master_volume=0.55,
            room_reverb=0.4,
        ),
        spatial_motion=SpatialMotion.APPROACH_FROM_DISTANCE,
        tags=["appliance", "dishwasher", "kitchen", "complete"],
    )


def _create_dryer_complete_earcon() -> EarconDefinition:
    """Warm, soft completion - dryer done."""
    return EarconDefinition(
        name="dryer_complete",
        intent=EmotionalIntent.GENTLE_ATTENTION,
        description="Dryer cycle complete",
        duration=1.2,
        leitmotif="Soft, warm resolution",
        character="Warm, soft, cozy",
        orchestration=Orchestration(
            voices=[
                InstrumentVoice(
                    instrument_key="clarinet",
                    articulation="Legato",
                    notes=[
                        (0.0, 60, 0.5, 55),  # C4
                        (0.4, 64, 0.6, 60),  # E4
                    ],
                    cc1_dynamics=[(0.0, 50), (0.5, 65), (1.0, 50)],
                    pan=0.0,
                    reverb_send=0.4,
                ),
                InstrumentVoice(
                    instrument_key="vibraphone",
                    articulation="Short Hits",
                    notes=[(0.7, 67, 0.4, 50)],  # G4
                    pan=0.0,
                    reverb_send=0.45,
                ),
            ],
            tempo_bpm=80,
            total_duration=1.2,
            master_volume=0.55,
            room_reverb=0.4,
        ),
        spatial_motion=SpatialMotion.APPROACH_FROM_DISTANCE,
        tags=["appliance", "dryer", "laundry", "complete"],
    )


# =============================================================================
# Registry — All Earcons
# =============================================================================


def _build_earcon_registry() -> dict[str, EarconDefinition]:
    """Build the complete earcon registry.

    This creates all earcon definitions on demand.
    Contains 36 virtuoso orchestral earcons across 3 tiers:
    - Tier 1: 14 Core earcons (essential notifications)
    - Tier 2: 22 Extended earcons (full soundscape)
    """
    builders = [
        # Tier 1: Core (14) — Essential notifications
        _create_notification_earcon,
        _create_success_earcon,
        _create_error_earcon,
        _create_alert_earcon,
        _create_arrival_earcon,
        _create_departure_earcon,
        _create_celebration_earcon,
        _create_settling_earcon,
        _create_awakening_earcon,
        _create_cinematic_earcon,
        _create_focus_earcon,
        _create_security_arm_earcon,
        _create_package_earcon,
        _create_meeting_soon_earcon,
        # Tier 2: Extended — Full soundscape
        # Presence and movement
        _create_room_enter_earcon,
        _create_home_empty_earcon,
        _create_first_home_earcon,
        # Time of day
        _create_morning_sequence_earcon,
        _create_evening_transition_earcon,
        _create_midnight_earcon,
        # Appliances
        _create_washer_complete_earcon,
        _create_dryer_complete_earcon,
        _create_dishwasher_complete_earcon,
        _create_oven_preheat_earcon,
        _create_coffee_ready_earcon,
        # Security
        _create_door_open_earcon,
        _create_door_close_earcon,
        _create_lock_engaged_earcon,
        _create_motion_detected_earcon,
        _create_camera_alert_earcon,
        # Communication
        _create_voice_acknowledge_earcon,
        _create_voice_complete_earcon,
        _create_message_received_earcon,
        # Weather
        _create_storm_approaching_earcon,
        _create_rain_starting_earcon,
    ]

    registry = {}
    for builder in builders:
        earcon = builder()
        registry[earcon.name] = earcon
        logger.debug(f"Registered earcon: {earcon.name}")

    return registry


# Lazy initialization
_EARCON_REGISTRY: dict[str, EarconDefinition] | None = None


def get_earcon_registry() -> dict[str, EarconDefinition]:
    """Get the earcon registry, building it if needed."""
    global _EARCON_REGISTRY
    if _EARCON_REGISTRY is None:
        _EARCON_REGISTRY = _build_earcon_registry()
        logger.info(f"Built earcon registry with {len(_EARCON_REGISTRY)} earcons")
    return _EARCON_REGISTRY


def get_earcon(name: str) -> EarconDefinition | None:
    """Get an earcon definition by name."""
    return get_earcon_registry().get(name)


def list_earcons() -> list[str]:
    """List all registered earcon names."""
    return list(get_earcon_registry().keys())


def get_earcons_by_tag(tag: str) -> list[EarconDefinition]:
    """Get all earcons with a specific tag."""
    return [e for e in get_earcon_registry().values() if tag in e.tags]


def get_earcons_by_intent(intent: EmotionalIntent) -> list[EarconDefinition]:
    """Get all earcons with a specific emotional intent."""
    return [e for e in get_earcon_registry().values() if e.intent == intent]


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Trajectory generators
    "TRAJECTORY_GENERATORS",
    # Core types
    "EarconDefinition",
    "EmotionalIntent",
    "InstrumentVoice",
    "Orchestration",
    "SpatialMotion",
    "SpatialTrajectory",
    # Registry functions
    "get_earcon",
    "get_earcon_registry",
    "get_earcons_by_intent",
    "get_earcons_by_tag",
    "list_earcons",
]
