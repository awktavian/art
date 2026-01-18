"""LLM-Driven Multi-Model Router - NO HEURISTIC FALLBACKS.

This module implements fully LLM-driven routing with resilience through:
1. LLM-based task classification
2. LLM-based model selection
3. Exponential backoff retry on failures
4. NO hardcoded fallback chains
5. NO default models

All routing decisions are made by the LLM itself, ensuring the system
is fully self-directed and learns from outcomes.

Created: January 5, 2026
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class TaskType(Enum):
    """Task types for routing."""

    CREATIVE = "creative"
    ANALYTICAL = "analytical"
    CODE = "code"
    REASONING = "reasoning"
    GENERAL = "general"


@dataclass
class ModelCapability:
    """Model capability definition."""

    name: str
    provider: str
    api_key_env: str | None
    cost_per_1k_tokens: float
    available: bool = True
    strengths: list[str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        """Initialize strengths if None."""
        if self.strengths is None:
            self.strengths = []


class LLMDrivenRouter:
    """Fully LLM-driven router with NO heuristic fallbacks.

    Key principles:
    1. ALL routing decisions made by LLM
    2. NO hardcoded fallback chains
    3. NO default models
    4. Resilience through exponential backoff retry
    5. Learning from outcomes via performance tracking
    """

    def __init__(self) -> None:
        """Initialize LLM-driven router."""
        self._models: dict[str, ModelCapability] = {}
        self._performance_matrix: dict[tuple[TaskType, str], float] = {}
        self._usage_count: dict[str, int] = {}
        self._total_cost_usd: float = 0.0
        self._llm_service: Any = None

    async def initialize(self) -> None:
        """Initialize LLM service for routing decisions."""
        from kagami.core.services.llm import get_llm_service

        self._llm_service = get_llm_service()
        await self._llm_service.initialize()

        # Register available models
        self._register_models()

    def _register_models(self) -> None:
        """Register available models with their capabilities."""
        # Cloud models
        self._models["deepseek-v3"] = ModelCapability(
            name="deepseek-v3",
            provider="deepseek",
            api_key_env="DEEPSEEK_API_KEY",
            cost_per_1k_tokens=0.0014,
            strengths=["reasoning", "code", "general"],
        )

        self._models["gpt-4o"] = ModelCapability(
            name="gpt-4o",
            provider="openai",
            api_key_env="OPENAI_API_KEY",
            cost_per_1k_tokens=0.005,
            strengths=["creative", "analytical", "general"],
        )

        self._models["claude-3.5-sonnet"] = ModelCapability(
            name="claude-3.5-sonnet",
            provider="anthropic",
            api_key_env="ANTHROPIC_API_KEY",
            cost_per_1k_tokens=0.003,
            strengths=["reasoning", "analytical", "code"],
        )

        # Local models
        self._models["qwen2.5-72b"] = ModelCapability(
            name="qwen2.5-72b",
            provider="local",
            api_key_env=None,
            cost_per_1k_tokens=0.0,
            strengths=["general", "code"],
        )

        self._models["qwen2.5-14b"] = ModelCapability(
            name="qwen2.5-14b",
            provider="local",
            api_key_env=None,
            cost_per_1k_tokens=0.0,
            strengths=["general"],
        )

    async def classify_task(self, query: str) -> TaskType:
        """Classify task type using LLM.

        Args:
            query: User query

        Returns:
            TaskType classification

        Raises:
            RuntimeError: If LLM classification fails after retries
        """
        if not self._llm_service:
            raise RuntimeError("Router not initialized - call initialize() first")

        prompt = f"""Classify this task into ONE category:
- CREATIVE: Generate ideas, brainstorm, create content
- ANALYTICAL: Analyze data, research, investigate
- CODE: Write, debug, or review code
- REASONING: Complex logic, planning, problem-solving
- GENERAL: Simple queries, information retrieval

Task: {query}

Respond with ONLY the category name."""

        # Retry with exponential backoff
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = await self._llm_service.generate(
                    prompt=prompt,
                    max_tokens=10,
                    temperature=0.0,
                )

                # Parse response
                category = response.strip().upper()
                for task_type in TaskType:
                    if task_type.value.upper() == category:
                        return task_type

                # If no match, try again
                if attempt < max_retries - 1:
                    await asyncio.sleep(2**attempt)  # Exponential backoff
                    continue

                # Last attempt failed - raise error
                raise RuntimeError(f"LLM returned invalid category: {category}")

            except Exception as e:
                if attempt < max_retries - 1:
                    logger.warning(f"Task classification attempt {attempt + 1} failed: {e}")
                    await asyncio.sleep(2**attempt)
                    continue
                raise RuntimeError(
                    f"Task classification failed after {max_retries} attempts"
                ) from e

        # Should never reach here
        raise RuntimeError("Task classification failed")

    async def select_model(
        self,
        query: str,
        task_type: TaskType,
    ) -> tuple[str, str]:
        """Select best model using LLM reasoning.

        Args:
            query: User query
            task_type: Classified task type

        Returns:
            (model_name, provider) tuple

        Raises:
            RuntimeError: If model selection fails after retries
        """
        if not self._llm_service:
            raise RuntimeError("Router not initialized - call initialize() first")

        # Build model options with performance data
        model_options = []
        for name, model in self._models.items():
            if not model.available:
                continue

            perf = self._performance_matrix.get((task_type, name), 0.5)
            usage = self._usage_count.get(name, 0)

            model_options.append(
                f"- {name} ({model.provider}): "
                f"strengths={model.strengths}, "
                f"performance={perf:.2f}, "
                f"usage={usage}, "
                f"cost=${model.cost_per_1k_tokens}/1k"
            )

        prompt = f"""Select the BEST model for this task.

