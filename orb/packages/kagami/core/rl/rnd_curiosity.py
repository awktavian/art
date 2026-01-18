from __future__ import annotations

"""Random Network Distillation (RND) for Curiosity-Driven Exploration.

Implementation of RND from Burda et al. 2019.
https://arxiv.org/abs/1810.12894

RND solves the "noisy TV problem" in curiosity-driven RL:
- Old curiosity: prediction error on next state → can be high for random noise
- RND curiosity: prediction error on FIXED random target → high only for novel states

Key Innovation:
  Train predictor network to match fixed random target network.
  Intrinsic reward = prediction error.

  Random target ensures "interesting" states (learnable patterns)
  are distinguished from "noisy" states (unlearnable randomness).

Benefits:
- Solved Montezuma's Revenge (notoriously hard exploration)
- More robust than forward dynamics curiosity
- Works in stochastic environments (noise doesn't break it)

Algorithm:
  1. Initialize target network with random weights (FIXED forever)
  2. Train predictor network to match target on visited states
  3. Intrinsic reward = ||predictor(s) - target(s)||²
  4. States predictor can't match = novel = high reward
"""
import logging
from typing import Any

import numpy as np
from numpy.typing import NDArray

logger = logging.getLogger(__name__)


def _forward_two_layer_relu(
    state_embedding: NDArray[Any],
    W1: NDArray[Any],
    b1: NDArray[Any],
    W2: NDArray[Any],
    b2: NDArray[Any],
) -> NDArray[Any]:
    """Shared 2-layer (ReLU) MLP forward used by RND networks."""
    h = np.maximum(0, state_embedding @ W1 + b1)
    return np.asarray(h @ W2 + b2)


class _TwoLayerReLUForwardMixin:
    """Provides a shared forward() for 2-layer (ReLU) numpy MLPs."""

    W1: NDArray[Any]
    b1: NDArray[Any]
    W2: NDArray[Any]
    b2: NDArray[Any]

    def forward(self, state_embedding: NDArray[Any]) -> NDArray[Any]:
        output = _forward_two_layer_relu(state_embedding, self.W1, self.b1, self.W2, self.b2)
        return output


class RandomTargetNetwork(_TwoLayerReLUForwardMixin):
    """Fixed random neural network (never trained).

    This provides a stable "interestingness" signal.
    States that are far from random features = novel.
    """

    def __init__(self, input_dim: int = 128, hidden_dim: int = 64, output_dim: int = 32) -> None:
        """Initialize random target network.

        Args:
            input_dim: State embedding dimension
            hidden_dim: Hidden layer size
            output_dim: Output embedding dimension
        """
        self.input_dim = input_dim
        self.hidden_dim = hidden_dim
        self.output_dim = output_dim

        # Random weights (FIXED - never updated)
        np.random.seed(42)  # Deterministic for reproducibility
        self.W1 = np.random.randn(input_dim, hidden_dim) * np.sqrt(2.0 / input_dim)
        self.b1 = np.zeros(hidden_dim)

        self.W2 = np.random.randn(hidden_dim, output_dim) * np.sqrt(2.0 / hidden_dim)
        self.b2 = np.zeros(output_dim)

        # Reset seed for other random operations
        np.random.seed(None)


