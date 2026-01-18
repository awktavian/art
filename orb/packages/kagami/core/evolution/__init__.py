"""Evolution System - Autonomous Recursive Self-Improvement.

Complete system for safe autonomous code modification:
- Continuous Evolution Engine: observe→learn→improve→act→verify→evolve
- CI Feedback Bridge: Parse CI reports and generate fix proposals
- Fitness Functions: Multi-objective evaluation (safety, correctness, performance)
- Dry-Run Evaluator: Test changes in sandbox before applying
- Canary Rollout: Gradual deployment with automatic rollback
- Evolution Controls: Kill-switch, pause/resume, rate limiting
- Checkpoints: Save state, verify for 1hr, auto-rollback on degradation
- Improvement Ledger: Complete audit trail of all changes

This enables Kagami to improve itself recursively while maintaining safety.
"""

from kagami.core.evolution.autonomous_improvement import (
    AutonomousImprovementEngine,
    ByzantineConsensus,
    Colony,
    ColonyAnalyzer,
    ColonyScore,
    ConsensusResult,
    ImprovementCategory,
    ImprovementPlan,
    ImprovementPriority,
    analyze_codebase,
    get_improvement_engine,
    get_improvement_plan,
    get_report,
)
from kagami.core.evolution.canary_rollout import (
    CanaryConfig,
    CanaryRollout,
    RolloutStatus,
    get_canary_rollout,
)
from kagami.core.evolution.checkpoints import (
    Checkpoint,
    EvolutionCheckpoints,
    get_evolution_checkpoints,
)
from kagami.core.evolution.ci_feedback_bridge import (
    CIFeedbackBridge,
    CIReport,
    CIReportParser,
    CISignal,
    CISignalType,
    ImprovementProposal,
    get_ci_feedback_bridge,
)
from kagami.core.evolution.continuous_evolution_engine import (
    ContinuousEvolutionEngine,
    EvolutionCycle,
    EvolutionPhase,
)
from kagami.core.evolution.dry_run_evaluator import (
    DryRunEvaluator,
    DryRunResult,
    get_dry_run_evaluator,
)
from kagami.core.evolution.evolution_controls import (
    EvolutionControls,
    EvolutionState,
    get_evolution_controls,
)
from kagami.core.evolution.fitness_functions import (
    EvolutionGuardrails,
    FitnessFunctions,
    FitnessScore,
    FitnessWeights,
    get_fitness_functions,
)
from kagami.core.evolution.improvement_ledger import (
    ImprovementLedger,
    LedgerEntry,
    get_improvement_ledger,
)

__all__ = [
    # Autonomous Improvement
    "AutonomousImprovementEngine",
    "ByzantineConsensus",
    # CI Feedback Bridge
    "CIFeedbackBridge",
    "CIReport",
    "CIReportParser",
    "CISignal",
    "CISignalType",
    # Canary
    "CanaryConfig",
    "CanaryRollout",
    "Checkpoint",
    "Colony",
    "ColonyAnalyzer",
    "ColonyScore",
    "ConsensusResult",
    # Engine
    "ContinuousEvolutionEngine",
    # Dry-run
    "DryRunEvaluator",
    "DryRunResult",
    # Checkpoints
    "EvolutionCheckpoints",
    # Controls
    "EvolutionControls",
    "EvolutionCycle",
    "EvolutionGuardrails",
    "EvolutionPhase",
    "EvolutionState",
    # Fitness
    "FitnessFunctions",
    "FitnessScore",
    "FitnessWeights",
    "ImprovementCategory",
    # Ledger
    "ImprovementLedger",
    "ImprovementPlan",
    "ImprovementPriority",
    "ImprovementProposal",
    "LedgerEntry",
    "RolloutStatus",
    "analyze_codebase",
    # Singletons
    "get_canary_rollout",
    "get_ci_feedback_bridge",
    "get_continuous_evolution_engine",
    "get_dry_run_evaluator",
    "get_evolution_checkpoints",
    "get_evolution_controls",
    "get_evolution_engine",
    "get_fitness_functions",
    "get_improvement_engine",
    "get_improvement_ledger",
    "get_improvement_plan",
    "get_report",
]

# Singleton accessor for full system
_evolution_engine: ContinuousEvolutionEngine | None = None


def get_evolution_engine() -> ContinuousEvolutionEngine:
    """Get global evolution engine."""
    global _evolution_engine
    if _evolution_engine is None:
        _evolution_engine = ContinuousEvolutionEngine()
    return _evolution_engine


# Alias for consistent naming
get_continuous_evolution_engine = get_evolution_engine
