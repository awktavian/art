"""Kagami Media Processing.

Comprehensive video identity extraction system for creating digital clones
from video archives. Automatically extracts, segments, tracks, and profiles
all people detected in videos.

Core Capabilities:
- USB volume monitoring with auto-processing
- SAM2 video segmentation for person extraction
- Person tracking and re-identification across videos
- Face detection, embedding, and clustering
- Speaker diarization and voice sample extraction
- Pose estimation for motion capture
- Scene context extraction
- Identity profile generation with full metadata

Colony: Grove (e₆) — Research, Observation
Safety: h(x) ≥ 0 — All processing local, no cloud upload

Usage:
    # Process a USB drive automatically
    python -m kagami_media.volume_monitor --auto-extract

    # Process a volume manually
    from kagami_media import process_volume
    results = process_volume("/Volumes/WesData")

    # Manage identities
    from kagami_media import IdentityManager
    manager = IdentityManager()
    identities = manager.list_identities()
"""

# Core extraction modules
# Audio processing
from kagami_media.audio import (
    DiarizationResult,
    SpeakerDiarizer,
    SpeakerSegment,
    VoiceExtractor,
    VoiceSample,
    diarize_audio,
    extract_voice_samples,
)
from kagami_media.face_clusterer import (
    FaceClusterer,
    PersonCluster,
    cluster_faces,
)
from kagami_media.face_extractor import (
    ExtractedFace,
    FaceExtractor,
    extract_faces_from_video,
)

# Identity management
from kagami_media.identity_manager import (
    Identity,
    IdentityManager,
)

# Motion capture
from kagami_media.motion import (
    MotionTrack,
    PoseEstimator,
    PoseFrame,
    estimate_poses,
)

# Pipeline orchestration
from kagami_media.pipeline import (
    IdentityCluster,
    VideoIdentityPipeline,
    VideoProcessingResult,
    process_video,
    process_volume,
)
from kagami_media.profile_generator import (
    ProfileGenerator,
    generate_character_profile,
)
from kagami_media.quality_scorer import (
    QualityScore,
    QualityScorer,
    score_face_quality,
)

# Scene analysis
from kagami_media.scene import (
    LightingInfo,
    SceneAnalyzer,
    SceneContext,
    analyze_scene,
)

# Video segmentation
from kagami_media.segmentation import (
    FrameSegmentation,
    PersonSegment,
    VideoSegmenter,
    segment_video,
)

# Person tracking
from kagami_media.tracking import (
    PersonReID,
    PersonTracker,
    TrackedPerson,
    track_persons_in_video,
)

# Gemini video analysis (recommended for knowledge extraction)
from kagami_media.video_analyzer import (
    GeminiVideoAnalyzer,
    PersonAppearance,
    SceneDescription,
    TranscriptSegment,
    VideoAnalysis,
    analyze_usb_volume,
)

# Video enhancement (Topaz Video AI)
from kagami_media.video_enhancement import (
    EnhancementPreset,
    EnhancementProgress,
    EnhancementSettings,
    cancel_enhancement,
    enhance_video,
    get_enhancement_status,
    list_enhancement_jobs,
    wait_for_enhancement,
)

# Volume monitoring
from kagami_media.volume_monitor import (
    VolumeInfo,
    VolumeMonitor,
    start_monitor,
)

__all__ = [
    "DiarizationResult",
    # Video enhancement (Topaz Video AI)
    "EnhancementPreset",
    "EnhancementProgress",
    "EnhancementSettings",
    "ExtractedFace",
    "FaceClusterer",
    # Face extraction
    "FaceExtractor",
    "FrameSegmentation",
    # Gemini video analysis (RECOMMENDED for knowledge extraction)
    "GeminiVideoAnalyzer",
    "Identity",
    "IdentityCluster",
    # Identity management
    "IdentityManager",
    "LightingInfo",
    "MotionTrack",
    "PersonAppearance",
    "PersonCluster",
    "PersonReID",
    "PersonSegment",
    # Person tracking
    "PersonTracker",
    # Motion
    "PoseEstimator",
    "PoseFrame",
    "ProfileGenerator",
    "QualityScore",
    "QualityScorer",
    # Scene
    "SceneAnalyzer",
    "SceneContext",
    "SceneDescription",
    # Audio
    "SpeakerDiarizer",
    "SpeakerSegment",
    "TrackedPerson",
    "TranscriptSegment",
    "VideoAnalysis",
    # Pipeline
    "VideoIdentityPipeline",
    "VideoProcessingResult",
    # Video segmentation
    "VideoSegmenter",
    "VoiceExtractor",
    "VoiceSample",
    "VolumeInfo",
    # Volume monitoring
    "VolumeMonitor",
    "analyze_scene",
    "analyze_usb_volume",
    "cancel_enhancement",
    "cluster_faces",
    "diarize_audio",
    "enhance_video",
    "estimate_poses",
    "extract_faces_from_video",
    "extract_voice_samples",
    "generate_character_profile",
    "get_enhancement_status",
    "list_enhancement_jobs",
    "process_video",
    "process_volume",
    "score_face_quality",
    "segment_video",
    "start_monitor",
    "track_persons_in_video",
    "wait_for_enhancement",
]

__version__ = "0.3.0"
