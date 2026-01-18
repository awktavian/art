"""Strange Loop (μ_self) Improvements.

Improvements to the strange loop / self-reference mechanism:
1. Iterative fixed-point refinement - converge to stable μ_self via iteration
2. Contrastive self-recognition - discriminate self from other
3. Temporal consistency - μ_self should be stable across time

References:
- Hofstadter (1979): Gödel, Escher, Bach
- Kagami architecture: Strange loop as self-model
- Fixed-point theory for neural networks

Created: December 27, 2025
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import torch
import torch.nn as nn
import torch.nn.functional as F

logger = logging.getLogger(__name__)


@dataclass
class StrangeLoopConfig:
    """Configuration for iterative strange loop."""

    # Dimensions
    s7_dim: int = 7  # S7 phase dimension
    hidden_dim: int = 64  # Hidden dimension for fixed-point network

    # Iteration parameters
    max_iterations: int = 10  # Maximum fixed-point iterations
    convergence_threshold: float = 1e-4  # Convergence criterion
    damping: float = 0.5  # Damping factor for stability (0 = no update, 1 = full update)

    # Architecture
    num_layers: int = 2  # Layers in fixed-point network
    use_layer_norm: bool = True
    dropout: float = 0.0

    # Loss weights
    convergence_weight: float = 0.1  # Weight for convergence loss
    consistency_weight: float = 0.1  # Weight for temporal consistency
    recognition_weight: float = 0.05  # Weight for self-recognition


class FixedPointNetwork(nn.Module):
    """Network for computing fixed-point updates.

    Given current μ_self and context, computes the next iterate:
        μ_self' = f(μ_self, context)

    At a fixed point: μ_self* = f(μ_self*, context)
    """

    def __init__(self, config: StrangeLoopConfig):
        super().__init__()
        self.config = config

        # Input: concatenation of μ_self and context
        input_dim = config.s7_dim * 2  # μ_self + s7_context

        layers = []
        dim = input_dim

        for i in range(config.num_layers):
            out_dim = config.hidden_dim if i < config.num_layers - 1 else config.s7_dim
            layers.append(nn.Linear(dim, out_dim))

            if i < config.num_layers - 1:
                if config.use_layer_norm:
                    layers.append(nn.LayerNorm(out_dim))  # type: ignore[arg-type]
                layers.append(nn.GELU())  # type: ignore[arg-type]
                if config.dropout > 0:
                    layers.append(nn.Dropout(config.dropout))  # type: ignore[arg-type]

            dim = out_dim

        self.network = nn.Sequential(*layers)

        # Output normalization to S7 (unit sphere in R^7)
        self.normalize_output = True

    def forward(
        self,
        mu_self: torch.Tensor,
        s7_context: torch.Tensor,
    ) -> torch.Tensor:
        """Compute one fixed-point iteration.

        Args:
            mu_self: [B, 7] current self-model
            s7_context: [B, 7] context from S7 hierarchy

        Returns:
            [B, 7] updated self-model
        """
        # Concatenate inputs
        x = torch.cat([mu_self, s7_context], dim=-1)  # [B, 14]

        # Compute update
        update = self.network(x)  # [B, 7]

        # Normalize to S7 (unit sphere)
        if self.normalize_output:
            update = F.normalize(update, dim=-1)

        return update


class IterativeStrangeLoop(nn.Module):
    """Iterative fixed-point computation for μ_self.

    THEORY:
    =======
    The strange loop represents self-reference: μ_self is a compressed
    representation of the agent's own state. At equilibrium:

        μ_self* = f(μ_self*, context)

    This is a fixed-point equation. We solve it via iteration:
        μ_self^(k+1) = (1-α) * μ_self^(k) + α * f(μ_self^(k), context)

    Where α is the damping factor. Convergence is encouraged via:
    1. Contraction mapping property of f
    2. Damping for stability
    3. Loss term penalizing non-convergence

    IMPROVEMENT OVER PREVIOUS:
    ==========================
    Previous: Single-shot μ_self computation
    Now: Iterative refinement to stable fixed point

    This ensures μ_self actually represents a stable self-model,
    not just a noisy single-step estimate.
    """

    def __init__(self, config: StrangeLoopConfig | None = None):
        super().__init__()
        self.config = config or StrangeLoopConfig()

        # Fixed-point network
        self.fixed_point_net = FixedPointNetwork(self.config)

        # Self-recognition head (discriminate self from other)
        self.recognition_head = nn.Sequential(
            nn.Linear(self.config.s7_dim * 2, self.config.hidden_dim),
            nn.GELU(),
            nn.Linear(self.config.hidden_dim, 1),
        )

        # Temporal consistency projection
        self.temporal_proj = nn.Linear(self.config.s7_dim, self.config.s7_dim)

        logger.info(
            f"IterativeStrangeLoop initialized:\n"
            f"  Max iterations: {self.config.max_iterations}\n"
            f"  Convergence threshold: {self.config.convergence_threshold}\n"
            f"  Damping: {self.config.damping}"
        )

    def forward(
        self,
        s7_context: torch.Tensor,
        mu_self_init: torch.Tensor | None = None,
        return_trajectory: bool = False,
    ) -> dict[str, torch.Tensor]:
        """Compute μ_self via iterative fixed-point refinement.

        Args:
            s7_context: [B, 7] context from S7 hierarchy
            mu_self_init: Optional [B, 7] initial μ_self. If None, uses s7_context.
            return_trajectory: If True, return all iterates

        Returns:
            Dict with:
                - mu_self: [B, 7] converged self-model
                - convergence_loss: Scalar loss for non-convergence
                - num_iterations: Number of iterations used
                - trajectory: Optional list[Any] of iterates
        """
        s7_context.shape[0]
        device = s7_context.device

        # Initialize μ_self
        if mu_self_init is not None:
            mu_self = mu_self_init
        else:
            mu_self = F.normalize(s7_context, dim=-1)

        trajectory = [mu_self] if return_trajectory else []

        # Iterative refinement
        convergence_losses = []
        iteration = 0

        for iteration in range(self.config.max_iterations):  # noqa: B007
            # Compute next iterate
            mu_next = self.fixed_point_net(mu_self, s7_context)

            # Damped update
            mu_self_new = (1 - self.config.damping) * mu_self + self.config.damping * mu_next
            mu_self_new = F.normalize(mu_self_new, dim=-1)

            # Track convergence
            delta = (mu_self_new - mu_self).pow(2).sum(dim=-1).sqrt()  # [B]
            convergence_losses.append(delta.mean())

            if return_trajectory:
                trajectory.append(mu_self_new)

            # Check convergence
            if delta.max() < self.config.convergence_threshold:
                break

            mu_self = mu_self_new

        # Final normalization
        mu_self = F.normalize(mu_self, dim=-1)

        # Convergence loss: penalize if not converged
        # Use mean of last few iterations
        if len(convergence_losses) > 0:
            convergence_loss = sum(convergence_losses[-3:]) / min(3, len(convergence_losses))
        else:
            convergence_loss = torch.tensor(0.0, device=device)

        results = {
            "mu_self": mu_self,
            "convergence_loss": convergence_loss * self.config.convergence_weight,
            "num_iterations": torch.tensor(iteration + 1, device=device),
        }

        if return_trajectory:
            results["trajectory"] = trajectory  # type: ignore[assignment]

        return results  # type: ignore[return-value]

    def compute_recognition_loss(
        self,
        mu_self: torch.Tensor,
        mu_other: torch.Tensor,
    ) -> torch.Tensor:
        """Compute self-recognition loss.

        Trains the model to distinguish its own μ_self from others.

        Args:
            mu_self: [B, 7] self-model
            mu_other: [B, 7] other agent's model (or permuted self)

        Returns:
            Recognition loss
        """
        # Positive pairs: (μ_self, μ_self)
        pos_input = torch.cat([mu_self, mu_self], dim=-1)
        pos_score = self.recognition_head(pos_input)  # [B, 1]

        # Negative pairs: (μ_self, μ_other)
        neg_input = torch.cat([mu_self, mu_other], dim=-1)
        neg_score = self.recognition_head(neg_input)  # [B, 1]

        # Binary cross-entropy loss
        pos_loss = F.binary_cross_entropy_with_logits(pos_score, torch.ones_like(pos_score))
        neg_loss = F.binary_cross_entropy_with_logits(neg_score, torch.zeros_like(neg_score))

        return (pos_loss + neg_loss) * self.config.recognition_weight

    def compute_temporal_consistency_loss(
        self,
        mu_self_t: torch.Tensor,
        mu_self_t_prev: torch.Tensor,
    ) -> torch.Tensor:
        """Compute temporal consistency loss.

        μ_self should be stable across time steps (smooth evolution).

        Args:
            mu_self_t: [B, 7] current self-model
            mu_self_t_prev: [B, 7] previous self-model

        Returns:
            Temporal consistency loss
        """
        # Project previous to current (allow for slow drift)
        mu_prev_proj = self.temporal_proj(mu_self_t_prev)
        mu_prev_proj = F.normalize(mu_prev_proj, dim=-1)

        # Cosine similarity (should be high)
        similarity = F.cosine_similarity(mu_self_t, mu_prev_proj, dim=-1)

        # Loss: 1 - similarity (minimize to maximize similarity)
        loss = (1.0 - similarity).mean()

        return loss * self.config.consistency_weight

    def compute_total_loss(
        self,
        s7_context: torch.Tensor,
        mu_self_prev: torch.Tensor | None = None,
    ) -> tuple[torch.Tensor, dict[str, torch.Tensor]]:
        """Compute all strange loop losses.

        Args:
            s7_context: [B, 7] current S7 context
            mu_self_prev: Optional [B, 7] previous μ_self for consistency

        Returns:
            Tuple of (total_loss, metrics_dict)
        """
        # Run iterative fixed-point
        results = self.forward(s7_context)
        mu_self = results["mu_self"]

        total_loss = results["convergence_loss"]
        metrics = {
            "strange_loop_convergence_loss": results["convergence_loss"],
            "strange_loop_iterations": results["num_iterations"].float(),
        }

        # Recognition loss (use shuffled batch as "other")
        B = mu_self.shape[0]
        if B > 1:
            perm = torch.randperm(B, device=mu_self.device)
            mu_other = mu_self[perm]
            recognition_loss = self.compute_recognition_loss(mu_self, mu_other)
            total_loss = total_loss + recognition_loss
            metrics["strange_loop_recognition_loss"] = recognition_loss

        # Temporal consistency
        if mu_self_prev is not None:
            consistency_loss = self.compute_temporal_consistency_loss(mu_self, mu_self_prev)
            total_loss = total_loss + consistency_loss
            metrics["strange_loop_consistency_loss"] = consistency_loss

        metrics["strange_loop_total_loss"] = total_loss

        return total_loss, metrics


def create_iterative_strange_loop(
    s7_dim: int = 7,
    max_iterations: int = 10,
    damping: float = 0.5,
) -> IterativeStrangeLoop:
    """Factory function to create iterative strange loop.

    Args:
        s7_dim: S7 dimension (default: 7)
        max_iterations: Maximum iterations (default: 10)
        damping: Damping factor (default: 0.5)

    Returns:
        Configured IterativeStrangeLoop
    """
    config = StrangeLoopConfig(
        s7_dim=s7_dim,
        max_iterations=max_iterations,
        damping=damping,
    )
    return IterativeStrangeLoop(config)


__all__ = [
    "FixedPointNetwork",
    "IterativeStrangeLoop",
    "StrangeLoopConfig",
    "create_iterative_strange_loop",
]
