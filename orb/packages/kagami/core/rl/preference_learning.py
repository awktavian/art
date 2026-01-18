from __future__ import annotations

"""RLHF/Preference Learning for K os.

Implements reward modeling from human feedback and preference-based training
to align agent behavior with human values.

Key components:
- PreferenceDataset: stores human preference comparisons
- RewardModel: learned scalar reward from state-action pairs
- RLHFTrainer: updates reward model from preferences and trains policy
"""
import logging
from dataclasses import dataclass
from typing import Any, cast

import numpy as np
import torch
import torch.nn as nn
from kagami_observability import metrics

logger = logging.getLogger(__name__)

# Metrics
_RLHF_COMPARISONS_TOTAL = metrics.Counter(
    "kagami_rlhf_comparisons_total",
    "Total preference comparisons collected",
)
_RLHF_REWARD_LOSS = metrics.Histogram(
    "kagami_rlhf_reward_model_loss",
    "Reward model training loss",
)
_RLHF_POLICY_UPDATES_TOTAL = metrics.Counter(
    "kagami_rlhf_policy_updates_total",
    "Total policy updates from RLHF",
)


@dataclass
class PreferenceComparison:
    """A single human preference: trajectory_a > trajectory_b."""

    state: Any
    action_preferred: dict[str, Any]
    action_rejected: dict[str, Any]
    context: dict[str, Any]
    timestamp: float
    confidence: float = 1.0  # Human confidence in this judgment


class PreferenceDataset:
    """Store and manage human preference comparisons."""

    def __init__(self, capacity: int = 10000) -> None:
        self.capacity = capacity
        self.comparisons: list[PreferenceComparison] = []

    def add(self, comparison: PreferenceComparison) -> None:
        """Add preference comparison to dataset."""
        if len(self.comparisons) >= self.capacity:
            # Remove oldest
            self.comparisons.pop(0)
        self.comparisons.append(comparison)
        _RLHF_COMPARISONS_TOTAL.inc()

    def sample_batch(self, batch_size: int) -> list[PreferenceComparison]:
        """Sample random batch of comparisons."""
        if len(self.comparisons) == 0:
            return []
        indices = np.random.choice(
            len(self.comparisons), size=min(batch_size, len(self.comparisons)), replace=False
        )
        return [self.comparisons[i] for i in indices]

    def get_stats(self) -> dict[str, Any]:
        """Get dataset statistics."""
        return {
            "size": len(self.comparisons),
            "capacity": self.capacity,
            "utilization": len(self.comparisons) / self.capacity if self.capacity > 0 else 0,
        }


class RewardModel(nn.Module):
    """Learned reward function from preferences.

    Maps (state, action) → scalar reward aligned with human values.
    """

    def __init__(self, state_dim: int = 128, action_dim: int = 128, hidden_dim: int = 256) -> None:
        super().__init__()
        self.state_dim = state_dim
        self.action_dim = action_dim

        # Simple MLP reward function
        self.net = nn.Sequential(
            nn.Linear(state_dim + action_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, 1),  # Scalar reward
        )

    def forward(self, state: torch.Tensor, action: torch.Tensor) -> torch.Tensor:
        """Compute reward for (state, action) pair.

        Args:
            state: State tensor [B, state_dim]
            action: Action tensor [B, action_dim]

        Returns:
            Reward tensor [B]
        """
        x = torch.cat([state, action], dim=-1)
        r = self.net(x).squeeze(-1)
        return cast(torch.Tensor, r)


