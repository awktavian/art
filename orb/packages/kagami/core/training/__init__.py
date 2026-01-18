"""Training infrastructure for Kagami World Model.

APOLLO-GRADE TRAINING INFRASTRUCTURE (January 12, 2026):
=========================================================

THE CANONICAL ENTRY POINT is the `kagami-train` CLI.
Single source of truth: `config/training.yaml`

CLI Usage:
    kagami-train pipeline --config config/training.yaml
    kagami-train tpu start --config config/training.yaml
    kagami-train data generate
    kagami-train distill --student small
    kagami-train export --checkpoint gs://models/final --format onnx
    kagami-train monitor

Programmatic Usage:
    from kagami.core.training import train_kagami, ConsolidatedTrainer
    results = await train_kagami(config_path="config/training.yaml")

    # Or use the CLI programmatically
    from kagami.core.training.cli import PipelineOrchestrator, TrainingConfig
    config = TrainingConfig.from_yaml("config/training.yaml")
    pipeline = PipelineOrchestrator(config)
    await pipeline.run()

CURRICULUM (7 Phases):
======================
- Phase 0: WARMUP - Reconstruction warmup (β≈0)
- Phase 1: GEOMETRY (Fold A₂) - E8 hierarchy learning
- Phase 2: ROTATION (Cusp A₃) - SE(3) equivariance
- Phase 3: DYNAMICS (Swallowtail A₄) - Temporal prediction
- Phase 4: JOINT (Butterfly A₅) - Multi-dataset mixing
- Phase 5: GENERATION (Hyperbolic D₄⁺) - Generative control
- Phase 6: LANGUAGE (Elliptic D₄⁻) - Language grounding

DELETED (January 12, 2026):
===========================
- scripts/generate_training_data.py → Use: kagami-train data generate
- scripts/verify_training_stability.py → Integrated into training validator
- scripts/deploy/monitor_training.py → Use: kagami-train monitor
- scripts/smoke_test_pretraining.py → Use: pytest tests/training/
- scripts/visualization/parse_training_log.py → Integrated into telemetry
- config/training_*.yaml (4 files) → Use: config/training.yaml
"""

from typing import Any

# Training configuration helpers
from kagami.core.config.unified_config import get_kagami_config as _get_kagami_config

# === CONSOLIDATED TRAINER (January 5-8, 2026) ===
# THE CANONICAL entry point for all training
from kagami.core.training.consolidated import (
    ConsolidatedConfig,
    ConsolidatedTrainer,
    GCSCheckpointer,
    GeminiTuner,
    WandBLogger,
    train_kagami,
)
from kagami.core.training.consolidated import (
    TrainingBackend as ConsolidatedBackend,
)

# === GEMINI GROUNDING (January 5, 2026) ===
from kagami.core.training.gemini_grounding import (
    EmbeddingCache,
    GeminiEmbeddingService,
    GeminiGroundingConfig,
    GeminiGroundingModule,
    GroundingLoss,
    LanguageProjection,
    VICRegLoss,
    create_tpu_grounding_pipeline,
    get_gemini_grounding_module,
    load_precomputed_embeddings,
    precompute_embeddings_batch,
)

# === MULTIMODAL TRAINING (January 5, 2026) ===
from kagami.core.training.multimodal import (
    ActionEncoder,
    E8ModalityFusion,
    LanguageEncoder,
    Modality,
    ModalityConfig,
    MultimodalConfig,
    MultimodalContrastiveLoss,
    MultimodalEncoder,
    VisionEncoder,
    create_multimodal_encoder,
)

# Real data loading
from kagami.core.training.real_data_loader import (
    CurriculumDataset,
    create_curriculum_dataloader,
    curriculum_collate_fn,
)
from kagami.core.training.real_data_loader import (
    validate_batch as real_validate_batch,
)


def get_default_config() -> Any:
    """Get default training configuration."""
    return _get_kagami_config().training


def get_small_config() -> Any:
    """Get small training configuration."""
    return _get_kagami_config(profile="minimal").training


