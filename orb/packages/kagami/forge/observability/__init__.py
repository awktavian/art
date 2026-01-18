"""Forge Observability - Metrics and monitoring for Forge operations.

Provides Prometheus metrics following K4 single metrics surface pattern.
All metrics exposed via `/metrics` endpoint.
"""

from kagami.forge.observability.metrics import (
    CACHE_HITS_TOTAL,
    CACHE_MISSES_TOTAL,
    ERRORS_TOTAL,
    GENERATION_DURATION,
    GENERATION_TOTAL,
    GPU_USAGE_PERCENT,
    MEMORY_USAGE_MB,
    QUALITY_SCORE,
    VALIDATION_FAILURES_TOTAL,
)

__all__ = [
    "CACHE_HITS_TOTAL",
    "CACHE_MISSES_TOTAL",
    "ERRORS_TOTAL",
    "GENERATION_DURATION",
    "GENERATION_TOTAL",
    "GPU_USAGE_PERCENT",
    "MEMORY_USAGE_MB",
    "QUALITY_SCORE",
    "VALIDATION_FAILURES_TOTAL",
]
