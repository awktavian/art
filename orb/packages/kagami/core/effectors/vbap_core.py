"""VBAP Core — Vector Base Amplitude Panning for 5.1.4 Atmos.

Single source of truth for all spatial audio positioning in Kagami.
Optimized for Tim's KEF Reference 5.1.4 system with Denon AVR-A10H.

Tim's System:
    Front: KEF Reference 5 Meta (L/R), Phantom Center
    Surround: KEF Reference 1 Meta (L/R)
    Height: 4x CI200RR-THX (TFL, TFR, TRL, TRR)
    Sub: 2x CI3160RLB-THX Extreme

Output Targets:
    1. Direct 5.1.4 (10ch) - for orchestral/music
    2. 8ch PCM → Neural:X - for voice (upmixes to height)

Created: January 1, 2026
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from functools import lru_cache

import numpy as np
from numpy.typing import NDArray

# =============================================================================
# Channel Layout — 5.1.4 Dolby Atmos
# =============================================================================

# 10-channel layout (industry standard order)
CH_FL, CH_FR, CH_C, CH_LFE = 0, 1, 2, 3
CH_SL, CH_SR = 4, 5  # Surround L/R
CH_TFL, CH_TFR, CH_TRL, CH_TRR = 6, 7, 8, 9  # Top/Height speakers
NUM_CH = 10

# 8-channel layout for Neural:X (bed layer only)
CH_8_FL, CH_8_FR, CH_8_C, CH_8_LFE = 0, 1, 2, 3
CH_8_BL, CH_8_BR, CH_8_SL, CH_8_SR = 4, 5, 6, 7
NUM_CH_8 = 8

# Speaker positions (azimuth, elevation in degrees)
# Azimuth: 0=front, positive=right, negative=left
# Elevation: 0=ear level, positive=up
SPEAKERS_10CH: dict[int, tuple[float, float]] = {
    CH_FL: (-30, 0),
    CH_FR: (30, 0),
    CH_C: (0, 0),  # Phantom - no signal
    CH_LFE: (0, -90),  # Bass managed
    CH_SL: (-110, 0),
    CH_SR: (110, 0),
    CH_TFL: (-45, 45),
    CH_TFR: (45, 45),
    CH_TRL: (-135, 45),
    CH_TRR: (135, 45),
}

SPEAKERS_8CH: dict[int, tuple[float, float]] = {
    CH_8_FL: (-30, 0),
    CH_8_FR: (30, 0),
    CH_8_C: (0, 0),  # Phantom
    CH_8_LFE: (0, -90),
    CH_8_BL: (-110, 0),
    CH_8_BR: (110, 0),
    CH_8_SL: (-110, 0),  # Unused in Tim's 5.1 base
    CH_8_SR: (110, 0),  # Unused
}


# =============================================================================
# Position Types
# =============================================================================


@dataclass(frozen=True)
class Pos3D:
    """3D position in spherical coordinates (conductor's perspective)."""

    az: float = 0.0  # Azimuth: -180 to 180, neg=left, pos=right
    el: float = 0.0  # Elevation: -90 to 90, pos=up
    dist: float = 5.0  # Distance in meters


# =============================================================================
# VBAP — 10-Channel (Direct 5.1.4)
# =============================================================================


@lru_cache(maxsize=512)
def vbap_10ch(az: float, el: float, dist: float, use_center: bool = False) -> tuple[float, ...]:
    """Compute VBAP gains for 5.1.4 (10 channels).

    Algorithm:
        1. Convert source to unit vector
        2. For each speaker, compute angle from source
        3. Apply gain based on angular distance (cosine law)
        4. Boost height channels for elevated sources
        5. Distance attenuation
        6. Energy normalization

    Args:
        az: Azimuth in degrees
        el: Elevation in degrees
        dist: Distance in meters
        use_center: If False (default), uses phantom center

    Returns:
        10-element tuple of gains
    """
    gains = np.zeros(NUM_CH, dtype=np.float64)

    # Normalize azimuth to [-180, 180]
    az = ((az + 180) % 360) - 180
    el = max(-90, min(90, el))

    # Source unit vector
    az_rad = math.radians(az)
    el_rad = math.radians(el)
    sx = math.cos(el_rad) * math.sin(az_rad)
    sy = math.cos(el_rad) * math.cos(az_rad)
    sz = math.sin(el_rad)

    # Compute gains for each speaker
    for ch, (spk_az, spk_el) in SPEAKERS_10CH.items():
        if ch == CH_LFE:
            continue
        if ch == CH_C and not use_center:
            continue

        # Speaker unit vector
        spk_az_rad = math.radians(spk_az)
        spk_el_rad = math.radians(spk_el)
        px = math.cos(spk_el_rad) * math.sin(spk_az_rad)
        py = math.cos(spk_el_rad) * math.cos(spk_az_rad)
        pz = math.sin(spk_el_rad)

        # Dot product = cos(angle between source and speaker)
        dot = sx * px + sy * py + sz * pz
        dot = max(-1.0, min(1.0, dot))

        # Angle in degrees
        angle = math.degrees(math.acos(dot))

        # Gain based on angle (wider spread = 90°)
        if angle < 90:
            # Cosine falloff with power for smoother spread
            gains[ch] = math.cos(math.radians(angle)) ** 1.2

    # Height handling: boost top speakers for elevated sources
    if el > 10:
        el_factor = min((el - 10) / 35, 1.0)  # Full effect at 45°
        # Transfer energy from bed to height
        bed_reduction = el_factor * 0.4
        height_boost = el_factor * 0.6

        gains[CH_FL] *= 1 - bed_reduction
        gains[CH_FR] *= 1 - bed_reduction
        gains[CH_SL] *= 1 - bed_reduction
        gains[CH_SR] *= 1 - bed_reduction

        gains[CH_TFL] *= 1 + height_boost
        gains[CH_TFR] *= 1 + height_boost
        gains[CH_TRL] *= 1 + height_boost
        gains[CH_TRR] *= 1 + height_boost

    elif el < -10:
        # Below horizon: reduce height, boost bed
        el_factor = min(abs(el + 10) / 35, 1.0)
        gains[CH_TFL] *= 1 - el_factor * 0.5
        gains[CH_TFR] *= 1 - el_factor * 0.5
        gains[CH_TRL] *= 1 - el_factor * 0.5
        gains[CH_TRR] *= 1 - el_factor * 0.5

    # Distance attenuation (inverse distance, clamped)
    dist_atten = min(1.0, 4.0 / max(dist, 1.5))
    gains *= dist_atten

    # Energy normalization (constant loudness)
    energy = np.sqrt(np.sum(gains**2))
    if energy > 0.01:
        gains /= energy

    return tuple(gains)


@lru_cache(maxsize=512)
def vbap_8ch_neuralx(az: float, el: float, dist: float) -> tuple[float, ...]:
    """Compute VBAP gains optimized for Neural:X upmixing.

    Neural:X interprets:
    - Front bias + HF boost = "above" → upmixes to height
    - No center signal (phantom from L/R)

    Args:
        az: Azimuth in degrees
        el: Elevation in degrees
        dist: Distance in meters

    Returns:
        8-element tuple of gains (for Neural:X input)
    """
    gains = np.zeros(NUM_CH_8, dtype=np.float64)

    # Normalize
    az = ((az + 180) % 360) - 180

    # Simple quadrant-based for 4-speaker bed (FL, FR, BL, BR)
    front_back = 0.5 + 0.5 * math.cos(math.radians(az))
    left_right = 0.5 + 0.5 * math.sin(math.radians(az))

    gains[CH_8_FL] = front_back * (1 - left_right)
    gains[CH_8_FR] = front_back * left_right
    gains[CH_8_BL] = (1 - front_back) * (1 - left_right)
    gains[CH_8_BR] = (1 - front_back) * left_right

    # Neural:X height cue: bias front for elevation
    if el > 5:
        el_factor = min(el / 45, 1.0)
        height_bias = 0.4 * el_factor

        gains[CH_8_FL] *= 1 + height_bias
        gains[CH_8_FR] *= 1 + height_bias
        gains[CH_8_BL] *= 1 - height_bias * 0.5
        gains[CH_8_BR] *= 1 - height_bias * 0.5

    # No center (phantom)
    gains[CH_8_C] = 0.0
    gains[CH_8_SL] = 0.0
    gains[CH_8_SR] = 0.0

    # Normalize
    energy = np.sqrt(np.sum(gains**2))
    if energy > 0.01:
        gains /= energy

    # Distance
    gains *= min(1.0, 1.0 / max(0.5, dist))

    return tuple(gains)


# =============================================================================
# Spatialization Functions
# =============================================================================


def spatialize_10ch(mono: NDArray, pos: Pos3D) -> NDArray:
    """Spatialize mono audio to 10-channel 5.1.4.

    Args:
        mono: Mono audio array
        pos: 3D position

    Returns:
        (N, 10) array for 5.1.4 output
    """
    n = len(mono)
    out = np.zeros((n, NUM_CH), dtype=np.float32)

    gains = np.array(vbap_10ch(pos.az, pos.el, pos.dist), dtype=np.float32)

    for ch in range(NUM_CH):
        if ch != CH_LFE and gains[ch] > 0.001:
            out[:, ch] = mono * gains[ch]

    return out


def spatialize_8ch(mono: NDArray, pos: Pos3D) -> NDArray:
    """Spatialize mono audio to 8-channel for Neural:X.

    Args:
        mono: Mono audio array
        pos: 3D position

    Returns:
        (N, 8) array for Neural:X input
    """
    n = len(mono)
    out = np.zeros((n, NUM_CH_8), dtype=np.float32)

    gains = np.array(vbap_8ch_neuralx(pos.az, pos.el, pos.dist), dtype=np.float32)

    for ch in range(NUM_CH_8):
        if ch not in (CH_8_LFE, CH_8_C) and gains[ch] > 0.001:
            out[:, ch] = mono * gains[ch]

    return out


def interpolate_position(
    pos_start: Pos3D,
    pos_end: Pos3D,
    t: float,
) -> Pos3D:
    """Interpolate between two positions (cosine smoothing)."""
    t_smooth = 0.5 * (1 - math.cos(t * math.pi))
    return Pos3D(
        az=pos_start.az + (pos_end.az - pos_start.az) * t_smooth,
        el=pos_start.el + (pos_end.el - pos_start.el) * t_smooth,
        dist=pos_start.dist + (pos_end.dist - pos_start.dist) * t_smooth,
    )


# =============================================================================
# Orchestra Positions (Carnegie Hall Layout) — Virtuoso Edition
# =============================================================================
#
# UPDATED Jan 4, 2026: Positions now unified with virtuoso_orchestra.py
# Full 45-instrument mapping with proper elevation tiers:
# - Strings: floor level (0-3°)
# - Woodwinds: first riser (8-12°)
# - Brass: second riser (15-20°)
# - Percussion: back riser (18-25°)

ORCHESTRA_POSITIONS: dict[str, Pos3D] = {
    # ==========================================================================
    # STRINGS — Front row, stage floor (elevation 0-3°)
    # ==========================================================================
    "violin i": Pos3D(-45, 1, 4.5),
    "violin ii": Pos3D(-20, 1, 5),
    "violins_1": Pos3D(-45, 1, 4.5),
    "violins_2": Pos3D(-20, 1, 5),
    "viola": Pos3D(15, 1, 5),
    "violas": Pos3D(15, 1, 5),
    "violoncello": Pos3D(40, 1, 5.5),
    "cello": Pos3D(40, 1, 5.5),
    "celli": Pos3D(40, 1, 5.5),
    "contrabass": Pos3D(55, 3, 6),
    "basses": Pos3D(55, 3, 6),
    "bass": Pos3D(55, 3, 6),
    # ==========================================================================
    # WOODWINDS — Second row, first riser (elevation 8-12°)
    # ==========================================================================
    "flute": Pos3D(-22, 10, 7),
    "flutes_a3": Pos3D(-22, 10, 7),
    "piccolo": Pos3D(-28, 12, 7.5),
    "bass_flute": Pos3D(-18, 9, 7.5),
    "oboe": Pos3D(-8, 10, 7),
    "oboes_a3": Pos3D(-8, 10, 7),
    "cor_anglais": Pos3D(-5, 11, 7.5),
    "english horn": Pos3D(-5, 11, 7.5),
    "clarinet": Pos3D(8, 10, 7),
    "clarinets_a3": Pos3D(8, 10, 7),
    "bass_clarinet": Pos3D(12, 9, 7.5),
    "bass clarinet": Pos3D(12, 9, 7.5),
    "contrabass_clarinet": Pos3D(15, 8, 8),
    "bassoon": Pos3D(22, 9, 7.5),
    "bassoons_a3": Pos3D(22, 9, 7.5),
    "contrabassoon": Pos3D(25, 8, 8),
    # ==========================================================================
    # BRASS — Third row, second riser (elevation 15-20°)
    # ==========================================================================
    "horn": Pos3D(-35, 16, 9),
    "horns_a4": Pos3D(-35, 16, 9),
    "french horn": Pos3D(-35, 16, 9),
    "trumpet": Pos3D(-5, 18, 9.5),
    "trumpets_a2": Pos3D(-5, 18, 9.5),
    "tenor_trombone": Pos3D(15, 17, 9.5),
    "trombone": Pos3D(15, 17, 9.5),
    "tenor_trombones_a3": Pos3D(15, 17, 9.5),
    "bass_trombones_a2": Pos3D(22, 16, 10),
    "contrabass_trombone": Pos3D(28, 15, 10.5),
    "tuba": Pos3D(35, 15, 10),
    "cimbasso": Pos3D(38, 14, 10.5),
    "contrabass_tuba": Pos3D(42, 13, 11),
    # ==========================================================================
    # PERCUSSION — Back row, highest riser (elevation 18-25°)
    # ==========================================================================
    "timpani": Pos3D(-50, 18, 11),
    "percussion": Pos3D(0, 22, 11.5),
    "untuned_percussion": Pos3D(0, 22, 11.5),
    "cymbals": Pos3D(5, 22, 12),
    "triangle": Pos3D(-10, 20, 11),
    "snare": Pos3D(0, 20, 11),
    "bass drum": Pos3D(10, 18, 12),
    "glockenspiel": Pos3D(0, 22, 11.5),
    "xylophone": Pos3D(8, 22, 11.5),
    "marimba": Pos3D(-8, 22, 11.5),
    "vibraphone": Pos3D(15, 22, 11.5),
    "crotales": Pos3D(22, 24, 12),
    "tubular_bells": Pos3D(-15, 23, 12),
    # ==========================================================================
    # SPECIAL POSITIONS
    # ==========================================================================
    "harp": Pos3D(-60, 3, 5.5),
    "celesta": Pos3D(-55, 8, 6.5),
    "celeste": Pos3D(-55, 8, 6.5),
    "piano": Pos3D(-45, 5, 5),
    # Fallbacks
    "violin": Pos3D(-35, 1, 4.5),
    "default": Pos3D(0, 10, 7),
}

# Match order: longer/more specific names first to prevent partial matches
_MATCH_ORDER = [
    # Specific variants first
    "contrabass_clarinet",
    "contrabass_trombone",
    "contrabass_tuba",
    "contrabassoon",
    "bass_clarinet",
    "bass_flute",
    "bass clarinet",
    "bass_trombones_a2",
    "tenor_trombones_a3",
    "tenor_trombone",
    "english horn",
    "french horn",
    "cor_anglais",
    "untuned_percussion",
    "tubular_bells",
    "bass drum",
    "violins_1",
    "violins_2",
    "violin_1_leader",
    "violin_2_leader",
    "violin ii",
    "violin i",
    "violas",
    "viola_leader",
    "celli_leader",
    "bass_leader",
    "violoncello",
    "contrabass",
    # Then sections
    "flutes_a3",
    "oboes_a3",
    "clarinets_a3",
    "bassoons_a3",
    "horns_a4",
    "trumpets_a2",
    # Glockenspiel before "glock" prefix match
    "glockenspiel",
    "vibraphone",
    "xylophone",
    "marimba",
    "crotales",
    # Singles
    "piccolo",
    "flute",
    "oboe",
    "clarinet",
    "bassoon",
    "cimbasso",
    "horn",
    "trumpet",
    "trombone",
    "tuba",
    "timpani",
    "percussion",
    "cymbals",
    "triangle",
    "snare",
    "harp",
    "celesta",
    "celeste",
    "piano",
    # Generic fallbacks last
    "viola",
    "violin",
    "celli",
    "cello",
    "basses",
    "bass",
]


def get_orchestra_position(name: str, program: int = 0) -> Pos3D:
    """Get orchestra position for instrument name/program."""
    n = name.lower()
    for key in _MATCH_ORDER:
        if key in n:
            return ORCHESTRA_POSITIONS[key]
    # GM program fallback
    if 40 <= program <= 51:
        return Pos3D(0, 2, 5)
    if 56 <= program <= 63:
        return Pos3D(20, 15, 9)
    if 64 <= program <= 79:
        return Pos3D(-10, 10, 7)
    return ORCHESTRA_POSITIONS["default"]


__all__ = [
    "CH_C",
    # Channel indices
    "CH_FL",
    "CH_FR",
    "CH_LFE",
    "CH_SL",
    "CH_SR",
    "CH_TFL",
    "CH_TFR",
    "CH_TRL",
    "CH_TRR",
    "NUM_CH",
    "NUM_CH_8",
    # Orchestra
    "ORCHESTRA_POSITIONS",
    "SPEAKERS_8CH",
    # Speaker layouts
    "SPEAKERS_10CH",
    # Types
    "Pos3D",
    "get_orchestra_position",
    "interpolate_position",
    "spatialize_8ch",
    "spatialize_10ch",
    "vbap_8ch_neuralx",
    # VBAP
    "vbap_10ch",
]
