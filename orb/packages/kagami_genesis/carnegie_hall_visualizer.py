"""Carnegie Hall Orchestra Visualizer — A Living, Breathing 3D Experience.

This is not a visualizer. This is the music made visible.

Every instrument has a soul:
- The violin SINGS with golden light that rises from the heart
- The cello BREATHES deeply, warm amber pulsing with each bow stroke
- The brass BLAZES — triumphant, bold, reaching toward the heavens
- The timpani THUNDERS — primal energy radiating outward like ripples in still water
- The flute FLOATS — crystalline particles ascending, ethereal
- The harp CASCADES — water falling through light

The space is Carnegie Hall — 57th Street, New York.
Isaac Stern Auditorium. 2,804 seats. Built 1891.
The most famous concert hall in the world.

Dimensions (actual):
    Stage: 18m wide × 11m deep
    Ceiling height: 20m at apex
    Auditorium: 32m long × 28m wide
    Capacity: 2,804 seats

We don't just SEE the orchestra. We FEEL it.

Colony: Full Fano Collaboration — All 7 colonies united
Created: January 4, 2026
"""

from __future__ import annotations

import asyncio
import colorsys
import logging
import math
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf

logger = logging.getLogger(__name__)


# =============================================================================
# CARNEGIE HALL ARCHITECTURE
# =============================================================================

# Real dimensions (meters)
STAGE_WIDTH = 18.0
STAGE_DEPTH = 11.0
CEILING_HEIGHT = 20.0
HALL_LENGTH = 32.0
HALL_WIDTH = 28.0

# The stage exists in a 3D space where the conductor stands at (0, 0, 1.2)
# facing the audience (negative Y)
# X = stage left/right (positive = audience's right = stage left)
# Y = upstage/downstage (positive = toward back wall)
# Z = height (floor = 0)


@dataclass
class CarnegieInstrumentSoul:
    """The soul of an instrument — its visual character.

    Every instrument has a personality:
    - How it breathes with the music
    - Its color temperature and hue
    - How it moves through space
    - What emotions it expresses
    """

    # Identity
    name: str
    family: str  # strings, woodwinds, brass, percussion, keyboard

    # 3D Position on stage (meters from conductor)
    x: float  # left-right (neg=left from conductor's view)
    y: float  # upstage-downstage (pos=upstage)
    z: float  # height above stage floor

    # Visual Character
    color_hue: float  # 0-360 (HSV hue)
    color_saturation: float  # 0-1
    color_warmth: float  # 0-1 (0=cool blue shift, 1=warm amber shift)
    glow_intensity: float  # Base emissive intensity
    size_base: float  # Base visual size

    # Animation Character
    breath_rate: float  # Breathing cycle speed
    breath_depth: float  # How much it expands/contracts
    pulse_style: str  # "gentle", "sharp", "wave", "ripple"
    motion_style: str  # "float", "pulse", "shimmer", "flame"

    # Emotional Response
    attack_response: float  # How quickly it responds to transients
    sustain_glow: float  # How much it glows on sustained notes
    decay_trail: float  # How long the visual lingers

    # Energy frequency bands (Hz ranges this instrument responds to)
    freq_low: float
    freq_high: float


# =============================================================================
# THE ORCHESTRA — Every instrument's soul
# =============================================================================

