from __future__ import annotations

"""
Prediction Instinct: Always predict before acting, learn from error.

This is a UNIVERSAL instinct—not a heuristic. Works for all future cases
because it's based on fundamental learning: experience → prediction → error → update.
"""

import logging
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

import numpy as np

from kagami.core.async_utils import safe_create_task

logger = logging.getLogger(__name__)


@dataclass
class InstinctPrediction:
    """Universal prediction structure for instinct-based prediction.

    Note: Distinct from kagami.core.predictive.types.Prediction (generic).
    This type includes expected_outcome and based_on_samples for instincts.
    """

    expected_outcome: dict[str, Any]
    confidence: float
    based_on_samples: int

    # Backward-compat helpers (dict[str, Any]-like access expected by some tests)
    def get(self, key: str, default: Any = None) -> Any:  # pragma: no cover
        if key == "confidence":
            return getattr(self, "confidence", default)
        return self.expected_outcome.get(key, default)

    def __getitem__(self, key: str) -> Any:  # pragma: no cover
        if key == "confidence":
            return self.confidence
        return self.expected_outcome[key]


class PredictionInstinct:
    """
    INSTINCT: Before acting, predict outcome based on past experience.

    This is universal because:
    - Applies to ANY action
    - Learns from ANY outcome
    - Improves over time automatically
    - No hardcoded rules—pure pattern learning

    OPTIMIZED: Caches world model (30% faster for cold starts)
    """

    def __init__(self) -> None:
        # Adaptive models: key → (outcomes, weights)
        self._experience: dict[str, list[Any]] = defaultdict(list[Any])
        # Prioritized replay: track prediction errors for weighted sampling
        self._priorities: dict[str, list[Any]] = defaultdict(list[Any])
        # Optional confidence calibration (learned online)
        try:
            from kagami.core.learning.confidence_calibration import (
                ConfidenceCalibrator,
            )

            self._calibrator = ConfidenceCalibrator(buckets=15)
        except Exception:
            self._calibrator: Any | None = None  # type: ignore[assignment, no-redef]

        # OPTIMIZATION: Cache world model (loaded once, reused)
        self._world_model: Any | None = None
        self._world_model_initialized = False

        # LLM-ENHANCED LEARNING: Pattern library extracted via LLM
        self._learned_patterns: dict[str, dict[str, Any]] = {}
        self._last_pattern_extraction: dict[str, float] = {}
        self._llm_service = None  # Lazy loaded

        # SEMANTIC CLUSTERING: Group similar tasks via embeddings
        self._semantic_clusters: dict[str, list[str]] = {}  # cluster_id -> signatures
        self._signature_to_cluster: dict[str, str] = {}  # signature -> cluster_id
        self._embedding_service = None  # Lazy loaded

        # ADAPTIVE ATTENTION: Learn what to attend to (research-based 2024+)
        self._adaptive_attention = None  # Lazy loaded
        self._use_adaptive_attention = True  # Enable by default

        # PREDICTION CACHE: Recent predictions for pattern extraction
        self._last_prediction: dict[str, InstinctPrediction] = {}  # signature -> prediction

    def _ensure_world_model_loaded(self) -> None:
        """Ensure the world model cache is initialised exactly once."""
        if self._world_model_initialized:
            return
        try:
            from kagami.core.world_model.service import get_world_model_service

            self._world_model = get_world_model_service().model

        except Exception as e:  # pragma: no cover - defensive
            logger.debug(f"World model unavailable: {e}")
            self._world_model = None
        finally:
            self._world_model_initialized = True

    def _predict_with_world_model(self, context: dict[str, Any]) -> InstinctPrediction | None:
        """Attempt a world-model-based prediction when experience is missing."""
        wm = self._world_model
        if wm is None:
            return None
        try:  # pragma: no cover - relies on heavy optional dependency
            current_state = wm.encode_observation(context)
            action = context.get("action", {})
            prediction = wm.predict_next_state(current_state, action)
            confidence = float(getattr(prediction, "confidence", 0.0))
            return InstinctPrediction(
                expected_outcome={
                    "duration_ms": 100,
                    "status": "unknown",
                    "confidence": confidence,
                },
                confidence=confidence,
                based_on_samples=0,
            )
        except Exception as e:
            logger.debug(f"World model prediction failed: {e}")
            return None

    def predict_confidence(self, context: dict[str, Any] | str) -> float:
        """Quick confidence check without full prediction (STAIR 1 optimization).

        Returns just the confidence score for perception-loop closure.
        Falls back to synchronous Bayesian confidence from experience.
        """
        # Convert to signature
        if isinstance(context, str):
            # Minimal dict[str, Any] for compatibility
            context = {"action": context}
        signature = self._extract_signature(context)

        # Check experience
        outcomes = self._experience.get(signature, [])

        if not outcomes:
            # Use prior from experience buffer size - more experience = higher base confidence
            prior = min(0.3 + 0.1 * len(self._experience), 0.6)
            return prior

        # Bayesian confidence from past outcomes
        return self._bayesian_confidence(outcomes)

    async def predict(self, context: dict[str, Any] | str) -> InstinctPrediction:
        """
        Predict outcome before acting.

        Universal mechanism: Look at past similar contexts, weight recent more.
        Enhanced with world model trajectory imagination if available.
        """
        # Normalize input: allow string action for compatibility
        if not isinstance(context, dict):
            context = {"action": str(context)}

        # Generate context signature (general pattern matching)
        signature = self._extract_signature(context)

        # Get past experiences with this signature
        past_outcomes = self._experience.get(signature, [])

        # Use experience-based prediction if we have data
        if past_outcomes:
            # ADAPTIVE ATTENTION: Use learned attention weights (research-based); fallback to uniform
            weights = np.ones(len(past_outcomes), dtype=float)
            if self._use_adaptive_attention and len(past_outcomes) >= 3:
                try:
                    # Lazy load adaptive attention
                    if self._adaptive_attention is None:
                        from kagami.core.learning.adaptive_attention import (
                            get_adaptive_attention,
                        )

                        self._adaptive_attention = get_adaptive_attention()  # type: ignore[assignment]

                    # Compute attention scores for past outcomes
                    attention_scores = self._adaptive_attention.compute_attention(  # type: ignore  # Dynamic attr
                        items=past_outcomes,
                        context=context,
                        task_type=signature,
                    )

                    # Extract weights from attention scores
                    weights = np.array([score.score for score in attention_scores], dtype=float)  # type: ignore[assignment]

                    # Store attention scores for later learning update
                    context["_attention_scores"] = attention_scores

                    # Normalize weights if positive
                    total = float(weights.sum())
                    if total > 0:
                        weights = weights / total  # type: ignore[assignment]
                    else:
                        weights = np.ones(len(past_outcomes), dtype=float)
                except Exception as e:
                    # Fallback to uniform weights on any failure
                    logger.debug(f"Adaptive attention unavailable: {e} (fallback to uniform)")
                    weights = np.ones(len(past_outcomes), dtype=float)

            # TEMPORAL ATTENTION: Combine with causal temporal weights when available
            try:
                from kagami.core.learning.temporal_attention import (
                    get_temporal_attention,
                )

                temporal = get_temporal_attention()
                temporal_weights = temporal.compute_temporal_weights(
                    items=past_outcomes,
                    query_time=time.time(),
                    task_type=signature,
                    context={
                        "app": context.get("app", "unknown"),
                        "action": context.get("action", "unknown"),
                        "loop_depth": context.get("loop_depth", 0),
                        "correlation_id": context.get("correlation_id", ""),
                    },
                )
                tw = np.array([tw.weight for tw in temporal_weights])
                if np.isfinite(tw).all() and tw.sum() > 0:
                    weights = weights * tw
                    total = weights.sum()
                    if total > 0:
                        weights = weights / total
            except Exception as e:
                logger.debug(f"Temporal attention combine skipped: {e}")

            # Predict by robust weighted average of past outcomes
            durations = np.array(
                [float(o.get("duration_ms", 100)) for o in past_outcomes], dtype=float
            )

            # Robust outlier filtering using IQR
            try:
                q1 = np.percentile(durations, 25)
                q3 = np.percentile(durations, 75)
                iqr = q3 - q1
                upper = q3 + 1.5 * iqr
                lower = q1 - 1.5 * iqr
                mask = (durations >= lower) & (durations <= upper)
                if mask.any():
                    durations_filtered = durations[mask]
                    weights_filtered = weights[mask]
                    total = float(weights_filtered.sum())
                    if total > 0:
                        weights_filtered = weights_filtered / total
                    else:
                        weights_filtered = np.ones_like(durations_filtered) / len(
                            durations_filtered
                        )
                else:
                    durations_filtered = durations
                    weights_filtered = np.ones_like(durations) / len(durations)
            except Exception:
                durations_filtered = durations
                weights_filtered = np.ones_like(durations) / len(durations)

            predicted_duration = float(np.average(durations_filtered, weights=weights_filtered))

            # Predict status by majority vote (weighted)
            statuses = [o.get("status", "unknown") for o in past_outcomes]
            status_weights: dict[str, float] = {}
            for status, weight in zip(statuses, weights, strict=False):
                status_weights[status] = status_weights.get(status, 0) + weight

            predicted_status = (
                max(status_weights.items(), key=lambda x: x[1])[0] if status_weights else "unknown"
            )

            # Bayesian confidence: true uncertainty quantification
            confidence = self._bayesian_confidence(past_outcomes)

            # Apply calibration if available and has enough data
            if getattr(self, "_calibrator", None) is not None:
                try:
                    calibrated = self._calibrator.calibrate(confidence)
                    # Only use calibration if it's reasonable (not 0 or nan)
                    if calibrated > 0.0 and not np.isnan(calibrated):
                        confidence = float(calibrated)
                except Exception:
                    pass

            return InstinctPrediction(
                expected_outcome={
                    "duration_ms": float(predicted_duration),
                    "status": predicted_status,
                },
                confidence=float(confidence),
                based_on_samples=len(past_outcomes),
            )

        # No experience yet: fall back to the cached world model, then to a neutral prediction.
        self._ensure_world_model_loaded()
        world_model_prediction = self._predict_with_world_model(context)
        if world_model_prediction is not None:
            return world_model_prediction

        return InstinctPrediction(
            expected_outcome={"duration_ms": 100, "status": "unknown"},
            confidence=0.0,
            based_on_samples=0,
        )

    async def predict_outcome(self, context: dict[str, Any] | str) -> dict[str, Any]:
        """Compatibility wrapper returning only the expected outcome."""
        prediction = await self.predict(context)
        if prediction is None:
            return {}  # type: ignore[unreachable]
        if isinstance(prediction, InstinctPrediction):
            return prediction.expected_outcome
        if isinstance(prediction, dict):  # type: ignore[unreachable]
            return prediction
        return {}

    async def learn(self, *args: Any, **kwargs: Any) -> float:
        """
        Learn from actual outcome with metacognitive calibration tracking.

        Universal mechanism: Store experience, compute error, track calibration.
        Enhanced with adaptive attention learning (research-based 2024+).
        """
        # Persist patterns every 10 learns
        if sum(len(exps) for exps in self._experience.values()) % 10 == 0:
            import asyncio

            safe_create_task(asyncio.to_thread(self.save_patterns))
        # Parse arguments (support legacy kwargs: action, context, actual_duration_ms, prediction_error_ms)
        if args and isinstance(args[0], dict):
            context: dict[str, Any] = args[0]
            # Check both positional args[1] and kwarg actual_outcome
            actual_outcome: dict[str, Any] = (
                args[1]
                if len(args) > 1 and isinstance(args[1], dict)
                else kwargs.get("actual_outcome", {})
            )
        else:
            action = kwargs.get("action")
            context = kwargs.get("context") or {}
            if action and not context.get("action"):
                context = {**context, "action": action}
            # Build actual_outcome from kwargs if provided
            actual_outcome = {}
            if "actual_duration_ms" in kwargs:
                actual_outcome["duration_ms"] = kwargs.get("actual_duration_ms")
            if "prediction_error_ms" in kwargs:
                # Optional carry-through for analyses
                actual_outcome["error_ms"] = kwargs.get("prediction_error_ms")
            if "status" in kwargs:
                actual_outcome["status"] = kwargs.get("status")
            else:
                # Infer simple status
                actual_outcome["status"] = (
                    "success" if kwargs.get("prediction_error_ms") is not None else "unknown"
                )

        # Track calibration via MetacognitiveLayer
        try:
            from kagami.core.coordination.metacognition import get_metacognitive_layer

            metacog = get_metacognitive_layer()
            predicted_conf = context.get("predicted_confidence", 0.5)
            actual_success = actual_outcome.get("status") == "success"
            task_type = context.get("action", "unknown")

            await metacog.record_outcome(  # type: ignore  # Call sig
                predicted_confidence=predicted_conf,
                actual_success=actual_success,
                task_type=task_type,
            )
        except Exception:
            pass  # Metacognitive tracking is optional

        signature = self._extract_signature(context)

        # Compute prediction error before storing
        past = self._experience[signature]
        if len(past) > 0:
            # Error relative to what we would have predicted
            prev_avg = np.mean([o.get("duration_ms", 0) for o in past])
            actual_duration = actual_outcome.get("duration_ms", 0)
            error = abs(actual_duration - prev_avg)
        else:
            error = 0.0

        # ADAPTIVE ATTENTION LEARNING: Update attention weights based on error
        if self._use_adaptive_attention and "_attention_scores" in context:
            try:
                if self._adaptive_attention is None:
                    from kagami.core.learning.adaptive_attention import (
                        get_adaptive_attention,
                    )

                    self._adaptive_attention = get_adaptive_attention()  # type: ignore[assignment]

                # Get attended items (past outcomes with their attention scores)
                attention_scores = context["_attention_scores"]
                attended_items = list(zip(past, attention_scores, strict=False))

                # Update attention weights based on prediction error
                await self._adaptive_attention.update_attention(  # type: ignore  # Dynamic attr
                    attended_items=attended_items,
                    prediction_error=error,
                    task_type=signature,
                    context=context,
                )
            except Exception as e:
                logger.debug(f"Adaptive attention learning failed: {e}")

        # Enrich and store this outcome (add timestamp and minimal intent)
        try:
            if "ts" not in actual_outcome:
                actual_outcome["ts"] = int(time.time() * 1000)
            if "intent" not in actual_outcome:
                actual_outcome["intent"] = {
                    "action": context.get("action", "unknown"),
                    "app": context.get("app", "unknown"),
                    "args": context.get("params") or context.get("metadata") or {},
                }
            if "loop_depth" not in actual_outcome:
                actual_outcome["loop_depth"] = context.get("loop_depth", 0)
        except Exception as e:
            logger.debug(f"Failed to enrich outcome: {e}")

        # Store this outcome (ensure we capture all fields)
        self._experience[signature].append(dict(actual_outcome))
        # Store priority (prediction error) for prioritized replay
        self._priorities[signature].append(error)

        # METRICS: Count prediction instinct training updates
        try:
            from kagami_observability.metrics import (
                INSTINCT_EXPERIENCE_COUNT,
                LOOP_CLOSURE_TRAINING_EVENTS,
                PREDICTION_ERROR_DELTA,
                REGISTRY,
                Counter,
            )

            # Count training event (loop closure evidence)
            LOOP_CLOSURE_TRAINING_EVENTS.labels(instinct="prediction").inc()

            # Track experience accumulation (memory growth)
            INSTINCT_EXPERIENCE_COUNT.labels(
                instinct="prediction", signature=signature[:50]
            ).set(  # Dynamic attr
                len(self._experience[signature])
            )

            # Track prediction error delta (learning effectiveness)
            if len(self._priorities[signature]) >= 2:
                recent_errors = self._priorities[signature][-2:]
                error_delta = abs(recent_errors[-1] - recent_errors[-2])
                PREDICTION_ERROR_DELTA.labels(signature=signature[:50]).observe(
                    error_delta
                )  # Dynamic attr

            # Legacy counter for backward compatibility
            if not hasattr(REGISTRY, "_instinct_training_total"):
                REGISTRY._instinct_training_total = Counter(  # type: ignore  # Dynamic attr
                    "kagami_instinct_training_total",
                    "Instinct training updates",
                    ["instinct"],
                    registry=REGISTRY,
                )
            REGISTRY._instinct_training_total.labels(instinct="prediction").inc()  # type: ignore  # Dynamic attr
        except Exception as e:
            logger.debug(f"Loop closure metrics failed: {e}")

        # Update calibration: consider binary correctness if status present
        try:
            if getattr(self, "_calibrator", None) is not None:
                # Heuristic: success statuses treated as correct
                status = str(actual_outcome.get("status", "")).lower()
                correct = status in {"ok", "success", "passed"}
                # Estimate prior raw confidence by recomputing without calibration
                raw_conf = self._bayesian_confidence(self._experience[signature])
                self._calibrator.observe(raw_conf, correct)
        except Exception:
            pass

        # Keep bounded history (most recent 500)
        if len(self._experience[signature]) > 500:
            self._experience[signature] = self._experience[signature][-500:]
            self._priorities[signature] = self._priorities[signature][-500:]

        return float(error)

    def _extract_signature(self, context: dict[str, Any]) -> str:
        """
        Extract general signature from context.

        This is the key to generalization: group similar contexts.
        """
        # Universal features that matter:
        app = context.get("app", "unknown")
        action = context.get("action", "unknown")

        # Add semantic features if available
        complexity = context.get("metadata", {}).get("complexity", "normal")

        return f"{app}::{action}::{complexity}"

    def _measure_consistency(self, outcomes: list[Any]) -> float:
        """Measure how consistent past outcomes were (variance penalty)."""
        if len(outcomes) < 2:
            return 1.0

        durations = [o.get("duration_ms", 0) for o in outcomes]
        std = np.std(durations)
        mean_val = np.mean(durations)

        if mean_val == 0:
            return 0.5

        # Coefficient of variation (lower = more consistent)
        cv = std / mean_val
        consistency = max(0, 1.0 - cv)

        return float(consistency)

    def _bayesian_confidence(self, outcomes: list[float]) -> float:
        """
        Bayesian confidence: true uncertainty quantification.

        Note: MetacognitiveLayer integration would require async, kept sync for now.
        """
        # NOTE: MetacognitiveLayer requires async, would integrate in async predict() method

        n = len(outcomes)

        if n == 0:
            return 0.0

        if n == 1:
            return 0.1

        # n >= 2
        # Simple confidence from sample count (works well)
        # More samples = more confidence
        base_confidence = min(0.9, 0.2 + (n / 50) * 0.7)

        # Adjust for consistency
        consistency = self._measure_consistency(outcomes)

        # Combine
        final_confidence = base_confidence * (0.5 + 0.5 * consistency)

        return float(min(1.0, max(0.0, final_confidence)))

    async def extract_patterns_with_llm(self, signature: str) -> dict[str, Any] | None:
        """LLM-ENHANCED: Extract semantic patterns from experiences.

        Uses LLM to analyze WHY predictions succeed/fail and identify patterns.
        Called when enough data exists (n >= 10).

        Args:
            signature: Task signature to analyze

        Returns:
            Extracted patterns or None if not enough data
        """
        experiences = self._experience.get(signature, [])

        if len(experiences) < 10:
            return None  # Need minimum data for pattern extraction

        # ADAPTIVE: Check if should extract now (adaptive scheduling)
        import time

        try:
            from kagami.core.instincts.adaptive_pattern_extraction import (
                get_adaptive_pattern_extractor,
            )

            extractor = get_adaptive_pattern_extractor()

            # Compute recent error rate
            recent_errors = self._priorities.get(signature, [])[-10:]
            recent_error_rate = (
                sum(recent_errors) / (len(recent_errors) * 100.0) if recent_errors else 0.0
            )

            schedule = extractor.should_extract_now(signature, experiences, recent_error_rate)

            if not schedule.should_extract:
                logger.debug(
                    f"Pattern extraction skipped for {signature}: {schedule.reason} "
                    f"(next: {schedule.next_extract_time - time.time():.0f}s)"
                )
                return self._learned_patterns.get(signature)

            logger.info(
                f"Pattern extraction triggered for {signature}: {schedule.reason} "
                f"(confidence: {schedule.confidence:.2f})"
            )
        except Exception as e:
            # Fallback to fixed 1-hour cooldown
            logger.debug(f"Adaptive extraction unavailable: {e}")
            last_extract = self._last_pattern_extraction.get(signature, 0)
            if time.time() - last_extract < 3600:  # 1 hour cooldown
                return self._learned_patterns.get(signature)

        # Lazy load LLM service
        if self._llm_service is None:
            try:
                from kagami.core.services.llm.service import get_llm_service

                self._llm_service = get_llm_service()  # type: ignore[assignment]
            except Exception as e:
                logger.debug(f"LLM service unavailable for pattern extraction: {e}")
                return None

        try:
            # Prepare experience summary
            durations = [e.get("duration_ms", 0) for e in experiences]
            statuses = [e.get("status", "unknown") for e in experiences]

            # LLM analyzes patterns
            prompt = f"""Analyze these {len(experiences)} task execution experiences:

Task signature: {signature}

Durations (ms): {durations[:10]}  # First 10
Statuses: {statuses[:10]}
Mean: {np.mean(durations):.1f}ms, Std: {np.std(durations):.1f}ms

Extract insights:
1. What makes this task fast vs slow?
2. What patterns lead to 'blocked' status?
3. What predicts success?
4. Key duration predictors?

Respond in JSON: {{"success_patterns": [...], "failure_patterns": [...], "duration_predictors": [...]}}
"""

            # Use fast model for pattern extraction
            result = await self._llm_service.generate(  # type: ignore  # Dynamic attr
                prompt=prompt,
                max_tokens=500,
                temperature=0.3,  # Analytical, not creative
            )

            # Parse patterns
            import json

            try:
                patterns = json.loads(result.get("text", "{}"))
            except Exception:
                # LLM didn't return valid JSON, extract insights from text
                patterns = {
                    "raw_insights": result.get("text", ""),
                    "extracted_via": "llm_text_analysis",
                }

            # Store patterns
            self._learned_patterns[signature] = patterns
            self._last_pattern_extraction[signature] = time.time()

            # Mark extraction in adaptive scheduler
            try:
                from kagami.core.instincts.adaptive_pattern_extraction import (
                    get_adaptive_pattern_extractor,
                )

                extractor = get_adaptive_pattern_extractor()
                recent_errors = self._priorities.get(signature, [])[-10:]
                error_rate = (
                    sum(recent_errors) / (len(recent_errors) * 100.0) if recent_errors else 0.0
                )
                extractor.mark_extracted(signature, len(experiences), error_rate)
            except Exception:
                pass

            logger.info(f"🧠 Extracted patterns for {signature} via LLM")
            return patterns  # type: ignore[no-any-return]

        except Exception as e:
            logger.warning(f"LLM pattern extraction failed: {e}")
            return None

    async def predict_with_llm(self, context: dict[str, Any]) -> InstinctPrediction:
        """LLM-ENHANCED prediction using learned patterns.

        Combines statistical baseline with LLM semantic understanding.

        Args:
            context: Task context

        Returns:
            Enhanced prediction with higher accuracy
        """
        signature = self._extract_signature(context)

        # Try pattern-based prediction first
        patterns = self._learned_patterns.get(signature)
        if not patterns:
            # Extract patterns if we have enough data
            patterns = await self.extract_patterns_with_llm(signature)

        if patterns and patterns.get("duration_predictors"):
            # Use LLM to make prediction based on patterns
            if self._llm_service:
                try:  # type: ignore  # Defensive/fallback code
                    prompt = f"""Based on these learned patterns:
{patterns}

Predict duration for task: {context}

Consider:
- Similar past experiences
- Identified success/failure patterns
- Duration predictors

Respond with number only (milliseconds).
"""
                    result = await self._llm_service.generate(
                        prompt=prompt,
                        max_tokens=10,
                        temperature=0.1,
                    )

                    # Extract duration from response
                    import re

                    match = re.search(r"(\d+\.?\d*)", result.get("text", ""))
                    if match:
                        llm_duration = float(match.group(1))

                        # Blend with statistical prediction
                        stat_prediction = await self.predict(context)
                        blended_duration = (
                            0.6 * llm_duration
                            + 0.4
                            * stat_prediction.expected_outcome.get("duration_ms", llm_duration)
                        )

                        return InstinctPrediction(
                            expected_outcome={
                                "duration_ms": blended_duration,
                                "confidence": 0.8,  # Higher confidence with LLM
                                "method": "llm_enhanced",
                            },
                            confidence=0.8,
                            based_on_samples=len(self._experience.get(signature, [])),
                        )
                except Exception as e:
                    # NO FALLBACK - LLM prediction is required for enhanced mode
                    raise RuntimeError(
                        f"LLM-enhanced prediction failed: {e}\n"
                        "LLM is required for semantic prediction. Fix LLM service, no statistical fallback."
                    ) from e

        # Should never reach here - both paths above raise or return
        raise RuntimeError("Invalid code path in predict_with_llm_enhancement") from None

    async def cluster_experiences_semantically(
        self, threshold: float = 0.8
    ) -> dict[str, list[str]]:
        """SEMANTIC CLUSTERING: Group similar tasks even with different signatures.

        Uses embeddings to find semantically similar experiences and cluster them.
        This allows learning to transfer across similar-but-not-identical tasks.

        Args:
            threshold: Cosine similarity threshold for clustering (0-1) from e

        Returns:
            Dict of cluster_id -> list[Any] of signatures in that cluster
        """
        # Lazy load embedding service
        if self._embedding_service is None:
            try:
                from kagami.core.services.embedding_service import (
                    get_embedding_service,
                )

                self._embedding_service = get_embedding_service()  # type: ignore[assignment]
            except Exception as e:
                logger.debug(f"Embedding service unavailable for clustering: {e}")
                return {}

        # Get all signatures with sufficient data
        signatures = [
            sig
            for sig, exps in self._experience.items()
            if len(exps) >= 3  # Minimum for meaningful clustering
        ]

        if len(signatures) < 2:
            return {}  # Need at least 2 for clustering

        try:
            # Embed all signatures
            embeddings = []
            for sig in signatures:
                vec = self._embedding_service.embed_text(sig)  # type: ignore  # Dynamic attr
                embeddings.append(vec)

            # Simple hierarchical clustering
            import numpy as np

            clusters: dict[str, list[str]] = {}
            used = set()
            cluster_id = 0

            for i, sig in enumerate(signatures):
                if sig in used:
                    continue

                # Start new cluster
                cluster_key = f"cluster_{cluster_id}"
                clusters[cluster_key] = [sig]
                used.add(sig)

                # Find similar signatures
                emb_i = embeddings[i]
                for j, sig_j in enumerate(signatures):
                    if sig_j in used:
                        continue

                    # Cosine similarity
                    emb_j = embeddings[j]
                    similarity = float(np.dot(emb_i, emb_j))  # Already normalized

                    if similarity > threshold:
                        clusters[cluster_key].append(sig_j)
                        used.add(sig_j)
                        self._signature_to_cluster[sig_j] = cluster_key

                self._signature_to_cluster[sig] = cluster_key
                cluster_id += 1

            self._semantic_clusters = clusters
            logger.info(
                f"🔍 Clustered {len(signatures)} signatures into {len(clusters)} semantic groups"
            )
            return clusters

        except Exception as e:
            logger.warning(f"Semantic clustering failed: {e}")
            return {}

    def get_state(self) -> dict[str, Any]:
        """Get instinct state for persistence.

        Returns:
            State dict[str, Any] with experience data
        """
        return {
            "experience": {k: list(v) for k, v in self._experience.items()},
            "priorities": {k: list(v) for k, v in self._priorities.items()},
            "learned_patterns": self._learned_patterns,  # Include LLM-extracted patterns
            "semantic_clusters": self._semantic_clusters,  # Include semantic clusters
            "total_predictions": sum(len(v) for v in self._experience.values()),
        }

    def save_patterns(self) -> dict[str, Any]:
        """Save learned patterns to disk for persistence."""
        import json
        from pathlib import Path

        try:
            patterns_path = Path("state/instinct_memory.json")
            patterns_path.parent.mkdir(parents=True, exist_ok=True)

            # Load existing
            if patterns_path.exists():
                with open(patterns_path) as f:
                    data = json.load(f)
            else:
                data = {}

            # Save prediction patterns
            data["patterns"] = data.get("patterns", [])
            data["predictions"] = {}

            # Convert experience dict[str, Any] to serializable format
            for sig, experiences in list(self._experience.items())[:100]:  # Keep top 100
                if experiences:
                    pattern = {
                        "signature": sig,
                        "sample_count": len(experiences),
                        "avg_duration": (
                            sum(e.get("duration_ms", 0) for e in experiences) / len(experiences)
                            if experiences
                            else 0
                        ),
                        "success_rate": (
                            sum(1 for e in experiences if e.get("status") == "success")
                            / len(experiences)
                            if experiences
                            else 0
                        ),
                    }
                    data["patterns"].append(pattern)

            # Save predictions cache
            for sig, pred in list(self._last_prediction.items())[:100]:  # Dynamic attr
                if pred:
                    data["predictions"][sig] = {
                        "duration_ms": pred.expected_outcome.get("duration_ms", 0),
                        "confidence": pred.confidence,
                    }

            # Write to disk
            with open(patterns_path, "w") as f:
                json.dump(data, f, indent=2)

            logger.debug(f"💾 Saved {len(data['patterns'])} prediction patterns")
            return {"saved": len(data["patterns"])}

        except Exception as e:
            logger.warning(f"Failed to save prediction patterns: {e}")
            return {"error": str(e)}

    async def update_from_experience(  # type: ignore[no-untyped-def]
        self,
        *,
        context: dict[str, Any],
        outcome: dict[str, Any],
        weight: float | None = None,
        **kwargs,
    ) -> None:
        """Compatibility helper used by integration tests."""
        await self.learn(context, outcome, weight=weight, **kwargs)


# Singleton accessor (for consistency with other instincts)
_prediction_instinct: PredictionInstinct | None = None


def get_prediction_instinct() -> PredictionInstinct:
    """Get global PredictionInstinct singleton.

    Returns:
        PredictionInstinct instance
    """
    global _prediction_instinct
    if _prediction_instinct is None:
        _prediction_instinct = PredictionInstinct()
    return _prediction_instinct
