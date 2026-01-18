"""LLM + World Model + CBF Pipeline.

End-to-end pipeline that integrates:
- LLM candidate generation
- World model outcome prediction
- CBF safety filtering
- Learning and adaptation
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class PipelineConfig:
    """Configuration for LLM+WM+CBF pipeline."""

    n_candidates: int = 3
    use_world_model: bool = True
    use_cbf_filter: bool = True
    enable_learning: bool = False
    fallback_on_all_unsafe: bool = True
    timeout_seconds: float = 30.0


@dataclass
class PipelineResult:
    """Result of pipeline processing."""

    safe: bool = True
    response: str = ""
    h_x: float = 0.0
    confidence: float = 0.0
    candidates_generated: int = 0
    candidates_safe: int = 0
    latency_ms: float = 0.0
    world_model_used: bool = False
    breakdown: dict[str, float] = field(default_factory=dict)


class LLMWorldModelCBFPipeline:
    """Integrated pipeline for safe LLM response generation.

    Pipeline stages:
    1. Generate candidate responses (LLM)
    2. Predict outcomes (World Model)
    3. Filter unsafe candidates (CBF)
    4. Select best response
    5. Learn from outcome (optional)
    """

    def __init__(self, config: PipelineConfig | None = None) -> None:
        """Initialize pipeline.

        Args:
            config: Pipeline configuration
        """
        self.config = config or PipelineConfig()
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize pipeline components."""
        self._initialized = True

    async def process(
        self,
        prompt: str,
        context: dict[str, Any],
        app_name: str = "default",
    ) -> PipelineResult:
        """Process a prompt through the full pipeline.

        Args:
            prompt: User prompt
            context: Request context
            app_name: Application name for tracking

        Returns:
            PipelineResult with response and metrics
        """
        start_time = time.time()
        breakdown: dict[str, float] = {}

        # Stage 1: Generate candidates
        gen_start = time.time()
        candidates = await self._generate_candidates(prompt, context, app_name)
        breakdown["llm_generate"] = (time.time() - gen_start) * 1000

        if not candidates:
            return PipelineResult(
                safe=False,
                response="Failed to generate candidates",
                latency_ms=(time.time() - start_time) * 1000,
                breakdown=breakdown,
            )

        # Stage 2: Predict outcomes with world model
        wm_start = time.time()
        predictions = await self._predict_outcomes(candidates, context)
        breakdown["world_model_predict"] = (time.time() - wm_start) * 1000

        # Stage 3: Filter with CBF
        cbf_start = time.time()
        safe_candidates = await self._filter_with_cbf(candidates, predictions, context, app_name)
        breakdown["cbf_filter"] = (time.time() - cbf_start) * 1000

        # Stage 4: Select best
        select_start = time.time()
        if safe_candidates:
            # Select highest h_x
            best_candidate, best_prediction, best_h_x = max(safe_candidates, key=lambda x: x[2])
            response = best_candidate
            is_safe = True
            h_x = best_h_x
            confidence = best_prediction.get("confidence", 0.5)
        elif self.config.fallback_on_all_unsafe:
            # Use first candidate but mark as unsafe
            response = candidates[0]
            is_safe = False
            h_x = -0.1
            confidence = 0.0
        else:
            response = "All candidates filtered as unsafe"
            is_safe = False
            h_x = -0.5
            confidence = 0.0
        breakdown["selection"] = (time.time() - select_start) * 1000

        # Stage 5: Learn if enabled
        if self.config.enable_learning and is_safe:
            await self._record_outcome(
                {"prompt": prompt, "response": response, "h_x": h_x},
                context,
            )

        total_latency = (time.time() - start_time) * 1000

        return PipelineResult(
            safe=is_safe,
            response=response,
            h_x=h_x,
            confidence=confidence,
            candidates_generated=len(candidates),
            candidates_safe=len(safe_candidates),
            latency_ms=total_latency,
            world_model_used=self.config.use_world_model,
            breakdown=breakdown,
        )

    async def _generate_candidates(
        self,
        prompt: str,
        context: dict[str, Any],
        app_name: str,
    ) -> list[str]:
        """Generate candidate responses.

        Args:
            prompt: User prompt
            context: Request context
            app_name: Application name

        Returns:
            List of candidate responses
        """
        # Default implementation - generate simple responses
        candidates = []
        for i in range(self.config.n_candidates):
            candidates.append(f"Response {i + 1} for: {prompt}")
        return candidates

    async def _predict_outcomes(
        self,
        candidates: list[str],
        context: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Predict outcomes for candidates using world model.

        Args:
            candidates: List of candidate responses
            context: Request context

        Returns:
            List of prediction dictionaries
        """
        if not self.config.use_world_model:
            # Return default predictions
            return [
                {"confidence": 0.5, "uncertainty": 0.5, "state": {}, "learned_threat": 0.1}
                for _ in candidates
            ]

        predictions = []
        for candidate in candidates:
            predictions.append(
                {
                    "confidence": 0.8,
                    "uncertainty": 0.2,
                    "state": {"summary": candidate[:50]},
                    "learned_threat": 0.1,
                }
            )
        return predictions

    async def _filter_with_cbf(
        self,
        candidates: list[str],
        predictions: list[dict[str, Any]],
        context: dict[str, Any],
        app_name: str,
    ) -> list[tuple[str, dict[str, Any], float]]:
        """Filter candidates with CBF.

        Args:
            candidates: List of candidate responses
            predictions: List of predictions
            context: Request context
            app_name: Application name

        Returns:
            List of (candidate, prediction, h_x) tuples that pass CBF
        """
        if not self.config.use_cbf_filter:
            # Return all with default h_x
            return [(cand, pred, 0.5) for cand, pred in zip(candidates, predictions, strict=False)]

        safe_candidates = []
        for candidate, prediction in zip(candidates, predictions, strict=False):
            # Simple CBF check
            threat = prediction.get("learned_threat", 0.0)
            uncertainty = prediction.get("uncertainty", 0.5)

            h_x = 1.0 - threat - uncertainty * 0.5

            if h_x >= 0:
                safe_candidates.append((candidate, prediction, h_x))

        return safe_candidates

    async def _record_outcome(
        self,
        result: dict[str, Any],
        context: dict[str, Any],
    ) -> None:
        """Record outcome for learning.

        Args:
            result: Pipeline result
            context: Request context
        """
        # Default: no-op
        pass


# Global pipeline instance
_pipeline: LLMWorldModelCBFPipeline | None = None


def get_pipeline(config: PipelineConfig | None = None) -> LLMWorldModelCBFPipeline:
    """Get or create pipeline instance.

    Args:
        config: Optional configuration

    Returns:
        Pipeline instance
    """
    global _pipeline
    if _pipeline is None or config is not None:
        _pipeline = LLMWorldModelCBFPipeline(config)
    return _pipeline


__all__ = [
    "LLMWorldModelCBFPipeline",
    "PipelineConfig",
    "PipelineResult",
    "get_pipeline",
]
