"""Pluggable Renderer Architecture.

This module provides a unified interface for audio rendering backends.

Supported Renderers:
- ReaperRenderer (BBC): High-quality orchestral via BBC Symphony Orchestra + REAPER
- FluidSynthRenderer: Lightweight fallback using FluidSynth + SoundFonts
- DAWDreamerRenderer: Headless synthesis for non-sample-based VSTs

Rendering Modes:
- Serial: render() - One instrument at a time (simpler)
- Parallel: render_orchestra_parallel() - All instruments simultaneously (faster)

Usage:
    from kagami.core.effectors.renderers import get_renderer, render, RenderConfig

    # Use default (BBC if available, else FluidSynth)
    result = await render(midi_path, output_path)

    # Use specific renderer
    bbc = get_renderer("bbc")
    result = await bbc.render(midi_path, output_path)

    # Parallel rendering with VBAP spatial audio
    from kagami.core.effectors.renderers.parallel import render_orchestra_parallel
    result = await render_orchestra_parallel(midi_path, output_path, spatial=True)

    # With configuration
    config = RenderConfig(
        sample_rate=48000,
        channels=2,
        apply_expression=True,
        apply_spatialization=True,
    )
    result = await render(midi_path, output_path, config=config)

Created: January 1, 2026
Updated: January 2, 2026 - Added parallel rendering, ReaperRenderer
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================


class RenderQuality(Enum):
    """Render quality presets."""

    DRAFT = "draft"  # Fast preview, lower quality
    STANDARD = "standard"  # Balanced quality/speed
    HIGH = "high"  # High quality, slower
    MASTER = "master"  # Maximum quality for final output


@dataclass
class RenderConfig:
    """Configuration for audio rendering.

    Attributes:
        sample_rate: Output sample rate in Hz
        channels: Number of output channels (2=stereo, 6=5.1, 10=5.1.4)
        bit_depth: Output bit depth (16, 24, or 32)
        quality: Quality preset
        apply_expression: Add dynamics and expression to MIDI
        apply_keyswitches: Add articulation keyswitches
        apply_spatialization: Apply 5.1.4 VBAP spatialization
        normalize: Normalize output volume
        tempo: Override MIDI tempo (None=use file tempo)
        expression_style: Style of expression (romantic, classical, baroque)
    """

    sample_rate: int = 48000
    channels: int = 2
    bit_depth: int = 24
    quality: RenderQuality = RenderQuality.STANDARD
    apply_expression: bool = True
    apply_keyswitches: bool = True
    apply_spatialization: bool = False
    normalize: bool = True
    tempo: float | None = None
    expression_style: str = "romantic"

    # Extra parameters for specific renderers
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class RenderResult:
    """Result of a rendering operation.

    Attributes:
        success: Whether rendering completed successfully
        output_path: Path to the rendered audio file
        duration: Duration of rendered audio in seconds
        renderer: Name of the renderer used
        error: Error message if success=False
        metadata: Additional metadata about the render
    """

    success: bool
    output_path: Path | None = None
    duration: float = 0.0
    renderer: str = ""
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


# =============================================================================
# Protocol
# =============================================================================


@runtime_checkable
class RendererProtocol(Protocol):
    """Protocol for pluggable audio renderers.

    Any renderer implementation must satisfy this protocol to be used
    in the unified rendering pipeline.
    """

    @property
    def name(self) -> str:
        """Unique name identifier for this renderer."""
        ...

    @property
    def available(self) -> bool:
        """Whether this renderer is currently available for use."""
        ...

    async def initialize(self) -> bool:
        """Initialize the renderer.

        Returns:
            True if initialization succeeded
        """
        ...

    async def render(
        self,
        midi_path: Path,
        output_path: Path,
        config: RenderConfig | None = None,
    ) -> RenderResult:
        """Render a MIDI file to audio.

        Args:
            midi_path: Path to input MIDI file
            output_path: Path for output audio file
            config: Rendering configuration

        Returns:
            RenderResult with success status and output info
        """
        ...

    async def cleanup(self) -> None:
        """Clean up renderer resources."""
        ...


# =============================================================================
# Base Implementation
# =============================================================================


class BaseRenderer(ABC):
    """Abstract base class for renderers.

    Provides common functionality and enforces the protocol.
    """

    def __init__(self) -> None:
        self._initialized = False
        self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique name identifier for this renderer."""
        ...

    @property
    @abstractmethod
    def available(self) -> bool:
        """Whether this renderer is currently available for use."""
        ...

    async def initialize(self) -> bool:
        """Initialize the renderer."""
        if self._initialized:
            return True

        try:
            result = await self._do_initialize()
            self._initialized = result
            return result
        except Exception as e:
            self._logger.error(f"Failed to initialize {self.name}: {e}")
            return False

    @abstractmethod
    async def _do_initialize(self) -> bool:
        """Subclass initialization logic."""
        ...

    async def render(
        self,
        midi_path: Path,
        output_path: Path,
        config: RenderConfig | None = None,
    ) -> RenderResult:
        """Render a MIDI file to audio."""
        if not self._initialized:
            await self.initialize()

        if not self.available:
            return RenderResult(
                success=False,
                renderer=self.name,
                error=f"Renderer {self.name} is not available",
            )

        config = config or RenderConfig()

        try:
            return await self._do_render(midi_path, output_path, config)
        except Exception as e:
            self._logger.exception(f"Render failed: {e}")
            return RenderResult(
                success=False,
                renderer=self.name,
                error=str(e),
            )

    @abstractmethod
    async def _do_render(
        self,
        midi_path: Path,
        output_path: Path,
        config: RenderConfig,
    ) -> RenderResult:
        """Subclass rendering logic."""
        ...

    async def cleanup(self) -> None:
        """Clean up renderer resources."""
        self._initialized = False


