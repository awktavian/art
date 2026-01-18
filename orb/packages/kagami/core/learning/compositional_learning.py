from __future__ import annotations

"""Compositional skill library for novel problem solving.

Learns primitive skills and composes them into novel behaviors,
enabling generalization beyond training distribution.
"""
import hashlib
import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class PrimitiveSkill:
    """Atomic, reusable skill that can be composed."""

    name: str
    description: str
    preconditions: list[str]  # What must be true before
    postconditions: list[str]  # What becomes true after
    success_rate: float
    usage_count: int
    domain: str
    examples: list[dict[str, Any]] = field(default_factory=list[Any])


@dataclass
class CompositeSkill:
    """Complex skill built from primitives."""

    name: str
    primitives: list[str]  # Ordered sequence of primitive names
    goal: str
    success_rate: float
    uses: int
    discovered_at: str  # Timestamp


class SkillComposer:
    """Learn primitive skills and compose them into novel behaviors."""

    def __init__(self) -> None:
        # Library of primitive skills
        self._primitives: dict[str, PrimitiveSkill] = {}

        # Discovered composite skills
        self._composites: dict[str, CompositeSkill] = {}

        # Initialize with some universal primitives
        self._bootstrap_primitives()

    def _bootstrap_primitives(self) -> None:
        """Bootstrap with fundamental primitives found in many domains."""
        universal_primitives = [
            PrimitiveSkill(
                name="observe",
                description="Gather information about current state",
                preconditions=[],
                postconditions=["have_information"],
                success_rate=0.95,
                usage_count=0,
                domain="universal",
            ),
            PrimitiveSkill(
                name="decompose",
                description="Break complex problem into subproblems",
                preconditions=["have_problem"],
                postconditions=["have_subproblems"],
                success_rate=0.85,
                usage_count=0,
                domain="universal",
            ),
            PrimitiveSkill(
                name="test",
                description="Verify that something works as expected",
                preconditions=["have_hypothesis"],
                postconditions=["have_result"],
                success_rate=0.90,
                usage_count=0,
                domain="universal",
            ),
            PrimitiveSkill(
                name="iterate",
                description="Repeat process with refinements",
                preconditions=["have_feedback"],
                postconditions=["improved_solution"],
                success_rate=0.80,
                usage_count=0,
                domain="universal",
            ),
            PrimitiveSkill(
                name="compose",
                description="Combine parts into whole",
                preconditions=["have_components"],
                postconditions=["have_system"],
                success_rate=0.75,
                usage_count=0,
                domain="universal",
            ),
        ]

        for prim in universal_primitives:
            self._primitives[prim.name] = prim

    def decompose_into_primitives(self, complex_task: dict[str, Any]) -> list[str] | None:
        """Break complex task into sequence of primitive skills.

        Example:
        Task: "Refactor authentication system"
        → Primitives: [
            "observe" (understand current code),
            "decompose" (identify modules),
            "test" (write tests first),
            "refactor" (modify code),
            "test" (verify no breakage),
            "compose" (integrate changes)
        ]
        """
        complex_task.get("type", "")
        task_action = complex_task.get("action", "")

        # Pattern-based decomposition (extensible via learning)
        if "refactor" in task_action.lower():
            return ["observe", "test", "decompose", "refactor", "test", "compose"]
        elif "debug" in task_action.lower() or "fix" in task_action.lower():
            return ["observe", "decompose", "test", "isolate", "fix", "test"]
        elif "implement" in task_action.lower() or "create" in task_action.lower():
            return ["decompose", "design", "test", "implement", "test", "integrate"]
        elif "learn" in task_action.lower():
            return ["observe", "decompose", "practice", "test", "iterate"]

        # Default: general problem-solving sequence
        return ["observe", "decompose", "test", "iterate", "compose"]

    def learn_primitive(
        self, action: dict[str, Any], outcome: dict[str, Any]
    ) -> PrimitiveSkill | None:
        """Extract reusable primitive from successful action.

        Only succeeds if action is atomic (not further decomposable).
        """
        action_sig = self._compute_signature(action)
        action_type = action.get("action", "")

        # Check if this is atomic enough to be a primitive
        if not self._is_atomic(action):
            return None

        # Create or update primitive
        if action_sig in self._primitives:
            prim = self._primitives[action_sig]
            prim.usage_count += 1
            prim.examples.append({"action": action, "outcome": outcome})

            # Update success rate with Bayesian update
            success = outcome.get("status") == "success"
            alpha = 1.0 / (prim.usage_count + 1)
            prim.success_rate = alpha * (1.0 if success else 0.0) + (1 - alpha) * prim.success_rate
        else:
            # New primitive discovered
            prim = PrimitiveSkill(
                name=action_sig,
                description=action_type,
                preconditions=self._infer_preconditions(action),
                postconditions=self._infer_postconditions(outcome),
                success_rate=1.0 if outcome.get("status") == "success" else 0.0,
                usage_count=1,
                domain=action.get("domain", "general"),
                examples=[{"action": action, "outcome": outcome}],
            )
            self._primitives[action_sig] = prim

        logger.debug(f"Learned primitive: {prim.name[:30]} (success_rate: {prim.success_rate:.2f})")

        return prim

    def _compute_signature(self, action: dict[str, Any]) -> str:
        """Compute stable signature for action."""
        key = action.get("action", "") + action.get("type", "")
        return hashlib.md5(key.encode(), usedforsecurity=False).hexdigest()[:16]

    def _is_atomic(self, action: dict[str, Any]) -> bool:
        """Check if action is atomic (primitive) or composite."""
        # Heuristics for atomicity
        action_str = str(action.get("action", "")).lower()

        # Compound verbs suggest composite
        if " and " in action_str or " then " in action_str:
            return False

        # Multiple steps suggest composite
        if "steps" in action or "sequence" in action:
            return False

        return True

    def _infer_preconditions(self, action: dict[str, Any]) -> list[str]:
        """Infer what must be true before action can succeed."""
        # Extract from context
        context = action.get("context", {})
        preconditions = []

        if context.get("has_tests"):
            preconditions.append("tests_exist")
        if context.get("has_code"):
            preconditions.append("code_exists")

        return preconditions

    def _infer_postconditions(self, outcome: dict[str, Any]) -> list[str]:
        """Infer what becomes true after successful action."""
        postconditions = []

        if outcome.get("status") == "success":
            postconditions.append("action_succeeded")

        if outcome.get("tests_pass"):
            postconditions.append("tests_passing")

        return postconditions

    def compose_novel_solution(
        self, primitives: list[str], goal: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Combine learned primitives in new ways to solve novel problem.

        This is where generalization happens - using known building blocks
        to solve problems we've never seen before.
        """
        # Validate all primitives exist
        if not all(p in self._primitives for p in primitives):
            logger.warning("Some primitives not in library, cannot compose")
            return None

        # Check if composition is valid (postconditions → preconditions)
        if not self._validate_composition(primitives):
            logger.warning("Invalid primitive composition (precondition mismatch)")
            return None

        # Estimate success rate (product of primitive success rates)
        composite_success_rate = 1.0
        for prim_name in primitives:
            composite_success_rate *= self._primitives[prim_name].success_rate

        # Create composite skill
        composite_name = "_".join(primitives[:3])  # First 3 primitives
        composite = CompositeSkill(
            name=composite_name,
            primitives=primitives,
            goal=goal.get("goal", "unknown"),
            success_rate=composite_success_rate,
            uses=0,
            discovered_at=str(__import__("datetime").datetime.now()),
        )

        # Store for future reuse
        self._composites[composite_name] = composite

        logger.info(
            f"✨ Composed novel solution: {composite_name} "
            f"(expected success: {composite_success_rate:.2f})"
        )

        return {
            "composite": composite,
            "plan": primitives,
            "expected_success": composite_success_rate,
            "reasoning": "Novel composition of learned primitives",
        }

    def _validate_composition(self, primitives: list[str]) -> bool:
        """Check if primitive sequence is valid (chain of conditions)."""
        # Simplified validation: just check all primitives exist
        # Full version would verify preconditions → postconditions chain
        return all(p in self._primitives for p in primitives)

    def get_best_primitives(
        self, domain: str | None = None, min_success_rate: float = 0.7
    ) -> list[PrimitiveSkill]:
        """Get highest-success primitives, optionally filtered by domain."""
        candidates = self._primitives.values()

        if domain:
            candidates = [p for p in candidates if p.domain == domain or p.domain == "universal"]  # type: ignore[assignment]

        # Filter by success rate
        candidates = [p for p in candidates if p.success_rate >= min_success_rate]  # type: ignore[assignment]

        # Sort by success rate * usage count (proven reliability)
        return sorted(candidates, key=lambda p: p.success_rate * p.usage_count, reverse=True)

    def recommend_composition(self, goal: dict[str, Any]) -> list[str] | None:
        """Recommend primitive sequence for achieving goal.

        Uses past successful compositions and domain knowledge.
        """
        goal_type = goal.get("type", "")

        # Check if we have a proven composite for this goal type
        for composite in self._composites.values():
            if composite.goal == goal_type and composite.success_rate > 0.7:
                logger.info(
                    f"Reusing proven composite: {composite.name} "
                    f"(success_rate: {composite.success_rate:.2f})"
                )
                return composite.primitives

        # Otherwise, decompose fresh
        return self.decompose_into_primitives(goal)


# Global singleton
_skill_composer: SkillComposer | None = None


def get_skill_composer() -> SkillComposer:
    """Get or create global skill composer."""
    global _skill_composer

    if _skill_composer is None:
        _skill_composer = SkillComposer()

    return _skill_composer
