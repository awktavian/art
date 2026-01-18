"""TD-MPC2 Style Planning Head.

CREATED: January 4, 2026

Implements TD-MPC2 style model-based planning for downstream task evaluation.
This adds a planning capability on top of our world model (OrganismRSSM/H-JEPA).

Key Components:
===============
1. Latent dynamics model (from world model)
2. Reward predictor (MLP on latent state)
3. Value predictor (MLP on latent state)
4. MPPI planner (Model Predictive Path Integral)

Planning Algorithm:
==================
1. Encode current observation to latent
2. Sample action sequences (Gaussian)
3. Rollout each sequence through world model
4. Compute trajectory returns (reward + terminal value)
5. Weight sequences by return (softmax)
6. Return weighted mean of first actions

References:
- Hansen et al. (2024): TD-MPC2: Scalable, Robust World Models
- Williams et al. (2017): Model Predictive Path Integral Control
- Hafner et al. (2023): DreamerV3 planning
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import torch
import torch.nn as nn
import torch.nn.functional as F

logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION
# =============================================================================


@dataclass
class TDMPCPlanningConfig:
    """Configuration for TD-MPC2 style planning."""

    # Latent dimensions
    latent_dim: int = 8  # E8 latent dimension
    action_dim: int = 6  # Action dimension

    # Predictor architecture
    hidden_dim: int = 256
    num_layers: int = 3

    # Planning parameters
    horizon: int = 15  # Planning horizon
    num_samples: int = 512  # Number of action sequences
    num_elites: int = 64  # Top-k for CEM refinement
    num_iterations: int = 3  # CEM iterations
    temperature: float = 0.5  # Softmax temperature

    # Action sampling
    action_noise_std: float = 0.3  # Initial noise std
    action_noise_decay: float = 0.95  # Decay per iteration
    action_momentum: float = 0.1  # Momentum from previous plan

    # Reward/value prediction
    discount: float = 0.99  # Discount factor
    normalize_returns: bool = True

    # Uncertainty (optional)
    use_ensemble: bool = False
    ensemble_size: int = 5


# =============================================================================
# PREDICTOR NETWORKS
# =============================================================================


class RewardPredictor(nn.Module):
    """Predicts reward from latent state and action.

    Architecture: MLP with layer norm and SiLU activation.
    """

    def __init__(self, config: TDMPCPlanningConfig):
        super().__init__()
        self.config = config

        # Input: latent + action
        input_dim = config.latent_dim + config.action_dim

        layers = []
        for i in range(config.num_layers):
            in_features = input_dim if i == 0 else config.hidden_dim
            layers.extend(
                [
                    nn.Linear(in_features, config.hidden_dim),
                    nn.LayerNorm(config.hidden_dim),
                    nn.SiLU(),
                ]
            )

        # Output: scalar reward
        layers.append(nn.Linear(config.hidden_dim, 1))

        self.mlp = nn.Sequential(*layers)

    def forward(self, latent: torch.Tensor, action: torch.Tensor) -> torch.Tensor:
        """Predict reward.

        Args:
            latent: [B, latent_dim] latent state
            action: [B, action_dim] action

        Returns:
            [B] predicted rewards
        """
        x = torch.cat([latent, action], dim=-1)
        return self.mlp(x).squeeze(-1)


class ValuePredictor(nn.Module):
    """Predicts value (expected return) from latent state.

    Architecture: MLP with layer norm and SiLU activation.
    """

    def __init__(self, config: TDMPCPlanningConfig):
        super().__init__()
        self.config = config

        layers = []
        for i in range(config.num_layers):
            in_features = config.latent_dim if i == 0 else config.hidden_dim
            layers.extend(
                [
                    nn.Linear(in_features, config.hidden_dim),
                    nn.LayerNorm(config.hidden_dim),
                    nn.SiLU(),
                ]
            )

        # Output: scalar value
        layers.append(nn.Linear(config.hidden_dim, 1))

        self.mlp = nn.Sequential(*layers)

    def forward(self, latent: torch.Tensor) -> torch.Tensor:
        """Predict value.

        Args:
            latent: [B, latent_dim] latent state

        Returns:
            [B] predicted values
        """
        return self.mlp(latent).squeeze(-1)


class LatentDynamics(nn.Module):
    """Predicts next latent state from current state and action.

    This wraps the world model's dynamics for planning.
    Architecture: MLP with residual connection.
    """

    def __init__(self, config: TDMPCPlanningConfig):
        super().__init__()
        self.config = config

        # Input: latent + action
        input_dim = config.latent_dim + config.action_dim

        layers = []
        for i in range(config.num_layers):
            in_features = input_dim if i == 0 else config.hidden_dim
            layers.extend(
                [
                    nn.Linear(in_features, config.hidden_dim),
                    nn.LayerNorm(config.hidden_dim),
                    nn.SiLU(),
                ]
            )

        # Output: latent delta (residual)
        layers.append(nn.Linear(config.hidden_dim, config.latent_dim))

        self.mlp = nn.Sequential(*layers)

    def forward(self, latent: torch.Tensor, action: torch.Tensor) -> torch.Tensor:
        """Predict next latent state.

        Args:
            latent: [B, latent_dim] current latent state
            action: [B, action_dim] action

        Returns:
            [B, latent_dim] next latent state
        """
        x = torch.cat([latent, action], dim=-1)
        delta = self.mlp(x)
        # Residual connection
        return latent + delta


# =============================================================================
# TD-MPC2 PLANNING HEAD
# =============================================================================


class TDMPC2PlanningHead(nn.Module):
    """TD-MPC2 style planning head for downstream tasks.

    Integrates with world model for model-based planning.

    Usage:
        # Create planning head
        planner = TDMPC2PlanningHead(config)

        # Plan from latent state
        action = planner.plan(latent_state)

        # Or use with world model
        planner.set_world_model(organism_rssm)
        action = planner.plan(latent_state, use_world_model=True)
    """

    def __init__(self, config: TDMPCPlanningConfig | None = None):
        super().__init__()
        self.config = config or TDMPCPlanningConfig()

        # Predictors
        self.reward_predictor = RewardPredictor(self.config)
        self.value_predictor = ValuePredictor(self.config)
        self.dynamics = LatentDynamics(self.config)

        # Optional ensemble for uncertainty
        if self.config.use_ensemble:
            self.reward_ensemble = nn.ModuleList(
                [RewardPredictor(self.config) for _ in range(self.config.ensemble_size)]
            )
            self.value_ensemble = nn.ModuleList(
                [ValuePredictor(self.config) for _ in range(self.config.ensemble_size)]
            )

        # External world model (optional)
        self.world_model: nn.Module | None = None

        # Persistent action mean for temporal smoothing
        self.register_buffer(
            "_action_mean",
            torch.zeros(self.config.horizon, self.config.action_dim),
        )

        logger.info(
            f"TDMPC2PlanningHead initialized:\n"
            f"  Horizon: {self.config.horizon}\n"
            f"  Samples: {self.config.num_samples}\n"
            f"  Ensemble: {self.config.use_ensemble}"
        )

    def set_world_model(self, world_model: nn.Module) -> None:
        """Set external world model for dynamics.

        Args:
            world_model: World model (e.g., OrganismRSSM, HJEPAModule)
        """
        self.world_model = world_model
        logger.info("World model set for planning")

    def _imagine_trajectory(
        self,
        initial_latent: torch.Tensor,
        actions: torch.Tensor,
        use_world_model: bool = False,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """Imagine trajectory through latent dynamics.

        Args:
            initial_latent: [B, latent_dim] initial latent state
            actions: [B, H, action_dim] action sequence
            use_world_model: If True, use external world model

        Returns:
            Tuple of:
                - rewards: [B, H] predicted rewards
                - final_latent: [B, latent_dim] final latent state
        """
        _B, H, _ = actions.shape

        latent = initial_latent
        rewards = []

        for t in range(H):
            action = actions[:, t]

            # Predict reward
            if self.config.use_ensemble:
                # Ensemble mean
                r = torch.stack([pred(latent, action) for pred in self.reward_ensemble]).mean(0)
            else:
                r = self.reward_predictor(latent, action)
            rewards.append(r)

            # Predict next latent
            if use_world_model and self.world_model is not None:
                # Use world model dynamics
                if hasattr(self.world_model, "imagine_trajectory"):
                    # H-JEPA style
                    next_latent = self.world_model.imagine_trajectory(
                        latent, action.unsqueeze(1), horizon=1
                    )[:, -1]
                elif hasattr(self.world_model, "transition"):
                    # RSSM style
                    next_latent = self.world_model.transition(latent, action)
                else:
                    # Fallback to internal dynamics
                    next_latent = self.dynamics(latent, action)
            else:
                next_latent = self.dynamics(latent, action)

            latent = next_latent

        rewards = torch.stack(rewards, dim=1)  # [B, H]
        return rewards, latent

    def _compute_returns(
        self,
        rewards: torch.Tensor,
        final_latent: torch.Tensor,
    ) -> torch.Tensor:
        """Compute discounted returns.

        Args:
            rewards: [B, H] rewards
            final_latent: [B, latent_dim] final latent state

        Returns:
            [B] trajectory returns
        """
        # Terminal value
        if self.config.use_ensemble:
            terminal_value = torch.stack([pred(final_latent) for pred in self.value_ensemble]).mean(
                0
            )
        else:
            terminal_value = self.value_predictor(final_latent)

        # Discounted sum
        discount = self.config.discount
        H = rewards.shape[1]

        # Compute discount factors [gamma^0, gamma^1, ..., gamma^(H-1)]
        discounts = discount ** torch.arange(H, device=rewards.device)

        # Sum discounted rewards + terminal value
        returns = (rewards * discounts).sum(dim=1) + (discount**H) * terminal_value

        if self.config.normalize_returns:
            # Normalize for stability
            returns = (returns - returns.mean()) / (returns.std() + 1e-6)

        return returns

    @torch.no_grad()
    def plan(
        self,
        latent: torch.Tensor,
        use_world_model: bool = False,
        deterministic: bool = False,
    ) -> torch.Tensor:
        """Plan optimal action using MPPI.

        Args:
            latent: [B, latent_dim] or [latent_dim] current latent state
            use_world_model: If True, use external world model for dynamics
            deterministic: If True, use mean action without sampling

        Returns:
            [B, action_dim] or [action_dim] optimal action
        """
        # Handle single sample
        squeeze_output = latent.dim() == 1
        if squeeze_output:
            latent = latent.unsqueeze(0)

        B = latent.shape[0]
        device = latent.device
        H = self.config.horizon
        action_dim = self.config.action_dim
        num_samples = self.config.num_samples

        if deterministic:
            # Just use mean from previous plan
            action = self._action_mean[0].to(device)
            if squeeze_output:
                return action
            return action.unsqueeze(0).expand(B, -1)

        # Initialize action distribution with momentum
        action_mean = self._action_mean.to(device)  # [H, action_dim]
        action_std = torch.ones(H, action_dim, device=device) * self.config.action_noise_std

        best_actions = None

        # CEM iterations
        for iteration in range(self.config.num_iterations):
            # Sample action sequences
            noise = torch.randn(num_samples, H, action_dim, device=device)
            actions = action_mean + action_std * noise
            actions = actions.clamp(-1, 1)

            # Expand latent for all samples: [B, latent_dim] -> [B * num_samples, latent_dim]
            latent_expanded = latent.unsqueeze(1).expand(-1, num_samples, -1)
            latent_expanded = latent_expanded.reshape(-1, latent.shape[-1])

            # Expand actions: [num_samples, H, action_dim] -> [B * num_samples, H, action_dim]
            actions_expanded = actions.unsqueeze(0).expand(B, -1, -1, -1)
            actions_expanded = actions_expanded.reshape(-1, H, action_dim)

            # Imagine trajectories
            rewards, final_latent = self._imagine_trajectory(
                latent_expanded, actions_expanded, use_world_model
            )

            # Compute returns
            returns = self._compute_returns(rewards, final_latent)  # [B * num_samples]
            returns = returns.reshape(B, num_samples)

            # Average across batch for action selection
            returns_avg = returns.mean(dim=0)  # [num_samples]

            # MPPI weighting
            weights = F.softmax(returns_avg / self.config.temperature, dim=0)

            # Weighted mean of action sequences
            best_actions = (weights.view(-1, 1, 1) * actions).sum(dim=0)  # [H, action_dim]

            # Update distribution for next iteration
            if iteration < self.config.num_iterations - 1:
                # CEM: fit to elites
                elite_idx = returns_avg.topk(self.config.num_elites).indices
                elite_actions = actions[elite_idx]  # [num_elites, H, action_dim]
                action_mean = elite_actions.mean(dim=0)
                action_std = elite_actions.std(dim=0).clamp(min=0.01)
                action_std *= self.config.action_noise_decay

        # Update persistent mean (shift by 1 for next step)
        self._action_mean.data = torch.cat(
            [
                best_actions[1:],
                torch.zeros(1, action_dim, device=device),
            ]
        )

        # Apply momentum
        if self.config.action_momentum > 0:
            self._action_mean.data *= 1 - self.config.action_momentum

        # Return first action
        action = best_actions[0]  # [action_dim]

        if squeeze_output:
            return action
        return action.unsqueeze(0).expand(B, -1)

    def reset_plan(self) -> None:
        """Reset action mean (call at episode start)."""
        self._action_mean.zero_()

    def forward(
        self,
        latent: torch.Tensor,
        action: torch.Tensor,
    ) -> dict[str, torch.Tensor]:
        """Forward pass for training predictors.

        Args:
            latent: [B, latent_dim] latent states
            action: [B, action_dim] actions

        Returns:
            Dict with predictions:
                - reward: [B] predicted rewards
                - value: [B] predicted values
                - next_latent: [B, latent_dim] predicted next states
        """
        return {
            "reward": self.reward_predictor(latent, action),
            "value": self.value_predictor(latent),
            "next_latent": self.dynamics(latent, action),
        }

    def compute_loss(
        self,
        latent: torch.Tensor,
        action: torch.Tensor,
        next_latent: torch.Tensor,
        reward: torch.Tensor,
        value_target: torch.Tensor,
    ) -> dict[str, torch.Tensor]:
        """Compute training losses.

        Args:
            latent: [B, latent_dim] current latent
            action: [B, action_dim] action taken
            next_latent: [B, latent_dim] actual next latent
            reward: [B] actual reward
            value_target: [B] bootstrapped value target

        Returns:
            Dict with losses:
                - reward_loss: Reward prediction loss
                - value_loss: Value prediction loss
                - dynamics_loss: Dynamics prediction loss
                - total_loss: Sum of losses
        """
        preds = self.forward(latent, action)

        reward_loss = F.mse_loss(preds["reward"], reward)
        value_loss = F.mse_loss(preds["value"], value_target)
        dynamics_loss = F.mse_loss(preds["next_latent"], next_latent)

        total_loss = reward_loss + value_loss + dynamics_loss

        return {
            "reward_loss": reward_loss,
            "value_loss": value_loss,
            "dynamics_loss": dynamics_loss,
            "total_loss": total_loss,
        }


# =============================================================================
# FACTORY AND EXPORTS
# =============================================================================


def create_tdmpc2_planner(
    latent_dim: int = 8,
    action_dim: int = 6,
    horizon: int = 15,
    num_samples: int = 512,
    use_ensemble: bool = False,
) -> TDMPC2PlanningHead:
    """Factory function for TD-MPC2 planning head.

    Args:
        latent_dim: Latent state dimension
        action_dim: Action dimension
        horizon: Planning horizon
        num_samples: Number of action samples
        use_ensemble: Whether to use ensemble predictors

    Returns:
        Configured TDMPC2PlanningHead
    """
    config = TDMPCPlanningConfig(
        latent_dim=latent_dim,
        action_dim=action_dim,
        horizon=horizon,
        num_samples=num_samples,
        use_ensemble=use_ensemble,
    )
    return TDMPC2PlanningHead(config)


def integrate_with_world_model(
    planner: TDMPC2PlanningHead,
    world_model: nn.Module,
) -> TDMPC2PlanningHead:
    """Integrate planning head with world model.

    Args:
        planner: TD-MPC2 planning head
        world_model: World model (OrganismRSSM, HJEPAModule, etc.)

    Returns:
        Planner with world model set
    """
    planner.set_world_model(world_model)
    return planner


__all__ = [
    "LatentDynamics",
    "RewardPredictor",
    "TDMPC2PlanningHead",
    "TDMPCPlanningConfig",
    "ValuePredictor",
    "create_tdmpc2_planner",
    "integrate_with_world_model",
]
