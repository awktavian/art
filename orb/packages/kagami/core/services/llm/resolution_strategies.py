"""Resolution strategies for LLM model selection.

Extracted from model_resolver.py to reduce cyclomatic complexity.
Each strategy encapsulates a single resolution concern.

MODEL TIERS (Dec 2024 - M3 Ultra 512GB Optimized):
=================================================
- Instant: Qwen2.5-0.5B (sub-second)
- Fast: Qwen2.5-7B (general quick tasks)
- Standard: Qwen2.5-14B (balanced)
- Flagship: Qwen2.5-72B or Qwen2.5-Coder-32B
- Reasoning: DeepSeek-R1-70B (chain-of-thought)
- Cloud: DeepSeek V3 (best value API)
"""

import os
from abc import ABC, abstractmethod
from typing import Any

from kagami.core.config import get_bool_config, get_config
from kagami.core.services.llm.types import ModelSelection

# Model defaults for M3 Ultra 512GB
# These are dynamically resolved - see _get_cached_or_default()
DEFAULT_FAST = "Qwen/Qwen2.5-0.5B-Instruct"
DEFAULT_STANDARD = "Qwen/Qwen2.5-14B-Instruct"
DEFAULT_FLAGSHIP = "Qwen/Qwen2.5-72B-Instruct"
DEFAULT_CODER = "Qwen/Qwen2.5-Coder-32B-Instruct"
DEFAULT_REASONING = "deepseek-ai/DeepSeek-R1-Distill-Qwen-70B"
DEFAULT_VISION = "Qwen/Qwen2-VL-72B-Instruct"
DEFAULT_DEEPSEEK = "deepseek-chat"  # V3 model via API

# Fallback chains when preferred model isn't cached
# Order: preferred → actually_cached → smaller_fallback
FALLBACK_CHAINS = {
    "flagship": [
        "Qwen/Qwen2.5-72B-Instruct",  # Optimal (not cached)
        "Qwen/Qwen3-Coder-30B-A3B-Instruct",  # ✅ CACHED - 56.9GB
        "Qwen/Qwen2.5-14B-Instruct",  # ✅ CACHED - 27.5GB
    ],
    "coder": [
        "Qwen/Qwen2.5-Coder-32B-Instruct",  # Optimal (not cached)
        "Qwen/Qwen3-Coder-30B-A3B-Instruct",  # ✅ CACHED - 56.9GB (best coder!)
        "Qwen/Qwen2.5-14B-Instruct",  # ✅ CACHED - 27.5GB
    ],
    "reasoning": [
        "deepseek-ai/DeepSeek-R1-Distill-Qwen-70B",  # Optimal (not cached)
        "Qwen/Qwen3-Coder-30B-A3B-Instruct",  # ✅ CACHED - good for reasoning
        "Qwen/Qwen3-14B",  # ✅ CACHED - 27.5GB
        "Qwen/Qwen2.5-14B-Instruct",  # ✅ CACHED - 27.5GB
    ],
    "vision": [
        "Qwen/Qwen2-VL-72B-Instruct",  # Optimal (not cached)
        "Qwen/Qwen2.5-VL-7B-Instruct",  # Not cached
        "Qwen/Qwen2.5-14B-Instruct",  # ✅ CACHED - fallback to text
    ],
    "standard": [
        "Qwen/Qwen2.5-14B-Instruct",  # ✅ CACHED - 27.5GB
        "Qwen/Qwen2.5-7B-Instruct",  # ✅ CACHED - 14.2GB
        "Qwen/Qwen3-14B",  # ✅ CACHED - 27.5GB
    ],
    "fast": [
        "Qwen/Qwen2.5-0.5B-Instruct",  # ✅ CACHED - 0.9GB (instant)
        "Qwen/Qwen3-0.6B",  # ✅ CACHED - 1.4GB
        "Qwen/Qwen3-1.7B",  # ✅ CACHED - 3.8GB
        "Qwen/Qwen2.5-7B-Instruct",  # ✅ CACHED - 14.2GB
    ],
}


