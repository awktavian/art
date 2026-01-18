"""
Memory management and resource limits for K os.

This module provides centralized memory management to prevent memory leaks
and excessive memory usage across processes, especially when loading ML models.
"""

import asyncio
import gc
import hashlib
import logging
import multiprocessing as mp
import os
import time
from collections.abc import Callable, Generator
from contextlib import contextmanager
from multiprocessing.managers import SyncManager
from pathlib import Path
from typing import Any

import psutil

logger = logging.getLogger(__name__)

fcntl: Any = None
try:
    import fcntl as _fcntl

    fcntl = _fcntl
except ImportError as e:
    logger.debug(f"fcntl unavailable (Windows or unsupported platform): {e}")
    # Expected on Windows - fcntl is Unix-only
_manager: SyncManager | None = None
_shared_models: Any = None  # DictProxy when initialized
_model_locks: dict[str, Any] = {}  # mp.Lock objects


def _ensure_manager_enabled() -> bool:
    try:
        return (os.getenv("KAGAMI_ENABLE_SHARED_MODELS") or "0").lower() in (
            "1",
            "true",
            "yes",
            "on",
        )
    except (KeyError, AttributeError) as e:
        logger.debug(f"Environment variable access failed: {e}")
        return False


def initialize_shared_memory() -> None:
    """Initialize shared memory structures for model sharing across processes.

    Only starts the multiprocessing Manager when explicitly enabled via
    KAGAMI_ENABLE_SHARED_MODELS to avoid spawn failures in embedded contexts.
    """
    global _manager, _shared_models
    if _manager is not None:
        return
    if not _ensure_manager_enabled():
        _manager = None
        _shared_models = None
        return
    try:
        try:
            ctx: Any = mp.get_context("spawn")
        except ValueError as e:
            logger.debug(f"spawn context unavailable, using default: {e}")
            ctx = mp
        _manager = ctx.Manager()
        _shared_models = _manager.dict()  # Returns DictProxy
        logger.info("Initialized shared memory manager for model caching")
    except Exception as e:
        logger.warning("Shared Manager unavailable (%s); proceeding without cross-process cache", e)
        _manager = None
        _shared_models = None


def get_memory_info() -> dict[str, float]:
    """Get current memory usage information."""
    process = psutil.Process()
    system = psutil.virtual_memory()
    return {
        "process_rss_gb": process.memory_info().rss / 1024**3,
        "process_vms_gb": process.memory_info().vms / 1024**3,
        "system_total_gb": system.total / 1024**3,
        "system_available_gb": system.available / 1024**3,
        "system_percent": system.percent,
    }


def check_memory_availability(required_gb: float = 4.0) -> bool:
    """Check if enough memory is available for an operation.

    Args:
        required_gb: Required memory in GB

    Returns:
        True if enough memory is available
    """
    info = get_memory_info()
    available = info["system_available_gb"]
    if available < required_gb:
        logger.warning(
            f"Insufficient memory: {available:.2f}GB available, {required_gb:.2f}GB required"
        )
        return False
    return True


@contextmanager
def memory_guard(max_gb: float = 4.0, cleanup: bool = True) -> Generator[None, None, None]:
    """Context manager to guard memory-intensive operations.

    Args:
        max_gb: Maximum memory allowed for the operation
        cleanup: Whether to run garbage collection after
    """
    initial_memory = get_memory_info()
    logger.debug(f"Memory before operation: {initial_memory['process_rss_gb']:.2f}GB")
    try:
        yield
    finally:
        if cleanup:
            gc.collect()
            try:
                import torch

                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                    torch.mps.empty_cache() if hasattr(torch.mps, "empty_cache") else None
            except ImportError as e:
                logger.debug(f"torch unavailable for cache clearing: {e}")
        final_memory = get_memory_info()
        memory_increase = final_memory["process_rss_gb"] - initial_memory["process_rss_gb"]
        if memory_increase > max_gb:
            logger.warning(
                f"Operation exceeded memory limit: increased by {memory_increase:.2f}GB (limit was {max_gb}GB)"
            )


