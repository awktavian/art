"""Kagami Virtuoso Score Parser.

State-of-the-art optical music recognition for orchestral scores.

Pipeline:
    PDF → Pages → Pre-process → OMR → MusicXML → Partitura → MIDI

For complex orchestral scores, use the orchestral module:
    PDF → Layout Analysis → System Detection → Group-level OMR → Reconstruction

Supported formats:
    - Input: PDF, PNG, JPG, TIFF
    - Output: MusicXML, MIDI, Partitura Note Arrays

Architecture:
    1. PDFExtractor - High-res page extraction from PDF
    2. ImagePreprocessor - Binarization, deskew, denoise
    3. StaffDetector - Find staff lines and systems
    4. OMREngine - Neural network music recognition (oemer/homr)
    5. PostProcessor - Clean up and verify results
    6. MusicXMLWriter - Structured notation output
    7. MIDIConverter - Playback-ready MIDI

For orchestral scores (20+ staves):
    8. SystemDetector - Detect systems and instrument groups
    9. LayoutAnalyzer - High-level layout with hints
    10. EnsembleOMR - Multi-backend with voting
    11. OrchestralParser - Hierarchical processing

Example (simple scores):
    >>> from kagami_virtuoso.score_parser import parse_score
    >>> result = await parse_score("piano_sonata.pdf")
    >>> result.to_midi("piano_sonata.mid")

Example (orchestral scores):
    >>> from kagami_virtuoso.score_parser.orchestral import parse_orchestral_score, LayoutHint
    >>> result = await parse_orchestral_score(
    ...     "beethoven_5.pdf",
    ...     layout_hint=LayoutHint.ROMANTIC_ORCHESTRA,
    ... )
    >>> print(f"Extracted {result.note_count} notes using {result.strategy_used} strategy")
"""

from .comparison import (
    ComparisonReport,
    compare_beethoven_5_showcase,
    compare_midi_files,
    compare_omr_result,
)
from .instrument_mapper import (
    BEETHOVEN_5_INSTRUMENTATION,
    InstrumentMapper,
    InstrumentMapping,
    map_beethoven_5,
)
from .mps_patch import get_optimal_providers, is_apple_silicon, patch_homr_for_mps
from .omr_engine import OMREngine

# Orchestral processing (import on demand to avoid circular deps)
from .orchestral import (
    EnsembleOMR,
    LayoutAnalyzer,
    LayoutHint,
    OrchestralParser,
    SystemDetector,
    parse_orchestral_score,
)
from .parser import ScoreParser, parse_beethoven_5, parse_score, smart_parse
from .pdf_extractor import PDFExtractor
from .postprocessor import MIDIExporter, PostProcessor
from .preprocessor import ImagePreprocessor

__all__ = [
    "BEETHOVEN_5_INSTRUMENTATION",
    # Comparison
    "ComparisonReport",
    "EnsembleOMR",
    "ImagePreprocessor",
    # Instrument mapping
    "InstrumentMapper",
    "InstrumentMapping",
    "LayoutAnalyzer",
    "LayoutHint",
    "MIDIExporter",
    "OMREngine",
    "OrchestralParser",
    "PDFExtractor",
    "PostProcessor",
    # Standard parsing
    "ScoreParser",
    # Orchestral processing
    "SystemDetector",
    "compare_beethoven_5_showcase",
    "compare_midi_files",
    "compare_omr_result",
    "get_optimal_providers",
    "is_apple_silicon",
    "map_beethoven_5",
    "parse_beethoven_5",
    "parse_orchestral_score",
    "parse_score",
    # MPS/CoreML acceleration
    "patch_homr_for_mps",
    "smart_parse",  # NEW: Auto-selects best parser
]
