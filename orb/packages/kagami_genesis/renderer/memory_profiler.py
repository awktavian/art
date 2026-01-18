"""Memory Profiler for Genesis Realtime Renderer.

This module provides memory tracking and leak detection capabilities for
the Genesis rendering pipeline using Python's built-in tracemalloc module.
Memory profiling is disabled by default and can be enabled via environment
variable for debugging and optimization purposes.

Architecture:
    - Uses tracemalloc for precise Python memory tracking
    - Supports snapshot comparison for leak detection
    - Tracks peak memory usage across render sessions
    - Zero overhead when disabled

Usage:
    Enable via environment variable before running:
    ```bash
    ENABLE_MEMORY_PROFILING=1 python render_scene.py
    ```

    Or programmatically:
    ```python
    profiler = MemoryProfiler()
    profiler.start()
    # ... rendering code ...
    stats = profiler.get_memory_stats()
    print(f"Peak memory: {stats['peak_mb']:.2f} MB")
    profiler.stop()
    ```

Part of realtime_renderer.py refactoring (2,992 LOC → modules).
Created: 2026-01-05
Colony: Crystal (e₇) — Verification and monitoring
"""

from __future__ import annotations

import logging
import tracemalloc

logger = logging.getLogger(__name__)


class MemoryProfiler:
    """Memory profiler using Python's tracemalloc module.

    Provides memory usage tracking, peak detection, and snapshot capabilities
    for debugging memory leaks and optimizing memory consumption in the
    Genesis rendering pipeline.

    The profiler is disabled by default to avoid performance overhead.
    Enable it by setting the ENABLE_MEMORY_PROFILING environment variable
    to "1", "true", or "yes".

    Attributes:
        enabled: Whether memory profiling is enabled (read-only).

    Example:
        >>> profiler = MemoryProfiler()
        >>> if profiler.enabled:
        ...     profiler.start()
        ...     # ... do work ...
        ...     print(f"Peak: {profiler.get_peak_memory():.2f} MB")
        ...     profiler.stop()
    """

    def __init__(self) -> None:
        """Initialize the memory profiler.

        Checks the ENABLE_MEMORY_PROFILING environment variable to determine
        whether profiling should be active. Initializes internal state for
        tracking memory snapshots and peak usage.
        """
        import os

        self._enabled = os.getenv("ENABLE_MEMORY_PROFILING", "0").lower() in (
            "1",
            "true",
            "yes",
        )
        self._tracking = False
        self._snapshots: list[tracemalloc.Snapshot] = []
        self._peak_memory = 0.0

    @property
    def enabled(self) -> bool:
        """Check if memory profiling is enabled.

        Returns:
            True if ENABLE_MEMORY_PROFILING is set, False otherwise.
        """
        return self._enabled

    def start(self) -> None:
        """Start memory profiling.

        Begins tracking memory allocations using tracemalloc.
        Has no effect if profiling is disabled or already running.
        Resets peak memory tracking to zero.
        """
        if not self._enabled or self._tracking:
            return
        tracemalloc.start()
        self._tracking = True
        self._peak_memory = 0.0
        logger.debug("Memory profiling started")

    def stop(self) -> None:
        """Stop memory profiling.

        Stops tracemalloc tracking and releases its internal data structures.
        Has no effect if profiling is disabled or not currently running.
        """
        if not self._enabled or not self._tracking:
            return
        tracemalloc.stop()
        self._tracking = False
        logger.debug("Memory profiling stopped")

    def take_snapshot(self) -> tracemalloc.Snapshot | None:
        """Take a memory allocation snapshot.

        Captures the current state of all traced memory allocations.
        Snapshots can be compared to detect memory leaks between
        two points in time.

        Returns:
            A tracemalloc.Snapshot object if profiling is active,
            None if profiling is disabled or not running.

        Example:
            >>> before = profiler.take_snapshot()
            >>> # ... allocate memory ...
            >>> after = profiler.take_snapshot()
            >>> # Compare snapshots to find leaks
        """
        if not self._enabled or not self._tracking:
            return None
        snapshot = tracemalloc.take_snapshot()
        self._snapshots.append(snapshot)
        return snapshot

    def get_peak_memory(self) -> float:
        """Get peak memory usage in megabytes.

        Returns the highest memory usage observed since start() was called.
        Updates the tracked peak if current peak exceeds previous maximum.

        Returns:
            Peak memory usage in MB, or 0.0 if profiling is disabled.
        """
        if not self._enabled or not self._tracking:
            return 0.0
        _, peak = tracemalloc.get_traced_memory()
        peak_mb = peak / 1024 / 1024
        self._peak_memory = max(self._peak_memory, peak_mb)
        return self._peak_memory

    def get_current_memory(self) -> float:
        """Get current memory usage in megabytes.

        Returns the total size of all currently traced memory blocks.

        Returns:
            Current memory usage in MB, or 0.0 if profiling is disabled.
        """
        if not self._enabled or not self._tracking:
            return 0.0
        current, _ = tracemalloc.get_traced_memory()
        return current / 1024 / 1024

    def get_memory_stats(self) -> dict[str, float | bool | int]:
        """Get comprehensive memory statistics.

        Returns a dictionary with current memory state including:
        - enabled: Whether profiling is active
        - current_mb: Current memory usage in MB
        - peak_mb: Peak memory from tracemalloc
        - tracked_peak_mb: Maximum peak observed via get_peak_memory()
        - snapshots_taken: Number of snapshots captured

        Returns:
            Dictionary of memory statistics. If profiling is disabled,
            returns only {"enabled": False}.
        """
        if not self._enabled or not self._tracking:
            return {"enabled": False}

        current, peak = tracemalloc.get_traced_memory()
        return {
            "enabled": True,
            "current_mb": current / 1024 / 1024,
            "peak_mb": peak / 1024 / 1024,
            "tracked_peak_mb": self._peak_memory,
            "snapshots_taken": len(self._snapshots),
        }