def _get_cached_or_default(tier: str, env_var: str, default: str) -> str:
    """Get model from env, or find first cached model in fallback chain.

    This ensures we always use an actually-cached model when possible.
    """
    # Check explicit env override first
    explicit = os.getenv(env_var)
    if explicit:
        return explicit

    # Try fallback chain
    try:
        from kagami.core.services.llm.cached_model_resolver import validate_model_exists

        chain = FALLBACK_CHAINS.get(tier, [default])
        for model in chain:
            if validate_model_exists(model):
                return model
    except ImportError:
        pass

    return default


def _normalize_model_name(name: str | None) -> str | None:
    """Normalize common aliasing for internal model identifiers.

    Converts "gpt-oss:" prefix format to "gpt-oss-" format for consistency.

    Args:
        name: Model name string to normalize

    Returns:
        Normalized model name, or None if input is None

    Examples:
        >>> _normalize_model_name("gpt-oss:120b")
        "gpt-oss-120b"
        >>> _normalize_model_name("Qwen/Qwen2.5-14B")
        "Qwen/Qwen2.5-14B"
    """
    if not name:
        return name
    if name.startswith("gpt-oss:"):
        return name.replace(":", "-")
    return name


def compute_is_heavy(*, task_type: Any | None, prompt_length: int, hints: dict[str, Any]) -> bool:
    """Compute is_heavy flag based on task type, prompt length, and hints.

    Determines whether to use a heavy (powerful) or light (fast) model based on:
    - Task type (reasoning/planning are heavy)
    - Prompt length (long prompts require heavy models)
    - Budget constraints (low budget forces light)
    - Token requirements (high token requests require heavy)
    - Speed priority override (forces light)

    Args:
        task_type: Task type enum/string indicating task nature
        prompt_length: Length of input prompt in characters
        hints: Additional hints dictionary with keys:
            - budget_ms: Time budget in milliseconds
            - max_tokens: Maximum tokens to generate
            - speed_priority: Override to force fast model

    Returns:
        True if heavy model should be used, False for light model
    """
    config = _load_heavy_config()
    task_name = _get_task_name(task_type)

    # Base heavy determination
    is_heavy = _is_heavy_task(task_name, prompt_length, config)

    # Apply constraint adjustments
    is_heavy = _apply_budget_constraint(is_heavy, hints, config)
    is_heavy = _apply_token_constraint(is_heavy, hints, config)
    is_heavy = _apply_speed_priority(is_heavy, hints)

    return is_heavy


def _load_heavy_config() -> dict[str, int]:
    """Load configuration thresholds for heavy model selection.

    Environment variables:
        LLM_MAX_PROMPT_LEN_LIGHT: Max prompt length for light models (default: 4000)
        LLM_MIN_BUDGET_MS_HEAVY: Min budget to use heavy models (default: 800)
        LLM_MAX_TOKENS_LIGHT: Max tokens for light models (default: 4000)

    Returns:
        Dictionary with keys: max_len_for_light, min_budget_for_heavy, max_tokens_for_light
    """
    try:
        max_len_for_light = int(get_config("LLM_MAX_PROMPT_LEN_LIGHT") or 4000)
    except Exception:
        max_len_for_light = 4000

    try:
        min_budget_for_heavy = int(get_config("LLM_MIN_BUDGET_MS_HEAVY") or 800)
    except Exception:
        min_budget_for_heavy = 800

    try:
        max_tokens_for_light = int(get_config("LLM_MAX_TOKENS_LIGHT") or 4000)
    except Exception:
        max_tokens_for_light = 4000

    return {
        "max_len_for_light": max_len_for_light,
        "min_budget_for_heavy": min_budget_for_heavy,
        "max_tokens_for_light": max_tokens_for_light,
    }


def _get_task_name(task_type: Any | None) -> str:
    """Extract task name from task_type.

    Args:
        task_type: Task type object (enum or string)

    Returns:
        Uppercase task name string, or "UNKNOWN" if None
    """
    return getattr(task_type, "name", str(task_type)).upper() if task_type else "UNKNOWN"