class ModelMemoryManager:
    """Manages memory for ML model loading and caching."""

    _local_cache: dict[str, Any] = {}
    _cache_locks: dict[str, asyncio.Lock] = {}
    _lru_order: list[str] = []
    _max_cache_entries: int = int(os.getenv("KAGAMI_MODEL_CACHE_MAX", "3") or 3)

    @staticmethod
    def _locks_dir() -> Path:
        """Directory for interprocess model locks."""
        try:
            base = os.getenv("KAGAMI_MODEL_LOCK_DIR", "/tmp/kagami_model_locks")
        except (KeyError, AttributeError) as e:
            logger.debug(f"Environment variable access failed, using default: {e}")
            base = "/tmp/kagami_model_locks"
        p = Path(base)
        try:
            p.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            logger.warning(f"Could not create lock directory {p}: {e}")
            # Fallback to /tmp if custom dir fails
        return p

    @staticmethod
    def _lock_path_for(model_name: str) -> Path:
        """Stable lock file path per model name."""
        h = hashlib.sha1(model_name.encode("utf-8"), usedforsecurity=False).hexdigest()
        return ModelMemoryManager._locks_dir() / f"{h}.lock"

    @staticmethod
    @contextmanager
    def _interprocess_lock(
        model_name: str, timeout_s: float = 180.0
    ) -> Generator[None, None, None]:
        """Advisory file lock to singleflight model loads across processes.

        Uses POSIX flock when available. Falls back to no-op lock if unsupported.
        """
        if fcntl is None:
            yield
            return
        lock_path = ModelMemoryManager._lock_path_for(model_name)
        fd = None
        start = time.time()
        try:
            fd = os.open(str(lock_path), os.O_RDWR | os.O_CREAT, 384)
            acquired = False
            while not acquired:
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    acquired = True
                except BlockingIOError:
                    if time.time() - start > max(0.1, float(timeout_s)):
                        break
                    time.sleep(0.1)
            yield
        finally:
            try:
                if fd is not None and fcntl is not None:
                    try:
                        fcntl.flock(fd, fcntl.LOCK_UN)
                    except OSError as e:
                        logger.debug(f"Lock release failed: {e}")
                    os.close(fd)
            except OSError as e:
                logger.debug(f"File descriptor cleanup failed: {e}")

    @classmethod
    def get_or_load_model(
        cls, model_name: str, loader_func: Callable[..., Any], max_memory_gb: float = 4.0
    ) -> Any:
        """Get a model from cache or load it with memory protection.

        Args:
            model_name: Name/ID of the model
            loader_func: Function to load the model if not cached
            max_memory_gb: Maximum memory for loading

        Returns:
            The loaded model
        """
        if model_name in cls._local_cache:
            try:
                if model_name in cls._lru_order:
                    cls._lru_order.remove(model_name)
                cls._lru_order.insert(0, model_name)
            except (ValueError, IndexError) as e:
                logger.debug(f"LRU order update failed: {e}")
                # Non-critical, cache still works
            logger.debug(f"Using cached model: {model_name}")
            return cls._local_cache[model_name]
        initialize_shared_memory()
        if _shared_models and model_name in _shared_models:
            logger.debug(f"Using shared cached model: {model_name}")
            model = _shared_models[model_name]
            cls._local_cache[model_name] = model
            try:
                if model_name in cls._lru_order:
                    cls._lru_order.remove(model_name)
                cls._lru_order.insert(0, model_name)
            except (ValueError, IndexError) as e:
                logger.debug(f"LRU order update failed: {e}")
            return model
        with cls._interprocess_lock(model_name, timeout_s=180.0):
            if model_name in cls._local_cache:
                try:
                    if model_name in cls._lru_order:
                        cls._lru_order.remove(model_name)
                    cls._lru_order.insert(0, model_name)
                except (ValueError, IndexError) as e:
                    logger.debug(f"LRU order update failed: {e}")
                logger.debug(f"Using cached model after lock: {model_name}")
                return cls._local_cache[model_name]
            initialize_shared_memory()
            if _shared_models and model_name in _shared_models:
                logger.debug(f"Using shared cached model after lock: {model_name}")
                model = _shared_models[model_name]
                cls._local_cache[model_name] = model
                try:
                    if model_name in cls._lru_order:
                        cls._lru_order.remove(model_name)
                    cls._lru_order.insert(0, model_name)
                except (ValueError, IndexError) as e:
                    logger.debug(f"LRU order update failed: {e}")
                return model
            if not check_memory_availability(max_memory_gb):
                cls.cleanup_least_used()
                if not check_memory_availability(max_memory_gb):
                    raise MemoryError(
                        f"Insufficient memory to load model {model_name} (requires {max_memory_gb}GB)"
                    )
            with memory_guard(max_memory_gb):
                logger.info(f"Loading model: {model_name}")
                model = loader_func()

            cls._local_cache[model_name] = model
            try:
                if model_name in cls._lru_order:
                    cls._lru_order.remove(model_name)
                cls._lru_order.insert(0, model_name)
            except (ValueError, IndexError) as e:
                logger.debug(f"LRU order update failed: {e}")
            try:
                while len(cls._lru_order) > max(1, int(cls._max_cache_entries)):
                    evict_name = cls._lru_order.pop()
                    if evict_name in cls._local_cache:
                        logger.info(f"Evicting model from cache: {evict_name}")
                        del cls._local_cache[evict_name]
                        gc.collect()
            except (ValueError, IndexError, KeyError) as e:
                logger.debug(f"Cache eviction failed: {e}")
            initialize_shared_memory()
            if _shared_models is not None:
                try:
                    _shared_models[model_name] = model
                except Exception as e:
                    logger.debug(f"Could not share model {model_name} across processes: {e}")
            return model

    @classmethod
    async def get_or_load_model_async(
        cls, model_name: str, loader_func: Callable[..., Any], max_memory_gb: float = 4.0
    ) -> Any:
        """Async version with interprocess and intra-process singleflight."""
        if model_name not in cls._cache_locks:
            cls._cache_locks[model_name] = asyncio.Lock()
        async with cls._cache_locks[model_name]:
            if model_name in cls._local_cache:
                try:
                    if model_name in cls._lru_order:
                        cls._lru_order.remove(model_name)
                    cls._lru_order.insert(0, model_name)
                except (ValueError, IndexError) as e:
                    logger.debug(f"LRU order update failed: {e}")
                return cls._local_cache[model_name]

            def _load_sync() -> Any:
                return cls.get_or_load_model(model_name, loader_func, max_memory_gb=max_memory_gb)

            model = await asyncio.to_thread(_load_sync)
            return model

    @classmethod
    def cleanup_least_used(cls, keep_n: int = 2) -> None:
        """Clean up least recently used models to free memory.

        Args:
            keep_n: Number of models to keep
        """
        if len(cls._local_cache) <= keep_n:
            return
        try:
            order = list(cls._lru_order) if cls._lru_order else list(cls._local_cache.keys())
            models_to_remove = order[keep_n:]
        except (ValueError, IndexError, KeyError) as e:
            logger.debug(f"LRU order access failed, using cache keys: {e}")
            models_to_remove = list(cls._local_cache.keys())[keep_n:]
        for model_name in models_to_remove:
            logger.info(f"Removing model from cache: {model_name}")
            del cls._local_cache[model_name]

    @classmethod
    def clear_all(cls) -> None:
        """Clear all cached models."""
        cls._local_cache.clear()
        initialize_shared_memory()
        if _shared_models:
            try:
                _shared_models.clear()
            except Exception as e:
                logger.debug(f"Shared memory clear failed: {e}")
        gc.collect()


def configure_multiprocessing() -> None:
    """Configure multiprocessing for optimal memory usage."""
    try:
        mp.set_start_method("spawn", force=True)
    except RuntimeError:
        pass
    os.environ["PYTHONHASHSEED"] = "0"
    os.environ["OMP_NUM_THREADS"] = "1"
    os.environ["MKL_NUM_THREADS"] = "1"
    os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "max_split_size_mb:512"
    # MPS env tuning (centralized; torch-free)
    try:
        from kagami.core.utils.device import apply_mps_env_patches

        apply_mps_env_patches()
    except ImportError as e:
        logger.debug(f"MPS env patches unavailable: {e}")
        # Do not fail import-time initialization due to optional MPS tuning.
    os.environ.setdefault("ACCELERATE_DISABLE_RICH", "1")
    logger.info("Configured multiprocessing for optimal memory usage")


configure_multiprocessing()