class RLHFTrainer:
    """Trainer for reward model and policy using human preferences."""

    def __init__(
        self,
        reward_model: RewardModel,
        dataset: PreferenceDataset,
        learning_rate: float = 3e-4,
    ) -> None:
        self.reward_model = reward_model
        self.dataset = dataset
        self.optimizer = torch.optim.Adam(reward_model.parameters(), lr=learning_rate)
        self.train_steps = 0

    def _encode_state_action(
        self, state: Any, action: dict[str, Any]
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """Encode state and action to tensors using world model.

        HARDENED (Dec 22, 2025): Uses real world model encoding.
        """
        from kagami.core.world_model.service import get_world_model_service

        world_model = get_world_model_service()
        if world_model is None:
            raise RuntimeError("World model required for preference encoding")

        # Encode state via world model
        if isinstance(state, torch.Tensor):
            state_tensor = state
        elif isinstance(state, dict):
            # Extract observation from state dict[str, Any]
            obs = state.get("observation", state.get("obs"))
            if obs is None:
                raise ValueError("State dict[str, Any] must contain 'observation' or 'obs' key")
            state_tensor = (
                torch.tensor(obs, dtype=torch.float32) if not isinstance(obs, torch.Tensor) else obs
            )
        else:
            state_tensor = (
                torch.tensor(state, dtype=torch.float32)
                if not isinstance(state, torch.Tensor)
                else state
            )

        # Ensure batch dimension
        if state_tensor.ndim == 1:
            state_tensor = state_tensor.unsqueeze(0)

        # Encode via world model's encoder
        with torch.no_grad():
            encoded_state = world_model.encode_observation(state_tensor)  # type: ignore[attr-defined]

        # Pad/truncate to match reward model dimensions
        if encoded_state.shape[-1] < self.reward_model.state_dim:
            padding = torch.zeros(
                encoded_state.shape[0], self.reward_model.state_dim - encoded_state.shape[-1]
            )
            encoded_state = torch.cat([encoded_state, padding], dim=-1)
        elif encoded_state.shape[-1] > self.reward_model.state_dim:
            encoded_state = encoded_state[:, : self.reward_model.state_dim]

        # Encode action as one-hot or embedding
        action_str = str(action.get("action", action.get("type", "")))
        action_tensor = torch.zeros(1, self.reward_model.action_dim)
        # Use hash-based embedding for action (deterministic)
        import hashlib

        action_hash = int(hashlib.sha256(action_str.encode()).hexdigest(), 16)
        action_idx = action_hash % self.reward_model.action_dim
        action_tensor[0, action_idx] = 1.0

        return encoded_state, action_tensor

    def train_step(self, batch_size: int = 32) -> dict[str, Any]:
        """Train reward model from preference batch.

        Loss: Bradley-Terry model: P(a > b) = σ(r(s,a) - r(s,b))
        Maximize log P(preferred > rejected).
        """
        batch = self.dataset.sample_batch(batch_size)
        if not batch:
            return {"status": "no_data", "loss": 0.0}

        losses = []

        for comp in batch:
            # Encode preferred and rejected (state, action) pairs
            s_pref, a_pref = self._encode_state_action(comp.state, comp.action_preferred)
            s_rej, a_rej = self._encode_state_action(comp.state, comp.action_rejected)

            # Compute rewards
            r_pref = self.reward_model(s_pref, a_pref)
            r_rej = self.reward_model(s_rej, a_rej)

            # Bradley-Terry loss: -log σ(r_pref - r_rej)
            logit = r_pref - r_rej
            loss = -torch.nn.functional.logsigmoid(logit).mean()
            losses.append(loss)

        if not losses:
            return {"status": "no_data", "loss": 0.0}

        total_loss = torch.stack(losses).mean()

        self.optimizer.zero_grad()
        total_loss.backward()
        self.optimizer.step()

        self.train_steps += 1

        _RLHF_REWARD_LOSS.observe(float(total_loss.item()))

        return {
            "loss": float(total_loss.item()),
            "batch_size": len(batch),
            "train_steps": self.train_steps,
        }

    def get_reward(self, state: Any, action: dict[str, Any]) -> float:
        """Get learned reward for (state, action)."""
        with torch.no_grad():
            s, a = self._encode_state_action(state, action)
            r = self.reward_model(s, a)
            return float(r.item())


# Global instance
_preference_dataset: PreferenceDataset | None = None
_reward_model: RewardModel | None = None
_rlhf_trainer: RLHFTrainer | None = None


def get_preference_dataset() -> PreferenceDataset:
    """Get global preference dataset."""
    global _preference_dataset
    if _preference_dataset is None:
        _preference_dataset = PreferenceDataset()
    return _preference_dataset


def get_reward_model() -> RewardModel:
    """Get global reward model."""
    global _reward_model
    if _reward_model is None:
        _reward_model = RewardModel()
    return _reward_model


def get_rlhf_trainer() -> RLHFTrainer:
    """Get global RLHF trainer."""
    global _rlhf_trainer
    if _rlhf_trainer is None:
        _rlhf_trainer = RLHFTrainer(
            reward_model=get_reward_model(),
            dataset=get_preference_dataset(),
        )
    return _rlhf_trainer


async def record_preference(
    state: Any,
    action_preferred: dict[str, Any],
    action_rejected: dict[str, Any],
    context: dict[str, Any],
    confidence: float = 1.0,
) -> dict[str, Any]:
    """Record a human preference comparison.

    Args:
        state: State where comparison was made
        action_preferred: Action that was preferred
        action_rejected: Action that was rejected
        context: Additional context
        confidence: Human confidence (0-1)

    Returns:
        Status dict[str, Any]
    """
    import time

    dataset = get_preference_dataset()
    comparison = PreferenceComparison(
        state=state,
        action_preferred=action_preferred,
        action_rejected=action_rejected,
        context=context,
        timestamp=time.time(),
        confidence=confidence,
    )
    dataset.add(comparison)

    return {
        "status": "recorded",
        "dataset_size": len(dataset.comparisons),
    }