def _is_heavy_task(task_name: str, prompt_length: int, config: dict[str, int]) -> bool:
    """Determine if task is heavy based on task type or prompt length.

    Args:
        task_name: Uppercase task type name
        prompt_length: Input prompt length in characters
        config: Configuration dictionary from _load_heavy_config

    Returns:
        True if task requires heavy model due to type or length
    """
    heavy_task_types = {"REASONING", "PLANNING", "SYNTHESIS", "ANALYSIS", "OPTIMIZATION"}
    return task_name in heavy_task_types or prompt_length > config["max_len_for_light"]


def _apply_budget_constraint(is_heavy: bool, hints: dict[str, Any], config: dict[str, int]) -> bool:
    """Apply budget constraint to is_heavy determination.

    Forces light model if budget is below threshold, even if task would prefer heavy.

    Args:
        is_heavy: Current heavy determination
        hints: Hints dictionary with optional budget_ms key
        config: Configuration dictionary with min_budget_for_heavy threshold

    Returns:
        False if budget too low, otherwise original is_heavy value
    """
    budget_ms = 0
    try:
        budget_ms = int(hints.get("budget_ms", 0) or 0)
    except Exception:
        budget_ms = 0

    if budget_ms and budget_ms < config["min_budget_for_heavy"]:
        return False
    return is_heavy


def _apply_token_constraint(is_heavy: bool, hints: dict[str, Any], config: dict[str, int]) -> bool:
    """Apply token constraint to is_heavy determination.

    Forces heavy model if requested tokens exceed light model capacity.

    Args:
        is_heavy: Current heavy determination
        hints: Hints dictionary with optional max_tokens key
        config: Configuration dictionary with max_tokens_for_light threshold

    Returns:
        True if tokens exceed light capacity, otherwise original is_heavy value
    """
    requested_tokens = 0
    try:
        requested_tokens = int(hints.get("max_tokens", 0) or 0)
    except Exception:
        requested_tokens = 0

    if requested_tokens and requested_tokens > config["max_tokens_for_light"]:
        return True
    return is_heavy


def _apply_speed_priority(is_heavy: bool, hints: dict[str, Any]) -> bool:
    """Apply speed priority override to is_heavy determination.

    Forces light model if speed_priority hint is enabled.

    Args:
        is_heavy: Current heavy determination
        hints: Hints dictionary with optional speed_priority key

    Returns:
        False if speed_priority is truthy, otherwise original is_heavy value
    """
    if str(hints.get("speed_priority", "")).lower() in {"1", "true", "yes", "on"}:
        return False
    return is_heavy


class ResolutionStrategy(ABC):
    """Base class for model resolution strategies.

    Strategies form a chain of responsibility pattern. Each strategy checks if it
    can handle the request, and if so, resolves to a specific model configuration.
    """

    @abstractmethod
    def can_handle(
        self, *, task_type: Any | None, prompt_length: int, hints: dict[str, Any]
    ) -> bool:
        """Check if this strategy can handle the given inputs.

        Args:
            task_type: Task type enum/string
            prompt_length: Input prompt length in characters
            hints: Additional hints dictionary

        Returns:
            True if this strategy should be applied
        """
        ...

    @abstractmethod
    def resolve(
        self, *, task_type: Any | None, prompt_length: int, hints: dict[str, Any]
    ) -> ModelSelection | None:
        """Resolve to a ModelSelection, or None if cannot handle.

        Args:
            task_type: Task type enum/string
            prompt_length: Input prompt length in characters
            hints: Additional hints dictionary

        Returns:
            ModelSelection object with provider/model config, or None
        """
        ...


