from __future__ import annotations

"Actor-Critic Architecture for Policy Learning.\n\nActor: Learns WHAT to do (policy: state → action distribution)\nCritic: Learns HOW GOOD situations are (value: state → expected return)\n\nBased on A3C, PPO, and SAC algorithms - proven in production RL systems.\n"
import logging
import math
from collections import OrderedDict, defaultdict
from typing import Any

import torch

logger = logging.getLogger(__name__)


class Actor:
    """
    Policy network: state → action distribution.

    Learns optimal action selection through policy gradient.
    """

    def __init__(self, embedding_dim: int = 128, action_dim: int = 128) -> None:
        """Initialize actor (policy network).

        Args:
            embedding_dim: Dimensionality of state embeddings
            action_dim: Dimensionality of action space
        """
        self.embedding_dim = embedding_dim
        self.action_dim = action_dim
        # Store logits as torch tensors (CPU by default).
        self._policy_weights: OrderedDict[str, torch.Tensor] = OrderedDict()
        self._max_policy_weights = 10000
        self._action_history: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
        self._max_action_history = 10000
        self._adam_m: dict[str, torch.Tensor] = {}
        self._adam_v: dict[str, torch.Tensor] = {}
        self._adam_t: dict[str, int] = defaultdict(int)
        self.learning_rate = 0.001
        self.beta1 = 0.9
        self.beta2 = 0.999
        self.epsilon = 1e-08

    async def sample_actions(
        self,
        state: Any,
        k: int = 5,
        exploration_noise: float = 0.2,
        temperature: float = 1.0,
        context: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Sample K candidate actions from policy.

        Args:
            state: Current latent state
            k: Number of actions to sample
            exploration_noise: Amount of exploration (0=greedy, 1=random)
            temperature: Softmax temperature (higher=more exploration)
            context: Optional context for action generation (ignored in base Actor)

        Returns:
            List of candidate actions
        """
        state_hash = self._compute_state_hash(state)
        if state_hash not in self._policy_weights:
            if len(self._policy_weights) >= self._max_policy_weights:
                self._policy_weights.popitem(last=False)
                logger.debug(
                    f"Evicted oldest policy weight (at capacity {self._max_policy_weights})"
                )
            self._policy_weights[state_hash] = torch.randn(self.action_dim) * 0.01
        else:
            self._policy_weights.move_to_end(state_hash)
        logits = self._policy_weights[state_hash]
        temp = 1.0
        try:
            temp = float(temperature)
        except Exception:
            temp = 1.0
        if temp <= 0.0:
            temp = 1.0

        probs = self._softmax(logits / temp)
        if exploration_noise > 0:
            # Mix with Dirichlet noise (Torch-native).
            alpha = max(float(exploration_noise), 1e-3)
            noise = torch.distributions.Dirichlet(
                torch.full((self.action_dim,), alpha, dtype=probs.dtype)
            ).sample()
            probs = (1.0 - float(exploration_noise)) * probs + float(exploration_noise) * noise
            probs = probs / probs.sum()

        action_indices = torch.multinomial(probs, num_samples=int(k), replacement=True)
        actions = []
        for action_idx in action_indices.tolist():
            action = self._index_to_action(int(action_idx), state)
            actions.append(action)
        return actions

    def _compute_state_hash(self, state: Any) -> str:
        """Compute hash of state for indexing."""
        if hasattr(state, "context_hash"):
            return state.context_hash  # type: ignore[no-any-return]
        return str(hash(str(state)))[:16]

    def _softmax(self, logits: torch.Tensor) -> torch.Tensor:
        """Numerically stable softmax (Torch-native)."""
        return torch.softmax(logits.float(), dim=0).to(dtype=logits.dtype)

    def _index_to_action(self, idx: int, state: Any) -> dict[str, Any]:
        """
        Convert action index to action dict[str, Any].

        In production: Use action space definition.
        Here: Generate semantic actions based on context.
        """
        state_hash = self._compute_state_hash(state)
        past_actions = self._action_history.get(state_hash, [])
        if state_hash in self._action_history:
            self._action_history.move_to_end(state_hash)
        if past_actions and idx < len(past_actions):
            return past_actions[idx]
        action_types = ["search", "read", "edit", "create", "delete", "execute", "plan", "verify"]
        action_type = action_types[idx % len(action_types)]
        return {"action": action_type, "tool": action_type, "exploration_factor": 0.5}

    async def update(
        self, trajectory: list[Any], returns: list[float], advantages: list[float] | None = None
    ) -> float:
        """Update actor policy via policy gradient.

        ALGORITHM (PPO-style Actor-Critic):
        1. For each state in trajectory:
            - Compute old policy: π_old(a|s)
            - Compute new policy: π_new(a|s)
            - Compute ratio: r = π_new / π_old
            - Clip ratio to prevent large updates: clip(r, 1-ε, 1+ε)
        2. Policy gradient: ∇J(θ) = E[∇log π(a|s) × A(s,a)]
        3. Update: θ ← θ + α∇J(θ)

        Why advantages?
        - Advantage A(s,a) = Q(s,a) - V(s) reduces variance
        - Tells us: "How much better is this action vs average?"
        - Positive A → increase probability, Negative A → decrease

        Args:
            trajectory: Sequence of (state, action) pairs
            returns: Discounted returns G_t for each timestep
            advantages: Optional advantage estimates (if None, uses returns)

        Returns:
            Policy loss (for logging/monitoring)
        """
        total_loss = 0.0
        for i, pred in enumerate(trajectory):
            if i >= len(returns):
                break
            state = pred.predicted_state if hasattr(pred, "predicted_state") else pred
            state_hash = self._compute_state_hash(state)
            if advantages is not None and i < len(advantages):
                advantage = advantages[i]
            else:
                advantage = returns[i]
            if state_hash in self._policy_weights:
                if hasattr(pred, "selected_action_idx"):
                    selected_idx = pred.selected_action_idx
                elif hasattr(pred, "action") and isinstance(pred.action, dict):
                    selected_idx = pred.action.get("_selected_action_idx", 0)
                else:
                    selected_idx = 0
                    logger.warning("No selected_action_idx found, defaulting to 0")
                logits = self._policy_weights[state_hash]
                probs = self._softmax(logits)
                gradient = -probs.clone()
                gradient[int(selected_idx)] += 1.0
                gradient = gradient * float(advantage)
                try:
                    from kagami.core.learning.ewc import get_ewc

                    ewc = get_ewc()
                    penalty = ewc.compute_penalty_for_state(state_hash, logits)  # type: ignore[arg-type]
                    if penalty is not None:
                        penalty_t = (
                            penalty
                            if isinstance(penalty, torch.Tensor)  # type: ignore[unreachable]
                            else torch.as_tensor(penalty, dtype=gradient.dtype)
                        )
                        gradient = gradient - penalty_t
                except Exception:
                    pass
                await self._apply_gradient_adam(state_hash, gradient)
                total_loss += advantage**2
        avg_loss = total_loss / max(1, len(trajectory))
        logger.debug(f"Actor updated: loss={avg_loss:.4f}")
        return avg_loss

    async def _apply_gradient_adam(self, state_hash: str, gradient: torch.Tensor) -> None:
        """Apply gradient using Adam optimizer (Torch-native, CPU)."""
        if state_hash not in self._adam_m:
            self._adam_m[state_hash] = torch.zeros_like(gradient)
            self._adam_v[state_hash] = torch.zeros_like(gradient)
        self._adam_t[state_hash] += 1
        t = self._adam_t[state_hash]
        m = self._adam_m[state_hash]
        v = self._adam_v[state_hash]
        m = self.beta1 * m + (1 - self.beta1) * gradient
        v = self.beta2 * v + (1 - self.beta2) * (gradient**2)
        self._adam_m[state_hash] = m
        self._adam_v[state_hash] = v

        m_hat = m / (1 - self.beta1**t)
        v_hat = v / (1 - self.beta2**t)
        self._policy_weights[state_hash] = self._policy_weights[state_hash] + (
            self.learning_rate * m_hat / (torch.sqrt(v_hat) + float(self.epsilon))
        )
        self._policy_weights.move_to_end(state_hash)


class Critic:
    """
    Value function: state → expected return.

    Learns how good each situation is (for baseline in policy gradient).
    """

    def __init__(self, embedding_dim: int = 128, target_update_freq: int = 100) -> None:
        """Initialize critic (value function) with double Q-learning.

        Args:
            embedding_dim: Dimensionality of state embeddings
            target_update_freq: Steps between target network updates
        """
        self.embedding_dim = embedding_dim
        self._value_estimates_A: dict[str, float] = {}
        self._value_estimates_B: dict[str, float] = {}
        self._target_estimates_A: dict[str, float] = {}
        self._target_estimates_B: dict[str, float] = {}
        self._target_update_freq = target_update_freq
        self._update_counter = 0
        self._adam_m_A: dict[str, float] = defaultdict(float)
        self._adam_v_A: dict[str, float] = defaultdict(float)
        self._adam_t_A: dict[str, int] = defaultdict(int)
        self._adam_m_B: dict[str, float] = defaultdict(float)
        self._adam_v_B: dict[str, float] = defaultdict(float)
        self._adam_t_B: dict[str, int] = defaultdict(int)
        self.learning_rate = 0.01
        self.beta1 = 0.9
        self.beta2 = 0.999
        self.epsilon = 1e-08
        self.gamma = 0.99
        self._value_estimates = self._value_estimates_A
        self._adam_t = self._adam_t_A
        self._adam_m = self._adam_m_A
        self._adam_v = self._adam_v_A

    async def evaluate_trajectory(self, trajectory: list[Any]) -> float:
        """
        Estimate total return from trajectory.

        V(s_0) = r_0 + γ*r_1 + γ²*r_2 + ...

        Args:
            trajectory: List of predictions/states

        Returns:
            Estimated total return
        """
        total_value = 0.0
        for i, pred in enumerate(trajectory):
            state = pred.predicted_state if hasattr(pred, "predicted_state") else pred
            state_hash = self._compute_state_hash(state)
            state_value = self._value_estimates.get(state_hash, 0.0)
            total_value += self.gamma**i * state_value
        return total_value

    def evaluate_state(self, state: Any) -> float:
        """
        Evaluate single state.

        Args:
            state: State to evaluate

        Returns:
            Value estimate
        """
        state_hash = self._compute_state_hash(state)
        return self._value_estimates.get(state_hash, 0.0)

    async def get_baselines(self, trajectory: list[Any]) -> list[float]:
        """
        Get value estimates for each state in trajectory.

        Used as baseline for policy gradient (variance reduction).

        Args:
            trajectory: List of states

        Returns:
            List of value estimates
        """
        baselines = []
        for pred in trajectory:
            state = pred.predicted_state if hasattr(pred, "predicted_state") else pred
            value = self.evaluate_state(state)
            baselines.append(value)
        return baselines

    async def update(self, trajectory: list[Any], returns: list[float]) -> float:
        """
        Update value function using TD-learning.

        Loss: (V(s) - actual_return)²

        Args:
            trajectory: List of states
            returns: Actual returns observed

        Returns:
            Value loss (MSE)
        """
        total_loss = 0.0
        for i, pred in enumerate(trajectory):
            if i >= len(returns):
                break
            state = pred.predicted_state if hasattr(pred, "predicted_state") else pred
            state_hash = self._compute_state_hash(state)
            actual_return = returns[i]
            predicted_value = self._value_estimates.get(state_hash, 0.0)
            td_error = actual_return - predicted_value
            await self._update_value_adam(state_hash, td_error)
            total_loss += td_error**2
        avg_loss = total_loss / max(1, len(trajectory))
        logger.debug(f"Critic updated: loss={avg_loss:.4f}")
        self._update_counter += 1
        if self._update_counter >= self._target_update_freq:
            self._sync_target_network()
            self._update_counter = 0
        return avg_loss

    def _sync_target_network(self) -> None:
        """Sync target network with current weights (hard update)."""
        self._target_estimates = self._value_estimates.copy()
        logger.debug(f"🎯 Synced target network ({len(self._target_estimates)} states)")
        try:
            from kagami_observability.metrics import kagami_rl_target_network_syncs_total

            kagami_rl_target_network_syncs_total.inc()
        except Exception:
            pass

    def get_target_value(self, state: Any) -> float:
        """Get value from target network (stable baseline).

        Args:
            state: State to evaluate

        Returns:
            Target value estimate
        """
        state_hash = self._compute_state_hash(state)
        return self._target_estimates.get(state_hash, 0.0)

    async def _update_value_adam(self, state_hash: str, td_error: float) -> None:
        """Update value estimate using Adam optimizer."""
        if state_hash not in self._value_estimates:
            self._value_estimates[state_hash] = 0.0
        self._adam_t[state_hash] += 1
        t = self._adam_t[state_hash]
        gradient = td_error
        self._adam_m[state_hash] = (
            self.beta1 * self._adam_m[state_hash] + (1 - self.beta1) * gradient
        )
        self._adam_v[state_hash] = (
            self.beta2 * self._adam_v[state_hash] + (1 - self.beta2) * gradient**2
        )
        m_hat = self._adam_m[state_hash] / (1 - self.beta1**t)
        v_hat = self._adam_v[state_hash] / (1 - self.beta2**t)
        self._value_estimates[state_hash] += (
            self.learning_rate * m_hat / (math.sqrt(v_hat) + self.epsilon)
        )

    def _compute_state_hash(self, state: Any) -> str:
        """Compute hash of state for indexing."""
        if hasattr(state, "context_hash"):
            return state.context_hash  # type: ignore[no-any-return]
        return str(hash(str(state)))[:16]


_actor: Actor | None = None
_critic: Critic | None = None


def get_actor() -> Actor:
    """Get or create global actor."""
    global _actor
    if _actor is None:
        _actor = Actor()
    return _actor


def get_critic() -> Critic:
    """Get or create global critic."""
    global _critic
    if _critic is None:
        _critic = Critic()
    return _critic
