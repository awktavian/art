"""Active Inference Package - Free Energy Principle Implementation.

UNIFIED ARCHITECTURE (Dec 2, 2025):
===================================
Active Inference now uses OrganismRSSM directly for trajectory prediction.
There are NO separate dynamics models - EFE uses the world model.

Core components:
- ActiveInferenceEngine: Main coordinator using RSSM states (h, z)
- ExpectedFreeEnergy: Computes G(π) via OrganismRSSM planning
- PolicyGenerator: Generates candidate policies from RSSM state
- ColonyCollaborativeCoT: Fano-routed reasoning within Markov blanket

RSSM State Space:
- h: [256] deterministic state (recurrent history)
- z: [14] stochastic state (H¹⁴ uncertainty manifold)
- Action: [8] E8 octonion action space

References:
- Friston, K. (2010). "The free-energy principle: a unified brain theory?"
- Parr, T., & Friston, K. J. (2019). "Generalised free energy and active inference"
- Da Costa et al. (2020). "Active inference on discrete state-spaces"

Created: November 29, 2025
Unified: December 2, 2025
Status: Production-ready
"""

from kagami.core.active_inference.cbf_safety_projection import (
    CBFSafetyProjection,
)
from kagami.core.active_inference.colony_collaborative_cot import (
    CATASTROPHE_REASONING,
    CollaborativeThought,
    ColonyCollaborativeCoT,
    CoTPhase,
    ReasoningTrace,
    create_collaborative_cot,
)
from kagami.core.active_inference.efe_cbf_optimizer import (
    EFECBFConfig,
    EFECBFOptimizer,
    create_efe_cbf_optimizer,
)

# EFE components from dedicated modules (REQUIRED - no fallbacks)
from kagami.core.active_inference.efe_meta_learner import (
    EFEConfig,
    EFEWeightLearner,
    EFEWeightLearnerConfig,
    ExpectedFreeEnergy,
    PerformanceMetrics,
    PerformanceSnapshot,
    UpdateRule,
    integrate_meta_learner_with_efe,
)
from kagami.core.active_inference.engine import (
    ActiveInferenceConfig,
    ActiveInferenceEngine,
    get_active_inference_engine,
    reset_active_inference_engine,
)
from kagami.core.active_inference.epistemic_value import (
    EpistemicValue,
)
from kagami.core.active_inference.organism_cot import (
    OrganismCoT,
    OrganismCoTConfig,
    OrganismMetaReasoner,
    OrganismThought,
    create_organism_cot,
    integrate_organism_cot,
)

__all__ = [
    "CATASTROPHE_REASONING",
    "ActiveInferenceConfig",
    "ActiveInferenceEngine",
    "CBFSafetyProjection",
    "CoTPhase",
    "CollaborativeThought",
    "ColonyCollaborativeCoT",
    "EFECBFConfig",
    "EFECBFOptimizer",
    "EFEConfig",
    "EFEWeightLearner",
    "EFEWeightLearnerConfig",
    "EpistemicValue",
    "ExpectedFreeEnergy",
    "OrganismCoT",
    "OrganismCoTConfig",
    "OrganismMetaReasoner",
    "OrganismThought",
    "PerformanceMetrics",
    "PerformanceSnapshot",
    "ReasoningTrace",
    "UpdateRule",
    "create_collaborative_cot",
    "create_efe_cbf_optimizer",
    "create_organism_cot",
    "get_active_inference_engine",
    "integrate_meta_learner_with_efe",
    "integrate_organism_cot",
    "reset_active_inference_engine",
]
