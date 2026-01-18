"""Audio processing for multimodal AI.

Extracts mel-spectrograms and other audio features for fusion with
visual modalities. Enables audio-visual synchronization and cross-modal reasoning.
"""

import io
import logging
from collections.abc import Sequence
from typing import Any, overload

import numpy as np

logger = logging.getLogger(__name__)


@overload
def extract_audio_features(audio_bytes: bytes) -> dict[str, Any]: ...


@overload
def extract_audio_features(
    audio_bytes: np.ndarray,
    sample_rate: int,
) -> dict[str, Any]: ...


def extract_audio_features(
    audio_bytes: bytes | np.ndarray | None = None,
    sample_rate: int | None = None,
    *,
    audio: np.ndarray | None = None,
) -> dict[str, Any]:
    """Extract comprehensive audio features from audio bytes or numpy array.

    Args:
        audio_bytes: Raw audio file bytes (WAV, MP3, etc.) OR numpy array
        sample_rate: Sample rate in Hz (required if audio_bytes is numpy array)
        audio: Alternative name for audio_bytes when passing numpy array (for backward compat)

    Returns:
        Dict with mel-spectrogram, tempo, energy, and other features

    Examples:
        >>> # From bytes
        >>> features = extract_audio_features(audio_bytes)
        >>> # From numpy array
        >>> features = extract_audio_features(audio_array, sample_rate=16000)
        >>> # Alternative syntax
        >>> features = extract_audio_features(audio=audio_array, sample_rate=16000)
    """
    try:
        import librosa

        # Handle different input formats
        y: np.ndarray
        sr: int

        if audio is not None:
            # Keyword argument: audio=np.ndarray
            y = audio
            sr = sample_rate if sample_rate is not None else 22050
        elif isinstance(audio_bytes, np.ndarray):
            # Positional numpy array
            y = audio_bytes
            if sample_rate is None:
                raise ValueError("sample_rate required when passing numpy array")
            sr = sample_rate
        elif isinstance(audio_bytes, bytes):
            # Load audio from bytes
            y_float, sr_float = librosa.load(io.BytesIO(audio_bytes), sr=22050)
            y = y_float
            sr = int(sr_float)
        else:
            raise TypeError(f"audio_bytes must be bytes or np.ndarray, got {type(audio_bytes)}")

        # 1. Mel-spectrogram (frequency-time representation)
        mel_spec = librosa.feature.melspectrogram(
            y=y,
            sr=sr,
            n_mels=128,  # 128 mel frequency bins
            fmax=8000,  # Max frequency
            hop_length=512,  # Hop between frames
        )

        # Convert to log scale (dB)
        mel_spec_db = librosa.power_to_db(mel_spec, ref=np.max)

        # 2. Tempo estimation (handle librosa API across versions)
        # librosa <=0.9: librosa.beat.tempo returns ndarray[Any, Any] or float
        # librosa >=0.10: preferred path librosa.feature.rhythm.tempo
        tempo_val: Any
        try:
            try:
                # Newer API (0.10+)
                from librosa.feature.rhythm import tempo as tempo_fn

                tempo_val = tempo_fn(y=y, sr=sr)
            except Exception:
                # Fallback to legacy API
                tempo_val = librosa.beat.tempo(y=y, sr=sr)
        except Exception:
            tempo_val = 0.0

        # 3. Spectral features
        spectral_centroids = librosa.feature.spectral_centroid(y=y, sr=sr)[0]
        spectral_rolloff = librosa.feature.spectral_rolloff(y=y, sr=sr)[0]
        zero_crossing_rate = librosa.feature.zero_crossing_rate(y)[0]

        # 4. Energy/RMS
        rms = librosa.feature.rms(y=y)[0]

        # 5. MFCC (Mel-Frequency Cepstral Coefficients)
        mfccs = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=20)

        # 6. Chroma features (pitch class)
        chroma = librosa.feature.chroma_stft(y=y, sr=sr)

        return {
            "status": "success",
            "mel_spectrogram": mel_spec_db.tolist(),  # [128, T]
            "mel_shape": list(mel_spec_db.shape),
            "duration_seconds": float(len(y) / sr),
            "sample_rate": sr,
            "tempo_bpm": float(tempo_val[0]) if hasattr(tempo_val, "__len__") else float(tempo_val),
            "features": {
                "spectral_centroid_mean": float(np.mean(spectral_centroids)),
                "spectral_rolloff_mean": float(np.mean(spectral_rolloff)),
                "zero_crossing_rate_mean": float(np.mean(zero_crossing_rate)),
                "rms_energy_mean": float(np.mean(rms)),
                "rms_energy_max": float(np.max(rms)),
            },
            "mfcc": mfccs.tolist(),  # [20, T]
            "chroma": chroma.tolist(),  # [12, T]
        }

    except ImportError as e:
        return {
            "status": "dependency_missing",
            "message": f"librosa not installed - pip install librosa: {e}",
            "duration_seconds": 0.0,
        }
    except (ValueError, TypeError) as e:
        logger.error(f"Audio feature extraction failed (invalid input): {e}")
        return {"status": "error", "message": str(e), "duration_seconds": 0.0}
    except Exception as e:
        logger.error(f"Audio feature extraction failed: {e}")
        return {"status": "error", "message": str(e), "duration_seconds": 0.0}


