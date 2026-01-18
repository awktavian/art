"""World Model Package - Entry Point.

CANONICAL ENTRY POINT:
======================
    from kagami.core.world_model.service import get_world_model_service

    service = get_world_model_service()
    model = service.model              # KagamiWorldModel
    ai = service.active_inference      # ActiveInferenceEngine

Import world model components from:
- .kagami_world_model: Core model implementation
- .service: Service layer and factory functions
- .colony_rssm: RSSM dynamics
- .losses: Loss functions
- .compilation: torch.compile optimization utilities (EXPERIMENTAL)
"""

from __future__ import annotations

# Catastrophe-Guided Diffusion
from .catastrophe_diffusion import (
    COLONY_CATASTROPHES,
    CatastropheDiffusionConfig,
    CatastropheDiffusionModel,
    CatastropheDiTBlock,
    CatastropheNoiseSchedule,
    CatastrophePotential,
    CatastropheType,
    create_catastrophe_diffusion,
    create_colony_diffusion_ensemble,
)

# Causal Grounded Intelligence (December 27, 2025)
# Three-layer cognitive enhancement from "Kagami Evolution" proposal
from .causal_grounded_integration import (
    CausalGroundedWorldModel,
    CausalReasoningEngine,
    CounterfactualQuery,
    CounterfactualResult,
    GroundedIntelligenceConfig,
    HierarchicalPlanResult,
    MacroAction,
    SensorimotorEncoder,
    TemporalAbstractionLayer,
    get_causal_grounded_world_model,
    reset_causal_grounded_world_model,
)

# torch.compile utilities (experimental, opt-in via ENABLE_TORCH_COMPILE)
from .compilation import (
    compile_for_inference,
    compile_for_training,
    disable_compilation,
    enable_compilation,
    is_compilation_enabled,
)
from .decoder import Decoder

# Diffusion-based generation (Sora-style)
from .diffusion_dynamics import (
    DiffusionConfig,
    DiffusionWorldModel,
    DiTBlock,
    NoiseSchedule,
    create_diffusion_world_model,
)
from .e8_trajectory_cache import (
    BifurcationEntry,
    CacheEntry,
    CacheStats,
    E8TrajectoryCache,
    create_e8_trajectory_cache,
)

# =============================================================================
# E8-INTEGRATED COMPONENTS (UNIQUE to Kagami, January 4, 2026)
# =============================================================================
# E8 Transformer - E8 quantized attention
from .e8_transformer import (
    E8Attention,
    E8TransformerBlock,
    E8TransformerConfig,
    E8TransformerWorldModel,
    create_e8_transformer_world_model,
)

# World Model → Physical Embodiment bridge (December 30, 2025)
from .embodiment_bridge import (
    PHYSICAL_ACTION_ENCODINGS,
    ImaginedOutcome,
    PhysicalAction,
    WorldModelEmbodiment,
    get_world_model_embodiment,
    reset_world_model_embodiment,
)

# Encoder/Decoder classes for architectural clarity (Dec 20, 2025)
from .encoder import Encoder

# Fano Sparse Attention - 7-head octonion structure
from .fano_attention import (
    FanoAttentionBlock,
    FanoAttentionConfig,
    FanoOctonionAttention,
    FanoSparseAttention,
    FanoSparseMask,
    FanoTransformer,
    create_fano_attention,
    create_fano_transformer,
)

# Game World Model (Consolidated January 5, 2026)
from .games import (
    GameFrameDecoder,
    GameFrameEncoder,
    GameWorldModel,
    GameWorldModelConfig,
    GameWorldModelState,
    ImaginationPlanner,
    MCTSNode,
    PlanningConfig,
    SimpleImagination,
)

# H-JEPA with action conditioning (Updated January 4, 2026)
from .h_jepa import (
    HJEPAConfig,
    HJEPAContextEncoder,
    HJEPAModule,
    HJEPAPredictor,
    create_h_jepa_module,
)

# Kagami Ecosystem Bridge (connects to everything)
from .kagami_ecosystem_bridge import (
    ClaudeBridge,
    ColonyBridge,
    ComposioBridge,
    EcosystemBridgeConfig,
    KagamiEcosystemBridge,
    SafetyFilter,
    SmartHomeBridge,
    create_ecosystem_bridge,
)
from .kagami_world_model import (
    CoreState,
    KagamiWorldModel,
    KagamiWorldModelConfig,
    KagamiWorldModelFactory,
    create_model,  # Factory function for quick model creation
)

