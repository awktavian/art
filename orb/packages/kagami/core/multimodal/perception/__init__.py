"""鏡 Perception — unified sensory processing.

This package is the canonical, import-light namespace for perception primitives:
- **Multimodal primitives** (fusion, audio feature extraction, optical flow)
- **SOTA vision** (Florence-2 / SAM2 / DINOv2 / Jina-VLM)
- **DataStreamController** (LeCun-style 5-mode acquisition controller)

Importing this module must NOT trigger heavyweight model loads; model weights
are loaded lazily (e.g., via async `initialize()` calls).
"""

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# MULTIMODAL (cross-modal fusion + audio/motion primitives)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
from kagami.core.multimodal import (
    ContrastiveMultimodalFusion,
    HierarchicalEncoder,
    align_audio_visual_tempo,
    compute_dense_optical_flow,
    create_audio_visual_features,
    extract_audio_features,
    extract_motion_features,
    get_hierarchical_encoder,
    get_multimodal_fusion,
    mel_spectrogram_to_tensor,
    visualize_optical_flow,
)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# VISION (visual processing) — SOTA stack (Dec 2025)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
from kagami.core.multimodal.vision import (
    DetectedObject,
    DINOv2Encoder,
    Florence2Encoder,
    JinaVLM,
    SAM2Segmenter,
    SceneGraphResult,
    SceneRelation,
    TaskType,
    UnifiedSceneGraphGenerator,
    UnifiedVisionModule,
    VideoSegmentResult,
    get_optimal_device,
    get_unified_vision_module,
)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# DATA STREAMING (LeCun integration / unit tests)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
from .data_stream_controller import (
    DataMode,
    DataSample,
    DataStreamConfig,
    DataStreamController,
    get_data_stream_controller,
)

__all__ = [
    # === Multimodal ===
    "ContrastiveMultimodalFusion",
    "DINOv2Encoder",
    # === Data Stream ===
    "DataMode",
    "DataSample",
    "DataStreamConfig",
    "DataStreamController",
    "DetectedObject",
    "Florence2Encoder",
    "HierarchicalEncoder",
    "JinaVLM",
    "SAM2Segmenter",
    "SceneGraphResult",
    "SceneRelation",
    "TaskType",
    "UnifiedSceneGraphGenerator",
    # === Vision (SOTA) ===
    "UnifiedVisionModule",
    "VideoSegmentResult",
    "align_audio_visual_tempo",
    "compute_dense_optical_flow",
    "create_audio_visual_features",
    "extract_audio_features",
    "extract_motion_features",
    "get_data_stream_controller",
    "get_hierarchical_encoder",
    "get_multimodal_fusion",
    "get_optimal_device",
    "get_unified_vision_module",
    "mel_spectrogram_to_tensor",
    "visualize_optical_flow",
]
