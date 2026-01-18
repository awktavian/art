"""USB Volume Monitor.

Monitors /Volumes for new USB drive insertions and triggers face extraction.

Usage:
    monitor = VolumeMonitor(callback=on_new_drive)
    monitor.start()  # Runs in background

    # Or as daemon
    python -m kagami_media.volume_monitor
"""

import os
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

# Try to import FSEvents for macOS
try:
    from CoreFoundation import (
        CFRunLoopGetCurrent,
        CFRunLoopRun,
        CFRunLoopStop,
        kCFRunLoopDefaultMode,
    )
    from FSEvents import (
        FSEventStreamCreate,
        FSEventStreamInvalidate,
        FSEventStreamRelease,
        FSEventStreamScheduleWithRunLoop,
        FSEventStreamStart,
        FSEventStreamStop,
        kFSEventStreamCreateFlagNone,
        kFSEventStreamEventFlagItemCreated,
        kFSEventStreamEventFlagItemIsDir,
        kFSEventStreamEventIdSinceNow,
    )

    FSEVENTS_AVAILABLE = True
except ImportError:
    FSEVENTS_AVAILABLE = False


# Video file extensions to scan
VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".m4v", ".wmv", ".flv", ".webm"}


@dataclass
class VolumeInfo:
    """Information about a mounted volume."""

    name: str
    path: str
    mount_time: datetime
    video_files: list[str]
    total_size_mb: float

    @property
    def has_videos(self) -> bool:
        return len(self.video_files) > 0

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "path": self.path,
            "mount_time": self.mount_time.isoformat(),
            "video_count": len(self.video_files),
            "total_size_mb": self.total_size_mb,
            "video_files": self.video_files,
        }


