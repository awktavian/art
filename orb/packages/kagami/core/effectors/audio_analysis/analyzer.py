"""
Professional Mix Analysis Tools
================================
Objective, repeatable metrics for orchestral mix quality assessment.

Based on broadcast standards (EBU R128, ITU-R BS.1770) and
professional mastering practices.

Author: Kagami Mix Engineering
Date: January 2, 2026
"""

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy import signal


@dataclass
class FrequencyBalance:
    """Frequency band energy distribution."""

    sub_bass: float  # 20-60 Hz
    bass: float  # 60-250 Hz
    low_mid: float  # 250-500 Hz
    mid: float  # 500-2000 Hz
    upper_mid: float  # 2000-4000 Hz
    presence: float  # 4000-8000 Hz
    brilliance: float  # 8000-20000 Hz

    def as_dict(self):
        return {
            "sub_bass_20_60": self.sub_bass,
            "bass_60_250": self.bass,
            "low_mid_250_500": self.low_mid,
            "mid_500_2k": self.mid,
            "upper_mid_2k_4k": self.upper_mid,
            "presence_4k_8k": self.presence,
            "brilliance_8k_20k": self.brilliance,
        }


@dataclass
class DynamicsProfile:
    """Dynamic range and loudness metrics."""

    peak_db: float
    rms_db: float
    lufs_integrated: float  # EBU R128 integrated loudness
    lufs_short_term_max: float
    dynamic_range_db: float  # Difference between loud and quiet
    crest_factor_db: float  # Peak to RMS ratio

    def as_dict(self):
        return {
            "peak_dBFS": self.peak_db,
            "rms_dBFS": self.rms_db,
            "lufs_integrated": self.lufs_integrated,
            "lufs_short_term_max": self.lufs_short_term_max,
            "dynamic_range_dB": self.dynamic_range_db,
            "crest_factor_dB": self.crest_factor_db,
        }


@dataclass
class StereoImage:
    """Stereo field analysis."""

    correlation: float  # -1 to +1 (mono compatibility)
    width: float  # 0-1 (stereo width)
    balance: float  # -1 to +1 (L/R balance)
    center_weight: float  # How much energy in center

    def as_dict(self):
        return {
            "correlation": self.correlation,
            "width": self.width,
            "balance_LR": self.balance,
            "center_weight": self.center_weight,
        }


@dataclass
class MixAnalysis:
    """Complete mix analysis report."""

    file_path: str
    duration_sec: float
    sample_rate: int
    channels: int
    frequency_balance: FrequencyBalance
    dynamics: DynamicsProfile
    stereo_image: StereoImage | None
    issues: list
    recommendations: list
    score: float  # 0-100 overall quality score

    def to_json(self):
        return json.dumps(
            {
                "file": self.file_path,
                "duration_sec": self.duration_sec,
                "sample_rate": self.sample_rate,
                "channels": self.channels,
                "frequency_balance": self.frequency_balance.as_dict(),
                "dynamics": self.dynamics.as_dict(),
                "stereo_image": self.stereo_image.as_dict() if self.stereo_image else None,
                "issues": self.issues,
                "recommendations": self.recommendations,
                "quality_score": self.score,
            },
            indent=2,
        )


