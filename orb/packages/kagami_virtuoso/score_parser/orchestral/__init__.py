"""Orchestral score processing module.

Specialized OMR pipeline for complex orchestral full scores.
Handles multi-system layouts, instrument groups, and ensemble recognition.

Key components:
- SystemDetector: Detects musical systems and staff groups
- LayoutAnalyzer: High-level layout analysis with hints
- EnsembleOMR: Multi-backend OMR with result fusion
- OrchestralParser: Main entry point for orchestral scores
"""

from .ensemble_omr import EnsembleOMR, EnsembleResult, FusionStrategy
from .layout_analyzer import LayoutAnalyzer, LayoutHint, LayoutProfile
from .orchestral_parser import (
    OrchestralParser,
    OrchestralParseResult,
    parse_orchestral_score,
)
from .system_detector import (
    BoundingBox,
    InstrumentFamily,
    InstrumentGroup,
    PageLayout,
    StaffLine,
    SystemDetector,
    SystemRegion,
)

__all__ = [
    "BoundingBox",
    # Ensemble OMR
    "EnsembleOMR",
    "EnsembleResult",
    "FusionStrategy",
    "InstrumentFamily",
    "InstrumentGroup",
    # Layout analysis
    "LayoutAnalyzer",
    "LayoutHint",
    "LayoutProfile",
    "OrchestralParseResult",
    # Main parser
    "OrchestralParser",
    "PageLayout",
    "StaffLine",
    # System detection
    "SystemDetector",
    "SystemRegion",
    "parse_orchestral_score",
]
