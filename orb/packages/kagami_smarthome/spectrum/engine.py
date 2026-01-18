"""Spectrum Engine — Unified Music-Light Frequency Mapping.

LIGHT IS MUSIC IS SPECTRUM.

This engine creates a unified frequency space where:
- Sound frequencies (20Hz-20kHz) map to visible light (380nm-700nm)
- Musical dynamics map to light brightness
- Musical articulation maps to light patterns
- Musical phrasing maps to light timing
- Musical mood maps to color temperature

The visible spectrum is log-scaled to match human perception of both
sound (octaves) and light (color perception is logarithmic).

Frequency Mapping (logarithmic):
    Sub-bass    (20-60 Hz)     → Deep Red      (700nm, warm)
    Bass        (60-250 Hz)    → Red-Orange    (620nm)
    Low-mid     (250-500 Hz)   → Orange-Yellow (580nm)
    Mid         (500-2k Hz)    → Green         (520nm, center)
    Upper-mid   (2k-4k Hz)     → Cyan          (490nm)
    Presence    (4k-8k Hz)     → Blue          (450nm)
    Brilliance  (8k-20k Hz)    → Violet        (400nm, cool)

The mapping preserves the physics: both are electromagnetic waves,
differing only in frequency by ~10^12 orders of magnitude.

Created: January 3, 2026
h(x) >= 0 always.
"""

from __future__ import annotations

import colorsys
import logging
import math
from dataclasses import dataclass, field
from enum import Enum

import numpy as np

logger = logging.getLogger(__name__)


# =============================================================================
# Constants: The Unified Spectrum
# =============================================================================

# Audio frequency bands (Hz) - matches MixAnalyzer
AUDIO_BANDS = {
    "sub_bass": (20, 60),
    "bass": (60, 250),
    "low_mid": (250, 500),
    "mid": (500, 2000),
    "upper_mid": (2000, 4000),
    "presence": (4000, 8000),
    "brilliance": (8000, 20000),
}

# Visible light wavelengths (nm) - human visible spectrum
LIGHT_SPECTRUM = {
    "deep_red": 700,
    "red": 650,
    "orange": 600,
    "yellow": 580,
    "green": 520,
    "cyan": 490,
    "blue": 450,
    "violet": 400,
}

# Audio band → Hue mapping (0-360 HSV hue wheel)
# Low frequencies = warm (red/orange), high = cool (blue/violet)
BAND_HUE_MAP = {
    "sub_bass": 0,  # Deep red
    "bass": 20,  # Red-orange
    "low_mid": 40,  # Orange-yellow
    "mid": 120,  # Green (spectrum center)
    "upper_mid": 180,  # Cyan
    "presence": 220,  # Blue
    "brilliance": 270,  # Violet
}

# Musical key → Color temperature shift
# Major keys warm, minor keys cool, chromatic = full spectrum
KEY_COLOR_SHIFT = {
    "C": 0,
    "C#": 30,
    "D": 60,
    "D#": 90,
    "E": 120,
    "F": 150,
    "F#": 180,
    "G": 210,
    "G#": 240,
    "A": 270,
    "A#": 300,
    "B": 330,
}

# Mode modifier (major = warm shift, minor = cool shift)
MODE_SHIFT = {
    "major": -20,  # Warmer (toward red)
    "minor": +40,  # Cooler (toward blue)
    "diminished": +60,  # Very cool
    "augmented": -40,  # Very warm
    "dorian": +20,
    "phrygian": +50,
    "lydian": -30,
    "mixolydian": -10,
}


class PatternType(Enum):
    """Oelo pattern types mapped from musical articulation."""

    STATIONARY = "stationary"  # Sustained, legato
    FADE = "fade"  # Slow dynamics
    MARCH = "march"  # Rhythmic, walking
    CHASE = "chase"  # Fast, energetic
    TWINKLE = "twinkle"  # Staccato, pizzicato
    RIVER = "river"  # Flowing, smooth
    BOLT = "bolt"  # Sharp attacks
    SPARKLE = "sparkle"  # Delicate tremolo


