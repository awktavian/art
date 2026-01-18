"""Property blob cache.

File-based cache for property blobs with TTL support.
Stores blobs as JSON files in a cache directory.

The cache key is a hash of the normalized address.

Example:
    >>> cache = PropertyCache()
    >>> blob = await cache.get("123 Main St, Seattle, WA")
    >>> if not blob:
    ...     blob = await fetch_property_data(...)
    ...     await cache.set("123 Main St, Seattle, WA", blob)
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime
from pathlib import Path

from kagami_api.property.models import PropertyBlob

logger = logging.getLogger(__name__)

# Default cache directory
DEFAULT_CACHE_DIR = Path.home() / ".kagami" / "cache" / "properties"


class PropertyCache:
    """File-based property blob cache.

    Stores property blobs as JSON files indexed by address hash.
    Supports TTL-based expiration.

    Attributes:
        cache_dir: Directory for cache files.
        default_ttl_hours: Default TTL for cached blobs.
    """

    def __init__(
        self,
        cache_dir: Path | None = None,
        default_ttl_hours: int = 168,  # 1 week
    ):
        """Initialize cache.

        Args:
            cache_dir: Directory for cache files. Defaults to ~/.kagami/cache/properties
            default_ttl_hours: Default cache TTL in hours.
        """
        self.cache_dir = cache_dir or DEFAULT_CACHE_DIR
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.default_ttl_hours = default_ttl_hours

    def _get_cache_key(self, address: str) -> str:
        """Generate cache key from address.

        Normalizes address and creates SHA256 hash.

        Args:
            address: Property address.

        Returns:
            Hex hash string.
        """
        # Normalize: lowercase, remove extra whitespace
        normalized = " ".join(address.lower().split())
        return hashlib.sha256(normalized.encode()).hexdigest()[:16]

    def _get_cache_path(self, address: str) -> Path:
        """Get file path for cached blob.

        Args:
            address: Property address.

        Returns:
            Path to cache file.
        """
        key = self._get_cache_key(address)
        return self.cache_dir / f"{key}.json"

    async def get(self, address: str) -> PropertyBlob | None:
        """Retrieve cached property blob.

        Args:
            address: Property address to look up.

        Returns:
            PropertyBlob if found and not expired, None otherwise.
        """
        cache_path = self._get_cache_path(address)

        if not cache_path.exists():
            return None

        try:
            data = json.loads(cache_path.read_text())
            blob = PropertyBlob.model_validate(data)

            # Check expiration
            if blob.is_expired:
                logger.info(f"Cache expired for {address}")
                cache_path.unlink(missing_ok=True)
                return None

            logger.debug(f"Cache hit for {address}")
            return blob

        except Exception as e:
            logger.warning(f"Cache read error for {address}: {e}")
            cache_path.unlink(missing_ok=True)
            return None

    async def set(self, address: str, blob: PropertyBlob) -> None:
        """Store property blob in cache.

        Args:
            address: Property address.
            blob: PropertyBlob to cache.
        """
        cache_path = self._get_cache_path(address)

        try:
            # Update cache timestamp
            blob.cached_at = datetime.utcnow()

            # Write as JSON
            data = blob.model_dump(mode="json")
            cache_path.write_text(json.dumps(data, indent=2, default=str))
            logger.debug(f"Cached {address}")

        except Exception as e:
            logger.error(f"Cache write error for {address}: {e}")

    async def invalidate(self, address: str) -> None:
        """Remove cached blob for address.

        Args:
            address: Property address to invalidate.
        """
        cache_path = self._get_cache_path(address)
        cache_path.unlink(missing_ok=True)
        logger.debug(f"Invalidated cache for {address}")

    async def clear_all(self) -> int:
        """Clear all cached blobs.

        Returns:
            Number of blobs cleared.
        """
        count = 0
        for path in self.cache_dir.glob("*.json"):
            path.unlink()
            count += 1
        logger.info(f"Cleared {count} cached blobs")
        return count

    async def get_stats(self) -> dict:
        """Get cache statistics.

        Returns:
            Dict with cache stats (count, size, oldest, newest).
        """
        files = list(self.cache_dir.glob("*.json"))
        total_size = sum(f.stat().st_size for f in files)

        oldest = None
        newest = None
        for f in files:
            mtime = datetime.fromtimestamp(f.stat().st_mtime)
            if oldest is None or mtime < oldest:
                oldest = mtime
            if newest is None or mtime > newest:
                newest = mtime

        return {
            "count": len(files),
            "total_size_bytes": total_size,
            "oldest": oldest.isoformat() if oldest else None,
            "newest": newest.isoformat() if newest else None,
            "cache_dir": str(self.cache_dir),
        }


# Singleton instance
_cache: PropertyCache | None = None


def get_property_cache() -> PropertyCache:
    """Get singleton PropertyCache instance."""
    global _cache
    if _cache is None:
        _cache = PropertyCache()
    return _cache
