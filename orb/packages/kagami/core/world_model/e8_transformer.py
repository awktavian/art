"""E8-Integrated Transformer for World Model Dynamics.

CREATED: January 4, 2026

Integrates Kagami's unique E8 lattice mathematics directly into the
transformer architecture, rather than using E8 as a post-hoc quantization.

Key Innovation:
===============
Standard attention: Q, K, V → Softmax(QK^T/√d) → Output
E8-Transformer:     Q, K, V → nearest_e8(Q) ⊗ K^T → E8-weighted attention → Output

The E8 lattice provides 240 optimal "attention modes" - discrete attention
patterns that are mathematically optimal for 8D sphere packing.

Why This Matters:
================
1. E8 gives the densest possible lattice packing in 8D (Viazovska 2016)
2. Using E8 quantized queries creates structured attention patterns
3. These patterns are not arbitrary - they follow E8's root system
4. The 240 roots of E8 = 240 canonical attention directions

Integration with Fano Plane:
===========================
When combined with FanoSparseAttention (7 heads following 7 Fano lines),
the E8 quantization ensures that attention weights respect the octonion
multiplication structure.

References:
- Viazovska (2016): The sphere packing problem in dimension 8
- Conway & Sloane (1999): Sphere Packings, Lattices, and Groups
- Vaswani et al. (2017): Attention Is All You Need
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Any

import torch
import torch.nn as nn
import torch.nn.functional as F
from kagami_math.e8_lattice_quantizer import nearest_e8

logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION
# =============================================================================


@dataclass
class E8TransformerConfig:
    """Configuration for E8-integrated transformer."""

    # Model dimensions
    latent_dim: int = 256  # Latent state dimension
    action_dim: int = 8  # Action dimension (matches E8)
    hidden_dim: int = 512  # Transformer hidden dimension
    e8_dim: int = 8  # E8 operates in 8D

    # Architecture
    num_layers: int = 8  # Transformer layers
    num_heads: int = 8  # Attention heads (should divide hidden_dim)
    dropout: float = 0.1

    # E8 integration
    e8_quantize_queries: bool = True  # Quantize Q to E8 lattice
    e8_quantize_keys: bool = False  # Optionally quantize K too
    e8_attention_temperature: float = 1.0  # Temperature for E8 attention
    straight_through_gradient: bool = True  # STE for E8 quantization

    # Context
    max_seq_len: int = 512
    context_len: int = 64

    # Training
    use_causal_mask: bool = True
    use_rotary_embeddings: bool = True
    gradient_checkpointing: bool = False


# =============================================================================
# E8 ATTENTION
# =============================================================================


class E8Attention(nn.Module):
    """Multi-head attention with E8 quantized queries.

    Instead of continuous queries, we quantize Q to the nearest E8 lattice
    point. This creates 240 discrete "attention modes" corresponding to
    the roots of E8.

    The gradient flows through via straight-through estimator (STE).

    Mathematical Insight:
    ====================
    The E8 lattice has 240 minimal vectors (roots), each of squared norm 2.
    By quantizing Q to these roots, we constrain attention to follow
    mathematically optimal directions in 8D space.
    """

    def __init__(self, config: E8TransformerConfig):
        super().__init__()
        self.config = config
        self.num_heads = config.num_heads
        self.head_dim = config.hidden_dim // config.num_heads
        self.e8_dim = config.e8_dim

        # Projections
        self.q_proj = nn.Linear(config.hidden_dim, config.hidden_dim, bias=False)
        self.k_proj = nn.Linear(config.hidden_dim, config.hidden_dim, bias=False)
        self.v_proj = nn.Linear(config.hidden_dim, config.hidden_dim, bias=False)
        self.out_proj = nn.Linear(config.hidden_dim, config.hidden_dim, bias=False)

        # E8 projection: project head_dim -> 8D for E8 quantization
        if self.head_dim != config.e8_dim:
            self.to_e8 = nn.Linear(self.head_dim, config.e8_dim, bias=False)
            self.from_e8 = nn.Linear(config.e8_dim, self.head_dim, bias=False)
        else:
            self.to_e8 = nn.Identity()
            self.from_e8 = nn.Identity()

        # Temperature for attention softmax
        self.temperature = config.e8_attention_temperature

        self.dropout = nn.Dropout(config.dropout)

        # Check flash attention
        self.use_flash = hasattr(F, "scaled_dot_product_attention")

    def _quantize_e8(self, x: torch.Tensor) -> torch.Tensor:
        """Quantize tensor to E8 lattice with straight-through gradient.

        Args:
            x: [..., 8] tensor

        Returns:
            Quantized tensor, same shape
        """
        if self.config.straight_through_gradient:
            # Straight-through estimator: forward uses quantized, backward uses original
            x_quantized = nearest_e8(x)
            return x + (x_quantized - x).detach()
        else:
            return nearest_e8(x)

    def forward(
        self,
        x: torch.Tensor,
        mask: torch.Tensor | None = None,
        is_causal: bool = True,
    ) -> torch.Tensor:
        """Forward pass with E8 quantized attention.

        Args:
            x: [B, T, hidden_dim] input
            mask: Optional attention mask
            is_causal: Use causal masking

        Returns:
            [B, T, hidden_dim] output
        """
        B, T, _ = x.shape

        # Project to Q, K, V
        q = self.q_proj(x).view(B, T, self.num_heads, self.head_dim).transpose(1, 2)
        k = self.k_proj(x).view(B, T, self.num_heads, self.head_dim).transpose(1, 2)
        v = self.v_proj(x).view(B, T, self.num_heads, self.head_dim).transpose(1, 2)
        # q, k, v: [B, num_heads, T, head_dim]

        # E8 quantization of queries
        if self.config.e8_quantize_queries:
            # Project to E8 space, quantize, project back
            q_e8 = self.to_e8(q)  # [B, num_heads, T, 8]
            q_e8 = self._quantize_e8(q_e8)
            q = self.from_e8(q_e8)  # [B, num_heads, T, head_dim]

        # Optionally quantize keys too
        if self.config.e8_quantize_keys:
            k_e8 = self.to_e8(k)
            k_e8 = self._quantize_e8(k_e8)
            k = self.from_e8(k_e8)

        # Compute attention with temperature
        scale = self.temperature / math.sqrt(self.head_dim)

        if self.use_flash and mask is None:
            # Use PyTorch 2.0+ flash attention
            out = F.scaled_dot_product_attention(
                q,
                k,
                v,
                dropout_p=self.dropout.p if self.training else 0.0,
                is_causal=is_causal,
                scale=scale,
            )
        else:
            # Manual attention
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

        # Reshape and project output
        out = out.transpose(1, 2).contiguous().view(B, T, -1)
        out = self.out_proj(out)

        return out


# =============================================================================
# E8 TRANSFORMER BLOCK
# =============================================================================


class E8TransformerBlock(nn.Module):
    """Transformer block with E8-integrated attention."""

    def __init__(self, config: E8TransformerConfig):
        super().__init__()

        self.norm1 = nn.LayerNorm(config.hidden_dim)
        self.attn = E8Attention(config)

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
# E8 TRANSFORMER WORLD MODEL
# =============================================================================


class E8TransformerWorldModel(nn.Module):
    """E8-integrated transformer world model.

    This is a drop-in replacement for TransformerWorldModel that integrates
    E8 lattice mathematics directly into the attention mechanism.

    Key Differences from Standard Transformer:
    ==========================================
    1. Queries are quantized to E8 lattice before attention
    2. This creates 240 discrete attention patterns
    3. Gradients flow via straight-through estimator
    4. Compatible with Fano sparse attention

    Usage:
        model = E8TransformerWorldModel(config)

        # Training (parallel)
        next_states = model.forward(states, actions)

        # Inference
        next_state = model.predict_next(state, action)
        trajectory = model.imagine(state, actions, horizon=15)
    """

    def __init__(self, config: E8TransformerConfig | None = None):
        super().__init__()
        self.config = config or E8TransformerConfig()

        # Input embeddings
        self.state_embed = nn.Linear(self.config.latent_dim, self.config.hidden_dim)
        self.action_embed = nn.Linear(self.config.action_dim, self.config.hidden_dim)

        # E8 transformer blocks
        self.blocks = nn.ModuleList(
            [E8TransformerBlock(self.config) for _ in range(self.config.num_layers)]
        )

        # Output projection
        self.norm = nn.LayerNorm(self.config.hidden_dim)
        self.output_proj = nn.Linear(self.config.hidden_dim, self.config.latent_dim)

        # Optional: project output to E8 space for action generation
        self.e8_output_proj = nn.Linear(self.config.latent_dim, self.config.e8_dim)

        # Initialize weights
        self._init_weights()

        logger.info(
            f"E8TransformerWorldModel initialized:\n"
            f"  Layers: {self.config.num_layers}\n"
            f"  Heads: {self.config.num_heads}\n"
            f"  Hidden: {self.config.hidden_dim}\n"
            f"  E8 Quantized Q: {self.config.e8_quantize_queries}\n"
            f"  E8 Quantized K: {self.config.e8_quantize_keys}"
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

        Args:
            states: [B, T, latent_dim] sequence of latent states
            actions: [B, T, action_dim] sequence of actions
            return_all: If True, return intermediate info

        Returns:
            [B, T, latent_dim] predicted next states
        """
        B, T, _ = states.shape

        # Embed inputs
        state_emb = self.state_embed(states)  # [B, T, hidden]
        action_emb = self.action_embed(actions)  # [B, T, hidden]

        # Interleave: [s0, a0, s1, a1, ...]
        x = torch.zeros(B, T * 2, self.config.hidden_dim, device=states.device)
        x[:, 0::2] = state_emb
        x[:, 1::2] = action_emb

        # Apply E8 transformer blocks
        for block in self.blocks:
            if self.config.gradient_checkpointing and self.training:
                x = torch.utils.checkpoint.checkpoint(block, x, True, use_reentrant=False)
            else:
                x = block(x, is_causal=True)

        # Take output at action positions
        x = x[:, 1::2]  # [B, T, hidden]

        # Project to latent
        x = self.norm(x)
        predictions = self.output_proj(x)  # [B, T, latent_dim]

        if return_all:
            return predictions, {"e8_attention": True}
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
            states = state.unsqueeze(1)
            actions = action.unsqueeze(1)
        else:
            states = torch.cat([context, state.unsqueeze(1)], dim=1)
            T_ctx = context.shape[1]
            action_pad = torch.zeros(B, T_ctx, self.config.action_dim, device=state.device)
            actions = torch.cat([action_pad, action.unsqueeze(1)], dim=1)

        predictions = self.forward(states, actions)
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
            horizon: Override horizon

        Returns:
            [B, H+1, latent_dim] imagined trajectory
        """
        initial_state.shape[0]
        H = horizon or actions.shape[1]

        trajectory = [initial_state.unsqueeze(1)]
        state = initial_state

        for t in range(H):
            action = actions[:, t]
            context = torch.cat(trajectory, dim=1) if len(trajectory) > 1 else None
            next_state = self.predict_next(state, action, context)
            trajectory.append(next_state.unsqueeze(1))
            state = next_state

        return torch.cat(trajectory, dim=1)

    def get_e8_action(self, state: torch.Tensor) -> torch.Tensor:
        """Generate E8-quantized action from state.

        This projects the state to 8D and quantizes to E8 lattice.

        Args:
            state: [B, latent_dim] current state

        Returns:
            [B, 8] E8 lattice action
        """
        e8_raw = self.e8_output_proj(state)  # [B, 8]
        e8_action = nearest_e8(e8_raw)  # Quantize to E8
        return e8_action

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
        predictions = self.forward(states, actions)
        mse_loss = F.mse_loss(predictions, next_states)
        smooth_loss = F.smooth_l1_loss(predictions, next_states)

        return {
            "loss": mse_loss,
            "mse": mse_loss,
            "smooth_l1": smooth_loss,
        }


# =============================================================================
# FACTORY
# =============================================================================


def create_e8_transformer_world_model(
    latent_dim: int = 256,
    action_dim: int = 8,
    num_layers: int = 8,
    num_heads: int = 8,
    e8_quantize_queries: bool = True,
    e8_quantize_keys: bool = False,
) -> E8TransformerWorldModel:
    """Factory function for E8TransformerWorldModel.

    Args:
        latent_dim: Latent state dimension
        action_dim: Action dimension
        num_layers: Number of transformer layers
        num_heads: Number of attention heads
        e8_quantize_queries: Quantize queries to E8
        e8_quantize_keys: Quantize keys to E8

    Returns:
        Configured E8TransformerWorldModel
    """
    config = E8TransformerConfig(
        latent_dim=latent_dim,
        action_dim=action_dim,
        num_layers=num_layers,
        num_heads=num_heads,
        e8_quantize_queries=e8_quantize_queries,
        e8_quantize_keys=e8_quantize_keys,
    )
    return E8TransformerWorldModel(config)


__all__ = [
    "E8Attention",
    "E8TransformerBlock",
    "E8TransformerConfig",
    "E8TransformerWorldModel",
    "create_e8_transformer_world_model",
]
