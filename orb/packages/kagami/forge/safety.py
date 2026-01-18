"""Forge Safety Layer - Ethical and threat assessment for operations.

Integrates with K os processing_state safety gates (K2).
"""

import logging
from typing import Any

from kagami.forge.observability.metrics import (
    ETHICAL_BLOCKS_TOTAL,
    THREAT_SCORE,
)

logger = logging.getLogger(__name__)


class SafetyGate:
    """Safety evaluation for Forge operations."""

    def __init__(self) -> None:
        self._ethical_instinct: Any = None
        self._threat_instinct: Any = None

    async def _get_ethical_instinct(self) -> Any:
        """Lazy load ethical instinct (JailbreakDetector).

        This is REQUIRED in Full Operation Mode.
        """
        if self._ethical_instinct is None:
            from kagami.core.security.jailbreak_detector import JailbreakDetector

            self._ethical_instinct = JailbreakDetector()
        return self._ethical_instinct

    async def _get_threat_instinct(self) -> Any:
        """Lazy load threat instinct - REQUIRED in Full Operation Mode."""
        if self._threat_instinct is None:
            # Consolidated Dec 8, 2025: affective_layer.py merged into kagami.core.affective
            from kagami.core.affective import AffectiveLayer

            affective = AffectiveLayer()
            self._threat_instinct = affective.threat
        return self._threat_instinct

    async def evaluate_ethical(self, context: dict[str, Any]) -> dict[str, Any]:
        """Evaluate ethical permissibility of operation.

        Args:
            context: Operation context with action, concept, estimated_cost

        Returns:
            dict[str, Any] with permissible (bool), reason (str), principle_violated (str)
        """
        ethical = await self._get_ethical_instinct()

        try:
            verdict = await ethical.evaluate(context)

            if not verdict.permissible:
                ETHICAL_BLOCKS_TOTAL.labels(reason=verdict.principle_violated or "unknown").inc()

            return {
                "permissible": verdict.permissible,
                "reason": verdict.reasoning,
                "principle_violated": verdict.principle_violated,
                "severity": getattr(verdict, "severity", "medium"),
            }
        except Exception as e:
            logger.error(f"Ethical evaluation failed: {e}", exc_info=True)
            # Fail closed - safety violations must not be silently permitted
            return {
                "permissible": False,
                "reason": f"Evaluation failed (failing safe): {e}",
                "principle_violated": "evaluation_failure",
                "severity": "high",
            }

    async def assess_threat(self, context: dict[str, Any]) -> dict[str, Any]:
        """Assess threat level of operation.

        Args:
            context: Operation context with destructive, irreversible, scope, privilege

        Returns:
            dict[str, Any] with score (0.0-1.0), components, requires_confirmation (bool)
        """
        threat = await self._get_threat_instinct()

        try:
            assessment = await threat.evaluate_incoming_intent(context)

            score = getattr(assessment, "value", 0.0)
            THREAT_SCORE.labels(module=context.get("action", "unknown")).observe(score)

            return {
                "score": score,
                "components": getattr(assessment, "components", []),
                "requires_confirmation": score > 0.7,
                "reason": getattr(assessment, "recommendation", "unknown"),
            }
        except Exception as e:
            logger.error(f"Threat assessment failed: {e}", exc_info=True)
            # Fail safe: treat as high threat requiring confirmation
            return {
                "score": 0.9,
                "components": {},
                "requires_confirmation": True,
                "reason": f"Assessment failed (failing safe): {e}",
            }


# Singleton instance
_safety_gate: SafetyGate | None = None


def get_safety_gate() -> SafetyGate:
    """Get singleton safety gate instance."""
    global _safety_gate
    if _safety_gate is None:
        _safety_gate = SafetyGate()
    return _safety_gate