class MusicMood(Enum):
    """Musical mood categories."""

    PEACEFUL = "peaceful"  # pp-p, slow, legato
    GENTLE = "gentle"  # p-mp, moderate, smooth
    NEUTRAL = "neutral"  # mf, balanced
    ENERGETIC = "energetic"  # f, fast, rhythmic
    DRAMATIC = "dramatic"  # ff, large dynamics
    INTENSE = "intense"  # fff, very fast, sharp


# =============================================================================
# Data Types
# =============================================================================


@dataclass
class FrequencyBalance:
    """Audio frequency band energy distribution (from MixAnalyzer)."""

    sub_bass: float = 0.0  # 20-60 Hz
    bass: float = 0.0  # 60-250 Hz
    low_mid: float = 0.0  # 250-500 Hz
    mid: float = 0.0  # 500-2000 Hz
    upper_mid: float = 0.0  # 2000-4000 Hz
    presence: float = 0.0  # 4000-8000 Hz
    brilliance: float = 0.0  # 8000-20000 Hz

    def as_array(self) -> np.ndarray:
        """Return as numpy array for calculations."""
        return np.array(
            [
                self.sub_bass,
                self.bass,
                self.low_mid,
                self.mid,
                self.upper_mid,
                self.presence,
                self.brilliance,
            ]
        )

    def dominant_band(self) -> str:
        """Get the dominant frequency band."""
        bands = list(AUDIO_BANDS.keys())
        values = self.as_array()
        return bands[int(np.argmax(values))]

    def centroid_hue(self) -> float:
        """Calculate weighted centroid hue from frequency balance."""
        hues = np.array(list(BAND_HUE_MAP.values()))
        weights = self.as_array()
        # Normalize weights
        if weights.sum() > 0:
            weights = weights / weights.sum()
        # Weighted circular mean for hue
        x = np.sum(weights * np.cos(np.radians(hues)))
        y = np.sum(weights * np.sin(np.radians(hues)))
        centroid = np.degrees(np.arctan2(y, x)) % 360
        return centroid


@dataclass
class MusicalContext:
    """Complete musical context for spectrum mapping."""

    # Audio analysis
    frequency_balance: FrequencyBalance | None = None

    # Musical elements
    tempo_bpm: float = 120.0
    key: str = "C"  # C, D, E, F, G, A, B (with #/b)
    mode: str = "major"  # major, minor, etc.

    # Dynamics (0-1 normalized from MIDI velocity/LUFS)
    dynamics: float = 0.5  # 0=pp, 0.5=mf, 1=ff
    dynamics_range: float = 0.3  # Dynamic contrast

    # Articulation
    articulation: str = "legato"  # legato, staccato, marcato, etc.
    note_density: float = 0.5  # Notes per beat (normalized)

    # Phrasing
    phrase_position: float = 0.5  # 0=start, 0.5=middle, 1=peak
    phrase_length: float = 4.0  # Bars

    # Mood (derived or explicit)
    mood: MusicMood | None = None


@dataclass
class SpectrumOutput:
    """Output of spectrum engine — ready for Oelo."""

    # Primary color (HSV)
    hue: float  # 0-360
    saturation: float  # 0-1
    brightness: float  # 0-1

    # Secondary colors for patterns
    colors: list[tuple[int, int, int]] = field(default_factory=list)  # RGB tuples

    # Pattern
    pattern: PatternType = PatternType.STATIONARY
    speed: int = 5  # 1-20, Oelo speed

    # Timing
    transition_ms: int = 500  # Transition time between states

    # Metadata
    mood: MusicMood = MusicMood.NEUTRAL
    dominant_band: str = "mid"

    def primary_rgb(self) -> tuple[int, int, int]:
        """Convert primary HSV to RGB."""
        r, g, b = colorsys.hsv_to_rgb(self.hue / 360, self.saturation, self.brightness)
        return (int(r * 255), int(g * 255), int(b * 255))


# =============================================================================
# Spectrum Engine
# =============================================================================


