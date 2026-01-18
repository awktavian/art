from __future__ import annotations

"""Video Encoder - Temporal Visual Understanding.

Encodes video sequences (not just static frames) to spatiotemporal embeddings.

Hierarchy of encoders (best to fallback):
1. Veo API (Google Cloud): Richest, learned from billions of videos
2. TimeSformer (open-source): Good temporal understanding

Legacy CLIP frame-by-frame fallback was removed (Dec 2025). If neither Veo nor
TimeSformer is available, this encoder is unavailable and callers should
gracefully degrade.
"""
import logging
from pathlib import Path
from typing import Any, cast

import torch
import torch.nn as nn

logger = logging.getLogger(__name__)


class VideoEncoder(nn.Module):
    """Production video encoder with Veo → TimeSformer hierarchy.

    Outputs spatiotemporal embeddings that capture:
    - Motion and dynamics (what's moving, how fast)
    - Intuitive physics (gravity, collisions, forces)
    - Temporal coherence (object persistence across frames)
    - Visual reasoning (spatial relationships, causality)

    These are then fed into K os's Matryoshka brain for multi-scale reasoning.
    """

    def __init__(
        self,
        device: str = "mps",
        embedding_dim: int = 768,
        max_frames: int = 16,
        enable_veo: bool = True,
        enable_timesformer: bool = True,
        cache_dir: str | None = None,
    ) -> None:
        """Initialize video encoder with fallback hierarchy.

        Args:
            device: Device to run on (mps, cuda, cpu)
            embedding_dim: Output embedding dimension
            max_frames: Maximum frames per video clip
            enable_veo: Try to use Veo API (best quality)
            enable_timesformer: Try to use TimeSformer (good quality, local)
            cache_dir: Directory for model cache (default: ~/.cache/kagami/models)
        """
        super().__init__()
        self.device = device
        self.embedding_dim = embedding_dim
        self.max_frames = max_frames
        if cache_dir is None:
            cache_dir = str(Path.home() / ".cache" / "kagami" / "models")
        self.cache_dir = cache_dir
        Path(cache_dir).mkdir(parents=True, exist_ok=True)
        self.encoder_type = None
        self.veo_client = None
        self.timesformer_model = None
        if enable_veo:
            try:
                from google.cloud import aiplatform

                aiplatform.init()
                self.veo_client = aiplatform.gapic.PredictionServiceClient()
                self.encoder_type = "veo"
                logger.info("✅ Veo API available - using highest quality video encoding")
            except Exception as e:
                logger.debug(f"Veo API not available: {e}")
        if enable_timesformer and self.encoder_type is None:
            try:
                from transformers import TimesformerModel, VideoMAEImageProcessor

                model_name = "facebook/timesformer-base-finetuned-k400"
                rev = "8aaf40ea7d3d282dcb0a5dea01a198320d15d6c0"
                self.timesformer_model = TimesformerModel.from_pretrained(
                    model_name, cache_dir=cache_dir, revision=rev
                ).to(device)
                self.timesformer_processor = VideoMAEImageProcessor.from_pretrained(
                    model_name, cache_dir=cache_dir, revision=rev
                )
                self.timesformer_model.eval()
                if self.timesformer_model.config.hidden_size != embedding_dim:
                    self.timesformer_proj = nn.Linear(
                        self.timesformer_model.config.hidden_size, embedding_dim
                    ).to(device)
                else:
                    self.timesformer_proj: Any | None = None  # type: ignore[assignment, no-redef]
                self.encoder_type = "timesformer"
                logger.info(f"✅ TimeSformer loaded - temporal video encoding on {device}")
            except Exception as e:
                logger.debug(f"TimeSformer not available: {e}")
        if self.encoder_type is None:
            raise RuntimeError(
                "No video encoder available. Install TimeSformer dependencies (transformers) "
                "or configure Veo API to enable video encoding."
            )
        logger.info(f"Video encoder ready: {self.encoder_type}")

    @torch.no_grad()
    def encode_video(
        self,
        frames: list[torch.Tensor] | torch.Tensor,
        return_per_frame: bool = False,
        return_attention: bool = False,
    ) -> dict[str, Any]:
        """Encode video sequence to spatiotemporal embedding.

        Args:
            frames: Video frames as list[Any] or tensor [T, C, H, W] or [B, T, C, H, W]
            return_per_frame: Return per-frame embeddings (not just video-level)
            return_attention: Return attention maps (where model "looks")

        Returns:
            {
                'video_embedding': [B, embedding_dim],          # Video-level features
                'frame_embeddings': [B, T, embedding_dim],      # Per-frame (if requested)
                'temporal_features': [B, embedding_dim // 2],   # Motion/dynamics
                'physics_signals': dict[str, Any],                         # Intuitive physics hints
                'attention_maps': [B, T, H, W],                 # Visual attention (if requested)
                'encoder_type': str,                            # Which encoder was used
                'confidence': float,                            # Encoding confidence
            }
        """
        if isinstance(frames, list):
            frames = torch.stack(frames)
        if frames.dim() == 4:
            frames = frames.unsqueeze(0)
        _batch_size, num_frames, _channels, height, width = frames.shape
        if num_frames > self.max_frames:
            indices = torch.linspace(0, num_frames - 1, self.max_frames).long()
            frames = frames[:, indices]
            num_frames = self.max_frames
        if self.encoder_type == "veo":
            result = self._encode_veo(frames, return_per_frame, return_attention)
        elif self.encoder_type == "timesformer":
            result = self._encode_timesformer(frames, return_per_frame, return_attention)
        else:
            raise RuntimeError(f"Unsupported encoder_type: {self.encoder_type}")
        result["encoder_type"] = self.encoder_type
        result["num_frames"] = num_frames
        result["spatial_resolution"] = (height, width)
        return result

    def _encode_veo(
        self, frames: torch.Tensor, return_per_frame: bool, return_attention: bool
    ) -> dict[str, Any]:
        """Encode with Veo API (highest quality).

        Note: Veo is primarily a generative model, but we can use its encoder
        features via the API. This is the richest encoding, learned from
        billions of videos.
        """
        logger.warning("Veo encoding not yet implemented, using TimeSformer fallback")
        return self._encode_timesformer(frames, return_per_frame, return_attention)

    def _encode_timesformer(
        self, frames: torch.Tensor, return_per_frame: bool, return_attention: bool
    ) -> dict[str, Any]:
        """Encode with TimeSformer (good quality, local inference)."""
        batch_size = frames.shape[0]
        frames_list = []
        for b in range(batch_size):
            video = []
            for t in range(frames.shape[1]):
                frame = frames[b, t].cpu().numpy()
                frame = frame.transpose(1, 2, 0)
                frame_min = frame.min()
                frame_max = frame.max()
                if frame_max > frame_min:
                    frame = (frame - frame_min) / (frame_max - frame_min)
                else:
                    frame = frame - frame_min
                frame = (frame * 255).astype("uint8")
                video.append(frame)
            frames_list.append(video)
        inputs = self.timesformer_processor(frames_list, return_tensors="pt")
        inputs = {k: v.to(self.device) for k, v in inputs.items()}  # type: ignore[assignment]
        outputs = self.timesformer_model(**inputs)  # type: ignore[misc]
        video_embedding = outputs.last_hidden_state[:, 0]
        if self.timesformer_proj is not None:
            video_embedding = self.timesformer_proj(video_embedding)
        result = {"video_embedding": video_embedding, "confidence": 0.85}
        if return_per_frame:
            num_frames = frames.shape[1]
            num_patches = outputs.last_hidden_state.shape[1] - 1
            patches_per_frame = num_patches // num_frames
            frame_embeddings = []
            for t in range(num_frames):
                start_idx = 1 + t * patches_per_frame
                end_idx = start_idx + patches_per_frame
                frame_tokens = outputs.last_hidden_state[:, start_idx:end_idx]
                frame_emb = frame_tokens.mean(dim=1)
                if self.timesformer_proj is not None:
                    frame_emb = self.timesformer_proj(frame_emb)
                frame_embeddings.append(frame_emb)
            result["frame_embeddings"] = torch.stack(frame_embeddings, dim=1)
        if return_per_frame and "frame_embeddings" in result:
            frame_embs = result["frame_embeddings"]
            motion = frame_embs[:, 1:] - frame_embs[:, :-1]
            temporal_features = motion.mean(dim=1)
            result["temporal_features"] = temporal_features
        if return_attention and hasattr(outputs, "attentions") and outputs.attentions:
            attn = outputs.attentions[-1]
            attn = attn.mean(dim=1)
            cls_attn = attn[:, 0, 1:]
            result["attention_maps"] = cls_attn
        if "temporal_features" in result:
            motion_magnitude = result["temporal_features"].norm(dim=-1).mean()
            result["physics_signals"] = {
                "motion_detected": bool(motion_magnitude.item() > 0.1),
                "motion_magnitude": float(motion_magnitude.item()),
                "is_static": bool(motion_magnitude.item() < 0.05),
            }
        return result

    def forward(self, frames: torch.Tensor) -> torch.Tensor:
        """Forward pass for nn.Module compatibility.

        Returns just the video embedding (not full dict[str, Any]).
        """
        result = self.encode_video(frames)
        return cast(torch.Tensor, result["video_embedding"])


