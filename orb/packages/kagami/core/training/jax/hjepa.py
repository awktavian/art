"""JAX H-JEPA: Hierarchical Joint-Embedding Predictive Architecture.

PORTED FROM:
- world_model/h_jepa.py (HJEPAConfig, HJEPAContextEncoder, HJEPAPredictor, HJEPAModule)
- world_model/hierarchical_jepa.py (multi-horizon predictions)

This implements LeCun's world model vision with proper future prediction:
1. Context encoder: Encodes visible (unmasked) states
2. Predictor: Predicts FUTURE states from context (NOT self-consistency)
3. Target network: EMA of predictor for stable targets
4. Multi-horizon: [1, 4, 16] step ahead predictions

Key insight from V-JEPA (Meta 2024):
- Non-generative: Predict in latent space, not pixel space
- Asymmetric: Large context encoder, small predictor
- High mask ratio (90%) forces semantic understanding

References:
- LeCun (2022): A Path Towards Autonomous Machine Intelligence
- Assran et al. (2023): Self-Supervised Learning with JEPA
- Bardes et al. (2024): V-JEPA: Video JEPA

Created: January 12, 2026
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import NamedTuple

import jax
import jax.numpy as jnp
from flax import linen as nn

logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION
# =============================================================================


@dataclass(frozen=True)
class HJEPAConfig:
    """Configuration for H-JEPA module.

    frozen=True for JAX static_argnums compatibility.
    """

    # Dimensions
    e8_dim: int = 8  # E8 latent dimension (colony state)
    hidden_dim: int = 256  # Predictor hidden dimension
    context_dim: int = 128  # Context encoder output dimension
    num_colonies: int = 7  # Number of colonies

    # Architecture
    num_predictor_layers: int = 4  # Predictor transformer depth
    num_context_layers: int = 3  # Context encoder depth
    num_heads: int = 8  # Attention heads
    dropout: float = 0.1

    # Prediction horizons (multi-scale)
    horizons: tuple[int, ...] = (1, 4, 16)  # Steps ahead

    # Masking (V-JEPA 2 style)
    mask_ratio: float = 0.90  # Target mask ratio
    mask_ratio_min: float = 0.50  # Initial mask ratio
    mask_warmup_steps: int = 10000  # Steps to ramp mask ratio

    # EMA target network
    ema_decay: float = 0.996  # Target network EMA decay
    ema_warmup_steps: int = 1000  # Steps before full decay

    # Loss
    loss_type: str = "smooth_l1"  # "mse", "smooth_l1", "cosine"
    normalize_targets: bool = True  # L2 normalize targets

    # Action conditioning (TD-MPC2 style)
    action_dim: int = 8  # Action dimension (0 = no conditioning)


# =============================================================================
# SINUSOIDAL POSITIONAL ENCODING
# =============================================================================


def sinusoidal_pos_encoding(length: int, dim: int) -> jnp.ndarray:
    """Generate sinusoidal positional encoding.

    Args:
        length: Sequence length
        dim: Embedding dimension

    Returns:
        [length, dim] positional encoding
    """
    position = jnp.arange(length)[:, None]
    div_term = jnp.exp(jnp.arange(0, dim, 2) * (-jnp.log(10000.0) / dim))

    pe = jnp.zeros((length, dim))
    pe = pe.at[:, 0::2].set(jnp.sin(position * div_term))
    pe = pe.at[:, 1::2].set(jnp.cos(position * div_term[: dim // 2]))

    return pe


# =============================================================================
# CONTEXT ENCODER
# =============================================================================


class HJEPAContextEncoder(nn.Module):
    """Encode visible (unmasked) colony states to context.

    Architecture:
        E8 [B, T, 7, 8] → Linear → LayerNorm → Transformer → Context [B, T, D]

    Only processes unmasked positions (visible context).
    """

    config: HJEPAConfig

    @nn.compact
    def __call__(
        self,
        e8_sequence: jnp.ndarray,
        mask: jnp.ndarray | None = None,
        training: bool = True,
    ) -> jnp.ndarray:
        """Encode visible states to context.

        Args:
            e8_sequence: [B, T, 7, 8] E8 colony states
            mask: [B, T] visibility mask (1=visible, 0=masked)
            training: Whether in training mode

        Returns:
            [B, T, context_dim] context embeddings
        """
        cfg = self.config
        B, T, num_colonies, e8_dim = e8_sequence.shape

        # Flatten colonies: [B, T, 7, 8] -> [B, T, 56]
        x = e8_sequence.reshape(B, T, num_colonies * e8_dim)

        # Input projection
        x = nn.Dense(cfg.hidden_dim, name="input_proj")(x)
        x = nn.LayerNorm(name="input_ln")(x)
        x = nn.gelu(x)

        # Add positional encoding
        pos_enc = self.variable(
            "pos_enc",
            "pe",
            lambda: sinusoidal_pos_encoding(512, cfg.hidden_dim),
        ).value[:T]
        x = x + pos_enc[None, :, :]

        # Create attention mask from visibility mask
        attn_mask = None
        if mask is not None:
            # [B, T] -> [B, 1, T, T] attention mask
            attn_mask = mask[:, None, None, :] * mask[:, None, :, None]

        # Transformer encoder layers
        for i in range(cfg.num_context_layers):
            residual = x
            x = nn.LayerNorm(name=f"ln1_{i}")(x)
            x = nn.MultiHeadDotProductAttention(
                num_heads=cfg.num_heads,
                qkv_features=cfg.hidden_dim,
                dropout_rate=cfg.dropout,
                deterministic=not training,
                name=f"attn_{i}",
            )(x, x, mask=attn_mask)
            x = x + residual

            residual = x
            x = nn.LayerNorm(name=f"ln2_{i}")(x)
            x = nn.Dense(cfg.hidden_dim * 4, name=f"ffn1_{i}")(x)
            x = nn.gelu(x)
            x = nn.Dense(cfg.hidden_dim, name=f"ffn2_{i}")(x)
            if training:
                x = nn.Dropout(rate=cfg.dropout)(x, deterministic=False)
            x = x + residual

        # Output projection to context dim
        context = nn.Dense(cfg.context_dim, name="output_proj")(x)

        return context  # [B, T, context_dim]


# =============================================================================
# PREDICTOR
# =============================================================================


class HJEPAPredictor(nn.Module):
    """Predict future colony states from context.

    Key difference from self-consistency: predicts FUTURE positions,
    not the same position from the same position.

    Architecture:
        Context [B, T, D] + horizon_embed → Transformer → Prediction [B, T-h, 7, 8]
    """

    config: HJEPAConfig

    @nn.compact
    def __call__(
        self,
        context: jnp.ndarray,
        horizon: int,
        actions: jnp.ndarray | None = None,
        training: bool = True,
    ) -> jnp.ndarray:
        """Predict future states at given horizon.

        Args:
            context: [B, T, context_dim] context embeddings
            horizon: Steps ahead to predict
            actions: [B, T, action_dim] optional action sequence
            training: Whether in training mode

        Returns:
            [B, T-horizon, 7, 8] predicted E8 states
        """
        cfg = self.config
        B, T, D = context.shape

        # Project context to hidden dim
        x = nn.Dense(cfg.hidden_dim, name="context_proj")(context)

        # Add horizon embedding (learned)
        horizon_embed = nn.Embed(
            num_embeddings=max(cfg.horizons) + 1,
            features=cfg.hidden_dim,
            name="horizon_embed",
        )(jnp.array([horizon]))[0]  # [hidden_dim]
        x = x + horizon_embed[None, None, :]

        # Add positional encoding
        pos_enc = self.variable(
            "pos_enc",
            "pe",
            lambda: sinusoidal_pos_encoding(512, cfg.hidden_dim),
        ).value[:T]
        x = x + pos_enc[None, :, :]

        # Optional action conditioning (TD-MPC2 style)
        if actions is not None and cfg.action_dim > 0:
            action_embed = nn.Dense(cfg.hidden_dim, name="action_proj")(actions)
            x = x + action_embed

        # Causal transformer (predict future from past)
        causal_mask = jnp.tril(jnp.ones((T, T)))[None, None, :, :]

        for i in range(cfg.num_predictor_layers):
            residual = x
            x = nn.LayerNorm(name=f"ln1_{i}")(x)
            x = nn.MultiHeadDotProductAttention(
                num_heads=cfg.num_heads,
                qkv_features=cfg.hidden_dim,
                dropout_rate=cfg.dropout,
                deterministic=not training,
                name=f"attn_{i}",
            )(x, x, mask=causal_mask)
            x = x + residual

            residual = x
            x = nn.LayerNorm(name=f"ln2_{i}")(x)
            x = nn.Dense(cfg.hidden_dim * 4, name=f"ffn1_{i}")(x)
            x = nn.gelu(x)
            x = nn.Dense(cfg.hidden_dim, name=f"ffn2_{i}")(x)
            x = x + residual

        # Output projection to E8 colony states
        # [B, T, hidden] -> [B, T, 7*8]
        out = nn.Dense(cfg.num_colonies * cfg.e8_dim, name="output_proj")(x)

        # Reshape to colony structure
        out = out.reshape(B, T, cfg.num_colonies, cfg.e8_dim)

        # Slice to get predictions for positions where we have future targets
        # If predicting h steps ahead, we can only predict for positions 0:T-h
        if horizon > 0 and T > horizon:
            out = out[:, :-horizon]  # [B, T-h, 7, 8]

        return out


# =============================================================================
# H-JEPA MODULE (FULL)
# =============================================================================


class HJEPAOutput(NamedTuple):
    """Output from H-JEPA forward pass."""

    predictions: dict[int, jnp.ndarray]  # {horizon: [B, T-h, 7, 8]}
    targets: dict[int, jnp.ndarray]  # {horizon: [B, T-h, 7, 8]}
    loss: jnp.ndarray  # Scalar total loss
    losses_per_horizon: dict[int, jnp.ndarray]  # {horizon: scalar}


class HJEPAModule(nn.Module):
    """Full H-JEPA module with multi-horizon predictions.

    Combines:
    - Context encoder (encodes visible states)
    - Predictor (predicts future states)
    - Target network (EMA of predictor for stable targets)
    - Multi-horizon loss computation
    """

    config: HJEPAConfig

    def setup(self):
        """Initialize components."""
        cfg = self.config

        self.context_encoder = HJEPAContextEncoder(cfg)
        self.predictor = HJEPAPredictor(cfg)

    def __call__(
        self,
        e8_sequence: jnp.ndarray,
        mask: jnp.ndarray | None = None,
        actions: jnp.ndarray | None = None,
        training: bool = True,
    ) -> HJEPAOutput:
        """Full H-JEPA forward pass with multi-horizon predictions.

        Args:
            e8_sequence: [B, T, 7, 8] E8 colony states
            mask: [B, T] visibility mask (1=visible, 0=masked)
            actions: [B, T, action_dim] optional actions
            training: Whether in training mode

        Returns:
            HJEPAOutput with predictions, targets, and losses
        """
        cfg = self.config
        B, T, num_colonies, e8_dim = e8_sequence.shape

        # Encode context from visible positions
        context = self.context_encoder(e8_sequence, mask, training)

        # Predictions and targets for each horizon
        predictions = {}
        targets = {}
        losses = {}

        for h in cfg.horizons:
            if T <= h:
                continue  # Skip if sequence too short

            # Predict h steps ahead
            pred = self.predictor(context, h, actions, training)  # [B, T-h, 7, 8]
            predictions[h] = pred

            # Target: actual future states (detached)
            target = jax.lax.stop_gradient(e8_sequence[:, h:])  # [B, T-h, 7, 8]

            # Normalize targets if configured
            if cfg.normalize_targets:
                target = target / (jnp.linalg.norm(target, axis=-1, keepdims=True) + 1e-8)
            targets[h] = target

            # Compute loss for this horizon
            if cfg.loss_type == "mse":
                loss_h = jnp.mean((pred - target) ** 2)
            elif cfg.loss_type == "smooth_l1":
                diff = pred - target
                loss_h = jnp.where(
                    jnp.abs(diff) < 1.0,
                    0.5 * diff**2,
                    jnp.abs(diff) - 0.5,
                ).mean()
            elif cfg.loss_type == "cosine":
                # Cosine similarity loss
                pred_norm = pred / (jnp.linalg.norm(pred, axis=-1, keepdims=True) + 1e-8)
                target_norm = target / (jnp.linalg.norm(target, axis=-1, keepdims=True) + 1e-8)
                loss_h = 1.0 - jnp.mean(jnp.sum(pred_norm * target_norm, axis=-1))
            else:
                loss_h = jnp.mean((pred - target) ** 2)  # Default to MSE

            losses[h] = loss_h

        # Total loss (average across horizons)
        if losses:
            total_loss = sum(losses.values()) / len(losses)
        else:
            total_loss = jnp.array(0.0)

        return HJEPAOutput(
            predictions=predictions,
            targets=targets,
            loss=total_loss,
            losses_per_horizon=losses,
        )


# =============================================================================
# MASKING UTILITIES
# =============================================================================


def create_random_mask(
    key: jax.Array,
    batch_size: int,
    seq_len: int,
    mask_ratio: float,
    min_visible: int = 4,
) -> jnp.ndarray:
    """Create random visibility mask for H-JEPA training.

    Args:
        key: JAX random key
        batch_size: Batch size
        seq_len: Sequence length
        mask_ratio: Fraction to mask (0.9 = 90% masked)
        min_visible: Minimum visible positions

    Returns:
        [B, T] mask (1=visible, 0=masked)
    """
    # Number of visible positions
    num_visible = max(min_visible, int(seq_len * (1 - mask_ratio)))

    # Random permutation per batch
    keys = jax.random.split(key, batch_size)

    def sample_mask(k: jax.Array) -> jnp.ndarray:
        perm = jax.random.permutation(k, seq_len)
        mask = jnp.zeros(seq_len)
        mask = mask.at[perm[:num_visible]].set(1.0)
        return mask

    masks = jax.vmap(sample_mask)(keys)  # [B, T]
    return masks


def get_mask_ratio_schedule(
    step: int,
    config: HJEPAConfig,
) -> float:
    """Get current mask ratio with warmup schedule.

    Args:
        step: Current training step
        config: H-JEPA configuration

    Returns:
        Current mask ratio
    """
    if step >= config.mask_warmup_steps:
        return config.mask_ratio

    # Linear interpolation during warmup
    progress = step / config.mask_warmup_steps
    return config.mask_ratio_min + progress * (config.mask_ratio - config.mask_ratio_min)


# =============================================================================
# EMA UPDATE
# =============================================================================


def update_ema(
    online_params: dict,
    target_params: dict,
    decay: float,
    step: int,
    warmup_steps: int = 1000,
) -> dict:
    """Update target network parameters with EMA.

    Args:
        online_params: Current model parameters
        target_params: Target network parameters
        decay: EMA decay rate
        step: Current training step
        warmup_steps: Steps before using full decay

    Returns:
        Updated target parameters
    """
    # Warmup: use lower decay initially
    if step < warmup_steps:
        effective_decay = decay * (step / warmup_steps)
    else:
        effective_decay = decay

    def ema_update(online: jnp.ndarray, target: jnp.ndarray) -> jnp.ndarray:
        return effective_decay * target + (1 - effective_decay) * online

    return jax.tree.map(ema_update, online_params, target_params)


# =============================================================================
# FACTORY FUNCTION
# =============================================================================


def create_hjepa(
    e8_dim: int = 8,
    hidden_dim: int = 256,
    context_dim: int = 128,
    horizons: tuple[int, ...] = (1, 4, 16),
    num_predictor_layers: int = 4,
) -> HJEPAModule:
    """Create H-JEPA module with default configuration.

    Args:
        e8_dim: E8 latent dimension
        hidden_dim: Predictor hidden dimension
        context_dim: Context encoder output dimension
        horizons: Prediction horizons
        num_predictor_layers: Predictor depth

    Returns:
        Configured HJEPAModule
    """
    config = HJEPAConfig(
        e8_dim=e8_dim,
        hidden_dim=hidden_dim,
        context_dim=context_dim,
        horizons=horizons,
        num_predictor_layers=num_predictor_layers,
    )
    return HJEPAModule(config)


# =============================================================================
# EXPORTS
# =============================================================================


__all__ = [
    "HJEPAConfig",
    "HJEPAContextEncoder",
    "HJEPAModule",
    "HJEPAOutput",
    "HJEPAPredictor",
    "create_hjepa",
    "create_random_mask",
    "get_mask_ratio_schedule",
    "sinusoidal_pos_encoding",
    "update_ema",
]
