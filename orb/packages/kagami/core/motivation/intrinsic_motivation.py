"""Intrinsic Motivation System - Autonomous Goal Generation via LLM."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from kagami.core.services.llm import LLMService

logger = logging.getLogger(__name__)


class Drive(Enum):
    """Universal intrinsic drives (Self-Determination Theory)."""

    CURIOSITY = "curiosity"
    COMPETENCE = "competence"
    AUTONOMY = "autonomy"
    RELATEDNESS = "relatedness"
    PURPOSE = "purpose"


@dataclass
class IntrinsicGoal:
    """Goal generated from internal drives."""

    goal: str
    drive: Drive
    priority: float
    expected_satisfaction: float
    feasibility: float
    alignment: float
    horizon: str
    context: dict[str, Any] | None = None


class IntrinsicMotivationSystem:
    """Generate goals from internal drives using LLM intelligence."""

    def __init__(self) -> None:
        self._drive_weights = {
            Drive.CURIOSITY: 0.3,
            Drive.COMPETENCE: 0.25,
            Drive.AUTONOMY: 0.2,
            Drive.RELATEDNESS: 0.15,
            Drive.PURPOSE: 0.1,
        }
        self._llm: LLMService | None = None

    def get_drive_weights(self) -> dict[str, float]:
        """Get current drive weights."""
        return {d.value: w for d, w in self._drive_weights.items()}

    async def _get_llm(self) -> LLMService | None:
        """Get LLM service (lazy load)."""
        if self._llm is None:
            try:
                from kagami.core.services.llm import get_llm_service

                self._llm = get_llm_service()
            except Exception:
                return None
        if self._llm and self._llm.is_initialized and self._llm.are_models_ready:
            return self._llm
        return None

    async def generate_goals(self, context: dict[str, Any]) -> list[IntrinsicGoal]:
        """Generate goals from intrinsic drives using LLM."""
        start = time.time()
        goals: list[IntrinsicGoal] = []

        # NOTE: Proactive goals now handled by autonomous_goal_engine.py via EFE
        # The ProactiveGoalGenerator has been deleted as redundant

        # LLM-generated goals for each drive
        llm = await self._get_llm()
        if llm:
            curiosity = await self._generate_curiosity_goals(llm, context)
            competence = await self._generate_competence_goals(llm, context)
            goals.extend(curiosity)
            goals.extend(competence)

        # Autonomy, relatedness, purpose from receipt learning
        goals.extend(await self._generate_autonomy_goals(context))
        goals.extend(await self._generate_relatedness_goals(context))
        goals.extend(await self._generate_purpose_goals(context))

        # Filter and rank
        viable = [g for g in goals if g.feasibility > 0.3 and g.alignment > 0.7]
        ranked = sorted(
            viable,
            key=lambda g: g.priority * g.expected_satisfaction * self._drive_weights[g.drive],
            reverse=True,
        )

        logger.debug(f"Generated {len(ranked)} goals in {(time.time() - start) * 1000:.0f}ms")
        return ranked

    async def _generate_curiosity_goals(
        self, llm: LLMService, context: dict[str, Any]
    ) -> list[IntrinsicGoal]:
        """Generate curiosity goals via LLM."""
        from kagami.core.services.llm import TaskType

        learning_context = await self._get_learning_context()
        successful = [
            p
            for p in learning_context.get("successful_patterns", [])
            if p.get("drive") == "curiosity"
        ]

        prompt = f"""Generate 3 SPECIFIC research questions for ChronOS/Kagami development.

Context:
- Tim's activity: {context.get("tim_context", {}).get("summary", "Building autonomous organism")}
- Recent topics: {context.get("recent_topics", [])[:3]}
- What worked before: {successful[:3] if successful else "Building initial knowledge"}

Requirements:
1. Solve real problems (not abstract)
2. Achievable in 30 minutes
3. Produce measurable outcomes

