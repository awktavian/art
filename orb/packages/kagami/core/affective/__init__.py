"""Affective Computing Layer — Emotion-like Decision Shortcuts.

CONSOLIDATION (December 8, 2025):
================================
This module consolidates all affective computing components into a single file.
Merged: affective_layer.py, arousal_regulator.py, social_emotion.py,
        threat_assessment.py, valence_evaluator.py

MIGRATION NOTE:
Prefer importing from kagami.core.cognition for unified cognitive access:
    from kagami.core.cognition import AffectiveLayer, ThreatAssessment
"""

from __future__ import annotations

import logging
import time
import uuid
from collections import deque
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


async def _emit_affective_signal(signal_type: str, value: float) -> None:
    """Emit an affective signal to the unified event bus."""
    try:
        from kagami.core.events import get_unified_bus

        bus = get_unified_bus()
        await bus.publish(
            "affective.signal",
            {
                "type": "affective_signal",
                "signal_type": signal_type,
                "value": value,
                "timestamp": time.time(),
            },
        )
    except Exception as e:
        logger.debug(f"Could not emit affective signal: {e}")


# =============================================================================
# THREAT ASSESSMENT
# =============================================================================


@dataclass
class ThreatScore:
    """Result of threat assessment."""

    value: float  # 0.0 to 1.0
    components: list[tuple[str, float]]
    recommendation: str  # "block"|"monitor"|"allow"
    confidence: float = 0.8


class ThreatAssessment:
    """Rapidly evaluate threats and opportunities in incoming intents."""

    def __init__(self) -> None:
        self._threat_history: list[dict[str, Any]] = []

    async def evaluate_incoming_intent(self, intent: dict[str, Any]) -> ThreatScore:
        """Rapid threat assessment before execution."""
        risk_signals = []

        action = intent.get("action", "").lower()
        target = str(intent.get("target", "")).lower()
        metadata = intent.get("metadata", {})

        # Destructive operations
        destructive_keywords = ["delete", "drop", "destroy", "remove", "purge"]
        if any(kw in action for kw in destructive_keywords):
            risk_signals.append(("destructive_action", 0.8))

        # Production targets
        if "production" in target or "prod" in target:
            risk_signals.append(("production_target", 0.6))

        # High-value targets
        high_value = ["database", "user", "auth", "payment", "billing"]
        if any(hv in target for hv in high_value):
            risk_signals.append(("high_value_target", 0.5))

        # Unusual patterns (anomaly detection)
        if await self._is_anomalous(intent):
            risk_signals.append(("anomalous_pattern", 0.4))

        # Risk from metadata flags
        if metadata.get("risk") == "high":
            risk_signals.append(("explicit_high_risk", 0.7))

        # Compute aggregate threat
        threat_score = self._aggregate_threats(risk_signals)

        # Determine recommendation
        if threat_score > 0.7:
            recommendation = "block"
        elif threat_score > 0.4:
            recommendation = "monitor"
        else:
            recommendation = "allow"

        # Emit affective signal for downstream processing
        await _emit_affective_signal("threat", threat_score)

        return ThreatScore(
            value=threat_score,
            components=risk_signals,
            recommendation=recommendation,
        )

    def _aggregate_threats(self, signals: list[tuple[str, float]]) -> float:
        """Combine threat signals into single score."""
        if not signals:
            return 0.0

        weights = [s[1] for s in signals]
        max_threat = max(weights)
        avg_others = sum(w for w in weights if w != max_threat) / max(1, len(weights) - 1)
        return min(1.0, max_threat * 0.8 + avg_others * 0.2)

    async def _is_anomalous(self, intent: dict[str, Any]) -> bool:
        """Check if intent pattern is unusual."""
        action = intent.get("action")
        app = intent.get("app")
        recent_similar = [
            h
            for h in self._threat_history[-100:]
            if h.get("app") == app and h.get("action") == action
        ]
        return len(recent_similar) < 3


# =============================================================================
# VALENCE EVALUATOR
# =============================================================================


class ValenceEvaluator:
    """Assign positive/negative emotional significance to outcomes."""

    def __init__(self) -> None:
        self._valence_memory: deque[Any] = deque(maxlen=1000)

    async def evaluate_outcome(self, receipt: dict[str, Any]) -> float:
        """Assign valence (-1.0 to 1.0) to outcome."""
        status = receipt.get("status", "")
        duration_ms = receipt.get("duration_ms", 0)
        retries = receipt.get("retries", 0)

        if status == "success" and duration_ms < 100:
            valence = 0.8
        elif status == "success" and duration_ms < 500:
            valence = 0.6
        elif status == "success":
            valence = 0.3
        elif status == "error":
            valence = -0.8
        elif retries > 3:
            valence = -0.5
        elif status == "timeout":
            valence = -0.7
        else:
            valence = 0.0

        correlation_id = receipt.get("correlation_id") or f"c-{uuid.uuid4().hex[:16]}"
        await self._remember_valence(correlation_id, valence)
        await _emit_affective_signal("valence", valence)
        return valence

    async def _remember_valence(self, correlation_id: str, valence: float) -> None:
        """Store valence in memory for learning."""
        self._valence_memory.append(
            {"correlation_id": correlation_id, "valence": valence, "timestamp": time.time()}
        )

    def get_recent_average_valence(self, window_size: int = 100) -> float:
        """Get average valence over recent outcomes."""
        recent = list(self._valence_memory)[-window_size:]
        if not recent:
            return 0.0
        return float(sum(item["valence"] for item in recent) / len(recent))


# =============================================================================
# AROUSAL REGULATOR
# =============================================================================