ORCHESTRA_SOULS: dict[str, CarnegieInstrumentSoul] = {
    # =========================================================================
    # STRINGS — The heart of the orchestra. Warm, singing, expressive.
    # =========================================================================
    "violins_1": CarnegieInstrumentSoul(
        name="First Violins",
        family="strings",
        x=-4.0,
        y=2.0,
        z=0.8,  # Stage left, front
        color_hue=35,  # Golden amber
        color_saturation=0.75,
        color_warmth=0.9,
        glow_intensity=0.7,
        size_base=1.2,
        breath_rate=0.8,
        breath_depth=0.25,
        pulse_style="wave",
        motion_style="float",
        attack_response=0.6,
        sustain_glow=0.8,
        decay_trail=0.4,
        freq_low=196,  # G3
        freq_high=3520,  # A7
    ),
    "violins_2": CarnegieInstrumentSoul(
        name="Second Violins",
        family="strings",
        x=-2.0,
        y=3.0,
        z=0.8,
        color_hue=40,  # Slightly warmer
        color_saturation=0.7,
        color_warmth=0.85,
        glow_intensity=0.65,
        size_base=1.1,
        breath_rate=0.75,
        breath_depth=0.22,
        pulse_style="wave",
        motion_style="float",
        attack_response=0.55,
        sustain_glow=0.75,
        decay_trail=0.35,
        freq_low=196,
        freq_high=3520,
    ),
    "violas": CarnegieInstrumentSoul(
        name="Violas",
        family="strings",
        x=1.5,
        y=2.5,
        z=0.8,
        color_hue=30,  # Deeper amber
        color_saturation=0.65,
        color_warmth=0.95,
        glow_intensity=0.6,
        size_base=1.0,
        breath_rate=0.7,
        breath_depth=0.28,
        pulse_style="gentle",
        motion_style="float",
        attack_response=0.5,
        sustain_glow=0.85,
        decay_trail=0.45,
        freq_low=130,  # C3
        freq_high=2093,  # C7
    ),
    "celli": CarnegieInstrumentSoul(
        name="Cellos",
        family="strings",
        x=4.0,
        y=2.5,
        z=0.6,
        color_hue=25,  # Rich amber-orange
        color_saturation=0.8,
        color_warmth=1.0,
        glow_intensity=0.75,
        size_base=1.3,
        breath_rate=0.5,
        breath_depth=0.35,
        pulse_style="gentle",
        motion_style="pulse",
        attack_response=0.4,
        sustain_glow=0.9,
        decay_trail=0.5,
        freq_low=65,  # C2
        freq_high=1046,  # C6
    ),
    "basses": CarnegieInstrumentSoul(
        name="Double Basses",
        family="strings",
        x=5.5,
        y=3.5,
        z=0.5,
        color_hue=20,  # Deep warm orange
        color_saturation=0.7,
        color_warmth=1.0,
        glow_intensity=0.6,
        size_base=1.5,
        breath_rate=0.35,
        breath_depth=0.4,
        pulse_style="gentle",
        motion_style="pulse",
        attack_response=0.3,
        sustain_glow=0.85,
        decay_trail=0.6,
        freq_low=41,  # E1
        freq_high=392,  # G4
    ),
    # =========================================================================
    # WOODWINDS — Ethereal, clear, floating. The sprites of the orchestra.
    # =========================================================================
    "flutes_a3": CarnegieInstrumentSoul(
        name="Flutes",
        family="woodwinds",
        x=-2.5,
        y=5.0,
        z=1.8,  # First riser
        color_hue=180,  # Cyan-turquoise
        color_saturation=0.5,
        color_warmth=0.3,
        glow_intensity=0.8,
        size_base=0.8,
        breath_rate=1.2,
        breath_depth=0.3,
        pulse_style="shimmer",
        motion_style="float",
        attack_response=0.8,
        sustain_glow=0.6,
        decay_trail=0.25,
        freq_low=262,  # C4
        freq_high=4186,  # C8
    ),
    "piccolo": CarnegieInstrumentSoul(
        name="Piccolo",
        family="woodwinds",
        x=-3.5,
        y=5.5,
        z=2.0,
        color_hue=195,  # Bright cyan
        color_saturation=0.55,
        color_warmth=0.2,
        glow_intensity=0.9,
        size_base=0.5,
        breath_rate=1.5,
        breath_depth=0.35,
        pulse_style="shimmer",
        motion_style="float",
        attack_response=0.9,
        sustain_glow=0.5,
        decay_trail=0.2,
        freq_low=587,  # D5
        freq_high=4186,  # C8
    ),
    "oboes_a3": CarnegieInstrumentSoul(
        name="Oboes",
        family="woodwinds",
        x=-1.0,
        y=5.0,
        z=1.8,
        color_hue=120,  # Green
        color_saturation=0.6,
        color_warmth=0.4,
        glow_intensity=0.7,
        size_base=0.7,
        breath_rate=0.9,
        breath_depth=0.25,
        pulse_style="gentle",
        motion_style="shimmer",
        attack_response=0.7,
        sustain_glow=0.7,
        decay_trail=0.3,
        freq_low=233,  # Bb3
        freq_high=1760,  # A6
    ),
    "clarinets_a3": CarnegieInstrumentSoul(
        name="Clarinets",
        family="woodwinds",
        x=1.0,
        y=5.0,
        z=1.8,
        color_hue=150,  # Teal-green
        color_saturation=0.55,
        color_warmth=0.35,
        glow_intensity=0.65,
        size_base=0.75,
        breath_rate=0.85,
        breath_depth=0.22,
        pulse_style="gentle",
        motion_style="shimmer",
        attack_response=0.65,
        sustain_glow=0.75,
        decay_trail=0.35,
        freq_low=165,  # E3
        freq_high=2093,  # C7
    ),
    "bassoons_a3": CarnegieInstrumentSoul(
        name="Bassoons",
        family="woodwinds",
        x=2.5,
        y=5.0,
        z=1.6,
        color_hue=90,  # Yellow-green
        color_saturation=0.5,
        color_warmth=0.5,
        glow_intensity=0.55,
        size_base=0.9,
        breath_rate=0.6,
        breath_depth=0.28,
        pulse_style="gentle",
        motion_style="pulse",
        attack_response=0.5,
        sustain_glow=0.8,
        decay_trail=0.4,
        freq_low=58,  # Bb1
        freq_high=698,  # F5
    ),
    # =========================================================================
    # BRASS — Power, triumph, blazing glory. The warriors of sound.
    # =========================================================================
    "horns_a4": CarnegieInstrumentSoul(
        name="French Horns",
        family="brass",
        x=-4.0,
        y=7.0,
        z=2.5,  # Second riser
        color_hue=45,  # Gold
        color_saturation=0.85,
        color_warmth=0.85,
        glow_intensity=0.8,
        size_base=1.1,
        breath_rate=0.5,
        breath_depth=0.3,
        pulse_style="wave",
        motion_style="flame",
        attack_response=0.5,
        sustain_glow=0.9,
        decay_trail=0.5,
        freq_low=87,  # F2
        freq_high=1175,  # D6
    ),
    "trumpets_a2": CarnegieInstrumentSoul(
        name="Trumpets",
        family="brass",
        x=-0.5,
        y=7.5,
        z=2.8,
        color_hue=50,  # Bright gold
        color_saturation=0.9,
        color_warmth=0.8,
        glow_intensity=0.95,
        size_base=0.9,
        breath_rate=0.7,
        breath_depth=0.35,
        pulse_style="sharp",
        motion_style="flame",
        attack_response=0.85,
        sustain_glow=0.7,
        decay_trail=0.3,
        freq_low=165,  # E3
        freq_high=1175,  # D6
    ),
    "tenor_trombones_a3": CarnegieInstrumentSoul(
        name="Trombones",
        family="brass",
        x=2.0,
        y=7.5,
        z=2.6,
        color_hue=40,  # Deep gold
        color_saturation=0.8,
        color_warmth=0.9,
        glow_intensity=0.85,
        size_base=1.2,
        breath_rate=0.45,
        breath_depth=0.38,
        pulse_style="wave",
        motion_style="flame",
        attack_response=0.6,
        sustain_glow=0.85,
        decay_trail=0.45,
        freq_low=82,  # E2
        freq_high=587,  # D5
    ),
    "tuba": CarnegieInstrumentSoul(
        name="Tuba",
        family="brass",
        x=4.0,
        y=7.0,
        z=2.3,
        color_hue=35,  # Bronze
        color_saturation=0.7,
        color_warmth=1.0,
        glow_intensity=0.7,
        size_base=1.5,
        breath_rate=0.3,
        breath_depth=0.45,
        pulse_style="gentle",
        motion_style="pulse",
        attack_response=0.35,
        sustain_glow=0.9,
        decay_trail=0.55,
        freq_low=29,  # Bb0
        freq_high=311,  # Eb4
    ),
    # =========================================================================
    # PERCUSSION — Primal energy, rhythm, the heartbeat.
    # =========================================================================
    "timpani": CarnegieInstrumentSoul(
        name="Timpani",
        family="percussion",
        x=-5.5,
        y=9.0,
        z=2.8,
        color_hue=15,  # Deep red-orange
        color_saturation=0.9,
        color_warmth=1.0,
        glow_intensity=0.9,
        size_base=1.4,
        breath_rate=0.2,
        breath_depth=0.5,
        pulse_style="ripple",
        motion_style="pulse",
        attack_response=0.95,
        sustain_glow=0.6,
        decay_trail=0.4,
        freq_low=65,  # C2
        freq_high=262,  # C4
    ),
    "untuned_percussion": CarnegieInstrumentSoul(
        name="Percussion",
        family="percussion",
        x=0,
        y=9.5,
        z=3.0,
        color_hue=0,  # White/silver
        color_saturation=0.15,
        color_warmth=0.5,
        glow_intensity=1.0,
        size_base=1.0,
        breath_rate=0.3,
        breath_depth=0.6,
        pulse_style="ripple",
        motion_style="pulse",
        attack_response=1.0,
        sustain_glow=0.3,
        decay_trail=0.25,
        freq_low=20,
        freq_high=15000,
    ),
    "glockenspiel": CarnegieInstrumentSoul(
        name="Glockenspiel",
        family="percussion",
        x=1.5,
        y=9.0,
        z=3.2,
        color_hue=210,  # Bright blue
        color_saturation=0.6,
        color_warmth=0.2,
        glow_intensity=0.95,
        size_base=0.6,
        breath_rate=1.5,
        breath_depth=0.4,
        pulse_style="shimmer",
        motion_style="float",
        attack_response=0.95,
        sustain_glow=0.4,
        decay_trail=0.3,
        freq_low=1568,  # G6
        freq_high=6272,  # G8
    ),
    # =========================================================================
    # KEYBOARD & HARP — Crystalline, cascading, magical.
    # =========================================================================
    "harp": CarnegieInstrumentSoul(
        name="Harp",
        family="keyboard",
        x=-6.5,
        y=3.0,
        z=1.0,
        color_hue=270,  # Purple
        color_saturation=0.6,
        color_warmth=0.4,
        glow_intensity=0.75,
        size_base=1.3,
        breath_rate=1.0,
        breath_depth=0.3,
        pulse_style="shimmer",
        motion_style="float",
        attack_response=0.85,
        sustain_glow=0.5,
        decay_trail=0.35,
        freq_low=32,  # C1
        freq_high=3136,  # G7
    ),
    "celeste": CarnegieInstrumentSoul(
        name="Celesta",
        family="keyboard",
        x=-6.0,
        y=4.5,
        z=1.5,
        color_hue=240,  # Blue-violet
        color_saturation=0.5,
        color_warmth=0.25,
        glow_intensity=0.85,
        size_base=0.9,
        breath_rate=1.2,
        breath_depth=0.25,
        pulse_style="shimmer",
        motion_style="float",
        attack_response=0.9,
        sustain_glow=0.45,
        decay_trail=0.3,
        freq_low=262,  # C4
        freq_high=4186,  # C8
    ),
}


