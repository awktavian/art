"""Agent Empowerment - Intrinsic Motivation via Mutual Information.

Empowerment: E(s) = I(A; S'|S) - mutual information between actions and future states.
Agents maximize their ability to influence the future.

NOTE: For multi-step empowerment (E_n with horizon n), use MultiStepEmpowerment from
kagami.core.intrinsic.multi_step_empowerment. This module provides single-step (n=1)
empowerment which is simpler and faster for basic use cases.

Based on research:
- Klyubin et al. (2005): "Empowerment: A Universal Agent-Centric Measure of Control"
- Mohamed & Jimenez Rezende (2015): "Variational Information Maximisation for Intrinsically Motivated RL"
- Gregor et al. (2016): "Variational Intrinsic Control"

Created: November 2, 2025
Updated: November 29, 2025 - Added note about multi_step_empowerment.py
Status: Production-ready (single-step empowerment)
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

logger = logging.getLogger(__name__)


class EmpowermentEstimator(nn.Module):
    """Estimate empowerment E(s) = I(A; S'|S) using variational lower bound.

    Uses a variational approach to estimate mutual information:
    I(A; S'|S) ≈ H(A) - H(A|S')

    Where:
    - H(A) is entropy of action distribution (uniform assumption)
    - H(A|S') is conditional entropy estimated by inverse model q(a|s,s')
    """

    def __init__(
        self, state_dim: int = 512, action_dim: int = 8, hidden_dim: int = 256, device: str = "cpu"
    ):
        """Initialize empowerment estimator.

        Args:
            state_dim: Dimension of state embeddings
            action_dim: Number of discrete actions
            hidden_dim: Hidden layer dimension
            device: Computation device
        """
        super().__init__()
        self.state_dim = state_dim
        self.action_dim = action_dim
        self.device = device

        # Inverse model: q(a|s,s') - predicts action from state transition
        self.inverse_model = nn.Sequential(
            nn.Linear(state_dim * 2, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, action_dim),
        ).to(device)

        # Forward model: p(s'|s,a) - predicts next state from state and action
        self.forward_model = nn.Sequential(
            nn.Linear(state_dim + action_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, state_dim),
        ).to(device)

        logger.info(
            f"EmpowermentEstimator initialized: state_dim={state_dim}, action_dim={action_dim}"
        )

    def forward(self, state: torch.Tensor, next_state: torch.Tensor) -> torch.Tensor:
        """Compute empowerment E(s) = I(A; S'|S).

        Args:
            state: Current state embeddings [batch, state_dim]
            next_state: Next state embeddings [batch, state_dim]

        Returns:
            Empowerment values [batch]
        """
        # Concatenate states
        state_pair = torch.cat([state, next_state], dim=-1)

        # Inverse model predicts action distribution
        action_logits = self.inverse_model(state_pair)
        action_probs = F.softmax(action_logits, dim=-1)

        # Conditional entropy H(A|S,S')
        conditional_entropy = -torch.sum(action_probs * torch.log(action_probs + 1e-8), dim=-1)

        # Prior entropy H(A) assuming uniform distribution
        prior_entropy = np.log(self.action_dim)

        # Empowerment = H(A) - H(A|S,S')
        empowerment = prior_entropy - conditional_entropy

        return empowerment

    def compute_empowerment_batch(
        self, states: torch.Tensor, next_states: torch.Tensor
    ) -> torch.Tensor:
        """Compute empowerment for batch of transitions.

        Args:
            states: State embeddings [batch, state_dim]
            next_states: Next state embeddings [batch, state_dim]

        Returns:
            Empowerment values [batch]
        """
        return self.forward(states, next_states)

    def train_models(
        self,
        states: torch.Tensor,
        actions: torch.Tensor,
        next_states: torch.Tensor,
        optimizer: torch.optim.Optimizer,
    ) -> dict[str, float]:
        """Train inverse and forward models.

        Args:
            states: State embeddings [batch, state_dim]
            actions: Actions taken [batch] (discrete indices)
            next_states: Next state embeddings [batch, state_dim]
            optimizer: Optimizer for both models

        Returns:
            Training losses
        """
        optimizer.zero_grad()

        # Inverse model loss: predict action from (s, s')
        state_pair = torch.cat([states, next_states], dim=-1)
        action_logits = self.inverse_model(state_pair)
        inverse_loss = F.cross_entropy(action_logits, actions)

        # Forward model loss: predict s' from (s, a)
        actions_onehot = F.one_hot(actions, num_classes=self.action_dim).float()
        state_action = torch.cat([states, actions_onehot], dim=-1)
        next_state_pred = self.forward_model(state_action)
        forward_loss = F.mse_loss(next_state_pred, next_states)

        # Combined loss
        total_loss = inverse_loss + forward_loss
        total_loss.backward()
        optimizer.step()

        return {
            "inverse_loss": inverse_loss.item(),
            "forward_loss": forward_loss.item(),
            "total_loss": total_loss.item(),
        }


class EmpowermentReward:
    """Compute intrinsic rewards based on empowerment.

    Agents receive bonus reward for actions that increase their future control.
    """

    def __init__(
        self, estimator: EmpowermentEstimator, intrinsic_weight: float = 0.1, normalize: bool = True
    ):
        """Initialize empowerment reward.

        Args:
            estimator: Empowerment estimator
            intrinsic_weight: Weight for intrinsic reward (relative to extrinsic)
            normalize: Whether to normalize empowerment values
        """
        self.estimator = estimator
        self.intrinsic_weight = intrinsic_weight
        self.normalize = normalize

        # Running statistics for normalization
        self.empowerment_mean = 0.0
        self.empowerment_std = 1.0
        self.update_count = 0

        logger.info(
            f"EmpowermentReward initialized: "
            f"intrinsic_weight={intrinsic_weight}, normalize={normalize}"
        )

    def compute_reward(
        self, state: torch.Tensor, next_state: torch.Tensor, extrinsic_reward: float
    ) -> tuple[float, float, float]:
        """Compute combined reward = extrinsic + intrinsic.

        Args:
            state: Current state embedding
            next_state: Next state embedding
            extrinsic_reward: External reward from environment

        Returns:
            Tuple of (total_reward, extrinsic_reward, intrinsic_reward)
        """
        with torch.no_grad():
            # Compute empowerment
            empowerment = self.estimator(state.unsqueeze(0), next_state.unsqueeze(0)).item()

            # Normalize if enabled
            if self.normalize:
                empowerment = (empowerment - self.empowerment_mean) / (self.empowerment_std + 1e-8)

                # Update running statistics
                self.update_count += 1
                alpha = 1.0 / self.update_count if self.update_count < 100 else 0.01
                self.empowerment_mean += alpha * (empowerment - self.empowerment_mean)
                self.empowerment_std += alpha * (
                    abs(empowerment - self.empowerment_mean) - self.empowerment_std
                )

            # Compute intrinsic reward
            intrinsic_reward = self.intrinsic_weight * empowerment

            # Combined reward
            total_reward = extrinsic_reward + intrinsic_reward

            return total_reward, extrinsic_reward, intrinsic_reward

    def get_statistics(self) -> dict[str, Any]:
        """Get empowerment statistics.

        Returns:
            Dictionary of statistics
        """
        return {
            "empowerment_mean": self.empowerment_mean,
            "empowerment_std": self.empowerment_std,
            "update_count": self.update_count,
            "intrinsic_weight": self.intrinsic_weight,
        }


def compute_empowerment_simple(
    state_embedding: torch.Tensor, next_state_embedding: torch.Tensor, action_space_size: int = 8
) -> float:
    """Simplified empowerment estimate without training inverse model.

    Uses state change magnitude as proxy for empowerment.
    High state change = high empowerment (agent can affect environment).

    Args:
        state_embedding: Current state [state_dim]
        next_state_embedding: Next state [state_dim]
        action_space_size: Number of possible actions

    Returns:
        Empowerment estimate (higher = more control)
    """
    # State change magnitude
    state_change = torch.norm(next_state_embedding - state_embedding).item()

    # Normalize by action space size (more actions = higher potential empowerment)
    empowerment = state_change * np.log(action_space_size)

    return float(empowerment)


__all__ = ["EmpowermentEstimator", "EmpowermentReward", "compute_empowerment_simple"]
