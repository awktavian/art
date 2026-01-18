"""Progress Tracking — Feedback for long operations.

Provides progress callbacks and logging for initialization
and other long-running operations.

Created: January 2, 2026
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ProgressUpdate:
    """A progress update."""

    stage: str
    progress: float  # 0.0 to 1.0
    message: str
    elapsed_ms: float
    estimated_remaining_ms: float | None = None


ProgressCallback = Callable[[ProgressUpdate], None]


@dataclass
class ProgressTracker:
    """Tracks progress through a multi-stage operation.

    Usage:
        tracker = ProgressTracker(stages=["connect", "discover", "setup"])

        async with tracker.stage("connect"):
            await connect()

        async with tracker.stage("discover"):
            await discover()

        # Or with callback
        tracker = ProgressTracker(stages=["a", "b"], callback=print_progress)
    """

    stages: list[str]
    callback: ProgressCallback | None = None
    _current_stage: int = field(default=0, init=False)
    _start_time: float = field(default_factory=time.time, init=False)
    _stage_start: float = field(default=0, init=False)
    _stage_times: dict[str, float] = field(default_factory=dict, init=False)

    def stage(self, name: str) -> StageContext:
        """Context manager for a stage.

        Args:
            name: Stage name (must be in stages list)

        Returns:
            Context manager that tracks the stage
        """
        return StageContext(self, name)

    def _start_stage(self, name: str) -> None:
        """Start a stage (internal)."""
        if name not in self.stages:
            raise ValueError(f"Unknown stage: {name}")

        self._current_stage = self.stages.index(name)
        self._stage_start = time.time()

        progress = self._current_stage / len(self.stages)
        elapsed = (time.time() - self._start_time) * 1000

        update = ProgressUpdate(
            stage=name,
            progress=progress,
            message=f"Starting {name}...",
            elapsed_ms=elapsed,
            estimated_remaining_ms=self._estimate_remaining(),
        )

        if self.callback:
            self.callback(update)

        logger.info(f"[{progress * 100:.0f}%] {name}...")

    def _end_stage(self, name: str) -> None:
        """End a stage (internal)."""
        duration = time.time() - self._stage_start
        self._stage_times[name] = duration

        progress = (self._current_stage + 1) / len(self.stages)
        elapsed = (time.time() - self._start_time) * 1000

        update = ProgressUpdate(
            stage=name,
            progress=progress,
            message=f"Completed {name} in {duration * 1000:.0f}ms",
            elapsed_ms=elapsed,
            estimated_remaining_ms=self._estimate_remaining(),
        )

        if self.callback:
            self.callback(update)

        logger.debug(f"[{progress * 100:.0f}%] {name} completed in {duration * 1000:.0f}ms")

    def _estimate_remaining(self) -> float | None:
        """Estimate remaining time based on completed stages."""
        if not self._stage_times:
            return None

        avg_time = sum(self._stage_times.values()) / len(self._stage_times)
        remaining_stages = len(self.stages) - self._current_stage - 1
        return avg_time * remaining_stages * 1000

    def summary(self) -> dict[str, Any]:
        """Get timing summary."""
        total = (time.time() - self._start_time) * 1000
        return {
            "total_ms": total,
            "stages": {name: t * 1000 for name, t in self._stage_times.items()},
            "completed": self._current_stage + 1,
            "total_stages": len(self.stages),
        }


class StageContext:
    """Context manager for a progress stage."""

    def __init__(self, tracker: ProgressTracker, name: str):
        self._tracker = tracker
        self._name = name

    async def __aenter__(self) -> StageContext:
        self._tracker._start_stage(self._name)
        return self

    async def __aexit__(self, *args: Any) -> None:
        self._tracker._end_stage(self._name)


def create_initialization_tracker(callback: ProgressCallback | None = None) -> ProgressTracker:
    """Create tracker for SmartHome initialization.

    Args:
        callback: Optional progress callback

    Returns:
        ProgressTracker configured for initialization stages
    """
    stages = [
        "load_credentials",
        "connect_control4",
        "connect_unifi",
        "connect_denon",
        "connect_tesla",
        "connect_eight_sleep",
        "connect_august",
        "connect_envisalink",
        "discover_devices",
        "build_rooms",
        "start_services",
        "start_monitoring",
    ]
    return ProgressTracker(stages=stages, callback=callback)


def log_progress(update: ProgressUpdate) -> None:
    """Simple progress logger callback."""
    bar_width = 20
    filled = int(bar_width * update.progress)
    bar = "█" * filled + "░" * (bar_width - filled)

    remaining = ""
    if update.estimated_remaining_ms:
        remaining = f" (~{update.estimated_remaining_ms / 1000:.1f}s remaining)"

    print(f"\r[{bar}] {update.progress * 100:3.0f}% {update.stage}{remaining}", end="", flush=True)

    if update.progress >= 1.0:
        print()  # Newline at end


__all__ = [
    "ProgressCallback",
    "ProgressTracker",
    "ProgressUpdate",
    "create_initialization_tracker",
    "log_progress",
]