# =============================================================================
# AUDIO ANALYSIS — Feel the music
# =============================================================================

SAMPLE_RATE = 48000
FFT_SIZE = 4096
HOP_SIZE = 1024


@dataclass
class MusicMoment:
    """A single moment of the music, analyzed."""

    timestamp: float
    instrument_energies: dict[str, float]  # 0-1 per instrument
    overall_energy: float
    spectral_brightness: float  # Higher = brighter sound
    low_energy: float  # Bass rumble
    mid_energy: float  # Melodic content
    high_energy: float  # Brilliance
    onset_strength: float  # Transient detection
    is_crescendo: bool
    is_diminuendo: bool


class OrchestraAnalyzer:
    """Analyze audio and extract per-instrument energy."""

    def __init__(self) -> None:
        self._prev_energy = 0.0
        self._energy_history: list[float] = []
        self._window = np.hanning(FFT_SIZE)

    def analyze(self, audio_mono: np.ndarray, sample_rate: int) -> list[MusicMoment]:
        """Analyze entire audio file."""
        moments: list[MusicMoment] = []

        n_frames = (len(audio_mono) - FFT_SIZE) // HOP_SIZE + 1

        for i in range(n_frames):
            start = i * HOP_SIZE
            end = start + FFT_SIZE
            frame = audio_mono[start:end]
            timestamp = start / sample_rate

            moment = self._analyze_frame(frame, timestamp)
            moments.append(moment)

        return moments

    def _analyze_frame(self, frame: np.ndarray, timestamp: float) -> MusicMoment:
        """Analyze a single frame."""
        # FFT
        windowed = frame * self._window
        spectrum = np.abs(np.fft.rfft(windowed))
        freq_bins = np.fft.rfftfreq(FFT_SIZE, 1 / SAMPLE_RATE)

        # Convert to dB and normalize
        spectrum_db = 20 * np.log10(spectrum + 1e-10)
        spectrum_norm = np.clip((spectrum_db + 80) / 80, 0, 1)

        # Overall energy
        overall = np.mean(spectrum_norm)

        # Frequency bands
        low_mask = freq_bins < 200
        mid_mask = (freq_bins >= 200) & (freq_bins < 2000)
        high_mask = freq_bins >= 2000

        low_energy = np.mean(spectrum_norm[low_mask]) if np.any(low_mask) else 0
        mid_energy = np.mean(spectrum_norm[mid_mask]) if np.any(mid_mask) else 0
        high_energy = np.mean(spectrum_norm[high_mask]) if np.any(high_mask) else 0

        # Spectral centroid (brightness)
        total_mag = np.sum(spectrum)
        brightness = np.sum(freq_bins * spectrum) / total_mag if total_mag > 0 else 0

        # Per-instrument energy (based on frequency bands)
        instrument_energies = {}
        for key, soul in ORCHESTRA_SOULS.items():
            # Find indices for this instrument's frequency range
            inst_mask = (freq_bins >= soul.freq_low) & (freq_bins <= soul.freq_high)
            inst_energy = np.mean(spectrum_norm[inst_mask]) if np.any(inst_mask) else 0
            instrument_energies[key] = float(inst_energy)

        # Onset detection (energy flux)
        onset_strength = max(0, overall - self._prev_energy)
        self._prev_energy = overall * 0.9 + self._prev_energy * 0.1

        # Dynamics tracking
        self._energy_history.append(overall)
        if len(self._energy_history) > 30:
            self._energy_history.pop(0)

        is_crescendo = False
        is_diminuendo = False
        if len(self._energy_history) >= 10:
            recent = self._energy_history[-5:]
            older = self._energy_history[-10:-5]
            avg_recent = np.mean(recent)
            avg_older = np.mean(older)
            if avg_recent > avg_older * 1.15:
                is_crescendo = True
            elif avg_recent < avg_older * 0.85:
                is_diminuendo = True

        return MusicMoment(
            timestamp=timestamp,
            instrument_energies=instrument_energies,
            overall_energy=overall,
            spectral_brightness=brightness / 4000,  # Normalize
            low_energy=low_energy,
            mid_energy=mid_energy,
            high_energy=high_energy,
            onset_strength=onset_strength,
            is_crescendo=is_crescendo,
            is_diminuendo=is_diminuendo,
        )


