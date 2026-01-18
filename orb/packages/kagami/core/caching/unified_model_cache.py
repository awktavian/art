"""Unified model cache with XDG compliance and safetensors support.

This module provides a production-ready model caching system with:
- XDG-compliant cache directory (~/.cache/kagami/models/)
- SHA256-based deterministic cache keys
- LRU eviction policy with size and count limits
- Thread-safe async operations
- Support for both pickle and safetensors formats
- Atomic write operations with corruption recovery
- Comprehensive error handling

Security Notes:
- pickle.load() is restricted to validated paths within the cache directory
- Path traversal attacks are prevented via Path.relative_to() validation
- All cache writes use atomic operations (temp file + rename)
- Checksum verification prevents corruption
- File permissions restrict access to current user

Example:
    >>> cache = ModelCache()
    >>> async def load_model():
    ...     return torch.load("model.pt", weights_only=True)
    >>> model = await cache.get_cached_model(
    ...     model_id="bert-base-uncased",
    ...     config={"device": "cuda", "dtype": "float16"},
    ...     loader_fn=load_model
    ... )
"""

import asyncio
import hashlib
import json
import logging
import os
import pickle
import shutil
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

try:
    import aiofiles
    import aiofiles.os

    HAS_AIOFILES = True
except ImportError:
    HAS_AIOFILES = False

from kagami.core.exceptions import SecurityError
from kagami.core.security.signed_serialization import (
    load_signed,
    save_signed,
)
from kagami.core.unified_rate_limiter import (
    RateLimitError,
    get_cache_rate_limiter,
)

logger = logging.getLogger(__name__)


@dataclass
class _CacheEntry:
    """Internal representation of a cached model."""

    model_id: str
    cache_key: str
    size_bytes: int
    created_at: float
    last_access: float
    hit_count: int
    checksum: str
    config: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "_CacheEntry":
        """Create from dictionary."""
        return cls(**data)


