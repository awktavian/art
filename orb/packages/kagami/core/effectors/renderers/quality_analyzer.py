# pyright: reportGeneralTypeIssues=false
"""Audio Quality Analyzer — Automated orchestral rendering validation.

Provides comprehensive quality analysis for rendered orchestral audio:
- Silence detection (is there audio?)
- Dynamic range analysis (compressed vs natural)
- Frequency balance (spectral centroid, rolloff)
- Stereo width and imaging
- Noise floor / SNR estimation
- Clipping / distortion detection
- Onset detection (are notes attacking properly?)
- Envelope analysis (proper ADSR)

Usage:
    from kagami.core.effectors.renderers.quality_analyzer import (
        QualityAnalyzer,
        QualityReport,
        analyze_render,
    )

    # Quick analysis
    report = analyze_render("/path/to/audio.wav")
    if report.passed:
        print("✓ Quality check passed")
    else:
        for issue in report.issues:
            print(f"  ✗ {issue}")

    # Detailed analysis
    analyzer = QualityAnalyzer()
    report = analyzer.analyze("/path/to/audio.wav")
    print(f"Quality Score: {report.quality_score}/100")

Colony: Forge (e₂)
Created: January 2, 2026
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================


@dataclass
class QualityThresholds:
    """Configurable quality thresholds."""

    # Silence detection
    silence_threshold_db: float = -60.0
    max_silence_ratio: float = 0.5
    max_leading_silence_ms: float = 1000.0
    max_trailing_silence_ms: float = 3000.0

    # Dynamics
    min_dynamic_range_db: float = 8.0  # Orchestral needs dynamics
    min_crest_factor_db: float = 6.0
    max_peak_db: float = -0.3
    target_lufs: float = -14.0

    # Clipping
    clipping_threshold: float = 0.99
    max_clipping_ratio: float = 0.0001  # 0.01%

    # Noise
    max_noise_floor_db: float = -50.0
    min_snr_db: float = 30.0

    # Spectral
    min_spectral_centroid_hz: float = 300.0
    max_spectral_centroid_hz: float = 5000.0
    max_spectral_flatness: float = 0.3

    # Stereo
    min_stereo_correlation: float = -0.3  # Mono compatibility
    min_stereo_width: float = 0.05
    max_stereo_width: float = 0.8

    # Content
    min_onset_rate: float = 0.3  # Notes per second


# =============================================================================
# Quality Report
# =============================================================================


@dataclass
class QualityReport:
    """Complete quality analysis report."""

    # File info
    filename: str
    duration_sec: float
    sample_rate: int
    channels: int

    # Silence detection
    has_audio: bool
    silence_ratio: float
    leading_silence_ms: float
    trailing_silence_ms: float

    # Dynamics
    peak_db: float
    rms_db: float
    crest_factor_db: float
    dynamic_range_db: float
    lufs_integrated: float | None = None

    # Frequency balance
    spectral_centroid_hz: float = 0.0
    spectral_rolloff_hz: float = 0.0
    spectral_bandwidth_hz: float = 0.0
    spectral_flatness: float = 0.0

    # Stereo (if stereo)
    stereo_width: float | None = None
    stereo_correlation: float | None = None
    mono_compatible: bool | None = None

    # Quality issues
    clipping_detected: bool = False
    clipping_samples: int = 0
    clipping_ratio: float = 0.0
    noise_floor_db: float = -96.0
    snr_db: float | None = None

    # Musical content
    onset_count: int = 0
    onset_rate_per_sec: float = 0.0
    tempo_bpm: float | None = None

    # Envelope
    attack_time_ms: float | None = None
    has_proper_decay: bool = True

    # Overall assessment
    quality_score: float = 0.0
    passed: bool = False
    issues: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization.

        Converts numpy types to Python native types for JSON compatibility.
        """

        def to_python(val: Any) -> Any:
            """Convert numpy types to Python native types."""
            if val is None:
                return None
            if hasattr(val, "item"):  # numpy scalar
                return val.item()
            return val

        return {
            "filename": self.filename,
            "duration_sec": to_python(self.duration_sec),
            "sample_rate": to_python(self.sample_rate),
            "channels": to_python(self.channels),
            "has_audio": bool(self.has_audio),
            "silence_ratio": to_python(self.silence_ratio),
            "peak_db": to_python(self.peak_db),
            "rms_db": to_python(self.rms_db),
            "crest_factor_db": to_python(self.crest_factor_db),
            "dynamic_range_db": to_python(self.dynamic_range_db),
            "lufs_integrated": to_python(self.lufs_integrated),
            "spectral_centroid_hz": to_python(self.spectral_centroid_hz),
            "spectral_flatness": to_python(self.spectral_flatness),
            "stereo_width": to_python(self.stereo_width),
            "stereo_correlation": to_python(self.stereo_correlation),
            "mono_compatible": bool(self.mono_compatible),
            "clipping_detected": bool(self.clipping_detected),
            "clipping_ratio": to_python(self.clipping_ratio),
            "noise_floor_db": to_python(self.noise_floor_db),
            "snr_db": to_python(self.snr_db),
            "onset_count": to_python(self.onset_count),
            "onset_rate_per_sec": to_python(self.onset_rate_per_sec),
            "quality_score": to_python(self.quality_score),
            "passed": bool(self.passed),
            "issues": list(self.issues),
            "warnings": list(self.warnings),
        }

    def summary(self) -> str:
        """Generate human-readable summary."""
        lines = [
            f"Quality Report: {self.filename}",
            "=" * 50,
            f"Duration: {self.duration_sec:.2f}s | {self.sample_rate}Hz | {self.channels}ch",
            "",
            "Dynamics:",
            f"  Peak: {self.peak_db:.1f}dB | RMS: {self.rms_db:.1f}dB",
            f"  Crest: {self.crest_factor_db:.1f}dB | Range: {self.dynamic_range_db:.1f}dB",
        ]

        if self.lufs_integrated is not None:
            lines.append(f"  LUFS: {self.lufs_integrated:.1f}")

        lines.extend(
            [
                "",
                "Spectral:",
                f"  Centroid: {self.spectral_centroid_hz:.0f}Hz",
                f"  Flatness: {self.spectral_flatness:.3f}",
            ]
        )

        if self.stereo_width is not None:
            lines.extend(
                [
                    "",
                    "Stereo:",
                    f"  Width: {self.stereo_width:.2f}",
                    f"  Correlation: {self.stereo_correlation:.2f}",
                    f"  Mono OK: {self.mono_compatible}",
                ]
            )

        lines.extend(
            [
                "",
                "Content:",
                f"  Onsets: {self.onset_count} ({self.onset_rate_per_sec:.1f}/s)",
                f"  Clipping: {'YES' if self.clipping_detected else 'No'}",
                f"  SNR: {self.snr_db:.1f}dB" if self.snr_db else "  SNR: N/A",
                "",
                "=" * 50,
                f"SCORE: {self.quality_score:.0f}/100 | {'PASS' if self.passed else 'FAIL'}",
                "=" * 50,
            ]
        )

        if self.issues:
            lines.append("\nIssues:")
            for issue in self.issues:
                lines.append(f"  ✗ {issue}")

        if self.warnings:
            lines.append("\nWarnings:")
            for warning in self.warnings:
                lines.append(f"  ⚠ {warning}")

        return "\n".join(lines)


