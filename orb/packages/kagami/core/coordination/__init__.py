"""Coordination Module - System Integration and Experience Management.

Active components (Dec 2025):
- experience_store: Experience replay and storage
- hybrid_coordination: Coordination strategies
- memory_bridge: Memory integration
- metacognition: Self-monitoring
- optimal_integration: Optimal control
- system_coordinator: System-wide coordination
- emotional_expression: Affect modeling

Kagami Consensus & Self-Verification (Dec 14, 2025):
- inverter: Meta-observer (e₈) that verifies Kagami consensus
- kagami_consensus: Byzantine consensus protocol for coordination
- health_monitor: Coordinator health monitoring with hierarchical fallback
- kagami_blanket: Markov blanket interface for coordinator
- action_log_replicator: Distributed action log for colony recovery (Dec 15, 2025)
- state_sync: CRDT-based state synchronization for colony μ states (Dec 15, 2025)
- consensus_safety: Compositional CBF safety verification for consensus (Dec 15, 2025)
- consensus_metrics: Prometheus metrics for consensus monitoring (Dec 15, 2025)
- markov_blanket_guard: Enforce Markov blanket discipline in consensus (Dec 15, 2025)

COORDINATOR HIERARCHY (K OS-wide):
======================================
Level 1: System Lifecycle
- production_systems_coordinator.py: Boot sequence & lifecycle of 7 systems
- infra/graceful_shutdown.py: Shutdown coordination

Level 2: Collective Intelligence
- coordination/system_coordinator.py: System-wide collective coordination
- coordination/hybrid_coordination.py: Multi-strategy coordination
- coordination/optimal_integration.py: Optimal control decisions

Level 3: Learning
- learning/coordinator.py: UnifiedLearningCoordinator
- training/master_coordinator.py: MasterTrainingCoordinator
- federated_learning/coordinator.py: OrganismCoordinator (federated)
- federated_learning/etcd_coordinator.py: EtcdFederatedCoordinator

Level 4: Domain-Specific
- memory/pressure_coordinator.py: Memory pressure management
- cognition/recursive_feedback.py: Cognitive layer feedback
- ambient/multi_device_coordinator.py: Cross-device state
- free_energy.py: FreeEnergyCoordinator

Each coordinator owns its domain. No overlap.
"""

# Core coordination modules (all should exist)
from .emotional_expression import EmotionalExpressionEngine, get_emotional_engine
from .experience_store import CentralExperienceStore, get_experience_store
from .health_monitor import (
    CoordinatorHealth,
    CoordinatorHealthMonitor,
    HealthMetrics,
    KagamiHealthMonitor,
    create_health_monitor,
)
from .hybrid_coordination import Coordination

# Importance-based collaboration (consolidated from collaboration/ Dec 7, 2025)
from .importance_triggers import (
    CollaborationRelevance,
    ImportanceBasedTriggers,
    SocialState,
    get_importance_triggers,
)

# Kagami consensus & self-verification (Dec 14, 2025)
from .inverter import (
    CoordinatorDriftReport,
    InverterAgent,
    MetaCoordinationAnalysis,
    create_inverter,
)
from .kagami_consensus import (
    ColonyID,
    ConsensusState,
    CoordinationProposal,
    KagamiConsensus,
    create_consensus_protocol,
)
from .metacognition import MetacognitiveLayer
from .optimal_integration import CoordinatedDecisionResult

try:
    from .kagami_blanket import (
        ColonyObservation,
        CoordinationAction,
        KagamiMarkovBlanket,
        MessageBusInterface,
        create_kagami_blanket,
    )
except ImportError:
    KagamiMarkovBlanket = None
    ColonyObservation = None
    CoordinationAction = None
    MessageBusInterface = None
    create_kagami_blanket = None

# Action log replication & state sync (Dec 15, 2025)
from .action_log_replicator import (
    ActionLogReplicator,
    ReplicatedAction,
    create_action_log_replicator,
)
from .consensus_metrics import (
    ConsensusMetricsCollector,
    check_consensus_health,
    get_metrics_collector,
)

# Consensus optimization (Dec 15, 2025)
from .consensus_optimizer import (
    BatchedConsensus,
    ConsensusCache,
    ConsensusOptimizer,
    PredictiveConsensus,
    create_consensus_optimizer,
)

# Consensus safety & monitoring (Dec 15, 2025)
from .consensus_safety import (
    SafetyVerificationResult,
    SafetyViolation,
    compute_safety_margin_distribution,
    filter_unsafe_consensus,
    get_safest_colony,
    verify_compositional_cbf,
)

