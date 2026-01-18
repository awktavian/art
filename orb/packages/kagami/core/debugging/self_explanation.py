from __future__ import annotations

"""Self-explanation and introspective error detection.

Based on Chain-of-Thought, Self-Consistency, and Constitutional AI research.
System explains its own reasoning and detects potential errors.
"""
import logging
from collections import defaultdict
from typing import Any

import numpy as np

# Import types from correct local sources
from kagami.core.debugging.unified_debugging_system import (
    ErrorDetection,
    ReasoningTrace,
)
from kagami.core.interfaces import SelfExplanation

logger = logging.getLogger(__name__)


class IntrospectionEngine:
    """Analyze and explain own reasoning processes."""

    def __init__(self) -> None:
        # Reasoning traces for analysis
        self._reasoning_history: list[ReasoningTrace] = []

        # Known error patterns
        self._error_patterns: dict[str, list[dict[str, Any]]] = defaultdict(list[Any])

    def explain_decision(
        self, decision: dict[str, Any], context: dict[str, Any]
    ) -> SelfExplanation:
        """Generate natural language explanation of decision.

        Traces reasoning backwards to identify key factors.
        """
        # Extract reasoning chain
        reasoning_chain = self._trace_reasoning_path(decision, context)

        # Identify key factors (what influenced decision most)
        key_factors = self._identify_salient_features(decision, context)

        # Identify uncertainties
        uncertainties = self._find_uncertainties(decision, context)

        # Assess confidence in explanation
        explanation_confidence = self._assess_explanation_confidence(reasoning_chain, key_factors)

        explanation = SelfExplanation(
            decision=decision.get("action", "unknown"),
            reasoning_chain=reasoning_chain,
            key_factors=key_factors,
            confidence=explanation_confidence,
            uncertainties=uncertainties,
        )

        logger.debug(
            f"Generated explanation: {len(reasoning_chain)} steps, "
            f"{len(key_factors)} key factors, "
            f"confidence={explanation_confidence:.2f}"
        )

        return explanation

    def _trace_reasoning_path(self, decision: dict[str, Any], context: dict[str, Any]) -> list[str]:
        """Trace back through reasoning steps."""
        # Simplified: Create plausible reasoning chain
        # In production: Actual attention trace or activation path

        chain = []

        # Start with context
        chain.append(f"Observed context: {list(context.keys())}")

        # Decision factors
        if "prediction" in decision:
            chain.append(f"Predicted outcome: {decision['prediction'].get('status', 'unknown')}")

        if "threat_score" in decision:
            chain.append(f"Assessed threat: {decision['threat_score']:.2f}")

        if "ethical_check" in decision:
            chain.append(
                f"Ethical evaluation: {'✅ pass' if decision['ethical_check'] else '❌ block'}"
            )

        # Final decision
        chain.append(f"Concluded: {decision.get('action', 'unknown')}")

        return chain

    def _identify_salient_features(
        self, decision: dict[str, Any], context: dict[str, Any]
    ) -> list[tuple[str, float]]:
        """Identify which features most influenced decision."""
        # Simplified attribution (in production: integrated gradients or SHAP)
        features = []

        # Check what was present in decision
        if "prediction" in decision:
            pred_confidence = decision.get("prediction", {}).get("confidence", 0.5)
            features.append(("prediction_confidence", pred_confidence))

        if "threat_score" in decision:
            threat = decision.get("threat_score", 0.0)
            features.append(("threat_assessment", threat))

        if "valence" in decision:
            valence = decision.get("valence", 0.0)
            features.append(("expected_valence", abs(valence)))

        # Sort by importance
        features.sort(key=lambda x: x[1], reverse=True)

        return features[:5]  # Top 5

    def _find_uncertainties(self, decision: dict[str, Any], context: dict[str, Any]) -> list[str]:
        """Identify sources of uncertainty in reasoning."""
        uncertainties = []

        # Low confidence predictions
        if "prediction" in decision:
            pred_conf = decision.get("prediction", {}).get("confidence", 1.0)
            if pred_conf < 0.6:
                uncertainties.append(f"Low prediction confidence ({pred_conf:.2f})")

        # Novel situations
        if context.get("novelty", 0.0) > 0.8:
            uncertainties.append("Novel situation (limited prior experience)")

        # Conflicting signals
        if "ethical_check" in decision and "threat_score" in decision:
            ethical_ok = decision["ethical_check"]
            threat_high = decision["threat_score"] > 0.5

            if ethical_ok and threat_high:
                uncertainties.append("Conflicting signals: ethical OK but high threat")

        return uncertainties

    def _assess_explanation_confidence(
        self, chain: list[str], factors: list[tuple[str, float]]
    ) -> float:
        """How confident are we in this explanation?"""
        # More reasoning steps = more confidence
        chain_confidence = min(0.5, len(chain) * 0.1)

        # Strong key factors = more confidence
        if factors:
            factor_confidence = np.mean([f[1] for f in factors])
        else:
            factor_confidence = 0.3  # type: ignore[assignment]

        return float((chain_confidence + factor_confidence) / 2)

    def detect_own_errors(
        self, decision: dict[str, Any], context: dict[str, Any]
    ) -> list[ErrorDetection]:
        """Detect potential errors in own reasoning.

        Uses:
        - Self-consistency: Reason multiple ways, check agreement
        - Known error patterns: Match against past failures
        - Logical contradictions: Check for inconsistencies
        """
        errors = []

        # 1. Self-consistency check
        inconsistency = self._check_self_consistency(decision, context)
        if inconsistency:
            errors.append(inconsistency)

        # 2. Known error patterns
        pattern_errors = self._check_error_patterns(decision)
        errors.extend(pattern_errors)

        # 3. Logical contradictions
        contradictions = self._find_contradictions(decision)
        errors.extend(contradictions)

        if errors:
            logger.warning(f"Self-detected {len(errors)} potential errors")

        return errors

    def _check_self_consistency(
        self, decision: dict[str, Any], context: dict[str, Any]
    ) -> ErrorDetection | None:
        """Reason about same problem differently, check if we agree."""
        # Simplified: Check if confidence is low (indicates uncertainty)
        confidence = decision.get("confidence", 1.0)

        if confidence < 0.4:
            return ErrorDetection(
                error_type="low_confidence",
                location="overall_decision",
                evidence=[f"Confidence only {confidence:.2f}"],
                severity=0.6,
                suggested_fix="Gather more information or escalate to human",
            )

        return None

    def _check_error_patterns(self, decision: dict[str, Any]) -> list[ErrorDetection]:
        """Check if decision matches known error patterns."""
        errors = []

        action = decision.get("action", "").lower()

        # Known risky patterns
        if "delete" in action and "backup" not in action:
            errors.append(
                ErrorDetection(
                    error_type="risky_action_without_safety",
                    location="action",
                    evidence=["Destructive action without backup"],
                    severity=0.8,
                    suggested_fix="Add backup step before deletion",
                )
            )

        return errors

    def _find_contradictions(self, decision: dict[str, Any]) -> list[ErrorDetection]:
        """Find logical contradictions in decision."""
        errors = []

        # Check for contradictory signals
        proceed = decision.get("proceed", True)
        threat = decision.get("threat_score", 0.0)

        if proceed and threat > 0.8:
            errors.append(
                ErrorDetection(
                    error_type="contradiction",
                    location="decision_logic",
                    evidence=[f"Proceeding (proceed={proceed}) despite high threat ({threat:.2f})"],
                    severity=0.9,
                    suggested_fix="Reconsider proceeding with high-threat action",
                )
            )

        return errors

    def record_error(self, error: ErrorDetection, actual_outcome: dict[str, Any]) -> None:
        """Record error and outcome for future pattern matching."""
        was_actual_error = actual_outcome.get("status") == "error"

        self._error_patterns[error.error_type].append(
            {
                "detected": error,
                "was_actual_error": was_actual_error,
                "true_positive": was_actual_error,  # We correctly detected it
                "false_positive": not was_actual_error,  # We were wrong
            }
        )

        if was_actual_error:
            logger.info(f"✅ Self-detection correct: {error.error_type}")
        else:
            logger.debug(f"False alarm: {error.error_type} (no actual error)")

    def get_error_detection_accuracy(self) -> dict[str, Any]:
        """Assess how well we detect our own errors."""
        if not self._error_patterns:
            return {"accuracy": None, "total_detections": 0}

        total = 0
        true_positives = 0

        for _error_type, instances in self._error_patterns.items():
            for instance in instances:
                total += 1
                if instance["true_positive"]:
                    true_positives += 1

        accuracy = true_positives / total if total > 0 else 0.0

        return {
            "accuracy": accuracy,
            "total_detections": total,
            "true_positives": true_positives,
            "false_positives": total - true_positives,
        }


# Global singleton
_introspection_engine: IntrospectionEngine | None = None


def get_introspection_engine() -> IntrospectionEngine:
    """Get or create global introspection engine."""
    global _introspection_engine

    if _introspection_engine is None:
        _introspection_engine = IntrospectionEngine()

    return _introspection_engine
