"""Virtuoso Orchestra Visualizer — A Living, Breathing 3D Experience.

This is not a visualizer. This is a TRANSLATION.

Music is invisible vibration made audible.
This code makes it VISIBLE.

Each instrument has a SOUL, a CHARACTER, a WAY OF BEING.
The violin doesn't just make sound — it SINGS, CRIES, LAUGHS.
The timpani doesn't just make noise — it is THUNDER, HEARTBEAT, DOOM.

This visualizer knows the instruments. Loves them.
Places them in a REAL Carnegie Hall.
Makes them BREATHE with the music.

Carnegie Hall (Isaac Stern Auditorium):
- Stage: 21.3m wide × 14.6m deep
- Hall: 32.6m wide × 39.6m long × 25m tall
- 2,804 seats across 5 levels
- "Shoebox" acoustic design for optimal sound

The Orchestra breathes. The Hall breathes.
And when you watch this — YOU breathe with it.

Colony: Full Fano Collaboration (All Seven)
Created: January 4, 2026
"""

from __future__ import annotations

import logging
import math
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


# =============================================================================
# THE SOUL OF EACH INSTRUMENT
# =============================================================================


class InstrumentSoul(Enum):
    """The emotional character of each instrument family.

    These are not arbitrary categories — they are TRUTHS
    learned over centuries of orchestral writing.
    """

    # STRINGS — The Heart
    VIOLIN_I = "singer"  # The soprano. Brilliant, soaring, emotional.
    VIOLIN_II = "harmony"  # The alto. Supporting, weaving, responding.
    VIOLA = "poet"  # The introspective voice. Darker, mysterious.
    CELLO = "voice"  # Closest to human voice. Noble, warm, singing.
    BASS = "foundation"  # The earth. Grounding, supporting, rumbling.

    # WOODWINDS — The Breath
    FLUTE = "bird"  # Pure, crystalline, ethereal. Can be playful or haunting.
    OBOE = "shepherd"  # Plaintive, pastoral, ancient. Cuts through.
    CLARINET = "chameleon"  # Warm to bright. Jazz heritage. Flexible.
    BASSOON = "grandfather"  # Dignified wit. Noble in legato, comic in staccato.

    # BRASS — The Power
    HORN = "golden"  # Romantic, heroic, velvet to thunder. THE bridge.
    TRUMPET = "herald"  # Fanfare, ceremony, brilliance. Piercing light.
    TROMBONE = "noble"  # Solemn, powerful, chorale-like. Can terrify.
    TUBA = "giant"  # Foundation of brass. Deep power.

    # PERCUSSION — The Pulse
    TIMPANI = "thunder"  # Drama, tension, heartbeat. The orchestra's pulse.
    CYMBALS = "lightning"  # Explosive flash. Climax marker.
    TRIANGLE = "shimmer"  # Delicate sparkle. Magic dust.
    BASS_DRUM = "earthquake"  # The deepest boom. Earth-shaking.

    # SPECIAL
    HARP = "angel"  # Celestial, flowing, like water or starlight.
    CELESTA = "music_box"  # Ethereal, innocent, magical.
    PIANO = "orchestra"  # Contains all colors. The complete voice.


@dataclass
class InstrumentVisualIdentity:
    """Visual identity for an instrument — how it LOOKS when it plays.

    This is not arbitrary styling — each visual element reflects
    the instrument's acoustic and emotional character.
    """

    # Core color (RGB 0-1) — reflects timbre
    color_base: tuple[float, float, float]
    color_excited: tuple[float, float, float]  # When playing fortissimo

    # Visual behavior
    visual_type: str  # "ribbon", "particle", "orb", "ring", "wave", "string"
    breathe_rate: float  # How fast it "breathes" with sustain
    attack_response: float  # How sharply it responds to note attacks (0-1)
    decay_rate: float  # How quickly visual energy fades

    # Spatial extent
    visual_radius: float  # How far the visual spreads
    height_range: tuple[float, float]  # Vertical extent above seat position

    # Special behaviors
    trails: bool = False  # Leaves visual trails
    particles: bool = False  # Emits particles when playing
    shimmer: bool = False  # Has surface shimmer
    glow_halo: bool = False  # Glows with surrounding halo


