"""Spatial Audio Processing.

Provides VBAP-based 3D audio positioning for 5.1.4 Atmos playback.

Colony: Forge (e₂)
Created: January 2, 2026
"""

from kagami.core.effectors.spatial_audio import (
    SpatialPlayResult,
    UnifiedSpatialEngine,
    get_spatial_engine,
)
from kagami.core.effectors.vbap_core import (
    CH_C,
    CH_L,
    CH_LFE,
    CH_LS,
    CH_R,
    CH_RS,
    CH_TBL,
    CH_TBR,
    CH_TFL,
    CH_TFR,
    # Constants
    NUM_CH,
    # Data class
    Pos3D,
    pan_stereo_to_vbap,
    # Functions
    vbap_10ch,
)

__all__ = [
    "CH_C",
    "CH_L",
    "CH_LFE",
    "CH_LS",
    "CH_R",
    "CH_RS",
    "CH_TBL",
    "CH_TBR",
    "CH_TFL",
    "CH_TFR",
    # Constants
    "NUM_CH",
    # Data class
    "Pos3D",
    "SpatialPlayResult",
    # Spatial engine
    "UnifiedSpatialEngine",
    "get_spatial_engine",
    "pan_stereo_to_vbap",
    # VBAP functions
    "vbap_10ch",
]
