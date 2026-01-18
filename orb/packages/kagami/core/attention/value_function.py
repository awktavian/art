from __future__ import annotations

from typing import Any

"""Value Function - Critic network for TD-learning.

Estimates V(s) → R: expected cumulative reward from state s.

Architecture:
- Input: s ∈ R^8 (state vector)
- Hidden: [32, 32] with ReLU
- Output: scalar value

Training:
- Target: r_t + γ_TD·V(s_{t+1})
- Loss: MSE(V(s_t), target)
- Optimizer: Adam(lr=0.001)
"""
import json
import logging

import numpy as np

logger = logging.getLogger(__name__)


class CriticNetwork:
    """Simple neural network for value function estimation.

    Uses numpy for lightweight implementation.
    For production, could upgrade to PyTorch/JAX.
    """

    def __init__(
        self,
        input_dim: int = 8,
        hidden_dims: list[int] | None = None,
        learning_rate: float = 0.001,
        gamma_td: float = 0.95,
    ) -> None:
        """Initialize critic network.

        Args:
            input_dim: State vector dimension
            hidden_dims: Hidden layer sizes
            learning_rate: Learning rate for gradient descent
            gamma_td: TD discount factor
        """
        if hidden_dims is None:
            hidden_dims = [32, 32]
        self.input_dim = input_dim
        self.hidden_dims = hidden_dims
        self.learning_rate = learning_rate
        self.gamma_td = gamma_td

        # Initialize weights (Xavier initialization)
        self.weights = []
        self.biases = []

        dims = [input_dim, *hidden_dims, 1]
        for i in range(len(dims) - 1):
            fan_in, fan_out = dims[i], dims[i + 1]
            limit = np.sqrt(6.0 / (fan_in + fan_out))
            W = np.random.uniform(-limit, limit, (fan_in, fan_out)).astype(np.float32)
            b = np.zeros(fan_out, dtype=np.float32)
            self.weights.append(W)
            self.biases.append(b)

        # Adam optimizer state
        self.m_weights = [np.zeros_like(W) for W in self.weights]
        self.v_weights = [np.zeros_like(W) for W in self.weights]
        self.m_biases = [np.zeros_like(b) for b in self.biases]
        self.v_biases = [np.zeros_like(b) for b in self.biases]
        self.t = 0  # Time step for Adam

        # Training history
        self.loss_history: list[float] = []

    def forward(self, s: np.ndarray[Any, Any], store_activations: bool = False) -> float:
        """Forward pass through network.

        Args:
            s: State vector (input_dim,)
            store_activations: If True, store for backprop

        Returns:
            V(s): Estimated value (scalar)
        """
        x = s.copy()
        activations = [x] if store_activations else None

        # Forward through layers
        for i, (W, b) in enumerate(zip(self.weights, self.biases, strict=False)):
            x = x @ W + b

            # ReLU activation for hidden layers
            if i < len(self.weights) - 1:
                x = np.maximum(0, x)

            if store_activations:
                activations.append(x.copy())  # type: ignore  # Union member

        value = float(x[0])  # Output layer has dim 1

        if store_activations:
            self._last_activations = activations

        return value

    def train_step(self, s_t: np.ndarray[Any, Any], target: float) -> float:
        """Single training step via gradient descent.

        Args:
            s_t: State at time t
            target: Target value (r_t + γ·V(s_{t+1}))

        Returns:
            Loss (MSE)
        """
        # Forward pass with activation storage
        pred = self.forward(s_t, store_activations=True)

        # Compute loss
        error = pred - target
        loss = 0.5 * error**2

        # Backward pass (simple backprop)
        self._backward(error)

        # Store loss
        self.loss_history.append(loss)
        if len(self.loss_history) > 1000:
            self.loss_history = self.loss_history[-1000:]

        return loss

    def _backward(self, error: float) -> None:
        """Backward pass and weight update via Adam.

        Args:
            error: Output error (pred - target)
        """
        # Get stored activations
        activations = getattr(self, "_last_activations", None)
        if activations is None:
            return

        # Gradient starts at output
        delta = np.array([error], dtype=np.float32)

        # Backprop through layers (reverse order)
        weight_grads = []  # type: ignore  # Var
        bias_grads = []  # type: ignore  # Var

        for i in range(len(self.weights) - 1, -1, -1):
            # Gradient w.r.t. pre-activation
            if i < len(self.weights) - 1:
                # ReLU derivative
                delta = delta * (activations[i + 1] > 0).astype(np.float32)

            # Gradients
            grad_W = np.outer(activations[i], delta)
            grad_b = delta.copy()

            weight_grads.insert(0, grad_W)
            bias_grads.insert(0, grad_b)

            # Propagate to previous layer
            if i > 0:
                delta = delta @ self.weights[i].T

        # Adam update
        self.t += 1
        beta1, beta2, eps = 0.9, 0.999, 1e-8

        for i in range(len(self.weights)):
            # Update moments
            self.m_weights[i] = beta1 * self.m_weights[i] + (1 - beta1) * weight_grads[i]
            self.v_weights[i] = beta2 * self.v_weights[i] + (1 - beta2) * (weight_grads[i] ** 2)
            self.m_biases[i] = beta1 * self.m_biases[i] + (1 - beta1) * bias_grads[i]
            self.v_biases[i] = beta2 * self.v_biases[i] + (1 - beta2) * (bias_grads[i] ** 2)

            # Bias correction
            m_hat_W = self.m_weights[i] / (1 - beta1**self.t)
            v_hat_W = self.v_weights[i] / (1 - beta2**self.t)
            m_hat_b = self.m_biases[i] / (1 - beta1**self.t)
            v_hat_b = self.v_biases[i] / (1 - beta2**self.t)

            # Update weights
            self.weights[i] -= self.learning_rate * m_hat_W / (np.sqrt(v_hat_W) + eps)
            self.biases[i] -= self.learning_rate * m_hat_b / (np.sqrt(v_hat_b) + eps)

    def compute_td_error(
        self,
        s_t: np.ndarray[Any, Any],
        reward: float,
        s_next: np.ndarray[Any, Any],
        done: bool = False,
    ) -> float:
        """Compute TD error: δ = r + γ·V(s') - V(s).

        Args:
            s_t: Current state
            reward: Immediate reward
            s_next: Next state
            done: If True, terminal state (no future value)

        Returns:
            TD error δ_t
        """
        V_current = self.forward(s_t)
        V_next = 0.0 if done else self.forward(s_next)

        td_error = reward + self.gamma_td * V_next - V_current

        return float(td_error)

    def to_dict(self) -> dict[str, Any]:
        """Serialize network for persistence."""
        return {
            "weights": [W.tolist() for W in self.weights],
            "biases": [b.tolist() for b in self.biases],
            "input_dim": self.input_dim,
            "hidden_dims": self.hidden_dims,
            "learning_rate": self.learning_rate,
            "gamma_td": self.gamma_td,
            "t": self.t,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CriticNetwork:
        """Deserialize from dictionary."""
        network = cls(
            input_dim=data["input_dim"],
            hidden_dims=data["hidden_dims"],
            learning_rate=data["learning_rate"],
            gamma_td=data["gamma_td"],
        )
        # Variable array shapes from serialized data - shapes vary from serialized state
        network.weights = [np.array(W, dtype=np.float32) for W in data["weights"]]
        network.biases = [np.array(b, dtype=np.float32) for b in data["biases"]]  # type: ignore[misc]
        network.t = data.get("t", 0)
        return network


# Singleton instance
_value_function: CriticNetwork | None = None


def get_value_function() -> CriticNetwork:
    """Get singleton value function (critic network)."""
    global _value_function
    if _value_function is None:
        _value_function = CriticNetwork()

        # Try to load from Redis
        try:
            from kagami.core.caching.redis import RedisClientFactory

            redis_client = RedisClientFactory.get_client(
                purpose="default", async_mode=False, decode_responses=True
            )
            data = redis_client.get("kagami:value_function")
            if data:
                _value_function = CriticNetwork.from_dict(json.loads(data))
                logger.info("Loaded value function from Redis")
        except Exception as e:
            logger.warning(f"Could not load value function from Redis: {e}")

    return _value_function


def save_value_function() -> None:
    """Save value function to Redis."""
    global _value_function
    if _value_function is None:
        return

    try:
        from kagami.core.caching.redis import RedisClientFactory

        redis_client = RedisClientFactory.get_client(
            purpose="default", async_mode=False, decode_responses=True
        )
        data = json.dumps(_value_function.to_dict())
        redis_client.set("kagami:value_function", data, ex=86400 * 30)  # 30 days
        logger.info("Saved value function to Redis")
    except Exception as e:
        logger.warning(f"Could not save value function to Redis: {e}")


def extract_reward_from_receipt(receipt: dict[str, Any]) -> float:
    """Extract reward signal from receipt for TD-learning.

    Reward components:
    - Prediction accuracy: -prediction_error
    - Task success: +1.0 if success, -1.0 if failure
    - Safety margin: -5.0 if near boundary
    - Tim approval: +2.0 if present
    - Efficiency: +0.1 if fast

    Args:
        receipt: Receipt dictionary

    Returns:
        Reward r_t ∈ [-10, 10]
    """
    r = 0.0

    # Prediction accuracy
    try:
        metrics = receipt.get("metrics", {})
        if "prediction_error" in metrics:
            error = float(metrics["prediction_error"])
            r += -error  # Lower error = higher reward
    except Exception:
        pass

    # Task success
    try:
        event_name = str(receipt.get("event", {}).get("name", "")).lower()
        if "success" in event_name or "verified" in event_name:
            r += 1.0
        elif "error" in event_name or "failed" in event_name:
            r += -1.0
    except Exception:
        pass

    # Safety violations
    try:
        event_data = receipt.get("event", {}).get("data", {})
        if "safety_margin" in event_data:
            margin = float(event_data["safety_margin"])
            if margin < 0.1:
                r += -5.0  # Severe penalty near boundary
            elif margin > 0.8:
                r += 0.5  # Bonus for very safe
    except Exception:
        pass

    # Tim approval (if annotated in receipt)
    try:
        event_data = receipt.get("event", {}).get("data", {})
        if event_data.get("tim_approved"):
            r += 2.0
    except Exception:
        pass

    # Efficiency (faster is better)
    try:
        duration_ms = receipt.get("duration_ms", 0)
        if duration_ms > 0 and duration_ms < 1000:
            r += 0.1
        elif duration_ms > 10000:
            r += -0.1  # Slight penalty for very slow
    except Exception:
        pass

    # Clip to bounded range
    return float(np.clip(r, -10.0, 10.0))