# Instrument visual identities — CAREFULLY tuned to each instrument's character
INSTRUMENT_VISUALS: dict[InstrumentSoul, InstrumentVisualIdentity] = {
    # STRINGS — Warm, organic, flowing
    InstrumentSoul.VIOLIN_I: InstrumentVisualIdentity(
        color_base=(0.95, 0.45, 0.25),  # Warm amber-orange (wood, rosin)
        color_excited=(1.0, 0.65, 0.35),  # Brighter, more golden
        visual_type="ribbon",
        breathe_rate=1.2,
        attack_response=0.7,
        decay_rate=0.4,
        visual_radius=0.8,
        height_range=(0.3, 1.5),
        trails=True,
        shimmer=True,
    ),
    InstrumentSoul.VIOLIN_II: InstrumentVisualIdentity(
        color_base=(0.88, 0.42, 0.22),
        color_excited=(0.95, 0.55, 0.30),
        visual_type="ribbon",
        breathe_rate=1.1,
        attack_response=0.65,
        decay_rate=0.4,
        visual_radius=0.75,
        height_range=(0.25, 1.4),
        trails=True,
        shimmer=True,
    ),
    InstrumentSoul.VIOLA: InstrumentVisualIdentity(
        color_base=(0.65, 0.35, 0.45),  # Darker, more purple-brown
        color_excited=(0.75, 0.45, 0.55),
        visual_type="ribbon",
        breathe_rate=0.9,
        attack_response=0.6,
        decay_rate=0.35,
        visual_radius=0.85,
        height_range=(0.2, 1.3),
        trails=True,
    ),
    InstrumentSoul.CELLO: InstrumentVisualIdentity(
        color_base=(0.72, 0.28, 0.18),  # Deep amber-red
        color_excited=(0.85, 0.40, 0.25),
        visual_type="wave",
        breathe_rate=0.7,
        attack_response=0.5,
        decay_rate=0.3,
        visual_radius=1.0,
        height_range=(0.1, 1.8),
        trails=True,
        glow_halo=True,
    ),
    InstrumentSoul.BASS: InstrumentVisualIdentity(
        color_base=(0.45, 0.22, 0.15),  # Dark wood brown
        color_excited=(0.55, 0.30, 0.20),
        visual_type="wave",
        breathe_rate=0.5,
        attack_response=0.4,
        decay_rate=0.25,
        visual_radius=1.2,
        height_range=(0.0, 2.2),
        glow_halo=True,
    ),
    # WOODWINDS — Ethereal, breath-driven, floating
    InstrumentSoul.FLUTE: InstrumentVisualIdentity(
        color_base=(0.70, 0.85, 0.95),  # Silver-blue (metal, air)
        color_excited=(0.85, 0.95, 1.0),
        visual_type="particle",
        breathe_rate=1.5,
        attack_response=0.8,
        decay_rate=0.6,
        visual_radius=0.6,
        height_range=(0.5, 2.5),
        particles=True,
        shimmer=True,
    ),
    InstrumentSoul.OBOE: InstrumentVisualIdentity(
        color_base=(0.55, 0.70, 0.45),  # Pastoral green-brown
        color_excited=(0.65, 0.80, 0.55),
        visual_type="particle",
        breathe_rate=1.0,
        attack_response=0.75,
        decay_rate=0.5,
        visual_radius=0.5,
        height_range=(0.4, 2.0),
        particles=True,
    ),
    InstrumentSoul.CLARINET: InstrumentVisualIdentity(
        color_base=(0.30, 0.25, 0.35),  # Dark wood, ebony
        color_excited=(0.45, 0.40, 0.50),
        visual_type="particle",
        breathe_rate=1.1,
        attack_response=0.7,
        decay_rate=0.55,
        visual_radius=0.55,
        height_range=(0.3, 2.2),
        particles=True,
    ),
    InstrumentSoul.BASSOON: InstrumentVisualIdentity(
        color_base=(0.50, 0.35, 0.25),  # Rich mahogany
        color_excited=(0.60, 0.45, 0.35),
        visual_type="particle",
        breathe_rate=0.8,
        attack_response=0.6,
        decay_rate=0.45,
        visual_radius=0.7,
        height_range=(0.2, 2.5),
        particles=True,
    ),
    # BRASS — Golden, powerful, radiating
    InstrumentSoul.HORN: InstrumentVisualIdentity(
        color_base=(0.90, 0.72, 0.25),  # GOLDEN — the archetypal brass color
        color_excited=(1.0, 0.85, 0.40),
        visual_type="orb",
        breathe_rate=0.8,
        attack_response=0.6,
        decay_rate=0.4,
        visual_radius=1.0,
        height_range=(0.3, 1.8),
        glow_halo=True,
        shimmer=True,
    ),
    InstrumentSoul.TRUMPET: InstrumentVisualIdentity(
        color_base=(0.95, 0.80, 0.30),  # Bright brass gold
        color_excited=(1.0, 0.90, 0.50),
        visual_type="orb",
        breathe_rate=1.3,
        attack_response=0.9,
        decay_rate=0.5,
        visual_radius=0.8,
        height_range=(0.4, 2.0),
        trails=True,
        glow_halo=True,
    ),
    InstrumentSoul.TROMBONE: InstrumentVisualIdentity(
        color_base=(0.85, 0.65, 0.20),  # Darker brass
        color_excited=(0.95, 0.78, 0.35),
        visual_type="orb",
        breathe_rate=0.7,
        attack_response=0.65,
        decay_rate=0.35,
        visual_radius=1.1,
        height_range=(0.2, 1.6),
        glow_halo=True,
    ),
    InstrumentSoul.TUBA: InstrumentVisualIdentity(
        color_base=(0.70, 0.55, 0.18),  # Deep brass
        color_excited=(0.80, 0.68, 0.28),
        visual_type="orb",
        breathe_rate=0.5,
        attack_response=0.5,
        decay_rate=0.3,
        visual_radius=1.4,
        height_range=(0.0, 2.0),
        glow_halo=True,
    ),
    # PERCUSSION — Impact, pulse, drama
    InstrumentSoul.TIMPANI: InstrumentVisualIdentity(
        color_base=(0.40, 0.35, 0.50),  # Dark copper with purple
        color_excited=(0.60, 0.50, 0.70),
        visual_type="ring",
        breathe_rate=0.3,
        attack_response=1.0,  # INSTANT response
        decay_rate=0.6,
        visual_radius=2.0,
        height_range=(0.0, 0.5),
        trails=True,
    ),
    InstrumentSoul.CYMBALS: InstrumentVisualIdentity(
        color_base=(0.90, 0.88, 0.75),  # Bright bronze
        color_excited=(1.0, 1.0, 0.90),
        visual_type="ring",
        breathe_rate=0.1,
        attack_response=1.0,
        decay_rate=0.8,
        visual_radius=3.0,
        height_range=(0.0, 3.0),
        shimmer=True,
        particles=True,
    ),
    InstrumentSoul.TRIANGLE: InstrumentVisualIdentity(
        color_base=(0.85, 0.90, 0.95),  # Silver sparkle
        color_excited=(1.0, 1.0, 1.0),
        visual_type="particle",
        breathe_rate=0.2,
        attack_response=0.95,
        decay_rate=0.7,
        visual_radius=0.5,
        height_range=(0.5, 2.5),
        shimmer=True,
        particles=True,
    ),
    InstrumentSoul.BASS_DRUM: InstrumentVisualIdentity(
        color_base=(0.25, 0.20, 0.18),  # Deep, dark
        color_excited=(0.40, 0.35, 0.30),
        visual_type="ring",
        breathe_rate=0.2,
        attack_response=1.0,
        decay_rate=0.4,
        visual_radius=4.0,  # Huge impact
        height_range=(0.0, 0.3),
    ),
    # SPECIAL — Unique characters
    InstrumentSoul.HARP: InstrumentVisualIdentity(
        color_base=(0.60, 0.50, 0.75),  # Ethereal purple-gold
        color_excited=(0.75, 0.65, 0.90),
        visual_type="string",
        breathe_rate=1.0,
        attack_response=0.85,
        decay_rate=0.6,
        visual_radius=0.8,
        height_range=(0.5, 3.0),
        shimmer=True,
        trails=True,
    ),
    InstrumentSoul.CELESTA: InstrumentVisualIdentity(
        color_base=(0.85, 0.85, 0.95),  # Icy, magical
        color_excited=(0.95, 0.95, 1.0),
        visual_type="particle",
        breathe_rate=1.2,
        attack_response=0.9,
        decay_rate=0.65,
        visual_radius=0.6,
        height_range=(0.6, 2.8),
        shimmer=True,
        particles=True,
    ),
    InstrumentSoul.PIANO: InstrumentVisualIdentity(
        color_base=(0.15, 0.15, 0.18),  # Grand piano black
        color_excited=(0.30, 0.30, 0.35),
        visual_type="wave",
        breathe_rate=0.9,
        attack_response=0.85,
        decay_rate=0.5,
        visual_radius=1.5,
        height_range=(0.2, 2.0),
        shimmer=True,
        glow_halo=True,
    ),
}


