"""Unified Agents Package - Consolidated Agent Architecture.

This package replaces the fragmented agent/colony architecture with a
mathematically grounded, simplified implementation.

ARCHITECTURE (December 2025):
=============================

┌─────────────────────────────────────────────────────────────────────┐
│                        UNIFIED AGENTS                                │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                   UnifiedOrganism                            │   │
│  │  - Manages 7 MinimalColonies                                │   │
│  │  - Routes via FanoActionRouter                              │   │
│  │  - Fuses via E8ActionReducer                                │   │
│  │  - Communicates via UnifiedE8Bus (kagami.core.events)        │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                              │                                      │
│         ┌────────────────────┼────────────────────┐                │
│         ▼                    ▼                    ▼                │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐          │
│  │ MinimalColony│     │ MinimalColony│     │ MinimalColony│  x7     │
│  │    Spark    │     │    Forge    │     │   Crystal   │          │
│  └──────┬──────┘     └──────┬──────┘     └──────┬──────┘          │
│         │                   │                   │                  │
│         ▼                   ▼                   ▼                  │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐          │
│  │ Geometric   │     │ Geometric   │     │ Geometric   │          │
│  │   Worker    │     │   Worker    │     │   Worker    │          │
│  └─────────────┘     └─────────────┘     └─────────────┘          │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘

COMPONENTS:
===========
- UnifiedOrganism: Central orchestrator (replaces FractalOrganism)
- MinimalColony: Simplified colony with worker pool
- GeometricWorker: Unified agent on H¹⁴ × S⁷ manifold
- FanoActionRouter: 1/3/7 action routing via Fano plane
- E8ActionReducer: Colony output fusion via E₈ lattice
- UnifiedE8Bus: Inter-colony event bus (see kagami.core.events)

SCIENTIFIC FOUNDATIONS:
======================
- S⁷ parallelizability (Adams 1960): 7 is maximal
- Fano plane (Baez 2002): 7 lines encode valid compositions
- E₈ lattice (Viazovska 2016): Optimal 8D quantization
- 7 catastrophes (Thom 1972): Maps to 7 colony types

Created: December 2, 2025
"""

# =============================================================================
# ORGANISM (Central Orchestrator)
# =============================================================================

# =============================================================================
# API SUPPORT (Shared Awareness, Criticality, Fano Vitals)
# =============================================================================
# NOTE: Most imports temporarily commented for consciousness integration
# Re-enabled: CriticalityManager for API routes
from kagami.core.unified_agents.api_support import (
    # Criticality Manager
    CriticalityManager,
    get_criticality_manager,
)

# from kagami.core.unified_agents.api_support import (
#     # Shared Awareness
#     ActivityType,
#     ColonyActivity,
#     SharedAwareness,
#     get_shared_awareness,
#     # Fano Vitals
#     FanoLineVitals,
#     FanoCollaborationVitals,
#     FanoVitals,
#     get_fano_vitals,
#     record_fano_collaboration,
#     get_collaboration_health,
#     FANO_LINE_NAMES,
#     SQUAD_NAMES,
# )
# =============================================================================
# COLONY CONSTANTS (Differentiable S⁷ embeddings)
# =============================================================================
from kagami.core.unified_agents.colony_constants import (
    COLONY_NAMES,
    COLONY_TO_INDEX,
    INDEX_TO_COLONY,
    DomainType,
    get_all_colony_embeddings,
    get_colony_embedding,
    get_s7_basis,
)

# =============================================================================
# CORE TYPES (December 7, 2025 - Extracted from legacy_bridge)
# =============================================================================
from kagami.core.unified_agents.core_types import (
    ACTION_TO_APP_MAP,
    AGENT_PERSONALITIES,
    APP_MATURITY,
    APP_METADATA,
    APP_REGISTRY_V2,
    # Definitions
    CANONICAL_AGENTS_REGISTRY,
    DNA,
    DOMAIN_TO_OCTONION,
    AgentDNA,
    CatastrophePotential,
    # Execution
    ExecutionMode,
    Goal,
    # Task and Goal
    Task,
)

# =============================================================================
# REDUCER (E8 action fusion)
# =============================================================================
from kagami.core.unified_agents.e8_action_reducer import (
    E8Action,
    E8ActionReducer,
    create_e8_reducer,
    get_e8_roots,
)

# =============================================================================
# ROUTER (Fano-based 1/3/7 routing)
# =============================================================================
from kagami.core.unified_agents.fano_action_router import (
    FANO_LINES,
    FANO_LINES_0IDX,
    ActionMode,
    ColonyAction,
    FanoActionRouter,
    RoutingResult,
    create_fano_router,
    get_fano_router,
)

# =============================================================================
# MEMORY SYSTEMS
# =============================================================================
# META-LEARNING (Fano-constrained attention)
# =============================================================================
from kagami.core.unified_agents.fano_meta_learner import (
    FanoMetaLearner,
    visualize_fano_structure,
)

