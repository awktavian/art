# pyright: reportGeneralTypeIssues=false
"""Unified Spatial Audio Engine — Optimized for Tim's 5.1.4 System.

Tim's KEF Reference System:
- Front L/R: KEF Reference 5 Meta
- Center: PHANTOM (no physical speaker)
- Surround L/R: KEF Reference 1 Meta
- Height: 4x CI200RR-THX (Front Height + Rear Height)
- Subwoofers: 2x CI3160RLB-THX Extreme

Output Strategy:
- 8-channel PCM via HDMI to Denon AVR-A10H
- Denon Neural:X upmixes to 4 height speakers
- No signal to center channel (phantom imaging)

Neural:X Optimization:
- Front/rear balance encodes elevation
- High-shelf EQ on front for "up" cues
- Smooth trajectories with elevation variation
- Strong front bias for voice clarity

Architecture:
    TTS → Room Acoustics → 5.1 VBAP → 8ch PCM → Denon Neural:X → Height

Created: January 1, 2026
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

# Optional audio dependencies — graceful fallback for CI environments
try:
    import sounddevice as sd

    SOUNDDEVICE_AVAILABLE = True
except OSError:
    # PortAudio not installed (common in CI/Linux)
    sd = None  # type: ignore[assignment]
    SOUNDDEVICE_AVAILABLE = False

try:
    import soundfile as sf

    SOUNDFILE_AVAILABLE = True
except ImportError:
    sf = None  # type: ignore[assignment]
    SOUNDFILE_AVAILABLE = False

from scipy import signal

if TYPE_CHECKING:
    pass

# Binaural rendering for iOS/AirPods
try:
    from kagami.core.effectors.binaural_hrtf import (
        BinauralPosition,
        render_binaural_trajectory,
        save_ios_compatible,
    )

    BINAURAL_AVAILABLE = True
except ImportError:
    BINAURAL_AVAILABLE = False
    BinauralPosition = None  # type: ignore[assignment,misc]

logger = logging.getLogger(__name__)

# ============================================================================
# Constants — Optimized for Tim's 5.1.4 System
# ============================================================================

SAMPLE_RATE = 48000  # Denon preferred rate
NUM_CHANNELS = 8  # 7.1 PCM (but we use 5.1 + phantom center)

# Frame processing (tuned for smooth panning)
FRAME_SIZE_MS = 50  # 50ms frames
CROSSFADE_MS = 10  # 10ms crossfade overlap
POSITION_UPDATE_HZ = 30  # Position updates per second

# 7.1 Channel indices (SMPTE/ITU standard order)
CH_FL, CH_FR, CH_C, CH_LFE = 0, 1, 2, 3
CH_BL, CH_BR = 4, 5  # Tim uses these as Surround L/R (no back speakers)
CH_SL, CH_SR = 6, 7  # Side surrounds

# Tim's Speaker Layout (azimuth, elevation)
# His surrounds are in BL/BR positions (no separate side/back)
TIMS_SPEAKERS: dict[int, tuple[float, float]] = {
    CH_FL: (-30, 0),  # KEF Reference 5 Meta - Front Left
    CH_FR: (30, 0),  # KEF Reference 5 Meta - Front Right
    CH_C: (0, 0),  # PHANTOM - no signal here!
    CH_LFE: (0, -90),  # CI3160RLB-THX Extreme (bass managed)
    CH_BL: (-110, 0),  # KEF Reference 1 Meta - Surround Left
    CH_BR: (110, 0),  # KEF Reference 1 Meta - Surround Right
    CH_SL: (-110, 0),  # Unused (Tim has 5.1, not 7.1)
    CH_SR: (110, 0),  # Unused
}

# Neural:X Height Optimization
# When source is elevated, we bias front channels and add HF boost
# This gives Neural:X cues to upmix to Front Height speakers
NEURAL_X_HEIGHT_BIAS = 0.4  # How much to bias front for elevation
NEURAL_X_HF_BOOST_DB = 2.0  # High-frequency boost for elevation cue


class SpatialTarget(Enum):
    """Audio output target."""

    DENON_71 = "denon_5.1.4"  # Tim's system (via Neural:X)
    STEREO = "stereo"  # Basic stereo (no spatial)
    GLASSES = "glasses"  # Meta Ray-Ban spatial
    AIRPODS = "airpods"  # AirPods spatial audio (binaural HRTF)
    IOS = "ios"  # iOS device playback (binaural, head-tracking compatible)
    HEADPHONES = "headphones"  # Generic headphones (binaural HRTF)


@dataclass
class Position:
    """3D position in spherical coordinates."""

    azimuth: float = 0.0  # -180 to 180 degrees
    elevation: float = 0.0  # -90 to 90 degrees
    distance: float = 1.5  # meters

    def to_cartesian(self) -> np.ndarray:
        """Convert to Cartesian coordinates."""
        az = np.radians(self.azimuth)
        el = np.radians(self.elevation)
        return np.array(
            [
                np.cos(el) * np.cos(az),
                np.cos(el) * np.sin(az),
                np.sin(el),
            ]
        )


@dataclass
class RoomModel:
    """Acoustic room model."""

    name: str
    rt60: float = 0.3  # Reverb time (seconds)
    absorption: float = 0.6  # Surface absorption
    size: float = 5.0  # Characteristic dimension (m)
    early_reflection_ms: float = 12.0
    early_reflection_gain: float = 0.12


# Tim's Living Room acoustic model (KEF Reference system)
TIMS_LIVING_ROOM = RoomModel(
    name="Tim's Living Room",
    rt60=0.32,
    absorption=0.58,
    size=5.8,
    early_reflection_ms=12,
    early_reflection_gain=0.15,
)


@dataclass
class SpatialAudioConfig:
    """Configuration for spatial audio rendering."""

    # Neural:X settings
    enable_neural_x: bool = True
    neural_x_height_bias: float = NEURAL_X_HEIGHT_BIAS

    # Voice optimization
    voice_focus_front: bool = True  # Keep voice primarily in front
    voice_elevation_range: tuple[float, float] = (0, 35)  # Height range for voice

    # Phantom center
    use_phantom_center: bool = True  # No signal to center channel


@dataclass
class SpatialResult:
    """Result of spatial audio output."""

    success: bool
    target: SpatialTarget
    channels: int = 0
    duration_ms: float = 0
    error: str | None = None


# ============================================================================
# Core Processing — Optimized for Neural:X Height Upmixing
# ============================================================================


def compute_vbap_gains_5_1(pos: Position, config: SpatialAudioConfig | None = None) -> np.ndarray:
    """Compute VBAP gains optimized for Tim's 5.1.4 system.

    Key optimizations:
    1. NO center channel (phantom center from L/R)
    2. Front bias for elevated sounds (Neural:X height cue)
    3. Only uses FL, FR, BL, BR (Tim's actual speakers)

    Args:
        pos: 3D position
        config: Spatial configuration

    Returns:
        8-element gain array (but only FL, FR, BL, BR have signal)
    """
    config = config or SpatialAudioConfig()
    gains = np.zeros(NUM_CHANNELS, dtype=np.float32)

    # Normalize azimuth
    az = pos.azimuth
    while az > 180:
        az -= 360
    while az < -180:
        az += 360

    # Simple quadrant-based panning for 4-speaker system (FL, FR, BL, BR)
    # Tim's speakers: FL(-30°), FR(30°), BL(-110°), BR(110°)

    # Front/back factor (1 = full front, 0 = full back)
    # SOFTENED: Use sqrt(cos) for gentler front/back transition
    # This gives rear speakers more signal for front-arc content (orchestra)
    raw_cos = np.cos(np.radians(az))
    # Map -1..1 to 0..1, apply sqrt, then ensure minimum ambient level
    front_back_raw = 0.5 + 0.5 * raw_cos
    # Take sqrt for gentler curve, then ensure minimum 25% to rear
    front_back = 0.75 * np.sqrt(front_back_raw) + 0.25 * front_back_raw

    # Left/right factor (1 = full right, 0 = full left)
    left_right = 0.5 + 0.5 * np.sin(np.radians(az))

    # Base gains for 4 speakers
    gains[CH_FL] = front_back * (1 - left_right)
    gains[CH_FR] = front_back * left_right
    # Rear speakers get ambient contribution even for front sources
    # This simulates concert hall reflections
    rear_ambient = 0.25  # Minimum 25% signal to rear for envelopment
    gains[CH_BL] = max(rear_ambient * (1 - left_right), (1 - front_back) * (1 - left_right))
    gains[CH_BR] = max(rear_ambient * left_right, (1 - front_back) * left_right)

    # =========================================================================
    # Neural:X Height Optimization
    # =========================================================================
    # When elevation > 0, bias towards front channels
    # Neural:X interprets strong front with HF as "above" and upmixes to height

    if pos.elevation > 5:
        el_factor = min(pos.elevation / 45.0, 1.0)
        height_bias = config.neural_x_height_bias * el_factor

        # Boost front channels
        gains[CH_FL] *= 1.0 + height_bias
        gains[CH_FR] *= 1.0 + height_bias

        # Reduce rear channels
        gains[CH_BL] *= 1.0 - height_bias * 0.5
        gains[CH_BR] *= 1.0 - height_bias * 0.5

    elif pos.elevation < -5:
        # For below-horizon sounds, bias towards rear
        el_factor = min(abs(pos.elevation) / 45.0, 1.0)

        gains[CH_FL] *= 1.0 - el_factor * 0.3
        gains[CH_FR] *= 1.0 - el_factor * 0.3
        gains[CH_BL] *= 1.0 + el_factor * 0.2
        gains[CH_BR] *= 1.0 + el_factor * 0.2

    # NO CENTER CHANNEL - Tim uses phantom center
    gains[CH_C] = 0.0

    # Power normalization (constant loudness)
    total = np.sqrt(np.sum(gains**2))
    if total > 0.001:
        gains /= total

    # Distance attenuation - subtle for musical use
    # Use sqrt for gentler falloff: 1/sqrt(d) instead of 1/d
    # Also clamp to reasonable range for orchestral distances (2-15m)
    dist_atten = 1.0 / np.sqrt(max(1.0, pos.distance))
    gains *= dist_atten

    return gains


def apply_neural_x_elevation_eq(
    audio: np.ndarray,
    elevation: float,
    sample_rate: int = SAMPLE_RATE,
) -> np.ndarray:
    """Apply high-frequency boost for elevated sounds.

    Neural:X uses spectral cues - sounds with more HF content
    are perceived as "above" and upmixed to height speakers.
    """
    if elevation <= 5:
        return audio

    # Calculate boost amount based on elevation
    el_factor = min(elevation / 45.0, 1.0)
    boost_db = NEURAL_X_HF_BOOST_DB * el_factor
    boost_linear = 10 ** (boost_db / 20)

    # High-shelf filter at 3kHz
    # Creates the "above" perception that Neural:X uses
    nyquist = sample_rate / 2
    cutoff = min(3000 / nyquist, 0.95)

    b, a = signal.butter(1, cutoff, btype="high")
    high_freq = signal.lfilter(b, a, audio).astype(np.float32)

    # Mix boosted highs back in
    return audio + high_freq * (boost_linear - 1)


def apply_room_acoustics(
    audio: np.ndarray,
    pos: Position,
    room: RoomModel,
) -> np.ndarray:
    """Apply room acoustic simulation.

    NOTE: Distance attenuation is handled by compute_vbap_gains_5_1(),
    so we don't apply it here to avoid double-attenuation.
    """
    audio = audio.copy().astype(np.float32)

    # Apply Neural:X elevation EQ
    audio = apply_neural_x_elevation_eq(audio, pos.elevation)

    # NOTE: Distance attenuation removed - already in VBAP gains

    # Air absorption (roll off HF with distance)
    if pos.distance > 1.2:
        cutoff = max(4000, 14000 - (pos.distance - 1.2) * 3000)
        b, a = signal.butter(1, cutoff / (SAMPLE_RATE / 2), btype="low")
        audio = signal.lfilter(b, a, audio).astype(np.float32)

    # Early reflection
    delay = int(room.early_reflection_ms * SAMPLE_RATE / 1000)
    if delay > 0 and room.early_reflection_gain > 0:
        reflected = np.zeros(len(audio) + delay, dtype=np.float32)
        reflected[delay : delay + len(audio)] = (
            audio * room.early_reflection_gain * (1 - room.absorption)
        )
        audio = np.pad(audio, (0, delay))
        audio += reflected
        audio = audio[: len(audio) - delay // 2]

    return audio


def interpolate_gains(
    gains_start: np.ndarray,
    gains_end: np.ndarray,
    num_samples: int,
) -> np.ndarray:
    """Smoothly interpolate between two gain sets."""
    t = np.linspace(0, 1, num_samples).reshape(-1, 1)
    # Cosine interpolation for smooth transitions
    t_smooth = 0.5 * (1 - np.cos(t * np.pi))
    return gains_start + (gains_end - gains_start) * t_smooth


def downmix_stereo(multichannel: np.ndarray) -> np.ndarray:
    """Downmix to stereo (for non-Denon targets)."""
    n = len(multichannel)
    stereo = np.zeros((n, 2), dtype=np.float32)

    # Left (FL + BL contribution)
    stereo[:, 0] = (
        multichannel[:, CH_FL] * 1.0
        + multichannel[:, CH_BL] * 0.5
        + multichannel[:, CH_FR] * 0.15
        + multichannel[:, CH_LFE] * 0.3
    )

    # Right (FR + BR contribution)
    stereo[:, 1] = (
        multichannel[:, CH_FR] * 1.0
        + multichannel[:, CH_BR] * 0.5
        + multichannel[:, CH_FL] * 0.15
        + multichannel[:, CH_LFE] * 0.3
    )

    return stereo


# ============================================================================
# Trajectory Generation — FULL SPATIAL MOVEMENT
# ============================================================================


def generate_corkscrew(
    duration: float,
    revolutions: float = 1.5,
    fps: int = 60,
) -> list[tuple[float, Position]]:
    """Generate FULL 360° corkscrew - actually uses ALL speakers.

    Creates a spiral that:
    - Starts front-center
    - Rotates through ALL speakers (FL → FR → BR → BL → FL)
    - Rises and falls through elevation
    - Actually spatial - sound moves around the room
    """
    positions = []
    num_frames = int(duration * fps)

    for i in range(num_frames):
        t = i / max(num_frames - 1, 1)

        # FULL 360° rotation - linear sweep through all speakers
        # Multiply by revolutions for multiple rotations
        azimuth = -180 + 360 * t * revolutions
        while azimuth > 180:
            azimuth -= 360
        while azimuth < -180:
            azimuth += 360

        # Elevation: oscillate up/down as it rotates
        # Higher when at front, lower when at back
        elevation = (
            25 * np.sin(t * np.pi * 2 * revolutions) * (0.5 + 0.5 * np.cos(np.radians(azimuth)))
        )

        # Distance: closer at front, further at back
        distance = 1.3 + 0.4 * (1 - np.cos(np.radians(azimuth))) / 2

        positions.append((t * duration, Position(azimuth, elevation, distance)))

    return positions


def generate_orbit(
    duration: float,
    revolutions: float = 1.0,
    elevation: float = 15.0,
    distance: float = 1.5,
    fps: int = 60,
) -> list[tuple[float, Position]]:
    """Generate FULL 360° orbital trajectory - constant elevation.

    Linear rotation through all speakers at fixed height.
    """
    positions = []
    num_frames = int(duration * fps)

    for i in range(num_frames):
        t = i / max(num_frames - 1, 1)

        # Linear 360° sweep - no smoothing, hits all speakers evenly
        azimuth = -180 + 360 * t * revolutions
        while azimuth > 180:
            azimuth -= 360

        positions.append((t * duration, Position(azimuth, elevation, distance)))

    return positions


def generate_static(duration: float, pos: Position) -> list[tuple[float, Position]]:
    """Generate static position trajectory."""
    return [(t, pos) for t in np.linspace(0, duration, int(duration * 60))]


def generate_voice_presence(
    duration: float,
    fps: int = 60,
) -> list[tuple[float, Position]]:
    """Generate subtle voice trajectory - front-biased for speech clarity."""
    positions = []
    num_frames = int(duration * fps)

    for i in range(num_frames):
        t = i / max(num_frames - 1, 1)

        # Subtle azimuth drift (+/- 15°) - stays in front arc
        azimuth = 15 * np.sin(t * 2 * np.pi)

        # Gentle elevation for height engagement
        elevation = 10 + 10 * np.sin(t * np.pi)

        distance = 1.5

        positions.append((t * duration, Position(azimuth, elevation, distance)))

    return positions


# ============================================================================
# Spatial Earcons — Audio notification patterns
# ============================================================================


def generate_earcon_celebration(duration: float, fps: int = 60) -> list[tuple[float, Position]]:
    """CELEBRATION: Explosive bloom from center to all speakers.

    Pattern: Start center → expand outward in all directions → converge back
    Like fireworks - sound explodes from you and returns.
    """
    positions = []
    num_frames = int(duration * fps)

    for i in range(num_frames):
        t = i / max(num_frames - 1, 1)

        if t < 0.3:
            # Phase 1: Rapid expansion with rotation
            phase_t = t / 0.3
            azimuth = phase_t * 720  # 2 full rotations during expansion
            elevation = phase_t * 40  # Rise up
            distance = 0.8 + phase_t * 1.5  # Move outward
        elif t < 0.7:
            # Phase 2: Full spatial bloom - hit ALL corners
            phase_t = (t - 0.3) / 0.4
            # Spiral through all positions
            azimuth = 720 + phase_t * 360
            elevation = 40 - phase_t * 20  # Settle slightly
            distance = 2.3 - phase_t * 0.5
        else:
            # Phase 3: Converge back to center
            phase_t = (t - 0.7) / 0.3
            azimuth = 1080 + phase_t * 180
            elevation = 20 * (1 - phase_t)
            distance = 1.8 - phase_t * 0.8

        # Normalize azimuth
        while azimuth > 180:
            azimuth -= 360

        positions.append((t * duration, Position(azimuth, elevation, distance)))

    return positions


def generate_earcon_alert(duration: float, fps: int = 60) -> list[tuple[float, Position]]:
    """ALERT: Sharp ping from above, demands attention.

    Pattern: Drops from height to ear level, slight wobble.
    """
    positions = []
    num_frames = int(duration * fps)

    for i in range(num_frames):
        t = i / max(num_frames - 1, 1)

        # Start above, drop to ear level
        elevation = 60 * (1 - t**0.5)  # Fast drop, slow settle

        # Slight wobble left-right
        azimuth = 30 * np.sin(t * 4 * np.pi) * (1 - t)

        # Move closer as it descends
        distance = 2.0 - 0.5 * t

        positions.append((t * duration, Position(azimuth, elevation, distance)))

    return positions


def generate_earcon_notification(duration: float, fps: int = 60) -> list[tuple[float, Position]]:
    """NOTIFICATION: Gentle chime from side, non-intrusive.

    Pattern: Arrives from side-rear, crosses to opposite side.
    """
    positions = []
    num_frames = int(duration * fps)

    for i in range(num_frames):
        t = i / max(num_frames - 1, 1)

        # Cross from back-left to front-right
        azimuth = -120 + 180 * t

        # Subtle height variation
        elevation = 15 + 10 * np.sin(t * np.pi)

        # Constant distance
        distance = 1.8

        positions.append((t * duration, Position(azimuth, elevation, distance)))

    return positions


def generate_earcon_success(duration: float, fps: int = 60) -> list[tuple[float, Position]]:
    """SUCCESS: Rising sweep from below to above.

    Pattern: Starts low, sweeps upward with slight rotation.
    """
    positions = []
    num_frames = int(duration * fps)

    for i in range(num_frames):
        t = i / max(num_frames - 1, 1)

        # Rise from below to above
        elevation = -10 + 50 * t

        # Gentle spiral as it rises
        azimuth = 60 * np.sin(t * np.pi)

        # Move slightly closer
        distance = 2.0 - 0.3 * t

        positions.append((t * duration, Position(azimuth, elevation, distance)))

    return positions


def generate_earcon_error(duration: float, fps: int = 60) -> list[tuple[float, Position]]:
    """ERROR: Descending, slightly unsettling.

    Pattern: Falls from height with irregular wobble.
    """
    positions = []
    num_frames = int(duration * fps)

    for i in range(num_frames):
        t = i / max(num_frames - 1, 1)

        # Descend
        elevation = 40 * (1 - t)

        # Irregular wobble
        azimuth = 45 * np.sin(t * 6 * np.pi) * (1 - t * 0.5)

        # Move back slightly
        distance = 1.5 + 0.5 * t

        positions.append((t * duration, Position(azimuth, elevation, distance)))

    return positions


def generate_earcon_arrival(duration: float, fps: int = 60) -> list[tuple[float, Position]]:
    """ARRIVAL: Something/someone entering - from far to near.

    Pattern: Starts distant behind, approaches to front.
    """
    positions = []
    num_frames = int(duration * fps)

    for i in range(num_frames):
        t = i / max(num_frames - 1, 1)

        # Approach from behind
        azimuth = 180 * (1 - t)

        # Rise slightly as approaching
        elevation = 5 + 15 * np.sin(t * np.pi)

        # Move from far to close
        distance = 3.0 - 1.5 * t

        positions.append((t * duration, Position(azimuth, elevation, distance)))

    return positions


def generate_earcon_departure(duration: float, fps: int = 60) -> list[tuple[float, Position]]:
    """DEPARTURE: Something leaving - from near to far.

    Pattern: Starts at front, recedes to back.
    """
    positions = []
    num_frames = int(duration * fps)

    for i in range(num_frames):
        t = i / max(num_frames - 1, 1)

        # Recede to back
        azimuth = 180 * t

        # Slight descent
        elevation = 10 * (1 - t)

        # Move away
        distance = 1.5 + 1.5 * t

        positions.append((t * duration, Position(azimuth, elevation, distance)))

    return positions


# ============================================================================
# Unified Spatial Engine — Optimized for Tim's System
# ============================================================================


class UnifiedSpatialEngine:
    """Unified spatial audio engine for Tim's 5.1.4 KEF Reference system.

    Handles routing to:
    - Denon AVR-A10H (8ch PCM → Neural:X → 5.1.4 output)
    - Stereo fallback

    Key optimizations:
    - No center channel signal (phantom center)
    - Front bias for elevation (Neural:X height cues)
    - HF boost for elevated sounds
    - Smooth crossfaded panning
    """

    def __init__(
        self,
        room: RoomModel | None = None,
        config: SpatialAudioConfig | None = None,
    ):
        self.room = room or TIMS_LIVING_ROOM
        self.config = config or SpatialAudioConfig()
        self._denon_device: int | None = None
        self._initialized = False

    async def initialize(self) -> bool:
        """Initialize and detect audio devices."""
        if self._initialized:
            return True

        try:
            devices = sd.query_devices()
            for i, d in enumerate(devices):
                name = d.get("name", "")
                if "DENON" in name and d.get("max_output_channels", 0) >= 8:
                    self._denon_device = i
                    logger.info(f"✓ Found DENON-AVR at device {i} (8ch → Neural:X → 5.1.4)")
                    break

            self._initialized = True
            return True

        except Exception as e:
            logger.error(f"Spatial engine init failed: {e}")
            return False

    @property
    def has_denon(self) -> bool:
        """Check if Denon output is available."""
        return self._denon_device is not None

    async def _set_denon_neural_x(self) -> bool:
        """Set Denon to Neural:X mode for height upmixing.

        IMPORTANT: Only changes sound mode, never changes input source.
        Uses direct Denon connection to avoid SmartHome controller noise.

        Returns:
            True if Neural:X was set successfully
        """
        if not self.config.enable_neural_x:
            return False

        try:
            # Direct Denon connection for low-overhead Neural:X setting
            from kagami.core.security import get_secret

            denon_host = get_secret("denon_host")
            if not denon_host:
                return False

            # Send Neural:X command directly via telnet
            _reader, writer = await asyncio.wait_for(
                asyncio.open_connection(denon_host, 23),
                timeout=2.0,
            )
            writer.write(b"MSNEURAL:X\r")
            await writer.drain()
            writer.close()
            await writer.wait_closed()
            logger.info("✓ Denon: Neural:X mode")
            return True

        except TimeoutError:
            logger.debug("Denon connection timeout")
        except Exception as e:
            logger.debug(f"Could not set Denon Neural:X: {e}")

        return False

    async def play_spatial(
        self,
        audio_path: Path | str,
        trajectory: list[tuple[float, Position]] | None = None,
        target: SpatialTarget = SpatialTarget.DENON_71,
    ) -> SpatialResult:
        """Play audio with spatial positioning.

        Supports multiple output targets:
        - DENON_71: Tim's 5.1.4 system via Neural:X
        - AIRPODS/IOS/HEADPHONES: Binaural HRTF rendering
        - STEREO: Basic stereo downmix

        Pipeline for speakers:
        1. Load and resample audio
        2. Apply room acoustics + Neural:X EQ
        3. Render to 5.1 (phantom center) with VBAP
        4. Set Denon to Neural:X mode
        5. Output 8ch PCM via HDMI
        6. Denon upmixes to 4 height speakers

        Pipeline for headphones (iOS/AirPods):
        1. Load and resample audio
        2. Convert trajectory to binaural positions
        3. Apply HRTF convolution for each ear
        4. Output binaural stereo
        """
        if not self._initialized:
            await self.initialize()

        try:
            # Load audio
            mono, sr = sf.read(str(audio_path))
            if len(mono.shape) > 1:
                mono = mono.mean(axis=1)
            mono = mono.astype(np.float32)

            # Resample to 48kHz
            if sr != SAMPLE_RATE:
                mono = signal.resample(mono, int(len(mono) * SAMPLE_RATE / sr)).astype(np.float32)

            duration = len(mono) / SAMPLE_RATE

            # Default trajectory: subtle voice presence
            if trajectory is None:
                trajectory = generate_voice_presence(duration)

            # Route to appropriate renderer based on target
            if target == SpatialTarget.DENON_71 and self.has_denon:
                # Enable Neural:X for height upmixing
                await self._set_denon_neural_x()

                multichannel = self._render_5_1_4(mono, trajectory)
                await self._play_denon(multichannel)
                return SpatialResult(
                    success=True,
                    target=target,
                    channels=8,
                    duration_ms=duration * 1000,
                )

            elif target in (SpatialTarget.AIRPODS, SpatialTarget.IOS, SpatialTarget.HEADPHONES):
                # Binaural HRTF rendering for headphones
                if not BINAURAL_AVAILABLE:
                    logger.warning("Binaural rendering not available, falling back to stereo")
                    multichannel = self._render_5_1_4(mono, trajectory)
                    stereo = downmix_stereo(multichannel)
                    await self._play_stereo(stereo)
                    return SpatialResult(
                        success=True,
                        target=SpatialTarget.STEREO,
                        channels=2,
                        duration_ms=duration * 1000,
                    )

                # Convert speaker trajectory to binaural positions
                binaural_trajectory = [
                    (
                        t,
                        BinauralPosition(
                            azimuth=pos.azimuth, elevation=pos.elevation, distance=pos.distance
                        ),
                    )
                    for t, pos in trajectory
                ]

                # Render binaural audio
                stereo = render_binaural_trajectory(mono, binaural_trajectory)

                # Play through default stereo device
                await self._play_stereo(stereo)
                return SpatialResult(
                    success=True,
                    target=target,
                    channels=2,
                    duration_ms=duration * 1000,
                )

            else:
                # Stereo fallback (basic downmix, no spatialization)
                multichannel = self._render_5_1_4(mono, trajectory)
                stereo = downmix_stereo(multichannel)
                await self._play_stereo(stereo)
                return SpatialResult(
                    success=True,
                    target=SpatialTarget.STEREO,
                    channels=2,
                    duration_ms=duration * 1000,
                )

        except Exception as e:
            logger.error(f"Spatial playback failed: {e}")
            return SpatialResult(success=False, target=target, error=str(e))

    def _render_5_1_4(
        self,
        mono: np.ndarray,
        trajectory: list[tuple[float, Position]],
    ) -> np.ndarray:
        """Render mono to 5.1 multichannel for Neural:X upmixing.

        Optimized for Tim's system:
        - Uses FL, FR, BL, BR (no center, no SL/SR)
        - Front bias for elevation (Neural:X height cue)
        - Smooth per-sample gain interpolation (no complex overlap-add)
        """
        n_samples = len(mono)
        duration = n_samples / SAMPLE_RATE
        output = np.zeros((n_samples, NUM_CHANNELS), dtype=np.float32)

        # Pre-compute gains at regular intervals then interpolate
        # This avoids complex frame-based processing that causes pops
        num_keyframes = max(int(duration * POSITION_UPDATE_HZ), 2)
        keyframe_indices = np.linspace(0, n_samples - 1, num_keyframes).astype(int)

        # Compute gain keyframes
        keyframe_gains = []
        for idx in keyframe_indices:
            t = idx / n_samples
            traj_idx = min(int(t * len(trajectory)), len(trajectory) - 1)
            _, pos = trajectory[traj_idx]
            gains = compute_vbap_gains_5_1(pos, self.config)
            keyframe_gains.append(gains)

        keyframe_gains = np.array(keyframe_gains)  # [num_keyframes, 8]

        # Interpolate gains for every sample (smooth, no discontinuities)
        all_gains = np.zeros((n_samples, NUM_CHANNELS), dtype=np.float32)
        for ch in range(NUM_CHANNELS):
            all_gains[:, ch] = np.interp(
                np.arange(n_samples), keyframe_indices, keyframe_gains[:, ch]
            )

        # Apply room acoustics to entire signal at once
        # Use average position for room acoustics (it's subtle anyway)
        mid_idx = len(trajectory) // 2
        _, mid_pos = trajectory[mid_idx]
        processed = apply_room_acoustics(mono, mid_pos, self.room)

        # Room acoustics may extend the signal (convolution) - truncate to match
        if len(processed) > n_samples:
            processed = processed[:n_samples]
        elif len(processed) < n_samples:
            processed = np.pad(processed, (0, n_samples - len(processed)))

        # LFE filter
        b_lfe, a_lfe = signal.butter(2, 120 / (SAMPLE_RATE / 2), btype="low")
        lfe_signal = signal.lfilter(b_lfe, a_lfe, processed).astype(np.float32)

        # Apply gains per channel
        for ch in range(NUM_CHANNELS):
            if ch == CH_LFE:
                output[:, ch] = lfe_signal * 0.2
            elif ch in (CH_C, CH_SL, CH_SR):
                # No signal to center or unused side channels
                continue
            else:
                output[:, ch] = processed * all_gains[:, ch]

        # Gentle fade in/out to avoid clicks at boundaries
        fade_samples = min(int(SAMPLE_RATE * 0.01), n_samples // 4)  # 10ms fade
        if fade_samples > 0:
            fade_in = np.linspace(0, 1, fade_samples).reshape(-1, 1)
            fade_out = np.linspace(1, 0, fade_samples).reshape(-1, 1)
            output[:fade_samples] *= fade_in
            output[-fade_samples:] *= fade_out

        # Normalize
        peak = np.abs(output).max()
        if peak > 0.01:
            output = output / peak * 0.88

        return output

    async def _play_denon(self, multichannel: np.ndarray) -> None:
        """Play 8ch through Denon → Neural:X → 5.1.4."""
        sd.play(multichannel, samplerate=SAMPLE_RATE, device=self._denon_device)
        sd.wait()

    async def _play_stereo(self, stereo: np.ndarray) -> None:
        """Play stereo through default device."""
        sd.play(stereo, samplerate=SAMPLE_RATE)
        sd.wait()

    async def render_for_ios(
        self,
        audio_path: Path | str,
        output_path: Path | str,
        trajectory: list[tuple[float, Position]] | None = None,
    ) -> SpatialResult:
        """Render spatial audio to iOS-compatible binaural file.

        Creates a 48kHz 24-bit stereo WAV file with HRTF-based
        binaural spatialization. This file can be:
        - Played directly on iOS with AirPods
        - Enhanced by iOS "Spatialize Stereo" feature
        - Enhanced by personalized spatial audio profiles

        Args:
            audio_path: Input audio file (mono or stereo)
            output_path: Output WAV file path
            trajectory: Spatial trajectory (or None for voice presence)

        Returns:
            SpatialResult with success status
        """
        if not BINAURAL_AVAILABLE:
            return SpatialResult(
                success=False,
                target=SpatialTarget.IOS,
                error="Binaural rendering not available",
            )

        try:
            # Load audio
            mono, sr = sf.read(str(audio_path))
            if len(mono.shape) > 1:
                mono = mono.mean(axis=1)
            mono = mono.astype(np.float32)

            # Resample to 48kHz
            if sr != SAMPLE_RATE:
                mono = signal.resample(mono, int(len(mono) * SAMPLE_RATE / sr)).astype(np.float32)

            duration = len(mono) / SAMPLE_RATE

            # Default trajectory
            if trajectory is None:
                trajectory = generate_voice_presence(duration)

            # Convert to binaural positions
            binaural_trajectory = [
                (
                    t,
                    BinauralPosition(
                        azimuth=pos.azimuth, elevation=pos.elevation, distance=pos.distance
                    ),
                )
                for t, pos in trajectory
            ]

            # Render binaural
            stereo = render_binaural_trajectory(mono, binaural_trajectory)

            # Save iOS-compatible file
            save_ios_compatible(stereo, output_path)

            logger.info(f"✓ Rendered iOS spatial audio: {output_path}")
            return SpatialResult(
                success=True,
                target=SpatialTarget.IOS,
                channels=2,
                duration_ms=duration * 1000,
            )

        except Exception as e:
            logger.error(f"iOS render failed: {e}")
            return SpatialResult(success=False, target=SpatialTarget.IOS, error=str(e))

    async def play_multichannel_file(
        self,
        audio_path: Path | str,
        target: SpatialTarget = SpatialTarget.DENON_71,
    ) -> SpatialResult:
        """Play a pre-rendered multichannel audio file.

        Use this for files that are already spatialized (e.g., Orchestra output).
        Supports 8ch (7.1), 10ch (5.1.4), or stereo files.

        Args:
            audio_path: Path to multichannel audio file
            target: Output target (DENON_71 preferred for multichannel)

        Returns:
            SpatialResult with playback status
        """
        if not self._initialized:
            await self.initialize()

        try:
            # Load audio
            audio, sr = sf.read(str(audio_path))

            # Get channel count
            if len(audio.shape) == 1:
                channels = 1
            else:
                channels = audio.shape[1]

            duration = len(audio) / sr

            # Resample if needed
            if sr != SAMPLE_RATE:
                from scipy import signal as sig

                if channels == 1:
                    audio = sig.resample(audio, int(len(audio) * SAMPLE_RATE / sr))
                else:
                    # Resample each channel
                    new_len = int(audio.shape[0] * SAMPLE_RATE / sr)
                    resampled = np.zeros((new_len, channels), dtype=np.float32)
                    for ch in range(channels):
                        resampled[:, ch] = sig.resample(audio[:, ch], new_len)
                    audio = resampled

            audio = audio.astype(np.float32)

            # Route based on target and channel count
            if target == SpatialTarget.DENON_71 and self.has_denon:
                # Enable Neural:X for height upmixing (even for pre-rendered)
                await self._set_denon_neural_x()

                if channels == 10:
                    # 10ch (5.1.4 explicit) → Convert to 8ch for Denon
                    # Map: FL, FR, C, LFE, SL, SR, TFL, TFR, TRL, TRR
                    # To:  FL, FR, C, LFE, BL, BR, SL, SR (7.1)
                    # Fold heights into base layer - Neural:X will re-upmix
                    logger.info("🎵 Converting 10ch (5.1.4) → 8ch for Denon")
                    audio_8ch = np.zeros((len(audio), 8), dtype=np.float32)
                    # Direct copy: FL, FR, C, LFE
                    audio_8ch[:, 0] = audio[:, 0]  # FL
                    audio_8ch[:, 1] = audio[:, 1]  # FR
                    audio_8ch[:, 2] = audio[:, 2]  # C
                    audio_8ch[:, 3] = audio[:, 3]  # LFE
                    # Surrounds: SL/SR → BL/BR
                    audio_8ch[:, 4] = audio[:, 4]  # SL → BL
                    audio_8ch[:, 5] = audio[:, 5]  # SR → BR
                    # Fold heights into fronts (Neural:X will upmix back)
                    audio_8ch[:, 0] += audio[:, 6] * 0.5  # TFL → FL
                    audio_8ch[:, 1] += audio[:, 7] * 0.5  # TFR → FR
                    audio_8ch[:, 4] += audio[:, 8] * 0.5  # TRL → BL
                    audio_8ch[:, 5] += audio[:, 9] * 0.5  # TRR → BR
                    # Normalize to prevent clipping
                    peak = np.abs(audio_8ch).max()
                    if peak > 0.95:
                        audio_8ch *= 0.9 / peak
                    audio = audio_8ch
                    channels = 8

                if channels == 8:
                    # 8ch (7.1): play directly to Denon
                    logger.info(f"🎵 Playing {channels}ch spatial file to Denon")
                    sd.play(audio, samplerate=SAMPLE_RATE, device=self._denon_device)
                    sd.wait()
                elif channels == 2:
                    # Stereo: play through default (will be upmixed)
                    logger.info("🎵 Playing stereo file (Neural:X will upmix)")
                    sd.play(audio, samplerate=SAMPLE_RATE, device=self._denon_device)
                    sd.wait()
                else:
                    # Mono or other: convert to stereo
                    if channels == 1:
                        stereo = np.column_stack([audio, audio])
                    else:
                        stereo = audio[:, :2]
                    sd.play(stereo, samplerate=SAMPLE_RATE, device=self._denon_device)
                    sd.wait()

                return SpatialResult(
                    success=True,
                    target=target,
                    channels=channels,
                    duration_ms=duration * 1000,
                )
            else:
                # Stereo fallback
                if channels >= 8:
                    # Downmix multichannel to stereo
                    stereo = downmix_stereo(audio[:, :8])
                elif channels == 2:
                    stereo = audio
                else:
                    stereo = np.column_stack([audio[:, 0], audio[:, 0]])

                await self._play_stereo(stereo)
                return SpatialResult(
                    success=True,
                    target=SpatialTarget.STEREO,
                    channels=2,
                    duration_ms=duration * 1000,
                )

        except Exception as e:
            logger.error(f"Multichannel playback failed: {e}")
            return SpatialResult(success=False, target=target, error=str(e))


# ============================================================================
# Module-level API
# ============================================================================

_engine: UnifiedSpatialEngine | None = None


async def get_spatial_engine() -> UnifiedSpatialEngine:
    """Get or create the spatial audio engine singleton."""
    global _engine
    if _engine is None:
        _engine = UnifiedSpatialEngine()
        await _engine.initialize()
    return _engine


async def play_spatial(
    audio_path: Path | str,
    trajectory: list[tuple[float, Position]] | None = None,
    animate: str | None = None,
    duration: float | None = None,
) -> SpatialResult:
    """Play audio with spatial positioning.

    Args:
        audio_path: Path to audio file
        trajectory: Custom trajectory, or None for auto
        animate: Animation type ("corkscrew", "orbit", "voice", "static")
        duration: Audio duration (required if animate is set)

    Returns:
        SpatialResult
    """
    engine = await get_spatial_engine()

    # Generate trajectory from animation type
    if animate and duration:
        if animate == "corkscrew":
            trajectory = generate_corkscrew(duration, revolutions=1.5)
        elif animate == "orbit":
            trajectory = generate_orbit(duration, revolutions=1.0)
        elif animate == "voice":
            trajectory = generate_voice_presence(duration)
        # else: static (default)

    return await engine.play_spatial(audio_path, trajectory)


async def play_multichannel(audio_path: Path | str) -> SpatialResult:
    """Play a pre-rendered multichannel audio file.

    Use this for files that already have spatial positioning baked in,
    such as Orchestra output (10ch 5.1.4) or other pre-mixed content.

    Args:
        audio_path: Path to multichannel audio file (8ch, 10ch, or stereo)

    Returns:
        SpatialResult
    """
    engine = await get_spatial_engine()
    return await engine.play_multichannel_file(audio_path)


async def play_spatial_headphones(
    audio_path: Path | str,
    trajectory: list[tuple[float, Position]] | None = None,
) -> SpatialResult:
    """Play spatial audio optimized for headphones (AirPods, etc).

    Uses binaural HRTF rendering for 3D audio on headphones.
    Compatible with iOS spatial audio and AirPods head tracking.

    Args:
        audio_path: Path to audio file
        trajectory: Spatial trajectory (or None for auto)

    Returns:
        SpatialResult
    """
    engine = await get_spatial_engine()
    return await engine.play_spatial(audio_path, trajectory, target=SpatialTarget.AIRPODS)


async def render_ios_spatial(
    audio_path: Path | str,
    output_path: Path | str,
    trajectory: list[tuple[float, Position]] | None = None,
) -> SpatialResult:
    """Render spatial audio to iOS-compatible file.

    Creates a binaural stereo file (48kHz 24-bit WAV) that:
    - Works with iOS Spatial Audio
    - Compatible with AirPods head tracking
    - Can be enhanced by personalized spatial audio profiles

    Args:
        audio_path: Input audio file
        output_path: Output WAV file path
        trajectory: Spatial trajectory (or None for voice presence)

    Returns:
        SpatialResult
    """
    engine = await get_spatial_engine()
    return await engine.render_for_ios(audio_path, output_path, trajectory)


__all__ = [
    "BINAURAL_AVAILABLE",
    "CH_BL",
    "CH_BR",
    "CH_C",
    "CH_FL",
    "CH_FR",
    "CH_LFE",
    "CH_SL",
    "CH_SR",
    "NUM_CHANNELS",
    "SAMPLE_RATE",
    "TIMS_LIVING_ROOM",
    "TIMS_SPEAKERS",
    "Position",
    "RoomModel",
    "SpatialAudioConfig",
    "SpatialResult",
    "SpatialTarget",
    "UnifiedSpatialEngine",
    "apply_neural_x_elevation_eq",
    "apply_room_acoustics",
    "compute_vbap_gains_5_1",
    "downmix_stereo",
    "generate_corkscrew",
    "generate_earcon_alert",
    "generate_earcon_arrival",
    "generate_earcon_celebration",
    "generate_earcon_departure",
    "generate_earcon_error",
    "generate_earcon_notification",
    "generate_earcon_success",
    "generate_orbit",
    "generate_static",
    "generate_voice_presence",
    "get_spatial_engine",
    "interpolate_gains",
    "play_multichannel",
    "play_spatial",
    "play_spatial_headphones",
    "render_ios_spatial",
]
