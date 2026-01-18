"""World Model Improvements Package.

This package contains improvements to the Kagami World Model based on
state-of-the-art research (December 2025).

Modules:
- e8_improvements: Learnable per-channel scales for E8 quantizer
- fano_improvements: Associator tracking loss for octonion algebra
- strange_loop_improvements: Iterative fixed-point refinement for μ_self

Created: December 27, 2025
"""

from .e8_improvements import (
    FSQStyleE8Quantizer,
    LearnableScaleE8Quantizer,
)
from .fano_improvements import (
    FanoAssociatorLoss,
    OctonionAlgebraVerifier,
)
from .strange_loop_improvements import (
    IterativeStrangeLoop,
    StrangeLoopConfig,
)

__all__ = [
    "FSQStyleE8Quantizer",
    "FanoAssociatorLoss",
    "IterativeStrangeLoop",
    "LearnableScaleE8Quantizer",
    "OctonionAlgebraVerifier",
    "StrangeLoopConfig",
]
