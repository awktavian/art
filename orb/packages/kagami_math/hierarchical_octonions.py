"""Hierarchical Octonion Composition - Nested S^7 Spaces.

Multi-scale sensory fusion via nested octonion manifolds:
- Level 0: Raw sensory octonions (7 modalities -> S^7)
- Level 1: Composed pairs (S^7 x S^7 -> S^7 via octonion product)
- Level 2: Higher-order composition (nested S^7)

Key insight: Non-associativity enables hierarchical structure.
(a * b) * c != a * (b * c) means grouping order matters!

This creates a tree of sensory compositions with geometric interpretation.
"""

import importlib
import logging
from typing import cast

import torch
import torch.nn as nn


# FIX: Lazy import to avoid circular dependency
def _get_octonion_manifold() -> None:
    """Lazy import to avoid circular dependency."""
    # Package is kagami_math, not kagami.math
    mod = importlib.import_module("kagami_math.octonions")
    return mod.OctonionManifold  # type: ignore[no-any-return]


logger = logging.getLogger(__name__)


class HierarchicalOctonionFusion(nn.Module):
    """Hierarchical fusion via nested octonion composition.

    Architecture:
    - Level 0: Individual modality octonions
    - Level 1: Pairwise compositions (learned grouping)
    - Level 2: Global composition

    Output: Single octonion on S⁷ representing full sensory state.
    """

    def __init__(
        self,
        num_modalities: int | None = None,
        num_levels: int = 3,
        learn_grouping: bool = True,
        device: str = "cpu",
        input_dim: int | None = None,  # Backwards compatibility alias
    ) -> None:
        super().__init__()

        # Handle backwards compatibility: input_dim is alias for num_modalities
        if input_dim is not None and num_modalities is None:
            num_modalities = input_dim
        elif num_modalities is None:
            num_modalities = 7  # Default

        # Validation
        if num_levels < 1:
            raise ValueError(f"num_levels must be >= 1, got {num_levels}")
        if num_modalities < 1:
            raise ValueError(f"num_modalities must be >= 1, got {num_modalities}")

        self.num_modalities = num_modalities
        self.input_dim = num_modalities  # Expose both names
        self.num_levels = num_levels
        self.device = device
        OctonionManifold = _get_octonion_manifold()  # type: ignore[func-returns-value]
        self.manifold = OctonionManifold().to(device)
        # Use ParameterList instead of ModuleList for Parameters
        self.grouping_weights: nn.ParameterList | None
        if learn_grouping:
            self.grouping_weights = nn.ParameterList(
                [
                    nn.Parameter(torch.randn(num_modalities, num_modalities))
                    for _ in range(num_levels - 1)
                ]
            )
        else:
            self.grouping_weights = None
        logger.info(f"✅ Hierarchical octonions: {num_levels} levels, {num_modalities} modalities")

    def compose_pair(self, o1: torch.Tensor, o2: torch.Tensor, weight: float = 1.0) -> torch.Tensor:
        """Compose two octonions with optional weighting.

        Args:
            o1: [B, 8]
            o2: [B, 8]
            weight: Mixing weight in [0, 1]

        Returns:
            composed: [B, 8] on S⁷
        """
        composed = self.manifold.multiply_8d(o1, o2)
        if weight < 1.0:
            composed = weight * composed + (1 - weight) * o1
        composed = self.manifold.project_to_s7(composed)
        return cast(torch.Tensor, composed)

    def forward(
        self, modality_octonions: dict[str, torch.Tensor]
    ) -> dict[str, torch.Tensor | list[list[torch.Tensor]] | dict[str, list[str]]]:
        """Hierarchical composition of modality octonions.

        Args:
            modality_octonions: Dict mapping modality name to [B, 8] octonion

        Returns:
            Dict with:
              - final: [B, 8] final composed octonion
              - intermediate: List of intermediate compositions
              - tree_structure: Composition tree for visualization
        """
        available = {k: v for k, v in modality_octonions.items() if v is not None}
        if not available:
            batch_size = 1
            zero = torch.zeros(batch_size, 8, device=self.device)
            zero[:, 0] = 1.0
            return {"final": zero, "intermediate": [], "tree_structure": {}}
        if len(available) == 1:
            single_val: torch.Tensor = next(iter(available.values()))
            single_key: str = next(iter(available.keys()))
            tree_struct: dict[str, list[str]] = {"root": [single_key]}
            result_dict: dict[
                str, torch.Tensor | list[list[torch.Tensor]] | dict[str, list[str]]
            ] = {
                "final": single_val,
                "intermediate": [],
                "tree_structure": tree_struct,
            }
            return result_dict
        current_level = list(available.values())
        current_names = list(available.keys())
        intermediate = []
        tree = {"level_0": current_names}
        for level in range(1, self.num_levels):
            if len(current_level) == 1:
                break
            next_level = []
            next_names = []
            i = 0
            while i < len(current_level):
                if i + 1 < len(current_level):
                    o1 = current_level[i]
                    o2 = current_level[i + 1]
                    composed = self.compose_pair(o1, o2)
                    next_level.append(composed)
                    next_names.append(f"({current_names[i]}⊙{current_names[i + 1]})")
                    i += 2
                else:
                    next_level.append(current_level[i])
                    next_names.append(current_names[i])
                    i += 1
            intermediate.append(next_level.copy())
            tree[f"level_{level}"] = next_names.copy()
            current_level = next_level
            current_names = next_names
        final = current_level[0] if current_level else torch.zeros(1, 8, device=self.device)
        return {"final": final, "intermediate": intermediate, "tree_structure": tree}


# === Factory Functions ===


def create_hierarchical_fusion(
    num_modalities: int = 7,
    num_levels: int = 3,
    learn_grouping: bool = True,
    device: str = "cpu",
) -> HierarchicalOctonionFusion:
    """Create a HierarchicalOctonionFusion module.

    Args:
        num_modalities: Number of input modalities (default: 7 for octonions)
        num_levels: Number of hierarchical levels
        learn_grouping: Whether to learn composition grouping
        device: Device to place module on

    Returns:
        Initialized HierarchicalOctonionFusion module
    """
    return HierarchicalOctonionFusion(
        num_modalities=num_modalities,
        num_levels=num_levels,
        learn_grouping=learn_grouping,
        device=device,
    )


def get_hierarchical_octonion(
    modality_octonions: dict[str, torch.Tensor],
    num_levels: int = 3,
    device: str = "cpu",
) -> "HierarchicalOctonionFusion":
    """Get hierarchical octonion from modality inputs.

    Args:
        modality_octonions: Dict mapping modality name to [B, 8] octonion
        num_levels: Number of hierarchical levels
        device: Device for computation

    Returns:
        HierarchicalOctonionFusion result dict with final composed octonion and tree structure
    """
    fusion = create_hierarchical_fusion(
        num_modalities=len(modality_octonions),
        num_levels=num_levels,
        learn_grouping=False,  # Use fixed grouping for inference
        device=device,
    )
    fusion.eval()

    with torch.no_grad():
        result = fusion(modality_octonions)

    return result  # type: ignore[no-any-return]
