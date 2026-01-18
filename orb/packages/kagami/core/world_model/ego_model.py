"""EgoModel - Deterministic Self-Predictor.

LeCun (2022) Section 4.10:
"The ego model is a model of the cost as a function of action given the current
state. It can be optimized with standard gradient descent...The ego model can
be used by the actor to compute the optimal action."

Key distinction from World Model:
- World Model: Stochastic, predicts world state
- Ego Model: Deterministic, predicts OWN actions and their effects

The EgoModel answers: "If I take action a in state s, what will happen to ME?"

This is crucial for:
1. Action optimization (gradient descent on actions)
2. Forward simulation of action consequences
3. Separating self-prediction from world prediction

Architecture:
    ┌─────────────────────────────────────────────────────────────────┐
    │                         EGO MODEL                               │
    │  ┌─────────────────────────────────────────────────────────────┐│
    │  │  State Encoder: world_state + proprio → ego_state           ││
    │  │                                                              ││
    │  │  Action Predictor: ego_state → action_distribution          ││
    │  │                                                              ││
    │  │  Effect Predictor: ego_state + action → next_ego_state      ││
    │  │                    (deterministic, differentiable)           ││
    │  │                                                              ││
    │  │  Cost Predictor: ego_state + action → expected_cost         ││
    │  └─────────────────────────────────────────────────────────────┘│
    │                                                                 │
    │  Training: Supervised on (state, action, outcome) triplets      │
    │  Inference: Gradient descent on action to minimize cost         │
    └─────────────────────────────────────────────────────────────────┘

Created: December 6, 2025
Reference: LeCun (2022) Section 4.10 "The Cost Module", Figure 12
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import torch
import torch.nn as nn
import torch.nn.functional as F

logger = logging.getLogger(__name__)


@dataclass
class EgoModelConfig:
    """Configuration for EgoModel."""

    # Dimensions
    world_state_dim: int = 512  # From world model
    proprio_dim: int = 64  # Proprioceptive state (body sense)
    ego_state_dim: int = 256  # Internal ego representation
    action_dim: int = 64  # Action space dimension
    mu_self_dim: int = (
        7  # S7 dimension (was 32)  # Strange loop self-representation (from OrganismRSSM)
    )

    # Architecture
    hidden_dim: int = 256
    n_layers: int = 3
    dropout: float = 0.1

    # Action optimization
    action_optim_steps: int = 10  # Gradient steps for action optimization
    action_optim_lr: float = 0.1  # Learning rate for action optimization

    # Training
    cost_weight: float = 1.0
    effect_weight: float = 1.0
    action_reg_weight: float = 0.01  # Action regularization

    # Strange Loop integration
    use_strange_loop: bool = True  # Wire mu_self from Strange Loop


class EgoStateEncoder(nn.Module):
    """Encode world state + proprioception + mu_self into ego state.

    The ego state represents the agent's internal model of its own
    situation, separate from its model of the external world.

    STRANGE LOOP INTEGRATION (Dec 6, 2025):
    When use_strange_loop=True, the encoder also receives mu_self from
    the HofstadterStrangeLoop, making the ego state self-aware.
    """

    def __init__(self, config: EgoModelConfig):
        super().__init__()
        self.config = config

        # Input includes mu_self from Strange Loop when enabled
        input_dim = config.world_state_dim + config.proprio_dim
        if config.use_strange_loop:
            input_dim += config.mu_self_dim

        layers = []
        prev_dim = input_dim
        for _ in range(config.n_layers):
            layers.extend(
                [
                    nn.Linear(prev_dim, config.hidden_dim),
                    nn.LayerNorm(config.hidden_dim),
                    nn.GELU(),
                    nn.Dropout(config.dropout),
                ]
            )
            prev_dim = config.hidden_dim

        layers.append(nn.Linear(prev_dim, config.ego_state_dim))

        self.encoder = nn.Sequential(*layers)

    def forward(
        self,
        world_state: torch.Tensor,
        proprio: torch.Tensor | None = None,
        mu_self: torch.Tensor | None = None,
    ) -> torch.Tensor:
        """Encode ego state with Strange Loop self-representation.

        Args:
            world_state: [B, world_state_dim] from world model
            proprio: [B, proprio_dim] proprioceptive state (optional)
            mu_self: [B, mu_self_dim] Strange Loop self-representation (optional)

        Returns:
            [B, ego_state_dim] ego state encoding
        """
        batch_size = world_state.shape[0]
        device = world_state.device
        dtype = world_state.dtype

        if proprio is None:
            proprio = torch.zeros(batch_size, self.config.proprio_dim, device=device, dtype=dtype)

        inputs = [world_state, proprio]

        # Include mu_self from Strange Loop if enabled and provided
        if self.config.use_strange_loop:
            if mu_self is None:
                # Zero placeholder if Strange Loop not connected
                mu_self = torch.zeros(
                    batch_size, self.config.mu_self_dim, device=device, dtype=dtype
                )
            inputs.append(mu_self)

        x = torch.cat(inputs, dim=-1)
        return self.encoder(x)


class ActionPredictor(nn.Module):
    """Predict action distribution from ego state.

    Used for:
    1. Mode-1 reactive control (direct prediction)
    2. Initialization for Mode-2 optimization
    """

    def __init__(self, config: EgoModelConfig):
        super().__init__()
        self.config = config

        self.network = nn.Sequential(
            nn.Linear(config.ego_state_dim, config.hidden_dim),
            nn.GELU(),
            nn.Linear(config.hidden_dim, config.hidden_dim),
            nn.GELU(),
        )

        # Output mean and log_std for Gaussian policy
        self.mean_head = nn.Linear(config.hidden_dim, config.action_dim)
        self.logstd_head = nn.Linear(config.hidden_dim, config.action_dim)

    def forward(
        self,
        ego_state: torch.Tensor,
        deterministic: bool = False,
    ) -> tuple[torch.Tensor, dict[str, torch.Tensor]]:
        """Predict action from ego state.

        Args:
            ego_state: [B, ego_state_dim] ego state
            deterministic: If True, return mean (no sampling)

        Returns:
            action: [B, action_dim] predicted action
            info: Dict with mean, std, log_prob
        """
        h = self.network(ego_state)
        mean = self.mean_head(h)
        log_std = self.logstd_head(h).clamp(-10, 2)
        std = log_std.exp()

        if deterministic:
            action = mean
        else:
            # Reparameterized sampling
            noise = torch.randn_like(mean)
            action = mean + std * noise

        # Log probability for policy gradient
        # Use math.pi for full precision instead of hardcoded approximation
        import math

        log_2pi = math.log(2 * math.pi)
        log_prob = -0.5 * (((action - mean) / (std + 1e-8)) ** 2 + 2 * log_std + log_2pi).sum(
            dim=-1
        )

        return action, {
            "mean": mean,
            "std": std,
            "log_prob": log_prob,
        }


class EffectPredictor(nn.Module):
    """Predict effect of action on ego state (deterministic).

    This is the core of the ego model: given my current state and
    an action, what will my next state be?

    Crucially, this is DETERMINISTIC - no latent variables.
    Uncertainty about the world is handled by the world model.
    """

    def __init__(self, config: EgoModelConfig):
        super().__init__()
        self.config = config

        input_dim = config.ego_state_dim + config.action_dim

        self.network = nn.Sequential(
            nn.Linear(input_dim, config.hidden_dim),
            nn.LayerNorm(config.hidden_dim),
            nn.GELU(),
            nn.Linear(config.hidden_dim, config.hidden_dim),
            nn.LayerNorm(config.hidden_dim),
            nn.GELU(),
            nn.Linear(config.hidden_dim, config.ego_state_dim),
        )

        # Residual connection (predict delta, not full state)
        self.use_residual = True

    def forward(
        self,
        ego_state: torch.Tensor,
        action: torch.Tensor,
    ) -> torch.Tensor:
        """Predict next ego state given action.

        Args:
            ego_state: [B, ego_state_dim] current ego state
            action: [B, action_dim] action to take

        Returns:
            [B, ego_state_dim] predicted next ego state (deterministic)
        """
        x = torch.cat([ego_state, action], dim=-1)
        delta = self.network(x)

        if self.use_residual:
            return ego_state + delta
        return delta


class CostPredictor(nn.Module):
    """Predict expected cost of action in current state.

    LeCun: "The cost module computes a scalar cost from the current
    state and proposed action."

    This enables gradient-based action optimization:
    a* = argmin_a C(s, a)

    Differentiability is key - we need ∂C/∂a for optimization.
    """

    def __init__(self, config: EgoModelConfig):
        super().__init__()
        self.config = config

        input_dim = config.ego_state_dim + config.action_dim

        self.network = nn.Sequential(
            nn.Linear(input_dim, config.hidden_dim),
            nn.GELU(),
            nn.Linear(config.hidden_dim, config.hidden_dim // 2),
            nn.GELU(),
            nn.Linear(config.hidden_dim // 2, 1),
        )

    def forward(
        self,
        ego_state: torch.Tensor,
        action: torch.Tensor,
    ) -> torch.Tensor:
        """Predict cost of action.

        Args:
            ego_state: [B, ego_state_dim] current ego state
            action: [B, action_dim] proposed action

        Returns:
            [B, 1] predicted cost (lower is better)
        """
        x = torch.cat([ego_state, action], dim=-1)
        return self.network(x)


class EgoModel(nn.Module):
    """Complete Ego Model for self-prediction and action optimization.

    LeCun: "The ego model is a differentiable model that predicts
    one's own state and the cost of actions."

    STRANGE LOOP INTEGRATION (Dec 6, 2025):
    The EgoModel now integrates with HofstadterStrangeLoop via mu_self.
    When connected to OrganismRSSM, the ego state includes the Strange Loop's
    self-representation, making predictions self-aware.

    Usage:
        ego = EgoModel()

        # Connect to Strange Loop (from OrganismRSSM)
        ego.connect_strange_loop(organism_rssm.strange_loop)

        # Get ego state from world model output + mu_self
        ego_state = ego.encode(world_state, proprio)

        # Mode-1: Direct action prediction
        action, _ = ego.predict_action(ego_state)

        # Mode-2: Optimize action via gradient descent
        optimal_action = ego.optimize_action(ego_state)

        # Predict effect of action
        next_ego = ego.predict_effect(ego_state, action)

        # Get cost for planning
        cost = ego.predict_cost(ego_state, action)
    """

    def __init__(self, config: EgoModelConfig | None = None):
        super().__init__()
        self.config = config or EgoModelConfig()

        # Components
        self.state_encoder = EgoStateEncoder(self.config)
        self.action_predictor = ActionPredictor(self.config)
        self.effect_predictor = EffectPredictor(self.config)
        self.cost_predictor = CostPredictor(self.config)

        # Strange Loop connection (set[Any] via connect_strange_loop)
        self._strange_loop = None
        self._mu_self_cache: torch.Tensor | None = None

        logger.info(
            f"EgoModel: ego_state_dim={self.config.ego_state_dim}, "
            f"action_dim={self.config.action_dim}, "
            f"strange_loop={self.config.use_strange_loop}"
        )

    def connect_strange_loop(self, strange_loop: nn.Module) -> None:
        """Connect to HofstadterStrangeLoop from OrganismRSSM.

        Args:
            strange_loop: HofstadterStrangeLoop instance with mu_self parameter
        """
        self._strange_loop = strange_loop  # type: ignore[assignment]
        logger.info("EgoModel connected to HofstadterStrangeLoop")

    def get_mu_self(self, batch_size: int, device: torch.device) -> torch.Tensor | None:
        """Get mu_self from connected Strange Loop.

        Args:
            batch_size: Batch size for expansion
            device: Device for tensor

        Returns:
            [B, mu_self_dim] expanded mu_self or None
        """
        if self._strange_loop is None or not self.config.use_strange_loop:
            return None

        # Get mu_self from Strange Loop (it's a learnable parameter)
        mu_self = self._strange_loop.mu_self  # [mu_self_dim]
        return mu_self.unsqueeze(0).expand(batch_size, -1).to(device)

    def encode(
        self,
        world_state: torch.Tensor,
        proprio: torch.Tensor | None = None,
        mu_self: torch.Tensor | None = None,
    ) -> torch.Tensor:
        """Encode ego state from world state, proprioception, and mu_self.

        Args:
            world_state: [B, world_state_dim] from world model
            proprio: [B, proprio_dim] proprioceptive state (optional)
            mu_self: [B, mu_self_dim] Strange Loop self-representation (optional, auto-fetched if connected)

        Returns:
            [B, ego_state_dim] ego state encoding
        """
        # Auto-fetch mu_self from connected Strange Loop if not provided
        if mu_self is None and self.config.use_strange_loop:
            mu_self = self.get_mu_self(world_state.shape[0], world_state.device)

        return self.state_encoder(world_state, proprio, mu_self)

    def predict_action(
        self,
        ego_state: torch.Tensor,
        deterministic: bool = False,
    ) -> tuple[torch.Tensor, dict[str, torch.Tensor]]:
        """Predict action (Mode-1 reactive)."""
        return self.action_predictor(ego_state, deterministic)

    def predict_effect(
        self,
        ego_state: torch.Tensor,
        action: torch.Tensor,
    ) -> torch.Tensor:
        """Predict next ego state (deterministic)."""
        return self.effect_predictor(ego_state, action)

    def predict_cost(
        self,
        ego_state: torch.Tensor,
        action: torch.Tensor,
    ) -> torch.Tensor:
        """Predict cost of action."""
        return self.cost_predictor(ego_state, action)

    def optimize_action(
        self,
        ego_state: torch.Tensor,
        initial_action: torch.Tensor | None = None,
        horizon: int = 1,
    ) -> torch.Tensor:
        """Optimize action via gradient descent on cost (Mode-2 deliberative).

        LeCun: "Actions can be computed through optimization"

        Args:
            ego_state: [B, ego_state_dim] current ego state
            initial_action: [B, action_dim] starting point (or None for policy init)
            horizon: Number of steps to plan ahead

        Returns:
            [B, action_dim] optimized action
        """
        # Initialize action
        if initial_action is None:
            initial_action, _ = self.predict_action(ego_state, deterministic=True)

        # Clone and require grad for optimization
        action = initial_action.clone().detach().requires_grad_(True)

        # Optimizer for action
        optimizer = torch.optim.Adam([action], lr=self.config.action_optim_lr)

        # Gradient descent loop
        for _ in range(self.config.action_optim_steps):
            optimizer.zero_grad()

            # Compute total cost over horizon
            total_cost = torch.zeros(ego_state.shape[0], 1, device=ego_state.device)
            current_ego = ego_state

            for t in range(horizon):
                # Cost at this step
                step_cost = self.predict_cost(current_ego, action)
                total_cost = total_cost + step_cost

                # Predict next ego state (for multi-step planning)
                if t < horizon - 1:
                    current_ego = self.predict_effect(current_ego, action)

            # Add action regularization (prefer smaller actions)
            action_reg = self.config.action_reg_weight * (action**2).sum(dim=-1, keepdim=True)
            loss = (total_cost + action_reg).mean()

            loss.backward()
            optimizer.step()

        return action.detach()

    def forward(
        self,
        world_state: torch.Tensor,
        proprio: torch.Tensor | None = None,
        action: torch.Tensor | None = None,
        mu_self: torch.Tensor | None = None,
        optimize: bool = False,
    ) -> dict[str, torch.Tensor]:
        """Forward pass through ego model with Strange Loop integration.

        Args:
            world_state: [B, world_state_dim] from world model
            proprio: [B, proprio_dim] proprioceptive state (optional)
            action: [B, action_dim] action (optional, predicted if None)
            mu_self: [B, mu_self_dim] Strange Loop self-representation (optional)
            optimize: If True, optimize action (Mode-2)

        Returns:
            Dict with ego_state, action, next_ego, cost, action_info, mu_self
        """
        # Encode ego state (includes mu_self if connected)
        ego_state = self.encode(world_state, proprio, mu_self)

        # Get action
        if action is None:
            if optimize:
                action = self.optimize_action(ego_state)
                action_info = {"optimized": True}
            else:
                action, action_info = self.predict_action(ego_state)  # type: ignore[assignment]
        else:
            action_info = {"provided": True}

        # Predict effect and cost
        next_ego = self.predict_effect(ego_state, action)
        cost = self.predict_cost(ego_state, action)

        # Get mu_self from Strange Loop if connected
        batch_size = world_state.shape[0]
        mu_self_out = self.get_mu_self(batch_size, world_state.device)

        result = {
            "ego_state": ego_state,
            "action": action,
            "next_ego": next_ego,
            "cost": cost,
            "action_info": action_info,
        }

        # Add Strange Loop information if connected
        if mu_self_out is not None:
            result["mu_self"] = mu_self_out
            result["strange_loop_connected"] = True
        else:
            result["strange_loop_connected"] = False

        return result  # type: ignore[return-value]

    def training_step(
        self,
        batch: dict[str, torch.Tensor],
    ) -> dict[str, torch.Tensor]:
        """Compute training loss.

        Args:
            batch: Dict with world_state, proprio, action, next_world_state, cost

        Returns:
            Dict with loss, effect_loss, cost_loss, action_loss
        """
        world_state = batch["world_state"]
        proprio = batch.get("proprio")
        action = batch["action"]
        next_world_state = batch["next_world_state"]
        target_cost = batch.get("cost")

        # Encode states
        ego_state = self.encode(world_state, proprio)
        next_ego_target = self.encode(next_world_state, proprio)

        # Effect prediction loss
        next_ego_pred = self.predict_effect(ego_state, action)
        effect_loss = F.mse_loss(next_ego_pred, next_ego_target.detach())

        # Cost prediction loss (if target available)
        if target_cost is not None:
            cost_pred = self.predict_cost(ego_state, action)
            cost_loss = F.mse_loss(cost_pred, target_cost)
        else:
            cost_loss = torch.tensor(0.0, device=world_state.device)

        # Action prediction loss (imitation)
        action_pred, _ = self.predict_action(ego_state, deterministic=True)
        action_loss = F.mse_loss(action_pred, action)

        # Total loss
        total_loss = (
            self.config.effect_weight * effect_loss
            + self.config.cost_weight * cost_loss
            + action_loss  # Always learn to imitate actions
        )

        return {
            "loss": total_loss,
            "effect_loss": effect_loss,
            "cost_loss": cost_loss,
            "action_loss": action_loss,
        }


# =============================================================================
# SINGLETON ACCESS
# =============================================================================

_ego_model: EgoModel | None = None


def get_ego_model(config: EgoModelConfig | None = None) -> EgoModel:
    """Get or create global EgoModel."""
    global _ego_model
    if _ego_model is None:
        _ego_model = EgoModel(config)
        logger.info("Created global EgoModel")
    return _ego_model


def reset_ego_model() -> None:
    """Reset global EgoModel (for testing)."""
    global _ego_model
    _ego_model = None