class DeepSeekCloudStrategy(ResolutionStrategy):
    """Handle DeepSeek Cloud API requests (highest priority for cloud).

    Use when: DEEPSEEK_API_KEY is set[Any] OR provider=deepseek
    DeepSeek V3 (Dec 2024): Best value, MIT licensed, 671B MoE

    Environment variables:
        - DEEPSEEK_API_KEY: Required for API access
        - DEEPSEEK_MODEL: Model name (default: deepseek-chat = V3)
    """

    def can_handle(
        self, *, task_type: Any | None, prompt_length: int, hints: dict[str, Any]
    ) -> bool:
        explicit_provider = hints.get("provider") or os.getenv("KAGAMI_LLM_PROVIDER")
        has_key = bool(os.getenv("DEEPSEEK_API_KEY"))
        # Only handle if explicitly requesting deepseek, or if key is set and no other provider specified
        return explicit_provider == "deepseek" or (
            has_key
            and explicit_provider
            not in {"local", "transformers", "gemini", "api", "openai_compat", "vllm", "sglang"}
        )

    def resolve(
        self, *, task_type: Any | None, prompt_length: int, hints: dict[str, Any]
    ) -> ModelSelection | None:
        if not os.getenv("DEEPSEEK_API_KEY"):
            return None

        # Select model based on task
        task_name = getattr(task_type, "name", str(task_type)).upper() if task_type else "UNKNOWN"
        model = DEFAULT_DEEPSEEK

        if task_name in ("CODE_GENERATION", "CODE", "EXECUTION"):
            model = "deepseek-coder"

        return ModelSelection(
            provider="deepseek",
            model_name=hints.get("model") or os.getenv("DEEPSEEK_MODEL", model),  # type: ignore[arg-type]
            base_url="https://api.deepseek.com",
            is_heavy=True,
        )


class ExplicitAPIStrategy(ResolutionStrategy):
    """Handle explicit OpenAI-compatible API provider requests.

    Use when: provider hint or KAGAMI_LLM_PROVIDER explicitly requests API service
    Environment variables:
        - KAGAMI_LLM_PROVIDER: Provider type (api/openai_compat/vllm/sglang)
        - KAGAMI_LLM_API_BASE_URL: API endpoint URL
        - KAGAMI_LLM_API_MODEL: Model identifier
    """

    def can_handle(
        self, *, task_type: Any | None, prompt_length: int, hints: dict[str, Any]
    ) -> bool:
        explicit_provider = hints.get("provider") or os.getenv("KAGAMI_LLM_PROVIDER")
        return explicit_provider in {"api", "openai_compat", "openai-compatible", "vllm", "sglang"}

    def resolve(
        self, *, task_type: Any | None, prompt_length: int, hints: dict[str, Any]
    ) -> ModelSelection | None:
        api_base = (
            os.getenv("KAGAMI_LLM_API_BASE_URL")
            or os.getenv("OPENAI_API_BASE")
            or os.getenv("OPENAI_API_BASE_URL")
        )
        if api_base:
            api_model = _normalize_model_name(
                str(
                    hints.get("model")
                    or os.getenv("KAGAMI_LLM_API_MODEL")
                    or "deepseek-ai/DeepSeek-V3"  # Updated to V3
                )
            )
            return ModelSelection(
                provider="api",
                model_name=str(api_model or "deepseek-ai/DeepSeek-V3"),
                base_url=api_base,
                is_heavy=True,
            )
        return None


class TestModeStrategy(ResolutionStrategy):
    """Handle test mode with lightweight models.

    Use when: Running in test/CI environment (KAGAMI_TEST_MODE=1 or pytest detected)
    Returns: sshleifer/tiny-gpt2 or KAGAMI_TRANSFORMERS_MODEL_DEFAULT for fast tests
    """

    def can_handle(
        self, *, task_type: Any | None, prompt_length: int, hints: dict[str, Any]
    ) -> bool:
        # Only when not explicitly forcing API provider
        explicit_provider = hints.get("provider") or os.getenv("KAGAMI_LLM_PROVIDER")
        if explicit_provider in {"api", "openai_compat", "openai-compatible", "vllm", "sglang"}:
            return False
        return (
            os.getenv("KAGAMI_TEST_MODE") == "1"
            or os.getenv("PYTEST_RUNNING") == "1"
            or "PYTEST_CURRENT_TEST" in os.environ
        )

    def resolve(
        self, *, task_type: Any | None, prompt_length: int, hints: dict[str, Any]
    ) -> ModelSelection | None:
        test_model = os.getenv("KAGAMI_TRANSFORMERS_MODEL_DEFAULT", "sshleifer/tiny-gpt2")
        return ModelSelection(provider="local", model_name=test_model, is_heavy=False)


