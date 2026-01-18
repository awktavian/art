"""Audio Asset Store — Centralized earcon asset management with CDN delivery.

This module provides:
- Local caching of rendered earcons
- CDN delivery for extended earcons (Tier 2)
- Metadata index for quick lookup
- Format selection based on platform
- Async loading with progress tracking

Usage:
    from kagami.core.audio.asset_store import get_audio_asset_store

    store = await get_audio_asset_store()

    # Get audio file path (downloads if needed)
    path = await store.get_earcon("notification", format="aac")

    # Preload tier 1 earcons
    await store.preload_tier_1()

    # Get earcon metadata
    meta = store.get_metadata("success")

CDN Structure:
    gs://kagami-media-public/earcons/v1/
    ├── metadata.json
    ├── wav/{name}.wav
    ├── mp3/{name}.mp3
    └── aac/{name}.m4a

Local Cache:
    ~/.kagami/earcons/
    └── (same structure as CDN)

Created: January 12, 2026
Colony: 🔗 Nexus
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING

import aiohttp

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


# ============================================================================
# Constants
# ============================================================================

LOCAL_CACHE_DIR = Path.home() / ".kagami" / "earcons"
CDN_BASE_URL = "https://storage.googleapis.com/kagami-media-public/earcons/v1"

# Tier 1 earcons - bundled with apps for instant playback
TIER_1_EARCONS = frozenset(
    [
        "notification",
        "success",
        "error",
        "alert",
        "arrival",
        "departure",
        "celebration",
        "settling",
        "awakening",
        "cinematic",
        "focus",
        "security_arm",
        "package",
        "meeting_soon",
    ]
)


class AudioFormat(Enum):
    """Supported audio formats."""

    WAV = "wav"  # Archival (48kHz, 24-bit, ~5MB per earcon)
    MP3 = "mp3"  # Android/Web (320kbps, ~200KB per earcon)
    AAC = "aac"  # iOS/visionOS (256kbps, ~150KB per earcon)


@dataclass
class EarconAssetMetadata:
    """Metadata for a single earcon asset."""

    name: str
    duration_sec: float
    intent: str
    description: str
    leitmotif: str
    character: str
    tags: list[str]
    tier: int
    spatial_motion: str
    file_sizes: dict[str, int] = field(default_factory=dict)

    @property
    def is_tier_1(self) -> bool:
        """Check if this is a Tier 1 (core) earcon."""
        return self.tier == 1


# ============================================================================
# Audio Asset Store
# ============================================================================


class AudioAssetStore:
    """Centralized audio asset store with local cache and CDN fallback.

    Provides:
    - Automatic format selection based on platform
    - Local caching with lazy download
    - Tier 1 preloading for instant playback
    - Async download with progress callbacks
    - Metadata index for all earcons

    Thread-safe via asyncio locks.
    """

    def __init__(self) -> None:
        self._initialized = False
        self._metadata: dict[str, EarconAssetMetadata] = {}
        self._download_lock = asyncio.Lock()
        self._session: aiohttp.ClientSession | None = None

    async def initialize(self) -> bool:
        """Initialize the asset store.

        Loads metadata from local cache or CDN.

        Returns:
            True if initialization succeeded
        """
        if self._initialized:
            return True

        # Ensure cache directory exists
        LOCAL_CACHE_DIR.mkdir(parents=True, exist_ok=True)

        # Try to load local metadata first
        local_metadata = LOCAL_CACHE_DIR / "metadata.json"
        if local_metadata.exists():
            try:
                await self._load_metadata_from_file(local_metadata)
                logger.info(
                    "Loaded earcon metadata from local cache (%d earcons)", len(self._metadata)
                )
                self._initialized = True
                return True
            except Exception as e:
                logger.warning("Failed to load local metadata: %s", e)

        # Fall back to CDN
        try:
            await self._load_metadata_from_cdn()
            logger.info("Loaded earcon metadata from CDN (%d earcons)", len(self._metadata))
            self._initialized = True
            return True
        except Exception as e:
            logger.warning("Failed to load CDN metadata: %s", e)

        # If both fail, create empty metadata (render script will populate)
        logger.warning("No earcon metadata available - run render_all_earcons.py first")
        self._initialized = True
        return True

    async def _load_metadata_from_file(self, path: Path) -> None:
        """Load metadata from a local JSON file."""
        with open(path) as f:
            data = json.load(f)

        earcons = data.get("earcons", {})
        for name, meta in earcons.items():
            self._metadata[name] = EarconAssetMetadata(
                name=meta.get("name", name),
                duration_sec=meta.get("duration_sec", 0),
                intent=meta.get("intent", ""),
                description=meta.get("description", ""),
                leitmotif=meta.get("leitmotif", ""),
                character=meta.get("character", ""),
                tags=meta.get("tags", []),
                tier=meta.get("tier", 2),
                spatial_motion=meta.get("spatial_motion", ""),
                file_sizes=meta.get("file_sizes", {}),
            )

    async def _load_metadata_from_cdn(self) -> None:
        """Load metadata from CDN."""
        url = f"{CDN_BASE_URL}/metadata.json"

        async with self._get_session() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    raise RuntimeError(f"CDN metadata fetch failed: {response.status}")

                data = await response.json()

        # Parse and cache locally
        earcons = data.get("earcons", {})
        for name, meta in earcons.items():
            self._metadata[name] = EarconAssetMetadata(
                name=meta.get("name", name),
                duration_sec=meta.get("duration_sec", 0),
                intent=meta.get("intent", ""),
                description=meta.get("description", ""),
                leitmotif=meta.get("leitmotif", ""),
                character=meta.get("character", ""),
                tags=meta.get("tags", []),
                tier=meta.get("tier", 2),
                spatial_motion=meta.get("spatial_motion", ""),
                file_sizes=meta.get("file_sizes", {}),
            )

        # Save to local cache
        local_metadata = LOCAL_CACHE_DIR / "metadata.json"
        with open(local_metadata, "w") as f:
            json.dump(data, f, indent=2)

    def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self) -> None:
        """Close the asset store and release resources."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    # ========================================================================
    # Public API
    # ========================================================================

    def get_metadata(self, name: str) -> EarconAssetMetadata | None:
        """Get metadata for an earcon.

        Args:
            name: Earcon name (e.g., "notification", "success")

        Returns:
            EarconAssetMetadata or None if not found
        """
        return self._metadata.get(name)

    def list_earcons(self) -> list[str]:
        """List all available earcon names."""
        return list(self._metadata.keys())

    def list_tier_1_earcons(self) -> list[str]:
        """List Tier 1 (core) earcon names."""
        return [n for n, m in self._metadata.items() if m.is_tier_1]

    def list_tier_2_earcons(self) -> list[str]:
        """List Tier 2 (extended) earcon names."""
        return [n for n, m in self._metadata.items() if not m.is_tier_1]

    async def get_earcon(
        self,
        name: str,
        format: AudioFormat | str = AudioFormat.AAC,
    ) -> Path | None:
        """Get the path to an earcon audio file.

        Downloads from CDN if not in local cache.

        Args:
            name: Earcon name (e.g., "notification")
            format: Audio format (wav, mp3, aac)

        Returns:
            Path to local audio file, or None if not available
        """
        if isinstance(format, str):
            format = AudioFormat(format)

        # Check local cache first
        local_path = self._get_local_path(name, format)
        if local_path.exists():
            return local_path

        # Download from CDN
        async with self._download_lock:
            # Double-check after acquiring lock
            if local_path.exists():
                return local_path

            success = await self._download_earcon(name, format)
            if success and local_path.exists():
                return local_path

        return None

    async def get_earcon_bytes(
        self,
        name: str,
        format: AudioFormat | str = AudioFormat.AAC,
    ) -> bytes | None:
        """Get earcon audio data as bytes.

        Useful for embedding in responses or streaming.

        Args:
            name: Earcon name
            format: Audio format

        Returns:
            Audio file bytes or None
        """
        path = await self.get_earcon(name, format)
        if path and path.exists():
            return path.read_bytes()
        return None

    async def preload_tier_1(
        self,
        format: AudioFormat | str = AudioFormat.AAC,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> int:
        """Preload all Tier 1 (core) earcons for instant playback.

        Args:
            format: Audio format to preload
            progress_callback: Optional callback(current, total)

        Returns:
            Number of earcons loaded
        """
        if isinstance(format, str):
            format = AudioFormat(format)

        tier_1_names = self.list_tier_1_earcons()
        total = len(tier_1_names)
        loaded = 0

        for i, name in enumerate(tier_1_names):
            path = await self.get_earcon(name, format)
            if path:
                loaded += 1

            if progress_callback:
                progress_callback(i + 1, total)

        logger.info("Preloaded %d/%d Tier 1 earcons", loaded, total)
        return loaded

    async def preload_all(
        self,
        format: AudioFormat | str = AudioFormat.AAC,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> int:
        """Preload all earcons (for offline mode).

        Args:
            format: Audio format to preload
            progress_callback: Optional callback(current, total)

        Returns:
            Number of earcons loaded
        """
        if isinstance(format, str):
            format = AudioFormat(format)

        all_names = self.list_earcons()
        total = len(all_names)
        loaded = 0

        for i, name in enumerate(all_names):
            path = await self.get_earcon(name, format)
            if path:
                loaded += 1

            if progress_callback:
                progress_callback(i + 1, total)

        logger.info("Preloaded %d/%d earcons", loaded, total)
        return loaded

    def is_cached(self, name: str, format: AudioFormat | str = AudioFormat.AAC) -> bool:
        """Check if an earcon is in the local cache.

        Args:
            name: Earcon name
            format: Audio format

        Returns:
            True if locally cached
        """
        if isinstance(format, str):
            format = AudioFormat(format)

        return self._get_local_path(name, format).exists()

    def get_total_cache_size(self) -> int:
        """Get total size of local cache in bytes."""
        total = 0
        for format_dir in ["wav", "mp3", "aac"]:
            dir_path = LOCAL_CACHE_DIR / format_dir
            if dir_path.exists():
                for file in dir_path.iterdir():
                    if file.is_file():
                        total += file.stat().st_size
        return total

    def clear_cache(self) -> None:
        """Clear the local cache (except metadata)."""
        import shutil

        for format_dir in ["wav", "mp3", "aac"]:
            dir_path = LOCAL_CACHE_DIR / format_dir
            if dir_path.exists():
                shutil.rmtree(dir_path)

        logger.info("Cleared earcon cache")

    # ========================================================================
    # Internal Methods
    # ========================================================================

    def _get_local_path(self, name: str, format: AudioFormat) -> Path:
        """Get the local cache path for an earcon."""
        ext = "m4a" if format == AudioFormat.AAC else format.value
        return LOCAL_CACHE_DIR / format.value / f"{name}.{ext}"

    def _get_cdn_url(self, name: str, format: AudioFormat) -> str:
        """Get the CDN URL for an earcon."""
        ext = "m4a" if format == AudioFormat.AAC else format.value
        return f"{CDN_BASE_URL}/{format.value}/{name}.{ext}"

    async def _download_earcon(self, name: str, format: AudioFormat) -> bool:
        """Download an earcon from CDN.

        Args:
            name: Earcon name
            format: Audio format

        Returns:
            True if download succeeded
        """
        url = self._get_cdn_url(name, format)
        local_path = self._get_local_path(name, format)

        try:
            async with self._get_session() as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        logger.warning(
                            "Failed to download %s: HTTP %d",
                            name,
                            response.status,
                        )
                        return False

                    # Ensure directory exists
                    local_path.parent.mkdir(parents=True, exist_ok=True)

                    # Stream to file
                    with open(local_path, "wb") as f:
                        async for chunk in response.content.iter_chunked(8192):
                            f.write(chunk)

            logger.debug("Downloaded %s (%s)", name, format.value)
            return True

        except Exception as e:
            logger.error("Download failed for %s: %s", name, e)
            return False


# ============================================================================
# Factory Function
# ============================================================================

_store: AudioAssetStore | None = None


async def get_audio_asset_store() -> AudioAssetStore:
    """Get or create the audio asset store singleton.

    Returns:
        Initialized AudioAssetStore
    """
    global _store
    if _store is None:
        _store = AudioAssetStore()
        await _store.initialize()
    return _store


def get_earcon_path(name: str, format: str = "aac") -> Path:
    """Synchronous helper to get expected earcon path.

    Note: Does not download, just returns expected local path.

    Args:
        name: Earcon name
        format: Audio format (wav, mp3, aac)

    Returns:
        Expected local cache path
    """
    ext = "m4a" if format == "aac" else format
    return LOCAL_CACHE_DIR / format / f"{name}.{ext}"


# ============================================================================
# Exports
# ============================================================================

__all__ = [
    "TIER_1_EARCONS",
    "AudioAssetStore",
    "AudioFormat",
    "EarconAssetMetadata",
    "get_audio_asset_store",
    "get_earcon_path",
]
