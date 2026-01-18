"""Multimodal Training Support for Kagami World Model.

CREATED: January 5, 2026

Provides unified multimodal training combining:
- Vision (images, video)
- Language (text, captions)
- Action (motor commands, decisions)
- Audio (speech, soundscapes) [future]

Architecture:
=============
    ┌─────────────────────────────────────────────────────────────────┐
    │                   MultimodalDataPipeline                         │
    │                                                                  │
    │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
    │  │ Vision       │  │ Language     │  │ Action       │          │
    │  │ Encoder      │  │ Encoder      │  │ Encoder      │          │
    │  │ (DINOv2)     │  │ (SentenceTF) │  │ (MLP)        │          │
    │  └──────────────┘  └──────────────┘  └──────────────┘          │
    │         │                 │                 │                   │
    │         └─────────────────┴─────────────────┘                   │
    │                           │                                      │
    │                    ┌──────▼──────┐                              │
    │                    │ E8 Fusion   │                              │
    │                    │ (Multimodal │                              │
    │                    │  Embeddings)│                              │
    │                    └──────┬──────┘                              │
    │                           │                                      │
    │                    ┌──────▼──────┐                              │
    │                    │ OrganismRSSM│                              │
    │                    │ (World Model)                              │
    │                    └─────────────┘                              │
    └─────────────────────────────────────────────────────────────────┘

References:
- Gato: https://arxiv.org/abs/2205.06175
- Flamingo: https://arxiv.org/abs/2204.14198
- V-JEPA 2: https://ai.meta.com/research/publications/v-jepa-2/
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

import torch
import torch.nn as nn
import torch.nn.functional as F

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class Modality(str, Enum):
    """Supported modalities."""

    VISION = "vision"  # Images, video frames
    LANGUAGE = "language"  # Text, captions
    ACTION = "action"  # Motor commands, decisions
    AUDIO = "audio"  # Speech, sounds (future)
    PROPRIOCEPTION = "proprio"  # Body state (future)


@dataclass
class ModalityConfig:
    """Configuration for a single modality."""

    name: Modality
    enabled: bool = True
    embed_dim: int = 768  # Embedding dimension
    max_seq_len: int = 256  # Max sequence length
    weight: float = 1.0  # Loss weight

    # Modality-specific
    encoder_type: str = "default"  # Encoder architecture
    pretrained: bool = True  # Use pretrained encoder
    freeze_encoder: bool = False  # Freeze encoder weights


@dataclass
class MultimodalConfig:
    """Configuration for multimodal training."""

    # Output dimension (matches OrganismRSSM bulk_dim)
    fusion_dim: int = 128

    # Individual modalities
    vision: ModalityConfig = field(
        default_factory=lambda: ModalityConfig(
            name=Modality.VISION,
            embed_dim=768,
            encoder_type="dinov2",
        )
    )
    language: ModalityConfig = field(
        default_factory=lambda: ModalityConfig(
            name=Modality.LANGUAGE,
            embed_dim=384,
            encoder_type="sentence_transformer",
        )
    )
    action: ModalityConfig = field(
        default_factory=lambda: ModalityConfig(
            name=Modality.ACTION,
            embed_dim=64,
            encoder_type="mlp",
        )
    )

    # Fusion
    fusion_type: str = "e8"  # e8, attention, concat
    use_cross_attention: bool = True
    num_cross_attention_layers: int = 2

    # Training
    contrastive_loss_weight: float = 0.1
    alignment_loss_weight: float = 0.1


class VisionEncoder(nn.Module):
    """Vision encoder using DINOv2 or similar.

    Encodes images/video frames to embeddings.
    """

    def __init__(self, config: ModalityConfig):
        """Initialize vision encoder."""
        super().__init__()
        self.config = config
        self.embed_dim = config.embed_dim

        # Initialize encoder based on type
        if config.encoder_type == "dinov2":
            self._init_dinov2()
        elif config.encoder_type == "vjepa2":
            self._init_vjepa2()
        else:
            self._init_simple()

        # Projection to fusion dimension
        self.projection = nn.Linear(self.embed_dim, config.embed_dim)

    def _init_dinov2(self) -> None:
        """Initialize DINOv2 encoder."""
        try:
            import timm

            self.backbone = timm.create_model(
                "vit_base_patch14_dinov2.lvd142m",
                pretrained=self.config.pretrained,
                num_classes=0,  # Remove classification head
            )

            if self.config.freeze_encoder:
                for param in self.backbone.parameters():
                    param.requires_grad = False

            logger.info("Initialized DINOv2 vision encoder")

        except ImportError:
            logger.warning("timm not available, using simple CNN")
            self._init_simple()

    def _init_vjepa2(self) -> None:
        """Initialize V-JEPA 2 encoder for video."""
        try:
            from transformers import AutoModel

            model_name = "facebook/vjepa2-vitl-fpc64-256"
            self.backbone = AutoModel.from_pretrained(model_name)

            if self.config.freeze_encoder:
                for param in self.backbone.parameters():
                    param.requires_grad = False

            logger.info(f"Initialized V-JEPA 2 vision encoder: {model_name}")

        except ImportError:
            logger.warning("transformers not available, using simple CNN")
            self._init_simple()

    def _init_simple(self) -> None:
        """Initialize simple CNN encoder."""
        self.backbone = nn.Sequential(
            nn.Conv2d(3, 64, kernel_size=7, stride=2, padding=3),
            nn.BatchNorm2d(64),
            nn.ReLU(),
            nn.MaxPool2d(2),
            nn.Conv2d(64, 128, kernel_size=3, padding=1),
            nn.BatchNorm2d(128),
            nn.ReLU(),
            nn.AdaptiveAvgPool2d((1, 1)),
            nn.Flatten(),
            nn.Linear(128, self.embed_dim),
        )
        logger.info("Initialized simple CNN vision encoder")

    def forward(
        self,
        images: torch.Tensor,
        return_all_tokens: bool = False,
    ) -> torch.Tensor:
        """Encode images to embeddings.

        Args:
            images: Input images [B, C, H, W] or video [B, T, C, H, W]
            return_all_tokens: Return all patch tokens (for attention)

        Returns:
            Embeddings [B, D] or [B, T, D] for video
        """
        # Handle video input
        is_video = images.dim() == 5
        if is_video:
            B, T, C, H, W = images.shape
            images = images.view(B * T, C, H, W)

        # Encode
        if hasattr(self.backbone, "forward_features"):
            features = self.backbone.forward_features(images)
            if isinstance(features, dict):
                features = features.get("x_norm_patchtokens", features.get("x", features))
            # Global pool if needed
            if features.dim() == 3:
                features = features.mean(dim=1)  # [B, D]
        else:
            features = self.backbone(images)

        # Project
        embeddings = self.projection(features)

        # Reshape for video
        if is_video:
            embeddings = embeddings.view(B, T, -1)

        return embeddings


class LanguageEncoder(nn.Module):
    """Language encoder using Sentence Transformers.

    Encodes text to embeddings.
    """

    def __init__(self, config: ModalityConfig):
        """Initialize language encoder."""
        super().__init__()
        self.config = config
        self.embed_dim = config.embed_dim

        # Initialize encoder
        if config.encoder_type == "sentence_transformer":
            self._init_sentence_transformer()
        else:
            self._init_simple()

        # Projection
        self.projection = nn.Linear(self.embed_dim, config.embed_dim)

    def _init_sentence_transformer(self) -> None:
        """Initialize Sentence Transformer encoder."""
        try:
            from sentence_transformers import SentenceTransformer

            model_name = "sentence-transformers/all-MiniLM-L6-v2"
            self.backbone = SentenceTransformer(model_name)
            self.embed_dim = self.backbone.get_sentence_embedding_dimension()

            if self.config.freeze_encoder:
                for param in self.backbone.parameters():
                    param.requires_grad = False

            logger.info(f"Initialized Sentence Transformer: {model_name}")

        except ImportError:
            logger.warning("sentence_transformers not available, using simple")
            self._init_simple()

    def _init_simple(self) -> None:
        """Initialize simple embedding + LSTM encoder."""
        self.backbone = nn.LSTM(
            input_size=256,
            hidden_size=self.embed_dim // 2,
            num_layers=2,
            batch_first=True,
            bidirectional=True,
        )
        self.char_embed = nn.Embedding(256, 256)  # Character-level
        logger.info("Initialized simple LSTM language encoder")

    def forward(
        self,
        text: list[str] | torch.Tensor,
    ) -> torch.Tensor:
        """Encode text to embeddings.

        Args:
            text: List of strings or tokenized input

        Returns:
            Embeddings [B, D]
        """
        if hasattr(self.backbone, "encode"):
            # Sentence Transformer
            embeddings = self.backbone.encode(
                text if isinstance(text, list) else text.tolist(),
                convert_to_tensor=True,
                show_progress_bar=False,
            )
        else:
            # Simple LSTM
            if isinstance(text, list):
                # Convert to character indices
                max_len = max(len(t) for t in text)
                indices = torch.zeros(len(text), max_len, dtype=torch.long)
                for i, t in enumerate(text):
                    for j, c in enumerate(t[:max_len]):
                        indices[i, j] = ord(c) % 256
                text = indices.to(next(self.parameters()).device)

            embedded = self.char_embed(text)
            _output, (h_n, _) = self.backbone(embedded)
            # Concatenate forward and backward final states
            embeddings = torch.cat([h_n[-2], h_n[-1]], dim=-1)

        # Project
        embeddings = self.projection(embeddings)

        return embeddings


class ActionEncoder(nn.Module):
    """Action encoder for motor commands and decisions.

    Encodes discrete or continuous actions to embeddings.
    """

    def __init__(self, config: ModalityConfig, action_dim: int = 32):
        """Initialize action encoder."""
        super().__init__()
        self.config = config
        self.action_dim = action_dim

        # MLP encoder
        self.encoder = nn.Sequential(
            nn.Linear(action_dim, 128),
            nn.ReLU(),
            nn.Linear(128, 256),
            nn.ReLU(),
            nn.Linear(256, config.embed_dim),
        )

        # For discrete actions
        self.discrete_embed = nn.Embedding(1000, action_dim)

    def forward(
        self,
        actions: torch.Tensor,
        discrete: bool = False,
    ) -> torch.Tensor:
        """Encode actions to embeddings.

        Args:
            actions: Action tensor [B, action_dim] or [B] for discrete
            discrete: Whether actions are discrete indices

        Returns:
            Embeddings [B, D]
        """
        if discrete:
            actions = self.discrete_embed(actions.long())

        return self.encoder(actions)


class E8ModalityFusion(nn.Module):
    """Fuse multimodal embeddings using E8 lattice structure.

    Projects each modality to E8 lattice, then fuses via E8 operations.
    """

    def __init__(self, config: MultimodalConfig):
        """Initialize E8 fusion module."""
        super().__init__()
        self.config = config

        # Projections to 8D E8 space per modality
        self.vision_to_e8 = nn.Linear(config.vision.embed_dim, 8)
        self.language_to_e8 = nn.Linear(config.language.embed_dim, 8)
        self.action_to_e8 = nn.Linear(config.action.embed_dim, 8)

        # E8 fusion (learned combination)
        self.e8_fusion = nn.Sequential(
            nn.Linear(24, 64),  # 3 modalities * 8D
            nn.ReLU(),
            nn.Linear(64, 8),
        )

        # Output projection
        self.output_proj = nn.Linear(8, config.fusion_dim)

    def forward(
        self,
        vision_emb: torch.Tensor | None = None,
        language_emb: torch.Tensor | None = None,
        action_emb: torch.Tensor | None = None,
    ) -> torch.Tensor:
        """Fuse multimodal embeddings.

        Args:
            vision_emb: Vision embeddings [B, D_v]
            language_emb: Language embeddings [B, D_l]
            action_emb: Action embeddings [B, D_a]

        Returns:
            Fused embeddings [B, fusion_dim]
        """
        batch_size = None
        device = None

        # Find batch size and device from available inputs
        for emb in [vision_emb, language_emb, action_emb]:
            if emb is not None:
                batch_size = emb.shape[0]
                device = emb.device
                break

        if batch_size is None:
            raise ValueError("At least one modality must be provided")

        # Project to E8
        e8_embeddings = []

        if vision_emb is not None:
            e8_embeddings.append(self.vision_to_e8(vision_emb))
        else:
            e8_embeddings.append(torch.zeros(batch_size, 8, device=device))

        if language_emb is not None:
            e8_embeddings.append(self.language_to_e8(language_emb))
        else:
            e8_embeddings.append(torch.zeros(batch_size, 8, device=device))

        if action_emb is not None:
            e8_embeddings.append(self.action_to_e8(action_emb))
        else:
            e8_embeddings.append(torch.zeros(batch_size, 8, device=device))

        # Concatenate and fuse
        concat = torch.cat(e8_embeddings, dim=-1)  # [B, 24]
        fused_e8 = self.e8_fusion(concat)  # [B, 8]

        # Quantize to E8 lattice (optional, for discrete structure)
        # fused_e8 = self._quantize_e8(fused_e8)

        # Project to output dimension
        output = self.output_proj(fused_e8)

        return output

    def _quantize_e8(self, x: torch.Tensor) -> torch.Tensor:
        """Quantize to nearest E8 lattice point.

        Uses the decoding algorithm for E8 via D8.
        """
        # Simple version: round to nearest half-integer grid
        # Full E8 quantization would use kagami_math.e8_lattice_quantizer
        return torch.round(x * 2) / 2


class CrossModalAttention(nn.Module):
    """Cross-modal attention for fusing different modalities."""

    def __init__(self, config: MultimodalConfig):
        """Initialize cross-modal attention."""
        super().__init__()
        self.config = config

        # Attention layers per modality pair
        self.vision_to_language = nn.MultiheadAttention(
            embed_dim=config.vision.embed_dim,
            num_heads=8,
            batch_first=True,
        )
        self.language_to_vision = nn.MultiheadAttention(
            embed_dim=config.language.embed_dim,
            num_heads=8,
            batch_first=True,
        )

        # Output projection
        self.output_proj = nn.Linear(
            config.vision.embed_dim + config.language.embed_dim + config.action.embed_dim,
            config.fusion_dim,
        )

    def forward(
        self,
        vision_emb: torch.Tensor | None = None,
        language_emb: torch.Tensor | None = None,
        action_emb: torch.Tensor | None = None,
    ) -> torch.Tensor:
        """Fuse with cross-attention.

        Args:
            vision_emb: [B, D_v] or [B, T_v, D_v]
            language_emb: [B, D_l] or [B, T_l, D_l]
            action_emb: [B, D_a]

        Returns:
            Fused embeddings [B, fusion_dim]
        """
        embeddings = []

        # Ensure sequence dimension
        if vision_emb is not None:
            if vision_emb.dim() == 2:
                vision_emb = vision_emb.unsqueeze(1)
            embeddings.append(vision_emb.mean(dim=1))

        if language_emb is not None:
            if language_emb.dim() == 2:
                language_emb = language_emb.unsqueeze(1)
            embeddings.append(language_emb.mean(dim=1))

        if action_emb is not None:
            embeddings.append(action_emb)

        # Pad missing modalities with zeros
        batch_size = embeddings[0].shape[0]
        device = embeddings[0].device

        while len(embeddings) < 3:
            # Add zero padding for missing modality
            embeddings.append(torch.zeros(batch_size, self.config.fusion_dim, device=device))

        # Concatenate and project
        concat = torch.cat(embeddings, dim=-1)
        output = self.output_proj(concat)

        return output


class MultimodalEncoder(nn.Module):
    """Complete multimodal encoder for Kagami.

    Combines vision, language, and action encoders with fusion.
    """

    def __init__(self, config: MultimodalConfig):
        """Initialize multimodal encoder."""
        super().__init__()
        self.config = config

        # Individual encoders
        self.vision_encoder = VisionEncoder(config.vision) if config.vision.enabled else None
        self.language_encoder = (
            LanguageEncoder(config.language) if config.language.enabled else None
        )
        self.action_encoder = ActionEncoder(config.action) if config.action.enabled else None

        # Fusion
        if config.fusion_type == "e8":
            self.fusion = E8ModalityFusion(config)
        elif config.fusion_type == "attention":
            self.fusion = CrossModalAttention(config)
        else:
            # Simple concatenation + projection
            total_dim = sum(
                cfg.embed_dim
                for cfg in [config.vision, config.language, config.action]
                if cfg.enabled
            )
            self.fusion = nn.Linear(total_dim, config.fusion_dim)

    def forward(
        self,
        images: torch.Tensor | None = None,
        text: list[str] | torch.Tensor | None = None,
        actions: torch.Tensor | None = None,
    ) -> dict[str, torch.Tensor]:
        """Encode multimodal inputs.

        Args:
            images: Image/video tensor
            text: Text input (list of strings or tokenized)
            actions: Action tensor

        Returns:
            Dictionary with embeddings
        """
        outputs = {}

        # Encode each modality
        if images is not None and self.vision_encoder is not None:
            outputs["vision"] = self.vision_encoder(images)

        if text is not None and self.language_encoder is not None:
            outputs["language"] = self.language_encoder(text)

        if actions is not None and self.action_encoder is not None:
            outputs["action"] = self.action_encoder(actions)

        # Fuse modalities
        if isinstance(self.fusion, (E8ModalityFusion, CrossModalAttention)):
            outputs["fused"] = self.fusion(
                vision_emb=outputs.get("vision"),
                language_emb=outputs.get("language"),
                action_emb=outputs.get("action"),
            )
        else:
            # Simple concatenation
            to_concat = list(outputs.values())
            if to_concat:
                concat = torch.cat(to_concat, dim=-1)
                outputs["fused"] = self.fusion(concat)

        return outputs


class MultimodalContrastiveLoss(nn.Module):
    """Contrastive loss for multimodal alignment.

    Aligns embeddings from different modalities via contrastive learning.
    """

    def __init__(self, temperature: float = 0.07):
        """Initialize contrastive loss."""
        super().__init__()
        self.temperature = temperature

    def forward(
        self,
        emb1: torch.Tensor,
        emb2: torch.Tensor,
        labels: torch.Tensor | None = None,
    ) -> torch.Tensor:
        """Compute contrastive loss.

        Args:
            emb1: First modality embeddings [B, D]
            emb2: Second modality embeddings [B, D]
            labels: Optional labels for supervised contrastive

        Returns:
            Contrastive loss
        """
        # Normalize
        emb1 = F.normalize(emb1, p=2, dim=-1)
        emb2 = F.normalize(emb2, p=2, dim=-1)

        # Compute similarity
        sim = torch.matmul(emb1, emb2.T) / self.temperature  # [B, B]

        # Labels: positive pairs on diagonal
        if labels is None:
            labels = torch.arange(sim.shape[0], device=sim.device)

        # Cross-entropy loss both directions
        loss_1 = F.cross_entropy(sim, labels)
        loss_2 = F.cross_entropy(sim.T, labels)

        return (loss_1 + loss_2) / 2


def create_multimodal_encoder(
    fusion_dim: int = 128,
    vision_enabled: bool = True,
    language_enabled: bool = True,
    action_enabled: bool = True,
    fusion_type: str = "e8",
) -> MultimodalEncoder:
    """Factory function for multimodal encoder.

    Args:
        fusion_dim: Output embedding dimension
        vision_enabled: Enable vision modality
        language_enabled: Enable language modality
        action_enabled: Enable action modality
        fusion_type: Fusion method (e8, attention, concat)

    Returns:
        Configured MultimodalEncoder
    """
    config = MultimodalConfig(
        fusion_dim=fusion_dim,
        fusion_type=fusion_type,
    )
    config.vision.enabled = vision_enabled
    config.language.enabled = language_enabled
    config.action.enabled = action_enabled

    return MultimodalEncoder(config)


__all__ = [
    "ActionEncoder",
    "CrossModalAttention",
    "E8ModalityFusion",
    "LanguageEncoder",
    "Modality",
    "ModalityConfig",
    "MultimodalConfig",
    "MultimodalContrastiveLoss",
    "MultimodalEncoder",
    "VisionEncoder",
    "create_multimodal_encoder",
]
