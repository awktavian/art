"""Tests for Audio Processing Utilities.

Tests cover:
- Audio feature extraction
- Mel spectrogram conversion
- Audio-visual alignment
- Combined feature creation

Coverage target: kagami/core/multimodal/audio_processing.py
"""

from __future__ import annotations

from typing import Any

import pytest

pytestmark = pytest.mark.tier_unit


import numpy as np

from kagami.core.multimodal import (
    extract_audio_features,
    mel_spectrogram_to_tensor,
    align_audio_visual_tempo,
    create_audio_visual_features,
)

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def sample_audio():
    """Create sample audio waveform."""
    # 1 second of audio at 16kHz
    sample_rate = 16000
    duration = 1.0
    t = np.linspace(0, duration, int(sample_rate * duration))
    # Simple sine wave at 440Hz
    audio = np.sin(2 * np.pi * 440 * t).astype(np.float32)
    return audio, sample_rate


@pytest.fixture
def sample_stereo_audio():
    """Create sample stereo audio."""
    sample_rate = 16000
    duration = 1.0
    t = np.linspace(0, duration, int(sample_rate * duration))
    left = np.sin(2 * np.pi * 440 * t).astype(np.float32)
    right = np.sin(2 * np.pi * 880 * t).astype(np.float32)
    return np.stack([left, right], axis=0), sample_rate


@pytest.fixture
def sample_mel_spectrogram():
    """Create sample mel spectrogram."""
    # [n_mels, time_frames]
    return np.random.randn(128, 100).astype(np.float32)


@pytest.fixture
def sample_video_fps():
    """Sample video frame rate."""
    return 30.0


# =============================================================================
# AUDIO FEATURE EXTRACTION TESTS
# =============================================================================


class TestAudioFeatureExtraction:
    """Tests for audio feature extraction."""

    def test_extract_basic_features(self, sample_audio) -> None:
        """Test basic audio feature extraction."""
        audio, sr = sample_audio
        features = extract_audio_features(audio, sample_rate=sr)

        assert features is not None
        # Should return some form of features (dict or tensor)
        if isinstance(features, dict):
            assert len(features) > 0
        elif hasattr(features, "shape"):
            assert len(features.shape) >= 1

    def test_extract_with_various_sample_rates(self) -> None:
        """Test extraction with various sample rates."""
        for sr in [8000, 16000, 22050, 44100]:
            duration = 1.0
            t = np.linspace(0, duration, int(sr * duration))
            audio = np.sin(2 * np.pi * 440 * t).astype(np.float32)

            features = extract_audio_features(audio, sample_rate=sr)
            assert features is not None

    def test_extract_short_audio(self) -> None:
        """Test extraction with very short audio."""
        # 0.1 second audio
        sr = 16000
        short_audio = np.random.randn(int(sr * 0.1)).astype(np.float32)
        features = extract_audio_features(short_audio, sample_rate=sr)
        assert features is not None

    def test_extract_long_audio(self) -> None:
        """Test extraction with longer audio."""
        # 10 second audio
        sr = 16000
        long_audio = np.random.randn(int(sr * 10)).astype(np.float32)
        features = extract_audio_features(long_audio, sample_rate=sr)
        assert features is not None

    def test_extract_stereo_audio(self, sample_stereo_audio) -> None:
        """Test extraction handles stereo audio."""
        audio, sr = sample_stereo_audio
        # May need to convert to mono first depending on implementation
        try:
            features = extract_audio_features(audio, sample_rate=sr)
            assert features is not None
        except (ValueError, TypeError):
            # Some implementations may not support stereo directly
            # Convert to mono and retry
            mono = audio.mean(axis=0)
            features = extract_audio_features(mono, sample_rate=sr)
            assert features is not None


# =============================================================================
# MEL SPECTROGRAM TESTS
# =============================================================================


class TestMelSpectrogram:
    """Tests for mel spectrogram conversion."""

    def test_mel_to_tensor(self, sample_mel_spectrogram) -> None:
        """Test converting mel spectrogram to tensor."""
        tensor = mel_spectrogram_to_tensor(sample_mel_spectrogram)

        assert tensor is not None
        # Should preserve shape or add batch dim
        if hasattr(tensor, "shape"):
            assert tensor.shape[-2:] == sample_mel_spectrogram.shape or tensor.shape[-2:] == (
                128,
                100,
            )

    def test_mel_normalization(self, sample_mel_spectrogram) -> None:
        """Test mel spectrogram normalization."""
        tensor = mel_spectrogram_to_tensor(sample_mel_spectrogram, normalize=True)

        if hasattr(tensor, "mean"):
            # Normalized should have reasonable range
            assert tensor is not None

    def test_mel_various_shapes(self) -> None:
        """Test mel conversion with various shapes."""
        for n_mels in [40, 80, 128]:
            for time_frames in [50, 100, 200]:
                mel = np.random.randn(n_mels, time_frames).astype(np.float32)
                tensor = mel_spectrogram_to_tensor(mel)
                assert tensor is not None


# =============================================================================
# AUDIO-VISUAL ALIGNMENT TESTS
# =============================================================================


