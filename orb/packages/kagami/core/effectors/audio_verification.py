"""Audio Verification — Robust 24-bit WAV Analysis.

Proper audio verification for BBC Symphony Orchestra renders,
which output 24-bit WAV files. This module handles:
- 24-bit to 32-bit sample conversion
- RMS and peak level calculation
- Silent file detection
- Audio quality metrics

Created: January 6, 2026
"""

from __future__ import annotations

import logging
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# =============================================================================
# Constants
# =============================================================================

# Peak threshold for considering audio "present" (not silent)
# 24-bit audio has max peak of 2^23 = 8,388,608
# We use 1000 as threshold (~0.01% of max, -80dB)
SILENCE_THRESHOLD_24BIT = 1000

# 16-bit threshold
SILENCE_THRESHOLD_16BIT = 100

# RMS threshold for "good" audio (not just noise)
RMS_THRESHOLD = 500


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class AudioMetrics:
    """Audio analysis metrics."""

    path: Path
    sample_rate: int
    channels: int
    sample_width: int  # bytes per sample (2=16-bit, 3=24-bit, 4=32-bit)
    duration_sec: float
    total_samples: int
    peak: int
    rms: float
    has_audio: bool
    is_clipped: bool
    dc_offset: float
    error: str | None = None

    @property
    def peak_db(self) -> float:
        """Peak level in dB (relative to max for bit depth)."""
        max_val = 2 ** (self.sample_width * 8 - 1)
        if self.peak <= 0:
            return -120.0
        return 20 * np.log10(self.peak / max_val)

    @property
    def rms_db(self) -> float:
        """RMS level in dB."""
        max_val = 2 ** (self.sample_width * 8 - 1)
        if self.rms <= 0:
            return -120.0
        return 20 * np.log10(self.rms / max_val)


# =============================================================================
# Core Functions
# =============================================================================


