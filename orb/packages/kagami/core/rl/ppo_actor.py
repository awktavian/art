from __future__ import annotations

"""PPO (Proximal Policy Optimization) Actor.

Implementation of PPO from Schulman et al. 2017.
https://arxiv.org/abs/1707.06347

PPO is the industry-standard policy gradient algorithm, used by:
- OpenAI for GPT training (InstructGPT, ChatGPT)
- DeepMind for AlphaStar, MuZero
- Most modern RL research

Key Benefits vs REINFORCE:
- 2-5x more sample efficient
- Much more stable training
- Prevents destructive policy updates
- Easy to tune (fewer hyperparameters)

Algorithm:
  1. Collect trajectories with old policy π_old
  2. For K epochs:
      - Compute ratio r_t = π_new(a|s) / π_old(a|s)
      - Clip ratio to [1-ε, 1+ε] (prevents large updates)
      - Take gradient step on clipped objective
  3. Update π_old ← π_new
"""
import logging
import math
import random
import statistics
from typing import Any

import torch

from kagami.core.rl.actor_critic import Actor

logger = logging.getLogger(__name__)


class PPOActor(Actor):
    """
    PPO policy network with clipped objective.

    Learns optimal action selection through clipped policy gradient.
    Prevents destructive updates via ratio clipping.
    """

    def __init__(
        self,
        embedding_dim: int = 128,
        action_dim: int = 64,
        clip_epsilon: float = 0.2,
        ppo_epochs: int = 4,
        minibatch_size: int = 8,
        target_kl: float = 0.01,
        use_target_network: bool = True,
        target_update_freq: int = 100,
        target_tau: float = 0.005,
    ) -> None:
        """Initialize PPO actor with optional target network.

        Args:
            embedding_dim: Dimensionality of state embeddings
            action_dim: Dimensionality of action space
            clip_epsilon: PPO clipping parameter (0.2 typical)
            ppo_epochs: Number of optimization epochs per batch (4-10 typical)
            minibatch_size: Size of minibatches for updates
            target_kl: Target KL divergence for early stopping (0.01 typical)
            use_target_network: Enable target network for stability (TD3-style)
            target_update_freq: Steps between target updates (hard update)
            target_tau: Soft update coefficient (0.005 = 0.5% per update)
        """
        super().__init__(embedding_dim, action_dim)

        # PPO-specific hyperparameters
        self.clip_epsilon = clip_epsilon
        self.ppo_epochs = ppo_epochs
        self.minibatch_size = minibatch_size
        self.target_kl = target_kl

        # Old policy for computing ratio (π_new / π_old)
        self._old_policy_weights: dict[str, torch.Tensor] = {}

        # Target network (TD3-style delayed policy updates)
        self.use_target_network = use_target_network
        self.target_update_freq = target_update_freq
        self.target_tau = target_tau
        self._target_policy_weights: dict[str, torch.Tensor] = {}
        self._update_counter = 0

        # PPO statistics
        self._clip_fractions: list[float] = []
        self._kl_divergences: list[float] = []
        self._policy_losses: list[float] = []
        self._entropy_losses: list[float] = []

    def _copy_policy_to_old(self) -> None:
        """Copy current policy to old policy (for ratio computation)."""
        self._old_policy_weights = {
            state_hash: weights.clone() for state_hash, weights in self._policy_weights.items()
        }

    def _compute_log_prob(
        self, state_hash: str, action_idx: int, use_old_policy: bool = False
    ) -> float:
        """Compute log probability of action under policy.

        Args:
            state_hash: State identifier
            action_idx: Action index
            use_old_policy: Use old policy weights (for ratio)

        Returns:
            log π(a|s)
        """
        # Get policy weights
        if use_old_policy and state_hash in self._old_policy_weights:
            logits = self._old_policy_weights[state_hash]
        elif state_hash in self._policy_weights:
            logits = self._policy_weights[state_hash]
        else:
            # Initialize if not seen
            self._policy_weights[state_hash] = torch.randn(self.action_dim) * 0.01
            logits = self._policy_weights[state_hash]

        # Softmax probabilities
        probs = self._softmax(logits)

        # Log probability (clamp to avoid log(0))
        p = torch.clamp(probs[int(action_idx)], min=1e-10, max=1.0)
        log_prob = torch.log(p).item()

        return float(log_prob)

    def _compute_entropy(self, state_hash: str) -> float:
        """Compute policy entropy H(π(·|s)) for exploration bonus.

        Entropy bonus encourages exploration by penalizing
        overconfident (deterministic) policies.

        Args:
            state_hash: State identifier

        Returns:
            Entropy: -Σ π(a|s) log π(a|s)
        """
        if state_hash not in self._policy_weights:
            return 0.0

        logits = self._policy_weights[state_hash]
        probs = self._softmax(logits)

        # Entropy: -Σ p log p
        entropy = -torch.sum(probs * torch.log(torch.clamp(probs, min=1e-10, max=1.0))).item()

        return float(entropy)

    def _compute_kl_divergence(self, state_hash: str) -> float:
        """Compute KL divergence between new and old policy.

        KL(π_old || π_new) = Σ π_old(a|s) log(π_old(a|s) / π_new(a|s))

        Used for early stopping if policy changes too much.

        Args:
            state_hash: State identifier

        Returns:
            KL divergence
        """
        if state_hash not in self._policy_weights or state_hash not in self._old_policy_weights:
            return 0.0

        # Old and new probabilities
        old_probs = self._softmax(self._old_policy_weights[state_hash])
        new_probs = self._softmax(self._policy_weights[state_hash])

        # KL(old || new)
        kl = torch.sum(
            old_probs
            * (
                torch.log(torch.clamp(old_probs, min=1e-10, max=1.0))
                - torch.log(torch.clamp(new_probs, min=1e-10, max=1.0))
            )
        ).item()

        return float(kl)

    async def update(
        self,
        trajectory: list[Any],
        returns: list[float],
        advantages: list[float] | None = None,
    ) -> float:
        """
        Update policy using PPO clipped objective.

        PPO Objective:
          L^CLIP(θ) = E[min(r_t A_t, clip(r_t, 1-ε, 1+ε) A_t)]
          where r_t = π_θ(a|s) / π_θ_old(a|s)

        Args:
            trajectory: List of (state, action) predictions
            returns: Actual returns at each step
            advantages: GAE advantages (required for PPO)

        Returns:
            Average policy loss
        """
        if advantages is None:
            logger.warning("PPO requires GAE advantages; falling back to simple")
            return await super().update(trajectory, returns, advantages)

        # Copy current policy to old policy
        self._copy_policy_to_old()

        # Normalize advantages (standard in PPO)
        from kagami.core.rl.gae import normalize_advantages

        advantages = normalize_advantages(advantages)

        total_loss = 0.0
        clip_fractions = []
        kl_divergences = []
        entropy_values = []

        # PPO: Multiple epochs of optimization
        for epoch in range(self.ppo_epochs):
            epoch_loss = 0.0
            epoch_clips = 0
            epoch_samples = 0

            # Create minibatches (for better stability)
            indices = list(range(len(trajectory)))
            random.shuffle(indices)

            for start_idx in range(0, len(indices), self.minibatch_size):
                end_idx = min(start_idx + self.minibatch_size, len(indices))
                minibatch_indices = indices[start_idx:end_idx]

                minibatch_loss = 0.0

                for i in minibatch_indices:
                    if i >= len(returns) or i >= len(advantages):
                        continue

                    pred = trajectory[i]
                    state = pred.predicted_state if hasattr(pred, "predicted_state") else pred
                    state_hash = self._compute_state_hash(state)

                    # Get selected action index
                    if hasattr(pred, "selected_action_idx"):
                        selected_idx = pred.selected_action_idx
                    elif hasattr(pred, "action") and isinstance(pred.action, dict):
                        selected_idx = pred.action.get("_selected_action_idx", 0)
                    else:
                        selected_idx = 0

                    # Compute ratio: r_t = π_new(a|s) / π_old(a|s)
                    log_prob_new = self._compute_log_prob(state_hash, selected_idx, False)
                    log_prob_old = self._compute_log_prob(state_hash, selected_idx, True)

                    ratio = math.exp(log_prob_new - log_prob_old)

                    # Advantage
                    advantage = advantages[i]

                    # PPO clipped objective
                    unclipped_obj = ratio * advantage
                    clipped_ratio = max(
                        1.0 - self.clip_epsilon, min(1.0 + self.clip_epsilon, ratio)
                    )
                    clipped_obj = clipped_ratio * advantage

                    # Take minimum (pessimistic bound)
                    surrogate_loss = -min(unclipped_obj, clipped_obj)

                    # Entropy bonus (encourages exploration)
                    entropy = self._compute_entropy(state_hash)
                    entropy_loss = -0.01 * entropy  # Small coefficient

                    # Total loss
                    loss = surrogate_loss + entropy_loss

                    # Track clipping
                    was_clipped = abs(ratio - 1.0) > self.clip_epsilon
                    if was_clipped:
                        epoch_clips += 1
                    epoch_samples += 1

                    # Gradient (for this sample)
                    # Compute policy gradient at current policy
                    logits = self._policy_weights.get(state_hash)
                    if logits is None:
                        logits = torch.randn(self.action_dim) * 0.01
                        self._policy_weights[state_hash] = logits
                    probs = self._softmax(logits)

                    # PPO gradient (score function * clipped advantage)
                    gradient = -probs.clone()
                    gradient[int(selected_idx)] += 1.0

                    # Scale by clipped advantage
                    clipped_advantage = float(advantage) * clipped_ratio
                    gradient = gradient * clipped_advantage

                    # Apply gradient with Adam
                    await self._apply_gradient_adam(state_hash, gradient)

                    minibatch_loss += float(loss)
                    entropy_values.append(entropy)

                epoch_loss += minibatch_loss

            # Compute KL divergence (for early stopping)
            kl_values = []
            for i in range(len(trajectory)):
                pred = trajectory[i]
                state = pred.predicted_state if hasattr(pred, "predicted_state") else pred
                state_hash = self._compute_state_hash(state)
                kl = self._compute_kl_divergence(state_hash)
                kl_values.append(kl)

            mean_kl = statistics.mean(kl_values) if kl_values else 0.0
            kl_divergences.append(mean_kl)

            # Early stopping if KL too large (policy changed too much)
            if mean_kl > 1.5 * self.target_kl:
                logger.debug(
                    f"Early stopping at epoch {epoch + 1}/{self.ppo_epochs} "
                    f"(KL={mean_kl:.4f} > target={self.target_kl:.4f})"
                )
                break

            # Track metrics
            clip_fraction = epoch_clips / max(epoch_samples, 1)
            clip_fractions.append(clip_fraction)

            total_loss += epoch_loss

        # Average metrics
        avg_loss = total_loss / (len(trajectory) * self.ppo_epochs)
        avg_clip_fraction = statistics.mean(clip_fractions) if clip_fractions else 0.0
        avg_kl = statistics.mean(kl_divergences) if kl_divergences else 0.0
        avg_entropy = statistics.mean(entropy_values) if entropy_values else 0.0

        # Store for statistics
        self._policy_losses.append(avg_loss)
        self._clip_fractions.append(avg_clip_fraction)
        self._kl_divergences.append(avg_kl)
        self._entropy_losses.append(avg_entropy)

        # Keep recent history
        if len(self._policy_losses) > 100:
            self._policy_losses = self._policy_losses[-100:]
            self._clip_fractions = self._clip_fractions[-100:]
            self._kl_divergences = self._kl_divergences[-100:]
            self._entropy_losses = self._entropy_losses[-100:]

        # Update target network (if enabled)
        if self.use_target_network:
            self._update_counter += 1

            if self._update_counter >= self.target_update_freq:
                self._sync_target_network()
                self._update_counter = 0

        logger.debug(
            f"PPO updated: loss={avg_loss:.4f}, clip_frac={avg_clip_fraction:.3f}, "
            f"kl={avg_kl:.4f}, entropy={avg_entropy:.3f}"
        )

        # Emit metrics
        try:
            from kagami_observability.metrics import (
                kagami_ppo_clip_fraction,
                kagami_ppo_kl_divergence,
                kagami_ppo_policy_loss,
            )

            kagami_ppo_clip_fraction.observe(avg_clip_fraction)  # Dynamic attr
            kagami_ppo_kl_divergence.observe(avg_kl)  # Dynamic attr
            kagami_ppo_policy_loss.observe(avg_loss)  # Dynamic attr
        except Exception:
            pass  # Metrics optional

        return avg_loss

    def _sync_target_network(self, soft_update: bool = False) -> None:
        """Synchronize target network with current policy.

        Args:
            soft_update: Use soft update (Polyak averaging) vs hard update
        """
        if soft_update:
            # Soft update: θ_target = τ*θ + (1-τ)*θ_target
            for state_hash, weights in self._policy_weights.items():
                if state_hash in self._target_policy_weights:
                    self._target_policy_weights[state_hash] = (
                        self.target_tau * weights
                        + (1 - self.target_tau) * self._target_policy_weights[state_hash]
                    )
                else:
                    self._target_policy_weights[state_hash] = weights.clone()
        else:
            # Hard update: θ_target = θ
            self._target_policy_weights = {
                state_hash: weights.clone() for state_hash, weights in self._policy_weights.items()
            }

        logger.debug(f"🎯 Synced actor target network ({len(self._target_policy_weights)} states)")

        # Emit metric
        try:
            from kagami_observability.metrics import (
                kagami_rl_target_network_syncs_total,
            )

            kagami_rl_target_network_syncs_total.inc()
        except Exception:
            pass

    def get_target_policy_prob(self, state_hash: str, action_idx: int) -> float:
        """Get action probability from target network.

        Args:
            state_hash: State identifier
            action_idx: Action index

        Returns:
            π_target(a|s)
        """
        if state_hash not in self._target_policy_weights:
            # Initialize if not seen
            return 1.0 / self.action_dim  # Uniform

        logits = self._target_policy_weights[state_hash]
        probs = self._softmax(logits)

        return float(probs[action_idx])

    def get_stats(self) -> dict[str, Any]:
        """Get PPO-specific statistics.

        Returns:
            Statistics dict[str, Any]
        """
        if not self._policy_losses:
            return {
                "clip_epsilon": self.clip_epsilon,
                "ppo_epochs": self.ppo_epochs,
                "target_kl": self.target_kl,
            }

        return {
            "clip_epsilon": self.clip_epsilon,
            "ppo_epochs": self.ppo_epochs,
            "target_kl": self.target_kl,
            "avg_policy_loss": float(statistics.mean(self._policy_losses)),
            "avg_clip_fraction": float(statistics.mean(self._clip_fractions)),
            "avg_kl_divergence": float(statistics.mean(self._kl_divergences)),
            "avg_entropy": float(statistics.mean(self._entropy_losses)),
        }


# Global singleton
_ppo_actor: PPOActor | None = None


def get_ppo_actor() -> PPOActor:
    """Get or create global PPO actor."""
    global _ppo_actor
    if _ppo_actor is None:
        _ppo_actor = PPOActor()
        logger.info("✅ PPO actor initialized (ε=0.2, epochs=4)")
    return _ppo_actor
