"""Sheet Music Generator — MIDI to Notation (LilyPond/PDF/MusicXML).

Generate publication-quality sheet music from MIDI files using LilyPond.
Supports multiple output formats and automatic part extraction.

Pipeline:
    MIDI → music21 analysis → LilyPond → PDF/PNG/MusicXML

Usage:
    from kagami.forge.modules.audio.sheet_music import generate_sheet_music

    result = await generate_sheet_music(
        "symphony.mid",
        title="Symphony in C",
        composer="Kagami",
        output_format="pdf"
    )

Colony: Forge (e₂)
Created: January 2, 2026
"""

from __future__ import annotations

import asyncio
import logging
import shutil
import tempfile
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================


class OutputFormat(Enum):
    """Sheet music output format."""

    PDF = "pdf"  # Publication-quality PDF
    PNG = "png"  # Image (for display)
    MUSICXML = "musicxml"  # Interchange format
    LILYPOND = "ly"  # Raw LilyPond source


class PaperSize(Enum):
    """Paper size for PDF output."""

    LETTER = "letter"
    A4 = "a4"
    TABLOID = "tabloid"  # For orchestral scores


class ScoreLayout(Enum):
    """Score layout type."""

    FULL_SCORE = "full"  # All parts on one page
    PIANO_REDUCTION = "piano"  # Reduced to piano
    PARTS = "parts"  # Individual parts
    LEAD_SHEET = "lead"  # Melody + chords


@dataclass
class SheetMusicConfig:
    """Sheet music generation configuration."""

    # Metadata
    title: str = "Untitled"
    composer: str = "Kagami"
    arranger: str | None = None
    opus: str | None = None
    dedication: str | None = None

    # Layout
    output_format: OutputFormat = OutputFormat.PDF
    paper_size: PaperSize = PaperSize.LETTER
    layout: ScoreLayout = ScoreLayout.FULL_SCORE

    # Notation options
    include_tempo: bool = True
    include_dynamics: bool = True
    include_articulations: bool = True
    include_lyrics: bool = False

    # Part names (override auto-detected)
    part_names: dict[int, str] = field(default_factory=dict)

    # Formatting
    staff_size: int = 18  # Points (14-26 typical)
    system_count: int | None = None  # Auto if None
    page_count: int | None = None  # Auto if None

    # LilyPond options
    lilypond_version: str = "2.24.0"
    include_midi_output: bool = False


@dataclass
class SheetMusicResult:
    """Result of sheet music generation."""

    success: bool
    output_path: Path | None = None
    format: OutputFormat = OutputFormat.PDF
    pages: int = 0
    parts: int = 0
    measures: int = 0
    lilypond_source: str | None = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


# =============================================================================
# MIDI Analysis
# =============================================================================


@dataclass
class PartInfo:
    """Information about a MIDI part/track."""

    track_index: int
    name: str
    channel: int
    program: int  # GM program number
    note_count: int
    lowest_pitch: int
    highest_pitch: int
    is_percussion: bool
    suggested_clef: str
    instrument_family: str


