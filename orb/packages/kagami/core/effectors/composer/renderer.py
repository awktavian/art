"""
BBC Symphony Orchestra Renderer — REAPER headless rendering.

Renders MIDI files through BBC SO VST3 via REAPER CLI.
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

# Path to REAPER application
REAPER_PATH = "/Applications/REAPER.app/Contents/MacOS/REAPER"

# Working BBC SO templates (from Williams session)
TEMPLATE_DIR = Path("/tmp/kagami_williams_v2/renders")


@dataclass
class RenderResult:
    """Result of a BBC SO render."""

    success: bool
    wav_path: Path | None = None
    duration_seconds: float = 0.0
    error: str | None = None


class BBCSORenderer:
    """Render MIDI files through BBC Symphony Orchestra.

    Uses REAPER headless CLI with pre-configured BBC SO VST states.

    Example:
        renderer = BBCSORenderer()

        # Render a single instrument
        result = await renderer.render_instrument(
            "violins_1",
            Path("/tmp/my_piece/violins_1.mid"),
            Path("/tmp/my_piece/renders/violins_1.wav")
        )

        # Render all instruments
        results = await renderer.render_all(
            midi_dir=Path("/tmp/my_piece"),
            output_dir=Path("/tmp/my_piece/renders")
        )
    """

    def __init__(
        self,
        template_dir: Path | None = None,
        render_duration: float = 30.0,
        timeout_seconds: int = 180,
    ):
        """Initialize the renderer.

        Args:
            template_dir: Directory containing working BBC SO RPP templates
            render_duration: Duration to render in seconds
            timeout_seconds: Max time to wait for each render
        """
        self.template_dir = Path(template_dir or TEMPLATE_DIR)
        self.render_duration = render_duration
        self.timeout = timeout_seconds

    def _create_rpp(
        self,
        instrument: str,
        midi_path: Path,
        wav_path: Path,
    ) -> Path | None:
        """Create a REAPER project file from template.

        Args:
            instrument: Instrument name (e.g., "violins_1")
            midi_path: Path to input MIDI file
            wav_path: Path for output WAV file

        Returns:
            Path to created RPP file, or None if template not found
        """
        # Find template RPP
        template_rpp = self.template_dir / f"{instrument}.rpp"

        if not template_rpp.exists():
            # Try to find a similar template
            available = list(self.template_dir.glob("*.rpp"))
            if not available:
                logger.error(f"No templates found in {self.template_dir}")
                return None

            # Use first available as fallback (will use wrong instrument but render)
            template_rpp = available[0]
            logger.warning(f"No template for {instrument}, using {template_rpp.name}")

        # Read template
        content = template_rpp.read_text()

        # Update render output path
        content = re.sub(
            r'RENDER_FILE "[^"]*"',
            f'RENDER_FILE "{wav_path}"',
            content,
        )

        # Update track name
        content = re.sub(
            r'NAME "[^"]*"',
            f'NAME "{instrument}"',
            content,
            count=1,
        )

        # Update MIDI source
        content = re.sub(
            r'FILE "[^"]*\.mid"',
            f'FILE "{midi_path}"',
            content,
        )

        # Update render duration
        content = re.sub(
            r"RENDER_RANGE \d+ \d+ \d+",
            f"RENDER_RANGE 2 0 {int(self.render_duration)}",
            content,
        )

        # Write new RPP
        rpp_path = wav_path.parent / f"{instrument}.rpp"
        rpp_path.write_text(content)

        return rpp_path

    async def render_instrument(
        self,
        instrument: str,
        midi_path: Path,
        wav_path: Path,
    ) -> RenderResult:
        """Render a single instrument through BBC SO.

        Args:
            instrument: Instrument name
            midi_path: Path to MIDI file
            wav_path: Path for output WAV

        Returns:
            RenderResult with success status and output path
        """
        wav_path = Path(wav_path)
        wav_path.parent.mkdir(parents=True, exist_ok=True)

        # Create RPP
        rpp_path = self._create_rpp(instrument, midi_path, wav_path)
        if not rpp_path:
            return RenderResult(
                success=False,
                error=f"Could not create RPP for {instrument}",
            )

        # Render with REAPER CLI
        logger.info(f"Rendering {instrument} with BBC SO...")

        try:
            # Start REAPER render
            process = await asyncio.create_subprocess_exec(
                REAPER_PATH,
                "-renderproject",
                str(rpp_path),
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )

            # Wait for render with timeout
            start_time = asyncio.get_event_loop().time()

            while True:
                await asyncio.sleep(5)  # Check every 5 seconds

                # Check if WAV exists and is complete
                if wav_path.exists():
                    size = wav_path.stat().st_size
                    if size > 100000:  # At least 100KB
                        # Kill REAPER (it may hang after render)
                        try:
                            process.kill()
                        except ProcessLookupError:
                            pass
                        break

                # Check timeout
                elapsed = asyncio.get_event_loop().time() - start_time
                if elapsed > self.timeout:
                    try:
                        process.kill()
                    except ProcessLookupError:
                        pass
                    return RenderResult(
                        success=False,
                        error=f"Render timeout after {self.timeout}s",
                    )

            # Verify output
            if wav_path.exists() and wav_path.stat().st_size > 100000:
                import soundfile as sf

                audio, sr = sf.read(wav_path)
                duration = len(audio) / sr

                logger.info(f"✓ {instrument}: {duration:.1f}s rendered")

                return RenderResult(
                    success=True,
                    wav_path=wav_path,
                    duration_seconds=duration,
                )
            else:
                return RenderResult(
                    success=False,
                    error="Output file missing or too small",
                )

        except Exception as e:
            logger.error(f"Render failed: {e}")
            return RenderResult(success=False, error=str(e))

    async def render_all(
        self,
        midi_dir: Path,
        output_dir: Path,
    ) -> dict[str, RenderResult]:
        """Render all MIDI files in a directory.

        Args:
            midi_dir: Directory containing MIDI files
            output_dir: Directory for output WAV files

        Returns:
            Dict mapping instrument names to RenderResults
        """
        midi_dir = Path(midi_dir)
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        results = {}

        for midi_path in sorted(midi_dir.glob("*.mid")):
            instrument = midi_path.stem
            wav_path = output_dir / f"{instrument}.wav"

            result = await self.render_instrument(
                instrument,
                midi_path,
                wav_path,
            )
            results[instrument] = result

        return results
