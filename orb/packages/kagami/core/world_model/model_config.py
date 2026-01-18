"""KagamiWorldModel state (CoreState only).

UPDATED Dec 22, 2025: KagamiWorldModelConfig DELETED - use unified_config.WorldModelConfig

CoreState is runtime state used by:
- `kagami.core.world_model.service.WorldModelService`
- `kagami.core.world_model.losses.composed.UnifiedLossModule`
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

import torch

# Import config from world_model_config (Dec 28, 2025 - breaks circular import)
from kagami.core.config.world_model_config import WorldModelConfig

logger = logging.getLogger(__name__)


# Alias for backwards compatibility
KagamiWorldModelConfig = WorldModelConfig


@dataclass
class CoreState:
    """Canonical core state passed between encode/decode/predict.

    Minimal fields required by:
    - `kagami.core.world_model.service.WorldModelService`
    - `kagami.core.world_model.losses.composed.UnifiedLossModule`

    Shapes are typically:
    - e8_code: [B, S, 8]
    - s7_phase: [B, S, 7]
    - shell_residual: [B, S, 14] (H14 / G2 coordinates)

    NEW (Dec 13, 2025): S7 phases at all hierarchy levels + Gödelian self-reference.
    """

    e8_code: torch.Tensor | None = None
    s7_phase: torch.Tensor | None = None
    shell_residual: torch.Tensor | None = None

    # Optional auxiliary fields
    domain_activations: torch.Tensor | None = None  # [B, 7, 8]
    e8_index: torch.Tensor | None = None  # [B, S] E8 weighting index
    lattice_stress: float = 0.0

    # === S7 PHASES AT ALL HIERARCHY LEVELS (Dec 13, 2025) ===
    # These enable colony coherence tracking across the full hierarchy
    s7_e8: torch.Tensor | None = None  # [B, S, 7] S7 from E8(248)
    s7_e7: torch.Tensor | None = None  # [B, S, 7] S7 from E7(133)
    s7_e6: torch.Tensor | None = None  # [B, S, 7] S7 from E6(78)
    s7_f4: torch.Tensor | None = None  # [B, S, 7] S7 from F4(52)
    s7_coherence: float = 0.0  # Cross-level phase coherence

    # === GÖDELIAN SELF-REFERENCE (Dec 13, 2025) ===
    # Unified strange loop state from GodelianSelfReference integration
    godelian_self_encoding: torch.Tensor | None = None  # [30] code(15) + weight(15)
    godelian_e8_code: torch.Tensor | None = None  # [8] E8 VQ from self-encoding
    godelian_s7_phase: torch.Tensor | None = None  # [7] S7 from self-encoding
    godelian_consistency_h: float = 1.0  # Self-consistency CBF h(x) ∈ [0,1]
    godelian_source_changed: bool = False  # Source code change detected
    godelian_modification_count: int = 0  # Number of self-modifications

    # Strange loop convergence (μ_self fixed point)
    mu_self: torch.Tensor | None = None  # [7] Current fixed point estimate
    fixed_point_distance: float = 0.0  # ||s7 - μ_self||

    # === LLM INTEGRATION (Dec 16, 2025) ===
    # Flat embedding for joint LLM-World Model training
    embedding: torch.Tensor | None = None  # [B, D] concatenated state representation

    # Metadata
    timestamp: float = 0.0
    context_hash: str = ""

    def __post_init__(self) -> None:
        """Validate CoreState consistency after initialization.

        ADDED Dec 24, 2025: Validates tensor shape consistency to catch
        silent broadcasting bugs early.
        """
        if self.timestamp == 0.0:
            self.timestamp = time.time()

        # Validate batch dimension consistency between tensors
        batch_sizes: dict[str, int] = {}

        if self.e8_code is not None:
            batch_sizes["e8_code"] = self.e8_code.shape[0]
        if self.s7_phase is not None:
            batch_sizes["s7_phase"] = self.s7_phase.shape[0]
        if self.shell_residual is not None:
            batch_sizes["shell_residual"] = self.shell_residual.shape[0]

        # Check all batch sizes match
        if len(set(batch_sizes.values())) > 1:
            logger.warning(
                f"CoreState batch size mismatch: {batch_sizes}. "
                "This may cause silent broadcasting bugs."
            )

        # Validate expected tensor dimensions
        if self.e8_code is not None and self.e8_code.shape[-1] != 8:
            logger.warning(f"CoreState.e8_code expected last dim=8, got {self.e8_code.shape[-1]}")
        if self.s7_phase is not None and self.s7_phase.shape[-1] != 7:
            logger.warning(f"CoreState.s7_phase expected last dim=7, got {self.s7_phase.shape[-1]}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "e8_code": self.e8_code,
            "s7_phase": self.s7_phase,
            "shell_residual": self.shell_residual,
            "domain_activations": self.domain_activations,
            "e8_index": self.e8_index,
            "lattice_stress": self.lattice_stress,
            "timestamp": self.timestamp,
            "context_hash": self.context_hash,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CoreState:
        return cls(**data)


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------


def get_default_config() -> WorldModelConfig:
    """Get default world model config from unified_config."""
    # Lazy import to avoid circular dependency
    from kagami.core.config.unified_config import get_kagami_config

    return get_kagami_config().world_model