def analyze_midi(midi_path: Path) -> tuple[list[PartInfo], dict[str, Any]]:
    """Analyze MIDI file to extract part information.

    Args:
        midi_path: Path to MIDI file

    Returns:
        Tuple of (part infos, metadata dict)
    """
    import pretty_midi

    midi = pretty_midi.PrettyMIDI(str(midi_path))
    parts = []

    for i, inst in enumerate(midi.instruments):
        if not inst.notes:
            continue

        pitches = [n.pitch for n in inst.notes]
        lowest = min(pitches)
        highest = max(pitches)

        # Determine clef based on range
        avg_pitch = sum(pitches) / len(pitches)
        if inst.is_drum:
            clef = "percussion"
        elif avg_pitch < 48:  # Below C3
            clef = "bass"
        elif avg_pitch > 72:  # Above C5
            clef = "treble^8"  # Octave treble
        else:
            clef = "treble"

        # Instrument family from GM program
        family = _get_instrument_family(inst.program)

        parts.append(
            PartInfo(
                track_index=i,
                name=inst.name or f"Part {i + 1}",
                channel=inst.notes[0].pitch if inst.notes else 0,  # Approximate
                program=inst.program,
                note_count=len(inst.notes),
                lowest_pitch=lowest,
                highest_pitch=highest,
                is_percussion=inst.is_drum,
                suggested_clef=clef,
                instrument_family=family,
            )
        )

    # Metadata
    tempo_changes = midi.get_tempo_changes()
    tempo = int(tempo_changes[1][0]) if tempo_changes[1].size > 0 else 120

    time_sig = midi.time_signature_changes
    if time_sig:
        time_signature = f"{time_sig[0].numerator}/{time_sig[0].denominator}"
    else:
        time_signature = "4/4"

    key_sig = midi.key_signature_changes
    if key_sig:
        key = _midi_key_to_name(key_sig[0].key_number)
    else:
        key = "C major"

    metadata = {
        "tempo": tempo,
        "time_signature": time_signature,
        "key": key,
        "duration": midi.get_end_time(),
        "total_notes": sum(p.note_count for p in parts),
    }

    return parts, metadata


def _get_instrument_family(program: int) -> str:
    """Get instrument family from GM program number."""
    if program < 8:
        return "Piano"
    elif program < 16:
        return "Chromatic Percussion"
    elif program < 24:
        return "Organ"
    elif program < 32:
        return "Guitar"
    elif program < 40:
        return "Bass"
    elif program < 48:
        return "Strings"
    elif program < 56:
        return "Ensemble"
    elif program < 64:
        return "Brass"
    elif program < 72:
        return "Reed"
    elif program < 80:
        return "Pipe"
    elif program < 88:
        return "Synth Lead"
    elif program < 96:
        return "Synth Pad"
    elif program < 104:
        return "Synth Effects"
    elif program < 112:
        return "Ethnic"
    elif program < 120:
        return "Percussive"
    else:
        return "Sound Effects"


def _midi_key_to_name(key_number: int) -> str:
    """Convert MIDI key number to key name."""
    keys = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
    return f"{keys[key_number % 12]} major"


# =============================================================================
# LilyPond Generation
# =============================================================================


def midi_to_lilypond(
    midi_path: Path,
    config: SheetMusicConfig,
    parts: list[PartInfo],
    metadata: dict[str, Any],
) -> str:
    """Convert MIDI to LilyPond source code.

    Args:
        midi_path: Path to MIDI file
        config: Sheet music configuration
        parts: Analyzed part information
        metadata: MIDI metadata

    Returns:
        LilyPond source code string
    """
    import pretty_midi

    midi = pretty_midi.PrettyMIDI(str(midi_path))

    # Build LilyPond header
    ly_source = f'''\\version "{config.lilypond_version}"

\\header {{
  title = "{config.title}"
  composer = "{config.composer}"
'''

    if config.arranger:
        ly_source += f'  arranger = "{config.arranger}"\n'
    if config.opus:
        ly_source += f'  opus = "{config.opus}"\n'
    if config.dedication:
        ly_source += f'  dedication = "{config.dedication}"\n'

    ly_source += "}\n\n"

    # Paper settings
    ly_source += f'''\\paper {{
  #(set-paper-size "{config.paper_size.value}")
}}

\\layout {{
  \\context {{
    \\Score
    \\override SpacingSpanner.base-shortest-duration = #(ly:make-moment 1/16)
  }}
}}

'''

    # Generate each part
    part_vars = []
    for i, part_info in enumerate(parts):
        if i >= len(midi.instruments):
            continue

        inst = midi.instruments[i]
        if not inst.notes:
            continue

        # Get part name
        part_name = config.part_names.get(i, part_info.name)
        var_name = f"part{chr(65 + i)}"  # partA, partB, etc.
        part_vars.append((var_name, part_name, part_info))

        # Convert notes to LilyPond
        ly_notes = _notes_to_lilypond(inst.notes, metadata)

        # Determine clef
        clef = part_info.suggested_clef
        if clef == "percussion":
            clef_cmd = "\\clef percussion"
        else:
            clef_cmd = f"\\clef {clef}"

        ly_source += f"""{var_name} = \\relative c' {{
  {clef_cmd}
  \\key c \\major
  \\time {metadata.get("time_signature", "4/4")}
"""

        if config.include_tempo:
            ly_source += f"  \\tempo 4 = {metadata.get('tempo', 120)}\n"

        ly_source += f"  {ly_notes}\n}}\n\n"

    # Build score
    ly_source += "\\score {\n  <<\n"

    for var_name, part_name, part_info in part_vars:
        staff_type = "DrumStaff" if part_info.is_percussion else "Staff"
        ly_source += f'''    \\new {staff_type} \\with {{
      instrumentName = "{part_name}"
    }} {{ \\{var_name} }}
'''

    ly_source += "  >>\n"

    # Layout and MIDI blocks
    ly_source += "  \\layout { }\n"
    if config.include_midi_output:
        ly_source += "  \\midi { }\n"

    ly_source += "}\n"

    return ly_source


