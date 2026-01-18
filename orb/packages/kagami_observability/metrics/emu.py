"""Emu3.5 integration metrics.

Tracks:
- World generation operations (exploration, narrative, X2I)
- Image generation (T2I, X2I)
- Model loading/initialization
- Generation latency and quality
"""

from __future__ import annotations

from kagami_observability.metrics.core import Counter, Histogram

# World generation metrics
EMU_WORLD_GENERATIONS_TOTAL = Counter(
    "kagami_emu_world_generations_total",
    "Total Emu3.5 world generation requests",
    labelnames=["mode", "status"],  # mode: world_exploration, visual_narrative, x2i
)

EMU_WORLD_GENERATION_DURATION_SECONDS = Histogram(
    "kagami_emu_world_generation_duration_seconds",
    "Emu3.5 world generation latency",
    labelnames=["mode"],
    buckets=[1.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0],
)

# Image generation metrics
EMU_IMAGE_GENERATIONS_TOTAL = Counter(
    "kagami_emu_image_generations_total",
    "Total Emu3.5 image generation requests",
    labelnames=["mode", "status"],  # mode: t2i, x2i
)

EMU_IMAGE_GENERATION_DURATION_SECONDS = Histogram(
    "kagami_emu_image_generation_duration_seconds",
    "Emu3.5 image generation latency",
    labelnames=["mode"],
    buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0],
)

# Model initialization
EMU_MODEL_LOAD_DURATION_SECONDS = Histogram(
    "kagami_emu_model_load_duration_seconds",
    "Emu3.5 model loading time",
    labelnames=["component"],  # component: base_model, tokenizer, image_decoder
    buckets=[1.0, 5.0, 10.0, 30.0, 60.0, 120.0],
)

# Generation quality proxies
EMU_GENERATED_IMAGE_SIZE_BYTES = Histogram(
    "kagami_emu_generated_image_size_bytes",
    "Size of Emu-generated images in bytes",
    labelnames=["mode"],
    buckets=[10_000, 50_000, 100_000, 500_000, 1_000_000, 5_000_000],
)

EMU_GENERATED_FRAMES_PER_JOB = Histogram(
    "kagami_emu_generated_frames_per_job",
    "Number of frames generated per Emu world job",
    labelnames=["mode"],
    buckets=[1, 3, 5, 10, 20, 50],
)

# Provider routing
IMAGE_GEN_PROVIDER_REQUESTS_TOTAL = Counter(
    "kagami_image_gen_provider_requests_total",
    "Image generation requests by provider",
    labelnames=["provider", "status"],  # provider: emu, openai, flux, local
)

__all__ = [
    "EMU_GENERATED_FRAMES_PER_JOB",
    "EMU_GENERATED_IMAGE_SIZE_BYTES",
    "EMU_IMAGE_GENERATIONS_TOTAL",
    "EMU_IMAGE_GENERATION_DURATION_SECONDS",
    "EMU_MODEL_LOAD_DURATION_SECONDS",
    "EMU_WORLD_GENERATIONS_TOTAL",
    "EMU_WORLD_GENERATION_DURATION_SECONDS",
    "IMAGE_GEN_PROVIDER_REQUESTS_TOTAL",
]
