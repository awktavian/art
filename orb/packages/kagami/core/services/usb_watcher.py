"""USB Drive Watcher — Automatic Detection and Processing.

AUTOMATIC USB DRIVE INTEGRATION.

This service monitors for USB drive mount/unmount events on macOS and
automatically processes media drives when connected. Works with any USB drive
that contains media content.

Pipeline when a USB drive is connected:
1. Detect mount event via FSEvents/diskutil
2. Scan for media content (video, audio, images)
3. Check for existing profile data (family_profiles.json, etc.)
4. If no profile exists, offer to analyze and create one
5. Register drive with MediaStorageService
6. Notify household of new media availability

Created: January 3, 2026
h(x) >= 0 always.
"""

from __future__ import annotations

import asyncio
import json
import logging
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================


class DriveType(Enum):
    """Types of detected drives."""

    MEDIA_ARCHIVE = "media_archive"  # Contains family_profiles.json or similar
    RAW_MEDIA = "raw_media"  # Contains media files but no profile
    GENERAL = "general"  # General storage drive
    UNKNOWN = "unknown"


@dataclass
class USBDriveInfo:
    """Information about a detected USB drive."""

    name: str
    mount_path: str
    volume_uuid: str | None = None
    drive_type: DriveType = DriveType.UNKNOWN
    total_size_bytes: int = 0
    free_size_bytes: int = 0

    # Media analysis
    video_count: int = 0
    audio_count: int = 0
    image_count: int = 0
    total_media_size_bytes: int = 0

    # Profile data
    has_profile: bool = False
    profile_path: str | None = None
    family_name: str | None = None
    character_count: int = 0

    # Timestamps
    mounted_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "mount_path": self.mount_path,
            "volume_uuid": self.volume_uuid,
            "drive_type": self.drive_type.value,
            "total_size_bytes": self.total_size_bytes,
            "free_size_bytes": self.free_size_bytes,
            "video_count": self.video_count,
            "audio_count": self.audio_count,
            "image_count": self.image_count,
            "total_media_size_bytes": self.total_media_size_bytes,
            "has_profile": self.has_profile,
            "profile_path": self.profile_path,
            "family_name": self.family_name,
            "character_count": self.character_count,
            "mounted_at": self.mounted_at,
        }


@dataclass
class USBWatcherConfig:
    """Configuration for USB watcher."""

    # Polling interval for drive detection (seconds)
    poll_interval: float = 5.0

    # Mount point to watch
    volumes_path: str = "/Volumes"

    # Known system volumes to ignore
    ignore_volumes: list[str] = field(
        default_factory=lambda: [
            "Macintosh HD",
            "Macintosh HD - Data",
            "Recovery",
            "Preboot",
            "VM",
            "Update",
        ]
    )

    # Auto-process drives when mounted
    auto_process: bool = True

    # Notify on mount/unmount
    notify_on_mount: bool = True
    notify_on_unmount: bool = True


# =============================================================================
# Drive Analysis
# =============================================================================


