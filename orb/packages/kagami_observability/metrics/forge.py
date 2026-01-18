"""K os Forge generation metrics.

Domain-specific metrics for the Forge 3D character pipeline.

Exports counters and histograms for stage timings, generation latency
and quality. These are designed to be lightweight and safe to import
from hot paths in Forge modules.
"""

from kagami_observability.metrics.core import Counter, Histogram

# ----------------------- Pipeline-level metrics -----------------------

# Per-stage timings for Forge pipeline (milliseconds)
FORGE_STAGE_DURATION_MS = Histogram(
    "kagami_forge_stage_duration_ms",
    "Forge stage duration (ms)",
    ["stage", "status"],
)

# Overall character generation outcomes (high level)
FORGE_GENERATIONS = Counter(
    "kagami_forge_generations",
    "Forge end-to-end character generations",
    ["status"],  # success|error
)

# Character generation outcomes with quality level (used by kagami.forge.service)
CHARACTER_GENERATIONS = Counter(
    "kagami_character_generations_total",
    "Character generation outcomes by status and quality",
    ["status", "quality"],  # status: success/success_cached/error, quality: preview/draft/final
)

# Embodied action plan metrics
EMBODIED_PLAN_GENERATIONS = Counter(
    "kagami_embodied_plan_generations_total",
    "Virtual action plan generations",
    ["status"],
)

# Provider-specific world generation metrics
WORLD_PROVIDER_GENERATIONS = Counter(
    "kagami_world_provider_generations_total",
    "World generation attempts per provider",
    ["provider", "status"],
)

WORLD_PROVIDER_LATENCY_MS = Histogram(
    "kagami_world_provider_latency_ms",
    "World generation latency per provider (ms)",
    ["provider"],
)

# ----------------------------- Rigging (UniRig) -----------------------

UNIRIG_RIG_LATENCY_MS = Histogram(
    "kagami_unirig_rig_latency_ms",
    "UniRig rigging latency (ms)",
    ["mode"],  # api|local
)

UNIRIG_RIGS = Counter(
    "kagami_unirig_rigs",
    "UniRig rigging operations",
    ["mode"],
)

# ----------------------------- Animation (Motion-Agent) ---------------

MOTION_GENERATION_LATENCY_MS = Histogram(
    "kagami_motion_generation_latency_ms",
    "Motion generation latency (ms)",
    ["model"],  # motion_agent, etc.
)

MOTION_GENERATIONS = Counter(
    "kagami_motion_generations",
    "Motion generation outcomes",
    ["model", "status"],  # model, success|error
)

# ----------------------------- Audio2Face -----------------------------

AUDIO2FACE_ANIMATION_LATENCY_MS = Histogram(
    "kagami_audio2face_animation_latency_ms",
    "Audio2Face animation latency (ms)",
    ["mode"],  # server|client
)

AUDIO2FACE_ANIMATIONS = Counter(
    "kagami_audio2face_animations",
    "Audio2Face animations",
    ["mode", "status"],
)

# ----------------------------- GenUI ----------------------------------

GENUI_VALIDATE_FAILURES = Counter(
    "kagami_genui_validate_failures",
    "GenUI validation failures",
)

# ----------------------------- Style ----------------------------------

STYLE_REGENERATIONS = Counter(
    "kagami_style_regenerations",
    "Style regenerations triggered",
)

STYLE_VALIDATION = Counter(
    "kagami_style_validation",
    "Style validation events",
)


__all__ = [
    "AUDIO2FACE_ANIMATIONS",
    "AUDIO2FACE_ANIMATION_LATENCY_MS",
    "CHARACTER_GENERATIONS",
    "EMBODIED_PLAN_GENERATIONS",
    "FORGE_GENERATIONS",
    "FORGE_STAGE_DURATION_MS",
    "GENUI_VALIDATE_FAILURES",
    "MOTION_GENERATIONS",
    "MOTION_GENERATION_LATENCY_MS",
    "STYLE_REGENERATIONS",
    "STYLE_VALIDATION",
    "UNIRIG_RIGS",
    "UNIRIG_RIG_LATENCY_MS",
    "WORLD_PROVIDER_GENERATIONS",
    "WORLD_PROVIDER_LATENCY_MS",
]