class ExplicitGeminiStrategy(ResolutionStrategy):
    """Handle explicit Gemini provider requests.

    Use when: provider=gemini explicitly set[Any] AND GOOGLE_API_KEY available
    Environment variables:
        - KAGAMI_LLM_PROVIDER: Must be "gemini"
        - GOOGLE_API_KEY: Required for authentication
        - KAGAMI_GEMINI_MODEL: Model name (default: gemini-3-pro-preview)
    """

    def can_handle(
        self, *, task_type: Any | None, prompt_length: int, hints: dict[str, Any]
    ) -> bool:
        explicit_provider = hints.get("provider") or os.getenv("KAGAMI_LLM_PROVIDER")
        return explicit_provider == "gemini" and bool(os.getenv("GOOGLE_API_KEY"))

    def resolve(
        self, *, task_type: Any | None, prompt_length: int, hints: dict[str, Any]
    ) -> ModelSelection | None:
        return ModelSelection(
            provider="gemini",
            model_name=os.getenv("KAGAMI_GEMINI_MODEL", "gemini-3-pro-preview"),
            is_heavy=True,
        )


class VisionMultiModalStrategy(ResolutionStrategy):
    """Handle vision/multi-modal model requests.

    Use when: hints["multi_modal"] = True (image/video processing required)
    Returns: Best available vision model from cache
    """

    def can_handle(
        self, *, task_type: Any | None, prompt_length: int, hints: dict[str, Any]
    ) -> bool:
        return hints.get("multi_modal", False)  # type: ignore[no-any-return]

    def resolve(
        self, *, task_type: Any | None, prompt_length: int, hints: dict[str, Any]
    ) -> ModelSelection | None:
        vision = _get_cached_or_default(
            "vision", "KAGAMI_TRANSFORMERS_MODEL_VISION", DEFAULT_VISION
        )
        return ModelSelection(provider="local", model_name=vision, is_heavy=True)


class TaskTypeCodeStrategy(ResolutionStrategy):
    """Handle code generation task types.

    Use when: task_type in (CODE_GENERATION, EXECUTION, CODE, SYNTHESIS)
    Returns: Best available coder model from cache
    """

    def can_handle(
        self, *, task_type: Any | None, prompt_length: int, hints: dict[str, Any]
    ) -> bool:
        task_name = getattr(task_type, "name", str(task_type)).upper() if task_type else "UNKNOWN"
        return task_name in ("CODE_GENERATION", "EXECUTION", "CODE", "SYNTHESIS")

    def resolve(
        self, *, task_type: Any | None, prompt_length: int, hints: dict[str, Any]
    ) -> ModelSelection | None:
        coder = _get_cached_or_default("coder", "KAGAMI_TRANSFORMERS_MODEL_CODER", DEFAULT_CODER)
        return ModelSelection(provider="local", model_name=coder, is_heavy=True)


class TaskTypeReasoningStrategy(ResolutionStrategy):
    """Handle reasoning/planning task types.

    Use when: task_type in (REASONING, PLANNING, OPTIMIZATION, ANALYSIS, MATH_PROOF)
    Returns: Best available reasoning model from cache (prefers DeepSeek-R1)
    """

    def can_handle(
        self, *, task_type: Any | None, prompt_length: int, hints: dict[str, Any]
    ) -> bool:
        task_name = getattr(task_type, "name", str(task_type)).upper() if task_type else "UNKNOWN"
        return task_name in ("REASONING", "PLANNING", "OPTIMIZATION", "ANALYSIS", "MATH_PROOF")

    def resolve(
        self, *, task_type: Any | None, prompt_length: int, hints: dict[str, Any]
    ) -> ModelSelection | None:
        reasoning = _get_cached_or_default(
            "reasoning", "KAGAMI_TRANSFORMERS_MODEL_REASONING", DEFAULT_REASONING
        )
        return ModelSelection(provider="local", model_name=reasoning, is_heavy=True)


class LongPromptStrategy(ResolutionStrategy):
    """Handle long prompt lengths with flagship models.

    Use when: prompt_length > KAGAMI_LONG_PROMPT_THRESHOLD (default: 4000)
    Returns: Best available flagship model from cache
    """

    def can_handle(
        self, *, task_type: Any | None, prompt_length: int, hints: dict[str, Any]
    ) -> bool:
        threshold = int(os.getenv("KAGAMI_LONG_PROMPT_THRESHOLD", "4000"))
        return prompt_length > threshold

    def resolve(
        self, *, task_type: Any | None, prompt_length: int, hints: dict[str, Any]
    ) -> ModelSelection | None:
        flagship = _get_cached_or_default(
            "flagship", "KAGAMI_TRANSFORMERS_MODEL_FLAGSHIP", DEFAULT_FLAGSHIP
        )
        return ModelSelection(provider="local", model_name=flagship, is_heavy=True)


