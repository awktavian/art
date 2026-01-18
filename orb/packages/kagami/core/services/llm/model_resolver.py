"""Centralized model/provider resolution for all LLM and image backends.

Removes hardcoded provider/model logic from scattered call sites and unifies
selection based on environment, configuration, task hints, and budgets.

This module is deliberately dependency-light and should not import heavy LLM
clients. It returns selection metadata (provider, model_name, base_url, etc.).
"""

import asyncio
from typing import Any

# Import shared types to break circular dependency
from kagami.core.services.llm.types import ModelSelection

_psutil: Any | None = None
try:
    import psutil as _psutil
except Exception:
    _psutil = None
_PSUTIL_AVAILABLE = _psutil is not None
_requests: Any | None = None
try:
    import httpx as _requests
except Exception:
    _requests = None
_REQUESTS_AVAILABLE = _requests is not None
from kagami_observability.metrics import REGISTRY

from kagami.core.config import get_config

try:
    from prometheus_client import Counter

    LLM_SELECTIONS: Any | None = Counter(
        "kagami_llm_selections",
        "Resolved LLM model selections",
        ["source", "provider", "model", "heavy"],
        registry=REGISTRY,
    )
except Exception:
    LLM_SELECTIONS = None


def _normalize_model_name(name: str | None) -> str | None:
    """Normalize common aliasing for internal model identifiers.

    - Unify "gpt-oss:20b" vs "gpt-oss-20b"
    - Preserve vendor-prefixed names (e.g., qwen3:7b) as-is
    """
    if not name:
        return name
    if name.startswith("gpt-oss:"):
        return name.replace(":", "-")
    return name


def resolve_text_model(
    *, task_type: Any | None = None, prompt_length: int = 0, hints: dict[str, Any] | None = None
) -> ModelSelection:
    """Resolve optimal LOCAL transformers model (HF cache) for text generation.

    M3 ULTRA 512GB FLAGSHIP DEFAULTS - QWEN3 SERIES (2025 OPTIMAL):
    - KAGAMI_TRANSFORMERS_MODEL_FLAGSHIP (default Qwen/Qwen3-Coder-30B-A3B-Instruct)
    - KAGAMI_TRANSFORMERS_MODEL_CODER (default Qwen/Qwen3-Coder-30B-A3B-Instruct)
    - KAGAMI_TRANSFORMERS_MODEL_REASONING (default Qwen/Qwen3-Coder-30B-A3B-Instruct)
    - KAGAMI_TRANSFORMERS_MODEL_VISION (default Qwen/Qwen3-VL-14B)
    - KAGAMI_TRANSFORMERS_MODEL_FAST (default Qwen/Qwen3-14B)

    Uses strategy chain pattern for clean resolution logic.
    """
    from kagami.core.services.llm.resolution_strategies import ResolutionChain

    hints = hints or {}
    chain = ResolutionChain()
    selection = chain.resolve(task_type=task_type, prompt_length=prompt_length, hints=hints)

    # Determine source label for metrics
    source = _determine_source_label(selection, hints)
    _record_selection(source, selection)
    return selection


def _determine_source_label(selection: ModelSelection, hints: dict[str, Any]) -> str:
    """Determine metric source label based on selection characteristics."""
    if selection.provider == "api":
        return _api_source_label(selection, hints)
    if selection.provider == "gemini":
        return _gemini_source_label(hints)
    if selection.provider == "local":
        return _local_source_label(selection)
    return "unknown"


def _api_source_label(selection: ModelSelection, hints: dict[str, Any]) -> str:
    """Determine API provider source label."""
    model_lower = selection.model_name.lower()
    if "deepseek" in model_lower or "openai_compat" in str(hints.get("provider", "")):
        return "explicit_openai_compat"
    if "gpt-oss" in model_lower:
        return "gpt_oss_api"
    if "gpt" in model_lower:
        return "openai"
    return "api"


def _gemini_source_label(hints: dict[str, Any]) -> str:
    """Determine Gemini source label."""
    return "explicit_gemini" if hints.get("provider") == "gemini" else "gemini"


