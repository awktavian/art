"""REAPER Project Generator — Simple project creation for BBC SO rendering.

Generates REAPER project files with auto-generated RFX chains.
Uses the rfxchain_generator module to create BBC SO state files on demand.

IMPORTANT: BBC Symphony Orchestra requires special render handling:
- Uses 1x offline render mode (not full-speed) so samples can stream
- Larger media buffers for sample streaming
- RFXChains are generated automatically with proper BBC SO configuration

Usage:
    from kagami.core.effectors.renderers.reaper_project import (
        generate_reaper_project,
        render_project_headless,
        get_rfxchain_path,
    )

Colony: Forge (e₂)
Created: January 2, 2026
Updated: January 2, 2026 - Auto-generate RFXChains via rfxchain_generator
"""

from __future__ import annotations

import logging
import subprocess
import uuid
from pathlib import Path

from kagami.core.effectors.bbc_instruments import BBC_CATALOG
from kagami.core.effectors.rfxchain_generator import (
    RFXCHAIN_DIR as _GENERATOR_RFXCHAIN_DIR,
)
from kagami.core.effectors.rfxchain_generator import (
    get_rfxchain_path as _generator_get_rfxchain_path,
)

logger = logging.getLogger(__name__)

# =============================================================================
# Constants
# =============================================================================

REAPER_APP = Path("/Applications/REAPER.app/Contents/MacOS/REAPER")
RFXCHAIN_DIR = _GENERATOR_RFXCHAIN_DIR  # Use generator's directory

# Map BBC_CATALOG keys to RFXChain file names
# This handles naming differences and provides fallbacks for ensemble variants
FILE_MAP = {
    # ==========================================================================
    # STRINGS - Direct and ensemble mappings
    # ==========================================================================
    "celli": "cellos",
    "celli_leader": "cellos",  # Leader uses section chain
    "bass_leader": "basses",  # Leader uses section chain
    "viola_leader": "violas",  # Leader uses section chain
    "violin_1_leader": "violins_1",  # Leader uses section chain
    "violin_2_leader": "violins_2",  # Leader uses section chain
    # ==========================================================================
    # WOODWINDS - Solo to section mappings
    # ==========================================================================
    "flute": "flutes",
    "flutes_a3": "flutes",  # a3 ensemble uses same chain
    "oboe": "oboes",
    "oboes_a3": "oboes",  # a3 ensemble uses same chain
    "clarinet": "clarinets",
    "clarinets_a3": "clarinets",  # a3 ensemble uses same chain
    "bassoon": "bassoons",
    "bassoons_a3": "bassoons",  # a3 ensemble uses same chain
    "cor_anglais": "oboes",  # Cor anglais → oboes (similar register)
    "contrabassoon": "bassoons",  # Contrabassoon → bassoons (same family)
    "bass_clarinet": "clarinets",  # Bass clarinet → clarinets (same family)
    "contrabass_clarinet": "clarinets",  # Contrabass → clarinets
    "bass_flute": "flutes",  # Bass flute → flutes (same family)
    # ==========================================================================
    # BRASS - Solo to section mappings
    # ==========================================================================
    "horn": "horns",
    "horns_a4": "horns",  # a4 ensemble uses same chain
    "trumpet": "trumpets",
    "trumpets_a2": "trumpets",  # a2 ensemble uses same chain
    "tenor_trombone": "trombones_tenor",
    "tenor_trombones_a3": "trombones_tenor",  # a3 ensemble uses same chain
    "bass_trombones_a2": "trombones_bass",  # a2 bass trombones
    "contrabass_trombone": "trombones_bass",  # Contrabass → bass trombones
    "cimbasso": "tuba",  # Cimbasso → tuba (similar register)
    "contrabass_tuba": "tuba",  # Contrabass tuba → tuba
    # ==========================================================================
    # PERCUSSION - Tuned percussion mappings
    # ==========================================================================
    "vibraphone": "marimba",  # Vibraphone → marimba (similar mallet)
    "crotales": "glockenspiel",  # Crotales → glockenspiel (similar register)
    # ==========================================================================
    # PERCUSSION - Untuned percussion → specific chains
    # ==========================================================================
    "untuned_percussion": "snare_drum",  # Default untuned → snare
}