# =============================================================================
# CARNEGIE HALL — The Sacred Space
# =============================================================================


@dataclass
class CarnegieHall:
    """Carnegie Hall (Isaac Stern Auditorium) dimensions and acoustics.

    This is THE concert hall. Opened 1891. "Shoebox" design.
    The gold standard for orchestral acoustics.

    All dimensions in meters.
    Origin (0,0,0) = center of stage at floor level.
    +X = stage left (audience right)
    +Y = upstage (toward back wall)
    +Z = up
    """

    # Stage dimensions
    stage_width: float = 21.3
    stage_depth: float = 14.6
    stage_height_from_floor: float = 1.2  # Raised platform

    # Hall dimensions
    hall_width: float = 32.6
    hall_length: float = 39.6
    hall_height: float = 25.0

    # Acoustic properties
    reverb_time_t60: float = 1.9  # Seconds — rich but clear
    early_decay_time: float = 1.4  # EDT for clarity
    warmth: float = 0.95  # Bass ratio
    brilliance: float = 0.92  # High frequency preservation

    # Seat count
    total_seats: int = 2804

    # Key positions (relative to stage center)
    conductor_position: tuple[float, float, float] = (0.0, 2.0, 0.0)

    # Balcony levels (height above stage floor)
    parquet_height: float = 0.0  # Main floor
    first_tier_height: float = 4.5  # Dress circle
    second_tier_height: float = 8.5  # Balcony
    top_tier_height: float = 12.0  # Gallery

    @property
    def stage_bounds(self) -> tuple[tuple[float, float], tuple[float, float]]:
        """Stage bounds as ((x_min, x_max), (y_min, y_max))."""
        return (
            (-self.stage_width / 2, self.stage_width / 2),
            (0, self.stage_depth),
        )


CARNEGIE = CarnegieHall()


# =============================================================================
# ORCHESTRA SEATING — Where Each Voice Sits
# =============================================================================


@dataclass
class OrchestraSeat:
    """Position of an instrument section on the Carnegie Hall stage.

    Coordinates are relative to stage center (conductor position).
    Standard "American" seating with violins on the left.
    """

    soul: InstrumentSoul

    # Position (meters from conductor)
    x: float  # Stage left (+) to stage right (-)
    y: float  # Distance from front of stage
    z: float  # Height (for risers)

    # Section size
    width: float  # Lateral spread of section
    depth: float  # Front-to-back spread
    player_count: int

    # Riser tier (0 = floor, 1 = first riser, etc.)
    tier: int = 0


# Standard symphony orchestra layout at Carnegie Hall
# Based on typical 100-piece orchestra configuration
ORCHESTRA_LAYOUT: list[OrchestraSeat] = [
    # STRINGS — The Foundation (front, floor level)
    OrchestraSeat(
        InstrumentSoul.VIOLIN_I,
        x=-5.0,
        y=3.0,
        z=0.0,
        width=4.0,
        depth=3.0,
        player_count=16,
        tier=0,
    ),
    OrchestraSeat(
        InstrumentSoul.VIOLIN_II,
        x=-2.0,
        y=5.0,
        z=0.0,
        width=3.5,
        depth=2.5,
        player_count=14,
        tier=0,
    ),
    OrchestraSeat(
        InstrumentSoul.VIOLA,
        x=2.0,
        y=4.5,
        z=0.0,
        width=3.0,
        depth=2.5,
        player_count=12,
        tier=0,
    ),
    OrchestraSeat(
        InstrumentSoul.CELLO,
        x=4.5,
        y=3.5,
        z=0.0,
        width=3.0,
        depth=2.5,
        player_count=10,
        tier=0,
    ),
    OrchestraSeat(
        InstrumentSoul.BASS,
        x=6.0,
        y=6.0,
        z=0.3,
        width=2.5,
        depth=2.0,
        player_count=8,
        tier=1,
    ),
    # WOODWINDS — First Riser (behind strings)
    OrchestraSeat(
        InstrumentSoul.FLUTE,
        x=-2.5,
        y=7.5,
        z=0.6,
        width=2.0,
        depth=1.0,
        player_count=3,
        tier=1,
    ),
    OrchestraSeat(
        InstrumentSoul.OBOE,
        x=-0.5,
        y=7.5,
        z=0.6,
        width=1.5,
        depth=1.0,
        player_count=3,
        tier=1,
    ),
    OrchestraSeat(
        InstrumentSoul.CLARINET,
        x=1.5,
        y=7.5,
        z=0.6,
        width=1.5,
        depth=1.0,
        player_count=3,
        tier=1,
    ),
    OrchestraSeat(
        InstrumentSoul.BASSOON,
        x=3.5,
        y=7.5,
        z=0.6,
        width=1.5,
        depth=1.0,
        player_count=3,
        tier=1,
    ),
    # BRASS — Second Riser (powerful projection)
    OrchestraSeat(
        InstrumentSoul.HORN,
        x=-3.0,
        y=9.5,
        z=1.0,
        width=3.0,
        depth=1.0,
        player_count=4,
        tier=2,
    ),
    OrchestraSeat(
        InstrumentSoul.TRUMPET,
        x=0.5,
        y=9.5,
        z=1.0,
        width=2.0,
        depth=1.0,
        player_count=3,
        tier=2,
    ),
    OrchestraSeat(
        InstrumentSoul.TROMBONE,
        x=3.0,
        y=9.5,
        z=1.0,
        width=2.5,
        depth=1.0,
        player_count=3,
        tier=2,
    ),
    OrchestraSeat(
        InstrumentSoul.TUBA,
        x=5.0,
        y=9.5,
        z=1.0,
        width=1.5,
        depth=1.0,
        player_count=1,
        tier=2,
    ),
    # PERCUSSION — Back Riser (commanding presence)
    OrchestraSeat(
        InstrumentSoul.TIMPANI,
        x=-5.0,
        y=11.5,
        z=1.4,
        width=3.0,
        depth=1.5,
        player_count=1,
        tier=3,
    ),
    OrchestraSeat(
        InstrumentSoul.BASS_DRUM,
        x=-2.0,
        y=11.5,
        z=1.4,
        width=2.0,
        depth=1.0,
        player_count=1,
        tier=3,
    ),
    OrchestraSeat(
        InstrumentSoul.CYMBALS,
        x=0.0,
        y=11.5,
        z=1.4,
        width=1.5,
        depth=1.0,
        player_count=1,
        tier=3,
    ),
    OrchestraSeat(
        InstrumentSoul.TRIANGLE,
        x=2.0,
        y=11.5,
        z=1.4,
        width=0.5,
        depth=0.5,
        player_count=1,
        tier=3,
    ),
    # SPECIAL — Variable positions
    OrchestraSeat(
        InstrumentSoul.HARP,
        x=-7.0,
        y=5.0,
        z=0.0,
        width=1.5,
        depth=1.5,
        player_count=1,
        tier=0,
    ),
    OrchestraSeat(
        InstrumentSoul.CELESTA,
        x=7.0,
        y=5.0,
        z=0.0,
        width=1.0,
        depth=1.0,
        player_count=1,
        tier=0,
    ),
    OrchestraSeat(
        InstrumentSoul.PIANO,
        x=-8.0,
        y=3.0,
        z=0.0,
        width=2.5,
        depth=1.5,
        player_count=1,
        tier=0,
    ),
]