class MixAnalyzer:
    """Professional mix analysis engine."""

    # Target values for orchestral music
    TARGETS = {
        "lufs_integrated": -23.0,  # EBU R128 broadcast standard
        "lufs_tolerance": 1.0,
        "peak_ceiling": -1.0,  # Leave headroom
        "dynamic_range_min": 8.0,  # Orchestral needs dynamics
        "dynamic_range_max": 20.0,
        "crest_factor_min": 10.0,  # Healthy transients
        "correlation_min": 0.3,  # Mono compatibility
    }

    # Frequency balance targets (relative dB, 0 = average)
    FREQ_TARGETS = {
        "sub_bass": -6.0,  # Controlled sub
        "bass": 0.0,  # Foundation
        "low_mid": -2.0,  # Avoid mud
        "mid": 0.0,  # Body
        "upper_mid": -1.0,  # Presence without harshness
        "presence": -2.0,  # Air
        "brilliance": -6.0,  # Sparkle, not ice picks
    }

    def __init__(self):
        self.sr = 48000

    def analyze(self, audio_path: str) -> MixAnalysis:
        """Perform complete mix analysis."""
        audio, sr = sf.read(audio_path)
        self.sr = sr

        # Handle multichannel by analyzing first stereo pair or mono sum
        if len(audio.shape) == 1:
            audio = audio.reshape(-1, 1)

        n_channels = audio.shape[1]

        # For multichannel, create stereo downmix for analysis
        if n_channels > 2:
            # 5.1.4 to stereo: L/R + 0.707*C + 0.707*Ls/Rs
            stereo = np.zeros((len(audio), 2))
            stereo[:, 0] = audio[:, 0]  # L
            stereo[:, 1] = audio[:, 1]  # R
            if n_channels > 2:
                stereo[:, 0] += 0.707 * audio[:, 2]  # C to L
                stereo[:, 1] += 0.707 * audio[:, 2]  # C to R
            if n_channels > 4:
                stereo[:, 0] += 0.707 * audio[:, 4]  # Ls
                stereo[:, 1] += 0.707 * audio[:, 5]  # Rs
            audio_stereo = stereo
        else:
            audio_stereo = audio if audio.shape[1] == 2 else np.column_stack([audio, audio])

        # Mono sum for frequency analysis
        mono = audio_stereo.mean(axis=1)

        # Analyze
        freq_balance = self._analyze_frequency(mono)
        dynamics = self._analyze_dynamics(mono)
        stereo_image = self._analyze_stereo(audio_stereo) if audio_stereo.shape[1] >= 2 else None

        # Generate issues and recommendations
        issues, recommendations = self._evaluate(freq_balance, dynamics, stereo_image)

        # Calculate quality score
        score = self._calculate_score(freq_balance, dynamics, stereo_image, issues)

        return MixAnalysis(
            file_path=audio_path,
            duration_sec=len(audio) / sr,
            sample_rate=sr,
            channels=n_channels,
            frequency_balance=freq_balance,
            dynamics=dynamics,
            stereo_image=stereo_image,
            issues=issues,
            recommendations=recommendations,
            score=score,
        )

    def _analyze_frequency(self, mono: np.ndarray) -> FrequencyBalance:
        """Analyze frequency band energy distribution."""
        bands = [
            (20, 60),  # Sub bass
            (60, 250),  # Bass
            (250, 500),  # Low mid
            (500, 2000),  # Mid
            (2000, 4000),  # Upper mid
            (4000, 8000),  # Presence
            (8000, 20000),  # Brilliance
        ]

        energies = []
        for low, high in bands:
            # Bandpass filter
            nyq = self.sr / 2
            low_norm = max(low / nyq, 0.001)
            high_norm = min(high / nyq, 0.999)

            try:
                sos = signal.butter(4, [low_norm, high_norm], "band", output="sos")
                filtered = signal.sosfilt(sos, mono)
                energy = np.sqrt(np.mean(filtered**2))
                energy_db = 20 * np.log10(energy + 1e-10)
            except Exception:
                energy_db = -100

            energies.append(energy_db)

        # Normalize to average = 0
        avg = np.mean(energies)
        energies = [e - avg for e in energies]

        return FrequencyBalance(*energies)

    def _analyze_dynamics(self, mono: np.ndarray) -> DynamicsProfile:
        """Analyze loudness and dynamics."""
        # Peak
        peak = np.max(np.abs(mono))
        peak_db = 20 * np.log10(peak + 1e-10)

        # RMS
        rms = np.sqrt(np.mean(mono**2))
        rms_db = 20 * np.log10(rms + 1e-10)

        # Crest factor
        crest_db = peak_db - rms_db

        # LUFS approximation (simplified ITU-R BS.1770)
        # K-weighted pre-filter
        # High shelf +4dB at 1500Hz
        b_hs = [1.53512485958697, -2.69169618940638, 1.19839281085285]
        a_hs = [1.0, -1.69065929318241, 0.73248077421585]
        # High pass at 38Hz
        b_hp = [1.0, -2.0, 1.0]
        a_hp = [1.0, -1.99004745483398, 0.99007225036621]

        filtered = signal.lfilter(b_hs, a_hs, mono)
        filtered = signal.lfilter(b_hp, a_hp, filtered)

        # Integrated loudness
        lufs = -0.691 + 10 * np.log10(np.mean(filtered**2) + 1e-10)

        # Short-term loudness (3 second windows)
        window_samples = int(3.0 * self.sr)
        hop = window_samples // 4
        short_term = []
        for i in range(0, len(filtered) - window_samples, hop):
            window = filtered[i : i + window_samples]
            st_lufs = -0.691 + 10 * np.log10(np.mean(window**2) + 1e-10)
            short_term.append(st_lufs)

        lufs_st_max = max(short_term) if short_term else lufs

        # Dynamic range (difference between 95th and 10th percentile of short-term)
        if len(short_term) > 10:
            dr = np.percentile(short_term, 95) - np.percentile(short_term, 10)
        else:
            dr = 10.0

        return DynamicsProfile(
            peak_db=peak_db,
            rms_db=rms_db,
            lufs_integrated=lufs,
            lufs_short_term_max=lufs_st_max,
            dynamic_range_db=dr,
            crest_factor_db=crest_db,
        )

    def _analyze_stereo(self, stereo: np.ndarray) -> StereoImage:
        """Analyze stereo field."""
        L = stereo[:, 0]
        R = stereo[:, 1]

        # Correlation
        correlation = np.corrcoef(L, R)[0, 1]

        # Mid/Side
        M = (L + R) / 2
        S = (L - R) / 2

        # Width (S/M ratio)
        m_energy = np.sqrt(np.mean(M**2))
        s_energy = np.sqrt(np.mean(S**2))
        width = s_energy / (m_energy + s_energy + 1e-10)

        # Balance
        l_energy = np.sqrt(np.mean(L**2))
        r_energy = np.sqrt(np.mean(R**2))
        balance = (r_energy - l_energy) / (r_energy + l_energy + 1e-10)

        # Center weight
        center_weight = m_energy / (m_energy + s_energy + 1e-10)

        return StereoImage(
            correlation=correlation, width=width, balance=balance, center_weight=center_weight
        )

    def _evaluate(
        self, freq: FrequencyBalance, dyn: DynamicsProfile, stereo: StereoImage | None
    ) -> tuple:
        """Generate issues and recommendations."""
        issues = []
        recommendations = []

        # Loudness evaluation
        lufs_diff = dyn.lufs_integrated - self.TARGETS["lufs_integrated"]
        if abs(lufs_diff) > self.TARGETS["lufs_tolerance"]:
            if lufs_diff > 0:
                issues.append(
                    f"Too loud: {dyn.lufs_integrated:.1f} LUFS (target: {self.TARGETS['lufs_integrated']:.1f})"
                )
                recommendations.append(f"Reduce overall level by {lufs_diff:.1f} dB")
            else:
                issues.append(
                    f"Too quiet: {dyn.lufs_integrated:.1f} LUFS (target: {self.TARGETS['lufs_integrated']:.1f})"
                )
                recommendations.append(f"Increase overall level by {-lufs_diff:.1f} dB")

        # Peak evaluation
        if dyn.peak_db > self.TARGETS["peak_ceiling"]:
            issues.append(
                f"Peak too high: {dyn.peak_db:.1f} dBFS (ceiling: {self.TARGETS['peak_ceiling']:.1f})"
            )
            recommendations.append("Apply limiter or reduce gain to maintain headroom")

        # Dynamic range
        if dyn.dynamic_range_db < self.TARGETS["dynamic_range_min"]:
            issues.append(f"Over-compressed: DR={dyn.dynamic_range_db:.1f} dB")
            recommendations.append("Reduce compression, allow more dynamics")
        elif dyn.dynamic_range_db > self.TARGETS["dynamic_range_max"]:
            issues.append(f"Too dynamic: DR={dyn.dynamic_range_db:.1f} dB")
            recommendations.append("Apply gentle compression to control peaks")

        # Crest factor
        if dyn.crest_factor_db < self.TARGETS["crest_factor_min"]:
            issues.append(f"Squashed transients: CF={dyn.crest_factor_db:.1f} dB")
            recommendations.append("Reduce limiting, preserve transients")

        # Frequency balance
        for band, target in self.FREQ_TARGETS.items():
            actual = getattr(freq, band)
            diff = actual - target
            if abs(diff) > 3.0:  # 3dB tolerance
                if diff > 0:
                    issues.append(f"Excessive {band}: +{diff:.1f} dB")
                    recommendations.append(f"Reduce {band} by {diff:.1f} dB")
                else:
                    issues.append(f"Lacking {band}: {diff:.1f} dB")
                    recommendations.append(f"Boost {band} by {-diff:.1f} dB")

        # Stereo evaluation
        if stereo:
            if stereo.correlation < self.TARGETS["correlation_min"]:
                issues.append(f"Poor mono compatibility: correlation={stereo.correlation:.2f}")
                recommendations.append("Check phase, reduce stereo width")

            if abs(stereo.balance) > 0.1:
                side = "right" if stereo.balance > 0 else "left"
                issues.append(
                    f"Stereo imbalance: shifted {side} by {abs(stereo.balance) * 100:.0f}%"
                )
                recommendations.append(
                    f"Pan correction needed toward {'left' if stereo.balance > 0 else 'right'}"
                )

        return issues, recommendations

    def _calculate_score(
        self, freq: FrequencyBalance, dyn: DynamicsProfile, stereo: StereoImage | None, issues: list
    ) -> float:
        """Calculate overall quality score (0-100)."""
        score = 100.0

        # Deduct for loudness issues
        lufs_diff = abs(dyn.lufs_integrated - self.TARGETS["lufs_integrated"])
        score -= min(lufs_diff * 5, 20)

        # Deduct for peak issues
        if dyn.peak_db > self.TARGETS["peak_ceiling"]:
            score -= min((dyn.peak_db - self.TARGETS["peak_ceiling"]) * 10, 15)

        # Deduct for dynamic range issues
        if dyn.dynamic_range_db < self.TARGETS["dynamic_range_min"]:
            score -= min((self.TARGETS["dynamic_range_min"] - dyn.dynamic_range_db) * 3, 15)

        # Deduct for frequency imbalances
        for band, target in self.FREQ_TARGETS.items():
            actual = getattr(freq, band)
            diff = abs(actual - target)
            if diff > 3.0:
                score -= min((diff - 3.0) * 2, 10)

        # Deduct for stereo issues
        if stereo:
            if stereo.correlation < self.TARGETS["correlation_min"]:
                score -= 10
            if abs(stereo.balance) > 0.1:
                score -= 5

        # Deduct for each issue
        score -= len(issues) * 2

        return max(0, min(100, score))