def mel_spectrogram_to_tensor(
    mel_spec_db: Any,
    normalize: bool = True,
) -> Any:
    """Convert mel-spectrogram to tensor for neural network input.

    Args:
        mel_spec_db: Mel-spectrogram in dB [freq, time]
        normalize: Whether to normalize to 0-1 range (default: True)

    Returns:
        Tensor [1, freq, time] normalized to 0-1, or None on failure

    Examples:
        >>> tensor = mel_spectrogram_to_tensor(mel_spec)
        >>> tensor_unnormalized = mel_spectrogram_to_tensor(mel_spec, normalize=False)
    """
    try:
        import torch

        # Convert to numpy if needed
        if isinstance(mel_spec_db, list):
            mel_spec_db = np.array(mel_spec_db)

        # Normalize to 0-1 if requested
        if normalize:
            mel_min = mel_spec_db.min()
            mel_max = mel_spec_db.max()

            if mel_max > mel_min:
                normalized = (mel_spec_db - mel_min) / (mel_max - mel_min)
            else:
                normalized = np.zeros_like(mel_spec_db)
        else:
            normalized = mel_spec_db

        # Convert to tensor
        tensor = torch.tensor(normalized, dtype=torch.float32).unsqueeze(0)

        return tensor

    except Exception as e:
        logger.error(f"Mel-spectrogram conversion failed: {e}")
        return None


@overload
def align_audio_visual_tempo(
    audio_features: dict[str, Any],
    video_fps: float,
) -> dict[str, Any]: ...


@overload
def align_audio_visual_tempo(
    audio_features: np.ndarray,
    video_fps: float,
    sample_rate: int,
) -> dict[str, Any]: ...