# =============================================================================
# VISUAL SOUL — How the instruments BREATHE
# =============================================================================


@dataclass
class VisualSoulState:
    """The visual state of one instrument's soul."""

    # Position in 3D space
    x: float
    y: float
    z: float

    # Color (RGB 0-1)
    r: float
    g: float
    b: float

    # Glow
    glow: float  # 0-1
    glow_radius: float

    # Scale
    scale: float

    # Particles (for ethereal instruments)
    particle_count: int
    particle_velocities: list[tuple[float, float, float]]

    # Trail (for sustained sounds)
    trail_opacity: float
    trail_positions: list[tuple[float, float, float]]


class SoulRenderer:
    """Render the souls of the instruments."""

    def __init__(self) -> None:
        self._phase = 0.0
        self._soul_states: dict[str, VisualSoulState] = {}
        self._onset_flash = 0.0

        # Initialize states
        for key, soul in ORCHESTRA_SOULS.items():
            r, g, b = self._soul_color(soul, 0)
            self._soul_states[key] = VisualSoulState(
                x=soul.x,
                y=soul.y,
                z=soul.z,
                r=r,
                g=g,
                b=b,
                glow=0.1,
                glow_radius=soul.size_base * 0.5,
                scale=soul.size_base,
                particle_count=0,
                particle_velocities=[],
                trail_opacity=0,
                trail_positions=[],
            )

    def _soul_color(
        self,
        soul: CarnegieInstrumentSoul,
        energy: float,
    ) -> tuple[float, float, float]:
        """Compute the color for an instrument soul."""
        # Base HSV from soul
        h = soul.color_hue / 360
        s = soul.color_saturation * (0.5 + energy * 0.5)
        v = 0.3 + energy * 0.7

        # Apply warmth shift
        if soul.color_warmth > 0.5:
            # Shift toward amber
            h = h * (1 - soul.color_warmth * 0.3) + 0.1 * soul.color_warmth
        else:
            # Shift toward blue
            cool_shift = (0.5 - soul.color_warmth) * 0.2
            h = (h + cool_shift) % 1.0

        r, g, b = colorsys.hsv_to_rgb(h, s, v)
        return r, g, b

    def update(self, moment: MusicMoment, dt: float) -> dict[str, VisualSoulState]:
        """Update all soul states based on the current music moment."""
        self._phase += dt

        # Global onset flash
        if moment.onset_strength > 0.3:
            self._onset_flash = min(1.0, self._onset_flash + moment.onset_strength * 2)
        else:
            self._onset_flash *= 0.85

        for key, soul in ORCHESTRA_SOULS.items():
            energy = moment.instrument_energies.get(key, 0)
            state = self._soul_states[key]

            # Breathing animation
            breath = math.sin(self._phase * soul.breath_rate * 2 * math.pi)
            breath_scale = 1 + breath * soul.breath_depth * energy

            # Position animation based on motion style
            dx, dy, dz = 0.0, 0.0, 0.0
            if soul.motion_style == "float":
                dx = math.sin(self._phase * 0.5 + soul.x) * 0.1 * energy
                dz = math.sin(self._phase * 0.7 + soul.y) * 0.15 * energy
            elif soul.motion_style == "pulse":
                pulse = abs(math.sin(self._phase * soul.breath_rate * math.pi))
                dz = pulse * 0.2 * energy
            elif soul.motion_style == "flame":
                # Flickering upward motion
                flicker = (math.sin(self._phase * 3) + math.sin(self._phase * 7) * 0.5) * 0.5
                dz = flicker * 0.3 * energy + energy * 0.2
            elif soul.motion_style == "shimmer":
                dx = (math.sin(self._phase * 4 + soul.x * 10) * 0.05) * energy
                dy = (math.cos(self._phase * 3 + soul.y * 10) * 0.05) * energy

            # Update position
            state.x = soul.x + dx
            state.y = soul.y + dy
            state.z = soul.z + dz

            # Update color with energy
            state.r, state.g, state.b = self._soul_color(soul, energy)

            # Glow
            target_glow = soul.glow_intensity * energy
            if moment.onset_strength > 0.2:
                target_glow = min(1.0, target_glow + moment.onset_strength * soul.attack_response)
            state.glow = state.glow * 0.7 + target_glow * 0.3

            # Glow radius
            state.glow_radius = soul.size_base * (0.5 + energy * 0.5 + breath_scale * 0.2)

            # Scale
            state.scale = soul.size_base * breath_scale * (0.8 + energy * 0.4)

            # Particles for ethereal instruments
            if soul.motion_style in ("float", "shimmer") and energy > 0.3:
                state.particle_count = int(energy * 10)
            else:
                state.particle_count = 0

            # Trail for sustained sounds
            if energy > 0.2:
                state.trail_opacity = min(soul.decay_trail, state.trail_opacity + 0.1)
                state.trail_positions.append((state.x, state.y, state.z))
                if len(state.trail_positions) > 20:
                    state.trail_positions.pop(0)
            else:
                state.trail_opacity *= 0.9
                if state.trail_opacity < 0.05:
                    state.trail_positions.clear()

        return self._soul_states


