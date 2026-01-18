"""Latent Action Model (LAM) - Learn Actions from Unlabeled Video.

CREATED: January 4, 2026

Implements the Latent Action Model from Genie/Genie 2 that learns discrete
actions from video transitions WITHOUT explicit action labels.

Why This Matters:
================
Most video data (YouTube, movies, games) has NO action labels. The LAM
learns a discrete vocabulary of actions by analyzing frame-to-frame changes.

Key Insight (Genie):
====================
Given two consecutive frames, the "action" is the transformation needed
to go from frame t to frame t+1. We learn to:
1. Encode this transformation as a discrete code
2. Reconstruct frame t+1 from frame t + action code

Architecture:
=============
```
Frame t ─────┐
             ├──▶ ActionEncoder ──▶ VQ Codebook ──▶ action_idx
Frame t+1 ───┘         │
                       ▼
Frame t + action ──▶ FramePredictor ──▶ Predicted t+1
```

The VQ codebook learns a discrete vocabulary of ~256-1024 "verbs" that
describe possible transformations in the video domain.

References:
- Bruce et al. (2024): Genie - Generative Interactive Environments
- Bruce et al. (2024): Genie 2 - Foundation World Model
- van den Oord et al. (2017): Neural Discrete Representation Learning (VQ-VAE)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import torch
import torch.nn as nn
import torch.nn.functional as F

logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION
# =============================================================================


@dataclass
class LatentActionConfig:
    """Configuration for Latent Action Model."""

    # Encoder dimensions
    frame_dim: int = 256  # Encoded frame dimension (from image encoder)
    hidden_dim: int = 512
    action_dim: int = 64  # Latent action embedding dimension

    # VQ Codebook
    num_actions: int = 256  # Number of discrete actions in vocabulary
    codebook_decay: float = 0.99  # EMA decay for codebook update
    commitment_cost: float = 0.25  # Beta for commitment loss

    # Architecture
    encoder_layers: int = 3
    predictor_layers: int = 3
    use_residual: bool = True  # Predict residual (delta) instead of full frame

    # Training
    temperature: float = 1.0  # Gumbel softmax temperature (annealed during training)
    straight_through: bool = True  # Use straight-through estimator


# =============================================================================
# VECTOR QUANTIZER
# =============================================================================


class VectorQuantizer(nn.Module):
    """Vector Quantizer with EMA codebook update (VQ-VAE style).

    Learns a discrete codebook of action embeddings.
    """

    def __init__(
        self,
        num_embeddings: int,
        embedding_dim: int,
        commitment_cost: float = 0.25,
        decay: float = 0.99,
    ):
        super().__init__()
        self.num_embeddings = num_embeddings
        self.embedding_dim = embedding_dim
        self.commitment_cost = commitment_cost
        self.decay = decay

        # Codebook
        self.embedding = nn.Embedding(num_embeddings, embedding_dim)
        self.embedding.weight.data.uniform_(-1.0 / num_embeddings, 1.0 / num_embeddings)

        # EMA tracking
        self.register_buffer("_ema_cluster_size", torch.zeros(num_embeddings))
        self.register_buffer("_ema_embedding_sum", self.embedding.weight.data.clone())

    def forward(self, z: torch.Tensor) -> tuple[torch.Tensor, dict[str, Any]]:
        """Quantize input to nearest codebook entry.

        Args:
            z: [B, embedding_dim] continuous latent

        Returns:
            quantized: [B, embedding_dim] quantized latent
            info: Dict with indices, loss, etc.
        """
        # Flatten if needed
        flat_z = z.view(-1, self.embedding_dim)

        # Compute distances to codebook
        distances = (
            flat_z.pow(2).sum(dim=1, keepdim=True)
            - 2 * flat_z @ self.embedding.weight.t()
            + self.embedding.weight.pow(2).sum(dim=1, keepdim=True).t()
        )

        # Find nearest
        indices = distances.argmin(dim=1)

        # Get quantized
        quantized = self.embedding(indices)
        quantized = quantized.view_as(z)

        # Compute losses
        commitment_loss = F.mse_loss(z, quantized.detach())
        codebook_loss = F.mse_loss(quantized, z.detach())

        # EMA codebook update (during training)
        if self.training:
            with torch.no_grad():
                # Count assignments
                encodings = F.one_hot(indices, self.num_embeddings).float()
                cluster_size = encodings.sum(dim=0)
                embedding_sum = encodings.t() @ flat_z

                # EMA update
                self._ema_cluster_size.mul_(self.decay).add_(cluster_size, alpha=1 - self.decay)
                self._ema_embedding_sum.mul_(self.decay).add_(embedding_sum, alpha=1 - self.decay)

                # Update codebook
                n = self._ema_cluster_size.sum()
                cluster_size_normalized = (
                    (self._ema_cluster_size + 1e-5) / (n + self.num_embeddings * 1e-5) * n
                )
                self.embedding.weight.data.copy_(
                    self._ema_embedding_sum / cluster_size_normalized.unsqueeze(1)
                )

        # Straight-through estimator
        quantized = z + (quantized - z).detach()

        info = {
            "indices": indices.view(z.shape[:-1]),
            "commitment_loss": commitment_loss,
            "codebook_loss": codebook_loss,
            "vq_loss": codebook_loss + self.commitment_cost * commitment_loss,
            "perplexity": self._compute_perplexity(indices),
        }

        return quantized, info

    def _compute_perplexity(self, indices: torch.Tensor) -> torch.Tensor:
        """Compute codebook usage perplexity."""
        encodings = F.one_hot(indices, self.num_embeddings).float()
        avg_probs = encodings.mean(dim=0)
        perplexity = torch.exp(-torch.sum(avg_probs * torch.log(avg_probs + 1e-10)))
        return perplexity

    def get_codebook(self) -> torch.Tensor:
        """Get current codebook embeddings."""
        return self.embedding.weight.data


# =============================================================================
# ACTION ENCODER
# =============================================================================


class ActionEncoder(nn.Module):
    """Encodes frame transition into latent action.

    Takes (frame_t, frame_t+1) and outputs a continuous action embedding.
    """

    def __init__(self, config: LatentActionConfig):
        super().__init__()
        self.config = config

        # Input: concatenate two frames
        self.input_proj = nn.Linear(config.frame_dim * 2, config.hidden_dim)

        # MLP layers
        layers = []
        for _ in range(config.encoder_layers):
            layers.extend(
                [
                    nn.Linear(config.hidden_dim, config.hidden_dim),
                    nn.LayerNorm(config.hidden_dim),
                    nn.GELU(),
                ]
            )
        self.encoder = nn.Sequential(*layers)

        # Output projection to action dimension
        self.output_proj = nn.Linear(config.hidden_dim, config.action_dim)

    def forward(self, frame_t: torch.Tensor, frame_t1: torch.Tensor) -> torch.Tensor:
        """Encode transition to action embedding.

        Args:
            frame_t: [B, frame_dim] encoded frame at time t
            frame_t1: [B, frame_dim] encoded frame at time t+1

        Returns:
            [B, action_dim] continuous action embedding
        """
        # Concatenate frames
        x = torch.cat([frame_t, frame_t1], dim=-1)

        # Encode
        x = self.input_proj(x)
        x = self.encoder(x)
        action = self.output_proj(x)

        return action


# =============================================================================
# FRAME PREDICTOR
# =============================================================================


class FramePredictor(nn.Module):
    """Predicts next frame given current frame and action.

    Can predict either full frame or residual (delta).
    """

    def __init__(self, config: LatentActionConfig):
        super().__init__()
        self.config = config

        # Input: frame + action
        self.input_proj = nn.Linear(config.frame_dim + config.action_dim, config.hidden_dim)

        # MLP layers
        layers = []
        for _ in range(config.predictor_layers):
            layers.extend(
                [
                    nn.Linear(config.hidden_dim, config.hidden_dim),
                    nn.LayerNorm(config.hidden_dim),
                    nn.GELU(),
                ]
            )
        self.predictor = nn.Sequential(*layers)

        # Output projection
        self.output_proj = nn.Linear(config.hidden_dim, config.frame_dim)

    def forward(self, frame_t: torch.Tensor, action: torch.Tensor) -> torch.Tensor:
        """Predict next frame.

        Args:
            frame_t: [B, frame_dim] current frame
            action: [B, action_dim] action embedding

        Returns:
            [B, frame_dim] predicted next frame (or delta if use_residual)
        """
        # Concatenate inputs
        x = torch.cat([frame_t, action], dim=-1)

        # Predict
        x = self.input_proj(x)
        x = self.predictor(x)
        output = self.output_proj(x)

        # Residual prediction
        if self.config.use_residual:
            output = frame_t + output

        return output


# =============================================================================
# LATENT ACTION MODEL
# =============================================================================


class LatentActionModel(nn.Module):
    """Complete Latent Action Model (LAM) from Genie.

    Learns discrete action vocabulary from video without labels.

    Usage:
        lam = LatentActionModel(config)

        # Training: Learn action vocabulary
        pred_frame, action_idx, losses = lam(frame_t, frame_t1)

        # Inference: Execute action
        next_frame = lam.execute_action(frame_t, action_idx)

        # Get action vocabulary
        actions = lam.get_action_vocabulary()
    """

    def __init__(self, config: LatentActionConfig | None = None):
        super().__init__()
        self.config = config or LatentActionConfig()

        # Components
        self.action_encoder = ActionEncoder(self.config)
        self.vector_quantizer = VectorQuantizer(
            num_embeddings=self.config.num_actions,
            embedding_dim=self.config.action_dim,
            commitment_cost=self.config.commitment_cost,
            decay=self.config.codebook_decay,
        )
        self.frame_predictor = FramePredictor(self.config)

        logger.info(
            f"LatentActionModel initialized:\n"
            f"  Action vocabulary size: {self.config.num_actions}\n"
            f"  Action embedding dim: {self.config.action_dim}\n"
            f"  Residual prediction: {self.config.use_residual}"
        )

    def forward(
        self,
        frame_t: torch.Tensor,
        frame_t1: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor, dict[str, torch.Tensor]]:
        """Forward pass for training.

        Args:
            frame_t: [B, frame_dim] encoded frame at time t
            frame_t1: [B, frame_dim] encoded frame at time t+1

        Returns:
            pred_frame: [B, frame_dim] predicted frame t+1
            action_indices: [B] discrete action indices
            losses: Dict of loss components
        """
        # Encode transition to continuous action
        action_continuous = self.action_encoder(frame_t, frame_t1)

        # Quantize to discrete action
        action_quantized, vq_info = self.vector_quantizer(action_continuous)

        # Predict next frame
        pred_frame = self.frame_predictor(frame_t, action_quantized)

        # Reconstruction loss
        reconstruction_loss = F.mse_loss(pred_frame, frame_t1)

        # Total loss
        total_loss = reconstruction_loss + vq_info["vq_loss"]

        losses = {
            "loss": total_loss,
            "reconstruction": reconstruction_loss,
            "vq": vq_info["vq_loss"],
            "commitment": vq_info["commitment_loss"],
            "codebook": vq_info["codebook_loss"],
            "perplexity": vq_info["perplexity"],
        }

        return pred_frame, vq_info["indices"], losses

    @torch.no_grad()
    def infer_action(
        self,
        frame_t: torch.Tensor,
        frame_t1: torch.Tensor,
    ) -> torch.Tensor:
        """Infer the discrete action for a transition.

        Args:
            frame_t: [B, frame_dim] current frame
            frame_t1: [B, frame_dim] next frame

        Returns:
            [B] discrete action indices
        """
        action_continuous = self.action_encoder(frame_t, frame_t1)
        _, vq_info = self.vector_quantizer(action_continuous)
        return vq_info["indices"]

    @torch.no_grad()
    def execute_action(
        self,
        frame_t: torch.Tensor,
        action_idx: torch.Tensor | int,
    ) -> torch.Tensor:
        """Execute a discrete action to predict next frame.

        Args:
            frame_t: [B, frame_dim] current frame
            action_idx: [B] or int - discrete action index

        Returns:
            [B, frame_dim] predicted next frame
        """
        if isinstance(action_idx, int):
            action_idx = torch.full(
                (frame_t.shape[0],), action_idx, device=frame_t.device, dtype=torch.long
            )

        # Get action embedding from codebook
        action_emb = self.vector_quantizer.embedding(action_idx)

        # Predict next frame
        return self.frame_predictor(frame_t, action_emb)

    def get_action_vocabulary(self) -> torch.Tensor:
        """Get the learned action vocabulary (codebook).

        Returns:
            [num_actions, action_dim] action embeddings
        """
        return self.vector_quantizer.get_codebook()

    def get_action_usage(self) -> torch.Tensor:
        """Get usage statistics for each action in vocabulary.

        Returns:
            [num_actions] usage counts (from EMA)
        """
        return self.vector_quantizer._ema_cluster_size


# =============================================================================
# VIDEO-LEVEL LAM
# =============================================================================


class VideoLatentActionModel(nn.Module):
    """Latent Action Model that processes full video sequences.

    Wraps LAM to handle video inputs directly, including:
    - Frame encoding (via pretrained encoder)
    - Temporal processing
    - Action sequence extraction
    """

    def __init__(
        self,
        config: LatentActionConfig | None = None,
        frame_encoder: nn.Module | None = None,
    ):
        super().__init__()
        self.config = config or LatentActionConfig()

        # Frame encoder (should be pretrained, frozen)
        if frame_encoder is not None:
            self.frame_encoder = frame_encoder
            for param in self.frame_encoder.parameters():
                param.requires_grad = False
        else:
            # Placeholder - in practice, use DINOv2/CLIP
            self.frame_encoder = nn.Sequential(
                nn.Conv2d(3, 64, 7, stride=2, padding=3),
                nn.ReLU(),
                nn.AdaptiveAvgPool2d(1),
                nn.Flatten(),
                nn.Linear(64, self.config.frame_dim),
            )

        # LAM
        self.lam = LatentActionModel(self.config)

    def forward(
        self,
        video: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor, dict[str, torch.Tensor]]:
        """Process video to extract action sequence.

        Args:
            video: [B, T, C, H, W] or [B, T, frame_dim] video

        Returns:
            pred_frames: [B, T-1, frame_dim] predicted frames
            action_indices: [B, T-1] action sequence
            losses: Dict of aggregated losses
        """
        _B, T = video.shape[:2]

        # Encode frames if needed
        if video.dim() == 5:  # [B, T, C, H, W]
            frames = []
            for t in range(T):
                frame = self.frame_encoder(video[:, t])
                frames.append(frame)
            frames = torch.stack(frames, dim=1)  # [B, T, frame_dim]
        else:
            frames = video  # Already encoded

        # Process consecutive pairs
        all_pred = []
        all_idx = []
        total_loss = 0

        for t in range(T - 1):
            frame_t = frames[:, t]
            frame_t1 = frames[:, t + 1]

            pred, idx, losses = self.lam(frame_t, frame_t1)
            all_pred.append(pred)
            all_idx.append(idx)
            total_loss = total_loss + losses["loss"]

        pred_frames = torch.stack(all_pred, dim=1)  # [B, T-1, frame_dim]
        action_indices = torch.stack(all_idx, dim=1)  # [B, T-1]

        return pred_frames, action_indices, {"loss": total_loss / (T - 1)}

    @torch.no_grad()
    def extract_action_sequence(self, video: torch.Tensor) -> torch.Tensor:
        """Extract action sequence from video.

        Args:
            video: [B, T, C, H, W] or [B, T, frame_dim] video

        Returns:
            [B, T-1] action indices
        """
        _, action_indices, _ = self.forward(video)
        return action_indices


# =============================================================================
# FACTORY
# =============================================================================


def create_latent_action_model(
    num_actions: int = 256,
    action_dim: int = 64,
    frame_dim: int = 256,
) -> LatentActionModel:
    """Factory function for LatentActionModel.

    Args:
        num_actions: Size of action vocabulary
        action_dim: Dimension of action embeddings
        frame_dim: Dimension of encoded frames

    Returns:
        Configured LatentActionModel
    """
    config = LatentActionConfig(
        num_actions=num_actions,
        action_dim=action_dim,
        frame_dim=frame_dim,
    )
    return LatentActionModel(config)


__all__ = [
    "ActionEncoder",
    "FramePredictor",
    "LatentActionConfig",
    "LatentActionModel",
    "VectorQuantizer",
    "VideoLatentActionModel",
    "create_latent_action_model",
]