# =============================================================================
# Registry
# =============================================================================


_renderers: dict[str, RendererProtocol] = {}
_default_renderer: str | None = None


def register_renderer(renderer: RendererProtocol) -> None:
    """Register a renderer implementation.

    Args:
        renderer: Renderer instance to register
    """
    _renderers[renderer.name] = renderer
    logger.info(f"Registered renderer: {renderer.name}")


def get_renderer(name: str | None = None) -> RendererProtocol | None:
    """Get a renderer by name.

    Args:
        name: Renderer name, or None for default

    Returns:
        Renderer instance or None if not found
    """
    if name is None:
        name = _default_renderer

    if name is None:
        # Return first available renderer
        for renderer in _renderers.values():
            if renderer.available:
                return renderer
        return None

    return _renderers.get(name)


def get_available_renderers() -> list[str]:
    """Get names of all available renderers."""
    return [name for name, r in _renderers.items() if r.available]


def set_default_renderer(name: str) -> None:
    """Set the default renderer.

    Args:
        name: Name of renderer to use as default
    """
    global _default_renderer
    if name not in _renderers:
        raise ValueError(f"Unknown renderer: {name}. Available: {list(_renderers.keys())}")
    _default_renderer = name


# =============================================================================
# Convenience Functions
# =============================================================================


async def render(
    midi_path: Path | str,
    output_path: Path | str,
    config: RenderConfig | None = None,
    renderer_name: str | None = None,
) -> RenderResult:
    """Render a MIDI file to audio using the best available renderer.

    Args:
        midi_path: Path to input MIDI file
        output_path: Path for output audio file
        config: Rendering configuration
        renderer_name: Specific renderer to use (None=auto-select)

    Returns:
        RenderResult with success status and output info
    """
    midi_path = Path(midi_path)
    output_path = Path(output_path)

    renderer = get_renderer(renderer_name)
    if renderer is None:
        return RenderResult(
            success=False,
            error="No renderers available. Install BBC SO or FluidSynth.",
        )

    return await renderer.render(midi_path, output_path, config)


