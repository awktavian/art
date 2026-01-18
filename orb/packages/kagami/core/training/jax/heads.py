"""JAX Prediction Heads - Encoder/Decoder/Reward/Value/Actor.

BRICK-BY-BRICK COMPARISON:
=========================
PyTorch Source                          | JAX Target
----------------------------------------|-------------------------------------
rssm_core.py:obs_decoder                | ObservationDecoder
encoder.py (MLP encoder)                | ObservationEncoder
rssm_core.py:reward_head                | RewardHead
rssm_core.py:value_head                 | ValueHead
rssm_core.py:action_head                | ActorHead, ActionDecoder
rssm_core.py:continue_head              | ContinueHead

Created: January 8, 2026
"""

from __future__ import annotations

import jax.numpy as jnp
from flax import linen as nn

# =============================================================================
# OBSERVATION ENCODER
# =============================================================================


class ObservationEncoder(nn.Module):
    """Encodes observations to E8 codes and S7 phases.

    PyTorch: packages/kagami/core/world_model/encoder.py (MLP variant)

    Architecture:
    - obs → MLP → e8_code [B, 8]
    - obs → MLP → s7_phase [B, 7] (normalized to sphere)
    """

    obs_dim: int
    hidden_dim: int = 256
    e8_dim: int = 8
    num_layers: int = 2

    @nn.compact
    def __call__(self, obs: jnp.ndarray) -> tuple[jnp.ndarray, jnp.ndarray]:
        """Encode observation to E8 code and S7 phase.

        Args:
            obs: [B, obs_dim] or [B, T, obs_dim]

        Returns:
            e8_code: [B, 8] or [B, T, 8]
            s7_phase: [B, 7] or [B, T, 7] (unit sphere)
        """
        x = obs

        # MLP encoder
        for i in range(self.num_layers):
            x = nn.Dense(self.hidden_dim, name=f"fc{i}")(x)
            x = nn.relu(x)
        x = nn.LayerNorm(name="ln")(x)

        # E8 code head (8D)
        e8_code = nn.Dense(self.e8_dim, name="e8_head")(x)

        # S7 phase head (7D, normalized to unit sphere)
        s7_raw = nn.Dense(7, name="s7_head")(x)
        s7_phase = s7_raw / (jnp.linalg.norm(s7_raw, axis=-1, keepdims=True) + 1e-8)

        return e8_code, s7_phase


# =============================================================================
# OBSERVATION DECODER
# =============================================================================


class ObservationDecoder(nn.Module):
    """Decodes hidden state to observations (symlog space).

    PyTorch: packages/kagami/core/world_model/rssm_core.py:obs_decoder

    Architecture:
    - concat(h_mean, z_mean) → MLP → obs_pred
    - Output is in symlog space
    """

    obs_dim: int
    hidden_dim: int = 256
    num_layers: int = 2

    @nn.compact
    def __call__(self, h: jnp.ndarray, z: jnp.ndarray) -> jnp.ndarray:
        """Decode from hidden and stochastic state.

        Args:
            h: [B, 7, H] or [B, H] hidden state
            z: [B, 7, Z] or [B, Z] stochastic state

        Returns:
            obs_pred: [B, obs_dim] in symlog space
        """
        # Average over colonies if needed
        h_mean = jnp.mean(h, axis=-2) if h.ndim == 3 else h
        z_mean = jnp.mean(z, axis=-2) if z.ndim == 3 else z

        x = jnp.concatenate([h_mean, z_mean], axis=-1)

        for i in range(self.num_layers):
            x = nn.Dense(self.hidden_dim, name=f"fc{i}")(x)
            x = nn.relu(x)

        return nn.Dense(self.obs_dim, name="output")(x)


# =============================================================================
# REWARD HEAD (TwoHot)
# =============================================================================


