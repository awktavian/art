"""Identity Manager for Storage and Retrieval.

Manages identity profiles including storage, lookup, merging, and export.
Provides the interface between extracted identities and Kagami systems.

Usage:
    manager = IdentityManager()

    # List all identities
    identities = manager.list_identities()

    # Get specific identity
    identity = manager.get_identity("abc123")

    # Confirm and name identity
    manager.confirm_identity("abc123", name="Becky")

    # Export for voice cloning
    manager.export_for_voice_cloning("abc123", output_dir="/tmp/voice")
"""

import json
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import numpy as np


@dataclass
class Identity:
    """A stored identity with all associated data."""

    identity_id: str
    status: str = "auto_detected"  # auto_detected, confirmed, merged
    name: str | None = None
    confirmed: bool = False

    # Physical characteristics
    age_estimate: dict | None = None  # {min, max, confidence}
    gender_estimate: dict | None = None  # {value, confidence}

    # Appearance counts
    total_frames: int = 0
    total_duration_seconds: float = 0.0
    video_count: int = 0
    videos: list[str] = field(default_factory=list)

    # Voice readiness
    voice_total_seconds: float = 0.0
    voice_sample_count: int = 0
    voice_ready_for_cloning: bool = False

    # Face data
    face_count: int = 0
    best_face_quality: float = 0.0

    # Motion data
    motion_frames: int = 0
    activity_level: str = "unknown"

    # Paths
    base_path: Path | None = None

    # Linked systems
    presence_id: str | None = None
    voice_clone_id: str | None = None

    # Timestamps
    created_at: str | None = None
    updated_at: str | None = None

    @property
    def display_name(self) -> str:
        return self.name or f"Person {self.identity_id[:8]}"

    def to_dict(self) -> dict:
        return {
            "identity_id": self.identity_id,
            "status": self.status,
            "name": self.name,
            "confirmed": self.confirmed,
            "display_name": self.display_name,
            "physical": {
                "age_estimate": self.age_estimate,
                "gender_estimate": self.gender_estimate,
            },
            "appearances": {
                "total_frames": self.total_frames,
                "total_duration_seconds": self.total_duration_seconds,
                "video_count": self.video_count,
                "videos": self.videos,
            },
            "voice": {
                "total_seconds": self.voice_total_seconds,
                "sample_count": self.voice_sample_count,
                "ready_for_cloning": self.voice_ready_for_cloning,
            },
            "face": {
                "count": self.face_count,
                "best_quality": self.best_face_quality,
            },
            "motion": {
                "frames": self.motion_frames,
                "activity_level": self.activity_level,
            },
            "linked": {
                "presence_id": self.presence_id,
                "voice_clone_id": self.voice_clone_id,
            },
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class IdentityManager:
    """Manage identity profiles and their data.

    Provides CRUD operations, searching, and export functionality.
    """

    def __init__(
        self,
        base_dir: str = "assets/identities",
    ):
        """Initialize identity manager.

        Args:
            base_dir: Base directory for identity storage
        """
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def list_identities(
        self,
        confirmed_only: bool = False,
        with_voice: bool = False,
    ) -> list[Identity]:
        """List all stored identities.

        Args:
            confirmed_only: Only return confirmed identities
            with_voice: Only return identities with voice data

        Returns:
            List of Identity objects
        """
        identities = []

        for item in self.base_dir.iterdir():
            if item.is_dir() and not item.name.startswith("."):
                meta_path = item / "metadata.json"
                if meta_path.exists():
                    identity = self._load_identity(item)

                    if confirmed_only and not identity.confirmed:
                        continue

                    if with_voice and not identity.voice_ready_for_cloning:
                        continue

                    identities.append(identity)

        return identities

    def get_identity(self, identity_id: str) -> Identity | None:
        """Get a specific identity by ID.

        Args:
            identity_id: Identity ID

        Returns:
            Identity or None if not found
        """
        identity_dir = self.base_dir / identity_id

        if not identity_dir.exists():
            return None

        return self._load_identity(identity_dir)

    def search_identities(
        self,
        query: str,
    ) -> list[Identity]:
        """Search identities by name or ID.

        Args:
            query: Search query

        Returns:
            List of matching identities
        """
        query = query.lower()
        results = []

        for identity in self.list_identities():
            if query in identity.identity_id.lower() or (
                identity.name and query in identity.name.lower()
            ):
                results.append(identity)

        return results

    def confirm_identity(
        self,
        identity_id: str,
        name: str,
        age_estimate: dict | None = None,
        gender_estimate: dict | None = None,
    ) -> bool:
        """Confirm an identity and assign a name.

        Args:
            identity_id: Identity ID
            name: Human-readable name
            age_estimate: Optional age estimate {min, max, confidence}
            gender_estimate: Optional gender estimate {value, confidence}

        Returns:
            True if successful
        """
        identity = self.get_identity(identity_id)
        if not identity:
            return False

        identity.name = name
        identity.confirmed = True
        identity.status = "confirmed"
        identity.age_estimate = age_estimate
        identity.gender_estimate = gender_estimate
        identity.updated_at = datetime.now().isoformat()

        self._save_identity(identity)
        return True

    def merge_identities(
        self,
        primary_id: str,
        secondary_ids: list[str],
    ) -> Identity | None:
        """Merge multiple identities into one.

        Args:
            primary_id: ID of identity to keep
            secondary_ids: IDs of identities to merge in

        Returns:
            Merged identity or None if failed
        """
        primary = self.get_identity(primary_id)
        if not primary:
            return None

        for secondary_id in secondary_ids:
            secondary = self.get_identity(secondary_id)
            if secondary:
                # Merge data
                self._merge_identity_data(primary, secondary)

                # Delete secondary
                self.delete_identity(secondary_id)

        primary.status = "merged"
        primary.updated_at = datetime.now().isoformat()
        self._save_identity(primary)

        return primary

    def delete_identity(self, identity_id: str) -> bool:
        """Delete an identity.

        Args:
            identity_id: Identity ID

        Returns:
            True if successful
        """
        identity_dir = self.base_dir / identity_id

        if identity_dir.exists():
            shutil.rmtree(identity_dir)
            return True

        return False

    def get_face_references(
        self,
        identity_id: str,
        max_count: int = 10,
    ) -> list[Path]:
        """Get face reference image paths for an identity.

        Args:
            identity_id: Identity ID
            max_count: Maximum number of images

        Returns:
            List of image paths
        """
        identity_dir = self.base_dir / identity_id / "faces"

        if not identity_dir.exists():
            return []

        images = sorted(identity_dir.glob("*.jpg"))[:max_count]
        return images

    def get_voice_samples(
        self,
        identity_id: str,
    ) -> list[Path]:
        """Get voice sample paths for an identity.

        Args:
            identity_id: Identity ID

        Returns:
            List of audio file paths
        """
        identity_dir = self.base_dir / identity_id / "audio" / "voice_samples"

        if not identity_dir.exists():
            return []

        samples = sorted(identity_dir.glob("*.mp3"))
        samples.extend(sorted(identity_dir.glob("*.wav")))

        return samples

    def export_for_voice_cloning(
        self,
        identity_id: str,
        output_dir: str,
    ) -> dict:
        """Export identity's voice data for voice cloning.

        Args:
            identity_id: Identity ID
            output_dir: Output directory

        Returns:
            Export metadata
        """
        identity = self.get_identity(identity_id)
        if not identity:
            return {"error": "Identity not found"}

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # Copy voice samples
        samples = self.get_voice_samples(identity_id)
        total_duration = 0.0

        for sample in samples:
            dest = output_path / sample.name
            shutil.copy2(sample, dest)

            # Get duration
            duration = self._get_audio_duration(sample)
            total_duration += duration

        # Create export metadata
        metadata = {
            "identity_id": identity_id,
            "name": identity.name,
            "sample_count": len(samples),
            "total_duration_seconds": total_duration,
            "ready_for_instant_clone": total_duration >= 60,
            "ready_for_professional_clone": total_duration >= 1800,
            "exported_at": datetime.now().isoformat(),
        }

        meta_path = output_path / "voice_export.json"
        with open(meta_path, "w") as f:
            json.dump(metadata, f, indent=2)

        return metadata

    def export_for_image_generation(
        self,
        identity_id: str,
        output_dir: str,
    ) -> dict:
        """Export identity's face data for image generation.

        Args:
            identity_id: Identity ID
            output_dir: Output directory

        Returns:
            Export metadata
        """
        identity = self.get_identity(identity_id)
        if not identity:
            return {"error": "Identity not found"}

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # Copy face references
        faces = self.get_face_references(identity_id, max_count=20)

        for i, face in enumerate(faces):
            dest = output_path / f"reference_{i:03d}.jpg"
            shutil.copy2(face, dest)

        # Create export metadata
        metadata = {
            "identity_id": identity_id,
            "name": identity.name,
            "reference_count": len(faces),
            "exported_at": datetime.now().isoformat(),
        }

        meta_path = output_path / "image_export.json"
        with open(meta_path, "w") as f:
            json.dump(metadata, f, indent=2)

        return metadata

    def link_to_presence(
        self,
        identity_id: str,
        presence_id: str,
    ) -> bool:
        """Link identity to presence system.

        Args:
            identity_id: Identity ID
            presence_id: Presence system ID

        Returns:
            True if successful
        """
        identity = self.get_identity(identity_id)
        if not identity:
            return False

        identity.presence_id = presence_id
        identity.updated_at = datetime.now().isoformat()
        self._save_identity(identity)

        return True

    def link_to_voice_clone(
        self,
        identity_id: str,
        voice_clone_id: str,
    ) -> bool:
        """Link identity to voice clone.

        Args:
            identity_id: Identity ID
            voice_clone_id: ElevenLabs voice ID

        Returns:
            True if successful
        """
        identity = self.get_identity(identity_id)
        if not identity:
            return False

        identity.voice_clone_id = voice_clone_id
        identity.updated_at = datetime.now().isoformat()
        self._save_identity(identity)

        return True

    def _load_identity(self, identity_dir: Path) -> Identity:
        """Load identity from directory."""
        meta_path = identity_dir / "metadata.json"

        with open(meta_path) as f:
            data = json.load(f)

        # Map JSON to Identity object
        identity = Identity(
            identity_id=data.get("identity_id", identity_dir.name),
            status=data.get("status", "auto_detected"),
            name=data.get("name"),
            confirmed=data.get("confirmed", False),
            base_path=identity_dir,
        )

        # Appearances
        appearances = data.get("appearances", {})
        identity.total_frames = appearances.get("total_frames", 0)
        identity.total_duration_seconds = appearances.get("total_duration_seconds", 0)
        identity.video_count = appearances.get("video_count", 0)
        identity.videos = appearances.get("videos", [])

        # Physical
        physical = data.get("physical", {})
        identity.age_estimate = physical.get("age_estimate")
        identity.gender_estimate = physical.get("gender_estimate")

        # Voice
        voice = data.get("voice", {})
        identity.voice_total_seconds = voice.get("total_seconds", 0)
        identity.voice_sample_count = voice.get("sample_count", 0)
        identity.voice_ready_for_cloning = voice.get("ready_for_cloning", False)

        # Face
        face = data.get("face", {})
        identity.face_count = face.get("count", face.get("reference_count", 0))
        identity.best_face_quality = face.get("best_quality", 0)

        # Motion
        motion = data.get("motion", {})
        identity.motion_frames = motion.get("frames", 0)
        identity.activity_level = motion.get("activity_level", "unknown")

        # Linked
        linked = data.get("linked", {})
        identity.presence_id = linked.get("presence_id")
        identity.voice_clone_id = linked.get("voice_clone_id")

        # Timestamps
        identity.created_at = data.get("created_at")
        identity.updated_at = data.get("updated_at")

        return identity

    def _save_identity(self, identity: Identity):
        """Save identity to disk."""
        identity_dir = self.base_dir / identity.identity_id
        identity_dir.mkdir(parents=True, exist_ok=True)

        meta_path = identity_dir / "metadata.json"
        with open(meta_path, "w") as f:
            json.dump(identity.to_dict(), f, indent=2)

    def _merge_identity_data(
        self,
        primary: Identity,
        secondary: Identity,
    ):
        """Merge secondary identity data into primary."""
        # Merge counts
        primary.total_frames += secondary.total_frames
        primary.total_duration_seconds += secondary.total_duration_seconds
        primary.video_count += secondary.video_count
        primary.videos.extend(secondary.videos)
        primary.videos = list(set(primary.videos))

        primary.voice_total_seconds += secondary.voice_total_seconds
        primary.voice_sample_count += secondary.voice_sample_count
        primary.face_count += secondary.face_count
        primary.motion_frames += secondary.motion_frames

        # Update readiness
        primary.voice_ready_for_cloning = primary.voice_total_seconds >= 60

        # Merge files
        if secondary.base_path:
            primary_faces = self.base_dir / primary.identity_id / "faces"
            secondary_faces = secondary.base_path / "faces"

            if secondary_faces.exists():
                for face in secondary_faces.glob("*.jpg"):
                    dest = primary_faces / f"merged_{face.name}"
                    shutil.copy2(face, dest)

            # Merge voice samples
            primary_voice = self.base_dir / primary.identity_id / "audio" / "voice_samples"
            secondary_voice = secondary.base_path / "audio" / "voice_samples"

            if secondary_voice.exists():
                primary_voice.mkdir(parents=True, exist_ok=True)
                for sample in secondary_voice.glob("*"):
                    dest = primary_voice / f"merged_{sample.name}"
                    shutil.copy2(sample, dest)

    def _get_audio_duration(self, audio_path: Path) -> float:
        """Get audio duration in seconds."""
        import subprocess

        cmd = [
            "ffprobe",
            "-v",
            "quiet",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(audio_path),
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return float(result.stdout.strip())
        except Exception:
            return 0.0

    # =========================================================================
    # Real-time Observation Recording (Continuous Learning)
    # =========================================================================

    def record_observation(
        self,
        identity_id: str,
        source: str,
        location: str,
        confidence: float,
        timestamp: float | None = None,
        face_embedding: list[float] | None = None,
        voice_embedding: list[float] | None = None,
        image_bytes: bytes | None = None,
        metadata: dict | None = None,
    ) -> bool:
        """Record a real-time observation of an identity.

        This enables continuous learning from camera detections:
        - Stores each observation for audit/replay
        - Optionally saves face images to improve recognition
        - Updates embeddings for better matching over time

        Args:
            identity_id: Identity that was detected
            source: Detection source (e.g., "unifi_camera", "hub_microphone")
            location: Where the detection occurred (room/camera name)
            confidence: Detection confidence (0-1)
            timestamp: Observation timestamp (defaults to now)
            face_embedding: Optional 512-dim face embedding
            voice_embedding: Optional voice embedding
            image_bytes: Optional face image for storage
            metadata: Additional metadata (camera_id, face_quality, etc.)

        Returns:
            True if recorded successfully
        """
        identity = self.get_identity(identity_id)
        if not identity:
            # Create new identity if needed
            identity_dir = self.base_dir / identity_id
            identity_dir.mkdir(parents=True, exist_ok=True)

            identity = Identity(
                identity_id=identity_id,
                status="auto_detected",
                created_at=datetime.now().isoformat(),
                base_path=identity_dir,
            )
            self._save_identity(identity)

        ts = timestamp or datetime.now().timestamp()
        ts_str = datetime.fromtimestamp(ts).isoformat()

        # Create observations directory
        observations_dir = self.base_dir / identity_id / "observations"
        observations_dir.mkdir(parents=True, exist_ok=True)

        # Create observation record
        observation = {
            "timestamp": ts,
            "timestamp_iso": ts_str,
            "source": source,
            "location": location,
            "confidence": confidence,
            "metadata": metadata or {},
        }

        # Store embedding if provided
        if face_embedding:
            observation["has_face_embedding"] = True
            embeddings_dir = self.base_dir / identity_id / "embeddings"
            embeddings_dir.mkdir(parents=True, exist_ok=True)

            # Append to embeddings file (JSONL format)
            embedding_record = {
                "timestamp": ts,
                "type": "face",
                "embedding": face_embedding,
                "confidence": confidence,
                "source": source,
            }
            embeddings_file = embeddings_dir / "face_embeddings.jsonl"
            with open(embeddings_file, "a") as f:
                f.write(json.dumps(embedding_record) + "\n")

        if voice_embedding:
            observation["has_voice_embedding"] = True
            embeddings_dir = self.base_dir / identity_id / "embeddings"
            embeddings_dir.mkdir(parents=True, exist_ok=True)

            embedding_record = {
                "timestamp": ts,
                "type": "voice",
                "embedding": voice_embedding,
                "confidence": confidence,
                "source": source,
            }
            embeddings_file = embeddings_dir / "voice_embeddings.jsonl"
            with open(embeddings_file, "a") as f:
                f.write(json.dumps(embedding_record) + "\n")

        # Save face image if provided and high quality
        if image_bytes and confidence > 0.7:
            faces_dir = self.base_dir / identity_id / "faces" / "live"
            faces_dir.mkdir(parents=True, exist_ok=True)

            # Use timestamp as filename
            ts_filename = datetime.fromtimestamp(ts).strftime("%Y%m%d_%H%M%S")
            face_path = faces_dir / f"{ts_filename}_{source}.jpg"
            with open(face_path, "wb") as f:
                f.write(image_bytes)
            observation["face_image_path"] = str(face_path)

        # Append observation to log (JSONL for efficient streaming)
        log_file = observations_dir / f"observations_{datetime.now().strftime('%Y%m')}.jsonl"
        with open(log_file, "a") as f:
            f.write(json.dumps(observation) + "\n")

        # Update identity stats
        identity.total_frames += 1
        identity.updated_at = datetime.now().isoformat()
        self._save_identity(identity)

        return True

    def get_observations(
        self,
        identity_id: str,
        limit: int = 100,
        since: float | None = None,
    ) -> list[dict]:
        """Get recent observations for an identity.

        Args:
            identity_id: Identity ID
            limit: Maximum number of observations
            since: Only return observations after this timestamp

        Returns:
            List of observation records (most recent first)
        """
        observations_dir = self.base_dir / identity_id / "observations"
        if not observations_dir.exists():
            return []

        observations = []

        # Read from all log files
        for log_file in sorted(observations_dir.glob("observations_*.jsonl"), reverse=True):
            with open(log_file) as f:
                for line in f:
                    if line.strip():
                        obs = json.loads(line)
                        if since and obs.get("timestamp", 0) <= since:
                            continue
                        observations.append(obs)
                        if len(observations) >= limit:
                            break
            if len(observations) >= limit:
                break

        # Sort by timestamp descending
        observations.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
        return observations[:limit]

    def get_stored_embeddings(
        self,
        identity_id: str,
        embedding_type: str = "face",
        limit: int = 100,
    ) -> list[dict]:
        """Get stored embeddings for an identity.

        Args:
            identity_id: Identity ID
            embedding_type: "face" or "voice"
            limit: Maximum number of embeddings

        Returns:
            List of embedding records with confidence scores
        """
        embeddings_file = (
            self.base_dir / identity_id / "embeddings" / f"{embedding_type}_embeddings.jsonl"
        )
        if not embeddings_file.exists():
            return []

        embeddings = []
        with open(embeddings_file) as f:
            for line in f:
                if line.strip():
                    embeddings.append(json.loads(line))
                    if len(embeddings) >= limit:
                        break

        # Sort by confidence descending
        embeddings.sort(key=lambda x: x.get("confidence", 0), reverse=True)
        return embeddings[:limit]

    def get_best_embedding(
        self,
        identity_id: str,
        embedding_type: str = "face",
    ) -> list[float] | None:
        """Get the best (highest confidence) embedding for an identity.

        Args:
            identity_id: Identity ID
            embedding_type: "face" or "voice"

        Returns:
            Embedding vector or None
        """
        embeddings = self.get_stored_embeddings(identity_id, embedding_type, limit=1)
        if embeddings:
            return embeddings[0].get("embedding")
        return None

    def compute_average_embedding(
        self,
        identity_id: str,
        embedding_type: str = "face",
        top_n: int = 10,
    ) -> list[float] | None:
        """Compute average of top-N highest confidence embeddings.

        This can improve recognition by averaging out noise.

        Args:
            identity_id: Identity ID
            embedding_type: "face" or "voice"
            top_n: Number of top embeddings to average

        Returns:
            Averaged embedding vector or None
        """
        embeddings = self.get_stored_embeddings(identity_id, embedding_type, limit=top_n)
        if not embeddings:
            return None

        vectors = [e.get("embedding") for e in embeddings if e.get("embedding")]
        if not vectors:
            return None

        # Average the vectors
        avg = np.mean(vectors, axis=0)

        # Normalize (important for cosine similarity)
        norm = np.linalg.norm(avg)
        if norm > 0:
            avg = avg / norm

        return avg.tolist()
