"""鏡 Kagami Studio — THE Unified Production Platform.

One platform. Everything. No legacy code.

This is THE production system for Kagami. All other production code is deprecated.

Features:
    - Unified Character system (loads from assets/characters/*/metadata.json)
    - Unified Shot/Scene/Project composition
    - AI-native content generation (images, avatars, video, audio)
    - Full OBS Studio integration (real-time WebSocket control)
    - Video compositing (PIP, split, chromakey, documentary)
    - Multi-party dialogue (Holodeck mode)
    - Real-time streaming + recording + virtual camera
    - Native Dolby Atmos spatial audio output

Architecture:
    kagami_studio/
    ├── characters/     → Universal character protocol (voice, avatar, personality)
    ├── composition/    → Shot, Scene, Project (unified production units)
    ├── compositing/    → Video composition (PIP, chromakey, DCC documentary)
    ├── obs/            → OBS Studio WebSocket integration
    ├── modes/          → Holodeck, Podcast, Documentary workflows
    ├── generation/     → AI hub (image, avatar, video, audio)
    ├── enhancement/    → Topaz Video AI enhancement
    ├── sources/        → Input sources (camera, screen, avatar, AI)
    ├── scenes/         → Real-time scene composition
    ├── outputs/        → Recording, streaming, virtual camera
    └── engine.py       → Central orchestrator

Quick Start - Characters:
    from kagami_studio.characters import load_character, speak

    bella = load_character("bella")
    result = await speak("bella", "SNOW! SNOW SNOW SNOW!")

Quick Start - OBS Integration:
    from kagami_studio.obs import connect_obs

    async with connect_obs() as obs:
        await obs.switch_scene("Main", transition="Fade")
        await obs.start_streaming()

Quick Start - Compositing:
    from kagami_studio.compositing import create_pip_composite

    result = await create_pip_composite(
        background="game.mp4",
        overlay="webcam.mp4",
        output="output.mp4",
    )

Quick Start - Holodeck:
    from kagami_studio.modes import Holodeck

    holodeck = Holodeck()
    await holodeck.initialize()
    holodeck.dialogue("bella", "I am built for the cold.")
    result = await holodeck.render(play=True)

Version: 0.3.0 — OBS & Compositing Integration
"""

# === UNIFIED CHARACTER SYSTEM (NEW) ===
# === AUDIO ===
from kagami_studio.audio import (
    AudioChannel,
    AudioDucker,
    AudioMixer,
    DuckingConfig,
    MixerConfig,
)
from kagami_studio.characters import (
    AvatarConfig,
    Character,
    CharacterVoice,
    PersonalityConfig,
    VoiceConfig,
    get_character,
    list_characters,
    load_character,
    speak,
    speak_with_emotion,
)

# === UNIFIED COMPOSITION SYSTEM (NEW) ===
from kagami_studio.composition import (
    CameraAngle,
    Project,
    ProjectResult,
    SceneResult,
    Shot,
    ShotResult,
    ShotType,
    render_project,
    render_scene,
    render_shot,
)
from kagami_studio.composition import (
    Scene as CompositionScene,  # Renamed to avoid conflict with scenes.Scene
)

# === DEPTH & 3D CAMERA (NEW) ===
from kagami_studio.depth import (
    CameraConfig,
    CameraMotion,
    CameraPath,
    DepthEstimator,
    DepthModel,
    DepthResult,
    SceneGeometry,
    analyze_scene,
    create_camera_motion,
    create_dolly_zoom,
    create_ken_burns_3d,
    create_parallax_pan,
    estimate_depth,
    estimate_video_depth,
    segment_by_depth,
)
from kagami_studio.depth import (
    DepthLayer as SceneDepthLayer,
)

# === DOCUMENTARY MODULE DELETED ===
# Use production/ for video generation (THE Single System)
# DCC-style documentary LAYOUTS still available in compositing/

# === STUDIO ENGINE ===
from kagami_studio.engine import (
    Studio,
    StudioConfig,
    StudioEngine,
    StudioSession,
)

# === ENHANCEMENT (Topaz Video AI) ===
from kagami_studio.enhancement import (
    EnhancePreset,
    EnhanceResult,
    TopazConfig,
    TopazEnhancer,
    TopazModel,
    enhance_vhs,
    enhance_video,
    get_hardware,
)

