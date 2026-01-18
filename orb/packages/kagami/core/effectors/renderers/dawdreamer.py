"""DAWDreamer Renderer — Headless VST3 Synthesizer Rendering.

Renders MIDI using synthesizer VST3 plugins via DAWDreamer.
Fully headless - no external DAW required.

IMPORTANT: This renderer works with SYNTHESIZER VST3s only.
It does NOT work with sample-based plugins like BBC Symphony Orchestra,
Kontakt, or other sample libraries that require GUI initialization to load samples.

Supported VST types:
- Diva, Serum, Vital, Surge, Phase Plant
- Any synthesizer that doesn't load external samples

NOT supported:
- BBC Symphony Orchestra, Kontakt, Opus, Sample Tank
- Any plugin that requires GUI for sample loading

Colony: Forge (e₂)
Created: January 2, 2026
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from kagami.core.effectors.renderers import (
    BaseRenderer,
    RenderConfig,
    RenderResult,
    register_renderer,
)

logger = logging.getLogger(__name__)

# =============================================================================
# Constants
# =============================================================================

SAMPLE_RATE = 48000
BUFFER_SIZE = 512


# =============================================================================
# VST3 Preset Discovery
# =============================================================================


@dataclass
class VST3Info:
    """Information about a VST3 plugin."""

    path: Path
    name: str
    vendor: str = ""
    is_instrument: bool = True
    param_count: int = 0


def find_vst3_plugins(search_dirs: list[Path] | None = None) -> list[VST3Info]:
    """Find installed VST3 plugins.

    Args:
        search_dirs: Directories to search. Defaults to standard locations.

    Returns:
        List of discovered VST3 plugins.
    """
    if search_dirs is None:
        search_dirs = [
            Path("/Library/Audio/Plug-Ins/VST3"),
            Path.home() / "Library/Audio/Plug-Ins/VST3",
        ]

    plugins = []
    for dir_path in search_dirs:
        if not dir_path.exists():
            continue
        for vst3_path in dir_path.glob("*.vst3"):
            plugins.append(
                VST3Info(
                    path=vst3_path,
                    name=vst3_path.stem,
                )
            )
    return plugins


# =============================================================================
# DAWDreamer Renderer
# =============================================================================


class DAWDreamerRenderer(BaseRenderer):
    """Render synthesizer VST3s via DAWDreamer (headless).

    Works with synthesizers that don't require sample loading.
    Fully headless - no GUI, no external DAW.

    Example VSTs that work:
    - Diva, Serum, Vital, Surge, Phase Plant, Synth1

    Example VSTs that DON'T work:
    - BBC Symphony Orchestra, Kontakt, Opus (sample libraries need GUI init)
    """

    def __init__(self) -> None:
        super().__init__()
        self._dawdreamer_available = False
        self._engine: Any = None

    @property
    def name(self) -> str:
        return "dawdreamer"

    @property
    def available(self) -> bool:
        return self._dawdreamer_available

    async def _do_initialize(self) -> bool:
        """Initialize DAWDreamer."""
        try:
            import dawdreamer as daw

            self._engine = daw.RenderEngine(SAMPLE_RATE, BUFFER_SIZE)
            self._dawdreamer_available = True
            self._logger.info("✓ DAWDreamer initialized")
            return True
        except ImportError:
            self._logger.warning("DAWDreamer not installed. Install with: pip install dawdreamer")
            return False
        except Exception as e:
            self._logger.error("DAWDreamer init failed: %s", e)
            return False

    async def _do_render(
        self,
        midi_path: Path,
        output_path: Path,
        config: RenderConfig,
    ) -> RenderResult:
        """Render MIDI using a synthesizer VST3."""
        import dawdreamer as daw

        t0 = time.perf_counter()

        if not midi_path.exists():
            return RenderResult(
                success=False,
                renderer=self.name,
                error=f"MIDI not found: {midi_path}",
            )

        # Get VST3 path from config
        vst_path = config.extra.get("vst3_path")
        if not vst_path:
            return RenderResult(
                success=False,
                renderer=self.name,
                error="No vst3_path in config.extra",
            )
        vst_path = Path(vst_path)

        if not vst_path.exists():
            return RenderResult(
                success=False,
                renderer=self.name,
                error=f"VST3 not found: {vst_path}",
            )

        self._logger.info("🎹 DAWDreamer Render: %s with %s", midi_path.name, vst_path.name)

        try:
            # Create fresh engine for this render
            engine = daw.RenderEngine(config.sample_rate, BUFFER_SIZE)

            # Load VST3 plugin
            plugin = engine.make_plugin_processor("synth", str(vst_path))
            self._logger.info(
                "   Loaded VST3: %s (%d params)", vst_path.stem, plugin.get_num_parameters()
            )

            # Load preset if provided
            preset_path = config.extra.get("preset_path")
            if preset_path:
                preset_path = Path(preset_path)
                if preset_path.exists():
                    plugin.load_state(str(preset_path))
                    self._logger.info("   Loaded preset: %s", preset_path.name)

            # Apply any parameter overrides
            params = config.extra.get("params", {})
            for name, value in params.items():
                try:
                    plugin.set_parameter_by_name(name, value)
                except Exception as e:
                    self._logger.warning("   Failed to set param %s: %s", name, e)

            # Load MIDI
            plugin.load_midi(str(midi_path))
            self._logger.info("   Loaded MIDI: %s", midi_path.name)

            # Get duration from MIDI
            import pretty_midi

            midi = pretty_midi.PrettyMIDI(str(midi_path))
            duration = midi.get_end_time() + 2  # Add 2s tail for reverb/release

            # Build graph and render
            engine.load_graph([(plugin, [])])
            engine.render(duration)

            # Get audio
            audio = engine.get_audio()

            # Check for silence (common with sample-based plugins)
            if np.max(np.abs(audio)) < 0.001:
                return RenderResult(
                    success=False,
                    renderer=self.name,
                    error="Silent output - VST may require GUI initialization (sample library?)",
                )

            # Normalize if requested
            if config.normalize:
                peak = np.max(np.abs(audio))
                if peak > 0:
                    audio = audio / peak * 0.95

            # Write output
            import soundfile as sf

            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Transpose if needed (DAWDreamer outputs channels x samples)
            if audio.ndim == 2 and audio.shape[0] <= 2:
                audio = audio.T

            sf.write(str(output_path), audio, config.sample_rate)

            render_time = time.perf_counter() - t0
            duration_sec = len(audio) / config.sample_rate

            self._logger.info("   ✓ Complete: %s (%.1fs)", output_path.name, duration_sec)

            return RenderResult(
                success=True,
                output_path=output_path,
                duration=duration_sec,
                renderer=self.name,
                metadata={
                    "render_time": render_time,
                    "vst3": vst_path.stem,
                    "sample_rate": config.sample_rate,
                },
            )

        except Exception as e:
            self._logger.exception("DAWDreamer render failed: %s", e)
            return RenderResult(
                success=False,
                renderer=self.name,
                error=str(e),
            )

    async def render_synth(
        self,
        midi_path: Path,
        vst_path: Path,
        output_path: Path,
        preset_path: Path | None = None,
        params: dict[str, float] | None = None,
        sample_rate: int = 48000,
    ) -> RenderResult:
        """Convenience method for synthesizer rendering.

        Args:
            midi_path: Path to MIDI file
            vst_path: Path to VST3 plugin
            output_path: Output WAV path
            preset_path: Optional preset/state file
            params: Optional parameter overrides
            sample_rate: Output sample rate

        Returns:
            RenderResult
        """
        config = RenderConfig(
            sample_rate=sample_rate,
            extra={
                "vst3_path": vst_path,
                "preset_path": preset_path,
                "params": params or {},
            },
        )
        return await self.render(midi_path, output_path, config)


# =============================================================================
# Factory and Registration
# =============================================================================


_renderer: DAWDreamerRenderer | None = None


async def get_dawdreamer_renderer() -> DAWDreamerRenderer:
    """Get or create the DAWDreamer renderer singleton."""
    global _renderer
    if _renderer is None:
        _renderer = DAWDreamerRenderer()
        await _renderer.initialize()
    return _renderer


def _register() -> None:
    """Register the DAWDreamer renderer."""
    try:
        register_renderer(DAWDreamerRenderer())
    except Exception:
        pass  # DAWDreamer may not be installed


_register()


__all__ = [
    "DAWDreamerRenderer",
    "VST3Info",
    "find_vst3_plugins",
    "get_dawdreamer_renderer",
]