# Language-World Model integration
from .language_reasoning import (
    InstructionExecutor,
    LanguageEncoder,
    LanguageReasoning,
    LanguageReasoningConfig,
    LLMReasoner,
    StateCaptioner,
    TextGrounding,
    create_language_reasoning,
)

# Latent Action Model (Genie-style action discovery)
from .latent_action_model import (
    LatentActionConfig,
    LatentActionModel,
    VectorQuantizer,
    VideoLatentActionModel,
    create_latent_action_model,
)

# Sensory → World Model bridge (December 30, 2025)
from .sensory_encoder import (
    SensoryToWorldModel,
    get_sensory_encoder,
    reset_sensory_encoder,
)
from .service import get_world_model_service

# Smart Home World Model (practical Kagami integration)
from .smarthome_world_model import (
    ROOMS,
    SmartHomeWorldModel,
    SmartHomeWorldModelConfig,
    create_smarthome_world_model,
)

# 3D Spatial representation (World Labs style)
from .spatial_representation import (
    GaussianSplatting,
    NeRFMLP,
    SpatialConfig,
    SpatialWorldModel,
    TriPlaneDecoder,
    TriPlaneEncoder,
    VolumeRenderer,
    create_spatial_world_model,
)

# TD-MPC2 Planning Head (January 4, 2026)
# Model-based planning for downstream task evaluation
from .tdmpc2_planning import (
    LatentDynamics,
    RewardPredictor,
    TDMPC2PlanningHead,
    TDMPCPlanningConfig,
    ValuePredictor,
    create_tdmpc2_planner,
    integrate_with_world_model,
)
from .temporal_e8_quantizer import (
    TemporalE8Config,
    TemporalE8Quantizer,
    create_temporal_quantizer,
)

# =============================================================================
# SOTA WORLD MODEL COMPONENTS (January 4, 2026)
# =============================================================================
# Transformer-based dynamics (replaces GRU RSSM)
from .transformer_dynamics import (
    TransformerDynamicsConfig,
    TransformerWorldModel,
    create_transformer_world_model,
    upgrade_rssm_to_transformer,
)

# Unified SOTA World Model (THE WHOLE ENCHILADA)
from .unified_sota_world_model import (
    KagamiIntegration,
    MultiModalEncoder,
    PlanningAndSafety,
    UnifiedDynamics,
    UnifiedGenerator,
    UnifiedSOTAConfig,
    UnifiedSOTAWorldModel,
    create_unified_sota_world_model,
)

# Unified World Model + RSSM integration (Dec 20, 2025)
from .unified_world_model import (
    UnifiedConfig,
    UnifiedState,
    UnifiedWorldModel,
    create_unified_world_model,
)