# =============================================================================
# AUDIO ANALYSIS — Frequency to Instrument Mapping
# =============================================================================


@dataclass
class FrequencyProfile:
    """Frequency characteristics for identifying an instrument's activity.

    Each instrument has a fundamental frequency range and characteristic
    overtone patterns. We use these to estimate activity from FFT data.
    """

    fundamental_low: float  # Lowest fundamental frequency (Hz)
    fundamental_high: float  # Highest fundamental frequency (Hz)
    formant_peaks: list[float]  # Characteristic resonance frequencies
    brightness: float  # High-frequency content (0-1)


INSTRUMENT_FREQUENCIES: dict[InstrumentSoul, FrequencyProfile] = {
    # STRINGS
    InstrumentSoul.VIOLIN_I: FrequencyProfile(196, 3520, [1000, 2500, 4000], 0.8),
    InstrumentSoul.VIOLIN_II: FrequencyProfile(196, 3520, [1000, 2500, 4000], 0.75),
    InstrumentSoul.VIOLA: FrequencyProfile(130, 2000, [700, 1800, 3000], 0.6),
    InstrumentSoul.CELLO: FrequencyProfile(65, 1000, [300, 800, 1500], 0.5),
    InstrumentSoul.BASS: FrequencyProfile(41, 350, [100, 250, 500], 0.3),
    # WOODWINDS
    InstrumentSoul.FLUTE: FrequencyProfile(262, 4186, [600, 1200, 2400], 0.9),
    InstrumentSoul.OBOE: FrequencyProfile(233, 1400, [500, 1000, 2000], 0.7),
    InstrumentSoul.CLARINET: FrequencyProfile(147, 2000, [400, 1200, 2500], 0.65),
    InstrumentSoul.BASSOON: FrequencyProfile(58, 700, [200, 500, 900], 0.4),
    # BRASS
    InstrumentSoul.HORN: FrequencyProfile(87, 1200, [300, 800, 1400], 0.55),
    InstrumentSoul.TRUMPET: FrequencyProfile(165, 1400, [500, 1000, 2000], 0.75),
    InstrumentSoul.TROMBONE: FrequencyProfile(58, 700, [200, 500, 1000], 0.5),
    InstrumentSoul.TUBA: FrequencyProfile(29, 350, [80, 200, 400], 0.25),
    # PERCUSSION
    InstrumentSoul.TIMPANI: FrequencyProfile(65, 262, [100, 200, 400], 0.3),
    InstrumentSoul.BASS_DRUM: FrequencyProfile(30, 100, [50, 80], 0.1),
    InstrumentSoul.CYMBALS: FrequencyProfile(300, 16000, [2000, 5000, 10000], 0.95),
    InstrumentSoul.TRIANGLE: FrequencyProfile(1000, 8000, [3000, 6000], 0.9),
    # SPECIAL
    InstrumentSoul.HARP: FrequencyProfile(32, 3136, [200, 800, 1600], 0.7),
    InstrumentSoul.CELESTA: FrequencyProfile(262, 4186, [1000, 2000, 4000], 0.85),
    InstrumentSoul.PIANO: FrequencyProfile(27, 4186, [200, 800, 2000], 0.7),
}