# === GENERATION (REPLACED 2026-01-05) ===
# Old generation module replaced with new API clients
# from kagami_studio.generation import (
#     GenerationHub, RunwayGenerator, VideoModel, VideoPipeline,
#     generate_and_enhance, generate_audio, generate_avatar, generate_image, generate_video,
# )
# New imports:
from kagami_studio.generation import (
    MusicGenerator,
    ImageGenerator,
    VideoGenerator,
    Model3DGenerator,
    AudioGenerator,
)

# === PRODUCTION MODES (NEW) ===
from kagami_studio.modes import (
    DialogueLine,
    Holodeck,
    HolodeckResult,
    simulate_dialogue,
)

# === OUTPUTS ===
from kagami_studio.outputs import (
    Output,
    OutputManager,
    RecordingOutput,
    StreamingOutput,
    VirtualCamOutput,
)

# === PREVIEW ===
from kagami_studio.preview import (
    MultiView,
    MultiViewConfig,
    MultiViewLayout,
)

# === REAL-TIME SCENES ===
from kagami_studio.scenes import (
    LowerThird,
    Overlay,
    Scene,
    SceneManager,
    StingerLibrary,
    StingerTransition,
    Transition,
)

# === SOURCES ===
from kagami_studio.sources import (
    AudioSource,
    AvatarSource,
    BrowserSource,
    CameraSource,
    ImageSource,
    NDISource,
    ScreenSource,
    Source,
    SourceManager,
    VideoSource,
)

# === SUBTITLES (Kinetic DCC-style — optional, production uses HTML by default) ===
from kagami_studio.subtitles import (
    EmotionStyle as SubtitleEmotionStyle,
    KineticSubtitleGenerator,
    WordTiming,
)
from kagami_studio.subtitles.kinetic import (
    burn_subtitles,
    generate_kinetic_subtitles,
)

# === PRODUCTION (THE Unified Video Production Pipeline) ===
# Created: January 2026 — Replaces talk/, presentation/, scattered production code
from kagami_studio.production import (
    # Core production
    ProductionResult,
    ProductionScript,
    ScriptSlide,
    WordTiming as ProductionWordTiming,
    produce_video,
    # Speaker system
    SpeakerContext,
    list_available_speakers,
    load_speaker_context,
    # Slide generation
    generate_presentation,
    SlideLayout,
    SlideDesign,
    GradientPreset,
    generate_slide_html,
    generate_slide_deck_html,
    # Shot planning
    CoverageStrategy,
    ProductionPlan,
    PlannedShot,
    VisualSeed,
    plan_production,
    list_coverage_strategies,
    load_visual_seed,
    # === COMPOSABLE PRIMITIVES ===
    synthesize_speech,
    render_slide_image,
    render_slide_deck,
    composite_final_video,
    get_design_system,
)

# === VLM (Gemini 3 Vision Language Model) ===
from kagami_studio.vlm import (
    GeminiVLM,
    VLMAnalysis,
    VLMConfig,
    VLMScene,
    VLMSegment,
    VLMTranscript,
    VLMWord,
    get_vlm,
)
from kagami_studio.vlm import (
    analyze_video as vlm_analyze,
)
from kagami_studio.vlm import (
    transcribe_video as vlm_transcribe,
)

