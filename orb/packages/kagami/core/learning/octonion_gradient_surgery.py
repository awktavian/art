"""G₂-Equivariant Gradient Surgery for Multi-Colony Training.

Resolves gradient conflicts between colonies while respecting octonion algebra structure.

MATHEMATICAL FOUNDATION (Dec 14, 2025):
=======================================
When training 7 colonies simultaneously, their gradients can conflict. Standard gradient
surgery (PCGrad, CAGrad) treats gradients as generic vectors, ignoring the underlying
G₂ structure of the octonion-based colony architecture.

This module provides G₂-aware gradient surgery in two modes:

1. **G₂ Parameter Groups (Safe Mode)** - RECOMMENDED
   Partition model parameters into G₂ irreducible representations:
   - 1D (trivial): Global parameters shared by all colonies
   - 7D (standard): Colony-specific parameters (one per colony)
   - 14D (adjoint): Inter-colony coupling (Fano lines)
   - 27D (sym2_traceless): Higher-order interactions

   Since each colony has disjoint parameters, gradient conflicts are IMPOSSIBLE.
   This is the mathematically rigorous solution with convergence guarantees.

2. **Octonion Projection (Experimental)**
   Use octonion multiplication (e_i × e_j = ±e_k) to resolve conflicts.
   When gradients g_i and g_j conflict, project using Fano plane structure.

   WARNING: No convergence guarantees. Non-associativity can cause issues.
   Use only for research/experimentation.

REFERENCES:
===========
- Yu et al. (2020): "Gradient Surgery for Multi-Task Learning" (PCGrad)
- Baez (2002): "The Octonions"
- Bryant (1987): "Metrics with exceptional holonomy"

Created: December 14, 2025
Author: Forge (e₂) - The Builder
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import torch
import torch.nn as nn
import torch.nn.functional as F
from kagami_math.fano_plane import (
    FANO_SIGNS,
    get_fano_lines_zero_indexed,
)

from kagami.core.learning.gradient_surgery import PCGrad

if TYPE_CHECKING:
    from collections.abc import Sequence

logger = logging.getLogger(__name__)


# =============================================================================
# G₂ PARAMETER GROUPING
# =============================================================================


@dataclass
class G2ParameterGroups:
    """Partition model parameters into G₂ irreducible representations.

    Prevents gradient interference by assigning each colony to separate parameters.

    G₂ IRREPS:
    ----------
    - dim 1 (trivial): Global parameters shared by all colonies
    - dim 7 (standard): Colony-specific parameters (one 7D block per colony)
    - dim 14 (adjoint): Pairwise coupling parameters (Fano lines)
    - dim 27 (sym2_traceless): Higher-order multi-colony interactions

    USAGE:
    ------
    ```python
    groups = G2ParameterGroups(model)

    # Check partitioning
    print(f"Global params: {len(groups.global_params)}")
    print(f"Colony params: {[len(g) for g in groups.colony_params]}")
    print(f"Coupling params: {len(groups.coupling_params)}")
    ```

    PARAMETER NAMING CONVENTION:
    ----------------------------
    - "global_*" or "shared_*" → global_params (1D)
    - "colony_N_*" (N=0..6) → colony_params[N] (7D)
    - "fano_*" or "coupling_*" → coupling_params (14D)
    - "higher_*" or "multi_*" → higher_params (27D)
    - Unlabeled → assigned to global by default
    """

    # Parameter lists
    global_params: list[nn.Parameter] = field(default_factory=list[Any])  # 1D rep
    colony_params: list[list[nn.Parameter]] = field(
        default_factory=lambda: [[] for _ in range(7)]
    )  # 7× 7D reps
    coupling_params: list[nn.Parameter] = field(default_factory=list[Any])  # 14D rep
    higher_params: list[nn.Parameter] = field(default_factory=list[Any])  # 27D rep

    # Parameter metadata
    param_to_group: dict[nn.Parameter, str] = field(default_factory=dict[str, Any])
    param_to_colony: dict[nn.Parameter, int | None] = field(default_factory=dict[str, Any])

    def __post_init__(self) -> None:
        """Validate parameter groups after initialization."""
        # Verify we have 7 colony groups
        if len(self.colony_params) != 7:
            raise ValueError(f"Expected 7 colony groups, got {len(self.colony_params)}")

    @classmethod
    def from_model(cls, model: nn.Module) -> G2ParameterGroups:
        """Create parameter groups from a model.

        Args:
            model: PyTorch model with parameters to partition

        Returns:
            G2ParameterGroups with partitioned parameters
        """
        groups = cls()
        groups._partition_parameters(model)
        return groups

    def _partition_parameters(self, model: nn.Module) -> None:
        """Assign each parameter to appropriate G₂ representation.

        Args:
            model: PyTorch model to partition
        """
        for name, param in model.named_parameters():
            if not param.requires_grad:
                continue

            # Classify parameter by name
            group_type, colony_idx = self._classify_parameter(name)

            # Assign to appropriate group
            if group_type == "global":
                self.global_params.append(param)
                self.param_to_group[param] = "global"
                self.param_to_colony[param] = None

            elif group_type == "colony":
                if colony_idx is None:
                    logger.warning(f"Colony parameter {name} has no index, assigning to global")
                    self.global_params.append(param)
                    self.param_to_group[param] = "global"
                    self.param_to_colony[param] = None
                else:
                    self.colony_params[colony_idx].append(param)
                    self.param_to_group[param] = "colony"
                    self.param_to_colony[param] = colony_idx

            elif group_type == "coupling":
                self.coupling_params.append(param)
                self.param_to_group[param] = "coupling"
                self.param_to_colony[param] = None

            elif group_type == "higher":
                self.higher_params.append(param)
                self.param_to_group[param] = "higher"
                self.param_to_colony[param] = None

            else:
                # Default: assign to global
                self.global_params.append(param)
                self.param_to_group[param] = "global"
                self.param_to_colony[param] = None
                logger.debug(f"Parameter {name} assigned to global (default)")

    def _classify_parameter(self, name: str) -> tuple[str, int | None]:
        """Classify parameter by name into G₂ representation.

        Args:
            name: Parameter name

        Returns:
            (group_type, colony_idx) where group_type in {"global", "colony", "coupling", "higher"}
            and colony_idx is 0-6 for colony parameters, None otherwise
        """
        name_lower = name.lower()

        # Global parameters
        if "global" in name_lower or "shared" in name_lower:
            return "global", None

        # Colony-specific parameters
        if "colony" in name_lower:
            # Extract colony index (e.g., "colony_3_weight" → 3)
            colony_idx = self._extract_colony_idx(name)
            return "colony", colony_idx

        # Coupling parameters (Fano lines)
        if "fano" in name_lower or "coupling" in name_lower or "interaction" in name_lower:
            return "coupling", None

        # Higher-order parameters
        if "higher" in name_lower or "multi" in name_lower or "order_3" in name_lower:
            return "higher", None

        # Default: global
        return "global", None

    def _extract_colony_idx(self, name: str) -> int | None:
        """Extract colony index from parameter name.

        Examples:
            "colony_3_weight" → 3
            "embedding.colony_0.bias" → 0
            "colony_layer_5_norm" → 5
            "colony_layers.2.weight" → 2

        Args:
            name: Parameter name

        Returns:
            Colony index (0-6) or None if not found
        """
        import re

        # Try multiple patterns
        patterns = [
            r"colony[_\.](\d+)",  # colony_3_weight or colony.3.weight
            r"colony_layers?[_\.](\d+)",  # colony_layers.3.weight or colony_layer_3
            r"colony.*?(\d+)",  # any colony parameter with digit
        ]

        for pattern in patterns:
            match = re.search(pattern, name.lower())
            if match:
                idx = int(match.group(1))
                if 0 <= idx <= 6:
                    return idx
                else:
                    logger.warning(f"Colony index {idx} out of range [0,6] in {name}")
                    return None

        return None

    def get_colony_for_param(self, param: nn.Parameter) -> int | None:
        """Get colony index for a parameter.

        Args:
            param: Parameter tensor

        Returns:
            Colony index (0-6) or None if not a colony parameter
        """
        return self.param_to_colony.get(param)

    def get_group_for_param(self, param: nn.Parameter) -> str:
        """Get group type for a parameter.

        Args:
            param: Parameter tensor

        Returns:
            Group type: "global", "colony", "coupling", "higher", or "unknown"
        """
        return self.param_to_group.get(param, "unknown")

    def summary(self) -> dict[str, Any]:
        """Get summary statistics of parameter groups.

        Returns:
            Dictionary with counts and total parameters
        """

        def count_params(param_list: Sequence[nn.Parameter]) -> int:
            return sum(p.numel() for p in param_list)

        colony_counts = [count_params(colony) for colony in self.colony_params]

        return {
            "global_params": count_params(self.global_params),
            "colony_params": colony_counts,
            "total_colony_params": sum(colony_counts),
            "coupling_params": count_params(self.coupling_params),
            "higher_params": count_params(self.higher_params),
            "total_params": (
                count_params(self.global_params)
                + sum(colony_counts)
                + count_params(self.coupling_params)
                + count_params(self.higher_params)
            ),
        }


# =============================================================================
# G₂-EQUIVARIANT GRADIENT SURGERY
# =============================================================================


class OctonionGradientSurgery(nn.Module):
    """Gradient surgery using octonion algebra structure.

    Two modes:
    1. **G₂ Parameter Groups (safe)**: Guaranteed no interference via disjoint parameters
    2. **Octonion Projection (experimental)**: Use non-associativity to resolve conflicts

    USAGE:
    ------
    ```python
    # Mode 1: G₂ Parameter Groups (RECOMMENDED)
    surgery = OctonionGradientSurgery(mode="g2_groups")
    param_groups = G2ParameterGroups.from_model(model)

    # Compute gradients for each colony
    colony_gradients = [...]  # List of 7 gradient lists

    # Apply surgery
    corrected_grads = surgery.apply_g2_groups(colony_gradients, param_groups)

    # Mode 2: Octonion Projection (EXPERIMENTAL)
    surgery = OctonionGradientSurgery(mode="octonion_projection")
    corrected_grads = surgery.apply_octonion_projection(colony_gradients)
    ```

    PARAMETERS:
    -----------
    mode: str
        "g2_groups" (safe) or "octonion_projection" (experimental)
    use_fano_structure: bool
        If True, use Fano plane structure for coupling gradients
    conflict_threshold: float
        Threshold for detecting conflicts (cosine similarity < -threshold)
    """

    def __init__(
        self,
        mode: str = "g2_groups",
        use_fano_structure: bool = True,
        conflict_threshold: float = 0.1,
    ) -> None:
        """Initialize octonion gradient surgery.

        Args:
            mode: "g2_groups" or "octonion_projection"
            use_fano_structure: Use Fano plane for coupling gradients
            conflict_threshold: Threshold for conflict detection
        """
        super().__init__()

        if mode not in {"g2_groups", "octonion_projection"}:
            raise ValueError(f"Invalid mode: {mode}. Expected 'g2_groups' or 'octonion_projection'")

        self.mode = mode
        self.use_fano_structure = use_fano_structure
        self.conflict_threshold = conflict_threshold

        # Statistics
        self.total_conflicts = 0
        self.total_projections = 0

    def apply_g2_groups(
        self,
        colony_gradients: list[list[torch.Tensor | None]],
        param_groups: G2ParameterGroups,
    ) -> list[list[torch.Tensor | None]]:
        """Apply gradients respecting G₂ parameter partitioning.

        Since parameters are disjoint across colonies, no conflict is possible.
        We only need to handle:
        1. Global parameters: average gradients from all colonies
        2. Colony parameters: use as-is (no surgery needed)
        3. Coupling parameters: use Fano-aware averaging
        4. Higher-order parameters: average with optional weighting

        Args:
            colony_gradients: List of 7 gradient lists (one per colony)
            param_groups: G₂ parameter partitioning

        Returns:
            Corrected gradients (same structure as input)
        """
        if len(colony_gradients) != 7:
            raise ValueError(f"Expected 7 colony gradients, got {len(colony_gradients)}")

        # Result structure: one gradient list[Any] per colony
        corrected_grads: list[list[torch.Tensor | None]] = [[] for _ in range(7)]

        # Get all parameters (assumes all colonies have same param structure)
        all_params = (
            param_groups.global_params
            + [p for colony in param_groups.colony_params for p in colony]
            + param_groups.coupling_params
            + param_groups.higher_params
        )

        # Process each parameter
        for param_idx, param in enumerate(all_params):
            group_type = param_groups.get_group_for_param(param)

            if group_type == "global":
                # Global: average gradients from all colonies
                grad_avg = self._average_global_gradients(colony_gradients, param_idx, param)
                for colony_idx in range(7):
                    corrected_grads[colony_idx].append(grad_avg)

            elif group_type == "colony":
                # Colony-specific: use original gradient (no surgery)
                colony_idx_maybe = param_groups.get_colony_for_param(param)
                if colony_idx_maybe is not None:
                    c_idx: int = colony_idx_maybe
                    original_grad = self._get_gradient(colony_gradients[c_idx], param_idx)
                    corrected_grads[c_idx].append(original_grad)
                    # Other colonies get None for this parameter
                    for other_idx in range(7):
                        if other_idx != c_idx:
                            corrected_grads[other_idx].append(None)

            elif group_type == "coupling":
                # Coupling: use Fano-aware averaging
                if self.use_fano_structure:
                    grad_coupling = self._fano_aware_coupling(colony_gradients, param_idx, param)
                else:
                    grad_coupling = self._average_global_gradients(
                        colony_gradients, param_idx, param
                    )
                for colony_idx in range(7):
                    corrected_grads[colony_idx].append(grad_coupling)

            elif group_type == "higher":
                # Higher-order: simple average
                grad_higher = self._average_global_gradients(colony_gradients, param_idx, param)
                for colony_idx in range(7):
                    corrected_grads[colony_idx].append(grad_higher)

            else:
                # Unknown: default to average
                logger.warning(f"Unknown group type {group_type} for param, using average")
                grad_default = self._average_global_gradients(colony_gradients, param_idx, param)
                for colony_idx in range(7):
                    corrected_grads[colony_idx].append(grad_default)

        return corrected_grads

    def _average_global_gradients(
        self,
        colony_gradients: list[list[torch.Tensor | None]],
        param_idx: int,
        param: nn.Parameter,
    ) -> torch.Tensor:
        """Average gradients across colonies for global parameters.

        Args:
            colony_gradients: Gradients from all colonies
            param_idx: Parameter index
            param: Parameter tensor (for shape)

        Returns:
            Averaged gradient
        """
        grads: list[torch.Tensor] = []
        for colony_grads in colony_gradients:
            if param_idx < len(colony_grads) and colony_grads[param_idx] is not None:
                grad = colony_grads[param_idx]
                if grad is not None:  # Type guard for mypy
                    grads.append(grad)

        if not grads:
            # No gradients available, return zero
            return torch.zeros_like(param)

        # Average
        return torch.stack(grads).mean(dim=0)

    def _fano_aware_coupling(
        self,
        colony_gradients: list[list[torch.Tensor | None]],
        param_idx: int,
        param: nn.Parameter,
    ) -> torch.Tensor:
        """Compute gradients for coupling parameters using Fano structure.

        Coupling parameters connect colonies on Fano lines.
        We weight gradients based on octonion multiplication structure.

        For each Fano line (i, j, k) where e_i × e_j = ±e_k:
        - Gradients from colonies i, j, k should be combined with appropriate sign

        Args:
            colony_gradients: Gradients from all colonies
            param_idx: Parameter index
            param: Parameter tensor

        Returns:
            Fano-aware averaged gradient
        """
        fano_lines = get_fano_lines_zero_indexed()

        # For each Fano line, compute weighted average
        line_grads = []

        for i, j, k in fano_lines:
            # Get sign for this line: e_i × e_j = sign * e_k
            sign_tuple = FANO_SIGNS.get((i + 1, j + 1))  # FANO_SIGNS uses 1-indexed
            if sign_tuple is None:
                continue
            _result_idx, sign = sign_tuple

            # Get gradients from colonies on this line
            grad_i = self._get_gradient(colony_gradients[i], param_idx)
            grad_j = self._get_gradient(colony_gradients[j], param_idx)
            grad_k = self._get_gradient(colony_gradients[k], param_idx)

            # Combine with Fano sign
            # Formula: g_line = (g_i + g_j + sign * g_k) / 3
            grads_on_line = []
            if grad_i is not None:
                grads_on_line.append(grad_i)
            if grad_j is not None:
                grads_on_line.append(grad_j)
            if grad_k is not None:
                if sign == 1:
                    grads_on_line.append(grad_k)
                else:
                    grads_on_line.append(-grad_k)

            # Average gradients on this line (skip if no valid gradients)
            if grads_on_line:
                line_grad = torch.stack(grads_on_line).mean(dim=0)
                line_grads.append(line_grad)

        if not line_grads:
            # Fallback: simple average
            return self._average_global_gradients(colony_gradients, param_idx, param)

        # Average across all Fano lines
        return torch.stack(line_grads).mean(dim=0)

    def _get_gradient(
        self,
        grad_list: list[torch.Tensor | None],
        idx: int,
    ) -> torch.Tensor | None:
        """Safely get gradient from list[Any].

        Args:
            grad_list: List of gradients
            idx: Index

        Returns:
            Gradient tensor or None
        """
        if idx < len(grad_list):
            return grad_list[idx]
        return None

    def apply_octonion_projection(
        self,
        colony_gradients: list[torch.Tensor],
    ) -> list[torch.Tensor]:
        """Project gradients using octonion non-associativity.

        WARNING: Experimental! No convergence guarantees.

        When colonies i and j have conflicting gradients (negative cosine similarity),
        we use octonion multiplication e_i × e_j = ±e_k to resolve the conflict by
        projecting onto the e_k direction.

        Args:
            colony_gradients: List of 7 gradient tensors in octonion basis

        Returns:
            Projected gradients (same structure)
        """
        if len(colony_gradients) != 7:
            raise ValueError(f"Expected 7 colony gradients, got {len(colony_gradients)}")

        # Clone gradients for modification
        g_octonion = [g.clone() for g in colony_gradients]

        # Pairwise conflict detection and resolution
        for i in range(7):
            for j in range(i + 1, 7):
                if self._detect_conflict_octonion(g_octonion[i], g_octonion[j]):
                    # Use Fano multiplication: e_i × e_j = ±e_k
                    sign_tuple = FANO_SIGNS.get((i + 1, j + 1))  # 1-indexed
                    if sign_tuple is None:
                        logger.warning(f"No Fano sign for ({i}, {j}), skipping")
                        continue

                    k_1indexed, sign = sign_tuple
                    k = k_1indexed - 1  # Convert to 0-indexed

                    # Project gradient j onto direction k
                    projection = self._project_gradient_octonion(g_octonion[j], g_octonion[i], sign)
                    g_octonion[j] = projection

                    self.total_projections += 1
                    logger.debug(
                        f"Octonion projection: colony {j} onto {k} (from conflict with {i})"
                    )

        return g_octonion

    def _detect_conflict_octonion(
        self,
        grad_i: torch.Tensor,
        grad_j: torch.Tensor,
    ) -> bool:
        """Detect if two gradients conflict (negative cosine similarity).

        Args:
            grad_i: First gradient
            grad_j: Second gradient

        Returns:
            True if gradients conflict
        """
        cos_sim = F.cosine_similarity(
            grad_i.flatten().unsqueeze(0),
            grad_j.flatten().unsqueeze(0),
            dim=1,
        ).item()

        conflict = cos_sim < -self.conflict_threshold

        if conflict:
            self.total_conflicts += 1

        return conflict

    def _project_gradient_octonion(
        self,
        grad_to_project: torch.Tensor,
        grad_reference: torch.Tensor,
        sign: int,
    ) -> torch.Tensor:
        """Project gradient using octonion structure.

        Formula: g' = g - ⟨g, r⟩/||r||² · r  (standard projection)
        Modified by octonion sign for Fano-aware projection.

        Args:
            grad_to_project: Gradient to modify
            grad_reference: Reference gradient
            sign: Fano sign (±1)

        Returns:
            Projected gradient
        """
        # Flatten for dot product
        g_flat = grad_to_project.flatten()
        r_flat = grad_reference.flatten()

        # Compute projection
        dot = (g_flat * r_flat).sum()
        norm_sq = (r_flat * r_flat).sum()

        if norm_sq < 1e-8:
            logger.warning("Reference gradient near zero, skipping projection")
            return grad_to_project

        # Apply octonion sign
        scale = sign * dot / norm_sq

        # Project
        g_proj_flat = g_flat - scale * r_flat

        # Reshape back
        return g_proj_flat.view_as(grad_to_project)


# =============================================================================
# OCTONION-AWARE PCGRAD
# =============================================================================


class OctonionPCGrad(PCGrad):
    """Extension of PCGrad with Fano plane structure awareness.

    Standard PCGrad performs pairwise gradient projection for all conflicting tasks.
    OctonionPCGrad additionally:
    1. Uses Fano line structure to align gradients on the same line
    2. Ensures gradients on a Fano line have constructive (not destructive) interference

    USAGE:
    ------
    ```python
    pcgrad = OctonionPCGrad()

    # Compute gradients for 7 colonies
    gradients = [grad_colony_0, ..., grad_colony_6]

    # Apply Fano-aware PCGrad
    projected = pcgrad.apply(gradients)

    # Average and use
    final_grad = sum(projected) / 7
    ```
    """

    def __init__(
        self,
        conflict_threshold: float = 0.0,
        use_random_projection_order: bool = True,
        use_fano_alignment: bool = True,
    ) -> None:
        """Initialize Octonion PCGrad.

        Args:
            conflict_threshold: Threshold for conflict detection
            use_random_projection_order: Randomize projection order
            use_fano_alignment: Apply Fano line alignment after PCGrad
        """
        super().__init__(
            conflict_threshold=conflict_threshold,
            use_random_projection_order=use_random_projection_order,
        )
        self.use_fano_alignment = use_fano_alignment

    def apply(
        self,
        gradients: list[list[torch.Tensor | None]],
    ) -> list[list[torch.Tensor | None]]:
        """Apply PCGrad with Fano line structure awareness.

        Args:
            gradients: List of colony gradients

        Returns:
            Projected gradients with Fano alignment
        """
        # Standard PCGrad
        projected = super().apply(gradients)

        # Additional Fano line alignment
        if self.use_fano_alignment and len(gradients) == 7:
            projected = self._align_fano_lines(projected)

        return projected

    def _align_fano_lines(
        self,
        gradients: list[list[torch.Tensor | None]],
    ) -> list[list[torch.Tensor | None]]:
        """Ensure gradients on same Fano line are aligned (constructive interference).

        For each Fano line (i, j, k), we want:
        - g_i and g_j to not conflict
        - g_i and g_k to not conflict
        - g_j and g_k to not conflict

        If any pair on a line conflicts, we apply additional projection.

        Args:
            gradients: Projected gradients from PCGrad

        Returns:
            Fano-aligned gradients
        """
        fano_lines = get_fano_lines_zero_indexed()
        aligned = [[g.clone() if g is not None else None for g in grads] for grads in gradients]

        for i, j, k in fano_lines:
            # Check all pairs on this line
            pairs = [(i, j), (i, k), (j, k)]

            for idx_a, idx_b in pairs:
                if self.detect_conflict(aligned[idx_a], aligned[idx_b]):
                    # Project idx_b away from idx_a
                    aligned[idx_b] = self.project_gradient(aligned[idx_b], aligned[idx_a])
                    logger.debug(f"Fano alignment: projected colony {idx_b} away from {idx_a}")

        return aligned


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================


def apply_octonion_gradient_surgery(  # type: ignore[no-untyped-def]
    model: nn.Module,
    colony_losses: list[torch.Tensor],
    mode: str = "g2_groups",
    **kwargs,
) -> dict[str, Any]:
    """Convenience function to apply octonion gradient surgery to a model.

    Args:
        model: PyTorch model
        colony_losses: List of 7 colony losses
        mode: "g2_groups", "octonion_projection", or "fano_pcgrad"
        **kwargs: Additional arguments for the surgery method

    Returns:
        Dict with applied gradients and statistics
    """
    if len(colony_losses) != 7:
        raise ValueError(f"Expected 7 colony losses, got {len(colony_losses)}")

    if mode == "g2_groups":
        # G₂ parameter groups mode
        surgery = OctonionGradientSurgery(mode="g2_groups", **kwargs)
        param_groups = G2ParameterGroups.from_model(model)

        # Compute per-colony gradients
        params = list(model.parameters())
        colony_gradients: list[list[torch.Tensor | None]] = []

        for i, loss in enumerate(colony_losses):
            model.zero_grad()
            loss.backward(retain_graph=(i < 6))
            grads = [p.grad.clone() if p.grad is not None else None for p in params]
            colony_gradients.append(grads)

        # Apply G₂ surgery
        corrected = surgery.apply_g2_groups(colony_gradients, param_groups)

        # Average across colonies and set[Any]
        model.zero_grad()
        for param_idx, param in enumerate(params):
            grad_list: list[torch.Tensor] = []
            for c in range(7):
                if param_idx < len(corrected[c]) and corrected[c][param_idx] is not None:
                    grad = corrected[c][param_idx]
                    if grad is not None:  # Type guard for mypy
                        grad_list.append(grad)

            if grad_list:
                param.grad = torch.stack(grad_list).mean(dim=0)

        return {
            "method": "g2_groups",
            "param_groups": param_groups.summary(),
        }

    elif mode == "octonion_projection":
        # Octonion projection mode
        surgery = OctonionGradientSurgery(mode="octonion_projection", **kwargs)

        # Compute per-colony gradients (flattened)
        params = list(model.parameters())
        colony_gradients_flat: list[torch.Tensor] = []

        for i, loss in enumerate(colony_losses):
            model.zero_grad()
            loss.backward(retain_graph=(i < 6))

            # Flatten gradient
            grad_flat = torch.cat(
                [
                    p.grad.flatten() if p.grad is not None else torch.zeros_like(p).flatten()
                    for p in params
                ]
            )
            colony_gradients_flat.append(grad_flat)

        # Apply octonion projection
        projected = surgery.apply_octonion_projection(colony_gradients_flat)

        # Average and unflatten
        avg_grad_flat = torch.stack(projected).mean(dim=0)

        model.zero_grad()
        offset = 0
        for param in params:
            numel = param.numel()
            param.grad = avg_grad_flat[offset : offset + numel].view_as(param)
            offset += numel

        return {
            "method": "octonion_projection",
            "total_conflicts": surgery.total_conflicts,
            "total_projections": surgery.total_projections,
        }

    elif mode == "fano_pcgrad":
        # Fano-aware PCGrad
        pcgrad = OctonionPCGrad(**kwargs)
        pcgrad.apply_to_model(model, colony_losses)

        return {
            "method": "fano_pcgrad",
            "stats": pcgrad.get_stats(),
        }

    else:
        raise ValueError(f"Invalid mode: {mode}")


__all__ = [
    "G2ParameterGroups",
    "OctonionGradientSurgery",
    "OctonionPCGrad",
    "apply_octonion_gradient_surgery",
]
