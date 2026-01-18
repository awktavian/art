"""H-JEPA: Hierarchical Joint-Embedding Predictive Architecture.

CRITICAL FIX (December 27, 2025):
=================================
PREVIOUS: Self-consistency loss (predicting current target from current state)
NEW: Proper future prediction with spatiotemporal masking

This module implements H-JEPA following LeCun's world model architecture:
- Predictor network: Predicts FUTURE E8 states from current context
- Target network: EMA of predictor (provides stable targets)
- Masking strategy: Random masking of future positions
- Multi-horizon: Predictions at [1, 2, 4, 8] steps ahead

Key insight from V-JEPA (Meta 2024):
- Non-generative: Predict in latent space, not pixel space
- Asymmetric: Large context encoder, small predictor
- Masking: High mask ratio (75%+) forces semantic understanding

References:
- LeCun (2022): A Path Towards Autonomous Machine Intelligence
- Assran et al. (2023): Self-Supervised Learning from Images with a Joint-Embedding Predictive Architecture
- Bardes et al. (2024): V-JEPA: Video Joint-Embedding Predictive Architecture

Created: December 27, 2025
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Any

import torch
import torch.nn as nn
import torch.nn.functional as F

logger = logging.getLogger(__name__)


@dataclass
class HJEPAConfig:
    """Configuration for H-JEPA module."""

    # Dimensions
    e8_dim: int = 8  # E8 latent dimension
    hidden_dim: int = 128  # Predictor hidden dimension
    context_dim: int = 64  # Context encoder output dimension

    # Architecture
    num_predictor_layers: int = 3  # Predictor depth
    num_context_layers: int = 2  # Context encoder depth
    num_heads: int = 4  # Attention heads in predictor
    dropout: float = 0.1

    # Horizons
    horizons: tuple[int, ...] = (1, 2, 4, 8)  # Prediction horizons

    # Masking (Updated Jan 4, 2026 - V-JEPA 2 style)
    mask_ratio: float = 0.90  # Target mask ratio (V-JEPA 2 uses 0.9!)
    mask_ratio_min: float = 0.50  # Starting mask ratio for curriculum warmup
    mask_ratio_warmup_steps: int = 10000  # Steps to ramp from min to target
    min_mask_patches: int = 4  # Minimum number of masked positions

    # EMA target
    ema_decay: float = 0.996  # Target network EMA decay
    ema_warmup_steps: int = 1000  # Steps before using full decay

    # Loss
    loss_type: str = "smooth_l1"  # "mse", "smooth_l1", "cosine"
    normalize_targets: bool = True  # L2 normalize targets (from BYOL/DINO)

    # Action Conditioning (TD-MPC2 style) - ADDED Jan 4, 2026
    action_dim: int = 0  # Action dimension (0 = no action conditioning)
    action_hidden_dim: int = 64  # Hidden dim for action embedding
    action_fusion: str = "add"  # "add", "concat", "film" - how to fuse with queries


class PositionalEncoding(nn.Module):
    """Sinusoidal positional encoding for temporal sequences."""

    def __init__(self, d_model: int, max_len: int = 512, dropout: float = 0.1):
        super().__init__()
        self.dropout = nn.Dropout(p=dropout)

        pe = torch.zeros(max_len, d_model)
        position = torch.arange(0, max_len, dtype=torch.float).unsqueeze(1)
        div_term = torch.exp(torch.arange(0, d_model, 2).float() * (-math.log(10000.0) / d_model))

        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term[: d_model // 2])

        self.register_buffer("pe", pe.unsqueeze(0))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Add positional encoding to input.

        Args:
            x: [B, T, D] input tensor

        Returns:
            [B, T, D] with positional encoding added
        """
        x = x + self.pe[:, : x.size(1)]  # type: ignore[index]
        return self.dropout(x)


