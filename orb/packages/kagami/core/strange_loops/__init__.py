"""Strange Loop Dynamics and Verification.

Implements formal framework for strange loop trajectories under self-modification
in temporal H⁷ manifold.

Based on:
- Lawvere fixed-point theorem (category theory)
- Temporal Poincaré geometry (r=time)
- Gödel incompleteness (limits on self-prediction)
- Banach fixed-point theory (convergence)
- Schmidhuber's Gödel Machine (2003)
- Gödel Agent (arXiv:2410.04444v4, 2025)

Also includes:
- UnifiedSelfModel (consolidated from self_model/ - Dec 2025)
- GodelianSelfReference (TRUE self-reference - Dec 2025)
- WorldModelStrangeLoopIntegration (unified world model integration - Dec 2025)

See docs/INDEX.md for theory + navigation.

鏡 — The mirror that can read its own reflection as code.
"""

# TRUE Gödelian self-reference (Dec 2025)
# Based on Gödel Agent paper: self-inspection + self-modification + recursive improvement
from kagami.core.strange_loops.godelian_self_reference import (
    CodeEmbedder,
    GodelianConfig,
    GodelianSelfReference,
    SelfInspector,
    SelfReferentialWeightEncoder,
    StatisticalResult,
    StatisticalValidator,
    create_godelian_self_reference,
    create_godelian_wrapper,
    enable_godelian_self_reference,
)
from kagami.core.strange_loops.trajectory_verifier import (
    StrangeLoopVerifier,
    TrajectoryPoint,
    TrajectoryVerificationResult,
    get_strange_loop_verifier,
    verify_self_pointer_computation,
)
from kagami.core.strange_loops.unified_self_model import (
    UnifiedSelfModel,
)

# World Model ⟷ Strange Loop Integration (Dec 13, 2025)
# Unified integration: S7 phases at all levels + Gödelian self-encoding + μ_self tracking
from kagami.core.strange_loops.world_model_integration import (
    WorldModelStrangeLoopIntegration,
    integrate_strange_loop,
)

__all__ = [
    "CodeEmbedder",
    # Gödelian self-reference (TRUE self-reference)
    "GodelianConfig",
    "GodelianSelfReference",
    "SelfInspector",
    "SelfReferentialWeightEncoder",
    "StatisticalResult",
    "StatisticalValidator",
    # Trajectory verification
    "StrangeLoopVerifier",
    "TrajectoryPoint",
    "TrajectoryVerificationResult",
    # Self model
    "UnifiedSelfModel",
    # World Model Integration (Dec 13, 2025)
    "WorldModelStrangeLoopIntegration",
    "create_godelian_self_reference",
    "create_godelian_wrapper",
    "enable_godelian_self_reference",
    "get_strange_loop_verifier",
    "integrate_strange_loop",
    "verify_self_pointer_computation",
]
