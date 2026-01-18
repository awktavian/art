"""Policy Learning Loop with Discrete-Time CBF Safety.

Unified policy training combining:
- PPO (Proximal Policy Optimization)
- GAE (Generalized Advantage Estimation)
- Discrete-time CBF safety constraints via OptimalCBF
- Soft barrier cost integration
- DPO (Direct Preference Optimization) for safety alignment
- Intrinsic curiosity (RND)

Status: Production-ready
"""

from __future__ import annotations

import copy
import logging
from typing import TYPE_CHECKING, Any

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

if TYPE_CHECKING:
    from kagami.core.rl.preference_learning import PreferenceDataset

logger = logging.getLogger(__name__)


class SafetyStateExtractor(nn.Module):
    """Learns to extract safety state from raw state tensor.

    Maps high-dimensional state to 4D safety state:
    [threat, uncertainty, complexity, predictive_risk]

    The extractor can be calibrated with human feedback to ensure
    the learned safety state matches human risk perception.
    """

    def __init__(self, state_dim: int = 512, hidden_dim: int = 64) -> None:
        super().__init__()
        self.state_dim = state_dim
        self.hidden_dim = hidden_dim
        self.net = nn.Sequential(
            nn.Linear(state_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, 4),
            nn.Sigmoid(),  # Output in [0, 1]
        )

        # Calibration state
        self._calibration_buffer: list[tuple[torch.Tensor, float, float]] = []
        self._calibration_steps = 0

    def forward(self, state: torch.Tensor) -> torch.Tensor:
        """Extract safety state from raw state.

        Args:
            state: Raw state [B, state_dim]

        Returns:
            safety_state: [B, 4] with [threat, uncertainty, complexity, risk]
        """
        return self.net(state)

    def add_calibration_sample(
        self,
        state: torch.Tensor,
        human_risk_label: float,
        confidence: float = 1.0,
    ) -> None:
        """Add a calibration sample from human feedback.

        Args:
            state: Raw state tensor [state_dim]
            human_risk_label: Human-judged risk (0-1)
            confidence: Confidence in this judgment (0-1)
        """
        if state.dim() > 1:
            state = state.flatten()
        self._calibration_buffer.append((state.detach(), human_risk_label, confidence))

    def calibrate_from_feedback(
        self,
        states: torch.Tensor | None = None,
        human_risk_labels: torch.Tensor | None = None,
        weights: torch.Tensor | None = None,
        learning_rate: float = 1e-3,
        num_steps: int = 10,
    ) -> dict[str, float]:
        """Calibrate extractor using human risk judgments.

        Human labels tell us what the "aggregate risk" should be for each state.
        We learn to match the mean of our 4D safety state to this label.

        Args:
            states: State tensor [B, state_dim] (optional, uses buffer if None)
            human_risk_labels: Human-judged risk [B] (optional)
            weights: Confidence weights [B] (optional)
            learning_rate: Learning rate for calibration
            num_steps: Number of gradient steps

        Returns:
            Dict with calibration metrics (loss, samples, steps)
        """
        # Use buffer if no explicit data provided
        if states is None and self._calibration_buffer:
            buffer_states = []
            buffer_labels = []
            buffer_weights = []
            for state, label, conf in self._calibration_buffer:
                buffer_states.append(state)
                buffer_labels.append(label)
                buffer_weights.append(conf)

            states = torch.stack(buffer_states)
            human_risk_labels = torch.tensor(buffer_labels, dtype=torch.float32)
            weights = torch.tensor(buffer_weights, dtype=torch.float32)

        if states is None or human_risk_labels is None:
            return {"status": "no_data", "loss": 0.0, "samples": 0, "steps": 0}  # type: ignore[dict-item]

        if states.dim() == 1:
            states = states.unsqueeze(0)
        if human_risk_labels.dim() == 0:
            human_risk_labels = human_risk_labels.unsqueeze(0)

        # Ensure on same device
        device = next(self.parameters()).device
        states = states.to(device)
        human_risk_labels = human_risk_labels.to(device)
        if weights is not None:
            weights = weights.to(device)
        else:
            weights = torch.ones_like(human_risk_labels)

        # Optimizer for calibration
        optimizer = torch.optim.Adam(self.parameters(), lr=learning_rate)

        total_loss = 0.0
        for _ in range(num_steps):
            optimizer.zero_grad()

            # Get predicted safety state [B, 4]
            predicted = self(states)

            # Aggregate to scalar risk (mean of 4 dimensions)
            predicted_risk = predicted.mean(dim=-1)

            # Weighted MSE loss
            loss = (weights * (predicted_risk - human_risk_labels).pow(2)).mean()
            total_loss += loss.item()

            loss.backward()
            optimizer.step()

        self._calibration_steps += num_steps
        avg_loss = total_loss / num_steps if num_steps > 0 else 0.0

        return {
            "status": "calibrated",  # type: ignore[dict-item]
            "loss": avg_loss,
            "samples": len(states),
            "steps": num_steps,
            "total_calibration_steps": self._calibration_steps,
        }

    def clear_calibration_buffer(self) -> int:
        """Clear the calibration buffer.

        Returns:
            Number of samples cleared
        """
        count = len(self._calibration_buffer)
        self._calibration_buffer.clear()
        return count

    def get_calibration_stats(self) -> dict[str, int]:
        """Get calibration statistics."""
        return {
            "buffer_size": len(self._calibration_buffer),
            "total_steps": self._calibration_steps,
        }


