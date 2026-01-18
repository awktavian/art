"""Audio Module — Complete Orchestral Music Pipeline.

Contains:
- Symphony generation via LLM (MusicGen) + BBC Symphony Orchestra
- Sheet music generation (MIDI → LilyPond/PDF/MusicXML)
- LLM-powered arrangement and orchestration
- Unified Orchestra Composer pipeline (RALPH)
- Physics audio from real-time renderer (optional)

Main API:
    from kagami.forge.modules.audio import compose

    # Generate orchestral music from text
    result = await compose("A triumphant fanfare with brass")

    # Or use individual components
    result = await generate_symphony("epic battle music")
    result = await generate_sheet_music("symphony.mid")
    result = await arrange("theme.mid", style="romantic")

Colony: Forge (e₂)
Created: January 2, 2026
"""

# =============================================================================
# Symphony Generation (MusicGen → MIDI → BBC SO)
# =============================================================================
# =============================================================================
# LLM-Powered Arrangement
# =============================================================================
from kagami.forge.modules.audio.arranger import (
    BBC_INSTRUMENTS,
    ArrangementPlan,
    ArrangementResult,
    ArrangementStyle,
    Arranger,
    ArrangerConfig,
    TargetEnsemble,
    analyze_for_arrangement,
    arrange,
    get_arranger,
)

# =============================================================================
# Unified Orchestra Composer (RALPH)
# =============================================================================
from kagami.forge.modules.audio.orchestra_composer import (
    ComposerConfig,
    ComposerResult,
    ComposerStyle,
    OrchestraComposer,
    OutputType,
    compose,
    compose_from_prompt,
    get_composer,
    orchestrate_midi,
    render_score,
)

# =============================================================================
# Sheet Music Generation (MIDI → LilyPond/PDF)
# =============================================================================
from kagami.forge.modules.audio.sheet_music import (
    OutputFormat as SheetMusicFormat,
)
from kagami.forge.modules.audio.sheet_music import (
    PaperSize,
    ScoreLayout,
    SheetMusicConfig,
    SheetMusicGenerator,
    SheetMusicResult,
    generate_sheet_music,
    get_sheet_music_generator,
    midi_to_lilypond,
)
from kagami.forge.modules.audio.sheet_music import (
    analyze_midi as analyze_midi_for_notation,
)
from kagami.forge.modules.audio.symphony_generator import (
    STYLE_PROMPTS,
    CompositionStyle,
    MusicGenWrapper,
    SymphonyConfig,
    SymphonyGenerator,
    SymphonyResult,
    audio_to_midi,
    build_prompt,
    generate_symphony,
    get_symphony_generator,
)

# =============================================================================
# Physics Audio (optional - requires genesis module)
# =============================================================================
try:
    from kagami.forge.modules.genesis.realtime_renderer import (
        MATERIAL_MODES,
        PhysicsAudioEvent,
        RealtimeAudioEngine,
    )

    _HAS_PHYSICS_AUDIO = True
except ImportError:
    MATERIAL_MODES = {}
    PhysicsAudioEvent = None
    RealtimeAudioEngine = None
    _HAS_PHYSICS_AUDIO = False

# =============================================================================
# Exports
# =============================================================================
__all__ = [
    "BBC_INSTRUMENTS",
    # === Physics Audio (optional) ===
    "MATERIAL_MODES",
    "STYLE_PROMPTS",
    "ArrangementPlan",
    "ArrangementResult",
    # === Arrangement ===
    "ArrangementStyle",
    "Arranger",
    "ArrangerConfig",
    "ComposerConfig",
    "ComposerResult",
    # === Orchestra Composer ===
    "ComposerStyle",
    # === Symphony Generation ===
    "CompositionStyle",
    "MusicGenWrapper",
    "OrchestraComposer",
    "OutputType",
    "PaperSize",
    "PhysicsAudioEvent",
    "RealtimeAudioEngine",
    "ScoreLayout",
    "SheetMusicConfig",
    # === Sheet Music ===
    "SheetMusicFormat",
    "SheetMusicGenerator",
    "SheetMusicResult",
    "SymphonyConfig",
    "SymphonyGenerator",
    "SymphonyResult",
    "TargetEnsemble",
    "analyze_for_arrangement",
    "analyze_midi_for_notation",
    "arrange",
    "audio_to_midi",
    "build_prompt",
    # === MAIN API (compose is the unified entry point) ===
    "compose",
    "compose_from_prompt",
    "generate_sheet_music",
    "generate_symphony",
    "get_arranger",
    "get_composer",
    "get_sheet_music_generator",
    "get_symphony_generator",
    "midi_to_lilypond",
    "orchestrate_midi",
    "render_score",
]
