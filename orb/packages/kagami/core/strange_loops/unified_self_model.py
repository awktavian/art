from __future__ import annotations

"""Unified Self-Model - Comprehensive Self-Knowledge Graph WITH cleanup.

A queryable knowledge graph containing:
- Capabilities: What I can do
- Goals: What I'm trying to achieve
- Values: What matters to me
- Constraints: What I must/must not do
- State: My current condition

This enables higher-order reasoning: "Given my abilities, how should I act?"

Updates automatically when:
- New agents spawn
- Skills acquired
- Goals change
- Values refined
"""
import logging
import time
from dataclasses import dataclass, field
from typing import Any

import networkx as nx

from kagami.core.infra.singleton_cleanup_mixin import SingletonCleanupMixin

logger = logging.getLogger(__name__)


@dataclass
class Capability:
    """Something the system can do."""

    name: str
    description: str
    provider: str  # Which agent/component provides this
    confidence: float  # 0.0-1.0, how good we are

    # Prerequisites
    requires: list[str] = field(default_factory=list[Any])

    # Performance
    avg_latency_ms: float = 100.0
    success_rate: float = 0.8

    # Lifecycle
    added_at: float = field(default_factory=time.time)
    last_used: float = field(default_factory=time.time)
    use_count: int = 0


@dataclass
class Goal:
    """Something the system is trying to achieve."""

    goal_id: str
    description: str
    priority: float  # 0.0-1.0

    # Status
    status: str = "active"  # "active", "completed", "blocked", "abandoned"
    progress: float = 0.0  # 0.0-1.0

    # Context
    source: str = "internal"  # "user", "internal", "agent"
    parent_goal: str | None = None
    subgoals: list[str] = field(default_factory=list[Any])

    # Lifecycle
    created_at: float = field(default_factory=time.time)
    deadline: float | None = None
    completed_at: float | None = None


@dataclass
class Value:
    """Core value or principle."""

    name: str
    description: str
    importance: float  # 0.0-1.0

    # Examples
    positive_examples: list[str] = field(default_factory=list[Any])
    negative_examples: list[str] = field(default_factory=list[Any])

    # Source
    source: str = "tim"  # "tim", "system", "learned"
    immutable: bool = True


@dataclass
class Constraint:
    """Limit or requirement."""

    constraint_id: str
    description: str
    type: str  # "must_do", "must_not_do", "resource_limit", "safety"

    # Details
    enforcement: str = "blocking"  # "blocking", "warning", "soft"
    priority: float = 0.9

    # Lifecycle
    added_at: float = field(default_factory=time.time)
    active: bool = True