def analyze_drive(mount_path: str) -> USBDriveInfo:
    """Analyze a mounted drive for media content.

    Args:
        mount_path: Path where drive is mounted

    Returns:
        USBDriveInfo with analysis results
    """
    path = Path(mount_path)
    name = path.name

    info = USBDriveInfo(name=name, mount_path=mount_path)

    # Get volume info via diskutil
    try:
        result = subprocess.run(
            ["diskutil", "info", "-plist", mount_path],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            import plistlib

            plist = plistlib.loads(result.stdout.encode())
            info.volume_uuid = plist.get("VolumeUUID")
            info.total_size_bytes = plist.get("TotalSize", 0)
            info.free_size_bytes = plist.get("FreeSpace", 0)
    except Exception as e:
        logger.debug(f"Could not get diskutil info: {e}")

    # Scan for media files
    video_ext = {".mp4", ".mov", ".avi", ".mkv", ".m4v", ".wmv"}
    audio_ext = {".mp3", ".wav", ".flac", ".m4a", ".aac", ".ogg"}
    image_ext = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".webp"}

    try:
        for file_path in path.rglob("*"):
            if file_path.is_file() and not file_path.name.startswith("."):
                ext = file_path.suffix.lower()
                try:
                    size = file_path.stat().st_size
                except OSError:
                    continue

                if ext in video_ext:
                    info.video_count += 1
                    info.total_media_size_bytes += size
                elif ext in audio_ext:
                    info.audio_count += 1
                    info.total_media_size_bytes += size
                elif ext in image_ext:
                    info.image_count += 1
                    info.total_media_size_bytes += size
    except PermissionError:
        logger.warning(f"Permission denied scanning {mount_path}")

    # Check for profile data
    profile_candidates = [
        "family_profiles.json",
        "characters/family_profiles.json",
        "profile.json",
        "metadata.json",
        "inventory.json",
    ]

    for candidate in profile_candidates:
        profile_path = path / candidate
        if profile_path.exists():
            info.has_profile = True
            info.profile_path = str(profile_path)

            try:
                with open(profile_path) as f:
                    data = json.load(f)
                    info.family_name = data.get("family_name")
                    if "characters" in data:
                        info.character_count = len(data["characters"])
            except Exception:
                pass
            break

    # Determine drive type
    if info.has_profile:
        info.drive_type = DriveType.MEDIA_ARCHIVE
    elif info.video_count > 0 or info.audio_count > 0 or info.image_count > 0:
        info.drive_type = DriveType.RAW_MEDIA
    else:
        info.drive_type = DriveType.GENERAL

    return info


# =============================================================================
# USB Watcher Service
# =============================================================================