def _notes_to_lilypond(notes: list, metadata: dict) -> str:
    """Convert MIDI notes to LilyPond notation.

    This is a simplified conversion - full implementation would handle:
    - Proper rhythmic quantization
    - Tied notes
    - Rests
    - Beaming
    - Voice splitting
    """
    if not notes:
        return "R1"  # Whole rest

    # Sort by start time
    sorted_notes = sorted(notes, key=lambda n: n.start)

    # Quantize to sixteenth notes
    tempo = metadata.get("tempo", 120)
    beat_duration = 60.0 / tempo
    sixteenth = beat_duration / 4

    ly_notes = []
    current_time = 0.0

    pitch_names = ["c", "cis", "d", "dis", "e", "f", "fis", "g", "gis", "a", "ais", "b"]

    for note in sorted_notes[:200]:  # Limit for sanity
        # Calculate rest before note
        gap = note.start - current_time
        if gap > sixteenth * 2:
            rest_dur = _duration_to_lilypond(gap, beat_duration)
            ly_notes.append(f"r{rest_dur}")

        # Note pitch
        pitch_class = note.pitch % 12
        octave = note.pitch // 12 - 4  # LilyPond octave relative to middle C

        pitch_name = pitch_names[pitch_class]

        # Octave markers
        if octave > 0:
            pitch_name += "'" * octave
        elif octave < 0:
            pitch_name += "," * abs(octave)

        # Duration
        duration = note.end - note.start
        dur_str = _duration_to_lilypond(duration, beat_duration)

        ly_notes.append(f"{pitch_name}{dur_str}")
        current_time = note.end

    # Format with line breaks
    result = []
    for i, n in enumerate(ly_notes):
        result.append(n)
        if (i + 1) % 8 == 0:  # 8 notes per line
            result.append("\n  ")

    return " ".join(result)


def _duration_to_lilypond(duration: float, beat_duration: float) -> str:
    """Convert duration in seconds to LilyPond duration string."""
    # Duration relative to quarter note
    relative = duration / beat_duration

    if relative >= 4:
        return "1"  # Whole
    elif relative >= 2:
        return "2"  # Half
    elif relative >= 1:
        return "4"  # Quarter
    elif relative >= 0.5:
        return "8"  # Eighth
    elif relative >= 0.25:
        return "16"  # Sixteenth
    else:
        return "32"  # Thirty-second


# =============================================================================
# PDF Generation
# =============================================================================


