"""Google Drive Sync Service — Bidirectional sync between local storage and Google Drive.

Provides seamless synchronization between:
- Local USB drives (e.g., WesData family archive)
- Google Drive cloud storage via rclone

The sync is intelligent:
- Original videos stay on USB only (too large for cloud)
- Enhanced videos sync to cloud (for family sharing)
- Metadata, HTML, and profiles sync bidirectionally

Created: January 3, 2026
h(x) >= 0 always.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class SyncDirection(Enum):
    """Direction of synchronization."""

    UPLOAD = "upload"  # Local → Cloud
    DOWNLOAD = "download"  # Cloud → Local
    BIDIRECTIONAL = "bidirectional"  # Both ways


class SyncStatus(Enum):
    """Status of a sync operation."""

    IDLE = "idle"
    SYNCING = "syncing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class SyncConfig:
    """Configuration for a sync mapping."""

    name: str
    local_path: str
    remote_path: str  # rclone remote path (e.g., "gdrive:Folder/Path")
    direction: SyncDirection = SyncDirection.BIDIRECTIONAL

    # Filtering
    include_patterns: list[str] = field(default_factory=list)
    exclude_patterns: list[str] = field(default_factory=list)

    # Options
    delete_extra: bool = False  # Delete files not in source
    dry_run: bool = False

    # Size limits (bytes) - 0 means no limit
    max_file_size: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "local_path": self.local_path,
            "remote_path": self.remote_path,
            "direction": self.direction.value,
            "include_patterns": self.include_patterns,
            "exclude_patterns": self.exclude_patterns,
            "delete_extra": self.delete_extra,
            "max_file_size": self.max_file_size,
        }


@dataclass
class SyncResult:
    """Result of a sync operation."""

    success: bool
    files_transferred: int = 0
    bytes_transferred: int = 0
    errors: list[str] = field(default_factory=list)
    duration_seconds: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "files_transferred": self.files_transferred,
            "bytes_transferred": self.bytes_transferred,
            "errors": self.errors,
            "duration_seconds": self.duration_seconds,
        }


# =============================================================================
# Default Sync Configurations
# =============================================================================

# WesData Family Archive sync configuration
WESDATA_SYNC_CONFIGS = [
    # Enhanced videos → Cloud (family can access these)
    SyncConfig(
        name="enhanced_videos",
        local_path="/Volumes/WesData/enhanced",
        remote_path="gdrive:Jacoby Family Archive/enhanced",
        direction=SyncDirection.BIDIRECTIONAL,
        include_patterns=["*.mp4"],
    ),
    # HTML/Web files ↔ Cloud
    SyncConfig(
        name="web_interface",
        local_path="/Volumes/WesData",
        remote_path="gdrive:Jacoby Family Archive",
        direction=SyncDirection.BIDIRECTIONAL,
        include_patterns=["*.html", "*.txt"],
        exclude_patterns=["*.py", "*.pyc", ".cache/**"],
    ),
    # Character profiles ↔ Cloud
    SyncConfig(
        name="character_profiles",
        local_path="/Volumes/WesData/characters",
        remote_path="gdrive:Jacoby Family Archive/characters",
        direction=SyncDirection.BIDIRECTIONAL,
    ),
    # Metadata JSON files ↔ Cloud
    SyncConfig(
        name="metadata",
        local_path="/Volumes/WesData",
        remote_path="gdrive:Jacoby Family Archive/metadata",
        direction=SyncDirection.BIDIRECTIONAL,
        include_patterns=["*.json"],
        exclude_patterns=["inventory.json"],  # Too large, generated locally
    ),
]


# =============================================================================
# Google Drive Sync Service
# =============================================================================


class GDriveSyncService:
    """Google Drive synchronization service using rclone.

    Provides bidirectional sync between local storage and Google Drive,
    with intelligent filtering to avoid syncing large original videos.

    Usage:
        service = GDriveSyncService()
        await service.initialize()

        # Sync all configured mappings
        results = await service.sync_all()

        # Sync specific mapping
        result = await service.sync("enhanced_videos")

        # Check sync status
        status = service.get_status()
    """

    def __init__(
        self,
        configs: list[SyncConfig] | None = None,
        rclone_remote: str = "gdrive",
    ):
        """Initialize the sync service.

        Args:
            configs: List of sync configurations (uses defaults if None)
            rclone_remote: Name of the rclone remote for Google Drive
        """
        self._configs = {c.name: c for c in (configs or WESDATA_SYNC_CONFIGS)}
        self._rclone_remote = rclone_remote
        self._status = SyncStatus.IDLE
        self._last_sync: dict[str, SyncResult] = {}
        self._initialized = False

    async def initialize(self) -> bool:
        """Initialize the service and verify rclone configuration.

        Returns:
            True if initialization successful.
        """
        logger.info("Initializing GDriveSyncService...")

        # Check if rclone is available
        try:
            result = await self._run_rclone(["version"])
            if not result.success:
                logger.error("rclone not available")
                return False
        except Exception as e:
            logger.error(f"rclone check failed: {e}")
            return False

        # Check if Google Drive remote is configured
        try:
            result = await self._run_rclone(["listremotes"])
            remotes = (
                result.errors[0] if result.errors else ""
            )  # Output is in errors for listremotes

            # Check stdout from the command
            proc = await asyncio.create_subprocess_exec(
                "rclone",
                "listremotes",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            remotes = stdout.decode()

            if f"{self._rclone_remote}:" not in remotes:
                logger.warning(
                    f"rclone remote '{self._rclone_remote}' not configured. "
                    f"Run: rclone config create {self._rclone_remote} drive"
                )
                return False

        except Exception as e:
            logger.error(f"Failed to check rclone remotes: {e}")
            return False

        self._initialized = True
        logger.info(f"GDriveSyncService initialized with {len(self._configs)} sync configs")
        return True

    async def _run_rclone(
        self,
        args: list[str],
        timeout: float = 3600.0,
    ) -> SyncResult:
        """Run an rclone command.

        Args:
            args: Command arguments
            timeout: Timeout in seconds

        Returns:
            SyncResult with command output.
        """
        import time

        start_time = time.time()

        try:
            proc = await asyncio.create_subprocess_exec(
                "rclone",
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            _stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=timeout,
            )

            duration = time.time() - start_time
            success = proc.returncode == 0

            return SyncResult(
                success=success,
                errors=[stderr.decode()] if stderr else [],
                duration_seconds=duration,
            )

        except TimeoutError:
            return SyncResult(
                success=False,
                errors=[f"Command timed out after {timeout}s"],
                duration_seconds=timeout,
            )
        except Exception as e:
            return SyncResult(
                success=False,
                errors=[str(e)],
                duration_seconds=time.time() - start_time,
            )

    async def sync(
        self,
        config_name: str,
        direction: SyncDirection | None = None,
        dry_run: bool = False,
    ) -> SyncResult:
        """Sync a specific configuration.

        Args:
            config_name: Name of the sync configuration
            direction: Override sync direction
            dry_run: If True, only show what would be synced

        Returns:
            SyncResult with operation details.
        """
        config = self._configs.get(config_name)
        if not config:
            return SyncResult(
                success=False,
                errors=[f"Unknown sync config: {config_name}"],
            )

        # Check if local path exists
        local_path = Path(config.local_path)
        if not local_path.exists():
            return SyncResult(
                success=False,
                errors=[f"Local path does not exist: {config.local_path}"],
            )

        self._status = SyncStatus.SYNCING
        direction = direction or config.direction

        try:
            # Build rclone command
            if direction == SyncDirection.UPLOAD:
                result = await self._sync_upload(config, dry_run)
            elif direction == SyncDirection.DOWNLOAD:
                result = await self._sync_download(config, dry_run)
            else:
                # Bidirectional: upload then download (local wins on conflicts)
                upload_result = await self._sync_upload(config, dry_run)
                download_result = await self._sync_download(config, dry_run)

                result = SyncResult(
                    success=upload_result.success and download_result.success,
                    files_transferred=(
                        upload_result.files_transferred + download_result.files_transferred
                    ),
                    bytes_transferred=(
                        upload_result.bytes_transferred + download_result.bytes_transferred
                    ),
                    errors=upload_result.errors + download_result.errors,
                    duration_seconds=(
                        upload_result.duration_seconds + download_result.duration_seconds
                    ),
                )

            self._last_sync[config_name] = result
            self._status = SyncStatus.COMPLETED if result.success else SyncStatus.FAILED
            return result

        except Exception as e:
            result = SyncResult(success=False, errors=[str(e)])
            self._last_sync[config_name] = result
            self._status = SyncStatus.FAILED
            return result

    async def _sync_upload(
        self,
        config: SyncConfig,
        dry_run: bool = False,
    ) -> SyncResult:
        """Upload local files to Google Drive."""
        args = ["copy", config.local_path, config.remote_path]

        # Add filters
        for pattern in config.include_patterns:
            args.extend(["--include", pattern])
        for pattern in config.exclude_patterns:
            args.extend(["--exclude", pattern])

        if config.max_file_size > 0:
            args.extend(["--max-size", str(config.max_file_size)])

        if dry_run or config.dry_run:
            args.append("--dry-run")

        args.extend(["-v", "--stats", "0"])

        return await self._run_rclone(args)

    async def _sync_download(
        self,
        config: SyncConfig,
        dry_run: bool = False,
    ) -> SyncResult:
        """Download Google Drive files to local storage."""
        args = ["copy", config.remote_path, config.local_path]

        # Add filters
        for pattern in config.include_patterns:
            args.extend(["--include", pattern])
        for pattern in config.exclude_patterns:
            args.extend(["--exclude", pattern])

        if config.max_file_size > 0:
            args.extend(["--max-size", str(config.max_file_size)])

        if dry_run or config.dry_run:
            args.append("--dry-run")

        args.extend(["-v", "--stats", "0"])

        return await self._run_rclone(args)

    async def sync_all(
        self,
        dry_run: bool = False,
    ) -> dict[str, SyncResult]:
        """Sync all configured mappings.

        Args:
            dry_run: If True, only show what would be synced

        Returns:
            Dictionary of config name → SyncResult.
        """
        results = {}

        for name in self._configs:
            logger.info(f"Syncing: {name}")
            results[name] = await self.sync(name, dry_run=dry_run)

            if not results[name].success:
                logger.warning(f"Sync failed for {name}: {results[name].errors}")

        return results

    async def list_remote(
        self,
        path: str = "",
    ) -> list[dict[str, Any]]:
        """List files in Google Drive.

        Args:
            path: Path relative to the Jacoby Family Archive folder

        Returns:
            List of file/folder info dictionaries.
        """
        remote_path = f"{self._rclone_remote}:Jacoby Family Archive/{path}".rstrip("/")

        proc = await asyncio.create_subprocess_exec(
            "rclone",
            "lsjson",
            remote_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            logger.error(f"Failed to list remote: {stderr.decode()}")
            return []

        try:
            return json.loads(stdout.decode())
        except json.JSONDecodeError:
            return []

    async def get_remote_size(self) -> dict[str, Any]:
        """Get size information for the Google Drive archive.

        Returns:
            Size info dictionary.
        """
        proc = await asyncio.create_subprocess_exec(
            "rclone",
            "size",
            f"{self._rclone_remote}:Jacoby Family Archive",
            "--json",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            return {"error": stderr.decode()}

        try:
            return json.loads(stdout.decode())
        except json.JSONDecodeError:
            return {"error": "Failed to parse size output"}

    def get_status(self) -> dict[str, Any]:
        """Get service status.

        Returns:
            Status dictionary.
        """
        return {
            "initialized": self._initialized,
            "status": self._status.value,
            "rclone_remote": self._rclone_remote,
            "configs": list(self._configs.keys()),
            "last_sync": {name: result.to_dict() for name, result in self._last_sync.items()},
        }

    def get_configs(self) -> list[dict[str, Any]]:
        """Get all sync configurations.

        Returns:
            List of config dictionaries.
        """
        return [c.to_dict() for c in self._configs.values()]


# =============================================================================
# Singleton
# =============================================================================

_gdrive_sync: GDriveSyncService | None = None


def get_gdrive_sync() -> GDriveSyncService:
    """Get the global Google Drive sync service instance."""
    global _gdrive_sync
    if _gdrive_sync is None:
        _gdrive_sync = GDriveSyncService()
    return _gdrive_sync


async def initialize_gdrive_sync() -> GDriveSyncService:
    """Initialize and return the Google Drive sync service."""
    service = get_gdrive_sync()
    if not service._initialized:
        await service.initialize()
    return service


__all__ = [
    "WESDATA_SYNC_CONFIGS",
    "GDriveSyncService",
    "SyncConfig",
    "SyncDirection",
    "SyncResult",
    "SyncStatus",
    "get_gdrive_sync",
    "initialize_gdrive_sync",
]