class VolumeMonitor:
    """Monitor /Volumes for new USB drives with video content.

    Uses FSEvents on macOS for efficient event-driven monitoring.
    Falls back to polling on other platforms.

    When auto_extract=True, runs full identity extraction pipeline
    to create digital clone profiles for all detected people.
    """

    def __init__(
        self,
        callback: Callable[[VolumeInfo], None] | None = None,
        auto_extract: bool = False,
        full_pipeline: bool = True,  # Use full pipeline vs legacy face-only
        volumes_path: str = "/Volumes",
    ):
        """Initialize volume monitor.

        Args:
            callback: Function to call when new volume detected
            auto_extract: Automatically start identity extraction on new volumes
            full_pipeline: Use full pipeline (True) or legacy face-only (False)
            volumes_path: Path to monitor for volumes
        """
        self.callback = callback
        self.auto_extract = auto_extract
        self.full_pipeline = full_pipeline
        self.volumes_path = volumes_path

        self._running = False
        self._thread: threading.Thread | None = None
        self._known_volumes: set[str] = set()
        self._stream = None

        # Initialize known volumes
        self._scan_existing_volumes()

    def _scan_existing_volumes(self):
        """Scan for existing volumes on startup."""
        volumes_dir = Path(self.volumes_path)
        if volumes_dir.exists():
            for item in volumes_dir.iterdir():
                if item.is_dir() and not item.name.startswith("."):
                    self._known_volumes.add(item.name)

    def _scan_volume_for_videos(self, volume_path: str) -> list[str]:
        """Recursively scan volume for video files."""
        videos = []
        volume = Path(volume_path)

        try:
            for item in volume.rglob("*"):
                if item.is_file() and item.suffix.lower() in VIDEO_EXTENSIONS:
                    videos.append(str(item))
        except PermissionError:
            pass

        return videos

    def _get_volume_size(self, volume_path: str) -> float:
        """Get total size of video files in MB."""
        total = 0
        videos = self._scan_volume_for_videos(volume_path)
        for video in videos:
            try:
                total += os.path.getsize(video)
            except OSError:
                pass
        return total / (1024 * 1024)

    def _on_volume_detected(self, volume_name: str):
        """Handle new volume detection."""
        volume_path = os.path.join(self.volumes_path, volume_name)

        # Scan for videos
        videos = self._scan_volume_for_videos(volume_path)

        if not videos:
            print(f"Volume {volume_name} contains no video files, skipping")
            return

        # Create volume info
        info = VolumeInfo(
            name=volume_name,
            path=volume_path,
            mount_time=datetime.now(),
            video_files=videos,
            total_size_mb=self._get_volume_size(volume_path),
        )

        print(f"New volume detected: {volume_name}")
        print(f"  Videos found: {len(videos)}")
        print(f"  Total size: {info.total_size_mb:.1f} MB")

        # Call callback
        if self.callback:
            self.callback(info)

        # Auto-extract if enabled
        if self.auto_extract:
            if self.full_pipeline:
                self._run_full_pipeline(info)
            else:
                self._auto_extract_faces(info)

    def _auto_extract_faces(self, volume_info: VolumeInfo):
        """Automatically extract faces from volume videos (legacy method)."""
        from kagami_media.face_clusterer import FaceClusterer
        from kagami_media.face_extractor import FaceExtractor

        print(f"Starting automatic face extraction for {volume_info.name}...")

        extractor = FaceExtractor(sample_interval=2.0)
        all_faces = []

        for video_path in volume_info.video_files:
            print(f"  Processing: {os.path.basename(video_path)}")
            try:
                faces = extractor.extract_from_video(video_path)
                all_faces.extend(faces)
                print(f"    Found {len(faces)} faces")
            except Exception as e:
                print(f"    Error: {e}")

        if all_faces:
            print(f"Total faces extracted: {len(all_faces)}")

            # Cluster faces
            clusterer = FaceClusterer()
            clusters = clusterer.cluster(all_faces)

            print(f"Clustered into {len(clusters)} groups")

            # Save to temp location for review
            output_dir = f"/tmp/kagami_faces/{volume_info.name}"
            clusterer.save_clusters(clusters, output_dir)
            print(f"Saved clusters to: {output_dir}")

    def _run_full_pipeline(self, volume_info: VolumeInfo):
        """Run full identity extraction pipeline on volume.

        This is the comprehensive extraction that creates complete
        digital clone profiles for all detected people.
        """
        from kagami_media.pipeline import VideoIdentityPipeline

        print(f"\n{'=' * 60}")
        print("KAGAMI IDENTITY EXTRACTION PIPELINE")
        print(f"Volume: {volume_info.name}")
        print(f"Videos: {len(volume_info.video_files)}")
        print(f"{'=' * 60}\n")

        # Initialize pipeline
        pipeline = VideoIdentityPipeline(
            output_dir="assets/identities",
            sample_interval=0.5,
            enable_audio=True,
            enable_pose=True,
            enable_scene=True,
        )

        # Process callback
        def progress_callback(video_name: str, current: int, total: int):
            percent = (current / total) * 100 if total > 0 else 0
            print(f"[{percent:5.1f}%] Processing: {video_name}")

        # Process all videos
        try:
            results = pipeline.process_volume(
                volume_info.path,
                progress_callback=progress_callback,
            )

            # Print summary
            print(f"\n{'=' * 60}")
            print("EXTRACTION COMPLETE")
            print(f"{'=' * 60}")
            print(f"Videos processed: {len(results)}")

            total_persons = sum(r.person_count for r in results)
            total_faces = sum(r.face_count for r in results)
            total_speakers = sum(r.speaker_count for r in results)

            print(f"Total persons detected: {total_persons}")
            print(f"Total faces extracted: {total_faces}")
            print(f"Total speakers identified: {total_speakers}")

            errors = [e for r in results for e in r.errors]
            if errors:
                print(f"Errors encountered: {len(errors)}")
                for e in errors[:5]:
                    print(f"  - {e}")

            print("\nIdentities saved to: assets/identities/")
            print(f"{'=' * 60}\n")

        except Exception as e:
            print(f"Pipeline error: {e}")
            import traceback

            traceback.print_exc()

    def start(self, blocking: bool = False):
        """Start monitoring for new volumes.

        Args:
            blocking: If True, block the current thread
        """
        if self._running:
            return

        self._running = True

        if FSEVENTS_AVAILABLE:
            if blocking:
                self._run_fsevents()
            else:
                self._thread = threading.Thread(target=self._run_fsevents, daemon=True)
                self._thread.start()
        else:
            if blocking:
                self._run_polling()
            else:
                self._thread = threading.Thread(target=self._run_polling, daemon=True)
                self._thread.start()

    def stop(self):
        """Stop monitoring."""
        self._running = False

        if self._stream and FSEVENTS_AVAILABLE:
            FSEventStreamStop(self._stream)
            FSEventStreamInvalidate(self._stream)
            FSEventStreamRelease(self._stream)
            self._stream = None

    def _run_fsevents(self):
        """Run FSEvents-based monitoring (macOS)."""

        def event_callback(
            stream_ref, client_info, num_events, event_paths, event_flags, event_ids
        ):
            for i in range(num_events):
                path = event_paths[i]
                flags = event_flags[i]

                # Check if it's a new directory in /Volumes
                if (
                    flags & kFSEventStreamEventFlagItemCreated
                    and flags & kFSEventStreamEventFlagItemIsDir
                ):
                    # Extract volume name
                    if path.startswith(self.volumes_path):
                        parts = path[len(self.volumes_path) :].strip("/").split("/")
                        if len(parts) == 1:
                            volume_name = parts[0]
                            if volume_name not in self._known_volumes:
                                self._known_volumes.add(volume_name)
                                # Delay slightly to allow volume to fully mount
                                time.sleep(1)
                                self._on_volume_detected(volume_name)

        self._stream = FSEventStreamCreate(
            None,
            event_callback,
            None,
            [self.volumes_path],
            kFSEventStreamEventIdSinceNow,
            1.0,
            kFSEventStreamCreateFlagNone,
        )

        FSEventStreamScheduleWithRunLoop(
            self._stream,
            CFRunLoopGetCurrent(),
            kCFRunLoopDefaultMode,
        )
        FSEventStreamStart(self._stream)

        print(f"Monitoring {self.volumes_path} for new volumes (FSEvents)...")

        while self._running:
            CFRunLoopRun()

    def _run_polling(self):
        """Run polling-based monitoring (fallback)."""
        print(f"Monitoring {self.volumes_path} for new volumes (polling)...")

        while self._running:
            volumes_dir = Path(self.volumes_path)
            if volumes_dir.exists():
                current_volumes = {
                    item.name
                    for item in volumes_dir.iterdir()
                    if item.is_dir() and not item.name.startswith(".")
                }

                # Check for new volumes
                new_volumes = current_volumes - self._known_volumes
                for volume_name in new_volumes:
                    self._known_volumes.add(volume_name)
                    self._on_volume_detected(volume_name)

                # Update known volumes (handle removals)
                self._known_volumes = current_volumes

            time.sleep(2)  # Poll every 2 seconds