# Map untuned percussion articulations to specific RFXChain files
UNTUNED_PERCUSSION_MAP = {
    "Anvil": "anvil",
    "Bass Drum 1": "bass_drum",
    "Bass Drum 2": "bass_drum",
    "Cymbal": "suspended_cymbal",
    "Hits": "snare_drum",
    "Military Drum": "snare_drum",
    "Piatti": "piatti",
    "Snare 1": "snare_drum",
    "Snare 2": "snare_drum",
    "Tam Tam": "tam_tam",
    "Tambourine": "tambourine",
    "Tenor Drum": "tenor_drum",
    "Toys": "woodblock",
    "Triangle": "triangle",
}


# =============================================================================
# RFX Chain Lookup
# =============================================================================


def get_rfxchain_path(instrument_key: str) -> Path:
    """Get path to RfxChain file for an instrument.

    Auto-generates RFXChains using the rfxchain_generator module.
    Falls back to legacy manual files if they exist.

    Args:
        instrument_key: Key from BBC_CATALOG (e.g., "violins_1", "celli", "horn")

    Returns:
        Path to .RfxChain file

    Raises:
        ValueError: If instrument_key not in BBC_CATALOG
    """
    # Delegate to the generator module
    return _generator_get_rfxchain_path(instrument_key)


def get_all_instrument_keys() -> list[str]:
    """Get all available instrument keys from BBC_CATALOG."""
    return list(BBC_CATALOG.keys())


def get_available_rfxchains() -> list[str]:
    """Get instrument keys that have available RfxChain files."""
    available = []
    for key in BBC_CATALOG:
        try:
            get_rfxchain_path(key)
            available.append(key)
        except FileNotFoundError:
            pass
    return available


def get_instrument_mapping_status() -> dict[str, dict]:
    """Get detailed mapping status for all instruments.

    Returns dict with keys:
        - available: list of instrument keys with RFXChains
        - missing: list of instrument keys without RFXChains
        - mappings: dict of instrument_key -> rfxchain_file
        - fallbacks: dict of instrument_key -> fallback_used
    """
    available = []
    missing = []
    mappings = {}
    fallbacks = {}

    for key in BBC_CATALOG:
        try:
            path = get_rfxchain_path(key)
            available.append(key)
            rfx_name = path.stem
            mappings[key] = rfx_name

            # Track if using a fallback
            if key in FILE_MAP and FILE_MAP[key] != key:
                fallbacks[key] = FILE_MAP[key]
        except FileNotFoundError:
            missing.append(key)

    return {
        "available": available,
        "missing": missing,
        "mappings": mappings,
        "fallbacks": fallbacks,
        "total_catalog": len(BBC_CATALOG),
        "total_available": len(available),
        "coverage_percent": len(available) / len(BBC_CATALOG) * 100,
    }


# =============================================================================
# REAPER Project Generation
# =============================================================================


def _midi_to_reaper_events(midi_path: Path) -> str:
    """Convert MIDI file to REAPER inline event format.

    REAPER uses inline hex events in the format:
        E <tick> <status> <data1> <data2>

    Example:
        E 0 90 3c 64    # Note on, C4, velocity 100
        E 480 80 3c 00  # Note off, C4

    Args:
        midi_path: Path to MIDI file

    Returns:
        String of REAPER event lines
    """
    import pretty_midi

    midi = pretty_midi.PrettyMIDI(str(midi_path))
    events = []

    # REAPER uses 960 ticks per quarter note
    ticks_per_beat = 960

    # Add initial CC events (volume, pan)
    events.append("E 0 b0 07 64")  # CC7 volume = 100
    events.append("E 0 b0 0a 40")  # CC10 pan = center

    # Get tempo - try estimate_tempo first, fall back to 120 BPM for single-note files
    try:
        tempo_bpm = midi.estimate_tempo()
    except ValueError:
        # Single-note files can't estimate tempo, use default
        tempo_bpm = 120.0

    # Collect all note events with their tick times
    for instrument in midi.instruments:
        for note in instrument.notes:
            # Convert seconds to ticks
            start_tick = int(note.start * tempo_bpm / 60 * ticks_per_beat)
            end_tick = int(note.end * tempo_bpm / 60 * ticks_per_beat)

            # Note on: 9n pp vv (n=channel, pp=pitch, vv=velocity)
            events.append(f"E {start_tick} 90 {note.pitch:02x} {note.velocity:02x}")

            # Note off: 8n pp 00
            events.append(f"E {end_tick} 80 {note.pitch:02x} 00")

    # Sort events by tick time
    def event_tick(e: str) -> int:
        parts = e.split()
        return int(parts[1])

    events.sort(key=event_tick)

    return "\n        ".join(events)


