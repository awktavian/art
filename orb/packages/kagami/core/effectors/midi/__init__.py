"""MIDI Processing Utilities.

Provides MIDI analysis, expression generation, and articulation handling.

Colony: Forge (e₂)
Created: January 2, 2026
"""

from kagami.core.effectors.expression_engine import (
    ARTICULATION_ALIASES,
    # Keyswitch constants - universal for all BBC SO instruments
    BBC_KEYSWITCHES,
    STYLE_PRESETS,
    # Data classes
    ArticulationEvent,
    CCEvent,
    ExpressionConfig,
    # Engine
    ExpressionEngine,
    ExpressionResult,
    # Enums and config
    ExpressionStyle,
    NoteAnalysis,
    Phrase,
    add_expression,
    apply_keyswitches_to_file,
    apply_rubato,
    # Functions
    detect_articulations,
    detect_phrases,
    generate_dynamics_curve,
    generate_expression_curve,
    get_expression_engine,
    get_keyswitch_for_articulation,
    humanize_velocities,
    insert_keyswitches,
)

__all__ = [
    "ARTICULATION_ALIASES",
    # Keyswitch constants
    "BBC_KEYSWITCHES",
    "STYLE_PRESETS",
    # Data classes
    "ArticulationEvent",
    "CCEvent",
    "ExpressionConfig",
    # Engine
    "ExpressionEngine",
    "ExpressionResult",
    # Enums and config
    "ExpressionStyle",
    "NoteAnalysis",
    "Phrase",
    "add_expression",
    "apply_keyswitches_to_file",
    "apply_rubato",
    # Functions
    "detect_articulations",
    "detect_phrases",
    "generate_dynamics_curve",
    "generate_expression_curve",
    "get_expression_engine",
    "get_keyswitch_for_articulation",
    "humanize_velocities",
    "insert_keyswitches",
]