class RewardHead(nn.Module):
    """TwoHot reward prediction head.

    PyTorch: packages/kagami/core/world_model/rssm_core.py:reward_head

    Predicts logits over TwoHot bins for distributional reward prediction.
    Uses DreamerV3-style TwoHot encoding.
    """

    hidden_dim: int = 256
    num_bins: int = 255

    @nn.compact
    def __call__(self, h: jnp.ndarray, z: jnp.ndarray) -> jnp.ndarray:
        """Predict reward logits.

        Args:
            h: [B, 7, H] or [B, H] hidden state
            z: [B, 7, Z] or [B, Z] stochastic state

        Returns:
            [B, num_bins] reward logits for TwoHot
        """
        h_mean = jnp.mean(h, axis=-2) if h.ndim == 3 else h
        z_mean = jnp.mean(z, axis=-2) if z.ndim == 3 else z

        x = jnp.concatenate([h_mean, z_mean], axis=-1)
        x = nn.Dense(self.hidden_dim, name="fc1")(x)
        x = nn.gelu(x)
        x = nn.Dense(self.num_bins, name="output")(x)

        return x


# =============================================================================
# VALUE HEAD (TwoHot)
# =============================================================================


class ValueHead(nn.Module):
    """TwoHot value prediction head.

    PyTorch: packages/kagami/core/world_model/rssm_core.py:value_head

    Predicts state value V(s) using TwoHot distribution.
    Deeper network than reward head for better value estimation.
    """

    hidden_dim: int = 256
    num_bins: int = 255

    @nn.compact
    def __call__(self, h: jnp.ndarray, z: jnp.ndarray) -> jnp.ndarray:
        """Predict value logits.

        Args:
            h: [B, 7, H] or [B, H] hidden state
            z: [B, 7, Z] or [B, Z] stochastic state

        Returns:
            [B, num_bins] value logits for TwoHot
        """
        h_mean = jnp.mean(h, axis=-2) if h.ndim == 3 else h
        z_mean = jnp.mean(z, axis=-2) if z.ndim == 3 else z

        x = jnp.concatenate([h_mean, z_mean], axis=-1)
        x = nn.Dense(self.hidden_dim, name="fc1")(x)
        x = nn.gelu(x)
        x = nn.Dense(self.hidden_dim, name="fc2")(x)
        x = nn.gelu(x)
        x = nn.Dense(self.num_bins, name="output")(x)

        return x


# =============================================================================
# CONTINUE HEAD
# =============================================================================


class ContinueHead(nn.Module):
    """Episode continuation prediction head.

    PyTorch: packages/kagami/core/world_model/rssm_core.py:continue_head

    Predicts probability that episode continues (1 - done).
    Binary classification, no TwoHot needed.
    """

    hidden_dim: int = 256

    @nn.compact
    def __call__(self, h: jnp.ndarray, z: jnp.ndarray) -> jnp.ndarray:
        """Predict continuation probability.

        Args:
            h: [B, 7, H] or [B, H] hidden state
            z: [B, 7, Z] or [B, Z] stochastic state

        Returns:
            [B, 1] continuation probability (sigmoid applied)
        """
        h_mean = jnp.mean(h, axis=-2) if h.ndim == 3 else h
        z_mean = jnp.mean(z, axis=-2) if z.ndim == 3 else z

        x = jnp.concatenate([h_mean, z_mean], axis=-1)
        x = nn.Dense(self.hidden_dim, name="fc1")(x)
        x = nn.gelu(x)
        logits = nn.Dense(1, name="output")(x)

        return jax.nn.sigmoid(logits)


# =============================================================================
# ACTOR HEAD
# =============================================================================


