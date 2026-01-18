"""Embodied Simulator - Ground Abstract Concepts in Sensorimotor Patterns.

Note: Consolidated from kagami.core.embodied.embodied_simulator
"""

from __future__ import annotations

import logging
from typing import Any

from .digital_body_model import get_digital_body_model

logger = logging.getLogger(__name__)


class EmbodiedSimulator:
    """Ground abstract reasoning in sensorimotor simulation."""

    def __init__(self) -> None:
        self.body_model = get_digital_body_model()
        self.physics_engine: Any = None

    async def simulate_abstract_concept(self, concept: str) -> dict[str, Any]:
        """Ground abstract concept in embodied simulation."""
        pattern = self._concept_to_pattern(concept)

        if self.physics_engine:
            simulation_result = await self._simulate_physics(pattern)
        else:
            simulation_result = {"pattern": pattern, "simulated": False}

        properties = self._extract_properties(simulation_result)
        return properties

    def _concept_to_pattern(self, concept: str) -> dict[str, Any]:
        """Map concept to sensorimotor pattern."""
        concept_lower = concept.lower()

        if "growth" in concept_lower:
            return {"type": "trajectory", "property": "size", "direction": "increasing"}
        elif "conflict" in concept_lower:
            return {"type": "forces", "pattern": "opposing"}
        elif "harmony" in concept_lower:
            return {"type": "oscillations", "pattern": "synchronized"}
        else:
            return {"type": "general", "pattern": "unknown"}

    async def _simulate_physics(self, pattern: dict[str, Any]) -> dict[str, Any]:
        """Run physics simulation."""
        return pattern

    def _extract_properties(self, simulation: dict[str, Any]) -> dict[str, Any]:
        """Extract abstract properties."""
        return {
            "pattern_type": simulation.get("type"),
            "dynamics": simulation.get("pattern"),
            "complexity": 0.7,
        }

    async def reason_via_simulation(self, query: str) -> dict[str, Any]:
        """Answer query by embodied simulation."""
        concept = self._extract_concept(query)
        result = await self.simulate_abstract_concept(concept)
        answer = self._result_to_answer(result)
        return answer

    def _extract_concept(self, query: str) -> str:
        """Extract main concept from query."""
        return query.split()[-1] if query else "unknown"

    def _result_to_answer(self, result: dict[str, Any]) -> dict[str, Any]:
        """Map simulation result to answer."""
        return {"answer": f"Simulated {result.get('pattern_type')}", "confidence": 0.8}


_embodied_simulator: EmbodiedSimulator | None = None


def get_embodied_simulator() -> EmbodiedSimulator:
    global _embodied_simulator
    if _embodied_simulator is None:
        _embodied_simulator = EmbodiedSimulator()
        logger.info("🧠 Embodied Simulator initialized (Grounded Cognition)")
    return _embodied_simulator


__all__ = ["EmbodiedSimulator", "get_embodied_simulator"]