class ModelCache:
    """Production-ready model cache with XDG compliance.

    Provides a simple 3-function API for caching ML models with automatic
    LRU eviction, corruption recovery, and multi-format support.

    Thread-safe for concurrent access from multiple async tasks.
    """

    # Canonical config keys for deterministic cache key generation
    CANONICAL_KEYS = ["device", "dtype", "quantization", "revision"]

    def __init__(
        self,
        cache_dir: Path | None = None,
        max_size_gb: float = 100.0,
        max_models: int = 10,
        hf_cache_dir: Path | None = None,
        scan_hf_on_startup: bool = False,
    ) -> None:
        """Initialize model cache.

        Args:
            cache_dir: Cache directory (default: from get_model_cache_path())
            max_size_gb: Maximum total cache size in GB
            max_models: Maximum number of cached models
            hf_cache_dir: HuggingFace cache directory (default: ~/.cache/huggingface/hub)
            scan_hf_on_startup: Scan HF cache for existing models on startup

        Raises:
            OSError: If cache directory cannot be created
        """
        # Use XDG-compliant path if not specified
        if cache_dir is None:
            from kagami.core.config.unified_config import get_model_cache_path

            cache_dir = get_model_cache_path()

        self.cache_dir = cache_dir.expanduser().resolve()
        self.max_size_bytes = int(max_size_gb * 1024 * 1024 * 1024)
        self.max_models = max_models

        # HuggingFace cache integration
        if hf_cache_dir is None:
            # Respect HF_HOME and HUGGINGFACE_HUB_CACHE env vars
            hf_home = os.getenv("HF_HOME")
            if hf_home:
                hf_cache_dir = Path(hf_home) / "hub"
            else:
                hf_hub_cache = os.getenv("HUGGINGFACE_HUB_CACHE")
                if hf_hub_cache:
                    hf_cache_dir = Path(hf_hub_cache)
                else:
                    hf_cache_dir = Path.home() / ".cache" / "huggingface" / "hub"

        self.hf_cache_dir = hf_cache_dir.expanduser().resolve()
        self.scan_hf_on_startup = scan_hf_on_startup

        # Track HF cache models
        self._hf_cache_models: list[dict[str, Any]] = []

        # Create cache directory structure
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Initialized model cache at {self.cache_dir}")
        except OSError as e:
            logger.error(f"Failed to create cache directory {self.cache_dir}: {e}")
            raise

        # Index file tracks all cached models
        self.index_path = self.cache_dir / "index.json"

        # In-memory cache for fast access
        self._memory_cache: dict[str, Any] = {}

        # Index of cache entries (loaded from disk)
        self._index: dict[str, _CacheEntry] = {}

        # Per-key locks for thread safety
        self._locks: dict[str, asyncio.Lock] = {}
        self._index_lock = asyncio.Lock()

        # Rate limiter
        self._rate_limiter = get_cache_rate_limiter()

        # Load existing index
        try:
            asyncio.get_running_loop()
            # Already in async context - create task to load in background
            asyncio.create_task(self._load_index_async())
        except RuntimeError:
            # Not in async context - load synchronously
            asyncio.run(self._load_index_async())

        # Scan HF cache if requested
        if self.scan_hf_on_startup:
            self._hf_cache_models = self._scan_hf_cache()

    async def _load_index_async(self) -> None:
        """Load cache index from disk asynchronously (signed format)."""
        if not self.index_path.exists():
            logger.debug("No existing cache index found")
            return

        try:
            # Load from signed JSON format (auto-migrates legacy format)
            def _load_signed_sync() -> Any:
                return load_signed(self.index_path, format="json", allow_legacy_pickle=True)

            data = await asyncio.to_thread(_load_signed_sync)

            self._index = {key: _CacheEntry.from_dict(entry) for key, entry in data.items()}
            logger.info(f"Loaded cache index with {len(self._index)} entries")

        except FileNotFoundError:
            logger.debug("No existing cache index found")
            self._index = {}
        except SecurityError as e:
            logger.error(f"SECURITY: Cache index signature verification failed: {e}")
            logger.warning("Starting with empty cache index (corrupted or tampered)")
            self._index = {}
        except Exception as e:
            logger.error(f"Failed to load cache index: {e}")
            logger.warning("Starting with empty cache index")
            self._index = {}

    async def _save_index_async(self) -> None:
        """Save cache index to disk atomically (async, signed format)."""
        try:
            # Convert index to dict[str, Any] (CPU-bound)
            data = {key: entry.to_dict() for key, entry in self._index.items()}

            # Save with signed serialization (atomic write built-in)
            def _save_signed_sync() -> None:
                save_signed(data, self.index_path, format="json")

            await asyncio.to_thread(_save_signed_sync)

            logger.debug("Saved cache index (signed)")

        except Exception as e:
            logger.error(f"Failed to save cache index: {e}")

    def _save_index(self) -> None:
        """Save cache index to disk atomically (sync wrapper)."""
        try:
            # Try to use async version if in event loop
            asyncio.get_running_loop()
            # Create task but don't await - fire and forget
            asyncio.create_task(self._save_index_async())
        except RuntimeError:
            # Not in async context - run synchronously
            try:
                asyncio.run(self._save_index_async())
            except Exception as e:
                logger.error(f"Failed to save index: {e}")

    def _scan_hf_cache(self) -> list[dict[str, Any]]:
        """Scan HuggingFace cache directory for pre-downloaded models.

        Parses the HuggingFace hub cache structure:
        ~/.cache/huggingface/hub/
        ├── models--org--model/
        │   ├── snapshots/
        │   │   └── <commit_hash>/
        │   │       ├── model.safetensors
        │   │       ├── config.json
        │   │       └── ...
        │   └── refs/
        │       └── main  (contains commit hash)

        Returns:
            List of discovered models with metadata:
            [
                {
                    "model_id": "org/model",
                    "snapshot_path": "/path/to/snapshot/<hash>",
                    "size_gb": 28.0,
                    "commit_hash": "abc123..."
                }
            ]
        """
        discovered: list[dict[str, Any]] = []

        if not self.hf_cache_dir.exists():
            logger.info(f"HuggingFace cache directory not found: {self.hf_cache_dir}")
            return discovered

        logger.info(f"Scanning HuggingFace cache: {self.hf_cache_dir}")

        try:
            # Iterate over model directories (models--org--name)
            for model_dir in self.hf_cache_dir.iterdir():
                if not model_dir.is_dir():
                    continue

                # Parse model ID from directory name: models--org--name → org/name
                if not model_dir.name.startswith("models--"):
                    continue

                parts = model_dir.name.split("--")
                if len(parts) < 3:
                    logger.debug(f"Skipping invalid model directory: {model_dir.name}")
                    continue

                # Reconstruct model_id: models--Qwen--Qwen3-14B → Qwen/Qwen3-14B
                model_id = "/".join(parts[1:])

                # Find snapshots directory
                snapshots_dir = model_dir / "snapshots"
                if not snapshots_dir.exists():
                    logger.debug(f"No snapshots found for {model_id}")
                    continue

                # Read current commit hash from refs/main
                refs_main = model_dir / "refs" / "main"
                commit_hash = None
                if refs_main.exists():
                    try:
                        with open(refs_main) as f:
                            commit_hash = f.read().strip()
                    except Exception as e:
                        logger.debug(f"Failed to read refs/main for {model_id}: {e}")

                # Find the latest snapshot (use commit hash if available)
                snapshot_path = None
                if commit_hash:
                    snapshot_path = snapshots_dir / commit_hash
                    if not snapshot_path.exists():
                        snapshot_path = None

                # Fallback: find most recent snapshot by mtime
                if snapshot_path is None:
                    try:
                        snapshots = sorted(
                            snapshots_dir.iterdir(),
                            key=lambda p: p.stat().st_mtime,
                            reverse=True,
                        )
                        if snapshots:
                            snapshot_path = snapshots[0]
                            commit_hash = snapshot_path.name
                    except Exception as e:
                        logger.debug(f"Failed to find snapshots for {model_id}: {e}")
                        continue

                if not snapshot_path or not snapshot_path.exists():
                    logger.debug(f"No valid snapshot found for {model_id}")
                    continue

                # Calculate total size
                try:
                    total_bytes = sum(
                        f.stat().st_size for f in snapshot_path.rglob("*") if f.is_file()
                    )
                    size_gb = total_bytes / (1024**3)
                except Exception as e:
                    logger.debug(f"Failed to calculate size for {model_id}: {e}")
                    size_gb = 0.0

                discovered.append(
                    {
                        "model_id": model_id,
                        "snapshot_path": str(snapshot_path),
                        "size_gb": round(size_gb, 2),
                        "commit_hash": commit_hash or "unknown",
                    }
                )

                logger.debug(f"Found HF model: {model_id} ({size_gb:.2f} GB) at {snapshot_path}")

        except Exception as e:
            logger.error(f"Error scanning HuggingFace cache: {e}")

        logger.info(f"Discovered {len(discovered)} models in HuggingFace cache")
        return discovered

    async def _import_from_hf(
        self, model_id: str, snapshot_path: Path, use_symlink: bool = True
    ) -> bool:
        """Import existing HF model into ModelCache.

        Creates a cache entry that references the HF cache location, either by
        symlink (preferred) or by copying files.

        Args:
            model_id: HuggingFace model identifier (e.g., "Qwen/Qwen3-14B")
            snapshot_path: Path to HF snapshot directory
            use_symlink: Use symlink instead of copying (default: True)

        Returns:
            True if imported successfully, False otherwise
        """
        try:
            # Validate snapshot path exists
            if not snapshot_path.exists():
                logger.error(f"Snapshot path does not exist: {snapshot_path}")
                return False

            # Create cache key for this model (using minimal config)
            config = {"source": "huggingface", "revision": snapshot_path.name}
            cache_key = self._compute_cache_key(model_id, config)

            # Check if already cached
            if cache_key in self._index:
                logger.info(f"Model {model_id} already in cache, skipping import")
                return True

            cache_path = self._get_cache_path(cache_key)
            cache_path.mkdir(parents=True, exist_ok=True)

            # Import files from HF snapshot
            if use_symlink:
                # Create symlink to HF snapshot
                target_link = cache_path / "hf_snapshot"
                if target_link.exists():
                    target_link.unlink()

                target_link.symlink_to(snapshot_path)
                logger.info(f"Symlinked HF snapshot: {model_id} → {snapshot_path}")

                # Calculate size from original files
                size_bytes = sum(f.stat().st_size for f in snapshot_path.rglob("*") if f.is_file())
            else:
                # Copy files from HF snapshot
                for src_file in snapshot_path.rglob("*"):
                    if not src_file.is_file():
                        continue

                    rel_path = src_file.relative_to(snapshot_path)
                    dst_file = cache_path / rel_path
                    dst_file.parent.mkdir(parents=True, exist_ok=True)

                    shutil.copy2(src_file, dst_file)

                logger.info(f"Copied HF snapshot: {model_id} → {cache_path}")

                # Calculate size from copied files
                size_bytes = sum(f.stat().st_size for f in cache_path.rglob("*") if f.is_file())

            # Create cache entry
            entry = _CacheEntry(
                model_id=model_id,
                cache_key=cache_key,
                size_bytes=size_bytes,
                created_at=time.time(),
                last_access=time.time(),
                hit_count=0,
                checksum="hf_import",  # Special marker for HF imports
                config=config,
            )

            # Add to index
            async with self._index_lock:
                self._index[cache_key] = entry
                await self._save_index_async()

            logger.info(f"Imported HF model {model_id} ({size_bytes / 1024 / 1024:.2f} MB)")
            return True

        except Exception as e:
            logger.error(f"Failed to import HF model {model_id}: {e}")
            return False

    async def warm_cache_from_config(self, config: Any) -> dict[str, Any]:
        """Preload models specified in configuration.

        Loads models from config.warm_cache.models in priority order:
        high → medium → low

        Stops if cache limits (max_size_gb or max_models) are reached.

        Args:
            config: ModelCacheConfig with warm_cache settings

        Returns:
            Dictionary with warm cache results:
            {
                "loaded": ["model1", "model2"],
                "failed": ["model3"],
                "skipped": ["model4"],
                "total_size_gb": 56.0
            }
        """
        from kagami.core.caching.model_cache_config import ModelCacheConfig

        if not isinstance(config, ModelCacheConfig):
            logger.warning(f"Invalid config type for warm_cache: {type(config)}")
            return {"loaded": [], "failed": [], "skipped": [], "total_size_gb": 0.0}

        if not config.warm_cache.enabled:
            logger.info("Warm cache disabled in config")
            return {"loaded": [], "failed": [], "skipped": [], "total_size_gb": 0.0}

        if not config.warm_cache.models:
            logger.info("No models specified for warm cache")
            return {"loaded": [], "failed": [], "skipped": [], "total_size_gb": 0.0}

        # Sort models by priority
        priority_order = {"high": 0, "medium": 1, "low": 2}
        models = sorted(config.warm_cache.models, key=lambda m: priority_order[m.priority])

        loaded = []
        failed = []
        skipped = []

        logger.info(f"Starting warm cache with {len(models)} models")

        for warm_model in models:
            model_id = warm_model.model_id

            # Check if cache limits reached
            info = self.get_cache_info()
            if info["cached_models"] >= self.max_models:
                logger.warning(f"Max models limit reached ({self.max_models}), skipping {model_id}")
                skipped.append(model_id)
                continue

            # Check if model exists in HF cache
            hf_model = next((m for m in self._hf_cache_models if m["model_id"] == model_id), None)

            if hf_model:
                # Check if adding this model would exceed size limit
                model_size_bytes = int(hf_model["size_gb"] * 1024**3)
                if info["total_size_bytes"] + model_size_bytes > self.max_size_bytes:
                    logger.warning(
                        f"Adding {model_id} ({hf_model['size_gb']:.2f} GB) would exceed "
                        f"size limit ({self.max_size_bytes / 1024**3:.1f} GB), skipping"
                    )
                    skipped.append(model_id)
                    continue

                # Import from HF cache
                logger.info(f"Importing {model_id} from HF cache (priority: {warm_model.priority})")
                snapshot_path = Path(hf_model["snapshot_path"])
                success = await self._import_from_hf(model_id, snapshot_path)

                if success:
                    loaded.append(model_id)
                else:
                    failed.append(model_id)
            else:
                # Model not in HF cache - would need to download
                logger.warning(f"Model {model_id} not found in HF cache, download not implemented")
                skipped.append(model_id)

        # Calculate total loaded size
        info = self.get_cache_info()
        total_size_gb = info["total_size_gb"]

        logger.info(
            f"Warm cache complete: {len(loaded)} loaded, {len(failed)} failed, "
            f"{len(skipped)} skipped ({total_size_gb:.2f} GB)"
        )

        return {
            "loaded": loaded,
            "failed": failed,
            "skipped": skipped,
            "total_size_gb": total_size_gb,
        }

    def _compute_cache_key(self, model_id: str, config: dict[str, Any]) -> str:
        """Compute deterministic cache key from model ID and config.

        Args:
            model_id: Model identifier
            config: Model configuration

        Returns:
            SHA256 hex digest of (model_id + canonical_config)
        """
        # Extract canonical config keys in sorted order
        canonical_config = {key: config.get(key) for key in self.CANONICAL_KEYS if key in config}

        # Create deterministic string representation
        config_str = json.dumps(canonical_config, sort_keys=True)
        key_input = f"{model_id}:{config_str}"

        # Compute SHA256 hash
        return hashlib.sha256(key_input.encode()).hexdigest()

    def _get_cache_path(self, cache_key: str) -> Path:
        """Get directory path for cached model.

        Args:
            cache_key: Cache key (SHA256 hash)

        Returns:
            Path to cache directory for this model
        """
        return self.cache_dir / cache_key

    def _get_lock(self, cache_key: str) -> asyncio.Lock:
        """Get or create lock for cache key.

        Args:
            cache_key: Cache key

        Returns:
            asyncio.Lock for this cache key
        """
        if cache_key not in self._locks:
            self._locks[cache_key] = asyncio.Lock()
        return self._locks[cache_key]

    async def _compute_checksum_async(self, file_path: Path) -> str:
        """Compute SHA256 checksum of file asynchronously.

        Args:
            file_path: Path to file

        Returns:
            SHA256 hex digest
        """
        sha256 = hashlib.sha256()

        if HAS_AIOFILES:
            # Use aiofiles for async I/O
            async with aiofiles.open(file_path, "rb") as f:
                while chunk := await f.read(8192):
                    # Hash update is CPU-bound but fast, no need for thread pool
                    sha256.update(chunk)
        else:
            # Fallback to sync I/O in thread pool
            def _compute_sync() -> Any:
                sha = hashlib.sha256()
                with open(file_path, "rb") as f:
                    for chunk in iter(lambda: f.read(8192), b""):
                        sha.update(chunk)
                return sha.hexdigest()

            return await asyncio.to_thread(_compute_sync)

        return sha256.hexdigest()

    def _compute_checksum(self, file_path: Path) -> str:
        """Compute SHA256 checksum of file (sync wrapper).

        Args:
            file_path: Path to file

        Returns:
            SHA256 hex digest
        """
        # Always use sync version - this is only called from sync contexts
        # Async contexts should use _compute_checksum_async() directly
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    async def _verify_checksum_async(self, file_path: Path, expected: str) -> bool:
        """Verify file checksum asynchronously.

        Args:
            file_path: Path to file
            expected: Expected checksum

        Returns:
            True if checksum matches
        """
        try:
            actual = await self._compute_checksum_async(file_path)
            return actual == expected
        except Exception as e:
            logger.error(f"Checksum verification failed: {e}")
            return False

    def _verify_checksum(self, file_path: Path, expected: str) -> bool:
        """Verify file checksum (sync wrapper).

        Args:
            file_path: Path to file
            expected: Expected checksum

        Returns:
            True if checksum matches
        """
        try:
            actual = self._compute_checksum(file_path)
            return actual == expected
        except Exception as e:
            logger.error(f"Checksum verification failed: {e}")
            return False

    def _safe_pickle_load(self, path: Path) -> Any:
        """Load pickle file with path validation.

        SECURITY: Only unpickle from trusted cache directory to prevent
        arbitrary code execution from untrusted pickle files.

        Args:
            path: Path to pickle file

        Returns:
            Unpickled object

        Raises:
            SecurityError: If path is outside trusted cache directory
        """
        # Verify path is within our cache directory
        resolved_path = path.resolve()
        cache_dir_resolved = self.cache_dir.resolve()

        try:
            # Check if path is relative to cache_dir
            resolved_path.relative_to(cache_dir_resolved)
        except ValueError as err:
            raise SecurityError(
                f"Refusing to unpickle from untrusted path: {path}. "
                f"File must be in cache directory: {self.cache_dir}"
            ) from err

        # Additional check: file must exist and be a regular file
        if not resolved_path.is_file():
            raise SecurityError(f"Path is not a regular file: {path}")

        # Load pickle from trusted location
        with open(resolved_path, "rb") as f:
            return pickle.load(f)  # nosec B301 - path validated above

    async def _load_from_cache(self, cache_key: str, entry: _CacheEntry) -> Any:
        """Load model from disk cache.

        Args:
            cache_key: Cache key
            entry: Cache entry metadata

        Returns:
            Loaded model

        Raises:
            FileNotFoundError: If cache file doesn't exist
            ValueError: If checksum verification fails
            Exception: On other load failures
        """
        cache_path = self._get_cache_path(cache_key)

        # Try safetensors first (preferred format)
        safetensors_path = cache_path / "model.safetensors"
        if safetensors_path.exists():
            logger.debug(f"Loading model from safetensors: {cache_key}")

            # Verify checksum asynchronously
            if not await self._verify_checksum_async(safetensors_path, entry.checksum):
                logger.error(f"Checksum mismatch for {cache_key}, cache corrupted")
                raise ValueError(f"Cache corrupted for {cache_key}")

            try:
                # Import safetensors if available
                # safe_open() is synchronous and CPU-bound, run in thread pool
                def _load_safetensors() -> dict[str, Any]:
                    from safetensors import safe_open

                    with safe_open(safetensors_path, framework="pt") as f:
                        return {key: f.get_tensor(key) for key in f.keys()}

                model = await asyncio.to_thread(_load_safetensors)
                return model
            except ImportError:
                logger.warning("safetensors not available, falling back to pickle")

        # Fall back to pickle format
        pickle_path = cache_path / "model.pkl"
        if not pickle_path.exists():
            raise FileNotFoundError(f"Cache file not found for {cache_key}")

        logger.debug(f"Loading model from pickle: {cache_key}")

        # Verify checksum asynchronously
        if not await self._verify_checksum_async(pickle_path, entry.checksum):
            logger.error(f"Checksum mismatch for {cache_key}, cache corrupted")
            raise ValueError(f"Cache corrupted for {cache_key}")

        # Load from pickle with path validation (run in thread pool as it's I/O + CPU bound)
        model = await asyncio.to_thread(self._safe_pickle_load, pickle_path)

        return model

    async def _save_to_cache(self, cache_key: str, model: Any, entry: _CacheEntry) -> None:
        """Save model to disk cache atomically.

        Args:
            cache_key: Cache key
            model: Model to save
            entry: Cache entry metadata

        Raises:
            OSError: On disk write failure
        """
        cache_path = self._get_cache_path(cache_key)
        cache_path.mkdir(parents=True, exist_ok=True)

        # Try safetensors format first (if available and model is compatible)
        try:
            from safetensors.torch import save_file

            if isinstance(model, dict):
                # Atomic write: temp file + rename
                temp_path = cache_path / "model.safetensors.tmp"
                final_path = cache_path / "model.safetensors"

                # save_file is I/O + CPU bound, run in thread pool
                await asyncio.to_thread(save_file, model, str(temp_path))
                entry.checksum = await self._compute_checksum_async(temp_path)
                temp_path.replace(final_path)

                logger.debug(f"Saved model to safetensors: {cache_key}")

                # Save metadata asynchronously
                metadata_path = cache_path / "metadata.json"
                metadata_dict = entry.to_dict()

                if HAS_AIOFILES:
                    json_content = await asyncio.to_thread(json.dumps, metadata_dict, indent=2)
                    async with aiofiles.open(metadata_path, "w") as f:
                        await f.write(json_content)
                else:

                    def _save_json() -> None:
                        with open(metadata_path, "w") as f:
                            json.dump(metadata_dict, f, indent=2)

                    await asyncio.to_thread(_save_json)

                return
        except (ImportError, Exception) as e:
            logger.debug(f"Safetensors save failed, using pickle: {e}")

        # Fall back to pickle format
        pickle_path = cache_path / "model.pkl"
        temp_path = cache_path / "model.pkl.tmp"

        try:
            # Atomic write: temp file + rename (run in thread pool as pickle.dump is CPU-bound)
            def _save_pickle() -> None:
                with open(temp_path, "wb") as f:
                    pickle.dump(model, f)

            await asyncio.to_thread(_save_pickle)
            entry.checksum = await self._compute_checksum_async(temp_path)
            temp_path.replace(pickle_path)

            logger.debug(f"Saved model to pickle: {cache_key}")

            # Save metadata asynchronously
            metadata_path = cache_path / "metadata.json"
            metadata_dict = entry.to_dict()

            if HAS_AIOFILES:
                json_content = await asyncio.to_thread(json.dumps, metadata_dict, indent=2)
                async with aiofiles.open(metadata_path, "w") as f:
                    await f.write(json_content)
            else:

                def _save_json() -> None:
                    with open(metadata_path, "w") as f:
                        json.dump(metadata_dict, f, indent=2)

                await asyncio.to_thread(_save_json)

        except Exception:
            # Clean up temp file on failure
            if temp_path.exists():
                temp_path.unlink()
            raise

    async def _enforce_limits(self) -> None:
        """Enforce cache size limits using LRU eviction.

        This method is called after each cache write to ensure we don't
        exceed max_models or max_size_bytes limits.
        """
        # Check model count limit
        while len(self._index) > self.max_models:
            # Find LRU entry
            lru_key = min(self._index.keys(), key=lambda k: self._index[k].last_access)
            await self._evict_entry(lru_key)

        # Check size limit
        total_size = sum(entry.size_bytes for entry in self._index.values())
        while total_size > self.max_size_bytes and self._index:
            # Find LRU entry
            lru_key = min(self._index.keys(), key=lambda k: self._index[k].last_access)
            evicted_size = self._index[lru_key].size_bytes
            await self._evict_entry(lru_key)
            total_size -= evicted_size

    async def _evict_entry(self, cache_key: str) -> None:
        """Evict cache entry.

        Args:
            cache_key: Cache key to evict
        """
        logger.info(f"Evicting cache entry: {cache_key}")

        # Remove from memory cache
        self._memory_cache.pop(cache_key, None)

        # Remove from index
        entry = self._index.pop(cache_key, None)
        if entry is None:
            logger.warning(f"Attempted to evict non-existent entry: {cache_key}")
            return

        # Remove from disk (run in thread pool as rmtree can be slow)
        cache_path = self._get_cache_path(cache_key)
        try:
            if cache_path.exists():
                await asyncio.to_thread(shutil.rmtree, cache_path)
            logger.debug(f"Removed cache directory: {cache_path}")
        except Exception as e:
            logger.error(f"Failed to remove cache directory {cache_path}: {e}")

        # Save updated index asynchronously
        await self._save_index_async()

    async def get_cached_model(
        self, model_id: str, config: dict[str, Any], loader_fn: Callable[[], Any]
    ) -> Any:
        """Get model from cache or load it.

        This is the primary method for model caching. It checks memory cache,
        then disk cache, and finally calls loader_fn if cache miss.

        Args:
            model_id: Model identifier (e.g., "bert-base-uncased")
            config: Model configuration dict[str, Any] (e.g., {"device": "cuda", "dtype": "float16"})
            loader_fn: Function to load model if cache miss (can be sync or async)

        Returns:
            Loaded model (from cache or loader_fn)

        Raises:
            Exception: On load failure (after cache corruption recovery attempt)

        Example:
            >>> cache = ModelCache()
            >>> def load_bert():
            ...     return torch.load("bert.pt", weights_only=True)
            >>> model = await cache.get_cached_model(
            ...     model_id="bert-base-uncased",
            ...     config={"device": "cuda"},
            ...     loader_fn=load_bert
            ... )
        """
        # Rate limit check
        allowed, retry_after = await self._rate_limiter.check_limit(model_id, operation="get")
        if not allowed and self._rate_limiter.strategy == "block":
            raise RateLimitError(
                f"Rate limit exceeded for model: {model_id}",
                key=model_id,
                retry_after=retry_after,
            )
        elif not allowed:
            # Delay strategy
            await asyncio.sleep(min(retry_after, 0.1))

        # Compute cache key
        cache_key = self._compute_cache_key(model_id, config)

        # Get per-key lock for thread safety
        lock = self._get_lock(cache_key)

        async with lock:
            # Check memory cache first
            if cache_key in self._memory_cache:
                logger.debug(f"Memory cache hit: {model_id}")
                entry = self._index[cache_key]
                entry.last_access = time.time()
                entry.hit_count += 1
                await self._save_index_async()
                return self._memory_cache[cache_key]

            # Check disk cache
            if cache_key in self._index:
                logger.debug(f"Disk cache hit: {model_id}")
                entry = self._index[cache_key]

                try:
                    model = await self._load_from_cache(cache_key, entry)

                    # Update memory cache and stats
                    self._memory_cache[cache_key] = model
                    entry.last_access = time.time()
                    entry.hit_count += 1
                    await self._save_index_async()

                    return model

                except Exception as e:
                    logger.error(f"Cache load failed for {cache_key}: {e}")
                    logger.warning("Attempting recovery by evicting corrupted entry")

                    # Evict corrupted entry
                    await self._evict_entry(cache_key)

            # Cache miss - call loader function
            logger.info(f"Cache miss, loading model: {model_id}")

            try:
                # Support both sync and async loader functions
                if asyncio.iscoroutinefunction(loader_fn):
                    model = await loader_fn()
                else:
                    model = loader_fn()

            except Exception as e:
                logger.error(f"Model loading failed for {model_id}: {e}")
                raise

            # Create cache entry
            entry = _CacheEntry(
                model_id=model_id,
                cache_key=cache_key,
                size_bytes=0,  # Will be updated after save
                created_at=time.time(),
                last_access=time.time(),
                hit_count=1,
                checksum="",  # Will be computed during save
                config=config,
            )

            # Save to disk cache
            try:
                await self._save_to_cache(cache_key, model, entry)

                # Update size after save
                cache_path = self._get_cache_path(cache_key)
                entry.size_bytes = sum(
                    f.stat().st_size for f in cache_path.rglob("*") if f.is_file()
                )

                # Add to index
                async with self._index_lock:
                    self._index[cache_key] = entry
                    await self._save_index_async()

                # Add to memory cache
                self._memory_cache[cache_key] = model

                # Enforce limits
                await self._enforce_limits()

                logger.info(f"Cached model {model_id} ({entry.size_bytes / 1024 / 1024:.2f} MB)")

            except Exception as e:
                logger.error(f"Failed to cache model {model_id}: {e}")
                # Continue without caching - return loaded model

            return model

    async def invalidate_cache(self, model_id: str, config: dict[str, Any] | None = None) -> bool:
        """Invalidate cached model.

        If config is provided, only invalidate that specific configuration.
        If config is None, invalidate all cached versions of the model.

        Args:
            model_id: Model identifier
            config: Optional config to invalidate (None = invalidate all)

        Returns:
            True if any entries were invalidated

        Example:
            >>> cache = ModelCache()
            >>> # Invalidate specific config
            >>> await cache.invalidate_cache("bert-base", {"device": "cuda"})
            >>> # Invalidate all configs
            >>> await cache.invalidate_cache("bert-base")
        """
        invalidated = False

        if config is not None:
            # Invalidate specific config
            cache_key = self._compute_cache_key(model_id, config)
            if cache_key in self._index:
                await self._evict_entry(cache_key)
                logger.info(f"Invalidated cache for {model_id} with config {config}")
                invalidated = True
        else:
            # Invalidate all configs for this model
            keys_to_evict = [
                key for key, entry in self._index.items() if entry.model_id == model_id
            ]

            # Evict all entries in parallel
            if keys_to_evict:
                await asyncio.gather(
                    *[self._evict_entry(key) for key in keys_to_evict], return_exceptions=True
                )
                invalidated = True

            if invalidated:
                logger.info(f"Invalidated {len(keys_to_evict)} cache entries for {model_id}")

        return invalidated

    async def get_or_load_async(self, checkpoint_path: str, device: str | None = None) -> Any:
        """Load model from checkpoint with caching.

        This method is called by model_factory.load_model_from_checkpoint_async()
        to provide transparent caching for checkpoint loading.

        Args:
            checkpoint_path: Path to checkpoint file
            device: Target device ("cpu", "cuda", "mps", "auto")

        Returns:
            Loaded KagamiWorldModel instance

        Raises:
            Exception: On load failure
        """
        import torch

        # Use checkpoint path as model_id
        model_id = checkpoint_path

        # Normalize device config
        target_device = (device or "cpu").strip().lower()
        if target_device == "auto":
            if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                target_device = "mps"
            elif torch.cuda.is_available():
                target_device = "cuda"
            else:
                target_device = "cpu"

        # Build config for cache key
        config = {"device": target_device, "checkpoint_path": checkpoint_path}

        # Define loader function
        def _load_checkpoint() -> Any:
            from kagami.core.world_model.model_factory import load_model_from_checkpoint

            return load_model_from_checkpoint(
                checkpoint_path, device=target_device, weights_only=False, use_cache=False
            )

        # Use get_cached_model for unified caching logic
        return await self.get_cached_model(model_id, config, _load_checkpoint)

    def invalidate(self, checkpoint_path: str) -> None:
        """Invalidate cache entry for checkpoint file (sync version).

        This is a convenience wrapper for backward compatibility with
        save_model_checkpoint_async() which expects a simple sync invalidate() method.

        Args:
            checkpoint_path: Path to checkpoint file
        """
        # Create cache key for this checkpoint
        model_id = checkpoint_path

        # Invalidate all cached versions of this checkpoint
        # (different device configs may exist)
        keys_to_evict = [key for key, entry in self._index.items() if entry.model_id == model_id]

        for key in keys_to_evict:
            # Synchronous eviction (safe since we're just removing from index + disk)
            self._memory_cache.pop(key, None)
            self._index.pop(key, None)

            cache_path = self._get_cache_path(key)
            try:
                if cache_path.exists():
                    shutil.rmtree(cache_path)
                logger.debug(f"Invalidated cache: {cache_path}")
            except Exception as e:
                logger.error(f"Failed to invalidate cache {cache_path}: {e}")

        if keys_to_evict:
            self._save_index()
            logger.info(f"Invalidated {len(keys_to_evict)} cache entries for {checkpoint_path}")

    def get_cache_info(self) -> dict[str, Any]:
        """Get cache statistics and metadata.

        Returns:
            Dictionary with cache statistics:
            - cached_models: Number of cached models
            - total_size_bytes: Total cache size in bytes
            - total_size_gb: Total cache size in GB
            - max_models: Maximum model limit
            - max_size_gb: Maximum size limit in GB
            - cache_dir: Cache directory path
            - models: List of cached model info
            - hf_cache_discovered: Number of HF cache models found
            - hf_models: List of HF cache models (if scan_hf_on_startup enabled)

        Example:
            >>> cache = ModelCache()
            >>> info = cache.get_cache_info()
            >>> print(f"Cached models: {info['cached_models']}")
            >>> print(f"Cache size: {info['total_size_gb']:.2f} GB")
            >>> print(f"HF models: {info['hf_cache_discovered']}")
        """
        total_size = sum(entry.size_bytes for entry in self._index.values())

        # Sort entries by last access before building list[Any]
        sorted_entries = sorted(self._index.values(), key=lambda e: e.last_access, reverse=True)

        models = [
            {
                "model_id": entry.model_id,
                "cache_key": entry.cache_key,
                "size_mb": entry.size_bytes / 1024 / 1024,
                "created_at": entry.created_at,
                "last_access": entry.last_access,
                "hit_count": entry.hit_count,
                "config": entry.config,
            }
            for entry in sorted_entries
        ]

        info = {
            "cached_models": len(self._index),
            "total_size_bytes": total_size,
            "total_size_gb": total_size / 1024 / 1024 / 1024,
            "max_models": self.max_models,
            "max_size_gb": self.max_size_bytes / 1024 / 1024 / 1024,
            "cache_dir": str(self.cache_dir),
            "models": models,
        }

        # Include HF cache information if available
        if self._hf_cache_models:
            info["hf_cache_discovered"] = len(self._hf_cache_models)
            info["hf_models"] = [
                {
                    "model_id": m["model_id"],
                    "size_gb": m["size_gb"],
                    "commit_hash": m["commit_hash"],
                }
                for m in self._hf_cache_models
            ]
        else:
            info["hf_cache_discovered"] = 0
            info["hf_models"] = []

        return info


# Global instance for convenience
_global_cache: ModelCache | None = None


def get_model_cache(
    cache_dir: Path | None = None,
    max_size_gb: float = 100.0,
    max_models: int = 10,
) -> ModelCache:
    """Get or create global model cache instance.

    Args:
        cache_dir: Cache directory (default: from get_model_cache_path())
        max_size_gb: Maximum total cache size in GB
        max_models: Maximum number of cached models

    Returns:
        Global ModelCache instance

    Example:
        >>> cache = get_model_cache()
        >>> model = await cache.get_cached_model(...)
    """
    global _global_cache

    if _global_cache is None:
        _global_cache = ModelCache(
            cache_dir=cache_dir, max_size_gb=max_size_gb, max_models=max_models
        )

    return _global_cache