# Cross-Hub CRDT Synchronization (Jan 4, 2026)
from .cross_hub_crdt import (
    ClockOrdering,
    CrossHubCRDTManager,
    CrossHubCRDTState,
    GCounter,
    ORSet,
    ORSetElement,
    PNCounter,
    VectorClock,
    get_cross_hub_crdt_manager,
    shutdown_cross_hub_crdt,
)
from .markov_blanket_guard import (
    MarkovBlanketGuard,
    MarkovBlanketViolation,
    ValidationResult,
    ViolationType,
    create_markov_blanket_guard,
)

# Meta-Orchestrator (Dec 28, 2025) - General multi-instance coordination
from .meta_orchestrator import (
    CoordinationMode,
    CoordinationResult,
    InstanceAssigner,
    MetaOrchestrator,
    OrchestratableInstance,
    OrganismInstanceAdapter,
    StrategicMemory,
    TaskDAG,
    TaskDecomposer,
    TaskNode,
    TaskPriority,
    create_meta_orchestrator,
    get_meta_orchestrator,
    reset_meta_orchestrator,
)
from .state_sync import (
    ColonyStateCRDT,
    GSet,
    LWWRegister,
    create_colony_state_crdt,
)

# Swarm Coordination (Dec 28, 2025) - Advanced multi-instance patterns
from .swarm_coordination import (
    Bid,
    ConsensusVoting,
    LeaderFollower,
    PheromoneCoordinator,
    ScatterGather,
    SwarmCoordinator,
    SwarmSearch,
    SwarmSearchResult,
    SwarmSignal,
    TaskAuction,
    Vote,
    create_swarm_coordinator,
    get_swarm_coordinator,
    reset_swarm_coordinator,
)

__all__ = [
    "ActionLogReplicator",
    "BatchedConsensus",
    "Bid",
    "CentralExperienceStore",
    "ClockOrdering",
    "CollaborationRelevance",
    "ColonyID",
    "ColonyObservation",
    "ColonyStateCRDT",
    "ConsensusCache",
    "ConsensusMetricsCollector",
    "ConsensusOptimizer",
    "ConsensusState",
    "ConsensusVoting",
    "CoordinatedDecisionResult",
    "Coordination",
    "CoordinationAction",
    "CoordinationMode",
    "CoordinationProposal",
    "CoordinationResult",
    "CoordinatorDriftReport",
    "CoordinatorHealth",
    "CoordinatorHealthMonitor",
    "CrossHubCRDTManager",
    "CrossHubCRDTState",
    "EmotionalExpressionEngine",
    "GCounter",
    "GSet",
    "HealthMetrics",
    "ImportanceBasedTriggers",
    "InstanceAssigner",
    "InverterAgent",
    "KagamiConsensus",
    "KagamiHealthMonitor",
    "KagamiMarkovBlanket",
    "LWWRegister",
    "LeaderFollower",
    "MarkovBlanketGuard",
    "MarkovBlanketViolation",
    "MessageBusInterface",
    "MetaCoordinationAnalysis",
    "MetaOrchestrator",
    "MetacognitiveLayer",
    "ORSet",
    "ORSetElement",
    "OrchestratableInstance",
    "OrganismInstanceAdapter",
    "PNCounter",
    "PheromoneCoordinator",
    "PredictiveConsensus",
    "ReplicatedAction",
    "SafetyVerificationResult",
    "SafetyViolation",
    "ScatterGather",
    "SocialState",
    "StrategicMemory",
    "SwarmCoordinator",
    "SwarmSearch",
    "SwarmSearchResult",
    "SwarmSignal",
    "TaskAuction",
    "TaskDAG",
    "TaskDecomposer",
    "TaskNode",
    "TaskPriority",
    "ValidationResult",
    "VectorClock",
    "ViolationType",
    "Vote",
    "check_consensus_health",
    "compute_safety_margin_distribution",
    "create_action_log_replicator",
    "create_colony_state_crdt",
    "create_consensus_optimizer",
    "create_consensus_protocol",
    "create_health_monitor",
    "create_inverter",
    "create_kagami_blanket",
    "create_markov_blanket_guard",
    "create_meta_orchestrator",
    "create_swarm_coordinator",
    "filter_unsafe_consensus",
    "get_cross_hub_crdt_manager",
    "get_emotional_engine",
    "get_experience_store",
    "get_importance_triggers",
    "get_meta_orchestrator",
    "get_metrics_collector",
    "get_safest_colony",
    "get_swarm_coordinator",
    "reset_meta_orchestrator",
    "reset_swarm_coordinator",
    "shutdown_cross_hub_crdt",
    "verify_compositional_cbf",
]