class VirtuosoAudioAnalyzer:
    """Advanced audio analyzer that understands INSTRUMENTS, not just frequencies.

    This analyzer doesn't just do FFT — it LISTENS.
    It knows what a violin sounds like. It knows when the timpani thunders.
    It feels the breath of the woodwinds.
    """

    def __init__(
        self,
        sample_rate: int = 48000,
        fft_size: int = 4096,  # Larger for better frequency resolution
        hop_size: int = 512,
    ) -> None:
        self.sample_rate = sample_rate
        self.fft_size = fft_size
        self.hop_size = hop_size

        # Frequency bins
        self.freq_bins = np.fft.rfftfreq(fft_size, 1 / sample_rate)

        # Pre-compute instrument frequency masks
        self._instrument_masks: dict[InstrumentSoul, np.ndarray] = {}
        self._build_instrument_masks()

        # Temporal smoothing state
        self._smoothed_energies: dict[InstrumentSoul, float] = dict.fromkeys(InstrumentSoul, 0.0)

        # Onset detection state
        self._prev_energies: dict[InstrumentSoul, float] = dict.fromkeys(InstrumentSoul, 0.0)

        # Window
        self._window = np.hanning(fft_size)

        logger.info(f"Virtuoso analyzer: {sample_rate}Hz, FFT={fft_size}")

    def _build_instrument_masks(self) -> None:
        """Build frequency masks for each instrument based on their profiles."""
        for soul, profile in INSTRUMENT_FREQUENCIES.items():
            mask = np.zeros(len(self.freq_bins))

            # Fundamental range (strongest weight)
            fund_low_idx = np.searchsorted(self.freq_bins, profile.fundamental_low)
            fund_high_idx = np.searchsorted(self.freq_bins, profile.fundamental_high)
            mask[fund_low_idx:fund_high_idx] = 1.0

            # Formant peaks (add emphasis)
            for peak in profile.formant_peaks:
                peak_idx = np.searchsorted(self.freq_bins, peak)
                # Gaussian around peak
                sigma = 0.1 * peak / self.sample_rate * self.fft_size
                for i in range(len(mask)):
                    mask[i] += 0.3 * np.exp(-((i - peak_idx) ** 2) / (2 * sigma**2))

            # Apply brightness scaling to high frequencies
            brightness_freq = 2000  # Hz
            brightness_idx = np.searchsorted(self.freq_bins, brightness_freq)
            mask[brightness_idx:] *= profile.brightness

            # Normalize
            if mask.max() > 0:
                mask /= mask.max()

            self._instrument_masks[soul] = mask

    def analyze_frame(
        self,
        audio_frame: np.ndarray,
        timestamp: float,
    ) -> dict[InstrumentSoul, float]:
        """Analyze audio frame and return energy per instrument.

        Returns:
            Dict mapping each InstrumentSoul to its estimated energy (0-1)
        """
        # Ensure correct length
        if len(audio_frame) < self.fft_size:
            audio_frame = np.pad(audio_frame, (0, self.fft_size - len(audio_frame)))
        elif len(audio_frame) > self.fft_size:
            audio_frame = audio_frame[: self.fft_size]

        # FFT
        windowed = audio_frame * self._window
        spectrum = np.abs(np.fft.rfft(windowed))

        # Normalize spectrum
        spectrum_max = spectrum.max()
        spectrum_norm = spectrum / spectrum_max if spectrum_max > 0 else spectrum

        # Estimate energy for each instrument
        energies: dict[InstrumentSoul, float] = {}

        for soul, mask in self._instrument_masks.items():
            # Weighted energy
            raw_energy = np.sum(spectrum_norm * mask) / np.sum(mask)

            # Get visual identity for smoothing parameters
            visual = INSTRUMENT_VISUALS.get(soul)
            smoothing = 0.3 if visual is None else (1 - visual.attack_response) * 0.5

            # Temporal smoothing
            smoothed = self._smoothed_energies[soul] * smoothing + raw_energy * (1 - smoothing)
            self._smoothed_energies[soul] = smoothed

            energies[soul] = smoothed

        return energies

    def detect_onsets(
        self,
        energies: dict[InstrumentSoul, float],
    ) -> dict[InstrumentSoul, bool]:
        """Detect note onsets (attacks) for each instrument."""
        onsets: dict[InstrumentSoul, bool] = {}

        for soul, energy in energies.items():
            prev = self._prev_energies.get(soul, 0.0)

            # Onset = significant energy increase
            visual = INSTRUMENT_VISUALS.get(soul)
            threshold = 0.2 if visual is None else visual.attack_response * 0.3

            onset = (energy - prev) > threshold
            onsets[soul] = onset
            self._prev_energies[soul] = energy

        return onsets


# =============================================================================
# VISUALIZATION GENERATOR — The Translation
# =============================================================================


@dataclass
class VisualManifestation:
    """A single visual element in the scene."""

    # Identity
    instrument: InstrumentSoul
    element_id: int

    # Transform
    position: tuple[float, float, float]  # World position
    scale: tuple[float, float, float]
    rotation: tuple[float, float, float]  # Euler angles

    # Appearance
    color: tuple[float, float, float]  # RGB 0-1
    opacity: float
    emissive: float  # Glow intensity

    # Mesh type
    mesh_type: str  # "sphere", "ribbon", "ring", "particles", "trail"

    # Animation state
    animation_phase: float
    energy: float  # Current energy driving this element
    is_onset: bool  # True if currently experiencing an onset


@dataclass
class VirtuosoFrame:
    """A complete frame of the visualization."""

    timestamp: float

    # Visual elements
    manifestations: list[VisualManifestation]

    # Camera (orbits the orchestra)
    camera_position: tuple[float, float, float]
    camera_lookat: tuple[float, float, float]
    camera_fov: float

    # Environment
    ambient_color: tuple[float, float, float]
    ambient_intensity: float
    hall_brightness: float  # Overall brightness of Carnegie Hall

    # Post-processing hints
    bloom_intensity: float
    fog_density: float


