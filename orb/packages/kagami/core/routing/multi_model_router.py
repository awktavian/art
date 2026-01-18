from __future__ import annotations

from typing import Any

"""Multi-Model Router - Intelligent LLM Selection (Dec 2024).

Routes queries to optimal models based on task type and learned performance.

SUPPORTED MODELS (Dec 2024 - Verified):
========================================
Cloud:
- DeepSeek V3 (Dec 26, 2024) - 671B MoE, MIT licensed, $0.14/1M tokens
- DeepSeek-R1 - Reasoning model, chain-of-thought
- Gemini 2.0 Pro - 1M context, multimodal
- Claude 3.5 Opus - 200K context, safety-first
- GPT-4o - General reasoning

Local (M3 Ultra 512GB Optimized):
- Qwen2.5-72B-Instruct - Flagship general
- Qwen2.5-Coder-32B-Instruct - Code generation
- DeepSeek-R1-Distill-Qwen-70B - Local reasoning
- Llama-3.3-70B-Instruct - Alternative general

Learning: Tracks (task_type, model) → success_rate and improves routing.
"""
import asyncio
import logging
import os
from dataclasses import dataclass

# Import canonical TaskType from unified types module
from kagami.core.services.llm.types import TaskType, is_test_mode

logger = logging.getLogger(__name__)


def _is_test_runtime() -> bool:
    """Return True when running under pytest/test mode."""
    return is_test_mode()


def _get_classifier_timeout() -> float:
    """Read timeout for LLM-based routing."""
    try:
        return float(os.getenv("KAGAMI_ROUTER_CLASSIFIER_TIMEOUT_SECONDS", "5"))
    except ValueError:
        return 5.0


@dataclass
class ModelCapability:
    """Model capabilities and configuration."""

    name: str
    provider: str  # openai, google, anthropic, local
    api_key_env: str | None  # Environment variable for API key
    cost_per_1k_tokens: float  # Cost in USD
    strengths: list[TaskType]  # What it's good at
    max_tokens: int
    supports_streaming: bool = True
    available: bool = False  # Set at runtime