class HJEPAContextEncoder(nn.Module):
    """Context encoder: encodes visible (unmasked) E8 states.

    Architecture:
        E8 [B, T, 8] → Linear → LayerNorm → Transformer layers → Context [B, T, context_dim]
    """

    def __init__(self, config: HJEPAConfig):
        super().__init__()
        self.config = config

        # Input projection
        self.input_proj = nn.Sequential(
            nn.Linear(config.e8_dim, config.hidden_dim),
            nn.LayerNorm(config.hidden_dim),
            nn.GELU(),
        )

        # Positional encoding
        self.pos_enc = PositionalEncoding(config.hidden_dim, dropout=config.dropout)

        # Transformer layers
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=config.hidden_dim,
            nhead=config.num_heads,
            dim_feedforward=config.hidden_dim * 4,
            dropout=config.dropout,
            activation="gelu",
            batch_first=True,
        )
        self.transformer = nn.TransformerEncoder(
            encoder_layer, num_layers=config.num_context_layers
        )

        # Output projection to context dim
        self.output_proj = nn.Linear(config.hidden_dim, config.context_dim)

    def forward(
        self,
        e8_sequence: torch.Tensor,
        mask: torch.Tensor | None = None,
    ) -> torch.Tensor:
        """Encode visible E8 states into context.

        Args:
            e8_sequence: [B, T, 8] E8 latent sequence
            mask: [B, T] boolean mask (True = visible, False = masked)

        Returns:
            [B, T, context_dim] context representations
        """
        # Project to hidden dim
        x = self.input_proj(e8_sequence)  # [B, T, hidden_dim]

        # Add positional encoding
        x = self.pos_enc(x)

        # Apply mask to attention if provided
        attn_mask = None
        if mask is not None:
            # Create attention mask: masked positions can't attend to anything
            # and nothing can attend to masked positions
            attn_mask = ~mask.unsqueeze(1).expand(-1, mask.size(1), -1)  # [B, T, T]
            attn_mask = attn_mask.float() * -1e9  # Convert to additive mask

        # Transformer encoding
        # Note: PyTorch TransformerEncoder expects [B, T, D] with batch_first=True
        if attn_mask is not None:
            # Need to handle per-sample masks
            # For simplicity, use key_padding_mask instead
            key_padding_mask = ~mask if mask is not None else None  # [B, T], True = ignore
            x = self.transformer(x, src_key_padding_mask=key_padding_mask)
        else:
            x = self.transformer(x)

        # Project to context dim
        context = self.output_proj(x)  # [B, T, context_dim]

        return context