class VirtuosoVisualizationGenerator:
    """Generates the visual manifestation of music.

    This is not rendering — this is TRANSLATION.

    Music → Visual Language:
    - Sustained notes → Breathing, flowing forms
    - Attack/onset → Flash, expansion, birth
    - Decay → Fading, falling, release
    - Dynamics → Brightness, size, presence
    - Pitch → Height, shimmer rate
    - Timbre → Color, texture
    """

    def __init__(self) -> None:
        self._time = 0.0
        self._element_counter = 0

        # Per-instrument animation state
        self._phases: dict[InstrumentSoul, float] = dict.fromkeys(InstrumentSoul, 0.0)
        self._onset_flash: dict[InstrumentSoul, float] = dict.fromkeys(InstrumentSoul, 0.0)

    def generate_frame(
        self,
        energies: dict[InstrumentSoul, float],
        onsets: dict[InstrumentSoul, bool],
        timestamp: float,
        dt: float,
    ) -> VirtuosoFrame:
        """Generate a visualization frame from audio analysis.

        Args:
            energies: Energy level per instrument (0-1)
            onsets: Onset detection per instrument
            timestamp: Audio timestamp in seconds
            dt: Time since last frame

        Returns:
            VirtuosoFrame with all visual elements
        """
        self._time = timestamp

        manifestations: list[VisualManifestation] = []

        # Generate visuals for each instrument section
        for seat in ORCHESTRA_LAYOUT:
            soul = seat.soul
            energy = energies.get(soul, 0.0)
            onset = onsets.get(soul, False)
            visual = INSTRUMENT_VISUALS.get(soul)

            if visual is None:
                continue

            # Update animation phase
            self._phases[soul] += dt * visual.breathe_rate * (0.5 + energy)

            # Update onset flash
            if onset:
                self._onset_flash[soul] = 1.0
            else:
                self._onset_flash[soul] *= 1 - visual.decay_rate * dt * 10

            # Generate manifestations based on visual type
            elements = self._generate_instrument_visuals(
                seat,
                visual,
                energy,
                onset,
                self._phases[soul],
                self._onset_flash[soul],
            )
            manifestations.extend(elements)

        # Calculate overall energy for camera/environment
        total_energy = sum(energies.values()) / len(energies) if energies else 0

        # Camera slowly orbits, with energy affecting distance
        orbit_angle = timestamp * 0.05  # Slow orbit
        cam_distance = 18 - total_energy * 3  # Closer when louder
        cam_height = 8 + total_energy * 2  # Higher when louder

        camera_position = (
            cam_distance * math.sin(orbit_angle),
            -5 + cam_distance * math.cos(orbit_angle),  # Audience perspective
            cam_height,
        )
        camera_lookat = (0.0, 5.0, 1.5)  # Look at center of orchestra

        # Environment responds to music
        ambient_intensity = 0.15 + total_energy * 0.1
        bloom = 0.2 + total_energy * 0.3

        return VirtuosoFrame(
            timestamp=timestamp,
            manifestations=manifestations,
            camera_position=camera_position,
            camera_lookat=camera_lookat,
            camera_fov=45.0,
            ambient_color=(0.8, 0.85, 1.0),  # Warm concert hall
            ambient_intensity=ambient_intensity,
            hall_brightness=0.4 + total_energy * 0.2,
            bloom_intensity=bloom,
            fog_density=0.02,
        )

    def _generate_instrument_visuals(
        self,
        seat: OrchestraSeat,
        visual: InstrumentVisualIdentity,
        energy: float,
        onset: bool,
        phase: float,
        flash: float,
    ) -> list[VisualManifestation]:
        """Generate visual manifestations for one instrument section."""
        elements: list[VisualManifestation] = []

        # Color interpolates between base and excited based on energy
        color = tuple(
            b + (e - b) * energy
            for b, e in zip(visual.color_base, visual.color_excited, strict=False)
        )

        # Emissive glow from energy + onset flash
        emissive = energy * 0.5 + flash * 0.8

        # Base position from seat
        base_x = seat.x
        base_y = seat.y
        base_z = seat.z + CARNEGIE.stage_height_from_floor

        if visual.visual_type == "ribbon":
            elements.extend(
                self._generate_ribbons(
                    seat,
                    visual,
                    color,
                    energy,
                    emissive,
                    phase,
                    base_x,
                    base_y,
                    base_z,
                ),
            )
        elif visual.visual_type == "wave":
            elements.extend(
                self._generate_waves(
                    seat,
                    visual,
                    color,
                    energy,
                    emissive,
                    phase,
                    base_x,
                    base_y,
                    base_z,
                ),
            )
        elif visual.visual_type == "particle":
            elements.extend(
                self._generate_particles(
                    seat,
                    visual,
                    color,
                    energy,
                    emissive,
                    phase,
                    base_x,
                    base_y,
                    base_z,
                ),
            )
        elif visual.visual_type == "orb":
            elements.extend(
                self._generate_orbs(
                    seat,
                    visual,
                    color,
                    energy,
                    emissive,
                    phase,
                    flash,
                    base_x,
                    base_y,
                    base_z,
                ),
            )
        elif visual.visual_type == "ring":
            elements.extend(
                self._generate_rings(
                    seat,
                    visual,
                    color,
                    energy,
                    emissive,
                    phase,
                    flash,
                    base_x,
                    base_y,
                    base_z,
                ),
            )
        elif visual.visual_type == "string":
            elements.extend(
                self._generate_strings(
                    seat,
                    visual,
                    color,
                    energy,
                    emissive,
                    phase,
                    base_x,
                    base_y,
                    base_z,
                ),
            )

        return elements

    def _generate_ribbons(
        self,
        seat,
        visual,
        color,
        energy,
        emissive,
        phase,
        x,
        y,
        z,
    ) -> list[VisualManifestation]:
        """Generate flowing ribbon visuals (strings)."""
        elements = []
        num_ribbons = min(8, seat.player_count)

        for i in range(num_ribbons):
            ribbon_phase = phase + i * 0.4
            wave = math.sin(ribbon_phase) * visual.height_range[1] * 0.3 * energy

            # Spread across section
            offset_x = (i / num_ribbons - 0.5) * seat.width
            offset_y = (i % 2) * seat.depth * 0.3

            pos = (x + offset_x, y + offset_y, z + wave + 0.5)

            # Ribbon scale pulses with energy
            scale_y = 0.3 + energy * 0.5
            scale = (0.08, scale_y, 0.02)

            rot = (ribbon_phase * 0.3, 0, (i / num_ribbons) * 0.5)

            self._element_counter += 1
            elements.append(
                VisualManifestation(
                    instrument=seat.soul,
                    element_id=self._element_counter,
                    position=pos,
                    scale=scale,
                    rotation=rot,
                    color=color,
                    opacity=0.7 + energy * 0.3,
                    emissive=emissive,
                    mesh_type="ribbon",
                    animation_phase=phase,
                    energy=energy,
                    is_onset=False,
                ),
            )

        return elements

    def _generate_waves(
        self,
        seat,
        visual,
        color,
        energy,
        emissive,
        phase,
        x,
        y,
        z,
    ) -> list[VisualManifestation]:
        """Generate wave visuals (cello, bass, piano)."""
        elements = []

        # Central pulsing sphere
        pulse = 0.7 + 0.3 * math.sin(phase * 2)
        radius = visual.visual_radius * (0.3 + energy * 0.7) * pulse

        self._element_counter += 1
        elements.append(
            VisualManifestation(
                instrument=seat.soul,
                element_id=self._element_counter,
                position=(x, y, z + 0.8),
                scale=(radius, radius, radius * 0.5),
                rotation=(0, 0, phase * 0.1),
                color=color,
                opacity=0.5 + energy * 0.4,
                emissive=emissive,
                mesh_type="sphere",
                animation_phase=phase,
                energy=energy,
                is_onset=False,
            ),
        )

        # Concentric wave rings
        if energy > 0.2:
            for i in range(3):
                ring_phase = (phase * 0.5 + i * 0.7) % (2 * math.pi)
                ring_radius = visual.visual_radius * (0.5 + ring_phase / (2 * math.pi))
                ring_opacity = 0.3 * (1 - ring_phase / (2 * math.pi)) * energy

                self._element_counter += 1
                elements.append(
                    VisualManifestation(
                        instrument=seat.soul,
                        element_id=self._element_counter,
                        position=(x, y, z + 0.3),
                        scale=(ring_radius, ring_radius, 0.02),
                        rotation=(0, 0, 0),
                        color=color,
                        opacity=ring_opacity,
                        emissive=emissive * 0.5,
                        mesh_type="ring",
                        animation_phase=phase,
                        energy=energy,
                        is_onset=False,
                    ),
                )

        return elements

    def _generate_particles(
        self,
        seat,
        visual,
        color,
        energy,
        emissive,
        phase,
        x,
        y,
        z,
    ) -> list[VisualManifestation]:
        """Generate particle visuals (woodwinds)."""
        elements = []
        num_particles = int(5 + energy * 20)

        for i in range(num_particles):
            # Particles rise and spiral
            particle_phase = (phase * visual.breathe_rate + i * 0.2) % 1
            rise_height = particle_phase * visual.height_range[1]
            spiral = 0.3 * math.sin(phase * 2 + i)

            # Position with some randomness seeded by index
            seed = i * 0.618  # Golden ratio for distribution
            px = x + math.sin(seed * 10) * seat.width * 0.4 + spiral
            py = y + math.cos(seed * 10) * seat.depth * 0.3
            pz = z + rise_height

            # Fade as they rise
            opacity = (1 - particle_phase) * (0.3 + energy * 0.7)
            size = 0.03 + energy * 0.05 * (1 - particle_phase * 0.5)

            self._element_counter += 1
            elements.append(
                VisualManifestation(
                    instrument=seat.soul,
                    element_id=self._element_counter,
                    position=(px, py, pz),
                    scale=(size, size, size),
                    rotation=(0, 0, phase * i * 0.1),
                    color=color,
                    opacity=opacity,
                    emissive=emissive,
                    mesh_type="sphere",
                    animation_phase=phase,
                    energy=energy,
                    is_onset=False,
                ),
            )

        return elements

    def _generate_orbs(
        self,
        seat,
        visual,
        color,
        energy,
        emissive,
        phase,
        flash,
        x,
        y,
        z,
    ) -> list[VisualManifestation]:
        """Generate orb visuals (brass)."""
        elements = []

        # Main orb
        pulse = 0.6 + 0.4 * math.sin(phase * 3)
        radius = visual.visual_radius * (0.2 + energy * 0.8) * pulse

        self._element_counter += 1
        elements.append(
            VisualManifestation(
                instrument=seat.soul,
                element_id=self._element_counter,
                position=(x, y, z + 1.0),
                scale=(radius, radius, radius),
                rotation=(phase * 0.2, phase * 0.1, 0),
                color=color,
                opacity=0.6 + energy * 0.4,
                emissive=emissive + flash * 0.5,
                mesh_type="sphere",
                animation_phase=phase,
                energy=energy,
                is_onset=flash > 0.5,
            ),
        )

        # Radiating rays for high energy
        if energy > 0.4:
            num_rays = 6
            for i in range(num_rays):
                ray_angle = (i / num_rays) * 2 * math.pi + phase * 0.3
                ray_length = visual.visual_radius * energy * 1.5
                ray_x = x + math.cos(ray_angle) * ray_length * 0.5
                ray_y = y + math.sin(ray_angle) * ray_length * 0.5

                self._element_counter += 1
                elements.append(
                    VisualManifestation(
                        instrument=seat.soul,
                        element_id=self._element_counter,
                        position=(ray_x, ray_y, z + 1.0),
                        scale=(0.03, ray_length, 0.03),
                        rotation=(0, 0, ray_angle),
                        color=color,
                        opacity=energy * 0.5,
                        emissive=emissive * 0.7,
                        mesh_type="ribbon",
                        animation_phase=phase,
                        energy=energy,
                        is_onset=False,
                    ),
                )

        return elements

    def _generate_rings(
        self,
        seat,
        visual,
        color,
        energy,
        emissive,
        phase,
        flash,
        x,
        y,
        z,
    ) -> list[VisualManifestation]:
        """Generate impact ring visuals (percussion)."""
        elements = []

        # Timpani/drums generate expanding rings on impacts
        if flash > 0.1 or energy > 0.3:
            num_rings = 3
            for i in range(num_rings):
                ring_phase = (phase * 2 + i * 0.5) % 1
                ring_radius = visual.visual_radius * ring_phase
                ring_opacity = (1 - ring_phase) * (0.3 + flash * 0.7)

                self._element_counter += 1
                elements.append(
                    VisualManifestation(
                        instrument=seat.soul,
                        element_id=self._element_counter,
                        position=(x, y, z + 0.3),
                        scale=(ring_radius, ring_radius, 0.02),
                        rotation=(0, 0, 0),
                        color=color,
                        opacity=ring_opacity,
                        emissive=emissive + flash,
                        mesh_type="ring",
                        animation_phase=phase,
                        energy=energy,
                        is_onset=flash > 0.5,
                    ),
                )

        # Central impact point
        core_radius = 0.1 + energy * 0.2 + flash * 0.3
        self._element_counter += 1
        elements.append(
            VisualManifestation(
                instrument=seat.soul,
                element_id=self._element_counter,
                position=(x, y, z + 0.2),
                scale=(core_radius, core_radius, core_radius * 0.5),
                rotation=(0, 0, 0),
                color=color,
                opacity=0.6 + energy * 0.4,
                emissive=emissive + flash,
                mesh_type="sphere",
                animation_phase=phase,
                energy=energy,
                is_onset=flash > 0.5,
            ),
        )

        return elements

    def _generate_strings(
        self,
        seat,
        visual,
        color,
        energy,
        emissive,
        phase,
        x,
        y,
        z,
    ) -> list[VisualManifestation]:
        """Generate harp string visuals."""
        elements = []
        num_strings = 12

        for i in range(num_strings):
            string_phase = phase * 2 + i * 0.3
            string_active = math.sin(string_phase) > 0.2 and energy > 0.1

            if string_active:
                string_x = x + (i / num_strings - 0.5) * seat.width
                string_height = visual.height_range[1] * (0.5 + energy * 0.5)
                vibration = math.sin(string_phase * 10) * 0.02 * energy

                brightness = 0.5 + 0.5 * math.sin(string_phase * 3)

                self._element_counter += 1
                elements.append(
                    VisualManifestation(
                        instrument=seat.soul,
                        element_id=self._element_counter,
                        position=(string_x + vibration, y, z + string_height / 2),
                        scale=(0.01, 0.01, string_height),
                        rotation=(0, 0, 0),
                        color=color,
                        opacity=brightness * (0.4 + energy * 0.6),
                        emissive=emissive * brightness,
                        mesh_type="ribbon",
                        animation_phase=phase,
                        energy=energy,
                        is_onset=False,
                    ),
                )

        return elements


