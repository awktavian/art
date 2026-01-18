"""Curiosity-Driven Exploration via Prediction Error.

Intrinsic Curiosity Module (ICM) - agents are curious about unpredictable outcomes.
Curiosity reward = prediction error on forward model.

Based on research:
- Pathak et al. (2017): "Curiosity-driven Exploration by Self-supervised Prediction"
- Burda et al. (2019): "Exploration by Random Network Distillation"

Created: November 2, 2025
Status: Production-ready
"""

from __future__ import annotations

import logging

import torch
import torch.nn as nn
import torch.nn.functional as F

logger = logging.getLogger(__name__)


class CuriosityModule(nn.Module):
    """Intrinsic Curiosity Module (ICM).

    Provides intrinsic reward based on prediction error:
    r_intrinsic = η * ||φ(s') - φ_pred(s')||^2

    Where:
    - φ(s') is feature encoding of next state
    - φ_pred(s') is predicted features from (s,a)
    - η is curiosity coefficient
    """

    def __init__(
        self,
        state_dim: int = 512,
        action_dim: int = 8,
        feature_dim: int = 256,
        hidden_dim: int = 256,
        curiosity_coef: float = 0.1,
        device: str = "cpu",
    ):
        """Initialize curiosity module.

        Args:
            state_dim: State embedding dimension
            action_dim: Number of discrete actions
            feature_dim: Feature space dimension
            hidden_dim: Hidden layer dimension
            curiosity_coef: Curiosity reward coefficient
            device: Computation device
        """
        super().__init__()
        self.state_dim = state_dim
        self.action_dim = action_dim
        self.feature_dim = feature_dim
        self.curiosity_coef = curiosity_coef
        self.device = device

        # Feature encoder: φ(s) - extracts features from states
        self.feature_encoder = nn.Sequential(
            nn.Linear(state_dim, hidden_dim), nn.ReLU(), nn.Linear(hidden_dim, feature_dim)
        ).to(device)

        # Forward model: predicts φ(s') from φ(s) and a
        self.forward_model = nn.Sequential(
            nn.Linear(feature_dim + action_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, feature_dim),
        ).to(device)

        # Inverse model: predicts a from φ(s) and φ(s')
        self.inverse_model = nn.Sequential(
            nn.Linear(feature_dim * 2, hidden_dim), nn.ReLU(), nn.Linear(hidden_dim, action_dim)
        ).to(device)

        logger.info(
            f"CuriosityModule initialized: "
            f"state_dim={state_dim}, feature_dim={feature_dim}, "
            f"curiosity_coef={curiosity_coef}"
        )

    def forward(
        self, state: torch.Tensor, action: torch.Tensor, next_state: torch.Tensor
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """Compute curiosity reward and prediction errors.

        Args:
            state: Current state [batch, state_dim]
            action: Actions taken [batch] (discrete indices)
            next_state: Next state [batch, state_dim]

        Returns:
            Tuple of (curiosity_reward, forward_loss, inverse_loss)
        """
        # Encode features
        features = self.feature_encoder(state)
        next_features = self.feature_encoder(next_state)

        # Forward model: predict next features
        actions_onehot = F.one_hot(action, num_classes=self.action_dim).float()
        features_action = torch.cat([features, actions_onehot], dim=-1)
        predicted_next_features = self.forward_model(features_action)

        # Curiosity reward = prediction error
        forward_loss = F.mse_loss(predicted_next_features, next_features, reduction="none")
        forward_loss_mean = forward_loss.mean(dim=-1)
        curiosity_reward = self.curiosity_coef * forward_loss_mean

        # Inverse model: predict action from features
        features_pair = torch.cat([features, next_features], dim=-1)
        action_logits = self.inverse_model(features_pair)
        inverse_loss = F.cross_entropy(action_logits, action, reduction="none")

        return curiosity_reward, forward_loss_mean, inverse_loss

    def compute_intrinsic_reward(
        self, state: torch.Tensor, action: torch.Tensor, next_state: torch.Tensor
    ) -> torch.Tensor:
        """Compute intrinsic curiosity reward.

        Args:
            state: Current state [batch, state_dim]
            action: Actions taken [batch]
            next_state: Next state [batch, state_dim]

        Returns:
            Intrinsic rewards [batch]
        """
        with torch.no_grad():
            curiosity_reward, _, _ = self.forward(state, action, next_state)
            return curiosity_reward

    def train_step(
        self,
        state: torch.Tensor,
        action: torch.Tensor,
        next_state: torch.Tensor,
        optimizer: torch.optim.Optimizer,
        forward_weight: float = 0.8,
        inverse_weight: float = 0.2,
    ) -> dict[str, float]:
        """Train curiosity module.

        Args:
            state: Current state [batch, state_dim]
            action: Actions taken [batch]
            next_state: Next state [batch, state_dim]
            optimizer: Optimizer
            forward_weight: Weight for forward model loss
            inverse_weight: Weight for inverse model loss

        Returns:
            Training losses
        """
        optimizer.zero_grad()

        _, forward_loss, inverse_loss = self.forward(state, action, next_state)

        # Combined loss
        total_loss = forward_weight * forward_loss.mean() + inverse_weight * inverse_loss.mean()
        total_loss.backward()
        optimizer.step()

        return {
            "forward_loss": forward_loss.mean().item(),
            "inverse_loss": inverse_loss.mean().item(),
            "total_loss": total_loss.item(),
        }


class RandomNetworkDistillation(nn.Module):
    """Random Network Distillation (RND) for exploration bonus.

    Uses prediction error on random network as novelty signal.
    Novel states are harder to predict → higher exploration bonus.

    Based on Burda et al. (2019).
    """

    def __init__(
        self,
        state_dim: int = 512,
        hidden_dim: int = 256,
        output_dim: int = 128,
        device: str = "cpu",
    ):
        """Initialize RND.

        Args:
            state_dim: State embedding dimension
            hidden_dim: Hidden layer dimension
            output_dim: Output dimension
            device: Computation device
        """
        super().__init__()
        self.device = device

        # Random target network (fixed, not trained)
        self.target_network = nn.Sequential(
            nn.Linear(state_dim, hidden_dim), nn.ReLU(), nn.Linear(hidden_dim, output_dim)
        ).to(device)

        # Predictor network (trained)
        self.predictor_network = nn.Sequential(
            nn.Linear(state_dim, hidden_dim), nn.ReLU(), nn.Linear(hidden_dim, output_dim)
        ).to(device)

        # Freeze target network
        for param in self.target_network.parameters():
            param.requires_grad = False

        logger.info(
            f"RandomNetworkDistillation initialized: state_dim={state_dim}, output_dim={output_dim}"
        )

    def forward(self, state: torch.Tensor) -> torch.Tensor:
        """Compute novelty bonus.

        Args:
            state: State embeddings [batch, state_dim]

        Returns:
            Novelty bonus [batch]
        """
        with torch.no_grad():
            target_features = self.target_network(state)

        predicted_features = self.predictor_network(state)

        # Prediction error = novelty
        novelty = F.mse_loss(predicted_features, target_features, reduction="none").mean(dim=-1)

        return novelty

    def train_step(self, state: torch.Tensor, optimizer: torch.optim.Optimizer) -> dict[str, float]:
        """Train predictor network.

        Args:
            state: State embeddings [batch, state_dim]
            optimizer: Optimizer

        Returns:
            Training loss
        """
        optimizer.zero_grad()

        with torch.no_grad():
            target_features = self.target_network(state)

        predicted_features = self.predictor_network(state)
        loss = F.mse_loss(predicted_features, target_features)

        loss.backward()
        optimizer.step()

        return {"rnd_loss": loss.item()}


def compute_curiosity_simple(prediction_error: float, curiosity_coef: float = 0.1) -> float:
    """Simple curiosity reward from prediction error.

    Args:
        prediction_error: Prediction error magnitude
        curiosity_coef: Curiosity coefficient

    Returns:
        Intrinsic curiosity reward
    """
    return curiosity_coef * prediction_error


__all__ = ["CuriosityModule", "RandomNetworkDistillation", "compute_curiosity_simple"]
