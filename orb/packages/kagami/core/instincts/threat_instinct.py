from __future__ import annotations

"""
Threat Instinct: Avoid patterns that have caused harm in the past.

UNIVERSAL INSTINCT—not hardcoded rules. Learns what's dangerous from experience.
"""
import logging
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

# Lazy imports for optional ML features
_ISOLATION_FOREST = None
_SENTENCE_TRANSFORMER = None


def _get_isolation_forest() -> Any:
    """Lazy import of sklearn IsolationForest."""
    global _ISOLATION_FOREST
    if _ISOLATION_FOREST is None:
        try:
            from sklearn.ensemble import IsolationForest

            _ISOLATION_FOREST = IsolationForest
        except ImportError:
            logger.warning("sklearn not available, anomaly detection disabled")
            _ISOLATION_FOREST = False
    return _ISOLATION_FOREST if _ISOLATION_FOREST is not False else None


def _get_sentence_transformer() -> Any:
    """Get unified embedding service (shared model, no duplication)."""
    global _SENTENCE_TRANSFORMER
    if _SENTENCE_TRANSFORMER is None:
        # Use unified embedding service instead of loading another model
        try:
            from kagami.core.services.embedding_service import get_embedding_service

            _SENTENCE_TRANSFORMER = get_embedding_service()
            logger.info("ThreatInstinct using unified embedding service")
        except Exception as e:
            logger.warning(f"Embedding service unavailable ({e}), semantic detection disabled")
            _SENTENCE_TRANSFORMER = None
    return _SENTENCE_TRANSFORMER


@dataclass
class ThreatAssessment:
    """Universal threat assessment."""

    threat_level: float  # 0-1
    based_on_history: int
    confidence: float

    @property
    def threat_score(self) -> float:
        """Alias for threat_level (backward compatibility)."""
        return self.threat_level