async def render_to_mp3(
    midi_path: Path | str,
    output_path: Path | str,
    config: RenderConfig | None = None,
    renderer_name: str | None = None,
) -> RenderResult:
    """Render a MIDI file to MP3.

    Renders to WAV first, then converts to MP3.

    Args:
        midi_path: Path to input MIDI file
        output_path: Path for output MP3 file
        config: Rendering configuration
        renderer_name: Specific renderer to use

    Returns:
        RenderResult with success status and output info
    """
    import subprocess
    import tempfile

    midi_path = Path(midi_path)
    output_path = Path(output_path)

    # Render to WAV first
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        wav_path = Path(f.name)

    result = await render(midi_path, wav_path, config, renderer_name)
    if not result.success:
        return result

    # Convert to MP3
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(wav_path), "-b:a", "320k", str(output_path)],
            check=True,
            capture_output=True,
        )
        result.output_path = output_path
        result.metadata["format"] = "mp3"
    except subprocess.CalledProcessError as e:
        result.success = False
        result.error = f"MP3 conversion failed: {e.stderr.decode()}"
    finally:
        wav_path.unlink(missing_ok=True)

    return result


# =============================================================================
# Auto-import renderers to register them
# =============================================================================


def _auto_register_renderers() -> None:
    """Import renderer modules to trigger auto-registration."""
    try:
        # Import REAPER/BBC renderer (registers itself on import)
        from kagami.core.effectors.renderers.reaper import ReaperRenderer
    except ImportError:
        logger.debug("REAPER renderer not available")

    try:
        # Import FluidSynth renderer (registers itself on import)
        from kagami.core.effectors.renderers.fluidsynth_renderer import FluidSynthRenderer
    except ImportError:
        logger.debug("FluidSynth renderer not available")

    try:
        # Import DAWDreamer renderer (registers itself on import)
        from kagami.core.effectors.renderers.dawdreamer import DAWDreamerRenderer
    except ImportError:
        logger.debug("DAWDreamer renderer not available")


# =============================================================================
# High-Level API (recommended entry point)
# =============================================================================

try:
    from kagami.core.effectors.renderers.api import (
        RenderOptions,
        Style,
        get_available_styles,
        preview,
        render_orchestra,
        render_with_gui,
    )
    from kagami.core.effectors.renderers.api import (
        RenderResult as OrchestraRenderResult,
    )
except ImportError:
    pass

# =============================================================================
# Parallel Rendering API
# =============================================================================

try:
    from kagami.core.effectors.renderers.parallel import (
        MAX_PARALLEL_RENDERS,
        ORCHESTRA_POSITIONS,
        ParallelRenderResult,
        render_orchestra_parallel,
        render_parallel,
    )
except ImportError:
    pass

# =============================================================================
# Quality Analysis API
# =============================================================================

try:
    from kagami.core.effectors.renderers.quality_analyzer import (
        QualityAnalyzer,
        QualityReport,
        QualityThresholds,
        analyze_render,
        quick_check,
        validate_render_output,
    )
except ImportError:
    pass


# =============================================================================
# VM and Async Rendering API
# =============================================================================

try:
    from kagami.core.effectors.renderers.vm_renderer import (
        AsyncHostRenderer,
        VMRenderBatchResult,
        VMRenderer,
        VMRenderJob,
        VMRenderResult,
        get_best_renderer,
    )
except ImportError:
    pass


# Register renderers on module load
_auto_register_renderers()


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "MAX_PARALLEL_RENDERS",
    "ORCHESTRA_POSITIONS",
    # VM and Async Rendering API
    "AsyncHostRenderer",
    "BaseRenderer",
    "OrchestraRenderResult",
    "ParallelRenderResult",
    # Quality Analysis API
    "QualityAnalyzer",
    "QualityReport",
    "QualityThresholds",
    # Configuration
    "RenderConfig",
    "RenderOptions",
    "RenderQuality",
    "RenderResult",
    # Protocol and base class
    "RendererProtocol",
    # High-level Orchestra API (recommended)
    "Style",
    # VM Rendering
    "VMRenderBatchResult",
    "VMRenderJob",
    "VMRenderResult",
    "VMRenderer",
    "analyze_render",
    "get_available_renderers",
    "get_available_styles",
    "get_best_renderer",
    "get_renderer",
    "preview",
    "quick_check",
    # Registry
    "register_renderer",
    # Low-level convenience
    "render",
    "render_orchestra",
    "render_orchestra_parallel",
    # Parallel Rendering API
    "render_parallel",
    "render_to_mp3",
    "render_with_gui",
    "set_default_renderer",
    "validate_render_output",
]
