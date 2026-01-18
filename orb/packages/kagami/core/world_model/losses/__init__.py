"""Loss computation modules for KagamiWorldModel.

This package provides unified, geometry-aware loss computation
that fully exploits the E8, Fano, and H¹⁴ × S⁷ structure.

REFACTORED (Dec 15, 2025):
- Split unified_loss.py into focused modules
- reconstruction.py: Prediction losses, symlog functions
- latent_regularization.py: IB scheduler, KL losses, CBF scaler
- prediction.py: RSSM, chaos, catastrophe, self-reference
- composed.py: UnifiedLossModule orchestrator

WIRED UP (Dec 2, 2025):
- AdaptiveIBScheduler for dynamic β scheduling
- CBFAwareLossScaler for safety-aware loss weighting
- symlog/symexp utilities from DreamerV3

MATRYOSHKA LOSS (Dec 3, 2025):
- MatryoshkaLoss for hierarchical representation learning
- Aligned with exceptional Lie algebra dimensions (G₂ → E₈)
- Enables elastic inference at any nesting level

Usage:
    from kagami.core.world_model.losses import UnifiedLossModule, LossConfig

    loss_module = UnifiedLossModule(LossConfig())
    output, metrics = model(x)
    loss_output = loss_module(output, target, metrics, core_state, safety_margin=0.8)
    loss_output.backward()

    # Matryoshka loss for nested representations:
    from kagami.core.world_model.losses import MatryoshkaLoss, MatryoshkaLossConfig

    matryoshka = MatryoshkaLoss(MatryoshkaLossConfig(bulk_dim=512))
    loss, info = matryoshka(z_bulk, target)
"""

# Composed loss orchestrator (main interface)
# DreamerV3 transforms (re-exported for convenience)
from kagami.core.world_model.dreamer_transforms import symexp, symlog
from kagami.core.world_model.losses.composed import (
    LossConfig,
    LossOutput,
    UnifiedLossModule,
    create_loss_module,
)

# Latent regularization
from kagami.core.world_model.losses.latent_regularization import (
    AdaptiveIBScheduler,
    CBFAwareLossScaler,
    fsd_loss,
)

# Matryoshka loss (existing)
from kagami.core.world_model.losses.matryoshka_loss import (
    ExceptionalProjection,
    MatryoshkaLoss,
    MatryoshkaLossConfig,
    create_matryoshka_loss,
)

# Prediction and dynamic losses
from kagami.core.world_model.losses.prediction import (
    DynamicLossComputer,
    RegularizationLossComputer,
    SelfReferenceLossComputer,
)

# Reconstruction and geometric losses
from kagami.core.world_model.losses.reconstruction import (
    GeometricLossComputer,
    free_bits_kl,
    symlog_squared_loss,
)

# unified_loss.py has been refactored into focused modules:
# - composed.py: UnifiedLossModule orchestrator
# - reconstruction.py: Geometric losses, symlog functions
# - latent_regularization.py: IB scheduler, KL losses, CBF scaler
# - prediction.py: RSSM, chaos, catastrophe, self-reference

__all__ = [
    # Latent regularization (latent_regularization.py)
    "AdaptiveIBScheduler",
    "CBFAwareLossScaler",
    # Prediction losses (prediction.py)
    "DynamicLossComputer",
    "ExceptionalProjection",
    # Geometric losses (reconstruction.py)
    "GeometricLossComputer",
    # Main interface (composed.py)
    "LossConfig",
    "LossOutput",
    "MatryoshkaLoss",
    # Matryoshka Loss (existing)
    "MatryoshkaLossConfig",
    "RegularizationLossComputer",
    "SelfReferenceLossComputer",
    "UnifiedLossModule",
    "create_loss_module",
    "create_matryoshka_loss",
    "free_bits_kl",
    "fsd_loss",
    "symexp",
    # DreamerV3 transforms
    "symlog",
    "symlog_squared_loss",
]