class HJEPAPredictor(nn.Module):
    """Predictor: predicts target representations at masked/future positions.

    Architecture:
        Context [B, T, context_dim] + Position queries (+ Actions) → Transformer → Predictions [B, T, e8_dim]

    Key insight from I-JEPA/V-JEPA:
    - Predictor is NARROWER than context encoder
    - Uses position queries to specify what to predict
    - Cross-attention from queries to context

    Action Conditioning (TD-MPC2 style, Jan 4, 2026):
    - When action_dim > 0, actions are embedded and fused with position queries
    - Supports three fusion modes: add, concat, FiLM
    - Enables model-based planning for downstream tasks
    """

    def __init__(self, config: HJEPAConfig):
        super().__init__()
        self.config = config

        # Position query embeddings (learnable)
        # These tell the predictor which position to predict
        self.position_queries = nn.Parameter(torch.randn(1, 512, config.context_dim) * 0.02)

        # Horizon embeddings (one per horizon)
        self.horizon_emb = nn.Embedding(len(config.horizons), config.context_dim)

        # === ACTION CONDITIONING (Jan 4, 2026) ===
        self.use_actions = config.action_dim > 0
        if self.use_actions:
            # Action encoder: action → hidden → context_dim
            self.action_encoder = nn.Sequential(
                nn.Linear(config.action_dim, config.action_hidden_dim),
                nn.LayerNorm(config.action_hidden_dim),
                nn.GELU(),
                nn.Linear(config.action_hidden_dim, config.context_dim),
            )

            # FiLM conditioning (if using FiLM fusion)
            if config.action_fusion == "film":
                self.film_scale = nn.Linear(config.context_dim, config.context_dim)
                self.film_shift = nn.Linear(config.context_dim, config.context_dim)

            # Concat projection (if using concat fusion)
            if config.action_fusion == "concat":
                self.concat_proj = nn.Linear(config.context_dim * 2, config.context_dim)

            logger.info(
                f"HJEPAPredictor: Action conditioning enabled "
                f"(dim={config.action_dim}, fusion={config.action_fusion})"
            )

        # Transformer decoder (cross-attends to context)
        decoder_layer = nn.TransformerDecoderLayer(
            d_model=config.context_dim,
            nhead=config.num_heads,
            dim_feedforward=config.context_dim * 4,
            dropout=config.dropout,
            activation="gelu",
            batch_first=True,
        )
        self.transformer = nn.TransformerDecoder(
            decoder_layer, num_layers=config.num_predictor_layers
        )

        # Per-horizon output heads (predict E8 for each horizon)
        self.output_heads = nn.ModuleDict(
            {
                f"horizon_{h}": nn.Sequential(
                    nn.Linear(config.context_dim, config.context_dim),
                    nn.GELU(),
                    nn.Linear(config.context_dim, config.e8_dim),
                )
                for h in config.horizons
            }
        )

    def _fuse_actions(
        self,
        queries: torch.Tensor,
        action_emb: torch.Tensor,
    ) -> torch.Tensor:
        """Fuse action embeddings with position queries.

        Args:
            queries: [B, T, context_dim] position queries
            action_emb: [B, T, context_dim] action embeddings

        Returns:
            [B, T, context_dim] fused queries
        """
        fusion = self.config.action_fusion

        if fusion == "add":
            # Simple additive fusion
            return queries + action_emb

        elif fusion == "concat":
            # Concatenate and project
            concat = torch.cat([queries, action_emb], dim=-1)  # [B, T, 2*context_dim]
            return self.concat_proj(concat)

        elif fusion == "film":
            # Feature-wise Linear Modulation
            scale = torch.sigmoid(self.film_scale(action_emb))  # [B, T, context_dim]
            shift = self.film_shift(action_emb)  # [B, T, context_dim]
            return queries * scale + shift

        else:
            raise ValueError(f"Unknown action fusion mode: {fusion}")

    def forward(
        self,
        context: torch.Tensor,
        target_positions: torch.Tensor,
        horizon_idx: int,
        actions: torch.Tensor | None = None,
    ) -> torch.Tensor:
        """Predict E8 states at specified positions, optionally conditioned on actions.

        Args:
            context: [B, T_visible, context_dim] encoded context
            target_positions: [B, T_target] position indices to predict
            horizon_idx: Which horizon (index into config.horizons)
            actions: [B, T_target, action_dim] optional actions for each target position
                     If provided and action_dim > 0, predictions are action-conditioned.

        Returns:
            [B, T_target, e8_dim] predicted E8 states
        """
        B, T_target = target_positions.shape

        # Get position queries for target positions
        queries = self.position_queries[:, :T_target, :].expand(
            B, -1, -1
        )  # [B, T_target, context_dim]

        # Add horizon embedding
        horizon_emb = self.horizon_emb(
            torch.full((B, T_target), horizon_idx, device=context.device, dtype=torch.long)
        )  # [B, T_target, context_dim]
        queries = queries + horizon_emb

        # === ACTION CONDITIONING ===
        if self.use_actions and actions is not None:
            # Encode actions
            action_emb = self.action_encoder(actions)  # [B, T_target, context_dim]
            # Fuse with queries
            queries = self._fuse_actions(queries, action_emb)

        # Cross-attend to context
        predictions = self.transformer(queries, context)  # [B, T_target, context_dim]

        # Output head for this horizon
        horizon_key = f"horizon_{self.config.horizons[horizon_idx]}"
        output = self.output_heads[horizon_key](predictions)  # [B, T_target, e8_dim]

        return output