class PredictorNetwork(_TwoLayerReLUForwardMixin):
    """Learned network that tries to match random target.

    Trained via gradient descent to predict target network output.
    Prediction error = intrinsic reward signal.
    """

    def __init__(self, input_dim: int = 128, hidden_dim: int = 64, output_dim: int = 32) -> None:
        """Initialize predictor network.

        Args:
            input_dim: State embedding dimension
            hidden_dim: Hidden layer size
            output_dim: Output embedding dimension (match target)
        """
        self.input_dim = input_dim
        self.hidden_dim = hidden_dim
        self.output_dim = output_dim

        # Learnable weights
        self.W1 = np.random.randn(input_dim, hidden_dim) * np.sqrt(2.0 / input_dim)
        self.b1 = np.zeros(hidden_dim)

        self.W2 = np.random.randn(hidden_dim, output_dim) * np.sqrt(2.0 / hidden_dim)
        self.b2 = np.zeros(output_dim)

        # Adam optimizer state
        self.m_W1 = np.zeros_like(self.W1)
        self.v_W1 = np.zeros_like(self.W1)
        self.m_b1 = np.zeros_like(self.b1)
        self.v_b1 = np.zeros_like(self.b1)

        self.m_W2 = np.zeros_like(self.W2)
        self.v_W2 = np.zeros_like(self.W2)
        self.m_b2 = np.zeros_like(self.b2)
        self.v_b2 = np.zeros_like(self.b2)

        self.t = 0  # Adam timestep

        # Hyperparameters
        self.learning_rate = 0.001
        self.beta1 = 0.9
        self.beta2 = 0.999
        self.epsilon = 1e-8

    def update(
        self, state_embedding: np.ndarray[Any, Any], target_output: np.ndarray[Any, Any]
    ) -> float:
        """Update predictor to match target output.

        Args:
            state_embedding: Input state
            target_output: Target network output (fixed)

        Returns:
            MSE loss
        """
        # Forward pass
        h = np.maximum(0, state_embedding @ self.W1 + self.b1)
        predicted = h @ self.W2 + self.b2

        # Loss: MSE
        error = predicted - target_output
        loss = np.mean(error**2)

        # Backward pass (chain rule)
        # ∂L/∂W2 = h^T @ error
        # ∂L/∂b2 = error
        # ∂L/∂h = error @ W2^T
        # ∂L/∂W1 = state^T @ (∂L/∂h * relu_grad)
        # ∂L/∂b1 = ∂L/∂h * relu_grad

        d_output = 2 * error / len(error)  # Gradient of MSE

        # Layer 2 gradients
        grad_W2 = np.outer(h, d_output)
        grad_b2 = d_output

        # Layer 1 gradients
        d_h = d_output @ self.W2.T
        relu_grad = (h > 0).astype(float)  # ReLU derivative
        d_h_activated = d_h * relu_grad

        grad_W1 = np.outer(state_embedding, d_h_activated)
        grad_b1 = d_h_activated

        # Update with Adam
        self.t += 1

        # W1
        self.m_W1 = self.beta1 * self.m_W1 + (1 - self.beta1) * grad_W1
        self.v_W1 = self.beta2 * self.v_W1 + (1 - self.beta2) * (grad_W1**2)
        m_hat_W1 = self.m_W1 / (1 - self.beta1**self.t)
        v_hat_W1 = self.v_W1 / (1 - self.beta2**self.t)
        self.W1 -= self.learning_rate * m_hat_W1 / (np.sqrt(v_hat_W1) + self.epsilon)

        # b1
        self.m_b1 = self.beta1 * self.m_b1 + (1 - self.beta1) * grad_b1
        self.v_b1 = self.beta2 * self.v_b1 + (1 - self.beta2) * (grad_b1**2)
        m_hat_b1 = self.m_b1 / (1 - self.beta1**self.t)
        v_hat_b1 = self.v_b1 / (1 - self.beta2**self.t)
        self.b1 -= self.learning_rate * m_hat_b1 / (np.sqrt(v_hat_b1) + self.epsilon)

        # W2
        self.m_W2 = self.beta1 * self.m_W2 + (1 - self.beta1) * grad_W2
        self.v_W2 = self.beta2 * self.v_W2 + (1 - self.beta2) * (grad_W2**2)
        m_hat_W2 = self.m_W2 / (1 - self.beta1**self.t)
        v_hat_W2 = self.v_W2 / (1 - self.beta2**self.t)
        self.W2 -= self.learning_rate * m_hat_W2 / (np.sqrt(v_hat_W2) + self.epsilon)

        # b2
        self.m_b2 = self.beta1 * self.m_b2 + (1 - self.beta1) * grad_b2
        self.v_b2 = self.beta2 * self.v_b2 + (1 - self.beta2) * (grad_b2**2)
        m_hat_b2 = self.m_b2 / (1 - self.beta1**self.t)
        v_hat_b2 = self.v_b2 / (1 - self.beta2**self.t)
        self.b2 -= self.learning_rate * m_hat_b2 / (np.sqrt(v_hat_b2) + self.epsilon)

        return float(loss)


