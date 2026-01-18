"""Epistemic Value - SimSiam-based Information Gain for Active Inference.

CREATED: January 4, 2026
PURPOSE: Compute epistemic value (information gain) using SimSiam architecture.

BACKGROUND (December 3, 2025):
==============================
We replaced InfoNCE-based information gain with SimSiam because:
1. SimSiam works with any batch size (no minimum batch requirement)
2. Simpler architecture (no memory bank or momentum encoder)
3. Differentiable through stop-gradient (asymmetric loss)

SIMSIAM ARCHITECTURE:
====================
Given encoder f, predictor h:
    z1 = f(x1), z2 = f(x2)  # Encode two views
    p1 = h(z1), p2 = h(z2)  # Predict from embeddings

    D(p1, stopgrad(z2)) = -cosine_similarity(p1, z2)  # Asymmetric loss
    loss = D(p1, z2) + D(p2, z1)  # Symmetric loss

For epistemic value (information gain):
- View 1: Stochastic state z from RSSM (uncertainty about world)
- View 2: Observations (what we would learn from acting)
- High similarity = low surprise = low epistemic value
- Low similarity = high surprise = high epistemic value (explore!)

References:
- Chen & He (2020): "Exploring Simple Siamese Representation Learning"
- Friston et al. (2015): "Active inference and epistemic value"
"""

from __future__ import annotations

import logging

import torch
import torch.nn as nn
import torch.nn.functional as F

logger = logging.getLogger(__name__)


class EpistemicValue(nn.Module):
    """SimSiam-based epistemic value (information gain) computation.

    Measures how much an agent would learn from taking an action by comparing
    predicted states (z) with expected observations (o).

    HIGH epistemic value = states and observations are dissimilar = more to learn
    LOW epistemic value = states predict observations well = less to learn

    USAGE:
    ======
    ```python
    epistemic = EpistemicValue(state_dim=256, stochastic_dim=14, observation_dim=15)

    # Compute information gain
    info_gain = epistemic.compute_simsiam(z_states, observations)  # [batch]
    ```

    ARCHITECTURE:
    =============
    1. State encoder: Projects z_states to embedding space
    2. Observation encoder: Projects observations to same space
    3. Predictor: Asymmetric MLP for stop-gradient loss
    4. Information gain: 1 - cosine_similarity (high = dissimilar = explore)
    """

    def __init__(
        self,
        state_dim: int = 256,
        stochastic_dim: int = 14,
        observation_dim: int = 15,
        embedding_dim: int = 64,
        predictor_hidden: int = 32,
    ) -> None:
        """Initialize epistemic value computation.

        Args:
            state_dim: Deterministic state dimension (h from RSSM) - for compatibility
            stochastic_dim: Stochastic state dimension (z from RSSM) - input dim
            observation_dim: Observation dimension (E8 code + S7 phase = 8+7=15)
            embedding_dim: Shared embedding dimension
            predictor_hidden: Hidden dimension for predictor MLP
        """
        super().__init__()
        self.state_dim = state_dim
        self.stochastic_dim = stochastic_dim
        self.observation_dim = observation_dim
        self.embedding_dim = embedding_dim

        # State encoder (z -> embedding)
        self.state_encoder = nn.Sequential(
            nn.Linear(stochastic_dim, embedding_dim),
            nn.LayerNorm(embedding_dim),
            nn.ReLU(),
            nn.Linear(embedding_dim, embedding_dim),
        )

        # Observation encoder (o -> embedding)
        self.obs_encoder = nn.Sequential(
            nn.Linear(observation_dim, embedding_dim),
            nn.LayerNorm(embedding_dim),
            nn.ReLU(),
            nn.Linear(embedding_dim, embedding_dim),
        )

        # Predictor (for asymmetric loss)
        # Maps from embedding to embedding, enabling stop-gradient
        self.predictor = nn.Sequential(
            nn.Linear(embedding_dim, predictor_hidden),
            nn.ReLU(),
            nn.Linear(predictor_hidden, embedding_dim),
        )

        logger.debug(
            f"EpistemicValue: z_dim={stochastic_dim}, o_dim={observation_dim}, "
            f"emb_dim={embedding_dim}"
        )

    def compute_simsiam(
        self,
        z_states: torch.Tensor,
        observations: torch.Tensor,
    ) -> torch.Tensor:
        """Compute information gain using SimSiam architecture.

        SimSiam computes asymmetric cosine similarity between:
        - Predicted state embedding (through predictor)
        - Observation embedding (stop-gradient target)

        Information gain = 1 - similarity (so dissimilar = high value)

        Args:
            z_states: [batch, horizon, stochastic_dim] or [batch, stochastic_dim]
                     Stochastic states from RSSM
            observations: [batch, horizon, observation_dim] or [batch, observation_dim]
                         Expected observations

        Returns:
            info_gain: [batch] information gain values (higher = more to learn)
        """
        # Handle various input shapes
        original_shape = z_states.shape
        B = original_shape[0]

        # Flatten if has horizon dimension
        if len(original_shape) == 3:
            H = original_shape[1]
            z_flat = z_states.reshape(B * H, -1)  # [B*H, z_dim]
            o_flat = observations.reshape(B * H, -1)  # [B*H, o_dim]
        else:
            H = 1
            z_flat = z_states  # [B, z_dim]
            o_flat = observations  # [B, o_dim]

        N = z_flat.shape[0]

        # Handle batch size 1 edge case (BatchNorm constraint)
        # Use variance-based fallback for single samples
        if N == 1:
            # Can't compute meaningful SimSiam with N=1
            # Fallback: use variance of state as proxy for uncertainty
            z_var = z_states.var(dim=-1) if len(original_shape) == 3 else z_states.var()
            return z_var.reshape(B) * 0.1  # Scale to reasonable range

        # Encode states and observations
        z_emb = self.state_encoder(z_flat)  # [N, emb_dim]
        o_emb = self.obs_encoder(o_flat)  # [N, emb_dim]

        # L2 normalize embeddings
        z_emb = F.normalize(z_emb, dim=-1)
        o_emb = F.normalize(o_emb, dim=-1)

        # SimSiam asymmetric loss
        # p = predictor(z_emb), target = stopgrad(o_emb)
        p = self.predictor(z_emb)  # [N, emb_dim]
        p = F.normalize(p, dim=-1)

        # Cosine similarity between prediction and target
        # Stop gradient on observation embedding
        similarity = (p * o_emb.detach()).sum(dim=-1)  # [N]

        # Information gain = 1 - similarity
        # High similarity = low information gain (already know this)
        # Low similarity = high information gain (much to learn)
        info_gain_flat = 1.0 - similarity  # [N]

        # Clamp to [0, 2] range (cosine sim is [-1, 1])
        info_gain_flat = info_gain_flat.clamp(0.0, 2.0)

        # Reshape back to batch
        if len(original_shape) == 3:
            # Average over horizon
            info_gain = info_gain_flat.reshape(B, H).mean(dim=-1)  # [B]
        else:
            info_gain = info_gain_flat  # [B]

        return info_gain

    def forward(
        self,
        z_states: torch.Tensor,
        observations: torch.Tensor,
    ) -> torch.Tensor:
        """Forward pass (alias for compute_simsiam).

        Args:
            z_states: Stochastic states from RSSM
            observations: Expected observations

        Returns:
            info_gain: [batch] information gain values
        """
        return self.compute_simsiam(z_states, observations)


__all__ = ["EpistemicValue"]