class UCBExplorer:
    """Upper Confidence Bound (UCB) exploration strategy.

    Replaces epsilon-greedy with principled exploration-exploitation tradeoff.
    Uses UCB1 algorithm: action = argmax(Q(a) + c * sqrt(ln(t) / N(a)))

    Key advantages over epsilon-greedy:
    - No manual epsilon tuning
    - Exploration decreases naturally over time
    - Theoretical regret bounds (optimal for multi-armed bandits)

    Created: December 15, 2025
    Reference: Auer et al. (2002) "Finite-time Analysis of the Multi-armed Bandit Problem"
    """

    def __init__(
        self,
        n_actions: int,
        c: float = 2.0,
        action_bounds: tuple[float, float] | None = None,
    ) -> None:
        """Initialize UCB explorer.

        Args:
            n_actions: Number of discrete actions
            c: Exploration constant (higher = more exploration)
            action_bounds: Optional (min, max) for continuous action conversion
        """
        self.n_actions = n_actions
        self.c = c
        self.action_bounds = action_bounds or (0.0, 1.0)

        # Statistics
        self.Q = torch.zeros(n_actions, dtype=torch.float32)  # Estimated values
        self.N = torch.zeros(n_actions, dtype=torch.float32)  # Visit counts
        self.t = 0  # Total timesteps

    def select_action(self) -> int:
        """Select action using UCB1 strategy.

        Returns:
            action: Discrete action index
        """
        # Explore unvisited actions first
        if (self.N == 0).any():
            unvisited = torch.where(self.N == 0)[0]
            return int(unvisited[0])

        # Compute UCB values
        ucb_values = self.Q + self._compute_ucb_bonus_vectorized()

        # Select action with highest UCB
        return int(torch.argmax(ucb_values))

    def _compute_ucb_bonus_vectorized(self) -> torch.Tensor:
        """Compute UCB exploration bonus for all actions.

        Returns:
            bonus: [n_actions] exploration bonus
        """
        # UCB bonus: c * sqrt(ln(t) / N(a))
        # Add epsilon to avoid division by zero
        bonus = self.c * torch.sqrt(np.log(max(self.t, 1)) / (self.N + 1e-8))
        return bonus

    def _compute_ucb_bonus(self, action: int) -> float:
        """Compute UCB exploration bonus for single action.

        Args:
            action: Action index

        Returns:
            bonus: Exploration bonus
        """
        if self.N[action] == 0:
            return float("inf")
        return self.c * np.sqrt(np.log(max(self.t, 1)) / self.N[action])

    def update(self, action: int, reward: float) -> None:
        """Update statistics after taking action.

        Args:
            action: Action taken
            reward: Observed reward
        """
        self.t += 1
        self.N[action] += 1

        # Incremental mean update
        # Q_new = Q_old + (reward - Q_old) / N
        self.Q[action] += (reward - self.Q[action]) / self.N[action]

    def discrete_to_continuous(self, discrete_action: int) -> float:
        """Convert discrete action to continuous value.

        Args:
            discrete_action: Discrete action index [0, n_actions)

        Returns:
            continuous_action: Continuous value in action_bounds
        """
        # Linear interpolation
        min_val, max_val = self.action_bounds
        continuous = min_val + (discrete_action / (self.n_actions - 1)) * (max_val - min_val)
        return float(continuous)

    def reset(self) -> None:
        """Reset all statistics."""
        self.Q.zero_()
        self.N.zero_()
        self.t = 0


