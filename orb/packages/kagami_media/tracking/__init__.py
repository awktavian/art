"""Person Tracking and Re-Identification Module.

Tracks people across frames and across different videos using:
- ByteTrack/DeepSORT for frame-to-frame tracking
- TorchReID for cross-video person re-identification
- Face embeddings for identity clustering

Key Features:
- Real-time tracking within videos
- Cross-video identity matching
- ReID embedding generation (2048-dim)
- Track management and cleanup

Usage:
    from kagami_media.tracking import PersonTracker, PersonReID

    tracker = PersonTracker()
    reid = PersonReID()

    # Track in video
    tracks = tracker.track_video("video.mp4")

    # Match across videos
    matches = reid.match_identities(tracks_video1, tracks_video2)
"""

from kagami_media.tracking.person_reid import (
    PersonReID,
    PersonTracker,
    TrackedPerson,
    track_persons_in_video,
)

__all__ = [
    "PersonReID",
    "PersonTracker",
    "TrackedPerson",
    "track_persons_in_video",
]
