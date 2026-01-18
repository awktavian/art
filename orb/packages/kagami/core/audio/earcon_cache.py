"""Earcon Cache Service.

Pre-loads orchestral earcons for instant playback.

ARCHITECTURE:
=============

    ┌─────────────────────────────────────────────────────────────────┐
    │                     EarconCacheService                           │
    │                                                                  │
    │   Startup:                                                       │
    │   1. Load pre-rendered orchestral earcons from disk             │
    │   2. Fall back to synthesis if orchestral version missing       │
    │   3. Store in memory (dict[name] → PCM audio)                   │
    │   4. Broadcast to clients for their local caches                │
    │                                                                  │
    │   Runtime:                                                       │
    │   - play_earcon("name") → instant playback from cache           │
    │   - get_earcon("name") → return audio data                      │
    │                                                                  │
    │   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐     │
    │   │   Memory     │    │  Orchestral  │    │   Clients    │     │
    │   │  (instant)   │ ←─ │  (BBC SO)    │ → │  (broadcast) │     │
    │   └──────────────┘    └──────────────┘    └──────────────┘     │
    └─────────────────────────────────────────────────────────────────┘

DISK LOCATIONS:
===============

    ~/.kagami/earcons/spatialized/     (PREFERRED - Orchestral BBC SO)
    ├── notification.wav               (5.1.4 spatialized)
    ├── success.wav
    ├── error.wav
    └── ...

    ~/.kagami/cache/earcons/           (FALLBACK - Synthesized)
    ├── notification.wav
    └── ...

QUALITY STANDARDS:
==================

    "What would Terence Fletcher say? What would John Williams say?
     What would Danny Elfman say?!"

    Each earcon is:
    - Orchestrated with BBC Symphony Orchestra
    - Emotionally intentional (leitmotif, character)
    - Spatialized in 5.1.4 Dolby Atmos

Created: January 4, 2026
Updated: January 4, 2026 — Virtuoso Sound Library integration
Colony: ⚒️ Forge (e₂) — Building for speed
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf

from kagami.core.audio.protocol import (
    DEFAULT_SAMPLE_RATE,
    AudioFormat,
    AudioMetadata,
    AudioPriority,
)

logger = logging.getLogger(__name__)

# Disk cache locations (in priority order)
ORCHESTRAL_DIR = Path.home() / ".kagami" / "earcons" / "spatialized"  # BBC SO rendered
FALLBACK_DIR = Path.home() / ".kagami" / "cache" / "earcons"  # Synthesized fallback
CACHE_DIR = FALLBACK_DIR  # Legacy alias


@dataclass
class CachedEarcon:
    """A cached earcon ready for instant playback."""

    name: str
    audio: np.ndarray  # PCM float32
    sample_rate: int = DEFAULT_SAMPLE_RATE
    channels: int = 2
    duration_ms: float = 0.0
    synthesized_at: float = field(default_factory=time.time)
    file_path: Path | None = None

    @property
    def metadata(self) -> AudioMetadata:
        """Get audio metadata."""
        return AudioMetadata(
            sample_rate=self.sample_rate,
            channels=self.channels,
            format=AudioFormat.PCM_F32LE,
            duration_ms=self.duration_ms,
        )


@dataclass
class CacheStats:
    """Statistics for the earcon cache."""

    total_earcons: int = 0
    total_bytes: int = 0
    hits: int = 0
    misses: int = 0
    synthesis_time_ms: float = 0.0
    load_time_ms: float = 0.0

    @property
    def hit_rate(self) -> float:
        """Cache hit rate."""
        total = self.hits + self.misses
        if total == 0:
            return 0.0
        return self.hits / total


class EarconCacheService:
    """Pre-synthesized earcon cache for instant playback.

    Usage:
        cache = await get_earcon_cache()

        # Get earcon audio
        audio = cache.get("notification")

        # Play earcon
        await cache.play("success")

        # Get all earcon names
        names = cache.list_earcons()
    """

    def __init__(self) -> None:
        """Initialize cache service."""
        self._cache: dict[str, CachedEarcon] = {}
        self._stats = CacheStats()
        self._initialized = False
        self._initializing = False
        self._init_lock = asyncio.Lock()

    async def initialize(self) -> None:
        """Initialize cache by loading/synthesizing all earcons."""
        async with self._init_lock:
            if self._initialized or self._initializing:
                return

            self._initializing = True
            start = time.perf_counter()

            try:
                # Ensure cache directories exist
                ORCHESTRAL_DIR.mkdir(parents=True, exist_ok=True)
                FALLBACK_DIR.mkdir(parents=True, exist_ok=True)

                # Load earcon definitions (includes orchestral earcons)
                from kagami.core.ambient.spatial_earcons import (
                    EARCON_REGISTRY,
                    _init_default_earcons,
                )

                # Also load orchestral earcon definitions
                try:
                    from kagami.core.effectors.earcon_orchestrator import (
                        EARCON_REGISTRY as ORCHESTRATOR_REGISTRY,
                    )

                    # Merge orchestrator earcons into main registry
                    for name, defn in ORCHESTRATOR_REGISTRY.items():
                        if name not in EARCON_REGISTRY:
                            EARCON_REGISTRY[name] = defn
                    logger.debug(f"Merged {len(ORCHESTRATOR_REGISTRY)} orchestral earcons")
                except ImportError:
                    logger.debug("Orchestral earcon definitions not available")

                # Ensure defaults are registered
                if not EARCON_REGISTRY:
                    _init_default_earcons()

                logger.info(
                    f"Loading {len(EARCON_REGISTRY)} earcons "
                    f"(orchestral: {ORCHESTRAL_DIR}, fallback: {FALLBACK_DIR})"
                )

                # Load/synthesize each earcon in parallel
                tasks = []
                for name in EARCON_REGISTRY:
                    tasks.append(self._load_or_synthesize(name))

                await asyncio.gather(*tasks)

                elapsed = (time.perf_counter() - start) * 1000
                self._stats.load_time_ms = elapsed
                self._initialized = True

                logger.info(
                    f"✓ EarconCache initialized: "
                    f"{len(self._cache)} earcons, "
                    f"{self._stats.total_bytes / 1024:.1f}KB, "
                    f"{elapsed:.0f}ms"
                )

            except Exception as e:
                logger.error(f"Failed to initialize earcon cache: {e}")
                raise

            finally:
                self._initializing = False

    async def _load_or_synthesize(self, name: str) -> None:
        """Load earcon from disk (preferring orchestral) or synthesize.

        Priority order:
        1. Orchestral BBC SO rendered (~/.kagami/earcons/spatialized/)
        2. Fallback synthesized (~/.kagami/cache/earcons/)
        3. Runtime synthesis (if neither exists)
        """
        # Check orchestral directory first (preferred)
        orchestral_file = ORCHESTRAL_DIR / f"{name}.wav"
        fallback_file = FALLBACK_DIR / f"{name}.wav"

        # Try orchestral first
        for cache_file, source in [
            (orchestral_file, "orchestral"),
            (fallback_file, "fallback"),
        ]:
            if cache_file.exists():
                try:
                    audio, sr = sf.read(cache_file, dtype="float32")

                    # Handle channel normalization
                    if audio.ndim == 1:
                        # Mono to stereo
                        audio = np.column_stack([audio, audio])
                    elif audio.shape[1] > 2:
                        # Multi-channel (5.1.4) - keep as-is for spatial playback
                        # but also create stereo downmix for compatibility
                        pass

                    self._cache[name] = CachedEarcon(
                        name=name,
                        audio=audio,
                        sample_rate=sr,
                        channels=audio.shape[1] if audio.ndim > 1 else 1,
                        duration_ms=len(audio) / sr * 1000,
                        file_path=cache_file,
                    )
                    self._stats.total_earcons += 1
                    self._stats.total_bytes += audio.nbytes

                    logger.debug(f"Loaded earcon '{name}' from {source}: {cache_file}")
                    return

                except Exception as e:
                    logger.warning(
                        f"Failed to load {source} earcon '{name}' from {cache_file}: {e}"
                    )

        # Synthesize as last resort
        logger.info(f"No pre-rendered earcon for '{name}', synthesizing...")
        await self._synthesize(name)

    async def _synthesize(self, name: str) -> None:
        """Synthesize an earcon and cache it.

        For orchestral earcons (with orchestration), uses EarconRenderer.
        For legacy earcons (with synthesizer), uses the synthesizer function.
        """
        from kagami.core.ambient.spatial_earcons import get_earcon

        definition = get_earcon(name)
        if definition is None:
            logger.warning(f"No definition for earcon '{name}'")
            return

        start = time.perf_counter()

        try:
            audio: np.ndarray | None = None
            cache_file: Path

            # Check if this is an orchestral earcon (has orchestration)
            if hasattr(definition, "orchestration") and definition.orchestration:
                # Use EarconRenderer for orchestral synthesis
                try:
                    from kagami.core.effectors.earcon_renderer import EarconRenderer

                    renderer = EarconRenderer()
                    spatialized_path = await renderer.render_earcon(definition)
                    audio, _ = sf.read(spatialized_path, dtype="float32")
                    cache_file = spatialized_path
                    logger.info(f"Rendered orchestral earcon '{name}'")

                except ImportError:
                    logger.warning("EarconRenderer not available, falling back to synthesizer")
                except Exception as e:
                    logger.warning(f"Orchestral render failed for '{name}': {e}")

            # Fallback to legacy synthesizer
            if audio is None and hasattr(definition, "synthesizer") and definition.synthesizer:
                loop = asyncio.get_event_loop()
                audio = await loop.run_in_executor(
                    None,
                    definition.synthesizer,
                    definition.duration,
                )
                cache_file = FALLBACK_DIR / f"{name}.wav"

            if audio is None:
                logger.warning(f"No synthesis method available for '{name}'")
                return

            # Convert to float32
            if audio.dtype != np.float32:
                audio = audio.astype(np.float32)

            # Handle mono (convert to stereo for compatibility)
            if audio.ndim == 1:
                audio = np.column_stack([audio, audio])

            elapsed = (time.perf_counter() - start) * 1000
            self._stats.synthesis_time_ms += elapsed

            # Save to disk cache (fallback location for synthesized)
            if "cache_file" not in locals() or not cache_file.exists():
                cache_file = FALLBACK_DIR / f"{name}.wav"
                cache_file.parent.mkdir(parents=True, exist_ok=True)
                sf.write(cache_file, audio, DEFAULT_SAMPLE_RATE)

            # Store in memory
            self._cache[name] = CachedEarcon(
                name=name,
                audio=audio,
                sample_rate=DEFAULT_SAMPLE_RATE,
                channels=audio.shape[1] if audio.ndim > 1 else 1,
                duration_ms=len(audio) / DEFAULT_SAMPLE_RATE * 1000,
                file_path=cache_file,
            )
            self._stats.total_earcons += 1
            self._stats.total_bytes += audio.nbytes

            logger.debug(f"Synthesized earcon '{name}' in {elapsed:.0f}ms")

        except Exception as e:
            logger.error(f"Failed to synthesize earcon '{name}': {e}")

    def get(self, name: str) -> np.ndarray | None:
        """Get earcon audio data.

        Args:
            name: Earcon name

        Returns:
            Audio array or None if not found
        """
        cached = self._cache.get(name)
        if cached:
            self._stats.hits += 1
            return cached.audio
        else:
            self._stats.misses += 1
            return None

    def get_cached(self, name: str) -> CachedEarcon | None:
        """Get full cached earcon object.

        Args:
            name: Earcon name

        Returns:
            CachedEarcon or None
        """
        return self._cache.get(name)

    def list_earcons(self) -> list[str]:
        """List all cached earcon names."""
        return list(self._cache.keys())

    def list_all(self) -> list[CachedEarcon]:
        """List all cached earcons."""
        return list(self._cache.values())

    async def play(
        self,
        name: str,
        priority: AudioPriority = AudioPriority.NORMAL,
        volume: float = 1.0,
        room: str | None = None,
    ) -> str:
        """Play an earcon via the audio bus.

        Args:
            name: Earcon name
            priority: Playback priority
            volume: Volume (0.0-1.0)
            room: Target room

        Returns:
            Request ID
        """
        from kagami.core.audio.event_bus import play_earcon

        return await play_earcon(name, priority, volume, room)

    async def broadcast_all_to_clients(self) -> None:
        """Broadcast all earcons to connected clients for caching.

        Called when a new client connects to pre-populate its cache.
        """
        from kagami.core.audio.event_bus import get_audio_bus

        bus = await get_audio_bus()

        for name, cached in self._cache.items():
            await bus.cache_earcon(name, cached.audio, cached.metadata)
            # Small delay to not overwhelm
            await asyncio.sleep(0.01)

        logger.info(f"Broadcast {len(self._cache)} earcons to clients")

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        return {
            "total_earcons": self._stats.total_earcons,
            "total_bytes": self._stats.total_bytes,
            "total_mb": self._stats.total_bytes / 1024 / 1024,
            "hits": self._stats.hits,
            "misses": self._stats.misses,
            "hit_rate": self._stats.hit_rate,
            "synthesis_time_ms": self._stats.synthesis_time_ms,
            "load_time_ms": self._stats.load_time_ms,
            "earcons": list(self._cache.keys()),
        }

    async def refresh(self, name: str | None = None) -> None:
        """Refresh earcon(s) by re-synthesizing.

        Args:
            name: Specific earcon or None for all

        Note:
            Does NOT delete orchestral pre-rendered files - only fallback cache.
            To regenerate orchestral earcons, run generate_virtuoso_earcons.py.
        """
        if name:
            # Delete fallback cached file (preserve orchestral)
            cache_file = FALLBACK_DIR / f"{name}.wav"
            if cache_file.exists():
                cache_file.unlink()
            # Remove from memory
            self._cache.pop(name, None)
            # Re-load (will prefer orchestral if available)
            await self._load_or_synthesize(name)
        else:
            # Refresh all
            for earcon_name in list(self._cache.keys()):
                cache_file = FALLBACK_DIR / f"{earcon_name}.wav"
                if cache_file.exists():
                    cache_file.unlink()
            # Clear and reload
            self._cache.clear()
            self._stats = CacheStats()
            self._initialized = False
            await self.initialize()


# =============================================================================
# FACTORY (via centralized registry)
# =============================================================================

from kagami.core.shared_abstractions.singleton_consolidation import (
    get_singleton_registry,
)

_singleton_registry = get_singleton_registry()
get_earcon_cache = _singleton_registry.register_async("earcon_cache_service", EarconCacheService)


__all__ = [
    "CACHE_DIR",
    "FALLBACK_DIR",
    "ORCHESTRAL_DIR",
    "CacheStats",
    "CachedEarcon",
    "EarconCacheService",
    "get_earcon_cache",
]