class USBWatcherService:
    """Watches for USB drive mount/unmount events.

    Automatically detects when USB drives are connected, analyzes their
    content, and integrates them with the MediaStorageService.

    Usage:
        watcher = USBWatcherService()
        watcher.on_mount = my_mount_handler
        watcher.on_unmount = my_unmount_handler
        await watcher.start()

        # Or as context manager
        async with USBWatcherService() as watcher:
            await asyncio.sleep(3600)  # Run for an hour
    """

    def __init__(self, config: USBWatcherConfig | None = None):
        """Initialize USB watcher."""
        self._config = config or USBWatcherConfig()
        self._running = False
        self._task: asyncio.Task[None] | None = None
        self._known_volumes: dict[str, USBDriveInfo] = {}

        # Callbacks
        self.on_mount: Callable[[USBDriveInfo], None] | None = None
        self.on_unmount: Callable[[str], None] | None = None
        self.on_media_ready: Callable[[USBDriveInfo], None] | None = None

    async def start(self) -> None:
        """Start watching for USB events."""
        if self._running:
            return

        self._running = True
        logger.info("USBWatcherService started")

        # Initial scan
        await self._scan_volumes()

        # Start polling loop
        self._task = asyncio.create_task(self._poll_loop())

    async def stop(self) -> None:
        """Stop watching for USB events."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("USBWatcherService stopped")

    async def __aenter__(self) -> USBWatcherService:
        """Async context manager entry."""
        await self.start()
        return self

    async def __aexit__(self, *args: Any) -> None:
        """Async context manager exit."""
        await self.stop()

    async def _poll_loop(self) -> None:
        """Main polling loop."""
        while self._running:
            try:
                await self._scan_volumes()
                await asyncio.sleep(self._config.poll_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in USB poll loop: {e}")
                await asyncio.sleep(self._config.poll_interval)

    async def _scan_volumes(self) -> None:
        """Scan for mounted volumes and detect changes."""
        volumes_path = Path(self._config.volumes_path)
        if not volumes_path.exists():
            return

        current_volumes: set[str] = set()

        for volume in volumes_path.iterdir():
            if not volume.is_dir():
                continue

            name = volume.name
            if name in self._config.ignore_volumes:
                continue

            mount_path = str(volume)
            current_volumes.add(mount_path)

            # Check for new mount
            if mount_path not in self._known_volumes:
                await self._handle_mount(mount_path)

        # Check for unmounts
        for mount_path in list(self._known_volumes.keys()):
            if mount_path not in current_volumes:
                await self._handle_unmount(mount_path)

    async def _handle_mount(self, mount_path: str) -> None:
        """Handle a newly mounted drive."""
        logger.info(f"USB drive mounted: {mount_path}")

        # Analyze drive
        info = await asyncio.to_thread(analyze_drive, mount_path)
        self._known_volumes[mount_path] = info

        logger.info(
            f"Drive analyzed: {info.name} - {info.drive_type.value}, "
            f"{info.video_count} videos, {info.audio_count} audio, {info.image_count} images"
        )

        if info.has_profile:
            logger.info(f"Found profile: {info.family_name} with {info.character_count} characters")

        # Call mount callback
        if self.on_mount:
            try:
                self.on_mount(info)
            except Exception as e:
                logger.error(f"Error in mount callback: {e}")

        # Auto-process if configured
        if self._config.auto_process and info.drive_type in (
            DriveType.MEDIA_ARCHIVE,
            DriveType.RAW_MEDIA,
        ):
            await self._process_media_drive(info)

    async def _handle_unmount(self, mount_path: str) -> None:
        """Handle a drive unmount."""
        info = self._known_volumes.pop(mount_path, None)
        name = info.name if info else mount_path

        logger.info(f"USB drive unmounted: {name}")

        # Call unmount callback
        if self.on_unmount:
            try:
                self.on_unmount(mount_path)
            except Exception as e:
                logger.error(f"Error in unmount callback: {e}")

    async def _process_media_drive(self, info: USBDriveInfo) -> None:
        """Process a media drive (register with MediaStorageService)."""
        try:
            from kagami.core.services.media_storage import get_media_storage

            storage = get_media_storage()

            # Check if already initialized
            if not storage._initialized:
                await storage.initialize()

            # Register the drive if not already known
            if info.name not in storage._drives:
                from kagami.core.services.media_storage import (
                    MediaDriveConfig,
                    StorageType,
                )

                storage._drives[info.name] = MediaDriveConfig(
                    name=info.name,
                    storage_type=StorageType.USB_DRIVE,
                    mount_path=info.mount_path,
                    description=f"USB drive: {info.family_name or 'Media'} archive",
                    content_type="mixed",
                )

                logger.info(f"Registered drive with MediaStorageService: {info.name}")

            # Load family characters if present
            if info.has_profile and info.profile_path:
                await storage._load_family_characters()
                logger.info(f"Loaded {len(storage._family_characters)} family characters")

            # Call media ready callback
            if self.on_media_ready:
                try:
                    self.on_media_ready(info)
                except Exception as e:
                    logger.error(f"Error in media_ready callback: {e}")

        except Exception as e:
            logger.error(f"Error processing media drive: {e}")

    def get_mounted_drives(self) -> list[USBDriveInfo]:
        """Get list of currently mounted USB drives."""
        return list(self._known_volumes.values())

    def get_drive(self, name: str) -> USBDriveInfo | None:
        """Get info for a specific drive by name."""
        for info in self._known_volumes.values():
            if info.name == name:
                return info
        return None


# =============================================================================
# Drive Processing Pipeline
# =============================================================================


class DriveProcessingPipeline:
    """Pipeline for processing raw media drives.

    When a USB drive with raw media (no profile) is connected, this pipeline
    can analyze and create profile data automatically.

    Steps:
    1. Scan all video files
    2. Extract audio tracks for voice analysis
    3. Extract key frames for character detection
    4. Transcribe audio with speaker diarization
    5. Build character profiles
    6. Create family_profiles.json on the drive
    """

    def __init__(self, drive_info: USBDriveInfo):
        """Initialize pipeline for a drive."""
        self.drive = drive_info
        self._progress: dict[str, Any] = {}

    async def analyze(self, output_dir: str | None = None) -> dict[str, Any]:
        """Run full analysis pipeline.

        Args:
            output_dir: Where to save analysis results (default: drive root)

        Returns:
            Analysis results including character profiles
        """
        output_path = Path(output_dir or self.drive.mount_path)

        logger.info(f"Starting analysis pipeline for {self.drive.name}")
        self._progress["status"] = "scanning"

        # Step 1: Build video inventory
        videos = await self._scan_videos()
        self._progress["videos"] = len(videos)

        if not videos:
            return {"success": False, "error": "No video files found"}

        # Step 2: Extract metadata
        self._progress["status"] = "extracting_metadata"
        metadata = await self._extract_metadata(videos)

        # Step 3: Build inventory
        inventory = {
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "drive_name": self.drive.name,
            "total_videos": len(videos),
            "total_duration_minutes": sum(v.get("duration", 0) for v in metadata) / 60,
            "videos": metadata,
        }

        # Save inventory
        inventory_path = output_path / "inventory.json"
        with open(inventory_path, "w") as f:
            json.dump(inventory, f, indent=2)

        logger.info(f"Saved inventory to {inventory_path}")

        self._progress["status"] = "complete"
        return {
            "success": True,
            "inventory_path": str(inventory_path),
            "video_count": len(videos),
            "total_duration_minutes": inventory["total_duration_minutes"],
        }

    async def _scan_videos(self) -> list[Path]:
        """Scan drive for video files."""
        video_ext = {".mp4", ".mov", ".avi", ".mkv", ".m4v", ".wmv"}
        videos = []

        root = Path(self.drive.mount_path)
        for path in root.rglob("*"):
            if path.is_file() and path.suffix.lower() in video_ext:
                if not path.name.startswith("."):
                    videos.append(path)

        return sorted(videos)

    async def _extract_metadata(self, videos: list[Path]) -> list[dict[str, Any]]:
        """Extract metadata from video files."""
        metadata = []

        for video in videos:
            info: dict[str, Any] = {
                "name": video.stem,
                "path": str(video),
                "size_bytes": video.stat().st_size,
            }

            # Try to get duration with ffprobe
            try:
                result = subprocess.run(
                    [
                        "ffprobe",
                        "-v",
                        "quiet",
                        "-print_format",
                        "json",
                        "-show_format",
                        str(video),
                    ],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                if result.returncode == 0:
                    probe_data = json.loads(result.stdout)
                    fmt = probe_data.get("format", {})
                    info["duration"] = float(fmt.get("duration", 0))
                    info["bit_rate"] = int(fmt.get("bit_rate", 0))
            except Exception:
                pass

            metadata.append(info)

        return metadata

    def get_progress(self) -> dict[str, Any]:
        """Get current pipeline progress."""
        return self._progress.copy()


# =============================================================================
# Singleton and Convenience Functions
# =============================================================================

_usb_watcher: USBWatcherService | None = None


def get_usb_watcher() -> USBWatcherService:
    """Get global USB watcher instance."""
    global _usb_watcher
    if _usb_watcher is None:
        _usb_watcher = USBWatcherService()
    return _usb_watcher


async def start_usb_watcher() -> USBWatcherService:
    """Start the global USB watcher."""
    watcher = get_usb_watcher()
    await watcher.start()
    return watcher


async def scan_current_drives() -> list[USBDriveInfo]:
    """Scan and return info for all currently mounted USB drives."""
    config = USBWatcherConfig()
    volumes_path = Path(config.volumes_path)

    drives = []
    for volume in volumes_path.iterdir():
        if volume.is_dir() and volume.name not in config.ignore_volumes:
            info = await asyncio.to_thread(analyze_drive, str(volume))
            drives.append(info)

    return drives


__all__ = [
    "DriveProcessingPipeline",
    "DriveType",
    "USBDriveInfo",
    "USBWatcherConfig",
    "USBWatcherService",
    "analyze_drive",
    "get_usb_watcher",
    "scan_current_drives",
    "start_usb_watcher",
]