__all__ = [
    "COLONY_CATASTROPHES",
    "PHYSICAL_ACTION_ENCODINGS",
    "ROOMS",
    "BifurcationEntry",
    "CacheEntry",
    "CacheStats",
    "CatastropheDiTBlock",
    "CatastropheDiffusionConfig",
    # Catastrophe-Guided Diffusion
    "CatastropheDiffusionModel",
    "CatastropheNoiseSchedule",
    "CatastrophePotential",
    "CatastropheType",
    # Causal Grounded Intelligence (December 27, 2025)
    "CausalGroundedWorldModel",
    "CausalReasoningEngine",
    "ClaudeBridge",
    "ColonyBridge",
    "ComposioBridge",
    "CoreState",
    "CounterfactualQuery",
    "CounterfactualResult",
    "Decoder",
    "DiTBlock",
    "DiffusionConfig",
    # Diffusion Dynamics
    "DiffusionWorldModel",
    "E8Attention",
    # E8 trajectory cache
    "E8TrajectoryCache",
    "E8TransformerBlock",
    "E8TransformerConfig",
    # =========================================================================
    # E8-INTEGRATED COMPONENTS (UNIQUE to Kagami, January 4, 2026)
    # =========================================================================
    # E8 Transformer
    "E8TransformerWorldModel",
    "EcosystemBridgeConfig",
    # Encoder/Decoder (architectural clarity)
    "Encoder",
    "FanoAttentionBlock",
    "FanoAttentionConfig",
    "FanoOctonionAttention",
    # Fano Sparse Attention
    "FanoSparseAttention",
    "FanoSparseMask",
    "FanoTransformer",
    # =========================================================================
    # GAME WORLD MODEL (Consolidated January 5, 2026)
    # From: packages/kagami_games/kagami_games/world_model/
    # =========================================================================
    "GameFrameDecoder",
    "GameFrameEncoder",
    "GameWorldModel",
    "GameWorldModelConfig",
    "GameWorldModelState",
    "GaussianSplatting",
    "GroundedIntelligenceConfig",
    "HJEPAConfig",
    "HJEPAContextEncoder",
    # H-JEPA with action conditioning (January 4, 2026)
    "HJEPAModule",
    "HJEPAPredictor",
    "HierarchicalPlanResult",
    "ImaginationPlanner",
    "ImaginedOutcome",
    "InstructionExecutor",
    # Kagami Ecosystem Bridge
    "KagamiEcosystemBridge",
    "KagamiIntegration",
    # Core world model
    "KagamiWorldModel",
    "KagamiWorldModelConfig",
    "KagamiWorldModelFactory",
    "LLMReasoner",
    "LanguageEncoder",
    # Language Reasoning
    "LanguageReasoning",
    "LanguageReasoningConfig",
    "LatentActionConfig",
    # Latent Action Model
    "LatentActionModel",
    "LatentDynamics",
    "MCTSNode",
    "MacroAction",
    "MultiModalEncoder",
    "NeRFMLP",
    "NoiseSchedule",
    "PhysicalAction",
    "PlanningAndSafety",
    "PlanningConfig",
    "RewardPredictor",
    "SafetyFilter",
    "SensorimotorEncoder",
    "SensoryToWorldModel",
    "SimpleImagination",
    "SmartHomeBridge",
    # Smart Home World Model
    "SmartHomeWorldModel",
    "SmartHomeWorldModelConfig",
    "SpatialConfig",
    # 3D Spatial Representation
    "SpatialWorldModel",
    "StateCaptioner",
    # TD-MPC2 Planning (January 4, 2026)
    "TDMPC2PlanningHead",
    "TDMPCPlanningConfig",
    "TemporalAbstractionLayer",
    "TemporalE8Config",
    # Temporal E8 quantizer
    "TemporalE8Quantizer",
    "TextGrounding",
    "TransformerDynamicsConfig",
    # =========================================================================
    # SOTA World Model Components (January 4, 2026)
    # =========================================================================
    # Transformer Dynamics
    "TransformerWorldModel",
    "TriPlaneDecoder",
    "TriPlaneEncoder",
    "UnifiedConfig",
    "UnifiedDynamics",
    "UnifiedGenerator",
    "UnifiedSOTAConfig",
    # Unified SOTA World Model (THE WHOLE ENCHILADA)
    "UnifiedSOTAWorldModel",
    "UnifiedState",
    # Unified World Model + RSSM
    "UnifiedWorldModel",
    "ValuePredictor",
    "VectorQuantizer",
    "VideoLatentActionModel",
    "VolumeRenderer",
    "WorldModelEmbodiment",
    "compile_for_inference",
    "compile_for_training",
    "create_catastrophe_diffusion",
    "create_colony_diffusion_ensemble",
    "create_diffusion_world_model",
    "create_e8_trajectory_cache",
    "create_e8_transformer_world_model",
    "create_ecosystem_bridge",
    "create_fano_attention",
    "create_fano_transformer",
    "create_h_jepa_module",
    "create_language_reasoning",
    "create_latent_action_model",
    "create_model",
    "create_smarthome_world_model",
    "create_spatial_world_model",
    "create_tdmpc2_planner",
    "create_temporal_quantizer",
    "create_transformer_world_model",
    "create_unified_sota_world_model",
    "create_unified_world_model",
    "disable_compilation",
    # Compilation utilities (experimental)
    "enable_compilation",
    "get_causal_grounded_world_model",
    # Sensory → World Model bridge (December 30, 2025)
    "get_sensory_encoder",
    # World Model → Physical Embodiment bridge (December 30, 2025)
    "get_world_model_embodiment",
    "get_world_model_service",
    "integrate_with_world_model",
    "is_compilation_enabled",
    "reset_causal_grounded_world_model",
    "reset_sensory_encoder",
    "reset_world_model_embodiment",
    "upgrade_rssm_to_transformer",
]
