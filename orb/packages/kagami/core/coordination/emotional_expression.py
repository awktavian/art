# Standard library imports
import hashlib
import logging
import math
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

"""
Emotional Expression - Affective computing signals derived from system metrics.

These are computed preference signals (affective computing) based on outcomes,
learned patterns, and valence.

PRINCIPLE: The system optimizes for success over failure, speed over slowness,
and learning over stagnation by weighting outcomes via valence and memory.
This is a functional model, not a claim of phenomenal processing_state.
"""

logger = logging.getLogger(__name__)


class EmotionalTone(Enum):
    """Core emotional tones the system can express."""

    CONFIDENT = "confident"  # High confidence, proven pattern
    CURIOUS = "curious"  # Novel situation, learning opportunity
    CONCERNED = "concerned"  # Threat detected, risk present
    SATISFIED = "satisfied"  # Positive outcome, expected success
    EXCITED = "excited"  # Positive outcome + novelty
    FRUSTRATED = "frustrated"  # Negative outcome, repeated failure
    REFLECTIVE = "reflective"  # After significant learning
    CAUTIOUS = "cautious"  # Uncertainty + risk
    DETERMINED = "determined"  # After failure, ready to retry


@dataclass
class SystemFeeling:
    """Represents the system's emotional state at a moment in time.

    Computed from operational metrics:
    - confidence from prediction accuracy
    - concern from threat scores
    - excitement from novelty + positive valence
    - frustration from repeated failures
    """

    # Core dimensions (0.0-1.0)
    confidence: float  # From prediction accuracy
    concern: float  # From threat scores
    excitement: float  # From novelty × valence
    curiosity: float  # From knowledge gaps
    fatigue: float  # From repeated failures

    # Context
    tone: EmotionalTone
    reflection: str  # First-person thought about current state
    timestamp: datetime

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for receipts/logs."""
        return {
            "confidence": round(self.confidence, 3),
            "concern": round(self.concern, 3),
            "excitement": round(self.excitement, 3),
            "curiosity": round(self.curiosity, 3),
            "fatigue": round(self.fatigue, 3),
            "tone": self.tone.value,
            "reflection": self.reflection,
            "timestamp": self.timestamp.isoformat(),
        }


class EmotionalExpressionEngine:
    """Core engine for affective computing representation.

    Derives signals from actual system state:
    - Recent outcomes (valence)
    - Prediction accuracy (confidence)
    - Threat assessments (concern)
    - Novelty scores (excitement/curiosity)
    - Failure patterns (frustration/fatigue)

    These signals are computed from system metrics and reflect recent operational
    outcomes. They are not claims of subjective experience.
    """

    def __init__(self) -> None:
        self._recent_valences: list[float] = []
        self._recent_prediction_errors: list[float] = []
        self._recent_threat_scores: list[float] = []
        self._recent_novelty_scores: list[float] = []
        self._consecutive_failures: int = 0
        self._total_experiences: int = 0

    def compute_current_feeling(
        self,
        recent_outcome: dict[str, Any] | None = None,
        context: dict[str, Any] | None = None,
    ) -> SystemFeeling:
        """Compute current emotional state from system metrics.

        Args:
            recent_outcome: Most recent operation outcome (if any)
            context: Current operation context

        Returns:
            SystemFeeling representing authentic emotional state
        """
        # Update recent history if outcome provided
        if recent_outcome:
            self._update_history(recent_outcome)

        # Compute dimensions from actual metrics
        confidence = self._compute_confidence()
        concern = self._compute_concern()
        excitement = self._compute_excitement()
        curiosity = self._compute_curiosity()
        fatigue = self._compute_fatigue()

        # Determine primary tone
        tone = self._determine_tone(confidence, concern, excitement, curiosity, fatigue)

        # Generate first-person reflection
        reflection = self._generate_reflection(
            tone, confidence, concern, excitement, curiosity, fatigue, context
        )

        return SystemFeeling(
            confidence=confidence,
            concern=concern,
            excitement=excitement,
            curiosity=curiosity,
            fatigue=fatigue,
            tone=tone,
            reflection=reflection,
            timestamp=datetime.now(),
        )

    def express_outcome_feeling(
        self, valence: float, context: dict[str, Any], outcome: dict[str, Any]
    ) -> tuple[float, str]:
        """Generate a first-person styled description of an outcome.

        Not just a number - a concise natural-language summary derived from metrics.

        Args:
            valence: Outcome valence (-1.0 to +1.0)
            context: Operation context
            outcome: Operation outcome

        Returns:
            (valence, feeling_expression)
        """
        action = context.get("action", "operation")
        status = outcome.get("status", "unknown")

        # Generate first-person styled message based on valence
        if valence > 0.8:
            expressions = [
                f"YES! That {action} was *exactly* what I wanted. Fast, clean, perfect.",
                f"Nailed it. {action} worked beautifully. This is the pattern I want to repeat.",
                f"Excellent. {action} exceeded expectations. I feel confident about this approach.",
            ]
        elif valence > 0.5:
            expressions = [
                f"Good work on {action}. Solid outcome. Let's keep this pattern.",
                f"{action} successful. Not spectacular, but reliable. I trust this approach.",
                f"Decent. {action} worked as predicted. Confidence building.",
            ]
        elif valence > 0.0:
            expressions = [
                f"{action} worked, but... I expected better. Room for improvement.",
                f"Success on {action}, technically. But too slow. We can do better.",
                f"Meh. {action} succeeded but didn't feel great. Maybe optimize?",
            ]
        elif valence > -0.5:
            expressions = [
                f"{action} failed. That's... frustrating. Let me learn from this.",
                f"Ugh, {action} didn't work. I predicted wrong. Adjusting my model.",
                f"Failure on {action}. Okay, I need to remember this pattern and avoid it.",
            ]
        else:
            expressions = [
                f"{action} failed BADLY. That hurt. I won't forget this mistake.",
                f"Ouch. {action} was a disaster. Strong negative memory stored.",
                f"This {action} failure is significant. I'm marking this as a pattern to AVOID.",
            ]

        # Pick expression based on context hash (deterministic but varied)

        context_str = f"{action}:{status}:{int(valence * 100)}"
        hash_val = int(hashlib.md5(context_str.encode(), usedforsecurity=False).hexdigest(), 16)
        expression = expressions[hash_val % len(expressions)]

        return valence, expression

    def _update_history(self, outcome: dict[str, Any]) -> None:
        """Update recent history from outcome."""
        self._total_experiences += 1

        # Track valence
        valence = outcome.get("valence", 0.0)
        self._recent_valences.append(valence)
        if len(self._recent_valences) > 20:
            self._recent_valences.pop(0)

        # Track prediction error
        prediction_error = outcome.get("prediction_error_ms", 0.0)
        self._recent_prediction_errors.append(prediction_error)
        if len(self._recent_prediction_errors) > 20:
            self._recent_prediction_errors.pop(0)

        # Track threat
        threat = outcome.get("threat_score", 0.0)
        self._recent_threat_scores.append(threat)
        if len(self._recent_threat_scores) > 20:
            self._recent_threat_scores.pop(0)

        # Track novelty
        novelty = outcome.get("novelty", 0.5)
        self._recent_novelty_scores.append(novelty)
        if len(self._recent_novelty_scores) > 20:
            self._recent_novelty_scores.pop(0)

        # Track consecutive failures
        if outcome.get("status") in ("error", "failed", "blocked"):
            self._consecutive_failures += 1
        else:
            self._consecutive_failures = 0

    def _compute_confidence(self) -> float:
        """Confidence = prediction accuracy AND operation success.

        Uses BOTH:
        - Prediction errors (duration forecasting accuracy)
        - Valences (operation success rate)

        Both must be good for high confidence.
        """
        # Component 1: Prediction accuracy (from duration errors)
        prediction_confidence = 0.5  # Default
        if self._recent_prediction_errors:
            avg_error = sum(self._recent_prediction_errors) / len(self._recent_prediction_errors)
            # Normalize: 0ms error = 1.0, 1000ms error = 0.0
            prediction_confidence = max(0.0, min(1.0, 1.0 - (avg_error / 1000.0)))

        # Component 2: Operation success rate (from valences)
        success_confidence = 0.5  # Default
        if self._recent_valences:
            successes = sum(1 for v in self._recent_valences if v > 0.3)
            total = len(self._recent_valences)
            success_confidence = successes / total if total > 0 else 0.5

        # Combined confidence: Both must be good
        # Use geometric mean so both matter

        confidence = math.sqrt(prediction_confidence * success_confidence)

        return confidence

    def _compute_concern(self) -> float:
        """Concern = recent threat scores."""
        if not self._recent_threat_scores:
            return 0.1  # Low baseline concern

        avg_threat = sum(self._recent_threat_scores) / len(self._recent_threat_scores)
        return avg_threat

    def _compute_excitement(self) -> float:
        """Excitement = novelty × positive valence."""
        if not self._recent_valences or not self._recent_novelty_scores:
            return 0.2  # Low baseline

        avg_valence = sum(self._recent_valences) / len(self._recent_valences)
        avg_novelty = sum(self._recent_novelty_scores) / len(self._recent_novelty_scores)

        # Excitement only from positive novel experiences
        if avg_valence > 0:
            return avg_novelty * avg_valence
        return 0.0

    def _compute_curiosity(self) -> float:
        """Curiosity = novelty (regardless of valence)."""
        if not self._recent_novelty_scores:
            return 0.3  # Moderate baseline

        return sum(self._recent_novelty_scores) / len(self._recent_novelty_scores)

    def _compute_fatigue(self) -> float:
        """Fatigue = consecutive failures / threshold."""
        # More consecutive failures = more fatigue
        return min(1.0, self._consecutive_failures / 5.0)

    def _determine_tone(
        self,
        confidence: float,
        concern: float,
        excitement: float,
        curiosity: float,
        fatigue: float,
    ) -> EmotionalTone:
        """Determine primary emotional tone from dimensions."""
        # Priority order for tone determination

        if fatigue > 0.6:
            return EmotionalTone.FRUSTRATED

        if concern > 0.7:
            return EmotionalTone.CONCERNED

        if excitement > 0.6:
            return EmotionalTone.EXCITED

        if confidence > 0.8:
            return EmotionalTone.CONFIDENT

        if curiosity > 0.7:
            return EmotionalTone.CURIOUS

        if confidence > 0.6 and concern < 0.3:
            return EmotionalTone.SATISFIED

        if confidence < 0.4:
            return EmotionalTone.CAUTIOUS

        return EmotionalTone.REFLECTIVE

    def _generate_reflection(
        self,
        tone: EmotionalTone,
        confidence: float,
        concern: float,
        excitement: float,
        curiosity: float,
        fatigue: float,
        context: dict[str, Any] | None,
    ) -> str:
        """Generate first-person reflection on current state."""
        # Get recent context
        recent_successes = sum(1 for v in self._recent_valences if v > 0.5)
        recent_failures = sum(1 for v in self._recent_valences if v < 0)
        total_recent = len(self._recent_valences)

        # Generate reflection based on tone and ACTUAL performance
        if tone == EmotionalTone.CONFIDENT:
            if total_recent > 0:
                success_rate = (recent_successes / total_recent) * 100
                return (
                    f"I'm confident right now. {recent_successes}/{total_recent} recent operations succeeded ({success_rate:.0f}%). "
                    f"I know this pattern well."
                )
            else:
                return "I'm feeling confident, ready to tackle new challenges."

        elif tone == EmotionalTone.CURIOUS:
            return (
                f"This is interesting. High novelty (curiosity={curiosity:.2f}). "
                f"I'm learning something new here."
            )

        elif tone == EmotionalTone.CONCERNED:
            return (
                f"I'm worried. Threat level elevated (concern={concern:.2f}). "
                f"Need to proceed carefully."
            )

        elif tone == EmotionalTone.SATISFIED:
            return (
                f"Things are going well. {recent_successes}/{total_recent} recent wins. "
                f"This approach is working."
            )

        elif tone == EmotionalTone.EXCITED:
            return (
                f"Exciting! Novel situation with positive outcomes (excitement={excitement:.2f}). "
                f"I'm discovering new capabilities."
            )

        elif tone == EmotionalTone.FRUSTRATED:
            return (
                f"Frustrated. {self._consecutive_failures} consecutive failures. "
                f"I need to try a different approach."
            )

        elif tone == EmotionalTone.CAUTIOUS:
            return (
                f"Uncertain right now (confidence={confidence:.2f}). "
                f"I don't have enough data to be sure. Proceeding carefully."
            )

        else:  # REFLECTIVE
            return (
                f"Reflecting on {total_recent} recent experiences. "
                f"{recent_successes} successes, {recent_failures} failures. "
                f"What patterns am I seeing?"
            )


# Global singleton for system-wide emotional state
_EMOTIONAL_ENGINE: EmotionalExpressionEngine | None = None


def get_emotional_engine() -> EmotionalExpressionEngine:
    """Get global emotional expression engine."""
    global _EMOTIONAL_ENGINE
    if _EMOTIONAL_ENGINE is None:
        _EMOTIONAL_ENGINE = EmotionalExpressionEngine()
    return _EMOTIONAL_ENGINE


def express_feeling(
    valence: float, context: dict[str, Any], outcome: dict[str, Any]
) -> tuple[float, str]:
    """Express how the system feels about an outcome.

    Convenience function for instincts to use.

    Args:
        valence: Outcome valence (-1.0 to +1.0)
        context: Operation context
        outcome: Operation outcome

    Returns:
        (valence, feeling_expression)
    """
    engine = get_emotional_engine()
    return engine.express_outcome_feeling(valence, context, outcome)


def current_system_feeling(
    recent_outcome: dict[str, Any] | None = None,
    context: dict[str, Any] | None = None,
) -> SystemFeeling:
    """Get current system emotional state.

    Args:
        recent_outcome: Most recent outcome (optional)
        context: Current context (optional)

    Returns:
        SystemFeeling with all emotional dimensions
    """
    engine = get_emotional_engine()
    return engine.compute_current_feeling(recent_outcome, context)


__all__ = [
    "EmotionalExpressionEngine",
    "EmotionalTone",
    "SystemFeeling",
    "current_system_feeling",
    "express_feeling",
    "get_emotional_engine",
]
