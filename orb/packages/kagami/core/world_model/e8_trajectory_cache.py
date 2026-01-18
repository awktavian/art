"""E8 Trajectory Cache with Bifurcation Replay.

Caches E8-quantized trajectories from TemporalE8Quantizer for:
1. O(1) lookup for repeated temporal patterns
2. Bifurcation replay buffer for continual learning
3. Coverage tracking on S⁷ manifold
4. LRU and importance-based eviction policies

DESIGN:
=======
Trajectories are sequences of E8 lattice points (from catastrophe bifurcations).
Each E8 point is an 8D vector in the lattice, represented in half-step integers.

Hash function: Convert E8 sequence → deterministic string key
Cache: Dict[hash_key] → {e8_codes, prediction, metadata, stats}
Bifurcation buffer: Stores high-risk events for replay training

USAGE:
======
    cache = E8TrajectoryCache(max_size=10000)

    # Store trajectory
    cache.store(e8_codes, prediction, metadata)

    # Lookup (O(1))
    prediction = cache.lookup(e8_codes)

    # Sample bifurcations for continual learning
    bifurcation_batch = cache.sample_bifurcations(batch_size=32)

    # Statistics
    stats = cache.get_stats()
    print(f"Hit rate: {stats['hit_rate']:.2%}")

Created: December 14, 2025
Colony: Forge (e₂) - Quality implementation
"""

from __future__ import annotations

import hashlib
import logging
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import torch
from kagami_math.e8_lattice_quantizer import e8_to_half_step_ints

from kagami.core.security.signed_serialization import load_signed, save_signed

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """Single cache entry for an E8 trajectory.

    Attributes:
        e8_codes: [num_events, 8] E8 lattice points
        prediction: Model's prediction for this trajectory
        metadata: Dict with catastrophe_risks, event_times, etc.
        access_count: Number of times accessed (for importance eviction)
        last_access_time: Timestamp of last access (for LRU)
    """

    e8_codes: torch.Tensor
    prediction: torch.Tensor
    metadata: dict[str, Any]
    access_count: int = 0
    last_access_time: int = 0


@dataclass
class BifurcationEntry:
    """Entry in the bifurcation replay buffer.

    Stores critical states near catastrophe singularities for replay.

    Attributes:
        e8_code: [8] Single E8 lattice point at bifurcation
        catastrophe_risk: Risk value (0-1), higher = more critical
        metadata: Dict with colony_idx, event_time, etc.
        replay_count: Number of times used in replay training
    """

    e8_code: torch.Tensor
    catastrophe_risk: float
    metadata: dict[str, Any]
    replay_count: int = 0


@dataclass
class CacheStats:
    """Cache statistics for monitoring.

    Attributes:
        size: Current cache size
        hit_count: Total cache hits
        miss_count: Total cache misses
        hit_rate: hit_count / (hit_count + miss_count)
        eviction_count: Number of evictions performed
        bifurcation_buffer_size: Current bifurcation buffer size
    """

    size: int
    hit_count: int
    miss_count: int
    hit_rate: float
    eviction_count: int
    bifurcation_buffer_size: int


