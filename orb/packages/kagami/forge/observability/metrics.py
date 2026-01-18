"""Forge Prometheus Metrics.

All Forge metrics following K4 observability standards.
Integrated with single `/metrics` endpoint.

CONSOLIDATION (Dec 4, 2025):
===========================
This module is the CANONICAL source for service-level Forge metrics.
Pipeline-level metrics are in kagami_observability/metrics/forge.py.

Re-exports from both locations are provided for convenience.
"""

from kagami_observability.metrics import Counter, Gauge, Histogram

# ==============================================================================
# SERVICE-LEVEL METRICS (defined here)
# ==============================================================================

# Generation metrics
GENERATION_DURATION = Histogram(
    "kagami_forge_generation_duration_seconds",
    "Duration of Forge generation operations",
    ["module", "quality_level"],
)

GENERATION_TOTAL = Counter(
    "kagami_forge_generation_total",
    "Total Forge generation requests",
    ["module", "status"],
)

# Cache metrics
CACHE_HITS_TOTAL = Counter(
    "kagami_forge_cache_hits_total",
    "Total cache hits in Forge operations",
    ["module"],
)

CACHE_MISSES_TOTAL = Counter(
    "kagami_forge_cache_misses_total",
    "Total cache misses in Forge operations",
    ["module"],
)

# Quality metrics
QUALITY_SCORE = Histogram(
    "kagami_forge_quality_score",
    "Quality scores for generated assets",
    ["module", "aspect"],
)

VALIDATION_FAILURES_TOTAL = Counter(
    "kagami_forge_validation_failures_total",
    "Total validation failures",
    ["module", "reason"],
)

# Resource metrics
MEMORY_USAGE_MB = Gauge(
    "kagami_forge_memory_usage_mb",
    "Memory usage in megabytes",
    ["module"],
)

GPU_USAGE_PERCENT = Gauge(
    "kagami_forge_gpu_usage_percent",
    "GPU utilization percentage",
    ["module"],
)

# Error metrics
ERRORS_TOTAL = Counter(
    "kagami_forge_errors_total",
    "Total errors in Forge operations",
    ["module", "error_type"],
)

# Safety metrics
ETHICAL_BLOCKS_TOTAL = Counter(
    "kagami_forge_ethical_blocks_total",
    "Total operations blocked by ethical evaluation",
    ["reason"],
)

THREAT_SCORE = Histogram(
    "kagami_forge_threat_score",
    "Threat assessment scores",
    ["module"],
)

# Idempotency metrics
IDEMPOTENCY_CHECKS_TOTAL = Counter(
    "kagami_forge_idempotency_checks_total",
    "Total idempotency key checks",
    ["result"],  # new|duplicate
)

# ==============================================================================
# PIPELINE-LEVEL METRICS (re-exported from observability)
# ==============================================================================

from kagami_observability.metrics.forge import (
    # Audio2Face
    AUDIO2FACE_ANIMATION_LATENCY_MS,
    AUDIO2FACE_ANIMATIONS,
    EMBODIED_PLAN_GENERATIONS,
    FORGE_GENERATIONS,
    # Pipeline
    FORGE_STAGE_DURATION_MS,
    # GenUI
    GENUI_VALIDATE_FAILURES,
    # Motion
    MOTION_GENERATION_LATENCY_MS,
    MOTION_GENERATIONS,
    # Style
    STYLE_REGENERATIONS,
    STYLE_VALIDATION,
    # UniRig
    UNIRIG_RIG_LATENCY_MS,
    UNIRIG_RIGS,
    WORLD_PROVIDER_GENERATIONS,
    WORLD_PROVIDER_LATENCY_MS,
)

__all__ = [
    "AUDIO2FACE_ANIMATIONS",
    "AUDIO2FACE_ANIMATION_LATENCY_MS",
    "CACHE_HITS_TOTAL",
    "CACHE_MISSES_TOTAL",
    "EMBODIED_PLAN_GENERATIONS",
    "ERRORS_TOTAL",
    "ETHICAL_BLOCKS_TOTAL",
    "FORGE_GENERATIONS",
    # Pipeline-level (re-exported)
    "FORGE_STAGE_DURATION_MS",
    # Service-level
    "GENERATION_DURATION",
    "GENERATION_TOTAL",
    "GENUI_VALIDATE_FAILURES",
    "GPU_USAGE_PERCENT",
    "IDEMPOTENCY_CHECKS_TOTAL",
    "MEMORY_USAGE_MB",
    "MOTION_GENERATIONS",
    "MOTION_GENERATION_LATENCY_MS",
    "QUALITY_SCORE",
    "STYLE_REGENERATIONS",
    "STYLE_VALIDATION",
    "THREAT_SCORE",
    "UNIRIG_RIGS",
    "UNIRIG_RIG_LATENCY_MS",
    "VALIDATION_FAILURES_TOTAL",
    "WORLD_PROVIDER_GENERATIONS",
    "WORLD_PROVIDER_LATENCY_MS",
]