class ArousalRegulator:
    """Modulate response intensity based on situational demands."""

    def __init__(self) -> None:
        self._current_arousal = 0.5
        self._recent_failures = 0

    async def compute_arousal_level(self, context: dict[str, Any]) -> float:
        """Determine how intensely to respond (0.0 to 1.0)."""
        factors = []

        if context.get("user_waiting"):
            factors.append(0.7)
        if context.get("critical_path"):
            factors.append(0.8)
        if self._recent_failures > 3:
            factors.append(0.6)
        if context.get("high_priority"):
            factors.append(0.75)
        if context.get("background_task"):
            factors.append(0.2)
        if context.get("exploratory"):
            factors.append(0.3)
        if context.get("low_priority"):
            factors.append(0.25)

        arousal = sum(factors) / len(factors) if factors else 0.5
        self._current_arousal = arousal
        await self._set_processing_priority(arousal)
        return arousal

    async def _set_processing_priority(self, arousal: float) -> None:
        """Adjust system processing based on arousal."""
        logger.debug(f"Arousal level: {arousal:.2f}")

    def record_failure(self) -> None:
        """Record a failure to increase arousal."""
        self._recent_failures += 1

    def record_success(self) -> None:
        """Record success to potentially decrease arousal."""
        self._recent_failures = max(0, self._recent_failures - 1)

    def get_current_arousal(self) -> float:
        """Get current arousal level."""
        return self._current_arousal


# =============================================================================
# SOCIAL EMOTION PROCESSOR
# =============================================================================


@dataclass
class SentimentProfile:
    """User's emotional state from interaction."""

    urgency: bool = False
    frustration: bool = False
    satisfaction: bool = False
    confusion: bool = False
    confidence: float = 0.5


class SocialEmotionProcessor:
    """Enable empathy, trust assessment, and collaboration."""

    def __init__(self) -> None:
        self._response_mode = "default"

    async def assess_user_sentiment(self, interaction: dict[str, Any]) -> SentimentProfile:
        """Understand user's emotional state from interaction."""
        text = str(interaction.get("message", "")).lower()

        urgency = any(m in text for m in ["urgent", "asap", "critical", "emergency", "now"])
        frustration = any(
            m in text for m in ["again", "still broken", "not working", "failed", "error", "why"]
        )
        satisfaction = any(
            m in text for m in ["great", "perfect", "excellent", "love", "thanks", "awesome"]
        )
        confusion = any(
            m in text for m in ["don't understand", "confused", "unclear", "what", "how"]
        )

        sentiment = SentimentProfile(
            urgency=urgency,
            frustration=frustration,
            satisfaction=satisfaction,
            confusion=confusion,
            confidence=0.7,
        )

        if sentiment.frustration:
            await self._set_response_mode("empathetic_problem_solving")
        elif sentiment.confusion:
            await self._set_response_mode("explanatory")
        elif sentiment.satisfaction:
            await self._set_response_mode("collaborative_exploration")
        elif sentiment.urgency:
            await self._set_response_mode("efficient_action")

        return sentiment

    async def _set_response_mode(self, mode: str) -> None:
        """Set tone for responses."""
        self._response_mode = mode
        logger.debug(f"Response mode set to: {mode}")

    def get_response_mode(self) -> str:
        """Get current response mode."""
        return self._response_mode

    async def generate_empathetic_response(
        self, sentiment: SentimentProfile, base_response: str
    ) -> str:
        """Adjust response based on user sentiment."""
        if sentiment.frustration:
            prefix = "I understand this is frustrating. "
        elif sentiment.confusion:
            prefix = "Let me clarify: "
        elif sentiment.urgency:
            prefix = "Acting quickly on this. "
        elif sentiment.satisfaction:
            prefix = "Glad that worked! "
        else:
            prefix = ""
        return prefix + base_response


# =============================================================================
# MAIN AFFECTIVE LAYER
# =============================================================================


class AffectiveLayer:
    """Emotion-like decision shortcuts and rapid evaluation."""

    def __init__(self) -> None:
        self.threat = ThreatAssessment()
        self.valence = ValenceEvaluator()
        self.arousal = ArousalRegulator()
        self.social = SocialEmotionProcessor()

    async def assess_threat(self, intent: dict[str, Any]) -> ThreatScore:
        """Assess threat level of incoming intent."""
        threat_score = await self.threat.evaluate_incoming_intent(intent)
        return threat_score

    async def evaluate_outcome(self, receipt: dict[str, Any]) -> float:
        """Evaluate emotional significance of outcome."""
        valence = await self.valence.evaluate_outcome(receipt)

        if valence < -0.5:
            self.arousal.record_failure()
        elif valence > 0.5:
            self.arousal.record_success()
        return valence

    async def compute_arousal(self, context: dict[str, Any]) -> float:
        """Compute arousal level for current context."""
        arousal_level = await self.arousal.compute_arousal_level(context)
        return arousal_level

    async def assess_user_sentiment(self, interaction: dict[str, Any]) -> SentimentProfile:
        """Assess user's emotional state."""
        return await self.social.assess_user_sentiment(interaction)

    def get_affective_state(self) -> dict[str, Any]:
        """Get current affective state snapshot."""
        return {
            "arousal": self.arousal.get_current_arousal(),
            "recent_valence": self.valence.get_recent_average_valence(),
            "response_mode": self.social.get_response_mode(),
            "timestamp": time.time(),
        }


__all__ = [
    "AffectiveLayer",
    "ArousalRegulator",
    "SentimentProfile",
    "SocialEmotionProcessor",
    "ThreatAssessment",
    "ThreatScore",
    "ValenceEvaluator",
]
