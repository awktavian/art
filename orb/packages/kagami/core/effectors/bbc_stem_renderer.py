"""BBC Symphony Orchestra Stem Renderer — Robust Rendering with GUI.

BBC Symphony Orchestra has specific requirements:
1. Samples must be preloaded (takes 30-60 seconds)
2. Renders at 1x realtime (no faster-than-realtime)
3. Works best with GUI visible (headless can fail)

This module provides reliable rendering with:
- Proper sample preloading
- AppleScript automation for render triggering
- Audio verification
- Cache preservation

Created: January 6, 2026
"""

from __future__ import annotations

import logging
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from kagami.core.effectors.audio_verification import analyze_wav, check_audio_exists

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# =============================================================================
# Constants
# =============================================================================

REAPER_APP = Path("/Applications/REAPER.app/Contents/MacOS/REAPER")

# BBC SO sample preload time (seconds)
# Strings and large ensembles need more time
SAMPLE_PRELOAD_FAST = 20  # Small instruments
SAMPLE_PRELOAD_NORMAL = 30  # Most instruments
SAMPLE_PRELOAD_SLOW = 45  # Large ensembles (violins, celli)

# Render buffer after piece duration
RENDER_BUFFER = 30

# Instruments that need extra preload time
SLOW_LOAD_INSTRUMENTS = {
    "violins_1",
    "violins_2",
    "violas",
    "celli",
    "basses",
    "horns_a4",
}


# =============================================================================
# AppleScript Templates
# =============================================================================

APPLESCRIPT_TRIGGER_RENDER = """
tell application "REAPER"
    activate
end tell

delay 1

tell application "System Events"
    tell process "REAPER"
        -- Cmd+Alt+R to open render dialog
        keystroke "r" using {command down, option down}
    end tell
end tell

delay 2

tell application "System Events"
    tell process "REAPER"
        -- Click "Render 1 file" button
        try
            click button "Render 1 file" of window "Render to File"
        on error
            -- Fallback: press Enter
            keystroke return
        end try
    end tell
end tell
"""

APPLESCRIPT_CLOSE_PROJECT = """
tell application "System Events"
    tell process "REAPER"
        keystroke "w" using command down
        delay 0.5
        -- Don't save changes
        try
            keystroke return
        end try
    end tell
end tell
"""

APPLESCRIPT_CLOSE_RENDER_DIALOG = """
tell application "System Events"
    tell process "REAPER"
        try
            -- Close the "Finished in X:XX" render complete dialog
            click button "Close" of window 1
        on error
            try
                -- Fallback: click any Close button
                repeat with w in windows
                    if name of w contains "Finished" then
                        click button "Close" of w
                    end if
                end repeat
            end try
        end try
    end tell
end tell
"""

APPLESCRIPT_HIDE_REAPER = """
tell application "System Events"
    try
        set visible of application process "REAPER" to false
    end try
end tell
"""


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class BBCRenderConfig:
    """Configuration for BBC SO rendering."""

    sample_preload_time: int = SAMPLE_PRELOAD_NORMAL
    render_buffer: int = RENDER_BUFFER
    piece_duration: float = 360.0  # Default 6 minutes
    hide_reaper: bool = False  # Keep visible for reliability
    verify_audio: bool = True
    max_retries: int = 2
    play_preview: bool = True  # Play 5s preview after render
    preview_duration: float = 5.0  # Preview duration in seconds


# =============================================================================
# Core Functions
# =============================================================================


def get_preload_time(instrument_key: str) -> int:
    """Get appropriate preload time for an instrument.

    Args:
        instrument_key: BBC instrument key

    Returns:
        Preload time in seconds
    """
    if instrument_key in SLOW_LOAD_INSTRUMENTS:
        return SAMPLE_PRELOAD_SLOW
    return SAMPLE_PRELOAD_NORMAL


def run_applescript(script: str, timeout: float = 30.0) -> bool:
    """Run an AppleScript.

    Args:
        script: AppleScript code
        timeout: Timeout in seconds

    Returns:
        True if successful
    """
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.returncode == 0
    except Exception as e:
        logger.warning("AppleScript failed: %s", e)
        return False


def open_reaper_project(rpp_path: Path) -> bool:
    """Open a REAPER project.

    Args:
        rpp_path: Path to .rpp file

    Returns:
        True if successful
    """
    try:
        result = subprocess.run(
            ["open", "-a", "REAPER", str(rpp_path)],
            capture_output=True,
            timeout=30,
        )
        return result.returncode == 0
    except Exception as e:
        logger.error("Failed to open REAPER: %s", e)
        return False