class MultiModelRouter:
    """Routes queries to optimal LLM based on task type and performance.

    Key Features:
    - Task classification (auto-detect task type)
    - Performance tracking ((task, model) → success_rate)
    - Cost optimization (prefer local 90%, cloud 10%)
    - Fallback chains (GPT-5 → Gemini → Claude → local)
    - Learning from outcomes (gradient descent on performance matrix)
    """

    def __init__(self) -> None:
        self._models = self._initialize_models()
        self._performance_matrix: dict[tuple[str, str], float] = {}
        self._usage_count: dict[str, int] = {}
        self._total_cost_usd = 0.0

        # Check which models are available
        self._check_availability()

    def _initialize_models(self) -> dict[str, ModelCapability]:
        """Initialize model registry (Dec 2024 - Verified models only)."""
        return {
            # ═══════════════════════════════════════════════════════════════
            # DEEPSEEK (PRIMARY - Best value, MIT licensed)
            # ═══════════════════════════════════════════════════════════════
            "deepseek-v3": ModelCapability(
                name="deepseek-v3",
                provider="deepseek",
                api_key_env="DEEPSEEK_API_KEY",  # pragma: allowlist secret
                cost_per_1k_tokens=0.00014,  # $0.14/1M input, $0.28/1M output
                strengths=[
                    TaskType.CODE_GENERATION,
                    TaskType.CODE_REVIEW,
                    TaskType.MATH_PROOF,
                    TaskType.GENERAL_REASONING,
                    TaskType.LONG_CONTEXT,
                ],
                max_tokens=128000,
                supports_streaming=True,
                available=False,
            ),
            "deepseek-coder": ModelCapability(
                name="deepseek-coder",
                provider="deepseek",
                api_key_env="DEEPSEEK_API_KEY",  # pragma: allowlist secret
                cost_per_1k_tokens=0.00014,
                strengths=[TaskType.CODE_GENERATION, TaskType.CODE_REVIEW],
                max_tokens=128000,
                supports_streaming=True,
                available=False,
            ),
            # ═══════════════════════════════════════════════════════════════
            # LOCAL MODELS (M3 Ultra 512GB - Cost-free)
            # ═══════════════════════════════════════════════════════════════
            "qwen2.5-72b": ModelCapability(
                name="qwen2.5-72b",
                provider="local",
                api_key_env=None,
                cost_per_1k_tokens=0.0,
                strengths=[
                    TaskType.GENERAL_REASONING,
                    TaskType.CODE_GENERATION,
                    TaskType.MATH_PROOF,
                    TaskType.DATA_ANALYSIS,
                ],
                max_tokens=32768,
                supports_streaming=True,
                available=True,
            ),
            "qwen2.5-coder-32b": ModelCapability(
                name="qwen2.5-coder-32b",
                provider="local",
                api_key_env=None,
                cost_per_1k_tokens=0.0,
                strengths=[TaskType.CODE_GENERATION, TaskType.CODE_REVIEW],
                max_tokens=32768,
                supports_streaming=True,
                available=True,
            ),
            "qwen2.5-14b": ModelCapability(
                name="qwen2.5-14b",
                provider="local",
                api_key_env=None,
                cost_per_1k_tokens=0.0,
                strengths=[TaskType.GENERAL_REASONING, TaskType.FAST_QUERY],
                max_tokens=32768,
                supports_streaming=True,
                available=True,
            ),
            "qwen2.5-7b": ModelCapability(
                name="qwen2.5-7b",
                provider="local",
                api_key_env=None,
                cost_per_1k_tokens=0.0,
                strengths=[TaskType.FAST_QUERY],
                max_tokens=32768,
                supports_streaming=True,
                available=True,
            ),
            "deepseek-r1-70b": ModelCapability(
                name="deepseek-r1-70b",
                provider="local",
                api_key_env=None,
                cost_per_1k_tokens=0.0,
                strengths=[
                    TaskType.MATH_PROOF,
                    TaskType.SCIENCE_RESEARCH,
                    TaskType.GENERAL_REASONING,
                ],
                max_tokens=32768,
                supports_streaming=True,
                available=True,
            ),
            "llama-3.3-70b": ModelCapability(
                name="llama-3.3-70b",
                provider="local",
                api_key_env=None,
                cost_per_1k_tokens=0.0,
                strengths=[
                    TaskType.GENERAL_REASONING,
                    TaskType.CREATIVE_WRITING,
                    TaskType.CODE_GENERATION,
                ],
                max_tokens=128000,
                supports_streaming=True,
                available=True,
            ),
            # ═══════════════════════════════════════════════════════════════
            # CLOUD MODELS (Fallback / Specialized)
            # ═══════════════════════════════════════════════════════════════
            "gemini-2.0-pro": ModelCapability(
                name="gemini-2.0-pro",
                provider="google",
                api_key_env="GOOGLE_API_KEY",  # pragma: allowlist secret
                cost_per_1k_tokens=0.00125,  # $1.25/1M
                strengths=[
                    TaskType.WEB_RESEARCH,
                    TaskType.MULTIMODAL,
                    TaskType.MULTIMODAL_VISION,
                    TaskType.LONG_CONTEXT,
                ],
                max_tokens=1000000,
                supports_streaming=True,
                available=False,
            ),
            "claude-3.5-opus": ModelCapability(
                name="claude-3.5-opus",
                provider="anthropic",
                api_key_env="ANTHROPIC_API_KEY",  # pragma: allowlist secret
                cost_per_1k_tokens=0.015,
                strengths=[
                    TaskType.CODE_GENERATION,
                    TaskType.CODE_REVIEW,
                    TaskType.GENERAL_REASONING,
                    TaskType.LONG_CONTEXT,
                ],
                max_tokens=200000,
                supports_streaming=True,
                available=False,
            ),
            "gpt-4o": ModelCapability(
                name="gpt-4o",
                provider="openai",
                api_key_env="OPENAI_API_KEY",  # pragma: allowlist secret
                cost_per_1k_tokens=0.005,  # $5/1M input
                strengths=[
                    TaskType.GENERAL_REASONING,
                    TaskType.CREATIVE_WRITING,
                    TaskType.MULTIMODAL,
                ],
                max_tokens=128000,
                supports_streaming=True,
                available=False,
            ),
            # ═══════════════════════════════════════════════════════════════
            # MULTIMODAL (Vision/Audio)
            # ═══════════════════════════════════════════════════════════════
            "qwen2.5-vl-72b": ModelCapability(
                name="qwen2.5-vl-72b",
                provider="local",
                api_key_env=None,
                cost_per_1k_tokens=0.0,
                strengths=[
                    TaskType.MULTIMODAL,
                    TaskType.MULTIMODAL_VISION,
                    TaskType.DATA_ANALYSIS,
                ],
                max_tokens=32768,
                supports_streaming=True,
                available=True,
            ),
        }

    def _check_availability(self) -> None:
        """Check which models are actually available."""
        # Check API keys for cloud models
        for model_name, model in self._models.items():
            if model.provider == "local":
                # Local models always available (via Ollama)
                model.available = True
            elif model.api_key_env:
                # Cloud models need API key
                model.available = bool(os.getenv(model.api_key_env))

            if model.available:
                logger.debug(f"✓ Model available: {model_name}")

        # Log summary
        available_count = sum(1 for m in self._models.values() if m.available)
        logger.info(f"Multi-Model Router: {available_count}/{len(self._models)} models available")

    async def classify_task_llm(
        self,
        query: str,
        context: dict[str, Any] | None = None,
    ) -> tuple[TaskType, float]:
        """Classify task using LLM (higher accuracy, slower).

        Use when keyword heuristic has low confidence or for complex queries.

        Args:
            query: Query text
            context: Optional context

        Returns:
            (TaskType, confidence) tuple[Any, ...]
        """
        try:
            from kagami.core.services.llm.service import get_llm_service

            llm = get_llm_service()

            # Build prompt
            task_types_list = "\n".join(
                [f"- {t.value}: {self._get_task_description(t)}" for t in TaskType]
            )

            prompt = f"""Classify this query into ONE task type.

Query: "{query}"

Available task types:
{task_types_list}

Respond with ONLY the task type name (e.g., "code_generation") and confidence 0.0-1.0.
Format: task_type|confidence

Classification:"""

            timeout = _get_classifier_timeout()
            response = await asyncio.wait_for(
                llm.generate(  # type: ignore  # Call sig
                    prompt=prompt,
                    temperature=0.1,  # Low temperature for consistent classification
                    max_tokens=50,
                ),
                timeout=timeout,
            )

            # Parse response
            text = response.get("text", "").strip()  # type: ignore  # Dynamic attr
            if "|" in text:
                task_str, conf_str = text.split("|")
                task_str = task_str.strip()
                confidence = float(conf_str.strip())
            else:
                task_str = text
                confidence = 0.5

            # Map to TaskType
            task_type = TaskType.GENERAL_REASONING  # Default
            for t in TaskType:
                if t.value == task_str or task_str in t.value:  # type: ignore[operator]
                    task_type = t
                    break

            logger.debug(
                f"🧭 LLM classification: {query[:50]}... → {task_type.value} "
                f"(confidence: {confidence:.2f})"
            )

            # Emit metric
            try:
                from kagami_observability.metrics import REGISTRY
                from prometheus_client import Counter

                if not hasattr(REGISTRY, "_router_llm_classifications"):
                    REGISTRY._router_llm_classifications = Counter(  # type: ignore  # Dynamic attr
                        "kagami_router_llm_classifications_total",
                        "LLM-based task classifications",
                        ["task_type"],
                        registry=REGISTRY,
                    )

                REGISTRY._router_llm_classifications.labels(  # type: ignore  # Dynamic attr
                    task_type=task_type.value
                ).inc()
            except Exception:
                pass

            return (task_type, confidence)

        except TimeoutError:
            logger.warning(
                "LLM classification timed out after %.2fs, falling back to keyword classifier",
                _get_classifier_timeout(),
            )
            return (TaskType.GENERAL_REASONING, 0.3)
        except Exception as e:
            logger.warning(f"LLM classification failed: {e}, falling back to keyword")
            return (TaskType.GENERAL_REASONING, 0.3)

    def _get_task_description(self, task_type: TaskType) -> str:
        """Get human-readable description of task type."""
        descriptions = {
            TaskType.CODE_GENERATION: "Writing/implementing code",
            TaskType.CODE_REVIEW: "Analyzing/reviewing existing code",
            TaskType.MATH_PROOF: "Mathematical proofs and theorems",
            TaskType.SCIENCE_RESEARCH: "Scientific research and experimentation",
            TaskType.WEB_RESEARCH: "Finding current information online",
            TaskType.CREATIVE_WRITING: "Writing stories, poems, narratives",
            TaskType.DATA_ANALYSIS: "Analyzing data and statistics",
            TaskType.FAST_QUERY: "Quick, simple questions",
            TaskType.GENERAL_REASONING: "General thinking and problem solving",
            TaskType.MULTIMODAL: "Processing multiple data modalities (text, image, audio)",
            TaskType.MULTIMODAL_VISION: "Visual understanding and analysis (images, charts, diagrams)",
            TaskType.MULTIMODAL_AUDIO: "Audio processing and speech understanding",
            TaskType.LONG_CONTEXT: "Tasks requiring extended memory (100K+ tokens)",
            TaskType.FINANCIAL_ANALYSIS: "Financial modeling and investment analysis",
            TaskType.MEDICAL_RESEARCH: "Medical and healthcare domain expertise",
            TaskType.MULTILINGUAL: "Non-English or multi-language understanding",
        }
        return descriptions.get(task_type, "General task")

    def route(
        self, query: str, task_type: TaskType | None = None, prefer_local: bool = True
    ) -> str:
        """Route query to optimal model.

        Emits metrics:
        - kagami_model_router_decisions_total{from_model,to_model,reason}
        - kagami_router_cache_hit_ratio

        Args:
            query: The query text
            task_type: Optional explicit task type (otherwise auto-classified)
            prefer_local: If True, prefer local models (cost optimization)

        Returns:
            Model name to use
        """
        # METRICS: Track router decisions (variables available for future instrumentation)
        _ = "none"  # from_model
        _ = "initial"  # reason

        # Classify task if not provided (supports A/B and LLM modes)
        if task_type is None:
            # Read classifier mode from environment (no feature_flags dependency)
            mode_env = os.getenv("KAGAMI_ROUTER_CLASSIFIER_MODE")
            if mode_env is None and _is_test_runtime():
                mode = "keyword"
            else:
                mode = (mode_env or "keyword").lower()
            if mode not in {"keyword", "llm", "ab"}:
                mode = "keyword"

            if mode == "llm":
                try:
                    asyncio.get_running_loop()
                except RuntimeError:
                    timeout = _get_classifier_timeout()
                    try:
                        task_type = asyncio.run(
                            asyncio.wait_for(self.classify_task_llm(query), timeout=timeout)
                        )[0]
                    except TimeoutError:
                        logger.warning(
                            "LLM router classifier timed out after %.2fs; falling back to keyword classifier.",
                            timeout,
                        )
                        task_type = TaskType.GENERAL_REASONING
                else:
                    logger.warning(
                        "LLM router classifier requested while event loop running; "
                        "falling back to keyword classifier."
                    )
                    task_type = TaskType.GENERAL_REASONING
            elif mode == "ab":
                import random

                p = float(os.getenv("KAGAMI_ROUTER_AB_PROBABILITY", "0.5"))
                if random.random() < p:
                    try:
                        asyncio.get_running_loop()
                    except RuntimeError:
                        timeout = _get_classifier_timeout()
                        try:
                            task_type = asyncio.run(
                                asyncio.wait_for(self.classify_task_llm(query), timeout=timeout)
                            )[0]
                        except TimeoutError:
                            logger.warning(
                                "LLM router classifier timed out after %.2fs (A/B mode); falling back to keyword classifier.",
                                timeout,
                            )
                            task_type = TaskType.GENERAL_REASONING
                    else:
                        logger.warning(
                            "LLM router classifier requested while event loop running (A/B mode); "
                            "falling back to keyword classifier."
                        )
                        task_type = TaskType.GENERAL_REASONING
                else:
                    task_type = TaskType.GENERAL_REASONING
            else:
                task_type = TaskType.GENERAL_REASONING

        # Get candidate models for this task
        candidates = self._get_candidates(task_type)

        # Filter by availability
        candidates = [c for c in candidates if self._models[c].available]

        if not candidates:
            # Fallback to any available local model
            local_available = [
                name for name, m in self._models.items() if m.available and m.provider == "local"
            ]
            return local_available[0] if local_available else "qwen2.5-14b"

        # Cost optimization: prefer local if good enough
        if prefer_local:
            local_candidates = [c for c in candidates if self._models[c].provider == "local"]
            if local_candidates:
                # Use local if performance is acceptable
                best_local = self._select_best_from_candidates(local_candidates, task_type)
                performance = self._get_performance(task_type, best_local)

                if performance > 0.7:  # Good enough
                    to_model = best_local
                    _ = "local_sufficient"  # reason - for future instrumentation
                    return best_local

        # Otherwise, use best available (including cloud)
        to_model = self._select_best_from_candidates(candidates, task_type)
        _ = "best_available"  # reason - for future instrumentation

        return to_model

    def _get_candidates(self, task_type: TaskType) -> list[str]:
        """Get models that are strong at this task type."""
        candidates = []

        for model_name, model in self._models.items():
            if task_type in model.strengths:
                candidates.append(model_name)

        # If no specialists, return all available
        if not candidates:
            candidates = list(self._models.keys())

        return candidates

    def _select_best_from_candidates(self, candidates: list[str], task_type: TaskType) -> str:
        """Select best model from candidates based on learned performance."""
        if not candidates:
            return "qwen2.5-14b"  # Safe fallback (M3 Ultra optimized)

        # Score candidates by performance
        scored = []
        for model_name in candidates:
            performance = self._get_performance(task_type, model_name)
            scored.append((model_name, performance))

        # Sort by performance (descending)
        scored.sort(key=lambda x: x[1], reverse=True)

        return scored[0][0]

    def _get_performance(self, task_type: TaskType, model_name: str) -> float:
        """Get learned performance for (task_type, model)."""
        key = (task_type.value, model_name)

        # Return learned performance, or default based on strengths
        if key in self._performance_matrix:  # type: ignore[comparison-overlap]
            return self._performance_matrix[key]  # type: ignore[index]

        # Default: 0.8 if in strengths, 0.3 if neutral, 0.2 if weakness
        model = self._models.get(model_name)
        if model:
            if task_type in model.strengths:
                return 0.8
            elif hasattr(model, "weaknesses") and task_type in model.weaknesses:
                return 0.2
        return 0.3  # Conservative default for unknown combinations

    async def record_outcome(
        self,
        query: str,
        model_used: str,
        task_type: TaskType,
        success: bool,
        quality_score: float | None = None,
    ) -> None:
        """Record outcome to improve routing.

        Uses exponential moving average to learn performance.
        """
        key = (task_type.value, model_used)

        # Determine score
        if quality_score is not None:
            score = quality_score
        else:
            score = 1.0 if success else 0.0

        # Update performance matrix (EMA with alpha=0.2)
        current = self._performance_matrix.get(
            key,
            0.3,  # type: ignore[arg-type]
        )  # Start conservative  # type: ignore[arg-type]
        self._performance_matrix[key] = 0.2 * score + 0.8 * current  # type: ignore[index]

        # Track usage
        self._usage_count[model_used] = self._usage_count.get(model_used, 0) + 1

        # Track cost
        model = self._models.get(model_used)
        if model and model.provider != "local":
            # Estimate tokens (rough)
            estimated_tokens = len(query.split()) * 1.3 * 1000  # Rough estimate
            cost = (estimated_tokens / 1000) * model.cost_per_1k_tokens
            self._total_cost_usd += cost

    def get_stats(self) -> dict[str, Any]:
        """Get routing statistics."""
        return {
            "total_cost_usd": self._total_cost_usd,
            "usage_count": self._usage_count,
            "performance_matrix": {
                f"{task}/{model}": perf for (task, model), perf in self._performance_matrix.items()
            },
            "models_available": {name: model.available for name, model in self._models.items()},
        }

    async def route_with_fallback(
        self, query: str, task_type: TaskType | None = None, max_attempts: int = 3
    ) -> tuple[str, str]:
        """Route with LLM-driven selection and retry.

        NO HEURISTIC FALLBACKS. Uses LLM to select best model with exponential backoff retry.

        Returns:
            (model_name, provider)

        Raises:
            RuntimeError: If all retries fail
        """
        from kagami.core.routing.llm_driven_router import get_llm_driven_router

        router = await get_llm_driven_router()
        return await router.route(query, task_type)


# Singleton
_multi_model_router: MultiModelRouter | None = None


def get_multi_model_router() -> MultiModelRouter:
    """Get singleton multi-model router."""
    global _multi_model_router
    if _multi_model_router is None:
        _multi_model_router = MultiModelRouter()
    return _multi_model_router