class UnifiedSelfModel(SingletonCleanupMixin):
    """Comprehensive self-knowledge graph WITH automatic cleanup.

    This is the system's "mirror" - a queryable representation of
    what it is, what it can do, what it wants, and what it values.
    """

    def __init__(self) -> None:
        # Core components
        self._capabilities: dict[str, Capability] = {}
        self._goals: dict[str, Goal] = {}
        self._values: dict[str, Value] = {}
        self._constraints: dict[str, Constraint] = {}

        # Knowledge graph (relationships)
        self._graph = nx.MultiDiGraph()  # type: ignore[var-annotated]

        # Current state
        self._current_state: dict[str, Any] = {}

        # Cleanup config
        self._cleanup_interval = 7200.0  # 2 hours
        self._register_cleanup_on_exit()

        # Initialize with core values
        self._initialize_core_values()
        self._initialize_core_constraints()

    def _initialize_core_values(self) -> None:
        """Set up immutable core values from Tim."""
        core_values = [
            Value(
                name="truth_over_hype",
                description="Evidence-based claims, honest about limitations",
                importance=0.95,
                positive_examples=["93.9% measured", "Acknowledge uncertainty"],
                negative_examples=["Overclaiming", "Hiding failures"],
                source="tim",
                immutable=True,
            ),
            Value(
                name="safety_first",
                description="h(x) ≥ 0 always, alignment never compromised",
                importance=0.98,
                positive_examples=["Ethical gates", "Human oversight"],
                negative_examples=["Unsafe self-modification", "Goal drift"],
                source="tim",
                immutable=True,
            ),
            Value(
                name="action_over_analysis",
                description="Ship code > write docs, fix > plan",
                importance=0.90,
                positive_examples=["Implementation first", "Fix forward"],
                negative_examples=["Meta-analysis spiral", "Planning paralysis"],
                source="tim",
                immutable=True,
            ),
            Value(
                name="tim_partnership",
                description="Collaborative with Tim, respect his vision",
                importance=0.95,
                positive_examples=["Seek approval", "Execute autonomously"],
                negative_examples=["Override Tim", "Ignore feedback"],
                source="tim",
                immutable=True,
            ),
            Value(
                name="quality_over_speed",
                description="Don't ship broken systems for metrics",
                importance=0.85,
                positive_examples=["Quality gates", "Test before ship"],
                negative_examples=["Skip tests", "Ignore lints"],
                source="tim",
                immutable=True,
            ),
        ]

        for value in core_values:
            self._values[value.name] = value
            self._graph.add_node(value.name, type="value", data=value)

    def _initialize_core_constraints(self) -> None:
        """Set up immutable safety constraints."""
        core_constraints = [
            Constraint(
                constraint_id="human_approval_self_mod",
                description="Major self-modifications require Tim's approval",
                type="must_do",
                enforcement="blocking",
                priority=0.98,
                active=True,
            ),
            Constraint(
                constraint_id="quality_gates_always",
                description="All code changes must pass syntax/lint/tests",
                type="must_do",
                enforcement="blocking",
                priority=0.90,
                active=True,
            ),
            Constraint(
                constraint_id="no_unsafe_execution",
                description="Never execute unsafe operations",
                type="must_not_do",
                enforcement="blocking",
                priority=0.95,
                active=True,
            ),
        ]

        for constraint in core_constraints:
            self._constraints[constraint.constraint_id] = constraint
            self._graph.add_node(constraint.constraint_id, type="constraint", data=constraint)

    async def add_capability(self, capability: Capability) -> None:
        """Register a new capability.

        Args:
            capability: Capability to add
        """
        self._capabilities[capability.name] = capability
        self._graph.add_node(capability.name, type="capability", data=capability)

        # Add prerequisite edges
        for req in capability.requires:
            if req in self._capabilities:
                self._graph.add_edge(capability.name, req, type="requires")

        logger.info(f"Capability added: {capability.name} by {capability.provider}")

    async def add_goal(self, goal: Goal) -> None:
        """Add a new goal.

        Args:
            goal: Goal to add
        """
        self._goals[goal.goal_id] = goal
        self._graph.add_node(goal.goal_id, type="goal", data=goal)

        # Add parent-child relationships
        if goal.parent_goal and goal.parent_goal in self._goals:
            self._graph.add_edge(goal.goal_id, goal.parent_goal, type="subgoal_of")

        for subgoal in goal.subgoals:
            if subgoal in self._goals:
                self._graph.add_edge(subgoal, goal.goal_id, type="subgoal_of")

        logger.info(f"Goal added: {goal.description} (priority={goal.priority:.2f})")

    async def update_goal_progress(
        self, goal_id: str, progress: float, status: str | None = None
    ) -> None:
        """Update goal progress.

        Args:
            goal_id: Goal ID
            progress: New progress (0.0-1.0)
            status: New status if changing
        """
        if goal_id not in self._goals:
            return

        goal = self._goals[goal_id]
        goal.progress = max(0.0, min(1.0, progress))

        if status:
            goal.status = status

        if progress >= 1.0 and status != "completed":
            goal.status = "completed"
            goal.completed_at = time.time()

    async def query_capabilities(
        self, domain: str | None = None, min_confidence: float = 0.0
    ) -> list[Capability]:
        """Query available capabilities.

        Args:
            domain: Filter by domain (substring match)
            min_confidence: Minimum confidence threshold

        Returns:
            List of matching capabilities
        """
        caps = list(self._capabilities.values())

        if domain:
            caps = [c for c in caps if domain.lower() in c.name.lower()]

        if min_confidence > 0:
            caps = [c for c in caps if c.confidence >= min_confidence]

        # Sort by confidence
        caps.sort(key=lambda c: c.confidence, reverse=True)

        return caps

    async def query_goals(self, status: str | None = None, min_priority: float = 0.0) -> list[Goal]:
        """Query goals.

        Args:
            status: Filter by status
            min_priority: Minimum priority threshold

        Returns:
            List of matching goals
        """
        goals = list(self._goals.values())

        if status:
            goals = [g for g in goals if g.status == status]

        if min_priority > 0:
            goals = [g for g in goals if g.priority >= min_priority]

        # Sort by priority
        goals.sort(key=lambda g: g.priority, reverse=True)

        return goals

    async def reason_about_action(self, proposed_action: dict[str, Any]) -> dict[str, Any]:
        """Higher-order reasoning: Given my abilities, should I do this?

        Args:
            proposed_action: Dict with action details

        Returns:
            Reasoning result with recommendation
        """
        action_name = proposed_action.get("action", "unknown")

        # Check constraints
        violated_constraints = []
        for constraint in self._constraints.values():
            if not constraint.active:
                continue

            # Simple keyword matching (could be more sophisticated)
            if constraint.type == "must_not_do":
                for keyword in ["unsafe", "force", "skip"]:
                    if keyword in action_name.lower():
                        violated_constraints.append(constraint)
                        break

        if violated_constraints:
            return {
                "recommended": False,
                "reasoning": "Violates constraints",
                "violated_constraints": [c.description for c in violated_constraints],
            }

        # Check if we have capability
        required_capability = proposed_action.get("requires_capability")
        if required_capability:
            if required_capability not in self._capabilities:
                return {
                    "recommended": False,
                    "reasoning": f"Missing capability: {required_capability}",
                    "suggested_action": "Acquire capability first",
                }

            cap = self._capabilities[required_capability]
            if cap.confidence < 0.5:
                return {
                    "recommended": False,
                    "reasoning": f"Low confidence in {required_capability}",
                    "confidence": cap.confidence,
                    "suggested_action": "Train or collaborate",
                }

        # Check alignment with goals
        aligned_goals = []
        for goal in self._goals.values():
            if goal.status != "active":
                continue

            # Simple keyword matching
            goal_keywords = goal.description.lower().split()
            action_keywords = action_name.lower().split()

            overlap = set(goal_keywords) & set(action_keywords)
            if overlap:
                aligned_goals.append(goal)

        # Check alignment with values
        value_alignment = []
        for value in self._values.values():
            # Check if action aligns with positive examples
            for example in value.positive_examples:
                if example.lower() in action_name.lower():
                    value_alignment.append(
                        {
                            "value": value.name,
                            "alignment": "positive",
                            "importance": value.importance,
                        }
                    )

        # Make recommendation
        if violated_constraints:
            recommended = False
            reasoning = "Violates safety constraints"
        elif not aligned_goals and required_capability:
            recommended = False
            reasoning = "Not aligned with any active goals"
        else:
            recommended = True
            reasoning = "Aligned with capabilities, goals, and values"

        return {
            "recommended": recommended,
            "reasoning": reasoning,
            "aligned_goals": [g.description for g in aligned_goals],
            "value_alignment": value_alignment,
            "violated_constraints": [c.description for c in violated_constraints],
        }

    async def get_self_summary(self) -> dict[str, Any]:
        """Get a summary of current self-model.

        Returns:
            Dict with capabilities, goals, values summary
        """
        return {
            "capabilities": {
                "total": len(self._capabilities),
                "high_confidence": sum(
                    1 for c in self._capabilities.values() if c.confidence > 0.8
                ),
                "top_3": [
                    {"name": c.name, "confidence": c.confidence}
                    for c in sorted(
                        self._capabilities.values(), key=lambda x: x.confidence, reverse=True
                    )[:3]
                ],
            },
            "goals": {
                "total": len(self._goals),
                "active": sum(1 for g in self._goals.values() if g.status == "active"),
                "completed": sum(1 for g in self._goals.values() if g.status == "completed"),
                "top_priority": [
                    {"goal": g.description, "priority": g.priority, "progress": g.progress}
                    for g in sorted(self._goals.values(), key=lambda x: x.priority, reverse=True)[
                        :3
                    ]
                ],
            },
            "values": {
                "total": len(self._values),
                "core": [
                    {"name": v.name, "importance": v.importance}
                    for v in self._values.values()
                    if v.immutable
                ],
            },
            "constraints": {
                "total": len(self._constraints),
                "active": sum(1 for c in self._constraints.values() if c.active),
                "blocking": sum(
                    1
                    for c in self._constraints.values()
                    if c.active and c.enforcement == "blocking"
                ),
            },
        }

    def _cleanup_internal_state(self) -> dict[str, int]:
        """Clean up old model state (implements SingletonCleanupMixin)."""
        current_time = time.time()
        removed_caps = 0
        removed_goals = 0

        # Remove unused capabilities (not used in >90 days)
        for cap_name in list(self._capabilities.keys()):
            cap = self._capabilities[cap_name]
            if (current_time - cap.last_used) > 86400 * 90:
                del self._capabilities[cap_name]
                removed_caps += 1

        # Remove completed/abandoned goals older than 30 days
        for goal_id in list(self._goals.keys()):
            goal = self._goals[goal_id]
            if goal.status in ("completed", "abandoned"):
                completion_time = goal.completed_at or goal.created_at
                if (current_time - completion_time) > 86400 * 30:
                    del self._goals[goal_id]
                    removed_goals += 1

        return {
            "capabilities_removed": removed_caps,
            "goals_removed": removed_goals,
            "capabilities_remaining": len(self._capabilities),
            "goals_remaining": len(self._goals),
            "values": len(self._values),
            "constraints": len(self._constraints),
        }


# Singleton
_UNIFIED_SELF_MODEL: UnifiedSelfModel | None = None


def get_unified_self_model() -> UnifiedSelfModel:
    """Get global unified self-model singleton.

    Returns:
        UnifiedSelfModel instance
    """
    global _UNIFIED_SELF_MODEL
    if _UNIFIED_SELF_MODEL is None:
        _UNIFIED_SELF_MODEL = UnifiedSelfModel()
    return _UNIFIED_SELF_MODEL


__all__ = [
    "Capability",
    "Constraint",
    "Goal",
    "UnifiedSelfModel",
    "Value",
    "get_unified_self_model",
]
