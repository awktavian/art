"""Matryoshka Representation Learning Loss for Hierarchical Bottleneck.

MATRYOSHKA LOSS (Dec 3, 2025):
==============================
Implements Matryoshka Representation Learning (Kusupati et al., 2022) for
the exceptional Lie algebra hierarchy:

    G₂(14) ⊂ F₄(52) ⊂ E₆(78) ⊂ E₇(133) ⊂ E₈(248) ⊂ Bulk(N)

Key insight: The first D dimensions of any representation should be
INDEPENDENTLY useful. This enables:
1. Adaptive computation (use fewer dims for simple inputs)
2. Elastic inference (scale precision to hardware)
3. Nested semantic structure (coarse-to-fine encoding)

EXCEPTIONAL ALGEBRA ALIGNMENT:
============================
Unlike standard Matryoshka which uses arbitrary splits (64, 128, 256...),
we use the mathematically-meaningful exceptional dimensions:
    14 → 21 → 52 → 78 → 133 → 248 → bulk

Each level corresponds to a Lie algebra structure:
    - 14D: G₂ (core semantic compression, bottleneck)
    - 21D: Manifold (H¹⁴ × S⁷ combined)
    - 52D: F₄ (Jordan algebra actions)
    - 78D: E₆ (structure group)
    - 133D: E₇ (extended planning)
    - 248D: E₈ (full lattice)
    - bulk: Application-specific width

LOSS STRUCTURE:
==============
For each exceptional level d_k, we compute:
    L_k = TaskLoss(project(z, d_k))

Total: L = Σ_k w_k * L_k

Weights can be:
- Uniform: w_k = 1/K
- Exponential decay: w_k = α^k (emphasize small dims)
- Learned: w_k = softmax(θ_k)

GRADIENT FLOW:
=============
Each prefix gets gradients from:
1. Its own task loss (direct)
2. All larger prefixes (shared weights via projection)

This ensures early dimensions are well-optimized.

References:
- Kusupati et al. (2022) "Matryoshka Representation Learning"
- K OS exceptional hierarchy documentation

Created: December 3, 2025
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

import torch
import torch.nn as nn
import torch.nn.functional as F
from kagami_math.dimensions import (
    get_bulk_dim,
    get_matryoshka_dimensions,
)

logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION
# =============================================================================


@dataclass
class MatryoshkaLossConfig:
    """Configuration for Matryoshka representation learning loss.

    EXCEPTIONAL ALIGNMENT:
    =====================
    By default, uses the exceptional Lie algebra dimensions.
    Can also specify custom nesting dimensions.

    WEIGHT STRATEGIES:
    =================
    - "uniform": Equal weight to all levels
    - "exponential": Higher weight on smaller dimensions (coarse-to-fine)
    - "inverse": Weight inversely proportional to dimension
    - "learned": Learnable weight per level
    """

    # Matryoshka nesting dimensions (ascending order)
    # None = use exceptional hierarchy + bulk
    nesting_dims: tuple[int, ...] | None = None

    # Bulk dimension (for full representation)
    bulk_dim: int | None = None  # Uses KAGAMI_BULK_DIM if None

    # Weight strategy for combining level losses
    weight_strategy: Literal["uniform", "exponential", "inverse", "learned"] = "exponential"

    # Exponential decay factor (for "exponential" strategy)
    # w_k = alpha^k where k is level index
    alpha: float = 0.8

    # Minimum weight (prevents zero weight on any level)
    min_weight: float = 0.01

    # Whether to normalize weights to sum to 1
    normalize_weights: bool = True

    # Loss function for each level
    # "mse": Mean squared error (reconstruction)
    # "cosine": Cosine similarity (semantic)
    # "contrastive": InfoNCE-style (discriminative)
    level_loss: Literal["mse", "cosine", "contrastive"] = "mse"

    # Temperature for contrastive loss
    temperature: float = 0.07

    # Whether to compute hierarchical KL (nested prior matching)
    use_hierarchical_kl: bool = True
    kl_weight: float = 0.01

    # Adaptive: skip levels for simple inputs
    adaptive_skip: bool = False
    skip_threshold: float = 0.01  # Skip if residual < threshold

    def __post_init__(self) -> None:
        if self.bulk_dim is None:
            self.bulk_dim = get_bulk_dim()
        if self.nesting_dims is None:
            self.nesting_dims = get_matryoshka_dimensions(self.bulk_dim)


# =============================================================================
# PROJECTION LAYERS
# =============================================================================


class ExceptionalProjection(nn.Module):
    """Projects representations to each exceptional dimension level.

    ARCHITECTURE:
    ============
    For each nesting dimension d_k, we have a projection:
        proj_k: bulk_dim → d_k

    The projections are NOT simple slicing. Instead, we use learned
    linear projections to find the best d_k-dimensional subspace.

    ORTHOGONALITY REGULARIZATION:
    ============================
    We encourage projections to select orthogonal subspaces:
        L_orth = ||P_k^T P_k - I||_F

    This prevents all levels from collapsing to the same features.
    """

    def __init__(self, config: MatryoshkaLossConfig):
        super().__init__()
        self.config = config

        # Create projection for each level
        self.projections = nn.ModuleDict()
        if config.nesting_dims is not None:
            for dim in config.nesting_dims:
                if config.bulk_dim is not None and dim < config.bulk_dim:
                    self.projections[str(dim)] = nn.Linear(config.bulk_dim, dim, bias=False)
                # Full bulk_dim doesn't need projection

        # Initialize with orthogonal weights
        self._init_orthogonal()

    def _init_orthogonal(self) -> None:
        """Initialize projections with semi-orthogonal matrices (MPS-safe)."""
        for _name, proj in self.projections.items():
            # MPS-safe orthogonal init: do QR on CPU first
            assert isinstance(proj, nn.Linear), "proj must be Linear layer"
            original_device = proj.weight.device
            cpu_weight = proj.weight.cpu()
            nn.init.orthogonal_(cpu_weight)
            proj.weight.data = cpu_weight.to(original_device)

    def forward(self, x: torch.Tensor) -> dict[int, torch.Tensor]:
        """Project to all nesting dimensions.

        Args:
            x: [B, bulk_dim] input representation

        Returns:
            Dict mapping dimension → projected representation
        """
        projections: dict[int, torch.Tensor] = {}

        if self.config.nesting_dims is None:
            return projections

        for dim in self.config.nesting_dims:
            if dim == self.config.bulk_dim:
                projections[dim] = x
            elif self.config.bulk_dim is not None and dim < self.config.bulk_dim:
                projections[dim] = self.projections[str(dim)](x)
            # Skip dims > bulk_dim (shouldn't happen with proper config)

        return projections

    def orthogonality_loss(self) -> torch.Tensor:
        """Compute orthogonality regularization loss.

        Encourages each projection to select different features.

        Returns:
            Scalar orthogonality loss
        """
        if len(self.projections) < 2:
            return torch.tensor(0.0)

        total_loss = torch.tensor(0.0)

        for _name, proj in self.projections.items():
            assert isinstance(proj, nn.Linear), "proj must be Linear layer"
            W = proj.weight  # [out_dim, bulk_dim]
            # W @ W^T should be identity (rows are orthonormal)
            gram = W @ W.T  # [out_dim, out_dim]
            identity = torch.eye(gram.shape[0], device=gram.device)
            total_loss = total_loss + F.mse_loss(gram, identity)

        return total_loss / len(self.projections)


# =============================================================================
# LEVEL LOSS FUNCTIONS
# =============================================================================


def mse_level_loss(pred: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
    """MSE loss for reconstruction-based Matryoshka."""
    return F.mse_loss(pred, target, reduction="mean")


def cosine_level_loss(pred: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
    """Cosine similarity loss for semantic Matryoshka.

    Maximizes cosine similarity between projected representations.
    """
    # Normalize
    pred_norm = F.normalize(pred, dim=-1)
    target_norm = F.normalize(target, dim=-1)

    # Cosine similarity (want to maximize, so negate)
    cos_sim = (pred_norm * target_norm).sum(dim=-1)

    # Loss = 1 - cos_sim
    return (1 - cos_sim).mean()


def contrastive_level_loss(
    anchor: torch.Tensor,
    positive: torch.Tensor,
    temperature: float = 0.07,
) -> torch.Tensor:
    """InfoNCE contrastive loss for discriminative Matryoshka.

    Uses other batch samples as negatives.
    """
    B = anchor.shape[0]
    if B < 2:
        # Need at least 2 samples for contrastive
        return torch.tensor(0.0, device=anchor.device)

    # Normalize
    anchor = F.normalize(anchor, dim=-1)
    positive = F.normalize(positive, dim=-1)

    # Similarity matrix [B, B]
    sim_matrix = anchor @ positive.T / temperature

    # Labels: diagonal is positive
    labels = torch.arange(B, device=anchor.device)

    # Cross entropy (InfoNCE)
    loss = F.cross_entropy(sim_matrix, labels)

    return loss


# =============================================================================
# MATRYOSHKA LOSS MODULE
# =============================================================================


class MatryoshkaLoss(nn.Module):
    """Matryoshka representation learning loss for exceptional hierarchy.

    USAGE:
    =====
    loss_module = MatryoshkaLoss(config)

    # During training:
    z_bulk = encoder(x)  # [B, bulk_dim]
    target = encoder(x_target)  # [B, bulk_dim] or task-specific target

    loss, info = loss_module(z_bulk, target)

    # info contains per-level losses for monitoring

    ADAPTIVE INFERENCE:
    ==================
    At inference, use projections for elastic computation:

    z_small = loss_module.project(z_bulk, dim=52)  # F₄ level
    z_tiny = loss_module.project(z_bulk, dim=14)   # G₂ level (most compressed)
    """

    def __init__(self, config: MatryoshkaLossConfig | None = None):
        super().__init__()
        self.config = config or MatryoshkaLossConfig()

        # Projection layers
        self.projection = ExceptionalProjection(self.config)

        # Learnable weights (for "learned" strategy)
        if self.config.weight_strategy == "learned" and self.config.nesting_dims is not None:
            self.log_weights = nn.Parameter(torch.zeros(len(self.config.nesting_dims)))

        # Select loss function
        self._loss_fns = {
            "mse": mse_level_loss,
            "cosine": cosine_level_loss,
        }

        # Precompute static weights
        self._static_weights = self._compute_static_weights()

        if self.config.nesting_dims is not None:
            logger.debug("MatryoshkaLoss: %d levels", len(self.config.nesting_dims))

    def _compute_static_weights(self) -> torch.Tensor:
        """Compute static weights based on strategy."""
        if self.config.nesting_dims is None:
            return torch.ones(0)

        K = len(self.config.nesting_dims)

        if self.config.weight_strategy == "uniform":
            weights = torch.ones(K)
        elif self.config.weight_strategy == "exponential":
            # More weight on smaller dimensions
            weights = torch.tensor([self.config.alpha**k for k in range(K)])
        elif self.config.weight_strategy == "inverse":
            # Weight inversely proportional to dimension
            dims = torch.tensor(self.config.nesting_dims, dtype=torch.float)
            weights = 1.0 / dims
        else:
            # For "learned", return uniform (actual weights computed in forward)
            weights = torch.ones(K)

        # Apply minimum weight
        weights = torch.clamp(weights, min=self.config.min_weight)

        # Normalize if requested
        if self.config.normalize_weights:
            weights = weights / weights.sum()

        return weights

    def get_weights(self) -> torch.Tensor:
        """Get current level weights.

        Returns:
            [K] weight tensor
        """
        if self.config.weight_strategy == "learned":
            weights = F.softmax(self.log_weights, dim=0)
            weights = torch.clamp(weights, min=self.config.min_weight)
            if self.config.normalize_weights:
                weights = weights / weights.sum()
            return weights
        return self._static_weights.to(next(self.parameters()).device)

    def project(self, x: torch.Tensor, dim: int) -> torch.Tensor:
        """Project to specific dimension level.

        Args:
            x: [B, bulk_dim] input
            dim: Target dimension (must be in nesting_dims)

        Returns:
            [B, dim] projected representation
        """
        if self.config.nesting_dims is None or dim not in self.config.nesting_dims:
            raise ValueError(f"dim={dim} not in nesting_dims={self.config.nesting_dims}")

        projections = self.projection(x)
        return projections[dim]

    def forward(
        self,
        z: torch.Tensor,
        target: torch.Tensor | None = None,
        task_fn: Callable[[torch.Tensor], torch.Tensor] | None = None,
    ) -> tuple[torch.Tensor, dict[str, torch.Tensor]]:
        """Compute Matryoshka loss across all nesting levels.

        Args:
            z: [B, bulk_dim] encoded representation
            target: [B, bulk_dim] target for reconstruction/similarity
                    OR task-specific targets matching task_fn output
            task_fn: Optional task head (called on each projection)
                    If provided, target should match task_fn output

        Returns:
            Tuple of (total_loss, info_dict)
        """
        z.shape[0]
        device = z.device

        # Get projections at all levels
        projections = self.projection(z)

        # If target provided, project it too
        target_projections = None
        if target is not None and target.shape[-1] == self.config.bulk_dim:
            target_projections = self.projection(target)

        # Compute loss at each level
        weights = self.get_weights().to(device)
        level_losses: dict[str, torch.Tensor] = {}
        total_loss = torch.tensor(0.0, device=device)

        if self.config.nesting_dims is None:
            return total_loss, {"total_loss": total_loss}

        for k, dim in enumerate(self.config.nesting_dims):
            z_k = projections[dim]

            if task_fn is not None:
                # Apply task head and compute task loss
                pred_k = task_fn(z_k)
                loss_k = (
                    F.cross_entropy(pred_k, target) if target is not None else torch.tensor(0.0)
                )
            elif target_projections is not None:
                # Reconstruction/similarity to target at same level
                target_k = target_projections[dim]

                if self.config.level_loss == "contrastive":
                    loss_k = contrastive_level_loss(z_k, target_k, self.config.temperature)
                else:
                    loss_fn = self._loss_fns[self.config.level_loss]
                    loss_k = loss_fn(z_k, target_k)
            else:
                # Self-supervised: compare to larger prefix (hierarchical)
                if self.config.nesting_dims is not None and k < len(self.config.nesting_dims) - 1:
                    # Get next larger level
                    next_dim = self.config.nesting_dims[k + 1]
                    z_next = projections[next_dim]

                    # Project next level down to current (should match)
                    if next_dim > dim:
                        proj_key = str(dim)
                        if proj_key in self.projection.projections:
                            z_next_proj = self.projection.projections[proj_key](z_next)
                            loss_k = F.mse_loss(z_k, z_next_proj.detach())
                        else:
                            loss_k = torch.tensor(0.0, device=device)
                    else:
                        loss_k = torch.tensor(0.0, device=device)
                else:
                    loss_k = torch.tensor(0.0, device=device)

            level_losses[f"loss_d{dim}"] = loss_k
            total_loss = total_loss + weights[k] * loss_k

        # Orthogonality regularization
        orth_loss = self.projection.orthogonality_loss()
        total_loss = total_loss + 0.01 * orth_loss

        # Hierarchical KL (optional)
        kl_loss = torch.tensor(0.0, device=device)
        if self.config.use_hierarchical_kl and len(projections) > 1:
            kl_loss = self._hierarchical_kl(projections)
            total_loss = total_loss + self.config.kl_weight * kl_loss

        info = {
            **level_losses,
            "total_loss": total_loss,
            "orthogonality_loss": orth_loss,
            "hierarchical_kl": kl_loss,
            "weights": weights,
        }

        return total_loss, info

    def _hierarchical_kl(self, projections: dict[int, torch.Tensor]) -> torch.Tensor:
        """Compute hierarchical KL divergence.

        Ensures smaller prefixes are consistent with larger prefixes.
        Uses KL[q(z_k|z_{k+1}) || p(z_k)] where p is standard normal.
        """
        dims = sorted(projections.keys())
        if len(dims) < 2:
            return torch.tensor(0.0)

        total_kl = torch.tensor(0.0, device=projections[dims[0]].device)

        for i in range(len(dims) - 1):
            z_small = projections[dims[i]]
            z_large = projections[dims[i + 1]]

            # Approximate KL as variance mismatch
            # (Assumes Gaussian with unit variance prior)
            # NOTE: Use unbiased=False to avoid NaN gradients when batch_size=1
            var_small = z_small.var(dim=0, unbiased=False)
            var_large = (
                z_large[:, : dims[i]].var(dim=0, unbiased=False)
                if dims[i] < dims[i + 1]
                else z_large.var(dim=0, unbiased=False)
            )

            # KL component (simplified)
            kl_k = F.mse_loss(var_small, var_large)
            total_kl = total_kl + kl_k

        return total_kl / (len(dims) - 1)

    def get_elastic_representation(
        self,
        z: torch.Tensor,
        target_dim: int | None = None,
        complexity: float | None = None,
    ) -> torch.Tensor:
        """Get representation at appropriate dimension.

        Args:
            z: [B, bulk_dim] encoded representation
            target_dim: Explicit target dimension (from nesting_dims)
            complexity: Estimated input complexity [0, 1]
                       Low complexity → use smaller dimension

        Returns:
            Projected representation at selected dimension
        """
        if target_dim is not None:
            return self.project(z, target_dim)

        if complexity is not None:
            # Map complexity to dimension index
            if self.config.nesting_dims is None:
                return z
            K = len(self.config.nesting_dims)
            k = int(complexity * (K - 1))
            k = max(0, min(k, K - 1))
            dim = self.config.nesting_dims[k]
            return self.project(z, dim)

        # Default: return full representation
        return z


# =============================================================================
# FACTORY
# =============================================================================


def create_matryoshka_loss(
    bulk_dim: int | None = None,
    weight_strategy: Literal["uniform", "exponential", "inverse", "learned"] = "exponential",
    level_loss: Literal["mse", "cosine", "contrastive"] = "mse",
) -> MatryoshkaLoss:
    """Create Matryoshka loss module.

    Args:
        bulk_dim: Bulk dimension (default from KAGAMI_BULK_DIM)
        weight_strategy: Weight strategy for levels
        level_loss: Loss function per level

    Returns:
        Configured MatryoshkaLoss
    """
    config = MatryoshkaLossConfig(
        bulk_dim=bulk_dim,
        weight_strategy=weight_strategy,
        level_loss=level_loss,
    )
    return MatryoshkaLoss(config)


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "ExceptionalProjection",
    "MatryoshkaLoss",
    "MatryoshkaLossConfig",
    "create_matryoshka_loss",
]