Task Type: {task_type.value}
Query: {query}

Available Models:
{chr(10).join(model_options)}

Consider:
1. Model strengths matching task type
2. Historical performance for this task type
3. Cost efficiency
4. Current usage distribution (prefer underutilized models)

Respond with ONLY the model name (e.g., "deepseek-v3")."""

        # Retry with exponential backoff
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = await self._llm_service.generate(
                    prompt=prompt,
                    max_tokens=20,
                    temperature=0.2,  # Low temp for consistent selection
                )

                # Parse response
                model_name = response.strip().lower()

                # Validate model exists and is available
                if model_name in self._models and self._models[model_name].available:
                    provider = self._models[model_name].provider
                    logger.info(f"🎯 LLM selected: {model_name} ({provider}) for {task_type.value}")
                    return (model_name, provider)

                # Invalid model - retry
                if attempt < max_retries - 1:
                    logger.warning(f"LLM selected invalid model: {model_name}, retrying...")
                    await asyncio.sleep(2**attempt)
                    continue

                raise RuntimeError(f"LLM selected invalid model: {model_name}")

            except Exception as e:
                if attempt < max_retries - 1:
                    logger.warning(f"Model selection attempt {attempt + 1} failed: {e}")
                    await asyncio.sleep(2**attempt)
                    continue
                raise RuntimeError(f"Model selection failed after {max_retries} attempts") from e

        raise RuntimeError("Model selection failed")

    async def route(
        self,
        query: str,
        task_type: TaskType | None = None,
    ) -> tuple[str, str]:
        """Route query to best model using LLM decisions.

        Args:
            query: User query
            task_type: Optional pre-classified task type

        Returns:
            (model_name, provider) tuple

        Raises:
            RuntimeError: If routing fails after all retries
        """
        # Classify task if not provided
        if task_type is None:
            task_type = await self.classify_task(query)

        # Select model
        return await self.select_model(query, task_type)

    async def record_outcome(
        self,
        query: str,
        model_used: str,
        task_type: TaskType,
        success: bool,
        quality_score: float | None = None,
    ) -> None:
        """Record routing outcome for learning.

        Args:
            query: Original query
            model_used: Model that was used
            task_type: Task type
            success: Whether execution succeeded
            quality_score: Optional quality score (0-1)
        """
        # Update performance matrix
        key = (task_type, model_used)
        current_perf = self._performance_matrix.get(key, 0.5)

        # Update with exponential moving average
        alpha = 0.1  # Learning rate
        new_perf = quality_score if quality_score is not None else (1.0 if success else 0.0)
        updated_perf = (1 - alpha) * current_perf + alpha * new_perf

        self._performance_matrix[key] = updated_perf

        # Update usage count
        self._usage_count[model_used] = self._usage_count.get(model_used, 0) + 1

        # Update cost
        if model_used in self._models:
            # Estimate tokens (rough approximation)
            estimated_tokens = len(query.split()) * 1.3
            cost = (estimated_tokens / 1000) * self._models[model_used].cost_per_1k_tokens
            self._total_cost_usd += cost

        logger.debug(
            f"📊 Recorded outcome: {model_used} for {task_type.value} "
            f"(success={success}, perf={updated_perf:.2f})"
        )

    def get_stats(self) -> dict[str, Any]:
        """Get routing statistics.

        Returns:
            Dict with performance metrics
        """
        return {
            "total_cost_usd": self._total_cost_usd,
            "usage_count": self._usage_count,
            "performance_matrix": {
                f"{task.value}/{model}": perf
                for (task, model), perf in self._performance_matrix.items()
            },
            "models_available": {name: model.available for name, model in self._models.items()},
        }


# =============================================================================
# FACTORY (via centralized registry)
# =============================================================================

from kagami.core.shared_abstractions.singleton_consolidation import (
    get_singleton_registry,
)

_singleton_registry = get_singleton_registry()
get_llm_driven_router = _singleton_registry.register_async("llm_driven_router", LLMDrivenRouter)


__all__ = [
    "LLMDrivenRouter",
    "ModelCapability",
    "TaskType",
    "get_llm_driven_router",
]