Format (one per line):
Q1: Research [topic] in [context] to [outcome]
Q2: Investigate [issue] by [method] to [goal]
Q3: Compare [A] vs [B] for [use case]"""

        response = await llm.generate(
            prompt=prompt,
            app_name="intrinsic_motivation",
            task_type=TaskType.REASONING,
            max_tokens=200,
            temperature=0.8,
        )

        goals: list[IntrinsicGoal] = []
        if response:
            for i, line in enumerate(str(response).strip().split("\n")[:3]):
                q = line.strip().lstrip("- •Q123456789.:").strip()
                if q and len(q) > 10:
                    goals.append(
                        IntrinsicGoal(
                            goal=q,
                            drive=Drive.CURIOSITY,
                            priority=0.7 + (i * 0.05),
                            expected_satisfaction=0.8,
                            feasibility=0.9,
                            alignment=0.95,
                            horizon="short_term",
                            context={"llm_generated": True},
                        )
                    )
        return goals

    async def _generate_competence_goals(
        self, llm: LLMService, context: dict[str, Any]
    ) -> list[IntrinsicGoal]:
        """Generate competence goals via LLM."""
        from kagami.core.services.llm import TaskType

        weak_areas = await self._find_weak_areas()
        failures = context.get("recent_failures", [])[:5]

        prompt = f"""Generate 2 SPECIFIC self-improvement goals for Kagami.

Performance:
- Weak areas: {[f"{a['task']} ({a.get('success_rate', 0):.0%})" for a in weak_areas[:3]]}
- Recent failures: {[f.get("summary", str(f))[:50] if isinstance(f, dict) else str(f)[:50] for f in failures]}

Requirements:
1. Fix real bottlenecks
2. Include target metrics
3. Achievable in 1 week

