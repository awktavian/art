"""Neuromodulator System - Four-Channel State Modulation.

BRAIN SCIENCE BASIS (December 2025):
====================================
Neuromodulators globally configure neural processing:

1. DOPAMINE (DA) - Reward & Motivation
   - Reward prediction errors drive learning
   - Phasic bursts signal unexpected rewards
   - Tonic levels set[Any] motivation/engagement
   - Source: VTA, Substantia Nigra

2. NOREPINEPHRINE (NE) - Arousal & Exploration
   - Gain modulation (multiplicative effect)
   - Exploration vs exploitation tradeoff
   - Uncertainty/novelty signals
   - Source: Locus Coeruleus

3. ACETYLCHOLINE (ACh) - Attention & Learning
   - Precision weighting in predictive coding
   - Learning rate modulation
   - Bottom-up attention enhancement
   - Source: Basal Forebrain

4. SEROTONIN (5-HT) - Patience & Risk
   - Temporal discounting (impulsivity)
   - Risk aversion
   - Affective state
   - Source: Raphe Nuclei

References:
- Dayan & Yu (2006): Phasic norepinephrine: A neural interrupt signal
- Schultz et al. (1997): A neural substrate of prediction and reward
- Hasselmo & Sarter (2011): Modes and models of forebrain cholinergic modulation
- Doya (2002): Metalearning and neuromodulation
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import torch
import torch.nn as nn

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


@dataclass
class NeuromodulatorState:
    """Current state of all neuromodulator channels."""

    # Channel levels (all in [0, 1] normalized)
    dopamine: torch.Tensor  # [B] or [B, 7] per-colony
    norepinephrine: torch.Tensor
    acetylcholine: torch.Tensor
    serotonin: torch.Tensor

    # Derived modulation effects
    reward_sensitivity: float = 1.0  # From DA
    exploration_rate: float = 0.1  # From NE
    learning_rate_mod: float = 1.0  # From ACh
    discount_factor: float = 0.99  # From 5-HT

    # Diagnostic
    arousal: float = 0.5  # Overall arousal level
    valence: float = 0.0  # Positive/negative affect

    def to_dict(self) -> dict[str, Any]:
        return {
            "dopamine": self.dopamine.mean().item(),
            "norepinephrine": self.norepinephrine.mean().item(),
            "acetylcholine": self.acetylcholine.mean().item(),
            "serotonin": self.serotonin.mean().item(),
            "arousal": self.arousal,
            "valence": self.valence,
        }


class DopamineChannel(nn.Module):
    """Dopamine analog - Reward prediction and motivation.

    Computes reward prediction errors (RPE) and modulates:
    - Pragmatic value in EFE
    - Action selection gain
    - Memory consolidation priority
    """

    def __init__(
        self,
        input_dim: int = 8,  # E8 action dim
        hidden_dim: int = 32,
        baseline: float = 0.5,
    ):
        super().__init__()
        self.baseline = baseline

        # Value prediction network
        self.value_net = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.GELU(),
            nn.Linear(hidden_dim, 1),
        )

        # Tonic level (slow-changing motivation)
        self.register_buffer("tonic", torch.tensor(baseline))

    def forward(
        self,
        state: torch.Tensor,  # [B, D] current state
        reward: torch.Tensor | None = None,  # [B] actual reward
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """Compute dopamine signal.

        Args:
            state: Current state representation
            reward: Optional actual reward for RPE

        Returns:
            da_level: Dopamine level [B]
            rpe: Reward prediction error [B]
        """
        # Predict value
        predicted_value = self.value_net(state).squeeze(-1)

        # Compute RPE if reward provided
        if reward is not None:
            rpe = reward - predicted_value
        else:
            rpe = torch.zeros_like(predicted_value)

        # DA level = tonic + phasic (RPE)
        # Clamp to [0, 1] range
        da_level = torch.sigmoid(self.tonic + rpe)

        return da_level, rpe

    def update_tonic(self, reward_rate: float, lr: float = 0.01) -> None:
        """Update tonic DA based on recent reward rate."""
        with torch.no_grad():
            new_val = self.tonic * (1 - lr) + reward_rate * lr  # type: ignore[operator]
            self.tonic.copy_(
                new_val if isinstance(new_val, torch.Tensor) else torch.tensor(new_val)
            )  # type: ignore[operator]


class NorepinephrineChannel(nn.Module):
    """Norepinephrine analog - Arousal and exploration.

    Modulates gain and exploration-exploitation tradeoff based on:
    - Uncertainty in current state
    - Novelty of observations
    - Task demands
    """

    def __init__(
        self,
        input_dim: int = 8,
        hidden_dim: int = 32,
        baseline: float = 0.3,
    ):
        super().__init__()
        self.baseline = baseline

        # Uncertainty estimator
        self.uncertainty_net = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.GELU(),
            nn.Linear(hidden_dim, 1),
            nn.Sigmoid(),
        )

        # Tonic arousal level
        self.register_buffer("tonic", torch.tensor(baseline))

    def forward(
        self,
        state: torch.Tensor,  # [B, D]
        prediction_error: torch.Tensor | None = None,  # [B] surprise
    ) -> tuple[torch.Tensor, float]:
        """Compute norepinephrine signal.

        Args:
            state: Current state representation
            prediction_error: Optional prediction error (surprise)

        Returns:
            ne_level: NE level [B]
            exploration_rate: Exploration rate scalar
        """
        # Estimate uncertainty
        uncertainty = self.uncertainty_net(state).squeeze(-1)

        # Add surprise component
        if prediction_error is not None:
            surprise = torch.abs(prediction_error)
            phasic = uncertainty + 0.3 * torch.sigmoid(surprise)
        else:
            phasic = uncertainty

        # NE level = tonic + phasic
        ne_level = torch.sigmoid(self.tonic + phasic)

        # Exploration rate derived from NE
        # High NE → more exploration (less greedy)
        exploration_rate = ne_level.mean().item() * 0.5  # Max 0.5 exploration

        return ne_level, exploration_rate


class AcetylcholineChannel(nn.Module):
    """Acetylcholine analog - Attention and learning rate.

    Modulates:
    - Precision weighting in predictions
    - Learning rate for plasticity
    - Attention gain in bottom-up processing
    """

    def __init__(
        self,
        input_dim: int = 8,
        hidden_dim: int = 32,
        baseline: float = 0.5,
    ):
        super().__init__()
        self.baseline = baseline

        # Attention demand estimator
        self.attention_net = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.GELU(),
            nn.Linear(hidden_dim, 1),
            nn.Sigmoid(),
        )

        # Learning modulation (context-dependent)
        self.learning_net = nn.Sequential(
            nn.Linear(input_dim, 1),
            nn.Sigmoid(),
        )

        self.register_buffer("tonic", torch.tensor(baseline))

    def forward(
        self,
        state: torch.Tensor,  # [B, D]
        task_difficulty: torch.Tensor | None = None,  # [B]
    ) -> tuple[torch.Tensor, float]:
        """Compute acetylcholine signal.

        Args:
            state: Current state representation
            task_difficulty: Optional task difficulty signal

        Returns:
            ach_level: ACh level [B]
            learning_rate_mod: Learning rate modifier
        """
        # Estimate attention demand
        attention = self.attention_net(state).squeeze(-1)

        # Add task difficulty
        if task_difficulty is not None:
            phasic = attention + 0.3 * task_difficulty
        else:
            phasic = attention

        # ACh level
        ach_level = torch.sigmoid(self.tonic + phasic)

        # Learning rate modification
        # High ACh → higher learning rate (more plastic)
        # Future: use learned lr_raw = self.learning_net(state).squeeze(-1)
        learning_rate_mod = 0.5 + ach_level.mean().item()  # Range [0.5, 1.5]

        return ach_level, learning_rate_mod


class SerotoninChannel(nn.Module):
    """Serotonin analog - Patience and risk aversion.

    Modulates:
    - Temporal discount factor (patience)
    - Risk sensitivity
    - Affective state (valence)
    """

    def __init__(
        self,
        input_dim: int = 8,
        hidden_dim: int = 32,
        baseline: float = 0.5,
    ):
        super().__init__()
        self.baseline = baseline

        # Patience estimator
        self.patience_net = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.GELU(),
            nn.Linear(hidden_dim, 1),
            nn.Sigmoid(),
        )

        # Risk estimator
        self.risk_net = nn.Sequential(
            nn.Linear(input_dim, 1),
            nn.Tanh(),
        )

        self.register_buffer("tonic", torch.tensor(baseline))

    def forward(
        self,
        state: torch.Tensor,  # [B, D]
        recent_outcomes: torch.Tensor | None = None,  # [B] recent success/failure
    ) -> tuple[torch.Tensor, float, float]:
        """Compute serotonin signal.

        Args:
            state: Current state representation
            recent_outcomes: Optional recent outcome history

        Returns:
            serotonin_level: 5-HT level [B]
            discount_factor: Temporal discount factor
            risk_aversion: Risk aversion level
        """
        # Estimate patience
        patience = self.patience_net(state).squeeze(-1)

        # Adjust based on recent outcomes
        if recent_outcomes is not None:
            # Positive outcomes → more patience
            phasic = patience + 0.2 * recent_outcomes
        else:
            phasic = patience

        # 5-HT level
        ht_level = torch.sigmoid(self.tonic + phasic)

        # Discount factor: high 5-HT → more patient (higher discount)
        discount_factor = 0.9 + ht_level.mean().item() * 0.09  # Range [0.9, 0.99]

        # Risk aversion from risk net
        risk = self.risk_net(state).mean().item()
        risk_aversion = 0.5 + risk * 0.3  # Range [0.2, 0.8]

        return ht_level, discount_factor, risk_aversion


class NeuromodulatorSystem(nn.Module):
    """Unified neuromodulator system combining all four channels.

    This system modulates the entire processing pipeline:
    1. DA modulates pragmatic EFE weights
    2. NE modulates exploration rate
    3. ACh modulates precision/learning rate
    4. 5-HT modulates discount factor/risk

    The outputs are used to configure:
    - EFE calculator weights
    - Action selection temperature
    - Learning rates
    - Planning horizon
    """

    def __init__(
        self,
        input_dim: int = 8,
        hidden_dim: int = 64,
        per_colony: bool = False,  # Per-colony or global modulation
    ):
        super().__init__()
        self.input_dim = input_dim
        self.per_colony = per_colony

        # Four neuromodulator channels
        self.dopamine = DopamineChannel(input_dim, hidden_dim)
        self.norepinephrine = NorepinephrineChannel(input_dim, hidden_dim)
        self.acetylcholine = AcetylcholineChannel(input_dim, hidden_dim)
        self.serotonin = SerotoninChannel(input_dim, hidden_dim)

        # Cross-modulator interactions (they affect each other)
        self.interaction_net = nn.Sequential(
            nn.Linear(4, 16),
            nn.GELU(),
            nn.Linear(16, 4),
            nn.Sigmoid(),
        )

    def forward(
        self,
        state: torch.Tensor,  # [B, D] or [B, 7, D] if per_colony
        reward: torch.Tensor | None = None,
        prediction_error: torch.Tensor | None = None,
        task_difficulty: torch.Tensor | None = None,
        recent_outcomes: torch.Tensor | None = None,
    ) -> NeuromodulatorState:
        """Compute unified neuromodulator state.

        Args:
            state: Current state representation
            reward: Optional reward signal for DA
            prediction_error: Optional surprise for NE
            task_difficulty: Optional difficulty for ACh
            recent_outcomes: Optional outcome history for 5-HT

        Returns:
            NeuromodulatorState with all channel levels and derived effects
        """
        # Ensure batch dimension exists
        if state.dim() == 1:
            state = state.unsqueeze(0)  # [D] → [1, D]

        # Handle per-colony vs global
        if self.per_colony and state.dim() == 3:
            # [B, 7, D] → process each colony, average state for channels
            state_flat = state.mean(dim=1)  # [B, D]
        else:
            state_flat = state

        # Compute each channel
        da_level, rpe = self.dopamine(state_flat, reward)
        ne_level, exploration = self.norepinephrine(state_flat, prediction_error)
        ach_level, lr_mod = self.acetylcholine(state_flat, task_difficulty)
        ht_level, discount, _risk = self.serotonin(state_flat, recent_outcomes)

        # Cross-modulator interaction
        # Stack levels and compute interaction effects
        levels = torch.stack([da_level, ne_level, ach_level, ht_level], dim=-1)
        interaction = self.interaction_net(levels)

        # Apply interaction (multiplicative modulation)
        da_level = da_level * interaction[..., 0]
        ne_level = ne_level * interaction[..., 1]
        ach_level = ach_level * interaction[..., 2]
        ht_level = ht_level * interaction[..., 3]

        # Compute arousal (combination of DA and NE)
        arousal = (da_level.mean().item() + ne_level.mean().item()) / 2

        # Compute valence (DA positive, low 5-HT negative)
        valence = da_level.mean().item() - (1 - ht_level.mean().item()) * 0.5

        return NeuromodulatorState(
            dopamine=da_level,
            norepinephrine=ne_level,
            acetylcholine=ach_level,
            serotonin=ht_level,
            reward_sensitivity=1.0 + rpe.mean().item() * 0.5,
            exploration_rate=exploration,
            learning_rate_mod=lr_mod,
            discount_factor=discount,
            arousal=arousal,
            valence=valence,
        )

    def get_efe_weights(self, state: NeuromodulatorState) -> dict[str, float]:
        """Get EFE component weights from neuromodulator state.

        Returns weights for:
        - epistemic: Exploration/information gain (from NE + ACh)
        - pragmatic: Goal achievement (from DA)
        - safety: Risk aversion (from 5-HT)
        """
        return {
            "epistemic": state.exploration_rate * 2,  # NE drives exploration
            "pragmatic": state.reward_sensitivity,  # DA drives exploitation
            "safety": 1.0 + (1 - state.discount_factor) * 10,  # 5-HT → caution
        }

    def get_action_temperature(self, state: NeuromodulatorState) -> float:
        """Get action selection temperature from neuromodulator state.

        High NE → high temperature (more random)
        High DA → low temperature (more deterministic)
        """
        return 0.1 + state.exploration_rate * 2  # Range [0.1, 1.1]


def create_neuromodulator_system(
    input_dim: int = 8,
    hidden_dim: int = 64,
    per_colony: bool = False,
) -> NeuromodulatorSystem:
    """Factory function for neuromodulator system."""
    return NeuromodulatorSystem(
        input_dim=input_dim,
        hidden_dim=hidden_dim,
        per_colony=per_colony,
    )


__all__ = [
    "AcetylcholineChannel",
    "DopamineChannel",
    "NeuromodulatorState",
    "NeuromodulatorSystem",
    "NorepinephrineChannel",
    "SerotoninChannel",
    "create_neuromodulator_system",
]
