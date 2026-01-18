"""K OS Multimodal Module.

This package contains lightweight, import-safe multimodal utilities:
- Contrastive fusion (cross-modal alignment)
- Hierarchical encoder (multi-scale feature extraction)
- Audio feature extraction + A/V alignment helpers
- Optical flow + motion feature extraction

The subpackage `kagami.core.multimodal.perception` provides a higher-level
"LeCun Perception module" namespace built on top of these primitives.
"""

from __future__ import annotations

from kagami.core.multimodal.audio_processing import (
    align_audio_visual_tempo,
    create_audio_visual_features,
    extract_audio_features,
    mel_spectrogram_to_tensor,
)
from kagami.core.multimodal.contrastive_fusion import (
    ContrastiveMultimodalFusion,
    get_multimodal_fusion,
)
from kagami.core.multimodal.hierarchical_encoder import (
    HierarchicalEncoder,
    get_hierarchical_encoder,
)
from kagami.core.multimodal.optical_flow import (
    compute_dense_optical_flow,
    extract_motion_features,
    visualize_optical_flow,
)

__all__ = [
    # Fusion
    "ContrastiveMultimodalFusion",
    # Hierarchical encoder
    "HierarchicalEncoder",
    "align_audio_visual_tempo",
    # Optical flow / motion
    "compute_dense_optical_flow",
    "create_audio_visual_features",
    # Audio processing
    "extract_audio_features",
    "extract_motion_features",
    "get_hierarchical_encoder",
    "get_multimodal_fusion",
    "mel_spectrogram_to_tensor",
    "visualize_optical_flow",
]