# =============================================================================
# WORKER (Unified geometric agent)
# =============================================================================
from kagami.core.unified_agents.geometric_worker import (
    GeometricWorker,
    TaskResult,
    WorkerConfig,
    WorkerState,
    WorkerStatus,
    create_worker,
)

# =============================================================================
from kagami.core.unified_agents.memory import (
    StigmergyLearner,
    get_stigmergy_learner,
)

# =============================================================================
# COLONY (Minimal colony with worker pool)
# =============================================================================
from kagami.core.unified_agents.minimal_colony import (
    ColonyConfig,
    ColonyStats,
    MinimalColony,
    create_colony,
)

# =============================================================================
# OCTONION STATE (December 27, 2025 - Unified state representation)
# =============================================================================
from kagami.core.unified_agents.octonion_state import (
    OctonionState,
    octonion_state_from_agent_result,
    octonion_state_from_colony_state,
    octonion_state_from_core_state,
)

# =============================================================================
# CONTEXT TYPES (December 24, 2025 - Structured context/result objects)
# =============================================================================
from kagami.core.unified_agents.organism_context import (
    CostEvaluation,
    ExecutionResult,
    KnowledgeGraphSuggestion,
    OrganismContext,
    PerceptionState,
    SafetyZone,
    WorldModelHint,
)
from kagami.core.unified_agents.unified_organism import (
    HomeostasisState,
    OrganismConfig,
    OrganismStats,
    OrganismStatus,
    UnifiedOrganism,
    create_organism,
    get_organism,  # Alias
    get_unified_organism,
    set_unified_organism,
)

# =============================================================================
# CONVENIENCE FUNCTIONS (Module-level access)
# =============================================================================


def get_colony(name: str) -> MinimalColony | None:
    """Get colony by name from the default organism.

    Args:
        name: Colony name ('spark', 'forge', etc.)

    Returns:
        MinimalColony instance or None if not found
    """
    # get_unified_organism() automatically creates one if None
    organism = get_unified_organism()
    # Access colonies property to trigger lazy initialization
    _ = organism.colonies
    return organism.get_colony(name)


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "ACTION_TO_APP_MAP",
    "AGENT_PERSONALITIES",
    "APP_MATURITY",
    "APP_METADATA",
    "APP_REGISTRY_V2",
    "CANONICAL_AGENTS_REGISTRY",
    # Constants
    "COLONY_NAMES",
    "COLONY_TO_INDEX",
    "DNA",
    "DOMAIN_TO_OCTONION",
    "FANO_LINES",
    "FANO_LINES_0IDX",
    "FANO_LINE_NAMES",
    "INDEX_TO_COLONY",
    "SQUAD_NAMES",
    "ActionMode",
    # API Support - Shared Awareness
    "ActivityType",
    "AgentDNA",
    "CatastrophePotential",
    "ColonyAction",
    "ColonyActivity",
    "ColonyConfig",
    "ColonyStats",
    "CostEvaluation",
    # API Support - Criticality Manager
    "CriticalityManager",
    "DomainType",
    "E8Action",
    # Reducer
    "E8ActionReducer",
    "ExecutionMode",
    "ExecutionResult",
    # Router
    "FanoActionRouter",
    "FanoCollaborationVitals",
    # API Support - Fano Vitals
    "FanoLineVitals",
    # Meta-Learning
    "FanoMetaLearner",
    "FanoVitals",
    # Worker
    "GeometricWorker",
    "Goal",
    "HomeostasisState",
    "KnowledgeGraphSuggestion",
    # Colony
    "MinimalColony",
    # OctonionState (Dec 27, 2025)
    "OctonionState",
    "OrganismConfig",
    "OrganismContext",
    "OrganismStats",
    "OrganismStatus",
    "PerceptionState",
    "RoutingResult",
    # Context Types (Dec 24, 2025)
    "SafetyZone",
    "SharedAwareness",
    # Message Bus
    # Memory
    "StigmergyLearner",
    # Core Types
    "Task",
    "TaskResult",
    # Organism
    "UnifiedOrganism",
    "WorkerConfig",
    "WorkerState",
    "WorkerStatus",
    "WorldModelHint",
    "create_colony",
    "create_e8_reducer",
    "create_fano_router",
    "create_organism",
    "create_worker",
    "get_all_colony_embeddings",
    "get_collaboration_health",
    # Convenience functions
    "get_colony",
    "get_colony_embedding",
    "get_criticality_manager",
    "get_e8_roots",
    "get_fano_router",
    "get_fano_vitals",
    "get_organism",  # Alias for get_unified_organism
    "get_s7_basis",
    "get_shared_awareness",
    "get_stigmergy_learner",
    "get_unified_organism",
    "octonion_state_from_agent_result",
    "octonion_state_from_colony_state",
    "octonion_state_from_core_state",
    "record_fano_collaboration",
    "set_unified_organism",
    "visualize_fano_structure",
]