async def compile_lilypond(
    ly_source: str,
    output_path: Path,
    output_format: OutputFormat,
) -> bool:
    """Compile LilyPond source to output format.

    Args:
        ly_source: LilyPond source code
        output_path: Output file path
        output_format: Desired output format

    Returns:
        True if compilation succeeded
    """
    # Check for LilyPond
    lilypond_path = shutil.which("lilypond")
    if not lilypond_path:
        logger.error("LilyPond not found. Install with: brew install lilypond")
        return False

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        ly_file = tmp / "score.ly"
        ly_file.write_text(ly_source)

        # Build command
        cmd = [lilypond_path]

        if output_format == OutputFormat.PNG:
            cmd.extend(["--png", "-dresolution=300"])
        elif output_format == OutputFormat.PDF:
            cmd.append("--pdf")

        cmd.extend(["-o", str(tmp / "score"), str(ly_file)])

        # Run LilyPond
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=tmpdir,
            )
            _stdout, stderr = await proc.communicate()

            if proc.returncode != 0:
                logger.error(f"LilyPond failed: {stderr.decode()}")
                return False

            # Find output file
            if output_format == OutputFormat.PNG:
                output_file = tmp / "score.png"
            else:
                output_file = tmp / "score.pdf"

            if output_file.exists():
                # Copy to destination
                output_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(output_file, output_path)
                return True
            else:
                logger.error(f"Output file not created: {output_file}")
                return False

        except Exception as e:
            logger.error(f"LilyPond execution failed: {e}")
            return False


async def export_musicxml(midi_path: Path, output_path: Path) -> bool:
    """Export MIDI to MusicXML using music21.

    Args:
        midi_path: Input MIDI file
        output_path: Output MusicXML file

    Returns:
        True if export succeeded
    """
    try:
        from music21 import converter

        score = converter.parse(str(midi_path))
        score.write("musicxml", str(output_path))
        return True

    except ImportError:
        logger.error("music21 not installed. Install with: pip install music21")
        return False
    except Exception as e:
        logger.error(f"MusicXML export failed: {e}")
        return False


# =============================================================================
# Main Generator
# =============================================================================


class SheetMusicGenerator:
    """Generate sheet music from MIDI files.

    Converts MIDI to publication-quality scores using LilyPond.
    Supports multiple output formats and automatic part extraction.
    """

    def __init__(self, config: SheetMusicConfig | None = None):
        self.config = config or SheetMusicConfig()
        self._lilypond_available: bool | None = None

    async def check_dependencies(self) -> dict[str, bool]:
        """Check for required dependencies."""
        deps = {}

        # LilyPond
        deps["lilypond"] = shutil.which("lilypond") is not None

        # music21
        try:
            import music21  # noqa: F401

            deps["music21"] = True
        except ImportError:
            deps["music21"] = False

        # pretty_midi
        try:
            import pretty_midi  # noqa: F401

            deps["pretty_midi"] = True
        except ImportError:
            deps["pretty_midi"] = False

        self._lilypond_available = deps["lilypond"]
        return deps

    async def generate(
        self,
        midi_path: Path | str,
        output_path: Path | str | None = None,
    ) -> SheetMusicResult:
        """Generate sheet music from MIDI file.

        Args:
            midi_path: Input MIDI file path
            output_path: Output path (auto-generated if None)

        Returns:
            SheetMusicResult with output path and metadata
        """
        midi_path = Path(midi_path)

        if not midi_path.exists():
            return SheetMusicResult(
                success=False,
                error=f"MIDI file not found: {midi_path}",
            )

        # Check dependencies
        if self._lilypond_available is None:
            await self.check_dependencies()

        # Determine output path
        if output_path is None:
            suffix = f".{self.config.output_format.value}"
            output_path = midi_path.parent / f"{midi_path.stem}_score{suffix}"
        else:
            output_path = Path(output_path)

        try:
            # Analyze MIDI
            logger.info(f"🎼 Analyzing MIDI: {midi_path}")
            parts, metadata = analyze_midi(midi_path)

            if not parts:
                return SheetMusicResult(
                    success=False,
                    error="No playable parts found in MIDI",
                )

            logger.info(f"   Found {len(parts)} parts, {metadata['total_notes']} notes")

            # Handle different output formats
            if self.config.output_format == OutputFormat.MUSICXML:
                success = await export_musicxml(midi_path, output_path)
                if success:
                    return SheetMusicResult(
                        success=True,
                        output_path=output_path,
                        format=OutputFormat.MUSICXML,
                        parts=len(parts),
                        metadata=metadata,
                    )
                else:
                    return SheetMusicResult(
                        success=False,
                        error="MusicXML export failed",
                    )

            # Generate LilyPond source
            logger.info("   Generating LilyPond source...")
            ly_source = midi_to_lilypond(midi_path, self.config, parts, metadata)

            # Just return source if requested
            if self.config.output_format == OutputFormat.LILYPOND:
                output_path.write_text(ly_source)
                return SheetMusicResult(
                    success=True,
                    output_path=output_path,
                    format=OutputFormat.LILYPOND,
                    parts=len(parts),
                    lilypond_source=ly_source,
                    metadata=metadata,
                )

            # Compile to PDF/PNG
            if not self._lilypond_available:
                return SheetMusicResult(
                    success=False,
                    error="LilyPond not installed",
                    lilypond_source=ly_source,
                )

            logger.info(f"   Compiling to {self.config.output_format.value}...")
            success = await compile_lilypond(
                ly_source,
                output_path,
                self.config.output_format,
            )

            if success:
                logger.info(f"✓ Sheet music generated: {output_path}")
                return SheetMusicResult(
                    success=True,
                    output_path=output_path,
                    format=self.config.output_format,
                    parts=len(parts),
                    lilypond_source=ly_source,
                    metadata=metadata,
                )
            else:
                return SheetMusicResult(
                    success=False,
                    error="LilyPond compilation failed",
                    lilypond_source=ly_source,
                )

        except Exception as e:
            logger.error(f"Sheet music generation failed: {e}", exc_info=True)
            return SheetMusicResult(
                success=False,
                error=str(e),
            )


