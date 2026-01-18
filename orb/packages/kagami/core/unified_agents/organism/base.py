"""Base utilities for organism submodules.

Provides shared constants, lazy imports, and utility functions used across
all organism submodules.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Population limits
DEFAULT_MAX_POPULATION = 100  # Per colony
GLOBAL_MAX_POPULATION = 500  # Total across all colonies


def lazy_import_torch() -> Any:
    """Lazy import torch to avoid blocking module import.

    OPTIMIZATION (Dec 16, 2025): torch import adds 200-1000ms delay.
    Only import when actually needed for organism operations.

    Returns:
        torch module
    """
    import torch

    return torch


__all__ = [
    "DEFAULT_MAX_POPULATION",
    "GLOBAL_MAX_POPULATION",
    "lazy_import_torch",
]
