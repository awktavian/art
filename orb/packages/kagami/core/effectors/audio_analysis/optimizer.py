"""
Professional Mix Optimizer
===========================
Applies corrective processing based on analysis results.
"""

from pathlib import Path

import numpy as np
import soundfile as sf
from scipy import signal


class MixOptimizer:
    """Apply professional mix corrections."""

    def __init__(self, sample_rate: int = 44100):
        self.sr = sample_rate

    def apply_eq(self, audio: np.ndarray, corrections: dict) -> np.ndarray:
        """Apply parametric EQ corrections.

        corrections: dict of {freq: gain_db} for shelves/peaks
        """
        output = audio.copy()

        for freq, gain_db in corrections.items():
            if gain_db == 0:
                continue

            # Convert gain to linear
            gain = 10 ** (gain_db / 20)

            nyq = self.sr / 2

            if freq < 100:
                # Low shelf
                sos = signal.butter(2, freq / nyq, "low", output="sos")
                filtered = signal.sosfilt(sos, output, axis=0)
                output = output + (gain - 1) * filtered
            elif freq > 8000:
                # High shelf
                sos = signal.butter(2, freq / nyq, "high", output="sos")
                filtered = signal.sosfilt(sos, output, axis=0)
                output = output + (gain - 1) * filtered
            else:
                # Peak EQ (bandpass boost/cut)
                Q = 1.5
                bw = freq / Q
                low = max((freq - bw / 2) / nyq, 0.01)
                high = min((freq + bw / 2) / nyq, 0.99)
                sos = signal.butter(2, [low, high], "band", output="sos")
                filtered = signal.sosfilt(sos, output, axis=0)
                output = output + (gain - 1) * filtered

        return output

    def apply_multiband_compression(
        self, audio: np.ndarray, threshold_db: float = -20, ratio: float = 2.0
    ) -> np.ndarray:
        """Gentle multiband compression for dynamics control."""
        output = np.zeros_like(audio)

        # Split into 3 bands
        bands = [
            (20, 200),  # Low
            (200, 2000),  # Mid
            (2000, 20000),  # High
        ]

        nyq = self.sr / 2

        for low_f, high_f in bands:
            low = max(low_f / nyq, 0.01)
            high = min(high_f / nyq, 0.99)

            try:
                sos = signal.butter(4, [low, high], "band", output="sos")
                band = signal.sosfilt(sos, audio, axis=0)
            except Exception:
                continue

            # Simple compression
            threshold = 10 ** (threshold_db / 20)

            # Envelope follower
            env = np.abs(band)
            if len(env.shape) > 1:
                env = env.max(axis=1, keepdims=True)

            # Smooth envelope
            attack_samples = int(0.01 * self.sr)
            release_samples = int(0.1 * self.sr)

            smoothed = np.zeros_like(env)
            for i in range(1, len(env)):
                if env[i] > smoothed[i - 1]:
                    coef = 1 - np.exp(-1 / attack_samples)
                else:
                    coef = 1 - np.exp(-1 / release_samples)
                smoothed[i] = smoothed[i - 1] + coef * (env[i] - smoothed[i - 1])

            # Calculate gain reduction
            gain = np.ones_like(smoothed)
            mask = smoothed > threshold
            gain[mask] = threshold / smoothed[mask]
            gain[mask] = threshold * (smoothed[mask] / threshold) ** (1 / ratio - 1)

            output += band * gain

        return output

    def apply_limiter(self, audio: np.ndarray, ceiling_db: float = -1.0) -> np.ndarray:
        """True peak limiter with lookahead."""
        ceiling = 10 ** (ceiling_db / 20)

        # Lookahead buffer (5ms)
        lookahead = int(0.005 * self.sr)

        # Find peaks
        if len(audio.shape) > 1:
            peaks = np.max(np.abs(audio), axis=1)
        else:
            peaks = np.abs(audio)

        # Calculate gain reduction needed
        gain = np.ones_like(peaks)
        mask = peaks > ceiling
        gain[mask] = ceiling / peaks[mask]

        # Smooth the gain with attack/release
        smoothed = np.ones_like(gain)
        attack = 1 - np.exp(-1 / (0.001 * self.sr))
        release = 1 - np.exp(-1 / (0.05 * self.sr))

        for i in range(1, len(gain)):
            if gain[i] < smoothed[i - 1]:
                smoothed[i] = smoothed[i - 1] + attack * (gain[i] - smoothed[i - 1])
            else:
                smoothed[i] = smoothed[i - 1] + release * (gain[i] - smoothed[i - 1])

        # Apply with lookahead
        delayed_gain = np.roll(smoothed, lookahead)
        delayed_gain[:lookahead] = delayed_gain[lookahead]

        if len(audio.shape) > 1:
            return audio * delayed_gain[:, np.newaxis]
        return audio * delayed_gain

    def normalize_lufs(self, audio: np.ndarray, target_lufs: float = -23.0) -> np.ndarray:
        """Normalize to target LUFS."""
        # Simple LUFS measurement
        rms = np.sqrt(np.mean(audio**2))
        current_lufs = -0.691 + 10 * np.log10(rms**2 + 1e-10)

        # Calculate gain needed
        gain_db = target_lufs - current_lufs
        gain = 10 ** (gain_db / 20)

        return audio * gain

    def optimize(
        self,
        input_path: str,
        output_path: str,
        eq_corrections: dict | None = None,
        target_lufs: float = -23.0,
        ceiling_db: float = -1.0,
        compress: bool = True,
    ) -> dict:
        """Full optimization pipeline."""

        audio, sr = sf.read(input_path)
        self.sr = sr

        print(f"Optimizing: {Path(input_path).name}")
        print(f"  Input: {audio.shape}, SR={sr}")

        # Step 1: EQ corrections
        if eq_corrections:
            print(f"  Applying EQ: {len(eq_corrections)} bands")
            audio = self.apply_eq(audio, eq_corrections)

        # Step 2: Multiband compression (gentle)
        if compress:
            print("  Applying multiband compression")
            audio = self.apply_multiband_compression(audio, threshold_db=-24, ratio=1.5)

        # Step 3: Normalize to target LUFS
        print(f"  Normalizing to {target_lufs} LUFS")
        audio = self.normalize_lufs(audio, target_lufs)

        # Step 4: Limiter
        print(f"  Applying limiter (ceiling={ceiling_db} dB)")
        audio = self.apply_limiter(audio, ceiling_db)

        # Write output
        sf.write(output_path, audio, sr)
        print(f"  Output: {output_path}")

        # Return stats
        peak = np.max(np.abs(audio))
        rms = np.sqrt(np.mean(audio**2))

        return {
            "peak_db": 20 * np.log10(peak + 1e-10),
            "rms_db": 20 * np.log10(rms + 1e-10),
            "lufs_approx": -0.691 + 10 * np.log10(rms**2 + 1e-10),
        }


if __name__ == "__main__":
    optimizer = MixOptimizer()

    # EQ corrections based on analysis
    # Need to: cut bass/low-mid, boost presence/brilliance
    eq_corrections = {
        80: -6.0,  # Cut bass buildup
        300: -8.0,  # Cut low-mid mud
        500: -4.0,  # Cut boxy mids
        3000: +4.0,  # Boost presence
        6000: +3.0,  # Boost clarity
        10000: +6.0,  # Boost air
        14000: +4.0,  # Boost sparkle
    }

    result = optimizer.optimize(
        "/tmp/kagami_williams_v2/williams_virtuoso_spatial.wav",
        "/tmp/kagami_williams_v2/williams_virtuoso_mastered.wav",
        eq_corrections=eq_corrections,
        target_lufs=-23.0,
        ceiling_db=-1.0,
        compress=True,
    )

    print(
        f"\nResult: Peak={result['peak_db']:.1f}dB, RMS={result['rms_db']:.1f}dB, LUFS≈{result['lufs_approx']:.1f}"
    )