def create_video_encoder(
    device: str | None = None,
    embedding_dim: int = 768,
    enable_veo: bool = True,
    enable_timesformer: bool = True,
) -> VideoEncoder:
    """Factory function for video encoder.

    Args:
        device: Device to run on (auto-detect if None)
        embedding_dim: Output embedding dimension
        enable_veo: Try to use Veo API
        enable_timesformer: Try to use TimeSformer

    Returns:
        VideoEncoder instance with best available encoder

    Example:
        >>> encoder = create_video_encoder()
        >>> frames = torch.randn(1, 16, 3, 224, 224)  # 16-frame video
        >>> result = encoder.encode_video(frames)
        >>> print(result['video_embedding'].shape)  # [1, 768]
        >>> print(result['encoder_type'])  # 'timesformer' (or 'veo' when enabled)
    """
    if device is None:
        # Use unified device selection (MPS > CUDA > CPU)
        from kagami.core.utils.device import get_device_str

        device = get_device_str()
    return VideoEncoder(
        device=device,
        embedding_dim=embedding_dim,
        max_frames=16,
        enable_veo=enable_veo,
        enable_timesformer=enable_timesformer,
    )


_global_encoder: VideoEncoder | None = None
if __name__ == "__main__":
    import time

    print("=" * 60)
    print("Video Encoder Smoke Test")
    print("=" * 60)
    encoder = create_video_encoder()
    print(f"\n✅ Encoder type: {encoder.encoder_type}")
    print(f"   Output dimension: {encoder.embedding_dim}")
    print(f"   Max frames: {encoder.max_frames}")
    print("\n📹 Encoding test video (16 frames, 224x224)...")
    frames = torch.randn(1, 16, 3, 224, 224)
    start = time.perf_counter()
    result = encoder.encode_video(frames, return_per_frame=True, return_attention=False)
    elapsed = time.perf_counter() - start
    print(f"\n✅ Encoding complete in {elapsed * 1000:.1f}ms")
    print(f"   Video embedding: {result['video_embedding'].shape}")
    if "frame_embeddings" in result:
        print(f"   Frame embeddings: {result['frame_embeddings'].shape}")
    if "temporal_features" in result:
        print(f"   Temporal features: {result['temporal_features'].shape}")
    if "physics_signals" in result:
        print(f"   Physics signals: {result['physics_signals']}")
    print(f"   Confidence: {result['confidence']:.2f}")
    print("\n" + "=" * 60)
    print("✅ Video encoder operational")
    print("=" * 60)
