"""JAX/Flax implementation of OrganismRSSM world model.

This package contains a complete port of the PyTorch OrganismRSSM to JAX/Flax,
optimized for TPU training with full curriculum support.

BRICK-BY-BRICK ARCHITECTURE:
============================

PyTorch Source                          | JAX Target
----------------------------------------|-------------------------------------
unified_config.py:RSSMConfig            | config.py:OrganismRSSMConfig
losses/composed.py:LossConfig           | config.py:LossConfig
dreamer_transforms.py:*                 | transforms.py:*
rssm_core.py:BlockGRU                   | modules.py:BlockGRU
rssm_core.py:DiscreteLatentEncoder      | modules.py:DiscreteLatentEncoder
rssm_components.py:SparseFanoAttention  | modules.py:SparseFanoAttention
dreamer_transforms.py:SimNorm           | modules.py:SimNorm
rssm_core.py:*_head                     | heads.py:*Head
rssm_core.py:OrganismRSSM               | rssm.py:OrganismRSSM
losses/composed.py:UnifiedLossModule    | losses.py:compute_full_loss
training/tpu/curriculum.py              | curriculum.py:Curriculum

Usage:
    from kagami.core.training.jax import (
        OrganismRSSMConfig,
        OrganismRSSM,
        Curriculum,
        LossWeights,
        compute_full_loss,
    )

    # Create model
    config = OrganismRSSMConfig()
    model = OrganismRSSM(config)

    # Training uses distill.py or profiler.py with flax.training.train_state
"""

# Training state from flax (used by distill.py and profiler.py)
from flax.training.train_state import TrainState as OrganismTrainState

# Competence-Aware Curriculum Learning (CAMPUS 2025)
from .competence import (
    CompetenceAwareCurriculum,
    CompetenceConfig,
    CompetenceEnhancedPhase,
    CompetenceTracker,
    DifficultyAwareSampler,
)
from .config import (
    CurriculumConfig,
    CurriculumPhase,
    LossConfig,
    OrganismRSSMConfig,
    PhaseConfig,
    TrainingConfig,
)
from .curriculum import Curriculum, HyperscaleLRSchedule
from .data import (
    generate_structured_batch,
)
from .data import (
    generate_structured_batch as generate_batch,  # Alias for backward compatibility
)

# DoReMi-style Domain Reweighting (Stanford CRFM 2023)
from .doremi import (
    DomainStats,
    DoReMiConfig,
    DoReMiMixer,
    SoftDeduplicator,
    TopicAwareMixer,
)
from .heads import (
    ActionDecoder,
    ActorHead,
    ContinueHead,
    E8Decoder,
    HJEPAPredictor,
    ObservationDecoder,
    ObservationEncoder,
    RewardHead,
    ValueHead,
)
from .losses import (
    LossOutput,
    LossWeights,
    compute_fano_synergy_loss,
    compute_full_loss,
    compute_hjepa_loss,
    compute_stability_loss,
)
from .modules import (
    BlockGRU,
    ColonyEmbedding,
    DiscreteLatentEncoder,
    E8ToColonyProjection,
    SimNorm,
    SparseFanoAttention,
)

# Profiling infrastructure (PERMANENT - not one-off)
from .profiler import (
    BottleneckAnalyzer,
    BottleneckReport,
    MemoryTracker,
    ProfilerConfig,
    ProfileReport,
    ThroughputMetrics,
    ThroughputTracker,
    Timer,
    TPUProfiler,
    run_benchmark,
)
from .rssm import OrganismRSSM, RSSMOutput, RSSMStepOutput

# TPU v6e Optimizations (Trillium support)
from .tpu_optimization import (
    MixedPrecisionPolicy,
    QuantizationConfig,
    QuantizedDense,
    TPUVersion,
    create_tpu_optimized_pipeline,
    detect_tpu_version,
    get_mxu_alignment,
    pad_dimension,
)
from .train import (
    TrainState,
    create_train_state,
    train,
    train_step,
)
from .transforms import (
    KLInfo,
    PercentileNormalizer,
    TwoHotEncoder,
    balanced_kl_loss,
    gumbel_softmax,
    spherical_interpolate,
    spherical_softmax,
    symexp,
    symlog,
    symlog_loss,
    unimix_categorical,
)

__all__ = [
    "ActionDecoder",
    "ActorHead",
    "BlockGRU",
    "BottleneckAnalyzer",
    "BottleneckReport",
    "ColonyEmbedding",
    "CompetenceAwareCurriculum",
    "CompetenceConfig",
    "CompetenceEnhancedPhase",
    "CompetenceTracker",
    "ContinueHead",
    "Curriculum",
    "CurriculumConfig",
    "CurriculumPhase",
    "DifficultyAwareSampler",
    "DiscreteLatentEncoder",
    "DoReMiConfig",
    "DoReMiMixer",
    "DomainStats",
    "E8Decoder",
    "E8ToColonyProjection",
    "HJEPAPredictor",
    "HyperscaleLRSchedule",
    "KLInfo",
    "LossConfig",
    "LossOutput",
    "LossWeights",
    "MemoryTracker",
    "MixedPrecisionPolicy",
    "ObservationDecoder",
    "ObservationEncoder",
    "OrganismRSSM",
    "OrganismRSSMConfig",
    "OrganismTrainState",
    "PercentileNormalizer",
    "PhaseConfig",
    "ProfileReport",
    "ProfilerConfig",
    "QuantizationConfig",
    "QuantizedDense",
    "RSSMOutput",
    "RSSMStepOutput",
    "RewardHead",
    "SimNorm",
    "SoftDeduplicator",
    "SparseFanoAttention",
    "TPUProfiler",
    "TPUVersion",
    "ThroughputMetrics",
    "ThroughputTracker",
    "Timer",
    "TopicAwareMixer",
    "TrainState",
    "TrainingConfig",
    "TwoHotEncoder",
    "ValueHead",
    "balanced_kl_loss",
    "compute_fano_synergy_loss",
    "compute_full_loss",
    "compute_hjepa_loss",
    "compute_stability_loss",
    "create_tpu_optimized_pipeline",
    "create_train_state",
    "detect_tpu_version",
    "generate_batch",
    "generate_structured_batch",
    "get_mxu_alignment",
    "gumbel_softmax",
    "pad_dimension",
    "run_benchmark",
    "spherical_interpolate",
    "spherical_softmax",
    "symexp",
    "symlog",
    "symlog_loss",
    "train",
    "train_step",
    "unimix_categorical",
]