__all__ = [
    "EMOTION_KEYWORDS",
    "AdaptiveMasker",
    "AudioChannel",
    "AudioDucker",
    # === AUDIO ===
    "AudioMixer",
    "AudioSource",
    "AvatarConfig",
    "AvatarSource",
    "BridgeMode",
    "BrowserSource",
    "CameraAngle",
    "CameraConfig",
    "CameraMotion",
    "CameraPath",
    "CameraSource",
    # === CHARACTERS (NEW) ===
    "Character",
    "CharacterVoice",
    "ChromakeyConfig",
    "CompositeConfig",
    # === COMPOSITING (NEW) ===
    "CompositeEngine",
    "CompositeLayer",
    "CompositeResult",
    "CompositeTemplate",
    "CompositionScene",
    # Shot planning
    "CoverageStrategy",
    "DCCTemplate",
    # === DEPTH & 3D CAMERA (NEW) ===
    "DepthEstimator",
    "DepthLayer",
    "DepthModel",
    "DepthResult",
    "DialogueLine",
    "DocumentaryConfig",
    # === DOCUMENTARY (NEW) ===
    "DocumentaryEngine",
    "DocumentaryResult",
    "DuckingConfig",
    "EmotionStyle",
    "EnhancePreset",
    "EnhanceResult",
    "FaceRegion",
    "FilterType",
    # === VLM (Gemini 3) ===
    "GeminiVLM",
    # === GENERATION ===
    "GenerationHub",
    "GradientPreset",
    # === MODES (NEW) ===
    "Holodeck",
    "HolodeckResult",
    "ImageSource",
    "InterviewTemplate",
    "LayerBlendMode",
    "LowerThird",
    "MixerConfig",
    "MotionStyle",
    # === PREVIEW ===
    "MultiView",
    "MultiViewConfig",
    "MultiViewLayout",
    "NDISource",
    "OBSBridge",
    "OBSCompositor",
    "OBSConfig",
    "OBSConnectionState",
    # === OBS INTEGRATION (NEW) ===
    "OBSController",
    "OBSStreamingPlatform",
    # === OUTPUTS ===
    "Output",
    "OutputManager",
    "Overlay",
    "PIPTemplate",
    "PersonalityConfig",
    "PlannedShot",
    "ProductionPlan",
    "ProductionResult",
    "ProductionScript",
    "Project",
    "ProjectResult",
    "RecordingOutput",
    "RecordingSettings",
    "RunwayGenerator",
    # === SCENES ===
    "Scene",
    "SceneDepthLayer",
    "SceneGeometry",
    "SceneManager",
    "SceneResult",
    "ScreenSource",
    "ScriptSlide",
    # === COMPOSITION (NEW) ===
    "Shot",
    "ShotResult",
    "ShotType",
    "SlideDesign",
    "SlideLayout",
    # === SOURCES ===
    "Source",
    "SourceManager",
    # Speaker system
    "SpeakerContext",
    "SplitTemplate",
    "StingerLibrary",
    "StingerTransition",
    "StreamSettings",
    "StreamingOutput",
    "StreamingTemplate",
    # === ENGINE ===
    "Studio",
    "StudioConfig",
    "StudioEngine",
    "StudioSession",
    "TimedWord",
    "TopazConfig",
    # === ENHANCEMENT (Topaz Video AI) ===
    "TopazEnhancer",
    "TopazModel",
    "TranscriptSegment",
    "TranscriptionBackend",
    "Transition",
    "TransitionType",
    "TypographyEngine",
    "VLMAnalysis",
    "VLMConfig",
    "VLMScene",
    "VLMSegment",
    "VLMTranscript",
    "VLMWord",
    "VideoModel",
    # === VIDEO PIPELINE (RunwayML + Topaz) ===
    "VideoPipeline",
    "VideoSource",
    "VirtualCamOutput",
    "VisualSeed",
    "VoiceConfig",
    "WordTiming",
    "analyze_scene",
    "apply_chromakey",
    "composite_final_video",
    "connect_obs",
    "create_blur_filter",
    "create_camera_motion",
    "create_chromakey_composite",
    "create_chromakey_filter",
    "create_color_correction_filter",
    "create_dcc_artifact",
    "create_documentary_composite",
    "create_dolly_zoom",
    "create_ken_burns_3d",
    "create_parallax_pan",
    "create_pip_composite",
    "create_split_composite",
    "create_web_artifact",
    "enhance_vhs",
    "enhance_video",
    "estimate_depth",
    "estimate_video_depth",
    "generate_and_enhance",
    "generate_audio",
    "generate_avatar",
    "generate_image",
    # Slide generation
    "generate_presentation",
    "generate_slide_deck_html",
    "generate_slide_html",
    "generate_video",
    "get_character",
    "get_design_system",
    "get_hardware",
    "get_vlm",
    "list_available_speakers",
    "list_characters",
    "list_coverage_strategies",
    "load_character",
    "load_speaker_context",
    "load_visual_seed",
    "plan_production",
    # === PRODUCTION (Unified Video Pipeline) ===
    "produce_video",
    "render_project",
    "render_scene",
    "render_shot",
    "render_slide_deck",
    "render_slide_image",
    "segment_by_depth",
    "simulate_dialogue",
    "speak",
    "speak_with_emotion",
    # Composable primitives
    "synthesize_speech",
    "transcribe_video",
    "translate_transcript",
    "vlm_analyze",
    "vlm_transcribe",
]

__version__ = "0.5.0"