def start_monitor(
    callback: Callable[[VolumeInfo], None] | None = None,
    auto_extract: bool = False,
    blocking: bool = True,
) -> VolumeMonitor:
    """Start a volume monitor.

    Args:
        callback: Function to call on new volume
        auto_extract: Auto-start face extraction
        blocking: Block current thread

    Returns:
        VolumeMonitor instance
    """
    monitor = VolumeMonitor(callback=callback, auto_extract=auto_extract)
    monitor.start(blocking=blocking)
    return monitor


# CLI entry point
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Monitor for USB volumes with video content and extract identities"
    )
    parser.add_argument(
        "--auto-extract", action="store_true", help="Auto-extract identities when USB is inserted"
    )
    parser.add_argument(
        "--legacy",
        action="store_true",
        help="Use legacy face-only extraction instead of full pipeline",
    )
    parser.add_argument(
        "--process-now",
        type=str,
        metavar="PATH",
        help="Process a volume immediately without monitoring",
    )
    args = parser.parse_args()

    def on_volume(info: VolumeInfo):
        print(f"\n{'=' * 60}")
        print(f"NEW VOLUME DETECTED: {info.name}")
        print(f"Videos found: {len(info.video_files)}")
        print(f"Total size: {info.total_size_mb:.1f} MB")
        print(f"{'=' * 60}")
        for v in info.video_files[:10]:
            print(f"  - {os.path.basename(v)}")
        if len(info.video_files) > 10:
            print(f"  ... and {len(info.video_files) - 10} more")
        print()

    # Process existing volume immediately
    if args.process_now:
        from kagami_media.pipeline import VideoIdentityPipeline

        print(f"Processing volume: {args.process_now}")
        pipeline = VideoIdentityPipeline(output_dir="assets/identities")

        def progress(video_name, current, total):
            print(f"[{current + 1}/{total}] {video_name}")

        results = pipeline.process_volume(args.process_now, progress_callback=progress)

        print(f"\nProcessed {len(results)} videos")
        print(f"Total faces: {sum(r.face_count for r in results)}")
        print("Identities saved to: assets/identities/")
    else:
        # Start monitoring
        try:
            monitor = VolumeMonitor(
                callback=on_volume,
                auto_extract=args.auto_extract,
                full_pipeline=not args.legacy,
            )
            print("Kagami Identity Extraction Monitor")
            print("=" * 40)
            print(f"Auto-extract: {args.auto_extract}")
            print(f"Pipeline: {'Full' if not args.legacy else 'Legacy (face-only)'}")
            print("Waiting for USB drives with video content...")
            print("Press Ctrl+C to stop\n")

            monitor.start(blocking=True)
        except KeyboardInterrupt:
            print("\nStopped monitoring.")
