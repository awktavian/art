"""Configuration Management for Forge Matrix.

Handles Forge configuration loading and validation.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def load_forge_config(config: dict[str, Any] | None = None) -> dict[str, Any]:
    """Load and normalize Forge configuration.

    Args:
        config: Optional initial configuration

    Returns:
        Normalized configuration dictionary
    """
    cfg = config or {}

    # Legacy options removed (Dec 2025): fast mode masked missing wiring.
    cfg.pop("fast_mode", None)
    cfg.pop("force_fast_mode", None)

    # UniRig requirement
    if "require_unirig" not in cfg:
        cfg["require_unirig"] = os.getenv("FORGE_REQUIRE_UNIRIG", "1").lower() in (
            "1",
            "true",
            "yes",
            "on",
        )

    # Module defaults
    modules_cfg = cfg.setdefault("modules", {})
    rig_cfg = modules_cfg.setdefault("rigging", {})
    rig_cfg.setdefault("method", "unirig")
    rig_cfg.setdefault("require_real_models", True)

    return cfg


def get_cache_root() -> Path:
    """Get cache directory for Forge assets.

    Returns:
        Path to cache directory
    """
    try:
        from kagami.core.config import get_model_cache_path

        cache_root = get_model_cache_path() / "forge_cache"
    except Exception:
        cache_root = Path.home() / ".cache" / "forge_ai_models" / "forge_cache"

    cache_root.mkdir(parents=True, exist_ok=True)
    return cache_root


__all__ = [
    "get_cache_root",
    "load_forge_config",
]
