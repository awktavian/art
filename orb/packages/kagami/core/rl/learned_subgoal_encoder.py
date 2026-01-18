from __future__ import annotations

"""Learned Subgoal Encoder for Hierarchical Planning.

Upgrades from k-means clustering to learned neural encoder.
Discovers subgoals via:
1. Variational bottleneck (force compact representation)
2. Reconstruction loss (learn meaningful subgoals)
3. Temporal coherence loss (smooth subgoal transitions)

Based on:
- Hieros (Pan et al., 2024): Learned temporal abstractions
- VQ-VAE (van den Oord et al., 2017): Vector quantization
- β-VAE (Higgins et al., 2017): Disentangled representations
"""
import logging
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


class LearnedSubgoalEncoder:
    """Neural encoder for discovering subgoals.

    Architecture:
    - Encoder: state_embedding → subgoal_latent
    - Quantizer: Assign to nearest discrete subgoal
    - Decoder: subgoal → reconstructed state
    - Training: Reconstruction + temporal coherence
    """

    def __init__(  # type: ignore[misc]
        self,
        state_dim: int = 128,
        subgoal_dim: int = 32,
        n_subgoals: int = 8,
        use_neural: bool = True,
    ) -> Any:
        """Initialize learned subgoal encoder.

        Args:
            state_dim: Dimension of state embeddings
            subgoal_dim: Dimension of subgoal latent space
            n_subgoals: Number of discrete subgoals
            use_neural: Use neural encoder (vs linear projection)
        """
        self.state_dim = state_dim
        self.subgoal_dim = subgoal_dim
        self.n_subgoals = n_subgoals
        self.use_neural = use_neural

        # Subgoal codebook (discrete subgoal vectors)
        self._codebook = np.random.randn(n_subgoals, subgoal_dim) * 0.1

        # Neural network components (if PyTorch available)
        self._encoder_net = None
        self._decoder_net = None
        self._optimizer = None

        if use_neural:
            try:
                import torch
                import torch.nn as nn

                class SubgoalEncoderNet(nn.Module):
                    """Encode state to subgoal latent."""

                    def __init__(self, state_dim: Any, subgoal_dim: Any) -> None:
                        super().__init__()
                        self.net = nn.Sequential(
                            nn.Linear(state_dim, 128),
                            nn.ReLU(),
                            nn.Dropout(0.1),
                            nn.Linear(128, 64),
                            nn.ReLU(),
                            nn.Linear(64, subgoal_dim),  # Bottleneck
                        )

                    def forward(self, x: Any) -> Any:
                        return self.net(x)

                class SubgoalDecoderNet(nn.Module):
                    """Decode subgoal back to state space."""

                    def __init__(self, subgoal_dim: Any, state_dim: Any) -> None:
                        super().__init__()
                        self.net = nn.Sequential(
                            nn.Linear(subgoal_dim, 64),
                            nn.ReLU(),
                            nn.Linear(64, 128),
                            nn.ReLU(),
                            nn.Linear(128, state_dim),
                        )

                    def forward(self, x: Any) -> Any:
                        return self.net(x)

                self._encoder_net = SubgoalEncoderNet(state_dim, subgoal_dim)
                self._decoder_net = SubgoalDecoderNet(subgoal_dim, state_dim)

                # Shared optimizer
                params = list(self._encoder_net.parameters()) + list(self._decoder_net.parameters())
                self._optimizer = torch.optim.Adam(params, lr=0.001)

                logger.info(
                    f"✅ Learned subgoal encoder initialized (neural, {n_subgoals} subgoals)"
                )

            except ImportError:
                logger.debug("PyTorch unavailable, using linear projection")
                self.use_neural = False

    def encode_state_to_subgoal(self, state: np.ndarray[Any, Any]) -> np.ndarray[Any, Any]:
        """Encode state to subgoal latent space.

        Args:
            state: State embedding (state_dim,)

        Returns:
            Subgoal latent (subgoal_dim,)
        """
        if self.use_neural and self._encoder_net is not None:
            try:
                import torch

                with torch.no_grad():
                    state_tensor = torch.tensor(state, dtype=torch.float32).unsqueeze(0)
                    subgoal_tensor = self._encoder_net(state_tensor)
                    subgoal = subgoal_tensor.squeeze(0).numpy()
                    return subgoal  # type: ignore[no-any-return]  # numpy operations return ndarray[Any, Any]

            except Exception as e:
                logger.debug(f"Neural encoding failed: {e}")

        # Fallback: Linear projection
        return state[: self.subgoal_dim]

    def discover_subgoal(self, state: np.ndarray[Any, Any]) -> int:
        """Discover which discrete subgoal this state belongs to.

        Args:
            state: State embedding

        Returns:
            Subgoal ID (0 to n_subgoals-1)
        """
        # Encode to subgoal space
        subgoal_latent = self.encode_state_to_subgoal(state)

        # Find nearest codebook entry (vector quantization)
        distances = np.linalg.norm(self._codebook - subgoal_latent[np.newaxis, :], axis=1)
        subgoal_id = int(np.argmin(distances))

        return subgoal_id

    def get_subgoal_state(self, subgoal_id: int) -> np.ndarray[Any, Any]:
        """Get state representation of subgoal.

        Args:
            subgoal_id: Subgoal ID

        Returns:
            State in original space
        """
        if subgoal_id >= self.n_subgoals:
            subgoal_id = self.n_subgoals - 1

        # Get codebook vector
        subgoal_latent = self._codebook[subgoal_id]

        # Decode back to state space
        if self.use_neural and self._decoder_net is not None:
            try:
                import torch

                with torch.no_grad():
                    subgoal_tensor = torch.tensor(subgoal_latent, dtype=torch.float32).unsqueeze(0)
                    state_tensor = self._decoder_net(subgoal_tensor)
                    state = state_tensor.squeeze(0).numpy()
                    return state  # type: ignore[no-any-return]  # numpy operations return ndarray[Any, Any]

            except Exception as e:
                logger.debug(f"Neural decoding failed: {e}")

        # Fallback: Pad with zeros
        state = np.zeros(self.state_dim)
        state[: len(subgoal_latent)] = subgoal_latent
        return state

    async def train_from_trajectory(
        self, state_trajectory: list[np.ndarray[Any, Any]], rewards: list[float]
    ) -> dict[str, Any]:
        """Train encoder/decoder from trajectory.

        Updates:
        1. Codebook (via exponential moving average of assignments)
        2. Encoder/decoder (via reconstruction + coherence loss)

        Args:
            state_trajectory: Sequence of states
            rewards: Rewards at each step

        Returns:
            Training statistics
        """
        if len(state_trajectory) < 2:
            return {"status": "insufficient_data"}

        # Update codebook via exponential moving average
        assignments = [self.discover_subgoal(s) for s in state_trajectory]

        for state, subgoal_id in zip(state_trajectory, assignments, strict=False):
            subgoal_latent = self.encode_state_to_subgoal(state)

            # EMA update
            alpha = 0.1
            self._codebook[subgoal_id] = (
                alpha * subgoal_latent + (1 - alpha) * self._codebook[subgoal_id]
            )

        # Train neural encoder/decoder if available
        if self.use_neural and self._encoder_net is not None:
            try:
                import torch
                import torch.nn.functional as F

                # Convert to tensors
                states_tensor = torch.tensor(np.array(state_trajectory), dtype=torch.float32)

                # Forward pass
                subgoal_latents = self._encoder_net(states_tensor)
                reconstructed_states = self._decoder_net(subgoal_latents)  # type: ignore  # Misc

                # Reconstruction loss
                recon_loss = F.mse_loss(reconstructed_states, states_tensor)

                # Temporal coherence loss (smooth subgoal transitions)
                if len(subgoal_latents) > 1:
                    diff = subgoal_latents[1:] - subgoal_latents[:-1]
                    coherence_loss = torch.mean(diff**2)
                else:
                    coherence_loss = torch.tensor(0.0)

                # Total loss
                total_loss = recon_loss + 0.1 * coherence_loss

                # Backward pass
                self._optimizer.zero_grad()  # type: ignore  # Union member
                total_loss.backward()
                self._optimizer.step()  # type: ignore  # Union member

                return {
                    "status": "trained",
                    "recon_loss": float(recon_loss.item()),
                    "coherence_loss": float(coherence_loss.item()),
                    "total_loss": float(total_loss.item()),
                }

            except Exception as e:
                logger.debug(f"Neural training failed: {e}")
                return {"status": "error", "error": str(e)}

        return {"status": "codebook_updated"}


# Global singleton
_learned_encoder: LearnedSubgoalEncoder | None = None


def get_learned_subgoal_encoder() -> LearnedSubgoalEncoder:
    """Get or create learned subgoal encoder."""
    global _learned_encoder
    if _learned_encoder is None:
        _learned_encoder = LearnedSubgoalEncoder(use_neural=True)
        logger.info("✅ Learned subgoal encoder initialized")
    return _learned_encoder
