"""Main Video Processing Pipeline.

Orchestrates all extraction modules to create complete identity profiles
from video files. Chains: Segmentation -> Tracking -> Face -> Audio -> Pose -> Scene.

Usage:
    pipeline = VideoIdentityPipeline()
    results = pipeline.process_video("/path/to/video.mp4")

    # Or process entire USB drive
    results = pipeline.process_volume("/Volumes/WesData")
"""

import json
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from kagami_media.audio import DiarizationResult, SpeakerDiarizer, VoiceExtractor
from kagami_media.face_clusterer import FaceClusterer
from kagami_media.face_extractor import ExtractedFace, FaceExtractor
from kagami_media.motion import MotionTrack, PoseEstimator
from kagami_media.scene import SceneAnalyzer, SceneContext
from kagami_media.segmentation import FrameSegmentation, VideoSegmenter
from kagami_media.tracking import PersonReID, PersonTracker, TrackedPerson

# Video file extensions
VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".m4v", ".wmv", ".flv", ".webm"}


@dataclass
class VideoProcessingResult:
    """Result from processing a single video."""

    video_path: str
    video_name: str
    duration_seconds: float

    # Extracted data
    segments: list[FrameSegmentation] = field(default_factory=list)
    tracks: dict[int, TrackedPerson] = field(default_factory=dict)
    faces: list[ExtractedFace] = field(default_factory=list)
    diarization: DiarizationResult | None = None
    motion_tracks: list[MotionTrack] = field(default_factory=list)
    scene_context: SceneContext | None = None

    # Processing metadata
    processing_time_seconds: float = 0.0
    errors: list[str] = field(default_factory=list)

    @property
    def person_count(self) -> int:
        return len(self.tracks)

    @property
    def face_count(self) -> int:
        return len(self.faces)

    @property
    def speaker_count(self) -> int:
        return self.diarization.speaker_count if self.diarization else 0

    def to_dict(self) -> dict:
        return {
            "video_path": self.video_path,
            "video_name": self.video_name,
            "duration_seconds": self.duration_seconds,
            "person_count": self.person_count,
            "face_count": self.face_count,
            "speaker_count": self.speaker_count,
            "motion_track_count": len(self.motion_tracks),
            "processing_time_seconds": self.processing_time_seconds,
            "errors": self.errors,
            "scene": self.scene_context.to_dict() if self.scene_context else None,
        }


@dataclass
class IdentityCluster:
    """A cluster of data belonging to a single identity."""

    identity_id: str

    # Aggregated data from all videos
    faces: list[ExtractedFace] = field(default_factory=list)
    tracks: list[TrackedPerson] = field(default_factory=list)
    voice_segments: list = field(default_factory=list)
    motion_data: list[MotionTrack] = field(default_factory=list)

    # Embeddings
    face_embedding: object | None = None  # Average face embedding
    reid_embedding: object | None = None  # Average ReID embedding
    speaker_embedding: object | None = None

    # Statistics
    total_appearances: int = 0
    total_duration_seconds: float = 0.0
    videos_appeared_in: list[str] = field(default_factory=list)

    # Status
    name: str | None = None
    confirmed: bool = False

    def to_dict(self) -> dict:
        return {
            "identity_id": self.identity_id,
            "name": self.name,
            "confirmed": self.confirmed,
            "total_appearances": self.total_appearances,
            "total_duration_seconds": self.total_duration_seconds,
            "videos_appeared_in": self.videos_appeared_in,
            "face_count": len(self.faces),
            "track_count": len(self.tracks),
            "has_voice": len(self.voice_segments) > 0,
            "has_motion": len(self.motion_data) > 0,
        }