# =============================================================================
# THE VISUALIZATION — The music made visible
# =============================================================================


class CarnegieHallVisualizer:
    """The complete Carnegie Hall visualization experience."""

    def __init__(self, width: int = 1920, height: int = 1080) -> None:
        self.width = width
        self.height = height
        self.analyzer = OrchestraAnalyzer()
        self.renderer = SoulRenderer()

        # Camera
        self.camera_distance = 15.0
        self.camera_height = 8.0
        self.camera_orbit = 0.0

    async def play_with_visualization(
        self,
        audio_path: Path,
        progress_callback: Callable[[str, float], None] | None = None,
    ) -> None:
        """Play audio with synchronized 3D visualization."""
        import sounddevice as sd

        # Lazy import pygame
        try:
            import pygame
            from pygame import gfxdraw
        except ImportError:
            logger.error("pygame not installed. Run: pip install pygame")
            raise

        logger.info(f"🎭 Carnegie Hall — {audio_path.name}")

        # Load audio
        audio, sr = sf.read(str(audio_path))
        if len(audio.shape) > 1:
            audio_mono = np.mean(audio, axis=1)
        else:
            audio_mono = audio
            audio = np.stack([audio, audio], axis=1)

        # Convert to float32
        if audio.dtype == np.float64:
            audio = audio.astype(np.float32)

        # Pre-analyze
        if progress_callback:
            progress_callback("Analyzing", 0)
        moments = self.analyzer.analyze(audio_mono, sr)
        if progress_callback:
            progress_callback("Analyzing", 1)

        # Initialize pygame
        pygame.init()
        pygame.display.set_caption("🎭 Carnegie Hall — The Music Made Visible")
        screen = pygame.display.set_mode((self.width, self.height))
        clock = pygame.time.Clock()
        font = pygame.font.SysFont("SF Pro Display", 16)
        title_font = pygame.font.SysFont("SF Pro Display", 28)

        # Start audio
        stream = sd.OutputStream(
            samplerate=sr,
            channels=audio.shape[1],
            dtype="float32",
        )
        stream.start()

        # Playback loop
        audio_pos = 0
        samples_per_frame = int(sr / 60)
        running = True

        try:
            while running and audio_pos < len(audio):
                # Events
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        running = False
                    if event.type == pygame.KEYDOWN:
                        if event.key == pygame.K_ESCAPE:
                            running = False
                        if event.key == pygame.K_SPACE:
                            # Pause/resume (TODO)
                            pass

                # Current time and moment
                current_time = audio_pos / sr
                moment_idx = int(current_time * sr / HOP_SIZE)
                moment_idx = min(moment_idx, len(moments) - 1)
                moment = moments[moment_idx]

                # Update visualization
                dt = 1 / 60
                soul_states = self.renderer.update(moment, dt)

                # Render
                self._render_frame(
                    screen,
                    soul_states,
                    moment,
                    current_time,
                    font,
                    title_font,
                )

                # Play audio chunk
                chunk_end = min(audio_pos + samples_per_frame, len(audio))
                chunk = audio[audio_pos:chunk_end]
                if len(chunk) > 0:
                    stream.write(chunk)
                audio_pos = chunk_end

                pygame.display.flip()
                clock.tick(60)

        finally:
            stream.stop()
            stream.close()
            pygame.quit()

        logger.info("✓ Performance complete")

    def _render_frame(
        self,
        screen: Any,
        souls: dict[str, VisualSoulState],
        moment: MusicMoment,
        time: float,
        font: Any,
        title_font: Any,
    ) -> None:
        """Render one frame of the visualization."""
        import pygame

        # Background — deep concert hall black with subtle gradient
        screen.fill((8, 8, 12))

        # Ambient glow based on overall energy
        ambient = int(moment.overall_energy * 15)
        (ambient, ambient + 2, ambient + 5)

        # Draw stage floor (perspective rectangle)
        stage_color = (20 + ambient, 18 + ambient, 15 + ambient)
        stage_points = [
            self._project((-STAGE_WIDTH / 2, 0, 0)),
            self._project((STAGE_WIDTH / 2, 0, 0)),
            self._project((STAGE_WIDTH / 2, STAGE_DEPTH, 0)),
            self._project((-STAGE_WIDTH / 2, STAGE_DEPTH, 0)),
        ]
        pygame.draw.polygon(screen, stage_color, stage_points)

        # Sort souls by Y (depth) for proper layering
        sorted_souls = sorted(
            souls.items(),
            key=lambda x: ORCHESTRA_SOULS[x[0]].y,
            reverse=True,
        )

        # Draw each soul
        for key, state in sorted_souls:
            soul = ORCHESTRA_SOULS[key]
            energy = moment.instrument_energies.get(key, 0)

            # Project 3D to 2D
            cx, cy = self._project((state.x, state.y, state.z))

            # Skip if off screen
            if cx < -100 or cx > self.width + 100 or cy < -100 or cy > self.height + 100:
                continue

            # Size based on depth (farther = smaller)
            depth_scale = 1 / (1 + state.y * 0.08)
            base_radius = int(state.scale * 25 * depth_scale)

            if base_radius < 2:
                continue

            # Glow layers (outer to inner)
            if state.glow > 0.1:
                glow_radius = int(state.glow_radius * 60 * depth_scale)
                for i in range(5, 0, -1):
                    r = int(glow_radius * (i / 5))
                    alpha = int(state.glow * 80 * (1 - i / 5))
                    glow_color = (
                        min(255, int(state.r * 255)),
                        min(255, int(state.g * 255)),
                        min(255, int(state.b * 255)),
                    )
                    # Draw glow circle
                    s = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
                    pygame.draw.circle(s, (*glow_color, alpha), (r, r), r)
                    screen.blit(s, (cx - r, cy - r), special_flags=pygame.BLEND_ADD)

            # Core orb
            color = (
                min(255, int(state.r * 255 * (0.5 + state.glow * 0.5))),
                min(255, int(state.g * 255 * (0.5 + state.glow * 0.5))),
                min(255, int(state.b * 255 * (0.5 + state.glow * 0.5))),
            )

            # Different shapes based on family
            if soul.family == "strings":
                # Oval for strings (horizontal)
                ellipse_rect = pygame.Rect(
                    cx - base_radius,
                    cy - int(base_radius * 0.6),
                    base_radius * 2,
                    int(base_radius * 1.2),
                )
                pygame.draw.ellipse(screen, color, ellipse_rect)
            elif soul.family == "brass":
                # Larger, more intense circle for brass
                pygame.draw.circle(screen, color, (cx, cy), base_radius)
                # Inner bright core
                inner_color = (
                    min(255, color[0] + 50),
                    min(255, color[1] + 30),
                    min(255, color[2]),
                )
                pygame.draw.circle(screen, inner_color, (cx, cy), base_radius // 2)
            elif soul.family == "percussion":
                # Ripple effect for percussion
                if energy > 0.2:
                    n_rings = int(3 + energy * 4)
                    for ring in range(n_rings):
                        ring_r = base_radius + ring * 15
                        ring_alpha = int(255 * (1 - ring / n_rings) * energy)
                        ring_color = (*color[:3], ring_alpha)
                        s = pygame.Surface((ring_r * 2, ring_r * 2), pygame.SRCALPHA)
                        pygame.draw.circle(s, ring_color, (ring_r, ring_r), ring_r, 2)
                        screen.blit(s, (cx - ring_r, cy - ring_r))
                pygame.draw.circle(screen, color, (cx, cy), base_radius)
            else:
                # Default circle
                pygame.draw.circle(screen, color, (cx, cy), base_radius)

            # Particles for woodwinds
            if soul.family == "woodwinds" and state.particle_count > 0:
                import random

                for _ in range(state.particle_count):
                    px = cx + random.randint(-30, 30)
                    py = cy + random.randint(-50, 0)
                    ps = random.randint(2, 4)
                    random.randint(50, 150)
                    pc = (*color[:3],)
                    pygame.draw.circle(screen, pc, (px, py), ps)

        # HUD — Minimal, elegant
        self._render_hud(screen, moment, time, font, title_font)

    def _render_hud(
        self,
        screen: Any,
        moment: MusicMoment,
        time: float,
        font: Any,
        title_font: Any,
    ) -> None:
        """Render the heads-up display."""
        import pygame

        # Title
        title = title_font.render("CARNEGIE HALL", True, (200, 195, 185))
        screen.blit(title, (40, 30))

        # Time
        mins = int(time // 60)
        secs = time % 60
        time_str = f"{mins}:{secs:05.2f}"
        time_label = font.render(time_str, True, (140, 135, 125))
        screen.blit(time_label, (self.width - 100, 35))

        # Dynamics indicator
        if moment.is_crescendo:
            dyn_str = "CRESCENDO ▲"
            dyn_color = (255, 200, 100)
        elif moment.is_diminuendo:
            dyn_str = "DIMINUENDO ▼"
            dyn_color = (100, 150, 255)
        else:
            dyn_str = ""
            dyn_color = (150, 150, 150)

        if dyn_str:
            dyn_label = font.render(dyn_str, True, dyn_color)
            screen.blit(dyn_label, (40, 65))

        # Energy meter (bottom left, vertical bar)
        bar_x = 40
        bar_y = self.height - 200
        bar_width = 8
        bar_height = 150

        # Background
        pygame.draw.rect(screen, (30, 30, 35), (bar_x, bar_y, bar_width, bar_height))

        # Fill
        fill_height = int(bar_height * moment.overall_energy)
        fill_y = bar_y + bar_height - fill_height

        # Gradient fill
        for i in range(fill_height):
            t = i / max(fill_height, 1)
            r = int(50 + t * 150)
            g = int(80 + t * 100)
            b = int(120 - t * 50)
            pygame.draw.line(
                screen,
                (r, g, b),
                (bar_x, fill_y + fill_height - i),
                (bar_x + bar_width, fill_y + fill_height - i),
            )

        energy_label = font.render("ENERGY", True, (100, 100, 105))
        screen.blit(energy_label, (bar_x - 5, bar_y + bar_height + 10))

        # Instructions
        hint = font.render("ESC to exit", True, (60, 60, 65))
        screen.blit(hint, (self.width - 100, self.height - 40))

    def _project(self, point: tuple[float, float, float]) -> tuple[int, int]:
        """Project 3D point to 2D screen coordinates."""
        x, y, z = point

        # Simple perspective projection
        # Camera looking at stage center from audience position
        cam_y = -self.camera_distance
        cam_z = self.camera_height

        # Relative position
        rel_y = y - cam_y
        rel_z = z - cam_z

        # Perspective division
        rel_y = max(rel_y, 0.1)

        scale = 800 / rel_y  # Focal length

        screen_x = self.width / 2 + x * scale
        screen_y = self.height / 2 - rel_z * scale + 100  # Offset down

        return int(screen_x), int(screen_y)


# =============================================================================
# MAIN ENTRY
# =============================================================================


async def visualize_carnegie_hall(
    audio_path: str | Path,
    width: int = 1920,
    height: int = 1080,
) -> None:
    """Play orchestral audio with Carnegie Hall 3D visualization.

    This is not a visualizer. This is the music made visible.

    Args:
        audio_path: Path to orchestral audio file
        width: Display width
        height: Display height
    """
    visualizer = CarnegieHallVisualizer(width, height)
    await visualizer.play_with_visualization(Path(audio_path))


def main() -> None:
    """Command-line entry point."""
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        description="Carnegie Hall Orchestra Visualizer — The Music Made Visible",
    )
    parser.add_argument("audio_file", type=Path, help="Path to audio file")
    parser.add_argument("-W", "--width", type=int, default=1920)
    parser.add_argument("-H", "--height", type=int, default=1080)

    args = parser.parse_args()

    if not args.audio_file.exists():
        sys.exit(1)

    logging.basicConfig(level=logging.INFO)
    asyncio.run(visualize_carnegie_hall(args.audio_file, args.width, args.height))


if __name__ == "__main__":
    main()
