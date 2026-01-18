"""Cached Model Resolver - Detect and use only locally cached HuggingFace models.

This module ensures K OS only attempts to load models that are already downloaded,
preventing failed network requests and improving startup reliability.

DESIGN PRINCIPLES:
1. Never attempt to download models at runtime
2. Fail fast with clear error messages
3. Provide optimal fallback chains based on available models
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class CachedModel:
    """Represents a locally cached HuggingFace model."""

    name: str  # Full HuggingFace model name (e.g., "Qwen/Qwen3-14B")
    path: Path  # Local cache path
    size_gb: float = 0.0  # Estimated size
    capabilities: list[str] = field(default_factory=list[Any])


# Capability tags for model selection
CAPABILITY_CODER = "coder"
CAPABILITY_INSTRUCT = "instruct"
CAPABILITY_EMBEDDING = "embedding"
CAPABILITY_FAST = "fast"
CAPABILITY_FLAGSHIP = "flagship"
CAPABILITY_VISION = "vision"


def get_hf_cache_dir() -> Path:
    """Get HuggingFace cache directory."""
    # Check environment variable first
    cache_dir = os.getenv("HF_HOME") or os.getenv("HUGGINGFACE_HUB_CACHE")
    if cache_dir:
        return Path(cache_dir) / "hub"

    # Default location
    return Path.home() / ".cache" / "huggingface" / "hub"


def scan_cached_models() -> list[CachedModel]:
    """Scan HuggingFace cache for downloaded models.

    Returns:
        List of CachedModel objects for all locally cached models
    """
    cache_dir = get_hf_cache_dir()

    if not cache_dir.exists():
        logger.warning(f"HuggingFace cache directory not found: {cache_dir}")
        return []

    models: list[CachedModel] = []

    for item in cache_dir.iterdir():
        if not item.is_dir():
            continue

        # Parse model directory name (format: models--org--model-name)
        if not item.name.startswith("models--"):
            continue

        parts = item.name.split("--")
        if len(parts) < 3:
            continue

        org = parts[1]
        model_name = "--".join(parts[2:]).replace("--", "/")
        full_name = f"{org}/{model_name}"

        # Check if model has actual content (snapshots directory with files)
        snapshots_dir = item / "snapshots"
        if not snapshots_dir.exists():
            continue

        # Find the latest snapshot
        snapshot_dirs = [d for d in snapshots_dir.iterdir() if d.is_dir()]
        if not snapshot_dirs:
            continue

        # Estimate size from snapshot
        latest_snapshot = max(snapshot_dirs, key=lambda d: d.stat().st_mtime)
        size_bytes = sum(f.stat().st_size for f in latest_snapshot.rglob("*") if f.is_file())
        size_gb = size_bytes / (1024**3)

        # Determine capabilities
        capabilities = _infer_capabilities(full_name)

        models.append(
            CachedModel(
                name=full_name,
                path=item,
                size_gb=round(size_gb, 2),
                capabilities=capabilities,
            )
        )

    logger.info(f"✅ Found {len(models)} cached HuggingFace models")
    return models


def _infer_capabilities(model_name: str) -> list[str]:
    """Infer model capabilities from its name."""
    name_lower = model_name.lower()
    caps = []

    if "coder" in name_lower or "code" in name_lower:
        caps.append(CAPABILITY_CODER)

    if "instruct" in name_lower or "chat" in name_lower:
        caps.append(CAPABILITY_INSTRUCT)

    if "embedding" in name_lower or "embed" in name_lower:
        caps.append(CAPABILITY_EMBEDDING)

    if any(x in name_lower for x in ["0.5b", "0.6b", "1.5b", "1.7b", "2b"]):
        caps.append(CAPABILITY_FAST)
    elif any(x in name_lower for x in ["7b", "8b", "14b"]):
        caps.append(CAPABILITY_INSTRUCT)
    elif any(x in name_lower for x in ["30b", "32b", "70b", "72b"]):
        caps.append(CAPABILITY_FLAGSHIP)

    if "vl" in name_lower or "vision" in name_lower:
        caps.append(CAPABILITY_VISION)

    return caps


# Global cache of available models
_cached_models: list[CachedModel] | None = None


def get_cached_models(force_rescan: bool = False) -> list[CachedModel]:
    """Get list[Any] of cached models (with caching)."""
    global _cached_models

    if _cached_models is None or force_rescan:
        _cached_models = scan_cached_models()

    return _cached_models


def find_best_model(
    capability: str | None = None,
    prefer_larger: bool = True,
    exclude_patterns: list[str] | None = None,
) -> CachedModel | None:
    """Find the best available cached model matching criteria.

    Args:
        capability: Required capability (e.g., "coder", "fast")
        prefer_larger: If True, prefer larger models when multiple match
        exclude_patterns: List of patterns to exclude from results

    Returns:
        Best matching CachedModel or None
    """
    models = get_cached_models()

    if not models:
        return None

    # Filter by capability
    if capability:
        models = [m for m in models if capability in m.capabilities]

    # Exclude patterns
    if exclude_patterns:
        for pattern in exclude_patterns:
            models = [m for m in models if pattern.lower() not in m.name.lower()]

    if not models:
        return None

    # Sort by size
    models.sort(key=lambda m: m.size_gb, reverse=prefer_larger)

    return models[0]


def get_optimal_model_chain() -> dict[str, str]:
    """Get optimal model selection chain based on cached models.

    Returns:
        Dict mapping use-case to model name (Dec 2024 - M3 Ultra optimized):
        {
            "fast": Smallest Qwen (<2GB) for instant response
            "standard": 14B Instruct model for balanced quality/speed
            "coder": Best coder model (non-MoE for MPS performance)
            "flagship": Largest non-MoE capable model
            "reasoning": Best reasoning model
            "embedding": Sentence transformer for embeddings
        }

    IMPORTANT: MoE models (like Qwen3-Coder-30B-A3B) run at ~1 tok/s on MPS.
    This function excludes MoE models (A3B suffix) for local inference.
    Use vLLM/SGLang for MoE models at reasonable speed.

    Benchmark results (M3 Ultra, Dec 2024):
        - Qwen2.5-0.5B-Instruct: 30.6 tok/s (fast tier)
        - Qwen2.5-14B-Instruct:  12.5 tok/s (standard/coder/flagship)
        - Qwen3-Coder-30B-A3B:    1.2 tok/s (excluded - too slow)
    """
    models = get_cached_models()
    chain: dict[str, str] = {}

    # Find fast model (smallest Qwen, prefer Instruct variants)
    fast_candidates = [
        m
        for m in models
        if "qwen" in m.name.lower()
        and m.size_gb < 5
        and "embedding" not in m.name.lower()
        and "omni" not in m.name.lower()  # Omni models are multimodal, not ideal for fast text
    ]
    # Prefer Instruct variants, then sort by size
    fast_candidates.sort(key=lambda m: (0 if "instruct" in m.name.lower() else 1, m.size_gb))
    if fast_candidates:
        chain["fast"] = fast_candidates[0].name
    else:
        # Fallback to any small model
        small = [m for m in models if m.size_gb < 5 and "embedding" not in m.name.lower()]
        if small:
            chain["fast"] = min(small, key=lambda m: m.size_gb).name

    # Find standard model (prefer 14B Instruct, then largest in 10-30GB range)
    standard_candidates = [
        m
        for m in models
        if "qwen" in m.name.lower()
        and "instruct" in m.name.lower()
        and 10 <= m.size_gb <= 30
        and "embedding" not in m.name.lower()
        and "coder" not in m.name.lower()  # Coder goes to coder tier
    ]
    if standard_candidates:
        # Prefer 14B, then sort by size descending
        standard_candidates.sort(key=lambda m: (0 if "14b" in m.name.lower() else 1, -m.size_gb))
        chain["standard"] = standard_candidates[0].name
    elif "fast" in chain:
        chain["standard"] = chain["fast"]

    # Find coder model
    # IMPORTANT: MoE models (A3B suffix) run ~1 tok/s on MPS. Prefer non-MoE.
    # Benchmark: Qwen3-Coder-30B-A3B = 1.2 tok/s vs Qwen2.5-14B = 12.5 tok/s
    coder_candidates = [
        m
        for m in models
        if "coder" in m.name.lower()
        and "a3b" not in m.name.lower()  # Exclude MoE (A3B = "Activate 3 Billion")
    ]
    if coder_candidates:
        coder_candidates.sort(key=lambda m: m.size_gb, reverse=True)
        chain["coder"] = coder_candidates[0].name
    elif "standard" in chain:
        # Fallback: Use standard model for code (still 12 tok/s)
        chain["coder"] = chain["standard"]

    # Find flagship (largest non-MoE capable model)
    flagship_candidates = [
        m
        for m in models
        if "qwen" in m.name.lower()
        and "embedding" not in m.name.lower()
        and "a3b" not in m.name.lower()  # Exclude MoE
    ]
    if flagship_candidates:
        flagship_candidates.sort(key=lambda m: m.size_gb, reverse=True)
        chain["flagship"] = flagship_candidates[0].name
    elif "standard" in chain:
        chain["flagship"] = chain["standard"]

    # Reasoning model (prefer flagship for quality)
    if "flagship" in chain:
        chain["reasoning"] = chain["flagship"]
    elif "standard" in chain:
        chain["reasoning"] = chain["standard"]

    # Find embedding model
    embed_candidates = [
        m for m in models if "embedding" in m.name.lower() or "sentence" in m.name.lower()
    ]
    if embed_candidates:
        chain["embedding"] = embed_candidates[0].name

    return chain


def validate_model_exists(model_name: str) -> bool:
    """Check if a model is available in the local cache.

    Args:
        model_name: HuggingFace model name (e.g., "Qwen/Qwen3-14B")

    Returns:
        True if model is cached locally
    """
    models = get_cached_models()
    return any(m.name == model_name for m in models)


def get_fallback_model(requested: str) -> str | None:
    """Get a fallback model when requested model is not cached.

    Args:
        requested: Originally requested model name

    Returns:
        Alternative model name or None if no fallback available
    """
    # Determine what type of model was requested
    requested_lower = requested.lower()

    if "coder" in requested_lower:
        best = find_best_model(capability=CAPABILITY_CODER)
        if best:
            return best.name

    if "embed" in requested_lower:
        best = find_best_model(capability=CAPABILITY_EMBEDDING)
        if best:
            return best.name

    # Default: find any Qwen model
    models = get_cached_models()
    qwen_models = [
        m for m in models if "qwen" in m.name.lower() and "embedding" not in m.name.lower()
    ]
    if qwen_models:
        qwen_models.sort(key=lambda m: m.size_gb, reverse=True)
        return qwen_models[0].name

    # Last resort: any model
    if models:
        return models[0].name

    return None


def log_available_models() -> None:
    """Log all available cached models for debugging."""
    models = get_cached_models()

    if not models:
        logger.warning("⚠️ No cached HuggingFace models found!")
        logger.warning(f"   Cache directory: {get_hf_cache_dir()}")
        logger.warning("   Run: huggingface-cli download <model-name> to cache models")
        return

    logger.info("📦 Available cached models:")
    for m in sorted(models, key=lambda x: x.size_gb, reverse=True):
        caps = ", ".join(m.capabilities) if m.capabilities else "general"
        logger.info(f"   {m.name} ({m.size_gb:.1f}GB) [{caps}]")


def get_recommended_env_config() -> dict[str, str]:
    """Generate recommended environment variable configuration based on cached models.

    Returns:
        Dict of environment variable name to recommended value
    """
    chain = get_optimal_model_chain()
    config: dict[str, str] = {}

    if "fast" in chain:
        config["KAGAMI_TRANSFORMERS_MODEL_FAST"] = chain["fast"]
        config["KAGAMI_TRANSFORMERS_MODEL_DEFAULT"] = chain["fast"]

    if "standard" in chain:
        config["KAGAMI_TRANSFORMERS_MODEL_DEFAULT"] = chain["standard"]

    if "coder" in chain:
        config["KAGAMI_TRANSFORMERS_MODEL_CODER"] = chain["coder"]
        config["KAGAMI_BASE_MODEL"] = chain["coder"]

    if "flagship" in chain:
        config["KAGAMI_TRANSFORMERS_MODEL_FLAGSHIP"] = chain["flagship"]
        config["KAGAMI_TRANSFORMERS_MODEL_REASONING"] = chain["flagship"]

    return config


# Auto-configure on import if in non-test mode
def _auto_configure() -> None:
    """Auto-configure environment with cached models if not already set[Any]."""
    if os.getenv("PYTEST_RUNNING") == "1" or os.getenv("KAGAMI_TEST_MODE") == "1":
        return

    # Only auto-configure if KAGAMI_AUTO_DETECT_MODELS is set[Any]
    if os.getenv("KAGAMI_AUTO_DETECT_MODELS", "0") != "1":
        return

    config = get_recommended_env_config()
    for key, value in config.items():
        if not os.getenv(key):
            os.environ[key] = value
            logger.debug(f"Auto-configured {key}={value}")


__all__ = [
    "CAPABILITY_CODER",
    "CAPABILITY_EMBEDDING",
    "CAPABILITY_FAST",
    "CAPABILITY_FLAGSHIP",
    "CAPABILITY_INSTRUCT",
    "CAPABILITY_VISION",
    "CachedModel",
    "find_best_model",
    "get_cached_models",
    "get_fallback_model",
    "get_hf_cache_dir",
    "get_optimal_model_chain",
    "get_recommended_env_config",
    "log_available_models",
    "scan_cached_models",
    "validate_model_exists",
]
