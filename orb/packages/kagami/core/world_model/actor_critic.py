"""DreamerV3-Style Actor-Critic for Improved Action Selection.

This module implements a world model-based actor-critic following
DreamerV3 (Hafner et al. 2023) with enhancements from MuZero and
EfficientZero V2.

Key Features:
    1. Symlog value normalization (prevents value explosion)
    2. Lambda returns with TD(λ) for variance reduction
    3. Discrete and continuous action heads
    4. Curious Replay priority signal integration
    5. Action space registry coupling (automatic sync)

Architecture:
    ┌─────────────────────────────────────────────────────────────────┐
    │                    IMAGINATION (Latent Rollouts)                │
    │                                                                 │
    │  h_t, z_t ──→ Actor(h,z) ──→ a_t ──→ RSSM.step() ──→ h_{t+1}  │
    │              │                                                  │
    │              └──→ Critic(h,z) ──→ V(s_t)                       │
    │                                                                 │
    │  Returns: λ-return with symlog normalization                   │
    └─────────────────────────────────────────────────────────────────┘

References:
    - Hafner et al. (2023) "Mastering Diverse Domains through World Models"
    - MuZero: Schrittwieser et al. (2020)
    - EfficientZero V2: Ye et al. (2024)

Usage:
    from kagami.core.world_model.actor_critic import (
        DreamerActorCritic,
        create_actor_critic,
    )

    # Create actor-critic
    ac = create_actor_critic(state_dim=64, action_dim=8)

    # Compute action in latent space
    action, log_prob = ac.act(h, z, deterministic=False)

    # Compute lambda returns for training
    returns = ac.compute_lambda_returns(rewards, values, continues)

    # Training step
    loss = ac.training_step(trajectories)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.distributions import Categorical, Independent, Normal

logger = logging.getLogger(__name__)


# =============================================================================
# SYMLOG TRANSFORMS (DreamerV3)
# =============================================================================


def symlog(x: torch.Tensor) -> torch.Tensor:
    """Symmetric logarithm: sign(x) * ln(|x| + 1).

    Compresses large values while preserving sign.
    Critical for stable value learning.
    """
    return torch.sign(x) * torch.log1p(torch.abs(x))


def symexp(x: torch.Tensor) -> torch.Tensor:
    """Inverse of symlog: sign(x) * (exp(|x|) - 1)."""
    return torch.sign(x) * (torch.exp(torch.abs(x)) - 1)


def twohot_encode(x: torch.Tensor, num_bins: int = 255) -> torch.Tensor:
    """Two-hot encode continuous values for categorical value prediction.

    DreamerV3 uses this for stable value learning with categorical heads.

    Args:
        x: Values to encode [..., 1] or [...]
        num_bins: Number of bins (default: 255 for DreamerV3)

    Returns:
        Two-hot encoded values [..., num_bins]
    """
    # Ensure x is at least 1D and squeeze trailing 1
    if x.dim() == 0:
        x = x.unsqueeze(0)
    if x.shape[-1] == 1:
        x = x.squeeze(-1)

    # Symlog transform first
    x_symlog = symlog(x)

    # Define bin boundaries (linearly spaced in symlog space)
    boundaries = torch.linspace(-20, 20, num_bins, device=x.device, dtype=x.dtype)

    # Find bin indices: for each x, find first boundary >= x
    # Shape: [...] -> [..., num_bins] -> [...]
    below = (x_symlog.unsqueeze(-1) >= boundaries).sum(dim=-1) - 1
    below = below.clamp(0, num_bins - 2)
    above = below + 1

    # Compute interpolation weights
    # Use advanced indexing to get boundary values
    below_flat = below.reshape(-1)
    above_flat = above.reshape(-1)
    x_flat = x_symlog.reshape(-1)

    t = (x_flat - boundaries[below_flat]) / (boundaries[above_flat] - boundaries[below_flat] + 1e-8)
    t = t.clamp(0, 1)
    t = t.reshape(x_symlog.shape)

    # Create two-hot encoding
    original_shape = x_symlog.shape
    twohot = torch.zeros(*original_shape, num_bins, device=x.device, dtype=x.dtype)

    # Flatten for scatter
    twohot_flat = twohot.reshape(-1, num_bins)
    below_idx = below.reshape(-1, 1)
    above_idx = above.reshape(-1, 1)
    t_flat = t.reshape(-1, 1)

    twohot_flat.scatter_(-1, below_idx, 1 - t_flat)
    twohot_flat.scatter_(-1, above_idx, t_flat)

    return twohot_flat.reshape(*original_shape, num_bins)


def twohot_decode(probs: torch.Tensor, num_bins: int = 255) -> torch.Tensor:
    """Decode two-hot categorical distribution to scalar value.

    Args:
        probs: Categorical probabilities [..., num_bins]
        num_bins: Number of bins

    Returns:
        Decoded values [..., 1]
    """
    boundaries = torch.linspace(-20, 20, num_bins, device=probs.device, dtype=probs.dtype)
    # Compute expected value in symlog space
    value_symlog = (probs * boundaries).sum(dim=-1)
    # Transform back and add dim for consistency
    return symexp(value_symlog).unsqueeze(-1)


# =============================================================================
# CONFIGURATION
# =============================================================================


@dataclass
class ActorCriticConfig:
    """Configuration for actor-critic."""

    # Dimensions
    state_dim: int = 64  # h dimension (deterministic)
    stoch_dim: int = 32  # z dimension (stochastic)
    action_dim: int = 8  # Action dimension
    hidden_dim: int = 256  # MLP hidden dimension

    # Action type
    discrete_actions: bool = False
    num_discrete_actions: int = 388  # From action space registry

    # Value learning
    num_value_bins: int = 255  # For categorical value
    use_symlog: bool = True

    # Lambda returns
    lambda_: float = 0.95  # TD(λ) parameter
    gamma: float = 0.997  # Discount factor

    # Actor
    actor_entropy_scale: float = 3e-4  # Entropy regularization
    actor_grad_clip: float = 100.0

    # Critic
    critic_slow_ema: float = 0.98  # EMA for target critic
    critic_grad_clip: float = 100.0

    # Training
    imagination_horizon: int = 15  # Rollout length
    batch_size: int = 16
    learning_rate: float = 3e-4
    weight_decay: float = 0.0

    # Device
    device: str = "cpu"


# =============================================================================
# ACTOR NETWORK
# =============================================================================


class Actor(nn.Module):
    """Actor network for action selection.

    Supports both discrete and continuous action spaces.

    Architecture:
        [h; z] -> MLP -> action_dist

    For discrete: outputs categorical logits
    For continuous: outputs mean + log_std for diagonal Gaussian
    """

    def __init__(self, config: ActorCriticConfig):
        super().__init__()
        self.config = config
        input_dim = config.state_dim + config.stoch_dim

        # Shared trunk
        self.trunk = nn.Sequential(
            nn.Linear(input_dim, config.hidden_dim),
            nn.LayerNorm(config.hidden_dim),
            nn.SiLU(),
            nn.Linear(config.hidden_dim, config.hidden_dim),
            nn.LayerNorm(config.hidden_dim),
            nn.SiLU(),
        )

        if config.discrete_actions:
            # Categorical head
            self.head = nn.Linear(config.hidden_dim, config.num_discrete_actions)
        else:
            # Gaussian head (mean + log_std)
            self.mean = nn.Linear(config.hidden_dim, config.action_dim)
            self.log_std = nn.Linear(config.hidden_dim, config.action_dim)

        self._init_weights()

    def _init_weights(self) -> None:
        """Initialize output layer to near-zero for stable training."""
        if self.config.discrete_actions:
            nn.init.zeros_(self.head.weight)
            nn.init.zeros_(self.head.bias)
        else:
            nn.init.zeros_(self.mean.weight)
            nn.init.zeros_(self.mean.bias)
            # Initialize log_std to small values for narrow initial distribution
            nn.init.constant_(self.log_std.weight, 0.0)
            nn.init.constant_(self.log_std.bias, -1.0)

    def forward(
        self,
        h: torch.Tensor,
        z: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """Compute action distribution.

        Args:
            h: Deterministic state [B, state_dim]
            z: Stochastic state [B, stoch_dim]

        Returns:
            action: Sampled action [B, action_dim]
            log_prob: Log probability of action [B]
        """
        x = torch.cat([h, z], dim=-1)
        features = self.trunk(x)

        if self.config.discrete_actions:
            logits = self.head(features)
            dist = Categorical(logits=logits)
            action = dist.sample()
            log_prob = dist.log_prob(action)
        else:
            mean = self.mean(features)
            log_std = self.log_std(features)
            # Clamp log_std for stability
            log_std = torch.clamp(log_std, -10, 2)
            std = torch.exp(log_std)

            dist = Independent(Normal(mean, std), 1)
            action = dist.rsample()  # Reparameterized for gradient flow
            log_prob = dist.log_prob(action)

        return action, log_prob

    def get_action(
        self,
        h: torch.Tensor,
        z: torch.Tensor,
        deterministic: bool = False,
    ) -> torch.Tensor:
        """Get action (optionally deterministic).

        Args:
            h: Deterministic state [B, state_dim]
            z: Stochastic state [B, stoch_dim]
            deterministic: If True, return mode instead of sample

        Returns:
            action: [B, action_dim]
        """
        x = torch.cat([h, z], dim=-1)
        features = self.trunk(x)

        if self.config.discrete_actions:
            logits = self.head(features)
            if deterministic:
                action = logits.argmax(dim=-1)
            else:
                dist = Categorical(logits=logits)
                action = dist.sample()
        else:
            mean = self.mean(features)
            if deterministic:
                action = mean
            else:
                log_std = torch.clamp(self.log_std(features), -10, 2)
                std = torch.exp(log_std)
                action = Normal(mean, std).rsample()

        return action


# =============================================================================
# CRITIC NETWORK
# =============================================================================


class Critic(nn.Module):
    """Critic network for value estimation.

    Uses categorical value head (two-hot) for stable learning.

    Architecture:
        [h; z] -> MLP -> value_bins (categorical)
        Decode via two-hot to scalar value
    """

    def __init__(self, config: ActorCriticConfig):
        super().__init__()
        self.config = config
        input_dim = config.state_dim + config.stoch_dim

        # Value trunk
        self.trunk = nn.Sequential(
            nn.Linear(input_dim, config.hidden_dim),
            nn.LayerNorm(config.hidden_dim),
            nn.SiLU(),
            nn.Linear(config.hidden_dim, config.hidden_dim),
            nn.LayerNorm(config.hidden_dim),
            nn.SiLU(),
        )

        # Categorical value head
        self.value_head = nn.Linear(config.hidden_dim, config.num_value_bins)

        self._init_weights()

    def _init_weights(self) -> None:
        """Initialize to predict zero value initially."""
        nn.init.zeros_(self.value_head.weight)
        nn.init.zeros_(self.value_head.bias)

    def forward(self, h: torch.Tensor, z: torch.Tensor) -> torch.Tensor:
        """Compute value estimate.

        Args:
            h: Deterministic state [B, state_dim]
            z: Stochastic state [B, stoch_dim]

        Returns:
            value: Scalar value [B, 1]
        """
        x = torch.cat([h, z], dim=-1)
        features = self.trunk(x)
        logits = self.value_head(features)
        probs = F.softmax(logits, dim=-1)
        value = twohot_decode(probs, self.config.num_value_bins)
        return value

    def forward_logits(self, h: torch.Tensor, z: torch.Tensor) -> torch.Tensor:
        """Get raw value logits (for training).

        Args:
            h: Deterministic state [B, state_dim]
            z: Stochastic state [B, stoch_dim]

        Returns:
            logits: [B, num_bins]
        """
        x = torch.cat([h, z], dim=-1)
        features = self.trunk(x)
        return self.value_head(features)


# =============================================================================
# DREAMER ACTOR-CRITIC
# =============================================================================


class DreamerActorCritic(nn.Module):
    """DreamerV3-style actor-critic for world model-based RL.

    Implements:
        1. Actor-critic learning in latent space
        2. Lambda returns with symlog normalization
        3. Slow-target critic (EMA)
        4. Entropy regularization
        5. Automatic action space coupling

    Training occurs entirely in imagination (latent rollouts).
    """

    def __init__(self, config: ActorCriticConfig):
        super().__init__()
        self.config = config

        # Networks
        self.actor = Actor(config)
        self.critic = Critic(config)

        # Slow target critic (EMA copy)
        self.critic_target = Critic(config)
        self.critic_target.load_state_dict(self.critic.state_dict())
        for p in self.critic_target.parameters():
            p.requires_grad = False

        # Value normalization statistics (running mean/std)
        self.register_buffer("value_mean", torch.zeros(1))
        self.register_buffer("value_std", torch.ones(1))
        self.register_buffer("value_count", torch.zeros(1))

        logger.info(
            f"✅ DreamerActorCritic initialized: "
            f"discrete={config.discrete_actions}, "
            f"actions={config.num_discrete_actions if config.discrete_actions else config.action_dim}, "
            f"horizon={config.imagination_horizon}"
        )

    def act(
        self,
        h: torch.Tensor,
        z: torch.Tensor,
        deterministic: bool = False,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """Select action given latent state.

        Args:
            h: Deterministic state [B, state_dim]
            z: Stochastic state [B, stoch_dim]
            deterministic: Use mode instead of sample

        Returns:
            action: Selected action
            log_prob: Log probability (0 if deterministic)
        """
        if deterministic:
            action = self.actor.get_action(h, z, deterministic=True)
            log_prob = torch.zeros(action.shape[0], device=action.device)
        else:
            action, log_prob = self.actor(h, z)
        return action, log_prob

    def compute_value(self, h: torch.Tensor, z: torch.Tensor) -> torch.Tensor:
        """Compute value estimate.

        Args:
            h: Deterministic state [B, state_dim]
            z: Stochastic state [B, stoch_dim]

        Returns:
            value: [B, 1]
        """
        return self.critic(h, z)

    def compute_target_value(self, h: torch.Tensor, z: torch.Tensor) -> torch.Tensor:
        """Compute target value (from slow critic).

        Args:
            h: Deterministic state [B, state_dim]
            z: Stochastic state [B, stoch_dim]

        Returns:
            value: [B, 1]
        """
        with torch.no_grad():
            return self.critic_target(h, z)

    @torch.no_grad()
    def update_target(self) -> None:
        """Update slow target critic via EMA."""
        tau = self.config.critic_slow_ema
        for p, p_target in zip(
            self.critic.parameters(), self.critic_target.parameters(), strict=False
        ):
            p_target.data.lerp_(p.data, 1 - tau)

    def compute_lambda_returns(
        self,
        rewards: torch.Tensor,
        values: torch.Tensor,
        continues: torch.Tensor,
        bootstrap_value: torch.Tensor,
    ) -> torch.Tensor:
        """Compute λ-returns for value targets.

        Implements TD(λ) with proper bootstrapping.

        Args:
            rewards: [B, T] rewards at each step
            values: [B, T] value estimates
            continues: [B, T] continue flags (1 - done)
            bootstrap_value: [B, 1] value at final state

        Returns:
            returns: [B, T] lambda returns
        """
        λ = self.config.lambda_
        γ = self.config.gamma

        T = rewards.shape[1]

        # Work backwards to compute returns
        returns = torch.zeros_like(rewards)
        next_return = bootstrap_value.squeeze(-1)

        for t in reversed(range(T)):
            # TD target: r + γ * V(s')
            td_target = rewards[:, t] + γ * continues[:, t] * next_return

            # TD error
            delta = td_target - values[:, t]

            # λ-return: V(s) + δ + γλc * (G^λ_{t+1} - V(s'))
            returns[:, t] = (
                values[:, t]
                + delta
                + γ * λ * continues[:, t] * (next_return - values[:, t] if t < T - 1 else 0)
            )

            next_return = returns[:, t]

        return returns

    def _normalize_value(self, value: torch.Tensor) -> torch.Tensor:
        """Normalize value using running statistics."""
        return (value - self.value_mean) / (self.value_std + 1e-8)

    @torch.no_grad()
    def _update_value_stats(self, returns: torch.Tensor) -> None:
        """Update running mean/std of returns."""
        batch_mean = returns.mean()
        batch_std = returns.std()
        batch_count = returns.numel()

        # Welford's online algorithm
        old_count = self.value_count
        new_count = old_count + batch_count

        delta = batch_mean - self.value_mean
        self.value_mean.add_(delta * batch_count / new_count)

        m_a = self.value_std**2 * old_count
        m_b = batch_std**2 * batch_count
        M2 = m_a + m_b + delta**2 * old_count * batch_count / new_count

        self.value_std.copy_(torch.sqrt(M2 / new_count))
        self.value_count.copy_(new_count)

    def training_step(
        self,
        h_seq: torch.Tensor,
        z_seq: torch.Tensor,
        reward_seq: torch.Tensor,
        continue_seq: torch.Tensor,
    ) -> dict[str, torch.Tensor]:
        """Single training step on imagined trajectories.

        Args:
            h_seq: [B, T, state_dim] deterministic states
            z_seq: [B, T, stoch_dim] stochastic states
            reward_seq: [B, T] rewards
            continue_seq: [B, T] continue flags

        Returns:
            losses: Dict with actor_loss, critic_loss, entropy
        """
        B, T, _ = h_seq.shape

        # Compute values for all states
        h_flat = h_seq.reshape(B * T, -1)
        z_flat = z_seq.reshape(B * T, -1)

        values = self.critic(h_flat, z_flat).reshape(B, T)
        target_values = self.compute_target_value(h_flat, z_flat).reshape(B, T)

        # Bootstrap value from final state
        bootstrap = self.compute_target_value(h_seq[:, -1], z_seq[:, -1])

        # Compute λ-returns
        returns = self.compute_lambda_returns(reward_seq, target_values, continue_seq, bootstrap)

        # Update value statistics
        self._update_value_stats(returns)

        # --- Critic Loss ---
        # Two-hot encoding of returns for categorical value
        returns_encoded = twohot_encode(returns.unsqueeze(-1), self.config.num_value_bins)
        returns_encoded = returns_encoded.reshape(B * T, -1)

        value_logits = self.critic.forward_logits(h_flat, z_flat)
        critic_loss = F.cross_entropy(value_logits, returns_encoded.detach())

        # --- Actor Loss ---
        # Advantage = returns - baseline value
        advantages = returns - values.detach()

        # Normalize advantages (per-batch)
        advantages = (advantages - advantages.mean()) / (advantages.std() + 1e-8)

        # Get action log probs
        actions, log_probs = [], []
        for t in range(T):
            a, lp = self.actor(h_seq[:, t], z_seq[:, t])
            actions.append(a)
            log_probs.append(lp)

        log_probs = torch.stack(log_probs, dim=1)  # [B, T]

        # Policy gradient loss (negative because we maximize)
        policy_loss = -(log_probs * advantages).mean()

        # Entropy regularization
        entropy = -log_probs.mean()
        entropy_loss = -self.config.actor_entropy_scale * entropy

        actor_loss = policy_loss + entropy_loss

        # Update target critic
        self.update_target()

        return {
            "actor_loss": actor_loss,
            "critic_loss": critic_loss,
            "policy_loss": policy_loss,
            "entropy": entropy,
            "advantage_mean": advantages.mean(),
            "value_mean": values.mean(),
            "return_mean": returns.mean(),
        }


# =============================================================================
# FACTORY FUNCTIONS
# =============================================================================


def create_actor_critic(
    state_dim: int = 64,
    stoch_dim: int = 32,
    action_dim: int = 8,
    discrete_actions: bool = False,
    num_discrete_actions: int | None = None,
    device: str | None = None,
) -> DreamerActorCritic:
    """Create DreamerActorCritic instance.

    Args:
        state_dim: Deterministic state dimension (h)
        stoch_dim: Stochastic state dimension (z)
        action_dim: Continuous action dimension
        discrete_actions: Use discrete action space
        num_discrete_actions: Number of discrete actions (auto from registry if None)
        device: Torch device

    Returns:
        DreamerActorCritic instance
    """
    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"

    # Get action space size from registry if needed
    if discrete_actions and num_discrete_actions is None:
        from kagami.core.embodiment.action_space import get_action_registry

        registry = get_action_registry()
        num_discrete_actions = registry.effector_space_size

    config = ActorCriticConfig(
        state_dim=state_dim,
        stoch_dim=stoch_dim,
        action_dim=action_dim,
        discrete_actions=discrete_actions,
        num_discrete_actions=num_discrete_actions or 388,
        device=device,
    )

    model = DreamerActorCritic(config)
    return model.to(device)


# Global instance
_actor_critic: DreamerActorCritic | None = None


def get_actor_critic() -> DreamerActorCritic:
    """Get global actor-critic instance."""
    global _actor_critic
    if _actor_critic is None:
        _actor_critic = create_actor_critic()
    return _actor_critic


def reset_actor_critic() -> None:
    """Reset global instance."""
    global _actor_critic
    _actor_critic = None


__all__ = [
    "Actor",
    "ActorCriticConfig",
    "Critic",
    "DreamerActorCritic",
    "create_actor_critic",
    "get_actor_critic",
    "reset_actor_critic",
    "symexp",
    "symlog",
    "twohot_decode",
    "twohot_encode",
]