class ActorHead(nn.Module):
    """Action prediction head with Gaussian policy.

    Outputs mean and log_std for continuous action space.
    Used for actor-critic training in DreamerV3.
    """

    action_dim: int
    hidden_dim: int = 256
    min_log_std: float = -10.0
    max_log_std: float = 2.0

    @nn.compact
    def __call__(
        self,
        h: jnp.ndarray,
        z: jnp.ndarray,
    ) -> tuple[jnp.ndarray, jnp.ndarray]:
        """Predict action distribution parameters.

        Args:
            h: [B, 7, H] or [B, H] hidden state
            z: [B, 7, Z] or [B, Z] stochastic state

        Returns:
            mean: [B, action_dim] action mean
            log_std: [B, action_dim] action log std (clamped)
        """
        h_mean = jnp.mean(h, axis=-2) if h.ndim == 3 else h
        z_mean = jnp.mean(z, axis=-2) if z.ndim == 3 else z

        x = jnp.concatenate([h_mean, z_mean], axis=-1)
        x = nn.Dense(self.hidden_dim, name="fc1")(x)
        x = nn.relu(x)
        x = nn.Dense(self.hidden_dim, name="fc2")(x)
        x = nn.relu(x)

        mean = nn.Dense(self.action_dim, name="mean")(x)
        log_std = nn.Dense(self.action_dim, name="log_std")(x)
        log_std = jnp.clip(log_std, self.min_log_std, self.max_log_std)

        return mean, log_std


# =============================================================================
# ACTION DECODER (Simple)
# =============================================================================


class ActionDecoder(nn.Module):
    """Simple action decoder for RSSM action prediction.

    PyTorch: packages/kagami/core/world_model/rssm_core.py:action_head

    Decodes action from (h, z) pair. Used in RSSM step.
    """

    action_dim: int
    hidden_dim: int = 384

    @nn.compact
    def __call__(self, hz: jnp.ndarray) -> jnp.ndarray:
        """Decode action from concatenated (h, z).

        Args:
            hz: [B, 7, H+Z] concatenated hidden and stochastic

        Returns:
            [B, 7, action_dim] decoded actions per colony
        """
        x = nn.Dense(self.hidden_dim, name="fc1")(hz)
        x = nn.gelu(x)
        return nn.Dense(self.action_dim, name="output")(x)


# =============================================================================
# H-JEPA PREDICTORS
# =============================================================================


class HJEPAPredictor(nn.Module):
    """H-JEPA multi-horizon latent predictor.

    Predicts future hidden states at various horizons (1, 4, 16 steps).
    Used for hierarchical joint-embedding predictive architecture.
    """

    output_dim: int
    horizon: int = 1

    @nn.compact
    def __call__(self, h: jnp.ndarray) -> jnp.ndarray:
        """Predict future hidden state.

        Args:
            h: [B, T, 7, H] hidden state sequence

        Returns:
            [B, T-horizon, 7, H] predicted future states
        """
        return nn.Dense(self.output_dim, name=f"hjepa_{self.horizon}")(h)


# =============================================================================
# E8 DECODER (for reconstruction)
# =============================================================================


class E8Decoder(nn.Module):
    """Decode from hidden state to E8 code.

    PyTorch: packages/kagami/core/world_model/rssm_core.py:obs_decoder
    (Outputs E8 code directly for E8 lattice E2E dynamics)
    """

    e8_dim: int = 8
    hidden_dim: int = 384

    @nn.compact
    def __call__(self, h: jnp.ndarray, z: jnp.ndarray) -> jnp.ndarray:
        """Decode E8 code from latent state.

        Args:
            h: [B, 7, H] hidden state
            z: [B, 7, Z] stochastic state

        Returns:
            [B, 8] predicted E8 code
        """
        # Concatenate and process per-colony
        hz = jnp.concatenate([h, z], axis=-1)
        e8_per_colony = nn.Dense(self.e8_dim, name="e8_decode")(hz)

        # Aggregate across colonies
        return jnp.mean(e8_per_colony, axis=-2)


# Need jax import for sigmoid
import jax

# =============================================================================
# EXPORTS
# =============================================================================


__all__ = [
    "ActionDecoder",
    "ActorHead",
    "ContinueHead",
    "E8Decoder",
    "HJEPAPredictor",
    "ObservationDecoder",
    "ObservationEncoder",
    "RewardHead",
    "ValueHead",
]
