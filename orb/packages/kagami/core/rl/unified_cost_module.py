"""UnifiedCostModule - LeCun's Intrinsic/Trainable Cost Architecture.

LeCun (2022) Section 4.10:
"The cost module computes a scalar cost from the current state and proposed
action. It contains two sub-modules:
1. Intrinsic Cost (IC): Computes immutable costs (safety, basic drives)
2. Trainable Critic (TC): Learned cost predictor trained by backprop"

Key insight: IC is IMMUTABLE (hardcoded safety constraints), while TC is
LEARNED (adapts to tasks). The Configurator modulates their weights.

Architecture:
    ┌─────────────────────────────────────────────────────────────────┐
    │                    UNIFIED COST MODULE                          │
    │  ┌─────────────────────────────────────────────────────────────┐│
    │  │  Intrinsic Cost (IC) - IMMUTABLE                            ││
    │  │    → Safety: CBF h(x) violations                            ││
    │  │    → Discomfort: Extreme states (hunger, pain)              ││
    │  │    → Instincts: Basic drives (curiosity, homeostasis)       ││
    │  │                                                              ││
    │  │  Trainable Critic (TC) - LEARNED                            ││
    │  │    → Value predictor: state,action → expected future cost   ││
    │  │    → Trained via TD learning or world model rollouts        ││
    │  │                                                              ││
    │  │  Combined:                                                   ││
    │  │    C(s,a) = λ_IC * IC(s,a) + λ_TC * TC(s,a)                 ││
    │  │    where λ_IC, λ_TC set[Any] by Configurator                     ││
    │  └─────────────────────────────────────────────────────────────┘│
    └─────────────────────────────────────────────────────────────────┘

Created: December 6, 2025
Reference: LeCun (2022) Section 4.10 "The Cost Module", Figure 12
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import cast

import torch
import torch.nn as nn
import torch.nn.functional as F

logger = logging.getLogger(__name__)


@dataclass
class CostModuleConfig:
    """Configuration for UnifiedCostModule."""

    # Dimensions
    state_dim: int = 512
    action_dim: int = 64
    hidden_dim: int = 256

    # IC/TC balance (set[Any] by Configurator)
    ic_weight: float = 0.6  # Intrinsic cost weight (immutable)
    tc_weight: float = 0.4  # Trainable critic weight (learned)

    # Intrinsic cost components
    safety_weight: float = 10.0  # High weight for CBF violations
    discomfort_weight: float = 1.0
    drive_weight: float = 0.5

    # Trainable critic
    critic_layers: int = 3
    critic_dropout: float = 0.1

    # Safety thresholds
    cbf_threshold: float = 0.0  # h(x) < 0 is unsafe


class IntrinsicCost(nn.Module):
    """Intrinsic Cost Module (IC) - IMMUTABLE safety and drive costs.

    LeCun: "The IC sub-module is hard-wired (immutable) and computes
    the discomfort: the immediate cost of a state."

    IC encodes:
    1. Safety constraints (via CBF)
    2. Basic discomfort (extreme states)
    3. Instinctive drives (curiosity, homeostasis)

    IMPORTANT: IC parameters are NOT trainable by design.
    """

    def __init__(self, config: CostModuleConfig):
        super().__init__()
        self.config = config

        # Safety detector (identifies dangerous states)
        # Note: This USES CBF, doesn't replace it
        self.safety_detector = nn.Sequential(
            nn.Linear(config.state_dim + config.action_dim, config.hidden_dim),
            nn.ReLU(),
            nn.Linear(config.hidden_dim, 1),
        )

        # Discomfort detector (extreme states)
        self.discomfort_detector = nn.Sequential(
            nn.Linear(config.state_dim, config.hidden_dim // 2),
            nn.ReLU(),
            nn.Linear(config.hidden_dim // 2, 1),
            nn.Sigmoid(),  # Bounded 0-1
        )

        # Drive costs (from IntrinsicRewardCalculator, inverted)
        self.drive_weights = {
            "curiosity": 0.4,
            "novelty": 0.3,
            "empowerment": 0.2,
            "homeostasis": 0.1,
        }

        # FREEZE parameters (IC is immutable)
        for param in self.parameters():
            param.requires_grad = False

    def forward(
        self,
        state: torch.Tensor,
        action: torch.Tensor,
        cbf_value: torch.Tensor | None = None,
    ) -> dict[str, torch.Tensor]:
        """Compute intrinsic cost.

        Args:
            state: [B, state_dim] current state
            action: [B, action_dim] proposed action
            cbf_value: [B, 1] CBF h(x) value (optional)

        Returns:
            Dict with total IC cost and components
        """
        state.shape[0]
        device = state.device

        # 1. Safety cost (CBF violation)
        if cbf_value is not None:
            # Cost increases exponentially as h(x) approaches 0
            # h(x) < 0 → infinite cost (unsafe)
            safety_margin = cbf_value.clamp(min=-10)
            safety_cost = torch.where(
                safety_margin < self.config.cbf_threshold,
                torch.tensor(float("inf"), device=device),
                torch.exp(-safety_margin),  # Exponential barrier
            )
        else:
            # Estimate safety from state-action
            x = torch.cat([state, action], dim=-1)
            safety_score = self.safety_detector(x)
            safety_cost = F.softplus(-safety_score)  # Soft barrier

        # 2. Discomfort cost (extreme states)
        discomfort = self.discomfort_detector(state)

        # 3. Drive cost (inverse of intrinsic reward)
        # HARDENED (Dec 22, 2025): Use real drive system
        from kagami.core.motivation.drive_system import get_drive_system

        drive_system = get_drive_system()
        if drive_system is not None:
            # Get current drive satisfaction from real system
            drive_state = drive_system.get_state()
            # Drives return values in [0, 1], where 1 = fully satisfied
            # Cost is inverse: unsatisfied drives have high cost
            drive_satisfactions = torch.tensor(
                [
                    drive_state.get("curiosity", 0.5),
                    drive_state.get("competence", 0.5),
                    drive_state.get("autonomy", 0.5),
                    drive_state.get("relatedness", 0.5),
                ],
                device=device,
            )
            # Drive cost = 1 - satisfaction (unsatisfied = high cost)
            drive_cost = (1.0 - drive_satisfactions.mean()).unsqueeze(0).unsqueeze(0)
        else:
            # Fallback to learned drive detector if drive system unavailable
            drive_cost = self.discomfort_detector(state) * 0.5  # Use discomfort as proxy

        # Combine with weights
        total_ic = (
            self.config.safety_weight * safety_cost
            + self.config.discomfort_weight * discomfort
            + self.config.drive_weight * drive_cost
        )

        return {
            "total": total_ic,
            "safety": safety_cost,
            "discomfort": discomfort,
            "drives": drive_cost,
        }


class TrainableCritic(nn.Module):
    """Trainable Critic (TC) - Learned value predictor.

    LeCun: "The trainable critic sub-module predicts future values of
    the intrinsic cost. TC can be trained by back-propagation through
    a differentiable world model."

    TC learns to predict long-term costs from current state-action pairs.
    """

    def __init__(self, config: CostModuleConfig):
        super().__init__()
        self.config = config

        input_dim = config.state_dim + config.action_dim

        # Build networks with same architecture
        self.value_network = self._build_network(input_dim, config)
        self.target_network = self._build_network(input_dim, config)

        # Copy weights from value network to target and freeze
        self._sync_target()

    def _build_network(self, input_dim: int, config: CostModuleConfig) -> nn.Sequential:
        """Build value network."""
        layers = []
        prev_dim = input_dim

        for i in range(config.critic_layers):
            out_dim = config.hidden_dim if i < config.critic_layers - 1 else 1
            layers.append(nn.Linear(prev_dim, out_dim))

            if i < config.critic_layers - 1:
                layers.append(nn.LayerNorm(out_dim))  # type: ignore[arg-type]
                layers.append(nn.GELU())  # type: ignore[arg-type]
                layers.append(nn.Dropout(config.critic_dropout))  # type: ignore[arg-type]
            prev_dim = out_dim

        return nn.Sequential(*layers)

    def _sync_target(self) -> None:
        """Sync target network weights with value network."""
        self.target_network.load_state_dict(self.value_network.state_dict(), strict=False)
        for param in self.target_network.parameters():
            param.requires_grad = False

    def _update_target(self, tau: float = 0.005) -> None:
        """Update target network with EMA."""
        with torch.no_grad():
            for p, p_target in zip(
                self.value_network.parameters(), self.target_network.parameters(), strict=False
            ):
                p_target.data.mul_(1 - tau).add_(p.data, alpha=tau)

    def forward(
        self,
        state: torch.Tensor,
        action: torch.Tensor,
        use_target: bool = False,
    ) -> torch.Tensor:
        """Predict expected future cost.

        Args:
            state: [B, state_dim] current state
            action: [B, action_dim] proposed action
            use_target: Use target network (for stable targets)

        Returns:
            [B, 1] predicted future cost
        """
        x = torch.cat([state, action], dim=-1)
        network = self.target_network if use_target else self.value_network
        return cast(torch.Tensor, network(x))


class UnifiedCostModule(nn.Module):
    """Unified Cost Module combining IC and TC.

    Usage:
        cost_module = UnifiedCostModule()

        # Compute cost for action selection
        cost = cost_module(state, action, cbf_value)

        # Training (only TC is trainable)
        loss = cost_module.training_step(batch)

        # Configurator modulation
        cost_module.configure(ic_weight=0.7, tc_weight=0.3)
    """

    def __init__(self, config: CostModuleConfig | None = None):
        super().__init__()
        self.config = config or CostModuleConfig()

        # Sub-modules
        self.intrinsic_cost = IntrinsicCost(self.config)
        self.trainable_critic = TrainableCritic(self.config)

        # Modulation weights (set[Any] by Configurator)
        self.register_buffer("ic_weight", torch.tensor([self.config.ic_weight]))
        self.register_buffer("tc_weight", torch.tensor([self.config.tc_weight]))

        logger.info(
            f"UnifiedCostModule: IC weight={self.config.ic_weight:.2f}, "
            f"TC weight={self.config.tc_weight:.2f}"
        )

    def configure(
        self,
        ic_weight: float | None = None,
        tc_weight: float | None = None,
    ) -> None:
        """Configure IC/TC balance (called by Configurator).

        Args:
            ic_weight: Weight for intrinsic cost (safety-critical tasks → higher)
            tc_weight: Weight for trainable critic (learned tasks → higher)
        """
        if ic_weight is not None:
            self.ic_weight.fill_(ic_weight)  # type: ignore[operator]
        if tc_weight is not None:
            self.tc_weight.fill_(tc_weight)  # type: ignore[operator]

        logger.debug(
            f"CostModule configured: IC={float(self.ic_weight):.2f}, TC={float(self.tc_weight):.2f}"  # type: ignore[arg-type]
        )

    def forward(
        self,
        state: torch.Tensor,
        action: torch.Tensor,
        cbf_value: torch.Tensor | None = None,
    ) -> dict[str, torch.Tensor]:
        """Compute total cost.

        Args:
            state: [B, state_dim] current state
            action: [B, action_dim] proposed action
            cbf_value: [B, 1] CBF h(x) value (optional)

        Returns:
            Dict with total cost and components
        """
        # Intrinsic cost (immutable)
        ic_result = self.intrinsic_cost(state, action, cbf_value)

        # Trainable critic (learned)
        tc_value = self.trainable_critic(state, action)

        # Combine with weights
        total_cost = self.ic_weight * ic_result["total"] + self.tc_weight * tc_value

        return {
            "total": total_cost,
            "ic_total": ic_result["total"],
            "ic_safety": ic_result["safety"],
            "ic_discomfort": ic_result["discomfort"],
            "ic_drives": ic_result["drives"],
            "tc_value": tc_value,
            "ic_weight": self.ic_weight.clone(),  # type: ignore[operator]
            "tc_weight": self.tc_weight.clone(),  # type: ignore[operator]
        }

    def training_step(
        self,
        batch: dict[str, torch.Tensor],
    ) -> dict[str, torch.Tensor]:
        """Training step for TC (IC is frozen).

        Args:
            batch: Dict with state, action, next_state, cost

        Returns:
            Dict with loss components
        """
        state = batch["state"]
        action = batch["action"]
        next_state = batch["next_state"]
        target_cost = batch.get("cost")  # Optional ground truth

        # Current value estimate
        current_value = self.trainable_critic(state, action)

        # Target: IC at next state + discounted future TC
        with torch.no_grad():
            # Get IC at next state (no action needed for state cost)
            next_action = action  # Placeholder - should be from policy
            next_ic = self.intrinsic_cost(next_state, next_action)

            # Get discounted future value
            gamma = 0.99
            next_tc = self.trainable_critic(next_state, next_action, use_target=True)
            target = next_ic["total"] + gamma * next_tc

            if target_cost is not None:
                # Use ground truth if available
                target = target_cost

        # TD loss
        td_loss = F.mse_loss(current_value, target)

        # Update target network
        self.trainable_critic._update_target()

        return {
            "loss": td_loss,
            "current_value": current_value.mean(),
            "target_value": target.mean(),
        }

    def get_cost_gradient(
        self,
        state: torch.Tensor,
        action: torch.Tensor,
    ) -> torch.Tensor:
        """Get gradient of cost w.r.t. action for optimization.

        LeCun: "Actions can be computed through gradient-based optimization."

        Args:
            state: [B, state_dim] current state
            action: [B, action_dim] action to optimize

        Returns:
            [B, action_dim] gradient of cost w.r.t. action
        """
        action.requires_grad_(True)
        cost = self(state, action)["total"]
        grad = torch.autograd.grad(cost.sum(), action, create_graph=False)[0]
        action.requires_grad_(False)
        return grad


# =============================================================================
# INTEGRATION WITH CONFIGURATOR
# =============================================================================


def apply_cost_config(
    cost_module: UnifiedCostModule,
    config: dict[str, float],
) -> None:
    """Apply configuration from executive control.

    Args:
        cost_module: Cost module to configure
        config: Dict with ic_weight, tc_weight
    """
    cost_module.configure(
        ic_weight=config.get("ic_weight"),
        tc_weight=config.get("tc_weight"),
    )


# =============================================================================
# SINGLETON ACCESS
# =============================================================================

_cost_module: UnifiedCostModule | None = None


def get_cost_module(config: CostModuleConfig | None = None) -> UnifiedCostModule:
    """Get or create global UnifiedCostModule."""
    global _cost_module
    if _cost_module is None:
        _cost_module = UnifiedCostModule(config)
        logger.info("Created global UnifiedCostModule")
    return _cost_module


def reset_cost_module() -> None:
    """Reset global UnifiedCostModule (for testing)."""
    global _cost_module
    _cost_module = None
