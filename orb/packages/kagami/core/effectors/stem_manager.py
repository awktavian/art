"""Stem Manager — Intelligent Stem Caching and Rendering.

Manages orchestral stem rendering with:
- Cache preservation (don't re-render good stems)
- Parallel rendering support
- Progress tracking
- Quality verification

Created: January 6, 2026
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from kagami.core.effectors.audio_verification import (
    AudioMetrics,
    analyze_wav,
    check_audio_exists,
    verify_stems,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# =============================================================================
# Constants
# =============================================================================

STEMS_SUBDIR = "stems"
CACHE_FILE = "stem_cache.json"


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class StemInfo:
    """Information about a single stem."""

    name: str
    instrument_key: str
    midi_path: str
    rpp_path: str
    wav_path: str
    has_audio: bool = False
    peak: int = 0
    rms: float = 0.0
    duration_sec: float = 0.0
    rendered_at: float = 0.0
    render_time_sec: float = 0.0
    error: str | None = None


@dataclass
class StemCache:
    """Cache of stem rendering state."""

    project_name: str
    stems: dict[str, StemInfo] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def save(self, cache_dir: Path) -> None:
        """Save cache to disk."""
        cache_path = cache_dir / CACHE_FILE
        self.updated_at = time.time()
        with open(cache_path, "w") as f:
            json.dump(asdict(self), f, indent=2)

    @classmethod
    def load(cls, cache_dir: Path) -> StemCache | None:
        """Load cache from disk."""
        cache_path = cache_dir / CACHE_FILE
        if not cache_path.exists():
            return None
        try:
            with open(cache_path) as f:
                data = json.load(f)
            cache = cls(
                project_name=data["project_name"],
                created_at=data.get("created_at", time.time()),
                updated_at=data.get("updated_at", time.time()),
            )
            for name, stem_data in data.get("stems", {}).items():
                cache.stems[name] = StemInfo(**stem_data)
            return cache
        except Exception as e:
            logger.warning("Failed to load stem cache: %s", e)
            return None


@dataclass
class RenderProgress:
    """Progress tracking for stem rendering."""

    total: int
    completed: int = 0
    failed: int = 0
    skipped: int = 0  # Already cached with audio
    current: str = ""
    errors: dict[str, str] = field(default_factory=dict)

    @property
    def percent(self) -> float:
        """Completion percentage."""
        if self.total == 0:
            return 100.0
        return (self.completed + self.failed + self.skipped) / self.total * 100


# =============================================================================
# Stem Manager
# =============================================================================


class StemManager:
    """Manages stem rendering with caching and verification.

    Features:
    - Cache preservation: Won't re-render stems that have good audio
    - Progress tracking: Callbacks for progress updates
    - Error handling: Tracks failures per stem
    - Verification: Uses proper 24-bit audio analysis
    """

    def __init__(
        self,
        output_dir: Path,
        project_name: str,
        on_progress: Callable[[RenderProgress], None] | None = None,
    ):
        """Initialize stem manager.

        Args:
            output_dir: Base output directory
            project_name: Name of the project
            on_progress: Optional callback for progress updates
        """
        self.output_dir = Path(output_dir)
        self.project_name = project_name
        self.stems_dir = self.output_dir / STEMS_SUBDIR
        self.on_progress = on_progress

        # Create directories
        self.stems_dir.mkdir(parents=True, exist_ok=True)

        # Load or create cache
        self.cache = StemCache.load(self.output_dir) or StemCache(project_name=project_name)

    def get_stem_wav_path(self, stem_name: str) -> Path:
        """Get WAV path for a stem."""
        return self.stems_dir / f"{stem_name}.wav"

    def get_stem_rpp_path(self, stem_name: str) -> Path:
        """Get RPP path for a stem."""
        return self.stems_dir / f"{stem_name}.rpp"

    def check_stem_cached(self, stem_name: str) -> bool:
        """Check if a stem has good cached audio.

        Args:
            stem_name: Name of the stem

        Returns:
            True if stem has cached audio with content
        """
        wav_path = self.get_stem_wav_path(stem_name)
        if not wav_path.exists():
            return False

        # Check cache first
        if stem_name in self.cache.stems:
            stem_info = self.cache.stems[stem_name]
            if stem_info.has_audio:
                # Verify file still exists and hasn't changed
                if wav_path.stat().st_mtime <= stem_info.rendered_at:
                    return True

        # Verify actual audio content
        return check_audio_exists(wav_path)

    def get_stems_to_render(self, all_stems: list[str]) -> list[str]:
        """Get list of stems that need rendering.

        Excludes stems that already have cached audio.

        Args:
            all_stems: List of all stem names

        Returns:
            List of stems that need rendering
        """
        to_render = []
        for stem in all_stems:
            if not self.check_stem_cached(stem):
                to_render.append(stem)
            else:
                logger.debug("Stem %s has cached audio, skipping", stem)
        return to_render

    def update_stem_info(
        self, stem_name: str, metrics: AudioMetrics, render_time: float = 0.0
    ) -> None:
        """Update stem info in cache.

        Args:
            stem_name: Name of the stem
            metrics: Audio metrics from analysis
            render_time: Time taken to render (seconds)
        """
        wav_path = self.get_stem_wav_path(stem_name)
        rpp_path = self.get_stem_rpp_path(stem_name)

        self.cache.stems[stem_name] = StemInfo(
            name=stem_name,
            instrument_key=stem_name,
            midi_path="",  # Will be filled by caller if needed
            rpp_path=str(rpp_path),
            wav_path=str(wav_path),
            has_audio=metrics.has_audio,
            peak=metrics.peak,
            rms=metrics.rms,
            duration_sec=metrics.duration_sec,
            rendered_at=time.time(),
            render_time_sec=render_time,
            error=metrics.error,
        )
        self.cache.save(self.output_dir)

    def verify_all_stems(self) -> tuple[list[str], list[str]]:
        """Verify all stems in the stems directory.

        Returns:
            Tuple of (stems_with_audio, silent_stems)
        """
        with_audio, silent = verify_stems(self.stems_dir)

        # Update cache
        for stem_name in with_audio:
            wav_path = self.get_stem_wav_path(stem_name)
            metrics = analyze_wav(wav_path)
            self.update_stem_info(stem_name, metrics)

        for stem_name in silent:
            wav_path = self.get_stem_wav_path(stem_name)
            if wav_path.exists():
                metrics = analyze_wav(wav_path)
                self.update_stem_info(stem_name, metrics)

        return with_audio, silent

    def get_render_summary(self) -> dict:
        """Get summary of stems in cache.

        Returns:
            Summary dict with counts and lists
        """
        with_audio = []
        silent = []
        missing = []

        for stem_name, info in self.cache.stems.items():
            wav_path = self.get_stem_wav_path(stem_name)
            if not wav_path.exists():
                missing.append(stem_name)
            elif info.has_audio:
                with_audio.append(stem_name)
            else:
                silent.append(stem_name)

        return {
            "with_audio": with_audio,
            "silent": silent,
            "missing": missing,
            "total": len(self.cache.stems),
        }

    async def render_stem(
        self,
        stem_name: str,
        render_func: Callable[[str, Path, Path], tuple[bool, str]],
    ) -> bool:
        """Render a single stem using the provided render function.

        Args:
            stem_name: Name of the stem
            render_func: Function(stem_name, rpp_path, wav_path) -> (success, error)

        Returns:
            True if render succeeded with audio
        """
        rpp_path = self.get_stem_rpp_path(stem_name)
        wav_path = self.get_stem_wav_path(stem_name)

        if not rpp_path.exists():
            logger.error("RPP not found for stem %s: %s", stem_name, rpp_path)
            return False

        t0 = time.time()

        # Call render function
        success, error = await asyncio.get_event_loop().run_in_executor(
            None, render_func, stem_name, rpp_path, wav_path
        )

        render_time = time.time() - t0

        if not success:
            logger.error("Render failed for %s: %s", stem_name, error)
            return False

        # Verify audio
        metrics = analyze_wav(wav_path)
        self.update_stem_info(stem_name, metrics, render_time)

        if not metrics.has_audio:
            logger.warning("Stem %s rendered but has no audio", stem_name)
            return False

        logger.info(
            "✓ Rendered %s: peak=%d rms=%.0f (%.1fs)",
            stem_name,
            metrics.peak,
            metrics.rms,
            render_time,
        )
        return True

    async def render_all(
        self,
        stems: list[str],
        render_func: Callable[[str, Path, Path], tuple[bool, str]],
        parallel: int = 1,
        skip_cached: bool = True,
    ) -> RenderProgress:
        """Render multiple stems with optional parallelism.

        Args:
            stems: List of stem names to render
            render_func: Function(stem_name, rpp_path, wav_path) -> (success, error)
            parallel: Number of parallel renders (1 for sequential)
            skip_cached: If True, skip stems with cached audio

        Returns:
            RenderProgress with final status
        """
        # Filter out cached stems if requested
        if skip_cached:
            to_render = self.get_stems_to_render(stems)
            skipped = len(stems) - len(to_render)
        else:
            to_render = stems
            skipped = 0

        progress = RenderProgress(
            total=len(stems),
            skipped=skipped,
        )

        if self.on_progress:
            self.on_progress(progress)

        # Render stems
        if parallel <= 1:
            # Sequential rendering
            for stem_name in to_render:
                progress.current = stem_name
                if self.on_progress:
                    self.on_progress(progress)

                success = await self.render_stem(stem_name, render_func)

                if success:
                    progress.completed += 1
                else:
                    progress.failed += 1
                    progress.errors[stem_name] = (
                        self.cache.stems.get(
                            stem_name,
                            StemInfo(
                                name=stem_name,
                                instrument_key="",
                                midi_path="",
                                rpp_path="",
                                wav_path="",
                            ),
                        ).error
                        or "Unknown error"
                    )

                if self.on_progress:
                    self.on_progress(progress)
        else:
            # Parallel rendering with semaphore
            sem = asyncio.Semaphore(parallel)

            async def render_with_sem(stem_name: str) -> tuple[str, bool]:
                async with sem:
                    success = await self.render_stem(stem_name, render_func)
                    return stem_name, success

            tasks = [render_with_sem(stem) for stem in to_render]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in results:
                if isinstance(result, Exception):
                    progress.failed += 1
                else:
                    stem_name, success = result
                    if success:
                        progress.completed += 1
                    else:
                        progress.failed += 1
                        progress.errors[stem_name] = "Render failed"

        progress.current = ""
        if self.on_progress:
            self.on_progress(progress)

        return progress


# =============================================================================
# Factory Functions
# =============================================================================


def get_stem_manager(
    output_dir: Path | str,
    project_name: str,
    on_progress: Callable[[RenderProgress], None] | None = None,
) -> StemManager:
    """Create a stem manager.

    Args:
        output_dir: Base output directory
        project_name: Project name
        on_progress: Optional progress callback

    Returns:
        Configured StemManager
    """
    return StemManager(Path(output_dir), project_name, on_progress)


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "CACHE_FILE",
    "STEMS_SUBDIR",
    "RenderProgress",
    "StemCache",
    "StemInfo",
    "StemManager",
    "get_stem_manager",
]