def get_large_config() -> Any:
    """Get large training configuration."""
    return _get_kagami_config(profile="large").training


def get_mps_optimal_config() -> Any:
    """Get MPS-optimized training configuration."""
    config = _get_kagami_config(profile="balanced").training
    config.device = "mps"
    return config


def get_minimal_config() -> Any:
    """Get minimal training configuration."""
    return _get_kagami_config(profile="minimal").training


def get_balanced_config() -> Any:
    """Get balanced training configuration."""
    return _get_kagami_config(profile="balanced").training


def get_maximal_config() -> Any:
    """Get maximal training configuration."""
    return _get_kagami_config(profile="maximal").training


# Curriculum Schedulers
from kagami.core.training.unified_curriculum import (
    CATASTROPHE_TYPES,
    UnifiedCurriculumScheduler,
)
from kagami.core.training.unified_curriculum import (
    PHASE_NAMES as UNIFIED_PHASE_NAMES,
)
from kagami.core.training.unified_curriculum import (
    CurriculumPhase as UnifiedCurriculumPhase,
)
from kagami.core.training.unified_curriculum import (
    CurriculumState as UnifiedCurriculumState,
)
from kagami.core.training.unified_curriculum import (
    PhaseConfig as UnifiedPhaseConfig,
)

# Validation (MANDATORY - learned from v6e failures)
from kagami.core.training.validation import (
    DivergenceDetector,
    GradientHealthMonitor,
    KLCollapseDetector,
    TrainingValidator,
    ValidationLevel,
    ValidationResult,
)
from kagami.core.training.validation import (
    PlateauDetector as ValidationPlateauDetector,
)

# Backward compatibility: Point to validation module equivalents
# (consolidated.py versions DELETED Jan 11, 2026 - were duplicates)
PlateauDetector = ValidationPlateauDetector
KLCollapseMonitor = KLCollapseDetector  # Same functionality, different name

__all__ = [
    # === CANONICAL TRAINING (January 12, 2026) ===
    "ConsolidatedConfig",
    "ConsolidatedTrainer",
    "train_kagami",
    # === CURRICULUM ===
    "CATASTROPHE_TYPES",
    "UNIFIED_PHASE_NAMES",
    "UnifiedCurriculumPhase",
    "UnifiedCurriculumScheduler",
    "UnifiedCurriculumState",
    "UnifiedPhaseConfig",
    # === DATA ===
    "CurriculumDataset",
    "create_curriculum_dataloader",
    "curriculum_collate_fn",
    "real_validate_batch",
    # === MULTIMODAL ===
    "ActionEncoder",
    "E8ModalityFusion",
    "LanguageEncoder",
    "Modality",
    "ModalityConfig",
    "MultimodalConfig",
    "MultimodalContrastiveLoss",
    "MultimodalEncoder",
    "VisionEncoder",
    "create_multimodal_encoder",
    # === GEMINI GROUNDING ===
    "EmbeddingCache",
    "GeminiEmbeddingService",
    "GeminiGroundingConfig",
    "GeminiGroundingModule",
    "GroundingLoss",
    "LanguageProjection",
    "VICRegLoss",
    "create_tpu_grounding_pipeline",
    "get_gemini_grounding_module",
    "load_precomputed_embeddings",
    "precompute_embeddings_batch",
    # === VALIDATION (MANDATORY - v6e lessons) ===
    "DivergenceDetector",
    "GradientHealthMonitor",
    "KLCollapseDetector",
    "KLCollapseMonitor",
    "PlateauDetector",
    "TrainingValidator",
    "ValidationLevel",
    "ValidationPlateauDetector",
    "ValidationResult",
    # === CHECKPOINTING ===
    "GCSCheckpointer",
    "GeminiTuner",
    "WandBLogger",
    # === CONFIG HELPERS ===
    "get_balanced_config",
    "get_default_config",
    "get_large_config",
    "get_maximal_config",
    "get_minimal_config",
    "get_mps_optimal_config",
    "get_small_config",
]