def align_audio_visual_tempo(
    audio_features: dict[str, Any] | np.ndarray | None = None,
    video_fps: float | None = None,
    sample_rate: int | None = None,
    *,
    audio: np.ndarray | None = None,
) -> dict[str, Any]:
    """Analyze audio-visual temporal alignment.

    Args:
        audio_features: Features dict[str, Any] from extract_audio_features() OR numpy array
        video_fps: Video frames per second
        sample_rate: Sample rate (required if audio_features is numpy array)
        audio: Alternative name for audio when passing numpy array

    Returns:
        Synchronization analysis

    Examples:
        >>> # From features dict[str, Any]
        >>> result = align_audio_visual_tempo(features, video_fps=30.0)
        >>> # From numpy array
        >>> result = align_audio_visual_tempo(audio_array, sample_rate=16000, video_fps=30.0)
    """
    try:
        # Handle different input formats
        features: dict[str, Any]
        if audio is not None or isinstance(audio_features, np.ndarray):
            # Extract features from numpy array first
            audio_array = audio if audio is not None else audio_features
            if sample_rate is None:
                raise ValueError("sample_rate required when passing numpy array")
            if not isinstance(audio_array, np.ndarray):
                raise TypeError(f"Expected np.ndarray, got {type(audio_array)}")
            features = extract_audio_features(audio_array, sample_rate=sample_rate)
        elif isinstance(audio_features, dict):
            features = audio_features
        else:
            raise TypeError(
                f"audio_features must be dict[str, Any] or np.ndarray, got {type(audio_features)}"
            )

        if video_fps is None:
            raise ValueError("video_fps is required")

        # Get audio tempo (beats per minute)
        tempo_bpm = features.get("tempo_bpm", 0)

        if tempo_bpm == 0:
            return {"synchronized": False, "reason": "no_tempo_detected"}

        # Convert to beats per second
        tempo_bps = tempo_bpm / 60.0

        # Check if video FPS is a multiple of audio tempo
        ratio = video_fps / tempo_bps

        # Consider synchronized if ratio is close to an integer
        nearest_int = round(ratio)
        deviation = abs(ratio - nearest_int)

        synchronized = deviation < 0.1  # Within 10% of integer ratio

        return {
            "synchronized": synchronized,
            "audio_tempo_bpm": tempo_bpm,
            "video_fps": video_fps,
            "ratio": round(ratio, 2),
            "deviation": round(deviation, 3),
            "recommendation": (
                "Audio and video are temporally aligned"
                if synchronized
                else f"Consider resampling to {nearest_int}:1 ratio"
            ),
        }

    except Exception as e:
        logger.error(f"Tempo alignment failed: {e}")
        return {"synchronized": False, "error": str(e)}


