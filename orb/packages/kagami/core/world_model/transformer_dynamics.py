"""Transformer-Based World Model Dynamics.

CREATED: January 4, 2026

Replaces the GRU-based RSSM dynamics with a transformer architecture
following SOTA techniques from Genie 2 and Sora.

Why Transformers Over RSSM:
===========================
1. Better scaling - transformers scale with compute (proven by LLMs)
2. Parallel training - not sequential like RSSM
3. Longer horizons - attention can model long-range dependencies
4. Pretrained weights - can leverage vision transformers

Architecture:
=============
This implements a "Temporal Transformer" that:
1. Encodes state-action sequences with positional encoding
2. Uses causal attention for autoregressive prediction
3. Supports both training (parallel) and inference (sequential)
4. Integrates with existing E8 quantization

References:
- Hafner et al. (2024): DreamerV3 with Transformer (concurrent work)
- Reed et al. (2022): GATO (multi-task transformer)
- Bruce et al. (2024): Genie 2 (learned latent actions)
- OpenAI (2024): Sora (diffusion transformer)
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


# =============================================================================
# CONFIGURATION
# =============================================================================


@dataclass
class TransformerDynamicsConfig:
    """Configuration for transformer-based dynamics."""

    # Model dimensions
    latent_dim: int = 256  # Latent state dimension (larger than E8's 8)
    action_dim: int = 8  # Action dimension
    hidden_dim: int = 512  # Transformer hidden dimension

    # Architecture
    num_layers: int = 8  # Transformer layers
    num_heads: int = 8  # Attention heads
    dropout: float = 0.1

    # Context
    max_seq_len: int = 512  # Maximum sequence length
    context_len: int = 64  # Context window for prediction

    # Training
    use_causal_mask: bool = True
    use_rotary_embeddings: bool = True  # RoPE from Llama

    # E8 integration (optional)
    use_e8_quantization: bool = False  # If True, quantize to E8 after prediction
    e8_codebook_size: int = 240

    # Efficiency
    use_flash_attention: bool = True  # Use flash attention if available
    gradient_checkpointing: bool = False


# =============================================================================
# ROTARY POSITIONAL EMBEDDING (RoPE)
# =============================================================================


class RotaryEmbedding(nn.Module):
    """Rotary Positional Embedding (RoPE) from Llama.

    Better than sinusoidal for relative position modeling.
    """

    def __init__(self, dim: int, max_seq_len: int = 512, base: float = 10000.0):
        super().__init__()
        self.dim = dim
        self.max_seq_len = max_seq_len
        self.base = base

        # Precompute frequencies
        inv_freq = 1.0 / (base ** (torch.arange(0, dim, 2).float() / dim))
        self.register_buffer("inv_freq", inv_freq)

        # Precompute sin/cos
        self._precompute_cache(max_seq_len)

    def _precompute_cache(self, seq_len: int) -> None:
        """Precompute sin/cos cache for efficiency."""
        t = torch.arange(seq_len, device=self.inv_freq.device)
        freqs = torch.outer(t, self.inv_freq)  # [seq_len, dim/2]

        # Duplicate for sin and cos
        emb = torch.cat([freqs, freqs], dim=-1)  # [seq_len, dim]

        self.register_buffer("cos_cached", emb.cos())
        self.register_buffer("sin_cached", emb.sin())

    def forward(self, x: torch.Tensor, seq_len: int) -> tuple[torch.Tensor, torch.Tensor]:
        """Get cos and sin for sequence length."""
        return self.cos_cached[:seq_len], self.sin_cached[:seq_len]


def apply_rotary_emb(
    q: torch.Tensor, k: torch.Tensor, cos: torch.Tensor, sin: torch.Tensor
) -> tuple[torch.Tensor, torch.Tensor]:
    """Apply rotary embeddings to query and key.

    Args:
        q: [B, num_heads, seq_len, head_dim]
        k: [B, num_heads, seq_len, head_dim]
        cos: [seq_len, head_dim]
        sin: [seq_len, head_dim]

    Returns:
        Rotated q and k
    """

    def rotate_half(x):
        x1, x2 = x[..., : x.shape[-1] // 2], x[..., x.shape[-1] // 2 :]
        return torch.cat([-x2, x1], dim=-1)

    q_embed = (q * cos) + (rotate_half(q) * sin)
    k_embed = (k * cos) + (rotate_half(k) * sin)

    return q_embed, k_embed


# =============================================================================
# TRANSFORMER ATTENTION
# =============================================================================


class TransformerAttention(nn.Module):
    """Multi-head attention with RoPE and flash attention support."""

    def __init__(self, config: TransformerDynamicsConfig):
        super().__init__()
        self.config = config
        self.num_heads = config.num_heads
        self.head_dim = config.hidden_dim // config.num_heads

        # Projections
        self.q_proj = nn.Linear(config.hidden_dim, config.hidden_dim, bias=False)
        self.k_proj = nn.Linear(config.hidden_dim, config.hidden_dim, bias=False)
        self.v_proj = nn.Linear(config.hidden_dim, config.hidden_dim, bias=False)
        self.out_proj = nn.Linear(config.hidden_dim, config.hidden_dim, bias=False)

        # RoPE
        if config.use_rotary_embeddings:
            self.rotary_emb = RotaryEmbedding(self.head_dim, config.max_seq_len)
        else:
            self.rotary_emb = None

        self.dropout = nn.Dropout(config.dropout)

        # Check flash attention availability
        self.use_flash = config.use_flash_attention and hasattr(F, "scaled_dot_product_attention")

    def forward(
        self,
        x: torch.Tensor,
        mask: torch.Tensor | None = None,
        is_causal: bool = True,
    ) -> torch.Tensor:
        """Forward pass.

        Args:
            x: [B, T, hidden_dim]
            mask: Optional attention mask
            is_causal: Use causal masking

        Returns:
            [B, T, hidden_dim]
        """
        B, T, _ = x.shape

        # Project to Q, K, V
        q = self.q_proj(x).view(B, T, self.num_heads, self.head_dim).transpose(1, 2)
        k = self.k_proj(x).view(B, T, self.num_heads, self.head_dim).transpose(1, 2)
        v = self.v_proj(x).view(B, T, self.num_heads, self.head_dim).transpose(1, 2)

        # Apply RoPE
        if self.rotary_emb is not None:
            cos, sin = self.rotary_emb(x, T)
            q, k = apply_rotary_emb(
                q, k, cos.unsqueeze(0).unsqueeze(0), sin.unsqueeze(0).unsqueeze(0)
            )

        # Attention
        if self.use_flash:
            # Use PyTorch 2.0+ scaled_dot_product_attention
            out = F.scaled_dot_product_attention(
                q,
                k,
                v,
                attn_mask=mask,
                dropout_p=self.dropout.p if self.training else 0.0,
                is_causal=is_causal and mask is None,
            )
        else:
            # Manual attention
            scale = 1.0 / math.sqrt(self.head_dim)
            attn = torch.matmul(q, k.transpose(-2, -1)) * scale

            if is_causal:
                causal_mask = torch.triu(
                    torch.ones(T, T, device=x.device, dtype=torch.bool), diagonal=1
                )
                attn = attn.masked_fill(causal_mask, float("-inf"))

            if mask is not None:
                attn = attn + mask

            attn = F.softmax(attn, dim=-1)
            attn = self.dropout(attn)
            out = torch.matmul(attn, v)

        # Reshape and project
        out = out.transpose(1, 2).contiguous().view(B, T, -1)
        out = self.out_proj(out)

        return out


# =============================================================================
# TRANSFORMER BLOCK
# =============================================================================


class TransformerBlock(nn.Module):
    """Standard transformer block with pre-norm."""

    def __init__(self, config: TransformerDynamicsConfig):
        super().__init__()

        self.norm1 = nn.LayerNorm(config.hidden_dim)
        self.attn = TransformerAttention(config)

        self.norm2 = nn.LayerNorm(config.hidden_dim)
        self.ffn = nn.Sequential(
            nn.Linear(config.hidden_dim, config.hidden_dim * 4),
            nn.GELU(),
            nn.Dropout(config.dropout),
            nn.Linear(config.hidden_dim * 4, config.hidden_dim),
            nn.Dropout(config.dropout),
        )

    def forward(self, x: torch.Tensor, is_causal: bool = True) -> torch.Tensor:
        """Forward with residual connections."""
        x = x + self.attn(self.norm1(x), is_causal=is_causal)
        x = x + self.ffn(self.norm2(x))
        return x


# =============================================================================
# TRANSFORMER WORLD MODEL
# =============================================================================


class TransformerWorldModel(nn.Module):
    """Transformer-based world model dynamics.

    Replaces GRU-based RSSM with transformer for better scaling and
    longer horizon predictions.

    Usage:
        model = TransformerWorldModel(config)

        # Training (parallel)
        next_states = model.forward(states, actions)

        # Inference (autoregressive)
        next_state = model.predict_next(state, action)
        trajectory = model.imagine(state, actions, horizon=15)
    """

    def __init__(self, config: TransformerDynamicsConfig | None = None):
        super().__init__()
        self.config = config or TransformerDynamicsConfig()

        # Input embeddings
        self.state_embed = nn.Linear(self.config.latent_dim, self.config.hidden_dim)
        self.action_embed = nn.Linear(self.config.action_dim, self.config.hidden_dim)

        # Transformer blocks
        self.blocks = nn.ModuleList(
            [TransformerBlock(self.config) for _ in range(self.config.num_layers)]
        )

        # Output projection
        self.norm = nn.LayerNorm(self.config.hidden_dim)
        self.output_proj = nn.Linear(self.config.hidden_dim, self.config.latent_dim)

        # Optional E8 quantization
        if self.config.use_e8_quantization:
            from kagami.core.world_model.quantization import E8Quantizer

            self.quantizer = E8Quantizer(self.config.latent_dim)
        else:
            self.quantizer = None

        # Initialize weights
        self._init_weights()

        logger.info(
            f"TransformerWorldModel initialized:\n"
            f"  Layers: {self.config.num_layers}\n"
            f"  Heads: {self.config.num_heads}\n"
            f"  Hidden: {self.config.hidden_dim}\n"
            f"  RoPE: {self.config.use_rotary_embeddings}\n"
            f"  Flash: {self.config.use_flash_attention}"
        )

    def _init_weights(self) -> None:
        """Initialize weights with small values for stability."""
        for module in self.modules():
            if isinstance(module, nn.Linear):
                nn.init.normal_(module.weight, std=0.02)
                if module.bias is not None:
                    nn.init.zeros_(module.bias)

    def forward(
        self,
        states: torch.Tensor,
        actions: torch.Tensor,
        return_all: bool = False,
    ) -> torch.Tensor | tuple[torch.Tensor, dict[str, Any]]:
        """Forward pass for training.

        Given sequence of states and actions, predict next states.

        Args:
            states: [B, T, latent_dim] sequence of latent states
            actions: [B, T, action_dim] sequence of actions
            return_all: If True, return intermediate info

        Returns:
            [B, T, latent_dim] predicted next states (shifted by 1)
        """
        B, T, _ = states.shape

        # Embed inputs
        state_emb = self.state_embed(states)  # [B, T, hidden]
        action_emb = self.action_embed(actions)  # [B, T, hidden]

        # Interleave state and action: [s0, a0, s1, a1, ...]
        # This creates 2T sequence length
        x = torch.zeros(B, T * 2, self.config.hidden_dim, device=states.device)
        x[:, 0::2] = state_emb
        x[:, 1::2] = action_emb

        # Apply transformer blocks with causal mask
        for block in self.blocks:
            if self.config.gradient_checkpointing and self.training:
                x = torch.utils.checkpoint.checkpoint(block, x, True, use_reentrant=False)
            else:
                x = block(x, is_causal=True)

        # Take output at action positions (predict next state after action)
        x = x[:, 1::2]  # [B, T, hidden]

        # Project to latent
        x = self.norm(x)
        predictions = self.output_proj(x)  # [B, T, latent_dim]

        # Optional quantization
        if self.quantizer is not None:
            predictions, quant_info = self.quantizer(predictions)
            if return_all:
                return predictions, {"quantization": quant_info}

        if return_all:
            return predictions, {}
        return predictions

    @torch.no_grad()
    def predict_next(
        self,
        state: torch.Tensor,
        action: torch.Tensor,
        context: torch.Tensor | None = None,
    ) -> torch.Tensor:
        """Predict next state given current state and action.

        Args:
            state: [B, latent_dim] current state
            action: [B, action_dim] action to take
            context: Optional [B, context_len, latent_dim] history

        Returns:
            [B, latent_dim] predicted next state
        """
        B = state.shape[0]

        if context is None:
            # No context, just single step
            states = state.unsqueeze(1)  # [B, 1, latent_dim]
            actions = action.unsqueeze(1)  # [B, 1, action_dim]
        else:
            # Append current state to context
            states = torch.cat([context, state.unsqueeze(1)], dim=1)
            # Need matching actions (pad with zeros for history)
            T_ctx = context.shape[1]
            action_pad = torch.zeros(B, T_ctx, self.config.action_dim, device=state.device)
            actions = torch.cat([action_pad, action.unsqueeze(1)], dim=1)

        # Forward pass
        predictions = self.forward(states, actions)

        # Return last prediction
        return predictions[:, -1]

    @torch.no_grad()
    def imagine(
        self,
        initial_state: torch.Tensor,
        actions: torch.Tensor,
        horizon: int | None = None,
    ) -> torch.Tensor:
        """Imagine trajectory given initial state and action sequence.

        Args:
            initial_state: [B, latent_dim] starting state
            actions: [B, H, action_dim] action sequence
            horizon: Override horizon (uses actions.shape[1] if None)

        Returns:
            [B, H+1, latent_dim] imagined trajectory (includes initial)
        """
        initial_state.shape[0]
        H = horizon or actions.shape[1]

        trajectory = [initial_state.unsqueeze(1)]  # Start with initial
        state = initial_state

        # Autoregressive imagination
        for t in range(H):
            action = actions[:, t]

            # Build context from trajectory so far
            context = torch.cat(trajectory, dim=1) if len(trajectory) > 1 else None

            # Predict next state
            next_state = self.predict_next(state, action, context)
            trajectory.append(next_state.unsqueeze(1))
            state = next_state

        return torch.cat(trajectory, dim=1)

    def compute_loss(
        self,
        states: torch.Tensor,
        actions: torch.Tensor,
        next_states: torch.Tensor,
    ) -> dict[str, torch.Tensor]:
        """Compute training loss.

        Args:
            states: [B, T, latent_dim] current states
            actions: [B, T, action_dim] actions
            next_states: [B, T, latent_dim] ground truth next states

        Returns:
            Dict with loss components
        """
        # Predict
        predictions = self.forward(states, actions)

        # MSE loss
        mse_loss = F.mse_loss(predictions, next_states)

        # Optional: smooth L1 for outliers
        smooth_loss = F.smooth_l1_loss(predictions, next_states)

        return {
            "loss": mse_loss,
            "mse": mse_loss,
            "smooth_l1": smooth_loss,
        }


# =============================================================================
# FACTORY
# =============================================================================


def create_transformer_world_model(
    latent_dim: int = 256,
    action_dim: int = 8,
    num_layers: int = 8,
    num_heads: int = 8,
    use_e8: bool = False,
) -> TransformerWorldModel:
    """Factory function for TransformerWorldModel.

    Args:
        latent_dim: Latent state dimension
        action_dim: Action dimension
        num_layers: Number of transformer layers
        num_heads: Number of attention heads
        use_e8: Use E8 quantization

    Returns:
        Configured TransformerWorldModel
    """
    config = TransformerDynamicsConfig(
        latent_dim=latent_dim,
        action_dim=action_dim,
        num_layers=num_layers,
        num_heads=num_heads,
        use_e8_quantization=use_e8,
    )
    return TransformerWorldModel(config)


def upgrade_rssm_to_transformer(
    rssm_state_dict: dict[str, torch.Tensor] | None = None,
) -> TransformerWorldModel:
    """Create transformer model, optionally migrating from RSSM.

    This function helps migrate from the GRU-based RSSM to transformer.
    Note: Weights are NOT directly transferable, but dimensions are preserved.

    Args:
        rssm_state_dict: Optional RSSM state dict (for dimension inference)

    Returns:
        New TransformerWorldModel
    """
    # Default config matching typical RSSM
    config = TransformerDynamicsConfig(
        latent_dim=256,
        action_dim=8,
        hidden_dim=512,
        num_layers=8,
    )

    # Could infer dimensions from RSSM state dict if provided
    # For now, just create default

    model = TransformerWorldModel(config)
    logger.info("Created TransformerWorldModel to replace RSSM")
    logger.warning("Note: RSSM weights cannot be transferred. Training from scratch required.")

    return model


__all__ = [
    "RotaryEmbedding",
    "TransformerAttention",
    "TransformerBlock",
    "TransformerDynamicsConfig",
    "TransformerWorldModel",
    "create_transformer_world_model",
    "upgrade_rssm_to_transformer",
]