def _local_source_label(selection: ModelSelection) -> str:
    """Determine local model source label."""
    model_lower = selection.model_name.lower()
    if "tiny" in model_lower or "gpt2" in model_lower:
        return "test_mode_lightweight"
    if "vision" in model_lower or "vl" in model_lower:
        return "local_transformers_vision"
    if "coder" in model_lower:
        return "local_transformers_code"
    if "reasoning" in model_lower:
        return "local_transformers_reasoning"
    if "flagship" in model_lower:
        return "local_transformers_flagship"
    if not selection.is_heavy:
        return "local_transformers_fast"
    return "local_transformers_default"


def _estimate_device_tier() -> str:
    """Estimate device capability tier from memory and cores."""
    try:
        mem_gb = (
            _psutil.virtual_memory().total / 1024**3
            if _PSUTIL_AVAILABLE and _psutil is not None
            else 8.0
        )
    except Exception:
        mem_gb = 8.0
    try:
        cores = _psutil.cpu_count(logical=True) if _PSUTIL_AVAILABLE and _psutil is not None else 8
    except Exception:
        cores = 8
    if mem_gb >= 256 and cores >= 16:
        return "datacenter"
    if mem_gb >= 64 and cores >= 16:
        return "huge"
    if mem_gb >= 32 and cores >= 12:
        return "large"
    if mem_gb >= 16 and cores >= 8:
        return "medium"
    if mem_gb >= 8:
        return "fast"
    return "tiny"


async def recommend_local_tiers(*, hints: dict[str, Any] | None = None) -> dict[str, str]:
    """Return a recommended mapping of tiers → model names based on installed models and device.

    Tiers (Dec 2024 - M3 Ultra 512GB Optimized):
    - tiny: Instant response (<1s)
    - fast: Quick tasks (~2s)
    - medium: Balanced quality/speed
    - large: High quality
    - huge: Maximum quality (flagship)
    - datacenter: Same as huge for consumer hardware
    """
    hints = hints or {}
    base_url = get_config("OLLAMA_HOST") or get_config("OLLAMA_URL") or "http://localhost:11434"
    installed = set()  # Ollama models no longer fetched
    candidates = {
        "tiny": ["qwen2.5:0.5b", "qwen2.5:1.5b"],
        "fast": ["qwen2.5:7b", "qwen2.5:3b"],
        "medium": ["qwen2.5:14b", "qwen2.5-coder:14b"],
        "large": ["qwen2.5-coder:32b", "qwen2.5:32b", "deepseek-r1:32b"],
        "huge": ["qwen2.5:72b", "deepseek-r1:70b", "qwen2.5-coder:32b", "llama3.3:70b"],
        "datacenter": ["qwen2.5:72b", "deepseek-r1:70b", "qwen2.5-coder:32b", "llama3.3:70b"],
    }

    # OPTIMIZATION: Make HTTP requests async to avoid blocking
    import aiohttp

    async def check_model_async(model_name: str) -> bool:
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=0.5)) as session:
                async with session.get(
                    f"{base_url}/api/show", params={"name": model_name}
                ) as response:
                    return response.status == 200
        except Exception:
            return False

    # Run checks in parallel for all models
    all_models = set()
    for opts in candidates.values():
        all_models.update(opts)

    tasks = [check_model_async(m) for m in all_models]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    for m, result in zip(all_models, results, strict=False):
        if isinstance(result, bool) and result:
            installed.add(m)

    selection: dict[str, str] = {}
    for tier, opts in candidates.items():
        pick = next((m for m in opts if m in installed), None)
        if pick:
            selection[tier] = pick
    device_tier = _estimate_device_tier()
    order = ["tiny", "fast", "medium", "large", "huge"]
    max_idx = order.index(device_tier)
    for t in list(selection.keys()):
        if order.index(t) > max_idx:
            selection[t] = selection.get(order[max_idx], selection[t])
    return selection


def _record_selection(source: str, selection: ModelSelection) -> None:
    try:
        if LLM_SELECTIONS is not None:
            LLM_SELECTIONS.labels(
                source=source,
                provider=selection.provider,
                model=selection.model_name,
                heavy=str(bool(selection.is_heavy)).lower(),
            ).inc()
    except Exception:
        pass
