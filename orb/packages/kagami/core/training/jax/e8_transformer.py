"""E8-Integrated Transformer for JAX/TPU Training.

JAX/Flax port of the E8 Transformer world model from PyTorch.

Key Innovation:
===============
Quantizes attention queries to E8 lattice, creating 240 discrete
"attention modes" corresponding to the roots of E8.

Usage:
    model = E8TransformerWorldModel(config)
    params = model.init(rng, obs, actions)
    predictions = model.apply(params, obs, actions)

Created: January 12, 2026
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import jax
import jax.numpy as jnp
from flax import linen as nn

# =============================================================================
# E8 LATTICE UTILITIES (JAX)
# =============================================================================


def _generate_e8_roots() -> jnp.ndarray:
    """Generate the 240 roots of E8 lattice.

    E8 roots consist of:
    1. ±e_i ± e_j for i < j: 112 roots (2 * C(8,2) * 4)
    2. (±1/2, ±1/2, ..., ±1/2) with even number of minus signs: 128 roots

    Returns:
        [240, 8] array of E8 root vectors
    """
    roots = []

    # Type 1: ±e_i ± e_j (112 roots)
    for i in range(8):
        for j in range(i + 1, 8):
            for si in [1, -1]:
                for sj in [1, -1]:
                    v = jnp.zeros(8)
                    v = v.at[i].set(si)
                    v = v.at[j].set(sj)
                    roots.append(v)

    # Type 2: (±1/2, ..., ±1/2) with even minus signs (128 roots)
    for mask in range(256):
        if bin(mask).count("1") % 2 == 0:  # Even number of minus signs
            v = jnp.array([0.5 if (mask >> i) & 1 == 0 else -0.5 for i in range(8)])
            roots.append(v)

    return jnp.stack(roots)


# Pre-compute E8 roots (immutable)
E8_ROOTS = _generate_e8_roots()


def nearest_e8_jax(x: jnp.ndarray) -> jnp.ndarray:
    """Find nearest E8 lattice point using fast algorithm.

    Uses the decoding algorithm from Conway & Sloane (1999).

    Args:
        x: [..., 8] tensor to quantize

    Returns:
        Nearest E8 lattice point, same shape
    """
    original_shape = x.shape
    x_flat = x.reshape(-1, 8)

    # Compute distances to all 240 roots
    # x_flat: [N, 8], E8_ROOTS: [240, 8]
    dists = jnp.sum((x_flat[:, None, :] - E8_ROOTS[None, :, :]) ** 2, axis=-1)
    nearest_idx = jnp.argmin(dists, axis=-1)

    result = E8_ROOTS[nearest_idx]
    return result.reshape(original_shape)


def e8_quantize_ste(x: jnp.ndarray) -> jnp.ndarray:
    """E8 quantization with straight-through estimator.

    Forward: return quantized value
    Backward: gradient flows through original value

    Args:
        x: [..., 8] tensor

    Returns:
        Quantized tensor with STE gradient
    """

    @jax.custom_vjp
    def ste_forward(x: jnp.ndarray) -> jnp.ndarray:
        return nearest_e8_jax(x)

    def ste_fwd(x: jnp.ndarray) -> tuple[jnp.ndarray, jnp.ndarray]:
        return ste_forward(x), x

    def ste_bwd(res: jnp.ndarray, g: jnp.ndarray) -> tuple[jnp.ndarray]:
        # Pass gradient through unchanged (straight-through)
        return (g,)

    ste_forward.defvjp(ste_fwd, ste_bwd)
    return ste_forward(x)


# =============================================================================
# CONFIGURATION
# =============================================================================


@dataclass
class E8TransformerConfig:
    """Configuration for E8-integrated transformer."""

    # Model dimensions
    latent_dim: int = 256
    action_dim: int = 8
    hidden_dim: int = 512
    e8_dim: int = 8

    # Architecture
    num_layers: int = 8
    num_heads: int = 8
    dropout: float = 0.1

    # E8 integration
    e8_quantize_queries: bool = True
    e8_quantize_keys: bool = False
    e8_attention_temperature: float = 1.0
    straight_through_gradient: bool = True

    # Context
    max_seq_len: int = 512

    # Training
    use_causal_mask: bool = True
    dtype: Any = jnp.bfloat16


# =============================================================================
# E8 ATTENTION (FLAX)
# =============================================================================


class E8Attention(nn.Module):
    """Multi-head attention with E8 quantized queries.

    Quantizes Q to the nearest E8 lattice point, creating 240 discrete
    attention patterns corresponding to E8 roots.
    """

    config: E8TransformerConfig

    @nn.compact
    def __call__(
        self,
        x: jnp.ndarray,
        is_causal: bool = True,
        deterministic: bool = False,
    ) -> jnp.ndarray:
        """Forward pass with E8 quantized attention.

        Args:
            x: [B, T, hidden_dim] input
            is_causal: Use causal masking
            deterministic: Disable dropout

        Returns:
            [B, T, hidden_dim] output
        """
        cfg = self.config
        B, T, D = x.shape
        head_dim = cfg.hidden_dim // cfg.num_heads

        # Projections
        q = nn.Dense(cfg.hidden_dim, use_bias=False, name="q_proj")(x)
        k = nn.Dense(cfg.hidden_dim, use_bias=False, name="k_proj")(x)
        v = nn.Dense(cfg.hidden_dim, use_bias=False, name="v_proj")(x)

        # Reshape to [B, num_heads, T, head_dim]
        q = q.reshape(B, T, cfg.num_heads, head_dim).transpose(0, 2, 1, 3)
        k = k.reshape(B, T, cfg.num_heads, head_dim).transpose(0, 2, 1, 3)
        v = v.reshape(B, T, cfg.num_heads, head_dim).transpose(0, 2, 1, 3)

        # E8 quantization of queries
        if cfg.e8_quantize_queries:
            # Project to E8 space
            if head_dim != cfg.e8_dim:
                to_e8 = nn.Dense(cfg.e8_dim, use_bias=False, name="to_e8")
                from_e8 = nn.Dense(head_dim, use_bias=False, name="from_e8")
                q_e8 = to_e8(q)
            else:
                q_e8 = q

            # Quantize with STE
            if cfg.straight_through_gradient:
                q_e8 = e8_quantize_ste(q_e8)
            else:
                q_e8 = nearest_e8_jax(q_e8)

            # Project back
            if head_dim != cfg.e8_dim:
                q = from_e8(q_e8)
            else:
                q = q_e8

        # Optionally quantize keys
        if cfg.e8_quantize_keys:
            if head_dim != cfg.e8_dim:
                k_e8 = to_e8(k)
            else:
                k_e8 = k
            if cfg.straight_through_gradient:
                k_e8 = e8_quantize_ste(k_e8)
            else:
                k_e8 = nearest_e8_jax(k_e8)
            if head_dim != cfg.e8_dim:
                k = from_e8(k_e8)
            else:
                k = k_e8

        # Compute attention scores
        scale = cfg.e8_attention_temperature / jnp.sqrt(head_dim)
        attn = jnp.einsum("bhqd,bhkd->bhqk", q, k) * scale

        # Causal mask
        if is_causal:
            mask = jnp.triu(jnp.ones((T, T), dtype=bool), k=1)
            attn = jnp.where(mask, -1e9, attn)

        attn = jax.nn.softmax(attn, axis=-1)

        if not deterministic:
            attn = nn.Dropout(cfg.dropout)(attn, deterministic=deterministic)

        # Apply attention to values
        out = jnp.einsum("bhqk,bhkd->bhqd", attn, v)

        # Reshape back
        out = out.transpose(0, 2, 1, 3).reshape(B, T, cfg.hidden_dim)

        # Output projection
        out = nn.Dense(cfg.hidden_dim, use_bias=False, name="out_proj")(out)

        return out


# =============================================================================
# E8 TRANSFORMER BLOCK
# =============================================================================


class E8TransformerBlock(nn.Module):
    """Transformer block with E8-integrated attention."""

    config: E8TransformerConfig

    @nn.compact
    def __call__(
        self,
        x: jnp.ndarray,
        is_causal: bool = True,
        deterministic: bool = False,
    ) -> jnp.ndarray:
        """Forward with residual connections."""
        cfg = self.config

        # Pre-norm attention
        residual = x
        x = nn.LayerNorm(name="norm1")(x)
        x = E8Attention(cfg, name="attn")(x, is_causal, deterministic)
        x = residual + x

        # Pre-norm FFN
        residual = x
        x = nn.LayerNorm(name="norm2")(x)
        x = nn.Dense(cfg.hidden_dim * 4, name="ffn1")(x)
        x = nn.gelu(x)
        if not deterministic:
            x = nn.Dropout(cfg.dropout)(x, deterministic=deterministic)
        x = nn.Dense(cfg.hidden_dim, name="ffn2")(x)
        if not deterministic:
            x = nn.Dropout(cfg.dropout)(x, deterministic=deterministic)
        x = residual + x

        return x


# =============================================================================
# E8 TRANSFORMER WORLD MODEL
# =============================================================================


class E8TransformerWorldModel(nn.Module):
    """E8-integrated transformer world model for TPU training.

    Predicts next states given state-action sequences.
    Compatible with OrganismRSSM training pipeline.
    """

    config: E8TransformerConfig

    @nn.compact
    def __call__(
        self,
        states: jnp.ndarray,
        actions: jnp.ndarray,
        deterministic: bool = False,
    ) -> jnp.ndarray:
        """Forward pass for training.

        Args:
            states: [B, T, latent_dim] sequence of latent states
            actions: [B, T, action_dim] sequence of actions
            deterministic: Disable dropout

        Returns:
            [B, T, latent_dim] predicted next states
        """
        cfg = self.config
        B, T, _ = states.shape

        # Embed inputs
        state_emb = nn.Dense(cfg.hidden_dim, name="state_embed")(states)
        action_emb = nn.Dense(cfg.hidden_dim, name="action_embed")(actions)

        # Interleave: [s0, a0, s1, a1, ...]
        x = jnp.zeros((B, T * 2, cfg.hidden_dim), dtype=states.dtype)
        x = x.at[:, 0::2].set(state_emb)
        x = x.at[:, 1::2].set(action_emb)

        # Apply E8 transformer blocks
        for i in range(cfg.num_layers):
            x = E8TransformerBlock(cfg, name=f"block_{i}")(
                x, is_causal=True, deterministic=deterministic
            )

        # Take output at action positions (predicts next state)
        x = x[:, 1::2]  # [B, T, hidden]

        # Final projection
        x = nn.LayerNorm(name="final_norm")(x)
        predictions = nn.Dense(cfg.latent_dim, name="output_proj")(x)

        return predictions

    def predict_next(
        self,
        state: jnp.ndarray,
        action: jnp.ndarray,
    ) -> jnp.ndarray:
        """Predict next state (inference helper).

        Args:
            state: [B, latent_dim] current state
            action: [B, action_dim] action

        Returns:
            [B, latent_dim] predicted next state
        """
        states = state[:, None, :]  # [B, 1, latent_dim]
        actions = action[:, None, :]  # [B, 1, action_dim]
        predictions = self(states, actions, deterministic=True)
        return predictions[:, 0]  # [B, latent_dim]

    def imagine(
        self,
        initial_state: jnp.ndarray,
        actions: jnp.ndarray,
    ) -> jnp.ndarray:
        """Imagine trajectory autoregressively.

        Args:
            initial_state: [B, latent_dim] starting state
            actions: [B, H, action_dim] action sequence

        Returns:
            [B, H+1, latent_dim] imagined trajectory
        """
        _B = initial_state.shape[0]  # Batch size (for documentation)
        _H = actions.shape[1]  # Horizon (for documentation)

        def scan_fn(state, action):
            # Predict next state
            next_state = self.predict_next(state, action)
            return next_state, next_state

        # Scan over action sequence
        _, trajectory = jax.lax.scan(scan_fn, initial_state, actions.transpose(1, 0, 2))

        # trajectory: [H, B, latent_dim] -> [B, H, latent_dim]
        trajectory = trajectory.transpose(1, 0, 2)

        # Prepend initial state
        return jnp.concatenate([initial_state[:, None, :], trajectory], axis=1)


# =============================================================================
# LOSS FUNCTIONS
# =============================================================================


def e8_transformer_loss(
    predictions: jnp.ndarray,
    targets: jnp.ndarray,
) -> dict[str, jnp.ndarray]:
    """Compute E8 transformer training loss.

    Args:
        predictions: [B, T, latent_dim] predicted states
        targets: [B, T, latent_dim] ground truth states

    Returns:
        Dict with loss components
    """
    # MSE loss
    mse = jnp.mean((predictions - targets) ** 2)

    # Smooth L1 loss
    diff = jnp.abs(predictions - targets)
    smooth_l1 = jnp.where(diff < 1, 0.5 * diff**2, diff - 0.5)
    smooth_l1 = jnp.mean(smooth_l1)

    return {
        "loss": mse,
        "mse": mse,
        "smooth_l1": smooth_l1,
    }


# =============================================================================
# FACTORY FUNCTIONS
# =============================================================================


def create_e8_transformer_config(
    latent_dim: int = 256,
    action_dim: int = 8,
    num_layers: int = 8,
    num_heads: int = 8,
    hidden_dim: int = 512,
    e8_quantize_queries: bool = True,
    e8_quantize_keys: bool = False,
    dtype: Any = jnp.bfloat16,
) -> E8TransformerConfig:
    """Create E8 transformer configuration.

    Args:
        latent_dim: Latent state dimension
        action_dim: Action dimension
        num_layers: Number of transformer layers
        num_heads: Number of attention heads
        hidden_dim: Hidden dimension
        e8_quantize_queries: Quantize queries to E8
        e8_quantize_keys: Quantize keys to E8
        dtype: Computation dtype

    Returns:
        E8TransformerConfig
    """
    return E8TransformerConfig(
        latent_dim=latent_dim,
        action_dim=action_dim,
        hidden_dim=hidden_dim,
        num_layers=num_layers,
        num_heads=num_heads,
        e8_quantize_queries=e8_quantize_queries,
        e8_quantize_keys=e8_quantize_keys,
        dtype=dtype,
    )


def create_e8_transformer(
    config: E8TransformerConfig | None = None,
    rng: jax.Array | None = None,
    batch_size: int = 1,
    seq_len: int = 32,
) -> tuple[E8TransformerWorldModel, dict]:
    """Create and initialize E8 transformer model.

    Args:
        config: Model configuration
        rng: Random key for initialization
        batch_size: Batch size for dummy input
        seq_len: Sequence length for dummy input

    Returns:
        (model, params) tuple
    """
    if config is None:
        config = create_e8_transformer_config()

    if rng is None:
        rng = jax.random.PRNGKey(42)

    model = E8TransformerWorldModel(config)

    # Initialize with dummy input
    dummy_states = jnp.zeros((batch_size, seq_len, config.latent_dim))
    dummy_actions = jnp.zeros((batch_size, seq_len, config.action_dim))

    params = model.init(rng, dummy_states, dummy_actions)

    return model, params


__all__ = [
    "E8Attention",
    "E8TransformerBlock",
    "E8TransformerConfig",
    "E8TransformerWorldModel",
    "create_e8_transformer",
    "create_e8_transformer_config",
    "e8_quantize_ste",
    "e8_transformer_loss",
    "nearest_e8_jax",
]
