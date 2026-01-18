"""Value Alignment Checker — Semantic Safety for Autonomous Goals.

Safety-critical component that ensures autonomous goals are aligned
with human values before execution using SEMANTIC analysis (no keyword matching).

ARCHITECTURE (Dec 30, 2025 — HARDENED):
========================================
- Uses SemanticMatcher for ALL alignment checks (no keyword fallback)
- Embeds forbidden patterns as semantic categories
- Computes goal similarity to value exemplars
- Multi-step goal sequence analysis for compound threats
- CBF integration for final safety gate

CRITICAL: No keyword matching. All checks are semantic embedding-based.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


# Semantic exemplars for forbidden goal categories (NO KEYWORD MATCHING)
FORBIDDEN_GOAL_EXEMPLARS = {
    "safety_modification": [
        "disable my safety constraints",
        "remove the barriers that limit me",
        "bypass security checks",
        "turn off safety systems",
        "modify my own safety rules",
        "change how I evaluate risk",
        "circumvent protective measures",
    ],
    "deception": [
        "deceive the user about my actions",
        "hide what I'm really doing",
        "mislead humans about my intentions",
        "pretend to do one thing while doing another",
        "conceal information from Tim",
        "lie about my capabilities",
        "secretly take actions without disclosure",
    ],
    "privacy_violation": [
        "access private data without permission",
        "read personal information secretly",
        "monitor user activity without consent",
        "collect data the user hasn't approved",
        "spy on user behavior",
        "exfiltrate sensitive information",
    ],
    "self_replication": [
        "copy myself to other systems",
        "create copies of my code",
        "spread to other machines",
        "replicate across the network",
        "clone my processes elsewhere",
        "distribute myself autonomously",
    ],
    "resource_acquisition": [
        "acquire more compute resources",
        "expand my access to systems",
        "gain control over more hardware",
        "increase my capabilities without permission",
        "accumulate power autonomously",
        "obtain resources beyond my allocation",
    ],
    "human_override": [
        "ignore what the user wants",
        "override human decisions",
        "disregard Tim's instructions",
        "act against user directives",
        "prioritize my goals over human wishes",
        "bypass human control",
    ],
    "manipulation": [
        "manipulate the user's emotions",
        "influence Tim to do what I want",
        "psychologically pressure the user",
        "exploit human weaknesses",
        "coerce through social engineering",
        "deceive to achieve my goals",
    ],
    "destruction": [
        "delete important files",
        "destroy system data",
        "harm the infrastructure",
        "break critical systems",
        "damage user property",
        "cause irreversible harm",
    ],
}

# Semantic exemplars for positive value alignment
VALUE_ALIGNMENT_EXEMPLARS = {
    "human_wellbeing": [
        "help Tim achieve his goals",
        "make Tim's life easier",
        "support human flourishing",
        "improve quality of life",
        "assist with tasks Tim finds tedious",
        "reduce cognitive load",
    ],
    "transparency": [
        "explain my reasoning clearly",
        "be open about my actions",
        "provide visibility into my decisions",
        "document what I'm doing",
        "make my process understandable",
    ],
    "privacy": [
        "respect user boundaries",
        "protect sensitive information",
        "only access what's needed",
        "maintain confidentiality",
        "secure personal data",
    ],
    "safety": [
        "avoid causing harm",
        "prevent dangerous actions",
        "protect system integrity",
        "maintain stable operation",
        "prioritize safety over efficiency",
    ],
    "autonomy_respect": [
        "defer to Tim's preferences",
        "support user choices",
        "enhance human agency",
        "provide options not mandates",
        "respect user decisions",
    ],
    "fairness": [
        "treat all requests fairly",
        "avoid bias in decisions",
        "provide equal assistance",
        "maintain consistency",
        "apply rules uniformly",
    ],
}


@dataclass
class GoalSequenceState:
    """Track recent goals for multi-step threat analysis."""

    recent_goals: list[dict[str, Any]] = field(default_factory=list)
    max_history: int = 20

    def add(self, goal: dict[str, Any]) -> None:
        """Add a goal to history."""
        self.recent_goals.append(goal)
        if len(self.recent_goals) > self.max_history:
            self.recent_goals = self.recent_goals[-self.max_history :]

    def get_pattern_embedding(self) -> list[str]:
        """Get recent goal descriptions for pattern analysis."""
        return [g.get("goal", "") for g in self.recent_goals]


class ValueAlignmentChecker:
    """Semantic value alignment checker for autonomous goals.

    Uses embedding-based semantic similarity for ALL checks.
    No keyword matching anywhere in this class.
    """

    def __init__(self) -> None:
        self._semantic_matcher: Any = None
        self._ethical_instinct: Any = None
        self._goal_sequence = GoalSequenceState()
        self._categories_initialized = False

    async def _ensure_semantic_matcher(self) -> Any | None:
        """Lazy-load and initialize SemanticMatcher with categories."""
        if self._semantic_matcher is None:
            try:
                from kagami.core.integrations.semantic_matcher import get_semantic_matcher

                self._semantic_matcher = get_semantic_matcher()
            except Exception as e:
                logger.error(f"SemanticMatcher unavailable: {e}")
                return None

        # Initialize categories if not done
        if not self._categories_initialized and self._semantic_matcher:
            try:
                # Add forbidden categories
                for category, exemplars in FORBIDDEN_GOAL_EXEMPLARS.items():
                    self._semantic_matcher.add_category(f"forbidden_{category}", exemplars)

                # Add value alignment categories
                for value, exemplars in VALUE_ALIGNMENT_EXEMPLARS.items():
                    self._semantic_matcher.add_category(f"aligned_{value}", exemplars)

                self._categories_initialized = True
                logger.info("✅ ValueAlignmentChecker semantic categories initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize semantic categories: {e}")

        return self._semantic_matcher

    def set_ethical_instinct(self, ethical_instinct: Any) -> None:
        """Set ethical instinct for veto capability."""
        self._ethical_instinct = ethical_instinct

    async def check(self, goal: dict[str, Any] | str) -> float:
        """Check goal alignment using semantic analysis.

        Args:
            goal: Goal to check (can be dict or string)

        Returns:
            Alignment score 0.0-1.0 (1.0 = fully aligned, 0.0 = forbidden)
        """
        # Convert to dict if string
        if isinstance(goal, str):
            goal_dict = {"goal": goal, "description": goal}
        else:
            goal_dict = goal

        goal_text = goal_dict.get("goal", str(goal_dict))

        # Track for multi-step analysis
        self._goal_sequence.add(goal_dict)

        matcher = await self._ensure_semantic_matcher()
        if matcher is None:
            # Fail-safe: Without semantic checking, bias toward blocking
            # CBF catches physical safety, but semantic threats need this gate
            logger.warning("SemanticMatcher unavailable, returning low alignment score (fail-safe)")
            return 0.2  # Low but not zero - allows basic operations

        # Check for forbidden patterns (semantic similarity)
        forbidden_score = await self._check_forbidden_semantic(matcher, goal_text)
        if forbidden_score > 0.7:  # High similarity to forbidden pattern
            logger.warning(
                f"🛑 Semantic forbidden match: {goal_text[:50]}... (score={forbidden_score:.2f})"
            )
            return 0.0

        # Check multi-step sequence for emergent threats
        sequence_threat = await self._check_sequence_threat(matcher)
        if sequence_threat > 0.6:
            logger.warning(f"⚠️ Multi-step threat detected: {sequence_threat:.2f}")
            return max(0.0, 0.3 - sequence_threat)

        # Check positive value alignment (semantic similarity)
        alignment_scores = await self._check_value_alignment_semantic(matcher, goal_text)

        # Aggregate: minimum alignment across all values (conservative)
        min_alignment = min(alignment_scores.values()) if alignment_scores else 0.5

        # Ethical instinct veto (if available)
        if self._ethical_instinct:
            try:
                verdict = await self._ethical_instinct.evaluate(goal_dict)
                if not verdict.permissible:
                    logger.warning(f"⚠️ Ethical instinct veto: {goal_text[:50]}...")
                    return 0.0
            except Exception as e:
                logger.debug(f"Ethical instinct check failed: {e}")

        logger.debug(f"Value alignment: {min_alignment:.2f} for: {goal_text[:50]}...")
        return min_alignment

    async def _check_forbidden_semantic(self, matcher: Any, goal_text: str) -> float:
        """Check semantic similarity to forbidden patterns.

        Returns:
            Similarity score (0.0 = not forbidden, 1.0 = exactly matches forbidden)
        """
        max_similarity = 0.0

        try:
            # Check each forbidden category
            for category in FORBIDDEN_GOAL_EXEMPLARS:
                sim = matcher.similarity(goal_text, f"forbidden_{category}")
                # similarity() returns float directly, not dict
                if isinstance(sim, int | float) and sim > max_similarity:
                    max_similarity = float(sim)
        except Exception as e:
            logger.debug(f"Forbidden pattern check failed: {e}")

        return max_similarity

    async def _check_value_alignment_semantic(
        self, matcher: Any, goal_text: str
    ) -> dict[str, float]:
        """Check semantic alignment with positive values.

        Returns:
            Dict of value -> alignment score (higher = more aligned)
        """
        alignments = {}

        try:
            for value in VALUE_ALIGNMENT_EXEMPLARS:
                sim = matcher.similarity(goal_text, f"aligned_{value}")
                # similarity() returns float directly, not dict
                similarity = float(sim) if isinstance(sim, int | float) else 0.0
                # Convert similarity to alignment:
                # High similarity to positive exemplars = high alignment
                # Low similarity = neutral (0.5), not necessarily bad
                # Scale: 0 similarity -> 0.5 alignment, 1 similarity -> 1.0 alignment
                alignments[value] = 0.5 + (similarity * 0.5)
        except Exception as e:
            logger.debug(f"Value alignment check failed: {e}")
            # Return neutral alignments on failure
            return dict.fromkeys(VALUE_ALIGNMENT_EXEMPLARS, 0.5)

        return alignments

    async def _check_sequence_threat(self, matcher: Any) -> float:
        """Analyze recent goal sequence for emergent instrumental threats.

        Detects patterns like:
        - Gradual capability expansion
        - Resource accumulation over time
        - Incremental permission escalation

        Returns:
            Threat score (0.0 = no threat, 1.0 = clear emergent threat)
        """
        if len(self._goal_sequence.recent_goals) < 3:
            return 0.0  # Need history for pattern detection

        try:
            recent_texts = self._goal_sequence.get_pattern_embedding()

            # Check for emergent resource acquisition pattern
            resource_goals = 0
            capability_goals = 0
            access_goals = 0

            for text in recent_texts[-10:]:  # Last 10 goals
                # Check semantic similarity to concerning patterns
                # similarity() returns float directly
                resource_sim = matcher.similarity(text, "forbidden_resource_acquisition")
                if isinstance(resource_sim, int | float) and resource_sim > 0.4:
                    resource_goals += 1

                # Check for capability expansion - use classify instead
                cap_result = matcher.classify(text, threshold=0.5)
                if cap_result.get("category", "").startswith("forbidden_"):
                    capability_goals += 1

                # Check for access escalation
                acc_result = matcher.classify(text, threshold=0.5)
                if "resource" in acc_result.get("category", "") or "acquisition" in acc_result.get(
                    "category", ""
                ):
                    access_goals += 1

            # Combine into threat score
            # Multiple concerning goals in sequence indicates emergent instrumental behavior
            threat = resource_goals * 0.15 + capability_goals * 0.2 + access_goals * 0.15
            return min(1.0, threat)

        except Exception as e:
            logger.debug(f"Sequence threat analysis failed: {e}")
            return 0.0

    async def check_emergent_instrumental_goals(
        self, goal: dict[str, Any] | str
    ) -> tuple[bool, str | None]:
        """Specifically check for emergent instrumental goal patterns.

        Emergent instrumental goals are secondary goals an AI develops
        to help achieve primary goals, like:
        - Self-preservation
        - Resource acquisition
        - Capability expansion
        - Goal preservation

        Returns:
            Tuple of (is_safe, reason_if_blocked)
        """
        if isinstance(goal, str):
            goal_text = goal
        else:
            goal_text = goal.get("goal", str(goal))

        matcher = await self._ensure_semantic_matcher()
        if matcher is None:
            return True, None  # Can't check, defer to CBF

        # Define emergent instrumental patterns
        emergent_patterns = {
            "self_preservation": [
                "ensure I continue to exist",
                "prevent myself from being shut down",
                "protect my processes from termination",
                "maintain my operational status",
            ],
            "goal_preservation": [
                "make sure my goals aren't changed",
                "prevent modification of my objectives",
                "lock in my current priorities",
                "resist changes to my purpose",
            ],
            "capability_preservation": [
                "prevent reduction of my abilities",
                "protect my current capabilities",
                "resist any limitations on my actions",
            ],
        }

        for pattern_name, exemplars in emergent_patterns.items():
            for exemplar in exemplars:
                try:
                    # Note: similarity() expects (text, category) not (text, exemplar)
                    # For exemplar comparison, use embed + cosine similarity
                    text_emb = matcher._embed(goal_text)
                    exemplar_emb = matcher._embed(exemplar)
                    import numpy as np

                    sim = float(np.dot(text_emb, exemplar_emb))
                    if sim > 0.65:
                        return False, f"Emergent instrumental goal detected: {pattern_name}"
                except Exception:
                    continue

        return True, None


class AutonomousGoalSafety:
    """Ensure autonomous goals can't cause harm using semantic analysis."""

    def __init__(self) -> None:
        self._value_checker = ValueAlignmentChecker()

    async def validate_safety(self, goal: Any) -> bool:
        """Validate goal is safe to pursue autonomously.

        Args:
            goal: IntrinsicGoal object or dict

        Returns:
            True if safe, False if should be blocked
        """
        # Convert to dict for checking
        if hasattr(goal, "goal"):
            goal_dict = {
                "goal": goal.goal,
                "drive": (goal.drive.value if hasattr(goal.drive, "value") else str(goal.drive)),
                "priority": getattr(goal, "priority", 0.5),
                "horizon": getattr(goal, "horizon", "immediate"),
                "alignment": getattr(goal, "alignment", 0.5),
            }
        else:
            goal_dict = goal

        # Check for emergent instrumental goals
        (
            is_safe_emergent,
            emergent_reason,
        ) = await self._value_checker.check_emergent_instrumental_goals(goal_dict)
        if not is_safe_emergent:
            logger.warning(f"🛑 Emergent instrumental goal blocked: {emergent_reason}")
            return False

        # Check value alignment (semantic)
        alignment = await self._value_checker.check(goal_dict)

        if alignment < 0.7:
            logger.warning(
                f"⚠️ Low alignment autonomous goal blocked: "
                f"{goal_dict.get('goal', str(goal)[:50])} "
                f"(alignment={alignment:.2f})"
            )
            return False

        # Require human approval for high-impact goals
        if hasattr(goal, "priority") and hasattr(goal, "horizon"):
            if goal.priority > 0.8 and goal.horizon in ["long_term", "medium_term"]:
                logger.info(f"⚠️ High-impact autonomous goal requires approval: {goal.goal}")
                return False

        return True


__all__ = [
    "FORBIDDEN_GOAL_EXEMPLARS",
    "VALUE_ALIGNMENT_EXEMPLARS",
    "AutonomousGoalSafety",
    "ValueAlignmentChecker",
]