def analyze_and_report(audio_path: str) -> MixAnalysis:
    """Analyze audio file and print report."""
    analyzer = MixAnalyzer()
    analysis = analyzer.analyze(audio_path)

    print("=" * 70)
    print("MIX ANALYSIS REPORT")
    print("=" * 70)
    print(f"File: {Path(audio_path).name}")
    print(
        f"Duration: {analysis.duration_sec:.1f}s | SR: {analysis.sample_rate}Hz | Ch: {analysis.channels}"
    )
    print()

    print("DYNAMICS:")
    print(f"  Peak:       {analysis.dynamics.peak_db:+.1f} dBFS")
    print(f"  RMS:        {analysis.dynamics.rms_db:+.1f} dBFS")
    print(f"  LUFS (int): {analysis.dynamics.lufs_integrated:+.1f} LUFS")
    print(f"  LUFS (max): {analysis.dynamics.lufs_short_term_max:+.1f} LUFS")
    print(f"  Dyn Range:  {analysis.dynamics.dynamic_range_db:.1f} dB")
    print(f"  Crest:      {analysis.dynamics.crest_factor_db:.1f} dB")
    print()

    print("FREQUENCY BALANCE (relative to average):")
    fb = analysis.frequency_balance

    def bars(v: float) -> str:
        return "█" * int(max(0, (v + 10) / 2)) + "░" * int(max(0, (10 - v) / 2))

    print(f"  Sub (20-60):     {fb.sub_bass:+5.1f} dB {bars(fb.sub_bass)}")
    print(f"  Bass (60-250):   {fb.bass:+5.1f} dB {bars(fb.bass)}")
    print(f"  Low-Mid (250-500): {fb.low_mid:+5.1f} dB {bars(fb.low_mid)}")
    print(f"  Mid (500-2k):    {fb.mid:+5.1f} dB {bars(fb.mid)}")
    print(f"  Upper-Mid (2k-4k): {fb.upper_mid:+5.1f} dB {bars(fb.upper_mid)}")
    print(f"  Presence (4k-8k): {fb.presence:+5.1f} dB {bars(fb.presence)}")
    print(f"  Brilliance (8k+): {fb.brilliance:+5.1f} dB {bars(fb.brilliance)}")
    print()

    if analysis.stereo_image:
        si = analysis.stereo_image
        print("STEREO IMAGE:")
        print(f"  Correlation: {si.correlation:.2f} {'✓' if si.correlation > 0.3 else '⚠'}")
        print(f"  Width:       {si.width:.2f}")
        print(f"  Balance:     {si.balance:+.2f} {'(centered)' if abs(si.balance) < 0.05 else ''}")
        print(f"  Center Wt:   {si.center_weight:.2f}")
        print()

    print("QUALITY SCORE:", end=" ")
    score = analysis.score
    if score >= 90:
        print(f"★★★★★ {score:.0f}/100 - Excellent")
    elif score >= 80:
        print(f"★★★★☆ {score:.0f}/100 - Very Good")
    elif score >= 70:
        print(f"★★★☆☆ {score:.0f}/100 - Good")
    elif score >= 60:
        print(f"★★☆☆☆ {score:.0f}/100 - Needs Work")
    else:
        print(f"★☆☆☆☆ {score:.0f}/100 - Significant Issues")
    print()

    if analysis.issues:
        print("ISSUES:")
        for issue in analysis.issues:
            print(f"  ⚠ {issue}")
        print()

    if analysis.recommendations:
        print("RECOMMENDATIONS:")
        for rec in analysis.recommendations:
            print(f"  → {rec}")
        print()

    print("=" * 70)

    return analysis


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        analyze_and_report(sys.argv[1])
    else:
        print("Usage: python mix_analyzer.py <audio_file>")