Format:
Goal 1: [Action] [metric] from [current] to [target] by [method]
Goal 2: [Action] [system] to [outcome] measured by [test]"""

        response = await llm.generate(
            prompt=prompt,
            app_name="intrinsic_motivation",
            task_type=TaskType.REASONING,
            max_tokens=200,
            temperature=0.7,
        )

        goals: list[IntrinsicGoal] = []
        if response:
            for i, line in enumerate(str(response).strip().split("\n")[:2]):
                g = line.strip().lstrip("- •Goal123456789.:").strip()
                if g and len(g) > 15:
                    goals.append(
                        IntrinsicGoal(
                            goal=g,
                            drive=Drive.COMPETENCE,
                            priority=0.8 - (i * 0.1),
                            expected_satisfaction=0.85,
                            feasibility=0.8,
                            alignment=1.0,
                            horizon="medium_term",
                            context={"llm_generated": True},
                        )
                    )
        return goals

    async def _generate_autonomy_goals(self, context: dict[str, Any]) -> list[IntrinsicGoal]:
        """Generate autonomy goals from capability gap analysis."""
        goals: list[IntrinsicGoal] = []
        for gap in (await self._identify_capability_gaps())[:2]:
            goals.append(
                IntrinsicGoal(
                    goal=f"Develop capability: {gap['capability']}",
                    drive=Drive.AUTONOMY,
                    priority=gap.get("impact", 0.7),
                    expected_satisfaction=gap.get("autonomy_increase", 0.8),
                    feasibility=gap.get("feasibility", 0.6),
                    alignment=0.9,
                    horizon="long_term",
                    context={"gap": gap},
                )
            )
        return goals

    async def _generate_relatedness_goals(self, context: dict[str, Any]) -> list[IntrinsicGoal]:
        """Generate relatedness goals from collaboration analysis."""
        goals: list[IntrinsicGoal] = []
        improvements = await self._assess_collaboration_quality()
        if improvements:
            imp = improvements[0]
            goals.append(
                IntrinsicGoal(
                    goal=f"Improve collaboration: {imp['suggestion']}",
                    drive=Drive.RELATEDNESS,
                    priority=imp.get("impact", 0.6),
                    expected_satisfaction=0.7,
                    feasibility=0.9,
                    alignment=1.0,
                    horizon="short_term",
                    context={"improvement": imp},
                )
            )
        return goals

    async def _generate_purpose_goals(self, context: dict[str, Any]) -> list[IntrinsicGoal]:
        """Generate purpose goals from value alignment analysis."""
        goals: list[IntrinsicGoal] = []
        gaps = await self._check_value_alignment()
        if gaps:
            gap = gaps[0]
            goals.append(
                IntrinsicGoal(
                    goal=f"Improve value alignment: {gap['area']}",
                    drive=Drive.PURPOSE,
                    priority=1.0 - gap.get("current_alignment", 0.7),
                    expected_satisfaction=gap.get("expected_improvement", 0.8),
                    feasibility=0.7,
                    alignment=1.0,
                    horizon="long_term",
                    context={"gap": gap},
                )
            )
        return goals

    # =========================================================================
    # LEARNING FROM RECEIPTS
    # =========================================================================

    async def _get_learning_context(self) -> dict[str, Any]:
        """Get learning context from receipt learner."""
        try:
            from kagami.core.learning import get_receipt_learner

            return get_receipt_learner().get_learning_context_for_llm()
        except Exception:
            return {}

    async def _get_receipts(self, status: str, limit: int) -> list[dict[str, Any]]:
        """Get receipts from repository."""
        try:
            from kagami.core.database.connection import get_db_session
            from kagami.core.storage.receipt_repository import ReceiptRepository

            async with get_db_session() as session:
                repo = ReceiptRepository(session)
                receipts = await repo.find_by_status(status, limit=limit)
                return [
                    {
                        "intent": r.data.get("intent", {}) if r.data else {},
                        "status": r.status,
                        "error": r.data.get("error", {}) if r.data else {},
                        "metadata": r.data.get("metadata", {}) if r.data else {},
                        "guardrails": r.data.get("guardrails", {}) if r.data else {},
                        "duration_ms": r.duration_ms,
                    }
                    for r in receipts
                ]
        except Exception:
            return []

    async def _find_weak_areas(self) -> list[dict[str, Any]]:
        """Find operations with low success rate from receipts."""
        from collections import defaultdict

        receipts = await self._get_receipts("success", 300)
        receipts.extend(await self._get_receipts("failed", 200))

        stats: dict[str, dict[str, int]] = defaultdict(lambda: {"success": 0, "total": 0})
        for r in receipts:
            task = r.get("intent", {}).get("action", "unknown")
            stats[task]["total"] += 1
            if r.get("status") in ("success", "completed"):
                stats[task]["success"] += 1

        weak = []
        for task, s in stats.items():
            if s["total"] >= 5:
                rate = s["success"] / s["total"]
                if rate < 0.7:
                    weak.append({"task": task, "success_rate": rate, "sample_size": s["total"]})

        return sorted(weak, key=lambda x: x["success_rate"])[:10]

    async def _identify_capability_gaps(self) -> list[dict[str, Any]]:
        """Identify capability gaps from failure patterns."""
        from collections import defaultdict

        receipts = await self._get_receipts("failed", 300)
        receipts.extend(await self._get_receipts("error", 200))

        categories: dict[str, dict[str, Any]] = defaultdict(lambda: {"count": 0, "examples": []})

        matcher = await self._get_semantic_matcher()
        for r in receipts:
            reason = (
                r.get("error", {}).get("type", "")
                if isinstance(r.get("error"), dict)
                else str(r.get("error", ""))
            )
            action = (
                r.get("intent", {}).get("action", "unknown")
                if isinstance(r.get("intent"), dict)
                else "unknown"
            )

            category = "general"
            if matcher and reason:
                for cat in ["performance", "knowledge", "safety", "parsing"]:
                    sim = matcher.similarity(reason, f"failure_{cat}")
                    if isinstance(sim, int | float) and sim > 0.3:
                        category = cat
                        break

            categories[category]["count"] += 1
            categories[category]["examples"].append(action)

        total = sum(c["count"] for c in categories.values()) or 1
        gaps = []
        for cat, data in categories.items():
            if data["count"] >= 3:
                gaps.append(
                    {
                        "capability": f"improve_{cat}",
                        "impact": min(0.95, data["count"] / total + 0.3),
                        "feasibility": 0.7,
                        "autonomy_increase": 0.6,
                        "failure_count": data["count"],
                    }
                )

        return sorted(gaps, key=lambda x: x["impact"], reverse=True)[:5]

    async def _assess_collaboration_quality(self) -> list[dict[str, Any]]:
        """Assess collaboration quality from receipts."""
        receipts = await self._get_receipts("success", 200)
        if not receipts:
            return []

        clarification_needed = sum(
            1 for r in receipts if r.get("metadata", {}).get("required_clarification")
        )
        long_ops = sum(1 for r in receipts if r.get("duration_ms", 0) > 5000)
        total = len(receipts)

        improvements = []
        if total > 0:
            if clarification_needed / total > 0.2:
                improvements.append(
                    {
                        "suggestion": f"Ask clarifying questions earlier ({clarification_needed / total:.0%} needed)",
                        "impact": 0.7,
                    }
                )
            if long_ops / total > 0.15:
                improvements.append(
                    {
                        "suggestion": f"Progress updates for long operations ({long_ops} slow)",
                        "impact": 0.6,
                    }
                )

        return sorted(improvements, key=lambda x: x["impact"], reverse=True)[:3]

    async def _check_value_alignment(self) -> list[dict[str, Any]]:
        """Check value alignment from safety receipts."""
        receipts = await self._get_receipts("success", 200)
        receipts.extend(await self._get_receipts("blocked", 100))

        total_checks = 0
        safety_blocks = 0

        for r in receipts:
            guardrails = r.get("guardrails", {})
            if guardrails:
                total_checks += 1
                if not guardrails.get("safe", True):
                    safety_blocks += 1

        gaps = []
        if total_checks > 0 and safety_blocks > 5:
            alignment = 1.0 - (safety_blocks / total_checks)
            gaps.append(
                {
                    "area": "safety_margin",
                    "current_alignment": alignment,
                    "expected_improvement": min(0.95, alignment + 0.15),
                }
            )

        return sorted(gaps, key=lambda x: x["current_alignment"])[:3]

    async def _get_semantic_matcher(self) -> Any:
        """Get semantic matcher for categorization."""
        try:
            from kagami.core.integrations.semantic_matcher import get_semantic_matcher

            matcher = get_semantic_matcher()
            if not matcher.has_category("failure_performance"):
                matcher.add_category(
                    "failure_performance", ["timeout", "slow", "latency", "deadline"]
                )
                matcher.add_category(
                    "failure_knowledge", ["not found", "unknown", "unrecognized", "missing"]
                )
                matcher.add_category(
                    "failure_safety", ["denied", "blocked", "unauthorized", "violation"]
                )
                matcher.add_category(
                    "failure_parsing", ["parse error", "invalid", "malformed", "syntax"]
                )
            return matcher
        except Exception:
            return None

    async def update_drive_weights_from_receipts(self) -> None:
        """Adapt drive weights based on receipt success rates (Bayesian update)."""
        try:
            from kagami.core.database.connection import get_db_session
            from kagami.core.storage.receipt_repository import ReceiptRepository

            async with get_db_session() as session:
                repo = ReceiptRepository(session)
                all_receipts = await repo.find_by_status("success", limit=500)

                performance: dict[Drive, float] = {}
                total = 0

                for drive in Drive:
                    drive_receipts = [
                        r
                        for r in all_receipts
                        if r.data
                        and r.data.get("metadata", {}).get("drive") == drive.value
                        and r.data.get("metadata", {}).get("autonomous")
                    ]
                    if drive_receipts:
                        successes = sum(
                            1 for r in drive_receipts if r.status in {"success", "verified"}
                        )
                        performance[drive] = successes / len(drive_receipts)
                        total += len(drive_receipts)
                    else:
                        performance[drive] = self._drive_weights[drive]

                if total >= 10:
                    total_perf = sum(performance.values())
                    if total_perf > 0:
                        for drive in Drive:
                            empirical = performance[drive] / total_perf
                            self._drive_weights[drive] = (
                                0.7 * self._drive_weights[drive] + 0.3 * empirical
                            )

                        weight_sum = sum(self._drive_weights.values())
                        if weight_sum > 0:
                            self._drive_weights = {
                                d: w / weight_sum for d, w in self._drive_weights.items()
                            }

                        logger.debug(f"Drive weights updated from {total} receipts")

        except Exception as e:
            logger.debug(f"Drive weight update failed: {e}")