# =============================================================================
# API Functions
# =============================================================================

_generator: SheetMusicGenerator | None = None


def get_sheet_music_generator(
    config: SheetMusicConfig | None = None,
) -> SheetMusicGenerator:
    """Get or create sheet music generator singleton."""
    global _generator
    if _generator is None or config is not None:
        _generator = SheetMusicGenerator(config)
    return _generator


async def generate_sheet_music(
    midi_path: Path | str,
    output_path: Path | str | None = None,
    title: str = "Untitled",
    composer: str = "Kagami",
    output_format: str | OutputFormat = "pdf",
    **kwargs,
) -> SheetMusicResult:
    """Generate sheet music from MIDI file.

    This is the main API for sheet music generation.

    Args:
        midi_path: Input MIDI file
        output_path: Output path (auto-generated if None)
        title: Score title
        composer: Composer name
        output_format: Output format (pdf, png, musicxml, ly)
        **kwargs: Additional SheetMusicConfig options

    Returns:
        SheetMusicResult with output path and metadata

    Examples:
        # Basic PDF generation
        result = await generate_sheet_music("symphony.mid", title="Symphony No. 1")

        # PNG for display
        result = await generate_sheet_music(
            "melody.mid",
            output_format="png",
            title="Simple Melody"
        )

        # MusicXML for interchange
        result = await generate_sheet_music(
            "score.mid",
            output_format="musicxml"
        )
    """
    # Parse output format
    if isinstance(output_format, str):
        output_format = OutputFormat(output_format.lower())

    # Build config
    config = SheetMusicConfig(
        title=title,
        composer=composer,
        output_format=output_format,
        **kwargs,
    )

    generator = get_sheet_music_generator(config)
    return await generator.generate(midi_path, output_path)


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Enums
    "OutputFormat",
    "PaperSize",
    # Analysis
    "PartInfo",
    "ScoreLayout",
    # Config
    "SheetMusicConfig",
    # Generator
    "SheetMusicGenerator",
    # Result
    "SheetMusicResult",
    "analyze_midi",
    "compile_lilypond",
    "export_musicxml",
    "generate_sheet_music",
    "get_sheet_music_generator",
    # Low-level
    "midi_to_lilypond",
]
