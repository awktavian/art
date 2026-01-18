"""Motivation — Intrinsic Drives and Goal Hierarchies.

ARCHITECTURE (Jan 1, 2026 — SELF-ACTUALIZED):
==============================================
Primary goal selection now via Active Inference EFE in autonomous_goal_engine.py.
This package provides supporting abstractions:
- Drive/IntrinsicGoal: Goal representation types
- ValueAlignmentChecker: Semantic safety checking
- IntelligentActionMapper: LLM goal→action (legacy, deprecated)
- PhysicalPolicySpace: SmartHome execution with CBF safety
- DriveSystem: Drive state tracking

DELETED (redundant with EFE):
- MaslowHierarchy: Replaced by EFE epistemic/pragmatic computation
- ProactiveGoalGenerator: Replaced by EFE capability discovery
"""

# Drive System with real history
from .drive_system import (
    DriveSnapshot,
    DriveState,
    DriveSystem,
    get_drive_system,
    reset_drive_system,
    set_drive_system,
)
from .goal_hierarchy import (
    CONFLICT_EXEMPLAR_PAIRS,
    GoalExecutionRecord,
    GoalHierarchyManager,
)
from .intelligent_action_mapper import (
    SEMANTIC_ACTION_EXEMPLARS,
    SEMANTIC_PHYSICAL_EXEMPLARS,
    IntelligentActionMapper,
    get_intelligent_action_mapper,
    reset_intelligent_action_mapper,
    sanitize_context,
    sanitize_goal_input,
)
from .intrinsic_motivation import (
    Drive,
    IntrinsicGoal,
    IntrinsicMotivationSystem,
)

# Physical Policy Space with CBF safety
from .physical_policy_space import (
    SECURITY_ACTIONS,
    VALID_ROOMS,
    PhysicalActionResult,
    PhysicalPolicySpace,
    get_physical_policy_space,
    reset_physical_policy_space,
)
from .value_alignment import (
    FORBIDDEN_GOAL_EXEMPLARS,
    VALUE_ALIGNMENT_EXEMPLARS,
    AutonomousGoalSafety,
    ValueAlignmentChecker,
)
from .value_discovery import (
    ImplicitValue,
    ValueDiscovery,
)

__all__ = [
    "CONFLICT_EXEMPLAR_PAIRS",
    "FORBIDDEN_GOAL_EXEMPLARS",
    "SECURITY_ACTIONS",
    "SEMANTIC_ACTION_EXEMPLARS",
    "SEMANTIC_PHYSICAL_EXEMPLARS",
    "VALID_ROOMS",
    "VALUE_ALIGNMENT_EXEMPLARS",
    # Value Alignment (semantic)
    "AutonomousGoalSafety",
    # Intrinsic Motivation
    "Drive",
    "DriveSnapshot",
    "DriveState",
    # Drive System (with history)
    "DriveSystem",
    "GoalExecutionRecord",
    # Goal Hierarchy (semantic coherence)
    "GoalHierarchyManager",
    # Value Discovery
    "ImplicitValue",
    # Intelligent Action Mapper (legacy, deprecated)
    "IntelligentActionMapper",
    "IntrinsicGoal",
    "IntrinsicMotivationSystem",
    "PhysicalActionResult",
    # Physical Policy Space (with CBF safety)
    "PhysicalPolicySpace",
    "ValueAlignmentChecker",
    "ValueDiscovery",
    "get_drive_system",
    "get_intelligent_action_mapper",
    "get_physical_policy_space",
    "reset_drive_system",
    "reset_intelligent_action_mapper",
    "reset_physical_policy_space",
    "sanitize_context",
    "sanitize_goal_input",
    "set_drive_system",
]