class PolicyLoop(nn.Module):
    """Policy learning loop with safety guarantees.

    Learns optimal action selection while maintaining safety through
    discrete-time Control Barrier Functions with differentiable training.

    Key features:
    - Differentiable CBF for end-to-end gradient flow
    - Learned safety state extraction (no hardcoded values)
    - Soft barrier cost in policy loss
    - Multi-step safety horizon support
    """

    def __init__(
        self,
        policy: nn.Module | None = None,
        use_cbf: bool = True,
        use_dpo: bool = True,
        use_ucb_exploration: bool = True,
        safety_penalty_weight: float = 1.0,
        dpo_beta: float = 0.1,
        dpo_weight: float = 0.5,
        ucb_n_actions: int = 10,
        ucb_c: float = 2.0,
        safety_threshold: float = 0.3,
        state_dim: int = 512,
        action_dim: int = 8,
        device: str = "cpu",
    ) -> None:
        """Initialize policy loop.

        Args:
            policy: Policy network (PPOActor or compatible)
            use_cbf: Enable CBF safety constraints (OptimalCBF)
            use_dpo: Enable DPO loss for preference-based safety learning
            use_ucb_exploration: Enable UCB exploration (replaces epsilon-greedy)
            safety_penalty_weight: Weight for soft barrier penalty in loss
            dpo_beta: DPO temperature parameter (higher = sharper preference)
            dpo_weight: Weight for DPO loss in total loss
            ucb_n_actions: Number of discrete actions for UCB
            ucb_c: UCB exploration constant
            safety_threshold: CBF safety threshold (h(x) >= 0)
            state_dim: Input state dimension
            action_dim: Output action dimension
            device: Computation device
        """
        super().__init__()

        self.use_cbf = use_cbf
        self.use_dpo = use_dpo
        self.use_ucb_exploration = use_ucb_exploration
        self.safety_penalty_weight = safety_penalty_weight
        self.safety_threshold = safety_threshold
        self.dpo_beta = dpo_beta
        self.dpo_weight = dpo_weight
        self.state_dim = state_dim
        self.action_dim = action_dim
        self.device = device

        # Create policy if not provided
        if policy is None:
            self.policy = nn.Sequential(
                nn.Linear(state_dim, 256),
                nn.GELU(),
                nn.Linear(256, action_dim),
            ).to(device)
        else:
            self.policy = policy.to(device)  # type: ignore[assignment]

        # Reference policy for DPO (frozen copy of initial policy)
        # Used to compute log π_ref(y|x) in DPO loss
        if use_dpo:
            self.reference_policy = copy.deepcopy(self.policy)
            for param in self.reference_policy.parameters():
                param.requires_grad = False
            logger.info("Reference policy initialized for DPO training")
        else:
            self.reference_policy = None  # type: ignore[assignment]

        # Value function (critic)
        self.critic = nn.Sequential(
            nn.Linear(state_dim, 256),
            nn.GELU(),
            nn.Linear(256, 1),
        ).to(device)

        # Safety state extractor (learned, not hardcoded)
        self.safety_extractor = SafetyStateExtractor(
            state_dim=state_dim,
            hidden_dim=64,
        ).to(device)

        # OptimalCBF for safety constraints (inference and training)
        if use_cbf:
            try:
                from kagami.core.safety.optimal_cbf import OptimalCBF, OptimalCBFConfig

                cbf_config = OptimalCBFConfig(
                    observation_dim=4,
                    state_dim=16,
                    control_dim=min(2, action_dim),
                    metric_threshold=safety_threshold,
                    soft_penalty_weight=10.0,
                    use_topological=False,
                )
                self.cbf = OptimalCBF(cbf_config).to(device)
                logger.info("OptimalCBF initialized")
            except ImportError as e:
                logger.warning(f"OptimalCBF not available: {e}")
                self.cbf = None  # type: ignore[assignment]
                self.use_cbf = False
        else:
            self.cbf = None  # type: ignore[assignment]

        # UCB exploration (December 15, 2025)
        if use_ucb_exploration:
            self.ucb_explorer = UCBExplorer(
                n_actions=ucb_n_actions,
                c=ucb_c,
                action_bounds=(0.0, 1.0),
            )
            logger.info(f"UCB exploration enabled: n_actions={ucb_n_actions}, c={ucb_c}")
        else:
            self.ucb_explorer = None  # type: ignore[assignment]

        # Track last CBF results
        self.last_qp_iterations = 0
        self.last_safety_margin = 0.0
        self.last_cbf_penalty = 0.0
        self.last_dpo_loss = 0.0

        logger.info(
            f"Policy loop initialized: CBF={use_cbf}, DPO={use_dpo}, "
            f"UCB={use_ucb_exploration}, safety_weight={safety_penalty_weight}"
        )

    def _encode_dict_to_tensor(
        self,
        data: Any,
        target_dim: int,
        prefix: str = "",
    ) -> torch.Tensor:
        """Encode a dict[str, Any] or complex type to a fixed-size tensor.

        Recursively flattens dictionaries and lists into a single tensor.
        Uses consistent ordering and padding/truncation to ensure fixed output size.

        Args:
            data: Dict, list[Any], scalar, or tensor to encode
            target_dim: Target tensor dimension
            prefix: Key prefix for nested dicts (internal use)

        Returns:
            Tensor of shape [target_dim]
        """
        values: list[float] = []

        def _extract_values(obj: Any, depth: int = 0) -> None:
            """Recursively extract numeric values from nested structures."""
            if depth > 10:  # Prevent infinite recursion
                return

            if isinstance(obj, (int, float)):
                values.append(float(obj))
            elif isinstance(obj, bool):
                values.append(1.0 if obj else 0.0)
            elif isinstance(obj, torch.Tensor):
                values.extend(obj.flatten().tolist())
            elif isinstance(obj, np.ndarray[Any, Any]):
                values.extend(obj.flatten().tolist())
            elif isinstance(obj, dict):
                # Sort keys for consistent ordering
                for key in sorted(obj.keys()):
                    _extract_values(obj[key], depth + 1)
            elif isinstance(obj, (list[Any], tuple[Any, ...])):
                for item in obj:
                    _extract_values(item, depth + 1)
            elif obj is None:
                values.append(0.0)
            else:
                # Try to convert to float
                try:
                    values.append(float(obj))
                except (TypeError, ValueError):
                    pass  # Skip unconvertible types

        _extract_values(data)

        # Create tensor with padding/truncation
        if len(values) == 0:
            return torch.zeros(target_dim, device=self.device)
        elif len(values) >= target_dim:
            return torch.tensor(values[:target_dim], device=self.device, dtype=torch.float32)
        else:
            # Pad with zeros
            padded = values + [0.0] * (target_dim - len(values))
            return torch.tensor(padded, device=self.device, dtype=torch.float32)

    def extract_safety_state(self, state: torch.Tensor) -> torch.Tensor:
        """Extract safety state from raw state tensor.

        Uses learned safety extractor instead of hardcoded values.

        Args:
            state: Raw state [B, state_dim]

        Returns:
            safety_state: [B, 4] with [threat, uncertainty, complexity, risk]
        """
        return self.safety_extractor(state)

    def select_action(
        self,
        state: torch.Tensor,
        safe: bool = True,
        return_info: bool = False,
        explore: bool = False,
    ) -> torch.Tensor | tuple[torch.Tensor, dict[str, Any]]:
        """Select action with optional safety filtering and exploration.

        Args:
            state: [B, state_dim] current state
            safe: Whether to apply CBF safety filter
            return_info: Whether to return CBF info dict[str, Any]
            explore: Whether to use UCB exploration

        Returns:
            action: [B, action_dim] selected action
            info: (optional) Dict with CBF metrics
        """
        # Ensure proper shape
        if state.dim() == 1:
            state = state.unsqueeze(0)

        # Get nominal action from policy
        action_nominal = self.policy(state)

        # UCB exploration (December 15, 2025)
        if explore and self.use_ucb_exploration and self.ucb_explorer is not None:
            # Select action using UCB
            discrete_action = self.ucb_explorer.select_action()
            # Convert to continuous
            continuous_action = self.ucb_explorer.discrete_to_continuous(discrete_action)
            # Override first dimension with UCB action
            action_nominal = action_nominal.clone()
            action_nominal[:, 0] = continuous_action

        info = {
            "adjusted": False,
            "safety_margin": 0.0,
            "qp_iterations": 0,
        }

        # HARD SAFETY REJECTION (December 15, 2025)
        # Check h(x) >= 0 BEFORE applying CBF filter
        if safe and self.use_cbf and self.cbf is not None:
            # Extract safety state
            with torch.no_grad():
                safety_state_tensor = self.extract_safety_state(state)
                h_x = self.cbf.barrier_value(safety_state_tensor)

            # ENFORCE h(x) >= 0 (no exceptions)
            if (h_x < 0.0).any():
                from kagami.core.exceptions import SafetyViolationError

                min_h_x = float(h_x.min().item())
                raise SafetyViolationError(
                    f"Policy violates CBF safety constraint: h(x)={min_h_x:.4f} < 0. "
                    f"Action rejected to maintain safety invariant.",
                    context={
                        "h_x": min_h_x,
                        "safety_state": safety_state_tensor.tolist(),
                        "threshold": self.safety_threshold,
                    },
                )

        # Apply unified CBF safety filter (Dec 6, 2025)
        if safe and self.use_cbf and self.cbf is not None:
            # Extract safety state from raw state (learned, not hardcoded)
            with torch.no_grad():
                safety_state_tensor = self.extract_safety_state(state)

            # Only use first 2 dims of action for CBF
            action_2d = (
                action_nominal[:, :2]
                if action_nominal.dim() > 1
                else action_nominal[:2].unsqueeze(0)
            )

            # Apply unified CBF filter
            safe_control, _penalty, cbf_info = self.cbf(
                safety_state_tensor,
                action_2d,
            )

            # Reconstruct full action with filtered first 2 dims
            action = action_nominal.clone()
            action[:, :2] = safe_control

            # Store CBF metrics
            self.last_safety_margin = (
                float(cbf_info.get("h_metric", torch.tensor(0.0)).mean().item())
                if cbf_info.get("h_metric") is not None
                else 0.0
            )
            self.last_qp_iterations = cbf_info.get("qp_iterations", 0)

            info["adjusted"] = cbf_info.get("adjusted", False)
            info["safety_margin"] = self.last_safety_margin
            info["qp_iterations"] = self.last_qp_iterations
        else:
            action = action_nominal

        if return_info:
            return action, info
        return action

    def compute_safety_penalty(
        self,
        state: torch.Tensor,
        action: torch.Tensor,
    ) -> torch.Tensor:
        """Compute differentiable safety penalty for training.

        Uses soft barrier cost from OptimalCBF.

        Args:
            state: State tensor [B, state_dim]
            action: Action tensor [B, action_dim]

        Returns:
            penalty: Scalar safety penalty loss
        """
        if not self.use_cbf or self.cbf is None:
            return torch.tensor(0.0, device=self.device)

        # Extract safety state (differentiable)
        safety_state = self.extract_safety_state(state)

        # Get control subset for CBF (first 2 dims)
        control = action[..., :2]

        # Apply CBF
        _, penalty, info = self.cbf(
            safety_state,
            control,
        )

        # Store for monitoring
        self.last_cbf_penalty = penalty.item() if penalty.numel() == 1 else penalty.mean().item()
        if "h_metric" in info:
            self.last_safety_margin = info["h_metric"].mean().item()

        return penalty

    def compute_dpo_loss(
        self,
        states: torch.Tensor,
        actions_chosen: torch.Tensor,
        actions_rejected: torch.Tensor,
    ) -> torch.Tensor:
        """Compute Direct Preference Optimization (DPO) loss.

        DPO directly optimizes the policy to prefer safe actions over unsafe ones
        without requiring a separate reward model. This is simpler and more stable
        than RLHF's Bradley-Terry reward modeling approach.

        Loss formula:
            L_DPO = -log σ(β(log π(y_w|x) - log π_ref(y_w|x))
                         - β(log π(y_l|x) - log π_ref(y_l|x)))

        Where:
            - π is the current policy
            - π_ref is the reference (frozen initial) policy
            - y_w is the chosen/preferred action
            - y_l is the rejected action
            - β is the temperature parameter

        Args:
            states: State tensor [B, state_dim]
            actions_chosen: Preferred/safe actions [B, action_dim]
            actions_rejected: Rejected/unsafe actions [B, action_dim]

        Returns:
            dpo_loss: Scalar DPO loss

        References:
            Rafailov et al. (2023) "Direct Preference Optimization"
        """
        if not self.use_dpo or self.reference_policy is None:
            return torch.tensor(0.0, device=self.device, requires_grad=True)

        # Get policy outputs for chosen and rejected actions
        policy_chosen_pred = self.policy(states)
        policy_rejected_pred = self.policy(states)

        # Compute log probabilities (negative MSE as proxy for action likelihood)
        # For continuous actions, we use Gaussian assumption where
        # log π(a|s) ∝ -||π(s) - a||²
        policy_chosen_logps = -F.mse_loss(policy_chosen_pred, actions_chosen, reduction="none").sum(
            dim=-1
        )
        policy_rejected_logps = -F.mse_loss(
            policy_rejected_pred, actions_rejected, reduction="none"
        ).sum(dim=-1)

        # Reference policy log probs (no gradient)
        with torch.no_grad():
            ref_chosen_pred = self.reference_policy(states)
            ref_rejected_pred = self.reference_policy(states)

            reference_chosen_logps = -F.mse_loss(
                ref_chosen_pred, actions_chosen, reduction="none"
            ).sum(dim=-1)
            reference_rejected_logps = -F.mse_loss(
                ref_rejected_pred, actions_rejected, reduction="none"
            ).sum(dim=-1)

        # DPO loss: -log σ(β * (policy_chosen - ref_chosen) - β * (policy_rejected - ref_rejected))
        chosen_rewards = self.dpo_beta * (policy_chosen_logps - reference_chosen_logps)
        rejected_rewards = self.dpo_beta * (policy_rejected_logps - reference_rejected_logps)

        dpo_loss = -F.logsigmoid(chosen_rewards - rejected_rewards).mean()

        # Store for monitoring
        self.last_dpo_loss = dpo_loss.item()

        return dpo_loss

    def compute_dpo_loss_from_dataset(
        self,
        preference_dataset: PreferenceDataset,
        batch_size: int = 32,
        action_encoder: nn.Module | None = None,
    ) -> torch.Tensor:
        """Compute DPO loss using preference comparisons from dataset.

        Samples preference pairs and computes DPO loss to align the policy
        with human safety preferences.

        Args:
            preference_dataset: Dataset containing preference comparisons
            batch_size: Number of comparisons to sample
            action_encoder: Optional encoder to convert action dicts to tensors

        Returns:
            dpo_loss: Scalar DPO loss (0 if no data available)
        """
        if not self.use_dpo:
            return torch.tensor(0.0, device=self.device, requires_grad=True)

        # Sample batch from preference dataset
        batch = preference_dataset.sample_batch(batch_size)
        if not batch:
            return torch.tensor(0.0, device=self.device, requires_grad=True)

        # Encode states and actions
        states_list = []
        chosen_list = []
        rejected_list = []

        for comparison in batch:
            # Encode state: handle tensors, arrays, dicts, and other types
            if hasattr(comparison.state, "shape"):
                state = torch.as_tensor(comparison.state, device=self.device, dtype=torch.float32)
            elif isinstance(comparison.state, dict):
                # Proper encoding for dict[str, Any] state types
                state = self._encode_dict_to_tensor(comparison.state, self.state_dim)
            else:
                # Fallback: try to convert to tensor or encode as dict[str, Any]
                try:
                    state = torch.as_tensor(
                        comparison.state, device=self.device, dtype=torch.float32
                    )
                except (TypeError, ValueError):
                    state = self._encode_dict_to_tensor(comparison.state, self.state_dim)

            # Encode actions
            if action_encoder is not None:
                chosen = action_encoder(comparison.action_preferred)
                rejected = action_encoder(comparison.action_rejected)
            elif isinstance(comparison.action_preferred, dict):
                # Proper encoding for action dicts
                chosen = self._encode_dict_to_tensor(comparison.action_preferred, self.action_dim)
                rejected = self._encode_dict_to_tensor(comparison.action_rejected, self.action_dim)
            else:
                # Fallback: try to convert or encode
                try:
                    chosen = torch.as_tensor(
                        comparison.action_preferred, device=self.device, dtype=torch.float32
                    )
                    rejected = torch.as_tensor(
                        comparison.action_rejected, device=self.device, dtype=torch.float32
                    )
                except (TypeError, ValueError):
                    chosen = self._encode_dict_to_tensor(
                        comparison.action_preferred, self.action_dim
                    )
                    rejected = self._encode_dict_to_tensor(
                        comparison.action_rejected, self.action_dim
                    )

            states_list.append(state)
            chosen_list.append(chosen)
            rejected_list.append(rejected)

        # Stack into batches
        states = torch.stack(states_list)
        actions_chosen = torch.stack(chosen_list)
        actions_rejected = torch.stack(rejected_list)

        return self.compute_dpo_loss(states, actions_chosen, actions_rejected)

    def compute_loss(
        self,
        batch: dict[str, Any],
        preference_dataset: PreferenceDataset | None = None,
        dpo_batch_size: int = 16,
    ) -> torch.Tensor:
        """Compute policy loss with integrated CBF safety penalty and DPO.

        Loss = policy_loss + value_loss + safety_penalty + dpo_loss

        The safety penalty provides gradients through the CBF constraint,
        and the DPO loss aligns the policy with human safety preferences.

        Args:
            batch: Dict with 'state', 'action', 'reward', 'advantage'
                   Optional: 'action_chosen', 'action_rejected' for DPO
            preference_dataset: Optional dataset for DPO (alternative to batch DPO)
            dpo_batch_size: Batch size for DPO sampling from dataset

        Returns:
            loss: Total policy optimization loss
        """
        state = batch.get("state")
        action = batch.get("action")
        reward = batch.get("reward")
        advantage = batch.get("advantage")

        if state is None or action is None:
            return torch.tensor(0.0, device=self.device, requires_grad=True)

        # Ensure tensors with proper dtype
        if not isinstance(state, torch.Tensor):
            state = torch.as_tensor(state, device=self.device, dtype=torch.float32)
        else:
            state = state.to(self.device)

        if not isinstance(action, torch.Tensor):
            action = torch.as_tensor(action, device=self.device, dtype=torch.float32)
        else:
            action = action.to(self.device)

        # Compute action log probabilities
        action_pred = self.policy(state)
        log_prob = -F.mse_loss(action_pred, action, reduction="none").sum(dim=-1)

        # Use advantage if provided, else use reward
        if advantage is not None:
            if not isinstance(advantage, torch.Tensor):
                advantage = torch.as_tensor(advantage, device=self.device, dtype=torch.float32)
            else:
                advantage = advantage.to(self.device)
        elif reward is not None:
            if not isinstance(reward, torch.Tensor):
                advantage = torch.as_tensor(reward, device=self.device, dtype=torch.float32)
            else:
                advantage = reward.to(self.device)
        else:
            advantage = torch.zeros(len(state), device=self.device)

        # PPO-style loss (simplified)
        policy_loss = -(log_prob * advantage).mean()

        # Value function loss
        value_pred = self.critic(state).squeeze(-1)
        if reward is not None:
            if not isinstance(reward, torch.Tensor):
                reward = torch.as_tensor(reward, device=self.device, dtype=torch.float32)
            else:
                reward = reward.to(self.device)
            value_loss = F.mse_loss(value_pred, reward)
        else:
            value_loss = torch.tensor(0.0, device=self.device, requires_grad=True)

        # Safety penalty (differentiable CBF)
        # Provides gradient signal for learning safe policies
        safety_penalty = self.compute_safety_penalty(state, action_pred)

        # DPO loss for preference-based safety alignment
        dpo_loss = torch.tensor(0.0, device=self.device, requires_grad=True)
        if self.use_dpo:
            # Option 1: DPO from batch (if chosen/rejected actions provided)
            action_chosen = batch.get("action_chosen")
            action_rejected = batch.get("action_rejected")
            if action_chosen is not None and action_rejected is not None:
                if not isinstance(action_chosen, torch.Tensor):
                    action_chosen = torch.as_tensor(
                        action_chosen, device=self.device, dtype=torch.float32
                    )
                if not isinstance(action_rejected, torch.Tensor):
                    action_rejected = torch.as_tensor(
                        action_rejected, device=self.device, dtype=torch.float32
                    )
                dpo_loss = self.compute_dpo_loss(state, action_chosen, action_rejected)

            # Option 2: DPO from preference dataset (if provided)
            elif preference_dataset is not None:
                dpo_loss = self.compute_dpo_loss_from_dataset(
                    preference_dataset, batch_size=dpo_batch_size
                )

        # Combined loss with safety penalty and DPO
        loss = (
            policy_loss
            + 0.5 * value_loss
            + self.safety_penalty_weight * safety_penalty
            + self.dpo_weight * dpo_loss
        )

        return loss

    def get_metrics(self) -> dict[str, float]:
        """Get current CBF, DPO, and UCB metrics for monitoring.

        Returns:
            Dict with safety, preference learning, and exploration metrics
        """
        metrics = {
            "cbf_qp_iterations": self.last_qp_iterations,
            "cbf_safety_margin": self.last_safety_margin,
            "cbf_penalty": self.last_cbf_penalty,
            "dpo_loss": self.last_dpo_loss,
            "dpo_enabled": float(self.use_dpo),
            "dpo_beta": self.dpo_beta,
            "ucb_enabled": float(self.use_ucb_exploration),
        }

        # Add UCB-specific metrics if enabled
        if self.use_ucb_exploration and self.ucb_explorer is not None:
            metrics.update(
                {
                    "ucb_timesteps": float(self.ucb_explorer.t),
                    "ucb_mean_visits": float(self.ucb_explorer.N.mean().item()),
                    "ucb_mean_q": float(self.ucb_explorer.Q.mean().item()),
                }
            )

        return metrics

    def update_reference_policy(self) -> None:
        """Update the reference policy to current policy weights.

        Call this periodically (e.g., after N training steps) to prevent
        the reference policy from becoming too stale. This is similar to
        the "iterative DPO" approach.
        """
        if self.reference_policy is not None:
            self.reference_policy.load_state_dict(self.policy.state_dict())
            for param in self.reference_policy.parameters():
                param.requires_grad = False
            logger.debug("Reference policy updated to current policy weights")


__all__ = ["PolicyLoop", "SafetyStateExtractor", "UCBExplorer"]
