"""
3D Generation Module — SOTA Gaussian Splatting — December 2025.

Provides text-to-3D generation using:
- Gsgen-style Gaussian Splatting
- DecompDreamer multi-object decomposition
- SDS (Score Distillation Sampling) optimization

鏡 K OS 3D Generation
"""

from .gaussian_splatting import (
    DecompDreamerGenerator,
    # Data
    Gaussian3D,
    GaussianCloud,
    # Config
    GaussianSplattingConfig,
    GenerationMode,
    GenerationResult,
    # Generators
    GsgenGenerator,
    Unified3DGenerator,
    generate_3d,
    # Functions
    get_3d_generator,
)

__all__ = [
    "DecompDreamerGenerator",
    # Data
    "Gaussian3D",
    "GaussianCloud",
    # Config
    "GaussianSplattingConfig",
    "GenerationMode",
    "GenerationResult",
    # Generators
    "GsgenGenerator",
    "Unified3DGenerator",
    "generate_3d",
    # Functions
    "get_3d_generator",
]