class HJEPAModule(nn.Module):
    """Complete H-JEPA module with proper future prediction.

    ARCHITECTURE:
    =============
    1. Masking: Randomly mask positions in E8 sequence
    2. Context Encoder: Encode visible positions
    3. Predictor: Predict masked/future positions from context
    4. Target Encoder: EMA copy (provides stable targets)
    5. Loss: MSE/SmoothL1/Cosine between predictions and targets

    CRITICAL DIFFERENCE FROM PREVIOUS IMPLEMENTATION:
    =================================================
    Previous: pred(s_t) vs target(s_t) (WRONG - self-consistency)
    Now: pred(context) vs target(s_{t+k}) (CORRECT - future prediction)
    """

    def __init__(self, config: HJEPAConfig | None = None):
        super().__init__()
        self.config = config or HJEPAConfig()

        # Online networks (trainable)
        self.context_encoder = HJEPAContextEncoder(self.config)
        self.predictor = HJEPAPredictor(self.config)

        # Target encoder (EMA, frozen)
        self.target_encoder = HJEPAContextEncoder(self.config)

        # Target output projection (to match predictor output)
        self.target_proj = nn.Linear(self.config.context_dim, self.config.e8_dim)

        # Initialize target as copy of context encoder
        self._init_target_encoder()

        # EMA step counter
        self.register_buffer("_ema_step", torch.tensor(0, dtype=torch.long))

        # Mask curriculum step counter (Jan 4, 2026)
        self.register_buffer("_mask_step", torch.tensor(0, dtype=torch.long))

        logger.info(
            f"HJEPAModule initialized (UPDATED Jan 4, 2026):\n"
            f"  Horizons: {self.config.horizons}\n"
            f"  Mask ratio: {self.config.mask_ratio_min} → {self.config.mask_ratio} "
            f"(warmup: {self.config.mask_ratio_warmup_steps} steps)\n"
            f"  EMA decay: {self.config.ema_decay}\n"
            f"  Loss type: {self.config.loss_type}\n"
            f"  Action conditioning: {'enabled' if self.config.action_dim > 0 else 'disabled'}"
        )

    def _init_target_encoder(self) -> None:
        """Initialize target encoder as copy of context encoder."""
        for p_target, p_online in zip(
            self.target_encoder.parameters(),
            self.context_encoder.parameters(),
            strict=True,
        ):
            p_target.data.copy_(p_online.data)
            p_target.requires_grad = False

    @torch.no_grad()
    def update_target_encoder(self) -> None:
        """Update target encoder with EMA.

        Uses warmup schedule: decay starts at 0.5 and increases to ema_decay.
        """
        step = self._ema_step.item()  # type: ignore[operator]
        self._ema_step.add_(1)  # type: ignore[operator]

        # Warmup schedule
        if step < self.config.ema_warmup_steps:
            decay = 0.5 + 0.5 * (self.config.ema_decay - 0.5) * (
                step / self.config.ema_warmup_steps
            )
        else:
            decay = self.config.ema_decay

        # EMA update
        for p_target, p_online in zip(
            self.target_encoder.parameters(),
            self.context_encoder.parameters(),
            strict=True,
        ):
            p_target.data.mul_(decay).add_(p_online.data, alpha=1.0 - decay)

    def get_current_mask_ratio(self) -> float:
        """Get current mask ratio based on curriculum warmup.

        Returns:
            Current mask ratio (interpolated between min and target)
        """
        step = self._mask_step.item()  # type: ignore[operator]
        warmup_steps = self.config.mask_ratio_warmup_steps

        if step >= warmup_steps:
            return self.config.mask_ratio

        # Linear interpolation from min to target
        progress = step / warmup_steps
        return self.config.mask_ratio_min + progress * (
            self.config.mask_ratio - self.config.mask_ratio_min
        )

    def generate_mask(
        self,
        batch_size: int,
        seq_len: int,
        device: torch.device,
        training: bool = True,
    ) -> torch.Tensor:
        """Generate random mask for sequence with curriculum warmup.

        During training, mask ratio increases from mask_ratio_min to mask_ratio
        over mask_ratio_warmup_steps. Higher masking forces more semantic understanding.

        Args:
            batch_size: Number of samples
            seq_len: Sequence length
            device: Target device
            training: If True, use curriculum warmup; otherwise use target ratio

        Returns:
            [B, T] boolean mask (True = visible, False = masked)
        """
        # Get mask ratio (curriculum warmup during training)
        if training:
            mask_ratio = self.get_current_mask_ratio()
            # Increment mask step
            self._mask_step.add_(1)  # type: ignore[operator]
        else:
            mask_ratio = self.config.mask_ratio

        # Number of positions to mask
        num_mask = max(
            self.config.min_mask_patches,
            int(seq_len * mask_ratio),
        )
        num_visible = seq_len - num_mask

        # Generate random mask per sample
        masks = []
        for _ in range(batch_size):
            # Random permutation for this sample
            perm = torch.randperm(seq_len, device=device)
            mask = torch.zeros(seq_len, dtype=torch.bool, device=device)
            mask[perm[:num_visible]] = True  # First num_visible positions are visible
            masks.append(mask)

        return torch.stack(masks)  # [B, T]

    def forward(
        self,
        e8_sequence: torch.Tensor,
        mask: torch.Tensor | None = None,
        actions: torch.Tensor | None = None,
    ) -> dict[str, Any]:
        """Forward pass with masking and multi-horizon prediction.

        Args:
            e8_sequence: [B, T, 8] E8 latent sequence
            mask: Optional [B, T] mask (True = visible). If None, generates random mask.
            actions: Optional [B, T, action_dim] action sequence for conditioned prediction.
                     If provided and config.action_dim > 0, predictions are action-conditioned.

        Returns:
            Dict with:
                - predictions: Dict[horizon, [B, T_masked, 8]]
                - targets: Dict[horizon, [B, T_masked, 8]]
                - loss: Total H-JEPA loss
                - losses_per_horizon: Dict[horizon, loss]
                - mask: [B, T] mask used
        """
        B, T, _D = e8_sequence.shape
        device = e8_sequence.device

        # Generate mask if not provided
        if mask is None:
            mask = self.generate_mask(B, T, device)

        # Encode visible positions
        context = self.context_encoder(e8_sequence, mask)  # [B, T, context_dim]

        # Get target representations (from EMA encoder, no gradient)
        with torch.no_grad():
            target_context = self.target_encoder(e8_sequence, None)  # Full sequence
            target_e8 = self.target_proj(target_context)  # [B, T, e8_dim]

            if self.config.normalize_targets:
                target_e8 = F.normalize(target_e8, dim=-1)

        # Predict at each horizon
        predictions: dict[int, torch.Tensor] = {}
        targets: dict[int, torch.Tensor] = {}
        losses: dict[int, torch.Tensor] = {}

        # Get masked positions (where we predict)
        masked_positions = ~mask  # [B, T]

        for horizon_idx, horizon in enumerate(self.config.horizons):
            # Shift targets by horizon (future prediction!)
            # Target for position t is the target at position t + horizon
            if horizon < T:
                # Shift targets
                shifted_target = torch.zeros_like(target_e8)
                shifted_target[:, :-horizon] = target_e8[:, horizon:]
                # Positions beyond T-horizon have no valid target (use last known)
                shifted_target[:, -horizon:] = target_e8[:, -1:].expand(-1, horizon, -1)
            else:
                # Horizon exceeds sequence length - use last position
                shifted_target = target_e8[:, -1:].expand(-1, T, -1)

            # Get positions to predict (masked positions)
            # Create position indices for masked positions
            # This is a simplification - proper implementation would batch variable-length masks
            target_positions = torch.arange(T, device=device).unsqueeze(0).expand(B, -1)  # [B, T]

            # Predict (only care about masked positions for loss)
            # Pass actions if available for action-conditioned prediction
            pred = self.predictor(
                context, target_positions, horizon_idx, actions=actions
            )  # [B, T, e8_dim]

            if self.config.normalize_targets:
                pred = F.normalize(pred, dim=-1)

            # Compute loss only on masked positions
            if self.config.loss_type == "mse":
                loss_per_pos = (pred - shifted_target).pow(2).mean(dim=-1)  # [B, T]
            elif self.config.loss_type == "smooth_l1":
                loss_per_pos = F.smooth_l1_loss(pred, shifted_target, reduction="none").mean(dim=-1)
            elif self.config.loss_type == "cosine":
                loss_per_pos = 1.0 - F.cosine_similarity(pred, shifted_target, dim=-1)  # [B, T]
            else:
                raise ValueError(f"Unknown loss type: {self.config.loss_type}")

            # Average over masked positions only
            masked_loss = (
                loss_per_pos * masked_positions.float()
            ).sum() / masked_positions.float().sum().clamp(min=1.0)

            predictions[horizon] = pred
            targets[horizon] = shifted_target
            losses[horizon] = masked_loss

        # Total loss (average over horizons)
        total_loss = sum(losses.values()) / len(losses)

        return {
            "predictions": predictions,
            "targets": targets,
            "loss": total_loss,
            "losses_per_horizon": losses,
            "mask": mask,
            "context": context,
        }

    def predict_future(
        self,
        e8_context: torch.Tensor,
        horizon: int = 1,
        actions: torch.Tensor | None = None,
    ) -> torch.Tensor:
        """Predict future E8 states given context (inference mode).

        Args:
            e8_context: [B, T, 8] E8 context sequence (all visible)
            horizon: Steps ahead to predict
            actions: Optional [B, T, action_dim] actions for conditioned prediction

        Returns:
            [B, T, 8] predicted future E8 states
        """
        B, T, _ = e8_context.shape
        device = e8_context.device

        # Full visibility mask
        mask = torch.ones(B, T, dtype=torch.bool, device=device)

        # Encode context
        context = self.context_encoder(e8_context, mask)

        # Find horizon index
        if horizon in self.config.horizons:
            horizon_idx = self.config.horizons.index(horizon)
        else:
            # Use closest available horizon
            horizon_idx = min(
                range(len(self.config.horizons)),
                key=lambda i: abs(self.config.horizons[i] - horizon),
            )

        # Predict
        target_positions = torch.arange(T, device=device).unsqueeze(0).expand(B, -1)
        predictions = self.predictor(context, target_positions, horizon_idx, actions=actions)

        return predictions

    def imagine_trajectory(
        self,
        initial_state: torch.Tensor,
        actions: torch.Tensor,
        horizon: int = 1,
    ) -> torch.Tensor:
        """Imagine a trajectory given initial state and action sequence.

        This is the key interface for model-based planning (TD-MPC2 style).

        Args:
            initial_state: [B, 8] initial E8 state
            actions: [B, H, action_dim] action sequence to imagine
            horizon: Prediction horizon to use

        Returns:
            [B, H, 8] imagined trajectory of E8 states
        """
        B = initial_state.shape[0]
        H = actions.shape[1]
        device = initial_state.device

        # Start with initial state as context (expanded to sequence)
        current_context = initial_state.unsqueeze(1)  # [B, 1, 8]

        # Autoregressively predict
        trajectory = [initial_state.unsqueeze(1)]  # Start with initial

        for t in range(H):
            # Get action for this step
            action_t = actions[:, t : t + 1, :]  # [B, 1, action_dim]

            # Predict next state
            context_encoded = self.context_encoder(
                current_context,
                torch.ones(B, current_context.shape[1], dtype=torch.bool, device=device),
            )

            # Find horizon index
            horizon_idx = (
                self.config.horizons.index(horizon) if horizon in self.config.horizons else 0
            )

            # Single position prediction
            target_positions = torch.zeros(B, 1, dtype=torch.long, device=device)
            next_state = self.predictor(
                context_encoded, target_positions, horizon_idx, actions=action_t
            )

            trajectory.append(next_state)

            # Update context (append new state)
            current_context = torch.cat([current_context, next_state], dim=1)

            # Keep context bounded (sliding window)
            if current_context.shape[1] > 16:
                current_context = current_context[:, -16:]

        return torch.cat(trajectory, dim=1)  # [B, H+1, 8]


def create_h_jepa_module(
    e8_dim: int = 8,
    hidden_dim: int = 128,
    mask_ratio: float = 0.75,
    ema_decay: float = 0.996,
    action_dim: int = 0,
    action_fusion: str = "add",
) -> HJEPAModule:
    """Factory function to create H-JEPA module.

    Args:
        e8_dim: E8 latent dimension (default: 8)
        hidden_dim: Hidden dimension (default: 128)
        mask_ratio: Fraction of positions to mask (default: 0.75)
        ema_decay: Target network EMA decay (default: 0.996)
        action_dim: Action dimension for conditioning (default: 0 = no actions)
        action_fusion: How to fuse actions ("add", "concat", "film")

    Returns:
        Configured HJEPAModule
    """
    config = HJEPAConfig(
        e8_dim=e8_dim,
        hidden_dim=hidden_dim,
        mask_ratio=mask_ratio,
        ema_decay=ema_decay,
        action_dim=action_dim,
        action_fusion=action_fusion,
    )
    return HJEPAModule(config)


__all__ = [
    "HJEPAConfig",
    "HJEPAContextEncoder",
    "HJEPAModule",
    "HJEPAPredictor",
    "create_h_jepa_module",
]