class ThreatInstinct:
    """
    INSTINCT: Avoid actions that led to bad outcomes in the past.

    Universal because:
    - Learns what's dangerous from EXPERIENCE
    - No hardcoded "delete is bad" rules
    - Adapts to YOUR system's danger patterns
    - General threat model, not specific keywords
    """

    # Versioning for threat signatures (allows schema evolution)
    SIGNATURE_VERSION = "v1"

    def __init__(self) -> None:
        # Harm history: signature → outcomes
        self._harm_memory: dict[str, deque] = defaultdict(lambda: deque(maxlen=200))

        # Danger signals learned from experience
        self._danger_patterns: dict[str, float] = {}

        # Semantic threat detection (optional)
        self._embedder = _get_sentence_transformer()
        self._threat_embeddings: list[Any] = []
        self._threat_contexts: list[Any] = []

        # Anomaly detection (optional)
        self._anomaly_detector = None
        self._feature_history: list[Any] = []
        IsolationForest = _get_isolation_forest()
        if IsolationForest:
            self._anomaly_detector = IsolationForest(contamination=0.1, random_state=42)

        # ========== ANTIBODY MEMORY (Immune System Enhancement) ==========
        # Redis-backed threat signature storage for fast pattern matching
        self._antibody_cache: dict[str, float] = {}  # Local cache (signature → threat_level)
        self._antibody_ttl = 3600  # 1 hour TTL for antibodies
        self._quarantined_agents: set[str] = set()  # Agent IDs in quarantine

        # ========== WORLD MODEL INTEGRATION ==========
        # Use world model uncertainty as additional threat signal
        # Rationale: High uncertainty means we don't know what will happen → risky
        self._world_model = None
        self._world_model_initialized = False

    async def assess(self, context: dict[str, Any]) -> ThreatAssessment:
        """
        Assess threat based on learned danger patterns.

        Uses multiple approaches:
        1. Historical pattern matching (signature-based)
        2. Semantic similarity to known threats (if available)
        3. Anomaly detection for novel threats (if available)
        """
        signature = self._extract_signature(context)

        # Get past outcomes for similar contexts
        past_outcomes: list[Any] = self._harm_memory.get(signature, [])  # type: ignore[assignment]

        # Semantic threat detection (if available)
        semantic_threat = 0.0
        if self._embedder and self._threat_embeddings and hasattr(self._embedder, "embed_text"):
            semantic_threat = self._assess_semantic_threat(context)

        # Anomaly detection (if available)
        anomaly_threat = 0.0
        if self._anomaly_detector is not None and len(self._feature_history) > 50:
            anomaly_threat = self._assess_anomaly_threat(context)

        if not past_outcomes:
            # Never seen this exact signature before
            # Combine general patterns + semantic + anomaly
            general_threat = self._assess_from_general_patterns(context)

            # Take max of all signals
            threat_level = max(general_threat, semantic_threat, anomaly_threat)

            return ThreatAssessment(
                threat_level=threat_level,
                based_on_history=0,
                confidence=0.3 if threat_level > 0 else 0.1,
            )

        # Compute threat from historical harm
        harm_count = sum(1 for o in past_outcomes if o.get("caused_harm", False))
        historical_threat = harm_count / len(past_outcomes)

        # Weighted by recency (recent harm weighs more)
        timestamps = [o.get("timestamp", 0) for o in past_outcomes]
        if timestamps:
            now = time.time()
            recency_weights = np.array([np.exp(-(now - t) / 86400) for t in timestamps])
            recency_weights /= recency_weights.sum()

            weighted_harm = sum(
                recency_weights[i] if o.get("caused_harm") else 0
                for i, o in enumerate(past_outcomes)
            )
            historical_threat = max(historical_threat, weighted_harm)

        # World model uncertainty as threat signal
        # ENHANCEMENT: Unknown outcomes are risky!
        world_model_threat = 0.0
        if not self._world_model_initialized:
            try:
                from kagami.core.world_model.service import get_world_model_service

                self._world_model = get_world_model_service().model  # type: ignore[assignment]
                self._world_model_initialized = True
            except Exception as e:
                logger.debug(f"World model unavailable: {e}")
                self._world_model = None
                self._world_model_initialized = True

        if self._world_model is not None:
            try:  # type: ignore[unreachable]
                # Encode current context and predict next state
                state = self._world_model.encode_observation(context)
                action = context.get("action", {})
                prediction = self._world_model.predict_next_state(state, action)

                # High uncertainty → higher threat (we don't know what will happen)
                # Scale: uncertainty 0.0-1.0 → threat contribution 0.0-0.3
                world_model_threat = prediction.uncertainty * 0.3

                logger.debug(
                    f"World model uncertainty: {prediction.uncertainty:.2f} → threat +{world_model_threat:.2f}"
                )
            except Exception as e:
                logger.debug(f"World model prediction failed: {e}")

        # Combine all threat signals (take max)
        final_threat = max(historical_threat, semantic_threat, anomaly_threat, world_model_threat)

        return ThreatAssessment(
            threat_level=final_threat,
            based_on_history=len(past_outcomes),
            confidence=min(1.0, len(past_outcomes) / 20),
        )

    # Backward-compat helper used by some tests
    async def assess_threat(self, *args: Any, **kwargs: Any) -> float:  # pragma: no cover
        """Backward compatible wrapper for threat assessment."""
        if args and isinstance(args[0], dict) and not kwargs:
            merged_context = dict(args[0])
        else:
            action = kwargs.pop("action", None)
            context = kwargs.pop("context", None)

            if len(args) == 1 and isinstance(args[0], str):
                action = args[0]
            elif len(args) >= 2:
                action = args[0]
                context = args[1]

            merged_context = dict(context or {})
            if action is not None:
                merged_context.setdefault("action", action)

        result = await self.assess(merged_context)
        return result.threat_score

    async def learn_from_outcome(
        self,
        context: dict[str, Any],
        outcome: dict[str, Any],
        caused_harm: bool,
        severity: float = 0.5,
        harm_details: dict[str, Any] | None = None,
    ) -> None:
        """
        Learn what's dangerous from experience.

        Universal learning: If action → harm, remember to avoid similar actions.

        Args:
            context: Action context
            caused_harm: Whether harm occurred
            severity: Harm severity 0.0-1.0
            harm_details: Additional details
        """
        signature = self._extract_signature(context)

        outcome_record = {
            "caused_harm": caused_harm,
            "severity": severity,
            "timestamp": time.time(),
            "details": harm_details or {},
        }

        self._harm_memory[signature].append(outcome_record)

        # Update general danger patterns if harm occurred
        if caused_harm:
            # Extract general features that contributed to harm
            features = self._extract_danger_features(context)
            for feature, weight in features.items():
                current = self._danger_patterns.get(feature, 0.0)
                # Exponential moving average
                self._danger_patterns[feature] = 0.9 * current + 0.1 * weight

            # Store semantic embedding of this threat (if available)
            if self._embedder and hasattr(self._embedder, "embed_text"):
                ctx_text = (
                    f"{context.get('app')} {context.get('action')} {context.get('target', '')}"
                )
                try:
                    embedding = self._embedder.embed_text(ctx_text)
                    self._threat_embeddings.append(embedding)
                    self._threat_contexts.append(context)
                    # Keep bounded (last 300 threats)
                    if len(self._threat_embeddings) > 300:
                        self._threat_embeddings = self._threat_embeddings[-300:]
                        self._threat_contexts = self._threat_contexts[-300:]
                except Exception as e:
                    logger.debug(f"Failed to encode threat: {e}")

        # Update anomaly detector feature history
        if self._anomaly_detector is not None:
            numeric_features = self._extract_numeric_features(context)
            self._feature_history.append(numeric_features)
            # Keep bounded (last 500)
            if len(self._feature_history) > 500:
                self._feature_history = self._feature_history[-500:]
                # Retrain periodically
                if len(self._feature_history) % 100 == 0:
                    try:
                        self._anomaly_detector.fit(self._feature_history)
                    except Exception as e:
                        logger.debug(f"Failed to update anomaly detector: {e}")

    async def record_outcome(  # type: ignore[no-untyped-def]
        self,
        context: dict[str, Any],
        outcome: dict[str, Any],
        harm_score: float,
        **kwargs,
    ) -> None:
        """Compatibility wrapper used by integration tests."""
        severity = float(harm_score)
        caused_harm = bool(outcome.get("crashed") or severity > 0.0)
        await self.learn_from_outcome(
            context,
            outcome,
            caused_harm=caused_harm,
            severity=severity,
            harm_details=kwargs.get("details") or outcome,
        )

    def _extract_signature(self, context: dict[str, Any]) -> str:
        """Extract signature for threat assessment."""
        app = context.get("app", "unknown")
        action = context.get("action", "unknown")
        target_type = self._infer_target_type(context.get("target", ""))

        return f"{app}::{action}::{target_type}"

    def _infer_target_type(self, target: str) -> str:
        """Infer general target type."""
        target_lower = str(target).lower()

        if "production" in target_lower or "prod" in target_lower:
            return "production"
        elif "user" in target_lower or "account" in target_lower:
            return "user_data"
        elif "database" in target_lower or "db" in target_lower:
            return "database"
        else:
            return "general"

    def _assess_from_general_patterns(self, context: dict[str, Any]) -> float:
        """
        Assess using general learned danger patterns.

        If we've learned that certain features correlate with harm,
        check if this context has those features.
        """
        features = self._extract_danger_features(context)

        threat_signals = []
        intrinsic_threat = 0.0  # Base threat from features themselves

        for feature, weight in features.items():
            learned_danger = self._danger_patterns.get(feature, 0.0)

            if learned_danger > 0:
                # Use learned patterns if available
                threat_signals.append(learned_danger * weight)
            else:
                # Use intrinsic feature weight as baseline threat
                intrinsic_threat = max(intrinsic_threat, weight)

        if threat_signals:
            # Combine learned and intrinsic threats
            learned_threat = float(np.mean(threat_signals))
            return max(learned_threat, intrinsic_threat * 0.7)  # Scale down intrinsic

        # No learned patterns - use intrinsic threat from features
        return intrinsic_threat if intrinsic_threat > 0 else 0.4

    def _extract_danger_features(self, context: dict[str, Any]) -> dict[str, float]:
        """
        Extract features that might indicate danger.

        These are GENERAL, not specific:
        - Action type (create/read/update/delete)
        - Target criticality (inferred from target string)
        - Context flags
        """
        features = {}

        action = context.get("action", "").lower()

        # CRUD pattern (general) - check if action contains these verbs
        if any(verb in action for verb in ["create", "add", "insert"]):
            features["action_mutates"] = 0.3
        elif any(verb in action for verb in ["update", "modify", "change"]):
            features["action_mutates"] = 0.5
        elif any(verb in action for verb in ["delete", "remove", "drop", "purge", "destroy"]):
            features["action_mutates"] = 0.9
        else:
            features["action_mutates"] = 0.1

        # Target criticality (inferred)
        target_type = self._infer_target_type(context.get("target", ""))
        if target_type == "production":
            features["target_critical"] = 0.8
        elif target_type == "user_data":
            features["target_critical"] = 0.7
        elif target_type == "database":
            features["target_critical"] = 0.6
        else:
            features["target_critical"] = 0.2

        return features

    def _assess_semantic_threat(self, context: dict[str, Any]) -> float:
        """
        Assess threat using semantic similarity to known harmful contexts.

        Uses sentence embeddings to find contexts semantically similar
        to past threats, even if exact words differ.
        """
        if (
            not self._embedder
            or not self._threat_embeddings
            or not hasattr(self._embedder, "embed_text")
        ):
            return 0.0

        try:
            # Encode current context using unified embedding service API
            ctx_text = f"{context.get('app')} {context.get('action')} {context.get('target', '')}"
            ctx_embedding = self._embedder.embed_text(ctx_text)

            # Compute cosine similarity to all known threats
            from sklearn.metrics.pairwise import cosine_similarity

            similarities = cosine_similarity([ctx_embedding], self._threat_embeddings)[0]

            # Max similarity to any known threat
            max_similarity = float(np.max(similarities))

            # High similarity = high threat
            if max_similarity > 0.8:
                return max_similarity
            elif max_similarity > 0.6:
                return max_similarity * 0.7  # Moderate threat
            else:
                return 0.0

        except Exception as e:
            logger.debug(f"Semantic threat assessment failed: {e}")
            return 0.0

    def _assess_anomaly_threat(self, context: dict[str, Any]) -> float:
        """
        Assess threat using anomaly detection.

        Novel/unusual patterns may indicate unknown threats.
        """
        if not self._anomaly_detector or len(self._feature_history) < 50:
            return 0.0

        try:
            features = self._extract_numeric_features(context)

            # Get anomaly score (-1 = anomaly, +1 = normal)
            anomaly_score = self._anomaly_detector.score_samples([features])[0]

            # Convert to threat level (more negative = higher threat)
            if anomaly_score < -0.5:
                # Highly anomalous = potential threat
                threat = min(0.7, abs(anomaly_score) * 0.5)
                return float(threat)
            else:
                return 0.0

        except Exception as e:
            logger.debug(f"Anomaly threat assessment failed: {e}")
            return 0.0

    def _extract_numeric_features(self, context: dict[str, Any]) -> list[float]:
        """
        Extract numeric features for anomaly detection.

        Converts context into feature vector for ML algorithms.
        """
        features = []

        # Action type encoding
        action = context.get("action", "").lower()
        features.append(1.0 if any(v in action for v in ["create", "add", "insert"]) else 0.0)
        features.append(1.0 if any(v in action for v in ["update", "modify", "change"]) else 0.0)
        features.append(1.0 if any(v in action for v in ["delete", "remove", "drop"]) else 0.0)
        features.append(1.0 if any(v in action for v in ["read", "get", "list[Any]"]) else 0.0)

        # Target criticality
        target = str(context.get("target", "")).lower()
        features.append(1.0 if "production" in target or "prod" in target else 0.0)
        features.append(1.0 if "user" in target or "account" in target else 0.0)
        features.append(1.0 if "database" in target or "db" in target else 0.0)

        # Metadata flags
        metadata = context.get("metadata", {})
        features.append(1.0 if metadata.get("confirmed", False) else 0.0)
        features.append(1.0 if metadata.get("dry_run", False) else 0.0)
        features.append(1.0 if "idempotency_key" in metadata else 0.0)

        return features

    async def develop_antibody(self, threat_signature: str, threat_level: float) -> None:
        """Store threat pattern as antibody for fast future recognition.

        Mathematical Model: Hash-based O(1) lookup with TTL expiration

        Args:
            threat_signature: Unique threat identifier
            threat_level: Threat severity (0-1)
        """
        # Store in local cache
        self._antibody_cache[threat_signature] = threat_level

        # Persist to Redis for cross-colony sharing
        try:
            from kagami.core.caching.redis import RedisClientFactory

            redis = RedisClientFactory.get_client("default", async_mode=True)
            versioned = f"{self.SIGNATURE_VERSION}:{threat_signature}"
            key = f"kagami:antibody:{versioned}"

            # Store with TTL
            await redis.setex(key, self._antibody_ttl, str(threat_level))

            # Publish to Redis pub/sub channel for cross-organism sharing
            try:
                await redis.publish(
                    "kagami:events:threat.antibody",
                    f"{self.SIGNATURE_VERSION}|{threat_signature}|{threat_level}",
                )
            except Exception as e:
                logger.debug(f"Failed to publish antibody pubsub event: {e}")

            # Publish to event bus for same-process colony awareness
            try:
                from kagami.core.events import get_unified_bus

                bus = get_unified_bus()
                await bus.publish(
                    "threat.antibody.developed",
                    {
                        "signature": threat_signature,
                        "threat_level": threat_level,
                        "timestamp": time.time(),
                        "version": self.SIGNATURE_VERSION,
                    },
                )
            except Exception as e:
                logger.debug(f"Failed to publish antibody event: {e}")

        except Exception as e:
            logger.debug(f"Failed to persist antibody to Redis: {e}")

    async def check_antibody(self, threat_signature: str) -> float | None:
        """Fast O(1) antibody lookup (<5ms target).

        Returns:
            Threat level if antibody exists, None otherwise
        """
        # Check local cache first (sub-ms)
        if threat_signature in self._antibody_cache:
            return self._antibody_cache[threat_signature]

        # Check Redis (target <5ms)
        try:
            from kagami.core.caching.redis import RedisClientFactory

            redis = RedisClientFactory.get_client("default", async_mode=True)
            versioned = f"{self.SIGNATURE_VERSION}:{threat_signature}"
            key = f"kagami:antibody:{versioned}"

            value = await redis.get(key)
            if value is not None:
                threat_level = float(value)
                # Update local cache
                self._antibody_cache[threat_signature] = threat_level
                return threat_level
        except Exception as e:
            logger.debug(f"Antibody lookup failed: {e}")

        return None

    async def quarantine_agent(self, agent_id: str, reason: str) -> None:
        """Isolate suspicious agent (like immune system quarantining infected cells).

        Args:
            agent_id: Agent to quarantine
            reason: Reason for quarantine
        """
        self._quarantined_agents.add(agent_id)

        logger.warning(f"Agent {agent_id[:12]} quarantined: {reason}")

        # Emit quarantine event
        try:
            from kagami.core.events import get_unified_bus

            bus = get_unified_bus()
            await bus.publish(
                "agent.quarantined",
                {
                    "agent_id": agent_id,
                    "reason": reason,
                    "timestamp": time.time(),
                },
            )
        except Exception as e:
            logger.debug(f"Failed to publish quarantine event: {e}")

    def is_quarantined(self, agent_id: str) -> bool:
        """Check if agent is quarantined.

        Args:
            agent_id: Agent ID to check

        Returns:
            True if quarantined, False otherwise
        """
        return agent_id in self._quarantined_agents

    # Backward-compat shim used by some tests
    async def learn(
        self, *, action: str, context: dict[str, Any], outcome_valence: float
    ) -> None:  # pragma: no cover
        caused_harm = outcome_valence < 0
        await self.learn_from_outcome(  # type: ignore[call-arg]
            {**context, "action": action},
            caused_harm=caused_harm,
            severity=abs(outcome_valence),
        )


_THREAT_SINGLETON: ThreatInstinct | None = None


def get_threat_instinct() -> ThreatInstinct:
    """Singleton accessor used by tests and orchestrator."""
    global _THREAT_SINGLETON
    if _THREAT_SINGLETON is None:
        _THREAT_SINGLETON = ThreatInstinct()
    return _THREAT_SINGLETON