class E8TrajectoryCache:
    """Cache for E8-quantized trajectories with bifurcation replay.

    Stores sequences of E8 codes (from TemporalE8Quantizer).
    Enables:
    1. O(1) lookup for repeated trajectories
    2. Bifurcation replay for continual learning
    3. Coverage tracking on S⁷

    Thread-safe implementation with locks for concurrent access.

    Usage:
        >>> cache = E8TrajectoryCache(max_size=10000)
        >>> e8_codes = torch.randn(10, 8)  # 10 events
        >>> prediction = torch.randn(256)
        >>> metadata = {"catastrophe_risks": [0.8, 0.7, 0.9]}
        >>> cache.store(e8_codes, prediction, metadata)
        >>> result = cache.lookup(e8_codes)
        >>> print(f"Cache hit: {result is not None}")
    """

    def __init__(
        self,
        max_size: int = 10000,
        bifurcation_buffer_size: int = 1000,
        eviction_policy: str = "lru",
        bifurcation_threshold: float = 0.7,
        thread_safe: bool = True,
    ):
        """Initialize E8 trajectory cache.

        Args:
            max_size: Maximum number of cached trajectories
            bifurcation_buffer_size: Max size of bifurcation replay buffer
            eviction_policy: "lru" (least recently used) or "importance" (lowest access count)
            bifurcation_threshold: Catastrophe risk threshold for replay buffer (0-1)
            thread_safe: Enable thread safety with locks
        """
        if eviction_policy not in ("lru", "importance"):
            raise ValueError(
                f"Invalid eviction_policy: {eviction_policy}. Must be 'lru' or 'importance'"
            )

        self.max_size = max_size
        self.bifurcation_buffer_size = bifurcation_buffer_size
        self.eviction_policy = eviction_policy
        self.bifurcation_threshold = bifurcation_threshold
        self.thread_safe = thread_safe

        # Main cache: hash_key → CacheEntry
        self._cache: dict[str, CacheEntry] = {}

        # Bifurcation replay buffer
        self._bifurcation_buffer: list[BifurcationEntry] = []

        # Statistics
        self._current_time: int = 0
        self._hit_count: int = 0
        self._miss_count: int = 0
        self._eviction_count: int = 0

        # Thread safety
        self._lock = threading.RLock() if thread_safe else None

        logger.info(
            "E8TrajectoryCache initialized: max_size=%d, eviction=%s, bifurcation_buffer=%d",
            max_size,
            eviction_policy,
            bifurcation_buffer_size,
        )

    def _hash_e8_sequence(self, e8_codes: torch.Tensor) -> str:
        """Convert E8 code sequence to hashable string key.

        Uses half-step integer representation for deterministic hashing.

        Args:
            e8_codes: [num_events, 8] E8 lattice points

        Returns:
            hash_key: SHA256 hash of integer sequence
        """
        if e8_codes.ndim != 2 or e8_codes.shape[-1] != 8:
            raise ValueError(f"Expected [num_events, 8] tensor, got shape {e8_codes.shape}")

        # Convert to half-step integers (2x scaling for integer coordinates)
        half_step_ints = e8_to_half_step_ints(e8_codes)  # [num_events, 8] int64

        # Convert to bytes (deterministic)
        int_bytes = half_step_ints.cpu().numpy().tobytes()

        # Hash with SHA256 (64 hex chars, collision-resistant)
        hash_obj = hashlib.sha256(int_bytes)
        hash_key = hash_obj.hexdigest()

        return hash_key

    def _evict_one(self) -> None:
        """Evict one entry based on eviction policy.

        - LRU: Evict least recently used
        - Importance: Evict lowest access count
        """
        if not self._cache:
            return

        if self.eviction_policy == "lru":
            # Evict least recently used
            lru_key = min(self._cache.keys(), key=lambda k: self._cache[k].last_access_time)
            del self._cache[lru_key]
            logger.debug("Evicted LRU entry: %s", lru_key[:16])

        elif self.eviction_policy == "importance":
            # Evict lowest access count
            min_access_key = min(self._cache.keys(), key=lambda k: self._cache[k].access_count)
            del self._cache[min_access_key]
            logger.debug("Evicted low-importance entry: %s", min_access_key[:16])

        self._eviction_count += 1

    def _add_to_bifurcation_buffer(
        self,
        e8_codes: torch.Tensor,
        metadata: dict[str, Any],
    ) -> None:
        """Add critical bifurcation events to replay buffer.

        Args:
            e8_codes: [num_events, 8] E8 codes
            metadata: Dict with catastrophe_risks, event_times, etc.
        """
        catastrophe_risks = metadata.get("catastrophe_risks", [])

        # Add each high-risk event to buffer
        for i, risk in enumerate(catastrophe_risks):
            if risk >= self.bifurcation_threshold:
                entry = BifurcationEntry(
                    e8_code=e8_codes[i].clone(),
                    catastrophe_risk=risk,
                    metadata={
                        "event_index": i,
                        "event_time": metadata.get("event_times", [None])[i]
                        if i < len(metadata.get("event_times", []))
                        else None,
                        "colony_idx": metadata.get("colony_idx", 0),
                    },
                    replay_count=0,
                )
                self._bifurcation_buffer.append(entry)

        # Evict oldest if buffer full
        while len(self._bifurcation_buffer) > self.bifurcation_buffer_size:
            self._bifurcation_buffer.pop(0)  # FIFO eviction

    def store(
        self,
        e8_codes: torch.Tensor,
        prediction: torch.Tensor,
        metadata: dict[str, Any],
    ) -> None:
        """Store E8 trajectory and its prediction.

        Thread-safe operation with optional locking.

        Args:
            e8_codes: [num_events, 8] Temporal sequence of E8 codes
            prediction: Model's prediction for this trajectory (any shape)
            metadata: Dict with catastrophe_risks, event_times, colony_idx, etc.
        """
        if e8_codes.shape[0] == 0:
            logger.warning("Attempted to store empty E8 sequence, skipping")
            return

        hash_key = self._hash_e8_sequence(e8_codes)

        if self._lock:
            with self._lock:
                self._store_unlocked(hash_key, e8_codes, prediction, metadata)
        else:
            self._store_unlocked(hash_key, e8_codes, prediction, metadata)

    def _store_unlocked(
        self,
        hash_key: str,
        e8_codes: torch.Tensor,
        prediction: torch.Tensor,
        metadata: dict[str, Any],
    ) -> None:
        """Internal store without lock (assumes caller holds lock)."""
        # Evict if at capacity
        if len(self._cache) >= self.max_size:
            self._evict_one()

        # Store entry
        entry = CacheEntry(
            e8_codes=e8_codes.clone(),
            prediction=prediction.clone(),
            metadata=metadata.copy(),
            access_count=0,
            last_access_time=self._current_time,
        )
        self._cache[hash_key] = entry

        # Add to bifurcation buffer if high catastrophe risk
        if "catastrophe_risks" in metadata:
            self._add_to_bifurcation_buffer(e8_codes, metadata)

        logger.debug(
            "Stored trajectory: key=%s, num_events=%d",
            hash_key[:16],
            e8_codes.shape[0],
        )

    def lookup(self, e8_codes: torch.Tensor) -> torch.Tensor | None:
        """O(1) lookup for cached prediction.

        Thread-safe operation with optional locking.

        Args:
            e8_codes: [num_events, 8] E8 code sequence

        Returns:
            prediction if found, None otherwise
        """
        if e8_codes.shape[0] == 0:
            return None

        hash_key = self._hash_e8_sequence(e8_codes)

        if self._lock:
            with self._lock:
                return self._lookup_unlocked(hash_key)
        else:
            return self._lookup_unlocked(hash_key)

    def _lookup_unlocked(self, hash_key: str) -> torch.Tensor | None:
        """Internal lookup without lock (assumes caller holds lock)."""
        if hash_key in self._cache:
            # Cache hit
            entry = self._cache[hash_key]
            entry.access_count += 1
            entry.last_access_time = self._current_time
            self._current_time += 1
            self._hit_count += 1

            logger.debug("Cache HIT: key=%s, access_count=%d", hash_key[:16], entry.access_count)
            return entry.prediction.clone()
        else:
            # Cache miss
            self._miss_count += 1
            logger.debug("Cache MISS: key=%s", hash_key[:16])
            return None

    def sample_bifurcations(
        self,
        batch_size: int = 32,
        increment_replay_count: bool = True,
    ) -> torch.Tensor | None:
        """Sample critical states for continual learning replay.

        Randomly samples from bifurcation buffer for experience replay.

        Args:
            batch_size: Number of bifurcation states to sample
            increment_replay_count: Whether to track replay usage

        Returns:
            [batch_size, 8] E8 codes near bifurcation points, or None if insufficient
        """
        if self._lock:
            with self._lock:
                return self._sample_bifurcations_unlocked(batch_size, increment_replay_count)
        else:
            return self._sample_bifurcations_unlocked(batch_size, increment_replay_count)

    def _sample_bifurcations_unlocked(
        self,
        batch_size: int,
        increment_replay_count: bool,
    ) -> torch.Tensor | None:
        """Internal sample without lock."""
        if len(self._bifurcation_buffer) < batch_size:
            logger.debug(
                "Insufficient bifurcations: requested=%d, available=%d",
                batch_size,
                len(self._bifurcation_buffer),
            )
            return None

        # Random sample without replacement
        indices = torch.randperm(len(self._bifurcation_buffer))[:batch_size]
        samples = []

        for idx in indices:
            entry = self._bifurcation_buffer[idx.item()]
            samples.append(entry.e8_code)

            if increment_replay_count:
                entry.replay_count += 1

        batch = torch.stack(samples)  # [batch_size, 8]

        logger.debug("Sampled %d bifurcations for replay", batch_size)
        return batch

    def get_stats(self) -> CacheStats:
        """Get cache statistics.

        Returns:
            CacheStats object with hit rate, size, evictions, etc.
        """
        if self._lock:
            with self._lock:
                return self._get_stats_unlocked()
        else:
            return self._get_stats_unlocked()

    def _get_stats_unlocked(self) -> CacheStats:
        """Internal stats without lock."""
        total_accesses = self._hit_count + self._miss_count
        hit_rate = self._hit_count / total_accesses if total_accesses > 0 else 0.0

        return CacheStats(
            size=len(self._cache),
            hit_count=self._hit_count,
            miss_count=self._miss_count,
            hit_rate=hit_rate,
            eviction_count=self._eviction_count,
            bifurcation_buffer_size=len(self._bifurcation_buffer),
        )

    def clear(self) -> None:
        """Clear all cache and bifurcation buffer entries."""
        if self._lock:
            with self._lock:
                self._clear_unlocked()
        else:
            self._clear_unlocked()

    def _clear_unlocked(self) -> None:
        """Internal clear without lock."""
        self._cache.clear()
        self._bifurcation_buffer.clear()
        logger.info("Cache cleared")

    def save(self, path: Path | str) -> None:
        """Save cache to disk.

        Serializes cache and bifurcation buffer to pickle file.

        Args:
            path: File path to save to
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        if self._lock:
            with self._lock:
                self._save_unlocked(path)
        else:
            self._save_unlocked(path)

    def _save_unlocked(self, path: Path) -> None:
        """Internal save without lock.

        Uses signed torch format for tensors + metadata.
        Stores:
        - Metadata (stats, config) as JSON in .meta file
        - Cache entries (tensors) as individual torch files
        """
        # Save metadata (JSON format)
        metadata = {
            "stats": {
                "current_time": self._current_time,
                "hit_count": self._hit_count,
                "miss_count": self._miss_count,
                "eviction_count": self._eviction_count,
            },
            "config": {
                "max_size": self.max_size,
                "bifurcation_buffer_size": self.bifurcation_buffer_size,
                "eviction_policy": self.eviction_policy,
                "bifurcation_threshold": self.bifurcation_threshold,
            },
            "cache_keys": list(self._cache.keys()),
            "bifurcation_count": len(self._bifurcation_buffer),
        }

        metadata_path = path.with_suffix(".meta")
        save_signed(metadata, metadata_path, format="json")

        # Save cache entries as separate torch files (more secure, faster loading)
        cache_dir = path.parent / f"{path.stem}_entries"
        cache_dir.mkdir(parents=True, exist_ok=True)

        for hash_key, entry in self._cache.items():
            entry_path = cache_dir / f"{hash_key[:16]}.pt"
            entry_data = {
                "e8_codes": entry.e8_codes,
                "prediction": entry.prediction,
                "metadata": entry.metadata,
                "access_count": entry.access_count,
                "last_access_time": entry.last_access_time,
            }
            save_signed(entry_data, entry_path, format="torch")

        # Save bifurcation buffer
        bifurcation_path = path.with_suffix(".bifurcation.pt")
        if self._bifurcation_buffer:
            bifurcation_data = {
                "entries": [
                    {
                        "e8_code": entry.e8_code,
                        "catastrophe_risk": entry.catastrophe_risk,
                        "metadata": entry.metadata,
                        "replay_count": entry.replay_count,
                    }
                    for entry in self._bifurcation_buffer
                ]
            }
            save_signed(bifurcation_data, bifurcation_path, format="torch")

        logger.info("Cache saved to %s (%d entries)", path, len(self._cache))

    def load(self, path: Path | str) -> None:
        """Load cache from disk.

        Deserializes cache and bifurcation buffer from pickle file.

        Args:
            path: File path to load from
        """
        path = Path(path)

        # Check for metadata file (new signed format) or legacy pickle
        metadata_path = path.with_suffix(".meta")
        if not metadata_path.exists() and not path.exists():
            raise FileNotFoundError(f"Cache file not found: {path}")

        if self._lock:
            with self._lock:
                self._load_unlocked(path)
        else:
            self._load_unlocked(path)

    def _load_unlocked(self, path: Path) -> None:
        """Internal load without lock.

        Loads from signed JSON/torch format (secure).
        Supports automatic migration from legacy pickle format.
        """
        metadata_path = path.with_suffix(".meta")

        # Check if we need to migrate from legacy pickle format
        if not metadata_path.exists() and path.exists():
            logger.warning(
                "Detected legacy pickle cache at %s. Migrating to signed format...", path
            )
            self._migrate_from_pickle(path)
            return

        if not metadata_path.exists():
            raise FileNotFoundError(f"Cache metadata not found: {metadata_path}")

        # Load metadata
        metadata = load_signed(metadata_path, format="json", allow_legacy_pickle=False)

        # Restore stats
        stats = metadata.get("stats", {})
        self._current_time = stats.get("current_time", 0)
        self._hit_count = stats.get("hit_count", 0)
        self._miss_count = stats.get("miss_count", 0)
        self._eviction_count = stats.get("eviction_count", 0)

        # Validate config matches (warn if mismatch)
        config = metadata.get("config", {})
        if config.get("eviction_policy") != self.eviction_policy:
            logger.warning(
                "Loaded cache has different eviction policy: %s vs %s",
                config.get("eviction_policy"),
                self.eviction_policy,
            )

        # Load cache entries
        cache_keys = metadata.get("cache_keys", [])
        cache_dir = path.parent / f"{path.stem}_entries"

        self._cache = {}
        for hash_key in cache_keys:
            entry_path = cache_dir / f"{hash_key[:16]}.pt"
            if not entry_path.exists():
                logger.warning("Missing cache entry file: %s", entry_path)
                continue

            try:
                entry_data = load_signed(entry_path, format="torch", allow_legacy_pickle=False)

                # Reconstruct CacheEntry
                entry = CacheEntry(
                    e8_codes=entry_data["e8_codes"],
                    prediction=entry_data["prediction"],
                    metadata=entry_data["metadata"],
                    access_count=entry_data["access_count"],
                    last_access_time=entry_data["last_access_time"],
                )
                self._cache[hash_key] = entry

            except Exception as e:
                logger.error("Failed to load cache entry %s: %s", hash_key[:16], e)
                continue

        # Load bifurcation buffer
        bifurcation_path = path.with_suffix(".bifurcation.pt")
        self._bifurcation_buffer = []

        if bifurcation_path.exists():
            try:
                bifurcation_data = load_signed(
                    bifurcation_path, format="torch", allow_legacy_pickle=False
                )

                for entry_dict in bifurcation_data.get("entries", []):
                    entry = BifurcationEntry(  # type: ignore[assignment]
                        e8_code=entry_dict["e8_code"],
                        catastrophe_risk=entry_dict["catastrophe_risk"],
                        metadata=entry_dict["metadata"],
                        replay_count=entry_dict["replay_count"],
                    )
                    self._bifurcation_buffer.append(entry)  # type: ignore[arg-type]

            except Exception as e:
                logger.error("Failed to load bifurcation buffer: %s", e)

        logger.info("Cache loaded from %s (%d entries)", path, len(self._cache))

    def _migrate_from_pickle(self, path: Path) -> None:
        """Migrate legacy pickle cache to signed format (ONE-TIME migration).

        Args:
            path: Path to legacy pickle file
        """
        import pickle

        logger.warning("Migrating legacy pickle cache to signed format...")

        try:
            with path.open("rb") as f:
                # LAST TIME we use pickle.load - one-time migration
                data = pickle.load(f)  # nosec B301

            # Extract data
            self._cache = data.get("cache", {})
            self._bifurcation_buffer = data.get("bifurcation_buffer", [])

            stats = data.get("stats", {})
            self._current_time = stats.get("current_time", 0)
            self._hit_count = stats.get("hit_count", 0)
            self._miss_count = stats.get("miss_count", 0)
            self._eviction_count = stats.get("eviction_count", 0)

            # Backup original pickle
            backup_path = path.with_suffix(".pickle.bak")
            path.rename(backup_path)
            logger.info("Backed up original pickle to %s", backup_path)

            # Save in new signed format
            self._save_unlocked(path)
            logger.info("Migration complete: %d entries migrated", len(self._cache))

        except Exception as e:
            logger.error("Migration failed: %s", e)
            raise

    def get_bifurcation_stats(self) -> dict[str, Any]:
        """Get statistics about bifurcation replay buffer.

        Returns:
            Dict with buffer size, risk distribution, replay counts
        """
        if self._lock:
            with self._lock:
                return self._get_bifurcation_stats_unlocked()
        else:
            return self._get_bifurcation_stats_unlocked()

    def _get_bifurcation_stats_unlocked(self) -> dict[str, Any]:
        """Internal bifurcation stats without lock."""
        if not self._bifurcation_buffer:
            return {
                "buffer_size": 0,
                "avg_risk": 0.0,
                "max_risk": 0.0,
                "min_risk": 0.0,
                "avg_replay_count": 0.0,
            }

        risks = [entry.catastrophe_risk for entry in self._bifurcation_buffer]
        replay_counts = [entry.replay_count for entry in self._bifurcation_buffer]

        return {
            "buffer_size": len(self._bifurcation_buffer),
            "avg_risk": sum(risks) / len(risks),
            "max_risk": max(risks),
            "min_risk": min(risks),
            "avg_replay_count": sum(replay_counts) / len(replay_counts),
            "max_replay_count": max(replay_counts),
        }


# Factory function for easy instantiation
def create_e8_trajectory_cache(
    max_size: int = 10000,
    eviction_policy: str = "lru",
    bifurcation_buffer_size: int = 1000,
    bifurcation_threshold: float = 0.7,
    thread_safe: bool = True,
) -> E8TrajectoryCache:
    """Create E8 trajectory cache with sensible defaults.

    Args:
        max_size: Maximum cache size
        eviction_policy: "lru" or "importance"
        bifurcation_buffer_size: Size of bifurcation replay buffer
        bifurcation_threshold: Threshold for bifurcation detection
        thread_safe: Enable thread-safe access

    Returns:
        Configured E8TrajectoryCache
    """
    return E8TrajectoryCache(
        max_size=max_size,
        eviction_policy=eviction_policy,
        bifurcation_buffer_size=bifurcation_buffer_size,
        bifurcation_threshold=bifurcation_threshold,
        thread_safe=thread_safe,
    )


__all__ = [
    "BifurcationEntry",
    "CacheEntry",
    "CacheStats",
    "E8TrajectoryCache",
    "create_e8_trajectory_cache",
]