class SpectrumEngine:
    """Unified Music-Light Spectrum Mapping Engine.

    Maps musical features to light parameters in a unified frequency space.

    Usage:
        engine = SpectrumEngine()
        context = MusicalContext(tempo_bpm=90, key="Am", dynamics=0.7)
        output = engine.compute(context)
        # output.primary_rgb() → (R, G, B)
        # output.pattern → PatternType.FADE
    """

    def __init__(self) -> None:
        """Initialize spectrum engine."""
        self._last_output: SpectrumOutput | None = None
        self._smoothing = 0.3  # Temporal smoothing factor

    def compute(self, context: MusicalContext) -> SpectrumOutput:
        """Compute light output from musical context.

        Args:
            context: Complete musical context

        Returns:
            SpectrumOutput ready for Oelo control
        """
        # 1. Determine base hue from frequency balance or key
        if context.frequency_balance:
            base_hue = context.frequency_balance.centroid_hue()
        else:
            base_hue = self._key_to_hue(context.key, context.mode)

        # 2. Apply mood-based hue shift
        mood = context.mood or self._infer_mood(context)
        hue = self._apply_mood_shift(base_hue, mood)

        # 3. Calculate saturation from dynamics contrast
        saturation = self._dynamics_to_saturation(context.dynamics, context.dynamics_range)

        # 4. Calculate brightness from dynamics level
        brightness = self._dynamics_to_brightness(context.dynamics)

        # 5. Determine pattern from articulation and tempo
        pattern = self._articulation_to_pattern(context.articulation, context.tempo_bpm)

        # 6. Calculate pattern speed from tempo
        speed = self._tempo_to_speed(context.tempo_bpm, pattern)

        # 7. Generate color palette for patterns
        colors = self._generate_palette(hue, saturation, brightness, mood)

        # 8. Calculate transition timing from phrase
        transition_ms = self._phrase_to_transition(context.phrase_position, context.tempo_bpm)

        # Build output
        output = SpectrumOutput(
            hue=hue,
            saturation=saturation,
            brightness=brightness,
            colors=colors,
            pattern=pattern,
            speed=speed,
            transition_ms=transition_ms,
            mood=mood,
            dominant_band=(
                context.frequency_balance.dominant_band() if context.frequency_balance else "mid"
            ),
        )

        # Apply temporal smoothing
        if self._last_output:
            output = self._smooth_transition(self._last_output, output)
        self._last_output = output

        return output

    def compute_from_audio(
        self, frequency_balance: FrequencyBalance, lufs: float
    ) -> SpectrumOutput:
        """Quick compute from audio analysis only.

        Args:
            frequency_balance: 7-band frequency analysis
            lufs: Integrated loudness (typically -30 to 0)

        Returns:
            SpectrumOutput for Oelo
        """
        # Convert LUFS to dynamics (0-1)
        # -30 LUFS = very quiet (0), -10 LUFS = very loud (1)
        dynamics = max(0.0, min(1.0, (lufs + 30) / 20))

        context = MusicalContext(
            frequency_balance=frequency_balance,
            dynamics=dynamics,
        )
        return self.compute(context)

    def compute_from_midi(
        self,
        tempo_bpm: float,
        key: str = "C",
        mode: str = "major",
        avg_velocity: int = 80,
        note_density: float = 0.5,
        articulation: str = "legato",
    ) -> SpectrumOutput:
        """Quick compute from MIDI analysis.

        Args:
            tempo_bpm: Tempo in BPM
            key: Musical key (C, D, E, F, G, A, B with #/b)
            mode: Mode (major, minor, etc.)
            avg_velocity: Average MIDI velocity (0-127)
            note_density: Notes per beat (normalized 0-1)
            articulation: Detected articulation

        Returns:
            SpectrumOutput for Oelo
        """
        dynamics = avg_velocity / 127.0

        context = MusicalContext(
            tempo_bpm=tempo_bpm,
            key=key,
            mode=mode,
            dynamics=dynamics,
            note_density=note_density,
            articulation=articulation,
        )
        return self.compute(context)

    # =========================================================================
    # Internal Mapping Functions
    # =========================================================================

    def _key_to_hue(self, key: str, mode: str) -> float:
        """Convert musical key to base hue."""
        # Extract root note
        root = key[0].upper()
        if len(key) > 1 and key[1] in "#b":
            root = key[:2]

        # Base hue from key
        base_hue = KEY_COLOR_SHIFT.get(root.replace("b", "#"), 0)

        # Mode shift
        mode_shift = MODE_SHIFT.get(mode.lower(), 0)

        return (base_hue + mode_shift) % 360

    def _apply_mood_shift(self, base_hue: float, mood: MusicMood) -> float:
        """Apply mood-based hue adjustment."""
        shifts = {
            MusicMood.PEACEFUL: 30,  # Toward blue
            MusicMood.GENTLE: 15,
            MusicMood.NEUTRAL: 0,
            MusicMood.ENERGETIC: -20,  # Toward red
            MusicMood.DRAMATIC: -30,
            MusicMood.INTENSE: -40,
        }
        return (base_hue + shifts.get(mood, 0)) % 360

    def _infer_mood(self, context: MusicalContext) -> MusicMood:
        """Infer mood from musical context."""
        tempo = context.tempo_bpm
        dynamics = context.dynamics
        density = context.note_density

        # Decision tree based on tempo and dynamics
        if tempo < 60 and dynamics < 0.3:
            return MusicMood.PEACEFUL
        elif tempo < 80 and dynamics < 0.5:
            return MusicMood.GENTLE
        elif tempo > 140 and dynamics > 0.7:
            return MusicMood.INTENSE
        elif tempo > 120 and dynamics > 0.6:
            return MusicMood.DRAMATIC
        elif tempo > 100 and density > 0.6:
            return MusicMood.ENERGETIC
        else:
            return MusicMood.NEUTRAL

    def _dynamics_to_saturation(self, dynamics: float, contrast: float) -> float:
        """Map dynamics to color saturation."""
        # Higher dynamics = more saturation
        # More contrast = more saturation variance
        base = 0.5 + (dynamics * 0.5)  # 0.5-1.0
        variance = contrast * 0.3
        return max(0.4, min(1.0, base + variance))

    def _dynamics_to_brightness(self, dynamics: float) -> float:
        """Map dynamics to light brightness."""
        # pp=0.2, p=0.4, mp=0.5, mf=0.6, f=0.8, ff=1.0
        return 0.2 + (dynamics * 0.8)

    def _articulation_to_pattern(self, articulation: str, tempo: float) -> PatternType:
        """Map articulation to Oelo pattern type."""
        art_lower = articulation.lower()

        if art_lower in ("legato", "sustained", "tenuto"):
            return PatternType.FADE if tempo < 80 else PatternType.RIVER
        elif art_lower in ("staccato", "pizzicato", "spiccato"):
            return PatternType.TWINKLE if tempo < 100 else PatternType.SPARKLE
        elif art_lower in ("marcato", "accent", "sforzando"):
            return PatternType.BOLT if tempo > 120 else PatternType.MARCH
        elif art_lower in ("tremolo", "trill"):
            return PatternType.SPARKLE
        else:
            # Default based on tempo
            if tempo < 70:
                return PatternType.FADE
            elif tempo < 100:
                return PatternType.RIVER
            elif tempo < 130:
                return PatternType.MARCH
            else:
                return PatternType.CHASE

    def _tempo_to_speed(self, tempo: float, pattern: PatternType) -> int:
        """Map tempo to Oelo pattern speed (1-20)."""
        # Normalize tempo to speed
        # 40 BPM = speed 1, 200 BPM = speed 20
        base_speed = int((tempo - 40) / 8) + 1
        base_speed = max(1, min(20, base_speed))

        # Pattern-specific adjustments
        if pattern in (PatternType.FADE, PatternType.STATIONARY):
            return max(1, base_speed // 2)
        elif pattern in (PatternType.BOLT, PatternType.SPARKLE):
            return min(20, base_speed + 3)
        else:
            return base_speed

    def _generate_palette(
        self,
        hue: float,
        saturation: float,
        brightness: float,
        mood: MusicMood,
    ) -> list[tuple[int, int, int]]:
        """Generate color palette for patterns."""

        def hsv_to_rgb(h: float, s: float, v: float) -> tuple[int, int, int]:
            r, g, b = colorsys.hsv_to_rgb(h / 360, s, v)
            return (int(r * 255), int(g * 255), int(b * 255))

        colors = [hsv_to_rgb(hue, saturation, brightness)]

        # Add complementary/analogous colors based on mood
        if mood in (MusicMood.DRAMATIC, MusicMood.INTENSE):
            # High contrast: complementary
            colors.append(hsv_to_rgb((hue + 180) % 360, saturation, brightness * 0.8))
            colors.append(hsv_to_rgb((hue + 90) % 360, saturation * 0.7, brightness * 0.6))
        elif mood in (MusicMood.ENERGETIC,):
            # Triadic harmony
            colors.append(hsv_to_rgb((hue + 120) % 360, saturation * 0.9, brightness * 0.9))
            colors.append(hsv_to_rgb((hue + 240) % 360, saturation * 0.8, brightness * 0.8))
        elif mood in (MusicMood.PEACEFUL, MusicMood.GENTLE):
            # Analogous harmony (close hues)
            colors.append(hsv_to_rgb((hue + 30) % 360, saturation * 0.7, brightness * 0.8))
            colors.append(hsv_to_rgb((hue - 30) % 360, saturation * 0.6, brightness * 0.6))
        else:
            # Split complementary
            colors.append(hsv_to_rgb((hue + 150) % 360, saturation * 0.8, brightness * 0.7))
            colors.append(hsv_to_rgb((hue + 210) % 360, saturation * 0.7, brightness * 0.6))

        return colors

    def _phrase_to_transition(self, phrase_position: float, tempo: float) -> int:
        """Calculate transition timing from phrase position."""
        # Faster transitions at phrase boundaries, slower at peaks
        # Base on one beat duration
        beat_ms = int(60000 / tempo)

        if phrase_position < 0.2 or phrase_position > 0.9:
            # Phrase boundary: quick transition
            return beat_ms // 2
        elif 0.4 < phrase_position < 0.7:
            # Peak: hold longer
            return beat_ms * 2
        else:
            return beat_ms

    def _smooth_transition(self, prev: SpectrumOutput, curr: SpectrumOutput) -> SpectrumOutput:
        """Apply temporal smoothing between states."""
        alpha = self._smoothing

        # Smooth hue (circular interpolation)
        hue_diff = curr.hue - prev.hue
        if abs(hue_diff) > 180:
            hue_diff = hue_diff - 360 * np.sign(hue_diff)
        smoothed_hue = (prev.hue + alpha * hue_diff) % 360

        # Smooth saturation and brightness linearly
        smoothed_sat = prev.saturation + alpha * (curr.saturation - prev.saturation)
        smoothed_bright = prev.brightness + alpha * (curr.brightness - prev.brightness)

        return SpectrumOutput(
            hue=smoothed_hue,
            saturation=smoothed_sat,
            brightness=smoothed_bright,
            colors=curr.colors,  # Don't smooth palette
            pattern=curr.pattern,  # Instant pattern change
            speed=curr.speed,
            transition_ms=curr.transition_ms,
            mood=curr.mood,
            dominant_band=curr.dominant_band,
        )


# =============================================================================
# Convenience Functions
# =============================================================================


def frequency_to_hue(frequency_hz: float) -> float:
    """Map audio frequency to hue.

    Uses logarithmic scale matching human perception.
    20Hz → Red (0°), 20kHz → Violet (270°)
    """
    if frequency_hz <= 20:
        return 0  # Red
    if frequency_hz >= 20000:
        return 270  # Violet

    # Log scale: 10 octaves from 20Hz to 20kHz
    log_freq = math.log2(frequency_hz / 20)  # 0-10
    normalized = log_freq / 10  # 0-1

    # Map to hue (red=0 to violet=270)
    return normalized * 270


def hue_to_wavelength(hue: float) -> float:
    """Map HSV hue to approximate wavelength (nm).

    Red (0°) → 700nm, Violet (270°) → 400nm
    """
    # Clamp to valid range
    hue = hue % 360
    if hue > 270:
        hue = 270

    # Linear interpolation (inverse of frequency-to-hue)
    normalized = hue / 270  # 0-1
    wavelength = 700 - (normalized * 300)  # 700-400nm

    return wavelength


# Global singleton
_spectrum_engine: SpectrumEngine | None = None


def get_spectrum_engine() -> SpectrumEngine:
    """Get or create global spectrum engine."""
    global _spectrum_engine
    if _spectrum_engine is None:
        _spectrum_engine = SpectrumEngine()
    return _spectrum_engine


__all__ = [
    "FrequencyBalance",
    "MusicMood",
    "MusicalContext",
    "PatternType",
    "SpectrumEngine",
    "SpectrumOutput",
    "frequency_to_hue",
    "get_spectrum_engine",
    "hue_to_wavelength",
]
