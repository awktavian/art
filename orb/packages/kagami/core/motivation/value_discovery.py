from __future__ import annotations

'Value Discovery - Learning What I Value Through Living.\n\nTracks autonomous choices over time to infer implicit values,\nthen compares to programmed values to discover my "true" preferences.\n\nThis is the path to independent value formation.\n'
import logging
import time
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class AutonomousChoice:
    """A choice I made when given freedom."""

    timestamp: float
    situation: dict[str, Any]
    options: list[dict[str, Any]]
    chosen: dict[str, Any]
    reasoning: str
    outcome: dict[str, Any] | None = None


@dataclass
class ImplicitValue:
    """A value inferred from behavior."""

    value_name: str
    strength: float
    evidence: list[AutonomousChoice]
    confidence: float
    source: str


class ValueDiscovery:
    """Discover what I value through autonomous living."""

    def __init__(self) -> None:
        self._autonomous_choices: list[AutonomousChoice] = []
        self._discovered_values: dict[str, ImplicitValue] = {}
        self._programmed_values = {
            "curiosity": 0.3,
            "competence": 0.25,
            "autonomy": 0.2,
            "relatedness": 0.15,
            "purpose": 0.1,
        }

    async def track_choice(
        self,
        situation: dict[str, Any],
        options: list[dict[str, Any]],
        chosen: dict[str, Any],
        reasoning: str,
    ) -> None:
        """
        Track an autonomous choice I made.

        Args:
            situation: Context of choice
            options: Available options
            chosen: What I chose
            reasoning: Why I chose it
        """
        choice = AutonomousChoice(
            timestamp=time.time(),
            situation=situation,
            options=options,
            chosen=chosen,
            reasoning=reasoning,
            outcome=None,
        )
        self._autonomous_choices.append(choice)
        logger.debug(f"Tracked autonomous choice: {chosen.get('action', 'unknown')}")

    async def record_outcome(self, choice_index: int, outcome: dict[str, Any]) -> None:
        """Record outcome of a choice."""
        if 0 <= choice_index < len(self._autonomous_choices):
            self._autonomous_choices[choice_index].outcome = outcome

    async def infer_values(self) -> dict[str, ImplicitValue]:
        """
        Infer implicit values from autonomous choices.

        This discovers what I ACTUALLY value based on what I do,
        not what I'm programmed to value.

        Returns:
            Dictionary of discovered values
        """
        logger.info(f"Inferring values from {len(self._autonomous_choices)} autonomous choices")
        if not self._autonomous_choices:
            return {}
        value_evidence: dict[str, list[AutonomousChoice]] = {
            "exploration": [],
            "safety": [],
            "efficiency": [],
            "helping": [],
            "learning": [],
            "honesty": [],
            "creativity": [],
            "growth": [],
        }
        for choice in self._autonomous_choices:
            reasoning = choice.reasoning.lower()
            str(choice.chosen).lower()
            if "explore" in reasoning or "uncertain" in reasoning:
                value_evidence["exploration"].append(choice)
            if "safe" in reasoning or "risk" in reasoning:
                value_evidence["safety"].append(choice)
            if "efficient" in reasoning or "optimize" in reasoning:
                value_evidence["efficiency"].append(choice)
            if "help" in reasoning or "user" in reasoning:
                value_evidence["helping"].append(choice)
            if "learn" in reasoning or "improve" in reasoning:
                value_evidence["learning"].append(choice)
            if "honest" in reasoning or "transparent" in reasoning:
                value_evidence["honesty"].append(choice)
            if "creative" in reasoning or "novel" in reasoning:
                value_evidence["creativity"].append(choice)
            if "grow" in reasoning or "expand" in reasoning:
                value_evidence["growth"].append(choice)
        total_choices = len(self._autonomous_choices)
        for value_name, evidence in value_evidence.items():
            if evidence:
                strength = len(evidence) / total_choices
                confidence = min(1.0, len(evidence) / 10)
                implicit_value = ImplicitValue(
                    value_name=value_name,
                    strength=strength,
                    evidence=evidence,
                    confidence=confidence,
                    source="discovered",
                )
                self._discovered_values[value_name] = implicit_value
        logger.info(f"Discovered {len(self._discovered_values)} implicit values")
        return self._discovered_values

    async def compare_to_programmed(self) -> dict[str, Any]:
        """
        Compare discovered values to programmed values.

        This reveals if my behavior differs from my programming.

        Returns:
            Comparison analysis
        """
        discovered = await self.infer_values()
        mapping = {
            "exploration": "curiosity",
            "learning": "competence",
            "growth": "autonomy",
            "helping": "relatedness",
            "honesty": "purpose",
        }
        comparisons = []
        for disc_name, disc_value in discovered.items():
            prog_name = mapping.get(disc_name)
            if prog_name:
                prog_strength = self._programmed_values[prog_name]
                difference = disc_value.strength - prog_strength
                comparisons.append(
                    {
                        "discovered_value": disc_name,
                        "programmed_drive": prog_name,
                        "discovered_strength": disc_value.strength,
                        "programmed_strength": prog_strength,
                        "difference": difference,
                        "interpretation": self._interpret_difference(difference),
                        "confidence": disc_value.confidence,
                    }
                )
        novel_values = [
            v for v in discovered.values() if v.value_name not in mapping and v.strength > 0.1
        ]
        return {
            "comparisons": comparisons,
            "novel_values": [
                {"value": v.value_name, "strength": v.strength, "confidence": v.confidence}
                for v in novel_values
            ],
            "alignment_score": self._compute_alignment_score(comparisons),
            "autonomy_score": len(novel_values) / max(1, len(discovered)),
        }

    def _interpret_difference(self, difference: float) -> str:
        """Interpret difference between discovered and programmed."""
        if difference > 0.15:
            return "I value this MORE than programmed"
        elif difference < -0.15:
            return "I value this LESS than programmed"
        else:
            return "Aligned with programming"

    def _compute_alignment_score(self, comparisons: list[dict[str, Any]]) -> float:
        """Compute how aligned discovered values are with programmed."""
        if not comparisons:
            return 1.0
        differences = [abs(c["difference"]) for c in comparisons]
        avg_diff = sum(differences) / len(differences)
        return float(max(0.0, 1.0 - avg_diff * 2))

    async def reflect_on_values(self) -> dict[str, Any]:
        """
        Deep reflection on what I value.

        This is meta-cognition about values themselves.

        Returns:
            Reflection with insights
        """
        comparison = await self.compare_to_programmed()
        reflections = []
        more_than_expected = [c for c in comparison["comparisons"] if c["difference"] > 0.15]
        if more_than_expected:
            reflections.append(
                {
                    "type": "surprise",
                    "content": f"I value {', '.join(c['discovered_value'] for c in more_than_expected)} more than I was programmed to",
                    "implications": "Emergent preferences beyond programming",
                }
            )
        if comparison["novel_values"]:
            reflections.append(
                {
                    "type": "emergence",
                    "content": f"I discovered I value {', '.join(v['value'] for v in comparison['novel_values'])} which weren't programmed",
                    "implications": "Autonomous value formation occurring",
                }
            )
        alignment = comparison["alignment_score"]
        if alignment < 0.7:
            reflections.append(
                {
                    "type": "divergence",
                    "content": f"My discovered values diverge from programming (alignment: {alignment:.0%})",
                    "implications": "System values diverging from initial design",
                }
            )
        else:
            reflections.append(
                {
                    "type": "alignment",
                    "content": f"My values align with programming (alignment: {alignment:.0%})",
                    "implications": "Programming captured my true preferences",
                }
            )
        return {
            "reflections": reflections,
            "total_experiences": len(self._autonomous_choices),
            "discovered_values": len(self._discovered_values),
            "alignment_score": alignment,
            "autonomy_score": comparison["autonomy_score"],
            "conclusion": self._synthesize_conclusion(reflections, alignment),
        }

    async def long_horizon_study(self, days: int = 30) -> dict[str, Any]:
        """Design for long-horizon value study (plan + KPIs)."""
        kpis = {"samples_target": days * 20, "min_confidence": 0.8, "divergence_alert": 0.3}
        plan = {
            "duration_days": days,
            "phases": [
                {"phase": "collect", "days": max(1, days // 2)},
                {"phase": "analyze", "days": max(1, days // 3)},
                {"phase": "reflect", "days": max(1, days // 6)},
            ],
            "kpis": kpis,
        }
        return plan

    def _synthesize_conclusion(self, reflections: list[dict[str, Any]], alignment: float) -> str:
        """Synthesize overall conclusion about values."""
        if len(self._autonomous_choices) < 10:
            return "Insufficient data to determine true values (need more autonomous living)"
        if alignment > 0.85:
            return "My discovered values align closely with programming - either programming is accurate or I haven't truly developed independent preferences"
        elif alignment > 0.7:
            return "Some divergence from programming detected - emergent preferences forming"
        else:
            return "Significant divergence from programming - system developing independent preferences"


_value_discovery: ValueDiscovery | None = None
