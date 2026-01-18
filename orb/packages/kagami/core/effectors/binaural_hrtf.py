# pyright: reportGeneralTypeIssues=false
"""Binaural HRTF Rendering — iOS/AirPods Spatial Audio Support.

Provides binaural (headphone-compatible) spatial audio rendering using
Head-Related Transfer Functions (HRTFs). This enables spatial audio
playback on iOS devices with AirPods and other headphones.

Apple Spatial Audio Compatibility:
    - Outputs binaural stereo that works with iOS "Spatialize Stereo"
    - Compatible with AirPods head tracking (sound anchored to device)
    - Works with personalized spatial audio profiles

HRTF Database:
    Uses built-in synthetic HRTF based on spherical head model.
    For production, can load MIT KEMAR or CIPIC database.

Architecture:
    Position → HRTF Lookup → Convolution → Binaural Stereo
                                    ↓
                              iOS/AirPods

Created: January 6, 2026
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
from numpy.typing import NDArray
from scipy import signal

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Constants
SAMPLE_RATE = 48000
HRTF_LENGTH = 128  # HRIR filter length (samples)
SPEED_OF_SOUND = 343.0  # m/s at 20°C
HEAD_RADIUS = 0.0875  # meters (average human head)


@dataclass(frozen=True)
class BinauralPosition:
    """Position for binaural rendering."""

    azimuth: float = 0.0  # -180 to 180, 0=front, positive=right
    elevation: float = 0.0  # -90 to 90, positive=up
    distance: float = 1.5  # meters


@dataclass
class BinauralConfig:
    """Configuration for binaural rendering."""

    # HRTF settings
    use_hrtf: bool = True
    hrtf_database: str = "synthetic"  # "synthetic", "kemar", "cipic"

    # ITD/ILD settings (used when HRTF disabled)
    enable_itd: bool = True  # Interaural Time Difference
    enable_ild: bool = True  # Interaural Level Difference

    # Distance simulation
    enable_distance_attenuation: bool = True
    enable_air_absorption: bool = True

    # Head tracking compatibility (for iOS)
    anchor_to_device: bool = True  # Sound anchored to device position

    # Quality settings
    crossfade_ms: float = 10.0  # Crossfade between position updates
    update_rate_hz: float = 60.0  # Position update rate


# =============================================================================
# Synthetic HRTF Generation (Spherical Head Model)
# =============================================================================


def _woodworth_itd(azimuth: float, head_radius: float = HEAD_RADIUS) -> float:
    """Calculate ITD using Woodworth formula.

    Based on spherical head model. More accurate than simple sin model.

    Args:
        azimuth: Azimuth in degrees (-180 to 180)
        head_radius: Head radius in meters

    Returns:
        ITD in seconds (positive = right ear leads)
    """
    az_rad = math.radians(azimuth)

    if abs(azimuth) <= 90:
        # Front hemisphere
        itd = (head_radius / SPEED_OF_SOUND) * (az_rad + math.sin(az_rad))
    else:
        # Back hemisphere
        if azimuth > 0:
            itd = (head_radius / SPEED_OF_SOUND) * (math.pi - az_rad + math.sin(az_rad))
        else:
            itd = (head_radius / SPEED_OF_SOUND) * (-math.pi - az_rad + math.sin(az_rad))

    return itd


def _calculate_ild(azimuth: float, elevation: float, frequency: float = 3000.0) -> float:
    """Calculate frequency-dependent ILD.

    Based on spherical head model with frequency-dependent shadowing.

    Args:
        azimuth: Azimuth in degrees
        elevation: Elevation in degrees
        frequency: Frequency in Hz (ILD is frequency-dependent)

    Returns:
        ILD in dB (positive = right ear louder)
    """
    az_rad = math.radians(azimuth)
    el_rad = math.radians(elevation)

    # Head shadowing increases with frequency
    # Below ~500Hz, ILD is minimal
    # Above ~3kHz, ILD can be 10-15dB
    freq_factor = min(1.0, max(0.0, (frequency - 500) / 2500))

    # Basic ILD from azimuth (sine model with elevation reduction)
    ild_base = 10.0 * math.sin(az_rad) * math.cos(el_rad)

    return ild_base * freq_factor


@lru_cache(maxsize=512)
def _generate_synthetic_hrir(
    azimuth: float,
    elevation: float,
    length: int = HRTF_LENGTH,
) -> tuple[NDArray, NDArray]:
    """Generate synthetic HRIR pair using spherical head model.

    Creates left and right ear impulse responses based on:
    1. ITD (Interaural Time Difference) - delay modeling
    2. ILD (Interaural Level Difference) - level modeling
    3. Spectral shaping - head/pinna filtering

    Args:
        azimuth: Azimuth in degrees
        elevation: Elevation in degrees
        length: HRIR length in samples

    Returns:
        (left_hrir, right_hrir) as numpy arrays
    """
    # Calculate ITD
    itd = _woodworth_itd(azimuth)
    itd_samples = int(abs(itd) * SAMPLE_RATE)

    # Create base impulse
    left_hrir = np.zeros(length, dtype=np.float32)
    right_hrir = np.zeros(length, dtype=np.float32)

    # Apply ITD (delay to far ear)
    if itd >= 0:
        # Sound from right: delay left ear
        left_delay = min(itd_samples, length - 1)
        right_delay = 0
    else:
        # Sound from left: delay right ear
        left_delay = 0
        right_delay = min(itd_samples, length - 1)

    # Create impulse with spectral shaping (lowpass for far ear = head shadow)
    # This simulates frequency-dependent head shadowing
    impulse = np.zeros(length, dtype=np.float32)
    impulse[0] = 1.0

    # Calculate ILD
    ild_db = _calculate_ild(azimuth, elevation)
    ild_linear = 10 ** (ild_db / 20)

    # Apply gains based on ILD
    if ild_db >= 0:
        # Right ear louder
        left_gain = 1.0 / max(ild_linear, 1.0)
        right_gain = 1.0
    else:
        # Left ear louder
        left_gain = 1.0
        right_gain = 1.0 * (10 ** (ild_db / 20))

    # Apply head shadow filter to far ear (lowpass)
    # Head shadows high frequencies from far ear
    shadow_strength = abs(math.sin(math.radians(azimuth))) * 0.6
    cutoff = 8000 - shadow_strength * 4000  # 4-8kHz depending on angle
    b_shadow, a_shadow = signal.butter(2, cutoff / (SAMPLE_RATE / 2), btype="low")

    if azimuth > 0:
        # Sound from right: shadow left ear
        left_impulse = signal.lfilter(b_shadow, a_shadow, impulse).astype(np.float32)
        right_impulse = impulse.copy()
    elif azimuth < 0:
        # Sound from left: shadow right ear
        left_impulse = impulse.copy()
        right_impulse = signal.lfilter(b_shadow, a_shadow, impulse).astype(np.float32)
    else:
        # Center: no shadow
        left_impulse = impulse.copy()
        right_impulse = impulse.copy()

    # Elevation affects pinna filtering (notches at specific frequencies)
    # Simplified: high elevation boosts highs, low elevation cuts highs
    if abs(elevation) > 10:
        el_factor = elevation / 90.0
        if elevation > 0:
            # Above: slight HF boost (pinna reflection)
            b_el, a_el = signal.butter(1, 6000 / (SAMPLE_RATE / 2), btype="high")
            boost = signal.lfilter(b_el, a_el, left_impulse) * 0.2 * el_factor
            left_impulse = left_impulse + boost.astype(np.float32)
            boost = signal.lfilter(b_el, a_el, right_impulse) * 0.2 * el_factor
            right_impulse = right_impulse + boost.astype(np.float32)
        else:
            # Below: slight HF cut
            cutoff_el = 10000 + elevation * 50  # Lower cutoff for lower elevation
            b_el, a_el = signal.butter(1, max(3000, cutoff_el) / (SAMPLE_RATE / 2), btype="low")
            left_impulse = signal.lfilter(b_el, a_el, left_impulse).astype(np.float32)
            right_impulse = signal.lfilter(b_el, a_el, right_impulse).astype(np.float32)

    # Apply delays
    if left_delay > 0:
        left_hrir[left_delay:] = left_impulse[: length - left_delay]
    else:
        left_hrir[:] = left_impulse

    if right_delay > 0:
        right_hrir[right_delay:] = right_impulse[: length - right_delay]
    else:
        right_hrir[:] = right_impulse

    # Apply gains
    left_hrir *= left_gain
    right_hrir *= right_gain

    # Normalize to prevent clipping
    max_val = max(np.abs(left_hrir).max(), np.abs(right_hrir).max())
    if max_val > 0.001:
        left_hrir /= max_val
        right_hrir /= max_val

    return left_hrir, right_hrir


def get_hrir(
    azimuth: float,
    elevation: float,
    database: str = "synthetic",
) -> tuple[NDArray, NDArray]:
    """Get HRIR pair for given position.

    Args:
        azimuth: Azimuth in degrees
        elevation: Elevation in degrees
        database: HRTF database to use

    Returns:
        (left_hrir, right_hrir) as numpy arrays
    """
    # Normalize angles
    azimuth = ((azimuth + 180) % 360) - 180
    elevation = max(-90, min(90, elevation))

    if database == "synthetic":
        return _generate_synthetic_hrir(azimuth, elevation)
    else:
        # External HRTF databases (KEMAR, CIPIC) require dataset download
        logger.warning(f"HRTF database '{database}' not available, using synthetic")
        return _generate_synthetic_hrir(azimuth, elevation)


# =============================================================================
# Binaural Rendering
# =============================================================================


def render_binaural_static(
    mono: NDArray,
    position: BinauralPosition,
    config: BinauralConfig | None = None,
) -> NDArray:
    """Render mono audio to binaural stereo at static position.

    Args:
        mono: Mono audio array
        position: 3D position
        config: Rendering configuration

    Returns:
        (N, 2) stereo array
    """
    config = config or BinauralConfig()
    n_samples = len(mono)
    stereo = np.zeros((n_samples, 2), dtype=np.float32)

    if config.use_hrtf:
        # Get HRIR for position
        left_hrir, right_hrir = get_hrir(
            position.azimuth,
            position.elevation,
            config.hrtf_database,
        )

        # Convolve with HRIRs
        left = signal.fftconvolve(mono, left_hrir, mode="same").astype(np.float32)
        right = signal.fftconvolve(mono, right_hrir, mode="same").astype(np.float32)
    else:
        # Simple ITD + ILD without full HRTF
        left = mono.copy()
        right = mono.copy()

        if config.enable_itd:
            itd = _woodworth_itd(position.azimuth)
            itd_samples = int(abs(itd) * SAMPLE_RATE)

            if itd > 0:
                # Delay left
                left = np.pad(mono, (itd_samples, 0))[:n_samples]
            elif itd < 0:
                # Delay right
                right = np.pad(mono, (itd_samples, 0))[:n_samples]

        if config.enable_ild:
            ild_db = _calculate_ild(position.azimuth, position.elevation)
            if ild_db > 0:
                left *= 10 ** (-ild_db / 20)
            else:
                right *= 10 ** (ild_db / 20)

    # Distance attenuation
    if config.enable_distance_attenuation and position.distance > 0.5:
        attenuation = min(1.0, 1.0 / position.distance)
        left *= attenuation
        right *= attenuation

    # Air absorption (HF rolloff with distance)
    if config.enable_air_absorption and position.distance > 1.5:
        cutoff = max(4000, 16000 - (position.distance - 1.5) * 2000)
        b, a = signal.butter(1, cutoff / (SAMPLE_RATE / 2), btype="low")
        left = signal.lfilter(b, a, left).astype(np.float32)
        right = signal.lfilter(b, a, right).astype(np.float32)

    stereo[:, 0] = left
    stereo[:, 1] = right

    return stereo


def render_binaural_trajectory(
    mono: NDArray,
    trajectory: list[tuple[float, BinauralPosition]],
    config: BinauralConfig | None = None,
) -> NDArray:
    """Render mono audio to binaural stereo with moving position.

    Args:
        mono: Mono audio array
        trajectory: List of (time_seconds, position) tuples
        config: Rendering configuration

    Returns:
        (N, 2) stereo array
    """
    config = config or BinauralConfig()
    n_samples = len(mono)
    stereo = np.zeros((n_samples, 2), dtype=np.float32)

    if len(trajectory) < 2:
        # Static position
        pos = trajectory[0][1] if trajectory else BinauralPosition()
        return render_binaural_static(mono, pos, config)

    # Process in frames with crossfade
    frame_size = int(SAMPLE_RATE / config.update_rate_hz)
    crossfade_samples = int(config.crossfade_ms * SAMPLE_RATE / 1000)

    # Pre-compute positions for each frame
    num_frames = (n_samples + frame_size - 1) // frame_size

    for frame_idx in range(num_frames):
        start = frame_idx * frame_size
        end = min(start + frame_size, n_samples)
        frame_len = end - start

        # Get position for this frame (interpolate from trajectory)
        t = start / SAMPLE_RATE
        pos = _interpolate_trajectory(trajectory, t)

        # Get HRIR for this position
        left_hrir, right_hrir = get_hrir(
            pos.azimuth,
            pos.elevation,
            config.hrtf_database,
        )

        # Get frame audio with padding for convolution
        pad_before = min(start, HRTF_LENGTH)
        pad_after = min(n_samples - end, HRTF_LENGTH)

        frame_start = start - pad_before
        frame_end = end + pad_after
        frame_audio = mono[frame_start:frame_end]

        # Convolve
        left = signal.fftconvolve(frame_audio, left_hrir, mode="same").astype(np.float32)
        right = signal.fftconvolve(frame_audio, right_hrir, mode="same").astype(np.float32)

        # Extract the relevant portion
        left = left[pad_before : pad_before + frame_len]
        right = right[pad_before : pad_before + frame_len]

        # Apply distance effects
        if config.enable_distance_attenuation and pos.distance > 0.5:
            attenuation = min(1.0, 1.0 / pos.distance)
            left *= attenuation
            right *= attenuation

        # Crossfade with previous frame
        if frame_idx > 0 and crossfade_samples > 0:
            crossfade_len = min(crossfade_samples, frame_len)
            fade_in = np.linspace(0, 1, crossfade_len).astype(np.float32)
            fade_out = 1 - fade_in

            # Blend with existing (previous frame's tail)
            stereo[start : start + crossfade_len, 0] = (
                stereo[start : start + crossfade_len, 0] * fade_out + left[:crossfade_len] * fade_in
            )
            stereo[start : start + crossfade_len, 1] = (
                stereo[start : start + crossfade_len, 1] * fade_out
                + right[:crossfade_len] * fade_in
            )

            # Copy rest without blend
            if frame_len > crossfade_len:
                stereo[start + crossfade_len : end, 0] = left[crossfade_len:]
                stereo[start + crossfade_len : end, 1] = right[crossfade_len:]
        else:
            stereo[start:end, 0] = left
            stereo[start:end, 1] = right

    return stereo


def _interpolate_trajectory(
    trajectory: list[tuple[float, BinauralPosition]],
    t: float,
) -> BinauralPosition:
    """Interpolate position from trajectory at time t."""
    if not trajectory:
        return BinauralPosition()

    if t <= trajectory[0][0]:
        return trajectory[0][1]

    if t >= trajectory[-1][0]:
        return trajectory[-1][1]

    # Find surrounding keyframes
    for i in range(len(trajectory) - 1):
        t0, pos0 = trajectory[i]
        t1, pos1 = trajectory[i + 1]

        if t0 <= t <= t1:
            # Linear interpolation
            alpha = (t - t0) / (t1 - t0) if t1 > t0 else 0

            return BinauralPosition(
                azimuth=pos0.azimuth + alpha * (pos1.azimuth - pos0.azimuth),
                elevation=pos0.elevation + alpha * (pos1.elevation - pos0.elevation),
                distance=pos0.distance + alpha * (pos1.distance - pos0.distance),
            )

    return trajectory[-1][1]


# =============================================================================
# iOS Compatibility Layer
# =============================================================================


def convert_speaker_trajectory_to_binaural(
    trajectory: list[tuple[float, tuple[float, float, float]]],
) -> list[tuple[float, BinauralPosition]]:
    """Convert speaker-based trajectory to binaural positions.

    Takes trajectories from spatial_audio.py (Position objects) and converts
    to BinauralPosition for headphone rendering.

    Args:
        trajectory: List of (time, (azimuth, elevation, distance)) tuples

    Returns:
        List of (time, BinauralPosition) tuples
    """
    return [
        (t, BinauralPosition(azimuth=az, elevation=el, distance=dist))
        for t, (az, el, dist) in trajectory
    ]


def render_for_ios(
    mono: NDArray,
    trajectory: list[tuple[float, BinauralPosition]] | None = None,
    position: BinauralPosition | None = None,
) -> NDArray:
    """Render binaural audio optimized for iOS/AirPods.

    Creates binaural stereo that:
    - Works with iOS "Spatialize Stereo" feature
    - Compatible with AirPods head tracking
    - Can be enhanced by personalized spatial audio profiles

    Args:
        mono: Mono audio array
        trajectory: Optional moving position trajectory
        position: Static position (used if trajectory is None)

    Returns:
        (N, 2) binaural stereo array
    """
    config = BinauralConfig(
        use_hrtf=True,
        hrtf_database="synthetic",
        enable_distance_attenuation=True,
        enable_air_absorption=True,
        anchor_to_device=True,
    )

    if trajectory:
        return render_binaural_trajectory(mono, trajectory, config)
    else:
        pos = position or BinauralPosition()
        return render_binaural_static(mono, pos, config)


def save_ios_compatible(
    audio: NDArray,
    output_path: Path | str,
    sample_rate: int = SAMPLE_RATE,
) -> bool:
    """Save audio in iOS-compatible format.

    Creates 48kHz 24-bit stereo WAV file suitable for:
    - Direct playback on iOS
    - AirPlay streaming
    - Import to Apple Music for spatial audio

    Args:
        audio: Audio array (mono or stereo)
        output_path: Output file path
        sample_rate: Sample rate (48kHz recommended for iOS)

    Returns:
        True if successful
    """
    try:
        import soundfile as sf

        # Ensure stereo
        if len(audio.shape) == 1:
            # Mono - duplicate to stereo
            audio = np.column_stack([audio, audio])

        # Ensure float32 for 24-bit output
        audio = audio.astype(np.float32)

        # Normalize
        peak = np.abs(audio).max()
        if peak > 0.95:
            audio = audio * (0.9 / peak)

        # Save as 24-bit WAV
        sf.write(
            str(output_path),
            audio,
            sample_rate,
            subtype="PCM_24",  # 24-bit for iOS quality
        )

        logger.info(f"Saved iOS-compatible audio: {output_path}")
        return True

    except Exception as e:
        logger.error(f"Failed to save iOS audio: {e}")
        return False


# =============================================================================
# API for Streaming to iOS
# =============================================================================


@dataclass
class BinauralStreamConfig:
    """Configuration for streaming binaural audio to iOS."""

    # Audio format
    sample_rate: int = 48000
    bit_depth: int = 24
    channels: int = 2

    # Streaming
    chunk_size_ms: float = 50.0  # Chunk size for streaming
    buffer_chunks: int = 4  # Number of chunks to buffer

    # Head tracking
    enable_head_tracking: bool = True
    head_tracking_update_hz: float = 60.0


class BinauralStreamState:
    """State for real-time binaural streaming."""

    def __init__(self, config: BinauralStreamConfig | None = None):
        self.config = config or BinauralStreamConfig()
        self._current_position = BinauralPosition()
        self._head_orientation = (0.0, 0.0, 0.0)  # yaw, pitch, roll

    def update_head_orientation(self, yaw: float, pitch: float, roll: float) -> None:
        """Update head orientation from iOS device.

        When head tracking is enabled, iOS sends device orientation.
        We offset the sound position to maintain device-anchored audio.

        Args:
            yaw: Yaw in degrees (left/right rotation)
            pitch: Pitch in degrees (up/down tilt)
            roll: Roll in degrees (side tilt)
        """
        self._head_orientation = (yaw, pitch, roll)

    def get_adjusted_position(self, source_position: BinauralPosition) -> BinauralPosition:
        """Get source position adjusted for head tracking.

        When the user turns their head, we adjust the source position
        to keep the sound anchored to the device (as Apple spatial audio does).

        Args:
            source_position: Original source position

        Returns:
            Adjusted position accounting for head rotation
        """
        if not self.config.enable_head_tracking:
            return source_position

        yaw, pitch, _roll = self._head_orientation

        # Offset azimuth by head yaw (user looks right, sound shifts left)
        adjusted_azimuth = source_position.azimuth - yaw

        # Offset elevation by head pitch
        adjusted_elevation = source_position.elevation - pitch

        # Normalize
        adjusted_azimuth = ((adjusted_azimuth + 180) % 360) - 180
        adjusted_elevation = max(-90, min(90, adjusted_elevation))

        return BinauralPosition(
            azimuth=adjusted_azimuth,
            elevation=adjusted_elevation,
            distance=source_position.distance,
        )


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "HRTF_LENGTH",
    "SAMPLE_RATE",
    "BinauralConfig",
    "BinauralPosition",
    "BinauralStreamConfig",
    "BinauralStreamState",
    "convert_speaker_trajectory_to_binaural",
    "get_hrir",
    "render_binaural_static",
    "render_binaural_trajectory",
    "render_for_ios",
    "save_ios_compatible",
]