class RNDCuriosity:
    """
    RND-based intrinsic motivation.

    Computes intrinsic reward as prediction error on random target.
    More robust than forward dynamics prediction error.
    """

    def __init__(self, state_dim: int = 128, hidden_dim: int = 64, output_dim: int = 32) -> None:
        """Initialize RND curiosity module.

        Args:
            state_dim: State embedding dimension
            hidden_dim: Hidden layer size
            output_dim: Target embedding dimension
        """
        self.state_dim = state_dim

        # Fixed random target (never updated)
        self.target_network = RandomTargetNetwork(state_dim, hidden_dim, output_dim)

        # Learned predictor (trained to match target)
        self.predictor_network = PredictorNetwork(state_dim, hidden_dim, output_dim)

        # Running mean/std for reward normalization
        self._reward_mean = 0.0
        self._reward_std = 1.0
        self._reward_history: list[float] = []

    def compute_intrinsic_reward(self, state: Any) -> float:
        """Compute RND intrinsic reward.

        Args:
            state: Latent state (with embedding attribute)

        Returns:
            Intrinsic reward (0.0-1.0, normalized)
        """
        try:
            # Extract state embedding
            if hasattr(state, "embedding"):
                state_emb = np.array(state.embedding, dtype=np.float32)
            else:
                # Fallback for non-LatentState
                state_emb = np.zeros(self.state_dim, dtype=np.float32)

            # Ensure correct dimension
            if len(state_emb) < self.state_dim:
                state_emb = np.pad(state_emb, (0, self.state_dim - len(state_emb)))
            elif len(state_emb) > self.state_dim:
                state_emb = state_emb[: self.state_dim]

            # Compute predictions
            target_output = self.target_network.forward(state_emb)
            predicted_output = self.predictor_network.forward(state_emb)

            # Prediction error = intrinsic reward
            error = np.linalg.norm(predicted_output - target_output)
            raw_reward = float(error)

            # Normalize using running statistics
            self._reward_history.append(raw_reward)
            if len(self._reward_history) > 1000:
                self._reward_history = self._reward_history[-1000:]

            if len(self._reward_history) > 10:
                self._reward_mean = float(np.mean(self._reward_history))
                self._reward_std = float(np.std(self._reward_history)) + 1e-8

            # Normalized reward (0-1 range)
            normalized_reward = (raw_reward - self._reward_mean) / self._reward_std
            normalized_reward = np.clip(normalized_reward, 0.0, 1.0)

            return float(normalized_reward)

        except Exception as e:
            logger.debug(f"RND curiosity computation failed: {e}")
            # Use normalized historical mean if available, else conservative low value
            return self._reward_mean if self._reward_mean > 0 else 0.3

    async def update_predictor(self, state: Any) -> float:
        """Update predictor network to match target.

        Args:
            state: State to learn from

        Returns:
            Prediction loss
        """
        try:
            # Extract state embedding
            if hasattr(state, "embedding"):
                state_emb = np.array(state.embedding, dtype=np.float32)
            else:
                return 0.0

            # Ensure correct dimension
            if len(state_emb) < self.state_dim:
                state_emb = np.pad(state_emb, (0, self.state_dim - len(state_emb)))
            elif len(state_emb) > self.state_dim:
                state_emb = state_emb[: self.state_dim]

            # Get target (fixed)
            target_output = self.target_network.forward(state_emb)

            # Update predictor
            loss = self.predictor_network.update(state_emb, target_output)

            return loss

        except Exception as e:
            logger.debug(f"RND predictor update failed: {e}")
            return 0.0

    def get_stats(self) -> dict[str, Any]:
        """Get RND statistics.

        Returns:
            Statistics dict[str, Any]
        """
        return {
            "state_dim": self.state_dim,
            "reward_mean": self._reward_mean,
            "reward_std": self._reward_std,
            "samples_seen": len(self._reward_history),
            "predictor_steps": self.predictor_network.t,
        }


# Global singleton
_rnd_curiosity: RNDCuriosity | None = None


def get_rnd_curiosity() -> RNDCuriosity:
    """Get or create global RND curiosity module."""
    global _rnd_curiosity
    if _rnd_curiosity is None:
        _rnd_curiosity = RNDCuriosity(state_dim=128, hidden_dim=64, output_dim=32)
        logger.info("✅ RND curiosity initialized (robust exploration)")
    return _rnd_curiosity
