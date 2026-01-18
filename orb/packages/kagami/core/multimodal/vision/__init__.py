"""SOTA Vision Encoders — December 2025.

Unified vision stack with state-of-the-art models:
1. Florence-2 — Unified vision foundation (detection + segmentation + grounding)
2. SAM2 — Real-time video segmentation with streaming memory
3. DINOv2 — Self-supervised visual features (with registers)
4. Jina-VLM — Compact 2.4B multilingual VLM
5. NeuralDenoiser — KPCN-style differentiable denoiser for ray tracing

This module REPLACES the legacy CLIP/DETR stack.

Usage:
    from kagami.core.multimodal.vision import UnifiedVisionModule

    vision = UnifiedVisionModule()
    await vision.initialize_all()

    # Detection (Florence-2)
    objects = await vision.detect(image)

    # Captioning (Florence-2)
    caption = await vision.caption(image, detailed=True)

    # Segmentation (SAM2)
    masks = await vision.segment(image, points=[(100, 100)])

    # Visual features (DINOv2)
    features = await vision.encode(image)

    # VQA (Jina-VLM)
    answer = await vision.answer(image, "What is this?")

    # Full scene analysis
    scene = await vision.analyze(image)

    # Denoising (NeuralDenoiser)
    from kagami.core.multimodal.vision import create_denoiser
    denoiser = create_denoiser()
    clean = denoiser.denoise_numpy(noisy_rgb, depth=depth)
"""

# SOTA unified module (December 2025)
# Neural Denoiser (December 2025) - Differentiable for E2E training
from kagami.core.multimodal.vision.neural_denoiser import (
    DenoiserConfig,
    DenoiserLoss,
    GenesisDenoiserWrapper,
    NeuralDenoiser,
    create_denoiser,
)

# OIDN Denoiser (December 2025) - Production quality with pretrained weights
from kagami.core.multimodal.vision.oidn_denoiser import (
    GenesisOIDNDenoiser,
    OIDNDenoiser,
    create_oidn_denoiser,
)
from kagami.core.multimodal.vision.unified_vision import (
    DetectedObject,
    DINOv2Encoder,
    # Core encoders
    Florence2Encoder,
    JinaVLM,
    SAM2Segmenter,
    SceneGraphResult,
    SceneRelation,
    # Utilities
    TaskType,
    # Scene graph
    UnifiedSceneGraphGenerator,
    # Unified interface
    UnifiedVisionModule,
    # Video
    VideoSegmentResult,
    get_optimal_device,
    get_unified_vision_module,
)

__all__ = [
    "DINOv2Encoder",
    "DenoiserConfig",
    "DenoiserLoss",
    "DetectedObject",
    "Florence2Encoder",
    "GenesisDenoiserWrapper",
    "GenesisOIDNDenoiser",
    "JinaVLM",
    # Neural Denoiser (differentiable, for training)
    "NeuralDenoiser",
    # OIDN Denoiser (production, pretrained)
    "OIDNDenoiser",
    "SAM2Segmenter",
    "SceneGraphResult",
    "SceneRelation",
    # Utilities
    "TaskType",
    # Scene Graph
    "UnifiedSceneGraphGenerator",
    # SOTA Vision Models
    "UnifiedVisionModule",
    # Video
    "VideoSegmentResult",
    "create_denoiser",
    "create_oidn_denoiser",
    "get_optimal_device",
    "get_unified_vision_module",
]
