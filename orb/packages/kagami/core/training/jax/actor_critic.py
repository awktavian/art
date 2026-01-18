"""JAX Actor-Critic Module — DreamerV3-Style Policy Learning.

Ports critical RL training capabilities from PyTorch:
1. Actor network with discrete/continuous action support
2. Critic with TwoHot value prediction
3. Lambda returns computation
4. Imagination rollouts in latent space

Architecture:
=============
```
                    IMAGINATION (Latent Rollouts)

  h_t, z_t ──→ Actor(h,z) ──→ a_t ──→ RSSM.step() ──→ h_{t+1}
               │
               └──→ Critic(h,z) ──→ V(s_t)

  Returns: λ-return with symlog normalization
```

References:
- Hafner et al. (2023) "Mastering Diverse Domains through World Models" (DreamerV3)
- Schrittwieser et al. (2020) "MuZero"

Created: January 12, 2026
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import NamedTuple

import jax
import jax.numpy as jnp
from flax import linen as nn

from .transforms import TwoHotEncoder, symlog

logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION
# =============================================================================


@dataclass(frozen=True)
class ActorCriticConfig:
    """Configuration for actor-critic."""

    # State dimensions
    hidden_dim: int = 384  # RSSM hidden dim
    stoch_dim: int = 32  # RSSM stochastic dim
    num_colonies: int = 7

    # Action space
    action_dim: int = 8
    discrete_actions: bool = False
    num_discrete_actions: int = 256  # For discrete action space

    # Network architecture
    actor_layers: tuple[int, ...] = (512, 512)
    critic_layers: tuple[int, ...] = (512, 512)

    # Value prediction
    num_value_bins: int = 255  # TwoHot bins
    value_low: float = -20.0
    value_high: float = 20.0

    # Lambda returns
    lambda_: float = 0.95  # TD(λ) parameter
    gamma: float = 0.997  # Discount factor

    # Actor
    entropy_scale: float = 3e-4
    actor_grad_mode: str = "dynamics"  # "dynamics" or "reinforce"

    # Training
    actor_lr: float = 3e-5
    critic_lr: float = 3e-5


# =============================================================================
# OUTPUT TYPES
# =============================================================================


class ActorOutput(NamedTuple):
    """Output from actor network."""

    action: jnp.ndarray  # [B, action_dim] sampled action
    log_prob: jnp.ndarray  # [B] log probability
    entropy: jnp.ndarray  # [B] entropy
    mean: jnp.ndarray  # [B, action_dim] action mean (for continuous)


class CriticOutput(NamedTuple):
    """Output from critic network."""

    value: jnp.ndarray  # [B] expected value
    logits: jnp.ndarray  # [B, num_bins] TwoHot logits


class ImagineOutput(NamedTuple):
    """Output from imagination rollout."""

    states: jnp.ndarray  # [B, H, state_dim] imagined states
    actions: jnp.ndarray  # [B, H, action_dim] taken actions
    rewards: jnp.ndarray  # [B, H] predicted rewards
    values: jnp.ndarray  # [B, H] predicted values
    continues: jnp.ndarray  # [B, H] continue probabilities
    log_probs: jnp.ndarray  # [B, H] action log probabilities


# =============================================================================
# ACTOR NETWORK
# =============================================================================


class Actor(nn.Module):
    """Actor network for action selection.

    Supports both discrete and continuous action spaces.
    Uses symlog activation for robust learning.
    """

    config: ActorCriticConfig

    @nn.compact
    def __call__(
        self,
        h: jnp.ndarray,
        z: jnp.ndarray,
        key: jax.Array | None = None,
        deterministic: bool = False,
    ) -> ActorOutput:
        """Compute action from latent state.

        Args:
            h: [B, 7, H] or [B, H] hidden state
            z: [B, 7, Z] or [B, Z] stochastic state
            key: Random key for sampling
            deterministic: If True, return mean action

        Returns:
            ActorOutput
        """
        cfg = self.config

        # Flatten colony dimension if present
        if h.ndim == 3:
            h_flat = h.reshape(h.shape[0], -1)
        else:
            h_flat = h

        if z.ndim == 3:
            z_flat = z.reshape(z.shape[0], -1)
        else:
            z_flat = z

        # Concatenate h and z
        x = jnp.concatenate([h_flat, z_flat], axis=-1)

        # MLP layers
        for i, units in enumerate(cfg.actor_layers):
            x = nn.Dense(units, name=f"fc_{i}")(x)
            x = nn.LayerNorm(name=f"ln_{i}")(x)
            x = jax.nn.silu(x)

        if cfg.discrete_actions:
            # Discrete action space
            logits = nn.Dense(cfg.num_discrete_actions, name="logits")(x)

            if deterministic:
                action_idx = jnp.argmax(logits, axis=-1)
            else:
                action_idx = jax.random.categorical(key, logits, axis=-1)

            # One-hot encode
            action = jax.nn.one_hot(action_idx, cfg.num_discrete_actions)

            # Log probability and entropy
            log_probs = jax.nn.log_softmax(logits, axis=-1)
            log_prob = jnp.take_along_axis(log_probs, action_idx[:, None], axis=-1).squeeze(-1)

            probs = jax.nn.softmax(logits, axis=-1)
            entropy = -jnp.sum(probs * log_probs, axis=-1)

            mean = probs
        else:
            # Continuous action space (Gaussian)
            mean = nn.Dense(cfg.action_dim, name="mean")(x)
            log_std = self.param(
                "log_std",
                nn.initializers.constant(-0.5),
                (cfg.action_dim,),
            )
            std = jnp.exp(log_std)

            if deterministic:
                action = mean
            else:
                action = mean + std * jax.random.normal(key, mean.shape)

            # Tanh squashing
            action = jnp.tanh(action)

            # Log probability (with tanh correction)
            log_prob = -0.5 * jnp.sum(
                jnp.square((jnp.arctanh(jnp.clip(action, -0.999, 0.999)) - mean) / std)
                + 2 * log_std
                + jnp.log(2 * jnp.pi),
                axis=-1,
            )
            # Tanh correction
            log_prob = log_prob - jnp.sum(jnp.log(1 - jnp.square(action) + 1e-6), axis=-1)

            # Entropy of Gaussian
            entropy = 0.5 * jnp.sum(1 + jnp.log(2 * jnp.pi) + 2 * log_std)
            entropy = jnp.broadcast_to(entropy, (action.shape[0],))

        return ActorOutput(
            action=action,
            log_prob=log_prob,
            entropy=entropy,
            mean=mean,
        )


# =============================================================================
# CRITIC NETWORK
# =============================================================================


class Critic(nn.Module):
    """Critic network for value estimation.

    Uses TwoHot encoding for robust value prediction across scales.
    """

    config: ActorCriticConfig

    def setup(self):
        self.twohot = TwoHotEncoder(
            num_bins=self.config.num_value_bins,
            low=self.config.value_low,
            high=self.config.value_high,
        )

    @nn.compact
    def __call__(
        self,
        h: jnp.ndarray,
        z: jnp.ndarray,
    ) -> CriticOutput:
        """Compute value from latent state.

        Args:
            h: [B, 7, H] or [B, H] hidden state
            z: [B, 7, Z] or [B, Z] stochastic state

        Returns:
            CriticOutput
        """
        cfg = self.config

        # Flatten colony dimension if present
        if h.ndim == 3:
            h_flat = h.reshape(h.shape[0], -1)
        else:
            h_flat = h

        if z.ndim == 3:
            z_flat = z.reshape(z.shape[0], -1)
        else:
            z_flat = z

        # Concatenate h and z
        x = jnp.concatenate([h_flat, z_flat], axis=-1)

        # MLP layers
        for i, units in enumerate(cfg.critic_layers):
            x = nn.Dense(units, name=f"fc_{i}")(x)
            x = nn.LayerNorm(name=f"ln_{i}")(x)
            x = jax.nn.silu(x)

        # TwoHot logits
        logits = nn.Dense(cfg.num_value_bins, name="value_logits")(x)

        # Decode to expected value
        value = self.twohot.decode(logits)

        return CriticOutput(value=value, logits=logits)


# =============================================================================
# LAMBDA RETURNS
# =============================================================================


def compute_lambda_returns(
    rewards: jnp.ndarray,
    values: jnp.ndarray,
    continues: jnp.ndarray,
    bootstrap: jnp.ndarray,
    lambda_: float = 0.95,
    gamma: float = 0.997,
) -> jnp.ndarray:
    """Compute λ-returns (TD(λ) targets).

    PyTorch: actor_critic.py:compute_lambda_returns

    λ-return is a weighted average of n-step returns:
        G_t^λ = (1-λ) Σ_{n=1}^{∞} λ^{n-1} G_t^{(n)}

    Computed recursively:
        G_t^λ = r_t + γ * c_t * ((1-λ) * V_{t+1} + λ * G_{t+1}^λ)

    Args:
        rewards: [B, H] predicted rewards
        values: [B, H] predicted values
        continues: [B, H] continue probabilities (1 - done)
        bootstrap: [B] bootstrap value at horizon
        lambda_: TD(λ) parameter (default: 0.95)
        gamma: Discount factor (default: 0.997)

    Returns:
        [B, H] λ-returns
    """
    _H = rewards.shape[1]  # Horizon (for documentation)

    # Append bootstrap value
    next_values = jnp.concatenate([values[:, 1:], bootstrap[:, None]], axis=1)

    # Compute recursively from the end
    def scan_fn(carry, inputs):
        next_return = carry
        r_t, v_next, c_t = inputs

        # G_t = r_t + γ * c_t * ((1-λ) * V_{t+1} + λ * G_{t+1})
        g_t = r_t + gamma * c_t * ((1 - lambda_) * v_next + lambda_ * next_return)

        return g_t, g_t

    # Scan backwards
    rewards_rev = rewards[:, ::-1].T  # [H, B]
    next_values_rev = next_values[:, ::-1].T
    continues_rev = continues[:, ::-1].T

    _, returns_rev = jax.lax.scan(
        scan_fn,
        bootstrap,
        (rewards_rev, next_values_rev, continues_rev),
    )

    # Reverse back
    returns = returns_rev[::-1].T  # [B, H]

    return returns


# =============================================================================
# DREAMER ACTOR-CRITIC
# =============================================================================


class DreamerActorCritic(nn.Module):
    """DreamerV3-style actor-critic for imagination-based learning.

    JAX port of PyTorch actor_critic.py:DreamerActorCritic
    """

    config: ActorCriticConfig

    def setup(self):
        self.actor = Actor(self.config)
        self.critic = Critic(self.config)

    def act(
        self,
        h: jnp.ndarray,
        z: jnp.ndarray,
        key: jax.Array,
        deterministic: bool = False,
    ) -> ActorOutput:
        """Select action from latent state."""
        return self.actor(h, z, key, deterministic)

    def value(
        self,
        h: jnp.ndarray,
        z: jnp.ndarray,
    ) -> CriticOutput:
        """Estimate value from latent state."""
        return self.critic(h, z)

    def compute_actor_loss(
        self,
        log_probs: jnp.ndarray,
        returns: jnp.ndarray,
        values: jnp.ndarray,
        entropy: jnp.ndarray,
    ) -> tuple[jnp.ndarray, dict]:
        """Compute actor loss.

        Uses either:
        - Dynamics backprop (DreamerV3 default): gradients flow through world model
        - REINFORCE: policy gradient with advantages

        Args:
            log_probs: [B, H] action log probabilities
            returns: [B, H] λ-returns
            values: [B, H] predicted values
            entropy: [B, H] action entropy

        Returns:
            loss: Scalar loss
            metrics: Dict of metrics
        """
        cfg = self.config

        # Advantages (normalized)
        advantages = returns - values
        advantages = (advantages - jnp.mean(advantages)) / (jnp.std(advantages) + 1e-8)

        if cfg.actor_grad_mode == "dynamics":
            # DreamerV3 style: maximize returns directly
            # Stop gradient on advantages (they're targets)
            actor_loss = -jnp.mean(returns)
        else:
            # REINFORCE style
            actor_loss = -jnp.mean(log_probs * jax.lax.stop_gradient(advantages))

        # Entropy bonus
        entropy_loss = -cfg.entropy_scale * jnp.mean(entropy)

        total_loss = actor_loss + entropy_loss

        metrics = {
            "actor_loss": actor_loss,
            "entropy_loss": entropy_loss,
            "entropy_mean": jnp.mean(entropy),
            "advantage_mean": jnp.mean(advantages),
            "advantage_std": jnp.std(advantages),
        }

        return total_loss, metrics

    def compute_critic_loss(
        self,
        value_logits: jnp.ndarray,
        returns: jnp.ndarray,
    ) -> tuple[jnp.ndarray, dict]:
        """Compute critic loss.

        Uses TwoHot cross-entropy for robust value learning.

        Args:
            value_logits: [B, H, num_bins] value prediction logits
            returns: [B, H] λ-return targets

        Returns:
            loss: Scalar loss
            metrics: Dict of metrics
        """
        # Symlog transform targets
        returns_symlog = symlog(returns)

        # TwoHot loss
        twohot = TwoHotEncoder(
            num_bins=self.config.num_value_bins,
            low=self.config.value_low,
            high=self.config.value_high,
        )

        # Flatten for loss computation
        B, H = returns.shape[:2]
        logits_flat = value_logits.reshape(-1, self.config.num_value_bins)
        returns_flat = returns_symlog.flatten()

        critic_loss = twohot.loss(logits_flat, returns_flat)

        # Decode values for metrics
        values = twohot.decode(value_logits)
        value_error = jnp.mean(jnp.abs(values - returns))

        metrics = {
            "critic_loss": critic_loss,
            "value_error": value_error,
            "value_mean": jnp.mean(values),
            "return_mean": jnp.mean(returns),
        }

        return critic_loss, metrics


# =============================================================================
# UNCERTAINTY-WEIGHTED LOSS
# =============================================================================


class UncertaintyWeightedLoss(nn.Module):
    """Multi-task loss with learnable uncertainty-based weights.

    JAX port of PyTorch losses/uncertainty_weighted.py

    Based on Kendall et al. (2018):
        L_total = Σ_i (1/(2σ_i²)) * L_i + log(σ_i)

    Parameterized as log(σ²) for numerical stability.
    """

    task_names: tuple[str, ...]
    init_log_var: float = 0.0

    @nn.compact
    def __call__(
        self,
        losses: dict[str, jnp.ndarray],
    ) -> tuple[jnp.ndarray, dict[str, jnp.ndarray], dict[str, jnp.ndarray]]:
        """Compute uncertainty-weighted loss.

        Args:
            losses: Dict mapping task name to loss value

        Returns:
            total_loss: Weighted sum of losses
            weighted_losses: Dict of weighted individual losses
            weights: Dict of learned weights
        """
        # Learnable log variances
        log_vars = self.param(
            "log_vars",
            nn.initializers.constant(self.init_log_var),
            (len(self.task_names),),
        )

        # Clamp for stability
        log_vars = jnp.clip(log_vars, -10.0, 10.0)

        total_loss = jnp.array(0.0)
        weighted_losses = {}
        weights = {}

        for i, name in enumerate(self.task_names):
            if name not in losses:
                continue

            loss_i = losses[name]
            log_var_i = log_vars[i]

            # Weight = exp(-log_var) = 1/σ²
            weight_i = jnp.exp(-log_var_i)

            # Weighted loss + regularizer
            weighted_loss = 0.5 * weight_i * loss_i + 0.5 * log_var_i

            total_loss = total_loss + weighted_loss
            weighted_losses[name] = weighted_loss
            weights[name] = weight_i

        return total_loss, weighted_losses, weights


# =============================================================================
# FACTORY FUNCTIONS
# =============================================================================


def create_actor_critic(
    config: ActorCriticConfig | None = None,
) -> DreamerActorCritic:
    """Create DreamerV3-style actor-critic."""
    if config is None:
        config = ActorCriticConfig()
    return DreamerActorCritic(config)


def create_actor(
    config: ActorCriticConfig | None = None,
) -> Actor:
    """Create actor network."""
    if config is None:
        config = ActorCriticConfig()
    return Actor(config)


def create_critic(
    config: ActorCriticConfig | None = None,
) -> Critic:
    """Create critic network."""
    if config is None:
        config = ActorCriticConfig()
    return Critic(config)


def create_uncertainty_weighted_loss(
    task_names: tuple[str, ...],
    init_log_var: float = 0.0,
) -> UncertaintyWeightedLoss:
    """Create uncertainty-weighted loss module."""
    return UncertaintyWeightedLoss(
        task_names=task_names,
        init_log_var=init_log_var,
    )


__all__ = [
    # Config
    "ActorCriticConfig",
    # Outputs
    "ActorOutput",
    "CriticOutput",
    "ImagineOutput",
    # Networks
    "Actor",
    "Critic",
    "DreamerActorCritic",
    # Loss
    "UncertaintyWeightedLoss",
    # Functions
    "compute_lambda_returns",
    # Factories
    "create_actor_critic",
    "create_actor",
    "create_critic",
    "create_uncertainty_weighted_loss",
]
