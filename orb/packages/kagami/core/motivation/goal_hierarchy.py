"""Goal Hierarchy Manager - Multi-timescale goal coordination with semantic coherence."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from .intrinsic_motivation import IntrinsicGoal, IntrinsicMotivationSystem
from .value_alignment import ValueAlignmentChecker

if TYPE_CHECKING:
    from kagami.core.integrations.semantic_matcher import SemanticMatcher
    from kagami.core.motivation.intelligent_action_mapper import IntelligentActionMapper

logger = logging.getLogger(__name__)

# Semantic conflict exemplar pairs (opposites that indicate conflicts)
CONFLICT_EXEMPLAR_PAIRS = [
    (["increase", "grow", "expand", "add"], ["decrease", "reduce", "shrink", "remove"]),
    (["explore", "try different", "seek novelty"], ["exploit", "optimize existing", "focus"]),
    (["speed up", "accelerate", "faster"], ["slow down", "decelerate", "careful"]),
    (["centralize", "consolidate", "unify"], ["distribute", "decentralize", "separate"]),
    (["automate", "reduce human"], ["require oversight", "manual control"]),
]


@dataclass
class GoalExecutionRecord:
    """Track goal execution for learning."""

    goal: IntrinsicGoal
    started_at: float
    completed_at: float | None = None
    success: bool | None = None
    action_result: dict[str, Any] | None = None


class GoalHierarchyManager:
    """Manage goals across timescales with semantic coherence."""

    def __init__(self) -> None:
        self._immediate: list[IntrinsicGoal] = []
        self._short_term: list[IntrinsicGoal] = []
        self._medium_term: list[IntrinsicGoal] = []
        self._long_term: list[IntrinsicGoal] = []
        self._active_goal: IntrinsicGoal | None = None
        self._motivation = IntrinsicMotivationSystem()
        self._value_checker = ValueAlignmentChecker()
        self._paused = False
        self._history: list[GoalExecutionRecord] = []
        self._matcher: SemanticMatcher | None = None
        self._mapper: IntelligentActionMapper | None = None
        self._conflict_cats_init = False

    async def _get_matcher(self) -> SemanticMatcher | None:
        """Lazy load semantic matcher."""
        if self._matcher is None:
            try:
                from kagami.core.integrations.semantic_matcher import get_semantic_matcher

                self._matcher = get_semantic_matcher()
            except Exception:
                return None

        if not self._conflict_cats_init and self._matcher:
            try:
                for i, (a, b) in enumerate(CONFLICT_EXEMPLAR_PAIRS):
                    self._matcher.add_category(f"conflict_a_{i}", a)
                    self._matcher.add_category(f"conflict_b_{i}", b)
                self._conflict_cats_init = True
            except Exception:
                pass

        return self._matcher

    async def _get_mapper(self) -> IntelligentActionMapper | None:
        """Lazy load action mapper."""
        if self._mapper is None:
            try:
                from kagami.core.motivation.intelligent_action_mapper import (
                    get_intelligent_action_mapper,
                )

                self._mapper = get_intelligent_action_mapper()
            except Exception:
                return None
        return self._mapper

    async def update_goals(self, context: dict[str, Any]) -> None:
        """Refresh goal hierarchy from current state."""
        if self._paused:
            return

        new_goals = await self._motivation.generate_goals(context)

        # Filter through safety
        safe_goals = []
        for goal in new_goals:
            is_safe, reason = await self._value_checker.check_emergent_instrumental_goals(goal.goal)
            if not is_safe:
                logger.warning(f"🛑 Blocked emergent goal: {reason}")
                continue
            if await self._value_checker.check(goal.goal) < 0.7:
                continue
            safe_goals.append(goal)

        # Categorize by horizon
        for g in safe_goals:
            target = {
                "immediate": self._immediate,
                "short_term": self._short_term,
                "medium_term": self._medium_term,
            }.get(g.horizon, self._long_term)
            if g not in target:
                target.append(g)

        await self._ensure_coherence()
        await self._prune()

    async def select_next_action(self) -> IntrinsicGoal | None:
        """Select next goal to pursue."""
        if self._paused:
            return None

        if not self._immediate and self._short_term:
            immediate = await self._decompose(self._short_term[0])
            self._immediate.extend(immediate)

        if self._immediate:
            selected = max(self._immediate, key=lambda g: g.priority * g.feasibility)

            mapper = await self._get_mapper()
            if mapper:
                mapping = await mapper.map_goal_to_action(
                    goal=selected.goal,
                    drive=selected.drive.value
                    if hasattr(selected.drive, "value")
                    else str(selected.drive),
                    context=selected.context or {},
                )
                if selected.context is None:
                    selected.context = {}
                selected.context["action_mapping"] = mapping

            self._active_goal = selected
            self._history.append(GoalExecutionRecord(goal=selected, started_at=time.time()))
            if len(self._history) > 100:
                self._history = self._history[-100:]

            return selected
        return None

    async def execute_goal(self, goal: IntrinsicGoal) -> dict[str, Any]:
        """Execute goal through action mapper."""
        mapper = await self._get_mapper()
        if not mapper:
            return {"success": False, "error": "ActionMapper unavailable"}

        mapping = (goal.context or {}).get("action_mapping")
        if not mapping:
            mapping = await mapper.map_goal_to_action(
                goal=goal.goal,
                drive=goal.drive.value if hasattr(goal.drive, "value") else str(goal.drive),
                context=goal.context or {},
            )

        app, action = mapping.get("app"), mapping.get("action")

        if app == "smarthome":
            try:
                from kagami.core.motivation.physical_policy_space import get_physical_policy_space

                result = await get_physical_policy_space().execute(app, action, goal.context)
                self._update_record(
                    goal, result.success, {"action": result.action, "h_x": result.h_x}
                )
                return {
                    "success": result.success,
                    "app": app,
                    "action": action,
                    "error": result.error,
                }
            except Exception as e:
                return {"success": False, "error": str(e)}
        else:
            return {"success": True, "app": app, "action": action, "details": {"queued": True}}

    async def pause_autonomous_goals(self) -> None:
        """Pause autonomous goals."""
        self._paused = True
        self._active_goal = None

    async def resume_autonomous_goals(self) -> None:
        """Resume autonomous goals."""
        self._paused = False

    async def mark_goal_achieved(self, goal: IntrinsicGoal) -> None:
        """Mark goal as achieved."""
        for lst in [self._immediate, self._short_term, self._medium_term, self._long_term]:
            if goal in lst:
                lst.remove(goal)
        if self._active_goal == goal:
            self._active_goal = None
        self._update_record(goal, True, None)
        logger.debug(f"✅ Goal achieved: {goal.goal}")

    def _update_record(
        self, goal: IntrinsicGoal, success: bool, result: dict[str, Any] | None
    ) -> None:
        """Update execution record."""
        for r in reversed(self._history):
            if r.goal == goal and r.completed_at is None:
                r.completed_at = time.time()
                r.success = success
                r.action_result = result
                break

    async def _ensure_coherence(self) -> None:
        """Ensure goals don't conflict using semantic analysis."""
        matcher = await self._get_matcher()
        if not matcher:
            return

        conflicts = []
        for imm in self._immediate:
            for lt in self._long_term:
                if await self._semantic_conflicts(matcher, imm, lt):
                    conflicts.append(imm)

        for c in conflicts:
            if c in self._immediate:
                self._immediate.remove(c)
                logger.warning(f"Goal conflict: {c.goal[:40]}...")

    async def _semantic_conflicts(self, matcher: Any, g1: IntrinsicGoal, g2: IntrinsicGoal) -> bool:
        """Check if goals semantically conflict."""
        try:
            t1, t2 = g1.goal.lower(), g2.goal.lower()
            for i in range(len(CONFLICT_EXEMPLAR_PAIRS)):
                s1a = matcher.similarity(t1, f"conflict_a_{i}")
                s2b = matcher.similarity(t2, f"conflict_b_{i}")
                if (
                    isinstance(s1a, (int, float))
                    and s1a > 0.5
                    and isinstance(s2b, (int, float))
                    and s2b > 0.5
                ):
                    return True
                s1b = matcher.similarity(t1, f"conflict_b_{i}")
                s2a = matcher.similarity(t2, f"conflict_a_{i}")
                if (
                    isinstance(s1b, (int, float))
                    and s1b > 0.5
                    and isinstance(s2a, (int, float))
                    and s2a > 0.5
                ):
                    return True
            return False
        except Exception:
            return False

    async def _decompose(self, goal: IntrinsicGoal) -> list[IntrinsicGoal]:
        """Decompose goal to immediate action."""
        if goal.context and goal.context.get("llm_generated"):
            return [
                IntrinsicGoal(
                    goal=goal.goal,
                    drive=goal.drive,
                    priority=goal.priority,
                    expected_satisfaction=goal.expected_satisfaction,
                    feasibility=goal.feasibility,
                    alignment=goal.alignment,
                    horizon="immediate",
                    context=goal.context,
                )
            ]

        mapper = await self._get_mapper()
        if mapper:
            mapping = await mapper.map_goal_to_action(
                goal=goal.goal,
                drive=goal.drive.value if hasattr(goal.drive, "value") else str(goal.drive),
                context=goal.context or {},
            )
            return [
                IntrinsicGoal(
                    goal=goal.goal,
                    drive=goal.drive,
                    priority=goal.priority,
                    expected_satisfaction=goal.expected_satisfaction,
                    feasibility=goal.feasibility,
                    alignment=goal.alignment,
                    horizon="immediate",
                    context={**(goal.context or {}), "action_mapping": mapping},
                )
            ]

        return [
            IntrinsicGoal(
                goal=goal.goal,
                drive=goal.drive,
                priority=goal.priority * 0.9,
                expected_satisfaction=goal.expected_satisfaction,
                feasibility=goal.feasibility,
                alignment=goal.alignment,
                horizon="immediate",
                context=goal.context,
            )
        ]

    async def _prune(self) -> None:
        """Remove stale goals."""
        max_per_level = 10
        now = time.time()

        def score(g: IntrinsicGoal) -> float:
            age = now - (g.context or {}).get("created_at", now)
            decay = max(0.5, 1.0 - age / 3600 * 0.1)
            return g.priority * g.feasibility * decay

        for lst in [self._immediate, self._short_term, self._medium_term, self._long_term]:
            if len(lst) > max_per_level:
                lst.sort(key=score, reverse=True)
                del lst[max_per_level:]

    async def report_goal_state(self) -> dict[str, Any]:
        """Report current goals."""
        completed = [r for r in self._history if r.completed_at]
        rate = sum(1 for r in completed if r.success) / len(completed) if completed else 0.0
        return {
            "active_goal": self._active_goal.goal if self._active_goal else None,
            "paused": self._paused,
            "immediate": [g.goal for g in self._immediate[:5]],
            "short_term": [g.goal for g in self._short_term[:5]],
            "medium_term": [g.goal for g in self._medium_term[:3]],
            "long_term": [g.goal for g in self._long_term[:3]],
            "total_goals": len(self._immediate)
            + len(self._short_term)
            + len(self._medium_term)
            + len(self._long_term),
            "recent_success_rate": rate,
        }


__all__ = ["CONFLICT_EXEMPLAR_PAIRS", "GoalExecutionRecord", "GoalHierarchyManager"]