def create_audio_visual_features(
    audio_bytes: bytes | np.ndarray | None = None,
    video_frames: Sequence[Any] | np.ndarray | None = None,
    video_fps: float | None = None,
    *,
    max_frames: int = 60,
    sample_rate: int | None = None,
    audio: np.ndarray | None = None,
    video_features: np.ndarray | None = None,
) -> dict[str, Any]:
    """Fuse audio and visual streams into a single feature representation.

    Args:
        audio_bytes: Raw audio payload (WAV/MP3/etc.) OR numpy array. Optional.
        video_frames: Sequence of frames (numpy arrays, PIL images, or torch tensors).
        video_fps: Frames per second for the video stream. Required for tempo alignment.
        max_frames: Maximum frames to process for optical-flow analysis.
        sample_rate: Sample rate (required if audio_bytes is numpy array)
        audio: Alternative name for audio_bytes when passing numpy array
        video_features: Pre-extracted video features (alternative to video_frames)

    Returns:
        Dict containing audio, video, alignment, and fused feature summaries.

    Examples:
        >>> # From bytes
        >>> result = create_audio_visual_features(audio_bytes=b"...", video_frames=frames)
        >>> # From numpy arrays
        >>> result = create_audio_visual_features(
        ...     audio=audio_array,
        ...     sample_rate=16000,
        ...     video_features=video_feats
        ... )
    """
    status = "success"
    fused_signature: list[float] = []

    # Handle audio input formats
    audio_input = audio if audio is not None else audio_bytes
    audio_summary: dict[str, Any] = {"status": "missing"}
    if audio_input is not None:
        if isinstance(audio_input, np.ndarray):
            if sample_rate is None:
                raise ValueError("sample_rate required when passing numpy array")
            audio_summary = extract_audio_features(audio_input, sample_rate=sample_rate)
        else:
            audio_summary = extract_audio_features(audio_input)
        if audio_summary.get("status") != "success":
            status = "partial"
        else:
            mel_tensor = mel_spectrogram_to_tensor(audio_summary.get("mel_spectrogram"))
            if mel_tensor is not None:
                try:
                    import torch

                    audio_summary["mel_tensor_stats"] = {
                        "shape": list(mel_tensor.shape),
                        "mean": float(torch.mean(mel_tensor).item()),
                        "std": float(torch.std(mel_tensor).item()),
                    }
                except Exception:
                    audio_summary["mel_tensor_shape"] = list(getattr(mel_tensor, "shape", []))

            fused_signature.extend(
                [
                    float(audio_summary.get("tempo_bpm") or 0.0),
                    float(audio_summary.get("features", {}).get("spectral_centroid_mean", 0.0)),
                    float(audio_summary.get("features", {}).get("spectral_rolloff_mean", 0.0)),
                    float(audio_summary.get("features", {}).get("rms_energy_mean", 0.0)),
                ]
            )

    video_summary: dict[str, Any] = {"status": "missing"}
    motion_metrics: dict[str, float] = {}
    frames_to_use: list[Any] = []

    if video_frames:
        try:
            for frame in video_frames[:max_frames]:
                if frame is None:
                    continue
                if hasattr(frame, "cpu"):
                    frame_np = frame.cpu().numpy()
                elif hasattr(frame, "numpy"):
                    frame_np = frame.numpy()
                else:
                    frame_np = np.asarray(frame)
                if frame_np.ndim == 2:
                    frame_np = np.expand_dims(frame_np, axis=-1)
                frames_to_use.append(frame_np)
        except Exception as exc:
            logger.error(f"Video frame conversion failed: {exc}")
            status = "partial"
            video_summary = {"status": "error", "message": str(exc)}

    if len(frames_to_use) >= 2 and video_summary.get("status") != "error":
        from kagami.core.multimodal.optical_flow import (
            compute_dense_optical_flow,
            extract_motion_features,
        )

        try:
            flow_result = compute_dense_optical_flow(frames_to_use[0], frames_to_use[1])
            motion_metrics = extract_motion_features(flow_result)

            if flow_result.get("error"):
                status = "partial"
                video_summary = {
                    "status": "error",
                    "message": flow_result["error"],
                    "frame_count": len(frames_to_use),
                }
            else:
                video_summary = {
                    "status": "success",
                    "frame_count": len(frames_to_use),
                    "frame_shape": list(frames_to_use[0].shape),
                    "motion": motion_metrics,
                    "flow_stats": flow_result.get("stats", {}),
                }

            fused_signature.extend(
                [
                    float(motion_metrics.get("motion_intensity", 0.0)),
                    float(motion_metrics.get("motion_complexity", 0.0)),
                    float(motion_metrics.get("motion_coverage", 0.0)),
                ]
            )
        except Exception as exc:
            status = "partial"
            logger.error(f"Optical flow analysis failed: {exc}")
            video_summary = {"status": "error", "message": str(exc)}

    alignment_summary: dict[str, Any] = {"status": "not_computed"}
    if (
        audio_summary.get("status") == "success"
        and video_summary.get("status") == "success"
        and video_fps
    ):
        alignment_summary = align_audio_visual_tempo(audio_summary, video_fps)
    elif video_fps is None and video_summary.get("status") == "success":
        alignment_summary = {
            "status": "not_computed",
            "reason": "video_fps_required",
        }

    fused_vector = None
    if any(value != 0.0 for value in fused_signature):
        fused_vector = {
            "vector": fused_signature,
            "dimension": len(fused_signature),
        }

    return {
        "status": status,
        "audio": audio_summary,
        "video": video_summary,
        "alignment": alignment_summary,
        "fused_signature": fused_vector,
        "modalities": {
            "has_audio": audio_bytes is not None,
            "has_video": bool(frames_to_use),
        },
    }