def read_wav_samples(wav_path: Path, max_samples: int | None = None) -> tuple[np.ndarray, int, int]:
    """Read WAV file and return samples as int32 array.

    Handles 16-bit, 24-bit, and 32-bit WAV files correctly.

    Args:
        wav_path: Path to WAV file
        max_samples: Maximum samples to read (None = all)

    Returns:
        Tuple of (samples as int32 array, sample_rate, sample_width)
    """
    with wave.open(str(wav_path), "rb") as wf:
        sample_rate = wf.getframerate()
        channels = wf.getnchannels()
        sample_width = wf.getsampwidth()
        n_frames = wf.getnframes()

        if max_samples:
            n_frames = min(n_frames, max_samples // channels)

        raw = wf.readframes(n_frames)

    # Convert to int32 based on sample width
    if sample_width == 2:  # 16-bit
        samples = np.frombuffer(raw, dtype=np.int16).astype(np.int32)
    elif sample_width == 3:  # 24-bit
        # Manual 24-bit to 32-bit conversion
        n_samples = len(raw) // 3
        samples = np.zeros(n_samples, dtype=np.int32)
        for i in range(n_samples):
            b0, b1, b2 = raw[i * 3], raw[i * 3 + 1], raw[i * 3 + 2]
            val = b0 | (b1 << 8) | (b2 << 16)
            # Sign extend from 24-bit
            if val >= 0x800000:
                val -= 0x1000000
            samples[i] = val
    elif sample_width == 4:  # 32-bit
        samples = np.frombuffer(raw, dtype=np.int32)
    else:
        raise ValueError(f"Unsupported sample width: {sample_width}")

    return samples, sample_rate, sample_width


def analyze_wav(wav_path: Path, analyze_first_sec: float = 60.0) -> AudioMetrics:
    """Analyze a WAV file for audio content.

    Performs comprehensive analysis including:
    - Peak level detection
    - RMS calculation
    - DC offset detection
    - Clipping detection

    Args:
        wav_path: Path to WAV file
        analyze_first_sec: Only analyze first N seconds (default 60)

    Returns:
        AudioMetrics with analysis results
    """
    try:
        with wave.open(str(wav_path), "rb") as wf:
            sample_rate = wf.getframerate()
            channels = wf.getnchannels()
            sample_width = wf.getsampwidth()
            total_frames = wf.getnframes()

        duration_sec = total_frames / sample_rate

        # Read samples for analysis
        max_samples = int(analyze_first_sec * sample_rate * channels)
        samples, _, _ = read_wav_samples(wav_path, max_samples)

        if len(samples) == 0:
            return AudioMetrics(
                path=wav_path,
                sample_rate=sample_rate,
                channels=channels,
                sample_width=sample_width,
                duration_sec=duration_sec,
                total_samples=total_frames * channels,
                peak=0,
                rms=0.0,
                has_audio=False,
                is_clipped=False,
                dc_offset=0.0,
                error="Empty audio data",
            )

        # Calculate metrics
        peak = int(np.max(np.abs(samples)))
        rms = float(np.sqrt(np.mean(samples.astype(np.float64) ** 2)))
        dc_offset = float(np.mean(samples))

        # Check for clipping
        max_val = 2 ** (sample_width * 8 - 1) - 1
        is_clipped = peak >= max_val * 0.99

        # Determine silence threshold based on bit depth
        if sample_width == 3:
            threshold = SILENCE_THRESHOLD_24BIT
        else:
            threshold = SILENCE_THRESHOLD_16BIT

        has_audio = peak > threshold

        return AudioMetrics(
            path=wav_path,
            sample_rate=sample_rate,
            channels=channels,
            sample_width=sample_width,
            duration_sec=duration_sec,
            total_samples=total_frames * channels,
            peak=peak,
            rms=rms,
            has_audio=has_audio,
            is_clipped=is_clipped,
            dc_offset=dc_offset,
        )

    except Exception as e:
        return AudioMetrics(
            path=wav_path,
            sample_rate=0,
            channels=0,
            sample_width=0,
            duration_sec=0.0,
            total_samples=0,
            peak=0,
            rms=0.0,
            has_audio=False,
            is_clipped=False,
            dc_offset=0.0,
            error=str(e),
        )


def check_audio_exists(wav_path: Path) -> bool:
    """Quick check if WAV file contains audio (not silent).

    This is a fast check that only reads the first 30 seconds.

    Args:
        wav_path: Path to WAV file

    Returns:
        True if file contains audio, False if silent or error
    """
    if not wav_path.exists():
        return False

    metrics = analyze_wav(wav_path, analyze_first_sec=30.0)
    return metrics.has_audio


def batch_analyze(
    wav_paths: list[Path],
    analyze_first_sec: float = 60.0,
) -> dict[str, AudioMetrics]:
    """Analyze multiple WAV files.

    Args:
        wav_paths: List of WAV file paths
        analyze_first_sec: Seconds to analyze per file

    Returns:
        Dict mapping stem name to AudioMetrics
    """
    results = {}
    for path in wav_paths:
        results[path.stem] = analyze_wav(path, analyze_first_sec)
    return results


def get_silent_stems(stems_dir: Path) -> list[str]:
    """Get list of silent stems in a directory.

    Args:
        stems_dir: Directory containing WAV stems

    Returns:
        List of stem names that are silent
    """
    silent = []
    for wav in stems_dir.glob("*.wav"):
        if not check_audio_exists(wav):
            silent.append(wav.stem)
    return silent


def get_stems_with_audio(stems_dir: Path) -> list[str]:
    """Get list of stems that have audio content.

    Args:
        stems_dir: Directory containing WAV stems

    Returns:
        List of stem names with audio
    """
    with_audio = []
    for wav in stems_dir.glob("*.wav"):
        if check_audio_exists(wav):
            with_audio.append(wav.stem)
    return with_audio


def verify_stems(stems_dir: Path) -> tuple[list[str], list[str]]:
    """Verify all stems in a directory.

    Args:
        stems_dir: Directory containing WAV stems

    Returns:
        Tuple of (stems_with_audio, silent_stems)
    """
    with_audio = []
    silent = []

    for wav in sorted(stems_dir.glob("*.wav")):
        if check_audio_exists(wav):
            with_audio.append(wav.stem)
        else:
            silent.append(wav.stem)

    return with_audio, silent


def print_stem_report(stems_dir: Path) -> None:
    """Print detailed report of stems in a directory."""
    print(f"\n{'=' * 70}")
    print(f"STEM ANALYSIS: {stems_dir}")
    print("=" * 70)

    with_audio, silent = verify_stems(stems_dir)

    for wav in sorted(stems_dir.glob("*.wav")):
        metrics = analyze_wav(wav, analyze_first_sec=30.0)
        status = "✓" if metrics.has_audio else "✗"
        size_mb = wav.stat().st_size / 1024 / 1024
        print(
            f"  {status} {wav.stem:25} "
            f"Peak={metrics.peak:10} RMS={metrics.rms:12.1f} "
            f"({size_mb:.1f}MB) {metrics.peak_db:.1f}dB"
        )

    print("-" * 70)
    print(f"WITH AUDIO: {len(with_audio)}")
    print(f"SILENT: {len(silent)}")
    print("=" * 70)


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "RMS_THRESHOLD",
    "SILENCE_THRESHOLD_16BIT",
    "SILENCE_THRESHOLD_24BIT",
    "AudioMetrics",
    "analyze_wav",
    "batch_analyze",
    "check_audio_exists",
    "get_silent_stems",
    "get_stems_with_audio",
    "print_stem_report",
    "read_wav_samples",
    "verify_stems",
]