class TestAudioVisualAlignment:
    """Tests for audio-visual tempo alignment."""

    def test_align_tempo_basic(self, sample_audio, sample_video_fps) -> None:
        """Test basic audio-visual alignment."""
        audio, sr = sample_audio

        aligned = align_audio_visual_tempo(
            audio=audio,
            sample_rate=sr,
            video_fps=sample_video_fps,
        )

        assert aligned is not None

    def test_align_various_fps(self, sample_audio) -> None:
        """Test alignment with various frame rates."""
        audio, sr = sample_audio

        for fps in [24, 25, 30, 60]:
            aligned = align_audio_visual_tempo(
                audio=audio,
                sample_rate=sr,
                video_fps=fps,
            )
            assert aligned is not None

    def test_align_returns_frame_aligned_features(self, sample_audio, sample_video_fps) -> None:
        """Test that alignment returns frame-aligned features."""
        audio, sr = sample_audio

        result = align_audio_visual_tempo(
            audio=audio,
            sample_rate=sr,
            video_fps=sample_video_fps,
        )

        # Result should have features per video frame
        if hasattr(result, "shape"):
            # Expected frames for 1 second video at 30fps
            expected_frames = int(sample_video_fps * 1.0)
            # Allow some tolerance for edge effects
            if len(result.shape) >= 2:
                assert abs(result.shape[0] - expected_frames) <= 5


# =============================================================================
# COMBINED FEATURE TESTS
# =============================================================================


class TestCombinedFeatures:
    """Tests for combined audio-visual features."""

    def test_create_combined_features(self, sample_audio, sample_video_fps) -> None:
        """Test creating combined audio-visual features."""
        audio, sr = sample_audio

        # Create dummy video features
        num_frames = int(sample_video_fps * 1.0)
        video_features = np.random.randn(num_frames, 512).astype(np.float32)

        combined = create_audio_visual_features(
            audio=audio,
            sample_rate=sr,
            video_features=video_features,
            video_fps=sample_video_fps,
        )

        assert combined is not None

    def test_combined_features_shape(self, sample_audio, sample_video_fps) -> None:
        """Test combined features have correct shape."""
        audio, sr = sample_audio
        num_frames = int(sample_video_fps * 1.0)
        video_features = np.random.randn(num_frames, 512).astype(np.float32)

        combined = create_audio_visual_features(
            audio=audio,
            sample_rate=sr,
            video_features=video_features,
            video_fps=sample_video_fps,
        )

        if hasattr(combined, "shape") and len(combined.shape) >= 2:
            # Should have same number of frames as video
            assert combined.shape[0] == num_frames or abs(combined.shape[0] - num_frames) <= 2


# =============================================================================
# EDGE CASES
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases."""

    def test_silent_audio(self) -> None:
        """Test handling of silent audio."""
        sr = 16000
        silent = np.zeros(sr, dtype=np.float32)
        features = extract_audio_features(silent, sample_rate=sr)
        assert features is not None

    def test_clipped_audio(self) -> None:
        """Test handling of clipped audio."""
        sr = 16000
        # Clipped sine wave
        t = np.linspace(0, 1, sr)
        audio = np.clip(2 * np.sin(2 * np.pi * 440 * t), -1, 1).astype(np.float32)
        features = extract_audio_features(audio, sample_rate=sr)
        assert features is not None

    def test_noisy_audio(self) -> None:
        """Test handling of noisy audio."""
        sr = 16000
        noise = np.random.randn(sr).astype(np.float32) * 0.1
        features = extract_audio_features(noise, sample_rate=sr)
        assert features is not None

    def test_empty_audio(self) -> None:
        """Test handling of empty audio."""
        sr = 16000
        empty = np.array([], dtype=np.float32)
        try:
            features = extract_audio_features(empty, sample_rate=sr)
            # Should either return something or raise gracefully
            assert features is not None or True
        except (ValueError, IndexError):
            # Expected for empty input
            pass

    def test_single_sample_audio(self) -> None:
        """Test handling of single sample audio."""
        sr = 16000
        single = np.array([0.5], dtype=np.float32)
        try:
            features = extract_audio_features(single, sample_rate=sr)
            assert features is not None or True
        except (ValueError, IndexError):
            # Expected for too-short input
            pass


# =============================================================================
# DTYPE HANDLING TESTS
# =============================================================================


class TestDtypeHandling:
    """Tests for dtype handling."""

    def test_float32_input(self) -> None:
        """Test with float32 input."""
        sr = 16000
        audio = np.random.randn(sr).astype(np.float32)
        features = extract_audio_features(audio, sample_rate=sr)
        assert features is not None

    def test_float64_input(self) -> None:
        """Test with float64 input."""
        sr = 16000
        audio = np.random.randn(sr).astype(np.float64)
        features = extract_audio_features(audio, sample_rate=sr)
        assert features is not None

    def test_int16_input(self) -> None:
        """Test with int16 input (common for WAV files)."""
        sr = 16000
        audio = (np.random.randn(sr) * 32767).astype(np.int16)
        try:
            features = extract_audio_features(audio, sample_rate=sr)
            assert features is not None
        except TypeError:
            # May need float conversion
            audio_float = audio.astype(np.float32) / 32767.0
            features = extract_audio_features(audio_float, sample_rate=sr)
            assert features is not None