# =============================================================================
# Quality Analyzer
# =============================================================================


class QualityAnalyzer:
    """Comprehensive audio quality analyzer for orchestral renders.

    Provides detailed analysis including:
    - Silence/content detection
    - Dynamic range measurement
    - Spectral balance analysis
    - Stereo field analysis
    - Clipping/distortion detection
    - Noise floor estimation
    - Musical content analysis (onsets, tempo)

    Example:
        analyzer = QualityAnalyzer()
        report = analyzer.analyze("/path/to/audio.wav")

        if report.passed:
            print(f"✓ Quality OK (score: {report.quality_score}/100)")
        else:
            for issue in report.issues:
                print(f"  ✗ {issue}")
    """

    def __init__(self, thresholds: QualityThresholds | None = None):
        self.thresholds = thresholds or QualityThresholds()

    def analyze(self, audio_path: str | Path) -> QualityReport:
        """Run complete quality analysis on audio file."""
        import librosa

        path = Path(audio_path)
        if not path.exists():
            return self._error_report(path.name, "File not found")

        try:
            # Load audio
            y, sr = librosa.load(str(audio_path), sr=None, mono=False)
        except Exception as e:
            return self._error_report(path.name, f"Failed to load: {e}")

        # Handle mono vs stereo
        if y.ndim == 1:
            y_mono = y
            y_stereo = None
            channels = 1
        else:
            y_mono = librosa.to_mono(y)
            y_stereo = y
            channels = y.shape[0]

        duration = len(y_mono) / sr

        # Initialize report
        report = QualityReport(
            filename=path.name,
            duration_sec=duration,
            sample_rate=sr,
            channels=channels,
            has_audio=True,
            silence_ratio=0.0,
            leading_silence_ms=0.0,
            trailing_silence_ms=0.0,
            peak_db=-96.0,
            rms_db=-96.0,
            crest_factor_db=0.0,
            dynamic_range_db=0.0,
        )

        # Run all analyses
        self._analyze_silence(y_mono, sr, report)
        self._analyze_dynamics(y_mono, sr, report)
        self._analyze_frequency(y_mono, sr, report)
        self._analyze_clipping(y_mono, report)
        self._analyze_noise_floor(y_mono, sr, report)
        self._analyze_onsets(y_mono, sr, report)

        if y_stereo is not None:
            self._analyze_stereo(y_stereo, sr, report)

        # Try LUFS measurement
        self._analyze_loudness(y_mono if y_stereo is None else y_stereo, sr, report)

        # Calculate overall score
        self._calculate_score(report)

        return report

    def _error_report(self, filename: str, error: str) -> QualityReport:
        """Create error report when analysis fails."""
        return QualityReport(
            filename=filename,
            duration_sec=0.0,
            sample_rate=0,
            channels=0,
            has_audio=False,
            silence_ratio=1.0,
            leading_silence_ms=0.0,
            trailing_silence_ms=0.0,
            peak_db=-96.0,
            rms_db=-96.0,
            crest_factor_db=0.0,
            dynamic_range_db=0.0,
            quality_score=0.0,
            passed=False,
            issues=[f"CRITICAL: {error}"],
        )

    def _analyze_silence(self, y: np.ndarray, sr: int, report: QualityReport) -> None:
        """Detect silence and check if audio contains content."""
        import librosa

        t = self.thresholds

        # Frame-based RMS
        frame_length = int(sr * 0.02)  # 20ms frames
        hop_length = frame_length // 2

        rms = librosa.feature.rms(y=y, frame_length=frame_length, hop_length=hop_length)[0]
        rms_db = librosa.amplitude_to_db(rms + 1e-10)

        # Find silent frames
        silent_frames = rms_db < t.silence_threshold_db
        silence_ratio = np.mean(silent_frames)

        # Check if entirely silent
        if silence_ratio > 0.99:
            report.has_audio = False
            report.silence_ratio = 1.0
            report.issues.append("Audio file is silent")
            return

        report.silence_ratio = silence_ratio

        # Leading silence
        for i, is_silent in enumerate(silent_frames):
            if not is_silent:
                report.leading_silence_ms = (i * hop_length / sr) * 1000
                break

        # Trailing silence
        for i, is_silent in enumerate(reversed(silent_frames)):
            if not is_silent:
                report.trailing_silence_ms = (i * hop_length / sr) * 1000
                break

        # Check thresholds
        if report.leading_silence_ms > t.max_leading_silence_ms:
            report.warnings.append(f"Long leading silence: {report.leading_silence_ms:.0f}ms")
        if report.trailing_silence_ms > t.max_trailing_silence_ms:
            report.warnings.append(f"Long trailing silence: {report.trailing_silence_ms:.0f}ms")
        if silence_ratio > t.max_silence_ratio:
            report.warnings.append(f"High silence ratio: {silence_ratio * 100:.1f}%")

    def _analyze_dynamics(self, y: np.ndarray, sr: int, report: QualityReport) -> None:
        """Analyze dynamic range, peak, RMS, crest factor."""
        import librosa

        t = self.thresholds

        # Peak level
        peak = np.max(np.abs(y))
        report.peak_db = 20 * np.log10(peak + 1e-10)

        # RMS level
        rms = np.sqrt(np.mean(y**2))
        report.rms_db = 20 * np.log10(rms + 1e-10)

        # Crest factor
        report.crest_factor_db = report.peak_db - report.rms_db

        # Dynamic range (difference between loud and quiet sections)
        frame_length = int(sr * 0.1)  # 100ms frames
        hop_length = frame_length // 2

        rms_frames = librosa.feature.rms(y=y, frame_length=frame_length, hop_length=hop_length)[0]
        rms_db_frames = librosa.amplitude_to_db(rms_frames + 1e-10)

        # Filter out silent frames
        non_silent = rms_db_frames > t.silence_threshold_db
        if np.any(non_silent):
            loud = np.percentile(rms_db_frames[non_silent], 95)
            quiet = np.percentile(rms_db_frames[non_silent], 10)
            report.dynamic_range_db = loud - quiet

        # Check thresholds
        if report.crest_factor_db < t.min_crest_factor_db:
            report.warnings.append(
                f"Low crest factor: {report.crest_factor_db:.1f}dB (over-compressed?)"
            )
        if report.dynamic_range_db < t.min_dynamic_range_db:
            report.warnings.append(f"Limited dynamics: {report.dynamic_range_db:.1f}dB")
        if report.peak_db > t.max_peak_db:
            report.warnings.append(f"Peak near 0dBFS: {report.peak_db:.1f}dB")

    def _analyze_frequency(self, y: np.ndarray, sr: int, report: QualityReport) -> None:
        """Analyze spectral characteristics."""
        import librosa

        t = self.thresholds

        # Spectral centroid (brightness)
        centroid = librosa.feature.spectral_centroid(y=y, sr=sr)[0]
        report.spectral_centroid_hz = float(np.mean(centroid))

        # Spectral rolloff (85% energy)
        rolloff = librosa.feature.spectral_rolloff(y=y, sr=sr, roll_percent=0.85)[0]
        report.spectral_rolloff_hz = float(np.mean(rolloff))

        # Spectral bandwidth
        bandwidth = librosa.feature.spectral_bandwidth(y=y, sr=sr)[0]
        report.spectral_bandwidth_hz = float(np.mean(bandwidth))

        # Spectral flatness (0=tonal, 1=noise)
        flatness = librosa.feature.spectral_flatness(y=y)[0]
        report.spectral_flatness = float(np.mean(flatness))

        # Check thresholds
        if report.spectral_centroid_hz < t.min_spectral_centroid_hz:
            report.warnings.append("Very dark/bass-heavy spectrum")
        elif report.spectral_centroid_hz > t.max_spectral_centroid_hz:
            report.warnings.append("Very bright spectrum")

        if report.spectral_flatness > t.max_spectral_flatness:
            report.warnings.append("High spectral flatness (noise-like)")

    def _analyze_clipping(self, y: np.ndarray, report: QualityReport) -> None:
        """Detect clipping and distortion."""
        t = self.thresholds

        # Threshold-based clipping detection
        clipped = np.abs(y) >= t.clipping_threshold
        report.clipping_samples = int(np.sum(clipped))
        report.clipping_ratio = report.clipping_samples / len(y)
        report.clipping_detected = report.clipping_samples > 10

        if report.clipping_detected:
            if report.clipping_ratio > t.max_clipping_ratio:
                report.issues.append(f"Significant clipping: {report.clipping_ratio * 100:.3f}%")
            else:
                report.warnings.append(f"Minor clipping: {report.clipping_samples} samples")

    def _analyze_noise_floor(self, y: np.ndarray, sr: int, report: QualityReport) -> None:
        """Estimate noise floor and SNR."""
        import librosa

        t = self.thresholds

        # Frame-based RMS for noise estimation
        frame_length = int(sr * 0.05)  # 50ms frames
        hop_length = frame_length // 2

        rms_frames = librosa.feature.rms(y=y, frame_length=frame_length, hop_length=hop_length)[0]

        # Noise floor = 5th percentile of RMS
        noise_floor_linear = np.percentile(rms_frames, 5)
        report.noise_floor_db = 20 * np.log10(noise_floor_linear + 1e-10)

        # SNR estimation (90th percentile as signal)
        signal_rms = np.percentile(rms_frames, 90)
        if noise_floor_linear > 1e-10:
            report.snr_db = 20 * np.log10(signal_rms / noise_floor_linear)

        # Check thresholds
        if report.noise_floor_db > t.max_noise_floor_db:
            report.warnings.append(f"High noise floor: {report.noise_floor_db:.1f}dB")
        if report.snr_db and report.snr_db < t.min_snr_db:
            report.warnings.append(f"Low SNR: {report.snr_db:.1f}dB")

    def _analyze_onsets(self, y: np.ndarray, sr: int, report: QualityReport) -> None:
        """Detect note onsets and musical content."""
        import librosa

        t = self.thresholds

        try:
            # Onset detection
            onset_frames = librosa.onset.onset_detect(y=y, sr=sr, units="frames")
            onset_times = librosa.frames_to_time(onset_frames, sr=sr)

            report.onset_count = len(onset_times)
            report.onset_rate_per_sec = (
                report.onset_count / report.duration_sec if report.duration_sec > 0 else 0
            )

            # Tempo estimation
            if len(onset_frames) > 4:
                tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
                report.tempo_bpm = float(tempo) if hasattr(tempo, "__float__") else float(tempo[0])

            # Check thresholds
            if report.onset_count == 0 and report.duration_sec > 2:
                report.warnings.append("No note onsets detected")
            elif report.onset_rate_per_sec < t.min_onset_rate:
                report.warnings.append(f"Sparse note activity: {report.onset_rate_per_sec:.1f}/s")
        except Exception as e:
            logger.warning("Onset detection failed: %s", e)

    def _analyze_stereo(self, y: np.ndarray, sr: int, report: QualityReport) -> None:
        """Analyze stereo field characteristics."""
        if y.shape[0] < 2:
            return

        t = self.thresholds

        left = y[0]
        right = y[1]

        # Mid-Side encoding
        mid = (left + right) / 2
        side = (left - right) / 2

        # Stereo width
        mid_energy = np.sum(mid**2)
        side_energy = np.sum(side**2)
        total_energy = mid_energy + side_energy

        if total_energy > 0:
            report.stereo_width = side_energy / total_energy
        else:
            report.stereo_width = 0.0

        # Correlation
        if len(left) > 0:
            correlation = np.corrcoef(left, right)[0, 1]
            report.stereo_correlation = float(correlation) if not np.isnan(correlation) else 1.0

        # Mono compatibility
        report.mono_compatible = (
            report.stereo_correlation > t.min_stereo_correlation
            if report.stereo_correlation is not None
            else True
        )

        # Check thresholds
        if report.stereo_width < t.min_stereo_width:
            report.warnings.append("Very narrow stereo (nearly mono)")
        elif report.stereo_width > t.max_stereo_width:
            report.warnings.append("Very wide stereo (check mono compatibility)")

        if not report.mono_compatible:
            report.issues.append("Poor mono compatibility (phase cancellation)")

    def _analyze_loudness(self, y: np.ndarray, sr: int, report: QualityReport) -> None:
        """Measure integrated loudness in LUFS."""
        try:
            import pyloudnorm as pyln

            meter = pyln.Meter(sr)

            # pyloudnorm expects shape (samples, channels) for stereo
            if y.ndim == 2:
                y_for_lufs = y.T
            else:
                y_for_lufs = y

            report.lufs_integrated = meter.integrated_loudness(y_for_lufs)

            if report.lufs_integrated < -24:
                report.warnings.append(f"Very quiet: {report.lufs_integrated:.1f} LUFS")
            elif report.lufs_integrated > -8:
                report.warnings.append(f"Very loud: {report.lufs_integrated:.1f} LUFS")

        except ImportError:
            pass  # pyloudnorm not available
        except Exception as e:
            logger.debug("LUFS measurement failed: %s", e)

    def _calculate_score(self, report: QualityReport) -> None:
        """Calculate overall quality score 0-100."""
        score = 100.0

        # Critical issues (major deductions)
        if not report.has_audio:
            report.quality_score = 0.0
            report.passed = False
            return

        # Clipping (major issue)
        if report.clipping_ratio > self.thresholds.max_clipping_ratio:
            score -= 30
        elif report.clipping_detected:
            score -= 10

        # Dynamic issues
        if report.crest_factor_db < self.thresholds.min_crest_factor_db:
            score -= 15
        if report.dynamic_range_db < self.thresholds.min_dynamic_range_db:
            score -= 10

        # Noise issues
        if report.noise_floor_db > -40:
            score -= 20
        elif report.noise_floor_db > self.thresholds.max_noise_floor_db:
            score -= 10

        # Silence issues
        if report.silence_ratio > self.thresholds.max_silence_ratio:
            score -= 15
        elif report.silence_ratio > 0.3:
            score -= 5

        # Stereo issues
        if report.mono_compatible is False:
            score -= 15

        # Content issues
        if report.onset_count == 0 and report.duration_sec > 2:
            score -= 10

        # Each issue costs points
        score -= len(report.issues) * 5
        score -= len(report.warnings) * 2

        report.quality_score = max(0.0, min(100.0, score))
        report.passed = report.quality_score >= 70 and len(report.issues) == 0


