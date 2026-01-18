"""Unified Perception Module - LeCun Cognitive Architecture Component.

LeCun (2022): "The perception module estimates the current state of the world
from sensory signals. It is trained to extract task-relevant information."

This module provides a unified interface to all sensory modalities:
- Vision (images, video)
- Audio (speech, sounds)
- Text (language)
- Proprioception (internal state)

Architecture:
    ┌─────────────────────────────────────────────────────────────────┐
    │                    PERCEPTION MODULE                            │
    │  ┌─────────────────────────────────────────────────────────────┐│
    │  │  Multimodal Encoders                                        ││
    │  │    → Vision: CLIP/DINOv2 (images)                          ││
    │  │    → Audio: Whisper/Wav2Vec (audio)                        ││
    │  │    → Text: SentenceTransformer (language)                  ││
    │  │    → Proprioception: State vector (internal)               ││
    │  │                                                             ││
    │  │  Fusion Layer                                               ││
    │  │    → Cross-attention or concatenation                      ││
    │  │    → Projects to unified 512-dim state space               ││
    │  └─────────────────────────────────────────────────────────────┘│
    └─────────────────────────────────────────────────────────────────┘

Created: December 21, 2025
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, cast

import torch
import torch.nn as nn

logger = logging.getLogger(__name__)


@dataclass
class PerceptionConfig:
    """Configuration for unified perception."""

    # Output dimension (unified state space)
    state_dim: int = 512

    # Modality dimensions
    vision_dim: int = 512  # CLIP/DINOv2 embedding
    audio_dim: int = 512  # Whisper/Wav2Vec embedding
    text_dim: int = 384  # SentenceTransformer embedding
    proprio_dim: int = 256  # Internal state dimension

    # Fusion
    fusion_type: str = "concat"  # "concat" or "attention"
    hidden_dim: int = 1024


class VisionEncoder(nn.Module):
    """Vision encoder (wrapper for existing vision encoders)."""

    def __init__(self, config: PerceptionConfig):
        super().__init__()
        self.config = config
        # Lazy load actual vision encoder
        self._encoder = None
        self._projection: nn.Linear | None = None

    def forward(self, images: torch.Tensor) -> torch.Tensor:
        """Encode images to vision features.

        Args:
            images: [B, C, H, W] image tensor

        Returns:
            [B, vision_dim] vision features
        """
        if self._encoder is None:
            # Lazy load from existing multimodal encoders
            try:
                from kagami.core.multimodal.vision import DINOv2Encoder

                self._encoder = DINOv2Encoder()  # type: ignore[assignment]
                logger.info("✓ VisionEncoder using DINOv2")
            except ImportError:
                # Fallback: simple CNN
                logger.warning("DINOv2 encoder unavailable, using simple CNN")
                self._encoder = nn.Sequential(  # type: ignore[assignment]
                    nn.Conv2d(images.shape[1], 64, 7, stride=2, padding=3),
                    nn.ReLU(),
                    nn.AdaptiveAvgPool2d((1, 1)),
                    nn.Flatten(),
                    nn.Linear(64, self.config.vision_dim),
                )

        # Handle DINOv2Encoder (not nn.Module)
        if not isinstance(self._encoder, nn.Module):
            # DINOv2Encoder has encode() method
            if hasattr(self._encoder, "encode"):
                # Convert to PIL Images for DINOv2
                import torchvision.transforms.functional as TF

                batch = []
                for i in range(images.shape[0]):
                    # Convert tensor to PIL Image
                    img_tensor = images[i]
                    # Denormalize if needed
                    if img_tensor.min() < 0:
                        img_tensor = (img_tensor + 1) / 2
                    img_tensor = img_tensor.clamp(0, 1)
                    pil_img = TF.to_pil_image(img_tensor)
                    batch.append(pil_img)

                # Encode batch
                embeddings = self._encoder.encode(batch)  # type: ignore[attr-defined]

                # Project to target dimension if needed
                if embeddings.shape[-1] != self.config.vision_dim:
                    if self._projection is None:
                        self._projection = nn.Linear(
                            embeddings.shape[-1], self.config.vision_dim
                        ).to(embeddings.device)
                    embeddings = self._projection(embeddings)

                return cast(torch.Tensor, embeddings)
            else:
                raise RuntimeError("Vision encoder has no encode() method")

        return self._encoder(images)  # type: ignore[unreachable]


class AudioEncoder(nn.Module):
    """Audio encoder (wrapper for existing audio encoders)."""

    def __init__(self, config: PerceptionConfig):
        super().__init__()
        self.config = config
        self._encoder = None

    def forward(self, audio: torch.Tensor) -> torch.Tensor:
        """Encode audio to features.

        Args:
            audio: [B, T] audio waveform

        Returns:
            [B, audio_dim] audio features
        """
        if self._encoder is None:
            # Fallback: simple 1D CNN (audio encoders need async init)
            logger.info("AudioEncoder using simple 1D CNN (async audio encoders not initialized)")
            self._encoder = nn.Sequential(  # type: ignore[assignment]
                nn.Conv1d(1, 64, 7, stride=2, padding=3),
                nn.ReLU(),
                nn.AdaptiveAvgPool1d(1),
                nn.Flatten(),
                nn.Linear(64, self.config.audio_dim),
            ).to(audio.device)

        if audio.dim() == 2:
            audio = audio.unsqueeze(1)  # Add channel dim
        return cast(torch.Tensor, self._encoder(audio))  # type: ignore[misc]


class TextEncoder(nn.Module):
    """Text encoder (wrapper for existing text encoders)."""

    def __init__(self, config: PerceptionConfig):
        super().__init__()
        self.config = config
        self._encoder = None
        self._proj: nn.Linear | None = None
        self.device = torch.device("cpu")  # Will be updated

    def to(self, device: torch.device | str) -> TextEncoder:  # type: ignore[override]
        """Move encoder to device."""
        super().to(device)
        self.device = torch.device(device) if isinstance(device, str) else device
        return self

    def forward(self, text: list[str]) -> torch.Tensor:
        """Encode text to features using LLM embedding service.

        HARDENED (Dec 22, 2025): Uses real LLM embeddings - no placeholders.

        Args:
            text: List of text strings

        Returns:
            [B, text_dim] text features
        """
        if self._encoder is None:
            from kagami.core.services.embedding_service import get_embedding_service

            self._encoder = get_embedding_service()  # type: ignore[assignment]
            if self._encoder is None:
                raise RuntimeError("Embedding service required for text encoding")
            logger.info("✓ TextEncoder using embedding service")  # type: ignore[unreachable]

        # Encode text using embedding service
        import asyncio  # type: ignore[unreachable]

        async def _encode_batch():
            embeddings = []
            for t in text:
                emb = await self._encoder.embed_text(t)
                if isinstance(emb, torch.Tensor):
                    embeddings.append(emb.to(device=self.device))
                else:
                    embeddings.append(torch.tensor(emb, device=self.device, dtype=torch.float32))
            return embeddings

        # CONCURRENCY FIX (Dec 25, 2025): Use shared thread pool instead of creating
        # per-call executor, handle async context correctly without nested asyncio.run()
        def _run_in_new_loop_sync():
            """Run async embedding in a new event loop (for thread pool execution)."""
            new_loop = asyncio.new_event_loop()
            try:
                asyncio.set_event_loop(new_loop)
                embeddings = []
                for t in text:
                    emb = new_loop.run_until_complete(self._encoder.embed_text(t))
                    if isinstance(emb, torch.Tensor):
                        embeddings.append(emb.to(device=self.device))
                    else:
                        embeddings.append(
                            torch.tensor(emb, device=self.device, dtype=torch.float32)
                        )
                return embeddings
            finally:
                new_loop.close()

        # Check if we're inside a running event loop
        try:
            asyncio.get_running_loop()  # Raises RuntimeError if no loop
            # Already in async context - run in thread pool to avoid blocking
            # Use shared pool instead of creating per-call ThreadPoolExecutor
            from kagami.core.infra.shared_thread_pool import get_shared_thread_pool

            pool = get_shared_thread_pool()
            future = pool.submit(_run_in_new_loop_sync)
            # Wait for result with timeout (non-async wait since we're in sync context)
            embeddings = future.result(timeout=60.0)
        except RuntimeError:
            # No running event loop - safe to use asyncio.run()
            embeddings = asyncio.run(_encode_batch())

        # Stack and ensure correct dimensions
        result = torch.stack(embeddings)

        # Pad/truncate to text_dim
        if result.shape[-1] < self.config.text_dim:
            padding = torch.zeros(
                result.shape[0], self.config.text_dim - result.shape[-1], device=self.device
            )
            result = torch.cat([result, padding], dim=-1)
        elif result.shape[-1] > self.config.text_dim:
            result = result[:, : self.config.text_dim]

        return result


class ProprioceptionEncoder(nn.Module):
    """Proprioception encoder (internal state)."""

    def __init__(self, config: PerceptionConfig):
        super().__init__()
        self.encoder = nn.Sequential(
            nn.Linear(config.proprio_dim, config.proprio_dim),
            nn.LayerNorm(config.proprio_dim),
            nn.GELU(),
        )

    def forward(self, state: torch.Tensor) -> torch.Tensor:
        """Encode internal state.

        Args:
            state: [B, proprio_dim] internal state

        Returns:
            [B, proprio_dim] encoded state
        """
        return cast(torch.Tensor, self.encoder(state))


class CrossAttentionFusion(nn.Module):
    """Cross-attention based multimodal fusion.

    Implements bidirectional cross-attention between modalities,
    allowing each modality to attend to others for rich fusion.

    Architecture:
        1. Project each modality to common dimension
        2. Apply cross-attention between all pairs
        3. Pool attended features
        4. Project to output state dimension
    """

    def __init__(
        self,
        modality_dims: list[int],
        hidden_dim: int = 512,
        state_dim: int = 512,
        num_heads: int = 8,
        dropout: float = 0.1,
    ):
        super().__init__()
        self.num_modalities = len(modality_dims)
        self.hidden_dim = hidden_dim

        # Project each modality to hidden_dim
        self.projections = nn.ModuleList([nn.Linear(dim, hidden_dim) for dim in modality_dims])

        # LayerNorm for each modality
        self.layer_norms = nn.ModuleList([nn.LayerNorm(hidden_dim) for _ in modality_dims])

        # Cross-attention (query attends to all other modalities)
        self.cross_attention = nn.MultiheadAttention(
            embed_dim=hidden_dim,
            num_heads=num_heads,
            dropout=dropout,
            batch_first=True,
        )

        # Feed-forward after attention
        self.ffn = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim * 4),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim * 4, hidden_dim),
        )
        self.ffn_norm = nn.LayerNorm(hidden_dim)

        # Final projection to state_dim
        self.output_projection = nn.Linear(hidden_dim * self.num_modalities, state_dim)

    def forward(self, modalities: list[torch.Tensor]) -> torch.Tensor:
        """Fuse modalities via cross-attention.

        Args:
            modalities: List of [B, modality_dim] tensors

        Returns:
            [B, state_dim] fused state
        """
        batch_size = modalities[0].shape[0]

        # Project all modalities to hidden_dim
        projected = []
        for mod, proj, norm in zip(modalities, self.projections, self.layer_norms, strict=True):
            x = proj(mod)
            x = norm(x)
            projected.append(x.unsqueeze(1))  # [B, 1, hidden_dim]

        # Stack all modalities: [B, num_modalities, hidden_dim]
        stacked = torch.cat(projected, dim=1)

        # Cross-attention: each modality attends to all others
        attended, _ = self.cross_attention(stacked, stacked, stacked)

        # Residual + FFN
        attended = stacked + attended
        attended = attended + self.ffn(self.ffn_norm(attended))

        # Flatten and project to output
        # [B, num_modalities, hidden_dim] -> [B, num_modalities * hidden_dim]
        flattened = attended.reshape(batch_size, -1)
        return cast(torch.Tensor, self.output_projection(flattened))


class FusionLayer(nn.Module):
    """Fuses multimodal features into unified state."""

    def __init__(self, config: PerceptionConfig):
        super().__init__()
        self.config = config

        if config.fusion_type == "concat":
            # Simple concatenation + projection
            total_dim = config.vision_dim + config.audio_dim + config.text_dim + config.proprio_dim
            self.fusion = nn.Sequential(
                nn.Linear(total_dim, config.hidden_dim),
                nn.LayerNorm(config.hidden_dim),
                nn.GELU(),
                nn.Linear(config.hidden_dim, config.state_dim),
            )
        elif config.fusion_type == "attention":
            # Cross-attention fusion
            modality_dims = [
                config.vision_dim,
                config.audio_dim,
                config.text_dim,
                config.proprio_dim,
            ]
            self.fusion = CrossAttentionFusion(  # type: ignore[assignment]
                modality_dims=modality_dims,
                hidden_dim=config.hidden_dim,
                state_dim=config.state_dim,
                num_heads=8,
                dropout=0.1,
            )
        else:
            raise ValueError(
                f"Unknown fusion_type: {config.fusion_type}. Use 'concat' or 'attention'."
            )

    def forward(self, modalities: list[torch.Tensor]) -> torch.Tensor:
        """Fuse modalities into unified state.

        Args:
            modalities: List of [B, *_dim] tensors

        Returns:
            [B, state_dim] unified state
        """
        if self.config.fusion_type == "concat":
            # Concatenate all modalities
            fused = torch.cat(modalities, dim=-1)
            return cast(torch.Tensor, self.fusion(fused))
        else:
            # Attention-based fusion
            return cast(torch.Tensor, self.fusion(modalities))


class PerceptionModule(nn.Module):
    """Unified Perception Module - LeCun Architecture Component.

    Usage:
        perception = PerceptionModule()

        state = perception.perceive({
            'image': image_tensor,
            'audio': audio_tensor,
            'text': ["hello world"],
            'proprio': internal_state,
        })
    """

    def __init__(self, config: PerceptionConfig | None = None, device: str | None = None):
        super().__init__()
        self.config = config or PerceptionConfig()

        # Determine device
        if device is None:
            from kagami.core.utils.device import get_device_str

            device = get_device_str()
        self.device = torch.device(device)

        # Modality encoders
        self.vision = VisionEncoder(self.config)
        self.audio = AudioEncoder(self.config).to(self.device)
        self.text = TextEncoder(self.config).to(self.device)
        self.proprio = ProprioceptionEncoder(self.config).to(self.device)

        # Fusion layer
        self.fusion = FusionLayer(self.config).to(self.device)

        logger.info(
            f"PerceptionModule initialized: state_dim={self.config.state_dim}, device={self.device}"
        )

    def perceive(self, sensors: dict[str, Any]) -> torch.Tensor:
        """Unified perception API.

        Args:
            sensors: Dict with keys:
                - 'image': [B, C, H, W] images (optional)
                - 'audio': [B, T] audio waveform (optional)
                - 'text': List[str] text (optional)
                - 'proprio': [B, proprio_dim] internal state (optional)

        Returns:
            [B, state_dim] unified perceptual state
        """
        # First pass: determine batch size
        batch_size = None

        # Vision
        if "image" in sensors and sensors["image"] is not None:
            img = sensors["image"]
            # Move to module device if it's a tensor
            if isinstance(img, torch.Tensor):
                img = img.to(self.device)
            vision_feat = self.vision(img)
            batch_size = vision_feat.shape[0]
            vision_modality = vision_feat
        else:
            vision_modality = None

        # Audio
        if "audio" in sensors and sensors["audio"] is not None:
            aud = sensors["audio"].to(self.device)
            audio_feat = self.audio(aud)
            if batch_size is None:
                batch_size = audio_feat.shape[0]
            audio_modality = audio_feat
        else:
            audio_modality = None

        # Text
        if "text" in sensors and sensors["text"] is not None:
            text_feat = self.text(sensors["text"])
            if batch_size is None:
                batch_size = text_feat.shape[0]
            text_modality = text_feat
        else:
            text_modality = None

        # Proprioception
        if "proprio" in sensors and sensors["proprio"] is not None:
            prop = sensors["proprio"].to(self.device)
            proprio_feat = self.proprio(prop)
            if batch_size is None:
                batch_size = proprio_feat.shape[0]
            proprio_modality = proprio_feat
        else:
            proprio_modality = None

        # Set defaults if no modalities provided
        if batch_size is None:
            batch_size = 1

        # Ensure all tensors are on the same device (self.device)
        # Second pass: build modality list[Any] with zero padding for missing modalities
        modalities = [
            vision_modality.to(self.device)
            if vision_modality is not None
            else torch.zeros(batch_size, self.config.vision_dim, device=self.device),
            audio_modality.to(self.device)
            if audio_modality is not None
            else torch.zeros(batch_size, self.config.audio_dim, device=self.device),
            text_modality.to(self.device)
            if text_modality is not None
            else torch.zeros(batch_size, self.config.text_dim, device=self.device),
            proprio_modality.to(self.device)
            if proprio_modality is not None
            else torch.zeros(batch_size, self.config.proprio_dim, device=self.device),
        ]

        # Fuse modalities
        return cast(torch.Tensor, self.fusion(modalities))

    def get_state(self) -> torch.Tensor:
        """Get perception state for Configurator.

        Returns:
            [state_dim] perception state summary
        """
        # Return zero state (will be updated with real perception)
        return torch.zeros(self.config.state_dim)


# =============================================================================
# SINGLETON ACCESS
# =============================================================================

_perception_module: PerceptionModule | None = None


def get_perception_module(config: PerceptionConfig | None = None) -> PerceptionModule:
    """Get or create global PerceptionModule."""
    global _perception_module
    if _perception_module is None:
        _perception_module = PerceptionModule(config)
        logger.info("Created global PerceptionModule")
    return _perception_module


def reset_perception_module() -> None:
    """Reset global PerceptionModule (for testing)."""
    global _perception_module
    _perception_module = None