def _read_rfxchain_content(rfxchain_path: Path) -> str:
    """Read and return RFXChain file content for embedding.

    Args:
        rfxchain_path: Path to .RfxChain file

    Returns:
        Content of the RFXChain file
    """
    return rfxchain_path.read_text()


def generate_reaper_project(
    midi_path: Path | None,
    tracks: list[tuple[str, str, float]],
    output_dir: Path,
    output_name: str,
    tempo: float = 120.0,
    duration: float | None = None,
    split_midi_paths: dict[str, Path] | None = None,
) -> Path:
    """Generate REAPER project file with BBC instrument tracks.

    CRITICAL: This function embeds MIDI events inline and FX chain content
    directly in the project file. REAPER CLI mode does not support:
    - RENDER_SRATE / RENDER_CHANNELS tokens
    - External MIDI file references via <X path>
    - <INCLUDE> directive for FX chains

    Args:
        midi_path: Path to MIDI file (used if split_midi_paths not provided)
        tracks: List of (track_name, instrument_key, pan)
        output_dir: Output directory
        output_name: Base name for output
        tempo: Project tempo
        duration: Duration in seconds (auto-detected if None)
        split_midi_paths: Dict mapping instrument_key to per-track MIDI path.
            Each track gets its own MIDI file for correct instrument separation.

    Returns:
        Path to generated .rpp file
    """
    import pretty_midi

    # Auto-detect duration from MIDI
    if duration is None:
        try:
            ref_path = midi_path
            if split_midi_paths:
                ref_path = next(iter(split_midi_paths.values()))
            if ref_path:
                midi = pretty_midi.PrettyMIDI(str(ref_path))
                duration = midi.get_end_time() + 2
            else:
                duration = 60.0
        except Exception:
            duration = 60.0

    output_dir.mkdir(parents=True, exist_ok=True)
    project_path = output_dir / f"{output_name}.rpp"

    colors = [16576, 21760, 26880, 31744, 16711680, 255, 65280, 16711935]
    track_blocks = []

    for i, (track_name, instrument_key, pan) in enumerate(tracks):
        rfxchain_path = get_rfxchain_path(instrument_key)

        # CRITICAL: Use per-track MIDI if available
        if split_midi_paths and instrument_key in split_midi_paths:
            track_midi_path = split_midi_paths[instrument_key]
        else:
            track_midi_path = midi_path
            logger.warning(
                "Track %s using shared MIDI (no split file for %s)",
                track_name,
                instrument_key,
            )

        # Convert MIDI to inline events (REAPER CLI doesn't support external refs)
        midi_events = _midi_to_reaper_events(track_midi_path)

        # Read FX chain content for embedding (REAPER CLI doesn't support INCLUDE)
        fxchain_content = _read_rfxchain_content(rfxchain_path)

        # Build track with embedded MIDI and FX chain
        track_block = f"""  <TRACK
    NAME "{track_name}"
    PEAKCOL {colors[i % len(colors)]}
    BEAT -1
    AUTOMODE 0
    VOLPAN 1 {pan} -1 -1 1
    MUTESOLO 0 0 0
    IPHASE 0
    ISBUS 0 0
    BUSCOMP 0 0
    SHOWINMIX 1 0.6667 0.5 1 0.5 0 0 0
    FREEMODE 0
    SEL 1
    REC 0 0 1 0 0 0 0
    VU 2
    TRACKHEIGHT 0 0 0
    INQ 0 0 0 0.5 100 0 0 100
    NCHAN 2
    FX 1
    TRACKID {{{uuid.uuid4()}}}
    PERF 0
    MIDIOUT -1
    MAINSEND 1 0
    <FXCHAIN
      WNDRECT 0 0 0 0
      SHOW 0
      LASTSEL 0
      DOCKED 0
{fxchain_content}
    >
    <ITEM
      POSITION 0
      SNAPOFFS 0
      LENGTH {duration}
      LOOP 0
      ALLTAKES 0
      FADEIN 1 0 0 1 0 0
      FADEOUT 1 0.5 0 1 0 0
      MUTE 0
      SEL 1
      IGUID {{{uuid.uuid4()}}}
      IID {i + 1}
      NAME "{track_name}"
      VOLPAN 1 0 1 -1
      SOFFS 0
      PLAYRATE 1 1 0 -1 0 0.0025
      CHANMODE 0
      GUID {{{uuid.uuid4()}}}
      <SOURCE MIDI
        HASDATA 1 960 QN
        {midi_events}
        <X
        >
        GUID {{{uuid.uuid4()}}}
        IGNTEMPO 0
        SRCCOLOR 0
        VELLANE -1 100 0
        CFGEDITVIEW 0 0.0625 96 12 0 -1 0 0 0 0.5
        KEYSNAP 0
        TRACKSEL 0
        EVTFILTER 0 -1 -1 -1 -1 0 0 0 0 -1 -1 -1 -1 0 -1 0 -1 -1
        CFGEDIT 1 1 0 1 1 0 1 1 1 1 1 0.0625 -1 0 0 0 0 0 1 64
      >
    >
  >"""
        track_blocks.append(track_block)

    # Generate project matching REAPER's native format
    # NO RENDER_SRATE or RENDER_CHANNELS - not supported in CLI mode
    # RENDER_1X 1 = render at 1x speed (critical for BBC SO sample streaming)
    project = f"""<REAPER_PROJECT 0.1 "7.0" 1704067200
  RIPPLE 0
  GROUPOVERRIDE 0 0 0
  AUTOXFADE 1
  ENVATTACH 1
  MIXERUIFLAGS 11 48
  PEAKGAIN 1
  FEEDBACK 0
  PANLAW 1
  PROJOFFS 0 0 0
  MAXPROJLEN 0 600
  GRID 3199 8 1 8 1 0 0 0
  TIMEMODE 1 5 -1 30 0 0 -1
  VIDEO_CONFIG 0 0 256
  PANMODE 3
  CURSOR 0
  ZOOM 100 0 0
  VZOOMEX 6 0
  USE_REC_CFG 0
  RECMODE 1
  SMPTESYNC 0 30 100 40 1000 300 0 0 1 0 0
  LOOP 0
  LOOPGRAN 0 4
  RECORD_PATH "" ""
  <RECORD_CFG
  >
  <APPLYFX_CFG
  >
  RENDER_FILE "{output_dir}/{output_name}.wav"
  RENDER_PATTERN ""
  RENDER_FMT 0 2 0
  RENDER_1X 1
  RENDER_RANGE 2 0 {duration} 18 1000
  RENDER_RESAMPLE 3 0 1
  RENDER_ADDTOPROJ 0
  RENDER_STEMS 0
  RENDER_DITHER 0
  TIMELOCKMODE 1
  TEMPOENVLOCKMODE 1
  ITEMMIX 0
  DEFPITCHMODE 589824 0
  TEMPO {tempo} 4 4
  PLAYRATE 1 0 0.25 4
  MASTERAUTOMODE 0
  MASTERTRACKHEIGHT 0 0
  MASTERPEAKCOL 16576
  MASTERMUTESOLO 0
  MASTERTRACKVIEW 0 0.6667 0.5 0.5 0 0 0 0 0 0
  MASTERHWOUT 0 0 1 0 0 0 0 -1
  MASTER_NCH 2 2
  MASTER_VOLUME 1 0 -1 -1 1
  MASTER_PANMODE 3
  MASTER_FX 1
  MASTER_SEL 0
{chr(10).join(track_blocks)}
>"""

    project_path.write_text(project)
    logger.info("Generated REAPER project: %s (%d tracks)", project_path.name, len(tracks))
    return project_path


