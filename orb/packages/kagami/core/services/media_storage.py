"""Media Storage Service — USB Drive + Google Drive Integration.

JACOBY FAMILY MEDIA ARCHIVE INTEGRATION.

This service provides unified access to:
1. Local USB drives (e.g., WesData containing family video archives)
2. Google Drive via rclone (bidirectional sync)
3. Local filesystem media directories

The WesData drive contains digitized VHS tapes from the Jacoby family (1985-1995),
with extracted character profiles, voice samples, and images.

Sync Strategy:
- Original videos: USB only (too large for cloud)
- Enhanced videos: Bidirectional sync to Google Drive
- Metadata/HTML: Bidirectional sync to Google Drive
- Character profiles: Bidirectional sync to Google Drive

Created: January 3, 2026
h(x) >= 0 always.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from kagami.core.services.gdrive_sync import GDriveSyncService

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================


class StorageType(Enum):
    """Types of media storage."""

    USB_DRIVE = "usb_drive"
    GOOGLE_DRIVE = "google_drive"
    LOCAL = "local"


@dataclass
class MediaDriveConfig:
    """Configuration for a media drive."""

    name: str
    storage_type: StorageType
    mount_path: str | None = None  # For USB/local
    drive_id: str | None = None  # For Google Drive
    read_only: bool = True
    enabled: bool = True

    # Metadata
    description: str = ""
    content_type: str = "mixed"  # video, audio, image, mixed


@dataclass
class MediaStorageConfig:
    """Configuration for media storage service."""

    # Default USB drives to scan
    usb_mount_paths: list[str] = field(
        default_factory=lambda: [
            "/Volumes/WesData",  # Jacoby family archive
            "/Volumes/MediaBackup",
        ]
    )

    # Local media directories
    local_paths: list[str] = field(
        default_factory=lambda: [
            str(Path.home() / "Movies"),
            str(Path.home() / "Music"),
            str(Path.home() / "Pictures"),
        ]
    )

    # Google Drive folders to sync
    gdrive_folders: list[str] = field(
        default_factory=lambda: [
            "Family Videos",
            "Photos",
        ]
    )

    # Enable Google Drive integration
    enable_gdrive: bool = True

    # Cache settings
    inventory_cache_ttl: int = 3600  # 1 hour


# =============================================================================
# Media Item Types
# =============================================================================


@dataclass
class MediaItem:
    """Represents a media file."""

    path: str
    name: str
    media_type: str  # video, audio, image
    size_bytes: int
    storage_type: StorageType
    drive_name: str

    # Optional metadata
    duration_seconds: float | None = None
    resolution: str | None = None
    created_at: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "path": self.path,
            "name": self.name,
            "media_type": self.media_type,
            "size_bytes": self.size_bytes,
            "storage_type": self.storage_type.value,
            "drive_name": self.drive_name,
            "duration_seconds": self.duration_seconds,
            "resolution": self.resolution,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }


@dataclass
class FamilyCharacter:
    """Represents a family member from the archive."""

    identity_id: str
    full_name: str
    role: str
    era: str
    age_range: str | None = None

    # Media references
    voice_samples_path: str | None = None
    images: list[str] = field(default_factory=list)
    video_appearances: list[str] = field(default_factory=list)

    # Profile
    personality_traits: list[str] = field(default_factory=list)
    key_quotes: list[str] = field(default_factory=list)
    relationships: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "identity_id": self.identity_id,
            "full_name": self.full_name,
            "role": self.role,
            "era": self.era,
            "age_range": self.age_range,
            "voice_samples_path": self.voice_samples_path,
            "images": self.images,
            "video_appearances": self.video_appearances,
            "personality_traits": self.personality_traits,
            "key_quotes": self.key_quotes,
            "relationships": self.relationships,
        }


# =============================================================================
# Media Storage Service
# =============================================================================


class MediaStorageService:
    """Unified media storage service for USB drives and Google Drive.

    Provides access to:
    - WesData USB drive (Jacoby family video archive)
    - Google Drive via Composio
    - Local media directories

    Usage:
        service = MediaStorageService()
        await service.initialize()

        # List available drives
        drives = service.list_drives()

        # Get media inventory
        items = await service.get_media_inventory("WesData")

        # Get family characters from archive
        characters = await service.get_family_characters()
    """

    def __init__(self, config: MediaStorageConfig | None = None):
        """Initialize media storage service."""
        self._config = config or MediaStorageConfig()
        self._drives: dict[str, MediaDriveConfig] = {}
        self._inventory_cache: dict[str, tuple[float, list[MediaItem]]] = {}
        self._family_characters: dict[str, FamilyCharacter] = {}
        self._gdrive_sync: GDriveSyncService | None = None
        self._initialized = False

    async def initialize(self) -> bool:
        """Initialize the service and discover available drives."""
        logger.info("Initializing MediaStorageService...")

        # Discover USB drives
        await self._discover_usb_drives()

        # Discover local directories
        self._discover_local_paths()

        # Initialize Google Drive sync via rclone
        if self._config.enable_gdrive:
            await self._init_gdrive_sync()

        # Load family characters from WesData if available
        await self._load_family_characters()

        self._initialized = True
        logger.info(
            f"MediaStorageService initialized with {len(self._drives)} drives, "
            f"{len(self._family_characters)} family characters"
        )
        return True

    async def _discover_usb_drives(self) -> None:
        """Discover mounted USB drives."""
        for mount_path in self._config.usb_mount_paths:
            path = Path(mount_path)
            if path.exists() and path.is_dir():
                drive_name = path.name
                self._drives[drive_name] = MediaDriveConfig(
                    name=drive_name,
                    storage_type=StorageType.USB_DRIVE,
                    mount_path=str(path),
                    description=f"USB drive at {mount_path}",
                )
                logger.info(f"Discovered USB drive: {drive_name} at {mount_path}")

    def _discover_local_paths(self) -> None:
        """Discover local media directories."""
        for local_path in self._config.local_paths:
            path = Path(local_path)
            if path.exists() and path.is_dir():
                dir_name = f"Local_{path.name}"
                self._drives[dir_name] = MediaDriveConfig(
                    name=dir_name,
                    storage_type=StorageType.LOCAL,
                    mount_path=str(path),
                    description=f"Local directory: {local_path}",
                )

    async def _init_gdrive_sync(self) -> None:
        """Initialize Google Drive sync via rclone."""
        try:
            from kagami.core.services.gdrive_sync import get_gdrive_sync

            self._gdrive_sync = get_gdrive_sync()
            initialized = await self._gdrive_sync.initialize()

            if initialized:
                self._drives["GoogleDrive"] = MediaDriveConfig(
                    name="GoogleDrive",
                    storage_type=StorageType.GOOGLE_DRIVE,
                    description="Google Drive via rclone (Jacoby Family Archive)",
                    content_type="mixed",
                )
                logger.info("Google Drive connected via rclone")
            else:
                logger.info("Google Drive not configured in rclone")

        except Exception as e:
            logger.warning(f"Failed to initialize Google Drive sync: {e}")

    async def _load_family_characters(self) -> None:
        """Load family characters from WesData drive."""
        wesdata = self._drives.get("WesData")
        if not wesdata or not wesdata.mount_path:
            return

        # Try to load family_profiles.json
        profiles_path = Path(wesdata.mount_path) / "characters" / "family_profiles.json"
        if not profiles_path.exists():
            logger.debug(f"No family profiles found at {profiles_path}")
            return

        try:
            with open(profiles_path) as f:
                data = json.load(f)

            for char_id, char_data in data.get("characters", {}).items():
                self._family_characters[char_id] = FamilyCharacter(
                    identity_id=f"{char_id}_jacoby",
                    full_name=char_data.get("full_name", char_id),
                    role=char_data.get("role", "unknown"),
                    era=data.get("estimated_video_era", "1985-1995"),
                    age_range=char_data.get("estimated_birth_year"),
                    voice_samples_path=char_data.get("voice_samples"),
                    images=char_data.get("images", []),
                    video_appearances=char_data.get("video_appearances", []),
                    personality_traits=char_data.get("personality_traits", []),
                    key_quotes=char_data.get("key_quotes", []),
                    relationships=char_data.get("relationships", {}),
                )

            logger.info(
                f"Loaded {len(self._family_characters)} family characters "
                f"from {data.get('family_name', 'Unknown')} archive"
            )

        except Exception as e:
            logger.warning(f"Failed to load family profiles: {e}")

    # =========================================================================
    # Public API
    # =========================================================================

    def list_drives(self) -> list[dict[str, Any]]:
        """List all available media drives.

        Returns:
            List of drive configurations.
        """
        return [
            {
                "name": drive.name,
                "type": drive.storage_type.value,
                "path": drive.mount_path,
                "description": drive.description,
                "enabled": drive.enabled,
            }
            for drive in self._drives.values()
        ]

    def get_drive(self, name: str) -> MediaDriveConfig | None:
        """Get a specific drive by name."""
        return self._drives.get(name)

    async def get_media_inventory(
        self,
        drive_name: str,
        media_type: str | None = None,
        use_cache: bool = True,
    ) -> list[MediaItem]:
        """Get media inventory for a drive.

        Args:
            drive_name: Name of the drive
            media_type: Filter by type (video, audio, image)
            use_cache: Whether to use cached inventory

        Returns:
            List of media items.
        """
        drive = self._drives.get(drive_name)
        if not drive:
            logger.warning(f"Drive not found: {drive_name}")
            return []

        # Check cache
        import time

        if use_cache and drive_name in self._inventory_cache:
            cache_time, items = self._inventory_cache[drive_name]
            if time.time() - cache_time < self._config.inventory_cache_ttl:
                if media_type:
                    return [i for i in items if i.media_type == media_type]
                return items

        # Build inventory based on storage type
        if drive.storage_type == StorageType.GOOGLE_DRIVE:
            items = await self._get_gdrive_inventory(drive)
        else:
            items = self._get_local_inventory(drive)

        # Cache
        self._inventory_cache[drive_name] = (time.time(), items)

        if media_type:
            return [i for i in items if i.media_type == media_type]
        return items

    def _get_local_inventory(self, drive: MediaDriveConfig) -> list[MediaItem]:
        """Get inventory from local/USB drive."""
        if not drive.mount_path:
            return []

        items: list[MediaItem] = []
        root = Path(drive.mount_path)

        # Media file extensions
        video_ext = {".mp4", ".mov", ".avi", ".mkv", ".m4v", ".wmv"}
        audio_ext = {".mp3", ".wav", ".flac", ".m4a", ".aac", ".ogg"}
        image_ext = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".webp"}

        for path in root.rglob("*"):
            if path.is_file() and not path.name.startswith("."):
                ext = path.suffix.lower()

                if ext in video_ext:
                    media_type = "video"
                elif ext in audio_ext:
                    media_type = "audio"
                elif ext in image_ext:
                    media_type = "image"
                else:
                    continue

                try:
                    stat = path.stat()
                    items.append(
                        MediaItem(
                            path=str(path),
                            name=path.name,
                            media_type=media_type,
                            size_bytes=stat.st_size,
                            storage_type=drive.storage_type,
                            drive_name=drive.name,
                            created_at=str(stat.st_mtime),
                        )
                    )
                except OSError:
                    continue

        return items

    async def _get_gdrive_inventory(self, drive: MediaDriveConfig) -> list[MediaItem]:
        """Get inventory from Google Drive via rclone."""
        if not self._gdrive_sync:
            return []

        items: list[MediaItem] = []

        try:
            # List files from Google Drive using rclone
            files = await self._gdrive_sync.list_remote()

            # Media file extensions
            video_ext = {".mp4", ".mov", ".avi", ".mkv", ".m4v", ".wmv"}
            audio_ext = {".mp3", ".wav", ".flac", ".m4a", ".aac", ".ogg"}
            image_ext = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".webp"}

            for f in files:
                name = f.get("Name", "")
                ext = Path(name).suffix.lower()

                if ext in video_ext:
                    media_type = "video"
                elif ext in audio_ext:
                    media_type = "audio"
                elif ext in image_ext:
                    media_type = "image"
                else:
                    continue

                items.append(
                    MediaItem(
                        path=f.get("Path", name),
                        name=name,
                        media_type=media_type,
                        size_bytes=int(f.get("Size", 0)),
                        storage_type=StorageType.GOOGLE_DRIVE,
                        drive_name=drive.name,
                        created_at=f.get("ModTime"),
                        metadata={"is_dir": f.get("IsDir", False)},
                    )
                )

        except Exception as e:
            logger.warning(f"Failed to get Google Drive inventory: {e}")

        return items

    # =========================================================================
    # Family Archive API
    # =========================================================================

    def get_family_characters(self) -> list[FamilyCharacter]:
        """Get all family characters from the archive.

        Returns:
            List of family characters.
        """
        return list(self._family_characters.values())

    def get_family_character(self, identity_id: str) -> FamilyCharacter | None:
        """Get a specific family character.

        Args:
            identity_id: Character identity ID (e.g., 'tim', 'kristi')

        Returns:
            FamilyCharacter or None.
        """
        # Try direct lookup
        if identity_id in self._family_characters:
            return self._family_characters[identity_id]

        # Try without _jacoby suffix
        short_id = identity_id.replace("_jacoby", "")
        return self._family_characters.get(short_id)

    async def get_video_info(
        self,
        video_name: str,
        drive_name: str = "WesData",
    ) -> dict[str, Any] | None:
        """Get detailed info about a video from the archive.

        Args:
            video_name: Name of the video (e.g., "Easter", "Tape04")
            drive_name: Name of the drive

        Returns:
            Video metadata or None.
        """
        drive = self._drives.get(drive_name)
        if not drive or not drive.mount_path:
            return None

        # Check knowledge_base.json
        kb_path = Path(drive.mount_path) / "knowledge_base.json"
        if kb_path.exists():
            try:
                with open(kb_path) as f:
                    data = json.load(f)

                for video in data.get("videos", []):
                    if video.get("name") == video_name:
                        return video

            except Exception as e:
                logger.warning(f"Failed to read knowledge base: {e}")

        return None

    async def get_scene_database(
        self,
        drive_name: str = "WesData",
    ) -> dict[str, Any] | None:
        """Get the scene database from the archive.

        Args:
            drive_name: Name of the drive

        Returns:
            Scene database or None.
        """
        drive = self._drives.get(drive_name)
        if not drive or not drive.mount_path:
            return None

        scene_path = Path(drive.mount_path) / "scene_database.json"
        if scene_path.exists():
            try:
                with open(scene_path) as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to read scene database: {e}")

        return None

    async def sync_to_google_drive(
        self,
        source_path: str | None = None,
        config_name: str | None = None,
    ) -> dict[str, Any]:
        """Sync files to Google Drive.

        Can sync a specific file or use a predefined sync config.

        Args:
            source_path: Local file/folder path to upload
            config_name: Name of sync config (e.g., "enhanced_videos")

        Returns:
            Sync result.
        """
        if not self._gdrive_sync:
            return {"success": False, "error": "Google Drive not connected"}

        try:
            if config_name:
                # Use predefined sync config
                result = await self._gdrive_sync.sync(config_name)
                return result.to_dict()

            elif source_path:
                # Ad-hoc upload using rclone copy
                import asyncio

                source = Path(source_path)
                if not source.exists():
                    return {"success": False, "error": f"Path not found: {source_path}"}

                # Determine destination based on file type
                if source.suffix == ".mp4" and "enhanced" in str(source):
                    dest = "gdrive:Jacoby Family Archive/enhanced/"
                elif source.suffix in (".html", ".txt"):
                    dest = "gdrive:Jacoby Family Archive/"
                elif source.suffix == ".json":
                    dest = "gdrive:Jacoby Family Archive/metadata/"
                else:
                    dest = "gdrive:Jacoby Family Archive/"

                proc = await asyncio.create_subprocess_exec(
                    "rclone",
                    "copy",
                    str(source),
                    dest,
                    "-v",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                _, stderr = await proc.communicate()

                return {
                    "success": proc.returncode == 0,
                    "destination": dest,
                    "error": stderr.decode() if proc.returncode != 0 else None,
                }

            else:
                return {"success": False, "error": "No source_path or config_name provided"}

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def sync_all_to_google_drive(self) -> dict[str, Any]:
        """Sync all WesData delta files to Google Drive.

        Returns:
            Dictionary of sync results by config name.
        """
        if not self._gdrive_sync:
            return {"success": False, "error": "Google Drive not connected"}

        results = await self._gdrive_sync.sync_all()
        return {name: result.to_dict() for name, result in results.items()}

    def get_status(self) -> dict[str, Any]:
        """Get service status.

        Returns:
            Status dictionary.
        """
        gdrive_status = None
        if self._gdrive_sync:
            gdrive_status = self._gdrive_sync.get_status()

        return {
            "initialized": self._initialized,
            "drives_count": len(self._drives),
            "drives": list(self._drives.keys()),
            "family_characters_count": len(self._family_characters),
            "family_characters": [c.identity_id for c in self._family_characters.values()],
            "gdrive_connected": "GoogleDrive" in self._drives,
            "gdrive_sync": gdrive_status,
        }


# =============================================================================
# Singleton
# =============================================================================

_media_storage: MediaStorageService | None = None


def get_media_storage() -> MediaStorageService:
    """Get the global media storage service instance."""
    global _media_storage
    if _media_storage is None:
        _media_storage = MediaStorageService()
    return _media_storage


async def initialize_media_storage() -> MediaStorageService:
    """Initialize and return the media storage service."""
    service = get_media_storage()
    if not service._initialized:
        await service.initialize()
    return service


__all__ = [
    "FamilyCharacter",
    "MediaDriveConfig",
    "MediaItem",
    "MediaStorageConfig",
    "MediaStorageService",
    "StorageType",
    "get_media_storage",
    "initialize_media_storage",
]