class PreferThinkingStrategy(ResolutionStrategy):
    """Handle prefer_thinking hint with reasoning model.

    Use when: Heavy task type OR prefer_thinking=true AND budget >= 1500ms
    Returns: Best available reasoning model from cache
    """

    def can_handle(
        self, *, task_type: Any | None, prompt_length: int, hints: dict[str, Any]
    ) -> bool:
        task_name = getattr(task_type, "name", str(task_type)).upper() if task_type else "UNKNOWN"
        heavy_task_types = {
            "REASONING",
            "PLANNING",
            "SYNTHESIS",
            "ANALYSIS",
            "OPTIMIZATION",
            "MATH_PROOF",
        }
        prefer_thinking = task_name in heavy_task_types or str(
            hints.get("prefer_thinking", "")
        ).lower() in {"1", "true", "yes", "on"}

        budget_ms = 0
        try:
            budget_ms = int(hints.get("budget_ms", 0) or 0)
        except Exception:
            budget_ms = 0

        return prefer_thinking and budget_ms >= 1500

    def resolve(
        self, *, task_type: Any | None, prompt_length: int, hints: dict[str, Any]
    ) -> ModelSelection | None:
        r1 = _get_cached_or_default(
            "reasoning", "KAGAMI_TRANSFORMERS_MODEL_REASONING", DEFAULT_REASONING
        )
        return ModelSelection(provider="local", model_name=r1, is_heavy=True)


class CloudAPIFallbackStrategy(ResolutionStrategy):
    """Fallback to cloud APIs when not prefer_local_only.

    Priority (Dec 2024):
    1. DeepSeek V3 (best value: $0.14/1M tokens)
    2. Gemini 2.0 Pro (1M context)
    3. GPT-4o (fallback)
    """

    def can_handle(
        self, *, task_type: Any | None, prompt_length: int, hints: dict[str, Any]
    ) -> bool:
        prefer_local_only = (
            get_bool_config("KAGAMI_LLM_PREFER_LOCAL", True)
            and (not os.getenv("DEEPSEEK_API_KEY"))
            and (not os.getenv("OPENAI_API_KEY"))
            and (not os.getenv("GOOGLE_API_KEY"))
        )
        return not prefer_local_only

    def resolve(
        self, *, task_type: Any | None, prompt_length: int, hints: dict[str, Any]
    ) -> ModelSelection | None:
        is_heavy = compute_is_heavy(task_type=task_type, prompt_length=prompt_length, hints=hints)

        # Priority 1: DeepSeek V3 (best value)
        if os.getenv("DEEPSEEK_API_KEY"):
            return ModelSelection(
                provider="deepseek",
                model_name=DEFAULT_DEEPSEEK,
                base_url="https://api.deepseek.com",
                is_heavy=is_heavy,
            )

        # Priority 2: Gemini (1M context)
        if os.getenv("GOOGLE_API_KEY"):
            return ModelSelection(
                provider="gemini",
                model_name=os.getenv("KAGAMI_GEMINI_MODEL", "gemini-2.0-pro"),
                is_heavy=is_heavy,
            )

        # Priority 3: OpenAI GPT-4o
        if os.getenv("OPENAI_API_KEY"):
            return ModelSelection(
                provider="api",
                model_name="gpt-4o",
                base_url=os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1"),
                is_heavy=is_heavy,
            )

        return None