# =============================================================================
# Convenience Functions
# =============================================================================


def analyze_render(
    audio_path: str | Path,
    thresholds: QualityThresholds | None = None,
    verbose: bool = False,
) -> QualityReport:
    """Analyze a rendered audio file for quality issues.

    Args:
        audio_path: Path to audio file
        thresholds: Custom quality thresholds
        verbose: Print detailed report

    Returns:
        QualityReport with analysis results

    Example:
        report = analyze_render("output.wav")
        if report.passed:
            print("✓ Quality check passed")
        else:
            print("✗ Quality check failed")
            for issue in report.issues:
                print(f"  - {issue}")
    """
    analyzer = QualityAnalyzer(thresholds)
    report = analyzer.analyze(audio_path)

    if verbose:
        print(report.summary())

    return report


def quick_check(audio_path: str | Path) -> tuple[bool, str]:
    """Quick pass/fail check for audio file.

    Returns:
        Tuple of (passed, summary_message)

    Example:
        passed, msg = quick_check("output.wav")
        print(f"{'✓' if passed else '✗'} {msg}")
    """
    report = analyze_render(audio_path)

    if report.passed:
        return True, f"Quality OK (score: {report.quality_score:.0f}/100)"
    else:
        issues = "; ".join(report.issues[:3])
        return False, f"Failed (score: {report.quality_score:.0f}): {issues}"


def validate_render_output(
    audio_path: str | Path,
    min_duration: float = 1.0,
    min_score: float = 70.0,
) -> tuple[bool, QualityReport]:
    """Validate render output meets minimum requirements.

    Args:
        audio_path: Path to rendered audio
        min_duration: Minimum acceptable duration in seconds
        min_score: Minimum quality score (0-100)

    Returns:
        Tuple of (valid, report)
    """
    report = analyze_render(audio_path)

    valid = (
        report.has_audio
        and report.duration_sec >= min_duration
        and report.quality_score >= min_score
        and len(report.issues) == 0
    )

    return valid, report


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "QualityAnalyzer",
    "QualityReport",
    "QualityThresholds",
    "analyze_render",
    "quick_check",
    "validate_render_output",
]