# =============================================================================
# Headless Rendering
# =============================================================================


def render_project_headless(
    project_path: Path,
    timeout: int = 300,
    parallel_safe: bool = True,
    background: bool = True,
    sample_preload_wait: float = 3.0,
    auto_dismiss_dialogs: bool = True,
) -> tuple[bool, str | None]:
    """Render a REAPER project without GUI/focus stealing.

    For sample libraries like BBC Symphony Orchestra:
    - The project uses RENDER_1X 1 for 1x offline render (samples can stream)
    - We wait for sample preloading before checking completion
    - Timeout should account for real-time rendering plus preload

    Uses optimized CLI flags:
    - nosplash: Skip splash screen
    - newinst: New instance (safe for parallel rendering)
    - renderproject: Render and exit immediately
    - nice: Lower CPU priority

    On macOS with background=True, uses AppleScript to:
    1. Launch REAPER hidden
    2. Auto-dismiss any blocking dialogs
    3. Wait for render completion
    4. Quit REAPER

    Args:
        project_path: Path to .rpp project file
        timeout: Render timeout in seconds (should be > duration for 1x render)
        parallel_safe: If True, use -newinst for parallel rendering
        background: If True, minimize GUI disruption (uses AppleScript)
        sample_preload_wait: Seconds to wait for sample library preloading
        auto_dismiss_dialogs: If True, auto-click OK/Yes on REAPER dialogs

    Returns:
        Tuple of (success, error_message)
    """
    if not REAPER_APP.exists():
        return False, f"REAPER not found at {REAPER_APP}"

    if not project_path.exists():
        return False, f"Project not found: {project_path}"

    logger.info("Rendering: %s (1x offline, background=%s)", project_path.name, background)

    # Build REAPER arguments
    reaper_args = ["-nosplash"]
    if parallel_safe:
        reaper_args.append("-newinst")
    reaper_args.extend(["-renderproject", str(project_path)])

    # AppleScript to aggressively hide REAPER - prevent focus stealing
    hide_script = """
    tell application "System Events"
        try
            -- Hide REAPER completely
            set visible of application process "REAPER" to false
            -- Also set it to background
            tell process "REAPER"
                set frontmost to false
            end tell
        end try
    end tell
    """

    # AppleScript to launch REAPER hidden from the start
    launch_hidden_script = f"""
    do shell script "open -a 'REAPER' -g --args {" ".join(reaper_args)}"
    delay 0.5
    tell application "System Events"
        set visible of application process "REAPER" to false
    end tell
    """

    # AppleScript to auto-dismiss any REAPER dialogs by clicking default button
    dismiss_dialog_script = """
    tell application "System Events"
        tell process "REAPER"
            try
                -- Click OK, Yes, or default button on any sheet/dialog
                if exists sheet 1 of window 1 then
                    click button 1 of sheet 1 of window 1
                else if exists window 1 then
                    set allButtons to buttons of window 1
                    repeat with btn in allButtons
                        set btnName to name of btn
                        if btnName is "OK" or btnName is "Yes" or btnName is "Continue" or btnName is "Don't Save" then
                            click btn
                            exit repeat
                        end if
                    end repeat
                end if
            end try
        end tell
    end tell
    """

    cmd = [
        "nice",
        "-n",
        "10",
        str(REAPER_APP),
        *reaper_args,
    ]

    try:
        import threading
        import time

        # Start REAPER hidden using open -g (background, no activation)
        if background:
            # Use 'open' command with -g flag to prevent activation
            open_cmd = [
                "open",
                "-g",  # Don't bring to foreground
                "-a",
                str(REAPER_APP.parent.parent.parent),  # REAPER.app
                "--args",
                *reaper_args,
            ]
            proc = subprocess.Popen(
                open_cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
            )
        else:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
            )

        # Give it a moment to start, then hide it aggressively
        time.sleep(0.5)
        if background:
            # Hide multiple times to ensure it stays hidden
            for _ in range(3):
                subprocess.run(
                    ["osascript", "-e", hide_script],
                    capture_output=True,
                    timeout=5,
                )
                time.sleep(0.2)

        # Dialog dismissal loop (runs in background thread)
        dialog_dismiss_stop = threading.Event()

        def dismiss_dialogs_loop():
            """Periodically try to dismiss REAPER dialogs."""
            while not dialog_dismiss_stop.is_set():
                try:
                    subprocess.run(
                        ["osascript", "-e", dismiss_dialog_script],
                        capture_output=True,
                        timeout=2,
                    )
                except Exception:
                    pass
                time.sleep(1.0)  # Check every second

        if auto_dismiss_dialogs:
            dismiss_thread = threading.Thread(target=dismiss_dialogs_loop, daemon=True)
            dismiss_thread.start()

        # Wait for sample preloading (BBC SO needs time to load samples)
        if sample_preload_wait > 0:
            logger.debug("   Waiting %.1fs for sample preloading...", sample_preload_wait)
            time.sleep(sample_preload_wait)

        # Wait for render to complete
        # Note: With RENDER_1X 1, render takes approximately real-time
        proc.wait(timeout=timeout)

        # Stop dialog dismissal thread
        dialog_dismiss_stop.set()

        return True, None

    except subprocess.TimeoutExpired:
        dialog_dismiss_stop.set() if "dialog_dismiss_stop" in dir() else None
        proc.kill()
        return False, f"Render timeout ({timeout}s) - try increasing timeout for long pieces"
    except Exception as e:
        if "dialog_dismiss_stop" in dir():
            dialog_dismiss_stop.set()
        return False, str(e)


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "FILE_MAP",
    "REAPER_APP",
    "RFXCHAIN_DIR",
    "UNTUNED_PERCUSSION_MAP",
    "generate_reaper_project",
    "get_all_instrument_keys",
    "get_available_rfxchains",
    "get_instrument_mapping_status",
    "get_rfxchain_path",
    "render_project_headless",
]