class VideoIdentityPipeline:
    """Main pipeline for extracting identities from videos.

    Chains all extraction modules and clusters results by identity.
    """

    def __init__(
        self,
        output_dir: str = "assets/identities",
        sample_interval: float = 0.5,
        enable_audio: bool = True,
        enable_pose: bool = True,
        enable_scene: bool = True,
        hf_token: str | None = None,  # For PyAnnote
    ):
        """Initialize pipeline.

        Args:
            output_dir: Base directory for identity data
            sample_interval: Seconds between frame samples
            enable_audio: Enable audio diarization
            enable_pose: Enable pose estimation
            enable_scene: Enable scene analysis
            hf_token: HuggingFace token for PyAnnote
        """
        self.output_dir = Path(output_dir)
        self.sample_interval = sample_interval
        self.enable_audio = enable_audio
        self.enable_pose = enable_pose
        self.enable_scene = enable_scene
        self.hf_token = hf_token

        # Initialize modules
        self._segmenter = VideoSegmenter(sample_interval=sample_interval)
        self._tracker = PersonTracker()
        self._reid = PersonReID()
        self._face_extractor = FaceExtractor(sample_interval=sample_interval)
        self._face_clusterer = FaceClusterer()

        if enable_audio:
            self._diarizer = SpeakerDiarizer(hf_token=hf_token)
            self._voice_extractor = VoiceExtractor()

        if enable_pose:
            self._pose_estimator = PoseEstimator(sample_interval=sample_interval)

        if enable_scene:
            self._scene_analyzer = SceneAnalyzer()

    def process_video(
        self,
        video_path: str,
        progress_callback: Callable[[str, float], None] | None = None,
    ) -> VideoProcessingResult:
        """Process a single video for identity extraction.

        Args:
            video_path: Path to video file
            progress_callback: Callback(stage, progress) for progress updates

        Returns:
            VideoProcessingResult with all extracted data
        """
        import time

        start_time = time.time()

        video_path = Path(video_path)
        result = VideoProcessingResult(
            video_path=str(video_path),
            video_name=video_path.name,
            duration_seconds=self._get_video_duration(video_path),
        )

        video_output_dir = self.output_dir / "videos" / video_path.stem
        video_output_dir.mkdir(parents=True, exist_ok=True)

        try:
            # Stage 1: Person Segmentation
            if progress_callback:
                progress_callback("segmentation", 0.0)

            segments = list(
                self._segmenter.segment_video(
                    str(video_path),
                    output_dir=str(video_output_dir / "segments"),
                )
            )
            result.segments = segments

            # Stage 2: Person Tracking
            if progress_callback:
                progress_callback("tracking", 0.2)

            tracks = self._tracker.track_video(str(video_path))
            tracks = self._reid.extract_embeddings_for_tracks(tracks)
            result.tracks = tracks

            # Stage 3: Face Extraction
            if progress_callback:
                progress_callback("faces", 0.4)

            faces = self._face_extractor.extract_from_video(
                str(video_path),
                output_dir=str(video_output_dir / "faces"),
            )
            result.faces = faces

            # Stage 4: Audio Diarization
            if self.enable_audio:
                if progress_callback:
                    progress_callback("audio", 0.6)

                try:
                    diarization = self._diarizer.diarize(str(video_path))
                    result.diarization = diarization

                    # Extract voice samples
                    if diarization and diarization.speaker_count > 0:
                        self._voice_extractor.extract_voice_samples(
                            diarization,
                            str(video_output_dir / "voice_samples"),
                        )
                except Exception as e:
                    result.errors.append(f"Audio processing failed: {e}")

            # Stage 5: Pose Estimation
            if self.enable_pose:
                if progress_callback:
                    progress_callback("pose", 0.8)

                try:
                    motion_tracks = self._pose_estimator.estimate_poses(
                        str(video_path),
                        output_dir=str(video_output_dir / "motion"),
                    )
                    result.motion_tracks = motion_tracks
                except Exception as e:
                    result.errors.append(f"Pose estimation failed: {e}")

            # Stage 6: Scene Context
            if self.enable_scene:
                if progress_callback:
                    progress_callback("scene", 0.9)

                try:
                    scene_context = self._scene_analyzer.analyze_video(
                        str(video_path),
                        output_dir=str(video_output_dir / "scene"),
                    )
                    result.scene_context = scene_context
                except Exception as e:
                    result.errors.append(f"Scene analysis failed: {e}")

            if progress_callback:
                progress_callback("complete", 1.0)

        except Exception as e:
            result.errors.append(f"Processing failed: {e}")

        result.processing_time_seconds = time.time() - start_time

        # Save result metadata
        self._save_video_result(result, video_output_dir)

        return result

    def process_volume(
        self,
        volume_path: str,
        progress_callback: Callable[[str, int, int], None] | None = None,
    ) -> list[VideoProcessingResult]:
        """Process all videos on a volume.

        Args:
            volume_path: Path to volume (e.g., /Volumes/WesData)
            progress_callback: Callback(video_name, current, total)

        Returns:
            List of VideoProcessingResult
        """
        volume_path = Path(volume_path)

        # Find all video files
        video_files = []
        for ext in VIDEO_EXTENSIONS:
            video_files.extend(volume_path.rglob(f"*{ext}"))
            video_files.extend(volume_path.rglob(f"*{ext.upper()}"))

        video_files = sorted(set(video_files))

        results = []

        for i, video_path in enumerate(video_files):
            if progress_callback:
                progress_callback(video_path.name, i, len(video_files))

            try:
                result = self.process_video(str(video_path))
                results.append(result)
            except Exception as e:
                print(f"Failed to process {video_path}: {e}")

        # After processing all videos, cluster identities
        self.cluster_identities(results)

        return results

    def cluster_identities(
        self,
        results: list[VideoProcessingResult],
    ) -> list[IdentityCluster]:
        """Cluster all extracted data by identity.

        Uses face embeddings and ReID embeddings to match people
        across different videos.

        Args:
            results: List of video processing results

        Returns:
            List of IdentityCluster objects
        """
        # Collect all faces with embeddings
        all_faces = []
        for result in results:
            all_faces.extend(result.faces)

        # Cluster faces
        face_clusters = self._face_clusterer.cluster(all_faces)

        # Collect all tracks for ReID matching
        all_tracks = [result.tracks for result in results]
        self._reid.match_across_videos(all_tracks)

        # Create identity clusters
        identities = []

        for _cluster_id, cluster in face_clusters.items():
            identity_id = str(uuid.uuid4())[:8]

            identity = IdentityCluster(
                identity_id=identity_id,
                faces=cluster.faces,
                total_appearances=len(cluster.faces),
            )

            # Find videos this identity appears in
            videos = {f.source_video for f in cluster.faces}
            identity.videos_appeared_in = list(videos)

            # Calculate total duration (rough estimate)
            identity.total_duration_seconds = len(cluster.faces) * self.sample_interval

            identities.append(identity)

        # Save identity clusters
        self._save_identity_clusters(identities)

        return identities

    def _get_video_duration(self, video_path: Path) -> float:
        """Get video duration in seconds."""
        import subprocess

        cmd = [
            "ffprobe",
            "-v",
            "quiet",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(video_path),
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return float(result.stdout.strip())
        except Exception:
            return 0.0

    def _save_video_result(
        self,
        result: VideoProcessingResult,
        output_dir: Path,
    ):
        """Save video processing result metadata."""
        meta_path = output_dir / "processing_result.json"
        with open(meta_path, "w") as f:
            json.dump(result.to_dict(), f, indent=2)

    def _save_identity_clusters(self, identities: list[IdentityCluster]):
        """Save identity clusters to disk."""
        for identity in identities:
            identity_dir = self.output_dir / identity.identity_id
            identity_dir.mkdir(parents=True, exist_ok=True)

            # Create directory structure
            (identity_dir / "faces").mkdir(exist_ok=True)
            (identity_dir / "segments").mkdir(exist_ok=True)
            (identity_dir / "audio").mkdir(exist_ok=True)
            (identity_dir / "motion").mkdir(exist_ok=True)
            (identity_dir / "reasoning").mkdir(exist_ok=True)

            # Save metadata
            metadata = {
                "identity_id": identity.identity_id,
                "status": "auto_detected",
                "name": identity.name,
                "confirmed": identity.confirmed,
                "appearances": {
                    "total_frames": identity.total_appearances,
                    "total_duration_seconds": identity.total_duration_seconds,
                    "video_count": len(identity.videos_appeared_in),
                    "videos": identity.videos_appeared_in,
                },
                "face": {
                    "reference_count": len(identity.faces),
                },
                "created_at": datetime.now().isoformat(),
            }

            meta_path = identity_dir / "metadata.json"
            with open(meta_path, "w") as f:
                json.dump(metadata, f, indent=2)

            # Save best face references
            import cv2

            for i, face in enumerate(identity.faces[:10]):  # Top 10 faces
                if face.face_image is not None:
                    face_path = identity_dir / "faces" / f"face_{i:03d}.jpg"
                    cv2.imwrite(str(face_path), face.face_image)

            # Save source timestamps
            timestamps = {
                "identity_id": identity.identity_id,
                "extraction_date": datetime.now().strftime("%Y-%m-%d"),
                "references": [face.to_dict() for face in identity.faces],
            }

            ts_path = identity_dir / "source_timestamps.json"
            with open(ts_path, "w") as f:
                json.dump(timestamps, f, indent=2)


def process_video(
    video_path: str,
    output_dir: str = "assets/identities",
) -> VideoProcessingResult:
    """Convenience function to process a video.

    Args:
        video_path: Path to video
        output_dir: Output directory

    Returns:
        VideoProcessingResult
    """
    pipeline = VideoIdentityPipeline(output_dir=output_dir)
    return pipeline.process_video(video_path)


def process_volume(
    volume_path: str,
    output_dir: str = "assets/identities",
) -> list[VideoProcessingResult]:
    """Convenience function to process a volume.

    Args:
        volume_path: Path to volume
        output_dir: Output directory

    Returns:
        List of VideoProcessingResult
    """
    pipeline = VideoIdentityPipeline(output_dir=output_dir)
    return pipeline.process_volume(volume_path)