class LocalTransformersDefaultStrategy(ResolutionStrategy):
    """Final fallback to local transformers models.

    Use when: No other strategy matches (always returns True)
    Uses cached model fallback chains for guaranteed availability.
    """

    def can_handle(
        self, *, task_type: Any | None, prompt_length: int, hints: dict[str, Any]
    ) -> bool:
        """Always can handle as final fallback."""
        return True

    def resolve(
        self, *, task_type: Any | None, prompt_length: int, hints: dict[str, Any]
    ) -> ModelSelection | None:
        is_heavy = compute_is_heavy(task_type=task_type, prompt_length=prompt_length, hints=hints)

        # Use cached model fallback chains
        fast = _get_cached_or_default("fast", "KAGAMI_TRANSFORMERS_MODEL_FAST", DEFAULT_FAST)
        default = _get_cached_or_default(
            "standard",
            "KAGAMI_TRANSFORMERS_MODEL_DEFAULT",
            os.getenv("KAGAMI_BASE_MODEL", DEFAULT_STANDARD),
        )

        if not is_heavy:
            return ModelSelection(provider="local", model_name=fast, is_heavy=False)
        return ModelSelection(provider="local", model_name=default, is_heavy=True)


class ResolutionChain:
    """Chain of responsibility for model resolution strategies.

    Executes strategies in priority order until one returns a ModelSelection.
    Default order (highest to lowest priority):
        1. ExplicitAPI - User explicitly requested API
        2. TestMode - CI/test environment
        3. ExplicitGemini - User explicitly requested Gemini
        4. VisionMultiModal - Multi-modal input detected
        5. TaskTypeCode - Code generation task
        6. TaskTypeReasoning - Reasoning/planning task
        7. LongPrompt - Very long input
        8. PreferThinking - Thinking preference with budget
        9. CloudAPIFallback - Cloud APIs if available
        10. LocalTransformersDefault - Final fallback (always matches)
    """

    def __init__(self, strategies: list[ResolutionStrategy] | None = None):
        """Initialize with ordered list[Any] of strategies.

        Args:
            strategies: Custom strategy list[Any], or None for defaults
        """
        self.strategies = strategies or self._default_strategies()

    def _default_strategies(self) -> list[ResolutionStrategy]:
        """Return default strategy chain in priority order.

        Priority (Dec 2024 - M3 Ultra 512GB optimized):
        1. DeepSeek Cloud (if API key set[Any]) - Best value API
        2. Explicit API (vLLM/SGLang/etc.)
        3. Test mode (lightweight for CI)
        4. Gemini (if explicitly requested)
        5. Vision/Multimodal tasks
        6. Code generation → Qwen2.5-Coder-32B
        7. Reasoning tasks → DeepSeek-R1-70B
        8. Long prompts → Qwen2.5-72B
        9. Prefer thinking → DeepSeek-R1-70B
        10. Cloud fallback (Gemini/OpenAI if keys present)
        11. Local transformers (always available)
        """
        return [
            DeepSeekCloudStrategy(),  # Best value cloud API
            ExplicitAPIStrategy(),
            TestModeStrategy(),
            ExplicitGeminiStrategy(),
            VisionMultiModalStrategy(),
            TaskTypeCodeStrategy(),
            TaskTypeReasoningStrategy(),
            LongPromptStrategy(),
            PreferThinkingStrategy(),
            CloudAPIFallbackStrategy(),
            LocalTransformersDefaultStrategy(),  # Always handles as final fallback
        ]

    def resolve(
        self,
        *,
        task_type: Any | None = None,
        prompt_length: int = 0,
        hints: dict[str, Any] | None = None,
    ) -> ModelSelection:
        """Execute resolution chain, returning first valid selection.

        Iterates strategies in order, calling can_handle() then resolve() on first match.

        Args:
            task_type: Task type enum/string indicating task nature
            prompt_length: Length of input prompt in characters
            hints: Additional resolution hints (provider, budget_ms, etc.)

        Returns:
            ModelSelection object with provider/model/base_url configuration

        Raises:
            RuntimeError: If chain exhausts without selection (should never happen)
        """
        hints = hints or {}

        for strategy in self.strategies:
            if strategy.can_handle(task_type=task_type, prompt_length=prompt_length, hints=hints):
                selection = strategy.resolve(
                    task_type=task_type, prompt_length=prompt_length, hints=hints
                )
                if selection:
                    return selection

        # Should never reach here due to LocalTransformersDefaultStrategy always handling
        raise RuntimeError("Resolution chain exhausted without selection")