# =============================================================================
# MAIN VISUALIZER — The Complete Experience
# =============================================================================


class VirtuosoOrchestra:
    """The complete Virtuoso Orchestra visualization system.

    This brings together:
    - Audio analysis that UNDERSTANDS instruments
    - Visual generation that TRANSLATES music
    - Carnegie Hall as the sacred space
    - Every instrument positioned with care

    The result is not a "visualizer" — it's a LIVING ORCHESTRA.
    """

    def __init__(self) -> None:
        self.analyzer = VirtuosoAudioAnalyzer()
        self.generator = VirtuosoVisualizationGenerator()
        self.hall = CARNEGIE

    async def play_with_visualization(
        self,
        audio_path: Path,
        render_callback: Callable[[VirtuosoFrame], None] | None = None,
    ) -> None:
        """Play audio with synchronized visualization.

        Args:
            audio_path: Path to audio file
            render_callback: Called for each frame with visualization data
        """
        import sounddevice as sd
        import soundfile as sf

        # Load audio
        audio, sample_rate = sf.read(str(audio_path))
        audio_mono = np.mean(audio, axis=1) if len(audio.shape) > 1 else audio

        # Convert to float32
        if audio.dtype == np.float64:
            audio = audio.astype(np.float32)

        # Pre-analyze
        hop_size = self.analyzer.hop_size
        frames: list[dict] = []

        for i in range((len(audio_mono) - self.analyzer.fft_size) // hop_size + 1):
            start = i * hop_size
            end = start + self.analyzer.fft_size
            if end > len(audio_mono):
                break

            frame_audio = audio_mono[start:end]
            timestamp = start / sample_rate

            energies = self.analyzer.analyze_frame(frame_audio, timestamp)
            onsets = self.analyzer.detect_onsets(energies)

            frames.append(
                {
                    "timestamp": timestamp,
                    "energies": energies,
                    "onsets": onsets,
                },
            )

        # Play with visualization
        stream = sd.OutputStream(
            samplerate=sample_rate,
            channels=2 if len(audio.shape) > 1 else 1,
            dtype="float32",
        )

        fps = 60
        samples_per_frame = int(sample_rate / fps)
        audio_pos = 0
        prev_timestamp = 0.0

        stream.start()
        time.perf_counter()

        try:
            while audio_pos < len(audio):
                current_time = audio_pos / sample_rate

                # Find analysis frame
                frame_idx = int(current_time * sample_rate / hop_size)
                frame_idx = min(frame_idx, len(frames) - 1)

                if frame_idx >= 0:
                    analysis = frames[frame_idx]
                    dt = current_time - prev_timestamp
                    prev_timestamp = current_time

                    # Generate visualization frame
                    vis_frame = self.generator.generate_frame(
                        energies=analysis["energies"],
                        onsets=analysis["onsets"],
                        timestamp=current_time,
                        dt=max(dt, 1 / fps),
                    )

                    if render_callback:
                        render_callback(vis_frame)

                # Write audio
                chunk_end = min(audio_pos + samples_per_frame, len(audio))
                audio_chunk = audio[audio_pos:chunk_end]
                if len(audio_chunk) > 0:
                    stream.write(audio_chunk)

                audio_pos = chunk_end

        finally:
            stream.stop()
            stream.close()


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "CARNEGIE",
    "INSTRUMENT_FREQUENCIES",
    "INSTRUMENT_VISUALS",
    "ORCHESTRA_LAYOUT",
    # Hall
    "CarnegieHall",
    # Analysis
    "FrequencyProfile",
    # Soul
    "InstrumentSoul",
    "InstrumentVisualIdentity",
    "OrchestraSeat",
    "VirtuosoAudioAnalyzer",
    "VirtuosoFrame",
    # Main
    "VirtuosoOrchestra",
    "VirtuosoVisualizationGenerator",
    # Visualization
    "VisualManifestation",
]