def render_stem_gui(
    stem_name: str,
    rpp_path: Path,
    wav_path: Path,
    config: BBCRenderConfig | None = None,
) -> tuple[bool, str]:
    """Render a stem using REAPER GUI with AppleScript.

    This is the most reliable method for BBC SO:
    1. Open project in REAPER GUI
    2. Wait for samples to load
    3. Trigger render via keystroke
    4. Wait for render to complete
    5. Verify output

    Args:
        stem_name: Name of the stem
        rpp_path: Path to REAPER project
        wav_path: Expected output path
        config: Render configuration

    Returns:
        Tuple of (success, error_message)
    """
    if config is None:
        config = BBCRenderConfig()

    if not rpp_path.exists():
        return False, f"RPP not found: {rpp_path}"

    # Get appropriate preload time
    preload_time = get_preload_time(stem_name)
    if config.sample_preload_time:
        preload_time = config.sample_preload_time

    logger.info(
        "Rendering %s (preload=%ds, duration=%.0fs)", stem_name, preload_time, config.piece_duration
    )

    # Delete existing output
    if wav_path.exists():
        wav_path.unlink()

    # Open project
    if not open_reaper_project(rpp_path):
        return False, "Failed to open REAPER"

    # Wait for samples to load
    logger.debug("Waiting %ds for sample preload...", preload_time)
    time.sleep(preload_time)

    # Hide REAPER if requested
    if config.hide_reaper:
        run_applescript(APPLESCRIPT_HIDE_REAPER)

    # Trigger render
    logger.debug("Triggering render...")
    if not run_applescript(APPLESCRIPT_TRIGGER_RENDER, timeout=10):
        return False, "Failed to trigger render"

    # Wait for render to complete
    # BBC SO renders at 1x realtime
    render_time = config.piece_duration + config.render_buffer
    logger.debug("Waiting %.0fs for render...", render_time)

    # Monitor for completion
    start = time.time()
    while time.time() - start < render_time:
        time.sleep(5)

        # Check if output exists and is complete
        if wav_path.exists():
            size1 = wav_path.stat().st_size
            time.sleep(2)
            if wav_path.exists():
                size2 = wav_path.stat().st_size
                if size1 == size2 and size1 > 10_000_000:  # >10MB and stable
                    logger.debug("Render complete (%.1fMB)", size1 / 1024 / 1024)
                    break

    # Close render complete dialog
    run_applescript(APPLESCRIPT_CLOSE_RENDER_DIALOG, timeout=5)
    time.sleep(0.5)

    # Close project
    run_applescript(APPLESCRIPT_CLOSE_PROJECT, timeout=5)
    time.sleep(1)

    # Verify output
    if not wav_path.exists():
        return False, "No output file created"

    if config.verify_audio:
        if not check_audio_exists(wav_path):
            return False, "Output file is silent"

    # Play preview if enabled
    if config.play_preview and wav_path.exists():
        play_audio_preview(wav_path, config.preview_duration)

    return True, ""


def play_audio_preview(wav_path: Path, duration: float = 5.0) -> None:
    """Play a short preview of the rendered audio.

    Args:
        wav_path: Path to WAV file
        duration: Preview duration in seconds
    """
    try:
        # Use afplay on macOS
        proc = subprocess.Popen(
            ["afplay", str(wav_path)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(duration)
        proc.terminate()
        logger.info("▶ Played %.1fs preview of %s", duration, wav_path.name)
    except Exception as e:
        logger.debug("Preview failed: %s", e)


def render_stem_with_retry(
    stem_name: str,
    rpp_path: Path,
    wav_path: Path,
    config: BBCRenderConfig | None = None,
) -> tuple[bool, str]:
    """Render a stem with retries.

    Args:
        stem_name: Name of the stem
        rpp_path: Path to REAPER project
        wav_path: Expected output path
        config: Render configuration

    Returns:
        Tuple of (success, error_message)
    """
    if config is None:
        config = BBCRenderConfig()

    max_retries = config.max_retries
    last_error = ""

    for attempt in range(max_retries + 1):
        if attempt > 0:
            logger.warning("Retry %d/%d for %s", attempt, max_retries, stem_name)
            # Increase preload time on retry
            config.sample_preload_time = min(
                config.sample_preload_time + 15,
                90,
            )

        success, error = render_stem_gui(stem_name, rpp_path, wav_path, config)
        if success:
            return True, ""
        last_error = error

    return False, f"Failed after {max_retries + 1} attempts: {last_error}"


async def render_stems_sequential(
    stems: list[tuple[str, Path, Path]],
    config: BBCRenderConfig | None = None,
    on_progress: callable | None = None,
) -> dict[str, tuple[bool, str]]:
    """Render multiple stems sequentially.

    Args:
        stems: List of (stem_name, rpp_path, wav_path) tuples
        config: Render configuration
        on_progress: Optional callback(stem_name, index, total)

    Returns:
        Dict mapping stem_name to (success, error)
    """
    import asyncio

    results = {}

    for i, (stem_name, rpp_path, wav_path) in enumerate(stems):
        if on_progress:
            on_progress(stem_name, i + 1, len(stems))

        # Run in executor to not block
        loop = asyncio.get_event_loop()
        success, error = await loop.run_in_executor(
            None,
            render_stem_with_retry,
            stem_name,
            rpp_path,
            wav_path,
            config,
        )

        results[stem_name] = (success, error)

        if success:
            metrics = analyze_wav(wav_path)
            logger.info(
                "✓ %s: peak=%d rms=%.0f (%.1fdB)",
                stem_name,
                metrics.peak,
                metrics.rms,
                metrics.peak_db,
            )
        else:
            logger.error("✗ %s: %s", stem_name, error)

    return results


# =============================================================================
# Factory Function for StemManager Integration
# =============================================================================


def create_bbc_render_func(config: BBCRenderConfig | None = None):
    """Create a render function for use with StemManager.

    Args:
        config: BBC render configuration

    Returns:
        Callable suitable for StemManager.render_stem
    """
    if config is None:
        config = BBCRenderConfig()

    def render_func(stem_name: str, rpp_path: Path, wav_path: Path) -> tuple[bool, str]:
        return render_stem_with_retry(stem_name, rpp_path, wav_path, config)

    return render_func


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "RENDER_BUFFER",
    "SAMPLE_PRELOAD_FAST",
    "SAMPLE_PRELOAD_NORMAL",
    "SAMPLE_PRELOAD_SLOW",
    "BBCRenderConfig",
    "create_bbc_render_func",
    "get_preload_time",
    "render_stem_gui",
    "render_stem_with_retry",
    "render_stems_sequential",
]
